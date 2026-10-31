# TASK-CWT-005 实施与审计说明

正式运行目录：artifacts/TASK-CWT-005/run_20261030_221635_70d83adf。

协议在任何本轮科学实验前创建；正式开始前补齐同物理8GHz带宽模型的独立噪声尺度校准，
因此 scoring calibration 为120条，threshold calibration 为240条；正式前协议和注册表一致。
主候选仅由16条 development 波形选择，在 held-out 开始前写出 candidate_frozen_before_evaluation.json。
冻结后未根据 held-out 修改评分、频带、voices、检测阈值或科学验收标准。

原82项回归测试先独立通过。开发新增13项首次通过；Ruff首次有37个格式/导入问题，mypy有两处标注问题，
修正仅限本任务新增文件。独立测试fixture曾继承 development 的-10dB，
而其“强干扰应100%选错”断言原本针对20dB：实际 wrong-branch 为0.948051948。
修正为测试明确传入20dB，保留-10dB为正式实验条件，没有调整科学阈值。
随后13项通过；另增波形级bootstrap/记录级Wilson置信区间语义测试，总回归96项通过。
第一次和最后一次持久化日志在TASK005根目录development_*；中间该次fixture失败输出保留在聊天工具记录，
本段记录具体失败原因与值，不声称该中间运行通过或其完整输出已落盘。

audit.py、summarize.py、visualize.py、contrasts.py、grid_resource.py与统计语义测试为正式变换开始后的独立后处理新增文件，
不属于最初source_snapshot；最终交付另外保存其SHA-256。audit曾有复用变量名导致的mypy错误，
修正为独立report变量，未更改实验计算。最终检查覆盖所有新增模块。

安装包metadata报告PyWavelets 1.10.0，而pywt.__version__返回1.8.0；
实际模块路径、源码签名支持precision，CWT FFT/precision18与离散核测试均运行通过。
这是环境标识差异，不按旧报告文字假装版本字段完全一致；未安装或升级任何依赖。

本轮正式过程使用每个pool最多2个计算worker。单项CWT仍保留2GiB规划与当前可用RAM70%限制。
性能比较另用独立进程、在导出与绘图前读取Windows生命周期峰值，
不把共享pool的峰值当单波形峰值；性能单次运行无跨机器置信结论。

完整原始真实时间轴保留在native.npz；common谱与图使用实际STFT中心对应的原始样点，
未对输入波形降采样。图末端可能距离最后原始样点不足一个hop，完整末端候选仍在native。
A2真实输出只作synthetic-white参考的探索性评分，真实噪声校准、物理真值和速度均UNKNOWN。

为分开记录网格三种信号类型的可比较峰值，正式run结束后补充18个独立新进程资源审计。
固定选择已注册的第一个mid频率，覆盖两rate×clean/noisy/linear×24/48/96，未按误差挑选或更改GO成本门槛。
每进程一份CWT供三评分共用；逐策略新进程峰值仍以原先22项performance比较为准。
配对评分差异的探索性CI单独写response_pairwise_comparison.csv，不能当新增确认性GO域。

独立后处理在首次正式执行前修正了physical补充组的对照配对：使用physical_balanced及同子网格，
不与正式128步长结果混配；物理补充行不具备主GO所需全部字段，明确不参评。
没有改动冻结的系数、候选或原始指标。最终所有检查覆盖48个源文件。

旧TASK004输出以及src和旧配置不变；不提交、推送或进行Production迁移。
