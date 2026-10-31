# CWT Research 复现与恢复说明

基准日期2026-10-31；只适用于本独立仓库当前研究阶段。科学结论、数据限制和环境疑点必须随结果一同恢复，不能只保留获益图。

## 环境与缓存

工作目录为 `D:\Code\Python_Projects\DPS_Studio_CWT`，预期分支 `research/cwt-morlet`。每次PowerShell 7会话必须先执行以下环境脚本；不要依赖IDE继承变量。该脚本同时检查仓库根与reparse路径，所有Python、Matplotlib、pytest、Ruff、mypy、pip/uv及临时缓存均位于 `.local_cache/`。

```powershell
Set-Location -LiteralPath 'D:\Code\Python_Projects\DPS_Studio_CWT'
. .\scripts\cwt_env.ps1
& .local_cache/venv/Scripts/python.exe -m pytest
& .local_cache/venv/Scripts/python.exe -m ruff check .
& .local_cache/venv/Scripts/python.exe -m mypy --strict src tests benchmarks
git diff --check
git diff --cached --check
```

当前解释器为Python3.12.15，venv在 `.local_cache/venv/`，解释器本体在 `.local_cache/python/`。发行metadata记录NumPy2.5.4、SciPy1.18.1、PyWavelets1.10.0、Matplotlib3.11.2、pytest9.2.0、Ruff0.17.3、mypy2.4.1。完整清单位于TASK006的 `environment_audit.json`；这些是本机观测，不是对公共包源可获取性的保证。venv无pip的历史问题保留，不因 `pip freeze` 不可用而安装依赖；用 `importlib.metadata.distributions()` 获取实际发行清单。

PyWavelets模块报告1.8.0，发行metadata报告1.10.0。实际 `pywt.cwt` 签名为 `(data, scales, wavelet, sampling_period=1.0, method='conv', axis=-1, *, precision=12)`。文件为 `.local_cache/venv/Lib/site-packages/pywt/_cwt.py`，SHA-256为 `2bdfe87b0a326e51fbcf7f444276097c1179d42c29130619eadda4984073036b`。函数文本SHA-256为 `9f511adf3441251a52c179ad4d4bddb463234f4f9fa74e392d0effc41d5388e9`，二者哈希对象不同，不能直接比较。文件哈希匹配TASK005，函数文本哈希匹配TASK002。

生成的 `version.py` 和实际源码均与已安装RECORD匹配，没有发现路径覆盖或第二个对应dist-info。该检查不认证RECORD或wheel来源，构建时为何带入旧版本号仍为UNKNOWN。`runtime_snapshot/` 保存实际PyWavelets的Python源码、扩展与metadata；它不是完整离线环境镜像，不含NumPy/SciPy的全部运行二进制，不能承诺在另一机器只凭版本号得到同一环境。禁止为修正显示而自动升级、重装或降级；可信来源重建应另行授权并在隔离环境验证，保留当前基准环境和历史结果。

## 代码入口与固定参数

| 功能 | 入口或配置 |
| --- | --- |
| SI输入及均匀采样验证 | `src/pdv_cwt/models.py` |
| 尺度映射、原始strongest | `src/pdv_cwt/frequency.py` |
| 唯一CWT计算引擎 | `src/pdv_cwt/transform.py` |
| 质量、边界和离散核 | `src/pdv_cwt/diagnostics.py` |
| 显式表观速度 | `src/pdv_cwt/physics.py` |
| 真实映射与后端 | `configs/real_batch.toml`、`src/pdv_cwt/batch.py` |
| 固定STFT对照 | `benchmarks/comparison/core.py` |
| TASK005生成/评分/统计 | `benchmarks/validation/{cases,scoring,run,summarize}.py` |
| TASK006独立审计 | `benchmarks/closure_audit.py`、`tests/test_closure_audit.py` |

主CWT为cmor1.5-1.0、FFT、precision18、0.1—6 GHz、24 voices/octave；grid补充48/96。正式STFT为Hann L768/512、hop128、NFFT4096；物理窗补充80 GS/s使用L1536/1024、hop256、NFFT8192，CWT也用对应子网格。配置TOML与注册表均须保存。TASK005运行器的许多数值实际冻结在Python源码常量中，TOML主要作声明索引，不应误认为只修改TOML即可改变全部实验；复现时同时校验源码、TOML和运行注册表。

## 持久结果与来源关系

| TASK | 正式证据目录 | 恢复关键内容 |
| --- | --- | --- |
| 002 | `artifacts/TASK-CWT-002/run_20261029_155407_996145/` | signals、candidates、metrics、manifest、滤波核和80k性能；首轮precision14负结果亦保留 |
| 003 | `artifacts/TASK-CWT-003/real_runs/run_20261030_143512_d623e95b/` | 输入清单、映射、14通道状态、完整候选CSV、显示NPZ、源码快照 |
| 004 | `artifacts/TASK-CWT-004/run_20261030_165336_eef69e3e/` | 三方法真实native/common、156合成波形及指标、配置快照、独立直接FFT证据 |
| 005 | `artifacts/TASK-CWT-005/run_20261030_221635_70d83adf/` | split_registry、独立校准、development冻结、1840条held-out预测/真值/配方、grid、14真实通道、性能 |
| 006 | `artifacts/TASK-CWT-006/` | 环境审计、独立指标、配对CI/GO、12波形重跑、图复验、完整SHA索引与边界证据 |

