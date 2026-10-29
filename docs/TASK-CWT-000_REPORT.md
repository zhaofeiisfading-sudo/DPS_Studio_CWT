# TASK-CWT-000 — 仓库规范与目录初始化

日期：2026-10-29（Asia/Shanghai）。结论：**LIMITED**。目录、缓存脚本、忽略规则和 Git 边界验收通过；指定的旧规划 `DPS_CWT_Research_Plan_2026-10-29.md` 在初始仓库中不存在，无法执行 v1.0 归档或与 v1.1 比较。

本报告只涉及初始化。未实现或运行 CWT，没有科学性能结论；未执行 TASK-CWT-001。

## 输入差异与保留

- 已完整阅读根 `AGENTS.md`、完整 Python `.gitignore`、README、提供的规划和环境脚本。
- 起始时 `docs/RESEARCH_PLAN.md` 不存在，v1.1 实际位于根 `RESEARCH_PLAN.md`。已将其原样移动到正式路径，SHA-256 保持为 `8A0358EAC0451ECEE3EBB37CE8A023420180ADB5DE3F87F078F1E6C4AA9E37D6`。
- 起始根 `cwt_env.ps1` 按 `scripts/` 布局计算根，直接从起始位置加载会拒绝执行。提供版原样保留为 `docs/archive/cwt_env.supplied.ps1.txt`；SHA-256 为 `3743873A9259E1FFFD38800FA99CEF90C77139E77DF5FEEAAC40F2D1EBA1252F`。
- README 和 AGENTS 的哈希未变；没有覆盖用户文件、修改 Git 配置、删除文件或执行清理。
- 本次不核验规划中的学术引用，保留原文不代表新增的文献核验结论。规划中后续任务涉及的目录/Git 初始化描述须受实际仓库和 AGENTS 约束，不能据此再次初始化。

## 实际目录与文件

```text
DPS_Studio_CWT/
├── .git/                         # 原有独立仓库，未手动编辑
├── .local_cache/                 # 被忽略；缓存目录和拒绝测试副本
├── artifacts/TASK-CWT-000/        # 被忽略；验收证据和审查 diff
├── benchmarks/.gitkeep
├── configs/.gitkeep
├── docs/
│   ├── RESEARCH_PLAN.md           # 提供的 v1.1，内容未变
│   ├── TASK-CWT-000_REPORT.md
│   └── archive/cwt_env.supplied.ps1.txt
├── scripts/
│   ├── cwt_env.ps1
│   └── Test-CwtEnvironment.ps1
├── src/pdv_cwt/.gitkeep
├── tests/.gitkeep
├── .gitignore                    # 仅追加规则
├── AGENTS.md                     # 起始已存在、未跟踪，内容未变
└── README.md                     # 原有已跟踪文件，内容未变
```

一级目录共 9 个（包含原有 `.git`），与 AGENTS 的集合完全相同。未创建 `pyproject.toml`、根 `.venv`、data/results/outputs/tmp/cache/build/dist 等目录。根目录初始和最终均没有待清理的缓存、构建或临时垃圾。`.local_cache/venv/` 仅为空目录占位，没有安装解释器或建立实际虚拟环境。

## 缓存脚本与验证

`scripts/cwt_env.ps1` 要求 PowerShell 7，检查固定工作区、独立 `.git` 目录、脚本文件、缓存目标及已有祖先的重解析点，在全部路径预检完成后创建缓存目录。重解析点先解析目标，再拒绝；不创建链接。脚本仅修改进程环境并回到项目根，辅助函数和错误处理偏好不泄漏到调用者。

下列路径全部指向本仓库 `.local_cache/`：`PYTHONPYCACHEPREFIX`、`RUFF_CACHE_DIR`、`MYPY_CACHE_DIR`、`MPLCONFIGDIR`、`PIP_CACHE_DIR`、`UV_CACHE_DIR`、`XDG_CACHE_HOME`、`NUMBA_CACHE_DIR`、`TEMP`、`TMP`、`TMPDIR`、`UV_PROJECT_ENVIRONMENT`。`PYTHONPATH` 清空；`PYTEST_ADDOPTS` 使用带引号的绝对 `pytest_tmp` 和 `pytest_cache` 路径。每个新 PowerShell 会话仍须先加载脚本。

