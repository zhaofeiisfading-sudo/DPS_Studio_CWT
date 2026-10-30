"""Independent mathematical checks and explicit failure-mode contracts."""

from dataclasses import replace

import numpy as np
import pytest
import pywt
from numpy.typing import ArrayLike

from pdv_cwt import (
    CWTConfig,
    SampledSignal,
    apparent_velocity,
    compute_cwt,
    diagnose,
    make_frequency_grid,
    strongest_candidate,
    synthetic_pdv,
)
from pdv_cwt.diagnostics import filter_energies


def test_si_physics_explicit_assumptions() -> None:
    actual = apparent_velocity([1e9, 0], wavelength_m=1550e-9, zero_optical_offset=True)
    np.testing.assert_allclose(actual, [775.0, 0], rtol=1e-14)
    with pytest.raises(ValueError, match="offset"):
        apparent_velocity([1e9], wavelength_m=1550e-9, zero_optical_offset=False)


@pytest.mark.parametrize("wavelength", [0, -1, np.nan, np.inf])
def test_invalid_wavelength(wavelength: float) -> None:
    with pytest.raises(ValueError):
        apparent_velocity([1e9], wavelength_m=wavelength, zero_optical_offset=True)


@pytest.mark.parametrize("frequency", [[-1.0], [np.nan], [[1.0]], [1j]])
def test_invalid_physics_frequency(frequency: ArrayLike) -> None:
    with pytest.raises(ValueError):
        apparent_velocity(frequency, wavelength_m=1e-6, zero_optical_offset=True)


@pytest.mark.parametrize(
    ("time", "voltage"),
    [
        ([0, 1, 2], [0, 0, 0]),
        ([0, 1, 2, 3], [0, 1]),
        ([[0, 1, 2, 3]], [0, 0, 0, 0]),
        ([0, 1, 2, 3], [[0, 0, 0, 0]]),
        ([0, 1, 1, 3], [0, 0, 0, 0]),
        ([3, 2, 1, 0], [0, 0, 0, 0]),
        ([0, 1, 2.01, 3], [0, 0, 0, 0]),
        ([0, 1, np.inf, 3], [0, 0, 0, 0]),
        ([0, 1, 2, 3], [0, np.nan, 0, 0]),
        ([0, 1, 2, 3], [0, 1j, 0, 0]),
        ([0, 1, 2, 3], [False, True, False, True]),
        ([1e12, 1e12 + 0.01, 1e12 + 0.02, 1e12 + 0.03], [0, 0, 0, 0]),
    ],
)
def test_bad_samples_rejected(time: ArrayLike, voltage: ArrayLike) -> None:
    with pytest.raises(ValueError):
        SampledSignal(time, voltage)


def test_input_owned_and_unmodified() -> None:
    time = 1e-7 + np.arange(4096) / 40e9
    voltage = np.cos(2 * np.pi * 1e9 * time)
    saved_time, saved_voltage = time.copy(), voltage.copy()
    signal = SampledSignal(time, voltage)
    result = compute_cwt(signal, CWTConfig(frequency_min_hz=0.5e9, frequency_max_hz=2e9))
    assert not np.shares_memory(signal.time_s, time)
    assert not np.shares_memory(signal.voltage_v, voltage)
    assert not signal.time_s.flags.writeable
    assert not result.coefficients.flags.writeable
    np.testing.assert_array_equal(time, saved_time)
    np.testing.assert_array_equal(voltage, saved_voltage)
    assert signal.sampling_period_s == pytest.approx(1 / 40e9, rel=1e-12)


def test_scale_mapping_endpoint_grid_and_axis_alignment() -> None:
    case = synthetic_pdv(samples=8192, sampling_rate_hz=40e9, frequency_start_hz=1e9, seed=1)
    result = compute_cwt(case.signal)
    grid = result.grid
    assert grid.frequency_hz[0] == pytest.approx(0.1e9)
    assert grid.frequency_hz[-1] == pytest.approx(6e9)
    assert grid.scales.size == 143
    assert np.max(grid.scales) == pytest.approx(400)
    assert np.max(grid.alias_tail_fraction) < 1e-6
    assert result.coefficients.shape == (143, 8192)
    assert np.all(np.diff(grid.frequency_hz) > 0)
    assert np.all(np.diff(grid.scales) < 0)
    assert np.max(grid.frequency_hz[1:] / grid.frequency_hz[:-1]) <= 2 ** (1 / 24) + 1e-12
    candidate = strongest_candidate(result)
    np.testing.assert_array_equal(candidate.time_s, case.signal.time_s)
    np.testing.assert_allclose(
        pywt.scale2frequency("cmor1.5-1.0", grid.scales, precision=14) / (1 / 40e9),
        grid.frequency_hz,
        rtol=1e-12,
    )


