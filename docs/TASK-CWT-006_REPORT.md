# TASK-CWT-006 科学审计、阶段结题与归档

日期2026-10-31，Asia/Shanghai。工程verdict：**LIMITED**；科学审计verdict：**NICHE_ONLY**。当前Research具备阶段性结题条件。数值、软件回归和证据一致性检查通过；LIMITED保留依赖发行来源未闭合与历史raw路径风险。缺少真实物理真值仍限制方法泛化，不妨碍对本阶段假设作出有边界的结论。

## 范围与主要交付

本任务只新增5份文档、一个审计模块和一个测试文件，未修改核心、默认A0、旧配置或TASK002—005原始结果。协议为 `TASK-CWT-006_PROTOCOL.md`；正式研究正文为 `CWT_RESEARCH_FINAL.md`；毕业设计可编辑方法、结果、图注及不宜使用的论断见 `CWT_FOR_GRADUATION_THESIS.md`；环境恢复和重跑入口见 `REPRODUCIBILITY.md`。可执行入口为 `benchmarks/closure_audit.py`，测试为 `tests/test_closure_audit.py`。

允许路径、SI单位、输入、验收、已知未知和停止边界已在复算前写入协议。所有新实验、重绘图、源码运行时快照和审计输出位于 `artifacts/TASK-CWT-006/`；缓存仅 `.local_cache/`。真实raw只计算起止文件集合、大小和SHA-256，没有重新解析或重新运行真实变换。没有访问或修改Production、其他Research及兄弟项目。

## 各历史阶段的证据判断

| TASK | 目标与实际实施 | 本轮核验及边界 |
| --- | --- | --- |
| 002 | 合成数学内核、单位、尺度和失败模式；precision14→18收敛修订有记录 | 25个case的两评分、all/interior/edge共150区域重算一致；原首轮和脉冲外误报负结果保留。不能据此推出STFT比较或真实正确性 |
| 003 | 全量真实后端，未知光学条件仅谱图与候选 | 10波形/14通道映射及SCALOGRAM_ONLY状态匹配，1,240,002个保存native时间点完整；与后续结果逐点关联。未独立重读raw解析单位 |
| 004 | 相同输入下固定Hann-STFT比较 | 156case的common_all/common_interior共936区域重算一致；共享seed、仅3重复、事件与全域口径区别保留；既有直接FFT证据继续归档 |
| 005 | A0/A1/A2、噪声模型、off-grid及物理窗验证 | 1840held-out、16development及72×3grid的完整索引匹配；14,680指标行、配对统计、GO和成本复核；没有重跑全部held-out算法 |

审查真实源码、冻结快照、配置声明和生成recipe后，未发现跨split seed复用、根据held-out重选主评分、质量筛选低误差帧或删除严重负例的证据。TASK005各split与当前冻结生成器注册表逐项相同；开发目标重算A0/A1/A2为1.116984/136.300833/1.108302，选A2/24一致。本地记录不提供外部可信预注册时间戳，不能排除所有记录外行为。固定两组STFT是本研究具体对照，不应写成全参数空间最优STFT。

CWT和STFT读取相同合成输入；实际重跑重新生成的输入time/voltage哈希与历史一致。真实通道以保存的时间/输入哈希和跨TASK输出复核关联。时间s、电压V、频率Hz及MHz换算一致；真实速度未知，不填零。FFT补零和CWT输出密度均未被解释为物理分辨力。全部正负结果保留，2091行失败清单是方法/波形行数，不是2091个独立波形。

## 独立重算与算法复现

`arithmetic_audit.json`及 `final_confirmation/arithmetic_audit.json`记录相同重算结果：TASK005 development200行、evaluation13400行、grid1080行，共14,680行、1,135,560个频率误差点；RMSE、MAE、bias最大差1.9073486328125×10⁻⁶ Hz，与浮点求和顺序差异相容。TASK002另核150区域，TASK004另核936区域。重复确认没有被当作新增独立实验。

CSV与逐case JSON的索引、数值、缺项和重复项另行交叉核对，三个表共14,680行，无缺失索引或重复key，未发现非预期非有限指标。无真值的纯噪声误差为null，NPZ中非active真值、无局部峰rank等NaN是合同定义的缺失值，不被填成0或错误报告为数据损坏。检测阈值从保存的独立60条校准帧与逐记录max重新计算，4个rate/PSD组一致；18组噪声尺度profile的长度、有限性和正值符合定义。未重新执行120条评分噪声校准，A2的完整校准参数不确定性亦未重新估计。

`algorithm_reproduction.json`记录12条独立代表性波形、16次完整CWT：40/80 GS/s各覆盖首个无噪恒频、低频白噪声−10 dB、高频白噪声−10 dB、20 ns解析chirp、弱目标2 GHz/强干扰0.5 GHz、白纯噪声；无噪恒频另核24/48/96 voices。三评分逐共同格点候选精确一致、响应幅值满足rtol=1e-12与atol=1e-12；两组STFT候选及chirp物理窗Balanced候选精确一致。纯噪声不计算频率RMSE。`probes/*.npz`保存本轮预测；这是实际算法复现，与读取保存数组重算指标分开计数。