实际复核命令：

```powershell
& 'C:\Users\89484\AppData\Local\Microsoft\WindowsApps\pwsh.exe' -NoLogo -NoProfile -Command '. .\scripts\cwt_env.ps1; & .\scripts\Test-CwtEnvironment.ps1 | ConvertTo-Json -Depth 8'
```

独立稳定版 PowerShell **7.6.9：23 PASS / 0 FAIL**。工具包装 shell 实测为 7.6.5，首次同组检查也是 23 PASS / 0 FAIL，证据分别保留。未使用 Windows PowerShell 5.1。

测试覆盖语法解析、从子目录加载、12 个路径、pytest 选项、调用者作用域、重复加载、错误根目录拒绝、重解析点和缓存路径被文件占用时拒绝。后两项采用模拟元数据，没有真实链接的端到端测试。未运行 Python 或 pytest，不能将字符串检查解释为 pytest 实际运行验证。

## 忽略规则与检查

`.gitignore` 原有 **4,884 字节**逐字节保留，并复核前缀 SHA-256 不变。追加 **40 行**，覆盖 `.local_cache/`、`artifacts/`、raw 路径及常见波形格式、敏感文件、误放缓存。保留原有 Python 缓存/构建规则；没有全局 `*.csv` 规则；忽略 `.dat` 不表示其一定是 raw。

实际对 45 个假想路径执行 `git check-ignore --no-index -v -- <path>`：**45 PASS / 0 FAIL**，其中 38 个应忽略、7 个应保留跟踪资格。普通 tests/benchmarks/configs CSV fixture 不被忽略，raw 目录中的 CSV 被忽略；没有创建或读取任何 raw 探针文件。

`git diff --check`：PASS；`git diff --cached --exit-code`：PASS，暂存区无变化。`pytest`、`ruff check`、`mypy --strict`：**NOT RUN**，本任务未建立 Python 项目或依赖，也没有 Python 代码；不为初始化任务安装工具。

Git 系统配置已有 `core.autocrlf=true`，对新增 LF 文本会提示将来转换为 CRLF；没有修改此配置，也没有重写原 `.gitignore` 字节。

## Git、产物和日志

仓库根为 `D:\Code\Python_Projects\DPS_Studio_CWT`；分支始终为 `research/cwt-morlet`；HEAD 始终为 `738d3c436236d1887a728327f77d12401b72ae7f`。origin 的 fetch/push 均为 `https://github.com/zhaofeiisfading-sudo/DPS_Studio_CWT.git`。这是独立 `.git` 目录，非 Production worktree 或子模块；未 init、切换分支、commit、push 或修改 remote。

已跟踪 diff 仅 `.gitignore`（+40/-0）；新规范、脚本、报告及 `.gitkeep` 都保持未跟踪，未暂存。起始 AGENTS 同样未跟踪，不能当作本次编写的规范。`.local_cache/` 与 `artifacts/` 正确忽略。准确最终状态和完整审查补丁见产物：

- `artifacts/TASK-CWT-000/environment_checks.json`
- `artifacts/TASK-CWT-000/environment_checks_stable_ps7.json`
- `artifacts/TASK-CWT-000/scaffold_acceptance.json`
- `artifacts/TASK-CWT-000/git_snapshot.json`
- `artifacts/TASK-CWT-000/review.diff`（包含未跟踪文件；不改暂存区）
- `artifacts/TASK-CWT-000/manifest.json`

逐步骤日志已写入 `D:\Research\Notes\05项目\DPS_Studio_CWT\2026-10-29_TASK-CWT-000_仓库规范与目录初始化.md`，不是 pending 草稿。其它项目和 Production 未访问或修改；真实 raw 未读取、复制或写入，raw 前后 SHA-256 **不适用**。哈希仅用于本仓库文本保留性验证。

唯一未完成的任务要求为缺失的 v1.0 规划归档/比较。下一步仅建议审查本次结果并确认旧规划的归档来源或缺失处理；后续任务须另行授权。
