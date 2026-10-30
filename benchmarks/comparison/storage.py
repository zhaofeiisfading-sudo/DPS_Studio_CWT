"""Repository-bounded, exclusive-create evidence writers and isolated workers."""

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from pdv_cwt.mapping import ChannelMapping, FileMapping
from pdv_cwt.models import FloatArray
from pdv_cwt.readers import read_channel
from pdv_cwt.safety import ROOT, checked_path, scan_files, sha256
from pdv_cwt.synthetic import synthetic_pdv

from .core import Analysis, analyze


def output_path(path: Path) -> Path:
    path = checked_path(path, ROOT)
    if not (
        path.is_relative_to(ROOT / "artifacts/TASK-CWT-004")
        or path.is_relative_to(ROOT / ".local_cache")
    ):
        raise ValueError("output outside TASK004 artifacts/cache")
    return path


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path: Path, values: Any) -> None:
    with output_path(path).open("x", encoding="utf-8") as handle:
        json.dump(clean(values), handle, indent=2, ensure_ascii=False, allow_nan=False)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with output_path(path).open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: json.dumps(clean(v), ensure_ascii=False) if isinstance(v, dict) else clean(v)
                    for k, v in row.items()
                }
            )


def array_hash(value: FloatArray) -> str:
    return hashlib.sha256(value.astype("<f8").tobytes()).hexdigest()


def raw_inventory() -> list[dict[str, Any]]:
    return [
        dict(
            path=p.relative_to(ROOT / "raw_data").as_posix(),
            size_bytes=p.stat().st_size,
            sha256=sha256(p),
        )
        for p in scan_files(ROOT / "raw_data")
    ]


def save_analysis(
    output: Path, analysis: Analysis, *, native_csv: bool = True, max_display: int = 2400
) -> None:
    output = output_path(output)
    output.mkdir(parents=True, exist_ok=False)
    start = perf_counter()
    np.savez_compressed(output / "native.npz", **analysis.native)
    count = analysis.response.shape[1]
    display = np.unique(np.linspace(0, count - 1, min(count, max_display), dtype=np.int64))
    vmax = float(np.max(analysis.response))
    np.savez_compressed(
        output / "display.npz",
        position=display,
        sample_index=analysis.native["sample_index"][display],
        time_s=analysis.native["time_s"][display],
        frequency_hz=analysis.frequency_hz,
        response=analysis.response[:, display],
        bank_edge=analysis.native["bank_edge"][display],
    )
    analysis.metadata["display"] = dict(
        rule="<=2400 actual columns, evenly selected incl endpoints; no averaging/interpolation",
        columns=int(display.size),
        vmin=0.0,
        vmax=vmax,
        near_black_fraction_below_1pct_full_max=float(np.mean(analysis.response < 0.01 * vmax)),
        noise_reference="NOT AVAILABLE for real data",
        frequency_limits_hz=[0.1e9, 6e9],
        time_origin_s=float(analysis.native["time_s"][0]),
    )
    if native_csv:
        keys = list(analysis.native)
        with (output / "native.csv").open("x", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([*keys, "quality"])
            for values in zip(*(analysis.native[k] for k in keys), strict=True):
                writer.writerow([*values, "UNKNOWN"])
    analysis.metadata["export_s"] = perf_counter() - start
    write_json(output / "metadata.json", analysis.metadata)


def load_analysis(path: Path) -> Analysis:
    with np.load(path / "native.npz") as saved:
        native = {k: saved[k] for k in saved.files}
    with np.load(path / "display.npz") as saved:
        score, frequency = saved["response"], saved["frequency_hz"]
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    # Only display matrix is loaded; full native vectors remain complete.
    return Analysis(native, frequency, score, metadata)


def run_isolated(request_path: Path, timeout_s: int = 900) -> dict[str, Any]:
    request_path = output_path(request_path)
    start = perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "benchmarks.comparison.worker", str(request_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        with request_path.with_suffix(".stdout.txt").open("x", encoding="utf-8") as handle:
            handle.write(result.stdout)
        with request_path.with_suffix(".stderr.txt").open("x", encoding="utf-8") as handle:
            handle.write(result.stderr)
        if result.returncode:
            raise RuntimeError(f"worker exit {result.returncode}; see stderr")
        record: dict[str, Any] = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError, OSError) as exc:
        record = dict(status="FAILED", error=f"{type(exc).__name__}: {exc}")
    record["worker_wall_s"] = perf_counter() - start
    write_json(request_path.with_suffix(".status.json"), record)
    return record


def worker(request_path: Path) -> dict[str, Any]:
    request = json.loads(output_path(request_path).read_text(encoding="utf-8"))
    method = request["method"]
    before_read = perf_counter()
    if request["kind"] == "real":
        source = checked_path(ROOT / "raw_data" / request["mapping"]["path"], ROOT / "raw_data")
        mapping_values = dict(request["mapping"])
        mapping_values["channels"] = tuple(ChannelMapping(**c) for c in mapping_values["channels"])
        mapping = FileMapping(**mapping_values)
        channel = next(c for c in mapping.channels if c.name == request["channel"])
        signal = read_channel(
            source,
            mapping,
            channel,
            rows=request["rows"],
            expected_sha256=request["sha256"],
            max_reader_bytes=256 * 1024**2,
        )
    else:
        base = synthetic_pdv(
            samples=request["samples"],
            sampling_rate_hz=request["fs_hz"],
            frequency_start_hz=1e9,
            seed=20001,
        )
        signal = base.signal
        source = None
    read_s = perf_counter() - before_read
    analysis = analyze(signal, method)
    analysis.metadata.update(
        time_sha256=array_hash(signal.time_s),
        voltage_sha256=array_hash(signal.voltage_v),
        reader_s=read_s,
        performance_scope="fresh worker; peak before exports/plots",
    )
    if source is not None:
        analysis.metadata.update(
            raw_sha256_after=sha256(source), raw_sha256_before=request["sha256"]
        )
        if analysis.metadata["raw_sha256_after"] != request["sha256"]:
            raise ValueError("raw changed during analysis")
    if request.get("save", True):
        save_analysis(Path(request["output"]), analysis)
    return dict(status="COMPLETED", **analysis.metadata)