所有14通道的TASK005 native与TASK004 A0输出/时间精确相同；两STFT共19,380个候选亦与TASK004一致。TASK003保存的1,240,002行候选CSV另逐行关联，未以历史报告文字代替检查。详见 `real_output_audit.json`、`real_cross_task_audit.json`。这验证导出和计算关联，不验证真实运动支路、噪声FPR或物理速度。

四幅汇总图使用历史绘图程序、保存数组及summary重绘到 `figure_verification/`，与旧PNG SHA-256逐项相同，结果见 `figure_verification.json`。本轮目视查看三幅合成汇总及20260607第二电压列、ch3原始谱图；没有声称逐张精读全部真实图。正式报告优先直接链接旧原图，caption标明单位、来源和适用边界。

## 关键数值、配对区间与判决

| 条件 | A2 / Balanced平均波形RMSE，MHz | A2−Balanced的95%配对区间，MHz |
| --- | --- | --- |
| 40 GS/s，低频白噪声−10 dB | 20.280896 / 5.964491 | [3.138147,31.303372] |
| 80 GS/s，同条件 | 7.043487 / 21.214186 | [−33.740639,−3.681439] |
| 40 GS/s，低频有色−10 dB | 1462.480740 / 347.603797 | [1011.617333,1229.480984] |
| 80 GS/s，同条件 | 1534.265300 / 526.900595 | [885.751842,1122.348619] |
| 40 GS/s，8 GHz带宽低频−10 dB | 454.944609 / 683.568978 | [−430.480124,−30.905484] |
| 80 GS/s，同条件 | 490.616937 / 1800.577028 | [−1509.028785,−1114.473576] |
| 40 GS/s，20 ns chirp事件 | 46.358625 / 194.113567 | [−150.714423,−145.286335] |
| 80 GS/s，正式固定样点窗 | 43.895317 / 33.226490 | [6.758316,14.373603] |
| 80 GS/s，同物理窗及共同256网格 | 46.358625 / 190.105541 | [−145.575735,−141.988221] |

数值来自 `paired_statistics.json`，统计单元为各条件20条独立波形，bootstrap10000次，条件于冻结噪声校准。40 GS/s和80 GS/s高频白噪声−10 dB的A2分别为2207.103/1952.260 MHz，Balanced为5.830/11.686 MHz，严重负结果没有被排除。无噪A1改善和其低频低SNR数GHz损害同时成立；A2有色低频退化不能被白噪声条件优势覆盖。

GO复核严格沿用历史实现：两个预指定域、两采样率、97.5%配对区间、近零基线分支、逐波形bias/灾难率/绝对误差限制及成本。低频白噪声域仅80 GS/s通过，20 ns事件域仅40 GS/s通过，两域的双采样率门槛均False。物理窗补充不作为正式GO域。历史文字“Balanced<10 MHz”的近零判断由实现取条件平均Balanced RMSE，而不是逐波形分别切换；这是应在引用协议时明确的实现解释。本轮没有改写其规则。

同输入新进程的22条原性能stdout与汇总一致。A2/24分析耗时比为64.1060575/68.3205858，输入32768/65536点，均超过50倍门槛；峰值低于2 GiB不能抵销时间失败。计时含变换、评分和argmax，不含进程启动/导出/绘图；CWT逐样点、STFT逐128点帧输出，峰值为Windows导出前worker生命周期工作集。没有重复性能测量，因此该比值是历史单次设备观测，不是跨设备稳定上界。

少量条件的配对改善存在，但通用和工程门槛未通过，故维持NICHE_ONLY。峰presence、rank、Top-K recall、strongest和wrong-branch在解释上分离；弱目标2 GHz/强干扰0.5 GHz时Top3均100%而wrong-branch亦100%，不能视为已恢复支路。完整证据和机制讨论见正式研究报告。

## 发现、修正与未解决项

已确认的文字/标识问题是旧报告“PyWavelets1.10.0”未同时报告module1.8.0，以及TASK005 grid源码注释声称相位共用、实际recipe独立抽取相位。最终材料已明确正确解释，旧实验文件与源码注释保留原样用于溯源；未发现必须改动历史数值的已确认错误。TOML主要作参数声明，实际运行还依赖冻结Python常量，恢复说明已明确。

环境只读核验定位到单一 `pywavelets-1.10.0.dist-info`、venv内 `pywt`、module1.8.0和生成的version.py；所有有哈希的RECORD条目及大小匹配。当前cwt文件哈希为 `2bdfe87b0a326e51fbcf7f444276097c1179d42c29130619eadda4984073036b`，与TASK005一致；TASK002记录的是函数文本哈希 `9f511adf3441251a52c179ad4d4bddb463234f4f9fa74e392d0effc41d5388e9`，亦匹配，不能把两种哈希对象混比为源码变化。未发现路径覆盖证据；原始wheel构建和可信包来源仍UNKNOWN。没有安装、升级、重装或改写依赖。RECORD自洽与函数能运行均不能替代发行来源认证。

