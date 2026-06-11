# Futures Industry Framework

期货产业链+基本面+技术面一体化交易决策框架

## 概述

本框架是一个完整的期货分析系统，通过「产业链定方向、基本面定强弱、技术面定时机」的三层分析逻辑，结合标准化指标体系、客观化权重配置和清晰化共振信号，为期货交易提供决策支持。

## 版本信息

- **版本**: 2.0.0
- **更新日期**: 2026-05-31

## 目录结构

```
futures-industry-framework/
├── SKILL.md                          # 技能文档（主要文档）
├── README.md                         # 本文件
├── requirements.txt                  # Python依赖包
├── __init__.py                       # 模块初始化
├── industry_chain_standardization.py # 产业链标准化模块
├── weight_optimization.py            # 权重优化模块
├── resonance_detection.py            # 共振检测模块
├── integrated_analyzer.py            # 集成分析引擎
├── examples/                         # 示例代码
│   ├── __init__.py
│   ├── quick_start.py               # 快速入门示例
│   └── weight_optimization_demo.py  # 权重优化示例
└── tests/                           # 测试代码
    ├── __init__.py
    └── test_integration.py          # 集成测试
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 简单使用

```python
from futures_industry_framework import quick_analyze, create_sample_data

# 创建示例数据
chain_metrics, fund_metrics, tech_metrics = create_sample_data()

# 执行分析
report = quick_analyze(chain_metrics, fund_metrics, tech_metrics, "黑色建材产业链")

# 打印报告
print(report)
```

### 3. 使用集成分析器

```python
from futures_industry_framework import IntegratedAnalyzer

# 创建分析器
analyzer = IntegratedAnalyzer()

# 执行分析
result = analyzer.analyze(chain_metrics, fund_metrics, tech_metrics, "能化产业链")

# 生成报告
print(analyzer.generate_report(result))
```

## 核心模块

### 1. 产业链标准化模块

通过量化指标体系替代主观判断：
- 库存周期四阶段自动判定
- 利润结构量化分析
- 产业链综合评分计算

### 2. 权重优化模块

通过历史回测确定最优权重：
- 基于夏普比率的权重优化
- 网格搜索权重探索
- 权重保存与加载

### 3. 共振检测模块

通过量化规则消除模糊地带：
- 三层共振等级判定
- 信号方向判定
- 多时间周期共振检测

### 4. 集成分析引擎

一站式整合所有模块，自动生成交易计划和风险提示。

## 运行示例

```bash
# 快速入门示例
python examples/quick_start.py

# 权重优化示例
python examples/weight_optimization_demo.py
```

## 运行测试

```bash
python -m pytest tests/test_integration.py -v
```

或使用unittest：

```bash
python -m unittest tests.test_integration
```

## 数据格式说明

### 产业链指标

```python
from futures_industry_framework import IndustryChainMetrics

chain_metrics = IndustryChainMetrics(
    inventory_change_rate=-0.03,
    inventory_history_percentile=0.35,
    price_change_rate=0.02,
    upstream_profit_margin=0.12,
    midstream_profit_margin=0.08,
    downstream_profit_margin=0.05,
    operating_rate=0.78,
    supply_demand_gap=0.03,
    basis=-30,
    basis_history_percentile=0.25,
    # ... 其他参数
)
```

### 基本面指标

```python
from futures_industry_framework import FundamentalMetrics

fundamental_metrics = FundamentalMetrics(
    supply_demand_gap=0.15,
    inventory_change=-0.03,
    profit_margin=0.12,
    basis_structure=-0.2,
    historical_price_percentile=0.35
)
```

### 技术面指标

```python
from futures_industry_framework import TechnicalMetrics

technical_metrics = TechnicalMetrics(
    trend_score=65,
    momentum_score=58,
    volatility_score=45,
    volume_score=60,
    pattern_score=55
)
```

## 依赖包

- pandas >= 1.5.0
- numpy >= 1.21.0
- scipy >= 1.7.0

## 许可证

本框架仅供学习和研究使用。

## 作者

Futures Analysis Team
