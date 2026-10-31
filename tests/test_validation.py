"""Independent contracts for TASK005; fixtures are synthetic and never touch raw."""

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy.signal import windows

from benchmarks.validation.cases import make_case, noise, registry
from benchmarks.validation.io import output
from benchmarks.validation.run import evaluate_job, freeze_candidate, profile_key
from benchmarks.validation.scoring import (
    cwt,
    cwt_banks,
    detection,
    physical_config,
    score_response,
    stft_bank,
    support,
)
from pdv_cwt.diagnostics import discrete_filter
from pdv_cwt.frequency import CWTConfig, Normalization, make_frequency_grid, strongest_candidate
from pdv_cwt.safety import ROOT


def spec(**values: Any) -> dict[str, Any]:
    return (
        dict(
            registry("development")[0],
            seed=920001,
            frequency_hz=1.137e9,
            id="unit_fixture",
            split="unit_fixture",
        )
        | values
    )


def test_registry_split_isolation_twenty_replicates_and_off_grid() -> None:
    splits = {
        s: registry(s) for s in ("cal_score", "cal_detect", "development", "evaluation", "grid")
    }
    seeds = [r["seed"] for cases in splits.values() for r in cases]
    assert len(seeds) == len(set(seeds))
    assert not set(seeds) & {101, 202, 303, 20001, 20002, 20003}
    assert [len(splits[s]) for s in splits] == [120, 240, 16, 1840, 72]
    for fs in (40e9, 80e9):
        for band in ("low", "mid", "high"):
            for model in ("white", "colored"):
                for snr in (20, 0, -10):
                    assert (
                        sum(
                            r["fs"] == fs
                            and r["band"] == band
                            and r["model"] == model
                            and r["snr"] == snr
                            and r["group"] == "core"
                            for r in splits["evaluation"]
                        )
                        == 20
                    )
    grid = make_frequency_grid(CWTConfig(), 1 / 40e9)
    for row in splits["grid"]:
        assert np.min(np.abs(grid.frequency_hz - row["frequency_hz"])) > 1


@pytest.mark.parametrize("model", ["white", "colored", "bandwidth"])
def test_noise_psd_and_input_snr(model: str) -> None:
    values = noise(32768, 40e9, model, 932)
    assert np.mean(values**2) == pytest.approx(1, rel=0.08)
    power = np.abs(np.fft.rfft(values)) ** 2
    hz = np.fft.rfftfreq(values.size, 1 / 40e9)
    if model == "colored":
        assert np.mean(power[hz < 1e9]) > 5 * np.mean(power[hz > 10e9])
    if model == "bandwidth":
        assert np.max(power[hz > 8e9]) < 1e-20
    case = make_case(spec(model=model, snr=-10))
    assert abs(case.recipe["realized_snr_db"] + 10) < 0.6
    assert case.sigma**2 == pytest.approx(case.recipe["clean_target_power_v2"] * 10)
    with pytest.raises(ValueError, match="PSD"):
        noise(1024, 40e9, "unknown", 2)


@pytest.mark.parametrize("frequency", [0.237e9, 1.137e9, 4.713e9])
def test_analytic_discrete_response_and_scale_agreement(frequency: float) -> None:
    case = make_case(spec(frequency_hz=frequency, snr=1000, phase0=0.37))
    result, _ = cwt(case.signal)
    banks = cwt_banks(result, np.ones(result.grid.scales.size))
    modes: tuple[tuple[str, Normalization], ...] = (("A0", "raw"), ("A1", "scale_amplitude"))
    for mode, normalization in modes:
        old = strongest_candidate(result, normalization=normalization)
        np.testing.assert_array_equal(old.frequency_hz[banks[mode].centers], banks[mode].predicted)
    # Direct discrete-kernel frequency gain is independent of PyWavelets convolution.
    i = int(np.argmin(np.abs(result.grid.frequency_hz - frequency)))
    kernel = discrete_filter(float(result.grid.scales[i]))
    z = np.exp(-2j * np.pi * frequency / case.signal.sampling_rate_hz * np.arange(kernel.size))
    analytic_gain = abs(np.sum(kernel * z)) / 2
    interior = ~banks["A0"].edge
    measured = np.mean(banks["A0"].score[i, interior])
    assert measured == pytest.approx(analytic_gain, rel=2e-3)
    assert np.median(banks["A0"].predicted[interior]) < frequency


def test_normalization_invalid_calibration_and_same_coefficients() -> None:
    raw = np.array([[2.0, 4.0], [3.0, 5.0]])
    saved = raw.copy()
    scales = np.array([4.0, 9.0])
    np.testing.assert_array_equal(score_response(raw, scales, "A0", np.ones(2)), raw)
    np.testing.assert_allclose(score_response(raw, scales, "A1", np.ones(2)), raw / [[2], [3]])
    np.testing.assert_allclose(
        score_response(raw, scales, "A2", np.array([2.0, 5.0])), raw / [[2], [5]]
    )
    np.testing.assert_array_equal(raw, saved)
    for rms in (np.zeros(2), np.array([np.nan, 1.0]), np.ones(3)):
        with pytest.raises(ValueError):
            score_response(raw, scales, "A2", rms)
    with pytest.raises(ValueError):
        score_response(raw, scales, "unknown", np.ones(2))


