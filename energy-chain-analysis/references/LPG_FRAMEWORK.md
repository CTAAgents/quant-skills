# 液化石油气（LPG/PG）完整分析框架 v2.14.0

> **核心定位**：LPG是油气田伴生或炼厂裂解副产物，**丙烷+丁烷混合**，分民用燃料（ domestic）和化工原料（petrochemical）两大需求；**LPG作为独立分析模块，不参与原油系顶层加权**，拥有独立的五层分析框架。

---

## 一句话精简复盘口诀

> **CP定锚、成本跟随、进口调节、民用季节强、化工利润狂、库存低位涨。**

---

## 整体架构

**外部市场（CP成本） → 国内供应 → 终端需求（民用+化工） → 库存+区域价差 → 政策与市场结构**，国际油价与丙烷脱氢（PDH）利润作为核心驱动。

> **定位**：LPG是独立品种，**CP（沙特丙烷合同价）定外盘锚**，国内进口量调节供需，PDH利润决定化工需求强弱。

---

## 一、第一层：外部市场与成本（行情大方向，占25%权重）

### 1. CP（沙特合同价）是LPG全球定价锚

```
CP丙烷 = 沙特阿美月度合同价（美元/吨）
CP丁烷 = 沙特阿美丁烷合同价（美元/吨）
```

| 指标 | 说明 | 影响 |
|------|------|------|
| CP丙烷 | 亚洲进口主导定价 | 美元计价，汇率传导 |
| CP丁烷 | 燃烧用途定价 | 与丙烷联动 |
| FEI（远东指数） | 现货价指数 | 日度参考 |
| MB（MB价格） | 美国出口FOB | 国际联动 |

### 2. 进口成本公式

```
进口完税成本 = CP价格 × 汇率 × 损耗系数 + 码头费用 + 仓储费
```

- 美元走强→人民币贬值→LPG进口成本抬升
- CP大涨→国内LPG被动跟涨

### 3. 与原油的关联

| 关联度 | 时期 | 说明 |
|--------|------|------|
| 60%~70% | 正常时期 | 油价→CP→LPG |
| 80%+ | 油气田增产期 | 丙烷作为伴生气大量产出 |
| 40%~50% | PDH高利润期 | 化工需求主导 |

---

## 二、第二层：国内供应（产量与进口）

### 1. 供应来源

| 供应来源 | 占比 | 说明 |
|---------|------|------|
| 炼厂副产 | ~50% | 催化裂化/延迟焦化副产 |
| 油气田伴生 | ~20% | 西部气田 |
| 进口 | ~30% | 中东+美国（PDH原料） |
| 国产轻烃 | ~10% | 轻烃综合利用 |

### 2. 供应关键指标

| 指标 | 数据频率 | 计分规则 |
|------|---------|---------|
| 国内LPG产量 | 月度 | 同比增速：增产=供应增加=反向 |
| 进口量 | 月度 | 进口大增=供应宽松=反向 |
| 进口依存度 | 月度 | 越高越受CP影响 |
| 炼厂开工率 | 周度 | 高开工=副产LPG增多 |
| PDH开工率 | 周度 | PDH需求端指标 |

---

## 三、第三层：终端需求（民用+化工）

### 1. 两类需求去向

| 需求类型 | 占比 | 时间特征 | 驱动逻辑 |
|---------|------|---------|---------|
| 民用燃料（燃烧） | ~55% | 强季节性 | 冬季取暖旺季 |
| 化工原料（PDH） | ~45% | 利润驱动 | 丙烯→PP产业链 |

### 2. 民用燃料需求

| 指标 | 数据频率 | 计分规则 |
|------|---------|---------|
| 民用LPG消费 | 月度 | 冬季增加=需求增加=正向 |
| 气温（北半球） | 周度 | 冬季低温=取暖需求增加=正向 |
| 城市燃气消费 | 月度 | 煤改气推进=需求增加 |

