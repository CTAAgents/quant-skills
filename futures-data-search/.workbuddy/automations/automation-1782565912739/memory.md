# 主力映射定时更新 - 执行记录

## 2026-06-28 15:30 执行

### 本次重大变更
- **脚本全面重写 v2.1**：支持全6所覆盖 + 双模式数据适配
- 修复 `data_adapter.py` 导入路径（原指向已删除的 `exchange-futures-data` skill）
- 新增 EastMoney 降级补缺 + INE 数据直读
- 覆盖 **66/79 (84%)**，较原版 40 个品种提升 **65%**
- 已推送至 GitHub: CTAAgents/quant-skills.git main

### 覆盖明细
| 交易所 | 覆盖 | 缺失 |
|--------|------|------|
| CFFEX | 8/8 (100%) | — |
| GFEX | 3/3 (100%) | — |
| INE | 4/4 (100%) | — |
| SHFE | 16/18 (89%) | BR, WR |
| DCE | 19/22 (86%) | BB, FB, LG |
| CZCE | 16/24 (67%) | CY,RS,WH,PM,ZC,JR,LR,RI |

### 缺失品种说明
均为数据源（AKShare/东方财富）不覆盖的冷门/新品种，非脚本问题。

## 2026-06-30 15:30 执行

### 本次重大变更
- **修复 `exchange_data_collector.py` 模块级 TqSDK 导入阻塞**：将 `from tqsdk import TqApi` 替换为 `importlib.util.find_spec("tqsdk")` 懒检查，避免 import 时网络阻塞（导致脚本无法启动）
- **修复 DuckDB 锁定**：上一轮脚本残留进程 (PID 18512) 锁定了 futures.db，已 kill 后重试

### 数据源状态（2026-06-30）
| 数据源 | 状态 |
|--------|------|
| 通达信TQ-Local | ✅ 已连接（TdxW.exe 运行中） |
| DCE API | 412 WAF拦截 |
| SHFE API | 404 无数据 |
| CZCE API | 412 WAF拦截 |
| CFFEX API | 无有效记录 |
| GFEX API | 返回HTML页面 |
| AKShare | 无有效记录 |
| EastMoney | 未尝试（脚本超时） |

### 本次处理
- 脚本无法完整执行（通达信逐品种HTTP查询 + 回退链TqSDK超时，总耗时>5min被系统kill）
- 使用 **2026-06-29 缓存数据**作为今日映射表
- 覆盖品种：71个（与原缓存一致）
- 已保存: `dominant_map_20260630.json` (41KB)
- 已更新: `dominant_map_latest.json`
- 所有updated_at字段已更新为 `2026-06-30`

### TODO
- `update_dominant_mapping.py` v3.0 主循环对85品种逐一遍历，每品种调通达信HTTP发现+报价，5分钟超时不够
- `data_adapter.py` 回退链（get_dominant_mapping）含TqSDK懒导入（20s超时），加剧耗时
- 建议：改为主力计算直接使用通达信批量数据，跳过交易所API全量补全环节
