# 期货交易辩论专家团 — 用户使用手册

## 1. 概述

期货交易辩论专家团是一个 **多Agent协作的期货分析系统**，通过7个专业Agent在5个阶段中串并行协作，对商品期货品种进行深度多空辩论分析，生成结构化HTML报告。

**核心理念**：不是让AI"替你做决定"，而是让AI"帮你把分析做透"——每个Agent从不同视角审视市场，最终由你（交易员）做决策。

## 2. 系统架构

```
                  ┌── 用户（交易员）
                  │
┌─────────────────▼──────────────────┐
│         明鉴秋（独立协调员）         │
│     调度、数据中转、报告汇总        │
└──────┬──────┬──────┬──────┬──────┘
       │      │      │      │
  ┌────▼─┐ ┌─▼───┐  │  ┌──▼────┐
  │数聚石│ │技研锋│  │  │牛势研 │
  │数据  │ │信号  │  │  │多头   │
  │采集  │ │核验  │  │  │论点   │
  └──────┘ └──────┘  │  └───────┘
       │      │      │  ┌───────┐
       │      │      │  │熊谋略 │
       │      │      │  │空头   │
       │      │      │  │论点   │
       │      │      │  └───────┘
       ▼      ▼      ▼
  ┌─────────────────────────┐
  │      链证源             │
  │  产业链验证 + 冗余检测  │
  └───────────┬─────────────┘
              ▼
  ┌─────────────────────────┐
  │      风控明             │
  │  风险评估 + 集中度检查  │  ← 产出JSON交接数据
  └───────────┬─────────────┘
              ▼
  ┌─────────────────────────┐
  │      策执远             │
  │  交易计划 + 仓位管理    │
  └───────────┬─────────────┘
              ▼
         HTML 分析报告
```

## 3. Skill 依赖关系

```
futures-trading-analysis（主编排 — 角色+边界+流程）
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
  │     (5维度多空论点构建 + 风险标注)
  │
  ├── debate-risk-manager         ← 风控明的工作方法
  │     (三方评估 + 铁律检查 + 组合级检查 + JSON交接)
  │
  └── debate-trading-planner      ← 策执远的工作方法
      (仓位分配 + 入场/止损/目标 + 对冲方案)
```

**依赖方向**：主skill引用子skill，子skill之间不互相引用。每个子skill独立维护自己的版本和工作方法。

## 4. 7 Agent 详细说明

### 4.1 数聚石 — 数据工程师 (P1)

| 项目 | 内容 |
|------|------|
| 工作方法定义在 | `futures-data-search` → "辩论专家团数据采集接口" |
| 输入 | 品种列表 ["rb", "hc", "SA", ...] |
| 输出 | 结构化JSON（含价格、期限结构、Z分数、数据质量状态） |
| 产出标记 | `###END_DATA_COLLECTION` |
| 边界 | 只做采集和校验，不做分析 |

调用接口示例：
- `MultiSourceAdapter.get_quote(pid)` — 实时报价
- `MultiSourceAdapter.get_kline(pid, days=200)` — 日线K线
- `MultiSourceAdapter.get_term_structure(pid)` — 期限结构

### 4.2 技研锋 — 信号分析师 (P1)

| 项目 | 内容 |
|------|------|
| 工作方法定义在 | `commodity-trend-signal` → "辩论专家团信号核验接口" |
| 输入 | 预计算L1-L4数据 + 各指标原始值 |
| 输出 | 裁决方向 + 趋势阶段 + 置信度 + 否决状态 |
| 产出标记 | `###END_TECH_ANALYSIS` |
| 边界 | 不做数据采集，不做产业链分析，不做交易计划 |

核验步骤：
1. 得分评估 — 审查L1-L4各维度，标注异常
2. 趋势阶段判断 — 启动/主升/主跌/衰竭/反转
3. 否决项检查 — ADX<15→震荡、RSI极端、OI背离
4. 关键价位标注 — 支撑/阻力/止损参考

### 4.3 链证源 — 产业链验证 (P2)

