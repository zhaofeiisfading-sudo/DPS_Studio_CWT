"""Independent support/alias/noise flags. These never alter frequency candidates."""

from dataclasses import dataclass
from math import isfinite, log

import numpy as np
import pywt

from .frequency import FrequencyCandidate
from .models import BoolArray, ComplexArray, FloatArray
from .transform import CWTResult


def discrete_filter(scale: float, *, precision: int = 18) -> ComplexArray:
    """Effective integrated/differenced kernel, matching installed pywt.cwt.

    Endpoint padding includes the tiny residual wavelet integral. Absolute shift
    is irrelevant for its energy; impulse tests verify the energy identity.
    """
    if not isfinite(scale) or scale <= 0 or not 12 <= precision <= 20:
        raise ValueError("invalid scale or precision")
    integrated, x = pywt.integrate_wavelet("cmor1.5-1.0", precision=precision)
    return _kernel(scale, np.conj(integrated), x)


def _kernel(scale: float, conjugate_integral: ComplexArray, x: FloatArray) -> ComplexArray:
    step = float(x[1] - x[0])
    index = (np.arange(scale * float(x[-1] - x[0]) + 1) / (scale * step)).astype(int)
    index = index[index < conjugate_integral.size]
    kernel = conjugate_integral[index][::-1]
    return np.asarray(-np.sqrt(scale) * np.diff(np.pad(kernel, (1, 1))), dtype=np.complex128)


def filter_energies(result: CWTResult) -> FloatArray:
    integrated, x = pywt.integrate_wavelet(result.config.wavelet, precision=result.config.precision)
    conjugate_integral = np.asarray(np.conj(integrated), dtype=np.complex128)
    return np.array(
        [
            float(np.sum(np.abs(_kernel(float(a), conjugate_integral, x)) ** 2))
            for a in result.grid.scales
        ],
        dtype=np.float64,
    )


@dataclass(frozen=True)
class QualityDiagnostics:
    candidate_edge_affected: BoolArray
    bank_edge_affected: BoolArray
    alias_risk: BoolArray
    above_noise: BoolArray
    passed: BoolArray
    raw_noise_threshold: FloatArray
    noise_model: str
    record_alpha: float


def diagnose(
    result: CWTResult,
    candidate: FrequencyCandidate,
    *,
    noise_sigma_v: float | None = None,
    record_alpha: float = 0.01,
) -> QualityDiagnostics:
    if not isfinite(record_alpha) or not 0 < record_alpha < 1:
        raise ValueError("record_alpha must be finite and in (0,1)")
    if noise_sigma_v is not None and (not isfinite(noise_sigma_v) or noise_sigma_v < 0):
        raise ValueError("noise_sigma_v must be finite and nonnegative, or None for UNKNOWN")
    if candidate.time_s is not result.signal.time_s:
        raise ValueError("candidate must originate from this CWT result")
    count = int(result.signal.time_s.size)
    distance = np.minimum(np.arange(count), np.arange(count)[::-1])
    selected_radius = result.grid.support_radius_samples[candidate.scale_index]
    edge = distance < selected_radius
    bank_edge = distance < np.max(result.grid.support_radius_samples)
    alias = (
        result.grid.alias_tail_fraction[candidate.scale_index] > result.config.alias_tail_tolerance
    )
    if noise_sigma_v is None:
        threshold = np.full(count, np.nan)
        above = np.zeros(count, dtype=np.bool_)
        model = "UNKNOWN: no explicit white-Gaussian noise sigma provided"
    else:
        energy = filter_energies(result)[candidate.scale_index]
        threshold = noise_sigma_v * np.sqrt(
            4 * energy * log(4 * count * result.grid.scales.size / record_alpha)
        )
        above = candidate.raw_magnitude > threshold
        model = "known iid zero-mean Gaussian voltage noise; conservative record-wise union bound"
    passed = above & ~bank_edge & ~alias
    for array in (edge, bank_edge, alias, above, passed, threshold):
        array.setflags(write=False)
    return QualityDiagnostics(edge, bank_edge, alias, above, passed, threshold, model, record_alpha)
