---
name: Polymarket
description: Polymarket预测市场多源数据集成路由系统。通过CLI查询实时赔率和事件，多数据源自动故障转移+健康监控+本地缓存。覆盖体育、政治、加密货币等。
agent_created: true
---

# Polymarket 预测市场 — 多源数据集成路由系统

## 概述

从Polymarket（全球最大预测市场）查询实时赔率。集成多源路由引擎（Python SmartRouter），
并内置零依赖Direct API降级模式——Python不可用时自动回退到纯Node.js直连，确保任何环境下都能工作。

## 快速参考卡片

```
🔍 搜索:     node wrapper.js search "Bitcoin"
📋 事件:     node wrapper.js events --tag=crypto
📊 详情:     node wrapper.js market will-bitcoin-reach-100k
🔧 诊断:     node wrapper.js diagnose
🌐 备选:     node wrapper.js alt-search "Bitcoin"
📡 代理:     node wrapper.js test-proxy http://proxy:port
❓ 帮助:     node wrapper.js
```

## 快速入门

```bash
# 搜索市场（通过 /public-search API，瞬时响应）
polymarket search "Arsenal FC"
polymarket search "Super Bowl"
polymarket search "Bitcoin"
polymarket search "Trump"

# 按类别浏览
polymarket events --tag=sports
polymarket events --tag=crypto
polymarket events --tag=politics

# 获取市场详情
polymarket market will-bitcoin-reach-100k

# 查看订单簿与实时价格
polymarket book <token_id>
polymarket price <token_id>

# 备选数据源查询（当Gamma API不可用时）
polymarket alt-search "Bitcoin"
polymarket alt crude-oil

# 路由器管理
polymarket router status
polymarket router stats
```

CLI工具: `scripts/wrapper.js`（双模引擎——首选Python Router，不可用时降级Direct API），
通过 `node scripts/wrapper.js <command>` 运行。

## 命令

### 基本命令

| 命令 | 短别名 | 描述 |
|------|--------|------|
| `search <query>` | `s` | 关键词搜索市场（推荐） |
| `events [options]` | `e` | 列出活跃事件 |
| `market <slug>` | `m` | 获取市场详情及当前赔率 |
| `sports` | — | 列出体育联赛/系列赛 |
| `tags` | `t` | 列出可用分类 |
| `price <token_id> [buy\|sell]` | `p` | 获取代币当前价格（CLOB API） |
| `book <token_id>` | `b` | 获取订单簿深度（CLOB API） |

### 备选数据源命令

| 命令 | 描述 |
|------|------|
| `alt-search <query>` | 备选数据源搜索 |
| `alt <asset>` | 备选资产查询 (crude-oil\|gold\|silver) |

### 路由器管理命令

| 命令 | 描述 |
|------|------|
| `router status` | 查看路由器状态 |
| `router test <query>` | 测试路由器功能 |
| `router stats` | 查看性能统计 |
| `router config` | 查看配置信息 |

### 诊断和调试命令

| 命令 | 描述 |
|------|------|
| `diagnose` | 运行完整诊断（网络、代理、Python环境） |
| `test-proxy [proxy_url]` | 测试代理连接 |

## 事件选项

- `--tag=<slug>` — 按类别筛选（crypto, politics, sports等）
- `--limit=<n>` — 最大结果数（默认20）
- `--series=<id>` — 按联赛筛选

## 理解赔率

Polymarket使用预测市场机制，价格直接反映市场共识概率：

| 价格 | 含义 |
|------|------|
| **0.65** (65¢) | 市场认为该事件有 **65%** 的概率发生 |
| **0.10** (10¢) | 市场认为该事件有 **10%** 的概率发生 |
| **0.95** (95¢) | 市场认为该事件几乎确定会发生 |

- **成交量 (Volume)**：该市场总交易金额（美元）。高成交量 = 更多参与者 = 更可靠的价格信号
- **流动性 (Liquidity)**：订单簿中可立即成交的资金量。高流动性 = 大额交易不易滑点
- **结算规则**：事件发生后，正确预测者获得 **$1.00/份**，错误预测者获得 **$0.00/份**
- **真金白银优势**：与民意调查不同，参与者用真实资金下注，预测准确性通常高于传统民调

