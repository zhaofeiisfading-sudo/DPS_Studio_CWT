"""Small post-study figure set; every plot is exported, with no analysis changes."""

import csv
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .io import output

COLORS = {
    "A0": "#0072B2",
    "A1": "#D55E00",
    "A2": "#009E73",
    "balanced": "#CC79A7",
    "high_time": "#555555",
}


def save(fig: Any, run: Path, name: str) -> None:
    fig.savefig(output(run / "figures" / name), dpi=180)
    plt.close(fig)


def figures(run: Path) -> None:
    rows = json.loads((run / "condition_summary.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), layout="constrained", sharex=True)
    for i, fs in enumerate((40e9, 80e9)):
        for j, band in enumerate(("low", "mid", "high")):
            ax = axes[i, j]
            for method, color in COLORS.items():
                selected = sorted(
                    [
                        r
                        for r in rows
                        if r["group"] == "core"
                        and r["fs_hz"] == fs
                        and r["band"] == band
                        and r["noise"] == "white"
                        and r["method"] == method
                    ],
                    key=lambda r: r["snr_db"],
                )
                ax.plot(
                    [r["snr_db"] for r in selected],
                    [r["rmse_hz_mean"] / 1e6 for r in selected],
                    "o-",
                    color=color,
                    label=method,
                )
            ax.set(
                title=f"{fs / 1e9:g} GS/s | {band}",
                xlabel="Input SNR (dB)",
                ylabel="Mean waveform RMSE (MHz)",
            )
            ax.set_yscale("log")
            ax.grid(alpha=0.2)
    axes[0, 0].legend(ncol=3, fontsize=8)
    fig.suptitle("Independent held-out off-grid tones | white noise | 20 waveforms / condition")
    save(fig, run, "heldout_weak_signal.png")
    with (run / "scale_bias_analysis.csv").open(encoding="utf-8", newline="") as handle:
        grid = list(csv.DictReader(handle))
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained")
    for ax, kind in zip(axes, ("clean", "noisy", "linear"), strict=True):
        for mode in ("A0", "A1", "A2"):
            for fs, style in ((40e9, "-"), (80e9, "--")):
                selected = [
                    r
                    for r in grid
                    if r["kind"] == kind and r["method"] == mode and float(r["fs_hz"]) == fs
                ]
                values = [
                    np.sqrt(
                        np.mean(
                            [float(r["rmse_hz"]) ** 2 for r in selected if int(r["voices"]) == v]
                        )
                    )
                    / 1e6
                    for v in (24, 48, 96)
                ]
                ax.plot(
                    [24, 48, 96],
                    values,
                    "o" + style,
                    color=COLORS[mode],
                    label=f"{mode}/{fs / 1e9:g}",
                )
        ax.set(title=kind, xlabel="Voices / octave", ylabel="Pooled grid RMSE (MHz)")
        ax.set_yscale("log")
        ax.grid(alpha=0.2)
    axes[0].legend(fontsize=7, ncol=2)
    fig.suptitle("Grid density: 12 frozen off-grid frequencies / type; noisy results descriptive")
    save(fig, run, "grid_density.png")
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout="constrained")
    for i, fs in enumerate((40e9, 80e9)):
        for j, physical in enumerate((False, True)):
            ax = axes[i, j]
            for mode in ("A0", "A1", "A2", "balanced", "high_time"):
                method = mode
                if physical:
                    method = f"{mode}_physical" if mode.startswith("A") else f"physical_{mode}"
                selected = sorted(
                    [
                        r
                        for r in rows
                        if r["group"] == "chirp"
                        and r["fs_hz"] == fs
                        and r["method"] == method
                        and r["scope"] == "event"
                    ],
                    key=lambda r: r["duration_ns"],
                )
                ax.plot(
                    [r["duration_ns"] for r in selected],
                    [r["rmse_hz_mean"] / 1e6 for r in selected],
                    "o-",
                    color=COLORS[mode],
                    label=mode,
                )
            ax.set(
                title=(
                    f"{fs / 1e9:g} GS/s | "
                    + ("physical-time control" if physical else "frozen sample windows")
                ),
                xlabel="Chirp duration (ns)",
                ylabel="Event mean waveform RMSE (MHz)",
            )
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.grid(alpha=0.2)
    axes[0, 0].legend(ncol=3, fontsize=8)
    fig.suptitle("Analytic 0.5 to 4 GHz chirps | white noise 20 dB | exact common sample centers")
    save(fig, run, "transient_window_mechanism.png")
    channels = json.loads((run / "real_channel_index.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(7, 2, figsize=(14, 19), layout="constrained")
    for ax, entry in zip(axes.flat, channels, strict=True):
        with np.load(run / entry["directory"] / "common_spectral_support.npz") as saved:
            for mode in COLORS:
                ax.plot(
                    saved["time_s"] * 1e6,
                    saved[f"{mode}_prediction"] / 1e9,
                    lw=0.5,
                    alpha=0.8,
                    color=COLORS[mode],
                    label=mode,
                )
        ax.set(
            title=f"{entry['file']}/{entry['channel']}",
            ylabel="Candidate GHz",
            xlabel="Absolute time (us)",
            ylim=(0.1, 6),
        )
        ax.ticklabel_format(axis="x", useOffset=False)
    axes[0, 0].legend(ncol=3, fontsize=8)
    fig.suptitle("All 14 real channels | descriptive only | A2 exploratory | no real truth")
    save(fig, run, "all_real_channels.png")


if __name__ == "__main__":
    figures(Path(sys.argv[1]))
