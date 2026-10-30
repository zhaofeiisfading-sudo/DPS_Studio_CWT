# TASK-CWT-003 — 全量真实 PDV 数据 CWT 后端

日期：2026-10-30（Asia/Shanghai）。状态：COMPLETED。科学 verdict：**LIMITED**。

全量覆盖 Level A：PASS；CWT 图覆盖 Level B：PASS。扫描 11 个文件，其中 10 个经用户确认的原始波形文件、1 个 Git 占位文件；14/14 个电压通道均完成全记录 CWT、时频图、逐样点候选频率 CSV 和独立诊断，失败 0、未尝试 0。Level C 为 LIMITED：本批全部通道缺少波长及零光学偏置依据，均为 SCALOGRAM_ONLY，真实速度换算 0/14。有限候选输出率 100% 是算法的输出合同，不能证明信号存在或支路正确。

本报告没有真实 RMSE、真实支路正确率或 CWT 优于 STFT 的结论。没有 STFT 比较、GUI、其他算法、轨迹修复、LiF/角度校正或 Production 迁移。

## 授权、输入与实现

仓库为独立 `D:\Code\Python_Projects\DPS_Studio_CWT`，分支 `research/cwt-morlet`。初始工作树、暂存区均为空，与 TASK-002 旧报告中的暂存状态不同；本任务不恢复或改动旧索引状态。允许范围、单位、验收和已知未知见 `docs/TASK-CWT-003_PROTOCOL.md`。

用户在本次聊天中明确确认：**10 个数值文件均为原始 PDV 波形，首列时间 s，其余列为独立电压 V；波长和光学偏置暂未知**。这是单位与原始属性的来源，文件自身均无表头，不能从数值量级独立核验单位。逐文件配置 `configs/real_batch.toml` 保存此来源；voltage_col1/2 仅代表零起始列索引 1/2，不推断物理通道用途、仪器型号或实验条件。

新增 `src/pdv_cwt/{safety,mapping,readers,resources,export,pipeline,batch}.py`。已有 CWT、candidate、diagnostics、physics 内核未改动。Reader 支持显式分隔符、表头行数、编码、列映射、SI 转换和多通道；按流审计，读取时先检查预算和 SHA-256，再构造 SampledSignal。空行、缺失/非法值、重复/倒序/不均匀时间轴明确拒绝，不删除、插补或重采样。单通道按新进程顺序运行，异常不会中断其余文件；CWT 图先于候选与速度导出，后续失败保留成功图件。

本次没有复制 raw 波形到 tests、快照或其他目录。源代码快照只保存 Python/TOML；图像及候选均为派生产物。文件写入限定在既有根目录，检查并拒绝链接或 junction；缓存环境逐会话先加载本仓库 `scripts/cwt_env.ps1`。

## 全量文件审计

包含子目录与隐藏文件的遍历实际得到 11 个文件，本批没有子目录。原始目录总大小 32,086,814 字节，包含 3 字节的 `.gitkeep`。5 个 DAT 均经用户确认是原始波形，实际结构为逗号分隔数值文本；没有 result DAT。后端仍强制排除 result DAT，合成反例已测试。

所有波形无空行、无非法数值、无非有限值，列宽一致，原始时间轴通过既有 1e-6 相对采样间隔容差检查。下表采样率由真实时间列计算，40/80 GS/s 为显示舍入，metadata 保留全精度。

| 文件 | 数据行×列 | 通道 | 采样率 GS/s | 记录跨度 μs | CWT 图 | 分类/最终状态 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| .gitkeep | 0 | 0 | — | — | — | NOT_RAW：Git 占位 |
| 20201210m.dat | 40000×2 | 1 | 40 | 0.999975 | 1/1 | 原始；ANALYZED |
| 20201211m.dat | 40000×2 | 1 | 40 | 0.999975 | 1/1 | 原始；ANALYZED |
| 20201214m.dat | 40000×2 | 1 | 40 | 0.999975 | 1/1 | 原始；ANALYZED |
| 20221017a.dat | 80000×2 | 1 | 80 | 0.9999875 | 1/1 | 原始；ANALYZED |
| 20231019-ch1.dat | 80000×2 | 1 | 80 | 0.9999875 | 1/1 | 原始；ANALYZED |
| 20260607.csv | 80000×3 | 2 | 40 | 1.999975 | 2/2 | 原始；ANALYZED |
| 20260630-1.csv | 200001×3 | 2 | 40 | 5.000000 | 2/2 | 原始；ANALYZED |
| 20260630-2.csv | 80000×3 | 2 | 40 | 1.999975 | 2/2 | 原始；ANALYZED |
| 20260701.csv | 80000×3 | 2 | 40 | 1.999975 | 2/2 | 原始；ANALYZED |
| ch3.csv | 80000×2 | 1 | 40 | 1.999975 | 1/1 | 原始；ANALYZED |

