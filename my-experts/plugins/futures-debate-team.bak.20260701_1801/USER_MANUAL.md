# 期货交易辩论专家团 — 用户使用手册

## 1. 概述

期货交易辩论专家团是一个 **多Agent协作的期货分析系统**，通过9个专业Agent在6个阶段中串并行协作，对商品期货品种进行深度多空辩论分析，生成结构化HTML报告。

**核心理念**：不是让AI"替你做决定"，而是让AI"帮你把分析做透"——每个Agent从不同视角审视市场，最终由你（交易员）做决策。

**当前版本**：v2.5（2026-07-01）

**v2.5 核心升级**：
- `contracts/` Pydantic schema 版本化契约替换 `###END_XXX` 哨兵
- `DebateState` typed state 按需传参（Sparse MAD 原则，token 节省 ~40%）
- P3 交叉质询：牛→熊→牛v2（rebuttal, max=1），告别"双人独白"
- 混合 Supervisor/Handoff 模式：Phase边界由明鉴秋控，Phase内稳定路径 Agent 直跳
- `PhaseMeta` 可观测性 + `repair_phase` 容错
- 风控明结构化输入：rebuttal 质量审查 + 维度级裁决（include/watch/exclude）+ 4条红线
- `adapt_debate_results()` 向下兼容，新旧 debate_results.json 格式自动适配

## 2. 系统架构

```
                  ┌── 用户（交易员）
                  │
┌─────────────────▼──────────────────┐
│         明鉴秋（独立协调员）         │
│    调度、DebateState维护、报告汇总   │
└──────┬──────┬──────┬──────┬──────┘
       │      │      │      │
  ┌────▼─┐ ┌─▼───┐  │  ┌──▼────┐     ┌───────┐
  │数聚石│ │技研锋│  │  │牛势研 │     │闫判官 │
  │P1数据│ │P1信号│  │  │P3多头 │◄───►│P3b裁决 │
  │采集  │ │核验  │  │  │论点   │     │判断   │
  └──────┘ └──────┘  │  └───────┘     └───────┘
       │      │      │  ┌───────┐
       │      │      │  │熊谋略 │
       │      │      │  │P3空头 │
       │      │      │  │论点   │
       ▼      ▼      ▼  └───────┘
  ┌─────────────────────────┐
  │      链证源             │
  │  P2产业链验证 + 冗余检测 │
  └───────────┬─────────────┘
              ▼
  ┌─────────────────────────┐
  │      风控明             │
  │  P4风险评估 + rebuttal  │  ← 结构化bull/bear输入 + 维度级裁决
  │  有效性审查             │
  └───────────┬─────────────┘
              ▼
  ┌─────────────────────────┐
  │      策执远             │
  │  P5交易计划 + 仓位管理   │  ← 直接读 risk_obj.verdicts[]
  └───────────┬─────────────┘
              ▼
          HTML 分析报告 + debate_results.json
```

## 3. 完整目录结构

