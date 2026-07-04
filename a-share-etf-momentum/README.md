# A股ETF双动量轮动策略 v1.7

## 概述

本skill实现了经典的双动量（Dual Momentum）策略，专为A股市场ETF轮动设计。

**核心逻辑**：
1. **绝对动量**（金丝雀）：沪深300ETF 90日收益率 > 0 → 允许持有行业ETF
2. **相对动量**（赛马）：选取50日收益率最高的行业ETF（参数优化最佳窗口）
3. **估值刹车**：PE分位 > 80% 且涨幅 > 30% → 跳过过热标的
4. **调仓频率**：月频调仓（参数优化最佳频率）

## 快速开始

### 安装依赖

```bash
pip install akshare pandas numpy pyarrow pytest
```

### 命令行使用（推荐）

```bash
# 运行回测
python -m scripts.main backtest

# 生成实时调仓信号
python -m scripts.main signal

# 更新数据缓存
python -m scripts.main update

# 显示当前配置
python -m scripts.main config

# 禁用估值刹车回测
python -m scripts.main backtest --no-valuation

# 指定回测区间
python -m scripts.main backtest --start 2020-01-01 --end 2025-12-31
```

### Python代码使用

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

## 标的池

| 类别 | ETF名称 | 代码 | 跟踪指数 |
|------|---------|------|----------|
| 基准 | 沪深300ETF | 510300 | 000300 |
| 行业 | 有色金属ETF | 512400 | 399395 |
| 行业 | 银行ETF | 510650 | 000951 |
| 行业 | 高端制造ETF | 516860 | 399808 |
| 行业 | 消费ETF | 159928 | 000932 |
| 行业 | 医药ETF | 512010 | 000933 |
| 行业 | 科技ETF | 515000 | 931087 |
| 防御 | 银华日利 | 511880 | - |

## 参数配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `momentum_window` | 90 | 动量窗口（交易日） |
| `top_n` | 1 | 相对动量选取数量 |
| `abs_momentum_threshold` | 0.0 | 绝对动量阈值 |
| `valuation_pe_threshold` | 80 | PE分位刹车阈值（%） |
| `valuation_return_threshold` | 0.30 | 涨幅刹车阈值 |
| `valuation_enabled` | True | 是否启用估值刹车 |
| `initial_capital` | 1000000 | 初始资金 |
| `commission_rate` | 0.001 | 单边手续费 |
| `slippage_rate` | 0.0001 | 滑点 |

## 模块说明

- `config.py`: 策略参数配置、ETF到指数映射
- `data_collector.py`: ETF数据采集（AKShare）+ 本地缓存
- `momentum.py`: 动量计算、估值分位获取与计算
- `strategy.py`: 策略核心逻辑
- `backtest.py`: 回测引擎
- `report.py`: HTML报告生成
- `main.py`: 命令行入口

## 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试类
pytest tests/test_strategy.py::TestConfig -v

# 运行并显示覆盖率
pytest tests/ -v --cov=scripts
```

## 预期绩效（A股历史）

- 年化收益: 15%-20%
- 最大回撤: <25%
- 月度胜率: 55%-65%
- 年化换手: 4-6倍

## 风险提示

1. 动量策略在行业快速轮动或震荡市中可能表现不佳
2. 绝对动量过滤在熊市初期可能滞后
3. 估值刹车不能完全规避顶部区域
4. 回测结果不代表未来收益

## 版本历史

### v1.5.0 (2026-06-26)
- **默认动量窗口调整**：将默认动量窗口从252天调整为90天（约4.5个月），更适合A股市场中期趋势捕捉
- **保持月频调仓**：月频调仓作为默认频率，平衡交易成本与趋势跟踪效果
- **文档更新**：更新所有相关文档中的默认参数
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
- 双动量核心逻辑
- 估值分位刹车
- 完整回测引擎
- HTML报告生成