## ⚠️ 预测市场数据解析最佳实践（重要）

### 商品价格预测市场的特殊性

对于黄金、白银、原油等商品价格预测市场，必须严格区分以下概念：

#### 1. 当前现货价格 vs 预测目标价格
- **当前现货价格**：资产在当前时刻的实际市场价格（如黄金$4,013.9/盎司）
- **预测目标价格**：预测市场中事件定义的价格目标（如"黄金能否在年底前触及$5,000"）
- **常见错误**：将预测目标价格错误地报告为"当前价格"

#### 2. 预测市场概率的含义
- **概率0-100%**：表示市场认为事件发生的可能性
- **价格目标**：是事件定义的一部分，不是当前价格
- **示例**：黄金预测市场显示"触及$5,000概率100%"意味着市场认为黄金几乎肯定会涨到$5,000，而不是当前价格是$5,000

#### 3. 数据解析检查清单
在解析商品价格预测市场数据时，必须验证：
- [ ] 是否明确区分了"当前价格"和"目标价格"
- [ ] 概率分布是否针对具体的价格目标
- [ ] 数据时间戳是否准确（预测时间范围）
- [ ] 是否与实时现货价格数据交叉验证

### 基于预测市场数据制定交易策略的原则

#### 1. 右侧交易铁律
- **绝对不能**因为预测市场显示高概率就建议交易
- **必须等待**右侧确认信号（价格行为确认、关键位突破等）
- **预测市场的概率**只描述市场预期，不提供入场时机

#### 2. 价格目标处理
- **不要**将预测目标价格直接作为交易目标
- **应该**基于当前价格和技术分析确定合理目标
- **预测目标**可作为长期参考，但不能直接用于交易策略

#### 3. 风险管理要求
任何基于预测市场数据的交易建议必须包含：
- 明确的止损位（基于技术分析）
- 合理的盈亏比（至少1:1.5）
- 仓位控制建议（基于波动率）
- 风险对冲方案

### 常见错误和陷阱

#### 错误1：价格概念混淆
- **错误**：报告"黄金当前价格$5,000"（实际是预测目标）
- **正确**：报告"黄金当前价格$4,013.9，预测市场显示100%概率触及$5,000目标"

#### 错误2：概率误解
- **错误**："预测市场显示黄金将达到$5,000"
- **正确**："预测市场显示黄金有100%概率在年底前触及$5,000"

#### 错误3：策略制定错误
- **错误**："黄金突破$5,000后加仓"（将目标价格作为突破点）
- **正确**："黄金突破$4,114阻力位后右侧入场，目标$5,000"

#### 错误4：忽略时间维度
- **错误**：未说明预测的时间范围
- **正确**："预测市场显示黄金在6月底前触及$5,000的概率为100%"

### 数据验证流程

1. **获取预测市场数据**：使用CLI工具查询目标价格概率
2. **获取实时现货价格**：从权威数据源获取当前市场价格
3. **交叉验证**：确保预测目标价格与当前价格有合理差距
4. **时间戳确认**：验证数据获取时间和预测时间范围
5. **策略制定**：基于右侧交易原则，结合技术分析制定策略

### 示例：正确的数据解析

**错误解析**：
```
黄金当前价格：$5,079.3
预测：触及$5,000概率100%
策略：等待$5,000突破确认
```

**正确解析**：
```
黄金当前价格：$4,013.9（现货XAU/USD）
预测市场：触及$5,000目标概率100%
策略：观望等待，关注$4,114阻力位突破确认
止损：$3,814下方
目标：$5,000
```

## 单项赛事博彩

Polymarket提供丰富的单项赛事市场（NFL, NBA, 足球, 网球等）。

```bash
# 足球 — 队名加 "FC" 后缀
polymarket search "Arsenal FC"
polymarket search "Manchester United FC"
polymarket search "Liverpool FC"

# NFL/NBA — 直接用队名
polymarket search "Patriots"
polymarket search "Chiefs"
polymarket search "Lakers"

# 按联赛浏览
polymarket events --tag=sports --limit=20
```