```
第一层：专家定义（绝对自包含）
my-experts/plugins/futures-debate-team/
├── .codebuddy-plugin/plugin.json   ← 唯一标识（name 和目录名不可改）
├── agents/                         ← 9个Agent定义
│   ├── futures-debate-team-team-lead.md   # 明鉴秋（主理人）
│   ├── futures-data-engineer.md           # 数聚石（P1）
│   ├── futures-trend-analyst.md           # 技研锋（P1）
│   ├── futures-chain-analyst.md           # 链证源（P2）
│   ├── futures-bull-researcher.md         # 牛势研（P3）
│   ├── futures-bear-researcher.md         # 熊谋略（P3）
│   ├── futures-judge.md                   # 闫判官（P3b）
│   ├── futures-risk-manager.md            # 风控明（P4）
│   └── futures-trading-strategist.md      # 策执远（P5）
├── avatars/*.png                 ← 9个头像
├── README.md                     ← 快速入门
├── USER_MANUAL.md                ← 本手册
└── settings.json                 ← 入口配置

第二层：编排+契约（可整体迁移）
skills/futures-trading-analysis/
├── SKILL.md                      ← 调度逻辑、铁律、裁决权重
├── contracts/                    ← 通信契约（Pydantic schema, 11个文件）
│   ├── __init__.py               ← 导出所有schema
│   ├── base.py                   ← PhaseMeta + BaseSkillOutput(version=2.0)
│   ├── data_collection.py        ← P1: DataCollectionOutput
│   ├── technical.py              ← P1: TechnicalOutput
│   ├── chain_analysis.py         ← P2: ChainAnalysisOutput
│   ├── debate.py                 ← P3: BullOutput / BearOutput
│   ├── judge.py                  ← P3b: JudgeOutput
│   ├── risk.py                   ← P4: RiskOutput
│   ├── trading_plan.py           ← P5: TradingPlanOutput
│   ├── migrations.py             ← 版本迁移函数
│   └── test_contracts.py         ← 13个测试
├── scripts/
│   ├── phase3_generate_report.py ← HTML报告生成（含adapt_debate_results适配器）
│   └── debate_feedback.py        ← 自进化反馈路由

第三层：子Skill（独立依赖，不内嵌）
skills/
├── debate-argument-builder/SKILL.md           ← 6维度分析+交叉质询
├── debate-risk-manager/SKILL.md               ← rebuttal审查+红线
├── debate-trading-planner/SKILL.md            ← 仓位分配+止损参数
├── debate-judge/SKILL.md                      ← 裁决权重铁律
├── futures-data-search/SKILL.md + 43脚本     ← 数据采集
├── commodity-trend-signal/SKILL.md + 16脚本  ← 信号计算
└── commodity-chain-analysis/SKILL.md + 9脚本  ← 产业链分析
```

## 4. Skill 依赖关系

```
futures-trading-analysis（主编排 — 引用contracts/中的schema）
  │
  ├── contracts/*.py              ← 接口契约（所有子skill间通信的Pydantic schema）
  │
  ├── futures-data-search         ← 数聚石的工作方法
  │     (MultiSourceAdapter: tdx_local → tqsdk → eastmoney → exchange_api → akshare)
  │
  ├── commodity-trend-signal      ← 技研锋的工作方法
  │     (L1-L4打分 + 趋势阶段检测 + 否决项检查)
  │
  ├── commodity-chain-analysis    ← 链证源的工作方法
  │     (产业链归类 + 期限结构 + 一致性验证)
  │
  ├── debate-argument-builder     ← 牛势研/熊谋略的工作方法
  │     (6维度论点构建 + 交叉质询 + 双轨输出)
  │
  ├── debate-judge                ← 闫判官的工作方法
  │     (多空证据权衡 + 裁决权重铁律)
  │
  ├── debate-risk-manager         ← 风控明的工作方法
  │     (rebuttal质量审查 + 维度级裁决 + 4条红线)
  │
  └── debate-trading-planner      ← 策执远的工作方法
      (仓位分配 + 入场/止损/目标 + 对冲方案)
```

**依赖方向**：主 skill 引用子 skill，子 skill 之间不互相引用。每个子 skill 独立维护自己的版本和工作方法。

**通信契约**：所有子 skill 通过 `contracts/` 目录下的 Pydantic schema 交换数据，每个输出带 `version` 字段，编排层 `parse_and_migrate()` 按版本号路由。版本迁移函数注册在 `migrations.py`。

## 5. 9 Agent 详细说明

### 5.1 数聚石 — 数据工程师 (P1)

| 项目 | 内容 |
|------|------|
| Agent ID | `futures-data-engineer` |
| 工作方法定义在 | `futures-data-search` → "辩论专家团数据采集接口" |
| 输入 | 品种列表 ["rb", "hc", "SA", ...] |
| 产出 schema | `DataCollectionOutput`（`contracts/data_collection.py`）— 含 contracts/key_prices/validation_status |
| 边界 | 只做采集和校验，不做分析 |

### 5.2 技研锋 — 信号分析师 (P1)

