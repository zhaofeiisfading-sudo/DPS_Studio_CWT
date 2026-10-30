"""Frozen S1-S6 synthetic experiment; each invocation preserves a new run directory."""

import csv
import hashlib
import importlib.metadata
import inspect
import json
import os
import platform
import subprocess
import sys
import time
import tomllib
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pywt

from pdv_cwt import (
    CWTConfig,
    CWTResult,
    SyntheticCase,
    compute_cwt,
    diagnose,
    strongest_candidate,
    synthetic_pdv,
)
from pdv_cwt.frequency import Normalization

from .metrics import evaluate
from .system_info import memory_snapshot

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf8"
    )


def build_cases(settings: dict[str, Any]) -> list[tuple[str, str, SyntheticCase]]:
    common: dict[str, Any] = {
        "samples": settings["samples"],
        "sampling_rate_hz": settings["sampling_rate_hz"],
        "amplitude_v": settings["amplitude_v"],
        "phase_rad": settings["phase_rad"],
        "frequency_start_hz": 1e9,
        "seed": 101,
    }
    cases: list[tuple[str, str, SyntheticCase]] = []

    def add(name: str, family: str, **changes: Any) -> None:
        cases.append((name, family, synthetic_pdv(**(common | changes))))

    add("S1_tone", "S1")
    for snr in settings["snr_db"]:
        sigma = settings["amplitude_v"] / np.sqrt(2) * 10 ** (-snr / 20)
        for seed in settings["evaluation_seeds"]:
            add(f"S2_snr{snr:g}_seed{seed}", "S2", noise_sigma_v=sigma, seed=seed)
    add(
        "S3_chirp",
        "S3",
        frequency_start_hz=settings["chirp_start_hz"],
        frequency_end_hz=settings["chirp_end_hz"],
    )
    add(
        "S3_fast_low_chirp",
        "S3",
        samples=settings["fast_chirp_samples"],
        frequency_start_hz=settings["fast_chirp_start_hz"],
        frequency_end_hz=settings["fast_chirp_end_hz"],
    )
    for frequency in settings["tone_frequencies_hz"]:
        add(f"S4_equal_amplitude_{frequency / 1e9:g}GHz", "S4", frequency_start_hz=frequency)
    add("S5_edge_pulse", "S5", pulse_s=(settings["pulse_start_s"], settings["pulse_end_s"]))
    add("S5_interior_pulse", "S5", pulse_s=(190e-9, 210e-9))
    for split, seeds in (
        ("calibration", settings["calibration_seeds"]),
        ("evaluation", settings["evaluation_seeds"]),
    ):
        for seed in seeds:
            add(f"S6_{split}_noise_seed{seed}", "S6", amplitude_v=0, noise_sigma_v=1, seed=seed)
    return cases


def save_case(output: Path, name: str, case: SyntheticCase) -> dict[str, Any]:
    np.savez_compressed(
        output / "signals" / f"{name}.npz",
        time_s=case.signal.time_s,
        voltage_v=case.signal.voltage_v,
        true_frequency_hz=case.true_frequency_hz,
        active=case.active,
        phase_rad=case.phase_rad,
    )
    return {
        "recipe": case.recipe,
        "array_hash_convention": "C-order little-endian float64 bytes, separate time and voltage",
        "time_sha256": hashlib.sha256(case.signal.time_s.astype("<f8").tobytes()).hexdigest(),
        "voltage_sha256": hashlib.sha256(case.signal.voltage_v.astype("<f8").tobytes()).hexdigest(),
        "file": f"signals/{name}.npz",
    }


