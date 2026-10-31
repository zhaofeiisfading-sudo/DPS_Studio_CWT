# TASK-CWT-005 — CWT尺度偏差、弱信号能力与工程适用性

执行日期：2026-10-30至2026-10-31，Asia/Shanghai。状态：COMPLETED。
**工程 verdict：PASS；科学 verdict：NICHE_ONLY（MIXED）。**

PASS限于数值合同、完整计算、可复算输出、回归检查和文件边界；不表示真实物理正确或值得启动GUI。
本轮未达到预注册的GO_FOR_OPTIONAL_ENGINEERING门槛，未改变默认raw响应，未启动TASK006或Production工程。

## 结论与八项交付问题

1. 高频严重误选部分减轻但没有解决。白噪声−10dB、2.3–5.3GHz新off-grid波形，40GS/s的A0/A1/A2平均波形RMSE为2235.25/1430.50/2207.10MHz；80GS/s为1925.34/1019.79/1952.26MHz。A1仍有明显GHz级错误，A2不构成普遍修复。
2. A1确实去除主要尺度幅值偏好，并在无噪声与慢chirp中减少系统误差；它在低SNR低频组造成很大损害。A2白噪声结果接近A0；有色模型标准化可显著损害低频目标。
3. 低频白噪声−10dB优势在80GS/s的新20波形中保留，A2/Balanced为7.043/21.214MHz；40GS/s为20.281/5.964MHz，优势不成立。不能把旧0.2GHz三seed结论推广到整个低频区间。
4. 20ns chirp优势强烈依赖STFT物理窗。40GS/s正式窗A2/Balanced为46.359/194.114MHz；80GS/s正式窗为43.895/33.226MHz。80GS/s改用同物理窗及同3.2ns评价网格，A2/Balanced变为46.359/190.106MHz。该补充仅支持机制解释。
5. 高频弱信号同时存在峰缺失与评分选错。双分量场景主要是峰存在但strongest无法识别预先指定的弱目标；不能把所有失败都归结为可用轨迹修复解决的问题。
6. 全部14通道完成，A1相对A0的共同内部候选修改率45.420%–81.707%，A2为4.878%–14.484%；修改不是纠错，真实准确率UNKNOWN。
7. 可保留明确条件下的离线研究用途；不支持现阶段开展GUI或默认算法替换。两种预指定GO场景均未在两采样率同时通过。
8. A2/24的总分析时间约为Balanced的64.106/68.321倍，超过预注册50倍成本门槛；96voices资源成本更高。收益不足以支持通用工程建设。

## 输入、方法与冻结

协议：[TASK-CWT-005_PROTOCOL.md](TASK-CWT-005_PROTOCOL.md)；实施记录：[IMPLEMENTATION_NOTES](TASK-CWT-005_IMPLEMENTATION_NOTES.md)。
本报告中的R为：`artifacts/TASK-CWT-005/run_20261030_221635_70d83adf/`。

初始独立仓库HEAD为f2ddb819a753ec09af1b1f0443428befb11e4773，分支research/cwt-morlet，status/两种diff为空。
只新增benchmarks/validation、两个tests、一个配置及本TASK文档；src、旧配置、旧TASK结果不变。
输入严格s/V，输出Hz；真实光学条件、波长、方向、噪声及物理真值UNKNOWN，不计算真实速度。

固定CWT：cmor1.5-1.0，PyWavelets FFT、precision18，0.1–6GHz，24/48/96 voices对应143/285/569尺度。
同一波形/网格的三种评分共用同一次完整CWT，候选始终为逐时刻argmax，无精修、质量门控、插值、平滑或支路锁定。

| 标识 | 数学定义 | 校准与单位 |
| --- | --- | --- |
| A0 | abs(W) | 保留默认；离散尺度系数幅值V |
| A1 | abs(W)/sqrt(a) | 显式实验；尺度a无量纲，响应V |
| A2 | abs(W)/r_a | r_a为独立1V-RMS噪声的系数RMS，按rate/PSD/voices分开；数值为相对该参考的无量纲响应 |

检测A2使用E/(sigma/1V)；代码中的sigma为以V表示的数值。等价地可把r_a/1V看作无量纲滤波增益、A2写成V等效响应后再除sigma。
三种写法不改变候选，不能将A2数值当作物理电压测量或精确显著性概率。

