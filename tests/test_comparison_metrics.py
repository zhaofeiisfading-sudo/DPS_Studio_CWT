"""Independent checks of evaluation semantics; no experimental files are read."""

import numpy as np
import pytest

from benchmarks.comparison.cases import make_case
from benchmarks.comparison.core import Analysis, common_indices
from benchmarks.comparison.metrics import auroc, frequency_metrics, presence_metrics


def test_presence_keeps_early_false_trigger_and_never_changes_candidates() -> None:
    case = make_case(dict(group="S4", fs=40e9, seed=20001, sigma=1, freq=1e9, duration_ns=20), 0)
    centers = common_indices(case.signal.time_s.size)
    active = case.active[centers]
    peak = np.ones(centers.size)
    peak[active] = 5
    peak[30] = 4
    frequency = np.full(centers.size, 1e9)
    paired = dict(
        sample_index=centers,
        common_interior=np.ones(centers.size, dtype=np.bool_),
        cwt_peak=peak,
        cwt_frequency_hz=frequency,
    )
    analysis = Analysis({}, np.array([1e9]), peak[None, :], dict(method="cwt"))
    original = frequency.copy()
    result = presence_metrics(case, analysis, 3.0, paired)
    assert result["pre_onset_trigger"]
    assert result["any_active_hit"]
    assert result["onset_error_s"] == pytest.approx(case.signal.time_s[centers[30]] - 200e-9)
    assert result["onset_error_s"] < 0
    assert result["noise_fpr"] == pytest.approx(1 / np.sum(~active))
    np.testing.assert_array_equal(frequency, original)


def test_auroc_ties_and_absent_class() -> None:
    labels = np.array([True, False, True, False])
    mask = np.ones(4, dtype=np.bool_)
    assert auroc(np.ones(4), labels, mask) == 0.5
    assert auroc(np.array([2.0, 1.0, 2.0, 1.0]), labels, mask) == 1.0
    assert auroc(np.array([1.0, 2.0, 1.0, 2.0]), labels, mask) == 0.0
    assert auroc(np.ones(4), np.zeros(4, dtype=np.bool_), mask) is None


def test_smooth_interference_branch_is_wrong_and_no_truth_is_not_zero() -> None:
    t = np.arange(4, dtype=np.float64)
    prediction = np.full(4, 2e9)
    truth = np.array([np.nan, 1e9, 1e9, np.nan])
    other = np.full(4, 2e9)
    metrics = frequency_metrics(prediction, truth, other, t, np.ones(4, dtype=np.bool_))
    assert metrics["rmse_hz"] == 1e9
    assert metrics["wrong_branch_rate"] == 1.0
    assert metrics["jump_over_500mhz_rate"] == 0.0
    assert metrics["truth_points"] == 2
