"""Synthetic controls only: mathematical conventions and non-gating contracts."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy.signal import windows

from benchmarks.comparison.cases import CALIBRATION_SEEDS, EVALUATION_SEEDS, case_specs, make_case
from benchmarks.comparison.core import (
    STFTConfig,
    analyze,
    common_indices,
    pair_native,
    stft_transform,
)
from benchmarks.comparison.metrics import frequency_metrics
from benchmarks.comparison.storage import output_path, run_isolated, write_json
from pdv_cwt.mapping import load_config
from pdv_cwt.models import SampledSignal
from pdv_cwt.safety import ROOT
from pdv_cwt.synthetic import synthetic_pdv


@pytest.mark.parametrize("length", [512, 768])
@pytest.mark.parametrize("rate", [40e9, 80e9])
def test_periodic_hann_fft_scaling_centers_and_padding(length: int, rate: float) -> None:
    rng = np.random.default_rng(881)
    t = 2e-4 + np.arange(4097) / rate
    signal = SampledSignal(t, rng.normal(size=t.size))
    config = STFTConfig(length, length - 128)
    coeff, hz, centers, edge, meta = stft_transform(signal, config)
    window = windows.hann(length, sym=False)
    np.testing.assert_allclose(
        window, 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(length) / length), atol=1e-15
    )
    assert window.sum() == pytest.approx(length / 2)
    expected_hz = np.fft.rfftfreq(4096, d=signal.sampling_period_s)
    band = (expected_hz >= 0.1e9) & (expected_hz <= 6e9)
    np.testing.assert_array_equal(hz, expected_hz[band])
    assert centers[0] == 0 and centers[-1] == 4096
    for pos in (0, 1, 5, centers.size - 1):
        index = centers[pos] + np.arange(length) - length // 2
        values = np.zeros(length)
        valid = (index >= 0) & (index < t.size)
        values[valid] = signal.voltage_v[index[valid]]
        direct = 2 * np.abs(np.fft.rfft(values * window, n=4096)) / window.sum()
        np.testing.assert_allclose(np.abs(coeff[:, pos]), direct[band], rtol=1e-12, atol=1e-14)
        assert edge[pos] == (not valid.all())
    assert meta["frame_interval_s"] == pytest.approx(128 / rate)
    assert meta["hann_enbw_hz"] == pytest.approx(1.5 * rate / length)
    np.testing.assert_array_equal(signal.time_s[centers], t[centers])


@pytest.mark.parametrize("method", ["balanced", "high_time"])
def test_tone_amplitude_and_no_sub_bin_refinement(method: str) -> None:
    # Integer cycles in both actual Hann windows; off-window-bin negative-frequency
    # leakage is instead checked against direct FFT in the random-input test.
    frequency = 128 * 40e9 / 4096
    case = synthetic_pdv(
        samples=8192, sampling_rate_hz=40e9, frequency_start_hz=frequency, amplitude_v=2, seed=35
    )
    analysis = analyze(case.signal, method)
    valid = ~analysis.native["bank_edge"]
    np.testing.assert_allclose(analysis.native["frequency_hz"][valid], frequency)
    np.testing.assert_allclose(analysis.native["peak"][valid], 2, rtol=1e-5)
    assert np.isin(analysis.native["frequency_hz"], analysis.frequency_hz).all()


@pytest.mark.parametrize("method", ["balanced", "high_time"])
def test_chirp_calibration_at_actual_frame_centers(method: str) -> None:
    case = synthetic_pdv(
        samples=16384,
        sampling_rate_hz=40e9,
        frequency_start_hz=0.5e9,
        frequency_end_hz=4e9,
        seed=33,
    )
    result = analyze(case.signal, method)
    valid = ~result.native["bank_edge"]
    indices = result.native["sample_index"][valid]
    error = result.native["frequency_hz"][valid] - case.true_frequency_hz[indices]
    assert np.max(np.abs(error)) < 6e6


def test_common_grid_native_edge_masks_noise_and_zero_keep_candidates() -> None:
    case = synthetic_pdv(
        samples=8192,
        sampling_rate_hz=40e9,
        frequency_start_hz=1e9,
        amplitude_v=0,
        noise_sigma_v=1,
        time_origin_s=2e-4,
        seed=88,
    )
    analyses = {m: analyze(case.signal, m) for m in ("cwt", "balanced", "high_time")}
    common = pair_native(analyses, 8192)
    indices = common_indices(8192)
    for method, result in analyses.items():
        assert np.isfinite(result.native["frequency_hz"]).all()
        np.testing.assert_array_equal(common[f"{method}_time_s"], case.signal.time_s[indices])
        assert result.native["bank_edge"][0]
        assert not result.native["bank_edge"][len(result.native["bank_edge"]) // 2]
    assert common["common_interior"].any()
    assert common["common_interior"].sum() < (~analyses["balanced"].native["bank_edge"]).sum()
    np.testing.assert_array_equal(
        common["cwt_frequency_hz"], analyses["cwt"].native["frequency_hz"][indices]
    )
    zeros = SampledSignal(case.signal.time_s, np.zeros(8192))
    for method in analyses:
        result = analyze(zeros, method)
        assert np.all(result.native["frequency_hz"] == result.frequency_hz[0])
        assert np.all(result.native["peak"] == 0)


def test_budget_and_config_rejected_before_stft(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("engine must not be called")

    monkeypatch.setattr("benchmarks.comparison.core.ShortTimeFFT", forbidden)
    signal = SampledSignal(np.arange(1024) / 40e9, np.ones(1024))
    with pytest.raises(MemoryError, match="budget"):
        stft_transform(signal, replace(STFTConfig(), max_memory_bytes=1))
    with pytest.raises(MemoryError, match="70%"):
        stft_transform(signal, STFTConfig(), available_bytes=1)
    with pytest.raises(ValueError, match="hop"):
        STFTConfig(hop=129)
    with pytest.raises(ValueError, match="Nyquist"):
        stft_transform(SampledSignal(np.arange(1024) / 10e9, np.ones(1024)), STFTConfig())


def test_registry_all_cases_seeds_physical_phase_and_mapping() -> None:
    specs = case_specs()
    assert len(specs) == 156
    assert not set(CALIBRATION_SEEDS) & set(EVALUATION_SEEDS)
    assert set(s["group"] for s in specs) == {
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S6",
        "S6_separation",
        "S7",
    }
    spec = next(s for s in specs if s["group"] == "S3" and s["kind"] == "fast")
    case = make_case(spec, 0)
    frequency = np.diff(case.phase_rad) / (2 * np.pi * case.signal.sampling_period_s)
    np.testing.assert_allclose(
        frequency, (case.truth_hz[:-1] + case.truth_hz[1:]) / 2, rtol=1e-10, atol=0.01
    )
    mapping = load_config(ROOT / "configs/real_batch.toml")
    assert len(mapping.mappings) == 10
    assert sum(len(m.channels) for m in mapping.mappings.values()) == 14


def test_noise_has_no_frequency_error_and_denominators_explicit() -> None:
    n = 5
    result = frequency_metrics(
        np.ones(n),
        np.full(n, np.nan),
        np.full(n, np.nan),
        np.arange(n, dtype=np.float64),
        np.ones(n, dtype=np.bool_),
    )
    assert result["rmse_hz"] is None and result["truth_points"] == 0
    assert result["evaluation_points"] == 5


def test_failed_worker_isolated_and_write_boundary(tmp_path: Path) -> None:
    request = tmp_path / "bad_request.json"
    write_json(request, dict(kind="invalid", method="invalid", samples=1024, fs_hz=40e9))
    result = run_isolated(request, timeout_s=30)
    assert result["status"] == "FAILED"
    assert request.with_suffix(".stderr.txt").exists()
    with pytest.raises(ValueError, match="outside"):
        output_path(ROOT / "raw_data/never_written.txt")


def test_plot_coordinates_and_export_consistency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matplotlib import pyplot as plt
    from matplotlib.figure import Figure

    from benchmarks.comparison.plots import comparison_plots
    from benchmarks.comparison.storage import save_analysis

    case = synthetic_pdv(
        samples=8192, sampling_rate_hz=40e9, frequency_start_hz=1e9, time_origin_s=1e-4, seed=90
    )
    analyses = {m: analyze(case.signal, m) for m in ("cwt", "balanced", "high_time")}
    paired = pair_native(analyses, 8192)
    paths = []

    def inspect(fig: Figure, path: Path) -> None:
        paths.append(path.name)
        first = fig.axes[0]
        if path.name != "background_diagnostics.png":
            assert first.get_ylim() == pytest.approx((0.1, 6))
        if path.name != "exploratory_roi.png":
            assert first.get_xlim() == pytest.approx(
                (case.signal.time_s[0] * 1e6, case.signal.time_s[-1] * 1e6)
            )
        plt.close(fig)

    monkeypatch.setattr("benchmarks.comparison.plots.save", inspect)
    for method, analysis in analyses.items():
        save_analysis(tmp_path / method, analysis, native_csv=False)
    meta = comparison_plots(tmp_path, "synthetic fixture", analyses, paired)
    assert len(paths) == 6
    assert meta["balanced"]["db_limits"] == [-20, 60]
    assert meta["cwt"]["background_normalization"] == "NOT AVAILABLE"
    assert (tmp_path / "plot_metadata.json").exists()