文件级 ANALYZED 表示其全部映射通道已生成图，不能与通道级完整速度状态混用。14 个通道全部为 SCALOGRAM_ONLY，全部有候选和诊断 CSV；完整速度输出为 0，没有无法计算 CWT 的原始文件。本批没有 NEEDS_MAPPING、NEEDS_METADATA、UNSUPPORTED_FORMAT 或 FAILED_RESOURCE 文件；这些后端状态及异常分支用合成 fixture 验证。

完整原始路径、扩展名、字节数、SHA-256、各列统计、映射来源及状态保存在批次的 `input_inventory_before.json`、`input_inventory.json`、`input_inventory.csv`、`file_summary.csv`。采样起止时刻、逐通道运行条件保存在 `batch_summary.csv`、manifest 和各通道 metadata，未使用虚构时间轴。

## 变换、图件及单位合同

全通道配置固定：`cmor1.5-1.0`，`pywt.cwt(method="fft", precision=18)`，0.1–6 GHz，24 voices/octave，含精确高端点，共 143 尺度；默认 raw `abs(W)`。40 GS/s 下尺度约 400–6.6667；80 GS/s 下约 800–13.3333。尺度通过 `scale2frequency / dt` 与引擎频率交叉核对。全部频段低于各自 Nyquist，所用连续 Morlet Nyquist 尾能量检查未超 1e-6；不能据此声称不存在所有离散数值伪影。

本次没有为单个文件改频段、响应、尺度密度或精度。未做归一化分支实验、连续性修复或物理速度拟合。raw 的跨尺度幅值偏好仍存在，TASK-002 的已知偏差与失败模式不能因真实图件可见而忽略。网格间距不是双频分辨力。

输入时间 s、电压 V；候选 Hz；缺失速度栏为空，不填 0。仅当配置同时提供有依据的 wavelength_m 和 zero_optical_offset=True，才计算 `v_app = wavelength_m * f_b / 2`。本批不满足条件，未输出 velocity_time.png；改为 candidate_frequency_time.png。正频候选不提供运动方向，也不代表已验证真实界面速度。

每个通道的原始 40k/80k/200001 个样点均参与完整 complex128 CWT 与 raw strongest。矩阵在 RAM 内保留用于分析，不永久落盘。每张时频图显示最多 2400 列：40k 每 17 列选一列，80k 每 34 列，200001 每 84 列，并显式补首尾，实际 2354/2354/2382 列。抽列不平均、不改变完整候选；短瞬态的峰值可能被显示抽列漏过，这属于显示限制。显示列和样点索引保存在 display_response.npz，图件并非合成数据或其他时频算法。

横坐标为相对首样点时间 μs，注明原始 t0（s）；纵坐标 GHz；色标为离散样点尺度约定下 raw abs(W)，单位 V、线性显示。每图 vmin=0，vmax 为其保存显示矩阵最大值；不同通道色标上限不同，不能直接按颜色跨通道比较幅值。原始绝对时间完整保留于 CSV。cyan 阴影表示整个频率库共同有限支撑风险，半径 `ceil(8*scale)+2`；所选尺度风险另外逐样点保存。

14 张 scalogram、14 张 quality_diagnostics、14 张 candidate_frequency_time 均保存。全部 scalogram 通过总览目视核验，重点单独查看 20260607 与 ch3 的大图及 ch3 诊断图；坐标、色标与低响应区域保留。原图 1980×900，未为了图像更亮而换算法。

## 逐通道结果与资源

以下 CWT 时间只包括变换调用；流水线时间包括读取、CWT、绘图、NPZ、候选 CSV 和诊断，未包含进程启动/全部导入。进程峰值为 Windows GetProcessMemoryInfo / PeakWorkingSetSize，包含该独立 worker 生命周期的导入和绘图；不是 Python-only 值，也不是主进程加 worker 的总和。