| 项目 | 内容 |
|------|------|
| Agent ID | `futures-trend-analyst` |
| 工作方法定义在 | `commodity-trend-signal` → "辩论专家团信号核验接口" |
| 输入 | 预计算L1-L4数据 + 各指标原始值 |
| 产出 schema | `TechnicalOutput`（`contracts/technical.py`）— 含 verdicts/trend_stages/veto_status |
| 边界 | 不做数据采集，不做产业链分析，不做交易计划 |

### 5.3 链证源 — 产业链验证 (P2)

| 项目 | 内容 |
|------|------|
| Agent ID | `futures-chain-analyst` |
| 工作方法定义在 | `commodity-chain-analysis` → "辩论专家团产业链验证接口" |
| 输入 | P1产出数据（data + tech） |
| 产出 schema | `ChainAnalysisOutput`（`contracts/chain_analysis.py`）— 含 metrics/inventory_level/basis_status |
| 边界 | 不做数据采集，不做信号分析 |

分析步骤：
1. 产业链归类 — `chains.get_chain_for_symbol(pid)`
2. 期限结构分析 — `term_basis.analyze_term_structure(pid)`
3. 产业链一致性验证 — `chain_verifier.chain_verification()`
4. Z分数极端性检查 — \|z\|>2标记极端值
5. **组合级产业链聚合** — 同链同方向→标记"同链冗余"

### 5.4 牛势研 — 多头研究员 (P3) ← 含交叉质询

| 项目 | 内容 |
|------|------|
| Agent ID | `futures-bull-researcher` |
| 工作方法定义在 | `debate-argument-builder`（bull角色）|
| 输入 | `state["data"].key_prices` + `state["tech"].trend_stages` + `state["chain"].chain_results` |
| 产出 schema | `BullOutput`（`contracts/debate.py`）— 含 dimensions[]/summary_4_risk/rebuttal_targets |
| 角色锚定 | 激进多头：怕踏空不怕回撤，对库存/基差零容忍 |
| 交叉质询 | 首轮出bull v1，读熊v1后出bull v2（rebuttal, max=1） |

### 5.5 熊谋略 — 空头研究员 (P3) ← 含交叉质询

| 项目 | 内容 |
|------|------|
| Agent ID | `futures-bear-researcher` |
| 工作方法定义在 | `debate-argument-builder`（bear角色）|
| 输入 | `state["data"].key_prices` + `state["tech"].trend_stages` + `state["chain"].chain_results` + bull v1论点 |
| 产出 schema | `BearOutput`（`contracts/debate.py`）— 含 dimensions[]/summary_4_risk |
| 角色锚定 | 风控空头：信库存/利润表不信叙事 |
| 非对称性 | 熊只产一次（bear v1），牛第2轮写rebuttal |

### 5.6 闫判官 — 辩论裁决官 (P3b)

| 项目 | 内容 |
|------|------|
| Agent ID | `futures-judge` |
| 工作方法定义在 | `debate-judge` |
| 输入 | `BullOutput` + `BearOutput` 结构化对象 |
| 产出 schema | `JudgeOutput`（`contracts/judge.py`）— 含 verdicts{}/overall_assessment |
| 边界 | 不做新分析，只基于已有论据裁决 |

### 5.7 风控明 — 风险管理总监 (P4) ← 结构化输入+红线

| 项目 | 内容 |
|------|------|
| Agent ID | `futures-risk-manager` |
| 工作方法定义在 | `debate-risk-manager` |
| 输入 | 结构化 `BullOutput` + `BearOutput` 对象（不是Markdown全文） |
| 产出 schema | `RiskOutput`（`contracts/risk.py`）— 含 verdicts[]/overlay |
| 红线 | ①禁止和稀泥（至少1个exclude）②rebuttal_quality不得全是"接住" ③每个verdict必须有reason ④overall.confidence ≤ 0.9 |

执行步骤：
1. **审查 Rebuttal 质量** — 检查牛v2是否真的接住了熊的质疑（接住/部分接住/糊弄）
2. **逐维度裁决** — include / watch / exclude
3. **综合判定** — 倾向 + 置信度 + 核心矛盾 + 建议仓位

### 5.8 策执远 — 交易策略师 (P5)

