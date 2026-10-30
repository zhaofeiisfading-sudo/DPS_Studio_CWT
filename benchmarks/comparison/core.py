"""Fixed Hann controls, sample-exact pairing and response-only diagnostics."""

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

import numpy as np
from scipy.signal import ShortTimeFFT, windows

from pdv_cwt.diagnostics import diagnose
from pdv_cwt.frequency import CWTConfig, strongest_candidate
from pdv_cwt.models import BoolArray, ComplexArray, FloatArray, IntArray, SampledSignal
from pdv_cwt.resources import memory_snapshot
from pdv_cwt.transform import compute_cwt

METHODS = ("cwt", "balanced", "high_time")
CWT_CONFIG = CWTConfig(max_memory_bytes=2 * 1024**3)


@dataclass(frozen=True)
class STFTConfig:
    window: int = 768
    overlap: int = 640
    hop: int = 128
    nfft: int = 4096
    low_hz: float = 0.1e9
    high_hz: float = 6e9
    max_memory_bytes: int = 2 * 1024**3

    def __post_init__(self) -> None:
        values = (self.window, self.overlap, self.hop, self.nfft, self.max_memory_bytes)
        if any(type(v) is not int for v in values):
            raise ValueError("integer STFT dimensions/budget required")
        if not 0 <= self.overlap < self.window or self.hop != self.window - self.overlap:
            raise ValueError("hop must equal window minus overlap")
        if self.window % 2 or self.nfft < self.window or self.max_memory_bytes <= 0:
            raise ValueError("even window, nfft >= window and positive budget required")
        if not np.isfinite([self.low_hz, self.high_hz]).all():
            raise ValueError("finite frequency band required")
        if not 0 < self.low_hz < self.high_hz:
            raise ValueError("invalid frequency band")


def common_indices(samples: int, hop: int = 128) -> IntArray:
    if samples < 4 or hop <= 0:
        raise ValueError("invalid sample count/hop")
    return np.arange(0, samples, hop, dtype=np.int64)


