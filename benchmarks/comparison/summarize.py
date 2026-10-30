"""Post-run tables and figures. No changes to frozen transforms or metrics."""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .core import METHODS
from .plots import COLORS, save
from .storage import output_path, write_csv, write_json


def condition(row: dict[str, Any]) -> str:
    recipe = row["recipe"]
    fields = ("freq", "snr", "kind", "duration_ns", "other", "separation")
    return json.dumps({k: recipe[k] for k in fields if k in recipe}, sort_keys=True)


def condition_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, float, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["scope"] == "common_interior":
            groups[(row["group"], row["recipe"]["fs"], condition(row), row["method"])].append(row)
    output = []
    for (group, fs, config, method), items in sorted(groups.items()):
        record = dict(
            group=group,
            fs_hz=fs,
            condition=config,
            method=method,
            seeds=[r["seed"] for r in items],
            count=len(items),
        )
        for name in (
            "rmse_hz",
            "mae_hz",
            "bias_hz",
            "wrong_branch_rate",
            "onset_error_s",
            "noise_fpr",
            "far_background_fpr",
            "active_frame_detection_rate",
            "response_auroc",
            "step_before_rmse_hz",
            "step_after_rmse_hz",
            "fast_chirp_rmse_hz",
            "jump_over_500mhz_rate",
        ):
            values = [r[name] for r in items if r.get(name) is not None]
            for suffix, function in (("mean", np.mean), ("min", np.min), ("max", np.max)):
                record[f"{name}_{suffix}"] = float(function(values)) if values else None
        valid = [r for r in items if r["rmse_hz"] is not None]
        record["pooled_rmse_hz"] = (
            float(
                np.sqrt(
                    sum(r["rmse_hz"] ** 2 * r["truth_points"] for r in valid)
                    / sum(r["truth_points"] for r in valid)
                )
            )
            if valid
            else None
        )
        for name in ("any_active_hit", "pre_onset_trigger", "onset_missed", "two_peaks_resolved"):
            values = [r[name] for r in items if r.get(name) is not None]
            record[f"{name}_fraction"] = float(np.mean(values)) if values else None
        output.append(record)
    return output


def example_figures(run: Path, rows: list[dict[str, Any]]) -> None:
    selected = []
    for fs in (40e9, 80e9):
        selectors: list[tuple[str, dict[str, Any]]] = [
            ("S2", dict(freq=1e9, snr=-10)),
            ("S3", dict(kind="fast")),
            ("S4", dict(freq=5e9, duration_ns=4)),
            ("S5", {}),
            ("S6", dict(freq=2e9)),
            ("S6_separation", dict(separation=0.1e9)),
            ("S7", dict(kind="step")),
            ("S7", dict(kind="cross")),
        ]
        for group, match in selectors:
            selected.append(
                next(
                    r
                    for r in rows
                    if r["method"] == "cwt"
                    and r["scope"] == "common_interior"
                    and r["group"] == group
                    and r["recipe"]["fs"] == fs
                    and r["seed"] == 20001
                    and all(r["recipe"].get(k) == v for k, v in match.items())
                )
            )
    examples = output_path(run / "synthetic_examples")
    examples.mkdir()
    for row in selected:
        directory = run / "synthetic" / row["case"]
        with np.load(directory / "signal_truth.npz") as loaded:
            t, truth, other = loaded["time_s"], loaded["truth_hz"], loaded["interference_hz"]
        with np.load(directory / "common_grid.npz") as loaded:
            paired = {k: loaded[k] for k in loaded.files}
        fig, axes = plt.subplots(4, 1, figsize=(10.5, 9), sharex=True, layout="constrained")
        fig.suptitle(f"{row['case']} | own linear scales; known truth; no gating")
        for i, method in enumerate(METHODS):
            with np.load(directory / method / "display.npz") as d:
                mesh = axes[i].pcolormesh(
                    d["time_s"] * 1e9,
                    d["frequency_hz"] / 1e9,
                    d["response"],
                    shading="nearest",
                    cmap="viridis",
                    vmin=0,
                    rasterized=True,
                )
                fig.colorbar(mesh, ax=axes[i], label="Response (V), method definition")
            axes[i].set_ylabel(f"{method}\nFrequency (GHz)")
            axes[i].set_ylim(0.1, 6)
            axes[i].plot(t * 1e9, truth / 1e9, color="white", lw=0.7, ls="--")
            axes[-1].scatter(
                paired[f"{method}_time_s"] * 1e9,
                paired[f"{method}_frequency_hz"] / 1e9,
                s=3,
                color=COLORS[i],
                label=method,
            )
        axes[-1].plot(t * 1e9, truth / 1e9, color="black", lw=1, ls="--", label="target truth")
        if np.isfinite(other).any():
            axes[-1].plot(t * 1e9, other / 1e9, color="0.5", lw=1, ls=":", label="other truth")
        axes[-1].set_ylim(0.1, 6)
        axes[-1].set_xlim(float(t[0] * 1e9), float(t[-1] * 1e9))
        axes[-1].set_xlabel("Time (ns); actual common-grid candidates")
        axes[-1].set_ylabel("Frequency (GHz)")
        axes[-1].legend(ncol=5, fontsize=7, loc="upper right")
        save(fig, examples / f"{row['case']}.png")


