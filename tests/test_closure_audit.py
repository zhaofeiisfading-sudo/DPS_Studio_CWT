"""Independent checks for evidence arithmetic, integrity and frozen contracts."""

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from benchmarks import closure_audit as audit
from benchmarks.validation.cases import registry


def test_metric_known_errors_mask_and_no_truth() -> None:
    values = audit.metrics([8, 13, 99, 7], [10, 10, 0, np.nan], [True, True, False, True])
    assert values["rmse_hz"] == pytest.approx(np.sqrt(6.5))
    assert values["mae_hz"] == 2.5
    assert values["bias_hz"] == 0.5
    assert values["truth_points"] == 2
    assert audit.metrics([3], [np.nan], [True])["rmse_hz"] is None


@pytest.mark.parametrize("prediction,truth,mask", [([np.inf], [1], [True]), ([1, 2], [1], [True])])
def test_invalid_predictions_rejected(prediction: Any, truth: Any, mask: Any) -> None:
    with pytest.raises(ValueError):
        audit.metrics(prediction, truth, mask)


@pytest.mark.parametrize("actual,expected", [(None, 0), (0, None), (np.nan, 1), (1, 2)])
def test_bad_metric_or_null_cannot_pass(actual: Any, expected: Any) -> None:
    with pytest.raises((ValueError, AssertionError)):
        audit.compare(actual, expected)


def test_interval_uses_waveforms_and_retains_adverse_outlier() -> None:
    assert audit.interval([-2.0] * 20) == [-2.0, -2.0]
    low, high = audit.interval([-2.0] * 19 + [100.0])
    assert low < 0 < high
    with pytest.raises(ValueError):
        audit.interval([1])


def test_split_registry_leakage_and_changed_protocol_rejected() -> None:
    splits = {
        s: registry(s) for s in ("cal_score", "cal_detect", "development", "evaluation", "grid")
    }
    audit.validate_registry(splits)
    splits["evaluation"][0]["seed"] = splits["development"][0]["seed"]
    with pytest.raises(ValueError, match="leakage"):
        audit.validate_registry(splits)
    splits["evaluation"] = registry("evaluation")
    splits["evaluation"][0]["frequency_hz"] += 1e6
    with pytest.raises(ValueError, match="registry mismatch"):
        audit.validate_registry(splits)


def test_parameter_contract_rejects_wrong_precision() -> None:
    audit.validate_parameters(dict(wavelet="cmor1.5-1.0", precision=18, voices=[24, 48, 96]))
    with pytest.raises(ValueError):
        audit.validate_parameters(dict(wavelet="cmor1.5-1.0", precision=14, voices=[24, 48, 96]))


def test_conclusion_requires_benefit_and_all_engineering_gates() -> None:
    assert audit.classify(False, False, False) == "NOT_SUPPORTED"
    assert audit.classify(False, False, True) == "NICHE_ONLY"
    assert audit.classify(True, False, True) == "NICHE_ONLY"
    assert audit.classify(True, True, True) == "GO_FOR_OPTIONAL_ENGINEERING"


def test_manifest_tampering_missing_and_unsafe_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    path = tmp_path / "result.json"
    path.write_text("evidence")
    entry = audit.file_entry(path)
    audit.verify_entries([entry])
    with pytest.raises(ValueError, match="duplicate"):
        audit.verify_entries([entry, entry])
    with pytest.raises(ValueError, match="missing"):
        audit.verify_entries([dict(entry, path="absent.json")])
    path.write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        audit.verify_entries([entry])
    for relative in ("../outside", "raw_data/source.csv", ".git/config", ".local_cache/file"):
        with pytest.raises(ValueError, match="unsafe"):
            audit.verify_entries([dict(entry, path=relative)])


def test_writes_are_exclusive_and_reject_historical_or_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "OUT", tmp_path / "artifacts/TASK-CWT-006")
    audit.write("new.json", {"ok": True})
    with pytest.raises(FileExistsError):
        audit.write("new.json", {"ok": False})
    for relative in ("artifacts/TASK-CWT-005/new.json", "raw_data/new.csv", "docs/new.md"):
        with pytest.raises(ValueError, match="boundary"):
            audit.output(tmp_path / relative)
