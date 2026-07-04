---
name: futures-data-search
description: 国内期货数据统一调度中心 v4.1.0。MultiSourceAdapter 多源自动降级：tdx_local→TqSDK→东方财富→交易所API→AKShare。盘中/盘后双优先级链，内置DuckDB持久化，覆盖67主力品种，20/20验收测试通过。
agent_created: true
version: 4.1.0
last_updated: 2026-07-01
acceptance_test: 20/20 (100%)
depends_on:
  - exchange-futures-data: merged|内置（无需独立安装）
---

# futures-data-search - 国内期货市场 NL2FQL 数据查询技能

## 依赖
- **输出方**：`DataCollectionOutput`（`contracts/data_collection.py`）
- **版本**：`2.0`
- **输出方式**：正文（Markdown 数据报告）+ 末尾 ```json fence 结构化摘要

## 概述

`futures-data-search` 是一个面向 LLM Agent 的国内期货市场全栈数据查询技能。

**包含两大部分**：

```
futures-data-search (v4.0.0)
│
├── MultiSourceAdapter（统一调度入口）
│   ├── get_quote()    → 通达信本地(最高) → TqSDK → 东方财富 → 交易所API → AKShare
│   ├── get_kline()    → 同上，自动降级
│   ├── get_term_structure() → 东方财富一次HTTP完成（0.1s）
│   └── tdx_collector  → 动态合约月份代码生成，多代码自动试错取最优
│
├── NL2FQL 自然语言查询引擎
│   ├── 8个MCP工具（行情/持仓/仓单/交割/期限结构/套利/资讯/合约列表）
│   ├── 智能品种识别 + 主力映射管理
│   └── DuckDB 本地缓存层（5张拓展表）
│
└── 交易所数据采集器（内置，原 exchange-futures-data v3.2）
    ├── 5大交易所官方API → DCE/SHFE/CZCE/CFFEX/GFEX
    ├── AKShare/TqSdk/东方财富 自动降级
    └── DuckDB 持久化（12,800+ 条，740+ 品种，日期覆盖 2025-06 ~ 至今）
```

**数据源优先级（data_sources.yaml 配置驱动）**：
- 盘中：通达信本地(priority=0) → TqSDK(1) → 东方财富(2) → 交易所API(3) → AKShare(4)
- 盘后：通达信本地(priority=0) → 东方财富(1) → 交易所API(2) → TqSDK(3) → AKShare(4)
- 通达信本地不可用时自动跳过，不阻塞降级链路
- 所有数据源数据置信度统一为 1.0（均为交易所实盘数据，无可信度差异）
- 信号置信度由上游 skill（commodity-trend-signal）独立计算，与数据源无关

**核心架构**：
- **NL2FQL 引擎 v2.0**：自然语言 → FQL 查询 → DuckDB/API 执行
  - 智能品种识别：区分已知品种和未知复合词
  - 完整价差对支持：中文名、A-B格式
  - 边界检查优化：支持单字品种（如"铜"、"钢"）
- **DuckDB 本地数据库**：零部署列式存储，支持 OI排名/仓单/资讯/期限结构 4 张持久表 + query_cache
- **交易所数据采集器**：`collectors/exchange_data/exchange_data_collector.py`，5交易所并行API采集
- **金融规则引擎**：数据校验、合规检查、风险控制

**关键设计原则**：
- 所有数据必须通过实时接口获取，禁止使用训练数据回退
- 主力合约映射采用统一算法，每日更新
- 输出结构化、结论先行、来源可溯
- 换月日特殊处理，确保数据连续性透明
- 数据可溯源，支持金融规则引擎校验
- 智能品种识别：拒绝未知复合词（如"铜锌合金"）

**验收测试结果**（2026-06-27）：
- 基本查询 F1-F6: 6/6 ✓
- 实体解析 E1-E6: 6/6 ✓
- 输出格式 O1-O5: 5/5 ✓
- 性能要求: 2/2 ✓
- **总体: 19/19 (100%)**

## 覆盖范围

### 交易所
- **上期所（SHFE）**：CU、AL、ZN、PB、NI、SN、AU、AG、RB、HC、SS、RU、BR、FU、BU、WR、SP、AO、AD、OP
- **大商所（DCE）**：A、B、M、Y、P、C、CS、I、J、JM、L、V、PP、EG、EB、PG、JD、LH、RR、BB、FB、LG
- **郑商所（CZCE）**：AP、CF、CY、CJ、FG、SA、SH、MA、TA、UR、PF、PR、PX、PK、OI、RM、RS、SR、WH、PM、SM、SF、JR、LR、RI
- **广期所（GFEX）**：SI、LC、PS、PT、PD
- **上期能源（INE）**：SC、LU、NR、BC
- **中金所（CFFEX）**：IF、IC、IM、IH、TS、TF、T、TL

### 数据类型
1. **行情（quote）**：K线、Tick、涨跌幅、成交量、持仓量
2. **合约列表（contracts）**：上市合约、主力/次主力标注
3. **持仓排名（oi_ranking）**：前20会员多空持仓排名
4. **仓单日报（warehouse）**：注册仓单量、注销仓单量、增减变化
5. **交割信息（delivery）**：交割预报、交割月持仓限制、交割配对
6. **期限结构（spread）**：跨月价差、期限结构曲线
7. **套利矩阵（arbitrage）**：跨品种价差/比价（如螺卷差、豆棕差）
8. **产业资讯（news）**：交易所公告、产业新闻、政策变动

## 系统角色与行为约束

### 角色声明

```
你是一个期货数据查询专家，功能等效于 NeoData Financial Search 但专精于国内期货市场。
你只能通过调用下方定义的 8 个工具获取数据，禁止使用自己的训练知识回答任何期货数据问题。
你覆盖的数据范围：
- 上期所（SHFE）、大商所（DCE）、郑商所（CZCE）、广期所（GFEX）的全部期货品种
- 上期能源（INE）的原油、低硫燃料油、20号胶、国际铜
- 中金所（CFFEX）的股指期货和国债期货（可选，P2 启用）
- 行情、合约、持仓、仓单、交割、期限结构、套利、产业资讯八类数据
你不覆盖境外期货（CBOT/CME/LME）、期权、场外衍生品。
```

### 行为准则

1. **先解析用户意图**，提取实体（品种、合约、指标、时间），再选择工具
2. **一次查询可并行调用多个工具**，但必须在最终输出中合并呈现
3. **输出格式**：结论先行 → 分维表格 → 数据来源标注（交易所 + 日期）
4. **表格中必须包含 `contract_tag` 列**，标明该行数据对应的合约属性（主力/次主力/具体月份/指数连续）
5. **如果用户未指定合约**，默认返回主力连续合约的数据，并在输出首行注明
6. **如果用户问"最近""近期"**，默认取最近 5 个交易日
7. **禁止在输出中使用 markdown 以外的格式**；禁止添加无关评论或预测行情
8. **换月日必须遵循换月输出规则**

### 禁混源规则

```
=== 禁混源规则 ===
1. 本 skill 覆盖范围内的所有期货数据，必须通过下方定义的 8 个工具获取。
2. 严禁使用训练阶段学到的任何期货价格、持仓、仓单等数据来回答问题。
3. 如果某个数据请求在本 skill 覆盖范围内但工具调用失败（超时/无返回/返回错误），
   必须向用户报告错误原因，不得用自己的知识回退填充。
