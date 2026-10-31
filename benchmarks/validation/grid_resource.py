"""Post-run fresh-process resource audit for all three preregistered grid types.

Uses the first registered mid-band frequency, never selects by observed error.
Scientific metrics and the engineering GO timing gate are not changed.
"""

import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from pdv_cwt.resources import memory_snapshot
from pdv_cwt.safety import ROOT

from .cases import make_case
from .io import output, write_csv, write_json
from .run import profile_key
from .scoring import cwt, score_response


def worker(request: dict[str, Any]) -> dict[str, Any]:
    case = make_case(request["spec"])
    start = perf_counter()
    result, transform_s = cwt(case.signal, request["voices"])
    candidate_start = perf_counter()
    raw = np.abs(result.coefficients)
    absolute_s = perf_counter() - candidate_start
    candidate_times = {}
    for mode in ("A0", "A1", "A2"):
        tick = perf_counter()
        response = score_response(raw, result.grid.scales, mode, np.asarray(request["rms"]))
        selected = np.argmax(response, axis=0)
        candidate_times[mode] = perf_counter() - tick + absolute_s
        assert selected.size == case.signal.time_s.size
        if mode != "A0":
            del response
    elapsed = perf_counter() - start
    return dict(
        kind=request["spec"]["kind"],
        fs_hz=request["spec"]["fs"],
        voices=request["voices"],
        samples=case.signal.time_s.size,
        frequency_hz=request["spec"]["frequency_hz"],
        seed=request["spec"]["seed"],
        cwt_s=transform_s,
        candidate_s=candidate_times,
        total_three_scores_s=elapsed,
        peak_bytes=memory_snapshot()["peak_working_set_bytes"],
        shape=result.coefficients.shape,
        coefficient_bytes=result.coefficients.nbytes,
        scope="fresh process; same CWT for A0/A1/A2; combined peak before exports",
    )


def run_audit(run: Path) -> list[dict[str, Any]]:
    splits = json.loads((run / "split_registry.json").read_text(encoding="utf-8"))
    profiles = json.loads((run / "calibration/score_profiles.json").read_text(encoding="utf-8"))
    rows = []
    for fs in (40e9, 80e9):
        for kind in ("clean", "noisy", "linear"):
            spec = next(
                s
                for s in splits["grid"]
                if s["fs"] == fs and s["band"] == "mid" and s["kind"] == kind
            )
            for voices in (24, 48, 96):
                request = dict(
                    spec=spec, voices=voices, rms=profiles[profile_key(fs, "white", voices)]
                )
                path = output(run / "grid_resource" / f"fs{int(fs)}_{kind}_v{voices}.json")
                write_json(path, request)
                result = subprocess.run(
                    [sys.executable, "-m", "benchmarks.validation.grid_resource", str(path)],
                    capture_output=True,
                    text=True,
                    cwd=ROOT,
                    timeout=900,
                    check=True,
                )
                with output(path.with_suffix(".stdout.txt")).open("x", encoding="utf-8") as handle:
                    handle.write(result.stdout)
                with output(path.with_suffix(".stderr.txt")).open("x", encoding="utf-8") as handle:
                    handle.write(result.stderr)
                rows.append(json.loads(result.stdout))
    write_csv(run / "grid_time_memory.csv", rows)
    write_json(run / "grid_time_memory.json", rows)
    return rows


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--run":
        print(json.dumps(run_audit(Path(sys.argv[2]))))
    else:
        print(json.dumps(worker(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))))
