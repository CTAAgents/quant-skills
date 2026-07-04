# quant-daily — 商品期货量化分析一体化

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-1.1.0-orange)

**quant-daily** 是一套面向中国商品期货市场的量化分析系统，覆盖 **数据采集 → 指标计算 → 趋势信号评分** 全流程。

- 覆盖 **62个主力品种**，14个板块（黑色、能源、聚酯、有色、贵金属、油脂油料等）
- 多源数据自动降级：`通达信TQ-Local → 东方财富 → 交易所API`
- **L1-L4四层打分** 100分制，识别趋势启动、主升/主跌阶段
- **真分层评分系统**（v1.1新增）：全品种截面排序 + 秩变换，消除方向预决偏见
- **Data Quality Circuit Breaker**：7道全局防呆机制保障数据可靠性
- 方向感知 Z-score 独立计算多空信号
- 内置 DuckDB 持久化存储，盘中盘后双优先采集链

## 架构总览

```
config/      →    data/         →    indicators/    →    signals/
(品种配置)      (多源数据采集)      (45项技术指标)      (L1-L4评分+交易计划)
```

单向依赖，每层职责单一，无循环引用。

## 快速开始

### 环境要求

- **操作系统**: Windows 10/11（通达信TQ-Local需Windows环境）
- **Python**: 3.10+
- **依赖**: numpy, pandas, duckdb, pyyaml, requests

### 安装

```bash
git clone https://github.com/CTAAgents/experts.git
cd experts/skills/quant-daily
pip install -e .
```

### 运行全品种扫描

```bash
# 全品种趋势信号扫描（JSON+HTML报告）
python scripts/scan_all.py

# 指定输出目录
python scripts/scan_all.py -o /path/to/output -p full_scan

# 自定义品种扫描
python scripts/scan_all.py --symbols PK,RB,B,UR
```

## 数据管道

### 三级指标获取管道

| 优先级 | 方式 | 说明 |
|:-----:|------|------|
| **1** | TdxCollector.get_indicators() | TQ-Local formula_zb 直取，44项指标 |
| **2** | tdx_bridge.patch_indicators() | 委托TdxCollector，35字段补丁 |
| **3** | calc_core.calculate_tdx_compatible() | numpy向量化，45字段（100%对齐通达信） |

### 数据质量熔断

| 防呆机制 | 规则 | 触发后果 |
|:---------|:----|:---------|
| 品种扫描成功率 | ≥90%（62品种中≥56成功） | 低于则终止评分 |
| 单品种K线条数 | ≥30条 | 不足则跳过评分 |
| 数据时效性 | 最新K线距运行日≤5交易日 | 超限标注"数据过期" |
| 成交量有效性 | volume>0占比≥50% | 标注"成交量数据质量差" |
| 扫描运行时间 | 全量≤120秒 | 超限终止 |
| 多源降级次数 | 单品种≤2次 | 超限标记"数据源耗尽" |
| 输出JSON大小 | ≤5MB | 超限裁剪低频字段 |

## 真分层评分系统（v1.1 新增）

基于 portfolio sort 学术方法，对全品种做截面排序 → 秩变换 → 等权汇总。

| 维度 | 假分层（原） | 真分层（新） |
|------|-------------|-------------|
| 打分方式 | 单品种阈值累加 | 全品种截面排序 → 秩变换 |
| 方向判断 | 先定方向再打分（方向预决） | 各因子独立裁判，不先定方向 |
| 冗余度容忍 | 不适用 | 高（秩空间天然降相关） |
| 极端值 | 硬阈值保留 | 秩变换拍平 |
| 可解释性 | "触发规则→得X分" | "在N个维度上的综合排名" |

```bash
# 运行真分层扫描
python scripts/scan_true_layered.py
python scripts/scan_true_layered.py --symbols PK,RB,B,UR
python scripts/scan_true_layered.py  
```

## 信号解读

### 评分等级

| 等级 | 分数区间 | 含义 |
|:----:|:--------:|------|
| **STRONG** | ≥ 75 | 趋势明确，可考虑建立仓位 |
| **WATCH** | 60–74 | 趋势初现，持续观察 |
| **WEAK** | 40–59 | 信号模糊，暂不介入 |
| **NOISE** | < 40 | 无有效信号 |

### L1-L4 权重配置

当前默认权重（2026-07-03 网格优化采纳，33组合×62品种，较Baseline WATCH+40%）：

| 层级 | 权重 | 核心因子 |
|:----:|:----:|---------|
| L1 — 萌芽/资金结构 | **35** | OI变化、基差、期限结构、ROC |
| L2 — 量价领先 | **35** | Vortex、CCI、Supertrend、HMA |
| L3 — 价格结构 | **20** | RSI健康区、DMI方向、突破 |
| L4 — 确认 | **10** | 通道突破、均线排列、MACD |

## 品种覆盖

| 板块 | 数量 | 品种 |
|:----|:----:|------|
| 黑色系 | 7 | rb, hc, i, j, jm, SF, SM |
| 能源链 | 6 | sc, lu, fu, bu, pg, PX |
| 聚酯链 | 5 | TA, PF, PR, eg, eb |
| 塑化链 | 4 | v, pp, l, MA |
| 化工 | 3 | SH, SA, UR |
| 有色金属 | 8 | cu, al, zn, pb, ni, sn, ao, SS |
| 贵金属 | 2 | au, ag |
| 油脂油料 | 8 | a, b, m, y, p, OI, RM, PK |
| 农产品 | 6 | c, cs, SR, CF, jd, lh |
| 建材化工 | 6 | FG, ru, nr, br, sp, op |
| 其他 | 7 | ap, CJ, lc, si, ps, ec, rr |
| **合计** | **62** | |

## 实用价值说明

当前评分系统定位为**品种筛选漏斗**和**结构化分析工具**，WATCH信号方向胜率约45-55%（接近随机基准），不适合直接下单。建议用途：

1. 日盘前自动扫描筛选候选品种
2. 作为辩论专家团的结构化输入（L1-L4分解维度）
3. 结合人工研判做最终决策

## 版本历史

- **v1.1.0** (2026-07-03): 权重优化(35/35/20/10)，新增真分层评分系统、Data Quality Circuit Breaker、回测框架
- **v1.0.1** (2026-07-03): 新增 `--symbols` 参数支持自定义品种扫描
- **v1.0.0** (2026-07-02): 初始版本，合并 futures-data-search + commodity-trend-signal + technical-indicator-calc

## 许可

本项目基于 MIT 许可证开源。详见 [LICENSE](LICENSE)。
