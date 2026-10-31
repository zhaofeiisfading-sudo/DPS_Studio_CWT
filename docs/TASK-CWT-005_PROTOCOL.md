# TASK-CWT-005 预注册协议 v1.0

日期 2026-10-30（Asia/Shanghai）。本文件在任何 TASK005 正式校准、development 或 held-out 变换之前创建。
初始 HEAD f2ddb819a753ec09af1b1f0443428befb11e4773；research/cwt-morlet；独立仓库，初始 status/diff/cached diff 为空。

## 范围与证据

目的：分离尺度评分、离散网格、弱信号谱信息与时间窗机制，作可选工程建设判断。
只新增 benchmarks/validation、tests/test_validation*、configs/task_cwt005.toml、本 TASK 文档及 artifacts/TASK-CWT-005；缓存仅 .local_cache。
src、旧配置、旧 TASK004 产物及默认 raw strongest 不变。仓库外只更新指定 Obsidian 轻量日志。
raw_data 的 10 个波形/14 通道获本任务只读授权；含 .gitkeep 的完整集合/大小/SHA256 开始和结束一致。
拒绝 reparse/junction 路径；不复制 raw、不改 Production/兄弟目录、不进行任何 Git 写操作。
输入 s/V、频率 Hz；真实 optics/noise/truth UNKNOWN，不计算真实速度或误差。

## 假设与固定方法

H_A：raw 的 sqrt(a) 增益导致低频幅值偏好；A1 改善无噪声偏差，但可能增加低 SNR 高频误选。
H_B：密化网格只能减少量化项，不能消除评分或离散滤波传递函数偏差。
H_C：低频白噪声优势可能受频率、噪声 PSD 与采样率影响；不预设 CWT 胜。
H_D：固定 STFT 样点窗造成跨采样率物理窗宽不同，是 TASK004 瞬态反转的待验证机制。
H_E：错误可来自真实局部峰缺失，或存在但未被 strongest 选中；仅作诊断，不实现追踪。

CWT 均 cmor1.5-1.0、pywt.cwt FFT、precision18、0.1–6GHz，24 voices/octave（143 尺度）。
A0=abs(W)；A1=abs(W)/sqrt(a)；A2=abs(W)/r_a，其中 r_a=sqrt(mean_calibration(abs(W_noise)^2))。
r_a 仅由对应采样率/噪声模型的独立单位方差噪声全库内部样点估计；不使用 signal truth。
这是经验二阶噪声标准化，不宣称 Rayleigh 尾、精确 p 值或未知真实噪声的已知模型。
同一输入/尺度密度的 A0/A1/A2 必须共用一次 CWT 系数矩阵；不平滑、插值、精修、门控或支路锁定。
Balanced/High time 沿用 TASK004 periodic Hann 768/512、hop128、NFFT4096 与幅值定义。
固定物理窗补充：40GS/s 用上述窗口；80GS/s 用1536/1024、hop256、NFFT8192，对应19.2/12.8ns、3.2ns、9.765625MHz。
该组仅解释机制，不取代正式 STFT。

## 数据、随机性与阶段隔离

长度固定409.6ns，40/80GS/s 对应16384/32768点；校准/held-out 噪声记录同长度。
RNG 为 NumPy default_rng；recipe 中 noise_seed 唯一确定波形，另以固定种子产生 off-grid 频率和初相。
低/中/高 off-grid 均匀分布区间0.15–0.45、0.55–1.85、2.3–5.3GHz，留出频带端点余量。
注册表在全部实验之前保存频率值，禁止按格点挑选；偶然近格点保留。
calibration scoring seeds 310000..310119（每 rate/model20，含补充8GHz带宽模型）；阈值独立 seeds 320000..320239（white/colored每 rate/model60）。
development seeds 410000 起，四个预指定域各4波形；held-out seeds 510000 起，每条件20波形。
grid seeds 610000 起；性能 seed710000；bootstrap seed810000。均不复用 TASK002/004 evaluation seeds。
编号按冻结注册表生成，跨条件不复用 noise_seed；校准/开发/held-out/grid 集合须程序断言无交集。
候选在 development 后、held-out 之前冻结：在 low/white/-10dB 与20ns chirp/white/20dB 的两采样率四组中，
以 mean(RMSE/max(Balanced RMSE,10MHz)) 最小选择 A0/A1/A2；相同分数按 A0,A1,A2 顺序。
voices24 为主候选，网格实验不能反向更改它；全部三评分无论开发胜负均完整评价。