| 项目 | 内容 |
|------|------|
| 工作方法定义在 | `commodity-chain-analysis` → "辩论专家团产业链验证接口" |
| 输入 | P1产出数据（数据 + 信号） |
| 输出 | 产业链归属 + 期限结构 + 一致性评分 + 冗余状态 |
| 产出标记 | `###END_CHAIN_ANALYSIS` |
| 边界 | 不做数据采集，不做信号分析 |

分析步骤：
1. 产业链归类 — `chains.get_chain_for_symbol(pid)`
2. 期限结构分析 — `term_basis.analyze_term_structure(pid)`
3. 产业链一致性验证 — `chain_verifier.chain_verification()`
4. Z分数极端性检查 — |z|>2标记极端值
5. **组合级产业链聚合** — 同链同方向→标记"同链冗余"

### 4.4 牛势研 — 多头研究员 (P3)

| 项目 | 内容 |
|------|------|
| 工作方法定义在 | `debate-argument-builder` |
| 输入 | P1+P2全部结构化数据 |
| 输出 | 5维度多头论点 + 风险标注 |
| 产出标记 | `###END_BULL_ARGUMENT` |
| 边界 | 纯定性分析，不做数据计算 |

5维度分析框架：
1. 趋势结构 — 做多右侧信号
2. 量价关系 — OI增+价涨
3. 期限结构 — Back→做多有利
4. 产业链验证 — 方向一致
5. 风险点 — 至少列出2个

### 4.5 熊谋略 — 空头研究员 (P3)

| 项目 | 内容 |
|------|------|
| 工作方法定义在 | `debate-argument-builder` |
| 输入 | P1+P2全部结构化数据 |
| 输出 | 5维度空头论点 + 风险标注 |
| 产出标记 | `###END_BEAR_ARGUMENT` |
| 边界 | 纯定性分析，不做数据计算 |

5维度分析框架：
1. 趋势结构 — 做空右侧信号
2. 量价关系 — OI减+价跌
3. 期限结构 — Contango→做空有利
4. 产业链验证 — 方向一致
5. 风险点 — 至少列出2个

### 4.6 风控明 — 风险总监 (P4)

| 项目 | 内容 |
|------|------|
| 工作方法定义在 | `debate-risk-manager` |
| 输入 | P1-P3全部数据 |
| 输出 | 三方评估 + 裁定 + JSON交接数据 |
| 产出标记 | `###END_RISK_ASSESSMENT` |
| 边界 | 不做交易计划 |

执行步骤：
1. **三方评估** — 激进(行动倾向) + 保守(安全倾向) + 中性(平衡)
2. **铁律检查** — ADX<15→降级、RSI极端→降级、数据缺失→排除、同链冗余→降级
3. **组合级风险检查** — 按产业链聚合，检查集中度（单链≤10%）
4. **最终裁定** — 可执行/观察/排除三级

JSON交接格式（供策执远消费）：
```json
{
  "excluded": ["hc"],
  "watch": ["si"],
  "chain_limits": {"黑色系": {"actual": 14.8, "limit": 10, "status": "超标"}},
  "verdicts": {"rb": {"status": "可执行", "risk_level": "中", "note": "..."}}
}
```

### 4.7 策执远 — 交易策略师 (P5)

| 项目 | 内容 |
|------|------|
| 工作方法定义在 | `debate-trading-planner` |
| 输入 | 风控明JSON交接 + 前序全部数据 |
| 输出 | 入场/止损/目标/仓位/对冲方案 |
| 产出标记 | `###END_TRADING_PLAN` |
| 边界 | 接受风控明裁定，不出执行 |
| 约束 | 禁止祈使句，每品种2-3选项附利弊 |

仓位分配规则：
- 可执行品种: 8-10%仓位
- 观察品种: 4-5%（半仓）
- 排除品种: 跳过
- 同一产业链总仓位 ≤ 10%
- 前3大品种 ≤ 30%
- 总仓位 ≤ 80%

## 5. 使用方式

