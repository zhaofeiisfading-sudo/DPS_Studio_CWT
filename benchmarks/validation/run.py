"""TASK005 phase-locked orchestration; exclusive new run with complete negative cases."""

import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import traceback
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from benchmarks.comparison.metrics import frequency_metrics
from pdv_cwt.frequency import CWTConfig, make_frequency_grid
from pdv_cwt.resources import memory_snapshot
from pdv_cwt.safety import ROOT, sha256

from .cases import RATES, make_case, registry
from .io import BASE, array_hash, output, raw_inventory, write_csv, write_json
from .scoring import METHODS, cwt, cwt_banks, detection, stft_bank, support


def profile_key(fs: float, model: str, voices: int = 24) -> str:
    return f"fs{round(fs / 1e9)}_{model}_v{voices}"


def calibration_job(spec: dict[str, Any]) -> dict[str, Any]:
    case = make_case(spec)
    result, elapsed = cwt(case.signal, 96)
    radius = int(result.grid.support_radius_samples.max())
    values = np.abs(result.coefficients[:, radius:-radius]) ** 2
    return dict(
        spec=spec,
        power=values.mean(axis=1),
        elapsed_s=elapsed,
        voltage_sha256=array_hash(case.signal.voltage_v),
    )


def calibrate_scores(run: Path) -> dict[str, list[float]]:
    rows = registry("cal_score")
    grouped: dict[str, list[Any]] = {}
    records = []
    with ProcessPoolExecutor(max_workers=2) as pool:
        for i, result in enumerate(pool.map(calibration_job, rows)):
            spec = result["spec"]
            grouped.setdefault(profile_key(spec["fs"], spec["model"], 96), []).append(
                result["power"]
            )
            records.append({k: v for k, v in result.items() if k != "power"})
            if (i + 1) % 10 == 0:
                print(f"score calibration {i + 1}/{len(rows)}", flush=True)
    profiles: dict[str, list[float]] = {}
    for fs in RATES:
        dense = make_frequency_grid(CWTConfig(voices_per_octave=96), 1 / fs)
        for model in ("white", "colored", "bandwidth"):
            rms = np.sqrt(np.mean(grouped[profile_key(fs, model, 96)], axis=0))
            for voices in (24, 48, 96):
                grid = make_frequency_grid(CWTConfig(voices_per_octave=voices), 1 / fs)
                indices = np.argmin(np.abs(dense.frequency_hz[:, None] - grid.frequency_hz), axis=0)
                np.testing.assert_allclose(
                    dense.frequency_hz[indices], grid.frequency_hz, rtol=1e-12
                )
                profiles[profile_key(fs, model, voices)] = rms[indices].tolist()
    write_json(run / "calibration/score_profiles.json", profiles)
    write_json(run / "calibration/score_records.json", records)
    return profiles


