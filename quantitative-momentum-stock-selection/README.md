# 量化动量选股系统 v1.1.0 (A股优化版)

基于《构建量化动量选股系统的实用指南》的完整动量选股策略，针对A股市场特性进行全面优化。

## 核心理念

**动量投资的本质**：买入赢家股（价格走势强劲的股票），而不是预测未来或寻找成长型股票。

**与价值投资的区别**：
- 价值投资者：买入便宜的"失宠"股
- 动量投资者：勇敢追涨，买入价格走势强劲股

## A股优化特性（v1.1.0）

### 1. 市场特性适配
- **涨跌停限制处理**：自动过滤涨跌停数据，跌停时强制止损
- **T+1交易制度适配**：更紧的止损设置，更短的动量窗口
- **散户行为影响**：提高成交量确认权重（25%）

### 2. A股特有数据源
- **北向资金数据**：外资动向指标
- **融资融券数据**：杠杆资金动向
- **行业资金流向**：行业资金流入流出
- **涨跌停数据**：市场热度和风险指标

### 3. 参数优化
- **动量窗口**：15/45/150天（原20/60/252天）
- **打分权重**：成交量和风险控制权重提高
- **动量阈值**：降低阈值，更早入场离场

## 功能特性

### 1. 多维度动量打分体系（100分制，A股优化版）

| 维度 | 权重 | 指标 | 说明 |
|------|------|------|------|
| **价格动量** | 25分 | 15日收益率、45日收益率、150日收益率 | A股优化后窗口更短 |
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

- **仓位控制**：单股15%/行业25%/总仓位70%
- **止损策略**：初始1.5倍ATR/移动0.75倍ATR/时间15天
- **止盈策略**：阶段式止盈，保护利润
- **涨跌停风险控制**：跌停强制止损，连续下跌预警

## 快速开始

### 安装依赖

```bash
pip install pandas numpy akshare
```

### 基本使用

```python
from scripts import get_config, DataCollector, MomentumScorer, MomentumStrategy

# 初始化
config = get_config()
collector = DataCollector(config)
scorer = MomentumScorer(config)
strategy = MomentumStrategy(config)

# 获取股票列表
stock_list = collector.get_stock_list()

# 获取股票历史数据
stock_data = {}
for stock_code in stock_list['code'].head(100):  # 示例：前100只股票
    data = collector.get_stock_history(stock_code)
    if not data.empty:
        stock_data[stock_code] = data

# 生成交易信号
signals = strategy.generate_signals(stock_data)

# 输出结果
for signal in signals[:10]:  # Top 10 信号
    print(f"{signal.stock_code} - {signal.stock_name}")
    print(f"操作：{signal.action}")
    print(f"动量分数：{signal.score.total_score:.1f}")
    print(f"趋势阶段：{signal.score.trend_stage}")
    print(f"原因：{signal.reason}")
    print("-" * 50)
```

### 命令行使用

```bash
# 扫描全市场
python -m scripts.main scan

# 分析单只股票
python -m scripts.main analyze --stock 600519

# 运行回测
python -m scripts.main backtest --start 2020-01-01 --end 2025-12-31

# 生成报告
python -m scripts.main report
```

## 模块说明

| 模块 | 功能 |
|------|------|
| `config.py` | 系统参数、股票池配置、数据源配置 |
| `data_collector.py` | 数据采集、缓存管理 |
| `scoring.py` | 多维度动量打分系统 |
| `strategy.py` | 策略核心逻辑、信号生成 |
| `backtest.py` | 回测引擎、绩效统计 |
| `report.py` | HTML报告生成 |

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

### 风险管理规则

1. **仓位限制**：
   - 单只股票最大仓位：20%
   - 单个行业最大仓位：30%
   - 总仓位上限：80%

2. **止损策略**：
   - 初始止损：买入价下方2×ATR
   - 移动止损：趋势延续时，止损移至近期低点下方1×ATR
   - 时间止损：持有超过20个交易日未盈利，考虑止损

3. **止盈策略**：
   - 第一目标：盈利20%时减仓30%
   - 第二目标：盈利40%时再减仓30%
   - 最终目标：趋势破坏时清仓

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

## 版本历史

### v1.1.0 (2026-06-28) **A股优化版**
**基于A股市场特性进行全面优化**

1. **A股市场特性适配**：
   - 涨跌停限制处理：自动过滤涨跌停数据，跌停时强制止损
   - T+1交易制度适配：更紧的止损设置，更短的动量窗口
   - 散户行为影响：提高成交量确认权重（25%）

2. **数据源扩展**：
   - 新增东方财富数据源
   - 新增北向资金数据接口
   - 新增融资融券数据接口
   - 新增行业资金流向数据接口
   - 新增涨跌停数据接口

3. **策略参数优化**：
   - 动量窗口：15/45/150天（原20/60/252天）
   - 打分权重：成交量25%/风险控制15%
   - 动量阈值：强烈买入75分/买入65分

4. **风险管理优化**：
   - 止损策略：初始1.5倍ATR/移动0.75倍ATR/时间15天
   - 仓位限制：单股15%/行业25%/总仓位70%
   - 涨跌停风险控制：跌停强制止损，连续下跌预警

### v1.0.0 (2026-06-28)
**初始版本 - 基于《构建量化动量选股系统的实用指南》**

1. **核心功能实现**：
   - 100分制多维动量打分体系（5个维度）
   - 趋势阶段识别（启动/主升/衰竭/反转）
   - 估值过滤机制（PE/PB分位）
   - 风险管理框架（仓位/止损/止盈）

2. **模块架构**：
   - 数据采集与缓存（data_collector.py）
   - 动量打分系统（scoring.py）
   - 策略核心（strategy.py）
   - 配置管理（config.py）

3. **数据源集成**：
   - AKShare作为主要数据源
   - 本地缓存提高效率
   - 多数据源降级策略

4. **使用方式**：
   - 全市场扫描模式
   - 单股分析模式
   - 回测验证模式
   - 实时信号模式

## 许可证

MIT License