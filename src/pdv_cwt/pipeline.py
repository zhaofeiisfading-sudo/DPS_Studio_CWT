"""One fresh-process channel: unchanged samples -> CWT -> candidate -> diagnostics."""

import json
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from .diagnostics import diagnose
from .export import candidate_csv, diagnostic_plots, scalogram, write_json
from .frequency import CWTConfig, strongest_candidate
from .mapping import ChannelMapping, FileMapping
from .physics import apparent_velocity
from .readers import read_channel
from .resources import memory_snapshot
from .safety import ROOT, checked_path, sha256
from .transform import compute_cwt


def analyze_channel(
    source: Path,
    mapping: FileMapping,
    channel: ChannelMapping,
    config: CWTConfig,
    audit: dict[str, Any],
    output: Path,
    *,
    max_reader_bytes: int = 256 * 1024**2,
    display_max_columns: int = 2400,
) -> dict[str, Any]:
    source = checked_path(source, ROOT)
    output = checked_path(output, ROOT)
    if not any(output.is_relative_to(ROOT / p) for p in ("artifacts/TASK-CWT-003", ".local_cache")):
        raise ValueError("channel output outside allowed artifact/cache boundaries")
    if display_max_columns < 2:
        raise ValueError("display_max_columns must be >= 2")
    output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    status: dict[str, Any] = {
        "file": mapping.path,
        "channel": channel.name,
        "status": "FAILED",
        "cwt_success": False,
        "candidate_success": False,
        "velocity_success": False,
        "output_path": str(output.relative_to(ROOT)),
        "reason": "",
    }
    metadata: dict[str, Any] = {
        "source_path": str(source),
        "source_sha256": audit["sha256_before"],
        "mapping": asdict(mapping),
        "channel_mapping": asdict(channel),
        "cwt_config": asdict(config),
        "normalization": "raw abs(W)",
        "method": "fft",
        "input_preprocessing": (
            "NONE; no resampling, trimming, smoothing, interpolation or deletion"
        ),
        "coefficient_storage": "full complex128 matrix in RAM; full candidates in CSV; display NPZ",
        "physical_scope": "unsigned beat-frequency candidates; real ground truth unavailable",
        "units": {"time": "s", "voltage": "V", "frequency": "Hz", "velocity": "m/s"},
        "noise_model_status": "UNKNOWN" if channel.noise_sigma_v is None else "KNOWN_IID_GAUSSIAN",
        "quality_caveat": "diagnostic only; TASK-002 pulse false positives; UNKNOWN is not FAIL",
    }
    stage = "reader"
    try:
        signal = read_channel(
            source,
            mapping,
            channel,
            rows=int(audit["data_rows"]),
            expected_sha256=audit["sha256_before"],
            max_reader_bytes=max_reader_bytes,
        )
        status.update(
            samples=int(signal.time_s.size),
            time_start_s=float(signal.time_s[0]),
            time_end_s=float(signal.time_s[-1]),
            sampling_rate_hz=signal.sampling_rate_hz,
            sampling_period_s=signal.sampling_period_s,
        )
        metadata["reader_elapsed_s"] = time.perf_counter() - start
        before = memory_snapshot()
        metadata["memory_before_cwt"] = before
        available = before["available_physical_bytes"]
        stage = "cwt"
        transform_start = time.perf_counter()
        result = compute_cwt(
            signal,
            config,
            available_memory_bytes=(available if isinstance(available, int) else None),
        )
        status["cwt_elapsed_s"] = time.perf_counter() - transform_start
        status.update(
            frequency_min_hz=float(result.grid.frequency_hz[0]),
            frequency_max_hz=float(result.grid.frequency_hz[-1]),
            scales=int(result.grid.scales.size),
            memory_estimate_bytes=result.memory.working_bytes,
        )
        metadata.update(
            scales=result.grid.scales.tolist(),
            frequency_hz=result.grid.frequency_hz.tolist(),
            alias_tail_fraction=result.grid.alias_tail_fraction.tolist(),
            support_radius_samples=result.grid.support_radius_samples.tolist(),
            boundary_policy="ceil(8*scale)+2 per edge; common bank mask retained",
            memory_estimate=asdict(result.memory),
            chunking=False,
            evaluation_mask="all samples; no quality-based removal",
        )
        stage = "scalogram"
        metadata["display"] = scalogram(
            result, output / "cwt_scalogram.png", display_max_columns,
            label=f"{mapping.path} / {channel.name}",
        )
        status.update(cwt_success=True, status="SCALOGRAM_ONLY")
        stage = "candidate_and_diagnostics"
        candidate = strongest_candidate(result)
        original_frequency = candidate.frequency_hz.copy()
        quality = diagnose(result, candidate, noise_sigma_v=channel.noise_sigma_v)
        if not np.array_equal(candidate.frequency_hz, original_frequency):
            raise RuntimeError("diagnostics changed raw candidate")
        known = channel.noise_sigma_v is not None
        velocity = None
        if channel.wavelength_m is not None and channel.zero_optical_offset is True:
            velocity = apparent_velocity(
                candidate.frequency_hz, wavelength_m=channel.wavelength_m, zero_optical_offset=True
            )
        else:
            status["reason"] = "Wavelength and/or explicit zero optical offset unavailable"
        candidate_csv(
            output / "candidate_velocity.csv",
            result,
            candidate,
            quality,
            velocity,
            noise_known=known,
        )
        diagnostic_plots(output, candidate, quality, velocity)
        status.update(
            candidate_success=True,
            velocity_success=velocity is not None,
            candidate_output_rate=float(np.mean(np.isfinite(candidate.frequency_hz))),
            quality_pass_rate=float(np.mean(quality.passed)) if known else None,
            quality_unknown_fraction=0.0 if known else 1.0,
            candidate_edge_risk_fraction=float(np.mean(quality.candidate_edge_affected)),
            bank_edge_risk_fraction=float(np.mean(quality.bank_edge_affected)),
            aliasing_risk_fraction=float(np.mean(quality.alias_risk)),
            candidate_frequency_median_hz=float(np.median(candidate.frequency_hz)),
            candidate_frequency_p05_hz=float(np.quantile(candidate.frequency_hz, 0.05)),
            candidate_frequency_p95_hz=float(np.quantile(candidate.frequency_hz, 0.95)),
            adjacent_jump_over_500mhz_fraction=float(
                np.mean(np.abs(np.diff(candidate.frequency_hz)) > 0.5e9)
            ),
        )
        metadata.update(
            noise_model=quality.noise_model,
            velocity_status="EXPORTED_UNSIGNED_APPARENT"
            if velocity is not None
            else "NOT_COMPUTED_MISSING_OPTICS",
            quality_evaluation_status="EVALUATED" if known else "NOT_EVALUATED",
            quality_result="PER_SAMPLE_DIAGNOSTIC" if known else "UNKNOWN",
            csv_rows=int(candidate.time_s.size),
            csv_missing_velocity="empty field; never zero substitution",
        )
        if velocity is not None:
            status["status"] = "ANALYZED"
    except Exception as exc:
        status["status"] = (
            "SCALOGRAM_ONLY"
            if status["cwt_success"]
            else "FAILED_RESOURCE"
            if isinstance(exc, MemoryError)
            else "FAILED"
        )
        status.update(reason=f"{stage}: {type(exc).__name__}: {exc}", failed_stage=stage)
        metadata["traceback"] = traceback.format_exc()
    finally:
        final_hash = sha256(source)
        status["raw_sha256_unchanged"] = final_hash == audit["sha256_before"]
        if not status["raw_sha256_unchanged"]:
            status.update(status="FAILED", reason="Source SHA-256 changed; outputs invalid")
        status["elapsed_s"] = time.perf_counter() - start
        metadata["memory_after"] = memory_snapshot()
        status["peak_working_set_bytes"] = metadata["memory_after"]["peak_working_set_bytes"]
        metadata.update(source_sha256_after=final_hash, status=status)
        write_json(output / "metadata.json", metadata)
        write_json(output / "analysis_status.json", status)
    return status


def run_request(path: Path) -> dict[str, Any]:
    request = json.loads(checked_path(path, ROOT).read_text(encoding="utf-8"))
    file_values = request["mapping"]
    file_values["channels"] = tuple(ChannelMapping(**c) for c in file_values["channels"])
    mapping = FileMapping(**file_values)
    channel = next(c for c in mapping.channels if c.name == request["channel"])
    return analyze_channel(
        Path(request["source"]),
        mapping,
        channel,
        CWTConfig(**request["cwt"]),
        request["audit"],
        Path(request["output"]),
        max_reader_bytes=request["max_reader_bytes"],
        display_max_columns=request["display_max_columns"],
    )


if __name__ == "__main__":
    print(json.dumps(run_request(Path(sys.argv[1])), ensure_ascii=False))