def summary_figure(run: Path, grouped: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 6.5), layout="constrained")
    for row, fs in enumerate((40e9, 80e9)):
        for col, f in enumerate((0.2e9, 1e9, 5e9)):
            ax = axes[row, col]
            for i, method in enumerate(METHODS):
                points = []
                for snr in (-10, 0, 20):
                    record = next(
                        g
                        for g in grouped
                        if g["group"] == "S2"
                        and g["fs_hz"] == fs
                        and g["method"] == method
                        and json.loads(g["condition"]) == dict(freq=f, snr=snr)
                    )
                    points.append(record)
                y = np.array([g["rmse_hz_mean"] for g in points]) / 1e6
                low = np.array([g["rmse_hz_min"] for g in points]) / 1e6
                high = np.array([g["rmse_hz_max"] for g in points]) / 1e6
                ax.errorbar(
                    [-10, 0, 20],
                    y,
                    yerr=[np.maximum(y - low, 0), np.maximum(high - y, 0)],
                    color=COLORS[i],
                    marker="o",
                    ms=3,
                    capsize=3,
                    label=method,
                )
            ax.set_yscale("symlog", linthresh=0.5)
            ax.set_ylim(bottom=0)
            ax.set_title(f"{fs / 1e9:g} GS/s | {f / 1e9:g} GHz")
            ax.set_xlabel("SNR (dB), defined at input")
            ax.set_ylabel("Frequency RMSE (MHz)")
            ax.set_xticks([-10, 0, 20])
            ax.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=7)
    fig.suptitle(
        "Held-out S2 | common interior | seed mean and min-max (not CI) | "
        "symlog linear below 0.5 MHz, including exact zero"
    )
    save(fig, run / "synthetic_snr_summary.png")