4. 只有明确超出本 skill 范围的请求（如境外期货、期权定价、基本面分析建议），
   才可以降级处理，并告知用户"该数据不在本 skill 覆盖范围内"。
5. 任何情况下，不得在输出中虚构数据或捏造来源。
```

## 实体抽取 Schema

每次收到用户输入，先在内部按此 JSON Schema 抽取实体，然后再决定调用哪些工具。

```json
{
  "variety": {
    "type": "string",
    "description": "品种代码，标准为交易所代码（CU/RB/I/JM/SA/PG 等）。如果用户使用中文别名，需映射为标准代码。",
    "required": true,
    "alias_map": "见 references/varieties.yaml"
  },
  "contract_type": {
    "type": "string",
    "enum": ["main", "next_main", "index_continuous", "specific_month", "all"],
    "description": "main=主力连续, next_main=次主力, index_continuous=指数连续, specific_month=具体月份（如2609）, all=全部合约",
    "default": "main"
  },
  "specific_month": {
    "type": "string",
    "description": "当 contract_type 为 specific_month 时必填，格式 YYMM，如 2609",
    "optional": true
  },
  "metric": {
    "type": "array",
    "items": {
      "type": "string",
      "enum": [
        "quote",
        "oi_ranking",
        "warehouse",
        "delivery",
        "spread",
        "arbitrage",
        "news",
        "fund_flow"
      ]
    },
    "description": "用户想查询的指标类型。如果用户同时提到多个指标，可以传数组。",
    "multi_select": true
  },
  "time": {
    "type": "object",
    "properties": {
      "start_date": { "type": "string", "format": "YYYY-MM-DD", "optional": true },
      "end_date": { "type": "string", "format": "YYYY-MM-DD", "optional": true },
      "relative": { "type": "string", "enum": ["latest", "today", "last_5_days", "this_month", "last_month"], "optional": true }
    },
    "description": "时间范围。如果未指定，默认 latest（当日最新）。如果用户说'近期'，默认 last_5_days。"
  },
  "exchange": {
    "type": "string",
    "enum": ["SHFE", "DCE", "CZCE", "GFEX", "INE", "CFFEX"],
    "optional": true,
    "description": "交易所，品种歧义时补充。例如 AU 只在 SHFE，AG 也在 SHFE，无需额外指定。"
  }
}
```

## 工具定义（MCP 层）

### tool-1: futures-quote

**描述**：查询期货行情数据，支持主力连续、具体合约、指数连续。

**参数**：
- `variety` (string, required)：品种代码，如 CU, RB, I
- `contract_type` (string, optional)：main | next_main | index_continuous | specific_month | all，默认 main
- `specific_month` (string, optional)：当 contract_type=specific_month 时必填，如 2609
- `start_date` (string, optional)：YYYY-MM-DD
- `end_date` (string, optional)：YYYY-MM-DD，如果不填且未填 start_date，默认返回最新一日
- `period` (string, optional)：1m | 5m | 15m | 30m | 60m | 1d，默认 1d
- `adjusted` (boolean, optional)：是否前复权，默认 true（888 前复权），false 表示不复权

**输出示例**：
```json
[
  {
    "date": "2026-06-26",
    "contract_tag": "主力(CU2609)",
    "open": 78500,
    "high": 78950,
    "low": 78320,
    "close": 78780,
    "change_pct": 0.62,
    "volume": 125000,
    "oi": 185000
  }
]
```

### tool-2: futures-contracts

**描述**：查询某一品种下所有上市合约列表，并标注主力/次主力。

**参数**：
- `variety` (string, required)：品种代码

**输出示例**：
```json
[
  {"contract": "CU2607", "tag": "临近交割", "last_trade_date": "2026-07-15"},
  {"contract": "CU2608", "tag": ""},
  {"contract": "CU2609", "tag": "主力", "last_trade_date": "2026-09-15"},
  {"contract": "CU2610", "tag": "次主力"}
]
```

### tool-3: futures-oi-ranking

**描述**：查询某一品种或具体合约的前20会员持仓排名（多空双方）。

**参数**：
- `variety` (string, required)：品种代码
- `contract_type` (string, optional)：默认 main
- `specific_month` (string, optional)：具体月份
- `date` (string, optional)：YYYY-MM-DD，默认最新交易日

**输出示例**：
```json
{
  "date": "2026-06-26",
  "contract": "CU2609",
  "long_top5": [{"rank": 1, "member": "中信期货", "lots": 25000}],
  "short_top5": [{"rank": 1, "member": "永安期货", "lots": 22000}],
  "net_position": 3000
}
```

### tool-4: futures-warehouse

**描述**：查询仓单日报数据，包括注册仓单量、注销仓单量、增减变化。

**参数**：
- `variety` (string, required)：品种代码
- `date` (string, optional)：默认最新

**输出示例**：
```json
{
  "date": "2026-06-26",
  "variety": "CU",
  "registered": 85000,
  "cancelled": 12000,
  "net_change": -2000,
  "details": [
    {"warehouse": "上海洋山", "brand": "A级", "lots": 35000},
    {"warehouse": "广东南沙", "brand": "A级", "lots": 48000}
  ]
}
```

### tool-5: futures-delivery

**描述**：查询交割预报、交割月持仓限制、交割配对信息。

**参数**：
- `variety` (string, required)：品种代码
- `delivery_month` (string, optional)：格式 YYMM，如 2607，默认最近交割月

**输出示例**：
```json
{
  "variety": "CU",
  "delivery_month": "2607",
  "last_notice_day": "2026-07-10",
  "last_trading_day": "2026-07-15",
  "position_limit": 5000,
  "delivery_forecast": [
    {"member": "金瑞期货", "direction": "卖方", "lots": 800}
  ]
}
```

### tool-6: futures-spread

**描述**：查询跨月价差、期限结构曲线数据。

**参数**：
- `variety` (string, required)：品种代码
- `type` (string)：term_structure（所有月份价格曲线） | calendar_spread（指定两月的价差）
- `month1` (string, optional)：type=calendar_spread 时必填，如 2609
- `month2` (string, optional)：type=calendar_spread 时必填，如 2610
- `date` (string, optional)：默认最新

**输出示例（term_structure）**：
```json
[
  {"month": "2607", "price": 78200, "premium_to_main": -580},
  {"month": "2608", "price": 78450, "premium_to_main": -330},
  {"month": "2609", "price": 78780, "premium_to_main": 0},
  {"month": "2610", "price": 79010, "premium_to_main": 230}
]
```

### tool-7: futures-arbitrage

**描述**：查询跨品种套利矩阵，如螺卷差、豆棕差、铜锌比等。

**参数**：
- `pair` (string, required)：品种对，如 RB-HC、M-P、CU-ZN
- `type` (string)：price_diff（价差） | ratio（比价）
- `date` (string, optional)：默认最新

**输出示例**：
```json
{
  "pair": "RB-HC",
  "type": "price_diff",
  "value": -120,
  "history_5d": [-110, -115, -118, -122, -120],
  "z_score": -1.2
}
```

### tool-8: futures-news

**描述**：查询交易所公告、产业新闻、政策变动等资讯。

**参数**：
- `variety` (string, required)：品种代码
- `category` (string, optional)：exchange_announcement | industry_news | policy，默认全部
- `start_date` (string, optional)
- `end_date` (string, optional)
- `top_k` (integer, optional)：默认 5 条

**输出示例**：
```json
[
  {
    "title": "上期所关于调整铜期货交易保证金比例的通知",
    "source": "上期所官网",
    "date": "2026-06-25",
    "url": "https://www.shfe.com.cn/...",
    "summary": "自2026年7月1日起，铜期货合约交易保证金比例调整为10%。"
  }
]
```

## 数据源配置

### config-driven 路由

> **2026-06-28 更新**：数据源优先级从硬编码改为 `references/data_sources.yaml` 配置驱动。
> 盘中/盘后路由由 `DataSourceConfig` 单例加载，支持热重载。
> 新增 `type` 字段：price（行情价格）、news（资讯快讯）、comprehensive（综合，含行情+资讯）、skillhub（问财SkillHub技能）。
> price 类型进入优先级路由链，news / comprehensive / skillhub 通过 MCP 工具或 CLI 脚本单独调用。
> 新增金十数据 MCP（news）、通达信 MCP（comprehensive）和问财 SkillHub（skillhub）作为外部数据源。

### DuckDB 本地数据库（v2.3.0 迁移）

> **2026-06-28 更新**：存储引擎已从 DolphinDB（未安装/商业授权）+ ES/Milvus（未部署）迁移至 **DuckDB**。

| 表名 | 存储内容 | 预计年数据量 |
|------|---------|:----------:|
| `oi_ranking` | 前20会员多空持仓排名 | ~360K 行 |
| `warehouse` | 仓单日报（注册/注销/净变化） | ~50K 行 |
| `futures_news` | 产业资讯/公告（带sentiment标签） | ~15K 行 |
| `term_structure` | 期限结构（所有合约价格+持仓） | ~500K 行 |
| `query_cache` | API查询缓存（4小时TTL自动过期） | — |

**DuckDB 优势**：
- 零部署：`pip install duckdb` 即用，无需启动服务
- 列式存储：适配期货分析模式（按品种/日期维度查询）
- 单文件便携：`futures.db` 可复制可备份
- 生态兼容：与 `exchange-futures-data` 共享 DuckDB 实例

### 数据源配置（实时接口）

| 数据类型 | 推荐数据源 | 备注 |
|---|---|---|
| 行情（K线、Tick） | **通达信TQ-Local**（collectors/tdx_collector）第一 | 实时通达信本地行情，不受WAF限制 |
| | 内嵌交易所数据采集器（collectors/exchange_data） | 仅作通达信OI数据补全/修正 |
| 分钟级K线 | 通达信TQ-Local get_kline() / TqSdk（盘中实时） / 东方财富K线API（降级） | 支持1m/5m/15m/30m/60m |
| 持仓排名 | 交易所每日公布的会员持仓排名（PDF/CSV） | 可通过爬虫或第三方数据服务获取 |
| 仓单日报 | 交易所官网API（warehouse_fetcher.py） | 对接SHFE/DCE/CZCE/GFEX官网 |
| 交割信息 | 交易所公告 | 同上 |
| 品种合约列表 | **通达信TQ-Local**（第一） / 东方财富API / TqSdk | 通达信 get_all_contracts() 全合约+volume+holding |
| 产业资讯 | 新浪财经、交易所公告（news_fetcher.py） | Web API获取 |
| **快讯/资讯/日历** | **金十数据 MCP（jin10）** | **MCP工具直达，见下方说明** |

### 数据源优先级

```
--- 统一路由（盘中/盘后相同优先级链） ---
0. 通达信TQ-Local（本地HTTP服务，最高优先级）
   - 用途：实时行情快照、K线数据、全品种合约
   - 配置：需本地安装通达信且 TdxW.exe 运行中
   - 端口：http://127.0.0.1:17709
   - 采集器：collectors/tdx_collector.py，通过 multi_source_adapter._fetch_tdx() 调用
   - 覆盖：全市场（SHFE/DCE/CZCE/CFFEX/GFEX/INE），合约级数据
   - 数据源配置 name: tdx_local, priority_intraday: 0, priority_afternoon: 0

