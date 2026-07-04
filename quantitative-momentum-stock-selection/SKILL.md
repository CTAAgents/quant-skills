---
name: quantitative-momentum-stock-selection
version: 1.1.0
description: 量化动量选股系统 v1.1.0 (A股优化版) — 多维度动量打分体系识别强势股票，构建动量投资组合。核心思想：买入赢家股而非成长型投资。支持全市场扫描、动量信号筛选、投资组合构建、回测验证。A股优化：涨跌停过滤+T+1适配+北向资金数据。
agent_created: true
user_invocable: true
triggers:
  - 动量选股
  - 量化动量
  - 赢家股
  - 趋势选股
  - 动量策略
  - 股票筛选
  - 强势股
  - 动量打分
  - 投资组合
  - 回测验证
  - A股动量
  - 涨跌停过滤
---

# 量化动量选股系统 v1.1.0 (A股优化版)

## 核心理念

**动量投资的本质**：买入赢家股（价格走势强劲的股票），而不是预测未来或寻找成长型股票。

**与价值投资的区别**：
- 价值投资者：买入便宜的"失宠"股
- 动量投资者：勇敢追涨，买入价格走势强劲股

**行为金融学基础**：推动价值投资者获得超额收益的行为偏差和职业担忧，正是推动动量效应长期存在的关键机制。

## 核心能力

### 1. 多维度动量打分体系（100分制，A股优化版）

| 维度 | 权重 | 指标 | 说明 |
|------|------|------|------|
| **价格动量** | 25分 | 15日收益率、45日收益率、150日收益率 | 核心动量指标，A股优化后窗口更短 |
| **相对强度** | 20分 | 行业相对强度、市场相对强度 | 相对于基准和行业的表现 |
| **成交量确认** | 25分 | 量价配合、成交量趋势 | A股散户交易活跃，成交量更重要 |
| **趋势结构** | 15分 | 均线排列、通道位置 | 价格结构健康度 |
| **风险控制** | 15分 | 波动率、回撤控制 | A股波动大，风险控制更重要 |

### 2. 趋势阶段识别

| 阶段 | 特征 | 操作建议 |
|------|------|---------|
| **启动期** | 价格突破关键阻力，成交量放大 | 重点关注，轻仓试探 |
| **主升期** | 均线多头排列，趋势明确 | 主力介入，持有待涨 |
| **衰竭期** | 动量减弱，出现顶背离 | 警惕风险，逐步减仓 |
| **反转期** | 趋势破坏，跌破关键支撑 | 及时止损，空仓观望 |

### 3. 估值过滤机制

- **PE分位过滤**：避免在估值过高时追涨
- **PB分位过滤**：辅助判断估值水平
- **行业估值对比**：相对估值优势判断

### 4. 风险管理框架（A股优化版）

- **仓位控制**：单只股票最大仓位15%，单个行业25%，总仓位70%
- **止损策略**：初始止损1.5倍ATR，移动止损0.75倍ATR，时间止损15天
- **止盈策略**：阶段式止盈，保护利润
- **分散投资**：行业分散，降低集中风险
- **涨跌停风险控制**：跌停时强制止损，连续下跌风险预警

### 5. A股市场特性适配（v1.1.0新增）

#### 5.1 涨跌停限制处理
- 自动过滤涨跌停数据，避免技术指标失真
- 跌停时触发强制止损信号
- 连续下跌风险预警（近5日4日下跌）

#### 5.2 T+1交易制度适配
- 更紧的止损设置（1.5倍ATR，考虑T+1限制）
- 更短的动量窗口（15/45/150天）
- 更早的入场和离场信号

#### 5.3 A股特有数据源
- **北向资金数据**：外资动向指标
- **融资融券数据**：杠杆资金动向
- **行业资金流向**：行业资金流入流出
- **涨跌停数据**：市场热度和风险指标

#### 5.4 A股特有指标
- 北向资金净流入
- 融资余额变化
- 涨停家数
- 换手率

