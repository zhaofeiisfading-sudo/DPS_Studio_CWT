# TASK-CWT-004 公平对照预注册协议 v1.0

_2026-10-30，Asia/Shanghai；在正式校准、合成和真实变换前冻结。_

## 📋 范围与停止规则

目标：全部真实通道的描述性比较，以及独立合成真值的误差、瞬态、存在性诊断和资源比较。初始 HEAD `ca2423e6b063d0d1b33c892dacb8772e4b20d902`，独立仓库、`research/cwt-morlet`、工作树与暂存区干净，既有65项测试通过。当前任务取代旧规划的任务编号安排，不启动下一任务。

写入仅 benchmarks/comparison、tests、configs、docs、artifacts/TASK-CWT-004、.local_cache，仓库外仅指定轻量 Obsidian 日志。src 正式算法与旧配置不变。raw_data 只读且开始/结束比较路径、大小、SHA-256；Production、兄弟项目不访问。无提交、推送、拉取、改索引、删除或清理。全部路径拒绝链接/junction。输入SI为s、V，输出Hz；真实波长、偏置、噪声模型及真值UNKNOWN，不计算真实速度。

每次运行独立run_id；失败保留并逐通道隔离；单worker超时900s，CWT规划预算2GiB且不超过当前可用RAM的70%，STFT采用同样2GiB上限及70%规则。预算拒绝、数据变化、映射缺失、非均匀采样均记录失败，禁止暗中缩短或重采样。资源或输出失败使工程结论至多LIMITED；无法核验输入/仓库为BLOCKED。正式后不得修改本协议来改善胜负；实现错误修复另存修订说明并重跑受影响结果。

## 🔬 三组固定方法

| 方法 | 参数 | 响应与候选 |
| --- | --- | --- |
| CWT | cmor1.5-1.0，pywt FFT，precision18，0.1–6GHz，24 voices/octave，143尺度 | raw abs(W)，逐样点argmax；平峰最低频 |
| Balanced | periodic Hann L768，overlap640，hop128，NFFT4096 | 单边正频，0.1–6GHz，2 abs(FFT)/sum(window)，逐帧argmax |
| High time | periodic Hann L512，overlap384，hop128，NFFT4096 | 同上 |

STFT使用SciPy ShortTimeFFT，onesided/magnitude结果乘2；指定p0=0，p1=floor((N−1)/128)+1，只输出中心在真实记录内的帧。窗口样点为[c−L/2,c+L/2)，越界补零且保留风险标志。不移除均值。幅值单位V，是正弦峰幅估计；CWT为离散尺度系数幅值V，两种定义不可同色标直接比较。全部方法无精修、门控、删点、平滑、连续性修复或物理修正。scale-normalized补充本轮不运行，避免稀释主比较。

40GS/s：L768/512对应19.2/12.8ns；80GS/s对应9.6/6.4ns。hop为3.2/1.6ns；FFT grid为9.765625/19.53125MHz，最近格点上界为半格。Hann ENBW=1.5 fs/L；主瓣首零点间宽度4 fs/L，分别208.333/312.5MHz（40GS/s）、416.667/625MHz（80GS/s）。ENBW和主瓣宽度是不同量，均非普适双支路分辨阈值。零填充仅密化网格。CWT相邻频率比2^(1/24)，最近格点相对上界约1.4545%，另有raw响应选择偏差；双支路分辨力须实验。