Balanced/High time沿用TASK004：periodic Hann L768/512、hop128、NFFT4096，0.1–6GHz单边幅值strongest。
固定物理窗补充在80GS/s用L1536/1024、hop256、NFFT8192；40GS/s保持原值。
正式比较按实际原始样点c=128p配对；物理窗补充另按c=256p配对，CWT也取同一子网格。无时间插值。
评价排除全库ceil(8a)+2支撑风险与STFT窗口边界的并集；候选本身全部保留。频率网格间距不是双频分辨力。

## 数据集与统计单元

所有频率与seed先存入R/split_registry.json，随后开始校准。新seed不复用TASK002/004评价集。
409.6ns、40/80GS/s为16384/32768点；off-grid区间为0.15–0.45、0.55–1.85、2.3–5.3GHz。
白噪声iid Gaussian；有色噪声PSD形状G(f)=1/[1+(f/1.5GHz)^2]，FFT生成周期平稳Gaussian并按理论方差归一化。
SNR用已知干净目标active功率确定sigma，不以输出拟合噪声；另存实测输入SNR。双分量目标/干扰幅值0.5:1，目标噪声SNR与干扰分开定义。

| 划分/组 | 独立波形数 | 说明 |
| --- | ---: | --- |
| scoring calibration | 120 | 每rate/white、colored、8GHz带限模型各20；最高密度96一次变换，嵌套取24/48网格 |
| detection calibration | 240 | 每rate/white、colored各60；与上述及evaluation隔离 |
| development | 16 | 两rate×低频白噪声−10dB/20ns chirp20dB×4 |
| held-out core | 720 | 两rate×三频段×20/0/−10dB×两PSD×20 |
| 慢幅变/衰落/宽带污染 | 360 | 各两rate×三频段×20，背景0dB |
| chirp | 160 | 200/80/20/4ns，解析积分相位，20dB，各条件20 |
| pulse | 240 | 1/5GHz×4/20/80ns，0dB，各条件20 |
| 双分量 | 80 | 两目标/干扰方向，各rate20 |
| noise-only | 160 | 两PSD×两rate×40 |
| matched bandwidth | 120 | 三频段×两rate×20，−10dB，相同8GHz物理带宽/PSD约束 |
| grid | 72 | 每rate×12预生成频率×无噪/0dB/线性chirp，三voices共216次变换 |

held-out共1840条，正式运行失败0；主指标13400行，grid1080行，逐条件汇总650行。
网格每频段只有4个随机频率，含噪网格结论是描述性；不能冒充20随机重复的稳健性证明。
grid的SNR=1000是有限JSON标记；独立审计确认其无噪两类输入与float64解析cosine逐值相同。

开发目标固定为四个预指定域的mean[RMSE/max(Balanced RMSE,10MHz)]：A0=1.116984、A1=136.300833、A2=1.108302。
冻结A2/24后才打开held-out；没有根据grid或真实图选择更密的主配置。冻结记录在candidate_frozen_before_evaluation.json。

下文held-out RMSE均为独立波形RMSE的均值；grid表为等权波形平方误差合并再开方。两者不能混用。
CI按独立波形配对bootstrap10000次，非相关帧独立重复；普通95%CI为逐条件描述，GO采用预定97.5%双侧区间。
CI以冻结噪声校准为条件，未传播校准参数不确定性；不提供未知真实噪声的精确p值。

## A：尺度偏差及归一化损害

连续局部单频近似abs(W)≈A sqrt(a)/2 exp[-pi²B(af dt−C)²]，B=1.5、C=1。
该模型推导raw最强频率约0.98366 f，A1去掉sqrt(a)后理想峰回到f；有限离散核、网格、噪声及瞬态仍可产生误差。
白噪声E|W_a|²=sigma² sum|h_a|²近似尺度不变，A1的噪声功率再除a，因而增强小尺度相对竞争。
有色噪声则由PSD与|H_a|²的积分决定；A2均衡二阶噪声响应，不能提升每尺度信息或自动选定目标支路。
以上为模型解释；数值证据另列，不据它认定真实物理误差。

等幅12个无噪off-grid频率、24voices的最大/最小峰响应：40GS/s A0/A1=4.4472/1.0262；80GS/s=4.3600/1.0060。
A2白噪声参考对应4.2527/4.3585，基本保留raw幅值增益结构，不能冒充幅值校正。

白噪声−10dB，各频段20新波形，单位MHz：