| 文件 | 电压列（零起始） | 样点 | CWT 秒 | 流水线秒 | 峰值 MiB | 全库边缘风险 % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 20201210m.dat | 1 | 40000 | 1.3116 | 3.7157 | 289.516 | 16.0100 |
| 20201211m.dat | 1 | 40000 | 1.3774 | 3.7969 | 289.664 | 16.0100 |
| 20201214m.dat | 1 | 40000 | 1.2769 | 3.6291 | 290.098 | 16.0150 |
| 20221017a.dat | 1 | 80000 | 2.8970 | 6.0920 | 464.789 | 16.0050 |
| 20231019-ch1.dat | 1 | 80000 | 2.7656 | 5.7119 | 464.902 | 16.0050 |
| 20260607.csv | 1 | 80000 | 2.7629 | 5.7399 | 464.816 | 8.0075 |
| 20260607.csv | 2 | 80000 | 2.9029 | 5.8894 | 464.828 | 8.0075 |
| 20260630-1.csv | 1 | 200001 | 5.8473 | 10.9117 | 991.684 | 3.2020 |
| 20260630-1.csv | 2 | 200001 | 5.6665 | 10.4260 | 991.684 | 3.2020 |
| 20260630-2.csv | 1 | 80000 | 2.5454 | 5.5410 | 464.938 | 8.0050 |
| 20260630-2.csv | 2 | 80000 | 2.9219 | 5.8750 | 465.027 | 8.0050 |
| 20260701.csv | 1 | 80000 | 2.9020 | 5.8917 | 464.844 | 8.0050 |
| 20260701.csv | 2 | 80000 | 2.9420 | 5.9213 | 464.836 | 8.0050 |
| ch3.csv | 1 | 80000 | 2.9037 | 6.1068 | 464.773 | 8.0075 |

全通道候选输出率均为 100%，质量 UNKNOWN 比例均为 100%，质量通过率均为 null / NOT EVALUATED，所选尺度 alias flag 均为 0。微小边缘比例差异来自实际 dt 的浮点映射与 ceil，未人为统一原始时间轴。

最大文件完整系数矩阵为 457,602,288 字节，规划工作内存 1,471,700,816 字节（约 1.371 GiB），超过旧 768 MiB 配置。因此本批预先明确设定 2 GiB 规划预算，同时要求不超 worker 计算前可用物理 RAM 的 70%；未修改已有 core 的默认预算。最大实测峰值 1,039,855,616 字节（991.684 MiB）。14 个 worker 顺序执行，全部完整计算，无分块、无降采样、无缩短时间区间。未实现分块引擎，故分块一致性为 NOT RUN / NOT APPLICABLE。

整批用时 128.1437 秒，包含全量审计、子进程启动、CWT、导出及批次末哈希核验，不包括之后的独立导出审计、总览生成和回归测试。数据为单次运行，未提供置信区间或跨硬件推广。OS 可见物理 RAM 为 16,385,748,992 字节，Windows 11、AMD64 Family 25 Model 117 Stepping 2、16 逻辑处理器；未从旧报告冒认具体设备型号。

## 谱观察与物理解读边界

**实际结果：** 20260607 两通道在相对首样点约 0.7 μs 后出现明显低频谱带，随后向低频变化。为描述图件，事后选择 0.75–1.25 μs 区间；两通道候选中位数均为 0.712719 GHz，20,000 样点各自 5%–95% 分位数都落在同一格点。该区间 raw 响应中位数分别 0.246774 和 0.691930 V；0–0.6 μs 区间分别仅约 0.001335 和 0.002460 V。稳定格点和谱支持可以复核，不能从这些量直接认定两通道对应同一物理界面、真实速度或无限频率精度。

**实际结果：** ch3 图中较强响应局限在短时区间，可见高频带、较低频带与宽带竖向结构。事后 1.08–1.30 μs 区间候选 5%–95% 为约 1.307–4.032 GHz，raw 响应中位数 0.033333 V；0–1.0 μs 区间响应中位数约 0.001255 V，但仍持续输出候选，其相邻跳变超过 0.5 GHz 的比例为 3.6175%。全记录该跳变比例 3.2675%。这些是逐样点诊断，不是已知噪声假阳性率，更不能认定跳变就是错误或将较平滑区域认证为正确支路。

