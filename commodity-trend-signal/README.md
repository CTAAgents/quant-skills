# commodity-trend-signal v2.13

商品期货趋势信号发现系统 — L1-L4 四层打分架构 + 期货专属早期信号。

## 核心能力

- **L1-L4 四层打分**：L1 萌芽(40) + L2 量价(25) + L3 结构(25) + L4 确认(10) + 否决(-20)
- **时间衰减**：突破后走远的信号分数递减，避免追高
- **阈值阶梯化**：T1 观察(60-75) / T2 主仓(75-90) / T3 警惕(>90)
- **排序赛马制**：相对排名取 Top N，非绝对分数线
- **四阶段生命周期**：启动 → 主升 → 衰竭 → 反转
- **早期信号**：OI 三角、基差走强、期限结构、跨期 Spread 等期货专属

## 目录结构

```
commodity-trend-signal/
├── SKILL.md              # Agent 指令文件
├── README.md             # 本文件
├── requirements.txt      # Python 依赖
├── _user_meta.json       # WorkBuddy 元数据
├── .gitignore
├── scripts/
│   ├── config.py         # 全局配置（品种列表、阈值、参数）
│   ├── collect_data.py   # 数据采集（TqSdk/AKShare 降级链）
│   ├── indicators.py     # 技术指标计算（纯 pandas/numpy）
│   ├── scoring_system.py # L1-L4 四层打分引擎
│   ├── early_signal.py   # 期货专属早期信号检测
│   ├── signal_screener.py# 信号筛选 + 趋势阶段判定
│   ├── trade_plan.py     # 交易方案生成（止损/目标/仓位）
│   ├── report.py         # Markdown 报告生成
│   ├── generate_html_report.py # HTML 报告生成
│   └── run_pipeline.py   # 入口：一键运行完整管道
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_indicators.py
    ├── test_scoring_system.py
    ├── test_early_signal.py
    ├── test_screen.py
    ├── test_trade_plan.py
    └── test_report.py
```

## 快速使用

```bash
# 安装依赖
pip install numpy pandas

# 运行完整管道
cd ~/.workbuddy/skills/commodity-trend-signal
python -m scripts.run_pipeline --source auto --top-n 10

# 运行测试
python -m pytest tests/ -v
```

## 与 commodity-chain-analysis 配合

本 skill 负责**信号发现**（自下而上扫描），commodity-chain-analysis 负责**产业链验证**（自上而下确认）。两个 skill 独立部署，通过数据字典传递中间结果。

## 版本历史

- **v2.13.0** (2026-06-26): L1-L4 四层打分架构，期货专属信号(OI/基差/期限结构)，时间衰减，阈值阶梯化
- **v2.11.0** (2026-06-25): 从 futures-industry-chain-analysis 拆分为独立 skill
