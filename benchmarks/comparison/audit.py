"""Independent output audit, including every real STFT frame against direct FFT."""

import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from pdv_cwt.mapping import load_config
from pdv_cwt.readers import read_channel
from pdv_cwt.safety import ROOT, sha256

from .core import METHODS, STFTConfig, common_indices
from .storage import array_hash, output_path, raw_inventory, write_json


def audit(run: Path) -> dict[str, Any]:
    run = output_path(run)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    before = json.loads(
        (ROOT / "artifacts/TASK-CWT-004/preflight.json").read_text(encoding="utf-8")
    )
    assert raw_inventory() == before["raw"]
    config = load_config(ROOT / "configs/real_batch.toml")
    inventory = json.loads((run / "input_inventory.json").read_text(encoding="utf-8"))
    channels = json.loads((run / "channel_index.json").read_text(encoding="utf-8"))
    assert len(channels) == 14
    counts = dict(cwt=0, balanced=0, high_time=0)
    direct_frames = 0
    common_frames = 0
    maximum_magnitude_error = 0.0
    records = []
    for item in channels:
        assert all(item["methods"][m] == "COMPLETED" for m in METHODS), item
        assert item["paired_outputs"] == "COMPLETED", item
        assert item["prior_cwt_consistency"]["time_exact_equal"]
        assert item["prior_cwt_consistency"]["candidate_exact_equal"]
        assert item["prior_cwt_consistency"]["config_equal"]
        directory = run / item["directory"]
        mapping = config.mappings[item["file"]]
        channel = next(c for c in mapping.channels if c.name == item["channel"])
        entry = next(e for e in inventory if e["path"] == item["file"])
        signal = read_channel(
            ROOT / "raw_data" / item["file"],
            mapping,
            channel,
            rows=entry["data_rows"],
            expected_sha256=entry["sha256_before"],
            max_reader_bytes=config.max_reader_bytes,
        )
        with np.load(directory / "common_grid.npz") as loaded:
            common = {k: loaded[k] for k in loaded.files}
        centers = common_indices(signal.time_s.size)
        np.testing.assert_array_equal(common["sample_index"], centers)
        common_frames += centers.size
        edges = []
        for method in METHODS:
            sub = directory / method
            meta = json.loads((sub / "metadata.json").read_text(encoding="utf-8"))
            assert meta["time_sha256"] == array_hash(signal.time_s)
            assert meta["voltage_sha256"] == array_hash(signal.voltage_v)
            assert meta["raw_sha256_after"] == entry["sha256_before"]
            with np.load(sub / "native.npz") as loaded:
                native = {k: loaded[k] for k in loaded.files}
            indices = np.arange(signal.time_s.size) if method == "cwt" else centers
            grid = np.array(meta["frequency_hz"])
            np.testing.assert_array_equal(native["sample_index"], indices)
            np.testing.assert_array_equal(native["time_s"], signal.time_s[indices])
            np.testing.assert_array_equal(native["frequency_hz"], grid[native["frequency_index"]])
            assert np.isfinite(native["frequency_hz"]).all()
            positions = centers if method == "cwt" else np.arange(centers.size)
            for key in (
                "time_s",
                "frequency_hz",
                "peak",
                "median",
                "q90",
                "peak_to_median",
                "concentration",
                "bank_edge",
                "selected_edge",
                "alias_risk",
            ):
                np.testing.assert_array_equal(common[f"{method}_{key}"], native[key][positions])
            edges.append(native["bank_edge"][positions])
            counts[method] += indices.size
            if method == "cwt":
                distance = np.minimum(indices, signal.time_s.size - 1 - indices)
                radii = np.array(meta["support_radius_samples"])
                np.testing.assert_array_equal(native["bank_edge"], distance < radii.max())
                np.testing.assert_array_equal(
                    native["selected_edge"], distance < radii[native["frequency_index"]]
                )
            else:
                params = STFTConfig() if method == "balanced" else STFTConfig(512, 384)
                length = params.window
                window = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(length) / length)
                hz = np.fft.rfftfreq(params.nfft, signal.sampling_period_s)
                band = (hz >= params.low_hz) & (hz <= params.high_hz)
                np.testing.assert_array_equal(grid, hz[band])
                for pos, center in enumerate(centers):
                    index = center + np.arange(length) - length // 2
                    valid = (index >= 0) & (index < signal.time_s.size)
                    frame = np.zeros(length)
                    frame[valid] = signal.voltage_v[index[valid]]
                    score = (2 * np.abs(np.fft.rfft(frame * window, n=params.nfft)) / window.sum())[
                        band
                    ]
                    strongest = int(np.argmax(score))
                    assert native["frequency_index"][pos] == strongest
                    np.testing.assert_allclose(
                        native["peak"][pos], score[strongest], rtol=1e-11, atol=1e-13
                    )
                    maximum_magnitude_error = max(
                        maximum_magnitude_error, abs(float(native["peak"][pos] - score[strongest]))
                    )
                    assert native["bank_edge"][pos] == (not valid.all())
                    direct_frames += 1
            with np.load(sub / "display.npz") as d:
                positions = d["position"]
                np.testing.assert_array_equal(d["time_s"], native["time_s"][positions])
                np.testing.assert_array_equal(
                    grid[np.argmax(d["response"], axis=0)], native["frequency_hz"][positions]
                )
                np.testing.assert_allclose(
                    np.max(d["response"], axis=0), native["peak"][positions], rtol=1e-14
                )
            with (sub / "native.csv").open(encoding="utf-8", newline="") as handle:
                csv_count = 0
                for pos, row in enumerate(csv.DictReader(handle)):
                    assert row["quality"] == "UNKNOWN"
                    assert float(row["time_s"]) == native["time_s"][pos]
                    assert float(row["frequency_hz"]) == native["frequency_hz"][pos]
                    csv_count += 1
                assert csv_count == indices.size
        np.testing.assert_array_equal(common["common_interior"], ~np.logical_or.reduce(edges))
        for name in (
            "comparison_linear.png",
            "comparison_db.png",
            "candidates_native.png",
            "candidates_common.png",
            "background_diagnostics.png",
            "exploratory_roi.png",
        ):
            assert (directory / name).stat().st_size > 1000
        records.append(dict(file=item["file"], channel=item["channel"], status="PASS"))
    metrics = json.loads((run / "synthetic_metrics.json").read_text(encoding="utf-8"))
    assert len(metrics) == 156 * 3 * 4
    assert manifest["failures"] == []
    for path in sorted((run / "synthetic").iterdir()):
        with np.load(path / "signal_truth.npz") as loaded:
            t, truth = loaded["time_s"], loaded["truth_hz"]
            provenance = json.loads((path / "recipe_hashes.json").read_text(encoding="utf-8"))
            assert array_hash(loaded["voltage_v"]) == provenance["voltage_sha256"]
            assert array_hash(t) == provenance["time_sha256"]
        with np.load(path / "common_grid.npz") as loaded:
            paired = {k: loaded[k] for k in loaded.files}
        indices = paired["sample_index"]
        for method in METHODS:
            rows = [r for r in metrics if r["case"] == path.name and r["method"] == method]
            assert len(rows) == 4
            for row in rows:
                if row["scope"] != "common_interior":
                    continue
                mask = paired["common_interior"] & np.isfinite(truth[indices])
                expected = (
                    float(
                        np.sqrt(
                            np.mean(
                                (paired[f"{method}_frequency_hz"][mask] - truth[indices][mask]) ** 2
                            )
                        )
                    )
                    if mask.any()
                    else None
                )
                assert expected == row["rmse_hz"]
                assert row["truth_points"] == int(mask.sum())
                if row["group"] == "S5":
                    assert row["rmse_hz"] is None
    assert raw_inventory() == before["raw"]
    source = json.loads((run / "source_environment.json").read_text(encoding="utf-8"))
    assert all(sha256(ROOT / path) == digest for path, digest in source["source_sha256"].items())
    result = dict(
        status="PASS",
        channels=records,
        native_counts=counts,
        common_frames=common_frames,
        direct_fft_frames=direct_frames,
        maximum_stft_peak_difference_v=maximum_magnitude_error,
        synthetic_cases=156,
        metric_rows=len(metrics),
        raw_unchanged=True,
        scope="data/export/math consistency; no real physical correctness claim",
    )
    write_json(run / "independent_output_audit.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(audit(Path(sys.argv[1])), indent=2))
