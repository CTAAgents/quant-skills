---
name: adaptive-heartbeat-skill
version: 3.0.0
description: 自适应心跳监控系统 v3 — 通用8步工作流引擎，所有差异化配置通过 monitor_config.json
  注入。支持交易时段判断、多数据源健康评估、四维信号评分、自适应调度、阈值自动校准。一个引擎驱动任意品种/市场的自适应监控。
agent_created: true
user_invocable: true
triggers:
  - 心跳监控
  - 自适应监控
  - 数据源健康评估
  - 焦点检测
  - 信号评分
  - 自适应调度
  - 阈值校准
  - 多数据源降级
  - 实时行情监控
  - 新闻监控
disable: true
---

# Adaptive Heartbeat Monitor — Universal Skill

## 概述

自适应心跳监控系统 v3 — 通用版。将 8 步工作流引擎从品种特定逻辑中完全解耦，所有差异化配置通过 `monitor_config.json` 注入。一个引擎，驱动任意品种/市场的自适应监控。

## 架构

```
SKILL.md (本文件)          ← 通用 8 步引擎（品种无关）
    ↓ 加载
monitor_config.json        ← Agent 专属配置（数据源/品种/焦点/阈值）
    ↓ 驱动
state.json                 ← 运行时状态（自动创建，格式一致）
reports/                   ← 报告输出（路径由 config 定义）
```

## 工作流（8 步统一框架）

当收到心跳触发时，严格按照以下 8 步流程执行。禁止编造数据，禁止使用模拟数据。

---

### Step 1：读取 monitor_config.json + state.json

**并行执行**：与 Step 2 的数据采集在同一次 function_calls 中一起发出。

使用 `read` 工具读取以下文件：

**主配置文件**：`{config_root}/monitor_config.json`（config_root 默认为当前 workspace 根目录，或由 system_prompt 指定）

| 字段 | 类型 | 用途 |
|------|------|------|
| `version` | 字符串 | 配置版本号 |
| `name` | 字符串 | 监控系统名称 |
| `trading_hours` | 对象/null | 交易时段定义（24h 市场设为 null） |
| `products` | 对象 | 监控品种（键为品种代码，值为品种定义） |
| `data_sources` | 数组 | 数据源配置（顺序即优先级） |
| `focus_types` | 对象 | 焦点类型定义（触发条件+置信度公式） |
| `focus_chains` | 对象/null | 焦点联动规则（产业链共振等） |
| `tech_signals` | 数组 | 技术信号定义（品种专用） |
| `scoring` | 对象 | 评分权重配置 |
| `thresholds` | 对象 | 推送阈值 + 极端事件条件 |
| `report_path` | 字符串 | 报告输出根目录 |
| `report_name_format` | 字符串 | 报告文件名格式 |
| `schedule` | 对象 | 自适应调度间隔配置 |
| `red_rules` | 对象 | 硬规则（数据层/输出层/调度层） |

**状态文件**：`{config_root}/adaptive_heartbeat_state.json`

| 字段 | 类型 | 用途 |
|------|------|------|
| `last_update` | ISO时间戳 | 上次运行时间 |
| `signal_history` | 数组(最近20条) | 历史信号记录 |
| `priority_history` | 数组(最近20条) | 焦点变化历史 |
| `user_feedback_weights` | 对象 | 各焦点类型权重 |
| `pending_feedback` | 数组 | 待检测反馈的推送记录 |
| `threshold_calibration` | 对象 | 推送阈值校准 |
| `run_count` | 整数 | 累计运行次数 |
| `temp_cron_jobs` | 数组 | 活跃的临时高频 cron |
| `source_health` | 对象 | 数据源健康度追踪 |

**如果 state.json 不存在**：用 `monitor_config.json` 的 `initial_state` 章节创建初始状态。用户反馈权重初始值从 `config.user_feedback.signal_type_weights` 复制，数据源健康度初始值从 `config.data_sources` 生成（每个源的 score 用 `config.source.reliability / 100`）。

---

### Step 2：采集真实数据（必须并行）

#### 2.0 交易时段判断（如果 config 有 trading_hours）

```
now = 当前时间（使用 config.timezone）
从 config.trading_hours 读取：
  - sessions[]: 交易时段列表 [{start, end, break_start, break_end}, ...]
  - non_trading_interval: 非交易时段基础间隔（分钟）

if now 在任意 session 内 且 不在 break 中:
    trading = true
else:
    trading = false
```

非交易时段策略：
- 跳过实时行情采集（仅采集新闻/大事/低频数据）
- novelty 不因重复衰减
- 心跳间隔固定为 config.schedule.non_trading_interval 分钟

#### 2.1 实时行情采集（交易时段内）

对 `config.data_sources` 中 `category == "realtime"` 且 `enabled == true` 的每个数据源：

**URL 模板替换**：使用 `config.products` 中每个品种的 `url_params` 替换 `source.url_template` 中的 `{param}` 占位符。

