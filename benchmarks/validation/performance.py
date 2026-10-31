"""Isolated strategy costs, with pre-export native Windows process peak."""

import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from pdv_cwt.models import SampledSignal
from pdv_cwt.resources import memory_snapshot
from pdv_cwt.safety import ROOT

from .io import output, write_csv, write_json
from .run import profile_key
from .scoring import cwt, score_response, stft_bank


def worker(request: dict[str, Any]) -> dict[str, Any]:
    fs, voices, mode = request["fs"], request["voices"], request["method"]
    n = round(32768 * fs / 40e9)
    t = np.arange(n, dtype=np.float64) / fs
    signal = SampledSignal(t, np.cos(2 * np.pi * 1.137e9 * t + 0.37))
    start = perf_counter()
    if mode.startswith("A"):
        result, transform_s = cwt(signal, voices)
        candidate_start = perf_counter()
        raw = np.abs(result.coefficients)
        score = score_response(raw, result.grid.scales, mode, np.asarray(request["rms"]))
        prediction = result.grid.frequency_hz[np.argmax(score, axis=0)]
        candidate_s = perf_counter() - candidate_start
        shape = result.coefficients.shape
        coefficient_bytes = result.coefficients.nbytes
        preflight = result.memory.working_bytes
    else:
        # Include amplitude/argmax here; explicitly report combined STFT operation.
        bank = stft_bank(signal, mode == "high_time")
        transform_s = perf_counter() - start
        candidate_s = None
        prediction = bank.predicted
        shape, coefficient_bytes = bank.score.shape, bank.score.nbytes * 2
        preflight = bank.metadata["preflight_memory_bytes"]
    elapsed = perf_counter() - start
    return dict(
        status="COMPLETED",
        method=mode,
        voices=voices,
        fs_hz=fs,
        samples=n,
        transform_s=transform_s,
        candidate_s=candidate_s,
        total_s=elapsed,
        seconds_per_physical_input_second=elapsed / (n / fs),
        seconds_per_million_samples=elapsed / n * 1e6,
        peak_memory_bytes=memory_snapshot()["peak_working_set_bytes"],
        matrix_shape=shape,
        coefficient_bytes=coefficient_bytes,
        preflight_bytes=preflight,
        native_output_count=prediction.size,
        finite_fraction=float(np.mean(np.isfinite(prediction))),
        memory_scope="fresh worker lifecycle; before exports/plots",
        timing_scope="CWT wrapper then score/argmax; total includes abs; STFT includes argmax",
    )


def performance_run(run: Path, profiles: dict[str, list[float]]) -> list[dict[str, Any]]:
    rows = []
    for fs in (40e9, 80e9):
        for voices in (24, 48, 96):
            for mode in ("A0", "A1", "A2"):
                request = dict(
                    fs=fs,
                    voices=voices,
                    method=mode,
                    rms=profiles[profile_key(fs, "white", voices)],
                )
                path = output(run / "performance" / f"fs{int(fs)}_v{voices}_{mode}.json")
                write_json(path, request)
                result = subprocess.run(
                    [sys.executable, "-m", "benchmarks.validation.performance", str(path)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=900,
                )
                with output(path.with_suffix(".stdout.txt")).open("x") as handle:
                    handle.write(result.stdout)
                with output(path.with_suffix(".stderr.txt")).open("x") as handle:
                    handle.write(result.stderr)
                record = (
                    json.loads(result.stdout)
                    if result.returncode == 0
                    else dict(status="FAILED", request=request, error=result.stderr)
                )
                rows.append(record)
        for mode in ("balanced", "high_time"):
            path = output(run / "performance" / f"fs{int(fs)}_{mode}.json")
            write_json(path, dict(fs=fs, voices=24, method=mode))
            result = subprocess.run(
                [sys.executable, "-m", "benchmarks.validation.performance", str(path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=900,
            )
            with output(path.with_suffix(".stdout.txt")).open("x") as handle:
                handle.write(result.stdout)
            with output(path.with_suffix(".stderr.txt")).open("x") as handle:
                handle.write(result.stderr)
            rows.append(
                json.loads(result.stdout)
                if result.returncode == 0
                else dict(status="FAILED", method=mode, error=result.stderr)
            )
    write_csv(run / "time_memory_comparison.csv", rows)
    return rows


if __name__ == "__main__":
    print(json.dumps(worker(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))))
