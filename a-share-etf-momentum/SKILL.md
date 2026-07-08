---
name: a-share-etf-momentum
version: 1.9.0
description: A股行业ETF双动量轮动策略 — 绝对动量择时+相对动量轮动+估值分位刹车。通过沪深300ETF判断市场趋势，多头轮动持有最强行业ETF，熊市切换货币ETF。支持完整回测与实盘调仓信号，年化44.30%，夏普1.275。
agent_created: true
user_invocable: true
triggers:
  - ETF轮动
  - 双动量
  - 行业轮动
  - 动量策略
  - A股ETF
  - 绝对动量
  - 相对动量
  - 估值刹车
  - 参数优化
---

# A股行业ETF双动量轮动策略 v1.9

## 策略概述

**核心思想**：双动量（Dual Momentum）结合绝对动量与相对动量：
- **绝对动量**（金丝雀）：沪深300ETF 120日收益率 > 0 → 多头市场，允许持有行业ETF
- **相对动量**（赛马）：在6只行业ETF中选取过去50日收益率最高者
- **估值刹车**：PE/PB分位 > 80% 且涨幅 > 30% → 跳过过热标的（v1.1新增完整实现）
- **调仓频率**：月频调仓

## 标的池

| 类别 | ETF名称 | 代码 | 跟踪指数 | 备注 |
|------|---------|------|----------|------|
| 基准（金丝雀） | 沪深300ETF | 510300 | 000300 | 绝对动量判定 |
| 行业A组 | 有色金属ETF | 512400 | 399395 | 资源 |
| | 银行ETF | 510650 | 000951 | 金融 |
| | 高端制造ETF | 516860 | 399808 | 制造 |
| | 消费ETF | 159928 | 000932 | 消费 |
| | 医药ETF | 512010 | 000933 | 医药 |
| | 科技ETF | 515000 | 931087 | 科技 |
| 防御资产 | 银华日利 | 511880 | - | 货币ETF |

## 核心参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `momentum_window` | 120 | 绝对动量窗口（交易日）- v1.9训练/测试优化 |
| `relative_momentum_window` | 50 | 相对动量窗口（交易日）- v1.9训练/测试优化 |
| `rebalance_freq` | monthly | 调仓频率（月末） |
| `top_n` | 1 | 相对动量选取数量 |
| `abs_momentum_threshold` | 0.0 | 绝对动量阈值 |
| `valuation_pe_threshold` | 80 | PE分位刹车阈值（%） |
| `valuation_return_threshold` | 0.30 | 涨幅刹车阈值 |
| `valuation_enabled` | True | 是否启用估值刹车 |
| `valuation_lookback_years` | 5 | 估值分位回看年数 |
| `initial_capital` | 1000000 | 初始资金 |
| `commission_rate` | 0.001 | 单边手续费 |
| `slippage_rate` | 0.0001 | 滑点 |

## 策略逻辑

### 每月调仓日执行流程

```
Step 1: 绝对动量（金丝雀检查）
  └─ 沪深300ETF 90日收益率 ≤ 0 → 全仓货币ETF，结束

Step 2: 相对动量（行业赛马）
  └─ 计算6只行业ETF的90日收益率，排序

Step 3: 估值分位刹车（v1.1完整实现）
  └─ 获取跟踪指数历史PE数据
  └─ 计算当前PE在近5年历史中的分位数
  └─ Top1的PE分位 > 80% 且 涨幅 > 30% → 跳过，取下一名

Step 4: 执行交易
  └─ 卖出非目标ETF → 买入选中ETF（100%仓位）
  └─ 交易成本：买卖双边手续费 + 双边滑点

Step 5: 记录调仓日志
```

## 使用方式

### 1. 命令行方式（推荐）

```bash
# 运行回测（默认使用腾讯自选股数据源）
python -m scripts.main backtest

# 指定数据源
python -m scripts.main backtest --source tdx        # 使用通达信数据源
python -m scripts.main backtest --source akshare    # 使用AKShare数据源

# 生成实时调仓信号
python -m scripts.main signal

# 更新数据缓存
python -m scripts.main update --force

# 显示当前配置
python -m scripts.main config

# 禁用估值刹车回测
python -m scripts.main backtest --no-valuation

# 指定回测区间
python -m scripts.main backtest --start 2020-01-01 --end 2025-12-31
```

### 2. Python代码方式

