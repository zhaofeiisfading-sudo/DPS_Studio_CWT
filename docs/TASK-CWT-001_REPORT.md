# TASK-CWT-001 — 复 Morlet CWT 内核开发前置检查

日期：2026-10-29（Asia/Shanghai）。状态与结论：**BLOCKED**。

本次完成仓库预检及已授权的最小规则修正。用户任务正文 §1.1 明确规定：若 artifacts/raw_data 内存在已跟踪文件，暂停算法开发并报告。实际索引中 raw_data 有 **6 个跟踪项（5 个 CSV 和 1 个 .gitkeep）**，因此没有进入 Python 项目搭建、依赖安装、CWT 开发或合成实验。该结论是前置条件阻断，不是对 CWT 科学有效性的否定。

## 目标、路径、输入与输出

- 原目标：Python 3.12 复 Morlet CWT 内核与合成 PDV 验证；本轮实际执行范围止于用户规定的前置门槛。
- 允许写入：本仓库内已批准的目录；仓库外仅指定 Obsidian Markdown 摘要。已检查写入目标及既有祖先，未发现重解析点。
- 禁止操作：读取、哈希或修改真实 raw；访问/修改 Production 和兄弟项目；修改 Git 索引/历史/remote；创建其他一级目录；开始 TASK-CWT-002。
- 输入：用户 TASK 正文、AGENTS.md、docs/RESEARCH_PLAN.md、docs/TASK-CWT-000_REPORT.md、.gitignore、scripts/cwt_env.ps1 及本仓库 Git 元数据。上述指定文件已完整阅读。
- 输出：最小目录规则和日志文字修正、本报告、artifacts/TASK-CWT-001/ 内的预检证据及同一篇 Obsidian 轻量摘要。
- 科学单位合同仍为 s、V、Hz、m/s、m；本轮没有波形输入或数值测量，单位验证未执行。
- 验收条件：独立仓库/分支正确；两目录全部普通内容默认忽略、当前均无跟踪项；不全局忽略 CSV；边界与记录可审查。
- 已知未知：CWT 误差、归一化偏差、边缘误差、噪声行为、80,000 点性能/内存全部 NOT MEASURED；Python 和工具安装状态未核验。

## 仓库核验与初始状态

本机实际状态优先于旧报告和规划文字：

| 项目 | 实际结果 |
| --- | --- |
| 根目录 | D:\Code\Python_Projects\DPS_Studio_CWT |
| 分支 | research/cwt-morlet |
| HEAD（前后不变） | 2ab657d0d39602e5ffdbbc0183a8571720f6fdd6 |
| origin fetch/push | https://github.com/zhaofeiisfading-sudo/DPS_Studio_CWT.git |
| git-dir / common-dir | .git / .git，独立目录 |
| worktree | 仅本仓库一个 checkout |
| superproject | 无输出，未识别为子模块 |
| 初始 git status --short / diff / staged diff | 均无输出，工作树与暂存区干净 |
| Git | 2.54.0.windows.1 |
| 实测 PowerShell | 7.6.5；未使用 Windows PowerShell 5.1 |

初始诊断先保存至 preflight_initial.json，再修改文本规则。未运行 git init、切换分支、commit、push、reset、clean、merge、rebase 或索引取消跟踪命令。未联网检查远程文件或历史；本报告不对远程原始数据状态作判断。

## 决定性阻断及最小修正

任务规定的三条命令均实际执行：

```powershell
git check-ignore -v --no-index -- artifacts/__probe__.json raw_data/__probe__.csv
git ls-files -- artifacts raw_data
git status --short --ignored -- artifacts raw_data
```

初始 artifacts 探针匹配 .gitignore 的 /artifacts/；raw_data CSV 探针无忽略匹配。索引元数据显示以下跟踪项（未打开对应数据文件）：

```text
raw_data/.gitkeep
raw_data/20260607.csv
raw_data/20260630-1.csv
raw_data/20260630-2.csv
raw_data/20260701.csv
raw_data/ch3.csv
```

已完成的授权修改：

- .gitignore 末尾增量追加 /raw_data/，保留已有 /artifacts/，没有添加全局 *.csv。
- AGENTS.md 的一级目录树和说明中增加用户批准的 raw_data/；明确其严格只读、永久忽略，并区分可丢弃缓存与持久 artifacts。未放松科学或 Git 规则。
- docs/RESEARCH_PLAN.md 仅协调三处日志要求为“同一篇轻量摘要，在关键里程碑更新”；未替换规划、调整算法或更改文献。

忽略规则对未来普通未跟踪内容生效，**不会将已跟踪文件移出索引**。现有 6 项原样保留。没有擅自执行 git rm --cached 或删除本地文件。

