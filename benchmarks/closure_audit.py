"""TASK006 read-only historical audits; all new evidence is exclusively created."""

import argparse
import base64
import csv
import hashlib
import importlib.metadata as metadata
import inspect
import json
import os
import platform
import sys
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pywt

from benchmarks.validation.cases import make_case, registry
from benchmarks.validation.run import profile_key
from benchmarks.validation.scoring import cwt, score_response, stft_bank
from pdv_cwt.mapping import load_config
from pdv_cwt.safety import ROOT, checked_path, sha256

OUT = ROOT / "artifacts/TASK-CWT-006"
R2 = ROOT / "artifacts/TASK-CWT-002/run_20261029_155407_996145"
R3 = ROOT / "artifacts/TASK-CWT-003/real_runs/run_20261030_143512_d623e95b"
R4 = ROOT / "artifacts/TASK-CWT-004/run_20261030_165336_eef69e3e"
R5 = ROOT / "artifacts/TASK-CWT-005/run_20261030_221635_70d83adf"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def output(path: Path) -> Path:
    path = checked_path(path, ROOT)
    if not path.is_relative_to(OUT):
        raise ValueError("TASK006 output boundary")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write(name: str, value: Any) -> None:
    with output(OUT / name).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def digest_array(values: Any) -> str:
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes()).hexdigest()


def metrics(prediction: Any, truth: Any, mask: Any) -> dict[str, Any]:
    p, t, m = np.asarray(prediction), np.asarray(truth), np.asarray(mask, dtype=bool)
    if p.shape != t.shape or p.shape != m.shape or not np.isfinite(p).all():
        raise ValueError("invalid prediction/shape")
    e = p[m & np.isfinite(t)] - t[m & np.isfinite(t)]
    if not e.size:
        return dict(rmse_hz=None, mae_hz=None, bias_hz=None, truth_points=0)
    return dict(
        rmse_hz=float(np.sqrt(np.dot(e, e) / e.size)),
        mae_hz=float(np.abs(e).sum() / e.size),
        bias_hz=float(e.sum() / e.size),
        truth_points=int(e.size),
    )


def compare(actual: Any, expected: Any) -> float:
    if actual is None or expected is None:
        if actual is not None or expected is not None:
            raise ValueError("null mismatch")
        return 0.0
    if not np.isfinite([actual, expected]).all():
        raise ValueError("nonfinite metric")
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-6)
    return float(abs(actual - expected))


def interval(values: Any, confidence: float = 0.95) -> list[float]:
    a = np.asarray(values, dtype=float)
    if a.ndim != 1 or a.size < 2 or not np.isfinite(a).all():
        raise ValueError("at least two independent finite waveforms required")
    rng = np.random.default_rng(810000)
    means = np.mean(a[rng.integers(a.size, size=(10000, a.size))], axis=1)
    tail = (1 - confidence) / 2
    return [float(x) for x in np.quantile(means, [tail, 1 - tail])]


def validate_registry(splits: dict[str, Any]) -> None:
    seeds = [r["seed"] for rows in splits.values() for r in rows]
    if len(seeds) != len(set(seeds)):
        raise ValueError("split seed leakage")
    for name in ("cal_score", "cal_detect", "development", "evaluation", "grid"):
        if splits[name] != registry(name):
            raise ValueError(f"frozen registry mismatch: {name}")


def validate_parameters(config: dict[str, Any]) -> None:
    if config["wavelet"] != "cmor1.5-1.0" or config["precision"] != 18:
        raise ValueError("historical wavelet/precision mismatch")
    if config["voices"] != [24, 48, 96]:
        raise ValueError("historical density mismatch")