@pytest.mark.parametrize(
    "config",
    [
        CWTConfig(frequency_max_hz=20e9),
        CWTConfig(frequency_max_hz=19e9),  # Below Nyquist, yet sampled Morlet aliases.
        CWTConfig(precision=12),  # Too coarse at maximum scale 400 for this band.
    ],
)
def test_nyquist_alias_or_coarse_integration_rejected(config: CWTConfig) -> None:
    with pytest.raises(ValueError):
        make_frequency_grid(config, 1 / 40e9)


def test_explicit_alias_risk_opt_in_retains_flags() -> None:
    config = CWTConfig(frequency_min_hz=10e9, frequency_max_hz=19e9, allow_alias_risk=True)
    case = synthetic_pdv(samples=512, sampling_rate_hz=40e9, frequency_start_hz=18e9, seed=1)
    result = compute_cwt(case.signal, config)
    quality = diagnose(result, strongest_candidate(result), noise_sigma_v=0)
    assert np.any(result.grid.alias_tail_fraction > config.alias_tail_tolerance)
    assert np.any(quality.alias_risk)
    assert not np.any(quality.passed & quality.alias_risk)


def test_memory_refused_before_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    case = synthetic_pdv(samples=4096, sampling_rate_hz=40e9, frequency_start_hz=1e9, seed=1)

    def forbidden_engine(*args: object, **kwargs: object) -> None:
        pytest.fail("engine must not allocate its coefficient matrix")

    monkeypatch.setattr(pywt, "cwt", forbidden_engine)
    with pytest.raises(MemoryError, match="budget"):
        compute_cwt(case.signal, CWTConfig(max_memory_bytes=1))
    with pytest.raises(MemoryError, match="RAM"):
        compute_cwt(case.signal, available_memory_bytes=1)


def test_fft_against_independent_direct_convolution() -> None:
    case = synthetic_pdv(
        samples=2048,
        sampling_rate_hz=40e9,
        frequency_start_hz=1e9,
        frequency_end_hz=2e9,
        noise_sigma_v=0.1,
        seed=11,
    )
    config = CWTConfig(frequency_min_hz=0.5e9, frequency_max_hz=3e9, voices_per_octave=6)
    result = compute_cwt(case.signal, config)
    expected, frequency = pywt.cwt(
        case.signal.voltage_v,
        result.grid.scales,
        config.wavelet,
        sampling_period=case.signal.sampling_period_s,
        method="conv",
        precision=config.precision,
    )
    np.testing.assert_allclose(result.coefficients, expected, rtol=1e-10, atol=1e-10)
    np.testing.assert_array_equal(result.grid.frequency_hz, frequency)


@pytest.mark.parametrize("frequency", [0.2e9, 0.5e9, 1e9, 2e9, 5e9])
def test_preregistered_tone_accuracy(frequency: float) -> None:
    case = synthetic_pdv(samples=16384, sampling_rate_hz=40e9, frequency_start_hz=frequency, seed=1)
    result = compute_cwt(case.signal)
    for normalization, bound in (("raw", 0.04), ("scale_amplitude", 0.03)):
        candidate = strongest_candidate(result, normalization=normalization)  # type: ignore[arg-type]
        quality = diagnose(result, candidate, noise_sigma_v=0)
        interior = ~quality.bank_edge_affected
        error = candidate.frequency_hz[interior] / frequency - 1
        assert np.sqrt(np.mean(error**2)) <= bound
        assert np.all(quality.passed[interior])


def test_analytic_chirp_and_fixed_accuracy_bound() -> None:
    case = synthetic_pdv(
        samples=16384,
        sampling_rate_hz=40e9,
        frequency_start_hz=0.5e9,
        frequency_end_hz=4e9,
        seed=101,
    )
    # Analytic derivative at interval midpoints, not a concatenated tone sequence.
    measured = np.diff(case.phase_rad) / (2 * np.pi * case.signal.sampling_period_s)
    midpoint = (case.true_frequency_hz[:-1] + case.true_frequency_hz[1:]) / 2
    np.testing.assert_allclose(measured, midpoint, rtol=1e-11)
    result = compute_cwt(case.signal)
    candidate = strongest_candidate(result, normalization="scale_amplitude")
    interior = ~diagnose(result, candidate, noise_sigma_v=0).bank_edge_affected
    error = candidate.frequency_hz[interior] - case.true_frequency_hz[interior]
    assert np.sqrt(np.mean(error**2)) / np.mean(case.true_frequency_hz[interior]) <= 0.05