def evaluate_job(request: dict[str, Any]) -> dict[str, Any]:
    spec, profiles, thresholds = request["spec"], request["profiles"], request.get("thresholds", {})
    voices = request.get("voices", 24)
    path = Path(request["run"]) / spec["split"] / f"{spec['id']}_v{voices}"
    output(path / "placeholder")
    path.mkdir(exist_ok=True)
    try:
        case = make_case(spec)
        result, transform_s = cwt(case.signal, voices)
        rms = np.asarray(profiles[profile_key(spec["fs"], spec["model"], voices)])
        banks = cwt_banks(result, rms)
        banks["balanced"] = stft_bank(case.signal)
        banks["high_time"] = stft_bank(case.signal, True)
        centers = banks["A0"].centers
        times = case.signal.time_s[centers]
        interior = ~np.logical_or.reduce([b.edge for b in banks.values()])
        saved: dict[str, Any] = dict(
            sample_index=centers,
            time_s=times,
            interior=interior,
            truth_hz=case.truth[centers],
            interference_hz=case.interference[centers],
            active=case.active[centers],
            noise_sigma_v=case.sigma,
        )
        rows = []
        for method, bank in banks.items():
            assert np.array_equal(bank.centers, centers)
            prediction = bank.predicted
            sup = support(bank.score, bank.hz, case.truth[centers])
            saved[f"{method}_prediction"] = prediction
            saved[f"{method}_peak"] = bank.peak
            for key, values in sup.items():
                saved[f"{method}_support_{key}"] = values
            scope_masks = {"interior": interior & case.active[centers]}
            if spec["group"] == "chirp":
                width = spec["duration_ns"] * 1e-9
                scope_masks["event"] = (
                    interior & (times >= 200e-9 - width / 2) & (times < 200e-9 + width / 2)
                )
            if spec["group"] in ("amplitude", "fade", "burst"):
                scope_masks["event"] = interior & (times >= 180e-9) & (times < 220e-9)
            for scope, mask in scope_masks.items():
                row = dict(
                    case=spec["id"],
                    split=spec["split"],
                    seed=spec["seed"],
                    group=spec["group"],
                    fs_hz=spec["fs"],
                    band=spec["band"],
                    snr_db=spec["snr"],
                    noise=spec["model"],
                    duration_ns=spec["duration_ns"],
                    kind=spec.get("kind", ""),
                    frequency_hz=spec["frequency_hz"],
                    method=method,
                    voices=voices,
                    scope=scope,
                    realized_snr_db=case.recipe["realized_snr_db"],
                )
                row.update(
                    frequency_metrics(
                        prediction, case.truth[centers], case.interference[centers], times, mask
                    )
                )
                error = prediction[mask] - case.truth[centers][mask]
                if error.size:
                    row.update(
                        catastrophic_rate=float(np.mean(np.abs(error) > 1e9)),
                        truth_mean_hz=float(np.mean(case.truth[centers][mask])),
                        presence=float(np.mean(sup["presence"][mask])),
                        supported=float(np.mean(sup["supported"][mask])),
                        strongest_accuracy=float(np.mean(sup["strongest_accurate"][mask])),
                        top3_recall=float(np.mean(sup["top3"][mask])),
                        top5_recall=float(np.mean(sup["top5"][mask])),
                    )
                    present = mask & (sup["presence"] > 0)
                    failed = mask & (sup["strongest_accurate"] == 0)
                    row.update(
                        rank_median=float(np.median(sup["rank"][present]))
                        if present.any()
                        else None,
                        background_ratio_median=float(
                            np.median(sup["relative_background"][present])
                        )
                        if present.any()
                        else None,
                        failure_presence=float(np.mean(sup["presence"][failed]))
                        if failed.any()
                        else None,
                        failure_top5=float(np.mean(sup["top5"][failed])) if failed.any() else None,
                    )
                row.update(
                    low_selection_fraction=float(np.mean(prediction[interior] < 0.5e9)),
                    high_selection_fraction=float(np.mean(prediction[interior] >= 2e9)),
                )
                if thresholds and spec["group"] in ("pulse", "noise"):
                    key = profile_key(spec["fs"], spec["model"])
                    for control in ("frame", "record"):
                        value = thresholds[key][method][control]
                        diagnostic = detection(
                            bank.peak / case.sigma,
                            times,
                            case.active[centers],
                            interior,
                            value,
                            200e-9 if spec["group"] == "pulse" else None,
                        )
                        row.update({f"{control}_{k}": v for k, v in diagnostic.items()})
                rows.append(row)
        # A separate physical-window control, aligned by exact subset indexing.
        if spec["group"] == "chirp":
            for high_time in (False, True):
                physical = stft_bank(case.signal, high_time, True)
                positions = np.searchsorted(centers, physical.centers)
                assert np.array_equal(centers[positions], physical.centers)
                common = interior[positions] & ~physical.edge
                for label, prediction in (
                    (
                        "physical_high_time" if high_time else "physical_balanced",
                        physical.predicted,
                    ),
                    ("A0_physical", banks["A0"].predicted[positions]),
                    ("A1_physical", banks["A1"].predicted[positions]),
                    ("A2_physical", banks["A2"].predicted[positions]),
                ):
                    if label.endswith("physical") and high_time:
                        continue
                    saved[f"{label}_prediction"] = prediction
                    saved[f"{label}_sample_index"] = physical.centers
                    for scope in ("interior", "event"):
                        ptime = case.signal.time_s[physical.centers]
                        width = spec["duration_ns"] * 1e-9
                        mask = (
                            common
                            if scope == "interior"
                            else common
                            & (ptime >= 200e-9 - width / 2)
                            & (ptime < 200e-9 + width / 2)
                        )
                        row = {
                            k: v
                            for k, v in rows[0].items()
                            if k
                            in (
                                "case",
                                "split",
                                "seed",
                                "group",
                                "fs_hz",
                                "band",
                                "snr_db",
                                "noise",
                                "duration_ns",
                                "kind",
                                "frequency_hz",
                                "voices",
                                "realized_snr_db",
                            )
                        }
                        row.update(method=label, scope=scope)
                        row.update(
                            frequency_metrics(
                                prediction,
                                case.truth[physical.centers],
                                case.interference[physical.centers],
                                ptime,
                                mask,
                            )
                        )
                        rows.append(row)
        if request.get("cal_detect"):
            return dict(spec=spec, peaks={m: b.peak[interior] for m, b in banks.items()})
        np.savez_compressed(output(path / "common.npz"), **saved)
        write_json(
            path / "recipe.json",
            dict(
                case.recipe,
                time_sha256=array_hash(case.signal.time_s),
                voltage_sha256=array_hash(case.signal.voltage_v),
            ),
        )
        write_json(path / "metrics.json", rows)
        write_json(
            path / "timing.json",
            dict(
                cwt_s=transform_s,
                process_peak_bytes=memory_snapshot()["peak_working_set_bytes"],
                peak_scope="shared pool worker lifecycle; not independent case peak",
                coefficient_shape=result.coefficients.shape,
                coefficient_bytes=result.coefficients.nbytes,
            ),
        )
        return dict(rows=rows, transform_s=transform_s, status="COMPLETED")
    except Exception:
        failure = dict(spec=spec, voices=voices, error=traceback.format_exc(), status="FAILED")
        write_json(path / "failure.json", failure)
        return failure