def environment() -> None:
    dist = metadata.distribution("PyWavelets")
    package = Path(pywt.__file__).parent
    records = list(csv.reader((dist.read_text("RECORD") or "").splitlines()))
    checks = []
    for relative, digest, size in records:
        if not digest:
            continue
        path = Path(str(dist.locate_file(relative)))
        algorithm, encoded = digest.split("=", 1)
        actual = base64.urlsafe_b64encode(hashlib.new(algorithm, path.read_bytes()).digest())
        checks.append(
            dict(
                path=relative,
                match=actual.decode().rstrip("=") == encoded,
                size_match=path.stat().st_size == int(size),
            )
        )
    runtime_files = []
    for path in sorted(package.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        runtime_files.append(
            dict(
                path=path.relative_to(package).as_posix(),
                size=path.stat().st_size,
                sha256=sha256(path),
            )
        )
        if path.suffix in (".py", ".pyd"):
            target = output(OUT / "runtime_snapshot/pywt" / path.relative_to(package))
            with target.open("xb") as handle:
                handle.write(path.read_bytes())
    for name in ("METADATA", "RECORD", "WHEEL", "INSTALLER"):
        value = dist.read_text(name)
        if value is not None:
            with output(OUT / "runtime_snapshot/distribution" / name).open("x") as handle:
                handle.write(value)
    source = inspect.getsourcefile(pywt.cwt)
    assert source is not None
    historical = read(ROOT / "artifacts/TASK-CWT-005/runtime_version_evidence.json")
    write(
        "environment_audit.json",
        dict(
            executable=sys.executable,
            python=sys.version,
            platform=platform.platform(),
            logical_cpus=os.cpu_count(),
            module_file=pywt.__file__,
            module_version=pywt.__version__,
            distribution_version=dist.version,
            metadata_path=str(dist.locate_file("pywavelets-1.10.0.dist-info")),
            cwt_signature=str(inspect.signature(pywt.cwt)),
            cwt_source=source,
            cwt_sha256=sha256(Path(source)),
            matches_TASK005_source=sha256(Path(source)) == historical["cwt_source_sha256"],
            version_file=(package / "version.py").read_text(),
            installed_record_checks=checks,
            package_files=runtime_files,
            record_all_match=all(r["match"] and r["size_match"] for r in checks),
            matching_metadata_directories=[
                str(p) for p in package.parent.glob("*wavelets*.dist-info")
            ],
            sys_path=sys.path,
            installer=dist.read_text("INSTALLER"),
            direct_url=dist.read_text("direct_url.json"),
            packages={d.metadata["Name"]: d.version for d in metadata.distributions()},
            diagnosis="Installed RECORD includes stale version.py; no observed path shadowing. "
            "Upstream wheel/build provenance UNKNOWN; RECORD is not authentication.",
            environment_cache={
                k: os.environ.get(k)
                for k in (
                    "PYTHONPYCACHEPREFIX",
                    "PYTEST_ADDOPTS",
                    "RUFF_CACHE_DIR",
                    "MYPY_CACHE_DIR",
                    "MPLCONFIGDIR",
                    "PIP_CACHE_DIR",
                    "UV_CACHE_DIR",
                    "XDG_CACHE_HOME",
                    "TEMP",
                    "TMP",
                    "TMPDIR",
                )
            },
        ),
    )


def arithmetic() -> None:
    validate_registry(read(R5 / "split_registry.json"))
    validate_parameters(read(R5 / "configuration_registry.json"))
    rows5: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    maximum = 0.0
    recomputed = []
    for split in ("development", "evaluation", "grid"):
        expected = len(read(R5 / "split_registry.json")[split]) * (3 if split == "grid" else 1)
        paths = sorted((R5 / split).glob("*/metrics.json"))
        assert len(paths) == expected
        for path in paths:
            rows = read(path)
            with np.load(path.parent / "common.npz", allow_pickle=False) as a:
                centers = a["sample_index"]
                assert np.all(np.diff(centers) == 128)
                for row in rows:
                    method = row["method"]
                    positions = np.arange(centers.size)
                    if "physical" in method:
                        pc = a[f"{method}_sample_index"]
                        positions = np.searchsorted(centers, pc)
                        np.testing.assert_array_equal(centers[positions], pc)
                        assert np.all(np.diff(pc) == (256 if row["fs_hz"] == 80e9 else 128))
                    mask = a["interior"][positions] & a["active"][positions]
                    if row["scope"] == "event":
                        t = a["time_s"][positions]
                        on, off = (180e-9, 220e-9)
                        if row["group"] == "chirp":
                            width = row["duration_ns"] * 1e-9
                            on, off = 200e-9 - width / 2, 200e-9 + width / 2
                        mask &= (t >= on) & (t < off)
                    truth, prediction = a["truth_hz"][positions], a[f"{method}_prediction"]
                    values = metrics(prediction, truth, mask)
                    for key, value in values.items():
                        maximum = max(maximum, compare(value, row[key]))
                    valid = mask & np.isfinite(truth)
                    if valid.any() and "catastrophic_rate" in row:
                        compare(
                            float(np.mean(np.abs(prediction[valid] - truth[valid]) > 1e9)),
                            row["catastrophic_rate"],
                        )
                    branch = valid & np.isfinite(a["interference_hz"][positions])
                    if branch.any():
                        other = a["interference_hz"][positions]
                        compare(
                            float(
                                np.mean(
                                    np.abs(prediction[branch] - other[branch])
                                    < np.abs(prediction[branch] - truth[branch])
                                )
                            ),
                            row["wrong_branch_rate"],
                        )
                    for key, value in row.items():
                        if isinstance(value, float) and not np.isfinite(value):
                            raise ValueError(f"nonfinite stored metric: {path}:{key}")
                    counts[f"005_{split}_rows"] += 1
                    counts["005_error_points"] += values["truth_points"]
                    recomputed.append(
                        dict(
                            task="005",
                            case=row["case"],
                            method=method,
                            voices=row["voices"],
                            scope=row["scope"],
                            **values,
                        )
                    )
                    if split == "evaluation":
                        rows5.append(row)
        csvname = "synthetic_metrics.csv" if split == "evaluation" else f"{split}_metrics.csv"
        with (R5 / csvname).open(encoding="utf-8", newline="") as handle:
            table = list(csv.DictReader(handle))
        assert len(table) == counts[f"005_{split}_rows"]
        csv_keys = [(r["case"], r["method"], r["scope"], int(r["voices"])) for r in table]
        assert len(csv_keys) == len(set(csv_keys))
        original = {
            (r["case"], r["method"], r["scope"], int(r["voices"])): r
            for p in paths
            for r in read(p)
        }
        assert set(csv_keys) == set(original)
        for r in table:
            source_row = original[r["case"], r["method"], r["scope"], int(r["voices"])]
            for name in ("rmse_hz", "mae_hz", "bias_hz"):
                if r[name] and not np.isfinite(float(r[name])):
                    raise ValueError("nonfinite CSV")
                compare(float(r[name]) if r[name] else None, source_row[name])
    # Earlier tasks use distinct denominators and storage formats.
    for row in read(R2 / "metrics.json"):
        case, mode = row["case"], row["normalization"]
        with np.load(R2 / f"signals/{case}.npz") as signal:
            with np.load(R2 / f"candidates/{case}_{mode}.npz") as a:
                active, edge = signal["active"], a["bank_edge_affected"]
                for scope, mask in (
                    ("all", active),
                    ("interior", active & ~edge),
                    ("edge", active & edge),
                ):
                    v = metrics(a["frequency_hz"], signal["true_frequency_hz"], mask)
                    for name in ("rmse_hz", "mae_hz", "bias_hz"):
                        maximum = max(maximum, compare(v[name], row[f"{scope}_{name}"]))
                    counts["002_regions"] += 1
    for path in sorted((R4 / "synthetic").glob("*/metrics.json")):
        with np.load(path.parent / "signal_truth.npz") as signal:
            with np.load(path.parent / "common_grid.npz") as a:
                for row in read(path):
                    scope, method = row["scope"], row["method"]
                    if scope not in ("common_all", "common_interior", "fast_transition_common"):
                        continue
                    idx = a["sample_index"]
                    mask = signal["active"][idx].copy()
                    if scope != "common_all":
                        mask &= a["common_interior"]
                    if scope == "fast_transition_common":
                        mask &= (a["cwt_time_s"] >= 190e-9) & (a["cwt_time_s"] < 210e-9)
                    v = metrics(a[f"{method}_frequency_hz"], signal["truth_hz"][idx], mask)
                    for name in ("rmse_hz", "mae_hz", "bias_hz", "truth_points"):
                        maximum = max(maximum, compare(v[name], row[name]))
                    counts["004_regions"] += 1
    # Recompute frozen development objective without consulting held-out outcomes.
    dev = [r for p in sorted((R5 / "development").glob("*/metrics.json")) for r in read(p)]
    baseline = {(r["case"], r["scope"]): r["rmse_hz"] for r in dev if r["method"] == "balanced"}
    objective = {}
    for mode in ("A0", "A1", "A2"):
        chosen_rows = [
            r
            for r in dev
            if r["method"] == mode
            and r["scope"] == ("event" if r["group"] == "chirp" else "interior")
        ]
        objective[mode] = float(
            np.mean([r["rmse_hz"] / max(1e7, baseline[r["case"], r["scope"]]) for r in chosen_rows])
        )
    frozen = read(R5 / "candidate_frozen_before_evaluation.json")
    assert min(objective, key=lambda k: objective[k]) == frozen["chosen"] == "A2"
    for mode, value in objective.items():
        compare(value, frozen["development_objective"][mode])
    write("metrics_recomputed.json", recomputed)
    write(
        "arithmetic_audit.json",
        dict(
            status="PASS",
            counts=dict(counts),
            max_metric_difference_hz=maximum,
            frozen_objective=objective,
            scope="Saved-array arithmetic, not a full algorithm rerun",
        ),
    )
    paired_decisions(rows5)


def classify(go_pass: bool, cost_pass: bool, paired_improvement: bool) -> str:
    if go_pass and cost_pass:
        return "GO_FOR_OPTIONAL_ENGINEERING"
    return "NICHE_ONLY" if paired_improvement else "NOT_SUPPORTED"


def paired_decisions(rows: list[dict[str, Any]]) -> None:
    results: list[dict[str, Any]] = []
    for fs in (40e9, 80e9):
        for group, band, model, scope, duration in (
            ("core", "low", "white", "interior", 0),
            ("core", "high", "white", "interior", 0),
            ("core", "low", "colored", "interior", 0),
            ("bandwidth", "low", "bandwidth", "interior", 0),
            ("chirp", "sweep", "white", "event", 20),
        ):
            selected = [
                r
                for r in rows
                if r["fs_hz"] == fs
                and r["group"] == group
                and r["band"] == band
                and r["noise"] == model
                and r["scope"] == scope
                and r["duration_ns"] == duration
                and r["snr_db"] == (20 if group == "chirp" else -10)
            ]
            for mode, baseline_name in (
                ("A0", "balanced"),
                ("A1", "balanced"),
                ("A2", "balanced"),
                ("A2_physical", "physical_balanced"),
            ):
                if "physical" in mode and group != "chirp":
                    continue
                a = sorted([r for r in selected if r["method"] == mode], key=lambda r: r["case"])
                b = sorted(
                    [r for r in selected if r["method"] == baseline_name], key=lambda r: r["case"]
                )
                assert len(a) == len(b) == 20
                assert [r["case"] for r in a] == [r["case"] for r in b]
                av, bv = np.array([r["rmse_hz"] for r in a]), np.array([r["rmse_hz"] for r in b])
                near_zero = bv.mean() < 1e7
                go = interval(av - bv + 2e6 if near_zero else av - 0.8 * bv, 0.975)
                formal = mode in ("A0", "A1", "A2")
                bias = formal and all(
                    abs(r["bias_hz"]) <= max(1e7, 0.02 * r["truth_mean_hz"]) for r in a
                )
                catastrophe = formal and all(r["catastrophic_rate"] < 0.01 for r in a)
                cap = bool(not near_zero or np.all(av <= 1e7))
                results.append(
                    dict(
                        fs_hz=fs,
                        group=group,
                        band=band,
                        noise=model,
                        method=mode,
                        n=20,
                        unit="independent waveform; fixed calibration conditional CI",
                        rmse_mean_hz=float(av.mean()),
                        balanced_mean_hz=float(bv.mean()),
                        delta_mean_hz=float((av - bv).mean()),
                        ci95_hz=interval(av - bv),
                        GO_ci975_hz=go,
                        bias_pass=bias,
                        catastrophe_pass=catastrophe,
                        cap_pass=cap,
                        performance_pass=bool(go[1] < 0 and bias and catastrophe and cap),
                    )
                )
    historical = read(R5 / "scientific_decision.json")
    formal_domains = {}
    for name, group in (("low_white_weak", "core"), ("fast20_white", "chirp")):
        selected = [
            r
            for r in results
            if r["method"] == "A2"
            and r["group"] == group
            and r["band"] == ("low" if group == "core" else "sweep")
            and r["noise"] == "white"
        ]
        passed = len(selected) == 2 and all(r["performance_pass"] for r in selected)
        assert passed == historical["domains"][name]["pass_both_rates"]
        formal_domains[name] = passed
    with (R5 / "time_memory_comparison.csv").open(newline="") as handle:
        perf = list(csv.DictReader(handle))
    costs = []
    for fs in (40e9, 80e9):
        perf_a = next(
            r
            for r in perf
            if r["method"] == "A2" and float(r["fs_hz"]) == fs and r["voices"] == "24"
        )
        perf_b = next(r for r in perf if r["method"] == "balanced" and float(r["fs_hz"]) == fs)
        costs.append(
            dict(
                fs_hz=fs,
                ratio=float(perf_a["total_s"]) / float(perf_b["total_s"]),
                samples=int(perf_a["samples"]),
                peak_bytes=int(perf_a["peak_memory_bytes"]),
            )
        )
    cost_ok = all(r["ratio"] <= 50 and r["peak_bytes"] <= 2 * 1024**3 for r in costs)
    assert cost_ok == historical["engineering_cost_pass"] is False
    assert not any(formal_domains.values())
    benefit = any(
        r["ci95_hz"][1] < 0
        for r in results
        if r["method"] == "A2" and r["group"] in ("core", "chirp")
    )
    verdict = classify(any(formal_domains.values()), cost_ok, benefit)
    assert verdict == historical["scientific_verdict"]
    write("paired_statistics.json", results)
    write(
        "decision_audit.json",
        dict(
            formal_domains=formal_domains,
            costs=costs,
            engineering_cost_pass=cost_ok,
            scientific_verdict=verdict,
            historical_decision_consistent=historical["scientific_verdict"] == "NICHE_ONLY",
        ),
    )


def probes() -> None:
    splits = read(R5 / "split_registry.json")
    profiles = read(R5 / "calibration/score_profiles.json")
    selected = []
    for fs in (40e9, 80e9):
        selected.append(next(r for r in splits["grid"] if r["fs"] == fs and r["kind"] == "clean"))
        for group, band in (
            ("core", "low"),
            ("core", "high"),
            ("chirp", "sweep"),
            ("branches", "mid"),
            ("noise", "none"),
        ):
            selected.append(
                next(
                    r
                    for r in splits["evaluation"]
                    if r["fs"] == fs
                    and r["group"] == group
                    and r["band"] == band
                    and r["model"] == "white"
                    and (group != "core" or r["snr"] == -10)
                    and (group != "chirp" or r["duration_ns"] == 20)
                )
            )
    records = []
    for spec in selected:
        case = make_case(spec)
        for voices in (24, 48, 96) if spec["split"] == "grid" else (24,):
            directory = R5 / spec["split"] / f"{spec['id']}_v{voices}"
            stored = read(directory / "recipe.json")
            assert digest_array(case.signal.voltage_v) == stored["voltage_sha256"]
            assert digest_array(case.signal.time_s) == stored["time_sha256"]
            result, elapsed = cwt(case.signal, voices)
            assert result.config.wavelet == "cmor1.5-1.0" and result.config.precision == 18
            raw = np.abs(result.coefficients)
            rms = np.asarray(profiles[profile_key(spec["fs"], spec["model"], voices)])
            predictions = {}
            errors = {}
            with np.load(directory / "common.npz") as a:
                centers = a["sample_index"]
                np.testing.assert_array_equal(case.signal.time_s[centers], a["time_s"])
                for mode in ("A0", "A1", "A2"):
                    score = score_response(raw, result.grid.scales, mode, rms)
                    pred = result.grid.frequency_hz[np.argmax(score, axis=0)][centers]
                    np.testing.assert_array_equal(pred, a[f"{mode}_prediction"])
                    # Also compare response amplitudes, rather than only grid indices.
                    np.testing.assert_allclose(
                        np.max(score[:, centers], axis=0), a[f"{mode}_peak"], rtol=1e-12, atol=1e-12
                    )
                    predictions[mode] = pred
                    errors[mode] = metrics(pred, a["truth_hz"], a["interior"] & a["active"])
                del result, raw, score
                for high in (False, True):
                    b = stft_bank(case.signal, high)
                    mode = "high_time" if high else "balanced"
                    np.testing.assert_array_equal(b.predicted, a[f"{mode}_prediction"])
                    predictions[mode] = b.predicted
                    errors[mode] = metrics(b.predicted, a["truth_hz"], a["interior"] & a["active"])
                if spec["group"] == "chirp":
                    b = stft_bank(case.signal, physical=True)
                    np.testing.assert_array_equal(b.centers, a["physical_balanced_sample_index"])
                    np.testing.assert_array_equal(b.predicted, a["physical_balanced_prediction"])
            path = output(OUT / "probes" / f"{spec['id']}_v{voices}.npz")
            np.savez_compressed(path, **predictions)
            records.append(
                dict(
                    case=spec["id"],
                    group=spec["group"],
                    fs=spec["fs"],
                    voices=voices,
                    seed=spec["seed"],
                    voltage_sha256=stored["voltage_sha256"],
                    exact_predictions=True,
                    response_allclose=True,
                    cwt_elapsed_s=elapsed,
                    metrics=errors,
                )
            )
            print(f"reproduced {spec['id']} v{voices}", flush=True)
    write(
        "algorithm_reproduction.json",
        dict(
            status="PASS",
            independent_waveforms=len(selected),
            cwt_executions=len(records),
            records=records,
            scope="Actual transforms in current installed environment; not all held-out waveforms",
        ),
    )


def real_audit() -> None:
    config = load_config(ROOT / "configs/real_batch.toml")
    index = read(R5 / "real_channel_index.json")
    expected = {
        (name, c.name) for name, mapping in config.mappings.items() for c in mapping.channels
    }
    assert {(e["file"], e["channel"]) for e in index} == expected and len(index) == 14
    raw = {Path(r["path"]).name: r for r in read(OUT / "raw_before.json")}
    points, channels = 0, []
    for e in index:
        assert e["raw_sha256_before"] == e["raw_sha256_after"] == raw[e["file"]]["sha256"]
        directory = R5 / e["directory"]
        for filename in (
            "metadata.json",
            "spectral_support.png",
            "quality_diagnostics.png",
            "native.npz",
            "common_spectral_support.npz",
        ):
            assert (directory / filename).is_file()
        with np.load(directory / "native.npz") as a:
            assert a["time_s"].size == e["samples"]
            assert digest_array(a["time_s"]) == e["time_sha256"]
            for mode in ("A0", "A1", "A2"):
                assert a[f"{mode}_frequency_hz"].size == e["samples"]
                assert np.isfinite(a[f"{mode}_frequency_hz"]).all()
            with np.load(R4 / "real" / directory.name / "cwt/native.npz") as p:
                np.testing.assert_array_equal(a["time_s"], p["time_s"])
                np.testing.assert_array_equal(a["A0_frequency_hz"], p["frequency_hz"])
        assert e["truth"] == "UNKNOWN" and e["velocity"] == "NOT COMPUTED"
        points += e["samples"]
        channels.append(
            dict(
                file=e["file"],
                channel=e["channel"],
                samples=e["samples"],
                status="saved outputs verified; physical truth UNKNOWN",
            )
        )
    write(
        "real_output_audit.json",
        dict(
            status="PASS",
            channels=channels,
            channel_count=len(index),
            native_points=points,
            raw_read_scope="hash only; no new waveform parsing",
            TASK003_batch_rows=sum(1 for _ in (R3 / "batch_summary.csv").open()) - 1,
        ),
    )


def file_entry(path: Path) -> dict[str, Any]:
    path = read_path(path)
    return dict(
        path=path.relative_to(ROOT).as_posix(), size=path.stat().st_size, sha256=sha256(path)
    )


@cache
def read_directory(path: Path) -> None:
    """Validate read-only tree ancestors once per audit process, rejecting links."""
    if path == ROOT:
        checked_path(path, ROOT)
        return
    if not path.is_relative_to(ROOT):
        raise ValueError("read outside repository")
    read_directory(path.parent)
    if path.is_symlink() or path.is_junction():
        raise ValueError("read reparse path refused")


def read_path(path: Path) -> Path:
    path = path.absolute()
    read_directory(path.parent)
    if path.is_symlink() or path.is_junction():
        raise ValueError("read reparse file refused")
    return path


def historical_inventory() -> list[dict[str, Any]]:
    return [
        file_entry(p)
        for task in (2, 3, 4, 5)
        for p in sorted((ROOT / f"artifacts/TASK-CWT-{task:03d}").rglob("*"))
        if p.is_file()
    ]


def verify_entries(entries: list[dict[str, Any]]) -> None:
    seen = set()
    for entry in entries:
        relative = Path(entry["path"])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] in ("raw_data", ".git", ".local_cache")
        ):
            raise ValueError("unsafe manifest path")
        path = read_path(ROOT / relative)
        if entry["path"] in seen or not path.is_file():
            raise ValueError("missing/duplicate indexed artifact")
        seen.add(entry["path"])
        if path.stat().st_size != entry["size"] or sha256(path) != entry["sha256"]:
            raise ValueError(f"artifact hash mismatch: {relative}")