**市场类型**：
- **胜平负 (Moneyline)**：Win / Draw / Lose 概率
- **让分盘 (Spreads)**：如 Arsenal -1.5
- **大小球 (Totals)**：Over/Under 2.5 球
- **双方进球 (BTTS)**：Both Teams to Score (Yes/No)

## 双模引擎说明

wrapper.js 采用自动降级策略：

```
用户请求
    ↓
首选: Python SmartRouter (多源路由 + 故障转移 + 缓存)
    ↓ 失败
降级: Node.js Direct API (零依赖，直连Gamma/CLOB)
```

- **Python Router 模式**：需 Python 环境 + requirements.txt 依赖，支持多源路由、健康检查、本地缓存
- **Direct API 模式**：仅需 Node.js（>=18），零外部依赖，使用原生 `fetch` 直连 Polymarket API
- 降级时会自动打印 `⚠️ Python Router 不可用，降级为 Direct API 模式` 提示

## 多源数据集成路由系统

### 数据源优先级

| 优先级 | 数据源 | 类型 | 状态 |
|--------|--------|------|------|
| 1 | **gamma-api** — Polymarket Gamma API | API | 主要 |
| 2 | **clob-api** — Polymarket CLOB API | API | 备用 |
| 3 | **polyspotter** — PolySpotter Web | Web | 备用 |
| 4 | **polymarketanalytics** — Analytics | Web | 备用 |
| 10 | **local-cache** — 本地缓存 | Cache | 最后手段 |

### 故障转移行为

1. 首先尝试主要数据源 (gamma-api)
2. 如失败，自动切换下一可用数据源
3. 全部失败时，使用本地缓存数据
4. 记录失败原因和切换历史

### 配置文件

`config/config.yaml` (或 `config_example.yaml`):

```yaml
router:
  default_timeout: 10000   # 默认超时(ms)
  max_retries: 3           # 最大重试次数
  cache_ttl: 300           # 缓存TTL(秒)
```

## API 参考

CLI使用的公开端点（无需认证）：

| 端点 | 用途 |
|------|------|
| `GET /public-search?q=<query>` | 关键词搜索市场 |
| `GET /events?active=true&closed=false` | 列出活跃事件 |
| `GET /markets?slug=<slug>` | 按slug获取市场详情 |
| `GET /tags` | 列出可用分类 |
| `GET /sports` | 列出体育联赛 |
| `GET /price?token_id=<id>&side=buy` | 获取代币价格 (CLOB) |
| `GET /book?token_id=<id>` | 获取订单簿深度 (CLOB) |

- **Gamma API** 基础URL: `https://gamma-api.polymarket.com`
- **CLOB API** 基础URL: `https://clob.polymarket.com`

## Python 集成

```python
from polymarket_router.router import SmartRouter
from polymarket_router.source_manager import SourceManager

manager = SourceManager()
router  = SmartRouter(manager)
result  = router.execute_request_sync(DataRequest(query="Bitcoin"))
```

## 文件结构

```
polymarket-router/
├── SKILL.md                     # 技能定义
├── _user_meta.json              # 元数据
├── requirements.txt             # Python依赖
├── .gitignore                   # Git忽略规则
├── scripts/                     # 可执行脚本
│   ├── polymarket_router/       # Python 包
│   │   ├── __init__.py
│   │   ├── router.py            # 智能路由引擎
│   │   ├── source_manager.py    # 数据源管理
│   │   └── discovery.py         # 动态发现
│   ├── router_client.py         # Python 客户端
│   ├── setup.py                 # 安装脚本
│   └── wrapper.js               # Node.js CLI (双模引擎)
├── tests/                       # 测试文件
│   ├── test_router.py           # 路由测试
│   ├── test_html_structure.py   # HTML结构测试
│   └── test_real_connectors.py  # 连接器测试
├── config/                      # 配置文件
│   ├── config.yaml              # 运行配置
│   └── config_example.yaml      # 配置模板
├── data/                        # 数据文件
├── references/                  # 参考文档
│   ├── README.md                # 项目文档
│   └── CLAUDE.md                # AI辅助文档
├── docs/                        # 文档
├── examples/                    # 使用示例
│   └── usage_example.py
└── assets/                      # 资源文件
```

