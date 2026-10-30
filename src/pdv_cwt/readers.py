"""Streaming text audit and bounded readers, preserving every input data row."""

import csv
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np

from .mapping import TIME_FACTORS, VOLTAGE_FACTORS, ChannelMapping, FileMapping
from .models import SampledSignal
from .safety import sha256


def text_rows(path: Path, mapping: FileMapping | None) -> Iterator[tuple[int, list[str]]]:
    encoding = mapping.encoding if mapping else "utf-8-sig"
    delimiter = mapping.delimiter if mapping else ","
    skip = mapping.skip_rows if mapping else 0
    with path.open("r", encoding=encoding, newline="") as handle:
        for _ in range(skip):
            if handle.readline() == "":
                raise ValueError("skip_rows exceeds file length")
        if delimiter == "whitespace":
            for line, text in enumerate(handle, skip + 1):
                yield line, text.split()
        else:
            reader = csv.reader(handle, delimiter=delimiter, strict=True)
            for row in reader:
                yield skip + reader.line_num, row


def audit_file(path: Path, mapping: FileMapping | None, max_bytes: int) -> dict[str, Any]:
    record: dict[str, Any] = {
        "size_bytes": path.stat().st_size,
        "sha256_before": sha256(path),
        "extension": path.suffix.lower(),
        "status": "NEEDS_MAPPING",
        "is_raw": None,
        "format": "UNKNOWN",
        "data_rows": 0,
        "column_width_counts": {},
        "invalid_numeric_cells": 0,
        "nonfinite_cells": 0,
        "blank_rows": 0,
        "column_statistics": [],
        "reason": "No explicit mapping and units",
    }
    if path.name == ".gitkeep":
        record.update(
            status="NOT_RAW", is_raw=False, format="placeholder", reason="Git placeholder"
        )
        return record
    if "result" in path.stem.lower() and path.suffix.lower() == ".dat":
        record.update(
            status="NOT_RAW",
            is_raw=False,
            format="processed_result_DAT",
            reason="result DAT excluded by repository contract",
        )
        return record
    if path.suffix.lower() not in (".csv", ".dat", ".txt", ".tsv"):
        record.update(status="UNSUPPORTED_FORMAT", reason="No reader for this extension")
        return record
    if path.stat().st_size > max_bytes:
        record.update(status="FAILED_RESOURCE", reason="Input exceeds explicit text reader budget")
        return record
    widths: dict[str, int] = {}
    stats: list[dict[str, Any]] = []
    issues: list[str] = []
    try:
        for line, row in text_rows(path, mapping):
            record["data_rows"] += 1
            widths[str(len(row))] = widths.get(str(len(row)), 0) + 1
            if not row:
                record["blank_rows"] += 1
            while len(stats) < len(row):
                stats.append(
                    dict(
                        finite=0,
                        invalid=0,
                        nonfinite=0,
                        minimum=None,
                        maximum=None,
                        first=None,
                        last=None,
                    )
                )
            for column, token in enumerate(row):
                item = stats[column]
                try:
                    value = float(token)
                    if not math.isfinite(value):
                        record["nonfinite_cells"] += 1
                        item["nonfinite"] += 1
                    else:
                        item["finite"] += 1
                        item["first"] = value if item["first"] is None else item["first"]
                        item["last"] = value
                        item["minimum"] = (
                            value if item["minimum"] is None else min(value, item["minimum"])
                        )
                        item["maximum"] = (
                            value if item["maximum"] is None else max(value, item["maximum"])
                        )
                except ValueError:
                    record["invalid_numeric_cells"] += 1
                    item["invalid"] += 1
                    if len(issues) < 8:
                        issues.append(f"line {line}, column {column}: invalid numeric value")
        record.update(
            format="delimited_numeric_text",
            column_width_counts=widths,
            column_statistics=stats,
            issues=issues,
        )
        if mapping is not None:
            record.update(
                is_raw=mapping.raw_confirmed,
                mapping_evidence=mapping.evidence,
                time_column=mapping.time_column,
                time_unit=mapping.time_unit,
                channels=[
                    {"name": c.name, "column": c.column, "voltage_unit": c.voltage_unit}
                    for c in mapping.channels
                ],
            )
            record.update(
                status="READY" if mapping.raw_confirmed else "NEEDS_METADATA",
                reason="" if mapping.raw_confirmed else "Raw-waveform status unconfirmed",
            )
        if record["blank_rows"] or len(widths) != 1 or not record["data_rows"]:
            record.update(status="FAILED", reason="Blank/empty or inconsistent-width data rows")
    except (UnicodeError, ValueError, csv.Error, OSError) as exc:
        record.update(status="FAILED", reason=f"{type(exc).__name__}: {exc}")
    return record


def read_channel(
    path: Path,
    mapping: FileMapping,
    channel: ChannelMapping,
    *,
    rows: int,
    expected_sha256: str,
    max_reader_bytes: int,
) -> SampledSignal:
    if not mapping.raw_confirmed:
        raise ValueError("raw-waveform status must be confirmed")
    if "result" in path.stem.lower() and path.suffix.lower() == ".dat":
        raise ValueError("processed result DAT cannot be read as raw voltage")
    if rows < 4:
        raise ValueError("at least four data rows required")
    # Two input vectors, two owned SI vectors, diff and validation temporaries.
    if rows * 8 * 8 > max_reader_bytes:
        raise MemoryError("reader preflight exceeds explicit memory budget")
    if sha256(path) != expected_sha256:
        raise ValueError("source SHA-256 changed before reading")
    time = np.empty(rows, dtype=np.float64)
    voltage = np.empty(rows, dtype=np.float64)
    count = 0
    width: int | None = None
    for line, row in text_rows(path, mapping):
        if count >= rows:
            raise ValueError("row count changed since audit")
        if width is None:
            width = len(row)
        if not row or len(row) != width:
            raise ValueError(f"line {line}: blank or inconsistent-width row")
        try:
            time[count] = float(row[mapping.time_column]) * TIME_FACTORS[mapping.time_unit]
            voltage[count] = float(row[channel.column]) * VOLTAGE_FACTORS[channel.voltage_unit]
        except (IndexError, ValueError) as exc:
            raise ValueError(f"line {line}: invalid/missing mapped time or voltage") from exc
        count += 1
    if count != rows:
        raise ValueError("row count changed since audit")
    if sha256(path) != expected_sha256:
        raise ValueError("source SHA-256 changed during reading")
    return SampledSignal(time, voltage)