| 项目 | 内容 |
|------|------|
| Agent ID | `futures-trading-strategist` |
| 工作方法定义在 | `debate-trading-planner` |
| 输入 | 结构化 `RiskOutput.verdicts[]` + `RiskOutput.overall`（不是Markdown全文）|
| 产出 schema | `TradingPlanOutput`（`contracts/trading_plan.py`）— 含 actions[]/risk_reward_ratio |
| 约束 | 禁止祈使句命令操作，每品种2-3选项附利弊 |

仓位分配规则：
- 基于 `risk_obj.verdicts[].ruling`：include → 8-10%、watch → 4-5%、exclude → 0%
- 同一产业链总仓位 ≤ 10%
- 前3大品种 ≤ 30%
- 总仓位 ≤ 80%

## 6. 数据流（v2.5 typed state 版）

```
明鉴秋维护 DebateState，各 phase 产出写入对应字段，下游按需读取。

Phase 1 (并行):
  数聚石 → DataCollectionOutput → state["data"]
  技研锋 → TechnicalOutput → state["tech"]
  
Phase 2 (串行 — 只传 state["data"].key_prices + state["tech"].verdicts):
  链证源 → ChainAnalysisOutput → state["chain"]
  
Phase 3 (交叉质询 3跳):
  步1: 牛势研 → ArgumentOutput(bull v1) → state["bull"]
  步2: Handoff → 熊谋略读bull v1 → ArgumentOutput(bear v1) → state["bear"]
  步3: Handoff → 牛势研读bear v1 → ArgumentOutput(bull v2, rebuttal) → state["bull_v2"]
  终止条件: ≥3/5维度承认对方论点→提前结束
  
Phase 3b (串行 — 只传 summary_4_risk + dimensions):
  闫判官 → JudgeOutput → state["judge"]
  
Phase 4 (串行 — 结构化bull/bear对象，不是全文):
  风控明 → RiskOutput(含 verdicts[]/overall) → state["risk"]
  → Command(goto=策执远)
  
Phase 5 (串行 — 读 risk_obj.verdicts[] + risk_obj.overall):
  策执远 → TradingPlanOutput(含 actions[]) → state["plan"]

汇总:
  write debate_results.json（新旧双格式）→ phase3_generate_report.py → HTML报告
  debate_feedback.py inject → 自进化
```

## 7. 通信协议（契约化）

所有子 skill 间的数据交换通过 `contracts/` 目录中的 Pydantic schema 进行。

### 7.1 解析流程

```
Agent 产出正文 + ```json fence
        │
        ▼
extract_fence_json()  ← 从Markdown中扒 ```json...```
        │
        ▼
schema_cls.model_validate(data)  ← 按版本号路由
        │
        ▼
apply_migration()  ← 迁移到编排层期望的目标版本
        │
        ▼
