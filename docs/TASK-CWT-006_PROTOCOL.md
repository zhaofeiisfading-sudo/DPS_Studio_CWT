# TASK-CWT-006 科学审计与阶段结题协议

执行日期：2026-10-31（Asia/Shanghai）；本协议先于本任务数值复算创建。

## 检查范围与边界

目标是检验 TASK-CWT-002—005 的方法、证据、可复现性及阶段结题条件，不预设沿用 NICHE_ONLY。初始独立仓库 HEAD 为 adc6f198dcba5766da456d4b516380d93d3b14fd，分支 research/cwt-morlet，工作树和暂存区干净，origin 为既有 GitHub 地址。审查实际工作树及源码快照，不以 HEAD 代替实验源码证据。

允许新增本协议、TASK006 报告、最终研究报告、毕业设计材料、复现说明，以及必要的 benchmarks 审计模块和 tests；新结果仅写 artifacts/TASK-CWT-006，缓存仅 .local_cache，仓库外仅指定的轻量 Obsidian 日志。历史配置、原始结果、默认 raw strongest、CWT 核心及一级目录不变。不安装依赖，不更改 Git 索引、历史或 remote，不访问 Production/兄弟项目，不执行后续任务。真实 raw 仅只读计算起止完整文件集合、大小、SHA-256；复核通道使用保存的派生结果和映射，不重复真实波形分析。

## 复算设计

输入是历史协议、源码、配置、合成 recipe、完整共同格点预测/真值/掩码、校准结果、性能 JSON 与真实通道索引。单位使用 s、V、Hz，报告频率误差换算 MHz；真实光学条件和真值未知，不计算真实速度或准确率。

独立指标审计直接从保存数组计算 RMSE、MAE、bias、灾难率和支路错误率，核对全量行、缺失值和非有限值；按 recipe 和 split_registry 检查完整性、种子隔离及固定配置。关键配对以独立波形为统计单元，用 10000 次固定种子 bootstrap 计算 95% 描述区间；GO 使用历史定义的 97.5% 区间及偏差、灾难、成本门槛，不改历史评价范围。另检查固定物理窗仅在其对应共同子网格比较。

算法复现预先选择各采样率首个注册的无噪恒频、低频白噪声−10 dB、高频白噪声−10 dB、20 ns chirp、弱目标2 GHz/强干扰0.5 GHz双分量、白纯噪声。使用历史 recipe、种子、143尺度、precision18及保存的 A2 校准，重算完整输入 CWT 和两种 STFT，直接核对共同格点预测和输入哈希。无噪 grid 同时检查24/48/96 voices。选择覆盖获益和严重失败，不重新运行1840条算法，也不调参。指标重算与算法复现分开记数。

## 环境、归档与判定

先加载 scripts/cwt_env.ps1，显式使用 .local_cache/venv/Scripts/python.exe。记录解释器、distribution metadata、模块路径、版本文件、实际 cwt 签名/源码/哈希、RECORD 一致性、路径覆盖和历史源码一致性；只读查找根因，不能确认发行来源则记 UNKNOWN。仅检查 Git 历史路径元数据，不读取历史 raw blob。

final_manifest.json 索引关键历史及本任务文件的仓库相对路径、大小、SHA-256、依赖组与源码状态；不收录 raw 内容、环境缓存、凭证。manifest 排除自身以避免自引用，记录该规则；提供只读验证入口。Git 忽略的 artifacts 必须单独备份，仅 Git 不能恢复完整研究结果。

工程 PASS 要求所需交付、复算和检查完成且边界完整；存在未解决来源或证据限制则 LIMITED，仓库或 raw 完整性失败则 BLOCKED。科学分别判断 GENERAL_REPLACEMENT_SUPPORTED、NICHE_ONLY、NOT_SUPPORTED、AUDIT_INCONCLUSIVE；已确认错误、证据不足、机制解释、直接数值证据分开记录。历史通用替代门槛未通过不得用事后获胜条件替代。允许在依赖来源保留疑点的前提下作有边界的阶段结题，须明确证据可复现范围。

## 验收及输出

输出 docs/TASK-CWT-006_REPORT.md、docs/CWT_RESEARCH_FINAL.md、docs/CWT_FOR_GRADUATION_THESIS.md、docs/REPRODUCIBILITY.md；artifacts/TASK-CWT-006 下保存独立指标、配对统计、GO复核、少量算法复现、环境审计、raw前后哈希、Git历史路径风险、最终manifest及检查日志。Obsidian 更新同一篇2026-10-31_TASK-CWT-006_CWT研究结题与归档.md。

执行 pytest、ruff check .、mypy --strict src tests benchmarks、新增 scripts（如有）的单独严格检查、git diff --check、git diff --cached --check。新增审计测试必须包含篡改哈希、缺失索引、参数不一致、指标/判定错误及写入边界等失败模式。记录实际命令、版本、结果及失败，不以历史通过替代本轮通过。完成 TASK006 后停止。