TASK005每个 `evaluation/<case>_v24/common.npz` 保存共同时间、原始样点索引、active、interior、truth、interference和各方法prediction/support；`recipe.json` 保存种子、输入哈希和生成参数。没有永久保存所有完整复系数，真实 `display_response.npz` 或common谱不能冒充全部native系数矩阵。需要其他评分的全矩阵时须按原输入重新变换。

**仅有Git仓库不足以恢复完整研究结果，必须另外保留artifacts。** TASK006的final_manifest索引TASK002—005的11732个历史文件及当前源码/报告/证据，历史总量1,565,612,446字节；不包含raw内容、Git对象库或缓存。原始数据只在另行授权的位置由用户保管，不加入Git，也不因归档而复制或公开。原始SHA清单只是关联与完整性凭证，不是数据副本。

## 独立指标重算与代表性算法重跑

直接在既有TASK006目录重复执行写入动作会因独占创建而拒绝覆盖。以下用一个此前不存在的TASK006子目录保存新证据；将日期后缀改成实际未使用的名称。算法和指标入口都只读历史正式结果。

```powershell
. .\scripts\cwt_env.ps1
& .local_cache/venv/Scripts/python.exe -m benchmarks.closure_audit arithmetic --output-dir artifacts/TASK-CWT-006/recheck_example
& .local_cache/venv/Scripts/python.exe -m benchmarks.closure_audit supplemental --output-dir artifacts/TASK-CWT-006/recheck_example
& .local_cache/venv/Scripts/python.exe -m benchmarks.closure_audit probes --output-dir artifacts/TASK-CWT-006/recheck_example
```

`arithmetic` 从保存数组重算RMSE、MAE、bias、灾难和支路指标，核对完整注册表和CSV索引；`supplemental` 进一步核对表值、校准阈值、源码及性能记录；`probes` 重造12条预定波形，执行16次CWT和两STFT，检查输入哈希、候选精确相等及CWT响应幅值。纯噪声候选仍输出，频率误差无真值。重跑不是全1840条的独立算法复现；原校准也没有全部重新生成。

对误差向量 $e_i=\hat f_i-f_i$，计算 $\mathrm{RMSE}=\sqrt{\sum e_i^2/N}$、$\mathrm{MAE}=\sum|e_i|/N$、bias=$\sum e_i/N$。每条波形先在其明确掩码上计算，随后跨波形等权配对。事件区域、全共同内部和物理窗子网格须分别处理，不能直接混合帧。配对bootstrap seed=810000、10000次；95%为描述区间，GO使用97.5%双侧区间和原近零基线规则，另查每波形bias、灾难率及50倍成本上限。

若只验证归档字节，无需读取真实波形：

```powershell
. .\scripts\cwt_env.ps1
& .local_cache/venv/Scripts/python.exe -m benchmarks.closure_audit verify
```

manifest以仓库相对路径保存大小和SHA-256，不给自身建立循环哈希。验证只能证明与本次清单一致，不能单独认证历史结果在生成时从未被修改。新增审计和历史快照/原始日志一起构成溯源证据。完整大规模重跑入口分别为 `benchmarks.run_benchmark`、`benchmarks.comparison.run`、`benchmarks.validation.run`，均产生新run；本任务没有执行这些全量重跑。真实后端命令会读取raw，后续必须另有明确授权、起止全量哈希与所需光学/单位来源，不能因本文列出入口就视为已授权。

## Git状态、恢复边界与未解决问题

TASK006开始HEAD为 `adc6f198dcba5766da456d4b516380d93d3b14fd`，工作树和暂存区干净。TASK006新增文档、审计模块和测试未提交；查看 `git_delivery.json`、`review.diff` 与final_manifest中的source_state，不能只用HEAD描述当前交付。TASK002历史源码以LF记录，部分当前文件为CRLF；应分别保存字节哈希与换行规范化后的比较结果，不把换行差异误判为算法变化，也不能未经核验忽略所有哈希差异。

`raw_data/`、`artifacts/`、`.local_cache/`继续忽略，索引中均无文件；小型测试CSV未全局忽略。检查当前忽略可用 `git check-ignore raw_data/.gitkeep artifacts/TASK-CWT-006/final_manifest.json .local_cache/venv/pyvenv.cfg`。一级目录冻结，禁止自动创建根venv或输出目录。Git历史仍有5个CSV及占位路径记录；本轮只查路径元数据，不读取历史blob、不清理历史、不访问远端。该风险治理与第三方包来源确认是后续可单独授权的维护事项。

其他科学限制为真实真值和光学条件缺失、未知实际噪声、有限参数及校准条件、局部事件与全记录表现不同、strongest无法识别指定弱目标、性能只测单设备单次。保留当前Research及负结果即可构成阶段结题；是否投入新瞬态诊断或环境治理应单独立项，禁止从本文自动继续执行。