写入 DebateState，下游按需访问
```

### 7.2 版本迁移

每个 schema 带 `version` 字段（当前 `"2.0"`）。升级到 `2.1` 时：

1. 创建 `XxxOutputV21` 子类（新增可选字段）
2. 注册迁移函数到 `MIGRATION_REGISTRY`（`migrations.py`）
3. 编排层 `parse_and_migrate()` 自动按版本路由

### 7.3 Feature Flag

```bash
# 环境变量控制新旧解析逻辑
USE_NEW_PARSE_LOGIC=true    # 默认，新逻辑
USE_NEW_PARSE_LOGIC=false   # 回退旧逻辑
```

## 8. 使用方式

### 8.1 定时模式（每天20:00自动运行）

由 `商品期货每日深度分析` 自动化任务触发。流程：
1. 召唤辩论专家团（mode=full_scan）
2. 数聚石全67品种采集 + 技研锋L1-L4信号筛选 → Top10进入辩论
3. P1→P2→P3(交叉质询)→P3b→P4→P5 六阶段辩论
4. 生成HTML报告 → 推送到微信

### 8.2 按需模式（手动召唤）

在WorkBuddy中输入触发词：
```
帮我分析品种 rb、FG、cs
召唤期货交易辩论专家团，mode=full_scan
```

### 8.3 修改某个Agent的工作方法

| 想改谁 | 改哪个文件 |
|--------|-----------|
| 数聚石的数据校验规则 | `futures-data-search/SKILL.md` → "辩论专家团数据采集接口" |
| 技研锋的否决条件 | `commodity-trend-signal/SKILL.md` → "辩论专家团信号核验接口" |
| 链证源的产业链归类 | `commodity-chain-analysis/SKILL.md` → "辩论专家团产业链验证接口" |
| 牛势研/熊谋略的论点框架 | `debate-argument-builder/SKILL.md` |
| 风控明的风控规则 | `debate-risk-manager/SKILL.md` |
| 策执远的仓位分配规则 | `debate-trading-planner/SKILL.md` |
| 辩论流程/阶段顺序/spawn协议 | `futures-trading-analysis/SKILL.md` |
| 通信契约（schema字段） | `futures-trading-analysis/contracts/*.py` |

## 9. 铁律

1. **决策辅助系统边界** — 禁止祈使句命令用户操作，禁止情绪化语言，多选项附利弊
2. **数据先行** — 所有数值必须通过 futures-data-search 获取真实数据
3. **流程不跳过** — 必须完整执行6阶段9专家，禁止协调器绕过Agent自行分析
4. **零Python模拟** — 辩论裁断必须用LLM推理+SendMessage完成，禁止Python dict拼接
5. **零捷径** — Agent spawn失败也要完整走完6阶段，降级标注 ⚠️辩论降级
6. **右侧交易** — 所有建议基于已确认右侧价格行为信号，无信号则HOLD
7. **裁决权重铁律** — 价格是唯一客观现实，期限结构权重上限15%
8. **组合级风控** — 同一产业链≤10%，强相关品种合并，前3大≤30%

## 10. 部署到新环境

三步部署：

```bash
# 1. 专家定义
cp -r ~/.workbuddy/plugins/marketplaces/my-experts/plugins/futures-debate-team {目标环境相同路径}

# 2. 编排+契约
cp -r ~/.workbuddy/skills/futures-trading-analysis {目标环境skills/}

# 3. 子skill
cp -r ~/.workbuddy/skills/debate-argument-builder {目标环境skills/}
cp -r ~/.workbuddy/skills/debate-risk-manager {目标环境skills/}
cp -r ~/.workbuddy/skills/debate-trading-planner {目标环境skills/}
cp -r ~/.workbuddy/skills/debate-judge {目标环境skills/}
cp -r ~/.workbuddy/skills/futures-data-search {目标环境skills/}
cp -r ~/.workbuddy/skills/commodity-trend-signal {目标环境skills/}
cp -r ~/.workbuddy/skills/commodity-chain-analysis {目标环境skills/}
```

依赖：Python 3.12+、`pydantic`、`pyyaml`。

## 11. 测试

完整性测试位于 `contracts/test_contracts.py`（13项验证）：

```bash
cd skills/futures-trading-analysis/contracts
python -m pytest test_contracts.py -v
```

涵盖：所有schema序列化/反序列化、版本迁移（v2.0 ↔ v2.1）、版本组合集成测试矩阵。

## 12. 扩展指南

### 12.1 新增一个Agent

1. 在 `futures-trading-analysis/SKILL.md` 的Agent表格中添加新行
2. 在 `执行流程` 中添加对应Phase
3. 在 `contracts/` 中创建对应schema
4. 创建或引用一个子skill定义其工作方法
5. 在 `agents/` 目录创建 agent .md 文件
6. 注册到 `plugin.json` 的 `members` 数组
7. 运行测试验证

### 12.2 升级schema版本

1. 在 `contracts/xxx.py` 中创建 `XxxOutputV21` 子类（新增可选字段）
2. 在 `contracts/migrations.py` 中添加迁移函数 + 注册到 `MIGRATION_REGISTRY`
3. 下游消费时用 `getattr(obj, 'new_field', None)` 安全获取新字段
4. 运行 `test_contracts.py` 验证版本组合兼容性