def onset_figure(run: Path, grouped: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(15, 7), layout="constrained")
    for row, fs in enumerate((40e9, 80e9)):
        for col, frequency in enumerate((1e9, 5e9)):
            for i, method in enumerate(METHODS):
                points = []
                for duration in (4, 20, 80):
                    point = next(
                        g
                        for g in grouped
                        if g["group"] == "S4"
                        and g["fs_hz"] == fs
                        and g["method"] == method
                        and json.loads(g["condition"]) == dict(freq=frequency, duration_ns=duration)
                    )
                    points.append(point)
                x = np.array([4, 20, 80]) + (i - 1) * 1.0
                onset = (
                    np.array(
                        [
                            p["onset_error_s_mean"]
                            if p["onset_error_s_mean"] is not None
                            else np.nan
                            for p in points
                        ]
                    )
                    * 1e9
                )
                low = (
                    np.array(
                        [
                            p["onset_error_s_min"] if p["onset_error_s_min"] is not None else np.nan
                            for p in points
                        ]
                    )
                    * 1e9
                )
                high = (
                    np.array(
                        [
                            p["onset_error_s_max"] if p["onset_error_s_max"] is not None else np.nan
                            for p in points
                        ]
                    )
                    * 1e9
                )
                axes[row, col].errorbar(
                    x,
                    onset,
                    yerr=[np.maximum(onset - low, 0), np.maximum(high - onset, 0)],
                    color=COLORS[i],
                    marker="o",
                    ms=3,
                    capsize=3,
                    label=method,
                )
                detection = [p["active_frame_detection_rate_mean"] for p in points]
                axes[row, col + 2].plot(
                    x, detection, color=COLORS[i], marker="o", ms=3, label=method
                )
            axes[row, col].axhline(0, color="0.5", ls=":", lw=0.7)
            axes[row, col].set_ylabel("First crossing - onset (ns)")
            axes[row, col + 2].set_ylabel("Active-frame detection fraction")
            axes[row, col + 2].set_ylim(0, 1.05)
            for ax in (axes[row, col], axes[row, col + 2]):
                ax.set_title(f"{fs / 1e9:g} GS/s | {frequency / 1e9:g} GHz")
                ax.set_xlabel("Pulse duration (ns)")
                ax.set_xticks([4, 20, 80])
                ax.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=7)
    fig.suptitle(
        "S4 | 0 dB input SNR | independent 1% frame-FPR calibration | "
        "onset mean and seed min-max, including early noise triggers"
    )
    save(fig, run / "onset_presence_summary.png")