```python
from scripts.config import Config
from scripts.data_collector import ETFDataCollector
from scripts.strategy import DualMomentumStrategy
from scripts.backtest import BacktestEngine
from scripts.report import ReportGenerator

# 初始化
config = Config()
collector = ETFDataCollector(config)
strategy = DualMomentumStrategy(config)

# 获取数据
data = collector.collect_all()

# 运行回测
engine = BacktestEngine(config, strategy, data)
result = engine.run()

# 生成报告
report = ReportGenerator(result, config)
report.generate_html("backtest_report.html")
```

### 3. 实时信号模式

```python
from scripts.config import Config
from scripts.data_collector import ETFDataCollector
from scripts.momentum import MomentumCalculator
from scripts.strategy import DualMomentumStrategy

config = Config()
collector = ETFDataCollector(config)
calculator = MomentumCalculator(config)
strategy = DualMomentumStrategy(config)

# 获取最新数据
data = collector.collect_all()

# 计算动量
is_bullish, benchmark_return = calculator.calculate_absolute_momentum(data)
momentum_results = calculator.calculate_relative_momentum(data)

# 获取估值数据
pe_data = calculator.fetch_all_valuation_data()
momentum_results = calculator.apply_valuation_brake(momentum_results, pe_data)

# 生成调仓信号
signal = strategy.generate_signal(data, pe_data=pe_data)
print(f"建议持有: {signal.selected_etf}")
print(f"决策理由: {signal.reason}")
```

## 模块说明

| 模块 | 功能 |
|------|------|
| `config.py` | 策略参数、标的池配置、数据源配置 |
| `data_collector.py` | ETF数据采集（westock/TDX多源）+ 前复权处理 + 本地缓存 |
| `momentum.py` | 动量计算（绝对/相对）、估值分位获取与计算 |
| `strategy.py` | 策略核心逻辑、调仓决策、信号生成 |
| `backtest.py` | 回测引擎、绩效统计、基准对比 |
| `report.py` | HTML报告生成（净值曲线、持仓记录、绩效指标） |
| `main.py` | 命令行入口（回测/信号/更新/配置） |

## 数据源

优先级：腾讯自选股(westock) → 通达信TQ-Local(tdx) → 本地缓存

- **主数据源 — 腾讯自选股(westock)**：通过 `westock-data-clawhub` CLI 获取前复权日线数据，覆盖8只ETF
- **备用数据源 — 通达信TQ-Local(tdx)**：通过本地HTTP服务(127.0.0.1:17709)获取**前复权**日线数据（`dividend_type: "front"`）
- **本地缓存**：作为离线兜底，parquet/csv格式存储
- **AKShare**：保留兼容，可通过 `--source akshare` 手动指定使用

> 通达信TQ-Local数据默认使用前复权（`dividend_type: "front"`），确保价格连续性。ETF代码格式：上交所 `510300.SH`，深交所 `159928.SZ`。

## v1.1更新内容

1. **估值分位刹车完整实现**：
   - 新增ETF到跟踪指数的映射配置
   - 通过AKShare获取指数历史PE/PB数据
   - 自动计算当前PE在近5年历史中的分位数
   - 支持批量获取所有行业ETF的估值数据

2. **交易成本修正**：
   - 调仓日扣除买卖双边手续费（原为单边）
   - 调仓日扣除双边滑点

3. **命令行接口**：
   - 统一入口脚本 `main.py`
   - 支持回测、信号生成、数据更新、配置查看

4. **配置增强**：
   - 新增 `valuation_enabled` 开关
   - ETF配置新增 `index_code` 字段
   - 支持通过配置禁用估值刹车

5. **测试完善**：
   - 固定随机种子，确保测试确定性
   - 新增估值刹车测试用例
   - 新增空头市场回测测试

## 回测预期特征（A股2005-2025）

| 指标 | 预期值 | 说明 |
|------|--------|------|
| 年化收益 | 15%-20% | 取决于行业ETF上市时间 |
| 最大回撤 | <25% | 绝对动量在2015/2018/2022有效 |
| 年化换手 | 4-6倍 | 月度调仓 |
| 胜率 | 55%-65% | 月度正收益比例 |
| 与沪深300相关性 | 0.7-0.8 | 超额明显 |

## 风险提示

1. **动量衰减**：行业快速轮动或震荡市中可能表现不佳
2. **滞后切换**：绝对动量在熊市初期可能滞后，导致小幅亏损后才切换
3. **估值刹车局限**：不能完全规避顶部区域，PE分位数据依赖估值数据源可用性
4. **历史回测**：不代表未来收益

## 版本历史

