# DPS_Studio_CWT — Codex / Agent Operating Rules

> Scope: **this independent repository only**. These rules apply to every task, including planning, audits, and failed/blocked attempts. Do not begin TASK-CWT-001 automatically when setting up the repository.

## 1. Mission, method, and authority

- Repository/workspace: `D:\Code\Python_Projects\DPS_Studio_CWT`.
- Intended branch: `research/cwt-morlet` (a branch **inside this independent Git repository**, not a Production branch/worktree).
- Product: reproducible **PDV research**, exclusively on the **complex Morlet continuous wavelet transform (CWT)** for time-frequency analysis and apparent-velocity estimation. The initial wavelet is `cmor1.5-1.0`; it is an unvalidated starting configuration, not a proven optimum.
- Comparison with **fixed-window Hann STFT + frame-wise strongest peak** is allowed **as a baseline only**, inside `benchmarks/`. Never quietly replace CWT with STFT or start a second new-method line (SST, chirplet, Hilbert-phase tracking, AI, IMM/MHT, Global Path, etc.).
- Initial scope: Python 3.12 scientific core, synthetic tests, reproducible benchmarks and reports. No GUI, executable packaging, Production export compatibility, or automatic LiF/angle correction.
- Authority order for facts: current repository source/Git state/tests/real artifacts > current user instructions and verified experiments > project charter > past task reports. If `docs/RESEARCH_PLAN.md` conflicts with the existing independent Git repository or this AGENTS document, **do not run `git init` or alter remotes**; report and reconcile non-destructively.
- The CWT plan is a **hypothesis and experiment protocol**, not proof that CWT outperforms STFT. Report negative results. Never invent papers, DOIs, measurements, instrument models, successful tests or Git states.

## 2. Immutable filesystem and data boundaries

**Only allowed code workspace:**
`D:\Code\Python_Projects\DPS_Studio_CWT`

**Always protected / read-only, including their subfolders:**
- `D:\Code\Python_Projects\DPS_Studio` (Production)
- `D:\Code\Python_Projects\DPS_Studio_TASK021A` (previous Research)
- `D:\Code\Python_Projects\DPS_Studio_BANDWIDTH` (other independent Research, if present)
- `D:\Code\Python_Projects\DPS_Studio_RESEARCH_CLEAN` (if present)
- every other sibling under `D:\Code\Python_Projects`, and the parent directory itself
- any source of real/raw PDV waveforms, wherever located

**Only routine permitted write outside this repository:** the mandatory Markdown TASK log in:
`D:\Research\Notes\05项目\DPS_Studio_CWT`

Never write code, generated cache, screenshots, experimental CSV, or intermediate artifacts to the Obsidian location; only the lightweight task log goes there. Do not create sibling projects, writable symlinks/junctions, or external scratch directories. Resolve Windows reparse points before writing; a path textually inside this repo but pointing elsewhere is not authorized. `AGENTS.md` is guidance, not a substitute for filesystem or sandbox permissions.

No real data access before a separately authorized TASK. For later real-data work, use explicit **read-only** file access, retain raw bytes, and record SHA-256 **before and after** reading. Filenames containing `result` with `.dat` are processed results, **not raw**. Never copy real raw data into this repo without explicit approval. No silent preprocessing, resampling, smoothing, interpolation, unit guessing, clipping, dropping, or modification of raw.

## 3. Fixed first-level repository layout