| GS/s | 频段 | A0 | A1 | A2 | Balanced | High time |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 40 | low | 20.384 | 3446.462 | 20.281 | 5.964 | 91.864 |
| 40 | mid | 681.100 | 2746.255 | 724.859 | 5.604 | 59.194 |
| 40 | high | 2235.255 | 1430.502 | 2207.103 | 5.830 | 97.077 |
| 80 | low | 6.987 | 2332.249 | 7.043 | 21.214 | 132.447 |
| 80 | mid | 257.092 | 1957.355 | 265.549 | 11.845 | 65.721 |
| 80 | high | 1925.339 | 1019.791 | 1952.260 | 11.686 | 113.077 |

A1−A0的低频配对差异95%CI：40GS/s +3312.06至+3543.62MHz；80GS/s +2230.38至+2418.25MHz。
高频相应CI为−1250.48至−359.83MHz、−1257.05至−550.29MHz：有部分改善，但剩余误差仍不合格。
这些为探索性逐条件对照，未作为新增GO场景。
高频白噪声灾难率(|error|>1GHz)：40GS/s A0/A1/A2=56.688%/39.286%/55.844%；80GS/s=38.677%/20.194%/39.355%。
不能把本轮随机2.3–5.3GHz均值直接与旧固定5GHz的3-seed结果比较成改进幅度。

有色噪声−10dB：

| GS/s | 频段 | A0 | A1 | A2 | Balanced | High time |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 40 | low | 235.821 | 1684.928 | 1462.481 | 347.604 | 436.557 |
| 40 | mid | 785.355 | 1201.221 | 1534.453 | 467.299 | 556.715 |
| 40 | high | 2987.356 | 1798.439 | 2298.840 | 1991.873 | 2325.726 |
| 80 | low | 247.255 | 1745.745 | 1534.265 | 526.901 | 619.316 |
| 80 | mid | 887.035 | 1196.101 | 1527.210 | 646.382 | 699.413 |
| 80 | high | 3764.845 | 2311.611 | 2723.210 | 3116.831 | 3223.894 |

A2低频有色噪声退化必须保留。即使STFT在有色高频组也有严重失败，CWT较小的相对误差不等于可用目标识别。
全部0/20dB、MAE/bias/跳变/coverage及配对分布见synthetic_metrics.csv、condition_summary.json。

## B：网格密化

两采样率的无噪恒频结果基本相同。40GS/s、12个off-grid频率的RMSE/bias，MHz：

| 模式/类型 | 24 | 48 | 96 |
| --- | --- | --- | --- |
| A0 无噪恒频 | 55.269 / −37.454 | 34.325 / −26.295 | 41.494 / −29.785 |
| A1 无噪恒频 | 18.430 / +13.727 | 9.615 / −0.403 | 6.460 / −1.067 |
| A2 无噪恒频 | 55.269 / −37.454 | 34.370 / −26.614 | 37.195 / −27.321 |
| A0 无噪线性chirp | 48.602 / −31.549 | 44.296 / −31.519 | 43.478 / −31.662 |
| A1 无噪线性chirp | 21.458 / −0.141 | 11.023 / +0.171 | 5.493 / −0.094 |
| A2 无噪线性chirp | 44.185 / −28.670 | 40.449 / −29.143 | 39.457 / −29.225 |

密化确实改善A1的量化误差；raw系统偏差保留，恒频还出现48到96非单调。
0dB恒频A1在40GS/s为93.981/90.466/95.662MHz，密化未稳定改善噪声误选；80GS/s为50.323/47.367/46.257MHz。
这支持“网格不能修复评分和噪声失效”，不支持把阶梯更细或输出更密称为物理分辨力提高。
逐频率及跳变在grid_metrics.csv，增益在scale_amplitude_response.csv，汇总在scale_bias_analysis.csv。

## C：弱信号、衰落及物理噪声带宽

80GS/s低频白噪声−10dB：A2−Balanced平均差−14.171MHz，95%CI[−33.741,−3.681]MHz。
40GS/s相应平均差+14.316MHz，95%CI[+3.138,+31.303]MHz；A2中位9.018MHz、最大156.869MHz。
40GS/s有一条波形的灾难率1/77=1.299%，也未满足每波形<1%的GO限制；不能用均值掩盖少量严重失败。