## 噪声和 SNR

白噪声 iid N(0,1)。有色噪声为离散周期平稳 Gaussian：对白噪声 FFT 乘 sqrt(G(f)/mean_full_DFT(G))，
G(f)=1/(1+(abs(f)/1.5GHz)^2)，DC 保留；记录有限长度和周期模型，非未知真实仪器模型。
SNR20/0/-10dB：sigma=sqrt(P_clean_active/10^(SNR/10))；P_clean_active 由干净电压在 active 样点的均方计算。
噪声不事后强制归一化，另存实测输入功率/SNR；amplitude/fade 时 active 含低幅段，门脉冲按门内功率定义。
宽带污染在190..192ns额外加入4sigma独立白噪声，只列背景 SNR 与含污染实测 SNR。
补充带宽约束：G=1(abs(f)<=8GHz)，按同样方差归一化，在两 rate 均相同物理8GHz低通、同单位方差，
故相同 sigma 时单边 PSD 约 sigma²/8GHz。单独列组，不混入全 Nyquist 白噪声结果。

## 合成注册表

- core：2 rate ×3 band ×3 SNR ×2 noise ×20 =720；每条随机 off-grid 恒频与初相。
- modulation：慢幅变0.6+0.4cos(2pi t/T)、暂降至0.05（180..220ns）、宽带污染；各2 rate×3 band×20，白噪声0dB，共360。
- chirp：0.5→4GHz，中心200ns，持续200/80/20/4ns，两侧恒频，解析相位积分；白噪声20dB，各20，160条。
- pulse：1/5GHz，起始200ns，4/20/80ns矩形门，白噪声0dB，各 rate20，240条。
- branches：目标0.5GHz/2GHz，干扰2GHz/0.5GHz，幅0.5:1、白噪声20dB，各 rate20，80条。
- noise：white/colored，各 rate40条独立无信号记录，共160（前20与后20独立用于覆盖稳定性，合并报告40）。
- bandwidth：3 band×2 rate×20，-10dB，相同8GHz物理带宽，共120。
合计1840条 held-out，任何失败均保存，不能删除严重误选案例。
grid 独立实验：固定 seed 产生每 band4个 off-grid 值，分别无噪声恒频、0dB恒频、全记录线性chirp（f→min(1.15f,5.7GHz)）；
两 rate×12频率×3类型×3 voices(24/48/96)=216次 CWT，三评分共用矩阵。
grid 每个带/类型只有4个随机频率；其含噪统计仅描述性，不冒充20重复高置信稳健性。

## 指标、谱支持和起跳

正式误差在 c=0,128,... 的实际输入样点、所有方法全库支撑/窗口共同内部且 active 处计算；保留全共同格点预测、真值与掩码供独立复算。
CWT bank 半径 ceil(8a)+2；selected radius/alias 另存。STFT 物理窗补充用共同256样点子网格，两组分别明确分母。
保存 RMSE/bias/MAE、|delta f|>500MHz 相邻跳变、coverage、|error|>1GHz 灾难率、相对 A0 harm、各背景候选频带比例。
chirp 同时报告全共同内部与解析变化区间的误差；pulse 误差只在 active，不删除提前检测。
branch wrong=距干扰比距目标更近，明确 weakest target 不等于自动可辨识物理界面。
局部峰：strict-left / nonstrict-right 内部峰，端点不算峰；匹配 tolerance=max(20MHz,2*f*(2^(1/24)-1))，
所有 voices 共用此预定物理邻域，不在结果后放宽；STFT同邻域。另存实际最近格点距离。
真实峰 presence、峰响应/频带median、局部峰的响应排序（最大为1）、Top1/3/5 recall、strongest within tolerance、
失败帧中 presence 与 Top-K recall 必须分开；不把任意微小峰称可靠检测。有效支持另要求 peak/bandmedian>=2。