### 5.1 定时模式（每天20:00自动运行）

由 `commodity-daily-analysis` 自动化任务触发。流程：
1. `phase1_collect_signals.py` 全品种扫描 → intermediate_data.json
2. 专家团读取 intermediate_data.json → 取Top10 → 5阶段辩论
3. 生成HTML报告 → 推送到微信

### 5.2 按需模式（手动召唤）

在WorkBuddy中输入触发词：`期货分析`、`商品分析`、`多空辩论`、`召唤专家团`

示例：
```
用户：帮我分析螺纹钢和纯碱
明鉴秋：启动辩论专家团...
```

### 5.3 修改某个Agent的工作方法

```
修改Agent方法 → 只改对应skill
```

| 想改谁 | 改哪个文件 |
|--------|-----------|
| 数聚石的数据校验规则 | `futures-data-search/SKILL.md` → "辩论专家团数据采集接口" |
| 技研锋的否决条件 | `commodity-trend-signal/SKILL.md` → "辩论专家团信号核验接口" |
| 链证源的产业链归类 | `commodity-chain-analysis/SKILL.md` → "辩论专家团产业链验证接口" |
| 牛势研/熊谋略的论点框架 | `debate-argument-builder/SKILL.md` |
| 风控明的风控规则 | `debate-risk-manager/SKILL.md` |
| 策执远的仓位分配规则 | `debate-trading-planner/SKILL.md` |
| 辩论流程（阶段顺序/spawn协议） | `futures-trading-analysis/SKILL.md` |

## 6. 数据流

```
Phase 1 (并行):
  数聚石 → ###END_DATA_COLLECTION（结构化数据）
  技研锋 → ###END_TECH_ANALYSIS（信号裁决）
  
Phase 2 (串行):
  链证源 → ###END_CHAIN_ANALYSIS（产业链+冗余标记）
  
Phase 3 (并行):
  牛势研 → ###END_BULL_ARGUMENT（多头论点）
  熊谋略 → ###END_BEAR_ARGUMENT（空头论点）
  
Phase 4 (串行):
  风控明 → ###END_RISK_ASSESSMENT（裁定+JSON交接）
  
Phase 5 (串行):
  策执远 → ###END_TRADING_PLAN（交易计划）
  
汇总:
  debate_results.json → phase3_generate_report.py → HTML报告
```

## 7. 铁律

1. **决策辅助系统边界** — 禁止祈使句命令用户操作，禁止情绪化语言，多选项附利弊
2. **数据先行** — 所有数值必须通过 futures-data-search 获取真实数据
3. **流程不跳过** — 必须完整执行5阶段7专家，禁止协调器绕过Agent自行分析
4. **零Python模拟** — 辩论裁断（论点/裁定/交易计划）必须用LLM推理+SendMessage完成，禁止用Python dict拼接或胶水脚本生成debate_results.json
5. **零捷径** — Agent spawn失败也要完整走完5阶段，不可裁剪/合并/跳过。降级标注 ⚠️辩论降级
6. **右侧交易** — 所有建议基于已确认右侧价格行为信号，无信号则HOLD
7. **组合级风控** — 同一产业链≤10%，强相关品种合并，前3大≤30%

## 8. 测试

完整性测试位于 `Tests/debate_system_integrity_test.py`，24项验证：

```bash
python Tests/debate_system_integrity_test.py
```

涵盖：技能存在性、frontmatter有效性、Agent→Skill映射、产出标记一致性、数据流链完整性、spawn协议引用、边界声明一致性。

## 9. 扩展指南

### 新增一个Agent

1. 在 `futures-trading-analysis/SKILL.md` 的Agent表格中添加新行
2. 在 `专家团链条`中添加对应的Phase
3. 创建或引用一个skill定义其工作方法
4. 在 spawn 协议中添加对应的 spawn 指令
5. 定义产出标记
6. 运行测试验证

### 新增一个产业链

1. 在 `commodity-chain-analysis` 的 `chains.py` 中添加产业链映射
2. 链证源自动继承该产业链分析能力
