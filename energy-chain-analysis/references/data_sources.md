# 燃料油数据源配置

## 一、五层降级策略

本技能采用多源数据容错策略，按优先级使用以下方案：

### Tier 0（最高优先级）：TqSdk 实盘行情

使用 TqSdk 获取实时行情和K线数据，认证通过环境变量 `TQSDK_USERNAME` 和 `TQSDK_PASSWORD`。

**合约符号**：
- FU主力：`KQ.m@SHFE.fu`
- LU主力：`KQ.m@INE.lu`
- 上海原油（布伦特代理）：`KQ.m@INE.sc`

**获取能力**：
- 实时行情快照（最新价、涨跌幅、成交量、持仓量）
- 日线/分钟K线数据（OHLCV）
- 通过 `scripts/fetch_fuel_oil_data.py` 调用

**技术指标计算**：使用 Ta-Lib（优先）或 pandas 计算全部13项技术指标

### Tier 1（第一优先级）：专业API数据源
1. `neodata-financial-search` - 专业金融数据（期货K线、技术指标、资金流向）
2. `westockdata` - 技术面分析数据（A股/期货K线、财务报表、技术指标、筹码分析）

**查询品种**：
- 上期所燃料油FU主力合约
- 上期所低硫燃料油LU主力合约
- 布伦特原油
- 美元指数DXY
- 美元兑人民币

**提取字段**：实时最新价、涨跌幅%、日内高低点、成交量、持仓量、日增仓、52周区间、主力合约切换信息

### Tier 2（第二优先级）：WebSearch + WebFetch（核心备用）
通用网络搜索 + 权威媒体网站抓取

**实时行情源**：
- Bloomberg Terminal（bloomberg.com）
- Reuters Eikon（reuters.com）
- Investing.com（技术指标数据）
- TradingView（图表和技术分析）

**交易所官方**：
- 上海国际能源交易中心（ine.cn）
- 上海期货交易所（shfe.com.cn）
- 新加坡交易所SGX（sgx.com）
- ICE期货交易所（theice.com）

**库存&供需数据**：
- 新加坡MPA（mpa.gov.sg）
- 隆众资讯（oilchem.com）
- EIA（eia.gov）
- IEA（iea.org）

**航运数据**：
- 波罗的海交易所（balticexchange.com）

**定价数据**：
- S&P Global Platts（spglobal.com/platts）
- Argus Media（argusmedia.com）

### 第三优先级：综合财经媒体（补充）
- **国际媒体**：Bloomberg、Reuters、Wall Street Journal、Financial Times
- **中文媒体**：新浪财经实时行情、东方财富实时行情、财联社快讯、隆众资讯

### 第四优先级：本地模拟（终极保底）
如果以上均无有效数据，基于近期市场数据合理推演，但必须标注"数据暂缺，基于历史数据推演"

---

## 二、核心数据清单

### 行情数据
| 数据项 | 搜索关键词（中文） | 搜索关键词（英文） | 优先数据源 |
|--------|-------------------|-------------------|-----------|
| FU期货行情 | "上期所燃料油FU主力 最新价格" | "Shanghai fuel oil futures FU price" | neodata/交易所官网 |
| LU期货行情 | "上期所低硫燃料油LU主力 最新" | "Shanghai low sulfur fuel oil LU" | neodata/交易所官网 |
| 布伦特原油 | "布伦特原油 最新价格" | "Brent crude oil price live today" | Bloomberg/Reuters |
| WTI原油 | "WTI原油 最新价格" | "WTI crude oil price live" | Bloomberg/Reuters |

### 库存数据
| 数据项 | 搜索关键词（中文） | 搜索关键词（英文） | 优先数据源 |
|--------|-------------------|-------------------|-----------|
| 新加坡燃料油库存 | "新加坡燃料油库存 最新" | "Singapore fuel oil inventory latest" | MPA/IEA/隆众 |
| 舟山保税库存 | "舟山保税燃料油库存 最新" | "Zhoushan bonded fuel oil stock" | 隆众/海关总署 |

### 价差数据
| 数据项 | 搜索关键词（中文） | 搜索关键词（英文） | 优先数据源 |
|--------|-------------------|-------------------|-----------|
| 高低硫价差 | "高低硫燃料油价差 最新" | "VLSFO HSFO spread latest" | Platts/Bloomberg |
| 裂解价差 | "燃料油裂解价差 最新" | "fuel oil crack spread latest" | Bloomberg/ICE |
| 内外价差 | "燃料油内外价差 进口成本" | "fuel oil import parity China" | 隆众/Platts |

