"""Supplemental numerical filter audit and transparent summaries of frozen experiments."""

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

from pdv_cwt.diagnostics import discrete_filter


def audit(run: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    if not run.resolve().is_relative_to(root / "artifacts/TASK-CWT-002"):
        raise ValueError("audit output must stay under this TASK's artifacts")
    for name in ("filter_audit.csv", "scientific_assessment.json"):
        if (run / name).exists():
            raise FileExistsError(f"preserving existing evidence: {name}")
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf8"))
    precision = int(manifest["cwt"]["precision"])
    filters: list[dict[str, Any]] = []
    for scale in (1.0, 2.0, 3.0, 4.0, 40 / 6, 8.0, 40.0, 400.0):
        kernel = discrete_filter(scale, precision=precision)
        nfft = max(16384, 2 ** math.ceil(math.log2(kernel.size * 16)))
        spectrum = np.fft.fft(kernel, n=nfft)
        frequency = np.fft.fftfreq(nfft)
        power = np.abs(spectrum) ** 2
        factor = math.sqrt(2) * math.pi * math.sqrt(1.5)
        filters.append(
            {
                "scale": scale,
                "precision": precision,
                "nominal_frequency_over_fs": 1 / scale,
                "measured_peak_frequency_over_fs": float(frequency[np.argmax(power)]),
                "negative_frequency_energy_fraction": float(
                    np.sum(power[frequency < 0]) / power.sum()
                ),
                "nyquist_to_peak_power_ratio": float(power[nfft // 2] / power.max()),
                "analytic_energy_outside_nyquist_fraction": 0.5
                * (math.erfc(factor * (scale / 2 - 1)) + math.erfc(factor * (scale / 2 + 1))),
                "discrete_filter_energy": float(np.sum(np.abs(kernel) ** 2)),
                "kernel_samples": kernel.size,
                "fft_samples_for_diagnostic": nfft,
            }
        )
    with (run / "filter_audit.csv").open("w", newline="", encoding="utf8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(filters[0]))
        writer.writeheader()
        writer.writerows(filters)
    rows: list[dict[str, Any]] = json.loads((run / "metrics.json").read_text(encoding="utf8"))
    checks: list[dict[str, Any]] = []
    for row in rows:
        mode = row["normalization"]
        limit = 0.04 if mode == "raw" else 0.03
        if row["family"] in ("S1", "S4"):
            error = row["interior_rmse_hz"] / row["true_frequency_start_hz"]
            checks.append(
                {
                    "case": row["case"],
                    "normalization": mode,
                    "relative_rmse": error,
                    "limit": limit,
                    "pass": error <= limit,
                }
            )
        if row["case"] == "S3_chirp" and mode == "scale_amplitude":
            error = row["interior_rmse_hz"] / 2.25e9
            checks.append(
                {
                    "case": row["case"],
                    "normalization": mode,
                    "relative_rmse": error,
                    "limit": 0.05,
                    "pass": error <= 0.05,
                }
            )
    aggregate: dict[str, Any] = {}
    for snr in (20, 0, -10):
        for mode in ("raw", "scale_amplitude"):
            group = [
                r
                for r in rows
                if r["case"].startswith(f"S2_snr{snr}_seed") and r["normalization"] == mode
            ]
            rmse = np.array([r["interior_rmse_hz"] for r in group])
            pooled = float(np.sqrt(np.mean(rmse**2)))
            aggregate[f"S2_{snr}dB_{mode}"] = {
                "seeds": [r["seed"] for r in group],
                "interior_pooled_rmse_hz": pooled,
                "rmse_across_seed_sample_std_hz": float(np.std(rmse, ddof=1)),
                "rmse_across_seed_min_max_hz": [float(rmse.min()), float(rmse.max())],
                "pooled_velocity_rmse_m_per_s": pooled * 1550e-9 / 2,
                "interior_mae_mean_hz": float(np.mean([r["interior_mae_hz"] for r in group])),
                "interior_bias_mean_hz": float(np.mean([r["interior_bias_hz"] for r in group])),
                "quality_pass_coverage_mean": float(
                    np.mean([r["quality_pass_coverage"] for r in group])
                ),
            }
    for mode in ("raw", "scale_amplitude"):
        tone_rows = [r for r in rows if r["family"] == "S4" and r["normalization"] == mode]
        values = [r["interior_selected_response_mean"] for r in tone_rows]
        aggregate[f"S4_{mode}"] = {
            "response_min": min(values),
            "response_max": max(values),
            "max_to_min_ratio": max(values) / min(values),
        }
    lag: list[dict[str, Any]] = []
    for mode in ("raw", "scale_amplitude"):
        with np.load(run / "candidates" / f"S3_chirp_{mode}.npz") as trace:
            for level in (1e9, 2e9, 3e9):
                first = np.flatnonzero(trace["frequency_hz"] >= level)[0]
                true_time = (level - 0.5e9) / (3.5e9 / (16383 / 40e9))
                lag.append(
                    {
                        "normalization": mode,
                        "crossing_frequency_hz": level,
                        "first_crossing_lag_s": float(trace["time_s"][first] - true_time),
                    }
                )
    assessment = {
        "task_verdict": "LIMITED",
        "numeric_acceptance_checks": checks,
        "all_preregistered_frequency_checks_passed": all(r["pass"] for r in checks),
        "aggregate": aggregate,
        "crossing_lag_exploratory": lag,
        "lag_caveat": (
            "Post-hoc 1/2/3 GHz crossings include grid quantization and scale bias. "
            "Not identified causal latency or an acceptance criterion."
        ),
        "theory": {
            "nearest_log_grid_max_relative_error": 2 ** (1 / 48) - 1,
            "continuous_raw_ridge_frequency_ratio": 2 / (1 + math.sqrt(1 + 1 / (math.pi**2 * 1.5))),
            "morlet_power_frequency_fwhm_over_center_frequency": (
                math.sqrt(2 * math.log(2)) / (math.pi * math.sqrt(1.5))
            ),
            "morlet_power_time_fwhm_at_1ghz_s": math.sqrt(2 * 1.5 * math.log(2)) * 1e-9,
        },
        "negative_findings": [
            "Scale normalization increases high-frequency noise selection at -10 dB.",
            "sigma=0 is not a reliable pulse detector; leakage/roundoff passes.",
            "Conservative full support excludes ~39% of the 16384-sample record.",
            "Only 3 evaluation noise seeds; zero observed false positives cannot prove zero risk.",
            "No conclusion of superiority to STFT; no real-data evidence.",
        ],
        "filter_audit_caveat": (
            "Analytic tail bound is a screening model, not proof of alias-free discrete filters. "
            "Negative-frequency energy includes integration/discretization artifacts. "
            "Diagnostic FFT padding does not add physical resolving power."
        ),
    }
    (run / "scientific_assessment.json").write_text(
        json.dumps(assessment, indent=2, allow_nan=False), encoding="utf8"
    )
    print(json.dumps(assessment, indent=2))


if __name__ == "__main__":
    audit(Path(sys.argv[1]))