def archive() -> None:
    before = read(OUT / "historical_before.json")
    verify_entries(before)
    assert before == historical_inventory()
    paths = [ROOT / name for name in ("AGENTS.md", "README.md", ".gitignore", "pyproject.toml")]
    paths += [
        p
        for folder in ("src", "benchmarks", "tests", "configs", "scripts", "docs")
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    ]
    paths += [p for p in OUT.rglob("*") if p.is_file() and p.name != "final_manifest.json"]
    entries = before + [file_entry(p) for p in sorted(set(paths))]
    for entry in entries:
        entry["dependency_group"] = (
            "historical_evidence"
            if entry["path"].startswith("artifacts/TASK-CWT-00")
            and not entry["path"].startswith("artifacts/TASK-CWT-006/")
            else "TASK006_evidence_or_source"
        )
    write(
        "final_manifest.json",
        dict(
            task="TASK-CWT-006",
            date="2026-10-31",
            files=entries,
            source_state=read(OUT / "git_delivery.json"),
            historical_files_unchanged=len(before),
            dependencies={
                "metrics_recomputed": [
                    "TASK002 signals+candidates",
                    "TASK004 signal_truth+common_grid",
                    "TASK005 common.npz+recipe+metrics",
                ],
                "algorithm_reproduction": [
                    "frozen source/config",
                    "split_registry",
                    "score_profiles",
                    "runtime_snapshot",
                ],
                "final_reports": [
                    "arithmetic_audit",
                    "paired_statistics",
                    "decision_audit",
                    "environment_audit",
                ],
            },
            excluded=(
                "self, raw contents, .git, .local_cache; raw fingerprints are separate evidence"
            ),
            warning=(
                "Git repository alone cannot recover research results. "
                "Preserve artifacts separately."
            ),
        ),
    )


