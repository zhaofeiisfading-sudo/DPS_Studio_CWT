"""Initial complex Morlet research core. No physical-velocity validation implied."""

from .diagnostics import QualityDiagnostics, diagnose
from .frequency import CWTConfig, FrequencyCandidate, make_frequency_grid, strongest_candidate
from .models import SampledSignal
from .physics import apparent_velocity
from .synthetic import SyntheticCase, synthetic_pdv
from .transform import CWTResult, compute_cwt, estimate_memory

__all__ = [
    "CWTConfig",
    "CWTResult",
    "FrequencyCandidate",
    "QualityDiagnostics",
    "SampledSignal",
    "SyntheticCase",
    "apparent_velocity",
    "compute_cwt",
    "diagnose",
    "estimate_memory",
    "make_frequency_grid",
    "strongest_candidate",
    "synthetic_pdv",
]
