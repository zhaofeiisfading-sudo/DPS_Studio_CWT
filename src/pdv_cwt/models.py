"""Validated, owned, read-only samples in explicit SI units; no preprocessing."""

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
IntArray = NDArray[np.int64]
ComplexArray = NDArray[np.complex128]


def real_vector(value: ArrayLike, name: str) -> FloatArray:
    original = np.asarray(value)
    if original.ndim != 1 or np.iscomplexobj(original) or original.dtype.kind not in "iuf":
        raise ValueError(f"{name} must be a one-dimensional real numeric array")
    result = np.array(original, dtype=np.float64, copy=True)
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain finite values")
    return result


@dataclass(frozen=True, init=False)
class SampledSignal:
    time_s: FloatArray
    voltage_v: FloatArray
    sampling_period_s: float = field(init=False)

    def __init__(self, time_s: ArrayLike, voltage_v: ArrayLike) -> None:
        time = real_vector(time_s, "time_s")
        voltage = real_vector(voltage_v, "voltage_v")
        if time.size < 4 or time.size != voltage.size:
            raise ValueError("time_s and voltage_v must have equal length >= 4")
        delta = np.diff(time)
        if np.any(delta <= 0):
            raise ValueError("time_s must be strictly increasing")
        dt = float((time[-1] - time[0]) / (time.size - 1))
        roundoff = 8 * np.finfo(np.float64).eps * float(np.max(np.abs(time)))
        if not np.isfinite(dt) or roundoff > 1e-3 * dt:
            raise ValueError("time origin/precision cannot establish uniform sampling reliably")
        if np.any(np.abs(delta - dt) > max(dt * 1e-6, roundoff)):
            raise ValueError("non-uniform sampling is unsupported; no resampling performed")
        time.setflags(write=False)
        voltage.setflags(write=False)
        object.__setattr__(self, "time_s", time)
        object.__setattr__(self, "voltage_v", voltage)
        object.__setattr__(self, "sampling_period_s", dt)

    @property
    def sampling_rate_hz(self) -> float:
        return 1.0 / self.sampling_period_s
