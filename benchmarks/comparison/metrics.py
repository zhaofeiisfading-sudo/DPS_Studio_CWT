"""Ground-truth metrics keep evaluation denominators explicit."""

from typing import Any

import numpy as np
from scipy.stats import rankdata

from pdv_cwt.models import BoolArray, FloatArray

from .cases import Case
from .core import METHODS, Analysis


def frequency_metrics(
    prediction: FloatArray,
    truth: FloatArray,
    interference: FloatArray,
    time_s: FloatArray,
    mask: BoolArray,
) -> dict[str, Any]:
    valid = mask & np.isfinite(truth)
    error = prediction[valid] - truth[valid]
    branch = valid & np.isfinite(interference)
    consecutive = mask[:-1] & mask[1:]
    changes = np.abs(np.diff(prediction)) > 0.5e9
    dt = np.diff(time_s)
    duration = float(np.sum(dt[consecutive]))
    return dict(
        evaluation_points=int(mask.sum()),
        truth_points=int(valid.sum()),
        finite_output_fraction=float(np.mean(np.isfinite(prediction[mask])))
        if mask.any()
        else None,
        rmse_hz=float(np.sqrt(np.mean(error**2))) if error.size else None,
        mae_hz=float(np.mean(np.abs(error))) if error.size else None,
        bias_hz=float(np.mean(error)) if error.size else None,
        wrong_branch_rate=float(
            np.mean(
                np.abs(prediction[branch] - interference[branch])
                < np.abs(prediction[branch] - truth[branch])
            )
        )
        if branch.any()
        else None,
        adjacent_pairs=int(consecutive.sum()),
        jump_over_500mhz_rate=float(np.mean(changes[consecutive])) if consecutive.any() else None,
        jumps_per_s=float(np.sum(changes & consecutive) / duration) if duration > 0 else None,
    )


def auroc(score: FloatArray, active: BoolArray, mask: BoolArray) -> float | None:
    x = score[mask]
    y = active[mask]
    positives = int(y.sum())
    negatives = y.size - positives
    if not positives or not negatives:
        return None
    ranks = np.asarray(rankdata(x), dtype=np.float64)
    return float((ranks[y].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def presence_metrics(
    case: Case,
    analysis: Analysis,
    threshold: float,
    common: dict[str, Any],
) -> dict[str, Any]:
    method = analysis.metadata["method"]
    centers = common["sample_index"]
    t = case.signal.time_s[centers]
    interior = common["common_interior"]
    active = case.active[centers]
    sigma = float(
        case.recipe["noise_sigma_v"] if "noise_sigma_v" in case.recipe else case.recipe["sigma"]
    )
    if sigma <= 0:
        return dict(detection_status="NOT_APPLICABLE_NO_NOISE_OR_ONSET")
    score = common[f"{method}_peak"] / sigma
    detected = score > threshold
    inactive = interior & ~active
    on = float(case.signal.time_s[np.flatnonzero(case.active)[0]]) if active.any() else None
    off = float(case.signal.time_s[np.flatnonzero(case.active)[-1]]) if active.any() else None
    far = inactive.copy()
    if on is not None and off is not None:
        far &= (t < on - 80e-9) | (t > off + 80e-9)
    crossing = np.flatnonzero(interior & detected)
    onset_error = float(t[crossing[0]] - on) if crossing.size and on is not None else None
    return dict(
        detection_status="DIAGNOSTIC_ONLY",
        calibrated_threshold=threshold,
        noise_fpr=float(np.mean(detected[inactive])) if inactive.any() else None,
        far_background_fpr=float(np.mean(detected[far])) if far.any() else None,
        active_frame_detection_rate=float(np.mean(detected[interior & active]))
        if np.any(interior & active)
        else None,
        any_active_hit=bool(np.any(detected & interior & active)) if active.any() else None,
        pre_onset_trigger=bool(np.any(detected & interior & (t < on))) if on is not None else None,
        onset_error_s=onset_error if case.group == "S4" else None,
        onset_missed=bool(not crossing.size) if case.group == "S4" else None,
        response_auroc=auroc(score, active, interior),
        inactive_frames=int(inactive.sum()),
        active_frames=int(np.sum(interior & active)),
    )


def separation_result(case: Case, analysis: Analysis) -> bool | None:
    if case.group != "S6_separation":
        return None
    native = analysis.native
    pos = int(np.argmin(np.abs(native["time_s"] - case.signal.time_s[-1] / 2)))
    spectrum = analysis.response[:, pos]
    peaks = np.flatnonzero((spectrum[1:-1] > spectrum[:-2]) & (spectrum[1:-1] >= spectrum[2:])) + 1
    peak_hz = analysis.frequency_hz[peaks]
    f1, f2 = float(case.truth_hz[0]), float(case.interference_hz[0])
    tolerance = min(0.1e9, (f2 - f1) / 3)
    first = peak_hz[np.abs(peak_hz - f1) <= tolerance]
    second = peak_hz[np.abs(peak_hz - f2) <= tolerance]
    return bool(first.size and second.size and np.any(first[:, None] != second[None, :]))


def case_metrics(
    case: Case,
    analyses: dict[str, Analysis],
    common: dict[str, Any],
    thresholds: dict[str, float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method in METHODS:
        analysis = analyses[method]
        n = analysis.native
        for scope in ("common_all", "common_interior", "native_all", "native_interior"):
            paired = scope.startswith("common")
            indices = common["sample_index"] if paired else n["sample_index"]
            prediction = common[f"{method}_frequency_hz"] if paired else n["frequency_hz"]
            mask = (
                (common["common_interior"] if paired else ~n["bank_edge"])
                if (scope.endswith("interior"))
                else np.ones(indices.size, dtype=np.bool_)
            )
            row = dict(
                case=case.name,
                group=case.group,
                method=method,
                scope=scope,
                fs_hz=case.signal.sampling_rate_hz,
                seed=case.recipe["seed"],
                recipe=case.recipe,
            )
            row.update(
                frequency_metrics(
                    prediction,
                    case.truth_hz[indices],
                    case.interference_hz[indices],
                    case.signal.time_s[indices],
                    mask,
                )
            )
            if scope == "common_interior":
                row.update(presence_metrics(case, analysis, thresholds[method], common))
                row["two_peaks_resolved"] = separation_result(case, analysis)
                for label, low, high in (
                    ("step_before", 180e-9, 200e-9),
                    ("step_after", 200e-9, 220e-9),
                    ("fast_chirp", 190e-9, 210e-9),
                ):
                    applies = (
                        case.group == "S7"
                        and case.recipe["kind"] == "step"
                        and label.startswith("step")
                    ) or (
                        case.group == "S3"
                        and case.recipe["kind"] == "fast"
                        and label == "fast_chirp"
                    )
                    if applies:
                        t = case.signal.time_s[indices]
                        event = mask & (t >= low) & (t < high)
                        row[f"{label}_rmse_hz"] = frequency_metrics(
                            prediction,
                            case.truth_hz[indices],
                            case.interference_hz[indices],
                            t,
                            event,
                        )["rmse_hz"]
            rows.append(row)
    return rows