### 6. 参数优化（A股市场）

| 参数 | 原值 | 优化值 | 说明 |
|------|------|--------|------|
| 短期窗口 | 20天 | 15天 | 更敏感 |
| 中期窗口 | 60天 | 45天 | 更短 |
| 长期窗口 | 252天 | 150天 | 更短 |
| 价格动量权重 | 30% | 25% | A股波动大 |
| 成交量权重 | 20% | 25% | 散户交易活跃 |
| 风险控制权重 | 10% | 15% | 风险控制更重要 |
| 强烈买入阈值 | 80分 | 75分 | 更宽松 |
| 买入阈值 | 70分 | 65分 | 更早入场 |
| 初始止损 | 2.0倍ATR | 1.5倍ATR | 更紧 |
| 移动止损 | 1.0倍ATR | 0.75倍ATR | 更紧 |
| 单股仓位 | 20% | 15% | 更分散 |
| 总仓位上限 | 80% | 70% | 更保守 |

## 使用方式

### 1. 全市场扫描模式

```python
from scripts.scanner import MarketScanner
from scripts.scoring import MomentumScorer
from scripts.portfolio import PortfolioBuilder

# 初始化
scanner = MarketScanner()
scorer = MomentumScorer()
builder = PortfolioBuilder()

# 扫描全市场
stocks = scanner.scan_all_stocks()

# 动量打分
scored_stocks = scorer.score_stocks(stocks)

# 构建投资组合
portfolio = builder.build_portfolio(scored_stocks)

# 输出结果
print(f"Top 10 动量股票：")
for stock in portfolio.top_stocks(10):
    print(f"{stock.code} - {stock.name} - 动量分数：{stock.momentum_score}")
```

### 2. 单股分析模式

```python
from scripts.analyzer import StockAnalyzer

# 分析单只股票
analyzer = StockAnalyzer("600519")  # 贵州茅台
analysis = analyzer.analyze()

print(f"股票代码：{analysis.code}")
print(f"股票名称：{analysis.name}")
print(f"动量分数：{analysis.momentum_score}")
print(f"趋势阶段：{analysis.trend_stage}")
print(f"估值分位：{analysis.valuation_percentile}")
print(f"操作建议：{analysis.recommendation}")
```

### 3. 回测验证模式

```python
from scripts.backtest import BacktestEngine
from scripts.strategy import MomentumStrategy

# 初始化回测引擎
strategy = MomentumStrategy()
engine = BacktestEngine(strategy)

# 运行回测
result = engine.run(
    start_date="2020-01-01",
    end_date="2025-12-31",
    initial_capital=1000000
)

# 输出回测结果
print(f"年化收益率：{result.annual_return:.2%}")
print(f"最大回撤：{result.max_drawdown:.2%}")
print(f"夏普比率：{result.sharpe_ratio:.3f}")
print(f"胜率：{result.win_rate:.2%}")
```

### 4. 实时信号模式

```python
from scripts.signal import SignalGenerator
from scripts.monitor import PortfolioMonitor

# 生成实时信号
generator = SignalGenerator()
signals = generator.generate_signals()

# 监控投资组合
monitor = PortfolioMonitor()
status = monitor.check_portfolio()

print(f"今日信号：")
for signal in signals:
    print(f"{signal.code} - {signal.action} - {signal.reason}")

print(f"\n投资组合状态：")
print(f"总市值：{status.total_value:,.2f}")
print(f"今日盈亏：{status.daily_pnl:,.2f}")
print(f"持仓数量：{status.holding_count}")
```

## 模块说明

