"""Seeded synthetic voltage, analytic integrated phase, and separate ground truth."""

from dataclasses import dataclass
from math import isfinite

import numpy as np

from .models import BoolArray, FloatArray, SampledSignal


@dataclass(frozen=True)
class SyntheticCase:
    signal: SampledSignal
    true_frequency_hz: FloatArray
    active: BoolArray
    phase_rad: FloatArray
    noise_sigma_v: float
    seed: int
    recipe: dict[str, float | int | str | None]


def synthetic_pdv(
    *,
    samples: int,
    sampling_rate_hz: float,
    frequency_start_hz: float,
    frequency_end_hz: float | None = None,
    amplitude_v: float = 1.0,
    phase_rad: float = 0.37,
    noise_sigma_v: float = 0.0,
    seed: int,
    pulse_s: tuple[float, float] | None = None,
    time_origin_s: float = 0.0,
) -> SyntheticCase:
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 4:
        raise ValueError("samples must be integer >= 4")
    end = frequency_start_hz if frequency_end_hz is None else frequency_end_hz
    parameters = (
        sampling_rate_hz,
        frequency_start_hz,
        end,
        amplitude_v,
        phase_rad,
        noise_sigma_v,
        time_origin_s,
    )
    if not all(isfinite(x) for x in parameters):
        raise ValueError("synthetic parameters must be finite SI values")
    if sampling_rate_hz <= 0 or not 0 < min(frequency_start_hz, end):
        raise ValueError("positive sample rate and beat frequencies required")
    if max(frequency_start_hz, end) >= sampling_rate_hz / 2:
        raise ValueError("synthetic beat must lie below Nyquist")
    if amplitude_v < 0 or noise_sigma_v < 0:
        raise ValueError("amplitude and noise sigma must be nonnegative")
    time = np.arange(samples, dtype=np.float64) / sampling_rate_hz
    chirp_rate = (end - frequency_start_hz) / float(time[-1])
    phase = phase_rad + 2 * np.pi * (frequency_start_hz * time + 0.5 * chirp_rate * time**2)
    active = np.full(samples, amplitude_v > 0, dtype=np.bool_)
    start_s: float | None = None
    end_s: float | None = None
    if pulse_s is not None:
        start_s, end_s = pulse_s
        if not (isfinite(start_s) and isfinite(end_s) and 0 <= start_s < end_s <= time[-1]):
            raise ValueError("pulse bounds must be finite, ordered and inside the synthetic record")
        active &= (time >= start_s) & (time < end_s)
    voltage = amplitude_v * active * np.cos(phase)
    voltage += np.random.default_rng(seed).normal(0, noise_sigma_v, samples)
    truth = np.where(active, frequency_start_hz + chirp_rate * time, np.nan)
    signal = SampledSignal(time + time_origin_s, voltage)
    for array in (truth, active, phase):
        array.setflags(write=False)
    recipe: dict[str, float | int | str | None] = {
        "generator": "analytic cosine with integrated linear frequency; iid Gaussian voltage noise",
        "samples": samples,
        "sampling_rate_hz": sampling_rate_hz,
        "frequency_start_hz": frequency_start_hz,
        "frequency_end_hz": end,
        "amplitude_v": amplitude_v,
        "phase_rad": phase_rad,
        "noise_sigma_v": noise_sigma_v,
        "seed": seed,
        "pulse_start_s": start_s,
        "pulse_end_s": end_s,
        "time_origin_s": time_origin_s,
        "chirp_rate_hz_per_s": chirp_rate,
    }
    return SyntheticCase(signal, truth, active, phase, noise_sigma_v, seed, recipe)