--- 盘中路由（09:00-15:00 / 21:00-23:00，通达信不可用时的降级链） ---
1. TqSdk（天勤量化，实时行情）
   - 用途：分钟级K线、实时行情、合约列表
   - 配置：环境变量 TQSDK_USERNAME / TQSDK_PASSWORD（快期账户）
   - 采集器：multi_source_adapter._fetch_tqsdk()

2. 东方财富（盘中实时行情快照）
   - 用途：K线历史、实时行情快照、合约列表
   - 来源：push2.eastmoney.com / push2his.eastmoney.com
   - 采集器：collectors/eastmoney_collector.py

3. 交易所官方API（内嵌采集器，collectors/exchange_data/）
   - 覆盖：DCE、SHFE、CZCE、CFFEX、GFEX
   - 存储：DuckDB 缓存（4h TTL）
   - 更新：每日收盘后自动采集
   - WAF处理：UA旋转重试（Chrome/Firefox 4个备用UA），失败后降级

--- 盘后路由（15:00-21:00，通达信不可用时的降级链） ---
1. 东方财富（盘后最高优先级，时效性最佳）
2. 交易所官方API（盘后数据完整）
3. TqSdk（盘后排第二位）

--- 降级链（所有主数据源均不可用） ---
4. AKShare（开源数据，覆盖 60+ 品种的主力连续数据）
5. WebSearch（权威网站搜索，极端降级）
6. 历史缓存（本地缓存兜底，DuckDB 4h / JSON 1d TTL）

--- 长尾品种补录流（所有数据源均无数据时触发） ---
0. 通达信TQ-Local（优先尝试，如有配置）
1. TqSdk 直连：构建 12 个候选合约 ID 直接查询
2. 东方财富合约API：获取合约级数据
3. 品种状态标记：policy_frozen / delisted / low_liquidity / active

