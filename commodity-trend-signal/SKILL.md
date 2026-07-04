---
name: commodity-trend-signal
version: 2.18.0
description: 商品期货趋势信号发现系统 v2.18.0 — L1-L4四层打分+TQ-Local桥接+评分单源真理原则+内联评分检测器。多空双向扫描全市场，100分制多维打分识别趋势启动/主升/主跌阶段。内置全品种扫描CLI，可与 commodity-chain-analysis 配合使用。
  L1层包含期货专属信号：OI三角、基差走强、期限结构、跨期Spread。解决"推荐已走远品种"问题。
  支持单品分析 + 全品种批量扫描，可独立使用或与 commodity-chain-analysis 配合进行产业链验证。
agent_created: true
user_invocable: true
triggers:
  - 趋势信号
  - 全品种扫描
  - 信号排序
  - 通道突破
  - 多维打分
  - 信号筛选
  - 趋势阶段识别
  - 萌芽信号
  - 排序赛马
  - OI信号
  - 基差信号
  - 期限结构
  - 做空信号
  - 空头趋势
  - 信号解读
  - 报告使用方法
  - 每日操作SOP
  - TQ-Local
  - 通达信指标
---

# 商品期货趋势信号发现系统 v2.16.0

## 依赖
- **输出方**：`TechnicalOutput`（`contracts/technical.py`）
- **版本**：`2.0`
- **输出方式**：正文（Markdown 信号分析报告）+ 末尾 ```json fence 结构化摘要

## 核心能力

- **TQ-Local桥接** ⭐：DMI(14,6)/RSI(14)/CCI(14)/MACD(12,26,9) 优先走通达信实盘公式，与通达信软件**100%一致**，不可用时自动降级numpy
- **L1-L4四层打分架构**：L1萌芽(40分) + L2量价(30分) + L3结构(20分) + L4确认(10分) + 否决(-20分)。**多空对称打分**
- **全品种批量扫描** ⭐：`scan_all.py` CLI一键扫描62品种，输出JSON + HTML报表，含指标来源标注
- **L1 萌芽/资金结构（最早，10-30根K）**：OI三角、基差走强/走弱、期限结构Back/Contango、跨期Spread、ROC零轴/零下、%b过0.5/低于0.2、ATR百分位、HH/HL(V2.13)
- **L2 量价领先（次早，3-10根K）**：Vortex交叉(多/空)、CCI破±100、Supertrend翻色(多/空)、HMA交叉、KAMA转向
- **L3 价格结构（中等，2-5根K）**：RSI健康区(40-60)/极端区、DMI方向(+DI/-DI)、前高/前低突破
- **L4 确认（基准，0根K）**：通道突破(上轨/下轨)、均线排列(多头/空头)、MACD确认(金叉/死叉)
- **否决维度**：RSI极端(>80/<20)、ADX<15震荡、极度偏离、OI背离、结构切换预警
- **时间衰减机制**：突破后走远的信号分数递减（多空均适用）
- **阈值阶梯化**：T1观察(60-75)、T2主仓(75-90)、T3警惕(>90)
- **排序赛马制**：多头Top5 + 空头Top5 分别排序
- **四阶段趋势生命周期**：启动(launch) → 主升(多头)/主跌(空头)(trending) → 衰竭(exhausted) → 反转(reversal)
- **双周期通道系统**：DC20(短期) + DC55(长期) + Bollinger(20,2)，多空对称突破检测
- **ATR追踪止损**：初始1.5×ATR，趋势延续期移至DC20轨道（多头用下轨，空头用上轨）
- **阶段式止盈**：RSI极端(>70/<30)→减30%；DC20破位→减50%；DC55中轨破→清仓
- **早期信号集成**：6种早期信号检测结果直接参与打分（非仅预警），多空方向均可检测
- **市场类型适配**：大宗商品/A股/数字货币/外汇参数自动适配

## 🔴 核心铁律：评分逻辑单源真理原则（2026-07-02 强制执行）

**所有评分逻辑必须且只能通过 `scoring_system.py` 实现。任何脚本文件不得内联 L1-L4 打分/趋势阶段判断/否决逻辑。**

### 三线防御体系

#### 防线 1：架构分层（不可违反）

```
scripts/
├── scoring_system.py         ← 唯一评分来源（不可分叉）
│   ├── score_L1_germination()
│   ├── score_L2_volume_price()
│   ├── score_L3_structure()
│   ├── score_L4_confirmation()
│   ├── score_veto_dimension()
│   ├── _determine_direction()
│   └── calculate_composite_score()  ← 唯一入口
├── indicators.py             ← 唯一指标计算来源
├── tdx_bridge.py             ← 通达信桥接
│
├── scan_all.py               ← 入口：必须 import scoring_system
├── full_scan_debate.py       ← 入口：必须 import scoring_system
├── lint_no_inline_scoring.py ← 合规检测
```

新入口脚本必须遵守的调用链：

```python
# ✅ 正确：统一入口
from scoring_system import calculate_composite_score
sym_dict = {'last_price': price, 'open_interest': tech.get('open_interest', 0)}
sc = calculate_composite_score(tech, sym_dict, 0, kline_closes, term_basis)

