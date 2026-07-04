# 商品期货每日深度分析 — 自动化任务设计文档

> **版本**: v2.10  
> **更新时间**: 2026-06-25  
> **关联自动化**: `automation-1782228336539`  
> **执行时间**: 每日 19:00 (北京时间)  
> **目标仓库**: [CTAAgents/quant-skills](https://github.com/CTAAgents/quant-skills)

---

## 目录

1. [架构概览](#1-架构概览)
2. [数据源体系](#2-数据源体系)
3. [完整工作流](#3-完整工作流)
4. [多Agent辩论机制](#4-多agent辩论机制)
5. [期限结构与基差分析](#5-期限结构与基差分析)
6. [置信度计算体系](#6-置信度计算体系)
7. [报告产出规范](#7-报告产出规范)
8. [自动化配置](#8-自动化配置)
9. [涉及的Skill清单](#9-涉及的skill清单)

---

## 1. 架构概览

### 设计目标

每天收盘后（19:00），自动化扫描中国五大期货交易所全部品种，通过量化管道筛选高置信度交易机会，然后启动多Agent辩论系统深度分析 Top 品种，最终产出结构化HTML报告。

### 核心原则

| 原则 | 说明 |
|------|------|
| **数据源优先级铁律** | 交易所官方API > AKShare > 历史缓存 (盘后不可用TqSdk) |
| **自下而上分析** | 先逐品种信号扫描，再产业链交叉验证 |
| **置信度优先** | 胜率优先于赔率，避免追高/追空 |
| **右侧交易** | 仅基于已确认信号，禁止左侧猜测 |
| **果断决策** | 研究主管和风险主管必须输出 BUY/SELL/HOLD |
| **多Agent隔离** | Agent之间不得直连，所有信息经主理人中转 |

### 系统层次

```
┌──────────────────────────────────────────────────────────┐
│                    定时任务调度层                          │
│              automation-1782228336539                     │
│              FREQ=DAILY;BYHOUR=19;BYMINUTE=0              │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                    数据采集层                              │
│  exchange-futures-data (交易所DuckDB)                     │
│  AKShare (现货价格, 降级源)                                │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                    量化管道层                              │
│  futures-industry-chain-analysis                         │
│  run_pipeline.py → 信号筛选 → 产业验证 → 期限/基差        │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                    多Agent辩论层                           │
│  futures-trading-analysis (12 Agent, 5 Phase)            │
│  Phase 1(4并行) → Phase 2(多空辩论) → Phase 3(交易员)     │
│  → Phase 4(三方风险) → Phase 5(汇总报告)                   │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                    报告产出层                              │
│  chain_report.html + analysis_*.html + quick_*.html       │
└──────────────────────────────────────────────────────────┘
```

---

## 2. 数据源体系

### 2.1 数据源优先级 (盘后19:00专用)

```
优先级: 交易所官方API > AKShare > 历史缓存
         ↑               ↑          ↑
      主力源          降级备选    最后手段
  (exchange-futures)  (-20%置信度)
```

### 2.2 TqSdk 角色说明

| 场景 | TqSdk | 原因 |
|------|-------|------|
| 盘中分析 | ✅ 主力实时源 | 交易时段有实时行情 |
| 盘后19:00 | ❌ 不可用 | 夜盘21:00才开盘，19:00无数据连接 |

### 2.3 数据时效性保障

```
时间线:
  15:00  上期所/广期所收盘
  15:15  大商所/郑商所收盘
  15:30  中金所收盘
  17:00  日线数据发布窗口开启 (~收盘后30分~2小时)
  19:00  定时任务执行 (距离收盘3.5~4小时)
```

**时效性验证规则**：
- 收盘日期必须 == 当前交易日(T日)
- T-1数据视为过期，自动切换数据源
- 交易所API + AKShare 交叉验证，偏差 > 0.5% 调查标注

### 2.4 数据源对应的数据维度

| 数据维度 | 数据源 | 状态 |
|---------|--------|------|
| OHLCV (全合约) | 交易所官方API → DuckDB | ✅ 主力源 |
| 结算价 | 交易所官方API → DuckDB | ✅ 主力源 |
| 持仓量 | 交易所官方API → DuckDB | ✅ 主力源 |
| 期限结构 | DuckDB (从OHLCV推算) | ✅ 派生数据 |
| 现货价格 | AKShare futures_spot_price() | ⚠️ 降级源(-20%) |
| 基差率 | AKShare现货 + DuckDB期货 | ⚠️ 混合源 |

---

## 3. 完整工作流

### Step 0: 前置数据准备 (~19:00-19:02)

```bash
# 1. 确保 DuckDB 中有当日交易所数据
cd ~/.workbuddy/skills/exchange-futures-data
python3 -c "
from scripts.exchange_data_collector import ExchangeDataCollector
c = ExchangeDataCollector()
trade_date = c.get_latest_trading_day()
print(f'交易日: {trade_date}')
df = c.get_all_exchange_data(trade_date, use_cache=True)
print(f'数据条数: {len(df) if df is not None else 0}')
"
```

### Step 1: 产业链全景管道 (~19:02-19:05)

```bash
cd ~/.workbuddy/skills/futures-industry-chain-analysis
python3 scripts/run_pipeline.py
```

管道内部7个阶段：

```
Phase 1:   加载 market_data.json → 解析全品种技术指标
Phase 1.5: term_basis.py → DuckDB期限结构 + AKShare现货→基差
Phase 2:   产业链聚类 (12链, 用于交叉验证)
Phase 3:   信号筛选 (score≥20, resonance≥50%, 排除趋势末期)
Phase 4:   逐品种辩论+产业链验证+置信度计算+交易方案
Phase 5:   置信度降序排序
Phase 6:   Top 10 风险评估
Phase 7:   生成 chain_report_{YYYYMMDD}.html/.md
```

**输出**: `chain_report` 含置信度排名、方向、交易方案、期限结构/基差信号

### Step 2: 智能筛选

从管道输出中按置信度分档：

| 档位 | 阈值 | 分析深度 | 产出 |
|------|------|---------|------|
| 第一档 | ≥ 0.85 | 完整5阶段 | `analysis_{code}_{date}.html` |
| 第二档 | 0.70 ~ 0.84 | 快速2阶段 | `quick_{code}_{date}.html` |
| 淘汰 | < 0.70 | 不分析 | — |

### Step 3: Top 2 完整分析 (5阶段辩论)

为每个第一档品种创建独立 Team，走完整 Workflow A。详见 [第4节](#4-多agent辩论机制)。

### Step 4: Top 3-5 快速分析 (2阶段简化)

跳过辩论和风险评估，仅市场分析师+基本面分析师→交易员。

### Step 5: 报告落盘

```powershell
New-Item -ItemType Directory -Force -Path "Reports\商品期货深度分析\$(Get-Date -Format 'yyyy-MM-dd')"
```

**输出**: 单文件自包含HTML，直接双击浏览器打开。
文件名: `daily_analysis_{YYYYMMDD}.html`

```
Reports/商品期货深度分析/2026-06-25/
└── daily_analysis_20260625.html      # 唯一文件 (全部内容合并)
    ├── 📄 封面/头版                  
    ├── 📊 产业链全景                  
    ├── 🔬 Top 1 深度分析 (6图表)      
    ├── 🔬 Top 2 深度分析 (6图表)      
    ├── ⚡ Top 3-5 快报 (简化)         
    └── 📋 页脚 (数据源+免责)          
```

产出：**单文件自包含HTML**

```
Reports/商品期货深度分析/2026-06-25/
└── daily_analysis_20260625.html      # 唯一的完整报告 (自包含)
    ├── 📄 封面/头版: 标题、日期、数据源、执行时间
    ├── 📊 产业链全景: 12链信号 + Top 10置信度排名
    ├── 🔬 Top 1 深度: 完整6图 (决策卡/雷达/走势/多空/风险/文本)
    ├── 🔬 Top 2 深度: 完整6图
    ├── ⚡ Top 3 快报: 简化版 (决策卡+数据表+结论)
    ├── ⚡ Top 4 快报: 简化版
    ├── ⚡ Top 5 快报: 简化版
    └── 📋 页脚: 数据源汇总 + 时间戳 + 免责声明
```

---

## 4. 多Agent辩论机制

### 4.1 团队构成 (12人)

```
主理人 (何执舟, Chief Strategist)
  │  编排调度，不直接做分析
  │
  ├─ Phase 1: 数据收集层 (4人并行)
  │   ├── market-analyst      技术分析 (含期限结构 ★)
  │   ├── fundamentals-analyst 基本面分析 (含基差分析 ★)
  │   ├── news-analyst         新闻/政策/宏观
  │   └── sentiment-analyst    资金流向/情绪
  │
  ├─ Phase 2: 辩论层 (3人串行)
  │   ├── bull-researcher      构建多头论证
  │   ├── bear-researcher      构建空头论证 (看到多头论证后反驳)
  │   └── research-manager     裁判 → [投资计划]
  │
  ├─ Phase 3: 执行层 (1人)
  │   └── trader               交易提案 (入场/目标/止损)
  │
  ├─ Phase 4: 风控层 (3人并行 + 1人裁决)
  │   ├── aggressive-risk-analyst   激进 (强调上行)
  │   ├── conservative-risk-analyst 保守 (强调下行)
  │   ├── neutral-risk-analyst      中性 (分批/对冲)
  │   └── risk-manager              裁决 → [最终交易决策]
  │
  └─ Phase 5: 报告层 (主理人)
      └── 生成 Markdown + HTML 报告
```

### 4.2 信息流规则 (铁律)

```
所有跨Agent信息必须经主理人中转:

  Phase 1产出 → SendMessage → 主理人 → 转交 → bull-researcher
  bull输出    → SendMessage → 主理人 → 转交 → bear-researcher
  双方输出    → SendMessage → 主理人 → 转交 → research-manager
  ...
  
  Agent之间禁止直连通信
```

### 4.3 辩论机制详解

**设计理念**: 空头研究员能看到多头论证，实现"针对性反驳"而非"闭门造车"。

```
[4份分析报告]
     │
     ▼
bull-researcher: "为何看多"
  ·技术面：MA多头排列+MACD金叉
  ·基本面：backwardation结构+库存低位
  ·资金面：主力增仓+北向持续流入
     │
     ▼ (多头论证全文)
bear-researcher: "为何看空" (逐条反驳)
  ·技术面：RSI已达超买区，动能衰减
  ·基本面：backwardation可能因交割月临近加剧
  ·资金面：主力增仓可能是套保盘
     │
     ▼ (多空论证)
research-manager: 裁判
  ·裁决: BUY
  ·理由: 多空论点权重对比 (多头7:空头3)
  ·信心: 高
  ·方向: 多头，建议持仓3-5个交易日
     │
     ▼
  [投资计划]
```

### 4.4 三方风险辩论

```
[交易员决策] + [投资计划]
     │
     ├── aggressive:  "backwardation意味现货紧，CTA资金还在追"
     ├── conservative: "限产政策随时反转，成本支撑是幻觉"
     └── neutral:      "方向对但仓位要轻，分3批建仓"
     │
     ▼
risk-manager: 最终裁决
  ·裁决: BUY
  ·仓位: 3% (中性建议的中间值)
  ·风控: ATR×2.0止损, 单笔最大亏损 < 总资金2%
```

### 4.5 Agent命名规范

调度Agent时必须使用 `name` + `subagent_type` 参数：

| name 值 | 角色 |
|---------|------|
| `market-analyst` | 市场技术分析师 |
| `fundamentals-analyst` | 基本面分析师 |
| `news-analyst` | 新闻分析师 |
| `sentiment-analyst` | 情绪分析师 |
| `bull-researcher` | 多头研究员 |
| `bear-researcher` | 空头研究员 |
| `research-manager` | 研究主管 |
| `trader` | 交易员 |
| `aggressive-risk-analyst` | 激进风险分析师 |
| `conservative-risk-analyst` | 保守风险分析师 |
| `neutral-risk-analyst` | 中性风险分析师 |
| `risk-manager` | 风险主管 |

---

## 5. 期限结构与基差分析

### 5.1 模块位置

`futures-industry-chain-analysis/scripts/term_basis.py`

### 5.2 期限结构 (主力源: DuckDB)

```
从 exchange-futures-data DuckDB 提取全品种全合约数据
  │
  ▼
按 symbol 排序 (天然按交割月)
  │
  ├─ 近月: 成交量最大的前2个合约
  ├─ 远月: 成交量大于0的最远合约
  │
  ▼
斜率 = (远月收盘 - 近月收盘) / 近月收盘
  │
  ├─ slope >  +2% → contango      → 利空 (供应宽松)      → score: -5
  ├─ slope <  -2% → backwardation → 利多 (现货紧缺)      → score: +5
  └─ others       → flat          → 中性                  → score:  0
```

### 5.3 基差分析 (降级源: AKShare)

```
AKShare.futures_spot_price(symbol) → 现货价
   +
DuckDB 近月合约收盘价 → 期货价
  │
  ▼
基差率 = (现货价 - 期货价) / 期货价 × 100%
  │
  ├─ > +3%  → 期货低估 → 利多 → score: +6 (权重10%, DuckDB现货则10%)
  ├─ > +1%  → 温和低估 → 利多 → score: +3
  ├─ < -3%  → 期货高估 → 利空 → score: -6 (权重 7%, AKShare降级惩罚)
  ├─ < -1%  → 温和高估 → 利空 → score: -3
  └─ others → 合理区间 → 中性 → score:  0
```

**降级惩罚**: AKShare为降级数据源，基差权重从10%降至7%，报告中红色标注"现货数据: AKShare(降级,-20%)"。

### 5.4 覆盖品种 (55个)

黑色系、能源链、聚酯链、油化工、煤化工、有色、贵金属、油脂油料、谷物软商品、建材、橡胶、新品种。

---

## 6. 置信度计算体系

### 6.1 公式 (v2.10)

```
置信度 = 40% × 信号强度
       + 20% × 指标共振 (RSI/MACD/DMI三指标同向比例)
       + 20% × 产业链验证 (产业链方向是否一致, ±20%调节)
       + 20% × 期限/基差
              ├── 10% 期限结构 (contango/backwardation信号)
              └── 7~10% 基差分析 (权重取决于数据源)
```

**旧版 (v2.9)**: 50% + 25% + 25% — 缺少期限/基差维度。

### 6.2 置信度调节因子

| 调节事件 | 影响 |
|---------|------|
| 产业链同向共振 | +20% |
| 产业链方向背离 | -10% |
| 辩论结果与信号一致 | 不调整 |
| 辩论结果为HOLD | ×0.85 |
| 辩论结果与信号矛盾 | ×0.60 |
| 偏空市场做多 | ×0.80 |
| 偏多市场做空 | ×0.80 |
| 使用降级数据源 | ×0.80 |

### 6.3 筛选阈值

| 阈值 | 含义 |
|------|------|
| ≥ 0.85 | 第一档 (深度分析) |
| 0.70 ~ 0.84 | 第二档 (快速分析) |
| 0.40 ~ 0.69 | 记录但不推荐 |
| < 0.40 | 自动过滤 |

---

## 7. 报告产出规范

### 7.1 HTML报告必须包含6个可视化板块

1. **决策卡片**: BUY/SELL/HOLD标识 + 入场/目标/止损/仓位四宫格
2. **雷达图**: 技术面/基本面/新闻面/情绪面/风险面五维评分
3. **价格走势图**: 60日K线 + SMA20/60 + 目标/止损线
4. **多空论点对比**: 水平柱状图, 每条论点带权重值
5. **风险三角图**: 激进/保守/中性三方评分
6. **详细文本区**: 四维摘要 + 辩论结论 + 风险结论 + 催化剂/风险列表

### 7.2 数据标注规范

每份报告必须包含：

```
data_time:   "截至 2026-06-25 18:55"     # 数据截取时间
report_time: "报告生成于 2026-06-25 19:12" # 报告生成时间
数据源标注:  "交易所官方API(DuckDB)"        # 标明优先级
现货源标注:  "AKShare(降级,-20%)"          # 降级源红色
收盘日期:    "20260625 (T日)"              # 时效性验证
```

---

## 8. 自动化配置

### 8.1 定时任务

```yaml
automation_id: automation-1782228336539
name: "商品期货每日深度分析"
schedule: FREQ=DAILY;BYHOUR=19;BYMINUTE=0
timezone: Asia/Shanghai
status: ACTIVE
expert: TradingAgentTeam
model: deepseek-v4-pro
model_is_thinking: true
workspace: C:\Users\yangd\Documents\WorkBuddy
```

### 8.2 执行Prompt (完整版)

```
执行商品期货每日深度分析（19:00盘后执行，确保数据齐全）。步骤：

⚠️ 数据源优先级与时效性铁律（盘后19:00专用）：
- 执行时间为19:00，上海期货交易所15:00收盘、大连/郑州15:15收盘、中金所15:30收盘，
  各交易所日线数据通常在17:00-18:00前全部更新完毕
- 优先级：交易所官方API(exchange-futures-data) > AKShare(降级备选) > 历史缓存(最后手段)
- TqSdk不参与盘后19:00数据源链条：中国期货市场夜盘21:00开盘，19:00时TqSdk大概率无数据连接；
  TqSdk仅用于盘中分析（交易时段内实时行情），盘后分析跳过TqSdk
- 收盘价时效性验证：获取数据后必须验证收盘日期==当前交易日（T日），
  如数据日期为T-1则视为过期，必须切换数据源重试
- 交叉验证：用交易所官方API与AKShare交叉验证收盘价，偏差>0.5%需调查并标注
- 使用降级源时置信度-20%，报告中必须红色标注数据来源
- 所有数据必须标注data_time（数据截取时间）和report_time（报告生成时间），
  格式"截至 YYYY-MM-DD HH:MM"

0. 前置数据准备（新增）：
   - 先运行 exchange-futures-data 技能确保 DuckDB 中有当日数据
   - 这样可以确保 term_basis.py 能从 DuckDB 中提取当日全品种期限结构

1. 产业链全景：
   - 首先尝试 exchange-futures-data 获取交易所官方日线数据（主力数据源）
   - 交易所API失败才用 AKShare（降级，置信度-20%）
   - 运行 python3 run_pipeline.py 获取12产业链信号+置信度排名
   - 管道内已含期限结构+基差分析：term_basis.py 自动从 DuckDB 提取期限结构
     (contango/backwardation)，从 AKShare 获取现货价计算基差率，注入置信度计算（权重20%）
   - 管道输出必须标注数据来源和收盘日期

2. 智能筛选：置信度≥0.7且方向明确(BUY/SELL)的品种，按置信度降序分两档

3. Top 2完整分析：启动futures-trading-analysis 5阶段
   （市场/基本面/新闻/情绪分析师→多空辩论→交易员→三方风险→HTML报告）
   - 给 market-analyst 追加任务：分析该品种期限结构（升水/贴水、曲线形态）
   - 给 fundamentals-analyst 追加任务：计算基差率，基差率<-3%为期货高估（空头信号），
     基差率>+3%为期货低估（多头信号）

4. Top 3-5快速分析：仅市场+基本面分析师→交易员决策→简化HTML报告

5. 综合报告输出：
   - 先创建日期子目录
   - 产业链全景：chain_report_{YYYYMMDD}.html/.md
   - Top 2深度：analysis_{code}_{YYYYMMDD}.html
   - Top 3-5快报：quick_{code}_{YYYYMMDD}.html
   - 所有报告必须包含：数据源标注(含优先级)、收盘日期验证、
     data_time、report_time、期限结构方向（contango/backwardation/flat）、
     基差率（含现货数据来源标注）

数据源: 交易所官方API(exchange-futures-data) > AKShare > 历史缓存
        （TqSdk盘后不可用，不列入优先级）
基差现货源: AKShare.futures_spot_price()
           （降级源，报告中标注"现货数据: AKShare(降级,-20%)"）
铁律: 禁止使用T-1日过期数据，确保收盘价=T日收盘，需时间戳+来源标注+交叉验证
```

---

## 9. 涉及的Skill清单

| Skill | 版本 | 角色 |
|-------|------|------|
| `exchange-futures-data` | v3.0 | 数据采集 (5交易所API → DuckDB) |
| `futures-industry-chain-analysis` | v2.10 | 量化管道 (信号筛选+产业链验证+期现结构) |
| `futures-trading-analysis` | v1.0 | 多Agent辩论 (12 Agent, 5 Phase) |
| `term_basis` (模块) | v1.0 | 期限结构+基差 (term_basis.py) |
| `neodata-financial-search` | v1.0.1 | 备用数据查询 |

### 本次更新文件清单

```
新增:
  skills/futures-industry-chain-analysis/scripts/term_basis.py

修改:
  skills/futures-industry-chain-analysis/scripts/trade_plan.py   (置信度公式重构)
  skills/futures-industry-chain-analysis/scripts/run_pipeline.py  (注入term_basis)

文档:
  docs/commodity-futures-daily-analysis.md  (本文档)
```

---

## 附录: 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-24 | 初始版本, 15:30执行 |
| v2.0 | 2026-06-25 | 执行时间改为19:00, 确立数据源优先级 |
| v2.1 | 2026-06-25 | TqSdk移出盘后优先级链条 |
| v2.10 | 2026-06-25 | 新增期限结构+基差分析模块, 置信度公式重构 |

---

> ⚠️ 免责声明: 本系统由AI基于公开市场数据自动生成分析，仅供研究参考，不构成任何投资建议。期货交易风险极高，可能导致本金全部损失。实际交易决策请咨询持牌专业顾问。