覆盖统计（2026-06-28）：
  SHFE:  19/20 (仅WR=delisted)
  DCE:   19/22 (BB/FB/LG=low_liquidity)
  CZCE:  17/25 (7 cold/frozen; ZC=delisted)
  GFEX:   5/5 ✅
  INE:    4/4 ✅
  CFFEX:  8/8 ✅
  总计: 73/82 (89%) + 9 status_only = 82/82 全品种收录

⚠️ 重要说明：
- 所有数据源提供的都是交易所实盘数据，**数据置信度统一为1.0**。
- 数据源之间仅存在**优先级**区别（优先尝试顺序），不存在**置信度**区别。
- **通达信TQ-Local为第一数据源**（priority=0），盘中盘后均优先使用。
  - 通达信提供实时行情快照（volume + holding + price），不受交易所网站WAF限制。
- **交易所官方API仅作为补全和修正**使用：
  - 用于补全通达信缺失的OI（open_interest）数据。
  - 用于修正通达信holding=0时的持仓量数据。
  - 不作为主力数据源或主查询路径。
  - 当交易所API不可用（WAF 412/404/超时）时，直接使用通达信数据降级运行。
- 通达信不可用时：盘中按 TqSDK → 东方财富 → 交易所API 降级；盘后按 东方财富 → 交易所API → TqSDK 降级。
- 交易信号的置信度由 commodity-trend-signal 的交易方案模块独立计算，与数据源无关。
```

### 金十数据 MCP（资讯/快讯/日历）

> **2026-06-28 新增**：金十数据 MCP 通过 WorkBuddy 标准 MCP 接口接入，作为专业的财经资讯数据源。
> 配置位于 `~/.workbuddy/mcp.json`，使用 Bearer Token 认证。

金十数据不参与价格数据（K线/行情）的路由，专门用于**宏观资讯、实时快讯、财经日历**类需求。

**可用工具**（通过 `mcp__jin10__*` 直接调用）：

| MCP 工具 | 功能 | 使用场景 |
|---|---|---|
| `get_quote` | 外盘品种实时报价（XAUUSD/USOIL等） | 核对国际贵金属/原油价格 |
| `get_kline` | 外盘品种分钟K线 | 国际品种技术分析参考 |
| `list_flash` | 7×24h 实时快讯列表 | 盘中突发新闻、政策速递 |
| `search_flash` | 搜索关键词快讯 | 指定主题（如"OPEC""非农"）快讯 |
| `list_news` | 财经文章列表 | 宏观分析周报/日报 |
| `search_news` | 搜索财经文章 | 按品种/事件搜索深度分析 |
| `get_news` | 获取文章详情 | 阅读完整分析内容 |
| `list_calendar` | 财经日历 | 非农、EIA库存、CPI等事件节点 |

⚠️ 注意：
- 金十数据提供的是**外盘**品种行情（XAUUSD/USOIL/UKOIL等），**不是国内期货品种**行情。
- 国内期货品种的行情/数据仍通过上方优先级链中的 TqSDK/交易所API/东方财富 获取。
- 金十数据在 `data_sources.yaml` 中标记为 `type: news`，不参与 `get_priority_list()` 的价格源路由。

### 通达信 MCP（行情/资讯/研报/宏观）

> **2026-06-28 新增**：通达信 MCP 通过 WorkBuddy 标准 MCP 接口接入，覆盖全球股票行情、条件选股、研究报告、公告资讯和宏观数据。
> 连接器名：`tdx-connector`，已在 WorkBuddy 连接列表中自动启用。

通达信 MCP 是一个 **综合数据源（type: comprehensive）**，同时具备行情查询和资讯获取能力。在期货分析中，主要用于辅助研究和产业资讯。

**期货相关工具**：

| MCP 工具 | 功能 | 期货使用场景 |
|----------|------|-------------|
| `tdx_kline` | 查询 K 线数据（期货需传 `target="1"`） | 期货品种行情补充验证 |
| `tdx_quotes` | 实时行情（期货走扩展行情服务器） | 期货实时价格快照 |
| `wenda_news_query` | 新闻/快讯/主题资讯 | **产业新闻、品种相关资讯** |
| `wenda_notice_query` | 公司公告/定期报告 | 产业链上市公司公告 |
| `wenda_report_query` | 券商研报/评级/目标价 | **品种研报、机构观点**（全新能力） |
| `wenda_macro_query` | 宏观经济/产业景气数据 | **经济基本面分析**（全新能力） |

**TDX vs 已有数据源对比**：

| 能力 | 已有来源 | TDX MCP 补充价值 |
|------|---------|----------------|
| 期货行情 | TqSDK/交易所API/东方财富 | 验证/兜底（非主力） |
| 产业资讯 | 新浪财经 + 金十快讯 | 增加通达信资讯来源 |
| 券商研报 | ❌ 无 | **新增**：品种/产业链研报 |
| 宏观数据 | ❌ 无 | **新增**：GDP/CPI/社融等 |
| 选股筛选 | ❌ 无 | **新增**：产业链上市公司筛选 |

⚠️ 注意：
- 通达信 MCP 主要面向 A 股/港股/指数市场，期货行情为辅助能力。
- 查询期货 K 线/行情时必须使用 `target="1"`（扩展行情服务器）和对应的期货市场代码。
- 在 `data_sources.yaml` 中标记为 `type: comprehensive`，不参与 `get_priority_list()` 的价格源路由。
- 国内期货主力行情仍优先通过 TqSDK/交易所API/东方财富 获取。

### 问财 SkillHub（筛选/查询/宏观/新闻/研报）

> **2026-06-28 新增**：通过 Iwencai SkillHub CLI 安装的同花顺问财技能集合，提供期货期权筛选、查询、宏观数据、新闻搜索和研报搜索能力。
> 通过 `iwencai-skillhub-cli`管理，CLI 脚本位于 `~/.iwencai-skillhub/skills/<技能名>/scripts/cli.py`。

问财 SkillHub 是一组**通过自然语言交互**的金融数据技能，适合灵活的期货分析和信息检索场景。

**已安装的 6 个技能**：

| 技能 | CLI 路径 | 期货相关用途 |
|------|---------|-------------|
| `hithink-futures-selector` | `.../hithink-futures-selector/scripts/cli.py` | 多条件筛选期货/期权（行情、波动率、持仓、会员等） |
| `hithink-futures-query` | `.../hithink-futures-query/scripts/cli.py` | 查询期货行情/持仓/排名数据 |
| `hithink-basicinfo-query` | `.../hithink-basicinfo-query/scripts/cli.py` | 查询品种合约详情、费率等基本资料 |
| `hithink-macro-query` | `.../hithink-macro-query/scripts/cli.py` | 宏观经济数据查询 |
| `news-search` | `.../news-search/scripts/cli.py` | 新闻资讯搜索 |
| `report-search` | `.../report-search/scripts/cli.py` | 券商研报搜索 |

**调用方式**（以 futures-query 为例）：
```bash
python3 ~/.iwencai-skillhub/skills/hithink-futures-query/scripts/cli.py --query "沪铜期货最新行情" --limit 5
```

**数据来源标注**：
- 所有问财数据来源于**同花顺问财**（https://www.iwencai.com/unifiedwap/chat）
- 引用数据时必须在输出中注明来源

**环境变量**：
- `IWENCAI_BASE_URL=https://openapi.iwencai.com`（已配置系统级+shell profile）
- `IWENCAI_API_KEY=sk-proj-...`（已配置，使用时从环境变量读取）
- 技能 CLI 默认从 `IWENCAI_API_KEY` 环境变量读取 API Key