相同8GHz物理带宽、−10dB时，低频A2/Balanced为454.945/683.569MHz（40），490.617/1800.577MHz（80）。
CWT相对优势仍可存在，但绝对误差已很大；全Nyquist白噪声80GS/s的7MHz结果不能直接推广到同PSD条件。
该补充与主白噪声结果分开，没有改变正式基线。

慢幅变0dB高频组A2/Balanced为1551.95/4.27MHz（40）、1180.99/9.07MHz（80）。
暂衰落事件低频为1548.79/2648.57MHz（40）、1353.50/2906.96MHz（80）；两者均可能失效，较小不代表合格。
宽带污染事件高频为456.06/2.88MHz（40）、390.53/5.99MHz（80）。所有波形/事件掩码与负结果均保留。

## D：瞬态、物理窗和起跳

解析0.5→4GHz chirp、20dB，变化区间平均波形RMSE，MHz：

| GS/s | 时长ns | A0 | A1 | A2 | 正式B/H | 同物理窗B/H |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 40 | 200 | 43.977 | 21.615 | 43.907 | 2.880 / 2.871 | 2.880 / 2.871 |
| 40 | 80 | 45.918 | 23.158 | 44.973 | 20.012 / 6.928 | 20.012 / 6.928 |
| 40 | 20 | 46.403 | 25.240 | 46.359 | 194.114 / 151.341 | 194.114 / 151.341 |
| 40 | 4 | 228.282 | 215.640 | 228.782 | 342.436 / 327.797 | 342.436 / 327.797 |
| 80 | 200 | 43.290 | 21.114 | 46.214 | 5.727 / 5.652 | 2.871 / 2.859 |
| 80 | 80 | 45.384 | 21.224 | 46.870 | 6.777 / 6.569 | 19.583 / 6.533 |
| 80 | 20 | 46.264 | 24.080 | 43.895 | 33.226 / 13.199 | 190.106 / 149.760 |
| 80 | 4 | 193.881 | 174.013 | 190.971 | 663.234 / 215.939 | 341.950 / 327.308 |

同物理窗的80GS/s CWT也必须改按共同256样点子网格：A2在20ns/4ns为46.359/233.586MHz，不能直接拿上表正式43.895/190.971对比。
20ns正式A2−Balanced的95%CI：40为[−150.714,−145.286]MHz，80为[+6.758,+14.374]MHz。
完整共同内部A2误差为59.398/59.174MHz，不能把仅变化区域的优势称为全记录优势。
4ns事件共同帧很少，不作为4ns普适分辨力认证。20ns真chirp在3.2/1.6ns帧间隔本来就改变0.56/0.28GHz，
因此>0.5GHz跳变率跨采样率不同，并不自动表示错误或轨迹质量改变。

检测以60条独立噪声记录校准逐帧99%分位与逐记录max的95%分位，统一名义1%/5%目标。
noise-only各条件40条held-out；实际逐帧FPR范围0.649%–1.371%，逐记录FPR如下，括号为触发记录数/40：

| GS/s / PSD | A0 | A1 | A2 | Balanced | High time |
| --- | --- | --- | --- | --- | --- |
| 40 white | 2.5%(1) | 0%(0) | 2.5%(1) | 5%(2) | 2.5%(1) |
| 40 colored | 7.5%(3) | 0%(0) | 7.5%(3) | 7.5%(3) | 7.5%(3) |
| 80 white | 7.5%(3) | 12.5%(5) | 5%(2) | 2.5%(1) | 5%(2) |
| 80 colored | 2.5%(1) | 5%(2) | 5%(2) | 17.5%(7) | 10%(4) |

有限校准没有保证实际统一FPR。80 colored Balanced 7/40的Wilson95%CI为[8.75%,31.95%]；
0/40的上界仍为8.76%。不能称零误报，也不能宣称起跳比较在实际相同误报率下严格公平。
未用held-out重新校准阈值；FPR偏离作为负结果保留。记录级CI以记录为单元。

0dB脉冲起始200ns，下面为逐记录阈值下A2的检测概率/提前率/首次触发误差均值ns，每格20波形：

| GS/s / GHz | 4ns | 20ns | 80ns |
| --- | --- | --- | --- |
| 40 / 1 | 100% / 0% / +1.60 | 100% / 5% / −1.44 | 100% / 0% / +1.60 |
| 40 / 5 | 55% / 0% / +1.60 | 100% / 0% / +4.32 | 100% / 0% / +3.68 |
| 80 / 1 | 100% / 0% / 0 | 100% / 5% / −0.48 | 100% / 5% / −5.52 |
| 80 / 5 | 100% / 0% / +1.36 | 100% / 0% / +1.20 | 100% / 0% / +1.44 |

