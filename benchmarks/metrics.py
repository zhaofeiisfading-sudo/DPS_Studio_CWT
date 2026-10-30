"""Evaluation masks never depend on candidate quality or observed estimation error."""

import numpy as np

from pdv_cwt import FrequencyCandidate, QualityDiagnostics, SyntheticCase, apparent_velocity
from pdv_cwt.models import BoolArray, FloatArray


def _errors(error: FloatArray, mask: BoolArray) -> dict[str, float | int | None]:
    selected = error[mask]
    if not selected.size:
        return {"count": 0, "rmse_hz": None, "mae_hz": None, "bias_hz": None}
    return {
        "count": int(selected.size),
        "rmse_hz": float(np.sqrt(np.mean(selected**2))),
        "mae_hz": float(np.mean(np.abs(selected))),
        "bias_hz": float(np.mean(selected)),
    }


def evaluate(
    case: SyntheticCase,
    candidate: FrequencyCandidate,
    quality: QualityDiagnostics,
    *,
    wavelength_m: float,
) -> dict[str, float | int | str | None]:
    valid = case.active & np.isfinite(case.true_frequency_hz)
    error = candidate.frequency_hz - case.true_frequency_hz
    row: dict[str, float | int | str | None] = {
        "normalization": candidate.normalization,
        "finite_candidate_coverage": float(np.mean(np.isfinite(candidate.frequency_hz))),
        "quality_pass_coverage": float(np.mean(quality.passed)),
        "bank_interior_fraction": float(np.mean(~quality.bank_edge_affected)),
        "quality_pass_given_active": (
            float(np.mean(quality.passed[valid])) if np.any(valid) else None
        ),
        "quality_false_positive_given_inactive": (
            float(np.mean(quality.passed[~case.active])) if np.any(~case.active) else None
        ),
        "above_noise_given_inactive": (
            float(np.mean(quality.above_noise[~case.active])) if np.any(~case.active) else None
        ),
        "noise_sigma_v": case.noise_sigma_v,
        "seed": case.seed,
    }
    for region, mask in (
        ("all", valid),
        ("interior", valid & ~quality.bank_edge_affected),
        ("edge", valid & quality.bank_edge_affected),
    ):
        for key, value in _errors(error, mask).items():
            row[f"{region}_{key}"] = value
        if np.any(mask):
            estimated_v = apparent_velocity(
                candidate.frequency_hz[mask], wavelength_m=wavelength_m, zero_optical_offset=True
            )
            true_v = apparent_velocity(
                case.true_frequency_hz[mask], wavelength_m=wavelength_m, zero_optical_offset=True
            )
            row[f"{region}_velocity_rmse_m_per_s"] = float(
                np.sqrt(np.mean((estimated_v - true_v) ** 2))
            )
        else:
            row[f"{region}_velocity_rmse_m_per_s"] = None
    return row
