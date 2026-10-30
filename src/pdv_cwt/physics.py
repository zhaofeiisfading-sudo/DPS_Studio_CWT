"""Zero-offset, unsigned apparent velocity; no direction, angle or window inference."""

from math import isfinite

import numpy as np
from numpy.typing import ArrayLike

from .models import FloatArray, real_vector


def apparent_velocity(
    frequency_hz: ArrayLike, *, wavelength_m: float, zero_optical_offset: bool
) -> FloatArray:
    if not isfinite(wavelength_m) or wavelength_m <= 0:
        raise ValueError("explicit wavelength_m must be finite and positive")
    if zero_optical_offset is not True:
        raise ValueError("only explicitly assumed zero optical offset is supported")
    frequency = real_vector(frequency_hz, "frequency_hz")
    if np.any(frequency < 0):
        raise ValueError("v1 unsigned beat frequency must be nonnegative")
    with np.errstate(over="raise", invalid="raise"):
        return np.asarray((frequency / 2) * wavelength_m, dtype=np.float64)