def calibration_thresholds(run: Path, profiles: dict[str, list[float]]) -> dict[str, Any]:
    requests = [
        dict(spec=s, profiles=profiles, run=str(run), cal_detect=True)
        for s in registry("cal_detect")
    ]
    values: dict[str, dict[str, list[Any]]] = {}
    with ProcessPoolExecutor(max_workers=2) as pool:
        for i, record in enumerate(pool.map(evaluate_job, requests)):
            if record.get("status") == "FAILED":
                raise RuntimeError(record["error"])
            spec = record["spec"]
            key = profile_key(spec["fs"], spec["model"])
            for method, peaks in record["peaks"].items():
                values.setdefault(key, {}).setdefault(method, []).append(peaks)
            if (i + 1) % 20 == 0:
                print(f"threshold calibration {i + 1}/{len(requests)}", flush=True)
    thresholds = {
        key: {
            method: dict(
                frame=float(np.quantile(np.concatenate(records), 0.99)),
                record=float(
                    np.quantile([float(np.max(v)) for v in records], 0.95, method="higher")
                ),
                calibration_record_max=[float(np.max(v)) for v in records],
                calibration_frames=[np.asarray(v).tolist() for v in records],
            )
            for method, records in methods.items()
        }
        for key, methods in values.items()
    }
    write_json(run / "calibration/detection_thresholds.json", thresholds)
    return thresholds


