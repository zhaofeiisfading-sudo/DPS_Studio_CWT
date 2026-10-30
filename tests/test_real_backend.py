"""All fixtures here are synthetic; no experimental raw bytes enter tracked tests."""

import csv
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pdv_cwt.batch import run_batch
from pdv_cwt.frequency import CWTConfig
from pdv_cwt.mapping import ChannelMapping, FileMapping, load_config
from pdv_cwt.pipeline import analyze_channel
from pdv_cwt.readers import audit_file, read_channel
from pdv_cwt.safety import ROOT, checked_path, scan_files, sha256


def mapping(path: str = "signal.csv", **changes: Any) -> FileMapping:
    return replace(
        FileMapping(
            path,
            0,
            "s",
            (ChannelMapping("c1", 1, "V"),),
            "synthetic fixture, explicit units",
            raw_confirmed=True,
        ),
        **changes,
    )


def fixture(path: Path, *, delimiter: str = ",", header: bool = False) -> None:
    time = np.arange(1024) / 40e9
    data = np.column_stack(
        (time, np.cos(2 * np.pi * 1e9 * time), 0.5 * np.cos(2 * np.pi * 1.5e9 * time))
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        if header:
            handle.write("instrument metadata\nTime;A;B\n")
        np.savetxt(handle, data, delimiter=delimiter)


def test_recursive_scan_all_files_and_link_boundary(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / ".gitkeep").write_text("")
    (nested / "unknown.bin").write_bytes(b"xyz")
    fixture(nested / "signal.csv")
    files = scan_files(tmp_path)
    assert len(files) == 3
    assert any(p.name == ".gitkeep" for p in files)
    with pytest.raises(ValueError, match="boundary"):
        checked_path(ROOT.parent, ROOT)


@pytest.mark.parametrize("delimiter", [",", ";", "\t", " "])
def test_reader_delimiters_and_dat(tmp_path: Path, delimiter: str) -> None:
    source = tmp_path / "waveform.dat"
    fixture(source, delimiter=delimiter)
    item = mapping("waveform.dat", delimiter="whitespace" if delimiter == " " else delimiter)
    audit = audit_file(source, item, 10**6)
    assert audit["status"] == "READY"
    signal = read_channel(
        source,
        item,
        item.channels[0],
        rows=audit["data_rows"],
        expected_sha256=audit["sha256_before"],
        max_reader_bytes=10**6,
    )
    assert signal.time_s.size == 1024
    assert signal.sampling_rate_hz == pytest.approx(40e9)
    assert signal.voltage_v[0] == 1
    assert sha256(source) == audit["sha256_before"]


def test_headers_multichannel_explicit_unit_conversion(tmp_path: Path) -> None:
    source = tmp_path / "signal.csv"
    time_ns = np.arange(1024) / 40
    with source.open("w", newline="") as handle:
        handle.write("metadata\ntime(ns);a(mV);b(uV)\n")
        np.savetxt(
            handle,
            np.column_stack((time_ns, np.ones(1024) * 200, np.ones(1024) * 3000)),
            delimiter=";",
        )
    item = mapping(
        delimiter=";",
        skip_rows=2,
        time_unit="ns",
        channels=(ChannelMapping("a", 1, "mV"), ChannelMapping("b", 2, "uV")),
    )
    audit = audit_file(source, item, 10**6)
    signals = [
        read_channel(
            source,
            item,
            c,
            rows=1024,
            expected_sha256=audit["sha256_before"],
            max_reader_bytes=10**6,
        )
        for c in item.channels
    ]
    assert audit["column_width_counts"] == {"3": 1024}
    np.testing.assert_allclose(signals[0].time_s, time_ns * 1e-9, atol=0)
    np.testing.assert_allclose(signals[0].voltage_v, 0.2)
    np.testing.assert_allclose(signals[1].voltage_v, 0.003)


def test_mapping_rejects_unknown_units_and_undocumented_optics() -> None:
    with pytest.raises(ValueError, match="unknown time unit"):
        mapping(time_unit="unknown")
    with pytest.raises(ValueError, match="unknown voltage unit"):
        ChannelMapping("a", 1, "counts")
    with pytest.raises(ValueError, match="optics evidence"):
        ChannelMapping("a", 1, "V", wavelength_m=1550e-9)
    with pytest.raises(ValueError, match="noise evidence"):
        ChannelMapping("a", 1, "V", noise_sigma_v=0)
    with pytest.raises(ValueError, match="duplicate"):
        mapping(channels=(ChannelMapping("a", 1, "V"), ChannelMapping("a", 2, "V")))


@pytest.mark.parametrize(
    "text",
    [
        "0,1\n1,1\n1,1\n3,1\n",
        "0,1\n1,1\n2.1,1\n3,1\n",
        "0,1\n1,nan\n2,1\n3,1\n",
        "0,1\n1,oops\n2,1\n3,1\n",
        "0,1\n1,1\n\n3,1\n",
        "0,1\n1,1,2\n2,1\n3,1\n",
    ],
)
def test_invalid_data_never_repaired(tmp_path: Path, text: str) -> None:
    source = tmp_path / "signal.csv"
    source.write_text(text)
    before = sha256(source)
    item = mapping()
    audit = audit_file(source, item, 10**6)
    with pytest.raises(ValueError):
        read_channel(
            source,
            item,
            item.channels[0],
            rows=audit["data_rows"],
            expected_sha256=before,
            max_reader_bytes=10**6,
        )
    assert sha256(source) == before


def test_processed_result_excluded_even_with_mapping(tmp_path: Path) -> None:
    source = tmp_path / "my_result.dat"
    fixture(source)
    item = mapping("my_result.dat")
    assert audit_file(source, item, 10**6)["status"] == "NOT_RAW"
    with pytest.raises(ValueError, match="processed result"):
        read_channel(
            source,
            item,
            item.channels[0],
            rows=1024,
            expected_sha256=sha256(source),
            max_reader_bytes=10**6,
        )


def test_memory_and_hash_preflights(tmp_path: Path) -> None:
    source = tmp_path / "signal.csv"
    fixture(source)
    item = mapping()
    before = sha256(source)
    assert audit_file(source, item, 1)["status"] == "FAILED_RESOURCE"
    with pytest.raises(MemoryError, match="reader preflight"):
        read_channel(
            source, item, item.channels[0], rows=10**10, expected_sha256=before, max_reader_bytes=1
        )
    with pytest.raises(ValueError, match="SHA-256"):
        read_channel(
            source,
            item,
            item.channels[0],
            rows=1024,
            expected_sha256="wrong",
            max_reader_bytes=10**6,
        )
    audit = audit_file(source, item, 10**6)
    status = analyze_channel(
        source,
        item,
        item.channels[0],
        CWTConfig(max_memory_bytes=1),
        audit,
        tmp_path / "budget_failure",
    )
    assert status["status"] == "FAILED_RESOURCE"
    assert not status["cwt_success"]
    assert sha256(source) == before


def test_source_open_modes_are_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "signal.csv"
    fixture(source)
    original_open = Path.open
    modes: list[str] = []

    def guarded_open(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if self == source:
            modes.append(mode)
            assert mode in ("r", "rb"), "reader/audit may only open source read-only"
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    item = mapping()
    audit = audit_file(source, item, 10**6)
    read_channel(
        source,
        item,
        item.channels[0],
        rows=audit["data_rows"],
        expected_sha256=audit["sha256_before"],
        max_reader_bytes=10**6,
    )
    assert "rb" in modes and "r" in modes


def test_scalogram_survives_candidate_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "signal.csv"
    fixture(source)
    item = mapping()
    audit = audit_file(source, item, 10**6)

    def unavailable_candidate(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected candidate failure")

    monkeypatch.setattr("pdv_cwt.pipeline.strongest_candidate", unavailable_candidate)
    output = tmp_path / "preserved_scalogram"
    status = analyze_channel(
        source,
        item,
        item.channels[0],
        CWTConfig(frequency_min_hz=0.5e9, frequency_max_hz=2e9, voices_per_octave=4),
        audit,
        output,
    )
    assert status["status"] == "SCALOGRAM_ONLY"
    assert status["cwt_success"]
    assert not status["candidate_success"]
    assert "injected candidate failure" in status["reason"]
    assert (output / "cwt_scalogram.png").is_file()
    assert (output / "metadata.json").is_file()
    with pytest.raises(ValueError, match="boundaries"):
        analyze_channel(
            source,
            item,
            item.channels[0],
            CWTConfig(),
            audit,
            ROOT / "raw_data" / "must_not_be_created",
        )


def test_velocity_requires_explicit_optics_and_quality_separate(tmp_path: Path) -> None:
    source = tmp_path / "signal.csv"
    fixture(source)
    item = mapping(
        channels=(
            ChannelMapping(
                "c1",
                1,
                "V",
                wavelength_m=1550e-9,
                zero_optical_offset=True,
                optics_evidence="synthetic fixture assumption",
            ),
        )
    )
    audit = audit_file(source, item, 10**6)
    output = tmp_path / "known_optics"
    status = analyze_channel(
        source,
        item,
        item.channels[0],
        CWTConfig(frequency_min_hz=0.5e9, frequency_max_hz=2e9, voices_per_octave=4),
        audit,
        output,
    )
    assert status["status"] == "ANALYZED"
    assert status["quality_pass_rate"] is None
    assert status["quality_unknown_fraction"] == 1
    with (output / "candidate_velocity.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1024
    assert all(r["quality_result"] == "UNKNOWN" for r in rows)
    np.testing.assert_allclose(
        [float(r["apparent_velocity_m_s"]) for r in rows],
        [float(r["candidate_frequency_hz"]) * 1550e-9 / 2 for r in rows],
    )
    assert (output / "velocity_time.png").exists()


def test_batch_e2e_all_files_failure_isolation_and_metadata(tmp_path: Path) -> None:
    raw = tmp_path / "synthetic_raw"
    raw.mkdir()
    fixture(raw / "signal.csv")
    (raw / "broken.csv").write_text("0,1\n1,bad\n2,1\n3,1\n")
    (raw / ".gitkeep").write_text("")
    fixture(raw / "result.dat")
    (raw / "unknown.bin").write_bytes(b"unsupported")
    nested = raw / "nested"
    nested.mkdir()
    fixture(nested / "unmapped.csv")
    hashes = {p.relative_to(raw).as_posix(): sha256(p) for p in scan_files(raw)}
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'''
[batch]
raw_root = "{raw.relative_to(ROOT).as_posix()}"
output_root = "{(tmp_path / "runs").relative_to(ROOT).as_posix()}"
display_max_columns = 200
[cwt]
frequency_min_hz = 500000000.0
frequency_max_hz = 2000000000.0
voices_per_octave = 4
[[files]]
path = "signal.csv"
time_column = 0
time_unit = "s"
evidence = "synthetic fixture"
raw_confirmed = true
[[files.channels]]
name = "a"
column = 1
voltage_unit = "V"
[[files.channels]]
name = "b"
column = 2
voltage_unit = "V"
[[files]]
path = "broken.csv"
time_column = 0
time_unit = "s"
evidence = "synthetic fixture"
raw_confirmed = true
[[files.channels]]
name = "c"
column = 1
voltage_unit = "V"
''',
        encoding="utf-8",
    )
    config = load_config(config_path)
    run = run_batch(config)
    manifest = json.loads((run / "batch_manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["files_scanned"] == 6
    assert manifest["counts"]["channels_attempted"] == 3
    assert manifest["counts"]["cwt_scalograms_success"] == 2
    assert manifest["counts"]["cwt_scalograms_failed"] == 1
    assert manifest["counts"]["scalogram_only_channels"] == 2
    assert manifest["raw_sha256_unchanged"]
    assert {r["file"] for r in manifest["files"]} == set(hashes)
    assert any(r["status"] == "NEEDS_MAPPING" for r in manifest["files"])
    for status in manifest["channels"]:
        if not status["cwt_success"]:
            assert status["file"] == "broken.csv"
            continue
        output = ROOT / status["output_path"]
        metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["csv_rows"] == status["samples"] == 1024
        assert metadata["source_sha256"] == hashes["signal.csv"]
        assert (output / "cwt_scalogram.png").stat().st_size > 1000
        assert not (output / "velocity_time.png").exists()
        with np.load(output / "display_response.npz") as display:
            assert display["time_s"].size <= 200
            assert display["source_sample_indices"][-1] == 1023
        with (output / "candidate_velocity.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 1024
        assert all(r["apparent_velocity_m_s"] == "" for r in rows)
        assert all(r["quality_evaluation_status"] == "NOT_EVALUATED" for r in rows)
        assert all(r["noise_model_status"] == "UNKNOWN" for r in rows)
        assert all(
            float(r["selected_scale"]) == metadata["scales"][int(r["scale_index"])] for r in rows
        )
    assert hashes == {p.relative_to(raw).as_posix(): sha256(p) for p in scan_files(raw)}
