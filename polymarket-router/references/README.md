# Quant Skills

个人量化交易技能集合，基于 WorkBuddy Skill 框架。

技能统一存放在 [`skills/`](./skills/) 目录下，每个 skill 包含 SKILL.md、脚本、参考文档和测试。

## 技能一览

### 📈 能源
| Skill | 说明 | 版本 |
|-------|------|------|
| [crude-oil-daily-news](./skills/crude-oil-daily-news/) | 国际原油每日资讯（WTI/布伦特），四层分析框架+20项技术指标 | v9.0 |
| [energy-chain-analysis](./skills/energy-chain-analysis/) | 能源产业链整体分析（SC/BU/FU/LU/PG），五层量化打分+七步决策法 | v2.19.0 |

### 💎 贵金属
| Skill | 说明 | 版本 |
|-------|------|------|
| [precious-metals-daily-news](./skills/precious-metals-daily-news/) | 贵金属每日资讯（黄金/白银/铂钯），19项技术指标+右侧交易原则 | v4.3.0 |
| [precious-metals-data-validation](./skills/precious-metals-data-validation/) | 贵金属数据标准化采集与验证，多源交叉校验 | v2.0.0 |
| [precious-metals-trading-decision](./skills/precious-metals-trading-decision/) | 三层架构贵金属交易决策（宏观→载体→多周期），R1-R5 Regime诊断 | v3.0.0 |

### 🔩 期货
| Skill | 说明 | 版本 |
|-------|------|------|
| [futures-industry-chain-analysis](./skills/futures-industry-chain-analysis/) | 12大产业链自动化分析，自下而上+置信度优先，67+品种 | v2.9.1 |
| [futures-trading-analysis](./skills/futures-trading-analysis/) | 多角色辩论式交易分析，12专业Agent，单品/产业链双模式 | v1.0 |

### 📊 数据
| Skill | 说明 | 版本 |
|-------|------|------|
| [exchange-futures-data](./skills/exchange-futures-data/) | 中国五大期货交易所（DCE/SHFE/CZCE/CFFEX/GFEX）官方数据采集 | - |

### 🎯 预测市场
| Skill | 说明 | 版本 |
|-------|------|------|
| [polymarket-router](./skills/polymarket-router/) | PolyMarket多源数据集成路由系统，智能路由引擎，支持多数据源自动故障转移、健康监控、本地缓存、动态发现和智能路由 | v1.0 |

### 🛠 工具
| Skill | 说明 |
|-------|------|
| [goal](./skills/goal/) | `/goal` 会话目标管理 |
| [grill-me](./skills/grill-me/) | 深度压力测试，系统性拷问计划/设计 |
| [loop](./skills/loop/) | `/loop` 循环执行任务 |

### 🧠 量化框架
| Skill | 说明 | 版本 |
|-------|------|------|
| [skillevolver](./skills/skillevolver/) | 面向在线技能学习的元技能自演化框架 | v2.0 |
| [skill-adaptor](./skills/skill-adaptor/) | 基于轨迹的LLM智能体自适应技能，显式故障归因 | - |
| [factorengine](./skills/factorengine/) | 程序级知识注入因子挖掘框架 | v2.0 |
| [agentic-factor-investing](./skills/agentic-factor-investing/) | AI 自主因子发现与系统化投资框架 | v2.0 |
| [embodiskill](./skills/embodiskill/) | 面向具身技能自演化的技能感知反思与进化 | v2.0 |

## 统计

- 总数：**17** 个自建 Skill
- 脚本文件：200+ Python / Shell 脚本
- 测试用例：200+ 单元测试
- 覆盖市场：原油、贵金属、黑色系、有色、化工、农产品、股指等