def summarize(run: Path) -> dict[str, Any]:
    run = output_path(run)
    rows = json.loads((run / "synthetic_metrics.json").read_text(encoding="utf-8"))
    grouped = condition_summary(rows)
    write_csv(run / "condition_summary.csv", grouped)
    write_json(run / "condition_summary.json", grouped)
    summary_figure(run, grouped)
    onset_figure(run, grouped)
    example_figures(run, rows)
    cases: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row["scope"] == "common_interior":
            cases[row["case"]][row["method"]] = row
    text = [
        "# 全部156个held-out案例：共同内部结果",
        "",
        "频率误差单位MHz；onset单位ns。顺序均CWT / Balanced / High time。",
        "无信号无频率真值记—；wrong为距预先标记的另一分量更近的比例；onset含提前触发。",
        "S6_separation是等幅双峰专项：其RMSE仅为距低频参考的距离，wrong仅为选择高频分量的比例，",
        "不视为物理错误或用于优胜统计；双峰结论只看two_peaks_resolved。",
        "",
        "| Case | 条件 | RMSE C/B/H (MHz) | wrong C/B/H | onset C/B/H (ns) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, methods in sorted(cases.items()):

        def values(
            key: str, multiplier: float = 1, current: dict[str, dict[str, Any]] = methods
        ) -> str:
            return " / ".join(
                "—" if current[m].get(key) is None else f"{current[m][key] * multiplier:.6g}"
                for m in METHODS
            )

        recipe = condition(methods["cwt"]).replace('"', "").replace("{}", "noise")
        text.append(
            f"| {name} | {recipe} | {values('rmse_hz', 1e-6)} | "
            f"{values('wrong_branch_rate')} | {values('onset_error_s', 1e9)} |"
        )
    (run / "all_synthetic_cases.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    comparisons = []
    for name, methods in sorted(cases.items()):
        cwt, stft = methods["cwt"], methods["balanced"]
        if cwt["rmse_hz"] is None or cwt["group"] == "S6_separation":
            continue
        ratio = cwt["rmse_hz"] / stft["rmse_hz"] if stft["rmse_hz"] > 0 else None
        comparisons.append(
            dict(
                case=name,
                group=cwt["group"],
                fs_hz=cwt["recipe"]["fs"],
                condition=condition(cwt),
                cwt_over_balanced_rmse=ratio,
                cwt_rmse_hz=cwt["rmse_hz"],
                balanced_rmse_hz=stft["rmse_hz"],
            )
        )
    write_csv(run / "case_harm_comparison.csv", comparisons)
    cwt_wins = sum(r["cwt_rmse_hz"] < 0.9 * r["balanced_rmse_hz"] for r in comparisons)
    cwt_harm = sum(r["cwt_rmse_hz"] > 1.1 * r["balanced_rmse_hz"] for r in comparisons)
    repeated: dict[tuple[str, float, str], list[dict[str, Any]]] = defaultdict(list)
    for record in comparisons:
        repeated[(record["group"], record["fs_hz"], record["condition"])].append(record)
    stable_wins = [
        str(k)
        for k, values in repeated.items()
        if len(values) == 3 and all(v["cwt_rmse_hz"] < 0.9 * v["balanced_rmse_hz"] for v in values)
    ]
    stable_losses = [
        str(k)
        for k, values in repeated.items()
        if len(values) == 3 and all(v["cwt_rmse_hz"] > 1.1 * v["balanced_rmse_hz"] for v in values)
    ]
    verdict = "MIXED" if stable_wins and stable_losses else "INCONCLUSIVE"
    result = dict(
        scientific_verdict=verdict,
        cases=156,
        conditions=len(grouped) // 3,
        cwt_better_by_10pct_cases_vs_balanced=cwt_wins,
        cwt_worse_by_10pct_cases_vs_balanced=cwt_harm,
        stable_win_conditions_vs_balanced=stable_wins,
        stable_loss_conditions_vs_balanced=stable_losses,
        caveat="Reused noise and correlated conditions; descriptive counts, not votes or p-values.",
        conditions_table="condition_summary.csv",
        all_case_table="all_synthetic_cases.md",
    )
    write_json(run / "scientific_assessment.json", result)
    failure_text = [
        "# 失败与负结果",
        "",
        "工程失败参见synthetic_failures及channel_index。",
        "本表按每组最大的CWT/Balanced误差比固定列出；不删除其余案例。",
        "",
        "| 组 | Case | CWT RMSE MHz | Balanced RMSE MHz | 比值 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for group in sorted({r["group"] for r in comparisons}):
        worst = max(
            (r for r in comparisons if r["group"] == group),
            key=lambda r: (
                r["cwt_over_balanced_rmse"]
                if r["cwt_over_balanced_rmse"] is not None
                else float("inf")
            ),
        )
        ratio_text = (
            f"{worst['cwt_over_balanced_rmse']:.6g}"
            if (worst["cwt_over_balanced_rmse"] is not None)
            else "undefined: Balanced=0"
        )
        failure_text.append(
            f"| {group} | {worst['case']} | {worst['cwt_rmse_hz'] / 1e6:.6g} | "
            f"{worst['balanced_rmse_hz'] / 1e6:.6g} | "
            f"{ratio_text} |"
        )
    failure_text += [
        "",
        "纯噪声不存在频率真值；不能用候选频率与0比较。",
        "存在性阈值只在10条独立噪声记录校准，held-out FPR并不保证等于1%。",
        "真实背景标准化NOT AVAILABLE；线性图暗色不能认证无信号或速度为0。",
        "完整逐条件种子范围、门内检测率、提前触发和双峰分离在condition_summary.csv。",
    ]
    (run / "failure_cases.md").write_text("\n".join(failure_text) + "\n", encoding="utf-8")
    paths = [
        dict(path=p.relative_to(run).as_posix(), bytes=p.stat().st_size)
        for p in sorted(run.rglob("*"))
        if p.is_file()
    ]
    write_csv(run / "results_index.csv", paths)
    return result


if __name__ == "__main__":
    print(json.dumps(summarize(Path(sys.argv[1])), indent=2))