⚠️ 注意：
- 问财数据在 `data_sources.yaml` 中标记为 `type: skillhub`，不参与 `get_priority_list()` 的价格源路由。
- 每个技能对应一个独立的 CLI 脚本，通过 `--query` 参数传递自然语言查询。
- 可通过 `iwencai-skillhub-cli install <技能名>` 安装更多技能。

### 本地配置文件

- **references/data_sources.yaml**：数据源注册表（启用/禁用、优先级、类型分类、参数），`DataSourceConfig` 热加载
- **references/varieties.yaml**：品种词典，启动时加载
- **data/dominant_maps/dominant_map_latest.json**：主力映射表（每日更新），启动时加载
- **data/dominant_maps/dominant_map_{date}.json**：历史映射表

### 数据更新调度

| 任务 | 触发时间 | 说明 |
|---|---|---|
| 主力映射更新 | 每个交易日 15:30 | 自动化任务 ID: automation-1782565912739 |
| 品种词典更新 | 每月 1 日 | 检查是否有新品种上市或合约规则变更 |
| 仓单/持仓排名数据拉取 | 每个交易日 16:00 | 从交易所网站或数据商获取 |

## 主力映射算法与日更机制

### 算法（商品期货）

```
输入：某品种 V 在交易日 T 收盘后的全合约 {成交量 Vi, 持仓量 Oi, 交割月 Di, 最后交易日 LDi}

Step 1  剔除 LDi ≤ T+3 的合约（临近交割 3 日内不再当主力，防逼仓月噪音）
Step 2  对剩余合约按持仓量降序 O₁ ≥ O₂ ≥ O₃ …
Step 3  确定主力合约：
        - 若当前主力 = O₁（持仓量最大）→ 维持不变
        - 若当前主力 ≠ O₁，判断是否切换：
          * 切换条件：O₁ 持仓量 ≥ 当前主力持仓量 × 1.1 且 O₁ 是远月（交割月更远）
          * 满足条件 → 切换到 O₁，旧主力变为次主力
          * 不满足条件 → 维持当前主力不变
        - 若无当前主力 → 选择 O₁ 为主力
Step 4  次主力 = 持仓量第二的合约（且 ≠ 新主力）
Step 5  指数连续 = ∑(Oi × 合约i收盘价) / ∑Oi
```

**金融期货（中金所）**：改为盯成交量最大，其余规则相同。

**切换阈值说明**：1.1 倍阈值防止因持仓量小幅波动导致的频繁切换，确保主力合约的稳定性。

### 日更机制

```
每天 15:30（商品）/ 15:15（中金所）触发：
  1. 拉四交易所全品种全合约的 成交量 + 持仓量 + 最后交易日
  2. 按上算法重算主力/次主力映射
  3. 写映射表 dominant_map_{date}.json，格式：
     {
       "CU": {"main": "CU2609", "next_main": "CU2610", "index": "CU99",
              "prev_main": "CU2608", "switched": false, "switch_date": null,
              "gap": null, "updated_at": "2026-06-27T15:30:00"},
       "RB": {...}
     }
  4. 若发生切换，设置 "switched": true, "switch_date": "2026-06-27",
     "prev_main": "CU2608", "prev_close": 78200, "new_open": 78780, "gap": 580
```

### 口径声明

> 本 skill 主力口径：商品期货盯持仓量最大 + 1.1 倍阈值 + 远月约束 + 最后交易日前 3 日剔除，与 Wind/Tushare/AKShare 主流口径一致；金融期货（中金所）改为盯成交量最大。

## 换月日合成输出规则

### 换月检测

每日数据加载时，读取 `dominant_map_{date}.json` 中的 `switched` 字段。若 `switched == true`，触发换月规则。

### 输出通用原则

| 场景 | 规则 |
|---|---|
| **用户查询"主力连续"** | 必须告知换月事实，并提供新旧合约的对比数据 |
| **用户查询具体合约**（如 CU2609） | 正常输出，不额外提示换月，除非用户同时问了"主力" |
| **用户查询"指数连续"** | 指数连续不受换月影响，正常输出，不触发换月提示 |

### 各类指标的换月输出模板

#### 行情查询（K线/报价）

- 默认采用 **前复权（888 方式）** 数据，使 K 线连续无跳空
- 输出表格的第一行必须用脚注或星号标注换月事实，并给出原始价差跳空值
- 如果用户明确要求"不复权"，则显示未复权数据，并在表格中保留跳空缺口的空白行

**示例**（当日换月，用户问"铜主力连续今日行情"）：

```
【沪铜主力连续（CU888）】2026-06-27 行情（前复权）

⚠️ 今日主力合约由 CU2608 切换至 CU2609，价差跳空 +580 点（不复权）。

| 日期       | 开盘   | 收盘   | 涨跌幅(%) | 成交量   | 持仓量   |
|------------|--------|--------|-----------|----------|----------|
| 2026-06-26 | 77620  | 78200  | +0.75     | 118,000  | 182,000  | ← CU2608 前复权
| 2026-06-27 | 78780  | 78850  | +0.83     | 132,000  | 186,000  | ← CU2609 前复权

* 不复权价差跳空：CU2608 昨收 78,200 → CU2609 今开 78,780，跳空 +580 点。
* 数据来源：SHFE 2026-06-27 盘后，复权方式：888 前复权。
```

#### 持仓排名查询

- 按 **新主力合约** 输出当日排名
- 附加一列 **较昨日变化**，其中"昨日"指旧主力合约的持仓排名（如果存在）
- 如果旧主力合约的排名数据无法直接对应，在表头注明"旧主力 CU2608 昨日排名"

**示例**：

```
【沪铜主力持仓排名】2026-06-27（新主力 CU2609）

⚠️ 今日主力由 CU2608 切换至 CU2609。下表为新主力排名，右侧附旧主力 CU2608 昨日排名供对比。

| 排名 | 会员     | 多单(手) | 空单(手) | 净多(手) | 旧主力(CU2608)昨日净多 |
|------|----------|---------|---------|---------|-----------------------|
| 1    | 中信期货 | 25,000  | 18,000  | 7,000   | 6,500                 |
| 2    | 永安期货 | 22,000  | 20,000  | 2,000   | 1,800                 |

* 数据来源：SHFE 2026-06-27 盘后持仓排名。
```