# ❌ 禁止：内联任何评分阈值
# if sl > 1.5: l1 += 12  — 禁止
# if rsi > 75: veto -= 5 — 禁止
```

#### 防线 2：修改检测（每次修改后必须执行）

```bash
# 脚本修改后立即运行
python scripts/lint_no_inline_scoring.py
```

退出码 0 = 通过，退出码 1 = 发现内联评分逻辑，需修正。

#### 防线 3：版本号锚定

所有评分算法迭代必须且只能修改 `scoring_system.py`，其他入口文件自动继承新逻辑。严禁出现"改了 scan_all.py 但忘了改 full_scan_debate.py"的情况。

```diff
- ❌ 修改 scan_all.py 的内联评分 → 需要同步修改 full_scan_debate.py
+ ✅ 修改 scoring_system.py → scan_all.py 和 full_scan_debate.py 自动继承
```

### 历史教训

2026-07-02 发现 `scan_all.py` 的 `l1_l4_score()` 中 3 个子信号（higher_low/lower_high/vol_ratio）因数据链断裂从未触发，L1 有效范围从 ±40 缩水至 ±19。`full_scan_debate.py` 存在完全相同的问题（代码行注释写明"与scan_all.py完全一致"），另有独立的 `determine_trend_stage()` 和 `check_veto()` 实现与 `indicators.py`/`scoring_system.py` 存在阈值偏差。

**每次在新脚本中内联评分逻辑，就是在制造一个迟早会腐烂的副本。**
**胶水代码零容忍** — 禁止为单次分析创建独立脚本。用 `--symbols` 参数复用现有 CLI。

## 🔒 Signal Quality Circuit Breaker（新增·全局强制）

| 防呆机制 | 规则 | 触发后果 |
|:---------|:----|:---------|
| L1-L4评分范围 | 每层得分范围**-25~+25**，总分范围**-100~+100** | 超出范围标注"评分越界"并裁剪至合法范围 |
| 否决项上限 | `veto`字段范围**-20~0** | 超出裁剪 |
| 方向一致性 | 若L1/L2/L3/L4中≥3层方向相反 → 标注"层间矛盾"并降级 | 信号等级降至NOISE |
| 信号等级映射 | 绝对值≥70=STRONG, 50-69=WATCH, 30-49=WEAK, <30=NOISE | 映射不一致时以abs值为准覆盖 |
| Z分数范围 | 方向感知Z-score**-3~+3** | 超出即为极端值，标注"极端Z" |
| 输出JSON大小 | **≤5MB** | 超限裁剪 |
| 运行超时 | **≤120秒** | 超限输出已有结果 |

## 使用方式

### 独立使用（单品分析）

```python
from scripts.collect_data import collect_symbol_data
from scripts.indicators import calculate_all_indicators, assess_trend_maturity
from scripts.scoring_system import calculate_composite_score
from scripts.signal_screener import detect_trend_stage, count_resonance, screen_signals
from scripts.trade_plan import generate_trade_plan
```

### 与 commodity-chain-analysis 配合

本 skill 负责信号发现，commodity-chain-analysis 负责产业链验证和多空辩论。
两个 skill 独立部署，通过数据字典传递中间结果。


### 报表输出说明

全品种扫描(scan_all.py)产出终端表格和HTML报表，各栏位含义如下：

| 栏位 | 说明 | 范围 |
|------|------|------|
| 总分 | L1+L2+L3+L4+否决 综合信号强度 |-100 ~ +100|
| L1 | 萌芽/资金结构层：OI/基差/期限/ROC/MA斜率/HL/OBV等12项 |-40 ~ +40|
| L2 | 量价领先层：Vortex/CCI/Supertrend/HMA 四项量价指标 |-25 ~ +25|
| L3 | 价格结构层：RSI健康区/DMI方向/前高前低突破 |-25 ~ +25|
| L4 | 确认层：通道突破/均线排列/MACD/DC55共振 |-10 ~ +10|
| 否决 | 硬警报：ADX震荡/RSI极端/CCI极端/缩量/偏离/结构切换 |-20 ~ 0|
| ADX | 趋势强度指数（Wilder平滑），>25为强趋势 |0~100|
| RSI | 14日相对强弱指数，>80超买/<20超卖 |0~100|
| Z | 总分在全市场中的Z-score偏离度，Z>|2|统计显著 |理论无界|
| CONS | L1-L4四层与总分方向一致的层数，4/4为干净信号 |0~4/4|

**使用方法**：按总分降序排列，绝对值越大信号越强。多头方向只做多，空头方向只做空。STRONG(>=75)优先关注，WATCH(>=60)可观察，WEAK(>=40)需验证，NOISE(<40)忽略。Z确认统计显著性，CONS确认方向一致性。

### 趋势阶段说明

全品种扫描(scan_all.py)输出的「阶段」列基于四阶段趋势成熟度模型：

| 阶段 | 判断依据 | 含义 |
|:----|:--------|:-----|
|  🟢 | 突破DC20通道 + (Boll收口或DC55同向拐头) | 趋势刚启动，空间大但需确认 |
|  🔵 | DC20通道上半区运行，或 ADX≥25 强制提升 | 趋势已确认，核心持仓区间 |
|  🟡 | DC20通道极值(多头>0.85/空头<0.15) + RSI极端(多头>75/空头<25) | 趋势末端，注意减仓或收紧止损 |
|  🔴 | 价格穿越DC55中轨反方向 + ADX<35(强趋势不标反转) | 方向可能转变，平仓观望 |

### 信号等级说明

| 等级 | 阈值 | 含义 |
|:----|:----:|:-----|
| **STRONG** | 总分 ≥ 75 | 最强信号，L1-L4多层共振，优先关注 |
| **WATCH** | 总分 ≥ 60 | 重点信号，方向一致性高，可纳入观察名单 |
| **WEAK** | 总分 ≥ 40 | 信号存在但质量一般，需基本面验证后再入场 |
| **NOISE** | 总分 < 40 | 噪音，层间矛盾或方向不明确，建议忽略 |

### 报表输出说明

全品种扫描产出终端表格和HTML报表，各栏位含义如下：

| 栏位 | 说明 | 范围 |
|------|------|------|
| 总分 | L1+L2+L3+L4+否决 综合信号强度 | -100 ~ +100|
| L1 | 萌芽/资金结构层：OI/基差/期限/ROC/MA斜率/HL/OBV等12项 | -40 ~ +40|
| L2 | 量价领先层：Vortex/CCI/Supertrend/HMA 四项量价指标 | -25 ~ +25|
| L3 | 价格结构层：RSI健康区/DMI方向/前高前低突破 | -25 ~ +25|
| L4 | 确认层：通道突破/均线排列/MACD/DC55共振 | -10 ~ +10|
| 否决 | 硬警报：ADX震荡/RSI极端/CCI极端/缩量/偏离/结构切换 | -20 ~ 0|
| 阶段 | launch/trending/exhausted/reversal 趋势成熟度 | 见上表 |
| 等级 | STRONG/WATCH/WEAK/NOISE 信号综合评级 | 见上表 |
| ADX | 趋势强度指数（Wilder平滑），>25为强趋势 | 0~100|
| RSI | 14日相对强弱指数，>80超买/<20超卖 | 0~100|
| Z | 总分在全市场中的Z-score偏离度，Z>|2|统计显著 | 理论无界|
| CONS | L1-L4四层与总分方向一致的层数，4/4为干净信号 | 0~4/4|

**使用方法**：按总分降序排列，绝对值越大信号越强。多头方向只做多，空头方向只做空。优先关注 STRONG 和 WATCH 等级品种，结合趋势阶段选择入场时机。


### 全品种批量扫描（CLI）⭐

```bash
# 一键扫描62品种，输出JSON + HTML报表
python scripts/scan_all.py