### 3. 化工原料需求（PDH利润）

PDH（丙烷脱氢制丙烯）是LPG化工需求核心：

| 指标 | 数据频率 | 计分规则 |
|------|---------|---------|
| PDH利润 | 周度 | 高利润=PDH开工积极=LPG需求增加 |
| PDH开工率 | 周度 | 高开工=LPG消耗增加 |
| 丙烯价格 | 周度 | 丙烯涨=PDH利润修复 |
| PP（聚丙烯）价格 | 周度 | PP涨=需求好=丙烯需求好 |

**PDH利润公式**：
```
PDH利润 = 丙烯价格 - CP丙烷价格 × 汇率 - 加工成本
```

| PDH利润区间 | 市场状态 | LPG需求 |
|------------|---------|--------|
| >500元/吨 | 高利润 | PDH满负荷，LPG需求强 |
| 200~500元/吨 | 正常利润 | 需求平稳 |
| <200元/吨 | 低利润 | PDH降负，LPG需求弱 |
| <0元/吨 | 亏损 | PDH停工，LPG需求崩塌 |

---

## 四、第四层：库存与区域价差

### 1. 库存指标

| 指标 | 数据频率 | 计分规则 |
|------|---------|---------|
| 华东LPG库存 | 周度 | 反向：库存高位=供应宽松=利空 |
| 华南LPG库存 | 周度 | 反向：库存低位=供应紧张=利多 |
| 港口库存 | 周度 | 进口码头库存 |
| 丙烷仓单 | 日度 | 上期所PG仓单 |

### 2. 区域价差

| 价差类型 | 计算公式 | 正常区间 | 交易信号 |
|---------|---------|---------|---------|
| 华东-华南价差 | 华东价 - 华南价 | ±100元/吨 | 极端值=跨区套利 |
| 国产-进口价差 | 国产价 - 进口成本 | 0~300元/吨 | 国产优势区间 |
| 丙烷-丁烷价差 | CP丙烷 - CP丁烷 | 0~50美元/吨 | 品种间套利 |

---

## 五、第五层：政策与市场结构

### 1. 政策变量

| 政策类型 | 影响逻辑 | 量化赋值 |
|---------|---------|---------|
| 煤改气政策 | 燃气替代→LPG民用减少 | 推进=-10 |
| 进口配额政策 | 进口限制→供应收紧 | 收紧=+8 |
| 能源安全政策 | 储备需求增加 | 增加=+5 |
| 化工园区政策 | PDH项目审批 | 新增=+5 |

### 2. 市场结构指标

| 指标 | 计算方式 | 计分规则 |
|------|---------|---------|
| 基差 | 现货-期货 | 正基差=现货紧=利多 |
| 月差 | 近月-远月 | Back=利多 |
| 跨品种价差 | LPG/原油比 | 历史分位 |

---

## 六、LPG五层量化打分框架

### 6.1 顶层权重总表

| 模块编号 | 模块名称 | 顶层总权重 | 核心定位 |
|----------|----------|------------|----------|
| 模块1 | 外部市场与成本 | 25% | 定价格外盘锚，成本方向 |
| 模块2 | 国内供应 | 20% | 定供应端边际变化 |
| 模块3 | 终端需求 | 30% | 定需求方向，核心驱动（民用+化工） |
| 模块4 | 库存与区域价差 | 15% | 定库存压力与套利机会 |
| 模块5 | 政策与市场结构 | 10% | 定独立行情与入场择时 |

### 6.2 全指标量化建模明细表

