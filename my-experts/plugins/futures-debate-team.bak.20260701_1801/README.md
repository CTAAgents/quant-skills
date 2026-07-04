# Futures Debate Team — 期货交易辩论专家团 v2.5

## 类型

Team 型（9角色多角色协作团队）

## 架构

6阶段串并行管道（P1→P2→P3→P3b→P4→P5），1名独立协调员调度8位专业Agent + 1位独立裁决官。

```
用户
  ↓
明鉴秋（独立协调员）→ 读取数据 → spawn各Agent（Phase边界Supervisor，Phase内Handoff）
  ↓
Phase 1 (并行) → 数聚石 + 技研锋
  ↓
Phase 2 (串行) → 链证源
  ↓
Phase 3 (交叉质询3跳) → 牛v1 → 熊v1 → 牛v2(rebuttal)
  ↓
Phase 3b (串行) → 闫判官（裁决）
  ↓
Phase 4 (串行) → 风控明（含rebuttal质量审查）
  ↓
Phase 5 (串行) → 策执远
  ↓
明鉴秋汇总 → HTML报告 → 交付用户
```

## 核心设计原则（v2.5）

```
修改Agent工作方法   → 只改对应skill
修改辩论流程        → 只改主SKILL.md（角色+编排+边界）
修改通信契约        → 只改contracts/*.py
```

所有子 skill 间的数据交换通过 `contracts/` Pydantic schema 进行，每个输出带 `version` 字段，编排层自动按版本路由。

| Agent | Phase | 工作方法定义在 | 产出 schema |
|-------|:-----:|---------------|-------------|
| 数聚石 | P1 | `futures-data-search` | `DataCollectionOutput` |
| 技研锋 | P1 | `commodity-trend-signal` | `TechnicalOutput` |
| 链证源 | P2 | `commodity-chain-analysis` | `ChainAnalysisOutput` |
| 牛势研 | P3 | `debate-argument-builder`（bull）| `BullOutput` |
| 熊谋略 | P3 | `debate-argument-builder`（bear）| `BearOutput` |
| 闫判官 | P3b | `debate-judge` | `JudgeOutput` |
| 风控明 | P4 | `debate-risk-manager` | `RiskOutput` |
| 策执远 | P5 | `debate-trading-planner` | `TradingPlanOutput` |

## 通信契约

契约定义在 `futures-trading-analysis/contracts/` 目录，包含 9 个 Pydantic schema + 版本迁移函数 + 13 个测试：

```
contracts/
├── base.py              # PhaseMeta + BaseSkillOutput(version=2.0)
├── data_collection.py   # P1
├── technical.py         # P1
├── chain_analysis.py    # P2
├── debate.py            # P3（含 DimensionItem + RebuttalTargets）
├── judge.py             # P3b
├── risk.py              # P4（含 VerdictItem + 4条红线）
├── trading_plan.py      # P5
├── migrations.py        # 版本迁移 + MIGRATION_REGISTRY
└── test_contracts.py    # 13个测试
```

## Sub-Skill 复用性

| Skill | 独立用途 |
|-------|---------|
| `debate-argument-builder` | 任意品种的多空论点分析 |
| `debate-risk-manager` | 任意交易想法的风险评估 |
| `debate-trading-planner` | 任意裁定结果的交易方案 |
| `debate-judge` | 多空辩论裁决 |
| `futures-data-search` | 期货行情数据采集 |
| `commodity-trend-signal` | 全品种信号扫描 |
| `commodity-chain-analysis` | 产业链分析 |

## 数据流（v2.5 typed state）

```
Agent 产出 = [正文(Markdown)] + [```json fence(结构化)] 
              → extract_fence_json()
              → schema_cls.model_validate()
              → apply_migration(target_version)
              → DebateState
              → 下游按需读取（不传全文，只传需要的子字段）
```

## 安装

```bash
# 1. 专家定义
cp -r futures-debate-team/ ~/.workbuddy/plugins/marketplaces/my-experts/plugins/

# 2. 编排+契约
cp -r skills/futures-trading-analysis/ ~/.workbuddy/skills/

# 3. 子skill
for s in debate-argument-builder debate-risk-manager debate-trading-planner debate-judge \
         futures-data-search commodity-trend-signal commodity-chain-analysis; do
  cp -r skills/$s/ ~/.workbuddy/skills/
done
```

依赖：Python 3.12+、`pydantic`、`pyyaml`。

## 变更日志

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.5 | 2026-07-01 | contracts/ Pydantic契约 + P3交叉质询 + 混合Supervisor/Handoff + PhaseMeta可观测 + 风控明结构化输入+红线 |
| v2.4 | 2026-06-30 | 新增裁决权重铁律 + 闫判官P3b裁决 + 各Agent基本面搜索能力 |
| v2.3 | 2026-06-30 | 闫判官裁决者角色 |
| v2.2 | 2026-06-30 | 基本面搜索 + 同链冗余相关性驱动 |
| v2.1 | 2026-06-30 | full_scan/custom 双模式 |
| v2.0 | 2026-07-01 | 架构解耦 — 各Agent工作方法剥离至对应skill |
| v1.3 | 2026-06-30 | 明鉴秋独立协调员 + 7专家 |