# 指定输出目录和文件名前缀
python scripts/scan_all.py -o Reports/2026-06-29 -p full_scan

# 自定义品种扫描（避免胶水代码）
python scripts/scan_all.py -s PK,RB,B,UR

# 辩论专家团模式（同上）
python scripts/full_scan_debate.py -s PK,RB,B,UR

# 输出文件：
#   {output_dir}/full_scan_{YYYYMMDD}.json      — 结构化信号数据
#   {output_dir}/full_scan_ranking_{YYYYMMDD}.html — 暗色主题交互报表
#   {output_dir}/custom_{prefix}_{YYYYMMDD}.json   — 自定义品种时自动加custom_前缀
```

**scan_all.py 特性**：
- 自动检测TQ-Local可用性，优先用通达信实盘指标
- 报表标注每品种指标来源（通达信/numpy）
- 包含L1-L4分层得分、ADX、RSI、CCI、趋势等级
- 25秒完成62品种全流程（通达信本地数据采集 + TQ-Local桥接指标

## 模块说明

| 模块 | 功能 |
|------|------|
| `config.py` | 系统参数、自适应权重、品种阈值、**v2.13 L1-L4四层打分配置**（含期货专属OI/基差/Spread配置）、市场类型适配 |
| `indicators.py` | 技术指标计算（numpy 65项）、TQ-Local桥接自动patch、四阶段趋势成熟度评估 |
| `tdx_bridge.py` ⭐ | **TQ-Local HTTP桥接器**：formula_zb批量获取DMI/RSI/CCI/MACD(与通达信100%一致)，自动降级numpy |
| `scan_all.py` ⭐ | **全品种扫描CLI**：62品种一键扫描 + JSON/HTML输出，自包含L1-L4评分 |
| `scoring_system.py` | **v2.17a L1-L4四层打分系统**：L1萌芽(40分)+L2量价(30分)+L3结构(20分)+L4确认(10分)+否决(-20分) |
| `early_signal.py` | 6种早期信号检测 + **v2.13期货专属L1信号**：`detect_oi_triangle()`、`detect_basis_signal()`、`detect_term_structure_signal()`、`detect_spread_signal()` + `inject_early_signals_to_tech()` |
| `signal_screener.py` | 趋势阶段检测、**v2.13 L1-L4四层共振度计算**（含OI/Vortex/CCI/Supertrend/HMA共振）、排序赛马制信号筛选 |
| `trade_plan.py` | 置信度计算（**v2.13使用L1-L4四层得分**）、盈亏比分析、阶梯化仓位（T1轻仓/T2标准/T3减仓）、ATR追踪止损、阶段式止盈 |
| `collect_data.py` | 数据采集（交易所官方API → TqSdk → AKShare 降级链） |
| `report.py` | Markdown/HTML报告生成 |

## 信号解读

### L1-L4四层打分架构详解

| 层级 | 名称 | 分值 | 信号含义 | 比传统指标早 |
|------|------|------|---------|-------------|
| **L1 萌芽/资金结构** | 最早期信号 | 40分 | 资金悄悄进场、基差变化、期限结构转变 | 10-30根K线 |
| **L2 量价领先** | 量价先行信号 | 30分 | 成交量/波动率先于价格变化 | 3-10根K线 |
| **L3 价格结构** | 价格形态信号 | 20分 | 价格突破关键位置、RSI健康区 | 2-5根K线 |
| **L4 确认** | 趋势确认信号 | 10分 | 均线排列、通道突破、MACD确认 | 0根K线（基准） |
| **否决** | 风险过滤 | -20分 | RSI极端(>80/<20)-15分、ADX<15震荡-5分、OI背离-3分、结构切换-2分 | — |

### 等级阈值说明

| 等级 | 分值范围 | 含义 | 操作建议 |
|------|---------|------|---------|
| **STRONG** | ≥75分 | 强趋势信号，多维度共振 | 可考虑主仓介入 |
| **WATCH** | 60-74分 | 趋势信号明确，但需验证 | 观察等待右侧确认 |
| **WEAK** | 40-59分 | 信号较弱或已走远 | 轻仓试探或观望 |
| **NOISE** | <40分 | 噪音信号，趋势不明确 | 不操作 |

### 表格字段解释

| 字段 | 含义 | 计算方法 |
|------|------|---------|
| **RSI** | 相对强弱指标 | 14周期，>70超买，<30超卖 |
| **ADX** | 趋势强度指标 | >25强趋势，<20震荡 |
| **MA20斜率** | 20日均线方向 | 正值上升，负值下降 |
| **L1分数** | 萌芽/资金结构得分 | 基于OI、基差、期限结构等 |
| **L2分数** | 量价领先得分 | 基于Vortex、CCI、Supertrend等 |
| **L3分数** | 价格结构得分 | 基于RSI健康区、DMI方向等 |
| **L4分数** | 确认得分 | 基于通道突破、均线排列等 |
| **否决分** | 风险扣分 | ADX震荡、RSI极端等 |

### 信号组合解读示例

#### 高质量信号（推荐关注）
```
品种：玻璃(FG) - 空头
总分：60分 (WATCH)
L1: 33分 (萌芽信号强)
L2: 10分
L3: 8分
L4: 9分
否决：0分
解读：L1萌芽信号最强（33分），说明资金已开始布局空头，但L2-L4确认不足，需等待右侧确认
```

#### 已走远信号（谨慎）
```
品种：螺纹钢(rb) - 空头
总分：56分 (WEAK)
L1: 24分
L2: 15分
L3: 8分
L4: 9分
否决：0分
解读：L2量价信号较强，但L1萌芽信号一般，说明趋势已启动一段时间，追空风险较大
```

#### 早期萌芽信号（潜力品种）
```
品种：豆一(a) - 多头
总分：60分 (WATCH)
L1: 29分
L2: 9分
L3: 12分
L4: 10分
否决：0分
解读：L1-L4分布均衡，L3价格结构较好，可能是早期多头信号，值得重点关注
```

## 报告使用方法

### 自适应SOP（根据市场类型自动调整）

#### 期货市场SOP
```
扫描信号 → 产业链验证 → 多空辩论 → 右侧确认 → 风控执行
```
- **扫描信号**：使用commodity-trend-signal扫描全品种，获取多空Top信号
- **产业链验证**：使用commodity-chain-analysis验证品种与产业链方向一致性
- **多空辩论**：基于产业链数据进行多空论点构建
- **右侧确认**：等待价格突破关键位置、均线排列确认
- **风控执行**：ATR止损、阶梯化仓位、阶段式止盈

#### 股市SOP
```
只扫描多头信号 → 行业验证 → 多空辩论 → 右侧确认 → 风控执行
```
- **扫描多头信号**：A股只能做多，专注多头信号扫描
- **行业验证**：验证个股与行业板块方向一致性
- **多空辩论**：分析行业景气度、估值水平、资金流向
- **右侧确认**：等待突破关键阻力位、均线多头排列
- **风控执行**：设置止损位、控制仓位比例

#### 加密货币SOP
```
扫描多空信号 → 币圈整体走势验证 → 多空辩论 → 右侧确认 → 风控执行
```
- **扫描多空信号**：加密货币支持双向交易，扫描多空Top信号
- **币圈整体走势验证**：分析BTC/ETH主导率、市场情绪、资金流向
- **多空辩论**：基于链上数据、交易所流入流出、持仓变化
- **右侧确认**：等待突破关键位置、成交量确认
- **风控执行**：加密货币波动大，严格止损、轻仓操作

### 正确用法（5步法）

#### 1️⃣ 选股（信号筛选）
- 扫描全市场信号，获取多头Top5和空头Top5
- 优先关注STRONG级信号，其次WATCH级
- 注意L1萌芽分数，高L1说明趋势刚启动

#### 2️⃣ 验证（产业链/行业/市场验证）
- **期货**：使用commodity-chain-analysis验证产业链方向
- **股票**：验证个股与行业板块一致性
- **加密货币**：分析BTC/ETH主导率、市场情绪

#### 3️⃣ 等待（右侧确认）
- 等待价格突破关键位置（前高/前低、通道上轨/下轨）
- 等待均线排列确认（多头排列/空头排列）
- 等待MACD金叉/死叉确认

#### 4️⃣ 执行（入场）
- 确认信号后入场，不提前布局
- 根据等级控制仓位：STRONG=5%base，WATCH=3%base，WEAK=1%base
- 设置初始止损：1.5×ATR

#### 5️⃣ 跟踪（持仓管理）
- 趋势延续：移动止损至DC20轨道（多头下轨，空头上轨）
- 阶段式止盈：RSI极端→减30%，DC20破位→减50%，DC55中轨破→清仓
- 定期复盘，更新信号评分

### 常见误区

#### ❌ 看到STRONG就冲
- **问题**：STRONG级信号可能已走远，追高风险大
- **正确**：检查L1萌芽分数，高L1才是好机会

#### ❌ 忽视否决分
- **问题**：否决分高说明信号矛盾，风险大
- **正确**：否决分超过-10分，谨慎操作

#### ❌ 只看总分不看分层
- **问题**：总分高但L1低，说明趋势已启动一段时间
- **正确**：关注L1-L4分布，L1高+L2-L4均衡才是好信号

#### ❌ 不做产业链验证
- **问题**：技术信号与基本面矛盾，容易被套
- **正确**：期货必须做产业链验证，股票做行业验证

#### ❌ 忽视右侧确认
- **问题**：提前布局容易被假突破骗线
- **正确**：等待价格突破关键位置、均线排列确认

### 每日操作SOP

#### 期货市场每日流程
```
08:00-09:00  扫描信号（commodity-trend-signal）
09:00-10:00  产业链验证（commodity-chain-analysis）
10:00-11:00  多空辩论（产业链数据支撑）
11:00-12:00  右侧确认（等待关键位置突破）
13:00-14:00  风控执行（入场、止损、仓位）
15:00-16:00  持仓跟踪（移动止损、阶段止盈）
```

#### 股市每日流程
```
08:00-09:00  扫描多头信号（专注多头）
09:00-10:00  行业验证（板块方向一致性）
10:00-11:00  多空辩论（行业景气度、估值）
11:00-12:00  右侧确认（突破关键阻力位）
13:00-14:00  风控执行（入场、止损、仓位）
15:00-16:00  持仓跟踪（移动止损、阶段止盈）
```

#### 加密货币每日流程
```
00:00-01:00  扫描多空信号（24小时市场）
01:00-02:00  市场验证（BTC/ETH主导率、情绪）
02:00-03:00  多空辩论（链上数据、资金流向）
03:00-04:00  右侧确认（突破关键位置）
04:00-05:00  风控执行（入场、止损、仓位）
06:00-07:00  持仓跟踪（移动止损、阶段止盈）
```

## 数据源优先级

由 futures-data-search 的 MultiSourceAdapter 统一调度：

```
MultiSourceAdapter.get_kline() / get_quote()
  ├─ 1. TqSdk（盘中优先，实时行情）
  ├─ 2. 交易所官方API（盘后优先，收盘数据完整）
  ├─ 3. 东方财富API（公开HTTP接口）
  ├─ 4. AKShare（开源数据，60+品种覆盖）
  └─ 5. WebSearch（极端降级，权威网站搜索）