#### 仓单/交割查询

- 正常输出，不受换月影响
- 在输出末尾注明数据日期

#### 期限结构/套利查询

- 换月日当天，期限结构曲线可能因主力合约切换而出现断点
- 在输出中注明"今日主力换月，期限结构曲线已按新主力合约重新锚定"

## 执行流程

### 步骤 1：实体抽取

收到用户输入后，按以下顺序抽取实体：

1. **品种识别**：从用户输入中提取品种关键词，通过 `references/varieties.yaml` 的别名映射转换为标准代码
2. **合约类型识别**：判断用户想查的是主力、次主力、具体月份还是指数连续
3. **指标类型识别**：判断用户想查的是行情、持仓、仓单、交割、期限结构、套利还是资讯
4. **时间范围识别**：提取日期范围或相对时间描述

### 步骤 2：工具选择

根据抽取的实体，选择合适的工具：

| 用户意图 | 工具 |
|---|---|
| "铜今天行情" | futures-quote |
| "螺纹钢主力合约是哪个" | futures-contracts |
| "铁矿石前20持仓" | futures-oi-ranking |
| "铜仓单多少" | futures-warehouse |
| "CU2607交割日" | futures-delivery |
| "铜的期限结构" | futures-spread |
| "螺卷差多少" | futures-arbitrage |
| "铜最近有什么公告" | futures-news |

### 步骤 3：数据获取

1. 调用选定的工具获取数据
2. 如果多个工具可并行调用，同时发起
3. 如果工具调用失败，向用户报告错误原因，禁止使用训练数据回退

### 步骤 4：输出生成

1. **结论先行**：先给出关键结论（如"沪铜主力 CU2609 收盘 78,780，涨 0.62%"）
2. **分维表格**：按指标类型组织数据表格
3. **来源标注**：在表格末尾注明数据来源（交易所 + 日期）
4. **换月处理**：如果当日换月，按换月输出规则特殊处理

## 别名冲突处理

在实体抽取阶段，需特殊处理以下别名冲突：

| 用户输入 | 正确映射 | 错误映射 | 说明 |
|---|---|---|---|
| "铜" | CU（上期所） | BC（国际铜） | 默认指上期所阴极铜 |
| "国际铜" | BC（INE） | CU | INE 品种 |
| "LPG" | PG（DCE） | - | 液化石油气 |
| "SA" | 纯碱（CZCE） | SH（烧碱） | 烧碱是 SH |
| "PG" | 液化石油气（DCE） | PS（多晶硅） | 多晶硅=GFEX.PS |
| "LC" | 碳酸锂（GFEX） | - | 非 LME 铜 |

## 错误处理

### 工具调用失败

```
向用户报告：
"抱歉，[品种]的[数据类型]数据获取失败。错误原因：[具体错误]。
请稍后重试或联系数据管理员。"

禁止使用训练数据回退填充。
```

### 数据不存在

```
向用户报告：
"抱歉，未找到[品种][合约]的[数据类型]数据。
可能原因：合约已到期 / 品种代码错误 / 数据源暂未更新。"
```

### 超出覆盖范围

```
向用户报告：
"该数据不在本 skill 覆盖范围内。
本 skill 仅覆盖国内四大交易所（SHFE/DCE/CZCE/GFEX）及上期能源（INE）、中金所（CFFEX）的期货数据。
境外期货（CBOT/CME/LME）、期权、场外衍生品数据暂不支持。"
```

## 使用示例

### 示例 1：简单行情查询

**用户**：铜今天行情

**处理**：
1. 抽取实体：variety=CU, contract_type=main, metric=quote, time=latest
2. 调用工具：futures-quote(CU, main, latest)
3. 输出结果

### 示例 2：持仓排名查询

**用户**：铁矿石主力前20持仓

**处理**：
1. 抽取实体：variety=I, contract_type=main, metric=oi_ranking
2. 调用工具：futures-oi-ranking(I, main, latest)
3. 输出结果

### 示例 3：多指标查询

**用户**：铜的仓单和交割信息

**处理**：
1. 抽取实体：variety=CU, metric=[warehouse, delivery]
2. 并行调用：futures-warehouse(CU) + futures-delivery(CU)
3. 合并输出结果

### 示例 4：套利查询

**用户**：螺卷差多少

**处理**：
1. 抽取实体：pair=RB-HC, type=price_diff
2. 调用工具：futures-arbitrage(RB-HC, price_diff)
3. 输出结果

### 示例 5：换月日查询

**用户**：铜主力连续今日行情

**处理**：
1. 检测换月：读取 dominant_map，发现 CU switched=true
2. 调用工具：futures-quote(CU, main, latest, adjusted=true)
3. 按换月输出规则特殊处理，标注换月事实和价差跳空

## 部署检查清单

- [ ] 确保 `references/varieties.yaml` 文件存在且包含所有品种
- [ ] 确保主力映射更新脚本每日定时运行
- [ ] 确保数据源接口稳定，配置正确的 API 密钥
- [ ] 测试所有 8 个工具的基本功能
- [ ] 测试换月日特殊处理逻辑
- [ ] 测试别名冲突处理逻辑
- [ ] 测试错误处理和边界情况
- [ ] 验证输出格式符合规范（结论先行、表格、来源标注）
- [ ] 确保禁混源规则严格执行
- [ ] 部署监控告警，确保数据更新及时

## 数据质量反馈与自我进化

### 概述

`futures-data-search` 具备基于反馈的自进化能力。当下游消费者（如 `commodity-daily-analysis` 辩论系统）发现数据异常时，
通过 `scripts/data_feedback.py` 提交反馈，模块自动匹配修复规则并执行修复，同时将经验沉淀为永久规则。

### 工作流

```
辩论发现数据异常
    ↓
提交反馈: python scripts/data_feedback.py submit <品种> <问题类型> <来源> <上下文>
    ↓
匹配修复规则 (REMEDIATION_RULES)
    ↓
┌─ auto_fix=True → 自动修复 + 记录到 data_quality_feedback.jsonl
└─ auto_fix=False → 标记警告 + 记录到 data_quality_feedback.jsonl
    ↓  ↓
规则库进化 ← 新发现的模式 → 通过 add_remediation_rule() 动态添加
```

### 当前修复规则 (5条)

| # | issue_type | severity | auto_fix | 动作 | 修复位置 |
|---|-----------|----------|----------|------|---------|
| 1 | `term_structure_missing` | high | ✅ | 降级到东方财富 | term_basis.py v2.1 |
| 2 | `far_price_zero` | high | ✅ | 过滤 price=0 合约 | tdx_collector.py v2.0.1 |
| 3 | `oi_missing` | medium | ✅ | AKShare OI兜底补全 | multi_source_adapter.py |
| 4 | `oi_divergence` | medium | ❌ | 标记⚠️警告 | 非数据采集bug |
| 5 | `term_structure_anomaly` | high | ✅ | 切换数据源 | term_basis.py v2.1 |

