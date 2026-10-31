# 可用于本科毕业设计的CWT对照研究材料

本文件供后续编辑为论文方法、结果与讨论正文；没有修改其他论文项目，也没有生成正式Word/PDF。数值来源为已保存的合成真值实验，审计基准日期2026-10-31。

## 方法正文建议

为评价不同时间尺度的拍频结构，采用复Morlet连续小波变换分析PDV电压信号。对于 $x(t)=A(t)\cos\phi(t)+n(t)$，瞬时拍频定义为 $f_b=\dot\phi/(2\pi)$。连续时间小波系数为 $W_x(a_t,b_t)=a_t^{-1/2}\int x(t)\psi^*((t-b_t)/a_t)dt$。本研究母小波固定为cmor1.5-1.0，其中带宽参数 $B=1.5$、中心参数 $C=1$；这是一组研究起始参数，未被证明为最优配置。

数值计算由PyWavelets的FFT CWT实现，积分小波precision设为18。软件采用无量纲样点尺度 $a=a_t/\Delta t$，离散系数与连续时间积分系数相差 $\sqrt{\Delta t}$；本文幅值均遵循离散系数约定。分析频段为0.1—6 GHz，24 voices/octave产生143个频率尺度，尺度与物理频率通过 `scale2frequency/Δt` 校验。边缘以 $\lceil8a\rceil+2$ 样点的有限支撑风险标记；Nyquist约束之外另检查小尺度混叠风险。输入时间和电压单位分别为s和V，未进行重采样、平滑或插值。[官方CWT定义](https://pywavelets.readthedocs.io/en/latest/ref/cwt.html)可用于引用API和尺度约定，不能用作本研究优越性的外部证据。

每一时刻以频带内响应最大值对应频率作为候选，保留所有时刻输出。研究比较A0=$|W|$、A1=$|W|/\sqrt a$和A2=$|W|/r_a$，其中 $r_a$ 为独立1 V RMS合成噪声在该尺度的系数RMS。三种评分共用相同CWT系数，未采用轨迹连续性约束或多支路锁定。A2依赖预定噪声模型；真实数据中应用合成白噪声参考仅是探索性评分，不是实际噪声校准。

STFT对照采用periodic Hann窗和逐帧带内最强幅值，两组参数为L768/hop128/NFFT4096和L512/hop128/NFFT4096。正频幅值定义为 $2|\mathrm{FFT}(xw)|/\sum w$，与CWT原始系数幅值不能直接作未校准色标比较。40 GS/s的实际窗口为19.2/12.8 ns，80 GS/s则为9.6/6.4 ns。FFT补零仅增加频率采样密度，不能使真实双频分辨能力等于格点间距。[ShortTimeFFT文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.ShortTimeFFT.html)用于说明相应实现约定。

评价使用相同完整输入和实际帧中心，CWT在对应原始样点直接取值。主误差限定在所有方法共同内部且具有已知真值的区域，未按输出质量筛选。主要held-out条件各有20条独立波形，以波形作为配对bootstrap的统计单元；纯噪声没有频率真值，RMSE留空。速度公式 $v_{\mathrm{app}}=\lambda_0f_b/2$ 仅在波长和零光学偏置显式成立时适用，并不提供运动方向、角度修正或窗口修正。

## 结果正文与原始来源

尺度归一化在无噪声条件下减少主要幅值尺度偏好。40 GS/s、12个预定off-grid频率的A1合并RMSE随24/48/96 voices由18.430降至9.615和6.460 MHz；A0则为55.269、34.325、41.494 MHz。该差异表明网格量化和raw响应偏差需要区分。A1在40 GS/s低频白噪声−10 dB条件下的平均波形RMSE为3446.462 MHz，远高于A0的20.384 MHz，说明无噪声改善不能外推为普遍弱信号优势。

低频白噪声−10 dB结果具有明确条件性。40 GS/s下A2和Balanced的平均波形RMSE分别为20.281和5.964 MHz，而80 GS/s下分别为7.043和21.214 MHz。两采样率的A2−Balanced配对差95%区间分别为[3.138,31.303] MHz和[−33.741,−3.681] MHz。低频有色噪声下A2误差增至1462.481/1534.265 MHz，不能称为普遍降噪能力。上述held-out均值不应与早期三seed平方误差合并RMSE混用。

快速瞬态表现与STFT实际窗口密切相关。20 ns、0.5→4 GHz解析chirp变化区域内，40 GS/s下A2/Balanced为46.359/194.114 MHz；80 GS/s采用固定样点窗时为43.895/33.226 MHz。80 GS/s补充匹配实际窗宽与共同256样点子网格后为46.359/190.106 MHz。这支持特定窗口条件下的局部优势；全共同内部A2误差约59 MHz，不能将事件区域的获益称为全记录改进。

| 可引用结果 | 原始数据，均相对于TASK005正式run | TASK006独立证据 |
| --- | --- | --- |
| 无噪与网格密度 | `grid_metrics.csv`、`grid/*/common.npz` | `grid_recomputed.json`、`arithmetic_audit.json` |
| 白噪/有色/带限噪声 | `synthetic_metrics.csv`、`evaluation/*/{recipe.json,common.npz}` | `metrics_recomputed.json`、`paired_statistics.json` |
| 20 ns事件及物理窗 | 同上，scope=event，物理窗method带physical | `paired_statistics.json`中A2与A2_physical分列 |
| 多分量失败与峰排序 | 同上，group=branches，support字段 | 全量数组重算及代表性算法复现 |
| 14通道描述性结果 | `real_channel_index.json`、`real/*/` | `real_output_audit.json` |
| 单次设备成本64.106/68.321倍 | `performance/*.stdout.txt`、`time_memory_comparison.csv` | `decision_audit.json`、`supplemental_audit.json` |

TASK005正式run为 `artifacts/TASK-CWT-005/run_20261030_221635_70d83adf/`；TASK006证据位于 `artifacts/TASK-CWT-006/`。科研正文引用表格时应同时给出条件、单位、统计口径与具体数据路径，不能只引用本文件的叙述。

## 可使用图件及图注

图件均直接复用真实生成的PNG及对应派生数据，未通过截图重新制造。TASK006对四幅汇总图重新执行原绘图程序，PNG与历史文件逐字节一致。论文编排可以改变图号，下面的来源和解释限制须保留。

| 建议图号及原文件（相对TASK005 run） | 可直接编辑的图注 |
| --- | --- |
| 图X-1 `figures/grid_density.png` | 不同voices/octave下的合并频率RMSE（MHz）。12个冻结off-grid频率覆盖三频段，比较无噪恒频、0 dB恒频和无噪线性chirp；40/80 GS/s分别以实线/虚线表示。频网格密化不等于双频物理分辨力提高。 |
| 图X-2 `figures/heldout_weak_signal.png` | 白噪声条件下三频段与两采样率的平均波形RMSE（MHz、对数轴）；横轴为输入SNR（dB），每条件20条独立波形。A1低频低SNR严重退化，A2优势依赖条件。 |
| 图X-3 `figures/transient_window_mechanism.png` | 0.5→4 GHz解析chirp在不同持续时间下的变化区域误差。左列固定STFT样点窗，右列匹配物理时间窗并使用对应共同子网格；不能跨面板混用评价时刻。 |
| 图X-4 `real/20260607_voltage_col2/spectral_support.png` | 同一真实电压通道的五种响应及strongest候选，横轴为原始绝对时间μs，纵轴GHz。dB为记录响应参考而非SNR，A2为探索性，灰区标记边缘风险；未标定真实运动支路。 |
| 图X-5 `real/ch3_voltage_col1/spectral_support.png` | 真实ch3通道的高频带、低频结构与宽带瞬态的描述性比较。轨迹仅为候选，真实噪声和物理真值UNKNOWN，不能据此报告真实准确率或速度。 |

图X-4/X-5只适用于已授权展示的实验派生图；论文正式公开前的数据使用权与实验元信息仍应由作者确认。本材料本身未发布或上传图件。应避免单凭局部截图裁去低支持区域，使读者误认为全部候选均有可靠谱证据。

## 讨论与结论正文建议

复Morlet CWT在固定研究参数下显示出局部研究价值。其尺度自适应窗口在特定低频白噪声和快速变化条件中可以降低候选频率误差，但表现受采样率、物理窗口、噪声PSD、评分归一化和频段影响。高频弱信号与强干扰场景保留严重失败，A0尺度偏差并未消失，A1可能放大低SNR误选，A2的独立噪声校准也不直接适用于未知真实实验噪声。因此，本研究结论为NICHE_ONLY，不支持全面替代STFT。

真实数据的14个通道均具备可复查时频结构和候选输出，但缺少独立物理ground truth及完整光学条件。双分量实验中正确频率可同时出现在Top3而strongest仍100%选错弱目标，这表明频谱信息存在与目标支路恢复必须分开评价。计算成本也限制了工程适用性：单设备单次测量中A2/24总分析耗时约为Balanced的64—68倍，此比值不构成跨设备上界。

论文中不应使用“CWT全面优于STFT”“CWT可以去除背景噪声”“CWT已解决真实PDV错误支路”“CWT能精确识别真实起跳时刻”或“全部真实数据已获得可靠速度”等陈述。旧规划中的四篇论文未在本轮获得足够来源核验，标记为unverified，不应直接导入已核实参考文献表。本文件引用的官方API资料也不替代PDV领域文献综述。

复现环境还需注明PyWavelets distribution metadata 1.10.0与module 1.8.0的差异、实际源码哈希及其来源尚未闭合的限制。可编写为：“本研究结果在所保存的Python3.12环境及代码快照中得到数值复现；第三方包内部版本标识存在差异，发行来源仍待独立核验。”完整依据见 `CWT_RESEARCH_FINAL.md` 与 `TASK-CWT-006_REPORT.md`。
