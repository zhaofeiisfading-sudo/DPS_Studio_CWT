"""Exclusive evidence writes inside TASK005, without copying raw samples."""

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from benchmarks.comparison.storage import array_hash, clean, raw_inventory
from pdv_cwt.safety import ROOT, checked_path

BASE = ROOT / "artifacts/TASK-CWT-005"
__all__ = ["BASE", "array_hash", "raw_inventory", "write_json", "write_csv", "output"]


def output(path: Path) -> Path:
    path = checked_path(path, ROOT)
    if not (path.is_relative_to(BASE) or path.is_relative_to(ROOT / ".local_cache")):
        raise ValueError("output outside TASK005 artifacts/cache")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, value: Any) -> None:
    with output(path).open("x", encoding="utf-8") as handle:
        json.dump(clean(value), handle, ensure_ascii=False, indent=2, allow_nan=False)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with output(path).open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: json.dumps(clean(v))
                    if isinstance(v, (dict, list, tuple, np.ndarray))
                    else clean(v)
                    for k, v in row.items()
                }
            )
