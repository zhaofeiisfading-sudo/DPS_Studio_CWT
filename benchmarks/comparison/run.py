"""Full TASK004 run. No external data writes, tuning or history mutations."""

import csv
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import tomllib
import traceback
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from pdv_cwt.mapping import load_config
from pdv_cwt.readers import audit_file
from pdv_cwt.safety import ROOT, checked_path, sha256

from .cases import CALIBRATION_SEEDS, EVALUATION_SEEDS, RATES, case_specs, make_case
from .core import CWT_CONFIG, METHODS, STFTConfig, analyze, pair_native
from .metrics import case_metrics, frequency_metrics
from .plots import comparison_plots, overview
from .storage import (
    array_hash,
    load_analysis,
    output_path,
    raw_inventory,
    run_isolated,
    save_analysis,
    write_csv,
    write_json,
)


def snapshot(run: Path) -> dict[str, Any]:
    source_paths = sorted(
        p
        for folder in ("src", "tests", "benchmarks", "configs", "scripts")
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and p.suffix in (".py", ".toml", ".ps1")
    )
    source_paths += [
        ROOT / p
        for p in (
            "AGENTS.md",
            "pyproject.toml",
            ".gitignore",
            "docs/TASK-CWT-004_PROTOCOL.md",
        )
    ]
    hashes = {}
    for source in source_paths:
        checked_path(source, ROOT)
        relative = source.relative_to(ROOT)
        target = output_path(run / "source_snapshot" / relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(source.read_bytes())
        hashes[relative.as_posix()] = sha256(source)
    git = {
        cmd: subprocess.check_output(["git", *cmd.split()], text=True, cwd=ROOT).strip()
        for cmd in ("rev-parse HEAD", "branch --show-current", "status --short", "remote -v")
    }
    packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    environment = dict(
        python=sys.version,
        executable=sys.executable,
        platform=platform.platform(),
        processor=platform.processor(),
        logical_cpus=os.cpu_count(),
        packages=packages,
        thread_environment={
            k: os.environ.get(k)
            for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
        },
    )
    record = dict(
        git=git,
        environment=environment,
        source_sha256=hashes,
        cwt=asdict(CWT_CONFIG),
        balanced=asdict(STFTConfig()),
        high_time=asdict(STFTConfig(512, 384)),
    )
    write_json(run / "source_environment.json", record)
    return record


def performance_row(record: dict[str, Any], **identity: Any) -> dict[str, Any]:
    fields = (
        "method",
        "samples",
        "sampling_period_s",
        "transform_s",
        "strongest_s",
        "analysis_s",
        "reader_s",
        "export_s",
        "worker_wall_s",
        "peak_working_set_bytes",
        "output_candidate_count",
        "coefficient_shape",
        "coefficient_bytes",
        "preflight_memory_bytes",
        "time_sha256",
        "voltage_sha256",
        "status",
    )
    return dict(**identity, **{k: record.get(k) for k in fields})


def previous_consistency(file: str, channel: str, directory: Path) -> dict[str, Any]:
    previous = ROOT / "artifacts/TASK-CWT-003/real_runs/run_20261030_143512_d623e95b"
    with (previous / "batch_summary.csv").open(encoding="utf-8", newline="") as handle:
        prior = next(
            r for r in csv.DictReader(handle) if r["file"] == file and r["channel"] == channel
        )
    old_directory = ROOT / prior["output_path"]
    with np.load(directory / "cwt/native.npz") as loaded:
        new_time, new_freq = loaded["time_s"], loaded["frequency_hz"]
    with (old_directory / "candidate_velocity.csv").open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        freq_key = next(k for k in reader.fieldnames if "frequency" in k and "hz" in k.lower())
        pairs = np.array([(float(r["time_s"]), float(r[freq_key])) for r in reader])
    old_time, old_freq = pairs[:, 0], pairs[:, 1]
    metadata = json.loads((old_directory / "metadata.json").read_text(encoding="utf-8"))
    same = dict(
        prior_directory=str(old_directory.relative_to(ROOT)),
        source_sha256=metadata["source_sha256"],
        time_exact_equal=bool(np.array_equal(new_time, old_time)),
        candidate_exact_equal=bool(np.array_equal(new_freq, old_freq)),
        config_equal=metadata["cwt_config"] == asdict(CWT_CONFIG),
        performance="historical timing NOT used",
    )
    return same


def descriptive_windows(
    file: str,
    paired: dict[str, Any],
    t0: float,
    duration: float,
) -> list[dict[str, Any]]:
    windows = [
        ("first_third", 0.0, duration / 3),
        ("middle_third", duration / 3, 2 * duration / 3),
        ("last_third", 2 * duration / 3, duration),
    ]
    if file == "20260607.csv":
        windows += [
            ("TASK003_posthoc_before", 0, 0.6e-6),
            ("TASK003_posthoc_band", 0.75e-6, 1.25e-6),
        ]
    if file == "ch3.csv":
        windows += [("TASK003_posthoc_before", 0, 1e-6), ("TASK003_posthoc_band", 1.08e-6, 1.30e-6)]
    rows = []
    for name, lo, hi in windows:
        t = paired["cwt_time_s"] - t0
        mask = (t >= lo) & (t < hi)
        for method in METHODS:

            def median(key: str, name: str = method, selected: Any = mask) -> float | None:
                v = paired[f"{name}_{key}"][selected]
                return float(np.median(v)) if v.size else None

            rows.append(
                dict(
                    window=name,
                    exploratory=True,
                    method=method,
                    low_relative_s=lo,
                    high_relative_s=hi,
                    frames=int(mask.sum()),
                    peak_median_v=median("peak"),
                    frequency_median_hz=median("frequency_hz"),
                    band_background_median_v=median("median"),
                    peak_to_background_median=median("peak_to_median"),
                    label_status="NOT independent presence/noise labels",
                )
            )
    return rows


def real_run(run: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    config = load_config(ROOT / "configs/real_batch.toml")
    inventory = raw_inventory()
    write_json(run / "raw_before.json", inventory)
    audit = []
    channels: list[dict[str, Any]] = []
    performance = []
    summaries = []
    for entry in inventory:
        mapping = config.mappings.get(entry["path"])
        record = audit_file(config.raw_root / entry["path"], mapping, config.max_input_bytes)
        record["path"] = entry["path"]
        audit.append(record)
    write_json(run / "input_inventory.json", audit)
    expected = set(config.mappings)
    found = {e["path"] for e in inventory if e["path"] != ".gitkeep"}
    write_json(
        run / "input_differences.json",
        dict(added=sorted(found - expected), missing=sorted(expected - found)),
    )
    for item in audit:
        if item["status"] != "READY":
            continue
        mapping = config.mappings[item["path"]]
        for channel in mapping.channels:
            ordinal = len(channels)
            slug = f"{Path(mapping.path).stem}_{channel.name}"
            directory = output_path(run / "real" / slug)
            directory.mkdir(parents=True, exist_ok=False)
            row: dict[str, Any] = dict(
                file=mapping.path,
                channel=channel.name,
                directory=directory.relative_to(run).as_posix(),
                methods={},
            )
            order = METHODS[ordinal % 3 :] + METHODS[: ordinal % 3]
            for method in order:
                request = dict(
                    kind="real",
                    method=method,
                    mapping=asdict(mapping),
                    channel=channel.name,
                    rows=item["data_rows"],
                    sha256=item["sha256_before"],
                    output=str(directory / method),
                )
                request_path = directory / f"{method}.request.json"
                write_json(request_path, request)
                status = run_isolated(request_path)
                row["methods"][method] = status["status"]
                performance.append(
                    performance_row(
                        status,
                        kind="real",
                        file=mapping.path,
                        channel=channel.name,
                        order=list(order),
                    )
                )
                print(
                    f"real {ordinal + 1}/14 {mapping.path}/{channel.name} {method}: "
                    f"{status['status']}",
                    flush=True,
                )
            if all(s == "COMPLETED" for s in row["methods"].values()):
                try:
                    analyses = {m: load_analysis(directory / m) for m in METHODS}
                    samples = analyses["cwt"].metadata["samples"]
                    paired = pair_native(analyses, samples)
                    hashes = {
                        (a.metadata["time_sha256"], a.metadata["voltage_sha256"])
                        for a in analyses.values()
                    }
                    if len(hashes) != 1:
                        raise ValueError("methods received different input samples")
                    np.savez_compressed(directory / "common_grid.npz", **paired)
                    write_csv(
                        directory / "common_grid.csv",
                        [
                            {k: v[i] for k, v in paired.items()}
                            for i in range(paired["sample_index"].size)
                        ],
                    )
                    plots = comparison_plots(
                        directory, f"{mapping.path}/{channel.name}", analyses, paired
                    )
                    t0 = float(analyses["cwt"].native["time_s"][0])
                    duration = float(analyses["cwt"].native["time_s"][-1] - t0)
                    observations = descriptive_windows(mapping.path, paired, t0, duration)
                    write_csv(directory / "exploratory_windows.csv", observations)
                    row["prior_cwt_consistency"] = previous_consistency(
                        mapping.path, channel.name, directory
                    )
                    for method in METHODS:
                        a = analyses[method]
                        n = a.native
                        mask = paired["common_interior"]
                        metrics = frequency_metrics(
                            paired[f"{method}_frequency_hz"],
                            np.full(mask.size, np.nan),
                            np.full(mask.size, np.nan),
                            paired[f"{method}_time_s"],
                            mask,
                        )
                        metrics.pop("rmse_hz")
                        metrics.pop("mae_hz")
                        metrics.pop("bias_hz")
                        metrics.pop("wrong_branch_rate")
                        native_metrics = frequency_metrics(
                            n["frequency_hz"],
                            np.full(n["time_s"].size, np.nan),
                            np.full(n["time_s"].size, np.nan),
                            n["time_s"],
                            ~n["bank_edge"],
                        )
                        summaries.append(
                            dict(
                                file=mapping.path,
                                channel=channel.name,
                                method=method,
                                samples=samples,
                                native_candidates=n["time_s"].size,
                                common_frames=mask.size,
                                common_interior_frames=int(mask.sum()),
                                common_interior_jump_rate=metrics["jump_over_500mhz_rate"],
                                native_interior_jump_rate=native_metrics["jump_over_500mhz_rate"],
                                median_frequency_hz=float(np.median(n["frequency_hz"])),
                                median_peak_response_v=float(np.median(n["peak"])),
                                bank_edge_fraction=float(np.mean(n["bank_edge"])),
                                selected_edge_fraction=float(np.mean(n["selected_edge"])),
                                alias_fraction=float(np.mean(n["alias_risk"])),
                                quality="UNKNOWN",
                                ground_truth="UNKNOWN; no real error metrics",
                                background_normalization="NOT AVAILABLE",
                                near_floor_fraction=a.metadata["display"][
                                    "near_black_fraction_below_1pct_full_max"
                                ],
                                record_reference_v=plots[method]["record_reference_v"],
                                common_median_abs_difference_from_cwt_hz=float(
                                    np.median(
                                        np.abs(
                                            paired[f"{method}_frequency_hz"][mask]
                                            - paired["cwt_frequency_hz"][mask]
                                        )
                                    )
                                ),
                            )
                        )
                    row["paired_outputs"] = "COMPLETED"
                    del analyses
                except Exception:
                    row["paired_outputs"] = "FAILED"
                    row["error"] = traceback.format_exc()
            channels.append(row)
            write_json(run / f"real_progress_{len(channels):02d}.json", row)
    write_csv(run / "real_comparison_summary.csv", summaries)
    write_json(run / "channel_index.json", channels)
    overview(run, channels)
    return channels, performance, audit


def calibrate(run: Path) -> dict[str, dict[str, float]]:
    calibration = output_path(run / "calibration")
    calibration.mkdir()
    thresholds: dict[str, dict[str, float]] = {}
    for fs in RATES:
        values: dict[str, list[Any]] = {m: [] for m in METHODS}
        for seed in CALIBRATION_SEEDS:
            case = make_case(dict(group="calibration", fs=fs, seed=seed, sigma=1), seed)
            analyses = {m: analyze(case.signal, m) for m in METHODS}
            common = pair_native(analyses, case.signal.time_s.size)
            for method in METHODS:
                values[method].append(common[f"{method}_peak"][common["common_interior"]])
            np.savez_compressed(calibration / f"fs{int(fs / 1e9)}_seed{seed}.npz", **common)
            del analyses
        key = str(int(fs))
        thresholds[key] = {
            m: float(np.quantile(np.concatenate(v), 0.99)) for m, v in values.items()
        }
        print(f"calibration fs{fs / 1e9:g} frozen: {thresholds[key]}", flush=True)
    write_json(
        calibration / "thresholds.json",
        dict(
            thresholds=thresholds,
            calibration_seeds=CALIBRATION_SEEDS,
            evaluation_seeds=EVALUATION_SEEDS,
            target_frame_fpr=0.01,
            quantile_method="linear",
            domain="E/sigma on common interior; fixed before evaluation; not record FPR",
        ),
    )
    return thresholds


def synthetic_run(run: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    thresholds = calibrate(run)
    specs = case_specs()
    write_json(run / "synthetic_registry.json", specs)
    assert len(specs) == 156
    metrics: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    provenance = []
    for ordinal, spec in enumerate(specs):
        case = make_case(spec, ordinal)
        output = output_path(run / "synthetic" / case.name)
        output.mkdir(parents=True)
        try:
            np.savez_compressed(
                output / "signal_truth.npz",
                time_s=case.signal.time_s,
                voltage_v=case.signal.voltage_v,
                truth_hz=case.truth_hz,
                interference_hz=case.interference_hz,
                active=case.active,
                phase_rad=case.phase_rad,
            )
            evidence = dict(
                case=case.name,
                recipe=case.recipe,
                time_sha256=array_hash(case.signal.time_s),
                voltage_sha256=array_hash(case.signal.voltage_v),
            )
            provenance.append(evidence)
            write_json(output / "recipe_hashes.json", evidence)
            analyses = {m: analyze(case.signal, m) for m in METHODS}
            common = pair_native(analyses, case.signal.time_s.size)
            key = str(int(spec["fs"]))
            case_rows = case_metrics(case, analyses, common, thresholds[key])
            metrics.extend(case_rows)
            np.savez_compressed(output / "common_grid.npz", **common)
            write_json(output / "metrics.json", case_rows)
            for method, analysis in analyses.items():
                analysis.metadata["performance_scope"] = "shared process; peak NOT comparable"
                save_analysis(output / method, analysis, native_csv=False, max_display=512)
            del analyses, analysis
        except Exception:
            failures.append(dict(case=case.name, error=traceback.format_exc()))
            write_json(output / "failure.json", failures[-1])
        if (ordinal + 1) % 6 == 0:
            print(f"synthetic {ordinal + 1}/{len(specs)}; failures={len(failures)}", flush=True)
    write_csv(run / "synthetic_comparison_metrics.csv", metrics)
    write_json(run / "synthetic_metrics.json", metrics)
    write_json(run / "synthetic_provenance.json", provenance)
    write_json(run / "synthetic_failures.json", failures)
    return metrics, failures


def synthetic_performance(run: Path) -> list[dict[str, Any]]:
    rows = []
    perf = output_path(run / "performance")
    perf.mkdir()
    for fs in RATES:
        for method in METHODS:
            request = perf / f"fs{int(fs / 1e9)}_{method}.request.json"
            write_json(
                request,
                dict(
                    kind="synthetic_performance",
                    method=method,
                    fs_hz=fs,
                    samples=int(80000 * fs / 40e9),
                    save=False,
                ),
            )
            record = run_isolated(request)
            rows.append(performance_row(record, kind="synthetic_fresh_process", fs_hz=fs))
    return rows


def main() -> None:
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], text=True, cwd=ROOT
    ).strip()
    if branch != "research/cwt-morlet":
        raise RuntimeError("branch mismatch; stop")
    config = tomllib.loads((ROOT / "configs/task_cwt004.toml").read_text(encoding="utf-8"))
    assert tuple(config["calibration_seeds"]) == CALIBRATION_SEEDS
    assert tuple(config["evaluation_seeds"]) == EVALUATION_SEEDS
    assert config["evaluation_cases"] == len(case_specs())
    # Use fixed UTC+08:00 explicitly, independent of the execution host timezone.
    stamp_text = (datetime.now(UTC) + timedelta(hours=8)).strftime("%Y%m%d_%H%M%S")
    run = output_path(ROOT / "artifacts/TASK-CWT-004" / f"run_{stamp_text}_{uuid.uuid4().hex[:8]}")
    run.mkdir()
    start = time.perf_counter()
    source = snapshot(run)
    write_json(
        run / "run_started.json",
        dict(status="IN PROGRESS", config=config, timestamp_cst=stamp_text),
    )
    print(f"RUN_DIRECTORY={run}", flush=True)
    initial = json.loads(
        (ROOT / "artifacts/TASK-CWT-004/preflight.json").read_text(encoding="utf-8")
    )
    if raw_inventory() != initial["raw"]:
        raise RuntimeError("raw changed since initial preflight")
    channels, perf, inventory = real_run(run)
    metrics, failures = synthetic_run(run)
    perf += synthetic_performance(run)
    write_csv(run / "performance_comparison.csv", perf)
    final_raw = raw_inventory()
    write_json(run / "raw_after.json", final_raw)
    current_hashes = {p: sha256(ROOT / p) for p in source["source_sha256"]}
    write_json(
        run / "source_integrity.json",
        dict(
            exact_equal=current_hashes == source["source_sha256"],
            final=current_hashes,
        ),
    )
    write_json(
        run / "manifest.json",
        dict(
            task="TASK-CWT-004",
            run_id=run.name,
            elapsed_s=time.perf_counter() - start,
            raw_unchanged=final_raw == initial["raw"],
            files=len(inventory),
            channels=channels,
            synthetic_case_count=len(case_specs()),
            synthetic_metrics_rows=len(metrics),
            failures=failures,
            performance_rows=len(perf),
            protocol_sha256=source["source_sha256"]["docs/TASK-CWT-004_PROTOCOL.md"],
            source_version="source_environment.json + source_snapshot",
            scope="synthetic truth; real descriptive only; no optics, gating or repair",
        ),
    )
    print(f"COMPLETE={run}", flush=True)


if __name__ == "__main__":
    main()