def stft_transform(
    signal: SampledSignal, config: STFTConfig, *, available_bytes: int | None = None
) -> tuple[ComplexArray, FloatArray, IntArray, BoolArray, dict[str, Any]]:
    if config.high_hz >= signal.sampling_rate_hz / 2:
        raise ValueError("band must lie below Nyquist")
    centers = common_indices(signal.time_s.size, config.hop)
    # Includes full one-sided output, a second matrix, response and bounded FFT workspace.
    estimate = int((config.nfft // 2 + 1) * centers.size * 48 + config.nfft * 16 * 16)
    if estimate > config.max_memory_bytes:
        raise MemoryError("STFT estimate exceeds budget")
    if available_bytes is not None and estimate > 0.7 * available_bytes:
        raise MemoryError("STFT estimate exceeds 70% of available RAM")
    window = np.asarray(windows.hann(config.window, sym=False), dtype=np.float64)
    engine = ShortTimeFFT(
        window,
        config.hop,
        signal.sampling_rate_hz,
        fft_mode="onesided",
        mfft=config.nfft,
        scale_to="magnitude",
    )
    coefficients = np.asarray(
        engine.stft(signal.voltage_v, p0=0, p1=int(centers.size), padding="zeros"),
        dtype=np.complex128,
    )
    hz = np.asarray(engine.f, dtype=np.float64)
    band = (hz >= config.low_hz) & (hz <= config.high_hz)
    if not np.any(band):
        raise ValueError("no FFT bins in requested band")
    edge = (centers - config.window // 2 < 0) | (centers + config.window // 2 > signal.time_s.size)
    metadata = dict(
        config=asdict(config),
        window="periodic Hann",
        padding="zero",
        center_rule="c=128*p; window [c-L/2,c+L/2); input.time_s[c]",
        scaling="2*abs(ShortTimeFFT magnitude onesided); no DC/Nyquist in band",
        units="V; sinusoidal peak amplitude estimate, not CWT coefficient units",
        window_duration_s=config.window * signal.sampling_period_s,
        frame_interval_s=config.hop * signal.sampling_period_s,
        fft_grid_spacing_hz=signal.sampling_rate_hz / config.nfft,
        nearest_grid_error_bound_hz=signal.sampling_rate_hz / config.nfft / 2,
        hann_enbw_hz=signal.sampling_rate_hz * float(np.sum(window**2) / np.sum(window) ** 2),
        first_null_to_null_hz=4 * signal.sampling_rate_hz / config.window,
        preflight_memory_bytes=estimate,
        full_onesided_shape=list(coefficients.shape),
    )
    return coefficients[band] * 2, hz[band], centers, edge, metadata


@dataclass
class Analysis:
    native: dict[str, Any]
    frequency_hz: FloatArray
    response: FloatArray
    metadata: dict[str, Any]


def response_diagnostics(score: FloatArray) -> dict[str, FloatArray]:
    count = score.shape[1]
    median = np.empty(count)
    q90 = np.empty(count)
    concentration = np.empty(count)
    for start in range(0, count, 4096):
        part = score[:, start : start + 4096]
        median[start : start + part.shape[1]] = np.median(part, axis=0)
        q90[start : start + part.shape[1]] = np.quantile(part, 0.9, axis=0)
        power = part**2
        total = np.sum(power, axis=0)
        concentration[start : start + part.shape[1]] = np.divide(
            np.sum(power**2, axis=0),
            total**2,
            out=np.zeros(total.size),
            where=total > 0,
        )
    peak = np.max(score, axis=0)
    ratio = np.divide(peak, median, out=np.full(count, np.nan), where=median > 0)
    return dict(
        peak=peak, median=median, q90=q90, peak_to_median=ratio, concentration=concentration
    )


def analyze(signal: SampledSignal, method: str) -> Analysis:
    if method not in METHODS:
        raise ValueError(f"unknown comparison method: {method}")
    before = memory_snapshot()
    available = before["available_physical_bytes"]
    available_bytes = available if isinstance(available, int) else None
    start = perf_counter()
    transform_start = start
    if method == "cwt":
        result = compute_cwt(signal, CWT_CONFIG, available_memory_bytes=available_bytes)
        transform_s = perf_counter() - transform_start
        extract_start = perf_counter()
        candidate = strongest_candidate(result)
        extract_s = perf_counter() - extract_start
        score = np.abs(result.coefficients)
        frequency = result.grid.frequency_hz
        centers = np.arange(signal.time_s.size, dtype=np.int64)
        selected = candidate.scale_index
        selected_hz = candidate.frequency_hz
        quality = diagnose(result, candidate)
        edge = quality.bank_edge_affected
        selected_edge = quality.candidate_edge_affected
        alias = quality.alias_risk
        metadata: dict[str, Any] = dict(
            config=asdict(CWT_CONFIG),
            scales=result.grid.scales.tolist(),
            support_radius_samples=result.grid.support_radius_samples.tolist(),
            alias_tail_fraction=result.grid.alias_tail_fraction.tolist(),
            units="V; PyWavelets discrete-scale coefficient abs(W)",
            boundary="bank and selected ceil(8*scale)+2; zero convolution extension",
            preflight_memory_bytes=result.memory.working_bytes,
            coefficient_shape=list(result.coefficients.shape),
            coefficient_bytes=result.coefficients.nbytes,
        )
    else:
        config = STFTConfig() if method == "balanced" else STFTConfig(512, 384)
        coefficients, frequency, centers, edge, metadata = stft_transform(
            signal,
            config,
            available_bytes=available_bytes,
        )
        transform_s = perf_counter() - transform_start
        extract_start = perf_counter()
        score = np.abs(coefficients)
        selected = np.asarray(np.argmax(score, axis=0), dtype=np.int64)
        selected_hz = frequency[selected]
        extract_s = perf_counter() - extract_start
        selected_edge = edge.copy()
        alias = np.zeros(centers.size, dtype=np.bool_)
        metadata.update(
            coefficient_shape=list(coefficients.shape), coefficient_bytes=coefficients.nbytes
        )
    native: dict[str, Any] = dict(
        sample_index=centers,
        time_s=signal.time_s[centers],
        frequency_hz=selected_hz,
        frequency_index=selected,
        bank_edge=edge,
        selected_edge=selected_edge,
        alias_risk=alias,
    )
    native.update(response_diagnostics(score))
    after = memory_snapshot()
    metadata.update(
        method=method,
        transform_s=transform_s,
        strongest_s=extract_s,
        analysis_s=perf_counter() - start,
        peak_working_set_bytes=after["peak_working_set_bytes"],
        memory_before=before,
        memory_after=after,
        frequency_hz=frequency.tolist(),
        samples=int(signal.time_s.size),
        sampling_period_s=signal.sampling_period_s,
        output_candidate_count=int(centers.size),
        quality="UNKNOWN; diagnostic never gates",
        candidate_rule="band argmax; tie lowest Hz; no sub-bin/sub-scale refinement or repair",
        finite_candidate_fraction=float(np.mean(np.isfinite(selected_hz))),
        nominal_center_max_error_s=float(
            np.max(
                np.abs(
                    signal.time_s[centers] - (signal.time_s[0] + centers * signal.sampling_period_s)
                )
            )
        ),
    )
    return Analysis(native, frequency, score, metadata)


def pair_native(analyses: dict[str, Analysis], samples: int) -> dict[str, Any]:
    centers = common_indices(samples)
    paired: dict[str, Any] = {"sample_index": centers}
    edges = []
    for method in METHODS:
        native = analyses[method].native
        positions = centers if method == "cwt" else np.arange(centers.size)
        if not np.array_equal(native["sample_index"][positions], centers):
            raise ValueError("common-grid sample centers disagree")
        for name in (
            "time_s",
            "frequency_hz",
            "peak",
            "median",
            "q90",
            "peak_to_median",
            "concentration",
            "bank_edge",
            "selected_edge",
            "alias_risk",
        ):
            paired[f"{method}_{name}"] = native[name][positions]
        edges.append(native["bank_edge"][positions])
    if not np.array_equal(paired["cwt_time_s"], paired["balanced_time_s"]) or not np.array_equal(
        paired["cwt_time_s"], paired["high_time_time_s"]
    ):
        raise ValueError("common-grid times disagree")
    paired["common_interior"] = ~np.logical_or.reduce(edges)
    return paired
