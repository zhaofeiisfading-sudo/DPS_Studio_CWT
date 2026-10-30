"""Traceable plots and full-sample CSV; display thinning never changes analysis."""

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .diagnostics import QualityDiagnostics
from .frequency import FrequencyCandidate
from .models import FloatArray
from .transform import CWTResult


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def write_table(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )


def scalogram(
    result: CWTResult, output: Path, max_columns: int, *, label: str = ""
) -> dict[str, Any]:
    samples = int(result.signal.time_s.size)
    stride = max(1, int(np.ceil((samples - 1) / (max_columns - 1))))
    indices = np.unique(np.append(np.arange(0, samples, stride), samples - 1))
    # Only selected display columns are materialized; analysis uses the full matrix.
    response = np.abs(result.coefficients[:, indices])
    origin = float(result.signal.time_s[0])
    time_us = (result.signal.time_s[indices] - origin) * 1e6
    frequency_ghz = result.grid.frequency_hz / 1e9
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    mesh = ax.pcolormesh(
        time_us,
        frequency_ghz,
        response,
        shading="nearest",
        cmap="magma",
        vmin=0,
        vmax=max(float(np.max(response)), np.finfo(float).tiny),
    )
    radius_us = result.grid.support_radius_samples[-1] * result.signal.sampling_period_s * 1e6
    bank_us = np.max(result.grid.support_radius_samples) * result.signal.sampling_period_s * 1e6
    ax.axvspan(0, min(bank_us, time_us[-1]), color="cyan", alpha=0.10)
    ax.axvspan(max(0, time_us[-1] - bank_us), time_us[-1], color="cyan", alpha=0.10)
    ax.set(
        xlabel=f"Time since first sample (us); t0 = {origin:.12g} s",
        ylabel="Beat frequency (GHz)",
        title=f"{label or output.parent.name}: cmor1.5-1.0 FFT CWT",
    )
    fig.colorbar(mesh, ax=ax, label="Raw abs(W) (V, discrete sample-scale convention; linear)")
    fig.savefig(output, dpi=180)
    plt.close(fig)
    np.savez_compressed(
        output.with_name("display_response.npz"),
        time_s=result.signal.time_s[indices],
        frequency_hz=result.grid.frequency_hz,
        raw_response_v=response,
        source_sample_indices=indices,
    )
    return {
        "method": "unaveraged display column selection incl first/last; full CWT for analysis",
        "stride": stride,
        "columns": int(indices.size),
        "original_columns": samples,
        "color": "linear raw abs(W), vmin=0, vmax=max of saved display matrix",
        "time_origin_s": origin,
        "bank_edge_radius_us": float(bank_us),
        "minimum_scale_edge_radius_us": float(radius_us),
        "edge_shading": "cyan marks common bank finite-support risk, not a rejection",
    }


def candidate_csv(
    path: Path,
    result: CWTResult,
    candidate: FrequencyCandidate,
    quality: QualityDiagnostics,
    velocity: FloatArray | None,
    *,
    noise_known: bool,
) -> None:
    names = [
        "time_s",
        "candidate_frequency_hz",
        "apparent_velocity_m_s",
        "scale_index",
        "selected_scale",
        "peak_raw_response_v",
        "candidate_edge_risk",
        "bank_edge_risk",
        "aliasing_risk",
        "noise_model_status",
        "quality_evaluation_status",
        "quality_result",
        "above_noise",
        "raw_noise_threshold_v",
    ]
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(names)
        for i in range(candidate.time_s.size):
            writer.writerow(
                [
                    candidate.time_s[i],
                    candidate.frequency_hz[i],
                    "" if velocity is None else velocity[i],
                    int(candidate.scale_index[i]),
                    result.grid.scales[candidate.scale_index[i]],
                    candidate.raw_magnitude[i],
                    int(quality.candidate_edge_affected[i]),
                    int(quality.bank_edge_affected[i]),
                    int(quality.alias_risk[i]),
                    "KNOWN_IID_GAUSSIAN" if noise_known else "UNKNOWN",
                    "EVALUATED" if noise_known else "NOT_EVALUATED",
                    ("PASS" if quality.passed[i] else "FAIL") if noise_known else "UNKNOWN",
                    int(quality.above_noise[i]) if noise_known else "",
                    quality.raw_noise_threshold[i] if noise_known else "",
                ]
            )


def diagnostic_plots(
    output: Path,
    candidate: FrequencyCandidate,
    quality: QualityDiagnostics,
    velocity: FloatArray | None,
) -> None:
    time_us = (candidate.time_s - candidate.time_s[0]) * 1e6
    stride = max(1, int(np.ceil(time_us.size / 5000)))
    show = slice(None, None, stride)
    fig, axes = plt.subplots(3, 1, figsize=(11, 7), sharex=True, layout="constrained")
    axes[0].plot(time_us[show], candidate.frequency_hz[show] / 1e9, lw=0.6)
    axes[0].set_ylabel("Candidate (GHz)")
    axes[1].plot(time_us[show], candidate.raw_magnitude[show], lw=0.6)
    axes[1].set_ylabel("Raw abs(W) (V)")
    axes[2].plot(time_us[show], quality.bank_edge_affected[show], label="Bank edge risk")
    axes[2].plot(time_us[show], quality.alias_risk[show], label="Selected alias risk")
    axes[2].set(xlabel="Time since first sample (us)", ylabel="Flag (0/1)")
    axes[2].legend()
    noise_label = "UNKNOWN; quality NOT EVALUATED" if "UNKNOWN" in quality.noise_model else (
        "explicit iid Gaussian model; per-sample diagnostic only"
    )
    fig.suptitle(f"Raw strongest; no continuity repair\nNoise: {noise_label}")
    fig.savefig(output / "quality_diagnostics.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 4), layout="constrained")
    values = candidate.frequency_hz / 1e9 if velocity is None else velocity
    ax.plot(time_us[show], values[show], lw=0.6)
    ax.set(
        xlabel="Time since first sample (us)",
        ylabel="Candidate frequency (GHz)" if velocity is None else "Unsigned v_app (m/s)",
        title="Frame-wise raw strongest; no continuity repair; not physical validation",
    )
    fig.savefig(
        output / ("candidate_frequency_time.png" if velocity is None else "velocity_time.png"),
        dpi=160,
    )
    plt.close(fig)