40GS/s、5GHz、4ns的A2漏检率45%，不能由较低提前率抵销。误差均值只对有记录触发者计算，漏检不填0。
Balanced各脉冲条件检测率100%，40GS/s提前率均100%；80GS/s为60%–90%。
High time提前率40GS/s为70%–90%、80GS/s为0%–5%。完整分条件误差分布/CI和逐帧阈值结果在condition_summary。
首次触发不排除已知onset前的帧；非因果窗口泄漏和很早噪声触发均可使均值提前，不认证因果时间分辨率。
NO_SIGNAL未转为零频率或零速度。

## E：峰缺失与评分失配

匹配邻域预定max(20MHz,2f(2^(1/24)−1))，所有voices和STFT相同；端点不算内部局部峰。
另要求峰/频带median>=2标为supported；该阈值不是经过物理认证的检测概率。

| 白噪声高频−10dB，A0 | 真频局部峰存在 | supported | 错误帧中峰存在，逐波形均值 |
| --- | ---: | ---: | ---: |
| 40GS/s | 57.99% | 26.30% | 42.30% |
| 80GS/s | 67.77% | 45.42% | 42.13% |

存在峰但未选中与根本缺少匹配峰均常见，且“存在”可含噪声小峰，不能直接视为可靠支路。
高频失败不是单纯调strongest就已经解决，也没有证据支持靠轨迹修补恢复缺失信息。

双分量两方向、全部方法的真频峰presence和Top3 recall均100%；弱目标2GHz、强干扰0.5GHz时wrong-branch均100%。
目标0.5GHz时wrong-branch：40GS/s A0/A1/A2/B=32.34%/100%/79.29%/100%；80GS/s=45.97%/100%/46.97%/100%。
这说明CWT可保留目标谱信息而global strongest选中强干扰；raw低频偏好造成的相对优势也对评分很敏感。
合成的“目标”是预先指定标签，真实数据不能自动把较弱峰指定为真实运动界面。未实现Top-K追踪。

## 全部真实14通道

完整读取10波形、14通道、1240002个原始样点，无裁剪、重采样或预处理。
全部A0 native候选/时间及两STFT候选与TASK004逐项精确一致；A1/A2只作独立实验输出。
每通道native.npz保存完整时间/候选/所选尺度边缘与alias；common_spectral_support.npz保存完整共同谱矩阵、峰排序和窗口掩码。
图使用实际共同帧中心，可能未覆盖最后不足一个hop的显示尾段；完整原始末端仍在native。
所有真实quality、噪声模型和truth为UNKNOWN；A2为synthetic-white参考EXPLORATORY，不是已校准测量。

以下修改率及跳变均在相同共同内部帧上，单位%；跳变为相邻|delta f|>0.5GHz：

| 文件/列 | A1修改 | A2修改 | 跳变 A0/A1/A2 | 跳变 B/H |
| --- | ---: | ---: | --- | --- |
| 20201210m/1 | 62.214 | 4.962 | 15.326/16.092/15.326 | 4.981/0 |
| 20201211m/1 | 69.084 | 6.107 | 12.644/22.222/13.410 | 3.831/0 |
| 20201214m/1 | 45.420 | 8.779 | 13.410/22.989/12.261 | 1.533/0 |
| 20221017a/1 | 62.023 | 11.260 | 13.576/17.208/13.958 | 4.971/4.015 |
| 20231019-ch1/1 | 73.092 | 8.588 | 15.870/20.650/15.870 | 5.736/4.589 |
| 20260607/1 | 74.564 | 5.575 | 28.098/30.017/28.447 | 15.358/20.244 |
| 20260607/2 | 81.707 | 6.620 | 24.258/29.843/24.607 | 13.613/21.815 |
| 20260630-1/1 | 72.817 | 14.484 | 8.206/37.459/8.604 | 14.560/19.126 |
| 20260630-1/2 | 74.603 | 14.352 | 15.089/41.430/16.876 | 19.457/25.347 |
| 20260630-2/1 | 58.362 | 8.885 | 6.806/20.070/7.330 | 9.250/11.693 |
| 20260630-2/2 | 58.885 | 9.233 | 9.424/23.909/9.773 | 9.075/11.693 |
| 20260701/1 | 78.223 | 11.324 | 6.457/31.414/7.853 | 10.646/16.056 |
| 20260701/2 | 79.965 | 11.498 | 10.122/36.126/10.297 | 16.405/24.433 |
| ch3/1 | 68.118 | 4.878 | 68.586/66.841/69.110 | 42.408/55.323 |