TASK002核心文件当前字节哈希与历史不等，换行规范化后全部匹配；TASK004/005冻结核心匹配。初次supplemental审计把字节差异直接当作核心变化而停止，证据保存在 `supplemental_console_01.txt`；修正为同时记录原字节与LF规范化比较，不忽略真实内容变化，最终通过。初次全量历史清单因逐文件重复检查全部祖先而过慢，停止只读进程后采用目录级验证缓存重新完整生成；真实CSV交叉核验亦将逐行重复NPZ解压改为每通道只读加载一次后重新完成。没有删除文件或把未完成检查当成功。raw完整性汇总初次PowerShell求和得到null，已从保存清单重新累计为32,086,814字节，原始逐文件哈希不变。Ruff格式与mypy标注开发失败保留在development日志，最终检查结果如下。

合理机制解释包括raw的尺度增益、A1的小尺度噪声竞争及STFT物理窗口变化；它们与数值相容，未对真实误差来源作已验证因果分解。证据不足项包括真实独立真值、实际噪声PSD、光学条件、校准不确定性、跨设备性能及可信环境重建。旧规划4篇论文未获得足够来源核验，仍标unverified，最终文本没有用其支持性能。官方PyWavelets和SciPy文档在本轮重新打开核验，只用于API/数学约定。

## 最终验收与归档边界

同一PowerShell7会话先加载 `. .\scripts\cwt_env.ps1`，使用明确venv解释器。最终命令与输出：

```powershell
& .local_cache/venv/Scripts/python.exe -m pytest
# 109 passed in 25.50s；final_pytest_02.txt
& .local_cache/venv/Scripts/python.exe -m ruff check .
# All checks passed!；final_ruff_03.txt
& .local_cache/venv/Scripts/python.exe -m mypy --strict src tests benchmarks
# Success: no issues found in 50 source files；final_mypy_03.txt
git diff --check
git diff --cached --check
# 均exit 0；对应git检查日志
& .local_cache/venv/Scripts/python.exe -m benchmarks.closure_audit verify
# 全部索引文件的路径、大小、SHA-256核验；最终输出见manifest核验证据
```

既有96测试保留，新增13项（含参数化）涵盖已知误差、无真值、非有限/shape错误、配对outlier、seed泄漏、参数错配、hash篡改、缺失/重复索引、危险路径、独占写入及科学判决门槛。最后只修正一处类型容器注解后重跑Ruff/mypy，未改变数值逻辑。没有新增独立scripts入口；审计模块包含在上述严格类型检查中。未把NOT RUN的全量算法/校准重跑或跨设备性能写成PASS。

分支/HEAD保持 `research/cwt-morlet` / `adc6f198dcba5766da456d4b516380d93d3b14fd`，origin fetch/push保持 `https://github.com/zhaofeiisfading-sudo/DPS_Studio_CWT.git`。无commit、push、pull、merge、rebase、reset、clean、remote或索引改动。普通diff和cached diff为空；7个新增文本/代码文件保持未跟踪，独立 `review.diff` 提供审查补丁。当前raw_data、artifacts、.local_cache均被忽略，均无被跟踪文件，一级目录符合规范；没有全局忽略CSV。

起止raw完整性为11/11文件路径、大小、SHA-256一致，共32,086,814字节，包含.gitkeep；见 `raw_before.json`、`raw_final.json`、`raw_integrity_final.json`。Git历史元数据仍记录5个CSV原始路径及.gitkeep，见 `git_history_raw_paths.txt`；没有读取、导出历史raw blob，也没有访问远端确认公开暴露范围。风险列出后保留，不执行历史清理。

`final_manifest.json`包含所有关键文件相对路径、大小、SHA-256、依赖关系及源代码状态；完整历史TASK002—005共11732文件、1,565,612,446字节在本轮完整归档基线与交付核验间未变，本任务没有向其写入。manifest自身不循环哈希，缓存、raw内容和Git对象库不收录。清单生成后的 `manifest_verification.json` 是后验验证凭证，单独保存，不反向纳入清单形成循环。仅有Git不足以恢复结果，必须单独保留artifacts；实际运行时源码/扩展快照也应随证据保存。

Obsidian同一轻量日志：`D:\Research\Notes\05项目\DPS_Studio_CWT\2026-10-31_TASK-CWT-006_CWT研究结题与归档.md`。报告和机器证据留在仓库，没有把完整执行过程复制到Obsidian。

建议保留STFT默认和独立CWT研究档案；后续仅在另行授权后核验可信依赖来源、处理历史raw风险，或为明确瞬态诊断需求单独立项。TASK-CWT-006完成后停止，不开展TASK007、GUI、默认算法替换或Production推广。
