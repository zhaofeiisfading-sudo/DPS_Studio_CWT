# TASK-CWT-003 执行合同

日期：2026-10-30。目标分支：research/cwt-morlet。初始独立 Git 仓库及工作树均核验；工作树与暂存区干净，origin 为原有 GitHub DPS_Studio_CWT 地址。不改变索引、历史或远程。

目标为全量文件审计、全部有效原始通道 CWT 时频图覆盖及可重复后端。当前用户任务覆盖旧计划中的 TASK-003 对照安排：本任务不做 STFT 比较。

允许修改本仓库既有 src、tests、configs、scripts、docs 根内的任务文件；持久产物仅写 artifacts/TASK-CWT-003，缓存仅 .local_cache。raw_data 仅只读遍历、解析、SHA-256；其他项目、父目录及 Production 不写入。仓库外只更新指定 Obsidian 轻量摘要。所有路径拒绝 reparse point。保留已有文件及旧产物，不清理、不覆盖 raw。

输入为 raw_data 实际全部文件（包括隐藏占位文件）；用户于本聊天明确确认全部 10 个数值文件为原始 PDV 波形，第 1 列时间 s，其他列为独立电压 V。配置逐文件记录此依据与列索引，不根据数值量级推单位。无表头 DAT 可按相同明确映射读取；result DAT 按处理结果排除并保留清单。波长、光学偏置、噪声模型未知；不默认 1550 nm、零偏置、sigma=0。真实速度不计算，不推断通道的实验含义。

算法固定 cmor1.5-1.0、FFT、precision=18、初始 0.1–6 GHz、24 voices/octave、raw abs(W)，复用已有 core。内部 SI 为 s、V、Hz、m/s、m。Nyquist 或离散尺度混叠不合格时报错并记录，不能偷偷调整。禁止重采样、平滑、裁剪、补点、删点、连续性修复。完整 CWT 优先，分配前估算内存；如需分块则必须先合成验证，不以时间抽段替代全记录。只允许图像显示矩阵明确抽列；完整候选仍逐样点导出。

输出为逐文件输入审计与哈希、逐通道时频图/候选诊断 CSV/metadata/status、批次清单和汇总、完整技术报告、轻量 Obsidian 索引。未知光学条件标 SCALOGRAM_ONLY；质量 UNKNOWN 与筛查失败区分，不删除候选。真实数据不报告 RMSE 或支路正确率。

验收：全部文件均有记录，有效通道全部尝试并分别统计图件与速度状态；合成 fixture 验证 Reader、多通道、SI 转换、异常输入、失败隔离、输出一致性、内存预算、raw 只读和哈希。运行全部 pytest、ruff check .、mypy --strict src tests benchmarks、git diff --check、git diff --cached --check，保存真实输出与工具版本。任务结束全量复核 raw SHA-256 及文件集合，不自动启动下一任务。

已知未知：物理通道用途、波长、偏置、噪声分布、独立真值；任何诊断或曲线连续性都不能认证真实界面速度。