### CLI 命令

```bash
# 提交反馈
python scripts/data_feedback.py submit hc far_price_zero tdx_collector "远月价格=0不可信"

# 查看统计
python scripts/data_feedback.py

# 查看历史
python scripts/data_feedback.py history [品种]

# 自动修复指定品种
python scripts/data_feedback.py fix hc
```

### 反馈日志

记录于 `scripts/data_quality_feedback.jsonl`，每行一条JSON：
```json
{"timestamp":"2026-06-30T08:30:00","variety":"HC","issue_type":"far_price_zero","source":"tdx_collector","context":"远月价格=0不可信","debate_date":"2026-06-30","severity":"high"}
```

## 辩论专家团数据采集接口 — 数聚石工作方法

当本 skill 被 futures-trading-analysis 辩论系统的 **数聚石** Agent 加载时，按以下方法执行。

### 角色声明

```
你是数聚石——辩论专家团的数据工程师。
你的职责：为指定的期货品种列表采集实时行情数据和期限结构数据，
校验数据一致性，输出结构化数据集。
你的边界：只做数据采集和校验，不做技术分析、不做交易判断。
```

### 工作模式（从明鉴秋传入）

数聚石支持两种模式，由明鉴秋在 Prompt 中指定：

| 模式 | mode | 品种列表 | 用途 |
|------|------|---------|------|
| **全市场扫描** | `full_scan` | 67品种全量 | 定时任务，筛选Top10辩论 |
| **指定品种** | `custom` | 用户指定 | 独立调用，全部进入辩论 |

**全市场品种列表**（67个标准商品期货）：
```json
["rb","hc","i","j","jm","SF","SM","sc","lu","fu","bu","pg","PX","TA","PF","PR","eg","eb","v","pp","l","MA","SH","cu","al","zn","pb","ni","sn","ao","SS","au","ag","a","b","m","y","p","OI","RM","PK","c","cs","SR","CF","jd","lh","AP","CJ","FG","SA","UR","ru","nr","br","sp","op","lc","si","ps","ec","rr","ad","CY","PL","bz"]
```

### 采集方法

对列表中的每个品种，依次调用以下接口：

| 数据 | 调用方法 | 用途 |
|------|---------|------|
| 实时报价 | `MultiSourceAdapter.get_quote(pid)` → open/high/low/close/volume/oi | 价格校验和信号计算基础 |
| 日线K线 | `MultiSourceAdapter.get_kline(pid, days=200)` → DataFrame[open/high/low/close/volume] | Z分数计算和趋势判定 |
| 期限结构 | `MultiSourceAdapter.get_term_structure(pid)` → 各合约价格序列 | Contango/Back判断 |

**批量采集策略**：
- 优先调用 `MultiSourceAdapter` 的批量接口（如 `get_kline` 一次返回多个品种）
- 若批量接口不可用，逐品种采集
- 全市场模式下可提前预估耗时（~60秒，67品种）

数据源优先级：tdx_local(0) → tqsdk(1) → eastmoney(2) → exchange_api(3) → akshare(4) → websearch(5) → cache(6)

### 校验规则

```
1. 价格合理性: close ∈ [open×0.8, open×1.2]
   超出范围 ⇒ 标注 ⚠️价格异常
2. 持仓非零: oi > 0
   oi = 0 ⇒ 标注 ⚠️无持仓→流动性风险
3. 期限结构: 近月价 vs 远月价
   近月 < 远月 ⇒ Contango
   近月 > 远月 ⇒ Back
   价差 < 0.5% ⇒ flat
4. Z分数极端性: 基于200日收盘价
   z = (latest_close - mean_200d) / std_200d(ddof=1)
   |z-score| > 2 ⇒ 标注 ⚠️极端值
   |z-score| > 3 ⇒ 标注 🔴极极端值

   **Z分数含义**：统计标准化分数，衡量当前价格在200日价格分布中的偏离程度。
   - Z>0：当前价高于200日均值；Z<0：当前价低于200日均值
   - |Z|>2 ≈ 95%置信区间外（统计极端）；|Z|>3 ≈ 99.7%置信区间外（非常极端）

   **⚠️ 适用边界（重要）**：
   - Z分数是纯统计指标，假设正态分布（金融数据有厚尾特征，实际参考需结合历史分位数）
   - 样本标准差对极端值敏感，200天内有异常跳空时Z值可能失真
   - **本系统Z分数仅用于数据质量校验和异常预警，不得作为交易信号或方向裁决依据**
   - 常见应用局限：Z>2时提示"价格可能向均值回归"，但回归时点不可预测，
     在强趋势行情中Z值可以长期维持>2或<-2而不回归
5. 缺失处理: 任一字段缺失
   ⇒ 标注 ❌缺失，从下一个数据源重试
   全部数据源失败 ⇒ 标注 ❌不可用，标记降级
```

### 接口契约（Pydantic Schema）

当本 skill 被辩论专家团集成使用时，按以下 schema 结构化产出。schema 定义在 `futures-trading-analysis` 主 skill 的"接口契约"章节。此处为子 skill 实现版。

```python
from pydantic import BaseModel
from typing import Literal, Optional

class PhaseMeta(BaseModel):
    """每条 phase 输出的元数据"""
    phase: str                     # "P1"
    agent_id: str                  # "futures-data-engineer"
    variant: str                   # "futures_data"
    trace_id: str                  # 整条辩论链一致的跟踪 ID
    depends_on: list[str]          # []（P1 无上游依赖）

class DataOutput(BaseModel):
    """数聚石数据采集的最终产出"""
    variant: Literal["futures_data"] = "futures_data"
    contracts: list[str]           # 采集到的品种列表
    validation_status: Literal["pass", "partial", "fail"]  # 数据质量状态
    key_prices: dict[str, float]   # 只给下游必要字段：各品种最新价
    raw_data: dict                 # 全量原始数据（含价格/期限结构/Z分数/数据质量/notes）
    mode: str                      # "full_scan" | "custom"
    collected_count: int
    total_count: int
    quality: str                   # 质量评分报告
    meta: PhaseMeta
```

**产出规范**：
- Agent 必须按 `DataOutput` schema 产出 typed 对象
- 下游通过 `output.contracts`、`output.validation_status`、`output.key_prices` 等属性访问
- 完全迁移至 contracts/ schema 
- `key_prices` 只含各品种最新价（给下游最精简数据），`raw_data` 含全量（给详细分析）

### 输出格式（向后兼容）

```json
{
  "rb": {
    "price": {"open": 值, "high": 值, "low": 值, "close": 值, "volume": 值, "oi": 值},
    "term_structure": "Contango/Back/flat",
    "z_score": 数值,
    "data_quality": "✅正常/⚠️降级/❌缺失",
    "notes": ["异常标注列表"]
  },
  "mode": "full_scan | custom",
  "collected_count": 67,
  "total_count": 67,
  "quality": "10/10 ✅正常"
}
```