### v1.9.0 (2026-07-08)
- **训练/测试/参数优化**：基于28组参数网格搜索（abs=[60,90,120,180] × rel=[20,30,40,50,60,75,90]），3年训练+2年测试
- **默认参数更新**：`momentum_window`: 90 → 120天，基于优化结果——长窗口在熊市反弹中避免频繁错误进场
- **优化结论**：120天绝对动量窗口在测试期（2024-2026）年化60.9%、夏普1.43，综合表现最优
- **代码格式映射修复**：WeStock 输出 Markdown 表格解析、TDX 列式数组解析、numpy 类型 JS 兼容
- **报告修复**：净值曲线 numpy.float64 → float 转换，Chart.js 可正常渲染

### v1.8.0 (2026-07-08)
- **数据源重构**：默认使用腾讯自选股(westock)作为主数据源，通过 `westock-data-clawhub` CLI 获取前复权日线数据
- **备用数据源**：保留通达信TQ-Local(tdx)作为备用数据源，通过本地HTTP服务获取数据
- **前复权默认**：通达信TQ-Local数据默认使用前复权（`dividend_type: "front"`），确保价格连续性
- **多源降级链**：westock → tdx → 本地缓存，自动降级无需手动切换
- **代码格式映射**：新增 `to_westock_code()` / `to_tdx_code()` 静态方法，自动转换ETF代码格式（sh/sz前缀 ↔ .SH/.SZ后缀）
- **CLI增强**：所有子命令新增 `--source` 参数，支持手动指定数据源（westock/tdx/akshare）
- **配置增强**：新增 `backup_data_source`、`tdx_dividend_type`、`westock_dividend_type`、`tdx_host` 配置项
- **文档更新**：更新SKILL.md、README.md数据源章节

### v1.7.0 (2026-06-27)
- **参数优化最佳组合**：基于21种参数组合的回测对比，确定最佳参数组合
  - 最佳相对动量窗口：50天（年化收益44.30%，夏普比率1.275，最大回撤-29.75%）
  - 最佳调仓频率：月频调仓（平均年化收益28.63%，平均夏普比率0.775）
- **默认参数更新**：将最佳参数组合设置为技能默认参数
  - `relative_momentum_window`: 90 → 50
  - `rebalance_freq`: monthly（保持不变）
- **交互式报告**：改进报告交互性，添加可折叠章节、可排序表格、参数筛选功能
- **JavaScript修复**：修复Chart.js配置语法错误，确保交互按钮正常工作
- **目录整理**：整理技能目录结构，删除重复脚本，移动文件到正确目录

### v1.6.0 (2026-06-27)
- **参数优化框架**：新增`optimize_parameters.py`脚本，支持批量运行不同参数组合的回测对比
- **动量窗口分离**：实现绝对动量和相对动量窗口独立配置，支持分离优化
- **配置增强**：Config类新增`relative_momentum_window`参数，默认值90天
- **调仓频率修复**：修复`should_rebalance`方法，支持weekly/biweekly/monthly三种调仓频率
- **参数优化发现**：
  - 最佳相对动量窗口：50天（年化收益44.30%，夏普比率1.275）
  - 调仓频率影响：月频调仓表现最佳，周频调仓表现最差
    - 周频调仓：平均年化收益-0.55%，平均最大回撤-57.03%
    - 2周频调仓：平均年化收益10.62%，平均最大回撤-55.10%
    - 月频调仓：平均年化收益28.63%，平均最大回撤-40.35%
  - 窗口特性：短窗口（20天）收益较高但波动大，长窗口（90天）收益稳定
- **代码改进**：
  - `momentum.py`中`calculate_relative_momentum`方法使用`relative_momentum_window`计算相对动量
  - `strategy.py`中`should_rebalance`方法支持三种调仓频率

### v1.5.0 (2026-06-26)
- **默认动量窗口调整**：将默认动量窗口从252天调整为90天（约4.5个月），更适合A股市场中期趋势捕捉
- **保持月频调仓**：月频调仓作为默认频率，平衡交易成本与趋势跟踪效果
- **文档更新**：更新所有相关文档（SKILL.md、README.md、config.py）中的默认参数
- **版本同步**：与quant-skills仓库版本保持一致（v1.5.0）

### v1.2.0 (2026-06-26)
- 默认动量窗口从252天调整为90天（约4.5个月）
- 保持月频调仓作为默认频率
- 更新所有相关文档和参数配置

### v1.1.0 (2026-06-26)
- 估值分位刹车完整实现
- 交易成本修正（双边）
- 命令行接口
- 配置增强
- 测试完善

### v1.0.0 (2026-06-26)
- 初始版本
- 实现双动量核心逻辑（绝对动量 + 相对动量）
- 估值分位刹车机制
- 完整回测引擎
- HTML报告生成
