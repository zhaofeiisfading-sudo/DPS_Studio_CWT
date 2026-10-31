"""Post-freeze independent arithmetic audit. No tuning and no result mutation."""

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from pdv_cwt.frequency import strongest_candidate
from pdv_cwt.mapping import load_config
from pdv_cwt.readers import read_channel
from pdv_cwt.safety import ROOT, sha256

from .cases import make_case
from .io import array_hash, raw_inventory, write_json
from .run import profile_key
from .scoring import cwt, score_response


def audit(run: Path) -> dict[str, Any]:
    source = json.loads((run / "source_environment.json").read_text(encoding="utf-8"))
    changed = [
        name for name, digest in source["source_sha256"].items() if sha256(ROOT / name) != digest
    ]
    checks, points = 0, 0
    for split in ("development", "evaluation", "grid"):
        for path in sorted((run / split).glob("*/metrics.json")):
            rows = json.loads(path.read_text(encoding="utf-8"))
            recipe = json.loads((path.parent / "recipe.json").read_text(encoding="utf-8"))
            if split == "grid" and recipe["kind"] != "noisy":
                clean_case = make_case(recipe)
                # SNR=1000 is the finite JSON marker; voltage rounds exactly to the
                # noiseless float64 analytic cosine, rather than merely close to it.
                np.testing.assert_array_equal(clean_case.signal.voltage_v, np.cos(clean_case.phase))
            with np.load(path.parent / "common.npz") as saved:
                centers = saved["sample_index"]
                for row in rows:
                    method = row["method"]
                    mask = saved["interior"] & saved["active"]
                    method_centers = centers
                    positions = np.arange(centers.size)
                    if method.endswith("physical") or method.startswith("physical_"):
                        method_centers = saved[f"{method}_sample_index"]
                        positions = np.searchsorted(centers, method_centers)
                        np.testing.assert_array_equal(centers[positions], method_centers)
                        mask = mask[positions]
                    if row["scope"] == "event":
                        t = saved["time_s"][positions]
                        if row["group"] == "chirp":
                            width = row["duration_ns"] * 1e-9
                            mask &= (t >= 200e-9 - width / 2) & (t < 200e-9 + width / 2)
                        else:
                            mask &= (t >= 180e-9) & (t < 220e-9)
                    error = saved[f"{method}_prediction"][mask] - saved["truth_hz"][positions][mask]
                    if error.size:
                        for name, value in (
                            ("rmse_hz", np.sqrt(np.mean(error**2))),
                            ("mae_hz", np.mean(np.abs(error))),
                            ("bias_hz", np.mean(error)),
                        ):
                            np.testing.assert_allclose(row[name], value, rtol=1e-12, atol=1e-6)
                        points += error.size
                    else:
                        assert row["rmse_hz"] is None
                    assert row["truth_points"] == int(mask.sum())
                    checks += 1
                # Regeneration verifies the saved input provenance, not historical prose.
                if recipe["split"] == "evaluation" and recipe["seed"] % 100 == 0:
                    case = make_case(recipe)
                    assert array_hash(case.signal.voltage_v) == recipe["voltage_sha256"]
                    np.testing.assert_array_equal(case.signal.time_s[centers], saved["time_s"])
    profiles = json.loads((run / "calibration/score_profiles.json").read_text(encoding="utf-8"))
    registry = json.loads((run / "split_registry.json").read_text(encoding="utf-8"))
    # Recompute the first waveform of each main counterexample group, at full native density.
    probes = []
    for group, band, snr in (
        ("core", "high", -10),
        ("core", "low", -10),
        ("branches", "mid", 20),
        ("chirp", "sweep", 20),
    ):
        recipe = next(
            s
            for s in registry["evaluation"]
            if s["group"] == group and s["band"] == band and s["snr"] == snr
        )
        case = make_case(recipe)
        result, _ = cwt(case.signal)
        with np.load(run / "evaluation" / f"{recipe['id']}_v24/common.npz") as saved:
            centers = saved["sample_index"]
            raw = np.abs(result.coefficients)
            rms = np.asarray(profiles[profile_key(recipe["fs"], recipe["model"])])
            for mode in ("A0", "A1", "A2"):
                response = score_response(raw, result.grid.scales, mode, rms)
                expected = result.grid.frequency_hz[np.argmax(response, axis=0)]
                np.testing.assert_array_equal(expected[centers], saved[f"{mode}_prediction"])
            np.testing.assert_array_equal(
                strongest_candidate(result).frequency_hz[centers], saved["A0_prediction"]
            )
        probes.append(recipe["id"])
    config = load_config(ROOT / "configs/real_batch.toml")
    real_points = 0
    for entry in json.loads((run / "real_channel_index.json").read_text(encoding="utf-8")):
        mapping = config.mappings[entry["file"]]
        channel = next(c for c in mapping.channels if c.name == entry["channel"])
        path = config.raw_root / mapping.path
        signal = read_channel(
            path,
            mapping,
            channel,
            rows=entry["samples"],
            expected_sha256=entry["raw_sha256_before"],
            max_reader_bytes=config.max_reader_bytes,
        )
        with np.load(run / entry["directory"] / "native.npz") as saved:
            np.testing.assert_array_equal(saved["time_s"], signal.time_s)
            for mode in ("A0", "A1", "A2"):
                assert saved[f"{mode}_frequency_hz"].size == signal.time_s.size
                assert np.isfinite(saved[f"{mode}_frequency_hz"]).all()
        real_points += signal.time_s.size
    before = json.loads((run / "raw_before.json").read_text(encoding="utf-8"))
    report = dict(
        status="PASS",
        metric_rows_recomputed=checks,
        frequency_error_points=points,
        native_real_time_points=real_points,
        real_channels=14,
        fresh_transform_probes=probes,
        source_changed=changed,
        raw_unchanged=raw_inventory() == before,
        scope="arithmetic, provenance, unchanged raw/default; not real physical truth",
    )
    assert not changed and report["raw_unchanged"]
    write_json(run / "independent_audit.json", report)
    return report


if __name__ == "__main__":
    print(json.dumps(audit(Path(sys.argv[1])), ensure_ascii=False))
