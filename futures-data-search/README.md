# futures-data-search v4.0.0

国内期货数据统一调度中心 — **MultiSourceAdapter 多源自动降级 + 通达信本地低延迟**

[![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-79%20varieties-green.svg)]()
[![Records](https://img.shields.io/badge/records-12.8K%20history-orange.svg)]()

---

## 数据源优先级

| 优先级 | 盘中链 (09-15 / 21-23) | 盘后链 (15-21) |
|:------:|:----------------------|:---------------|
| **0**（最高） | **通达信本地** — 本地HTTP JSON-RPC零延迟 | **通达信本地** |
| 1 | TqSDK — 天勤量化实时行情 | 东方财富 |
| 2 | 东方财富 — 公开HTTP实时快照 | 交易所API |
| 3 | 交易所API — DCE/SHFE/CZCE/CFFEX/GFEX | TqSDK |
| 4 | AKShare → WebSearch → Cache | AKShare → WebSearch → Cache |

> **数据置信度统一 1.0**：所有数据源均为交易所实盘数据，不存在可信度差异。
> 信号置信度由上游 skill（commodity-trend-signal）独立计算。

## 核心架构

```
MultiSourceAdapter（统一调度入口）
├── get_quote()    → 通达信本地(最高) → TqSDK → 东方财富 → 交易所API → AKShare
├── get_kline()    → 同上，自动降级（动态合约月代码，多代码试错）
├── get_term_structure() → 东方财富一次HTTP完成（0.1s）
└── tdx_collector  → 调用通达信本地HTTP服务（127.0.0.1:17709）

DuckDB 持久化层
├── 12,800+ 条历史K线
├── 67 个主力品种（每品种 170-250 天）
├── 740+ 总品种
└── 日期覆盖 2025-06 ~ 至今
```

## 依赖

```bash
# 基础依赖（必需）
pip install duckdb requests pandas pyyaml

# 可选依赖（降级数据源）
pip install akshare          # AKShare 开源数据
pip install tqsdk            # 天勤量化实时行情
```

## 快速开始

```python
from scripts.multi_source_adapter import MultiSourceAdapter

adapter = MultiSourceAdapter()

# 自动按优先级获取（通达信→TqSDK→东财→交易所→AKShare）
quote = adapter.get_quote('CU')         # 实时行情快照
kline = adapter.get_kline('RB', 365)    # 一年K线
ts    = adapter.get_term_structure('CU') # 期限结构
```

## 交易所覆盖

| 交易所 | 品种数 | 代表品种 |
|:-------|:------:|:---------|
| 上期所（SHFE） | 20 | CU, AU, RB, AG, NI, SN, AL, ZN |
| 大商所（DCE） | 22 | I, M, J, JM, PG, L, V, PP, EG, EB |
| 郑商所（CZCE） | 25 | TA, MA, FG, SA, CF, RM, SR, PF, PX |
| 广期所（GFEX） | 4 | SI, LC, PS |
| 上期能源（INE） | 5 | SC, LU, NR, BC, EC |
| 中金所（CFFEX） | 8 | IF, IH, IC, IM, T, TF, TS, TL |
| **合计** | **78** | 六大交易所全覆盖 |

## 目录结构

```
futures-data-search/
├── SKILL.md                        # 主技能定义
├── README.md                       # 本文档
├── USER_GUIDE.md                   # 用户使用手册
├── references/
│   ├── varieties.yaml              # 品种词典（79品种，150+别名）
│   └── data_sources.yaml           # 数据源优先级配置（盘中/盘后）
├── collectors/
│   ├── tdx_collector.py            # 通达信本地HTTP采集器（优先）
│   ├── eastmoney_collector.py      # 东方财富公开数据采集
│   ├── exchange_data/              # 交易所API采集器（内置）
│   └── ...                         # 其他采集器
├── scripts/
│   ├── multi_source_adapter.py     # 多源数据适配器（7级降级）
│   ├── data_source_config.py       # 数据源配置加载器
│   ├── correct_duckdb_with_tdx.py  # DuckDB数据修正脚本
│   ├── duckdb_store.py             # DuckDB存储引擎
│   ├── dominant_mapping.py         # 主力映射算法
│   └── ...                         # 其他脚本
└── data/
    └── dominant_maps/              # 主力映射表（每日更新）
```

## 版本历史

### v4.0.0 (2026-06-29)
- 新增通达信本地TQ-Local HTTP数据源（最高优先级，priority=0）
- 重写 tdx_collector：动态合约月份代码生成 + 多代码自动试错
- 东方财富新增 get_term_structure() 接口（0.1s计算期限结构）
- DuckDB 全面修正：12,800+ 条历史K线（从5天扩展到~1年）
- 数据置信度统一为 1.0（移除差异化置信度）
- 大小写/乱码数据清理完成

### v3.0.0 (2026-06-28)
- 合并 exchange-futures-data v3.2 为内置采集器
- 存储引擎迁移至 DuckDB（零部署，单文件便携）
- 多源适配器直接调用本地采集器

## 开发计划

- [x] 通达信本地低延迟数据源
- [x] DuckDB 历史数据全面修正
- [x] 东方财富期限结构计算
- [x] 数据置信度统一（移除差异化）
- [x] 全交易所主力映射覆盖（66/79 品种）
- [ ] 主力映射：补齐 CZCE 冷门品种（P2）
- [ ] 分钟级行情查询
- [ ] 资金流向查询
