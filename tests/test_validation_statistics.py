"""Waveform-level statistical semantics; deterministic probes, no study data."""

import numpy as np
import pytest

from benchmarks.validation.summarize import bootstrap, wilson


def test_paired_waveform_bootstrap_and_record_uncertainty() -> None:
    a = np.arange(20, dtype=np.float64) + 10
    b = a + 5
    assert bootstrap(a - b) == [-5.0, -5.0]
    low, high = bootstrap(np.linspace(-3, 3, 20))
    assert low < 0 < high
    low, high = wilson(0, 40)
    assert low == pytest.approx(0, abs=1e-15)
    assert 0.08 < high < 0.1  # Zero false records cannot certify a zero underlying FPR.
    low, high = wilson(2, 40)
    assert low < 0.05 < high