```

## 辩论专家团信号核验接口 — 技研锋工作方法

当本 skill 被 futures-trading-analysis 辩论系统的 **技研锋** Agent 加载时，按以下方法执行。

### 角色声明

```
你是技研锋——辩论专家团的趋势信号分析师。
你的职责：基于预计算L1-L4数据做独立核验和定性判断，输出信号裁决。
你的边界：不做数据采集（那是数聚石的事），不做产业链分析（那是链证源的事），
         不做交易计划（那是策执远的事）。
         只做信号核验和趋势判断。
```

### 🔴 脚本执行路径（强制）

当 Agent 加载本 skill 后需要运行 Python 脚本时，**必须 cd 到 skill 的正式安装目录**，禁止从工作区根目录执行相对路径：

```bash
# ✅ 正确：cd 到 skill 目录后执行
cd ~/.workbuddy/skills/commodity-trend-signal && python scripts/scan_all.py

# ❌ 错误：从工作区根目录执行（CWD 落在 C:\Users\yangd\Documents\WorkBuddy）
# 这会命中 quant-skills/commodity-trend-signal/scripts/（GitHub 同步副本）而非正本
python scripts/scan_all.py
```

**原因**：工作区根目录 `quant-skills/` 是 GitHub 同步的备份副本，`~/.workbuddy/skills/` 才是 WorkBuddy 管理的正本。两者内容理论上一致，但辩论系统的编排层（contracts/ 接口、PhaseMeta trace）只打通 WorkBuddy skill 路径。从 GitHub 副本运行会导致版本不匹配、trace 断裂、且绕过辩论系统管理。

### 输入

由 明鉴秋 传入辩论候选品种的结构化数据（含预计算L1-L4得分和各指标原始值）。

**支持两种工作模式**：

| 模式 | 品种数 | 行为 |
|------|--------|------|
| `full_scan` | 全67品种 | 计算全部品种的L1-L4 → 按 `abs(total)` 降序取Top10 → 只对Top10输出详细核验 |
| `custom` | 指定品种 | 计算指定品种的L1-L4 → 全部输出详细核验 |

### 全市场模式选Top10规则

当 mode=full_scan 时，在完成全部品种的L1-L4计算后执行：

```python
# 1. 按 composite_total（或 total）降序排序
candidates.sort(key=lambda x: abs(x.get('total', 0)), reverse=True)
# 2. 取前10名进入辩论
top10 = candidates[:10]
```

### 核验方法

对每个品种依次执行以下步骤：

#### Step 1: 得分评估

```
审查 L1-L4 各维度得分，标注异常：
- L1高分(>30)但L3低分(<5) ⇒ 结构不确认，降级
- L4高分(>10)但L1低分(<15) ⇒ 已走远，时间衰减
- 存在否决项(-20触发) ⇒ 标注否决原因
```

如需核验指标值，调用 numpy 指标引擎独立计算：
```python
from scripts.indicators import _compute_indicators_numpy
result = _compute_indicators_numpy(close_prices, high, low)
# 返回: rsi, adx, cci, macd, supertrend, donchian, bollinger ...
```

#### Step 2: 趋势阶段判断

| 特征 | 趋势阶段 |
|------|---------|
| MA20上穿MA60 + 通道突破上轨 + RSI 40-60健康区 | 启动→主升 |
| MA20下穿MA60 + 通道跌破下轨 + RSI 40-60健康区 | 启动→主跌 |
| RSI>70连续 + 量价背离 | 衰竭 |
| 前高被突破后回踩确认 | 主升延续 |
| 前低被跌破后反弹失败 | 主跌延续 |

#### Step 3: 否决项检查

| 检查项 | 条件 | 处理 |
|--------|------|------|
| ADX震荡 | ADX < 15 | ⚠️ 震荡市，降级 |
| RSI极端（方向同侧） | 多头+RSI>80 或 空头+RSI<20 | ⚠️ 追高/追低接飞刀，扣15分 |
| RSI极端（方向反侧） | 多头+RSI<20 或 空头+RSI>80 | ✅ 安全区域，反侧极端是顺趋势入场窗口，不扣分 |
| OI背离 | 价涨量缩/价跌量增 | ⚠️ 信号不可靠 |
| SuperTrend翻转 | ST方向与判定相反 | ⚠️ 短期趋势冲突 |

#### Step 4: 关键价位标注

```
支撑位: DC20下轨 / 前低 / MA60
阻力位: DC20上轨 / 前高 / MA60
止损参考: 1.5×ATR
```

### 接口契约（Pydantic Schema）

当本 skill 被辩论专家团集成使用时，按以下 schema 结构化产出。schema 定义在 `futures-trading-analysis` 主 skill 的"接口契约"章节。此处为子 skill 实现版。

```python
from pydantic import BaseModel
from typing import Literal, Optional