### 基础设施数据
| 数据项 | 搜索关键词（中文） | 搜索关键词（英文） | 优先数据源 |
|--------|-------------------|-------------------|-----------|
| BDI指数 | "BDI波罗的海干散货指数 最新" | "BDI Baltic Dry index today" | 波罗的海交易所 |
| 汇率 | "美元兑人民币 最新" | "USD CNY exchange rate live" | 中国外汇交易中心 |
| 新加坡MOPS | "新加坡MOPS燃料油现货 最新" | "Singapore MOPS fuel oil price" | Platts/Argus |

### 技术指标数据
| 数据项 | 搜索关键词 | 优先数据源 |
|--------|-----------|-----------|
| FU/LU RSI(14) | "燃料油FU RSI指标 最新" / "fuel oil RSI 14 today" | TradingView/Investing.com |
| FU/LU CCI(14) | "燃料油FU CCI指标 最新" / "fuel oil CCI 14" | TradingView/Investing.com |
| FU/LU MACD | "燃料油FU MACD指标 最新" / "fuel oil MACD" | TradingView/Investing.com |
| 布伦特原油RSI/CCI | "Brent crude oil RSI 14 today" | TradingView/Investing.com |

### 新闻&政策数据
| 数据项 | 搜索关键词（中文） | 搜索关键词（英文） | 优先数据源 |
|--------|-------------------|-------------------|-----------|
| IMO政策 | "IMO限硫 最新政策" / "IMO CII EEXI 最新" | "IMO shipping emissions regulation 2025" / "IMO CII EEXI latest" | IMO官网/Reuters |
| 关税政策 | "燃料油进口关税 最新" | "China fuel oil import tariff" | 海关总署/商务部 |
| 燃油新闻 | "燃料油市场 最新消息" | "fuel oil market news Asia latest" | Reuters/Bloomberg/隆众 |
| 中东地缘 | "中东局势 原油 最新" | "Middle East geopolitics oil latest" | Reuters/CNN |

---

## 三、技术指标阈值参考（完整清单）

| 指标 | 参数 | 超买阈值 | 超卖阈值 | 中性区间 | 信号解读 |
|------|------|---------|---------|---------|---------|
| MA | 5,10,20,60日 | - | - | - | 多头/空头排列、支撑/阻力 |
| RSI(14) | 14日 | >70 | <30 | 30-70 | 超买卖出/超卖买入/背离 |
| STOCH(9,6) | K=9,D=6 | >80 | <20 | 20-80 | K线穿越D线 |
| STOCHRSI(14) | 14日 | >80 | <20 | 20-80 | 随机RSI极端值 |
| MACD(12,26) | 快12/慢26/信号9 | 金叉 | 死叉 | - | 趋势确认/背离 |
| ADX(14) | 14日 | >25强趋势 | <20无趋势 | 20-25 | +DI/-DI方向判断 |
| Williams %R | 14日 | >-20 | <-80 | -80~-20 | 超买卖出/超卖买入 |
| CCI(14) | 14日 | >+100 | <-100 | -100~+100 | 穿越±100/穿越0轴 |
| ATR(14) | 14日 | - | - | - | 止损幅度参考 |
| Highs/Lows(14) | 14日 | - | - | - | 价格区间参考 |
| Ultimate Oscillator | 7,14,28 | >70 | <30 | 30-70 | 多周期动量综合 |
| ROC | 12日 | >5%强势 | <-5%弱势 | -5%~5% | 动量变化率 |
| Bull/Bear Power(13) | 13日 | 多头强势 | 空头强势 | - | 多空力量对比 |

**计算引擎**：Ta-Lib（优先，需安装C库）或纯 pandas/numpy 实现

## 四、价差分析参考区间

| 价差类型 | 计算公式 | 正常区间 | 警戒值 | 交易信号 |
|---------|---------|---------|--------|---------|
| 内外价差 | 国内FU/LU价 - MOPS×汇率 - 杂费 | 20~40元/吨 | >60 或 <0 | 高空低多 |
| 高低硫价差 | LU价格 - FU价格 | 300~500元/吨 | 历史80%分位 | 套利信号 |
| 裂解价差 | 原油价格 - 燃料油价格 | 品种特定 | 历史极值 | 跨品种套利 |
| WTI-Brent价差 | WTI - Brent | -5~5美元 | 极端偏离 | 参考信号 |

## 五、数据质量评级标准

| 评级 | 条件 | 输出要求 |
|------|------|---------|
| 高 | 至少2个Tier1数据源确认，数据时效<24h | 正常输出所有分析 |
| 中 | 1个Tier1或2个Tier2数据源，数据时效<48h | 标注数据来源，正常输出 |
| 低 | 仅Tier3或部分数据缺失 | 标注"数据暂缺"，限制输出深度 |
| 极低 | 无有效数据源 | 标注"基于历史推演"，仅输出框架 |