## 常见分类

| 分类 | 可用市场 |
|------|---------|
| `sports` | NFL, NBA, 足球, 网球等 |
| `politics` | 选举, 立法, 人事任命 |
| `crypto` | 价格目标, ETF, 法规 |
| `business` | IPO, 收购, 财报 |
| `tech` | 产品发布, AI发展 |

## 报告生成指南

### 商品价格预测市场报告结构

当生成包含商品价格预测市场的报告时，必须遵循以下结构：

#### 1. 数据部分
- **当前现货价格**：必须从权威数据源获取（如BullionMarketCap、Kitco等）
- **预测市场概率**：明确标注为目标价格的概率分布
- **数据时间戳**：明确标注数据获取时间和预测时间范围

#### 2. 分析部分
- **概率解读**：解释预测市场概率的含义
- **风险提示**：指出预测市场的不确定性
- **相关性分析**：如有多个相关市场，分析其相关性

#### 3. 策略部分
- **基于右侧交易原则**：等待确认信号，不预测底部或顶部
- **明确风险管理**：止损、目标、仓位控制
- **时间框架**：明确策略的时间范围

### 报告模板示例

```markdown
# 商品价格预测市场报告

## 数据概览
- **当前现货价格**：$X,XXX.XX（来源：XXX，时间：YYYY-MM-DD HH:MM）
- **预测市场概览**：[市场名称]显示[概率]%概率触及$X,XXX目标

## 预测市场分析
### 目标价格概率分布
- 触及$X,XXX：XX%
- 触及$X,XXX：XX%
- 触及$X,XXX：XX%

### 市场情绪解读
[解释预测市场概率的含义，区分当前价格和目标价格]

## 交易策略建议
### 策略1：[策略名称]
- **入场条件**：等待[具体技术条件]确认
- **止损**：$X,XXX（基于[技术分析依据]）
- **目标**：$X,XXX（基于[分析依据]）
- **仓位**：[具体建议]（基于[波动率/风险分析]）

### 风险管理
- [具体风险对冲建议]
- [仓位控制建议]
```

### 自动化报告生成检查清单

在生成自动化报告前，必须验证：

1. **数据准确性**
   - [ ] 当前现货价格已从权威数据源验证
   - [ ] 预测市场概率与原始数据一致
   - [ ] 数据时间戳准确

2. **概念清晰度**
   - [ ] 明确区分"当前价格"和"目标价格"
   - [ ] 概率解释准确无误
   - [ ] 时间范围明确标注

3. **策略合理性**
   - [ ] 遵循右侧交易原则
   - [ ] 包含完整的风险管理
   - [ ] 基于技术分析而非单纯预测

4. **格式规范**
   - [ ] 使用统一的货币格式（如$X,XXX.XX）
   - [ ] 包含必要的免责声明
   - [ ] 数据来源明确标注

## 限制与注意事项

- Python Router 故障转移增加少量延迟（通常<1秒）
- Direct API 降级模式零依赖，但无多源路由和缓存
- 缓存数据可能略有延迟
- 动态发现的新数据源需验证可靠性
- 网络受限时可使用 `alt-search` 访问PolySpotter备选源
- 真金白银市场的预测通常比传统民意调查更准确

## 商品价格预测市场常见错误

### 错误类型1：价格数据解析错误

#### 问题描述
将预测市场的目标价格错误地映射为当前现货价格。

#### 错误示例
```
黄金当前价格：$5,079.3  # 错误：这是预测目标价格
白银当前价格：$113.24   # 错误：这是预测目标价格
```

#### 正确做法
1. **分离数据源**：预测市场数据和现货价格数据应从不同来源获取
2. **交叉验证**：将预测目标价格与实时现货价格对比
3. **明确标注**：在报告中明确区分两种价格

#### 修复方案
```python
# 错误代码
current_price = market_data['price']  # 可能是目标价格

# 正确代码
current_price = get_spot_price(symbol)  # 从权威数据源获取
target_price = market_data['target']    # 预测目标价格
probability = market_data['probability']  # 达到目标的概率
```