规划中的文献未在本任务核验：其状态在本轮为 **unverified**，保留规划原文不构成验证。旧规划中有关目录/Git 初始化等描述由当前任务与 AGENTS 的限制约束，未据此执行任何初始化。

## 实际验收与未运行项

| 检查 | 命令或方法 | 结果 |
| --- | --- | --- |
| artifacts/raw_data 目录忽略 | git check-ignore -v --no-index -- <假想路径>，JSON/CSV/DAT/TXT/PNG 共 9 项 | 9 PASS / 0 FAIL，均命中目录级规则 |
| CSV fixture 可跟踪 | tests、benchmarks、configs 各一个假想 CSV 路径，同上 | 3 PASS / 0 FAIL，exit 1 表示未忽略，符合预期 |
| artifacts 跟踪项 | git ls-files -- artifacts | 0，PASS |
| raw_data 跟踪项 | git ls-files -- raw_data | 6，FAIL；前置门槛未通过 |
| 文本空白检查 | git diff --check | exit 0，PASS |
| 暂存区未变 | git diff --cached --exit-code | exit 0，无输出，PASS |
| pytest | 计划命令 pytest | NOT RUN：前置阻断，未创建 Python 项目或安装依赖 |
| Ruff | 计划命令 ruff check . | NOT RUN：同上 |
| mypy | 计划命令 mypy --strict src tests benchmarks | NOT RUN：同上 |

探针仅是传入 Git 的假想路径，没有在 raw_data 或其他目录创建探针文件。所有终端检查使用 PowerShell 7。后续验收显式请求了稳定版 pwsh 别名路径，但返回的实测进程仍是工具运行时的 7.6.5，记录实际进程路径于 preflight_final.json，不援引旧报告的 7.6.9 结果。

未调用 Python、包管理器、pytest、Ruff、mypy 或 benchmark，因而没有加载缓存脚本后运行上述工具的步骤；没有借用 TASK-CWT-000 的测试结果作为本任务结果。未创建 venv、pyproject.toml、算法、测试、实验配置或性能图。

拍频 RMSE/MAE、表观速度 RMSE、coverage、尺度选择偏差、边界误差、运行时间、峰值内存、80,000 点内存可行性：全部 **NOT MEASURED**。没有生成科学 metrics.csv 或 figures，manifest 明确记录这些产物未生成；不能将本轮 12 项 Git 忽略规则检查当成科学正确性测试。

## 交付、Git 差异和边界

最终版本控制范围：修改 .gitignore（+3）、AGENTS.md（+2）、docs/RESEARCH_PLAN.md（+3/-3）；新增本报告并保持未跟踪。原有 TASK-CWT-000 文件未修改，暂存区为空。已有 core.autocrlf 导致 LF/CRLF 提示，不是检查失败；未修改 Git 配置。

```text
 M .gitignore
 M AGENTS.md
 M docs/RESEARCH_PLAN.md
?? docs/TASK-CWT-001_REPORT.md
```

机器证据目录：artifacts/TASK-CWT-001/，包含：

- preflight_initial.json：修改前仓库状态、忽略规则和索引证据。
- preflight_final.json：9 个目录探针、3 个 fixture 探针、仍未通过的索引门槛及实测工具版本。
- manifest.json：本任务范围、阻断、未执行科学实验与工具检查。
- git_delivery.json：交付时分支、HEAD、remote、status、diff 与忽略检查。
- review.diff：已跟踪三文件差异及新增报告的审查补丁，不改变索引。

.local_cache/ 与 artifacts/ 保持忽略；本任务产物没有索引项。raw_data/ 新增目录保护，但上述 6 个已有跟踪项仍受 Git 跟踪。真实 raw 未直接读取、未哈希、未修改或复制；SHA-256 前后检查 **NOT RUN（本任务禁止且无真实数据读取）**。Production 与兄弟项目未访问或修改。未创建其他一级目录、临时缓存或外部实验文件。

Obsidian 摘要实际路径：D:\Research\Notes\05项目\DPS_Studio_CWT\2026-10-29_TASK-CWT-001_最小CWT内核.md。已先创建 IN PROGRESS stub，交付时更新同一文件为 BLOCKED；详细证据只保存在本仓库。

## 唯一建议

先取得针对上述 6 个跟踪项的明确授权，在保留本地文件的前提下处理索引跟踪；复检两目录跟踪数均为 0 后，继续尚未完成的 TASK-CWT-001。本轮没有足够证据提出 TASK-CWT-002 的科学参数建议，不自动进入下一任务。
