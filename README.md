# DPS_Studio_CWT
Independent research on continuous wavelet transform (CWT) for photonic Doppler velocimetry (PDV) signal analysis.

TASK-CWT-002 提供 Python 3.12 复 Morlet 科研内核与可复现合成实验。
初始方法为 `cmor1.5-1.0` + PyWavelets FFT CWT；频段0.1–6 GHz、24 voices/octave、
积分精度18。配置是研究起点，尚未证明优于STFT或适用于真实实验数据。

在本仓库的 PowerShell 7 中，每次调用 Python/工具前加载缓存脚本：

```powershell
. .\scripts\cwt_env.ps1
# 解释器与依赖仅安装于 .local_cache/；不得使用全局环境。
& .local_cache/venv/Scripts/python.exe -m pytest -q
& .local_cache/venv/Scripts/python.exe -m ruff check .
& .local_cache/venv/Scripts/python.exe -m mypy --strict src tests benchmarks
& .local_cache/venv/Scripts/python.exe -m benchmarks.run_benchmark
# 再对新run执行数学/汇总审计（替换为实际目录）
& .local_cache/venv/Scripts/python.exe -m benchmarks.audit_math artifacts/TASK-CWT-002/run_...
```

首次搭建时在加载上述脚本后，以已安装Python 3.12创建 `.local_cache/venv/`，
用 `uv pip install --python .local_cache/venv/Scripts/python.exe -e '.[dev]'` 安装。
本轮另将Python 3.12解释器本体放在 `.local_cache/python/`；精确环境见任务产物中的
`environment_lock.txt`。任何后续依赖安装仍须遵守AGENTS授权和缓存边界。

```python
from pdv_cwt import SampledSignal, compute_cwt, strongest_candidate, diagnose, apparent_velocity

signal = SampledSignal(time_s, voltage_v)  # 显式秒、伏；不均匀采样拒绝
result = compute_cwt(signal)              # 分配完整矩阵前检查内存预算
candidate = strongest_candidate(result)   # 默认raw；逐时刻保留候选
quality = diagnose(result, candidate)     # 未提供噪声sigma：UNKNOWN
velocity = apparent_velocity(candidate.frequency_hz,
                             wavelength_m=1550e-9, zero_optical_offset=True)
```

`scale_amplitude` 是显式候选选项，表示 `abs(W)/sqrt(scale)`；它改善部分单频标定，
也会恶化低SNR白噪声下的频率选择。所有候选与质量分开；已知白高斯噪声sigma时的
保守质量阈值也不等同于物理信号验证。尤其sigma=0无法排除脉冲外的泄漏/舍入响应。
表观速度无符号，必须显式提供波长并声明零光学偏置，不含角度或LiF修正。

协议见 `docs/TASK-CWT-002_PROTOCOL.md`，详细结论见 `docs/TASK-CWT-002_REPORT.md`。
`artifacts/TASK-CWT-002/` 保存合成信号/真值、指标、图件、环境与审计记录；
`raw_data/` 永久忽略且只读。上述合成 benchmark 不读取真实数据，不开发GUI或执行STFT比较。

TASK-CWT-003 增加显式 TOML 映射的真实数据批处理后端：

```powershell
. .\scripts\cwt_env.ps1
# 审计全部文件；不计算 CWT。
& .local_cache/venv/Scripts/python.exe -m pdv_cwt.batch --config configs/real_batch.toml --audit-only
# 全量、逐通道、独立进程；每次创建新 run，不覆盖旧结果。
& .local_cache/venv/Scripts/python.exe -m pdv_cwt.batch --config configs/real_batch.toml
# 独立核验本批真实数据 CSV 与保存的 CWT 显示矩阵（替换实际目录）。
& .local_cache/venv/Scripts/python.exe scripts/audit_cwt003_outputs.py artifacts/TASK-CWT-003/real_runs/run_...
```

`configs/real_batch.toml` 逐文件记录零起始列索引、分隔符、表头行数及单位依据。
本批 10 个数据文件的 s/V 和原始波形属性由用户在任务聊天中明确确认；列名只表示列号。
CSV/DAT 文本 Reader 支持明确配置的逗号、分号、制表符或空白分隔，以及多通道和 SI 转换。
未知单位、缺失/非法值和不均匀采样均明确报错，不删点、重采样或修复；文件/通道失败隔离。
完整 CWT 分配前检查显式预算及可用 RAM，超预算报 FAILED_RESOURCE，不偷偷抽短波形。

所有成功通道保存 `cwt_scalogram.png`、`metadata.json`、`analysis_status.json`、
全样点 `candidate_velocity.csv`、诊断图和明确抽列的 `display_response.npz`。
完整复系数矩阵在计算时保留于 RAM，不永久保存；CSV 保留全部样点，显示抽列不改变候选。
未知波长/光学偏置时状态为 SCALOGRAM_ONLY，CSV 速度栏为空；此状态仍包含候选频率和诊断。
无显式噪声模型时质量为 UNKNOWN / NOT_EVALUATED，通过率为空，不能解释为零通过率或无信号。
批次根目录同时提供 `file_summary.csv`（文件分母）、`batch_summary.csv`（通道分母）、
`batch_manifest.json` 和 `batch_status.md`；每个文件包括 NOT_RAW 占位项均列入清单。
正式结果和限制见 `docs/TASK-CWT-003_REPORT.md`。真实速度、方向、噪声可靠性均未认证。
