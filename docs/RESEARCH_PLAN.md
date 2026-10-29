# DPS Studio 独立研究线：复 Morlet 连续小波变换（CWT）

版本：规划 v1.1；日期：2026-10-29；状态：**GitHub 仓库与本地目录已由用户创建；CWT 代码及实验尚未执行，Git 分支仍须在本机核验**。

## 1. 唯一研究问题

在不修改 Production 或现有 TASK-021A Research 的前提下，验证**复 Morlet 连续小波变换（CWT）**相对经过合理调参的 Hann-STFT，能否提高 PDV **低速度、快速变速、短时瞬态**的频率/表观速度提取精度，并明确在哪些低信噪比和多支路条件下反而失效。

**唯一新时频分析法：CWT。** 不在此实验线实现 SST/WSST、Chirplet、Hilbert/Takeda 相位解调、Bayesian 推断、AI、Global Path、IMM/MHT、平滑后处理等新路线。STFT 仅可作为既有对照基线（可读取固定导出，或在 benchmarks 中保留纯粹的参考实现），不得成为新方法研发对象。

研究假设：H1：在特定低速、强加速度和冲击起跳数据中，CWT 自适应分析尺度可改善时频定位；H2：在纯噪声、弱信号和两支路竞争中，CWT 不保证优于 STFT，甚至可能更差。H1 和 H2 都需要以数据检验。

## 2. 研究边界

- Production：`D:\Code\Python_Projects\DPS_Studio`；原有 Research：`D:\Code\Python_Projects\DPS_Studio_TASK021A`，严格只读，不在其仓库添加算法。
- 新根目录：`D:\Code\Python_Projects\DPS_Studio_CWT`。建议**独立 Git 仓库**，初始实验分支 `research/cwt-morlet`，不共享旧仓库代码、历史或工作树。这样既有独立目录，也有独立研发分支；如后来明确要求继承 Git 历史，则另行重新设计。
- 新 Python 包：`pdv_cwt`；Python 3.12，NumPy、SciPy、PyWavelets、Matplotlib，pytest、Ruff、mypy strict。**不开发 GUI、不打包 exe、不写 Production 导出格式、不做 LiF/角度校正**。
- 不复制/覆盖/重命名原始数据。原始文件只从外部路径读取，生成前后检查 SHA-256；文件名含 `result` 的已处理 `.dat` 禁止作为 raw。
- 内部 SI：s、V、Hz、m/s。速度先只计算 `v_app = lambda_0 * f_b / 2`，不默认为任何数据是真实 1550 nm/0°/LiF 条件；由配置显式输入波长。无频偏单边频谱不给出运动方向，f=0 不可与低频背景无歧义区分。
- 不进行隐式重采样、单位猜测、插值、删点、平滑或 raw 替换。频带、列名、时间/电压单位需显式映射，时间轴非等间隔时报错并报告，而不是静默修正。
- `coverage-first`：保留 CWT 主候选频率/表观速度以及独立 `quality`、`edge_affected` 标记；不把低置信度等同于可确认的真实速度，也不以 NaN 拒绝策略作为算法创新。

## 3. 数学与实现合同

输入实值 `x(t)`，核心复 Morlet CWT：

`W_x(a,b) = 1/sqrt(a) * integral[x(t) * conj(psi((t-b)/a)) dt]`，约定连续时间和离散采样时的尺度与归一化分别注明。

V1 固定母小波为 `cmor1.5-1.0`（仅作为**初始预注册配置**，不是已知的最优参数）。**默认实现先采用 `pywt.cwt(..., method="fft")`**；从零编写的是软件架构、变换封装、频率标定、主峰提取、物理映射、测试和实验脚本，而不是盲目重造数值卷积库。将来确有性能问题，再在**同一 CWT 方法**下优化计算引擎，并使用 PyWavelets 做独立数值核对。