| 模块 | 功能 |
|------|------|
| `config.py` | 系统参数、股票池配置、数据源配置 |
| `scanner.py` | 全市场股票扫描、数据采集 |
| `scoring.py` | 多维度动量打分系统 |
| `analyzer.py` | 单股深度分析 |
| `strategy.py` | 策略核心逻辑、信号生成 |
| `portfolio.py` | 投资组合构建、仓位管理 |
| `backtest.py` | 回测引擎、绩效统计 |
| `signal.py` | 实时信号生成 |
| `monitor.py` | 投资组合监控 |
| `report.py` | HTML报告生成 |
| `data_collector.py` | 数据采集、缓存管理 |

## 数据源

### 主要数据源

| 数据类型 | 数据源 | 说明 |
|----------|--------|------|
| **股票行情** | AKShare / Tushare | 日线数据、分钟线数据 |
| **财务数据** | AKShare / 东方财富 | 财务报表、估值数据 |
| **行业数据** | AKShare | 行业分类、板块数据 |
| **资金流向** | AKShare / 同花顺 | 主力资金、北向资金 |

### 数据源优先级

1. **本地缓存**：优先使用缓存数据，提高效率
2. **AKShare**：免费、稳定、数据全面
3. **Tushare**：专业金融数据接口
4. **其他数据源**：作为降级备选

## 策略逻辑详解

### 动量打分算法

```python
def calculate_momentum_score(stock_data):
    """
    计算股票的动量分数（100分制）
    
    Args:
        stock_data: 股票历史数据
    
    Returns:
        momentum_score: 动量分数（0-100）
        components: 各维度分数明细
    """
    # 1. 价格动量（30分）
    price_momentum = calculate_price_momentum(stock_data)
    
    # 2. 相对强度（25分）
    relative_strength = calculate_relative_strength(stock_data)
    
    # 3. 成交量确认（20分）
    volume_confirmation = calculate_volume_confirmation(stock_data)
    
    # 4. 趋势结构（15分）
    trend_structure = calculate_trend_structure(stock_data)
    
    # 5. 风险控制（10分）
    risk_control = calculate_risk_control(stock_data)
    
    # 加权汇总
    total_score = (
        price_momentum * 0.30 +
        relative_strength * 0.25 +
        volume_confirmation * 0.20 +
        trend_structure * 0.15 +
        risk_control * 0.10
    )
    
    return total_score, {
        'price_momentum': price_momentum,
        'relative_strength': relative_strength,
        'volume_confirmation': volume_confirmation,
        'trend_structure': trend_structure,
        'risk_control': risk_control
    }
```

### 信号生成规则

| 信号类型 | 条件 | 操作建议 |
|----------|------|---------|
| **强烈买入** | 动量分数 ≥ 80，趋势阶段为启动期或主升期 | 主力介入，重仓买入 |
| **买入** | 动量分数 ≥ 70，趋势结构健康 | 可以买入，控制仓位 |
| **持有** | 动量分数 ≥ 60，趋势延续 | 继续持有，设置止损 |
| **减仓** | 动量分数 < 60，或出现顶背离 | 逐步减仓，保护利润 |
| **卖出** | 动量分数 < 50，趋势破坏 | 及时卖出，空仓观望 |

### 风险管理规则（A股优化版）

1. **仓位限制**：
   - 单只股票最大仓位：15%
   - 单个行业最大仓位：25%
   - 总仓位上限：70%

2. **止损策略**：
   - 初始止损：买入价下方1.5×ATR（更紧，考虑T+1限制）
   - 移动止损：趋势延续时，止损移至近期低点下方0.75×ATR
   - 时间止损：持有超过15个交易日未盈利，考虑止损

3. **止盈策略**：
   - 第一目标：盈利20%时减仓30%
   - 第二目标：盈利40%时再减仓30%
   - 最终目标：趋势破坏时清仓

4. **涨跌停风险控制**：
   - 跌停时强制止损
   - 近5日4日下跌时预警
   - 最大回撤限制15%

## 报告生成

### 报告内容

1. **市场概览**：大盘走势、行业轮动、资金流向
2. **动量扫描结果**：Top 10/20 动量股票列表
3. **投资组合建议**：具体股票、仓位比例、操作建议
4. **风险提示**：市场风险、个股风险、策略局限性
5. **回测验证**：策略历史表现、绩效指标

