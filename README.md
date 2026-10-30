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
`raw_data/` 永久忽略且只读。任务脚本不读取真实数据，不开发GUI或执行STFT比较。