- 对于给定采样间隔 `dt`，使用库提供的 `pywt.scale2frequency(wavelet, scales) / dt` 检查尺度-频率映射；理论公式与实测合成单频标定须一致。不得将频率网格间距误当真实频率分辨率。
- 建议先用 **0.1–6.0 GHz** 预设范围（实际频段可根据明确实验条件覆盖），**24 voices/octave** 左右的对数频率网格作为初始建议。大约 140–150 个尺度，必须记录实际数量及端点；不是不可修改的物理常量。
- PyWavelets 的小波系数采用特定尺度归一化。不能直接假设不同尺度的 `abs(W)` 峰值可无偏比较。以**相同幅度、不同频率的合成单频**定量审计频率偏倚；例如验证 `abs(W)/sqrt(a)` 这样的尺度响应校正，而非不经测试就采用。记录处理前/后误差及对噪声的影响。
- 边界锥/有限小波支撑造成的 edge effect（边缘效应）必须随频率标记。建议同时提供 raw strongest candidate 和独立边缘有效性标志，不得隐瞒末端污染。
- 初始轨迹估计：**每时刻 CWT 响应最强的频率**，允许已明确验证的局部尺度亚网格精修，须单独报告提升；禁止将 Global Path/IMM/人工框选拼进算法，以免归因混乱。
- CWT 先计算时间轴（可在内存约束下分块）；用于统一比较的时刻下采样必须明确输出网格，且不得静默改变输入波形。
- 保存代码版本、库版本、随机种子、波长、采样率、频带、尺度列表、母小波参数、归一化约定、分析区域、CPU 时间、峰值内存和输入 SHA-256。

## 4. 项目建议结构

一次性目录初始化属于 TASK-CWT-000；根目录仅允许下列一级目录，所有临时缓存统一进入 `.local_cache/`，原始 PDV 数据不得复制进项目。

```text
DPS_Studio_CWT/
  README.md
  AGENTS.md
  .gitignore
  .local_cache/               # 临时缓存/虚拟环境，不进 Git
  pyproject.toml
  configs/cwt_v1.yaml
  src/pdv_cwt/
    __init__.py
    models.py                 # 原始时间/电压与显式元信息
    transform.py              # 唯一新方法：复 Morlet CWT
    frequency.py              # scales -> Hz 与直接 strongest
    physics.py                # 显式波长 -> apparent velocity
    diagnostics.py            # 质量/边界标记，不干预轨迹
  benchmarks/
    synthetic_cases.py        # 确定性造数与 ground truth
    reference_stft.py         # 仅用于 STFT 对照；不改进 STFT
    metrics.py
    run_benchmark.py
  tests/
    test_units.py
    test_single_tone.py
    test_chirp.py
    test_edge.py
    test_normalization.py
    test_raw_safety.py
  docs/
    RESEARCH_PLAN.md          # 本文档，单一规范版本
    pending_logs/             # Obsidian 写入失败时才使用
    RESEARCH_CHARTER.md
    DECISION_LOG.md
    LITERATURE.md
  scripts/
    cwt_env.ps1               # PowerShell 缓存隔离
  artifacts/                   # 保留研究产物，不进 Git；无 raw
```

## 5. 分阶段任务（不得自动连做）

### TASK-CWT-000：仓库规范与目录初始化

仅核验已克隆的独立 Git 仓库、预期分支、现有文件及远程地址；放置 `AGENTS.md`、`docs/RESEARCH_PLAN.md`、`scripts/cwt_env.ps1`，合并 `.gitignore` 排除项，创建上述允许的一级目录。确保废弃缓存只进入 `.local_cache/`，不进行算法实现、依赖安装、真实数据读取、commit 或 push。按 AGENTS.md §8 在同一篇 Obsidian 轻量 TASK 摘要中更新关键进度，详细证据保留在仓库 docs/ 和 artifacts/。

### TASK-CWT-001：独立仓库与最小可验证内核

创建独立文件夹/Git 实验分支，初始化 Python 包与依赖，写研究章程和配置文件；仅使用合成信号，完成复 Morlet CWT、频率标定、直接 strongest、表观速度换算、边界标记、单频/啁啾/单位/不均匀采样/尺度归一化测试；输出一组可复现诊断图与 `manifest.json`。**本任务不接触任何真实数据，不做 GUI，不建多算法框架。**

验收：单频与线性 chirp 的频率/速度映射可与解析真值比对；无混淆的 SI 单位；`pytest`、`ruff`、`mypy --strict` 运行有据；`git status` 与 diff 可审查；无 Production/raw 修改。

### TASK-CWT-002：锁定合成数据基准

数据类型至少：恒频、低速快速线性 chirp、急跳/上升沿、双支路交叉、强干扰/弱目标、暂时衰落、仅有噪声或错误背景强线、短持续脉冲。固定 SNR/加速度/频率分布和多随机种子；训练/校准集与 held-out 集分离，后者不得用来调参。

