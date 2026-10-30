"""Full recursive audit and isolated sequential CWT workers; no silent file exclusions."""

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .export import write_json, write_table
from .mapping import BatchConfig, load_config
from .readers import audit_file
from .safety import ROOT, checked_path, scan_files, sha256


def input_inventory(config: BatchConfig) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in scan_files(config.raw_root):
        relative = path.relative_to(config.raw_root).as_posix()
        mapping = config.mappings.get(relative)
        record = audit_file(path, mapping, config.max_input_bytes)
        record.update(
            file=relative,
            filename=path.name,
            identifiable_channels=len(mapping.channels) if mapping else 0,
        )
        records.append(record)
    return records


def _worker(
    config: BatchConfig,
    record: dict[str, Any],
    channel_name: str,
    run: Path,
) -> dict[str, Any]:
    relative = record["file"]
    identity = sha256(config.raw_root / relative)[:12]
    # Path digest, not basename, keeps duplicate names in different folders separate.
    import hashlib

    path_digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12]
    parent = run / "channels" / f"file_{path_digest}_{identity}"
    parent.mkdir(parents=True, exist_ok=True)
    output = parent / channel_name
    request_path = parent / f"{channel_name}_request.json"
    write_json(
        request_path,
        {
            "source": str(config.raw_root / relative),
            "mapping": asdict(config.mappings[relative]),
            "channel": channel_name,
            "cwt": asdict(config.cwt),
            "audit": record,
            "output": str(output),
            "max_reader_bytes": config.max_reader_bytes,
            "display_max_columns": config.display_max_columns,
        },
    )
    start = time.perf_counter()
    failure = ""
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pdv_cwt.pipeline", str(request_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=config.worker_timeout_s,
            check=False,
        )
        (parent / f"{channel_name}_stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (parent / f"{channel_name}_stderr.txt").write_text(completed.stderr, encoding="utf-8")
        status_path = output / "analysis_status.json"
        if status_path.exists() and completed.returncode == 0:
            status: dict[str, Any] = json.loads(status_path.read_text(encoding="utf-8"))
            status["worker_wall_elapsed_s"] = time.perf_counter() - start
            return status
        failure = f"Worker exit={completed.returncode}; inspect stderr; status absent or invalid"
    except subprocess.TimeoutExpired:
        failure = f"FAILED_RESOURCE: worker timeout {config.worker_timeout_s} s; worker terminated"
    except (OSError, ValueError) as exc:
        failure = f"Worker launch/read failure: {type(exc).__name__}: {exc}"
    return {
        "file": relative,
        "channel": channel_name,
        "status": "FAILED_RESOURCE" if "FAILED_RESOURCE" in failure else "FAILED",
        "reason": failure,
        "cwt_success": (output / "cwt_scalogram.png").exists(),
        "candidate_success": False,
        "velocity_success": False,
        "output_path": str(output.relative_to(ROOT)),
        "elapsed_s": time.perf_counter() - start,
    }


def run_batch(config: BatchConfig, *, audit_only: bool = False) -> Path:
    started = time.perf_counter()
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S_") + uuid4().hex[:8]
    run = checked_path(config.output_root / run_id, ROOT)
    run.mkdir(parents=True, exist_ok=False)
    inventory = input_inventory(config)
    write_json(run / "input_inventory_before.json", inventory)
    write_table(run / "input_inventory.csv", inventory)
    config_hash = sha256(config.config_path)
    # Source snapshots are text/code only. Raw waveform bytes are never copied.
    snapshot_root = run / "source_snapshot"
    for source in [config.config_path, *sorted((ROOT / "src/pdv_cwt").glob("*.py"))]:
        snapshot = snapshot_root / source.relative_to(ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(source.read_bytes())
    statuses: list[dict[str, Any]] = []
    if not audit_only:
        for record in inventory:
            mapping = config.mappings.get(record["file"])
            if record["status"] != "READY" or mapping is None:
                continue
            for channel in mapping.channels:
                print(f"CWT {record['file']} / {channel.name}", flush=True)
                try:
                    status = _worker(config, record, channel.name, run)
                except Exception as exc:
                    status = dict(
                        file=record["file"],
                        channel=channel.name,
                        status="FAILED",
                        cwt_success=False,
                        candidate_success=False,
                        velocity_success=False,
                        reason=f"{type(exc).__name__}: {exc}",
                        traceback=traceback.format_exc(),
                    )
                statuses.append(status)
                print(f"  {status['status']}: {status.get('reason', '')}", flush=True)
                write_json(run / f"progress_{len(statuses):03d}.json", status)
    after_paths = scan_files(config.raw_root)
    after_hashes = {
        path.relative_to(config.raw_root).as_posix(): sha256(path) for path in after_paths
    }
    before_hashes = {r["file"]: r["sha256_before"] for r in inventory}
    unchanged = before_hashes == after_hashes
    for record in inventory:
        channels = [s for s in statuses if s["file"] == record["file"]]
        record["sha256_after"] = after_hashes.get(record["file"])
        record["sha256_unchanged"] = record["sha256_before"] == record["sha256_after"]
        record["channels_attempted"] = len(channels)
        record["scalograms_success"] = sum(bool(s["cwt_success"]) for s in channels)
        record["scalograms_failed"] = len(channels) - record["scalograms_success"]
        if channels:
            record["status"] = "ANALYZED" if all(s["cwt_success"] for s in channels) else "FAILED"
            record["channel_statuses"] = {s["channel"]: s["status"] for s in channels}
            record["reason"] = "; ".join(s["reason"] for s in channels if not s["cwt_success"])
    ready_channels = sum(r["identifiable_channels"] for r in inventory if r["is_raw"] is True)
    counts = {
        "files_scanned": len(inventory),
        "raw_waveform_files": sum(r["is_raw"] is True for r in inventory),
        "not_raw_files": sum(r["is_raw"] is False for r in inventory),
        "unclassified_files": sum(r["is_raw"] is None for r in inventory),
        "files_with_scalograms": sum(r["scalograms_success"] > 0 for r in inventory),
        "identifiable_channels": ready_channels,
        "channels_attempted": len(statuses),
        "cwt_scalograms_success": sum(bool(s["cwt_success"]) for s in statuses),
        "cwt_scalograms_failed": sum(not s["cwt_success"] for s in statuses),
        "velocity_backend_success": sum(bool(s["velocity_success"]) for s in statuses),
        "scalogram_only_channels": sum(s["status"] == "SCALOGRAM_ONLY" for s in statuses),
        "candidate_csv_success": sum(bool(s["candidate_success"]) for s in statuses),
        "unattempted_identifiable_channels": ready_channels - len(statuses),
    }
    write_json(run / "input_inventory.json", inventory)
    write_json(run / "raw_hashes_after.json", after_hashes)
    write_table(run / "file_summary.csv", inventory)
    write_table(run / "batch_summary.csv", statuses)
    versions = {
        name: importlib.metadata.version(name)
        for name in ("numpy", "scipy", "PyWavelets", "matplotlib", "pytest", "ruff", "mypy")
    }
    manifest: dict[str, Any] = {
        "task": "TASK-CWT-003",
        "run_id": run_id,
        "audit_only": audit_only,
        "counts": counts,
        "elapsed_s": time.perf_counter() - started,
        "raw_sha256_unchanged": unchanged,
        "raw_file_set_unchanged": set(before_hashes) == set(after_hashes),
        "config_path": str(config.config_path),
        "config_sha256": config_hash,
        "config_unchanged": sha256(config.config_path) == config_hash,
        "cwt": asdict(config.cwt),
        "versions": versions,
        "python": sys.version,
        "hardware": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
        },
        "source_sha256": {
            str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "src/pdv_cwt").glob("*.py"))
        },
        "channels": statuses,
        "files": inventory,
        "missing_configured_files": sorted(set(config.mappings) - set(before_hashes)),
        "scope": "CWT only; real truth unavailable; no STFT/GUI/optical corrections",
        "level_a": "PASS"
        if unchanged
        and counts["unattempted_identifiable_channels"] == 0
        and counts["unclassified_files"] == 0
        else "LIMITED",
        "level_b": "PASS"
        if counts["cwt_scalograms_success"] == ready_channels and ready_channels > 0 and unchanged
        else "LIMITED",
        "level_c": "LIMITED: missing explicit optics"
        if counts["velocity_backend_success"] < ready_channels
        else "PASS",
    }
    write_json(run / "batch_manifest.json", manifest)
    lines = [
        "# TASK-CWT-003 batch status",
        "",
        f"Run: {run_id}",
        f"Raw SHA-256 unchanged: {unchanged}",
        f"Audit only: {audit_only}",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in counts.items())
    lines.extend(["", "File statuses (file denominator)", ""])
    lines.extend(
        f"- {r['file']}: {r['status']}; CWT {r['scalograms_success']}/"
        f"{r['identifiable_channels']}; {r['reason']}"
        for r in inventory
    )
    lines.extend(["", "Channel statuses (channel denominator)", ""])
    lines.extend(f"- {s['file']} / {s['channel']}: {s['status']}; {s['reason']}" for s in statuses)
    (run / "batch_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    print(run_batch(load_config(args.config), audit_only=args.audit_only), flush=True)


if __name__ == "__main__":
    main()
