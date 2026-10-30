"""Scale mapping and independent frame-wise CWT strongest-response candidates."""

from dataclasses import dataclass
from math import ceil, erfc, isfinite, log2, pi, sqrt
from typing import TYPE_CHECKING, Literal

import numpy as np
import pywt

from .models import FloatArray, IntArray

if TYPE_CHECKING:
    from .transform import CWTResult

Normalization = Literal["raw", "scale_amplitude"]


@dataclass(frozen=True)
class CWTConfig:
    frequency_min_hz: float = 0.1e9
    frequency_max_hz: float = 6e9
    voices_per_octave: int = 24
    wavelet: str = "cmor1.5-1.0"
    precision: int = 18
    max_memory_bytes: int = 768 * 1024**2
    alias_tail_tolerance: float = 1e-6
    allow_alias_risk: bool = False

    def __post_init__(self) -> None:
        if self.wavelet != "cmor1.5-1.0":
            raise ValueError("v1 supports only the initial cmor1.5-1.0 research wavelet")
        if not (isfinite(self.frequency_min_hz) and isfinite(self.frequency_max_hz)):
            raise ValueError("frequency limits must be finite Hz")
        if not 0 < self.frequency_min_hz < self.frequency_max_hz:
            raise ValueError("require 0 < frequency_min_hz < frequency_max_hz")
        for name, value, lower, upper in (
            ("voices_per_octave", self.voices_per_octave, 1, 256),
            ("precision", self.precision, 12, 20),
            ("max_memory_bytes", self.max_memory_bytes, 1, 2**50),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
                raise ValueError(f"invalid {name}")
        if not isfinite(self.alias_tail_tolerance) or not 0 < self.alias_tail_tolerance < 1:
            raise ValueError("alias_tail_tolerance must be finite and in (0,1)")


@dataclass(frozen=True)
class FrequencyGrid:
    frequency_hz: FloatArray
    scales: FloatArray
    alias_tail_fraction: FloatArray
    support_radius_samples: IntArray


def make_frequency_grid(config: CWTConfig, sampling_period_s: float) -> FrequencyGrid:
    if not isfinite(sampling_period_s) or sampling_period_s <= 0:
        raise ValueError("sampling_period_s must be finite and positive")
    if config.frequency_max_hz >= 0.5 / sampling_period_s:
        raise ValueError("frequency band must lie strictly below Nyquist")
    octaves = log2(config.frequency_max_hz) - log2(config.frequency_min_hz)
    count = int(np.floor(config.voices_per_octave * octaves))
    if count > 100_000:
        raise ValueError("frequency grid exceeds the v1 scale-count limit")
    frequencies = config.frequency_min_hz * np.exp2(
        np.arange(count + 1, dtype=np.float64) / config.voices_per_octave
    )
    frequencies = frequencies[frequencies < config.frequency_max_hz * (1 - 1e-14)]
    frequencies = np.append(frequencies, config.frequency_max_hz)
    scales = np.asarray(
        pywt.frequency2scale(
            config.wavelet, frequencies * sampling_period_s, precision=config.precision
        ),
        dtype=np.float64,
    )
    if not np.all(np.isfinite(scales)) or np.max(scales) * 16 + 1 > 2**config.precision:
        raise ValueError("wavelet integration grid too coarse for requested maximum scale")
    mapped = (
        np.asarray(
            pywt.scale2frequency(config.wavelet, scales, precision=config.precision),
            dtype=np.float64,
        )
        / sampling_period_s
    )
    if not np.allclose(mapped, frequencies, rtol=1e-12, atol=0):
        raise RuntimeError("scale/frequency round-trip failed")
    # Analytic continuous Morlet spectral energy outside sampled [-fs/2,fs/2].
    factor = sqrt(2) * pi * sqrt(1.5)
    tails = np.array(
        [0.5 * (erfc(factor * (a / 2 - 1)) + erfc(factor * (a / 2 + 1))) for a in scales],
        dtype=np.float64,
    )
    if np.any(tails > config.alias_tail_tolerance) and not config.allow_alias_risk:
        raise ValueError("discrete-scale aliasing risk below Nyquist; band explicitly refused")
    radii = np.array([ceil(8 * a) + 2 for a in scales], dtype=np.int64)
    for array in (mapped, scales, tails, radii):
        array.setflags(write=False)
    return FrequencyGrid(mapped, scales, tails, radii)


@dataclass(frozen=True)
class FrequencyCandidate:
    time_s: FloatArray
    frequency_hz: FloatArray
    scale_index: IntArray
    raw_magnitude: FloatArray
    response: FloatArray
    normalization: Normalization


def strongest_candidate(
    result: "CWTResult", *, normalization: Normalization = "raw"
) -> FrequencyCandidate:
    if normalization not in ("raw", "scale_amplitude"):
        raise ValueError("normalization must be raw or scale_amplitude")
    score = np.abs(result.coefficients)
    if normalization == "scale_amplitude":
        score /= np.sqrt(result.grid.scales)[:, None]
    # Every sample retains a candidate, including zero signal and pure noise.
    # Ties select the first (lowest frequency) scale, explicitly, without repair.
    index = np.asarray(np.argmax(score, axis=0), dtype=np.int64)
    columns = np.arange(index.size)
    raw = np.abs(result.coefficients[index, columns])
    response = score[index, columns]
    hz = result.grid.frequency_hz[index].copy()
    for array in (index, raw, response, hz):
        array.setflags(write=False)
    return FrequencyCandidate(result.signal.time_s, hz, index, raw, response, normalization)