检测只用共同内部每帧 E=max response/sigma（A2 的 r 已按单位噪声），与候选评分分离。
每方法/rate/model 在独立60噪声记录上：逐帧阈值=合并帧99%分位；逐记录阈值=各记录 max(E) 的95%分位（higher）。
两套阈值独立报告；目标 frame FPR1% / record FPR5%，有限校准并非保证。
统一首次过阈为 onset，可在真实起始前；miss=active 内无命中，另列整记录无触发。
frame FPR、record FPR、门内检测概率、onset 误差、early trigger、miss 均保存；NO_SIGNAL 不转零。
不探索连续帧阈值，以控制范围。纯噪声独立记录为 FPR 不确定性单元；跨门泄漏 FPR另列且不删除。

## 统计判决与停止规则

独立波形为配对单元，每条件20（noise40）；均值/中位数/分布与10000次配对 bootstrap95% CI；禁止按相关帧增加 n。
主 GO 两个域：low/white/-10 与20ns chirp/white/20dB（后者使用变化区间）；在两 rate 均须支持。
仅冻结的开发候选可触发 GO。用 mean(CWT RMSE-0.8*Balanced RMSE) 的 Bonferroni97.5%双侧 CI 上限<0，
两 rate都满足；Balanced<10MHz时改要求绝对改善>=2MHz，且 CWT RMSE<=10MHz。
同时声明域内灾难率每波形均<1%、|bias|均<=max(10MHz,0.02*mean truth)，域外退化完整报告。
工程可选预算：同长度 fresh-process CWT总分析/ Balanced 比<=50、峰值<=2GiB；不满足仅NICHE_ONLY。
GO_FOR_OPTIONAL_ENGINEERING 只建议未来可选 Research 模式；不替换 Production。
部分可复现获益但敏感/成本过大→NICHE_ONLY；两主域都不支持且关键失效未改善→NOT_SUPPORTED。
不得凭获胜条件个数下结论，不将本轮已看的 held-out 再称下轮独立数据。
任何预算失败/覆盖不全/检查失败→工程最多LIMITED；数据变动/仓库无法核验→BLOCKED。
如果资源不足，先完成20重复core，再其他组；未完成项明确NOT RUN，不能缩成少seed后宣称完整。
每任务超时900s；并发最多2个计算进程，2GiB规划上限且单进程预估<=可用RAM70%，资源拒绝不改变输入。

## 真实全量与性能

全部14通道24voices，三评分同矩阵，A2仅采用 synthetic white 形状参考，标 EXPLORATORY/UNKNOWN REAL NOISE；
不从无标签真实片段估sigma/PSD或称已校准。对照沿用冻结STFT，重算并与TASK004 native逐项核验。
保留完整绝对时间/native候选及质量；common谱矩阵完整保存供诊断；图只作显示抽列，不变更波形。
每通道五行频谱/候选图加响应/峰排序诊断；全量、前/中/后三分之一，20260607/ch3既有观察窗口与
固定规则低/高强谱(共同内部各频带raw peak最高10%)、最大频率变化附近±20ns均标探索性；不称物理真值。
性能在独立新进程、两rate N=32768/65536（819.2ns）测voices24/48/96×A0/A1/A2及两STFT：
CWT时间、候选时间、分析总时间、导出前Windows生命周期峰值、矩阵尺寸、输入每物理秒成本与每百万样点成本。
fresh-process重复变换只为单策略成本；科学比较仍强制一次变换三评分。native密度与分辨力明确分离。
只生成必要汇总和14通道关键图，不为每个合成case批量绘图。

## 交付与检查

manifest、seed/频率划分、configuration_registry、synthetic_metrics、condition_summary、real_diagnostics、
scale_bias_analysis、time_memory_comparison、decision_matrix、失败清单、独立复算审计、环境/源码快照/哈希。
pytest / Ruff / mypy strict src tests benchmarks，以及两项 git diff check；所有命令先source scripts/cwt_env.ps1。
旧测试全部保留；数值正确、合成性能、真实推断分开判断；不引用未经核验论文。
详细报告 docs/TASK-CWT-005_REPORT.md；日志为指定2026-10-30_TASK-CWT-005_CWT偏差与适用性验证.md，15–30行。
完成后停止，不开始TASK006、GUI、promotion、commit或push。
