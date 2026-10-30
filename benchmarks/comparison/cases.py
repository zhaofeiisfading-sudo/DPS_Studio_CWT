"""Frozen TASK004 recipes; no reuse of TASK002 evaluation seeds."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from pdv_cwt.models import BoolArray, FloatArray, SampledSignal
from pdv_cwt.synthetic import synthetic_pdv

EVALUATION_SEEDS = (20001, 20002, 20003)
CALIBRATION_SEEDS = tuple(range(10001, 10011))
RATES = (40e9, 80e9)


@dataclass
class Case:
    name: str
    group: str
    signal: SampledSignal
    truth_hz: FloatArray
    interference_hz: FloatArray
    active: BoolArray
    recipe: dict[str, Any]
    phase_rad: FloatArray


def case_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for fs in RATES:
        for freq in (0.2e9, 1e9, 5e9):
            specs.append(dict(group="S1", fs=fs, freq=freq, seed=20001, sigma=0.0))
            for snr in (20, 0, -10):
                for seed in EVALUATION_SEEDS:
                    specs.append(
                        dict(
                            group="S2",
                            fs=fs,
                            freq=freq,
                            seed=seed,
                            snr=snr,
                            sigma=float(np.sqrt(0.5 / 10 ** (snr / 10))),
                        )
                    )
        for seed in EVALUATION_SEEDS:
            for kind in ("slow", "fast"):
                specs.append(
                    dict(group="S3", fs=fs, seed=seed, kind=kind, sigma=float(np.sqrt(0.005)))
                )
            for freq in (1e9, 5e9):
                for duration_ns in (4, 20, 80):
                    specs.append(
                        dict(
                            group="S4",
                            fs=fs,
                            seed=seed,
                            freq=freq,
                            duration_ns=duration_ns,
                            sigma=float(np.sqrt(0.5)),
                        )
                    )
            specs.append(dict(group="S5", fs=fs, seed=seed, sigma=1.0))
            for freq, other in ((0.5e9, 2e9), (2e9, 0.5e9)):
                specs.append(dict(group="S6", fs=fs, seed=seed, freq=freq, other=other, sigma=0.02))
            for separation in (0.1e9, 0.3e9, 0.8e9):
                specs.append(
                    dict(group="S6_separation", fs=fs, seed=seed, separation=separation, sigma=0.02)
                )
            for kind in ("step", "cross"):
                specs.append(dict(group="S7", fs=fs, seed=seed, kind=kind, sigma=0.02))
    return specs


def make_case(spec: dict[str, Any], ordinal: int) -> Case:
    fs = float(spec["fs"])
    n = int(16384 * fs / 40e9)
    group = str(spec["group"])
    seed = int(spec["seed"])
    sigma = float(spec["sigma"])
    name = f"{group}_{ordinal:03d}_fs{int(fs / 1e9)}_seed{seed}"
    recipe = dict(
        spec,
        samples=n,
        time_origin_s=0,
        phase0_rad=0.37,
        generator="analytic integrated phase + explicit Gaussian noise",
    )
    if group in ("S1", "S2", "S4", "S5", "calibration"):
        pulse = (200e-9, 200e-9 + spec["duration_ns"] * 1e-9) if group == "S4" else None
        base = synthetic_pdv(
            samples=n,
            sampling_rate_hz=fs,
            frequency_start_hz=spec.get("freq", 1e9),
            amplitude_v=0.0 if group in ("S5", "calibration") else 1.0,
            noise_sigma_v=sigma,
            seed=seed,
            pulse_s=pulse,
        )
        recipe.update(base.recipe)
        return Case(
            name,
            group,
            base.signal,
            base.true_frequency_hz,
            np.full(n, np.nan),
            base.active,
            recipe,
            base.phase_rad,
        )
    t = np.arange(n, dtype=np.float64) / fs
    active = np.ones(n, dtype=np.bool_)
    interference = np.full(n, np.nan)
    if group == "S3":
        if spec["kind"] == "slow":
            k = 3.5e9 / t[-1]
            truth = 0.5e9 + k * t
            cycles = 0.5e9 * t + 0.5 * k * t**2
        else:
            u = np.clip(t - 190e-9, 0, 20e-9)
            k = 3.5e9 / 20e-9
            truth = 0.5e9 + k * u
            cycles = 0.5e9 * t + 0.5 * k * u**2 + 3.5e9 * np.maximum(t - 210e-9, 0)
        phase = 0.37 + 2 * np.pi * cycles
        voltage = np.cos(phase)
        recipe["chirp_rate_hz_s"] = float(k)
    elif group == "S7" and spec["kind"] == "step":
        truth = np.where(t < 200e-9, 0.7e9, 3e9)
        cycles = 0.7e9 * t + 2.3e9 * np.maximum(t - 200e-9, 0)
        phase = 0.37 + 2 * np.pi * cycles
        voltage = np.cos(phase)
    elif group == "S7":
        k = 2.3e9 / t[-1]
        truth = 0.7e9 + k * t
        interference = 3e9 - k * t
        phase = 0.37 + 2 * np.pi * (0.7e9 * t + 0.5 * k * t**2)
        phase_other = 0.83 + 2 * np.pi * (3e9 * t - 0.5 * k * t**2)
        voltage = 0.5 * np.cos(phase) + np.cos(phase_other)
        recipe.update(target_amplitude_v=0.5, interference_amplitude_v=1.0)
    else:
        if group == "S6":
            f1, f2, a1 = spec["freq"], spec["other"], 0.5
        else:
            f1, f2, a1 = 1e9 - spec["separation"] / 2, 1e9 + spec["separation"] / 2, 1.0
        truth = np.full(n, f1)
        interference = np.full(n, f2)
        phase = 0.37 + 2 * np.pi * f1 * t
        voltage = a1 * np.cos(phase) + np.cos(0.83 + 2 * np.pi * f2 * t)
        recipe.update(target_amplitude_v=a1, interference_amplitude_v=1.0)
    voltage += np.random.default_rng(seed).normal(0, sigma, n)
    return Case(name, group, SampledSignal(t, voltage), truth, interference, active, recipe, phase)
