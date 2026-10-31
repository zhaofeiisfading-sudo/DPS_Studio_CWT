"""Frozen TASK005 recipes and analytic phase. No data-dependent recipe selection."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from pdv_cwt.models import BoolArray, FloatArray, SampledSignal

RATES = (40e9, 80e9)
BANDS = {"low": (0.15e9, 0.45e9), "mid": (0.55e9, 1.85e9), "high": (2.3e9, 5.3e9)}
DURATION = 409.6e-9


@dataclass
class Case:
    signal: SampledSignal
    truth: FloatArray
    interference: FloatArray
    active: BoolArray
    phase: FloatArray
    sigma: float
    recipe: dict[str, Any]


def noise(samples: int, fs: float, model: str, seed: int) -> FloatArray:
    rng = np.random.default_rng(seed)
    white = rng.normal(size=samples)
    if model == "white":
        return white
    hz = np.fft.fftfreq(samples, 1 / fs)
    if model == "colored":
        power = 1 / (1 + (hz / 1.5e9) ** 2)
    elif model == "bandwidth":
        power = np.asarray(np.abs(hz) <= 8e9, dtype=np.float64)
    else:
        raise ValueError("unknown noise PSD")
    # Full DFT sum implements E(mean(noise**2))=1, not fitted realized normalization.
    return np.asarray(np.fft.ifft(np.fft.fft(white) * np.sqrt(power / power.mean())).real)


def registry(split: str, repeats: int = 20) -> list[dict[str, Any]]:
    if split not in ("evaluation", "development", "grid", "cal_score", "cal_detect"):
        raise ValueError("unknown split")
    rng = np.random.default_rng(
        910000
        + {
            "evaluation": 0,
            "development": 1,
            "grid": 2,
            "cal_score": 3,
            "cal_detect": 4,
        }[split]
    )
    start = {
        "cal_score": 310000,
        "cal_detect": 320000,
        "development": 410000,
        "evaluation": 510000,
        "grid": 610000,
    }[split]
    rows: list[dict[str, Any]] = []

    def add(**values: Any) -> None:
        values = (
            dict(
                fs=40e9,
                group="core",
                band="mid",
                model="white",
                snr=20,
                duration_ns=0,
                **{"rep": 0},
            )
            | values
        )
        lo, hi = BANDS.get(str(values["band"]), BANDS["mid"])
        values.setdefault("frequency_hz", float(rng.uniform(lo, hi)))
        values.update(seed=start + len(rows), split=split, phase0=float(rng.uniform(0, 2 * np.pi)))
        values["id"] = f"{split}_{len(rows):04d}"
        rows.append(values)

    if split.startswith("cal_"):
        for fs in RATES:
            for model in (
                ("white", "colored", "bandwidth") if split == "cal_score" else ("white", "colored")
            ):
                for rep in range(20 if split == "cal_score" else 60):
                    add(fs=fs, model=model, group="noise", rep=rep)
    elif split == "development":
        for fs in RATES:
            for group in ("core", "chirp"):
                for rep in range(4):
                    add(
                        fs=fs,
                        group=group,
                        band="low",
                        snr=-10 if group == "core" else 20,
                        duration_ns=20 if group == "chirp" else 0,
                        rep=rep,
                    )
    elif split == "grid":
        # Same physical frequencies and phases across rates, types and scale grids.
        frequencies = [
            (b, float(rng.uniform(*bounds))) for b, bounds in BANDS.items() for _ in range(4)
        ]
        for fs in RATES:
            for band, freq in frequencies:
                for kind in ("clean", "noisy", "linear"):
                    add(
                        fs=fs,
                        group="grid",
                        band=band,
                        kind=kind,
                        frequency_hz=freq,
                        snr=0 if kind == "noisy" else 1000,
                    )
    else:
        for fs in RATES:
            for band in BANDS:
                for snr in (20, 0, -10):
                    for model in ("white", "colored"):
                        for rep in range(repeats):
                            add(fs=fs, band=band, snr=snr, model=model, rep=rep)
            for group in ("amplitude", "fade", "burst", "bandwidth"):
                for band in BANDS:
                    for rep in range(repeats):
                        add(
                            fs=fs,
                            band=band,
                            group=group,
                            snr=-10 if group == "bandwidth" else 0,
                            model="bandwidth" if group == "bandwidth" else "white",
                            rep=rep,
                        )
            for duration in (200, 80, 20, 4):
                for rep in range(repeats):
                    add(fs=fs, group="chirp", band="sweep", duration_ns=duration, rep=rep)
            for frequency in (1e9, 5e9):
                for duration in (4, 20, 80):
                    for rep in range(repeats):
                        add(
                            fs=fs,
                            group="pulse",
                            band="mid" if frequency == 1e9 else "high",
                            frequency_hz=frequency,
                            duration_ns=duration,
                            snr=0,
                            rep=rep,
                        )
            for frequency in (0.5e9, 2e9):
                for rep in range(repeats):
                    add(
                        fs=fs,
                        group="branches",
                        frequency_hz=frequency,
                        band="low" if frequency == 0.5e9 else "mid",
                        rep=rep,
                    )
            for model in ("white", "colored"):
                for rep in range(2 * repeats):
                    add(fs=fs, group="noise", model=model, band="none", rep=rep)
    return rows


def make_case(spec: dict[str, Any]) -> Case:
    fs, freq = float(spec["fs"]), float(spec["frequency_hz"])
    n = round(DURATION * fs)
    t = np.arange(n, dtype=np.float64) / fs
    group = spec["group"]
    truth = np.full(n, freq)
    active = np.ones(n, dtype=np.bool_)
    other = np.full(n, np.nan)
    amplitude = np.ones(n)
    cycles = freq * t
    if group == "chirp":
        duration = spec["duration_ns"] * 1e-9
        on, off = 200e-9 - duration / 2, 200e-9 + duration / 2
        u = np.clip(t - on, 0, duration)
        truth = 0.5e9 + 3.5e9 * u / duration
        cycles = 0.5e9 * t + 0.5 * 3.5e9 / duration * u**2 + 3.5e9 * np.maximum(t - off, 0)
    elif group == "grid" and spec["kind"] == "linear":
        rate = (min(1.15 * freq, 5.7e9) - freq) / t[-1]
        truth = freq + rate * t
        cycles = freq * t + 0.5 * rate * t**2
    elif group == "amplitude":
        amplitude = 0.6 + 0.4 * np.cos(2 * np.pi * t / DURATION)
    elif group == "fade":
        amplitude[(t >= 180e-9) & (t < 220e-9)] = 0.05
    elif group == "pulse":
        active = (t >= 200e-9) & (t < 200e-9 + spec["duration_ns"] * 1e-9)
    elif group == "noise":
        active[:] = False
    phase = spec["phase0"] + 2 * np.pi * cycles
    clean = amplitude * active * np.cos(phase)
    target_power = float(np.mean(clean[active] ** 2)) if active.any() else 0.0
    if group == "branches":
        clean *= 0.5
        target_power *= 0.25
        other[:] = 2e9 if freq == 0.5e9 else 0.5e9
        clean += np.cos(0.83 + 2 * np.pi * other * t)
    sigma = float(np.sqrt(target_power / 10 ** (float(spec["snr"]) / 10)))
    if group == "noise":
        sigma = 1.0
    contamination = sigma * noise(n, fs, spec["model"], spec["seed"])
    background_power = float(np.mean(contamination**2))
    if group == "burst":
        mask = (t >= 190e-9) & (t < 192e-9)
        rng = np.random.default_rng(np.random.SeedSequence([spec["seed"], 99]))
        contamination[mask] += 4 * sigma * rng.normal(size=int(mask.sum()))
    actual_noise_power = float(np.mean(contamination[active] ** 2)) if active.any() else 1.0
    recipe = dict(
        spec,
        samples=n,
        noise_sigma_v=sigma,
        clean_target_power_v2=target_power,
        background_noise_power_v2=background_power,
        actual_noise_power_v2=actual_noise_power,
        realized_snr_db=10 * np.log10(target_power / actual_noise_power)
        if target_power > 0 and actual_noise_power > 0
        else None,
    )
    truth = np.where(active, truth, np.nan)
    return Case(SampledSignal(t, clean + contamination), truth, other, active, phase, sigma, recipe)