比较：CWT strongest vs `frame-wise STFT strongest`，包括原 Balanced `768/640/128/4096`、High Time `512/384/128/4096`（window/overlap/hop/nfft）与一组**预注册、合理调优**的 STFT 固定窗口对照。使用相同 raw、同样频带、可对齐的评价时刻、同样波长和边界处理；不以更密的 CWT 输出时刻冒充提高了真实时间分辨率。

指标：频率 RMSE、速度 RMSE、速度跃迁/起跳定位误差、wrong-branch rate、coverage、虚假目标标记率、对反例的 harm、计算时间、峰值内存，以及带随机种子和不确定度的统计结果。数据作图不能代替数值判决。

### TASK-CWT-003：真实数据盲对照

在冻结主要 CWT 参数后再分析：`20260607.csv`（若可访问、已核实列与单位的 PDV 两通道）；`ch1.csv`～`ch4.csv`，重点 `ch3.csv`。`data/raw/PDV数据-质量中等` 可作为补充。对真实数据**不宣称存在 ground truth**。

报告：CWT/STFT 图与轨迹在同一实际时间/频率尺度上的差异、局部多峰候选、修改/偏移区域、信号支持强度、连续性/跳变、纯噪声假峰、可视化边界、运行时资源；人工诊断不等于真实性证明。对 `ch3` 这类 smooth wrong branch 问题，不以曲线更顺滑作为成功。

### TASK-CWT-004：Go/No-Go 结论

合成 held-out 测试上，建议预注册以下**研究决策门槛，而非声称已达成的结果**：

1. 目标短时/低速强加速度组：相对合理调参 STFT 的 RMSE 至少下降 10%，且在独立随机种子重复中稳定；或者事先选定的起跳时刻误差明显下降并提供不确定度。
2. 纯噪声假阳性、错误支路、低 SNR 组的性能不得产生无法接受的退化；若准确性与虚警权衡，必须在相同误报约束下比较。
3. 同一台机器上 80k 样本/约 140–150 尺度的峰值内存优先控制在约 1 GiB 内；记录 CWT/STFT 运行时间比，并评估 GUI 可接受性。这些是工程目标，须实测，不是已知性能。
4. 真实数据至少存在可解释、可重复、可由原始谱支持的局部改善证据，不能靠视觉光滑宣称获胜。

若只有少数样例漂亮、整体 held-out 不改善，判定 `NOT SUPPORTED` 并**停止这一方法线**；不得自动转做 SST、相位法或其他方法。只有通过独立验证，未来才另立 promotion 任务；本项目不自动迁移到 Production。

## 6. Git、日志、可复现性

**GitHub 仓库已由用户创建并在本地克隆：禁止重新 `git init`、修改 remote、自动 commit/push。** 每个 TASK 必须核验本机 `git rev-parse --show-toplevel`、`git branch --show-current`、`git status --short` 和 `git remote -v`。目标分支为 `research/cwt-morlet`；如未处于该分支，先报告并等待用户明确授权切换。

每一 TASK **从开始时**就在 `D:\Research\Notes\05项目\DPS_Studio_CWT` 创建一篇 IN PROGRESS 轻量摘要，并在关键里程碑和完成时更新同一文件；按 AGENTS.md §8 通常保持 15–30 行、约 500 中文字以内。TASK-CWT-001 文件名为 `YYYY-MM-DD_TASK-CWT-001_最小CWT内核.md`，仅记录日期、分支、状态、verdict、主要路径、1–3 项关键结果、验收与 Git/raw/Production 边界、未解决问题及下一步；不写逐步骤流水账。完整方法与证据保留在 docs/ 和 artifacts/，日志不是 source of truth。每一 TASK 不得在交付后自动推进下一 TASK。

## 7. 已核对的基础文献

