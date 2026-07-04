# precious-metals-trading-decision

贵金属交易决策分析辅助系统

## 版本

v2.6.0

## 目录结构

```
precious-metals-trading-decision/
├── SKILL.md                    # 主skill文件
├── README.md                   # 本文件
├── scripts/                    # 脚本目录
│   ├── strategy-combination.py # 策略组合优化模块
│   ├── ml-integration.py       # 机器学习集成模块
│   ├── backtesting-framework.py# 回测框架模块
│   ├── dynamic-params.py       # 动态参数调整模块
│   ├── test-cases-generator-v2.py # 测试用例生成器
│   └── real-trading-validator-v2.py # 验证脚本
├── tests/                      # 测试目录
│   └── test-cases-v2.json      # 测试用例
└── references/                 # 参考文档目录
```

## 模块说明

### 1. 策略组合优化模块 (strategy-combination.py)
- 均值-方差优化（Markowitz模型）
- 夏普比率最大化
- 分散化收益分析
- 13种策略的相关性分析

### 2. 机器学习集成模块 (ml-integration.py)
- 决策树分类器
- 特征工程（28个特征）
- Regime诊断模型
- 策略匹配模型

### 3. 回测框架模块 (backtesting-framework.py)
- 交易执行和记录
- 风险指标计算（夏普比率、索提诺比率、卡尔玛比率、最大回撤）
- 回测报告生成

### 4. 动态参数调整模块 (dynamic-params.py)
- 基于90天滚动窗口的分位数计算
- 根据市场状态动态调整阈值
- 动态仓位乘数和止损乘数调整

### 5. 测试用例生成器 (test-cases-generator-v2.py)
- 生成32个历史行情场景测试用例
- 覆盖所有Regime类型（R1-R5）
- 覆盖所有策略类型（13种）

### 6. 验证脚本 (real-trading-validator-v2.py)
- 验证Regime诊断逻辑
- 验证策略匹配准确性
- 验证仓位计算正确性
- 验证止损/止盈逻辑

## 使用方法

### 1. 运行测试用例生成器
```bash
python scripts/test-cases-generator-v2.py
```

### 2. 运行验证脚本
```bash
python scripts/real-trading-validator-v2.py
```

### 3. 运行策略组合优化
```bash
python scripts/strategy-combination.py
```

### 4. 运行机器学习集成
```bash
python scripts/ml-integration.py
```

### 5. 运行回测框架
```bash
python scripts/backtesting-framework.py
```

### 6. 运行动态参数调整
```bash
python scripts/dynamic-params.py
```

## 核心功能

### 1. 三层架构
- 宏观决策层（Level 1）：判定市场机制（Regime）与主方向
- 载体选择层（Level 2）：针对同一方向选出最优表达工具
- 多周期执行层（Level 3）：入场、止损、仓位管理的精细化

### 2. Regime诊断
- R1：降息/衰退式多头
- R2：高利率震荡（横盘）
- R3：鹰派重定价（加息/更高-for-longer）
- R4：信用折价/去美元化溢价
- R5：流动性危机清算模式

### 3. 策略库
- 宏观利率波段策略
- 央行抄底长线多头策略
- 金银比均值回归套利策略
- 均线顺势波段策略
- 区间震荡高抛低吸策略
- 突破追单策略
- 事件驱动避险短线策略
- 逆势抄底/摸顶策略
- 跨品种套利策略（金铂比）
- 季节性策略（央行购金周期）
- 技术形态策略（头肩顶底）
- 波动率交易策略（GVX/VXSLV均值回归）
- 资金流向策略（CFTC持仓极值反转）

### 4. 动态参数调整
- GVX/VXSLV阈值动态调整
- 仓位乘数动态调整
- 止损乘数动态调整

### 5. 机器学习集成
- Regime诊断模型
- 策略匹配模型
- 特征工程

### 6. 回测框架
- 交易执行和记录
- 风险指标计算
- 回测报告生成

## 依赖

- Python 3.8+
- NumPy
- JSON

## 许可证

内部使用，不对外公开。
