"""Exploratory waveform-paired response contrasts, separate from the frozen GO tests."""

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from .io import write_csv
from .summarize import bootstrap


def contrasts(run: Path) -> list[dict[str, Any]]:
    rows = [
        r
        for path in (run / "evaluation").glob("*/metrics.json")
        for r in json.loads(path.read_text(encoding="utf-8"))
        if r["group"] == "core" and r["snr_db"] == -10 and r["scope"] == "interior"
    ]
    results = []
    for fs in (40e9, 80e9):
        for model in ("white", "colored"):
            for band in ("low", "mid", "high"):
                selected = [
                    r
                    for r in rows
                    if r["fs_hz"] == fs and r["noise"] == model and r["band"] == band
                ]
                raw = {r["case"]: r for r in selected if r["method"] == "A0"}
                for mode in ("A1", "A2"):
                    values = [
                        r["rmse_hz"] - raw[r["case"]]["rmse_hz"]
                        for r in selected
                        if r["method"] == mode
                    ]
                    assert len(values) == 20
                    results.append(
                        dict(
                            fs_hz=fs,
                            noise=model,
                            band=band,
                            mode=mode,
                            n=20,
                            delta_A0_mean_hz=float(np.mean(values)),
                            delta_A0_ci95_hz=bootstrap(values),
                            status="exploratory; pointwise CI; not a new GO domain",
                        )
                    )
    write_csv(run / "response_pairwise_comparison.csv", results)
    return results


if __name__ == "__main__":
    print(json.dumps(contrasts(Path(sys.argv[1]))))