### 错误类型2：交易策略制定错误

#### 问题描述
基于预测目标价格制定交易策略，未遵循右侧交易原则。

#### 错误示例
```
策略：等待$5,000突破确认后加仓  # 错误：将目标价格作为突破点
策略：在$70支撑位附近轻仓做多  # 错误：未等待右侧确认信号
```

#### 正确做法
1. **基于当前价格分析**：使用当前价格进行技术分析
2. **等待右侧确认**：等待价格行为确认后再制定策略
3. **明确风险管理**：包含止损、目标、仓位控制

#### 修复方案
```python
# 错误策略
if current_price >= target_price:
    action = "加仓"

# 正确策略
if current_price >= resistance_level and confirmed_breakout:
    action = "右侧入场"
    stop_loss = calculate_stop_loss(current_price)
    target = calculate_target(current_price, risk_reward_ratio)
```

### 错误类型3：时间维度忽略

#### 问题描述
未明确预测市场的时间范围，导致策略时间框架混乱。

#### 错误示例
```
预测：黄金将触及$5,000  # 错误：未说明时间范围
```

#### 正确做法
1. **明确时间范围**：在报告中明确标注预测的时间范围
2. **策略时间框架**：交易策略应与预测时间范围一致
3. **动态调整**：根据时间推移调整策略

#### 修复方案
```python
# 错误表述
prediction = "黄金将触及$5,000"

# 正确表述
prediction = "预测市场显示黄金在6月底前触及$5,000的概率为100%"
time_horizon = "6月底前"
```

### 错误类型4：概率误解

#### 问题描述
误解预测市场概率的含义，将其作为确定性预测。

#### 错误示例
```
预测市场显示黄金将达到$5,000  # 错误：概率不是确定性
```

#### 正确做法
1. **概率解释**：明确说明概率是市场预期，不是确定性
2. **风险提示**：指出即使高概率事件也可能不发生
3. **情景分析**：考虑不同概率情景下的策略

#### 修复方案
```python
# 错误表述
if probability > 90:
    prediction = "黄金将达到目标价格"

# 正确表述
if probability > 90:
    prediction = f"市场预期黄金有{probability}%概率触及目标价格"
    risk_note = "但需注意，即使高概率事件也可能不发生"
```

### 错误类型5：数据源混淆

#### 问题描述
混淆预测市场数据和现货价格数据来源。

#### 错误示例
```
数据来源：Polymarket  # 错误：Polymarket提供预测概率，不是现货价格
```

#### 正确做法
1. **分离数据源**：明确标注不同数据的来源
2. **权威验证**：现货价格应从权威金融数据源获取
3. **时间同步**：确保不同数据源的时间一致性

#### 修复方案
```python
# 错误代码
data_source = "Polymarket"
current_price = data['price']  # 可能来自预测市场

# 正确代码
prediction_data = get_polymarket_data(query)
current_price = get_spot_price_from权威源(symbol)
```

### 错误预防检查清单

在生成商品价格预测市场报告前，必须验证：

1. **数据准确性**
   - [ ] 当前现货价格已从权威数据源验证
   - [ ] 预测市场概率与原始数据一致
   - [ ] 数据时间戳准确且一致

2. **概念清晰度**
   - [ ] 明确区分"当前价格"和"目标价格"
   - [ ] 概率解释准确无误
   - [ ] 时间范围明确标注

3. **策略合理性**
   - [ ] 遵循右侧交易原则
   - [ ] 包含完整的风险管理
   - [ ] 基于技术分析而非单纯预测

4. **格式规范**
   - [ ] 使用统一的货币格式
   - [ ] 包含必要的免责声明
   - [ ] 数据来源明确标注

## 错误处理与故障排除

### 常见错误及解决方案

#### 1. 网络连接失败
**错误信息**: `fetch failed` 或 `ECONNREFUSED`

**可能原因**:
- 网络连接中断
- 防火墙阻止连接
- 需要配置代理

