"""The only production transform engine in this research core: pywt.cwt FFT."""

from dataclasses import dataclass
from math import ceil

import numpy as np
import pywt
from scipy.fft import next_fast_len

from .frequency import CWTConfig, FrequencyGrid, make_frequency_grid
from .models import ComplexArray, SampledSignal


@dataclass(frozen=True)
class MemoryEstimate:
    coefficient_bytes: int
    working_bytes: int
    fft_length: int
    integration_workspace_bytes: int


def estimate_memory(samples: int, grid: FrequencyGrid, *, precision: int = 18) -> MemoryEstimate:
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 4:
        raise ValueError("samples must be an integer >= 4")
    nfft = int(next_fast_len(samples + ceil(16 * float(np.max(grid.scales))) + 1))
    coefficient_bytes = samples * int(grid.scales.size) * 16
    # 3 complex matrices allow CWT plus response/diagnostic temporaries; 12 FFT buffers.
    # A conservative planning estimate, not an allocator/OS guarantee.
    if not isinstance(precision, int) or not 12 <= precision <= 20:
        raise ValueError("precision must be an integer in [12,20]")
    integration_bytes = 2**precision * 16 * 8
    working_bytes = 3 * coefficient_bytes + nfft * 16 * 12 + samples * 8 * 16 + integration_bytes
    return MemoryEstimate(coefficient_bytes, working_bytes, nfft, integration_bytes)


@dataclass(frozen=True)
class CWTResult:
    signal: SampledSignal
    config: CWTConfig
    grid: FrequencyGrid
    coefficients: ComplexArray
    memory: MemoryEstimate


def compute_cwt(
    signal: SampledSignal,
    config: CWTConfig | None = None,
    *,
    available_memory_bytes: int | None = None,
) -> CWTResult:
    config = CWTConfig() if config is None else config
    grid = make_frequency_grid(config, signal.sampling_period_s)
    memory = estimate_memory(int(signal.time_s.size), grid, precision=config.precision)
    if memory.working_bytes > config.max_memory_bytes:
        raise MemoryError(
            f"CWT preflight estimate {memory.working_bytes} exceeds configured budget"
        )
    if available_memory_bytes is not None and memory.working_bytes > available_memory_bytes * 0.7:
        raise MemoryError("CWT preflight exceeds 70% of explicitly supplied available RAM")
    coefficients, frequency_hz = pywt.cwt(
        signal.voltage_v,
        grid.scales,
        config.wavelet,
        sampling_period=signal.sampling_period_s,
        method="fft",
        precision=config.precision,
    )
    values = np.asarray(coefficients, dtype=np.complex128)
    if values.shape != (grid.scales.size, signal.time_s.size):
        raise RuntimeError("unexpected CWT coefficient shape")
    if not np.allclose(frequency_hz, grid.frequency_hz, rtol=1e-12, atol=0):
        raise RuntimeError("CWT engine frequency mapping disagrees with requested scales")
    if not np.all(np.isfinite(values)):
        raise FloatingPointError("non-finite CWT coefficients; check input dynamic range")
    values.setflags(write=False)
    return CWTResult(signal, config, grid, values, memory)