观察：20260607低频强带中三CWT模式总体相近，A1常有格点移动；弱支持区域A1更常转向高频。
ch3高频带与短暂低频结构在五种谱中均可见，A1仍在带外持续跳动，A2接近raw；没有明确真实支路标签。
20260630-1与20260701等背景/后段的A1跳变增加尤其明显，不是只展示改善案例。
上述为人工谱观察；无真实RMSE、真实正确率、噪声FPR或物理速度结论。
低/高强谱、最大响应/最大跳变邻域、前三分段、既有ch3/20260607窗口均标exploratory，详细响应/峰排序见real_diagnostics.csv。

## 工程成本与科学判定

独立新进程819.2ns输入，40/80GS/s为32768/65536点；时间不含启动/导出，峰值为导出前Windows生命周期工作集，含导入。
CWT逐样点输出，STFT逐128样点帧输出，不能把点数比称为真实时间分辨率。
单次fresh-process主候选A2资源：

| GS/s | voices/尺度数 | CWT s | 候选s | 总分析s | 峰值MiB |
| --- | --- | ---: | ---: | ---: | ---: |
| 40 | 24/143 | 0.5815 | 0.3497 | 0.9315 | 278.34 |
| 40 | 48/285 | 1.0870 | 0.8137 | 1.9013 | 455.78 |
| 40 | 96/569 | 2.7019 | 1.8685 | 4.5708 | 810.71 |
| 80 | 24/143 | 1.2941 | 1.2029 | 2.4974 | 456.62 |
| 80 | 48/285 | 3.1675 | 2.1476 | 5.3154 | 812.04 |
| 80 | 96/569 | 7.2414 | 1.9119 | 9.1538 | 1522.18 |

Balanced总分析0.014531/0.036554s，A2/24为64.106/68.321倍；96为314.56/250.42倍左右。
A2/24每百万样点成本约28.43/38.11s；全部精确输入每物理秒成本、矩阵尺寸、输出密度、其他评分见time_memory_comparison.csv。
本表CWT完整系数矩阵143×32768/65536至569×32768/65536，complex128；96/80GS/s为596639744字节。
不同评分的资源表全部保留，不能将共享矩阵的批量科学试验时长当成单策略成本。

另对注册表首个mid频率、clean/noisy/linear分别运行18个新进程资源审计，长度与grid一致409.6ns，不改变GO成本门槛。
40GS/s的24/48/96 CWT时间范围0.245–0.262/0.422–0.443/0.766–0.797s，三评分合计峰值约187–188/276–277/454–455MiB。
80GS/s对应0.591–0.653/1.092–1.153/2.615–2.726s，峰值279–280/456–457/812–813MiB。
详细候选分时、类型、种子与矩阵在grid_time_memory.json/csv。共享pool每case峰值仅作生命周期记录，不作为独立比较。
所有资源是单次样本，无性能CI；不同记录长度、后台负载与硬件不能无条件外推。2GiB与可用RAM70%规划检查保留。

GO两个预指定域均未在两rate同时通过；80GS/s低频白噪声单独满足性能与偏差/灾难限制，40GS/s失败。
20ns fast在40GS/s通过、80GS/s正式基线下失败；A2/24两rate均超过50倍成本门槛。
因此判NICHE_ONLY，不依靠获胜条件计数，也不因事后看到A1某个瞬态较好而改主候选或增加GO域。
较高voices的A1可作为无噪声/高SNR数值研究参考；没有独立证据支持把它设为通用弱信号默认配置。

## 检查、复算、产物和边界

准确命令均在同一PowerShell7会话先执行`. .\scripts\cwt_env.ps1`，选择`.local_cache/venv/Scripts/python.exe`：

```powershell
& .local_cache/venv/Scripts/python.exe -m pytest
# 96 passed in 25.42s
& .local_cache/venv/Scripts/python.exe -m ruff check .
# All checks passed!
& .local_cache/venv/Scripts/python.exe -m mypy --strict src tests benchmarks
# Success: no issues found in 48 source files
git diff --check
git diff --cached --check
# 两者exit 0
```