def test_spectral_support_rank_missing_and_wrong_interference() -> None:
    hz = np.arange(7, dtype=np.float64) * 1e8
    score = np.array([[0.0], [4.0], [1.0], [3.0], [1.0], [8.0], [0.0]])
    result = support(score, hz, np.array([3e8]))
    assert result["presence"][0] == 1 and result["rank"][0] == 3
    assert result["top3"][0] == 1 and result["strongest_accurate"][0] == 0
    missing = support(score, hz, np.array([2e8]))
    assert missing["presence"][0] == 0 and np.isnan(missing["rank"][0])
    edge = support(score, hz, np.array([0.0]))
    assert edge["presence"][0] == 0


def test_onset_early_trigger_missed_active_and_record_fpr() -> None:
    times = np.arange(8, dtype=np.float64)
    active = (times >= 4) & (times < 6)
    peak = np.array([0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    record = detection(peak, times, active, np.ones(8, dtype=np.bool_), 3, 4)
    assert record["early_trigger"] and record["onset_error_s"] == -3
    assert record["missed_detection"] and not record["no_record_trigger"]
    record = detection(
        peak, times, np.zeros(8, dtype=np.bool_), np.ones(8, dtype=np.bool_), 3, None
    )
    assert record["frame_fpr"] == 1 / 8 and record["record_fpr"] is True


def test_physical_windows_and_independent_direct_fft() -> None:
    for high in (False, True):
        cfg40, cfg80 = physical_config(40e9, high), physical_config(80e9, high)
        assert cfg40.window / 40e9 == cfg80.window / 80e9
        assert cfg40.hop / 40e9 == cfg80.hop / 80e9
        assert 40e9 / cfg40.nfft == 80e9 / cfg80.nfft
        case = make_case(spec(fs=80e9, group="chirp", duration_ns=20))
        bank = stft_bank(case.signal, high, True)
        pos = 50
        center = bank.centers[pos]
        window = windows.hann(cfg80.window, sym=False)
        segment = case.signal.voltage_v[center - cfg80.window // 2 : center + cfg80.window // 2]
        direct = 2 * np.abs(np.fft.rfft(window * segment, n=cfg80.nfft)) / window.sum()
        hz = np.fft.rfftfreq(cfg80.nfft, case.signal.sampling_period_s)
        band = (hz >= 0.1e9) & (hz <= 6e9)
        np.testing.assert_allclose(bank.score[:, pos], direct[band], rtol=1e-11, atol=1e-14)
        measured = np.diff(case.phase) / (2 * np.pi * case.signal.sampling_period_s)
        np.testing.assert_allclose(
            measured, (case.truth[:-1] + case.truth[1:]) / 2, rtol=1e-9, atol=0.1
        )


def test_dense_scales_nested_and_high_frequency_catastrophe_low_frequency_advantage() -> None:
    grids = [make_frequency_grid(CWTConfig(voices_per_octave=v), 1 / 40e9) for v in (24, 48, 96)]
    assert [g.scales.size for g in grids] == [143, 285, 569]
    for grid in grids[:2]:
        assert (
            np.max(np.min(np.abs(grid.frequency_hz[:, None] - grids[-1].frequency_hz), axis=1))
            < 1e-3
        )
    high = make_case(spec(frequency_hz=5e9, snr=-10, seed=710050))
    result, _ = cwt(high.signal)
    bank = cwt_banks(result, np.ones(143))["A0"]
    assert np.sqrt(np.mean((bank.predicted[~bank.edge] - 5e9) ** 2)) > 1e9
    low = make_case(spec(fs=80e9, frequency_hz=0.2e9, snr=-10, seed=710051))
    result, _ = cwt(low.signal)
    bank = cwt_banks(result, np.ones(143))["A0"]
    control = stft_bank(low.signal)
    interior = ~bank.edge & ~control.edge
    assert np.mean((bank.predicted[interior] - 0.2e9) ** 2) < np.mean(
        (control.predicted[interior] - 0.2e9) ** 2
    )


def test_saved_heldout_metrics_recompute_and_frozen_selection(tmp_path: Path) -> None:
    row = spec(group="branches", frequency_hz=2e9, snr=20)
    result = evaluate_job(
        dict(spec=row, run=str(tmp_path), profiles={profile_key(40e9, "white"): [1.0] * 143})
    )
    assert result["status"] == "COMPLETED"
    path = tmp_path / row["split"] / f"{row['id']}_v24" / "common.npz"
    with np.load(path) as saved:
        mask = saved["interior"] & saved["active"]
        for record in result["rows"]:
            error = saved[f"{record['method']}_prediction"][mask] - saved["truth_hz"][mask]
            assert record["rmse_hz"] == pytest.approx(float(np.sqrt(np.mean(error**2))))
            assert record["wrong_branch_rate"] == 1
    records = [
        dict(case="x", scope="interior", group="core", method=m, rmse_hz=e)
        for m, e in (("balanced", 10e6), ("A0", 9e6), ("A1", 8e6), ("A2", 7e6))
    ]
    frozen = freeze_candidate(tmp_path, records)
    assert frozen["chosen"] == "A2" and not frozen["held_out_started"]
    with pytest.raises(ValueError, match="outside"):
        output(ROOT / "raw_data/never_written.txt")