频率与窗口约定参照[ShortTimeFFT官方文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.ShortTimeFFT.html)及[PyWavelets CWT官方文档](https://pywavelets.readthedocs.io/en/latest/ref/cwt.html)，实际实现再以安装源码和直接FFT验证。旧规划论文未重新核验，状态unverified，不作性能证据。

## ⏱️ 时间、边缘与指标

native保留全部CWT样点及全部STFT帧。共同索引c=0,128,...≤N−1；时间严格使用input.time_s[c]，对照名义t0+c dt并记录浮点差。CWT只索引原始样点，不插值。所有主误差在三者共同网格、CWT全库有限支撑与两STFT窗口共同内部计算。另存全记录common、各native全记录/内部指标；不混合分母。

CWT保留所选尺度与全库ceil(8a)+2边缘、alias与quality UNKNOWN；STFT保留真实窗口越界风险。主指标：active真值处RMSE/MAE/bias；相邻频率变化>0.5GHz比例与每秒次数；有干扰支路时以距干扰更近定义wrong-branch（同距不算）；step前后各20ns误差；同幅双频中点谱上，两个独立局部最大值分别距真值≤min(0.1GHz,间距/3)才算分离。纯噪声频率误差为空。coverage表示输出合同，不是正确率。

## 🧪 合成注册表与存在性诊断

两采样率40/80GS/s，N=16384/32768，均409.6ns，time0=0；相位0.37rad，噪声iid零均值Gaussian。evaluation seeds=20001,20002,20003；calibration seeds=10001..10010，两个采样率分别校准，各case不用于调参。相同seed跨条件复用噪声，条件间非独立重复，不给样点独立置信区间。

| 组 | 每个采样率固定案例 |
| --- | --- |
| S1 | 0.2/1/5GHz，A1V，无噪声，seed20001 |
| S2 | 三频×SNR20/0/−10dB×三seed；sigma=sqrt(0.5/10^(SNR/10))V |
| S3 | 0.5→4GHz全记录慢chirp；190–210ns内0.5→4GHz快chirp、两侧恒频；sigma0.070710678V，三seed |
| S4 | 1/5GHz×4/20/80ns矩形门，起始200ns，A1V，sigma=sqrt(0.5)V，三seed |
| S5 | 纯噪声sigma1V，三seed；S4同时提供长无信号区 |
| S6 | 弱目标0.5GHz/A0.5V vs 2GHz/A1V；弱目标2GHz/A0.5V vs 0.5GHz/A1V；sigma0.02V，三seed |
| S6 separation | 同幅1V双频中心1GHz，间距0.1/0.3/0.8GHz，sigma0.02V，三seed |
| S7 | 200ns处0.7→3GHz阶跃；弱目标0.7→3GHz与强干扰3→0.7GHz交叉，幅比0.5:1；sigma0.02V，三seed |

chirp和step由频率解析积分相位生成，跨段相位连续；双支路真值分别保存。预计每采样率78个evaluation，共156例（实际程序注册表核对，不能删掉负例）。信号、真值、配方和数组哈希保存；不覆盖TASK002。

每方法E(t)=max response；同时保存频带median、q90、peak/median、sum归一化平方集中度sum(p²)（不把两种频网格的集中度当等价概率密度）。诊断不改变候选。合成已知sigma时用E/sigma；每方法/采样率在10条独立纯噪声校准记录的共同内部帧上取99%分位阈值，相同目标逐帧FPR=1%，不保证record-wise FPR。冻结阈值后评价held-out纯噪声FPR和S4检测率；第一共同内部阈值越过作为全局onset，含提前噪声触发，报告有无门内命中及提前触发。无越过为miss，不填零误差。并记录门外FPR（包含变换跨门泄漏）及距门≥80ns的远背景FPR、E可分性AUROC。不能把相关帧当独立试验。

## 📊 真实、图件与资源

沿用configs/real_batch.toml逐文件逐列映射，实际扫描全文件；新增未映射文件记录并使覆盖结论LIMITED。全部14通道运行三方法，不复用历史计时。真实没有独立无信号标签，背景噪声标准化一律NOT AVAILABLE。另用每条记录共同内部频率median响应的时间median作为“record reference”，只能做20log10(response/reference)描述性dB，不能称SNR/噪声。统一dB范围−20..60；线性每方法vmin0/vmax完整响应最大，记录数值及低于1% vmax像素比例，分析自动色标的暗背景效应。

全记录每通道输出3行线性幅值图、3行统一record-reference dB图、native和common候选图、背景E/median/ratio图、全部通道总览及路径索引。显示仅选≤2400个实际时间列且保留首尾，不平均、不插值，完整native/common数据不抽样；metadata保存显示索引、色标及边界。ROI观察用：全部真实通道共同内部E最大帧附近±0.15us，另保存TASK003原先20260607的0–0.6/0.75–1.25us与ch3的0–1.0/1.08–1.30us窗口统计并明确事后探索；其他通道取前/中/后各三分之一描述，不称信号标签。ROI不参与优胜结论。

资源：真实每通道/方法独立新进程顺序测量，synthetic另各采样率80k/160k同一1GHz输入做三组独立新进程。测变换、strongest、分析总时间、输出写入/worker wall、Windows PeakWorkingSetSize、矩阵形状/字节与点数；峰值在绘图前采集，包含导入/读取及分析，非Python-only值。真实各方法在单次运行中的执行顺序轮换，合成主结果计时另标shared-process，不混用其峰值。单次测量无性能置信区间。

## ✅ 验收、结论与证据

测试覆盖窗口/中心/hop/单边/grid/直接FFT/恒频/chirp、无精修/删点、共同时间与边缘、噪声保候选、14通道映射覆盖、图件坐标/索引、预算/失败隔离与raw只读。运行pytest、ruff check .、mypy --strict src tests benchmarks、两项git diff check，原始失败与修复均留存。正式运行保存协议/配置/源码快照及SHA、环境、硬件、种子、全部真实/合成/资源表、failure_cases.md和manifest。

工程PASS要求14/14×3完成、图件/完整轨迹与审计齐全、全部检查通过、raw完整；已知无真实真值不阻止工程PASS。科学在条件分组解释，不作全局平均胜者：稳定频率/SNR组与瞬态/分支组如有可重复的相反优劣判MIXED；仅一侧所有可评组胜且无实质退化才CWT_BETTER/STFT_BETTER；不足或全部失败INCONCLUSIVE。以三seed逐case结果与范围呈现，>10%相对RMSE改善作有意义差异的描述阈值；若CWT存在高SNR偏差或弱支路失败必须保留，不以图清楚抵销误差。不自动推广、提交或启动TASK005。