- Liu S. et al., *Analysis of photonic Doppler velocimetry data based on the continuous wavelet transform*, Rev. Sci. Instrum. **82**, 023103 (2011). DOI: 10.1063/1.3534011.
- Song H. et al., *Measurement of fast-changing low velocities by photonic Doppler velocimetry*, Rev. Sci. Instrum. **83**, 073301 (2012). DOI: 10.1063/1.4731014.
- Devlaminck J. et al., *Digital signal processing for velocity measurements in dynamical material's behaviour studies*, Rev. Sci. Instrum. **85**, 035109 (2014). DOI: 10.1063/1.4866683.
- Yang Y. et al., *Research on demodulation method for instantaneous signal based on Photonic Doppler velocimetry*, Optics and Lasers in Engineering **194**, 109164 (2025). DOI: 10.1016/j.optlaseng.2025.109164. **混合 STFT/CWT 方法，不能算纯 CWT 的实验结果。**
- PyWavelets CWT API 与尺度/单位文档：https://pywavelets.readthedocs.io/en/latest/ref/cwt.html

## 8. 首次投递 Codex 的 TASK-CWT-001 Prompt

```text
TASK-CWT-001 — 独立 Morlet-CWT PDV Research 初始化与最小正确内核

目标：在已存在的 D:\Code\Python_Projects\DPS_Studio_CWT 独立 Git 仓库中开发 Python 3.12 Research 项目，用复 Morlet 连续小波变换（CWT）提取单通道合成 PDV 拍频与表观速度。唯一研究新方法是 CWT。本 TASK 不进行真实数据性能比较，不改现有 DPS Studio。

开始前：检查目标目录是否已存在及内容；确认 Production D:\Code\Python_Projects\DPS_Studio 和旧 Research D:\Code\Python_Projects\DPS_Studio_TASK021A 的 git status/branch（只能查看），不要覆盖它们；如新目录非空且归属不明则停止并报告，不擅自删除。仓库已经 clone；严禁再次 `git init` 或修改 remote。确认当前分支为 research/cwt-morlet；若不匹配先停止并报告；不 commit/push。

允许：在 TASK-CWT-000 已冻结的一级目录结构内新增 pyproject、配置、src/pdv_cwt、tests、docs、benchmarks、scripts、artifacts（产物不纳入 Git）；不得再增加一级目录。使用 NumPy/SciPy/PyWavelets/pytest/Ruff/mypy strict/Matplotlib；采用 pywt.cwt(..., method="fft") 作为初版数值引擎。原创实现输入模型、严格 SI/均匀采样检查、尺度→Hz、主峰频率提取、v_app=lambda0*f/2、边界影响诊断、可重复合成测试和结果导出。

禁止：创建其它一级目录或根目录缓存；修改/复制/覆盖 raw、修改 Production 或既有 Research、引入 STFT 之外的其他新方法、SST/Chirplet/相位法/Global Path/IMM/AI、写 GUI、接入 LiF/角度修正、隐式重采样/平滑/插值/删点、默认推断波长与单位、自动推进 TASK-CWT-002、commit/push。

初始 CWT 配置预注册：复 Morlet cmor1.5-1.0；建议 0.1–6 GHz 和 24 voices/octave；显式记录 scales、frequency_hz、time_s、wavelet、参数、库版本。测试单频与线性 chirp 的频率准确性、恒幅多频点下的尺度响应偏倚与候选校正、边界影响、低信号/纯噪声的诊断行为、不均匀采样拒绝、1550 nm 仅在明确输入时 1 GHz -> 775 m/s。将 CWT 频率网格间距与真实分辨力严格区分。实际输出频率范围不得越过采样 Nyquist，避免小尺度离散混叠。

开始 Python/pytest/ruff/mypy 前在同一 PowerShell 会话执行 `. .\scripts\cwt_env.ps1`，并确保 venv 在 `.local_cache/venv`。所有临时缓存不得散落根目录。

产物：源代码、测试、配置、实验章程、docs/DECISION_LOG.md、artifacts/task_cwt001/ 下可复现实验 CSV/PNG/manifest.json，记录运行环境、git status/diff、pytest、ruff、mypy --strict 的真实输出。不能凭文字声称测试通过；失败也记录。

从开始时创建 IN PROGRESS Obsidian 轻量摘要，在关键里程碑和完成时更新 D:\Research\Notes\05项目\DPS_Studio_CWT\YYYY-MM-DD_TASK-CWT-001_最小CWT内核.md 同一文件，通常 15–30 行、约 500 中文字以内；简述 task/date/branch/status/verdict/artifact、完成内容、主要修改路径、1–3 项关键结果、测试、Git/raw/Production 边界、未解决问题和下一步建议，不写执行流水账。完整技术报告与证据留在仓库 docs/ 和 artifacts/，日志不是 source of truth。只完成本 TASK 后停止，不做后续 TASK。
```