并行 web_fetch 所有品种的所有实时源 URL。并行调用数上限：20。

**时效性校验**：
```
# 通用校验规则
if config.data_sources[i].max_staleness_min:
    数据时间戳与当前时间差 > max_staleness_min → 标记 [STALE]
elif 交易时段内: 数据应 < 5分钟
elif 非交易时段: 最近一笔价格即最新，标记 [PRE-CLOSE]

STALE 处理：
  - 标记该源的 stale_count++
  - 自动切换到同 category 的下一个 enabled 源
  - 报告中标注 [DEGRADED]
```

#### 2.2 低频数据采集

对 `config.data_sources` 中 `category == "fundamental"` 的源：按各自 `refresh_minutes` 频率判断是否需要本次采集。

#### 2.3 新闻采集

对 `config.data_sources` 中 `category == "news"` 的源：执行 web_search，关键词和 freshness 来自配置。

---

### Step 2.5：数据源健康评估与自适应

#### 2.5.1 采集后验证

| 检查项 | 规则 | 不通过处理 |
|--------|------|----------|
| 可达性 | HTTP 200 + 有效内容 | 标记 fail |
| 时效性 | 数据时间戳 < 阈值 | 标记 stale |
| 完整性 | config 定义的必需字段均有值 | 标记 incomplete |
| 一致性 | 多源交叉验证偏差 < `config.data_sources[k].max_deviation_pct`% | 标记 suspect |

#### 2.5.2 源健康度评分公式

```
score = 0.5 × success_rate + 0.3 × freshness_score + 0.2 × (source.reliability / 100)

success_rate = success / (success + fail + stale)  [至少分母=1]
freshness_score = max(0, 1 - avg_freshness_min / 60)
```

#### 2.5.3 自动降级链

从 `config.data_sources` 的排序中获得降级链（同一 category 下按 enabled 优先级排列）。

#### 2.5.4 自动发现新源

```
# 触发条件：主源连续 fail >= 3 或 score < 0.4
web_search query="<品种名> 实时行情 API" freshness="month"
# 评估候选 → 加入 source_health → 标记 auto_discovered
```

#### 2.5.5 更新源健康度

每次运行结束时（Step 6），更新 source_health 的 success_count/fail_count/stale_count/avg_freshness_min/score。

---

### Step 3：焦点检测 + 自适应优先级

#### 3.1 焦点匹配引擎

遍历 `config.focus_types` 所有焦点类型，对每个类型的 `trigger_conditions` 数组进行评估：

```
对每个 focus_type:
    for condition in trigger_conditions:
        if condition.kind == "keyword":
            如果本次采集的所有 news 文本中包含 condition.keywords 中任意一个 → 触发
        elif condition.kind == "price_change":
            如果 config.products[condition.product].current_change_pct 超过阈值 → 触发
        elif condition.kind == "fundamental_change":
            如果 fundamental 数据变化超过 condition.threshold → 触发
        elif condition.kind == "supply_chain_resonance":
            取 condition.products 列表各品种的 price_change，超过各自的 threshold → 共振触发
    if 触发:
        confidence = eval(condition.confidence_formula)  # 用实际值代入
```

取置信度最高的 1-2 个焦点。

#### 3.2 焦点联动规则

如果 `config.focus_chains` 不为 null，检查联动条件：

```
for chain in focus_chains:
    if all(chain.conditions):  # 所有条件都满足
        → 对应的 target_focus 置信度 += chain.confidence_boost
```

#### 3.3 自适应优先级

从 `config.schedule.focus_intervals` 查表获取推荐间隔（按置信度区间 0.7+/0.3-0.7/<0.3）。

---

### Step 4：信号评分（四维打分）

#### 4.1 新奇性（Novelty）

从 `state.json` 的 `signal_history` 查找同类型信号：

```
recent = signal_history 中 type == current_type 的记录
if not recent → novelty = 0.8
else:
    last = 最近的记录
    hours_since = (now - last.ts) / 3600
    if hours_since < 6 → novelty = 0.2
    elif hours_since < 12 → novelty = 0.5
    else → novelty = 0.8

# 例外：非交易时段不惩罚重复
if not trading_hours → novelty = max(novelty, 0.5)
```

#### 4.2 市场影响（Impact）

从 `config.focus_types` 的 `impact_base` + `impact_bonuses` 计算，取最高置信度焦点的 impact 值。

#### 4.3 技术信号（Tech Signal）

遍历 `config.tech_signals`，对每个信号：
- 检查 `condition` 中的表达式（用当前品种数据代入）
- 触发的信号权重求和
- tech_signal_score = 触发权重之和 × config.scoring.tech_signal_weight

无信号触发时 tech_signal_score = 0。

#### 4.4 可信度（Reliability）

取所有可用数据源的平均可信度，fallback: config.scoring.avg_source_reliability。

#### 4.5 综合评分

