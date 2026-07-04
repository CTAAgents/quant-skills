# 聚酯链投研分析技能 v1.0.0

## 简介

聚酯链投研分析技能是一个专业的期货分析工具，专注于PX/PTA/MEG/PF/PR五个品种的产业链分析。该技能以**主驱动识别**为核心引擎，通过三层漏斗诊断SOP、驱动归属判定表、盘面验证三步法等方法，提供完整的产业链分析、套利信号识别和交易建议。

## 核心特性

### 1. 主驱动识别（核心引擎）

- **三层漏斗诊断SOP**：
  - L1年度层：产能周期、海外新装置
  - L2季度层：检修季、调油逻辑、地缘
  - L3周度层：港口库存、装置临停、聚酯负荷

- **驱动归属判定表**：
  - PX：成本+检修+调油三选一
  - PTA：加工费+大厂检修兑现+出口
  - MEG：港口库存+煤制利润+进口
  - PF/PR：加工费+减产函+出口

- **盘面验证三步法**：
  1. 看领涨领跌顺序
  2. 看利润往哪头挤
  3. 看月差结构

### 2. 产业链分析

- **成本传导分析**：原油→石脑油→PX→PTA
- **供需平衡分析**：PX/PTA/MEG/PF/PR供需状态
- **库存周期分析**：累库/去库/平衡，Back/Contango切换
- **利润分配分析**：PXN/TA加工费/PF加工费/PR加工费

### 3. 套利信号识别

- **TA-EG价差套利**：芳烃vs烯烃错配
- **PF-TA加工差套利**：短纤无定价权，均值回归
- **TA月差套利**：近端检修去库vs远端新产能
- **多腿组合建议**：三腿组合（近月TA正套+远月空TA+多TA空PR）

### 4. 报告生成

- **主驱动诊断清单**：每日5分钟勾清单
- **完整分析报告**：产业链分析+四维分析+套利信号+头寸建议
- **套利信号报告**：TA-EG价差+PF-TA加工差+TA月差

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行完整流程

```bash
python scripts/run_pipeline.py
```

### 仅运行主驱动识别

```bash
python scripts/run_pipeline.py --driver-only
```

### 仅运行套利信号识别

```bash
python scripts/run_pipeline.py --arbitrage-only
```

### 生成完整报告

```bash
python scripts/run_pipeline.py --report
```

### 生成主驱动诊断清单

```bash
python scripts/run_pipeline.py --checklist
```

## 配置说明

配置文件位于 `config.yaml`，包含以下配置：

- **数据源配置**：交易所数据、专业API、WebSearch等
- **打分权重配置**：三层漏斗权重、驱动归属权重
- **阈值参数配置**：PXN、TA加工费、PF加工费等阈值
- **套利信号配置**：TA-EG价差、PF-TA加工差、TA月差参数
- **报告配置**：报告格式、类型、保存路径
- **自动化配置**：定时任务、时区
- **性能配置**：并行计算、缓存、超时
- **日志配置**：日志级别、格式、文件
- **测试配置**：单元测试、集成测试、性能测试

## 目录结构

```
polyester-chain-analysis/
├── SKILL.md                    # 技能描述文档
├── README.md                   # 快速开始指南
├── requirements.txt            # 依赖包
├── config.yaml                 # 配置文件
├── scripts/                    # 核心脚本目录
│   ├── run_pipeline.py         # 主运行脚本
│   ├── driver_identification.py # 主驱动识别模块
│   ├── chain_analysis.py       # 产业链分析模块
│   ├── arbitrage_signals.py    # 套利信号模块
│   └── report_generator.py     # 报告生成模块
├── tests/                      # 测试目录
│   ├── test_driver_identification.py
│   ├── test_chain_analysis.py
│   └── test_arbitrage_signals.py
├── references/                 # 参考文档
│   ├── FRAMEWORK.md            # 完整分析框架
│   ├── ARBITRAGE.md            # 套利策略详解
│   └── DRIVER_IDENTIFICATION.md # 主驱动识别SOP
├── data/                       # 数据目录
└── output/                     # 输出目录（报告）
```

## 测试

### 运行所有测试

```bash
pytest tests/ -v
```

### 运行特定测试

```bash
pytest tests/test_driver_identification.py -v
pytest tests/test_chain_analysis.py -v
pytest tests/test_arbitrage_signals.py -v
```

### 生成测试覆盖率报告

```bash
pytest tests/ --cov=scripts --cov-report=html
```

## 自动化运行

支持配置每日定时任务：

- **早盘分析**（08:00）：生成每日分析报告
- **收盘更新**（20:00）：更新套利信号和头寸建议

## 质量保证

### 硬规则满足率100%

- 主驱动识别三层漏斗必须完整执行
- 驱动归属判定表必须覆盖所有品种
- 盘面验证三步法必须交叉验证
- 套利信号必须满足进出场条件
- 交易建议必须包含止损和仓位控制

### 金融逻辑正确率>95%

- 成本传导逻辑：原油→石脑油→PX→PTA
- 供需平衡逻辑：检修>产能>新装置
- 库存周期逻辑：Back/Contango切换
- 套利逻辑：均值回归+行为博弈

### 幻觉率<3%

- 所有数据必须有来源标注
- 所有判断必须有依据支撑
- 所有建议必须有风险提示
- 不确定信息必须标注"数据暂缺"

## 注意事项

### 数据质量

- 基本面数据可能存在延迟，需要建立数据质量监控
- WebSearch获取的数据需要交叉验证
- 异常数据需要标记或剔除

### 风险控制

- 所有交易建议必须包含止损位
- 多腿组合必须计算净敞口
- 油价单边走时需要补原油对冲
- 流动性差的品种注意滑点

### 持续优化

- 每季度review一次skill逻辑
- 根据市场变化调整打分权重和阈值
- 定期更新产业链逻辑和品种特性

## 版本历史

### v1.0.0 (2026-06-26)
- 初始版本
- 实现主驱动识别模块（三层漏斗+驱动归属判定表+盘面验证三步法）
- 实现产业链分析模块（成本传导+供需平衡）
- 实现套利信号模块（TA-EG价差+PF-TA加工差+TA月差）
- 实现交易建议模块（单腿+多腿组合）
- 实现报告生成模块（主驱动诊断清单+完整分析报告）
- 支持多源数据获取和自动化运行
- 50+测试用例覆盖

## 依赖

### Python包

- pandas>=1.5.0
- numpy>=1.21.0
- duckdb>=0.8.0
- pyyaml>=6.0
- requests>=2.28.0

### 外部技能

- commodity-trend-signal（技术指标计算）
- exchange-futures-data（交易所数据获取）

## 许可证

MIT License

## 联系方式

- 作者：谭溯源（掌柜）
- 邮箱：tansuyuan@example.com
- 项目地址：https://github.com/CTAAgents/quant-skills
