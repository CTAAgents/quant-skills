# Futures Debate Team — 期货交易辩论专家团 v2.0

## 类型

Team 型（7角色多角色协作团队）

## 架构

5阶段串并行管道，1名独立协调员调度7位专业Agent：

```
用户
  ↓
明鉴秋（独立协调员）→ 读取数据 → spawn各Agent
  ↓
Phase 1 (并行) → 数聚石 + 技研锋
  ↓
Phase 2 (串行) → 链证源
  ↓
Phase 3 (并行) → 牛势研 + 熊谋略
  ↓
Phase 4 (串行) → 风控明
  ↓
Phase 5 (串行) → 策执远
  ↓
明鉴秋汇总 → HTML报告 → 交付用户
```

## 核心设计原则（v2.0）

```
修改Agent工作方法 → 只改对应skill
修改辩论流程     → 只改主SKILL.md（角色+编排+边界）
```

各Agent的工作方法定义在对应的skill中，主skill不内嵌实现细节。

| Agent | Phase | 工作方法定义在 | 修改方式 |
|-------|:-----:|---------------|---------|
| 数聚石 | P1 | `futures-data-search` | 改该skill的"辩论专家团数据采集接口" |
| 技研锋 | P1 | `commodity-trend-signal` | 改该skill的"辩论专家团信号核验接口" |
| 链证源 | P2 | `commodity-chain-analysis` | 改该skill的"辩论专家团产业链验证接口" |
| 牛势研 | P3 | `debate-argument-builder` | 直接改该skill |
| 熊谋略 | P3 | `debate-argument-builder` | 直接改该skill |
| 风控明 | P4 | `debate-risk-manager` | 直接改该skill |
| 策执远 | P5 | `debate-trading-planner` | 直接改该skill |

## Skill 依赖关系

```
futures-trading-analysis（主编排）
  ├── futures-data-search         ← 数聚石
  ├── commodity-trend-signal      ← 技研锋
  ├── commodity-chain-analysis    ← 链证源
  ├── debate-argument-builder     ← 牛势研/熊谋略
  ├── debate-risk-manager         ← 风控明
  └── debate-trading-planner      ← 策执远
```

依赖方向：主skill引用子skill，子skill之间不互相引用。

## 团队成员

| 角色 | Agent ID | 职责 | 对应skill |
|------|----------|------|-----------|
| 协调员 | `futures-debate-team-team-lead` | 调度、数据中转、报告汇总 | futures-trading-analysis |
| 数据工程师 | `futures-data-engineer` | 数据采集与校验 | futures-data-search |
| 信号分析师 | `futures-trend-analyst` | L1-L4打分、趋势阶段、否决检查 | commodity-trend-signal |
| 产业链验证 | `futures-chain-analyst` | 产业链归类、期限结构、组合级冗余检测 | commodity-chain-analysis |
| 多头研究员 | `futures-bull-researcher` | 多头论点构建 | debate-argument-builder |
| 空头研究员 | `futures-bear-researcher` | 空头论点构建 | debate-argument-builder |
| 风险管理 | `futures-risk-manager` | 三方评估、铁律检查、组合级风险、JSON交接 | debate-risk-manager |
| 交易策略 | `futures-trading-strategist` | 入场/止损/目标/仓位/对冲 | debate-trading-planner |

## Skill 复用性

辩论专家团依赖的6个子skill全部支持**独立使用**，可在其他项目或专家团中复用：

| Skill | 复用性 | 独立用途 | 接口位置 |
|-------|:------:|---------|---------|
| `futures-data-search` | ✅ **完全独立** | 任何需要期货数据查询的项目 | SKILL.md全文 |
| `commodity-trend-signal` | ✅ **完全独立** | 全品种信号扫描、趋势阶段识别 | CLI: `scan_all.py` |
| `commodity-chain-analysis` | ✅ **完全独立** | 产业链归类、期限结构分析 | scripts/chains.py |
| `debate-argument-builder` | ✅ **通用接口** | 任意品种的5维度多空论点分析 | "独立使用模式"章节 |
| `debate-risk-manager` | ✅ **通用接口** | 任意交易想法的风险评估+集中度检查 | "独立使用模式"章节 |
| `debate-trading-planner` | ✅ **通用接口** | 任意裁定结果的交易方案生成 | "独立使用模式"章节 |

**复用方式**：LLM Agent加载对应skill的SKILL.md后，按"独立使用模式"章节传入自定义输入即可。
不依赖辩论专家团的任何特定数据格式。

## 数据流

```
P1: 数聚石 → ###END_DATA_COLLECTION（结构化JSON，含校验状态）
    + 技研锋 → ###END_TECH_ANALYSIS（趋势阶段+否决状态+关键价位）
P2: 链证源 → ###END_CHAIN_ANALYSIS（产业链+期限+冗余标记）
P3: 牛势研 → ###END_BULL_ARGUMENT（5维度多头论点）
    + 熊谋略 → ###END_BEAR_ARGUMENT（5维度空头论点）
P4: 风控明 → ###END_RISK_ASSESSMENT（JSON交接: excluded/watch/chain_limits/verdicts）
P5: 策执远 → ###END_TRADING_PLAN（仓位分配+入场方案+止损目标+对冲建议）
```

## 数据源

所有国内期货数据统一由 `futures-data-search` 的 MultiSourceAdapter 调度。

优先级：tdx_local(0) → tqsdk(1) → eastmoney(2) → exchange_api(3) → akshare(4) → websearch(5) → cache(6)

## 安装

```bash
# 将专家包放到以下路径
cp -r futures-debate-team/ ~/.workbuddy/plugins/marketplaces/my-experts/plugins/
# 刷新即可使用
```

## 打包分享

```bash
cd ~/.workbuddy/plugins/marketplaces/my-experts/plugins/
zip -r futures-debate-team.zip futures-debate-team/
```

## 变更日志

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.0 | 2026-07-01 | 架构解耦 — 各Agent工作方法剥离至对应skill，主skill只保留角色+编排+边界 |
| v1.3 | 2026-06-30 | 架构重构 — 明鉴秋独立协调员 + 7专家（废弃12Agent旧架构） |
| v1.2 | 2026-06-29 | 移除WH6数据源 |
| v1.0 | 2026-06-25 | 初始版本 |
