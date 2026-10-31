"""Waveform-paired uncertainty and preregistered decision rules, after evaluation."""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from .io import output, write_csv, write_json

GROUP = ("group", "fs_hz", "band", "snr_db", "noise", "duration_ns", "kind", "scope", "voices")


def bootstrap(values: Any, confidence: float = 0.95) -> list[float]:
    a = np.asarray(values, dtype=np.float64)
    if a.size < 2:
        return [float(a.mean()), float(a.mean())]
    rng = np.random.default_rng(810000)
    means = a[rng.integers(0, a.size, size=(10000, a.size))].mean(axis=1)
    tail = (1 - confidence) / 2
    return [float(v) for v in np.quantile(means, [tail, 1 - tail])]


def wilson(successes: int, count: int) -> list[float]:
    if not count:
        return [float("nan"), float("nan")]
    z = 1.959963984540054
    p = successes / count
    center = (p + z * z / (2 * count)) / (1 + z * z / count)
    half = z * np.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / (1 + z * z / count)
    return [float(center - half), float(center + half)]


def summarize(run: Path) -> dict[str, Any]:
    rows = [
        r
        for p in sorted((run / "evaluation").glob("*/metrics.json"))
        for r in json.loads(p.read_text(encoding="utf-8"))
    ]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(k) for k in GROUP)].append(row)
    summaries = []
    for key, records in groups.items():
        for method in sorted({r["method"] for r in records}):
            physical = "physical" in method
            baseline_method = "physical_balanced" if physical else "balanced"
            raw_method = "A0_physical" if physical else "A0"
            baselines = {r["case"]: r for r in records if r["method"] == baseline_method}
            raw = {r["case"]: r for r in records if r["method"] == raw_method}
            selected = [r for r in records if r["method"] == method]
            summary = dict(
                zip(GROUP, key, strict=True), method=method, independent_waveforms=len(selected)
            )
            for metric in (
                "rmse_hz",
                "mae_hz",
                "bias_hz",
                "catastrophic_rate",
                "wrong_branch_rate",
                "presence",
                "supported",
                "rank_median",
                "strongest_accuracy",
                "top3_recall",
                "top5_recall",
                "failure_presence",
                "failure_top5",
                "jump_over_500mhz_rate",
                "low_selection_fraction",
                "high_selection_fraction",
                "realized_snr_db",
                "background_ratio_median",
            ):
                values = [r[metric] for r in selected if r.get(metric) is not None]
                if values:
                    summary[f"{metric}_mean"] = float(np.mean(values))
                    summary[f"{metric}_median"] = float(np.median(values))
                    summary[f"{metric}_min"] = float(np.min(values))
                    summary[f"{metric}_max"] = float(np.max(values))
            paired = [
                (r, baselines[r["case"]])
                for r in selected
                if r["case"] in baselines and r.get("rmse_hz") is not None
            ]
            if paired:
                delta = [a["rmse_hz"] - b["rmse_hz"] for a, b in paired]
                summary["paired_delta_B_mean_hz"] = float(np.mean(delta))
                summary["paired_delta_B_ci95_hz"] = bootstrap(delta)
                near_zero = np.mean([b["rmse_hz"] for _, b in paired]) < 1e7
                go_delta = [
                    a["rmse_hz"] - b["rmse_hz"] + 2e6
                    if near_zero
                    else a["rmse_hz"] - 0.8 * b["rmse_hz"]
                    for a, b in paired
                ]
                summary["near_zero_baseline"] = bool(near_zero)
                summary["GO_delta_ci975_hz"] = bootstrap(go_delta, 0.975)
                summary["paired_harm_A0_mean_hz"] = (
                    float(np.mean([a["rmse_hz"] - raw[a["case"]]["rmse_hz"] for a, _ in paired]))
                    if raw
                    else None
                )
                if near_zero:
                    summary["GO_absolute_cap_pass"] = all(a["rmse_hz"] <= 1e7 for a, _ in paired)
                else:
                    summary["GO_absolute_cap_pass"] = True
                summary["GO_bias_pass"] = all(
                    "truth_mean_hz" in a
                    and abs(a["bias_hz"]) <= max(1e7, 0.02 * a["truth_mean_hz"])
                    for a, _ in paired
                )
                summary["GO_catastrophe_pass"] = all(
                    a["catastrophic_rate"] < 0.01 for a, _ in paired if "catastrophic_rate" in a
                )
            for control in ("frame", "record"):
                for metric in (
                    "frame_fpr",
                    "record_fpr",
                    "detection_probability",
                    "missed_detection",
                    "early_trigger",
                    "onset_error_s",
                    "active_frame_detection_rate",
                ):
                    name = f"{control}_{metric}"
                    values = [r[name] for r in selected if r.get(name) is not None]
                    if values:
                        summary[f"{name}_mean"] = float(np.mean(values))
                        summary[f"{name}_ci95"] = (
                            wilson(int(np.sum(values)), len(values))
                            if metric
                            in (
                                "record_fpr",
                                "detection_probability",
                                "missed_detection",
                                "early_trigger",
                            )
                            else bootstrap(values)
                        )
            summaries.append(summary)
    write_csv(run / "condition_summary.csv", summaries)
    write_json(run / "condition_summary.json", summaries)
    grid_rows = [
        r
        for p in sorted((run / "grid").glob("*/metrics.json"))
        for r in json.loads(p.read_text(encoding="utf-8"))
    ]
    bias_groups: dict[tuple[Any, ...], list[Any]] = defaultdict(list)
    for r in grid_rows:
        bias_groups[tuple(r[k] for k in ("fs_hz", "band", "kind", "voices", "method"))].append(r)
    scale_rows = []
    for key, records in bias_groups.items():
        row = dict(zip(("fs_hz", "band", "kind", "voices", "method"), key, strict=True))
        row.update(
            waveforms=len(records),
            rmse_hz=float(np.sqrt(np.mean([r["rmse_hz"] ** 2 for r in records]))),
            mae_hz=float(np.mean([r["mae_hz"] for r in records])),
            bias_hz=float(np.mean([r["bias_hz"] for r in records])),
            jump_rate=float(np.mean([r["jump_over_500mhz_rate"] for r in records])),
        )
        scale_rows.append(row)
    write_csv(run / "scale_bias_analysis.csv", scale_rows)
    amplitudes = []
    for path in sorted((run / "grid").glob("*/metrics.json")):
        records = json.loads(path.read_text(encoding="utf-8"))
        if records[0]["kind"] != "clean":
            continue
        with np.load(path.parent / "common.npz") as saved:
            mask = saved["interior"]
            for record in records:
                amplitudes.append(
                    dict(
                        case=record["case"],
                        fs_hz=record["fs_hz"],
                        frequency_hz=record["frequency_hz"],
                        voices=record["voices"],
                        method=record["method"],
                        mean_peak_response=float(np.mean(saved[f"{record['method']}_peak"][mask])),
                        input_amplitude_v=1.0,
                    )
                )
    write_csv(run / "scale_amplitude_response.csv", amplitudes)
    frozen = json.loads(
        (run / "candidate_frozen_before_evaluation.json").read_text(encoding="utf-8")
    )
    chosen = frozen["chosen"]
    domains = {}
    for domain in ("low_white_weak", "fast20_white"):
        selected = [
            s
            for s in summaries
            if s["method"] == chosen
            and s["noise"] == "white"
            and (
                (
                    domain == "low_white_weak"
                    and s["group"] == "core"
                    and s["band"] == "low"
                    and s["snr_db"] == -10
                    and s["scope"] == "interior"
                )
                or (
                    domain == "fast20_white"
                    and s["group"] == "chirp"
                    and s["duration_ns"] == 20
                    and s["scope"] == "event"
                )
            )
        ]
        domains[domain] = dict(
            rows=selected,
            pass_both_rates=len(selected) == 2
            and all(
                s["GO_delta_ci975_hz"][1] < 0
                and s["GO_bias_pass"]
                and s["GO_catastrophe_pass"]
                and s["GO_absolute_cap_pass"]
                for s in selected
            ),
        )
    with (run / "time_memory_comparison.csv").open(encoding="utf-8", newline="") as handle:
        perf = list(csv.DictReader(handle))
    costs = []
    for fs in (40e9, 80e9):
        a = next(
            r
            for r in perf
            if r.get("method") == chosen and float(r["fs_hz"]) == fs and int(r["voices"]) == 24
        )
        b = next(r for r in perf if r.get("method") == "balanced" and float(r["fs_hz"]) == fs)
        costs.append(
            dict(
                fs_hz=fs,
                cost_ratio=float(a["total_s"]) / float(b["total_s"]),
                peak_bytes=int(a["peak_memory_bytes"]),
            )
        )
    cost_ok = all(c["cost_ratio"] <= 50 and c["peak_bytes"] <= 2 * 1024**3 for c in costs)
    any_GO = any(d["pass_both_rates"] for d in domains.values())
    # NICHE needs a reproducible paired improvement, even when a full GO domain fails.
    niche = any(
        s.get("paired_delta_B_ci95_hz", [0, 0])[1] < 0
        for s in summaries
        if s["method"] in ("A0", "A1", "A2") and s["group"] in ("core", "chirp")
    )
    verdict = (
        "GO_FOR_OPTIONAL_ENGINEERING"
        if any_GO and cost_ok
        else ("NICHE_ONLY" if niche else "NOT_SUPPORTED")
    )
    decision = dict(
        scientific_verdict=verdict,
        frozen_candidate=chosen,
        domains=domains,
        engineering_cost_pass=cost_ok,
        costs=costs,
        uncertainty="independent waveform paired bootstrap; no pointwise replication",
    )
    write_json(run / "scientific_decision.json", decision)
    lines = [
        "# TASK005 decision matrix",
        "",
        f"Scientific verdict: {verdict}; frozen candidate {chosen}.",
        "",
        "| Domain | Both rates satisfy preregistered GO |",
        "| --- | --- |",
    ]
    lines += [f"| {name} | {d['pass_both_rates']} |" for name, d in domains.items()]
    lines += [
        "",
        f"Cost gate: {cost_ok}; costs={costs}",
        "",
        "Real data: no physical ground truth; A2 exploratory, not calibrated measurement.",
    ]
    with output(run / "decision_matrix.md").open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    failures = [
        r
        for r in rows
        if r["method"] in ("A0", "A1", "A2")
        and r["scope"] == "interior"
        and ((r.get("catastrophic_rate") or 0) > 0 or (r.get("wrong_branch_rate") or 0) > 0.5)
    ]
    write_csv(run / "failure_cases.csv", failures)
    with output(run / "failure_cases.md").open("x", encoding="utf-8") as handle:
        handle.write(
            f"# Preserved negative cases\n\n{len(failures)} method/waveform failures; "
            "complete rows in failure_cases.csv, recipes/predictions in evaluation/.\n"
        )
    return decision


if __name__ == "__main__":
    print(json.dumps(summarize(Path(sys.argv[1])), ensure_ascii=False))
