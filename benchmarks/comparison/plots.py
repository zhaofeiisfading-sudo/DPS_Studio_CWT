"""Actual-cell plots with complete records, explicit scales and no trajectory repair."""

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .core import METHODS, Analysis
from .storage import output_path, write_json

COLORS = ("#0072B2", "#D55E00", "#009E73")
LABELS = (
    "CWT cmor1.5-1.0 / raw / 143 scales",
    "Balanced Hann 768 / hop128 / FFT4096",
    "High time Hann 512 / hop128 / FFT4096",
)
plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "savefig.dpi": 300})


def axis_limits(ax: Axes, t0: float, t1: float) -> None:
    ax.set_xlim(t0 * 1e6, t1 * 1e6)
    ax.set_ylim(0.1, 6)
    ax.set_ylabel("Frequency (GHz)")
    ax.ticklabel_format(axis="x", style="plain", useOffset=False)


def shade_edge(ax: Axes, analysis: Analysis) -> None:
    t = analysis.native["time_s"] * 1e6
    inside = np.flatnonzero(~analysis.native["bank_edge"])
    if inside.size:
        ax.axvspan(t[0], t[inside[0]], color="white", alpha=0.18, hatch="///", lw=0)
        ax.axvspan(t[inside[-1]], t[-1], color="white", alpha=0.18, hatch="///", lw=0)
    else:
        ax.axvspan(t[0], t[-1], color="white", alpha=0.18, hatch="///", lw=0)


def save(fig: Figure, path: Path) -> None:
    output_path(path)
    if path.exists():
        raise FileExistsError(path)
    fig.savefig(path, dpi=300)
    plt.close(fig)


