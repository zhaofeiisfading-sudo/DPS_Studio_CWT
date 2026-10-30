# TASK-CWT-002 — Git 安全收尾与复 Morlet CWT 科研内核

日期：2026-10-29（Asia/Shanghai）。状态：**COMPLETED**；科学 verdict：**LIMITED**。

Git 取消跟踪、Python 3.12 科研包、S1–S6 合成实验、80,000 点完整计算和代码检查已完成。预注册的13项频率误差检查通过，单元/失败模式测试46项通过。结论仅支持此初始配置在指定合成条件下的数学一致性和部分频率标定能力；低SNR、脉冲存在性判别及真实数据有效性仍有限制。**不支持“CWT已经优于STFT”或“已经获得经实验验证的真实速度”这类结论。**

本轮没有开发GUI、开展STFT正式比较、处理真实波形、自动提交或启动TASK-CWT-003。旧TASK-CWT-001的BLOCKED记录保留原样。

## 范围、输入及交付

允许代码/产物写入根目录为 `D:\Code\Python_Projects\DPS_Studio_CWT`；仓库外仅指定Obsidian Markdown轻量摘要。既有一级目录未重组，新增根文件只有 `pyproject.toml`。Production、既有Research及兄弟项目未访问或修改。raw仅按本次授权读取字节以计算SHA-256，未解析、复制、预处理或修改。

输入为当前仓库规范/规划/旧报告和合成time_s/voltage_v；内部SI为s、V、Hz、m/s、m、rad。所有误差都来自保存的合成ground truth，非真实实验测量。验收与已知未知见 `docs/TASK-CWT-002_PROTOCOL.md`；本次用户的新任务范围优先于旧规划中TASK-002的STFT对比安排。

主要新增路径：

- `src/pdv_cwt/{models,frequency,transform,physics,diagnostics,synthetic,__init__}.py`及`py.typed`。
- `tests/test_core.py`；`configs/cwt_v1.toml`、`configs/task_cwt002.toml`。
- `benchmarks/{run_benchmark,performance,metrics,system_info,audit_math,__init__}.py`。
- `pyproject.toml`、本报告、实验协议；README增量加入复现步骤与限制。

主要接口：`SampledSignal(time_s, voltage_v)`、`CWTConfig`、`make_frequency_grid`、`estimate_memory`、`compute_cwt`、`strongest_candidate`、`diagnose`、`apparent_velocity`、`synthetic_pdv`。核心不导入GUI或Matplotlib；Matplotlib只在合成实验中采用Agg输出文件。

## Git与raw安全结果

初始根目录经`git rev-parse --show-toplevel`核验正确；git-dir/common-dir均为本仓库`.git`目录，仅一个工作树，非Production worktree或子模块。初始工作树和暂存区干净。

分支前后均为 `research/cwt-morlet`；HEAD前后均为 `23d60e744dbc66a7525cc0c92d28932c56866f5f`。origin fetch/push均为 `https://github.com/zhaofeiisfading-sudo/DPS_Studio_CWT.git`。未执行fetch/pull/merge/rebase/push，未核验或同步用户提到的远程删除提交。

`.gitignore`原来已包含`/raw_data/`、`/artifacts/`、`/.local_cache/`，因此无需重复修改。未添加全局CSV/JSON/PNG忽略规则。三项假想fixture路径不被忽略；没有创建raw探针文件。

按明确授权只执行一次 `git rm --cached -r -- raw_data`，解除5个CSV和1个`.gitkeep`的索引跟踪。两个目录`git ls-files -- raw_data`及`git ls-files -- artifacts`最终均为空。本地raw目录内**11个文件、32,086,814字节**，执行前、取消索引后和任务末尾三次SHA-256一致，文件均存在。这里仅核验字节完整性，不据文件所在目录认定其都是原始波形。

对应证据：`preflight_initial.json`、`git_safety_repair.json`、`raw_sha256_before.json`、`raw_sha256_after_index.json`、`raw_sha256_final.json`。取消跟踪显示为6项已暂存删除；这是索引变化，本地文件未删除，已有Git历史未改。

最终Git差异：README为未暂存修改；源码、测试、配置、pyproject及本轮两个文档保持未跟踪；只有上述6个raw索引删除被暂存。`AGENTS.md`、研究规划、TASK-000/001报告、`.gitignore`和既有环境脚本均未修改。`.local_cache/`、`artifacts/`、`raw_data/`被忽略。完整状态及文本审查补丁在`git_delivery.json`、`review.diff`；审查补丁不包含raw内容，也不将新代码加入索引。