初始82项保留，新增14项含参数化测试。开发失败和环境版本字段差异见IMPLEMENTATION_NOTES，未伪称首轮全通过。
Python3.12.15，NumPy2.5.4，SciPy1.18.1；PyWavelets distribution1.10.0而module.__version__1.8.0，实际源码签名/路径/hash另存。
Windows/AMD64、16逻辑CPU；环境、发行包及实际源码快照见source_environment.json与任务根runtime_version_evidence.json；未安装依赖。

独立审计PASS：14680行指标、1135560个频率误差点，4个全CWT重新生成探针，14通道1240002个native时间点；冻结源码无变化。
所有raw集合/大小/SHA256初末一致，11文件含.gitkeep共32086814字节；本轮仅读取，未复制raw波形。
2091条方法/波形严重负结果列于failure_cases.csv，配方及预测全部保留；该数是失败定义下的方法行数，不是2091个独立波形。
正式run墙钟6153.543s包含聊天中断期间；它不是纯算法基准，不用于上述成本比。后处理与附加资源审计另计。

| 产物 | R内路径 |
| --- | --- |
| 运行/配置/划分 | manifest.json、configuration_registry.json、split_registry.json |
| 校准/开发冻结 | calibration/score_profiles.json、calibration/detection_thresholds.json、candidate_frozen_before_evaluation.json |
| 全部真值指标/分布 | synthetic_metrics.csv、condition_summary.csv/json、evaluation/*/common.npz与recipe.json |
| 尺度/评分 | scale_bias_analysis.csv、scale_amplitude_response.csv、response_pairwise_comparison.csv |
| 真实全量 | real_diagnostics.csv、real_channel_index.json、real/*/{native.npz,common_spectral_support.npz,metadata.json} |
| 成本 | time_memory_comparison.csv、performance/*、grid_time_memory.csv/json、grid_resource/* |
| 判定/失败 | scientific_decision.json、decision_matrix.md、failure_cases.csv/md、各split_failures.json |
| 复算/原始边界 | independent_audit.json、raw_before.json、raw_after.json |
| 图件 | real/*/{spectral_support.png,quality_diagnostics.png}、figures/*.png |

查看了全部14通道候选总览、grid/瞬态汇总，以及20260607第二列和ch3原尺寸谱图；没有声称逐张精读所有图。
图中dB为各记录响应median参考，不是SNR；A2真实标EXPLORATORY，边界风险阴影保留。

普通git diff和cached diff均为空；本TASK的18个新文件未跟踪、未暂存，单独审查补丁在任务根review.diff。
分支/HEAD/origin保持初始值；origin fetch/push为https://github.com/zhaofeiisfading-sudo/DPS_Studio_CWT.git。
.local_cache、artifacts、raw_data继续被忽略；raw/artifacts无被跟踪文件。无commit/push/pull、历史或remote/索引改动。
Production及其他兄弟项目未修改、未作为本轮分析输入。

Obsidian同一篇起始日轻量日志，跨日完成后更新：
`D:\Research\Notes\05项目\DPS_Studio_CWT\2026-10-30_TASK-CWT-005_CWT偏差与适用性验证.md`。

复现会创建新run，不覆盖旧结果：

```powershell
. .\scripts\cwt_env.ps1
& .local_cache/venv/Scripts/python.exe -m benchmarks.validation.run
# 以实际新run目录替换R；后处理也使用独占新文件写入，不要对已有产物重复运行：
& .local_cache/venv/Scripts/python.exe -m benchmarks.validation.grid_resource --run R
& .local_cache/venv/Scripts/python.exe -m benchmarks.validation.summarize R
& .local_cache/venv/Scripts/python.exe -m benchmarks.validation.audit R
& .local_cache/venv/Scripts/python.exe -m benchmarks.validation.visualize R
& .local_cache/venv/Scripts/python.exe -m benchmarks.validation.contrasts R
```

数学/API定义参考[PyWavelets官方CWT文档](https://pywavelets.readthedocs.io/en/latest/ref/cwt.html)与[SciPy ShortTimeFFT官方文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.ShortTimeFFT.html)，另由安装源码与直接数值测试核验。
旧论文引用本轮未重新核验，仍标unverified，未据其作性能结论。

下一步仅建议保留Research方法和全部负结果；若继续，先独立验证明确低频/噪声带宽场景及记录级误报校准，再另行决定是否工程立项。本TASK到此停止。