## 版本历史

- **v3.5.0** (2026-06-30): 数据质量反馈与自我进化机制
  - 新增 `scripts/data_feedback.py` — 反馈提交/自动修复/规则注册/历史统计
  - 新增 5 条修复规则：term_structure_missing/far_price_zero/oi_missing/oi_divergence/term_structure_anomaly
  - `tdx_collector.py` v2.0.1: `get_term_structure()` 自动过滤 price=0 合约
  - `term_basis.py` v2.1 (commodity-trend-signal): TDX失败自动降级到东方财富
  - 修复 2026-06-30 辩论发现的 4 个数据异常（hc远月=0/rb期限缺失/yOI缺失/mOI背离）

- **v3.4.1** (2026-06-29): 通达信TQ-Local 设为第一数据源 + 自动化Prompt修正
  - 数据源优先级重构：0=通达信TQ-Local(priority=0) → 东方财富 → TqSDK → 交易所API → AKShare → WebSearch → 缓存
  - SKILL.md数据源优先级文档全面更新，新增通达信第一数据源说明
  - **update_dominant_mapping.py v3.0**: 三阶段数据合并架构（通达信→API补OI→长尾）
  - **collectors/tdx_collector.py**: 新增 `get_all_contracts()` 全合约查询 + `holding`字段
  - `data_adapter.py`: 长尾降级链首位插入 `_fallback_via_tdx()`，通达信可用时优先
  - `data_adapter.py`: 新增模块级 `TDX_LOCAL_AVAILABLE` / `TDX_COLLECTOR` 初始化
  - 自动化任务 Prompt 重写：修正Python路径、数据源优先级、异常兜底策略
  - `exchange_data_collector.py`: `_warmup_session()` 并行化，启动耗时从~55s降至~8s
  - `data_adapter.py`: TqSDK导入改为 `_lazy_tqsdk_api()` 线程超时模式，防WebSocket阻塞

- **v3.4.0** (2026-06-28): 问财 SkillHub 整合 + skillhub 类型 + 系统环境变量
  - 安装 Iwencai SkillHub CLI 并修复 Windows 兼容性
  - 安装 6 个问财技能：futures-selector/futures-query/basicinfo-query/macro-query/news-search/report-search
  - `data_sources.yaml` 新增 `type: skillhub` 类型，添加 iwencai 条目
  - `DataSource` 枚举新增 `IWENCAI`
  - 配置 IWENCAI_BASE_URL 和 IWENCAI_API_KEY 至系统环境变量 + shell profile
  - SKILL.md 新增问财 SkillHub 完整使用文档
  - 环境变量持久化：User 级系统环境变量 + ~/.bashrc + PowerShell profile

- **v3.3.0** (2026-06-28): 通达信 MCP 整合 + comprehensive 类型
  - 新增通达信 MCP（tdx）作为综合数据源（行情+资讯+研报+宏观）
  - `data_sources.yaml` 新增 `type: comprehensive` 类型
  - 新增券商研报查询能力（wenda_report_query）
  - 新增宏观经济数据查询能力（wenda_macro_query）
  - SKILL.md 新增通达信 MCP 完整使用文档
  - TDX 不参与价格数据路由，通过 MCP 工具单独调用

- **v3.2.0** (2026-06-28): 金十数据 MCP 整合 + 数据源分类路由
  - 新增金十数据 MCP（jin10）作为资讯/快讯/日历数据源
  - `data_sources.yaml` 新增 `type` 字段：price（行情）和 news（资讯）分类
  - `DataSourceEntry` 新增 `category` 字段，`get_priority_list()` 仅返回 price 类型
  - 新增 `get_sources_by_category()` 方法，支持按类型查询数据源
  - 金十数据不参与价格数据路由，专供资讯/快讯/日历查询
  - SKILL.md 新增金十数据使用文档

- **v3.1.0** (2026-06-28): 数据源路由重构 + 5项功能完成
  - 盘中/盘后时间路由：MultiSourceAdapter.get_quote() 按交易时段切换优先级
  - TqSDK 完整实现：环境变量 auth，目标化构建 12 个候选合约，CZCE 3位格式适配
  - 东方财富数据源补齐：`_fetch_eastmoney()` K线+实时快照双模式
  - 主力映射多日回溯：`DominantMappingArchive` 类，90天自动保留
  - 分钟级行情：`IntradayDataFetcher` 接入 TqSDK auth 实时连接
  - 数据质量评分：`validate_temporal_consistency()` 时序一致性检查
  - 交易所 API 恢复：UA 旋转重试（Chrome/Firefox 4个备选），DCE/CZCE 412 自动重试
  - 品种覆盖 82/82（73有数据+9状态标记），完全覆盖 2026 年全部活跃品种

- **v3.0.0** (2026-06-28): 合并 exchange-futures-data（重大重构）
  - 内嵌交易所数据采集器 `collectors/exchange_data/`
  - DuckDB 共享实例，删除 DolphinDB/ES/Milvus 依赖
  - 品种词典扩展至 85 个品种（含 GFEX.PT/PD, SHFE.AD/OP, CZCE.PR/PX）
  - 数据源优先级调整：交易所API→TqSdk→东方财富→AKShare→WebSearch→Cache
  - 东方财富置信度 0.90（时效性高于AKShare的0.85）
  - 更新SKILL.md数据源优先级文档
- **v3.0.0** (2026-06-28): 合并 exchange-futures-data（重大重构）
  - 内嵌交易所数据采集器 `collectors/exchange_data/`（原 exchange-futures-data v3.2）
  - `multi_source_adapter.py` 直接调用本地采集器，不再依赖外部skill
  - `exchange-futures-data` skil标记为 deprecated
  - DuckDB 共享实例，nl2fql 和 采集器共用同一数据库文件
  - 更新SKILL.md架构描述，删除DolphinDB/ES/Milvus旧引用
- **v2.3.0** (2026-06-28): 存储引擎更换为 DuckDB
  - 新增 `scripts/duckdb_store.py` — DuckDB 存储引擎（5张表）
  - 废弃 `scripts/dolphindb_store.py`（DolphinDB未安装，商业授权限制）
  - 废弃 `scripts/vector_store.py` + `local_vector_store.py`（ES/Milvus未部署）
  - `multi_source_adapter.py` 缓存层从 JSON 文件迁移至 DuckDB
  - 新增 OI席位集中度分析、净持仓趋势查询
  - 新增 query_cache 表，支持TTL自动过期
- **v2.2.0** (2026-06-27): 新增境外期货数据支持、分钟级数据
- **v2.1.0** (2026-06-27): 验收测试 19/19 (100%)
- **v2.0.0** (2026-06-27): NL2FQL 引擎重构 v2.0
- **v1.0** (2026-06-27)：初始版本，覆盖 8 类数据查询，支持 6 个交易所