| 模块 | 指标编号 | 指标名称 | 数据频率 | 模块内权重 | 顶层权重 | 多空阈值 |
|------|---------|---------|----------|------------|----------|----------|
| **模块1 外部市场与成本（25%）** | 1.1 | CP丙烷20日涨跌幅分位 | 月度 | 40% | 10% | >60利多,<40利空 |
| | 1.2 | CP丁烷20日涨跌幅分位 | 月度 | 25% | 6.25% | >60利多,<40利空 |
| | 1.3 | USDCNY汇率分位 | 日度 | 20% | 5% | >70利多,<30利空 |
| | 1.4 | FEI远东指数分位 | 日度 | 15% | 3.75% | >60利多,<40利空 |
| **模块2 国内供应（20%）** | 2.1 | 国内LPG产量同比分位 | 月度 | 35% | 7% | 反向：>60利空,<40利多 |
| | 2.2 | LPG进口量同比分位 | 月度 | 35% | 7% | 反向：>60利空,<40利多 |
| | 2.3 | 炼厂开工率分位 | 周度 | 30% | 6% | 正向：>60利多,<40利空 |
| **模块3 终端需求（30%）** | 3.1 | PDH利润分位 | 周度 | 35% | 10.5% | >60利多,<40利空 |
| | 3.2 | PDH开工率分位 | 周度 | 30% | 9% | >60利多,<40利空 |
| | 3.3 | 丙烯价格分位 | 周度 | 20% | 6% | >60利多,<40利空 |
| | 3.4 | 民用消费同比分位 | 月度 | 15% | 4.5% | >60利多,<40利空 |
| **模块4 库存与区域价差（15%）** | 4.1 | 华东库存分位 | 周度 | 40% | 6% | 反向：>60利空,<40利多 |
| | 4.2 | 华南库存分位 | 周度 | 35% | 5.25% | 反向：>60利空,<40利多 |
| | 4.3 | 华东-华南价差分位 | 周度 | 25% | 3.75% | 极端值=套利信号 |
| **模块5 政策与市场结构（10%）** | 5.1 | 煤改气政策变量 | 事件 | 30% | 3% | 推进=-10 |
| | 5.2 | 进口配额政策变量 | 事件 | 30% | 3% | 收紧=+8 |
| | 5.3 | 基差分位 | 日度 | 40% | 4% | 正基差=利多 |

### 6.3 综合得分合成公式

```
模块1得分 = 1.1×0.4 + 1.2×0.25 + 1.3×0.2 + 1.4×0.15
模块2得分 = 2.1×0.35 + 2.2×0.35 + 2.3×0.30
模块3得分 = 3.1×0.35 + 3.2×0.30 + 3.3×0.20 + 3.4×0.15
模块4得分 = 4.1×0.40 + 4.2×0.35 + 4.3×0.25
模块5得分 = 5.1×0.3 + 5.2×0.3 + 5.3×0.4

总得分 = 模块1×0.25 + 模块2×0.20 + 模块3×0.30 + 模块4×0.15 + 模块5×0.10
```

### 6.4 交易信号规则

| 总得分区间 | 交易信号 | 操作建议 |
|------------|----------|----------|
| >65 | 多头区间 | 顺势开多，回落至60分止盈离场 |
| 35~65 | 震荡中性 | 观望为主，仅做跨品种套利 |
| <35 | 空头区间 | 顺势开空，回升至40分止损离场 |

---

## 七、季节性规律

| 时间区间 | 季节性调整 | 说明 |
|---------|-----------|------|
| 11月~次年3月 | +10分 | 冬季取暖，民用需求旺季 |
| 4~5月 | 0分 | 淡旺季过渡 |
| 6~10月 | -5分 | 夏季燃烧需求淡季 |
| 9~10月 | +5分 | 双节备货小高峰 |

---

## 八、常用套利逻辑

### 1. 跨品种套利：LPG-原油

| 市场状态 | 策略 | 逻辑 |
|---------|------|------|
| LPG/原油比低位 | 多LPG空原油 | LPG相对低估 |
| LPG/原油比高位 | 空LPG多原油 | LPG相对高估 |

### 2. 跨品种套利：LPG-PP

| 市场状态 | 策略 | 逻辑 |
|---------|------|------|
| PDH利润高位 | 多LPG空PP | PDH需求强 |
| PDH利润低位 | 空LPG多PP | PDH需求弱 |