**解决方案**:
```bash
# 1. 检查网络连接
node wrapper.js diagnose

# 2. 配置代理（如果需要）
export HTTPS_PROXY=http://proxy:port
export HTTP_PROXY=http://proxy:port

# 3. 测试代理连接
node wrapper.js test-proxy http://proxy:port

# 4. 使用备选数据源
node wrapper.js alt-search "Bitcoin"
```

#### 2. 请求超时
**错误信息**: `timeout` 或 `ETIMEDOUT`

**可能原因**:
- 网络延迟过高
- 服务器响应慢
- 代理服务器问题

**解决方案**:
```bash
# 1. 稍后重试
# 2. 检查网络质量
# 3. 尝试其他数据源
node wrapper.js alt-search "query"
```

#### 3. HTTP 429 错误（请求过于频繁）
**错误信息**: `HTTP 429: Too Many Requests`

**解决方案**:
```bash
# 1. 等待1-2分钟后重试
# 2. 减少请求频率
# 3. 使用缓存机制（路由器自动处理）
```

#### 4. HTTP 403 错误（访问被拒绝）
**错误信息**: `HTTP 403: Forbidden`

**可能原因**:
- 需要认证
- IP被限制
- 需要代理

**解决方案**:
```bash
# 1. 尝试使用代理
export HTTPS_PROXY=http://proxy:port

# 2. 使用备选数据源
node wrapper.js alt-search "query"

# 3. 联系数据源管理员
```

#### 5. Python环境问题
**错误信息**: Python相关错误

**解决方案**:
```bash
# 1. 检查Python环境
node wrapper.js diagnose

# 2. 安装Python依赖
pip install -r requirements.txt

# 3. 使用Direct API模式（自动降级）
# 系统会自动使用Node.js Direct API模式
```

#### 6. 数据解析失败
**错误信息**: JSON解析错误

**可能原因**:
- 数据源返回格式错误
- 网络传输中断
- 数据源临时故障

**解决方案**:
```bash
# 1. 稍后重试
# 2. 使用diagnose命令检查数据源状态
node wrapper.js diagnose

# 3. 尝试其他数据源
node wrapper.js alt-search "query"
```

### 诊断工具

#### 完整诊断
```bash
node wrapper.js diagnose
```
该命令会检查：
- 网络连接状态
- 代理设置
- Python环境
- 数据源可达性

#### 代理测试
```bash
# 测试配置的代理
node wrapper.js test-proxy

# 测试指定代理
node wrapper.js test-proxy http://proxy:port
```

### 代理配置

#### 环境变量方式
```bash
# Linux/macOS
export HTTPS_PROXY=http://proxy:port
export HTTP_PROXY=http://proxy:port

# Windows (PowerShell)
$env:HTTPS_PROXY="http://proxy:port"
$env:HTTP_PROXY="http://proxy:port"
```

#### 命令行参数方式
```bash
# 当前版本暂不支持命令行代理参数
# 请使用环境变量配置
```

### 网络受限环境

在中国大陆等网络受限环境下，Polymarket API可能不可达。

**解决方案**:
1. **配置代理**: 使用上述代理配置方法
2. **使用备选数据源**:
   ```bash
   node wrapper.js alt-search "Bitcoin"
   node wrapper.js alt crude-oil
   ```
3. **使用WebSearch**: 作为最后手段，可以从权威金融网站获取数据

### 性能优化

#### 缓存机制
路由器自动缓存查询结果，减少重复请求：
- 默认缓存TTL: 5分钟
- 缓存大小: 1000条记录
- 自动清理过期缓存

#### 并发控制
- 最大并发连接数: 20
- 连接池大小: 10
- 自动重试机制

### 调试模式

启用详细调试信息：
```bash
export DEBUG=1
node wrapper.js search "Bitcoin"
```

### 获取帮助

```bash
# 查看完整帮助
node wrapper.js

# 查看路由器状态
node wrapper.js router status

# 运行诊断
node wrapper.js diagnose
```

### 联系支持

如果以上方法都无法解决问题：
1. 运行诊断命令收集信息
2. 查看错误日志
3. 检查网络环境
4. 尝试在不同时间段重试