def supplemental() -> None:
    source_checks = []
    for task, run in ((2, R2), (4, R4), (5, R5)):
        info = read(run / ("manifest.json" if task == 2 else "source_environment.json"))
        for name, digest in info["source_sha256"].items():
            path = ROOT / name
            source_checks.append(
                dict(
                    task=task,
                    path=name,
                    sha256=digest,
                    current_match=sha256(path) == digest,
                    current_LF_match=hashlib.sha256(
                        path.read_bytes().replace(b"\r\n", b"\n")
                    ).hexdigest()
                    == digest,
                )
            )
    function_digest = hashlib.sha256(inspect.getsource(pywt.cwt).encode()).hexdigest()
    assert function_digest == read(R2 / "manifest.json")["pywt_cwt_source_sha256"]
    assert all(
        (r["current_match"] or r["current_LF_match"])
        for r in source_checks
        if r["path"].replace("\\", "/").startswith("src/")
    )
    table_checks = []
    for split, filename in (
        ("development", "development_metrics.csv"),
        ("evaluation", "synthetic_metrics.csv"),
        ("grid", "grid_metrics.csv"),
    ):
        original = {
            (r["case"], r["method"], r["scope"], int(r["voices"])): r
            for p in sorted((R5 / split).glob("*/metrics.json"))
            for r in read(p)
        }
        with (R5 / filename).open(newline="", encoding="utf-8") as handle:
            table = list(csv.DictReader(handle))
        keys = [(r["case"], r["method"], r["scope"], int(r["voices"])) for r in table]
        assert len(keys) == len(set(keys)) == len(original) and set(keys) == set(original)
        for key, row in zip(keys, table, strict=True):
            for field in ("rmse_hz", "mae_hz", "bias_hz", "truth_points"):
                compare(float(row[field]) if row[field] else None, original[key][field])
        table_checks.append(
            dict(split=split, rows=len(table), missing_keys=0, duplicates=0, unexpected_nonfinite=0)
        )
    summaries = read(R5 / "condition_summary.json")
    paired = read(OUT / "paired_statistics.json")
    for row in paired:
        candidates = [
            s
            for s in summaries
            if all(s[k] == row[k] for k in ("fs_hz", "group", "band", "noise", "method"))
            and s["scope"] == ("event" if row["group"] == "chirp" else "interior")
            and s["snr_db"] == (20 if row["group"] == "chirp" else -10)
            and s["duration_ns"] == (20 if row["group"] == "chirp" else 0)
        ]
        assert len(candidates) == 1
        summary = candidates[0]
        compare(row["rmse_mean_hz"], summary["rmse_hz_mean"])
        np.testing.assert_allclose(row["ci95_hz"], summary["paired_delta_B_ci95_hz"], atol=1e-6)
        np.testing.assert_allclose(row["GO_ci975_hz"], summary["GO_delta_ci975_hz"], atol=1e-6)
    profiles = read(R5 / "calibration/score_profiles.json")
    for key, values in profiles.items():
        assert len(values) == {24: 143, 48: 285, 96: 569}[int(key.split("_v")[1])]
        assert np.all(np.isfinite(values)) and np.min(values) > 0
    thresholds = read(R5 / "calibration/detection_thresholds.json")
    for methods in thresholds.values():
        for values in methods.values():
            assert len(values["calibration_frames"]) == 60
            compare(
                values["frame"],
                float(np.quantile(np.concatenate(values["calibration_frames"]), 0.99)),
            )
            compare(
                values["record"],
                float(np.quantile(values["calibration_record_max"], 0.95, method="higher")),
            )
    with (R5 / "time_memory_comparison.csv").open(newline="") as handle:
        perf = list(csv.DictReader(handle))
    stdout = [read(p) for p in (R5 / "performance").glob("*.stdout.txt")]
    assert len(perf) == len(stdout) == 22
    for row in perf:
        match = next(
            r
            for r in stdout
            if r["method"] == row["method"]
            and r["fs_hz"] == float(row["fs_hz"])
            and r["voices"] == int(row["voices"])
        )
        compare(float(row["total_s"]), match["total_s"])
        compare(float(row["peak_memory_bytes"]), match["peak_memory_bytes"])
        assert match["samples"] == round(match["fs_hz"] * 819.2e-9)
        assert match["status"] == "COMPLETED" and match["finite_fraction"] == 1
    rows = [r for p in sorted((R5 / "grid").glob("*/metrics.json")) for r in read(p)]
    grid_summary = []
    for fs in (40e9, 80e9):
        for kind in ("clean", "noisy", "linear"):
            for voices in (24, 48, 96):
                for mode in ("A0", "A1", "A2"):
                    selected = [
                        r
                        for r in rows
                        if r["fs_hz"] == fs
                        and r["kind"] == kind
                        and r["voices"] == voices
                        and r["method"] == mode
                    ]
                    assert len(selected) == 12
                    grid_summary.append(
                        dict(
                            fs_hz=fs,
                            kind=kind,
                            voices=voices,
                            method=mode,
                            pooled_rmse_hz=float(
                                np.sqrt(np.mean([r["rmse_hz"] ** 2 for r in selected]))
                            ),
                            bias_hz=float(np.mean([r["bias_hz"] for r in selected])),
                        )
                    )
    write("grid_recomputed.json", grid_summary)
    write(
        "supplemental_audit.json",
        dict(
            status="PASS",
            source_checks=source_checks,
            TASK002_cwt_function_text_hash_matches=True,
            table_checks=table_checks,
            paired_intervals_checked=len(paired),
            score_profiles=len(profiles),
            threshold_calibration_groups=len(thresholds),
            performance_records_checked=len(perf),
            limits="Local consistency; no external preregistration timestamp.",
        ),
    )


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "inventory",
            "environment",
            "arithmetic",
            "probes",
            "real",
            "supplemental",
            "archive",
            "verify",
        ),
    )
    parser.add_argument(
        "--output-dir", type=Path, help="Fresh evidence subdirectory within artifacts/TASK-CWT-006"
    )
    arguments = parser.parse_args()
    action = arguments.action
    if arguments.output_dir is not None:
        candidate = checked_path(arguments.output_dir, ROOT / "artifacts/TASK-CWT-006")
        if candidate == ROOT / "artifacts/TASK-CWT-006":
            raise ValueError("use a fresh subdirectory for repeated audits")
        OUT = candidate
    if action == "inventory":
        write("historical_before.json", historical_inventory())
    elif action == "environment":
        environment()
    elif action == "arithmetic":
        arithmetic()
    elif action == "probes":
        probes()
    elif action == "real":
        real_audit()
    elif action == "supplemental":
        supplemental()
    elif action == "archive":
        archive()
    else:
        manifest = read(OUT / "final_manifest.json")
        verify_entries(manifest["files"])
        print(f"PASS: {len(manifest['files'])} indexed files verified")


if __name__ == "__main__":
    main()