**目视观察：** 20260630-1/2、20260701 的两个通道均存在局部较强低频带及后段变化；几个较早 DAT 存在更高频带、瞬态宽带结构或接近 6 GHz 上边界的响应。本次没有把弱线、暗背景或多支路的图丢弃，也没有扩大频段来追随预期。0.1–6 GHz 外的谱不在本任务的观察范围。

上述窗口仅用于事后描述，**不用于重新调参、计算准确率、估计噪声 sigma、自动分割信号或更改候选**。精确数值与窗口定义保存在 `descriptive_observations.json`。raw 尺度响应偏好、背景噪声、支路竞争与有限支撑都可能影响 strongest；这是模型解释，尚不能分解各因素对真实实验误差的贡献。没有 ground truth，RMSE、支路正确率、信号存在误报率为 NOT MEASURED。

## 质量诊断及工程限制

没有明确的独立白高斯噪声 sigma，本批不估算噪声、不默认 sigma=0。噪声模型 UNKNOWN，质量状态 NOT_EVALUATED，quality_result UNKNOWN；内部 passed=False 不导出为物理失败，不把 null 通过率写成 0%。候选频率在诊断前后逐项不变。14 条记录仍全时刻输出候选，强响应外的杂乱轨迹证实了必须分离“候选存在”和“真实信号存在”；不能声称 TASK-002 的脉冲外误报已经解决。

主要限制为：缺少光学/实验元数据及独立真值；raw 跨尺度偏好未校正；质量没有可验证噪声模型；固定频段外未分析；仅时间显示抽列可能漏过瞬态峰值；内存估算为规划值而非分配器硬上界；RAM 峰值仅 Windows 原生测量，其他平台明确 NOT MEASURED；输入文本预算 512 MiB、Reader 规划预算 256 MiB、每通道超时 900 秒，超限记录资源失败。本次没有大于 200001 点的真实验证，不能推广到任意大小。完整复系数未永久保存，复核其他响应需要按保存配置重算，不能用 display NPZ 冒充全部时间矩阵。

## 验收与独立审计

本轮新增 19 项（含参数化）合成 fixture 检查，原有 46 项全部保留。覆盖递归扫描、CSV/DAT、明确分隔符/表头、多通道、SI 单位、未知单位拒绝、异常采样/缺失值拒绝、result DAT 排除、单文件失败隔离、Reader→CWT→图件、独立通道输出、无光学参数 SCALOGRAM_ONLY、候选与质量分离、CSV/metadata、预算拒绝、source 仅 r/rb 打开及 SHA-256，以及注入候选失败时保留成功图件。fixture 全为生成的合成文本，不取真实 raw。

独立脚本 `scripts/audit_cwt003_outputs.py` 核验 **14 通道、1,240,002 行 CSV**：时间逐点与重新只读加载的原始时间轴精确相等；尺度/频率与 metadata 网格一致；逐点边缘标志符合支撑半径；未知质量、空速度/阈值表达一致；所有保存的显示列与真实 CWT raw strongest 及峰值响应精确一致。结果 PASS，仅验证数据/计算/导出一致性，不验证物理真值。总览及审计结果均另存，不覆盖原图。

每次工具会话先运行 `. .\scripts\cwt_env.ps1`，使用 `.local_cache/venv/Scripts/python.exe`，实际命令与最终结果：

```powershell
& .local_cache/venv/Scripts/python.exe -m pytest -q
# 65 passed in 25.41s
& .local_cache/venv/Scripts/python.exe -m ruff check .
# All checks passed!
& .local_cache/venv/Scripts/python.exe -m mypy --strict src tests benchmarks
# Success: no issues found in 22 source files
& .local_cache/venv/Scripts/python.exe -m mypy --strict scripts/audit_cwt003_outputs.py
# Success: no issues found in 1 source file
git diff --check
git diff --cached --check
# 均 exit 0
```

PyWavelets 1.10.0、NumPy 2.5.4、SciPy 1.18.1、Matplotlib 3.11.2、pytest 9.2.0、Ruff 0.17.3、mypy 2.4.1；Python 3.12.15。完整发行包清单在 `environment_inventory.txt/json`，PowerShell 版本另存。初轮 63 项测试通过，新增只读打开/后续失败保图两项后最终 65 项通过。开发中曾有 Ruff 行长和测试 helper 类型标注错误，已修复；不是把初轮标为全部通过。

