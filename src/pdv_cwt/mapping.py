"""Explicit TOML mappings. Column indices are zero-based, never inferred from size."""

import math
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .frequency import CWTConfig
from .safety import ROOT, checked_path

TIME_FACTORS = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9, "ps": 1e-12}
VOLTAGE_FACTORS = {"V": 1.0, "mV": 1e-3, "uV": 1e-6}


@dataclass(frozen=True)
class ChannelMapping:
    name: str
    column: int
    voltage_unit: str
    wavelength_m: float | None = None
    zero_optical_offset: bool | None = None
    optics_evidence: str = ""
    noise_sigma_v: float | None = None
    noise_evidence: str = ""

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.name):
            raise ValueError("channel name must be a safe ASCII identifier")
        if type(self.column) is not int or self.column < 0:
            raise ValueError("channel column must be a nonnegative integer")
        if self.voltage_unit not in VOLTAGE_FACTORS:
            raise ValueError(f"unknown voltage unit: {self.voltage_unit}")
        if self.wavelength_m is not None:
            if not math.isfinite(self.wavelength_m) or self.wavelength_m <= 0:
                raise ValueError("wavelength_m must be finite and positive")
        if self.zero_optical_offset is not None and type(self.zero_optical_offset) is not bool:
            raise ValueError("zero_optical_offset must be explicit bool or absent")
        if self.wavelength_m is not None or self.zero_optical_offset is not None:
            if not self.optics_evidence.strip():
                raise ValueError("explicit optics evidence required")
        if self.noise_sigma_v is not None:
            if not math.isfinite(self.noise_sigma_v) or self.noise_sigma_v < 0:
                raise ValueError("noise_sigma_v must be finite and nonnegative")
            if not self.noise_evidence.strip():
                raise ValueError("explicit iid white-Gaussian noise evidence required")


@dataclass(frozen=True)
class FileMapping:
    path: str
    time_column: int
    time_unit: str
    channels: tuple[ChannelMapping, ...]
    evidence: str
    delimiter: str = ","
    skip_rows: int = 0
    encoding: str = "utf-8-sig"
    raw_confirmed: bool = False

    def __post_init__(self) -> None:
        if Path(self.path).is_absolute() or ".." in Path(self.path).parts:
            raise ValueError("mapping path must be relative without parent traversal")
        if self.time_unit not in TIME_FACTORS:
            raise ValueError(f"unknown time unit: {self.time_unit}")
        if type(self.time_column) is not int or self.time_column < 0:
            raise ValueError("time column must be a nonnegative integer")
        if type(self.skip_rows) is not int or self.skip_rows < 0:
            raise ValueError("skip_rows must be a nonnegative integer")
        if self.delimiter != "whitespace" and len(self.delimiter) != 1:
            raise ValueError("delimiter must be one character or whitespace")
        if not self.evidence.strip() or not self.channels:
            raise ValueError("mapping evidence and at least one channel required")
        names = [channel.name for channel in self.channels]
        columns = [channel.column for channel in self.channels]
        if len(set(names)) != len(names) or len(set(columns)) != len(columns):
            raise ValueError("duplicate channel name or column")
        if self.time_column in columns:
            raise ValueError("time column cannot also be a voltage column")


@dataclass(frozen=True)
class BatchConfig:
    raw_root: Path
    output_root: Path
    mappings: dict[str, FileMapping]
    cwt: CWTConfig
    config_path: Path
    max_input_bytes: int = 512 * 1024**2
    max_reader_bytes: int = 256 * 1024**2
    display_max_columns: int = 2400
    worker_timeout_s: int = 900


def load_config(path: Path) -> BatchConfig:
    path = checked_path(path, ROOT)
    with path.open("rb") as handle:
        values = tomllib.load(handle)
    batch = values["batch"]
    raw_root = checked_path(ROOT / batch["raw_root"], ROOT)
    output_root = checked_path(ROOT / batch["output_root"], ROOT)
    if not any(raw_root.is_relative_to(ROOT / p) for p in ("raw_data", ".local_cache")):
        raise ValueError("input root must stay in raw_data or synthetic .local_cache")
    if not any(
        output_root.is_relative_to(ROOT / p) for p in ("artifacts/TASK-CWT-003", ".local_cache")
    ):
        raise ValueError("output root must stay in TASK-CWT-003 artifacts or .local_cache")
    mappings: dict[str, FileMapping] = {}
    for entry in values.get("files", []):
        item: dict[str, Any] = dict(entry)
        item["channels"] = tuple(ChannelMapping(**c) for c in item.pop("channels"))
        mapping = FileMapping(**item)
        key = Path(mapping.path).as_posix()
        if key.casefold() in {k.casefold() for k in mappings}:
            raise ValueError(f"duplicate file mapping: {key}")
        mappings[key] = mapping
    options = {key: value for key, value in batch.items() if key not in ("raw_root", "output_root")}
    for key, value in options.items():
        if type(value) is not int or value <= 0:
            raise ValueError(f"positive integer required: {key}")
    if options.get("display_max_columns", 2400) < 2:
        raise ValueError("display_max_columns must be >= 2")
    return BatchConfig(raw_root, output_root, mappings, CWTConfig(**values["cwt"]), path, **options)
