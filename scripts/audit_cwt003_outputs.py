"""Independently check every exported row and its agreement with saved CWT display columns."""

import csv
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pdv_cwt.export import write_json
from pdv_cwt.mapping import ChannelMapping, FileMapping
from pdv_cwt.readers import read_channel
from pdv_cwt.safety import ROOT, checked_path, sha256


def audit_outputs(run: Path) -> dict[str, Any]:
    run = checked_path(run, ROOT / "artifacts/TASK-CWT-003")
    manifest = json.loads((run / "batch_manifest.json").read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for status in manifest["channels"]:
        if not status["cwt_success"]:
            records.append(
                {
                    "file": status["file"],
                    "channel": status["channel"],
                    "status": "NOT_AUDITED_FAILED_CWT",
                }
            )
            continue
        output = checked_path(ROOT / status["output_path"], run)
        metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
        source = Path(metadata["source_path"])
        mapping_values = metadata["mapping"]
        mapping_values["channels"] = tuple(ChannelMapping(**c) for c in mapping_values["channels"])
        mapping = FileMapping(**mapping_values)
        channel = ChannelMapping(**metadata["channel_mapping"])
        signal = read_channel(
            source,
            mapping,
            channel,
            rows=status["samples"],
            expected_sha256=metadata["source_sha256"],
            max_reader_bytes=256 * 1024**2,
        )
        with np.load(output / "display_response.npz") as display:
            shown_indices = display["source_sample_indices"]
            shown_response = display["raw_response_v"]
            shown_time = display["time_s"]
            frequency = display["frequency_hz"]
        shown_lookup = {int(index): col for col, index in enumerate(shown_indices)}
        count = 0
        raw_candidates: list[float] = []
        np.testing.assert_array_equal(shown_time, signal.time_s[shown_indices])
        with (output / "candidate_velocity.csv").open(newline="", encoding="utf-8") as handle:
            for count, row in enumerate(csv.DictReader(handle), 1):
                i = count - 1
                index = int(row["scale_index"])
                assert float(row["time_s"]) == signal.time_s[i]
                assert float(row["selected_scale"]) == metadata["scales"][index]
                assert float(row["candidate_frequency_hz"]) == frequency[index]
                raw_candidates.append(float(row["candidate_frequency_hz"]))
                bank_edge = min(i, signal.time_s.size - 1 - i) < max(
                    metadata["support_radius_samples"]
                )
                selected_edge = (
                    min(i, signal.time_s.size - 1 - i) < metadata["support_radius_samples"][index]
                )
                assert bool(int(row["bank_edge_risk"])) == bank_edge
                assert bool(int(row["candidate_edge_risk"])) == selected_edge
                assert row["quality_result"] == "UNKNOWN"
                assert row["quality_evaluation_status"] == "NOT_EVALUATED"
                assert row["noise_model_status"] == "UNKNOWN"
                assert row["apparent_velocity_m_s"] == ""
                assert row["raw_noise_threshold_v"] == ""
                assert row["aliasing_risk"] == "0"
                if i in shown_lookup:
                    column = shown_lookup[i]
                    assert index == int(np.argmax(shown_response[:, column]))
                    assert float(row["peak_raw_response_v"]) == shown_response[index, column]
        assert count == status["samples"] == metadata["csv_rows"]
        assert sha256(source) == metadata["source_sha256"]
        records.append(
            {
                "file": status["file"],
                "channel": status["channel"],
                "status": "PASS",
                "rows_checked": count,
                "display_cwt_columns_checked": int(shown_indices.size),
                "source_time_exact_match": True,
                "sha256_unchanged": True,
                "full_candidate_frequency_sha256": __import__("hashlib")
                .sha256(np.array(raw_candidates, dtype="<f8").tobytes())
                .hexdigest(),
            }
        )
    passed = all(r["status"] == "PASS" for r in records)
    result = {
        "status": "PASS" if passed else "LIMITED",
        "channels": records,
        "total_csv_rows_checked": sum(r.get("rows_checked", 0) for r in records),
        "scope": "all times, scales, frequencies, flags, missing optics/noise; "
        "display-column strongest vs actual saved CWT; no real ground truth",
    }
    write_json(run / "output_audit.json", result)
    channels = [s for s in manifest["channels"] if s["cwt_success"]]
    fig, axes = plt.subplots(
        (len(channels) + 1) // 2,
        2,
        figsize=(18, 3.8 * ((len(channels) + 1) // 2)),
        layout="constrained",
    )
    for ax, status in zip(axes.flat, channels, strict=False):
        output = ROOT / status["output_path"]
        ax.imshow(plt.imread(output / "cwt_scalogram.png"))
        ax.axis("off")
    for ax in list(axes.flat)[len(channels) :]:
        ax.axis("off")
    fig.savefig(run / "all_scalograms_overview.png", dpi=150)
    plt.close(fig)
    return result


if __name__ == "__main__":
    print(json.dumps(audit_outputs(Path(sys.argv[1])), indent=2))