### 报告格式

- **HTML报告**：交互式图表、可折叠章节、移动端适配
- **PDF报告**：适合打印和分享
- **JSON数据**：程序化处理和分析

## 版本历史

### v1.1.0 (2026-06-28) **A股优化版**
**基于A股市场特性进行全面优化**

1. **A股市场特性适配**：
   - **涨跌停限制处理**：自动过滤涨跌停数据，跌停时强制止损
   - **T+1交易制度适配**：更紧的止损设置，更短的动量窗口
   - **政策影响因素**：预留政策事件驱动因子接口
   - **散户行为影响**：提高成交量确认权重

2. **数据源扩展**：
   - 新增东方财富数据源
   - 新增北向资金数据接口
   - 新增融资融券数据接口
   - 新增行业资金流向数据接口
   - 新增涨跌停数据接口

3. **策略参数优化**：
   - **动量窗口**：短期15天/中期45天/长期150天（原20/60/252天）
   - **打分权重**：价格动量25%/相对强度20%/成交量25%/趋势15%/风险15%
   - **动量阈值**：强烈买入75分/买入65分/持有55分/减仓45分/卖出35分

4. **风险管理优化**：
   - **止损策略**：初始止损1.5倍ATR/移动止损0.75倍ATR/时间止损15天
   - **仓位限制**：单股15%/行业25%/总仓位70%
   - **涨跌停风险控制**：跌停强制止损，连续下跌预警

5. **新增A股特有指标**：
   - 北向资金净流入
   - 融资余额变化
   - 涨停家数
   - 换手率

### v1.0.0 (2026-06-28)
**初始版本 - 基于《构建量化动量选股系统的实用指南》**

1. **核心功能实现**：
   - 100分制多维动量打分体系（5个维度）
   - 趋势阶段识别（启动/主升/衰竭/反转）
   - 估值过滤机制（PE/PB分位）
   - 风险管理框架（仓位/止损/止盈）

2. **模块架构**：
   - 数据采集与缓存（data_collector.py）
   - 全市场扫描（scanner.py）
   - 动量打分系统（scoring.py）
   - 单股分析（analyzer.py）
   - 策略核心（strategy.py）
   - 投资组合管理（portfolio.py）
   - 回测引擎（backtest.py）
   - 实时信号（signal.py）
   - 投资组合监控（monitor.py）
   - 报告生成（report.py）

3. **数据源集成**：
   - AKShare作为主要数据源
   - 本地缓存提高效率
   - 多数据源降级策略

4. **使用方式**：
   - 全市场扫描模式
   - 单股分析模式
   - 回测验证模式
   - 实时信号模式

5. **风险提示**：
   - 动量衰减风险
   - 市场系统性风险
   - 个股特异性风险
   - 策略局限性说明

## 与现有技能的配合

### 与 commodity-trend-signal 的配合

- **commodity-trend-signal**：负责商品期货趋势信号发现
- **quantitative-momentum-stock-selection**：负责股票动量选股
- **配合方式**：两个技能独立部署，通过数据字典传递中间结果

### 与 a-share-etf-momentum 的配合

- **a-share-etf-momentum**：负责行业ETF轮动策略
- **quantitative-momentum-stock-selection**：负责个股动量选股
- **配合方式**：ETF轮动提供市场趋势判断，个股选股提供具体标的

## 注意事项

1. **市场适应性**：动量策略在趋势明显的市场中表现最佳，在震荡市中可能表现不佳
2. **参数敏感性**：动量窗口、打分权重等参数需要根据市场环境调整
3. **交易成本**：频繁调仓会产生较高的交易成本，需要权衡收益与成本
4. **流动性风险**：确保选择的股票具有足够的流动性，避免冲击成本过高
5. **历史回测局限性**：过去的表现不代表未来收益，策略需要持续监控和优化