def comparison_plots(
    directory: Path,
    label: str,
    analyses: dict[str, Analysis],
    paired: dict[str, Any],
) -> dict[str, Any]:
    records: dict[str, Any] = {}
    displays: dict[str, dict[str, Any]] = {}
    t0 = float(analyses["cwt"].native["time_s"][0])
    t1 = float(analyses["cwt"].native["time_s"][-1])
    for method in METHODS:
        with np.load(directory / method / "display.npz") as loaded:
            displays[method] = {k: loaded[k] for k in loaded.files}
        interior = paired["common_interior"]
        reference = float(np.median(paired[f"{method}_median"][interior])) if interior.any() else 0
        records[method] = dict(
            linear=analyses[method].metadata["display"],
            record_reference_v=reference,
            background_normalization="NOT AVAILABLE",
            db_rule="20log10(response / median_time(common-interior median_frequency(response)))",
            db_limits=[-20, 60],
            zero_db_floor=-300,
            reference_caveat="record statistic, grid-dependent; NOT noise or SNR",
            absolute_time_limits_s=[t0, t1],
            frequency_limits_hz=[0.1e9, 6e9],
        )
    for style in ("linear", "db"):
        fig, axes = plt.subplots(3, 1, figsize=(11.5, 8.5), sharex=True, layout="constrained")
        fig.suptitle(f"{label} | full original record | {style}; hatching = edge risk")
        for i, method in enumerate(METHODS):
            d, a, ax = displays[method], analyses[method], axes[i]
            score = d["response"]
            if style == "db":
                ref = records[method]["record_reference_v"]
                if ref > 0:
                    values = 20 * np.log10(np.maximum(score / ref, 1e-15))
                else:
                    values = np.full_like(score, np.nan)
                vmin, vmax = -20, 60
                colorlabel = "dB / record reference\nnoise norm: NOT AVAILABLE"
            else:
                values = score
                vmin, vmax = 0, a.metadata["display"]["vmax"]
                colorlabel = "CWT coefficient (V)" if method == "cwt" else "STFT peak amplitude (V)"
            mesh = ax.pcolormesh(
                d["time_s"] * 1e6,
                d["frequency_hz"] / 1e9,
                values,
                cmap="viridis",
                shading="nearest",
                vmin=vmin,
                vmax=max(vmax, 1e-30),
                rasterized=True,
            )
            axis_limits(ax, t0, t1)
            shade_edge(ax, a)
            ax.set_title(LABELS[i], loc="left")
            fig.colorbar(mesh, ax=ax, label=colorlabel, pad=0.01)
        axes[-1].set_xlabel("Time (us), original input axis")
        save(fig, directory / f"comparison_{style}.png")
    for mode in ("native", "common"):
        fig, ax = plt.subplots(figsize=(11.5, 4), layout="constrained")
        for i, method in enumerate(METHODS):
            t = (
                analyses[method].native["time_s"]
                if mode == "native"
                else paired[f"{method}_time_s"]
            )
            f = (
                analyses[method].native["frequency_hz"]
                if mode == "native"
                else paired[f"{method}_frequency_hz"]
            )
            ax.scatter(
                t * 1e6,
                f / 1e9,
                s=0.5 if mode == "native" else 3,
                color=COLORS[i],
                alpha=0.55,
                label=f"{method}: {len(t)} points",
            )
        axis_limits(ax, t0, t1)
        ax.set_xlabel("Time (us), original input axis; unconnected actual candidates")
        ax.set_title(f"{label} | {mode} strongest; quality UNKNOWN, no gating")
        ax.legend(loc="upper right", markerscale=3, fontsize=8)
        save(fig, directory / f"candidates_{mode}.png")
    fig, axes = plt.subplots(3, 2, figsize=(11.5, 8), layout="constrained")
    for i, method in enumerate(METHODS):
        t = paired[f"{method}_time_s"] * 1e6
        peak, background = paired[f"{method}_peak"], paired[f"{method}_median"]
        axes[i, 0].plot(t, peak, lw=0.7, color=COLORS[i], label="E=max response")
        axes[i, 0].plot(t, background, lw=0.7, color="0.3", label="frequency median")
        axes[i, 0].set_ylabel(f"{method} response (V)")
        axes[i, 0].legend(fontsize=7)
        axes[i, 1].plot(t, paired[f"{method}_peak_to_median"], lw=0.7, color=COLORS[i])
        axes[i, 1].set_ylabel("Peak / frequency median")
        for ax in axes[i]:
            ax.set_xlim(t0 * 1e6, t1 * 1e6)
            ax.ticklabel_format(axis="x", style="plain", useOffset=False)
    for ax in axes[-1]:
        ax.set_xlabel("Time (us), original input axis")
    fig.suptitle(f"{label} | common-grid descriptive response; no independent presence labels")
    save(fig, directory / "background_diagnostics.png")
    good = np.flatnonzero(paired["common_interior"])
    if good.size:
        center = float(paired["cwt_time_s"][good[np.argmax(paired["cwt_peak"][good])]])
        low, high = max(t0, center - 0.15e-6), min(t1, center + 0.15e-6)
        fig, axes = plt.subplots(4, 1, figsize=(11.5, 9), sharex=True, layout="constrained")
        for i, method in enumerate(METHODS):
            d = displays[method]
            ref = records[method]["record_reference_v"]
            v = 20 * np.log10(np.maximum(d["response"] / max(ref, 1e-300), 1e-15))
            axes[i].pcolormesh(
                d["time_s"] * 1e6,
                d["frequency_hz"] / 1e9,
                v,
                shading="nearest",
                cmap="viridis",
                vmin=-20,
                vmax=60,
                rasterized=True,
            )
            axis_limits(axes[i], low, high)
            axes[i].set_title(LABELS[i], loc="left")
            axes[-1].scatter(
                paired[f"{method}_time_s"] * 1e6,
                paired[f"{method}_frequency_hz"] / 1e9,
                s=3,
                color=COLORS[i],
                label=method,
            )
        axis_limits(axes[-1], low, high)
        axes[-1].legend()
        axes[-1].set_xlabel("Time (us), original axis; dB reference as full-record plot")
        fig.suptitle(f"{label} | exploratory ROI at CWT E maximum; NOT unbiased evidence")
        save(fig, directory / "exploratory_roi.png")
        records["roi"] = dict(
            low_s=low,
            high_s=high,
            rule="CWT common-interior E maximum +/-150ns; post hoc observation",
        )
    write_json(directory / "plot_metadata.json", records)
    return records


def overview(run: Path, channels: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(
        len(channels), 3, figsize=(15, 2.0 * len(channels)), squeeze=False, layout="constrained"
    )
    for row, channel in enumerate(channels):
        directory = run / channel["directory"]
        for col, method in enumerate(METHODS):
            ax = axes[row, col]
            path = directory / method / "display.npz"
            if not path.exists():
                ax.text(0.5, 0.5, "FAILED; see manifest", ha="center")
                continue
            with np.load(path) as d:
                vmax = json.loads(
                    (directory / method / "metadata.json").read_text(encoding="utf-8")
                )["display"]["vmax"]
                ax.pcolormesh(
                    d["time_s"] * 1e6,
                    d["frequency_hz"] / 1e9,
                    d["response"],
                    cmap="viridis",
                    shading="nearest",
                    vmin=0,
                    vmax=max(vmax, 1e-30),
                    rasterized=True,
                )
                ax.set_xlim(float(d["time_s"][0] * 1e6), float(d["time_s"][-1] * 1e6))
            ax.set_ylim(0.1, 6)
            ax.set_title(f"{channel['file']} / {channel['channel']} | {method}", fontsize=8)
            ax.set_ylabel("GHz", fontsize=8)
            ax.set_xlabel("Time (us), original", fontsize=7)
            ax.ticklabel_format(axis="x", style="plain", useOffset=False)
            ax.tick_params(labelsize=6)
    fig.suptitle("All 14 channels | own linear amplitude scales; original plots indexed separately")
    save(fig, run / "all_channels_comparison_overview.png")