`python -m pip freeze` 失败：本地 venv 没有 pip。没有因此安装依赖；已用只读 `importlib.metadata.distributions()` 取得完整发行包清单。`environment_freeze_note.txt` 记录原因，早先生成的空 environment_lock.txt 不是有效锁文件。本轮未安装全局或本地依赖。

## 产物索引与复现

本轮最终真实运行目录（下文 R）：

`artifacts/TASK-CWT-003/real_runs/run_20261030_143512_d623e95b/`

R 根下：`input_inventory*.json/csv`、`file_summary.csv`、`batch_summary.csv`、`batch_manifest.json`、`batch_status.md`、`raw_hashes_after.json`、`output_audit.json`、`descriptive_observations.json`、`all_scalograms_overview.png`、source_snapshot 与逐通道进度/控制台记录。先行仅审计的运行 `run_20261030_143217_1de8217f` 完整保留，不能把它的零 CWT 数量与最终结果混用。

每个文件的通道位于 `R/channels/file_<相对路径哈希前缀>_<输入SHA前缀>/voltage_colN/`。准确相对目录列在 batch_summary.csv 的 output_path，避免同名子目录文件相互覆盖。每通道保存：cwt_scalogram.png、display_response.npz、metadata.json、analysis_status.json、candidate_velocity.csv、candidate_frequency_time.png、quality_diagnostics.png。worker request/stdout/stderr 留在通道父目录。本批 stderr 均为空。

`artifacts/TASK-CWT-003/` 根另保存任务起止 raw SHA-256、原始输入完整性、环境、测试输出、Git 检查、source_consistency、最终交付索引和审查 diff。14 个通道运行时核心源文件的哈希与交付时全部一致；研究结果可绑定到源码快照。

```powershell
. .\scripts\cwt_env.ps1
& .local_cache/venv/Scripts/python.exe -m pdv_cwt.batch --config configs/real_batch.toml
# 输出新的 run，不覆盖旧目录。随后对新 run 运行真实数据导出一致性审计：
& .local_cache/venv/Scripts/python.exe scripts/audit_cwt003_outputs.py artifacts/TASK-CWT-003/real_runs/run_...
```

审计脚本针对本批“全部未知 optics/noise”的合同；后续提供真实光学或噪声参数后，应相应更新审计合同，不能将本次 UNKNOWN 检查直接用于已知参数批次。

## Git、raw、日志与停止边界

任务开始/最终全量比较：**11/11 文件路径、大小、SHA-256 全部一致**，总计 32,086,814 字节。批次自身及逐通道读取前后、独立导出审计亦核验输入 SHA-256；最终完整性证据为 `raw_hashes_before.json`、`raw_hashes_final.json`、`raw_integrity_final.json`。没有修改、覆盖、移动、删除或复制 raw，也没有访问 Production 或其他 Research。

分支仍为 research/cwt-morlet，origin fetch/push 仍为 `https://github.com/zhaofeiisfading-sudo/DPS_Studio_CWT.git`。没有 commit、push、pull、merge、rebase、reset、clean、改 remote 或改索引。raw_data 和 artifacts 的 `git ls-files` 均为空；raw_data、artifacts、.local_cache 均被现有 .gitignore 忽略。旧源码、测试、配置及其他 TASK 产物保持原样。

交付差异为 README 增量修改及 12 个新文本/代码文件（7 个后端模块、1 个测试、1 个配置、1 个审计脚本、协议和本报告），均未暂存；无暂存差异。普通 git diff 仅展示 README，新文件另汇入 `review.diff`，不通过 git add 改索引。完整状态见 git_delivery.json。

Obsidian 轻量摘要实际更新于：

`D:\Research\Notes\05项目\DPS_Studio_CWT\2026-10-30_TASK-CWT-003_真实PDV后端.md`

文献性能论断未在本任务重新核验，旧计划引用不作为本报告科学结论的依据。下一步建议人工审查全部图件和映射，补充波长、光学参考偏置、通道用途及独立噪声/实验记录，再另行授权验证速度与质量模型。本任务到此停止，不自动启动 TASK-CWT-004。