def plot_case(output: Path, name: str, case: SyntheticCase, result: CWTResult) -> None:
    """Only display columns are thinned; computations and saved candidates use all samples."""
    raw = strongest_candidate(result)
    normalized = strongest_candidate(result, normalization="scale_amplitude")
    quality = diagnose(result, normalized, noise_sigma_v=case.noise_sigma_v)
    time_ns = case.signal.time_s * 1e9
    fig, axes = plt.subplots(3, 1, figsize=(10.5, 10), constrained_layout=True)
    axes[0].plot(time_ns, case.signal.voltage_v, color="#4f6475", linewidth=0.65)
    axes[0].set_ylabel("Voltage (V)")
    axes[0].set_title(f"{name}: synthetic input; fs=40 GS/s; analysis 0.1-6 GHz")
    stride = max(1, time_ns.size // 1600)
    response = np.abs(result.coefficients[:, ::stride]) / np.sqrt(result.grid.scales[:, None])
    image = axes[1].pcolormesh(
        time_ns[::stride], result.grid.frequency_hz / 1e9, response, shading="auto", cmap="magma"
    )
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Frequency (GHz)")
    axes[1].set_ylim(0.1, 6)
    fig.colorbar(image, ax=axes[1], label="|W| / sqrt(scale) (V)")
    axes[1].plot(
        time_ns,
        case.true_frequency_hz / 1e9,
        "--",
        color="#66d9ef",
        linewidth=1.3,
        label="Ground truth",
    )
    axes[1].plot(
        time_ns,
        normalized.frequency_hz / 1e9,
        color="#b8e65c",
        linewidth=0.8,
        alpha=0.85,
        label="Strongest, scale amplitude",
    )
    axes[1].legend(loc="upper left", fontsize=8)
    for candidate, label, color in (
        (raw, "raw", "#d95f02"),
        (normalized, "scale amplitude", "#157f97"),
    ):
        axes[2].plot(
            time_ns,
            (candidate.frequency_hz - case.true_frequency_hz) / 1e6,
            label=label,
            color=color,
            linewidth=0.7,
        )
    axes[2].fill_between(
        time_ns,
        0,
        1,
        where=quality.bank_edge_affected,
        transform=axes[2].get_xaxis_transform(),
        color="#aaaaaa",
        alpha=0.25,
        label="Full bank edge affected",
    )
    axes[2].set_ylabel("Frequency error (MHz)")
    axes[2].set_xlabel("Time (ns)")
    axes[2].legend(fontsize=8)
    for ax in axes:
        ax.set_xlim(float(time_ns[0]), float(time_ns[-1]))
    fig.savefig(output / "figures" / f"{name}.png", dpi=160)
    plt.close(fig)


def summary_figures(output: Path, rows: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    for mode, color in (("raw", "#d95f02"), ("scale_amplitude", "#157f97")):
        tones = [r for r in rows if r["family"] == "S4" and r["normalization"] == mode]
        frequencies = [r["true_frequency_start_hz"] / 1e9 for r in tones]
        axes[0].plot(
            frequencies,
            [r["interior_selected_response_mean"] for r in tones],
            "o-",
            color=color,
            label=mode,
        )
        axes[1].plot(
            frequencies,
            [r["interior_bias_hz"] / r["true_frequency_start_hz"] * 100 for r in tones],
            "o-",
            color=color,
            label=mode,
        )
    axes[0].set_ylabel("Selected CWT response (V)")
    axes[1].set_ylabel("Mean frequency bias (%)")
    for ax in axes:
        ax.set_xlabel("Equal-amplitude tone frequency (GHz)")
        ax.set_title("cmor1.5-1.0; analysis band 0.1-6 GHz")
        ax.legend()
        ax.grid(alpha=0.2)
    fig.savefig(output / "figures" / "S4_normalization_audit.png", dpi=160)
    plt.close(fig)


def run() -> Path:
    timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S_%f")
    output = ROOT / "artifacts" / "TASK-CWT-002" / f"run_{timestamp}"
    if output.resolve() != output or output.exists():
        raise ValueError("refusing output alias or existing run directory")
    for directory in (output, output / "figures", output / "signals", output / "candidates"):
        directory.mkdir(parents=True, exist_ok=False)
    with (ROOT / "configs/task_cwt002.toml").open("rb") as handle:
        settings = tomllib.load(handle)
    with (ROOT / "configs/cwt_v1.toml").open("rb") as handle:
        config_values = tomllib.load(handle)
    config_values.pop("normalization")
    config = CWTConfig(**config_values)
    write_json(output / "experiment_parameters.json", settings | {"cwt": asdict(config)})
    rows: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {}
    start_run = time.perf_counter()
    for name, family, case in build_cases(settings):
        provenance[name] = save_case(output, name, case)
        available = memory_snapshot()["available_physical_bytes"]
        start = time.perf_counter()
        result = compute_cwt(
            case.signal,
            config,
            available_memory_bytes=(available if isinstance(available, int) else None),
        )
        transform_elapsed = time.perf_counter() - start
        for mode in ("raw", "scale_amplitude"):
            normalization: Normalization = mode
            start_extract = time.perf_counter()
            candidate = strongest_candidate(result, normalization=normalization)
            quality = diagnose(
                result,
                candidate,
                noise_sigma_v=case.noise_sigma_v,
                record_alpha=settings["noise_record_alpha"],
            )
            extract_elapsed = time.perf_counter() - start_extract
            row: dict[str, Any] = evaluate(
                case, candidate, quality, wavelength_m=settings["wavelength_m"]
            )
            active_interior = case.active & ~quality.bank_edge_affected
            row.update(
                {
                    "case": name,
                    "family": family,
                    "samples": case.signal.time_s.size,
                    "true_frequency_start_hz": case.recipe["frequency_start_hz"],
                    "true_frequency_end_hz": case.recipe["frequency_end_hz"],
                    "transform_elapsed_s": transform_elapsed,
                    "extract_and_diagnose_elapsed_s": extract_elapsed,
                    "estimated_coefficient_bytes": result.memory.coefficient_bytes,
                    "estimated_working_bytes": result.memory.working_bytes,
                    "process_lifetime_peak_working_set_bytes": (
                        memory_snapshot()["peak_working_set_bytes"]
                    ),
                    "interior_selected_response_mean": (
                        float(np.mean(candidate.response[active_interior]))
                        if np.any(active_interior)
                        else None
                    ),
                    "onset_error_s": None,
                }
            )
            if family == "S5":
                # Known-amplitude offline diagnostic. Not a fitted detection threshold.
                amplitude = (
                    2 * candidate.raw_magnitude / np.sqrt(result.grid.scales[candidate.scale_index])
                )
                above = np.flatnonzero(amplitude > 0.5 * settings["amplitude_v"])
                if above.size:
                    pulse_start = case.recipe["pulse_start_s"]
                    assert isinstance(pulse_start, float)
                    row["onset_error_s"] = float(case.signal.time_s[above[0]]) - pulse_start
            rows.append(row)
            np.savez_compressed(
                output / "candidates" / f"{name}_{normalization}.npz",
                time_s=candidate.time_s,
                frequency_hz=candidate.frequency_hz,
                scale_index=candidate.scale_index,
                raw_magnitude=candidate.raw_magnitude,
                response=candidate.response,
                candidate_edge_affected=quality.candidate_edge_affected,
                bank_edge_affected=quality.bank_edge_affected,
                alias_risk=quality.alias_risk,
                above_noise=quality.above_noise,
                quality_passed=quality.passed,
                raw_noise_threshold=quality.raw_noise_threshold,
            )
        if name in (
            "S1_tone",
            "S3_chirp",
            "S3_fast_low_chirp",
            "S5_edge_pulse",
            "S5_interior_pulse",
            "S6_evaluation_noise_seed101",
        ):
            plot_case(output, name, case, result)
        print(f"{name}: CWT {transform_elapsed:.4f}s; {result.grid.scales.size} scales", flush=True)
        grid = result.grid
        del result
    summary_figures(output, rows)
    with (output / "metrics.csv").open("w", newline="", encoding="utf8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_json(output / "metrics.json", rows)
    write_json(output / "provenance.json", provenance)
    worker = subprocess.run(
        [sys.executable, "-m", "benchmarks.performance", str(output / "performance_80000.json")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    (output / "performance_stdout.txt").write_text(worker.stdout, encoding="utf8")
    (output / "performance_stderr.txt").write_text(worker.stderr, encoding="utf8")
    if worker.returncode:
        raise RuntimeError(f"performance worker failed: {worker.stderr}")
    protocol = ROOT / "docs/TASK-CWT-002_PROTOCOL.md"
    source_paths = sorted(
        list((ROOT / "src").rglob("*.py"))
        + list((ROOT / "benchmarks").rglob("*.py"))
        + list((ROOT / "tests").rglob("*.py"))
        + list((ROOT / "configs").glob("*.toml"))
        + [protocol, ROOT / "pyproject.toml"]
    )
    manifest = {
        "task": "TASK-CWT-002",
        "date_asia_shanghai": timestamp,
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "git_branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip(),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "PyWavelets", "matplotlib", "pytest", "ruff", "mypy")
        },
        "units": {"time": "s", "voltage": "V", "frequency": "Hz", "velocity": "m/s"},
        "cwt": asdict(config),
        "scales": grid.scales.tolist(),
        "frequency_hz": grid.frequency_hz.tolist(),
        "support_radius_samples": grid.support_radius_samples.tolist(),
        "analytic_alias_tail_fraction": grid.alias_tail_fraction.tolist(),
        "normalization_default": "raw",
        "normalization_experiment": "abs(W)/sqrt(scale)",
        "wavelength_m": settings["wavelength_m"],
        "zero_optical_offset": True,
        "sampling_period_s": 1 / settings["sampling_rate_hz"],
        "evaluation_mask": (
            "known active truth; fixed full-bank support interior; never quality-filtered"
        ),
        "quality_policy": (
            "known white Gaussian sigma, record alpha=0.01 union bound; full bank interior"
        ),
        "plotting_decimation_only": True,
        "input_decimation": False,
        "chunking": False,
        "coefficients_saved": False,
        "synthetic_cases": len(provenance),
        "metric_rows": len(rows),
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source_paths
        },
        "pywt_cwt_source_sha256": hashlib.sha256(inspect.getsource(pywt.cwt).encode()).hexdigest(),
        "method_source": "https://pywavelets.readthedocs.io/en/latest/ref/cwt.html",
        "elapsed_full_benchmark_s": time.perf_counter() - start_run,
        "memory_method": "native Windows lifetime peak; per-case peaks share prior process history",
        "scientific_limitations": [
            "No real data validation",
            "No STFT comparison",
            "No signed velocity",
            "No calibrated noise sigma estimator",
            "No multi-branch correctness claim",
        ],
    }
    write_json(output / "manifest.json", manifest)
    print(f"OUTPUT: {output}", flush=True)
    return output


if __name__ == "__main__":
    run()
