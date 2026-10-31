"""Explicit score definitions, spectral support and separate onset diagnostics."""

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np

from benchmarks.comparison.core import STFTConfig, common_indices, stft_transform
from pdv_cwt.frequency import CWTConfig
from pdv_cwt.models import BoolArray, FloatArray, IntArray, SampledSignal
from pdv_cwt.resources import memory_snapshot
from pdv_cwt.transform import CWTResult, compute_cwt

METHODS = ("A0", "A1", "A2", "balanced", "high_time")


@dataclass
class Bank:
    hz: FloatArray
    centers: IntArray
    edge: BoolArray
    score: FloatArray
    predicted: FloatArray
    peak: FloatArray
    metadata: dict[str, Any]


def score_response(raw: FloatArray, scales: FloatArray, mode: str, rms: FloatArray) -> FloatArray:
    if mode == "A0":
        return raw
    if mode == "A1":
        return np.asarray(raw / np.sqrt(scales)[:, None])
    if mode != "A2":
        raise ValueError("unknown response strategy")
    if rms.shape != scales.shape or not np.all(np.isfinite(rms)) or np.any(rms <= 0):
        raise ValueError("independent positive noise rms required")
    return np.asarray(raw / rms[:, None])


def cwt(signal: SampledSignal, voices: int = 24) -> tuple[CWTResult, float]:
    available = memory_snapshot()["available_physical_bytes"]
    start = perf_counter()
    result = compute_cwt(
        signal,
        CWTConfig(voices_per_octave=voices, max_memory_bytes=2 * 1024**3),
        available_memory_bytes=available if isinstance(available, int) else None,
    )
    return result, perf_counter() - start


def bank(
    score: FloatArray,
    hz: FloatArray,
    centers: IntArray,
    edge: BoolArray,
    metadata: dict[str, Any] | None = None,
) -> Bank:
    selected = np.argmax(score, axis=0)
    return Bank(
        hz,
        centers,
        edge,
        score,
        hz[selected],
        score[selected, np.arange(centers.size)],
        {} if metadata is None else metadata,
    )


def cwt_banks(result: CWTResult, rms: FloatArray) -> dict[str, Bank]:
    centers = common_indices(result.signal.time_s.size)
    radius = int(result.grid.support_radius_samples.max())
    edge = np.minimum(centers, result.signal.time_s.size - 1 - centers) < radius
    raw = np.abs(result.coefficients[:, centers])
    return {
        mode: bank(
            score_response(raw, result.grid.scales, mode, rms),
            result.grid.frequency_hz,
            centers,
            edge,
        )
        for mode in METHODS[:3]
    }


def physical_config(fs: float, high_time: bool = False) -> STFTConfig:
    factor = 2 if fs > 60e9 else 1
    length = (512 if high_time else 768) * factor
    return STFTConfig(length, length - 128 * factor, 128 * factor, 4096 * factor)


def stft_bank(signal: SampledSignal, high_time: bool = False, physical: bool = False) -> Bank:
    cfg = (
        physical_config(signal.sampling_rate_hz, high_time)
        if physical
        else (STFTConfig(512, 384) if high_time else STFTConfig())
    )
    available = memory_snapshot()["available_physical_bytes"]
    coeff, hz, centers, edge, metadata = stft_transform(
        signal, cfg, available_bytes=available if isinstance(available, int) else None
    )
    return bank(np.abs(coeff), hz, centers, edge, metadata)


def support(score: FloatArray, hz: FloatArray, truth: FloatArray) -> dict[str, FloatArray]:
    """One matched local peak per time, ranked among internal local peaks only."""
    peaks = np.zeros_like(score, dtype=np.bool_)
    peaks[1:-1] = (score[1:-1] > score[:-2]) & (score[1:-1] >= score[2:])
    tolerance = np.maximum(20e6, 2 * truth * (2 ** (1 / 24) - 1))
    match = peaks & (np.abs(hz[:, None] - truth) <= tolerance)
    candidate = np.where(match, score, -np.inf)
    index = np.argmax(candidate, axis=0)
    columns = np.arange(truth.size)
    matched = candidate[index, columns]
    present = np.any(match, axis=0)
    ranks = 1 + np.sum(peaks & (score > matched), axis=0)
    median = np.median(score, axis=0)
    strength = np.divide(matched, median, out=np.full(truth.size, np.nan), where=median > 0)
    selected = hz[np.argmax(score, axis=0)]
    return dict(
        presence=present.astype(float),
        rank=np.where(present, ranks, np.nan),
        relative_background=np.where(present, strength, np.nan),
        response=np.where(present, matched, np.nan),
        supported=(present & (strength >= 2)).astype(float),
        strongest_accurate=(np.abs(selected - truth) <= tolerance).astype(float),
        nearest_grid_distance_hz=np.min(np.abs(hz[:, None] - truth), axis=0),
        top3=(present & (ranks <= 3)).astype(float),
        top5=(present & (ranks <= 5)).astype(float),
    )


def detection(
    peak: FloatArray,
    time_s: FloatArray,
    active: BoolArray,
    interior: BoolArray,
    threshold: float,
    onset_s: float | None,
) -> dict[str, Any]:
    detected = (peak > threshold) & interior
    negative = ~active & interior
    crossings = np.flatnonzero(detected)
    error = (
        float(time_s[crossings[0]] - onset_s) if crossings.size and onset_s is not None else None
    )
    hit = bool(np.any(detected & active))
    return dict(
        frame_fpr=float(np.mean(detected[negative])) if negative.any() else None,
        record_fpr=bool(np.any(detected)) if not active.any() else None,
        detection_probability=hit if active.any() else None,
        missed_detection=not hit if active.any() else None,
        early_trigger=bool(np.any(detected & (time_s < onset_s))) if onset_s is not None else None,
        onset_error_s=error,
        no_record_trigger=not bool(crossings.size),
        active_frame_detection_rate=float(np.mean(detected[active & interior]))
        if np.any(active & interior)
        else None,
    )