During the **one-time TASK-CWT-000 scaffold only**, create these first-level directories (and no others without the user's approval):

```text
DPS_Studio_CWT/
├── .git/                    # Git-managed; never edit directly
├── .local_cache/            # ALL disposable caches/temporary build outputs; Git-ignored
├── src/pdv_cwt/             # Only CWT scientific core; NO GUI imports
├── tests/                   # Correctness, failure modes, numerical tests
├── configs/                 # Explicit, versioned research parameter files
├── benchmarks/              # Synthetic ground truth; fixed STFT reference; metrics
├── scripts/                 # Entrypoints, environment setup, safe tooling
├── docs/                    # Research plan, methodology, decisions, pending logs
├── artifacts/               # Persistent generated research results, per TASK, ignored by Git
├── raw_data/                # Real experimental data, strictly read-only, permanently Git-ignored
├── AGENTS.md
├── README.md
├── .gitignore
└── pyproject.toml           # Added by TASK-CWT-001, not assumed present now
```

- **No top-level** `data/`, `results/`, `outputs/`, `tmp/`, `cache/`, `logs/`, `build/`, `dist/`, `.venv/`, or loose experiment scripts/CSVs/PNGs. Do not create separate top-level cache locations.
- The corrected `docs/RESEARCH_PLAN.md` (v1.1) supplied with this scaffold is the **canonical current plan**. During TASK-CWT-000, **move** the existing root-level `DPS_CWT_Research_Plan_2026-10-29.md` (v1.0) to `docs/archive/` for provenance; do not overwrite v1.1 with the older copy. Preserve, compare, and log both; do not delete either.
- `src`, `tests`, `configs`, `benchmarks`, `scripts`, `docs` hold **reviewable code/text tracked by Git** (after explicit approval to commit). Use `artifacts/TASK-CWT-XXX/` for durable generated plots, tables, manifests and performance runs. Do not delete old artifacts without authorization.
- `.local_cache/` is **disposable** (including virtual environment, pycache, pytest, Ruff, mypy, pip/uv cache, Matplotlib cache, temp files, build intermediates). Artifacts and Obsidian logs are **not** disposable caches.
- `raw_data/` is the user-authorized additional first-level directory for real experimental data: **strictly read-only and permanently Git-ignored**. It is not a cache or an artifacts directory; do not access its contents without a separately authorized real-data TASK. `artifacts/` holds persistent generated research results and must not be silently deleted.
- Do not reorganize the frozen first-level layout after TASK-CWT-000 without explicit approval; subfolders inside the approved roots may be added as needed for a TASK.

## 4. Cache discipline: mandatory, not cosmetic

- Before invoking Python, tests, linters, package installers, or benchmark scripts in PowerShell, run **in the same shell**:

  ```powershell
  . .\scripts\cwt_env.ps1
  ```

  (The initial scaffold creates that script.) Confirm its root resolves to THIS repository; never source a sibling project's env script.
- The script redirects `PYTHONPYCACHEPREFIX`, `PYTEST_ADDOPTS` (pytest cache and tmp base), `RUFF_CACHE_DIR`, `MYPY_CACHE_DIR`, `MPLCONFIGDIR`, `PIP_CACHE_DIR`, `UV_CACHE_DIR`, `XDG_CACHE_HOME`, `TEMP`, `TMP`, and `TMPDIR` under `.local_cache/`, and changes the current directory to the project root. Make no assumptions that an IDE/other shell inherited these variables.
- If using a virtual environment, create it ONLY at `.local_cache/venv/` and explicitly select that interpreter; never create root `.venv/` or global project-specific Conda environments without approval.
- Configure `pyproject.toml` so `pytest` by itself also uses `.local_cache/pytest_cache` and `.local_cache/pytest_tmp`. Run `pytest`, Ruff, and mypy only after sourcing the cache script. If a tool cannot redirect its cache or build outputs, **stop and report**, rather than making root garbage.
- `.gitignore` must exclude `.local_cache/`, `artifacts/`, real data (`data/raw/` and relevant raw formats if introduced), secrets, and accidental cache/build directories. Do **not** globally ignore `*.csv` because small reference fixtures may be legitimate tracked source assets; instead keep raw out and artifacts ignored.
- Never invoke `git clean -fdx` or a similar broad cleanup. Even ignored files can be valuable. Cleanup requires user-approved explicit target paths; the cache directory is the only disposable root, and it must not be silently erased.

## 5. Git, repository hygiene, and task gate

At the beginning of **every** TASK, including TASK-CWT-000:

1. Verify exact `Get-Location`/resolved workspace path and branch using `git rev-parse --show-toplevel`, `git branch --show-current`, `git status --short`, `git remote -v`, and relevant `git diff`/untracked files.
2. The expected branch is `research/cwt-morlet`. If not, **stop and ask**, do not silently switch. Verify this is its own Git repository, not a Production worktree or Git submodule.
3. Inspect `AGENTS.md`, `docs/RESEARCH_PLAN.md` (or original plan until moved), `.gitignore`, relevant code/config/tests, and possible raw paths before making changes.
4. Record the initial status and scope in the TASK log (see §8). Preserve existing uncommitted and untracked changes.

Never `git init`, recreate the repository, alter `origin`, commit, push, merge, rebase, cherry-pick, reset, clean, delete branches, rewrite history, or promote to Production without an explicit new user authorization. Do not assume a branch exists because of a screenshot; verify. Do not write to the root of `D:\Code\Python_Projects` or other projects. If the repo cannot be verified, return `BLOCKED` with diagnostics and do not proceed.

Each TASK must declare objective, allowed/forbidden paths, inputs, outputs, units, acceptance tests, known unknowns, Git/data boundaries, and logging. Work **only on the requested TASK**; never automatically start the next one.

## 6. Scientific contracts and claims

- Input: explicit time axis and voltage samples, time in **seconds**, voltage in **volts**; internal SI units `s`, `V`, `Hz`, `m/s`, `m`, `rad`. Reject non-uniform sampling in v1; never silently resample.
- Physical conversion: `v_app = lambda_0 * f_b / 2` with **explicit** wavelength in metres and explicit assumption of zero optical offset. A one-sided real-signal spectrum ordinarily yields **unsigned** beat frequency/velocity. Do not silently infer direction, wavelength, optical offset, angle or LiF conditions.
- Distinguish beat-frequency candidate, apparent velocity, angle-corrected velocity, window-corrected velocity and validated physical velocity; only **apparent velocity** is in the initial core. Never add LiF/angle correction inside this Research TASK without separate approval.
- CWT implementation: v1 uses PyWavelets `pywt.cwt(..., method="fft")`, complex Morlet `cmor1.5-1.0`, and a documented scale-to-Hz mapping (`pywt.scale2frequency / sampling_period`). Frequency band must remain within Nyquist; also check for practical *discrete-scale aliasing*, which can occur even before Nyquist.
- Test amplitude/scale normalization and its influence on **strongest response across scales**, not merely the appearance of the scalogram. Explicitly mark finite-support/boundary contamination. Distinguish frequency-grid spacing from true resolving power; do not describe zero-padding as increased physical frequency resolution.
- Separate candidate extraction from diagnostics/quality. Raw strongest evidence and quality flags must be reproducible; no implicit continuity repair, interpolation, smoothing, or branch locking.
- Keep representative **STFT + frame-wise strongest** baseline for comparisons, with identical input, time/frequency evaluation constraints, fair calibration and no tuning on held-out ground truth. Coverage and curve smoothness alone are **not** correctness.
- Synthetic known truth: report RMSE, wrong-branch, coverage, onset error, noise false-positive rate, harm, compute time/memory as applicable, with fixed seeds/held-out splits. Real data lacks truth: report spectral support, provenance and observations only. Use `UNKNOWN`, `NOT SUPPORTED`, or `REQUIRES EXPERIMENTAL CONFIRMATION` when appropriate.
- No fabricated references, numerical results, passing test claims, or Git/runs. If contradictory scientific evidence is found, preserve it in an artifact and discuss it in the verdict.

## 7. Tests, deliverables, and artifacts

- Add targeted passing **and failure-mode** tests for code that changes. Use `pytest`, `ruff check`, and `mypy --strict` where applicable; record exact commands, tool versions, actual outcomes and existing failures. Do not label checks PASS if they were skipped.
- Reproducibility: record input provenance/sha256 (synthetic generation recipe or read-only raw hash), RNG seed, versions, wavelet/scales, frequency range, sampling interval, wavelength, normalization, boundary mask policy, evaluation mask, hardware and elapsed time as relevant.
- Put task-specific generated results under `artifacts/TASK-CWT-XXX/`, e.g. `manifest.json`, `metrics.csv`, `figures/*.png`; small human-reviewed methodology/decision reports belong in `docs/`.
- No automatic Git commit/push. Deliver a reviewable `git diff` and `git status`; state what remains untracked/ignored. Do not publish raw experimental data or unverified physical assertions.

## 8. Mandatory Obsidian **lightweight TASK summary**

**Purpose:** Obsidian is a **fast project index**, never an execution transcript or full research report. Every TASK (including BLOCKED/negative/audit tasks) must leave **one concise Markdown note** under:

`D:\Research\Notes\05项目\DPS_Studio_CWT`

Filename: `YYYY-MM-DD_TASK-CWT-XXX_简短标题.md` (actual execution date).

- Target **15–30 lines and generally <=500 Chinese characters** (not a rigid quota when essential information is longer). Create a minimal `IN PROGRESS` stub at task start, then **update the same file** at major milestones or completion; do not append a timestamped command-by-command diary.
- Record **only**: TASK/date/branch/status/verdict; one-sentence objective and completed work; main changed paths; **1–3 decisive quantitative findings including negative results** (or `NOT MEASURED`); pytest/Ruff/mypy outcome or `NOT RUN`; Git/raw/Production boundary status; links/paths to the detailed report and artifacts; one unresolved issue and recommended next TASK. Do not dump a file-by-file hash inventory, shell command transcript, entire Git status, full diffs or lengthy method discussions into Obsidian.
- Store full methods, interpretation and decisions in `docs/TASK-CWT-XXX_REPORT.md` (or another appropriately named `docs/` file); put machine-readable results, figures, manifests, hashes, command outputs and detailed evidence under `artifacts/TASK-CWT-XXX/`. These are the **audit/source-of-truth** locations. A brief note should make it easy to decide what to open next.
- Existing long TASK-CWT-000 note may be condensed **without deleting the underlying evidence**: keep `docs/TASK-CWT-000_REPORT.md` and artifacts, and optionally archive the original long narrative under `docs/archive/` before replacing the Obsidian note. Never invent missing measurements.
- If Obsidian is inaccessible, place the exact pending short note in `docs/pending_logs/`, mark `BLOCKED FOR LOGGING`, and report the failure. Never claim an external write that did not succeed.

Suggested 15–20-line shape:

```markdown
# TASK-CWT-XXX | 简短标题
- 日期/分支：... / research/cwt-morlet
- 状态/结论：COMPLETED / PASS|LIMITED|NOT SUPPORTED|BLOCKED
- 目标：...
- 完成：...
- 修改：`src/...`, `tests/...`
- 结果：...（1–3 项，负结果如实写）
- 验收：pytest ...；Ruff ...；mypy ...（未运行则 NOT RUN）
- 边界：Git 未提交/推送；raw 未访问；Production 未修改
- 报告：`docs/TASK-CWT-XXX_REPORT.md`
- 产物：`artifacts/TASK-CWT-XXX/`
- 问题：...
- 下一步：...
```

## 9. Mandatory response at the end of a TASK

Provide in Chinese:

- Task ID and verdict: `PASS`, `LIMITED`, `NOT SUPPORTED`, or `BLOCKED`, with evidence boundaries.
- Created/changed paths and concrete artifact locations.
- Numerical results and exact test/lint/type-check commands/outcomes (or explicit `NOT RUN` reason).
- `git status`, diff scope, branch/remote, any ignored files and raw SHA-256 checks when applicable.
- Obsidian log **full path** (or a documented pending draft + blocker).
- Next-step recommendation **only**. Stop after the authorized TASK.