def test_impulse_energy_and_time_localization() -> None:
    samples = 8192
    center = samples // 2
    values = np.zeros(samples)
    values[center] = 1
    signal = SampledSignal(np.arange(samples) / 40e9, values)
    result = compute_cwt(signal, CWTConfig(frequency_min_hz=0.5e9, frequency_max_hz=6e9))
    energy = np.sum(np.abs(result.coefficients) ** 2, axis=1)
    np.testing.assert_allclose(energy, filter_energies(result), rtol=1e-10, atol=1e-12)
    # Integral-wavelet sampling can move the maximum of a broad envelope several
    # samples. Energy centroid tests the axis/cropping independently of that ripple.
    centroid = (np.abs(result.coefficients) ** 2 @ np.arange(samples)) / energy
    assert np.all(np.abs(centroid - center) <= 1)


def test_support_mask_noise_unknown_zero_signal_and_ties() -> None:
    signal = SampledSignal(np.arange(8192) / 40e9, np.zeros(8192))
    result = compute_cwt(signal)
    candidate = strongest_candidate(result)
    saved = candidate.frequency_hz.copy()
    quality = diagnose(result, candidate)
    assert "UNKNOWN" in quality.noise_model
    assert np.all(np.isfinite(candidate.frequency_hz))
    assert np.all(candidate.scale_index == 0)
    assert not np.any(quality.passed)
    radius = int(np.max(result.grid.support_radius_samples))
    assert quality.bank_edge_affected.sum() == 2 * radius
    assert quality.bank_edge_affected[radius - 1]
    assert not quality.bank_edge_affected[radius]
    assert not np.any(diagnose(result, candidate, noise_sigma_v=0).passed)
    np.testing.assert_array_equal(candidate.frequency_hz, saved)


def test_known_noise_union_bound_independent_seed() -> None:
    case = synthetic_pdv(
        samples=8192,
        sampling_rate_hz=40e9,
        frequency_start_hz=1e9,
        amplitude_v=0,
        noise_sigma_v=1,
        seed=999,
    )
    result = compute_cwt(case.signal)
    candidate = strongest_candidate(result, normalization="scale_amplitude")
    quality = diagnose(result, candidate, noise_sigma_v=1)
    assert np.all(np.isfinite(candidate.frequency_hz))
    assert not np.any(quality.above_noise)  # A fixed seed check, not a universal no-FP claim.
    assert not np.any(quality.passed)


def test_invalid_configuration_and_quality_parameters() -> None:
    with pytest.raises(ValueError):
        CWTConfig(wavelet="morl")
    with pytest.raises(ValueError):
        CWTConfig(frequency_min_hz=-1)
    with pytest.raises(ValueError):
        CWTConfig(voices_per_octave=True)
    with pytest.raises(ValueError):
        CWTConfig(frequency_max_hz=np.nan)
    with pytest.raises(ValueError):
        make_frequency_grid(CWTConfig(), 0)
    case = synthetic_pdv(samples=1024, sampling_rate_hz=40e9, frequency_start_hz=1e9, seed=2)
    result = compute_cwt(case.signal)
    candidate = strongest_candidate(result)
    with pytest.raises(ValueError):
        diagnose(result, candidate, noise_sigma_v=-1)
    with pytest.raises(ValueError):
        diagnose(result, candidate, record_alpha=1)
    with pytest.raises(ValueError):
        diagnose(result, replace(candidate, time_s=candidate.time_s.copy()))


def test_reproducible_synthetic_noise_and_gate_truth() -> None:
    options = dict(
        samples=1024,
        sampling_rate_hz=40e9,
        frequency_start_hz=1e9,
        noise_sigma_v=0.1,
        seed=3,
        pulse_s=(2e-9, 12e-9),
    )
    first = synthetic_pdv(**options)  # type: ignore[arg-type]
    second = synthetic_pdv(**options)  # type: ignore[arg-type]
    np.testing.assert_array_equal(first.signal.voltage_v, second.signal.voltage_v)
    assert np.all(np.isnan(first.true_frequency_hz[~first.active]))
    assert np.all(first.true_frequency_hz[first.active] == 1e9)


@pytest.mark.parametrize(
    "options",
    [
        {"samples": 3},
        {"sampling_rate_hz": 0.0},
        {"frequency_start_hz": 21e9},
        {"noise_sigma_v": -1.0},
        {"phase_rad": np.inf},
        {"pulse_s": (3e-9, 2e-9)},
    ],
)
def test_synthetic_invalid_inputs(options: dict[str, object]) -> None:
    arguments: dict[str, object] = dict(
        samples=1024, sampling_rate_hz=40e9, frequency_start_hz=1e9, seed=1
    )
    arguments.update(options)
    with pytest.raises((ValueError, TypeError)):
        synthetic_pdv(**arguments)  # type: ignore[arg-type]
