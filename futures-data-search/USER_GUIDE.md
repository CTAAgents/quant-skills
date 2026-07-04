# futures-data-search 用户使用手册

> 国内期货数据统一调度中心 v4.0.0 — MultiSourceAdapter 多源自动降级 + 通达信本地低延迟

## 目录

1. [概述](#概述)
2. [数据源架构](#数据源架构)
3. [快速开始](#快速开始)
4. [功能详解](#功能详解)
5. [查询示例](#查询示例)
6. [API 参考](#api-参考)
7. [配置说明](#配置说明)
8. [常见问题](#常见问题)
9. [更新日志](#更新日志)

---

## 概述

`futures-data-search` 是一个面向 LLM Agent 的国内期货市场全栈数据查询技能。包含两大部分：

```
futures-data-search (v4.0.0)
│
├── MultiSourceAdapter（统一调度入口）
│   ├── get_quote()    → 通达信本地(最高) → TqSDK → 东方财富 → 交易所API → AKShare
│   ├── get_kline()    → 同上，自动降级
│   ├── get_term_structure() → 东方财富一次HTTP（0.1s）
│   └── tdx_collector  → 动态合约月份代码，多代码自动试错
│
├── NL2FQL 自然语言查询引擎
│   ├── 8个查询工具（行情/持仓/仓单/交割/期限结构/套利/资讯/合约列表）
│   ├── 智能品种识别 + 主力映射管理
│   └── DuckDB 本地缓存层（5张拓展表）
│
└── 交易所数据采集器（内置，原 exchange-futures-data v3.2）
    ├── 5大交易所官方 API → DCE/SHFE/CZCE/CFFEX/GFEX
    ├── AKShare/TqSdk/东方财富/通达信 自动降级
    └── DuckDB 持久化（12,800+ 条历史K线，740+ 品种）
```

### 核心特性

- **智能品种识别**：支持 79 个期货品种，150+ 中文别名映射
- **自然语言查询**：无需记忆代码，直接用中文提问
- **多维数据支持**：行情、持仓、仓单、价差、资讯等 8 类数据
- **7 级数据源降级**：通达信本地(最高) → TqSDK → 东方财富 → 交易所 API → AKShare → WebSearch → Cache
- **盘中/盘后双优先级链**：由 data_sources.yaml 配置驱动，自动切换
- **数据置信度统一 1.0**：所有数据源提供的均为交易所实盘数据，无可信度差异
- **三重校验**：交易所级清洗 → 规则引擎 price/oi 校验 → 主力算法审核
- **DuckDB 持久化**：12,800+ 条历史 K 线，740+ 品种，日期覆盖 2025-06 ~ 至今
- **东方财富期限结构**：一次 HTTP 请求（0.1s）获取全部合约月份价格
- **数据可溯源**：所有数据标注来源和更新时间
- **防幻觉机制**：禁止使用训练数据，强制实时查询

### 覆盖范围

| 交易所 | 品种数 | 主力映射 | 代表品种 |
|--------|--------|----------|----------|
| 上期所（SHFE） | 18 | 16/18 ✅ | CU铜、AU黄金、RB螺纹钢、AG白银 |
| 大商所（DCE） | 22 | 19/22 ✅ | I铁矿石、M豆粕、J焦炭、PG液化石油气 |
| 郑商所（CZCE） | 24 | 16/24 ✅ | SA纯碱、MA甲醇、CF棉花、TA PTA |
| 广期所（GFEX） | 3 | 3/3 ✅ | SI工业硅、LC碳酸锂、PS多晶硅 |
| 上期能源（INE） | 4 | 4/4 ✅ | SC原油、LU低硫燃油、NR20号胶、BC国际铜 |
| 中金所（CFFEX） | 8 | 8/8 ✅ | IF沪深300、T国债、IC中证500 |
| **合计** | **79** | **66/79 (84%)** | 缺失为冷门/新品种，数据源不覆盖 |

---

## 数据源架构

### 优先级链

系统按以下顺序尝试获取数据，自动跳过不可用的源：

```
盘中链 (09:00-15:00 / 21:00-23:00):
  通达信本地 (priority=0) ─── 本地HTTP JSON-RPC服务（127.0.0.1:17709），零延迟
    ↓ 不可用/未运行
  TqSDK (priority=1) ────── 天勤量化实时行情，需环境变量 auth
    ↓ 不可用/超时
  东方财富 (priority=2) ──── 公开HTTP接口，盘中实时快照
    ↓ 请求失败
  交易所API (priority=3) ─── DCE/SHFE/CZCE/CFFEX/GFEX 官方接口（懒加载，5s超时）
    ↓ 被WAF拦截/超时
  AKShare ───────────────── 开源金融数据
    ↓ 品种不覆盖
  WebSearch ─────────────── 权威网站爬取
    ↓ 无法获取结构化数据
  历史缓存 ──────────────── DuckDB/JSON缓存（4h/1d TTL）

盘后链 (15:00-21:00):
  通达信本地 (priority=0)
  东方财富 (priority=1)
  交易所API (priority=2)
  TqSDK (priority=3)
  AKShare → WebSearch → 缓存

注意：所有数据源数据置信度统一为 1.0（均为交易所实盘数据），
信号置信度由上游 skill（commodity-trend-signal）独立计算。
```

### 健康监控

每个数据源有独立的健康状态追踪：

- 连续 3 次请求失败 → 自动标记为不可用，不再尝试
- 每次成功调用 → 重置失败计数，更新最后成功时间
- 可用源恢复后 → 下次调度自动重新启用

### 数据校验流程

```
原始数据 → L1 数据源选择(自动降级)
         → L2 交易所级清洗(validate_price_record)
         → L3 规则引擎(price_logic/oi/limit)
         → L4 主力算法(1.1x阈值/远月约束)
         → L5 多源共识(最高置信度源)
         → DuckDB 持久化 + 输出溯源标注
```

---

## 快速开始

### 安装依赖

```bash
# 基础依赖（必需）
pip install requests beautifulsoup4 numpy pandas duckdb pyyaml

# 可选依赖（增强功能）
pip install akshare          # AKShare 开源降级数据源
pip install tqsdk            # 天勤量化实时行情
```

### 基本使用

```python
from scripts.ai_qa_service import AIQAService

# 初始化服务
service = AIQAService()

# 查询行情
result = service.query("沪铜主力最新价")
print(service.format_response(result, 'text'))

# 查询仓单
result = service.query("纯碱仓单")
print(service.format_response(result, 'text'))

# 查询价差
result = service.query("螺卷差")
print(service.format_response(result, 'text'))
```

### 命令行使用

```bash
# 进入技能目录
cd ~/.workbuddy/skills/futures-data-search

# 运行测试
python scripts/test_acceptance.py

# 交互式查询
python -c "
from scripts.ai_qa_service import AIQAService
service = AIQAService()
result = service.query(input('请输入查询: '))
print(service.format_response(result, 'text'))
"
```

---

## 功能详解

### 1. 行情查询

查询期货品种的实时行情数据，包括开盘价、收盘价、最高价、最低价、成交量、持仓量。

**支持的合约类型**：
- `main` — 主力连续合约（默认）
- `next_main` — 次主力合约
- `index_continuous` — 指数连续合约
- `specific_month` — 具体月份合约（如2609）

**主力合约标记说明**：
- `XXX888` — 品种级映射（AKShare 主力连续数据）
- `XXX2609` — 合约级映射（经主力算法计算的实际合约代码）

**示例**：
```
输入：沪铜主力最新价
输出：
CU 行情（主力=CU888）:
  日期: 2026-06-26
  开盘: 101440.00
  收盘: 101560.00
  最高: 101720.00
  最低: 101310.00
  成交量: 119,672
  持仓量: 159,247

数据来源: AKShare (confidence: 0.85)
```

### 2. 持仓排名查询

查询品种或合约的前20会员持仓排名。

**示例**：
```
输入：螺纹钢2609持仓排名
输出：
RB2609 持仓排名:
  多头前5:
    1. 中信期货: 25,000 手
    2. 永安期货: 22,000 手
    ...
  空头前5:
    1. 国泰君安: 20,000 手
    ...
  净持仓: 5,000 手（多头占优）
```

### 3. 仓单查询

查询品种的仓单日报数据，包括注册仓单量、注销仓单量、增减变化。

**数据源**：交易所官网 API

**示例**：
```
输入：纯碱仓单
输出：
仓单信息: SA
  日期: 2026-06-26
  注册仓单: 85,000 手
  注销仓单: 12,000 手
  净变化: -2,000 手
  分仓库明细:
    上海洋山: 35,000 手
    广东南沙: 48,000 手

数据来源: 郑商所官网
```

### 4. 价差查询

查询跨品种或跨期价差，支持历史价差和 Z-Score 计算。

**支持的价差对**（20+）：

| 类别 | 价差对 | 说明 |
|------|--------|------|
| 黑色系 | 螺卷差、螺矿比、焦炭焦煤比 | RB-HC、RB-I、J-JM |
| 有色金属 | 铜锌比、铜铝比 | CU-ZN、CU-AL |
| 贵金属 | 金银比 | AU/AG |
| 农产品 | 豆棕差、油粕比 | M-P、Y/M |
| 能源化工 | 原油燃油差、纯碱玻璃差 | SC-FU、SA-FG |

**示例**：
```
输入：螺卷差
输出：
价差分析: RB-HC
  当前价差: -120
  Z-Score: -1.2
  近5日历史: [-110, -115, -118, -122, -120]
  RB: 3800
  HC: 3920

数据来源: 上期所 + 上期所
```

### 5. 期限结构查询

查询品种各月份合约的价格曲线和升贴水。

**示例**：
```
输入：豆粕期限结构
输出：
期限结构: M
  M2607: 3200 (升贴水: -50)
  M2608: 3220 (升贴水: -30)
  M2609: 3250 (升贴水: 0) ← 主力
  M2610: 3280 (升贴水: +30)
  M2611: 3300 (升贴水: +50)

数据来源: 大商所 2026-06-26 盘后
```

### 6. 资讯查询

查询品种相关的交易所公告、产业新闻。

**数据源**：新浪财经、交易所官网

**示例**：
```
输入：铜今天有什么新闻
输出：
资讯信息: CU
  [2026-06-27] 上期所关于调整铜期货交易保证金比例的通知
    来源: 上期所官网
    摘要: 自2026年7月1日起，铜期货合约交易保证金比例调整为10%。
  [2026-06-26] 铜市场供需分析报告
    来源: 新浪财经
    摘要: 近期铜市场供需关系偏紧，价格有望继续上涨。

数据来源: 新浪财经、交易所官网
```

---

## 查询示例

### 基础查询

| 查询意图 | 示例输入 |
|----------|----------|
| 查询行情 | 沪铜主力最新价、螺纹钢今日行情 |
| 查询持仓 | 铁矿石2609持仓排名、前20名多空 |
| 查询仓单 | 纯碱仓单、橡胶有效仓单 |
| 查询价差 | 螺卷差、金银比、铜铝比 |
| 查询资讯 | 铜今天有什么新闻、原油公告 |

### 进阶查询

| 查询意图 | 示例输入 |
|----------|----------|
| 时间范围 | 铜最近5天行情、螺纹钢近一周走势 |
| 具体合约 | 沪铜2609行情、铁矿石2610持仓 |
| 聚合统计 | 铜平均收盘价、螺纹钢最高价 |
| 品种对比 | 铜和锌的价差、铁矿vs螺纹涨跌幅 |

### 口语化查询

系统支持口语化、简写、行业黑话：

| 口语输入 | 解析结果 |
|----------|----------|
| 卷螺差 | HC-RB 价差 |
| 01合约贴水 | M01 合约升贴水 |
| 累库去库 | 库存变化趋势 |
| 黑色系 | RB/HC/I/J/JM 等 |

---

## API 参考

### AIQAService

主服务类，提供自然语言查询接口。

#### 初始化

```python
from scripts.ai_qa_service import AIQAService

service = AIQAService()
```

#### query(question, context=None)

处理自然语言查询。

**参数**：
- `question` (str): 自然语言问题
- `context` (dict, optional): 上下文信息

**返回**：
```python
{
    "success": True,
    "data": [...],  # 查询结果
    "query_type": "quote",  # 查询类型
    "variety": "CU",  # 品种代码
    "count": 1,  # 结果数量
    "metadata": {
        "query_id": "xxx",
        "fql": {...},  # FQL 查询详情
        "execution_time_ms": 5.2
    }
}
```

#### format_response(result, format_type='text')

格式化查询结果。

**参数**：
- `result` (dict): 查询结果
- `format_type` (str): 格式类型 ('text'/'markdown'/'json')

**返回**：格式化后的字符串

#### batch_query(questions)

批量查询。

**参数**：
- `questions` (list): 问题列表

**返回**：结果列表

### MultiSourceAdapter

多源数据适配器，7 级数据源自动降级。

```python
from scripts.multi_source_adapter import MultiSourceAdapter, DataSource

adapter = MultiSourceAdapter()

# 获取行情（自动按优先级尝试每个数据源）
result = adapter.get_quote("CU", "2026-06-26")

# 查看各数据源健康状态
health = adapter.get_source_health()
for source, status in health.items():
    print(f"{source}: available={status['available']}")
```

### DuckDB 存储

所有数据持久化在 DuckDB，5 张表：

| 表名 | 内容 | 说明 |
|------|------|------|
| `oi_ranking` | 前20会员多空持仓 | ~360K 行/年 |
| `warehouse` | 仓单日报 | ~50K 行/年 |
| `futures_news` | 产业资讯 | ~15K 行/年 |
| `term_structure` | 期限结构 | ~500K 行/年 |
| `query_cache` | API 查询缓存 | 4h TTL 自动过期 |

---

## 配置说明

### 品种词典

品种词典定义在 `references/varieties.yaml`，包含所有支持的品种及其别名。

**格式**：
```yaml
varieties:
  - code: CU
    exchange: SHFE
    name: 铜
    aliases: [铜, 沪铜, 阴极铜]
    unit: 5t/手
    delivery_months: [1,2,3,4,5,6,7,8,9,10,11,12]
```

**添加新品种**：
1. 编辑 `references/varieties.yaml`
2. 添加品种信息
3. 重启服务（支持热加载）

### 主力映射表

主力映射表自动更新，存储在 `data/dominant_maps/` 目录。

**更新频率**：每个交易日 15:30
**自动化任务**：`automation-1782565912739`

映射表格式：
```json
{
  "CU": {
    "main": "CU888",
    "next_main": null,
    "index": "CU99",
    "index_price": 101560.0,
    "volume": 119672,
    "open_interest": 159247,
    "is_financial": false,
    "exchange": "SHFE",
    "trade_date": "2026-06-26",
    "updated_at": "2026-06-28T15:35:25"
  },
  "IF": {
    "main": "IF2609",
    "next_main": "IF2612",
    "index": "IF99",
    "index_price": 26331.42,
    "is_financial": true,
    "exchange": "CFFEX",
    ...
  }
}
```

字段说明：
- `main` — 主力合约代码（`XXX888` 为品种级映射，`XXX2609` 为合约级算法计算结果）
- `next_main` — 次主力（None 表示数据源未提供）
- `index` — 指数连续合约代码（`XXX99`）
- `is_financial` — 是否为金融期货（CFFEX）
- `exchange` — 所属交易所

### 数据源配置

数据源优先级定义在 `scripts/multi_source_adapter.py` 中的 `DataSourceHealth` 类：

```python
# 各数据源默认置信度
self.confidence_map = {
    DataSource.TQSDK: 1.0,
    DataSource.EXCHANGE_API: 1.0,
    DataSource.EASTMONEY: 1.0,
    DataSource.AKSHARE: 1.0,
    DataSource.WEBSEARCH: 1.0,
    DataSource.CACHE: 1.0,
}
```

如需调整优先级或禁用某数据源，直接修改此映射。

---

## 常见问题

### Q1: 查询返回"品种未识别"怎么办？

**A**: 检查输入是否包含有效的品种名称或代码。系统支持：
- 中文别名：铜、沪铜、阴极铜
- 英文代码：CU、RB、SA
- 行业术语：螺纹、焦煤、纯碱

如果仍然无法识别，可能是输入包含未知复合词（如"铜锌合金"）。

### Q2: 仓单数据获取失败怎么办？

**A**: 仓单数据依赖交易所官网 API，可能因网络问题失败。系统会：
1. 尝试从交易所官网获取
2. 如果失败，返回默认结构并提示
3. 建议用户直接访问交易所官网查询

### Q3: 如何添加自定义价差对？

**A**: 编辑 `scripts/nl2fql_engine.py`，在 `spread_pairs` 字典中添加：

```python
self.spread_pairs = {
    # 现有价差对...
    "我的价差": ("品种1", "品种2"),  # 新增
}
```

### Q4: 查询性能慢怎么办？

**A**: 检查以下几点：
1. 确保 DuckDB 缓存正常（首次查询较慢）
2. 检查网络连接（仓单/资讯依赖外部 API）
3. 减少查询时间范围（如从"近一年"改为"近一月"）

### Q5: 哪些品种有合约级主力映射？

**A**: 以下品种使用完整主力算法（持仓量/成交量排序 + 1.1x 阈值 + 远月约束）：
- **CFFEX 所有品种**（IF/IC/IM/IH/T/TF/TS/TL）— 交易所API 合约级数据
- **AO**（氧化铝）/ **BC**（国际铜）— 东方财富合约级数据

其余品种当前为 AKShare 品种级数据映射（888/99），如需更细粒度合约级数据，可等待交易所 API 恢复直连后自动升级。

### Q6: 如何扩展到境外期货？

**A**: 当前版本仅支持国内六大交易所。扩展境外期货需要：
1. 添加境外品种到 `varieties.yaml`
2. 对接境外数据源（COMEX、LME、CME 等）
3. 更新实体识别逻辑

---

## 更新日志

### v3.0.0 (2026-06-28)

**重大重构**：
- 合并 exchange-futures-data v3.2 为内置采集器 `collectors/exchange_data/`
- 存储引擎从 DolphinDB/ES/Milvus 迁移至 DuckDB（零部署，单文件便携）
- 多源适配器直接调用本地采集器，不再依赖外部 skill
- DuckDB 共享实例：NL2FQL 和采集器共用同一数据库文件

### v2.5.1 (2026-06-28)
- WH6 本地数据源已移除（v3.1.0）
- 数据源链路：TqSDK → 交易所 API → 东方财富 → AKShare → WebSearch → 缓存

### v2.5.0 (2026-06-28)
- WH6 本地数据源已移除（v3.1.0）

### v2.4.0 (2026-06-28)
- 新增东方财富 API 数据源采集器

### v2.3.0 (2026-06-28)
- DuckDB 存储引擎上线，废弃 DolphinDB/ES/Milvus
- 新增 query_cache 表，TTL 自动过期

### v2.2.0 (2026-06-27)
- 境外期货数据支持、分钟级数据

### v2.1.0 (2026-06-27)
- 对接实际仓单/资讯 API，20+ 价差对，验收测试 19/19 通过

### v2.0.0 (2026-06-27)
- NL2FQL 引擎 v2.0，智能品种识别，金融规则引擎

### v1.0.0 (2026-06-27)
- 初始版本：基础行情/持仓查询 + 主力映射

---

## 技术支持

- **技能路径**：`~/.workbuddy/skills/futures-data-search/`
- **GitHub 仓库**：https://github.com/CTAAgents/quant-skills
- **问题反馈**：请在 GitHub Issues 中提交

---

## 许可证

本技能遵循 MIT 许可证。