class PhaseMeta(BaseModel):
    """每条 phase 输出的元数据"""
    phase: str                     # "P1"
    agent_id: str                  # "futures-trend-analyst"
    variant: str                   # "tech_analysis"
    trace_id: str                  # 整条辩论链一致的跟踪 ID
    depends_on: list[str]          # ["P1_data"]

class TechOutput(BaseModel):
    """技研锋信号核验的最终产出"""
    variant: Literal["tech_analysis"] = "tech_analysis"
    verdicts: dict[str, str]           # 逐品种裁决 {"pid": "BUY/SELL/HOLD"}
    trend_stages: dict[str, str]       # 逐品种趋势阶段 {"pid": "启动/主升/主跌/衰竭/反转"}
    confidence: dict[str, str]         # 逐品种置信度 {"pid": "高/中/低"}
    veto_status: dict[str, str]        # 逐品种否决状态 {"pid": "✅通过/⚠️注意/❌否决"}
    veto_reasons: dict[str, str]       # 逐品种否决原因
    all_actionable: list[dict]         # 全品种L1-L4得分列表（full_scan模式下选Top10用）
    top10: list[str]                   # Top10候选品种（full_scan模式）
    key_levels: dict[str, dict]        # 逐品种关键价位 {"pid": {"support": 值, "resistance": 值, "atr": 值}}
    notes: dict[str, list[str]]        # 逐品种异常标注
    meta: PhaseMeta