def experiments(
    run: Path, split: str, profiles: dict[str, list[float]], thresholds: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requests = [
        dict(spec=s, run=str(run), profiles=profiles, thresholds=thresholds, voices=v)
        for s in registry(split)
        for v in ((24, 48, 96) if split == "grid" else (24,))
    ]
    rows, failures = [], []
    with ProcessPoolExecutor(max_workers=2) as pool:
        for i, result in enumerate(pool.map(evaluate_job, requests)):
            if result["status"] == "FAILED":
                failures.append(result)
            else:
                rows.extend(result["rows"])
            if (i + 1) % 20 == 0:
                print(f"{split} {i + 1}/{len(requests)} failures={len(failures)}", flush=True)
    write_csv(
        run / ("synthetic_metrics.csv" if split == "evaluation" else f"{split}_metrics.csv"), rows
    )
    write_json(run / f"{split}_failures.json", failures)
    return rows, failures


def freeze_candidate(run: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = {(r["case"], r["scope"]): r["rmse_hz"] for r in rows if r["method"] == "balanced"}
    scores = {}
    for mode in METHODS[:3]:
        selected = [
            r
            for r in rows
            if r["method"] == mode
            and r["scope"] == ("event" if r["group"] == "chirp" else "interior")
        ]
        scores[mode] = float(
            np.mean([r["rmse_hz"] / max(baseline[(r["case"], r["scope"])], 1e7) for r in selected])
        )
    chosen = min(scores, key=lambda mode: (scores[mode], METHODS.index(mode)))
    result = dict(
        chosen=chosen,
        voices=24,
        development_objective=scores,
        held_out_started=False,
        rule="TASK005 protocol development objective only",
    )
    write_json(run / "candidate_frozen_before_evaluation.json", result)
    print(f"FROZEN_CANDIDATE={result}", flush=True)
    return result


def snapshot(run: Path) -> None:
    paths = [
        p
        for folder in ("src", "benchmarks", "tests", "configs", "scripts")
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and p.suffix in (".py", ".toml", ".ps1")
    ]
    paths += [
        ROOT / p
        for p in ("docs/TASK-CWT-005_PROTOCOL.md", "AGENTS.md", "pyproject.toml", ".gitignore")
    ]
    hashes = {}
    for path in paths:
        relative = path.relative_to(ROOT)
        with output(run / "source_snapshot" / relative).open("xb") as handle:
            handle.write(path.read_bytes())
        hashes[relative.as_posix()] = sha256(path)
    write_json(
        run / "source_environment.json",
        dict(
            source_sha256=hashes,
            python=sys.version,
            executable=sys.executable,
            platform=platform.platform(),
            processor=platform.processor(),
            logical_cpus=os.cpu_count(),
            packages={d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
            git={
                cmd: subprocess.check_output(["git", *cmd.split()], text=True).strip()
                for cmd in (
                    "rev-parse HEAD",
                    "branch --show-current",
                    "remote -v",
                    "status --short",
                )
            },
        ),
    )


def main() -> None:
    if (
        subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
        != "research/cwt-morlet"
    ):
        raise RuntimeError("branch mismatch")
    stamp = (datetime.now(UTC) + timedelta(hours=8)).strftime("%Y%m%d_%H%M%S")
    run = output(BASE / f"run_{stamp}_{uuid.uuid4().hex[:8]}" / "placeholder").parent
    write_json(run / "raw_before.json", raw_inventory())
    snapshot(run)
    splits = {
        split: registry(split)
        for split in ("cal_score", "cal_detect", "development", "evaluation", "grid")
    }
    all_seeds = [s["seed"] for cases in splits.values() for s in cases]
    assert len(all_seeds) == len(set(all_seeds))
    assert len(splits["evaluation"]) == 1840
    write_json(run / "split_registry.json", splits)
    write_json(
        run / "configuration_registry.json",
        dict(
            wavelet="cmor1.5-1.0",
            precision=18,
            responses={"A0": "abs(W)", "A1": "abs(W)/sqrt(scale)", "A2": "abs(W)/independent RMS"},
            voices=[24, 48, 96],
            formal_baseline="TASK004 unchanged",
            real_A2="EXPLORATORY synthetic white reference; real noise UNKNOWN",
        ),
    )
    print(f"RUN_DIRECTORY={run}", flush=True)
    start = time.perf_counter()
    profiles = calibrate_scores(run)
    thresholds = calibration_thresholds(run, profiles)
    dev, dev_failures = experiments(run, "development", profiles, thresholds)
    if dev_failures:
        raise RuntimeError("development failed; held-out not opened")
    freeze_candidate(run, dev)
    rows, failures = experiments(run, "evaluation", profiles, thresholds)
    grid, grid_failures = experiments(run, "grid", profiles, thresholds)
    from .performance import performance_run
    from .real import real_run

    real = real_run(run, profiles)
    perf = performance_run(run, profiles)
    final_raw = raw_inventory()
    write_json(run / "raw_after.json", final_raw)
    write_json(
        run / "manifest.json",
        dict(
            task="TASK-CWT-005",
            run=run.name,
            elapsed_s=time.perf_counter() - start,
            evaluation_waveforms=1840,
            metrics_rows=len(rows),
            grid_rows=len(grid),
            failures=failures + grid_failures,
            real=real,
            performance_rows=len(perf),
            raw_unchanged=final_raw == json.loads((run / "raw_before.json").read_text()),
            source="source_snapshot + source_environment.json",
            status="COMPLETED",
        ),
    )
    print(f"COMPLETE={run}", flush=True)


if __name__ == "__main__":
    main()