## 数学方法与质量合同

使用已安装并核验源码的PyWavelets 1.10.0：`pywt.cwt(..., method="fft", precision=18)`；固定研究母小波`cmor1.5-1.0`。输入实电压向量，输出complex128矩阵，第一轴为尺度，第二轴与原始时间样点逐一对应。尺度经`frequency2scale(wavelet, f*dt, precision=18)`生成，并用`scale2frequency/dt`及引擎返回频率交叉核对。API、小波定义和离散小尺度混叠说明依据[PyWavelets官方CWT文档](https://pywavelets.readthedocs.io/en/latest/ref/cwt.html)。本任务未重新核验旧规划的论文引用，其状态为unverified，未据其作性能断言。

分析频率0.1–6 GHz，24 voices/octave，额外补入精确6 GHz端点，共143尺度；40 GS/s下尺度约400至6.6667。以下是研究起点，未证明是最优配置。保留所有输入样点，无重采样、滤波、平滑、插值、亚格点精修或连续性修复。

输入检查维度、数值类型、长度≥4、有限性、时间严格递增及等间隔；相对采样间隔容差1e-6，同时检查时间原点造成的浮点可辨识性。模型持有独立只读副本，不改变调用者数组。明显不均匀采样明确拒绝。

离散输出W采用PyWavelets的样点尺度约定，尺度无量纲，系数随输入电压计量；若换为连续时间尺度下的积分CWT，还需乘`sqrt(dt)`，本项目不混用两种幅值。默认响应为`abs(W)`；显式实验响应为`abs(W)/sqrt(a)`，两者候选及原始模值分别保存。平峰取最低频率格点；纯噪声和零信号仍保留候选。

本任务的连续近似推导：对`A*cos(2*pi*f*t+phi)`，忽略负频尾和数值离散时，模值约为

`A*sqrt(a)/2 * exp[-pi² B (a*f*dt-C)²]`，B=1.5、C=1。

raw最强尺度对应的估计频率约为真值的0.983660倍，存在约−1.634%的连续尺度选择偏差；尺度归一化去掉`sqrt(a)`因子，不能同时保证白噪声下仍有利。24 voices/octave的最近格点误差理论上界约1.4545%，不包含上述选择偏差。1 GHz处母小波功率谱FWHM的连续近似约306 MHz，时间功率包络FWHM约1.442 ns；29 MHz量级的网格间距不等于真实双频分辨力。FFT补零用于线性卷积与计算效率，不增加物理分辨率。

表观速度由显式`wavelength_m`和`zero_optical_offset=True`计算`v_app=lambda0*f_b/2`，验证1550 nm及1 GHz得到775 m/s。实信号的正频候选只支持无符号、零光学偏置假设下的表观速度；没有推断方向、真实激光波长、LiF或角度条件。

边缘半径为`ceil(8*a)+2`样点，既保存所选尺度污染标志，又保存整个频率库的保守污染标志。常规16384点的共同内部为9980点、60.9131%，两端共39.0869%标记风险；8192点低频chirp仅21.8262%属于共同内部。浮点ceil使80k案例最大半径3203点，质量可用内部73594点。边缘标志表示可能受未知延拓影响，不表示每个被标记点都有实际误差。

Candidate与Quality完全分离。没有显式噪声sigma时，noise model为UNKNOWN，passed=False表示未得到该质量判据支持。若提供已知独立零均值白高斯电压噪声sigma，按实际离散滤波器能量E_a使用

`T_a = sigma*sqrt(4*E_a*ln(4*M*N/alpha))`，alpha=0.01。

这是将复系数的实/虚部高斯尾与全记录MN次联合界结合的保守筛查，不要求CWT系数独立；通过还要求整个库内部及所选尺度没有混叠风险。该假设不覆盖有色噪声、未知sigma、脉冲跨时窗混合或浮点误差，也不是可靠物理信号的认证。

## 数值精度修正与离散滤波器审计

运行前协议v1采用precision=14。首轮已完整保留于`run_20261029_154712_218881/`，含源码快照。独立滤波器审计发现仅检查连续谱Nyquist尾不足以检出大尺度积分采样伪影，遂作v2精度修正。尺度400的负频能量比例：

| 积分precision | 负频能量比例 | 滤波器能量 |
| --- | ---: | ---: |
| 14 | 1.799581% | 0.3379773 |
| 16 | 0.085834% | 0.3262946 |
| 18（最终） | 0.001118% | 0.3257357 |

这项选择基于不使用目标轨迹真值的数值核收敛实验；没有更换波形、频段、种子、默认raw响应或放宽频率验收阈值。`precision_convergence.json`保留定量证据，最终完整S1–S6和80k重新运行。噪声滤波能量计算复用同一次积分小波，避免重复构造大型积分网格。

小尺度默认保护依据连续Morlet谱在Nyquist外能量比例，容忍度1e-6；超限即使中心频率低于Nyquist仍拒绝。尺度1、2的实际离散频谱呈明显折叠；尺度3也会被该保护拒绝。`filter_audit.csv`另外保存实际滤波器FFT、负频能量、Nyquist/主峰功率比等。连续尾界不是完全无离散伪影的证明；不能把不同来源的负频能量全部解释为同一种混叠。

初始单元测试45过/1失败：曾错误要求宽脉冲包络最高点离中心≤2样点；实测最大4点、能量质心最大偏移0.511点，FFT和直接conv仍一致。保留`initial_validation.json`，改为质心≤1点检验裁剪/时间轴并继续保留直接卷积测试。未删除失败模式覆盖或放宽频率指标。首轮Ruff的行长问题及随后审计脚本类型/格式问题均修复，日志保留。

## 合成输入与定量结果

最终运行目录：

`artifacts/TASK-CWT-002/run_20261029_155407_996145/`

共25个case ID、50行指标，每个case分别评价raw与尺度归一化；S1和S4中的1 GHz条件重复，不算独立重复证据。信号/真值/相位/active保存在NPZ，候选、阈值和全部质量标志另存NPZ；`provenance.json`记录生成配方及little-endian float64数组SHA-256。常规采样40 GS/s、N=16384、幅度1 V、相位0.37 rad；这是代表性合成条件，非真实仪器参数。

SNR定义为`10*log10((A²/2)/sigma²)`，用标称正弦功率，不是事后由有限记录拟合。S2与S6 evaluation种子101/202/303；S6另用1/2/3做独立校准核验，未拟合阈值。同种子在不同SNR间复用同一标准高斯序列，跨SNR条件并非独立样本。

所有误差默认使用已知active且位于整个库共同内部的样点，**没有按质量通过筛选以美化RMSE**。metrics中all表示全部有定义真值的样点；脉冲门外和纯噪声没有拍频真值，误差为null，绝不填0。

| 条件 | raw内部RMSE (MHz) | 归一化内部RMSE (MHz) | 归一化速度RMSE (m/s) | 归一化质量通过率（全记录） |
| --- | ---: | ---: | ---: | ---: |
| S1：1 GHz无噪声 | 20.7572 | 7.93684 | 6.15105 | 60.9131% |
| S2：20 dB，3种子合并 | 20.7572 | 7.93684 | 6.15105 | 60.9131% |
| S2：0 dB，3种子合并 | 20.8206 | 15.0584 | 11.6702 | 2.15047% |
| S2：−10 dB，3种子合并 | 644.967 | 2850.174 | 2208.885 | 0% |
| S3：0.5→4 GHz线性chirp | 42.5166 | 19.2883 | 14.9484 | 60.9131% |
| S3：0.15→2 GHz低频相对快速chirp | 19.6670 | 8.93076 | 6.92134 | 21.8262% |
| S5：中心20 ns脉冲，门内 | 20.2555 | 13.6151 | 10.5517 | 60.9131%（含门外误报） |
| S6：纯噪声，3个evaluation种子 | 无真值 | 无真值 | 无真值 | 0% |

S2合并RMSE为三个等样本数case的平方误差合并后开方。归一化0 dB各种子RMSE为14.558–15.723 MHz，种子间样本标准差0.603 MHz；−10 dB为2.720–2.944 GHz，样本标准差0.116 GHz。三个种子不能支持强泛化结论。

S1归一化内部MAE=7.93684 MHz、bias=+7.93684 MHz；raw bias=−20.7572 MHz。这不是随机统计不确定度，而主要是固定格点与响应选择偏差。

S3用解析积分相位`phi=phi0+2*pi*(f0*t+0.5*k*t²)`生成，未拼接正弦。两例k分别8.54544e15和9.03431e15 Hz/s，后者主要是低起始频率造成相对变化更快。慢chirp归一化内部MAE=16.1069 MHz、bias=+0.431683 MHz；raw bias=−36.5341 MHz。事后1/2/3 GHz首次越过时差，raw约+1.164/+2.318/+3.096 ns，归一化约−0.761/−1.532/−2.704 ns，包含格点和尺度偏差，不能认定为因果延迟或实时算法响应时间。

边缘与内部比较（归一化RMSE，MHz）：S1为8.41083 vs 7.93684；慢chirp为23.6292 vs 19.2883；低频chirp为12.6537 vs 8.93076。各条件完整all/edge/interior RMSE、MAE、bias、速度误差和耗时均在metrics.csv，不能将个别边缘点较准确解释为没有边缘风险。

### S4：等电压幅度的尺度偏差

| 恒频 (GHz) | raw bias (MHz) | 归一化bias (MHz) | raw平均响应 | 归一化平均响应 |
| --- | ---: | ---: | ---: | ---: |
| 0.2 | −5.69361 | 0 | 7.08301 | 0.499979 |
| 0.5 | −10.3786 | +3.96842 | 4.48817 | 0.499413 |
| 1 | −20.7572 | +7.93684 | 3.17117 | 0.499028 |
| 2 | −41.5143 | +15.8737 | 2.23544 | 0.497489 |
| 5 | −64.9254 | −64.9254 | 1.38363 | 0.486001 |

响应单位按本离散约定为V。raw最大/最小响应比5.11915，归一化后为1.02876，支持去除主要sqrt(scale)振幅偏好。5 GHz残余约2.8%的相对幅值变化与离散积分/差分传递函数及格点失配相容；这是模型解释，没有据此加入经验增益校正。0.2 GHz误差为0只是恰好落在格点，不能推成无限频率分辨率。

归一化在−10 dB的内部RMSE是raw的4.419倍。白噪声原始CWT能量随尺度约为常量，除sqrt(a)会增强小尺度相对噪声响应；这与观察到的高频误选相容。该反例足以否定“归一化在所有场景均更好”，所以默认保持raw。

### S5：短时瞬态及质量失效

两条20 ns、1 GHz矩形门脉冲分别位于2–22 ns和190–210 ns。边缘脉冲的有效门内全被共同边缘掩码标记，内部RMSE为null；其门内边缘RMSE为13.6151 MHz，与中心脉冲内部误差相同。该特例在记录外真实为零、相位匹配，零延拓不制造额外差异，说明风险掩码是保守边界，不能据此否定一般边缘污染。

半个已知输入幅度作为离线阈值时，两例onset偏差均+50 ps（2个采样间隔）。只适用这个已知幅度、相位和矩形门样例，未建立泛化起跳检测或50 ps时间分辨率。

**重要负结果：sigma=0的正响应判据不能可靠判断脉冲存在。** 边缘脉冲门内质量通过率0%，但全记录质量通过率60.9131%，完全来自门外；门外误报率64.0400%。中心脉冲门内通过率100%，门外误报率58.9066%。跨窗泄漏、非严格零均值母小波和极小舍入响应都可能留下非零系数。候选完整保留，未偷偷阈值、裁剪或修复；当前质量通过必须理解为特定筛查条件通过，不能等同于可靠物理信号。

### S6：纯噪声与异常输入

三条evaluation纯噪声记录及三条独立calibration记录，raw/归一化有限候选输出率均100%，已知sigma=1 V的质量通过率和实测误报率均0%。这是有限样本结果，非“真实噪声零误报”的证明；CWT各时刻相关，不能把数万个样点当作独立Bernoulli试验。噪声频率/速度误差没有真值，记录null。

异常输入由46项测试中的参数化反例覆盖：不均匀、重复、倒序和巨大原点时间，维度/长度不符，非有限/复数/布尔输入，非法波长/频段/配置，Nyquist内仍有混叠风险的尺度，以及预算不足时必须在引擎调用前拒绝。未提供sigma时明确UNKNOWN；零输入平峰候选不作为存在信号证据。

## 80,000点资源可行性

环境为Windows 11、AMD Ryzen 7 H 255（8核/16逻辑线程）、OS可见物理内存16,385,748,992字节；硬件信息保存在hardware.json。以下为单次新进程测量，无统计置信区间，不代表所有真实记录：

| 项目 | 最终precision=18实测/估算 |
| --- | ---: |
| 采样/频段/尺度 | 80,000点；40 GS/s；0.1–6 GHz；143尺度 |
| 系数矩阵 | complex128，143×80,000，183,040,000字节（174.561 MiB） |
| 分配前规划内存 | 609,510,144字节（581.274 MiB） |
| 配置预算 | 768 MiB |
| 分配前可用物理内存 | 5,128,105,984字节，另要求估算≤其70% |
| FFT CWT耗时 | 3.02802 s |
| CWT+两种候选提取及诊断 | 3.32724 s |
| 独立worker生命周期峰值工作集 | 434,540,544字节（414.410 MiB） |
| 有限候选数/每种响应 | 80,000（100%） |
| 质量通过数/每种响应 | 73,594（91.9925%） |

未分块、未改变输入采样率或指定频段。计时不含启动/导入、造数、NPZ压缩及绘图；峰值用Windows原生GetProcessMemoryInfo的PeakWorkingSetSize，包含worker导入及其整个先前生命周期。它不是Python-only tracemalloc值，也不是主进程+worker或整机总峰值；其他平台探针会明确NOT MEASURED。估算采用3份复矩阵、12个FFT缓冲、样点缓冲及积分网格余量，是规划值，不保证所有分配器/库版本的硬上界。

首轮precision=14曾用2.08879 s、415.016 MiB；最终采用18以降低数值伪影，不能引用较快首轮时间冒充最终配置性能。最终完整25-case实验（含文件输出、绘图和80k子进程）共43.2871 s。

## 软件环境与真实检查结果

Python 3.12.15解释器本体及venv分别位于`.local_cache/python/`、`.local_cache/venv/`。原系统Python为3.9.1，未修改。通过uv在上述本地路径安装，无全局依赖安装、无额外一级目录、无仓库克隆。临时文件、包缓存、字节码、pytest、Ruff、mypy和Matplotlib均先由本仓库环境脚本定向到`.local_cache/`。

NumPy 2.5.4；SciPy 1.18.1；PyWavelets 1.10.0；Matplotlib 3.11.2；pytest 9.2.0；Ruff 0.17.3；mypy 2.4.1；实测PowerShell Core 7.6.5。完整依赖冻结记录在environment_lock.txt。hatchling仅用于本地标准包构建；未添加其他科学算法依赖。PyWavelets/SciPy缺失类型声明的导入配置ignore_missing_imports；自身源码/测试/benchmark仍按strict检查，并用实际返回形状、频率映射和数值对照验证第三方边界。

每个工具会话均先执行`. .\scripts\cwt_env.ps1`。最终准确命令与结果：

```powershell
. .\scripts\cwt_env.ps1
& .local_cache/venv/Scripts/python.exe -m pytest -q
# 46 passed in 10.31s
& .local_cache/venv/Scripts/python.exe -m ruff check .
# All checks passed!
& .local_cache/venv/Scripts/python.exe -m mypy --strict src tests benchmarks
# Success: no issues found in 14 source files
git diff --check
git diff --cached --check
# 两项exit 0
```

最终原始输出保存在final_validation.json及final_pytest/ruff/mypy.txt。单元测试、解析物理换算、FFT/独立直接conv一致性、单位脉冲能量以及合成频率13项验收分别有代码和机器证据；不是把“运行无异常”当成科学正确性。

复现合成实验命令：

```powershell
. .\scripts\cwt_env.ps1
& .local_cache/venv/Scripts/python.exe -m benchmarks.run_benchmark
& .local_cache/venv/Scripts/python.exe -m benchmarks.audit_math artifacts/TASK-CWT-002/<新run目录>
```

运行自动新建目录，不覆盖旧产物。最终run的manifest保存变换时的源码/配置哈希；其后仅audit_math.py说明文字换行，不改变核心及结果，最终交付manifest另记录源码哈希及该差异。绘图使用显示抽列，完整指标和候选不抽样。图件已查看，单位和分析频段可读；图例中噪声的ground truth为空，不能据其strongest轨迹作物理解释。

## 产物索引与最终边界

`artifacts/TASK-CWT-002/manifest.json`为交付总索引；根metrics.csv为最终运行指标的便捷副本。详细结果位于最终run：manifest.json、metrics.csv/json、experiment_parameters.json、provenance.json、scientific_assessment.json、filter_audit.csv、performance_80000.json、signals/、candidates/和7幅PNG。首轮run、初始失败、精度收敛和全部检查输出均保留，无实验产物清理。

Obsidian轻量日志实际路径：

`D:\Research\Notes\05项目\DPS_Studio_CWT\2026-10-29_TASK-CWT-002_复Morlet小波内核开发.md`

详细方法和证据留在本仓库，Obsidian只保存简短索引。Git/raw/Production边界完成复核；未提交、推送或处理远程历史。待审查的新代码均未暂存，只有授权的raw索引删除处于暂存区。

## 下一步建议

另行授权后，优先验证未知/有色噪声下的独立质量模型和脉冲外误报，扩大固定seed与多支路反例；冻结CWT响应/边缘政策后，再按相同输入、频段、时间与误报约束进行固定Hann-STFT strongest对照。真实数据分析、真实速度结论及Production迁移仍需独立授权与实验支持。本TASK到此停止。