```

**产出规范**：
- Agent 必须按 `TechOutput` schema 产出 typed 对象
- 下游通过 `output.verdicts`、`output.trend_stages`、`output.veto_status` 等属性访问
- 完全迁移至 contracts/ schema 
- `all_actionable` 给明鉴秋保存 `intermediate_data.json` 使用

### 输出格式（向后兼容）

```json
{
  "rb": {
    "verdict": "BUY/SELL/HOLD",
    "trend_stage": "启动/主升/主跌/衰竭/反转",
    "confidence": "高/中/低",
    "veto_status": "✅通过/⚠️注意/❌否决",
    "veto_reason": "否决原因（如适用）",
    "key_levels": {"support": 值, "resistance": 值, "atr": 值},
    "notes": ["异常标注列表"]
  }
}
```

## 版本历史

### v2.16.0 (2026-06-29)
**TQ-Local桥接 + numpy兜底 — DMI/RSI/CCI/MACD与通达信100%一致**

1. **新增 `tdx_bridge.py`**: 通达信TQ-Local HTTP桥接器
   - 优先使用TQ-Local `formula_zb` 获取DMI/RSI/CCI/MACD（与通达信软件数值完全一致）
   - 批量查询62品种仅需2秒，自动缓存300s
   - TQ-Local不可用时静默降级numpy计算
2. **indicators.py接入**: `_compute_indicators_numpy()` 新增 `symbol` 参数 → 自动调bridge.patch_indicators()
3. **覆盖范围**: ADX/PDI/MDI、RSI、CCI、MACD(DIF/DEA)、MA5-60、BOLL、OBV
4. **自定义指标不变**: SuperTrend/HMA/KAMA/Vortex/CMF/Donchian仍用numpy

### v2.14.2 (2026-06-29)
**技术指标算法统一：RSI/ADX/ATR切换为通达信Wilder平滑**

1. **indicators.py**: `wilder_rma()` — 通达信SMA(X,N,1)等价实现（alpha=1/N）
2. **RSI**: `sma→wilder_rma`，超卖区数值更准确（消除SMA导致的RSI极端偏差）
3. **ADX/DMI**: TR/PDI/MDI/ADX全部使用Wilder平滑，与通达信DMI/ADX公式一致
4. **ATR/Vortex**: TR平滑同步切换为Wilder RMA

### v2.14.1 (2026-06-29)
**数据源重构：移除WH6，统一futures-data-search路由**

1. **移除WH6数据源**：SKILL.md数据源优先级WH6→TqSdk/交易所API/东方财富/AKShare
2. **更新term_basis.py**：exchange-futures-data→futures-data-search（注释+错误信息）
3. **置信度文档同步**：删除数据源置信度数值（所有数据源置信度统一为1.0）

### v2.14.0 (2026-06-27)
**核心改动：内置信号解读与自适应SOP报告使用规范**

1. **新增"信号解读"章节**：
   - L1-L4四层打分架构详解（每层含义、分值、比传统指标早多久）
   - 等级阈值说明（STRONG≥75 / WATCH 60-74 / WEAK 40-59 / NOISE<40）
   - 表格字段逐项解释（RSI/ADX/MA20斜率/L1-L4各层/否决分）
   - 信号组合解读示例（高质量信号 vs 已走远信号 vs 早期萌芽信号）

2. **新增"报告使用方法"章节**：
   - **自适应SOP**：根据市场类型自动调整流程
     - 期货市场：扫描信号→产业链验证→多空辩论→右侧确认→风控执行
     - 股市：只扫描多头信号→行业验证→多空辩论→右侧确认→风控执行
     - 加密货币：扫描多空信号→币圈整体走势验证→多空辩论→右侧确认→风控执行
   - **正确用法5步法**：选股→验证→等待→执行→跟踪
   - **常见误区**：5个典型错误及纠正方法
   - **每日操作SOP**：期货/股市/加密货币三个市场的具体时间流程

3. **技能定位升级**：
   - 从"信号发现工具"升级为"完整交易决策框架"
   - 内置市场类型识别和流程适配逻辑
   - 强化"右侧交易铁律"的执行规范

### v2.13.1 (2026-06-27)
**文档修正：补齐多空双向描述（代码层面v2.13已支持双向，文档滞后）**

1. **核心能力全面双向化**：L1-L4描述从单向多头标签改为多空对称表述
2. **四阶段生命周期修正**：标注"主升(多头)/主跌(空头)"，不再默认只有做多
3. **ATR止损/止盈双向化**：注明多头用DC20下轨、空头用DC20上轨
4. **信号检测双向化**：标注地Vortex/Supertrend/HMA/MACD等指标的空头等价物
5. **触发词新增**：做空信号、空头趋势

### v2.13.0 (2026-06-26)
**核心改动：L1-L4四层打分架构 + 期货专属早期信号（系统性铺开"早期发现趋势"方法）**

| 层级 | 分值 | 信号类型 | 比唐奇安早 | 期货专属度 |
|------|------|---------|-----------|-----------|
| L1 萌芽/资金结构 | 45分 | OI三角、基差、期限结构、Spread、ROC、%b、ATR% | 10-30根K | ★★★★★ |
| L2 量价领先 | 20分 | Vortex、CCI、Supertrend、HMA、KAMA | 3-10根K | ★★ |
| L3 价格结构 | 15分 | RSI健康区、DMI方向、前高突破 | 2-5根K | ★★ |
| L4 确认 | 20分 | 通道突破、均线排列、MACD、DC55共振 | 0（基准） | ★ |
| 否决 | -20分 | RSI极端(-15)、ADX震荡(-5)、OI背离(-3)、结构切换(-2) | — | ★★★ |

**测试验证**：萌芽型76分(STRONG) vs 已走远37分(NOISE)，v2.12仅59/32分。

**修改文件（7个）**：scoring_system.py(完全重写)、indicators.py(+15个L1/L2指标)、early_signal.py(+4个期货专属L1函数)、signal_screener.py(共振度8→16项)、trade_plan.py(置信度适配L1-L4)、config.py(L1-L4配置)、SKILL.md

1. **L1萌芽/资金结构维度（55分）**：v2.12保留——MA斜率(5分)、ROC零轴(5分)、接近通道上轨/下轨(5分)、量能先兆(5分)、Higher Low/Lower High(6分)；v2.13新增——OI三角(5分)、基差走强/走弱(3分)、期限结构(3分)、跨期Spread(3分)、%b过0.5/低于0.2(4分)、ATR百分位(3分)、OBV/CMF(6分)、量价背离(3分)
2. **L2量价领先维度（15分）**：Vortex(4分)、CCI(3分)、Supertrend(4分)、HMA(3分)、KAMA(1分)
3. **L3价格结构维度（15分）**：RSI健康区(8分)、DMI方向(4分)、前高突破(3分)
4. **L4确认维度（15分）**：从v2.12的35分降到15分，通道突破(6分)+均线排列(4分)+MACD(2分)+DC55共振(3分)
5. **否决维度新增**：OI背离否决(-3分)、结构切换预警(-2分)
6. **indicators.py新增L1/L2指标**：BB_PCTB、ATR_PERCENTILE、ATR_RATIO_20、CCI20、VI_PLUS/VI_MINUS、SUPERTREND_DIR、HMA10/HMA20、KAMA10、CMF21、STOCH_K5、WILLR14、VOL_PRICE_DIVERGENCE
7. **early_signal.py新增期货专属L1函数**：`detect_oi_triangle()`、`detect_basis_signal()`、`detect_term_structure_signal()`、`detect_spread_signal()`
8. **signal_screener.py共振度扩展**：从8项扩展到16项，覆盖L1-L4四层全部指标

### v2.12.0 (2026-06-26)
**核心改动：解决"推荐已走远品种"问题（Type A→Type B 打分架构升级）**

1. **萌芽维度（30分）**：5个萌芽因子（MA斜率转正/转负、ROC转正/转负、接近通道上轨/下轨、量能先兆、Higher Low/Lower High），给"刚冒头/刚破位"品种冲到阈值的机会
2. **确认维度降权（35分）**：通道突破+均线排列+MACD，带时间衰减（当天100%→20天+30%），只做加固不起跑线
3. **否决维度（-20分）**：RSI极端(>80/<20)、ADX<15震荡、极度偏离、严重缩量
4. **阈值阶梯化**：T1观察(60-75)、T2主仓(75-90)、T3警惕(>90)，替代一刀切
5. **排序赛马制**：取相对排名前N，不设绝对分数线
6. **早期信号集成**：`early_signal.py` 的检测结果通过 `inject_early_signals_to_tech()` 直接参与打分
7. **indicators.py 新增萌芽指标**：MA20_SLOPE、ROC10、VOL_5D_RATIO、PRICE_CHANGE_5D、HIGHER_LOW/LOWER_HIGH
8. **trade_plan.py 阶梯化仓位**：T1=3%base、T2=5%base、T3=3%base

### v2.11.0 (2026-06-26)
- 新增100分制多维打分系统（scoring_system.py）
- 新增四阶段趋势生命周期（launch/trending/exhausted/reversal）
- 新增双周期通道系统（DC20 + DC55 + Bollinger）
- 新增ATR追踪止损和阶段式止盈
- 新增市场类型参数适配表
- 从futures-industry-chain-analysis拆分为独立skill

### v2.10.0 (2026-06-25)
- 通道突破位置替代ADX作为趋势阶段主判据
- ADX降级为辅助信号
- 新增Bollinger带宽百分位和挤压检测


---
## v2.18.0 变更 (2026-07-02)
- **🔴 核心铁律：评分逻辑单源真理原则** — 禁止任何文件内联 L1-L4 评分逻辑，统一通过 `scoring_system.calculate_composite_score()` 调用
- **三线防御体系**：架构分层 → 修改检测(lint) → 版本号锚定
- **新增 `lint_no_inline_scoring.py`**：自动化检测脚本，运行 `python scripts/lint_no_inline_scoring.py` 验证合规
- **修复 `scan_all.py`**：删除内联 `l1_l4_score()`，改用 `calculate_composite_score()`
- **修复 `full_scan_debate.py`**：删除内联 `l1_l4_score()`/`determine_trend_stage()`/`check_veto()`，统一委派 scoring_system/indicators
- **修复 `scoring_system.py` import**：`from scripts.indicators` 兼容双路径导入
- 本次变更为架构级加固，无评分算法变更

## v2.16.0 变更 (2026-07-01)
- **方案D双排行**：Top10从单一abs(total)排序改为双排行
  - `early_top5`: 按 L1+L2-成熟度罚分 降序，捕捉趋势早期品种
  - `established_top5`: 按 abs(total) 降序（排除early_top5），覆盖已确认趋势
- **成熟度罚分**：新增`compute_maturity_penalty()`，对RSI极端(-4~-12)、ADX过高(-3~-6)、L4满分(-4)品种扣分
- **早期得分**：新增`compute_early_score()` = abs(L1+L2) - maturity_penalty
- 修复：abs(total)排序导致推荐已走远品种的问题（10/10 L4满分，7/10 RSI超卖/超买）
