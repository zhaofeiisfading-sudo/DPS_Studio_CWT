"""Fresh-process full 80k transform. Never reduces the requested sample rate/band."""

import hashlib
import json
import sys
import time
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from pdv_cwt import CWTConfig, compute_cwt, diagnose, strongest_candidate, synthetic_pdv

from .system_info import memory_snapshot


def performance_run(output: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    if not output.resolve().is_relative_to(root / "artifacts" / "TASK-CWT-002"):
        raise ValueError("performance outputs must stay under artifacts/TASK-CWT-002")
    with (root / "configs/cwt_v1.toml").open("rb") as handle:
        config_values = tomllib.load(handle)
    config_values.pop("normalization")
    config = CWTConfig(**config_values)
    case = synthetic_pdv(samples=80000, sampling_rate_hz=40e9, frequency_start_hz=1e9, seed=202)
    np.savez_compressed(
        output.parent / "signals/performance_80000.npz",
        time_s=case.signal.time_s,
        voltage_v=case.signal.voltage_v,
        true_frequency_hz=case.true_frequency_hz,
        active=case.active,
        phase_rad=case.phase_rad,
    )
    before = memory_snapshot()
    available = before["available_physical_bytes"]
    record: dict[str, Any] = {
        "samples": 80000,
        "sampling_rate_hz": 40e9,
        "frequency_band_hz": [0.1e9, 6e9],
        "normalizations": ["raw", "scale_amplitude"],
        "before": before,
        "status": "IN PROGRESS",
        "chunking": False,
        "recipe": case.recipe,
        "voltage_sha256": hashlib.sha256(case.signal.voltage_v.astype("<f8").tobytes()).hexdigest(),
        "time_sha256": hashlib.sha256(case.signal.time_s.astype("<f8").tobytes()).hexdigest(),
        "notes": "Native OS lifetime peak includes imports; no tracemalloc substitution.",
    }
    start = time.perf_counter()
    try:
        result = compute_cwt(
            case.signal,
            config,
            available_memory_bytes=(available if isinstance(available, int) else None),
        )
        record["transform_elapsed_s"] = time.perf_counter() - start
        for mode in ("raw", "scale_amplitude"):
            candidate = strongest_candidate(result, normalization=mode)
            quality = diagnose(result, candidate, noise_sigma_v=0)
            record[f"{mode}_finite_candidate_count"] = int(candidate.frequency_hz.size)
            record[f"{mode}_quality_pass_count"] = int(quality.passed.sum())
        record["total_transform_extract_diagnose_elapsed_s"] = time.perf_counter() - start
        record["memory_estimate"] = asdict(result.memory)
        record["coefficient_shape"] = list(result.coefficients.shape)
        record["coefficient_dtype"] = str(result.coefficients.dtype)
        record["status"] = "COMPLETED"
    except MemoryError as exc:
        record["status"] = "LIMITED_RESOURCE"
        record["reason"] = str(exc)
    record["after"] = memory_snapshot()
    output.write_text(json.dumps(record, indent=2, allow_nan=False), encoding="utf8")
    return record


if __name__ == "__main__":
    print(json.dumps(performance_run(Path(sys.argv[1])), indent=2))