### 3. 跨区套利

| 价差状态 | 策略 |
|---------|------|
| 华东-华南价差>150 | 卖华东买华南 |
| 华东-华南价差<-100 | 买华东卖华南 |

### 4. 丙烷-丁烷套利

根据CP丙烷-CP丁烷价差偏离历史均值做回归交易。

---

## 九、Python计算代码

### 9.1 LPG打分器核心代码

```python
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional

@dataclass
class LPGScore:
    """LPG综合打分结果"""
    total_score: float  # 总分 0-100
    external_score: float  # 外部市场与成本
    supply_score: float    # 国内供应
    demand_score: float    # 终端需求
    inventory_score: float # 库存与区域价差
    policy_score: float   # 政策与市场结构
    signal: str  # 信号：多头/震荡/空头

class LPGScorer:
    """LPG五层量化打分器"""
    
    # 顶层权重
    WEIGHTS = {
        'external': 0.25,
        'supply': 0.20,
        'demand': 0.30,
        'inventory': 0.15,
        'policy': 0.10
    }
    
    def __init__(self):
        self.data = {}
    
    def standard_score(self, x: pd.Series, window=365*3, 
                       is_forward: bool = True) -> pd.Series:
        """标准化得分：近3年滚动分位"""
        roll_min = x.rolling(window=window, min_periods=30).min()
        roll_max = x.rolling(window=window, min_periods=30).max()
        score = (x - roll_min) / (roll_max - roll_min + 1e-10) * 100
        if not is_forward:
            score = 100 - score
        return score.clip(0, 100)
    
    def calculate_external_score(self, cp_propane_chg: pd.Series,
                                 cp_butane_chg: pd.Series,
                                 usdcny: pd.Series,
                                 fei: pd.Series) -> float:
        """计算外部市场与成本因子得分"""
        s1 = self.standard_score(cp_propane_chg, is_forward=True)
        s2 = self.standard_score(cp_butane_chg, is_forward=True)
        s3 = self.standard_score(usdcny, is_forward=True)
        s4 = self.standard_score(fei, is_forward=True)
        return s1.iloc[-1] * 0.4 + s2.iloc[-1] * 0.25 + s3.iloc[-1] * 0.2 + s4.iloc[-1] * 0.15
    
    def calculate_supply_score(self, production_yoy: pd.Series,
                               import_yoy: pd.Series,
                               refinery_run: pd.Series) -> float:
        """计算国内供应因子得分"""
        s1 = self.standard_score(production_yoy, is_forward=False)
        s2 = self.standard_score(import_yoy, is_forward=False)
        s3 = self.standard_score(refinery_run, is_forward=True)
        return s1.iloc[-1] * 0.35 + s2.iloc[-1] * 0.35 + s3.iloc[-1] * 0.30
    
    def calculate_demand_score(self, pdh_margin: pd.Series,
                              pdh_run: pd.Series,
                              propylene_price: pd.Series,
                              domestic_consumption: pd.Series) -> float:
        """计算终端需求因子得分"""
        s1 = self.standard_score(pdh_margin, is_forward=True)
        s2 = self.standard_score(pdh_run, is_forward=True)
        s3 = self.standard_score(propylene_price, is_forward=True)
        s4 = self.standard_score(domestic_consumption, is_forward=True)
        return (s1.iloc[-1] * 0.35 + s2.iloc[-1] * 0.30 + 
                s3.iloc[-1] * 0.20 + s4.iloc[-1] * 0.15)
    
    def calculate_inventory_score(self, east_stock: pd.Series,
                                  south_stock: pd.Series,
                                  east_south_spread: pd.Series) -> float:
        """计算库存与区域价差因子得分"""
        s1 = self.standard_score(east_stock, is_forward=False)
        s2 = self.standard_score(south_stock, is_forward=False)
        s3 = self.standard_score(east_south_spread, is_forward=True)
        return s1.iloc[-1] * 0.40 + s2.iloc[-1] * 0.35 + s3.iloc[-1] * 0.25
    
    def calculate_policy_score(self, coal_to_gas: int,
                                import_quota: int,
                                basis: pd.Series) -> float:
        """计算政策与市场结构因子得分"""
        s = self.standard_score(basis, is_forward=True)
        return coal_to_gas * 0.3 + import_quota * 0.3 + s.iloc[-1] * 0.4
    
    def calculate_seasonal_adjustment(self, date: pd.Timestamp) -> float:
        """季节性调整"""
        month = date.month
        if month in [11, 12, 1, 2, 3]:
            return 10
        elif month in [9, 10]:
            return 5
        else:
            return -5
    
    def score(self, data: dict, date: Optional[pd.Timestamp] = None) -> LPGScore:
        """
        计算LPG综合打分
        
        data: dict, 包含以下键：
            - cp_propane_chg: CP丙烷20日涨跌幅
            - cp_butane_chg: CP丁烷20日涨跌幅
            - usdcny: 美元兑人民币
            - fei: FEI远东指数
            - production_yoy: LPG产量同比
            - import_yoy: LPG进口同比
            - refinery_run: 炼厂开工率
            - pdh_margin: PDH利润
            - pdh_run: PDH开工率
            - propylene_price: 丙烯价格
            - domestic_consumption: 民用消费同比
            - east_stock: 华东库存
            - south_stock: 华南库存
            - east_south_spread: 华东-华南价差
            - coal_to_gas: 煤改气政策（负值=推进）
            - import_quota: 进口配额政策（正值=收紧）
            - basis: 基差
        """
        external = self.calculate_external_score(
            data['cp_propane_chg'], data['cp_butane_chg'],
            data['usdcny'], data['fei'])
        
        supply = self.calculate_supply_score(
            data['production_yoy'], data['import_yoy'], data['refinery_run'])
        
        demand = self.calculate_demand_score(
            data['pdh_margin'], data['pdh_run'],
            data['propylene_price'], data['domestic_consumption'])
        
        inventory = self.calculate_inventory_score(
            data['east_stock'], data['south_stock'], data['east_south_spread'])
        
        policy = self.calculate_policy_score(
            data.get('coal_to_gas', 0), data.get('import_quota', 0),
            data['basis'])
        
        # 加权总分
        total = (external * self.WEIGHTS['external'] +
                supply * self.WEIGHTS['supply'] +
                demand * self.WEIGHTS['demand'] +
                inventory * self.WEIGHTS['inventory'] +
                policy * self.WEIGHTS['policy'])
        
        # 季节性调整
        if date is not None:
            seasonal_adj = self.calculate_seasonal_adjustment(date)
            total = (total * 10 + seasonal_adj) / 11
        
        # 信号判定
        if total > 65:
            signal = "多头"
        elif total < 35:
            signal = "空头"
        else:
            signal = "震荡"
        
        return LPGScore(
            total_score=round(total, 1),
            external_score=round(external, 1),
            supply_score=round(supply, 1),
            demand_score=round(demand, 1),
            inventory_score=round(inventory, 1),
            policy_score=round(policy, 1),
            signal=signal
        )
```

---

## 版本历史

### v1.0.0 (2026-06-03) — LPG框架初始版
- ⭐ **新增完整五层量化分析框架**：外部市场→国内供应→终端需求→库存区域价差→政策市场结构
- ⭐ **量化打分体系**：标准化0~100分，消除量纲
- ⭐ **综合公式**：加权合成强弱指数，总分>65做多，<35做空
- ⭐ **季节性量化**：11月~3月冬季+10分，6~10月夏季-5分
- ⭐ **PDH利润核心驱动**：PDH利润是化工需求核心指标
- ⭐ **完整建模汇总表**：全指标量化明细表、交易信号规则、Python代码