```
raw_score = novelty_weight × novelty 
          + impact_weight × max_impact 
          + reliability_weight × avg_reliability 
          + tech_signal_weight × tech_score

# 用户反馈权重调整
adjusted_score = raw_score × user_feedback_weights[current_focus_type]
```

硬规则：如果 novelty < 0.5 且 tech_signal_score == 0 → 直接「无信号，观望」。

#### 4.6 推送决策树

```
if config.thresholds.extreme_conditions 中任意条件满足:
    → 无条件推送

elif adjusted_score >= config.scoring.push_threshold:
    → 推送

elif 同类型信号 6 小时内已推送 AND 非极端:
    → 跳过

else:
    → 跳过
```

---

### Step 5：生成报告

按 `config.report_path` + `config.report_name_format` 保存报告。

报告结构（通用模板）：
1. 数据源状态
2. 行情数据（按 products 动态生成表格）
3. 产业链/关联指标（如果 config 有 link_metrics 定义）
4. 市场焦点
5. 信号评分
6. 交易信号评估（右侧交易准则，每个品种一栏）
7. 自适应调度
8. 重要新闻
9. 免责声明

---

### Step 6：更新状态（state.json）

**写入 signal_history**（追加，只保留最近 20 条）。

**更新 source_health**（所有使用的数据源计数+评分更新）。

**更新 priority_history**（追加，最近 20 条）。

**追踪 pending_feedback**（新增推送记录，检测旧反馈更新权重）。

**更新元数据**：last_update, run_count。

---

### Step 7：自适应调度（临时 cron 管理）

```
if 最高置信度焦点 >= config.schedule.urgent_threshold:
    创建/刷新高频 cron（间隔 = focus_intervals[confidence>=0.7]）
    过期时间 = now + max_urgent_cron_hours

elif 所有焦点置信度 < config.schedule.downgrade_threshold:
    删除所有临时 cron

临时 cron 配置：
  - sessionTarget: "isolated"
  - payload.kind: "agentTurn"
  - delivery mode: "none"
```

---

### Step 8：阈值自动校准（每 10 次运行）

当 `run_count % 10 == 0`：
- 统计最近 10 次的 false positive 率（noise_rate）
- 统计漏检率（miss_rate）
- noise_rate > 0.6 → push_threshold +0.05
- miss_rate > 0.3 → push_threshold -0.05
- 区间限制：[0.35, 0.75]

---

## 红色规则（通用硬规则）

### 数据层
- 不编造数据，失败标注「数据暂缺」
- 价格必须标注时间戳
- 时效性校验：实时源 < 5min，低频源 < 发布周期
- 新闻必须 freshness 过滤

### 输出层
- 不喊单，右侧交易（≥2 个可量化信号）
- 主时间框架：日线/4H 级别
- 免责声明必须包含

### 调度层
- 同类型信号 6 小时内不重复推送
- 临时 cron 必须有过期时间

---

## monitor_config.json Schema

完整 schema 见 `references/config_schema.json`。

核心结构：
```json
{
  "version": "3.0.0",
  "name": "监控系统名称",
  "timezone": "Asia/Shanghai",
  "monitor_root": "monitor_config 所在目录",
  "trading_hours": { ... } | null,
  "products": { "CODE": { "name": "...", "exchange": "...", "unit": "...", "url_params": {...} } },
  "data_sources": [ { "id": "...", "category": "realtime|fundamental|news", "url_template": "...", "reliability": 85, ... } ],
  "focus_types": { "TYPE": { "trigger_conditions": [...], "impact_base": 0.4, "impact_bonuses": [...] } },
  "focus_chains": [ { "conditions": [...], "target_focus": "...", "confidence_boost": 0.15 } ],
  "tech_signals": [ { "id": "T1", "type": "...", "condition": {...}, "weight": 0.3 } ],
  "link_metrics": [ { "name": "...", "formula": "...", "products": [...] } ],
  "scoring": { "novelty_weight": 0.5, "impact_weight": 0.2, "reliability_weight": 0.2, "tech_signal_weight": 0.1, "push_threshold": 0.55 },
  "thresholds": { "extreme_conditions": [...] },
  "report_path": "C:\\...",
  "report_name_format": "heartbeat_{config.name}_HHmm.md",
  "schedule": { "focus_intervals": {...}, "urgent_threshold": 0.7, "downgrade_threshold": 0.3, "non_trading_interval": 240 },
  "red_rules": { ... }
}
```

## 安装步骤

1. 将本 Skill 安装到目标 Agent
2. 在 Agent workspace 下创建 `monitor_config.json`（可使用 `examples/` 中的模板）
3. 创建 cron 任务指向本 Skill
4. 首次运行会自动创建 `adaptive_heartbeat_state.json`

## 已有配置模板

- `examples/oil_gold_config.json` — 原油+贵金属（WTI/Brent/黄金/白银 + 霍尔木兹海峡）
- `examples/black_metals_config.json` — 黑色系（螺纹钢/热卷/铁矿石/焦炭/焦煤）
