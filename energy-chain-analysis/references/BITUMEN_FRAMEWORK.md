# 沥青（BU）完整分析框架 v2.14.0

> **核心定位**：沥青是原油蒸馏后最重质的残渣产品，**原油定成本底座、道路需求定方向、季节性定节奏、区域价差定套利**；BU与SC相关性75%~85%，道路建设政策是独立驱动核心。

---

## 一句话精简复盘口诀

> **原油定底、需求定方向、季节节奏强、政策独立狂、区域价差套利忙。**

---

## 整体架构

**成本底座 → 供应端 → 需求端（道路建设） → 库存+区域价差 → 政策宏观 → 盘面结构**，季节性与政策作为外部修正项。

> **定位**：原油决定大方向（涨跌天花板/地板），**道路建设需求决定趋势节奏**，季节性与政策决定独立行情。

---

## 一、第一层：成本驱动（行情大方向，占价格40%权重）

沥青是原油蒸馏残渣，**布伦特/SC原油是成本底线**：

### 1. 成本公式（完税国内交割）

```
沥青完税成本 = 布伦特 × 汇率 × 桶吨换算 + 炼厂加工成本 + 运费
```

- 桶吨换算：原油1桶≈0.136吨，沥青密度约1.0~1.05吨/立方米
- 加工成本：约200~400元/吨（因炼厂类型不同）

### 2. 原油与沥青价格传导

| 原油变化 | 沥青响应 | 传导时滞 |
|---------|---------|---------|
| 原油大涨 | 沥青成本抬升 | 1~3个交易日 |
| 原油大跌 | 沥青成本下移 | 即时响应 |
| 原油震荡 | 沥青走独立需求逻辑 | 无传导 |

> **规律**：原油>70美元/桶时，沥青加工利润压缩，炼厂有挺价意愿；原油<50美元/桶时，沥青被动跟随。

### 3. 地缘与宏观传导

中东是全球重质原油核心出口国，霍尔木兹/红海扰动：

- **短期**：原油大涨+重质油紧张→沥青成本刚性抬升
- **中期**：宏观经济预期→道路施工计划→沥青需求

---

## 二、第二层：供应端（产量与进口，占价格20%权重）

### 1. 国内炼厂产出

| 供应来源 | 说明 | 影响 |
|---------|------|------|
| 中石化炼厂 | 加工重质原油，副产沥青 | 主力供应 |
| 中石油炼厂 | 东北/西北主力，沥青产出率高 | 季节性供应 |
| 地炼 | 山东、河北独立炼厂 | 灵活调节 |
| 进口 | 韩国、新加坡沥青 | 补充缺口 |

### 2. 产量关键指标

| 指标 | 数据频率 | 计分规则 |
|------|---------|---------|
| 国内沥青产量 | 月度 | 同比增速，正向：增产=供应增加=利空 |
| 炼厂开工率 | 周度 | 高开工=沥青产出多=供应宽松 |
| 炼厂利润 | 周度 | 利润高=增产意愿强=供应增加 |

### 3. 进口量

| 指标 | 数据频率 | 计分规则 |
|------|---------|---------|
| 沥青进口量 | 月度 | 进口大增=供应增加=反向指标 |
| 进口依存度 | 月度 | 越高越受外盘影响 |

---

## 三、第三层：需求端（道路建设，占价格25%权重）

**沥青需求≈道路建设≈宏观经济≈基建投资**，是沥青最大独立驱动。

### 1. 三类需求去向

| 需求类型 | 占比 | 时间特征 | 驱动逻辑 |
|---------|------|---------|---------|
| 道路建设（公路） | ~70% | 全年不均匀 | 基建投资+道路养护 |
| 防水材料 | ~15% | 季节性 | 房地产+基建 |
| 焦化需求 | ~10% | 灵活 | 替代品价格 |

### 2. 需求核心指标

| 指标 | 数据频率 | 计分规则 |
|------|---------|---------|
| 公路固投同比 | 月度 | 正向：基建投资增加=沥青需求增加 |
| 沥青表观消费量 | 月度 | 正向：消费增加=需求强劲 |
| 道路工程开工率 | 月度 | 正向：施工旺季=需求旺季 |
| 房地产新开工面积 | 月度 | 正向：房地产投资相关 |

### 3. 季节性规律（需求节奏）

| 时间 | 驱动逻辑 | BU方向 |
|------|---------|-------|
| 3~6月 | 道路施工旺季备货 | 偏强，易涨 |
| 7~8月 | 雨季施工放缓 | 偏弱，震荡 |
| 9~11月 | 施工旺季+冬储 | 偏强 |
| 12~2月 | 冬季停工 | 季节性低位 |

---

## 四、第四层：库存与区域价差（套利机会，占价格10%权重）

### 1. 库存指标

| 指标 | 数据频率 | 计分规则 |
|------|---------|---------|
| 沥青厂库（炼厂库存） | 周度 | 反向：库存高位=供应宽松=利空 |
| 沥青社库（社会库存） | 周度 | 反向：社会库存高=消化压力 |
| 仓单（上期所BU仓单） | 日度 | 反向：仓单注册=现货充裕 |

### 2. 区域价差（跨区域套利）

| 价差类型 | 计算公式 | 正常区间 | 交易信号 |
|---------|---------|---------|---------|
| 华东-华南价差 | 华东价 - 华南价 | ±100元/吨 | 价差>150=华东相对偏弱 |
| 华东-华北价差 | 华东价 - 华北价 | ±150元/吨 | 区域分化=跨区套利机会 |
| 山东-华东价差 | 山东价 - 华东价 | -200~+100 | 价差极端=区域套利窗口 |

### 3. 区域价差量化指标

| 指标 | 数据频率 | 计分规则 |
|------|---------|---------|
| 华东-华南价差分位 | 周度 | 近3年历史分位 |
| 山东-华东价差分位 | 周度 | 近3年历史分位 |
| 跨区套利窗口 | 事件 | 价差>历史80%分位=套利机会 |

---

## 五、第五层：政策与宏观（独立行情，占价格5%权重）

### 1. 政策变量

| 政策类型 | 影响逻辑 | 量化赋值 |
|---------|---------|---------|
| 基建投资政策 | 道路建设增加=沥青需求增加 | 积极=+15，中性=0，收缩=-15 |
| 环保政策 | 沥青厂限产=供应收缩 | 限产=+10，放松=-10 |
| 道路养护政策 | 道路大修=需求增加 | 积极=+8 |
| 房地产政策 | 防水材料需求=沥青需求 | 积极=+5 |

### 2. 宏观指标

| 指标 | 数据频率 | 计分规则 |
|------|---------|---------|
| GDP同比 | 季度 | 正向：经济好=基建好=沥青需求好 |
| 基建投资增速 | 月度 | 正向：基建强=沥青需求强 |
| 房地产投资增速 | 月度 | 正向：房地产强=沥青需求强 |

---

## 六、第六层：盘面结构（择时，占价格0%权重）

> **注**：沥青盘面结构因子权重设为0%，因沥青期货持仓量相对较小，月差结构不稳定，不作为主要信号源。

### 1. 基差

| 指标 | 计算方式 | 计分规则 |
|------|---------|---------|
| 基差=现货-期货 | 日度 | 正基差（现货升水）=现货紧=利多 |

### 2. 月间价差

| 指标 | 计算方式 | 计分规则 |
|------|---------|---------|
| 月差=近月-远月 | 日度 | Back结构=近月强=利多 |

---

## 七、沥青六层量化打分框架

### 7.1 顶层权重总表

| 模块编号 | 模块名称 | 顶层总权重 | 核心定位 |
|----------|----------|------------|----------|
| 模块1 | 成本因子 | 40% | 定价格上下边界，大方向 |
| 模块2 | 供应因子 | 20% | 定供应端边际变化 |
| 模块3 | 需求因子 | 25% | 定趋势方向，核心驱动 |
| 模块4 | 库存+区域价差 | 10% | 定套利机会 |
| 模块5 | 政策+宏观 | 5% | 定独立行情 |
| 模块6 | 盘面结构 | 0% | 定入场择时（辅助） |

### 7.2 全指标量化建模明细表

| 模块 | 指标编号 | 指标名称 | 数据频率 | 模块内权重 | 顶层权重 | 多空阈值 |
|------|---------|---------|----------|------------|----------|----------|
| **模块1 成本因子（40%）** | 1.1 | 布伦特原油20日涨跌幅分位 | 日度 | 50% | 20% | >60利多,<40利空 |
| | 1.2 | SC/布伦特价差分位 | 日度 | 30% | 12% | >65利多,<35利空 |
| | 1.3 | USDCNY汇率分位 | 日度 | 20% | 8% | >70利多,<30利空 |
| **模块2 供应因子（20%）** | 2.1 | 国内沥青产量同比分位 | 月度 | 40% | 8% | >60利多,<40利空 |
| | 2.2 | 炼厂开工率分位 | 周度 | 30% | 6% | >65利多,<35利空 |
| | 2.3 | 沥青进口量同比分位 | 月度 | 30% | 6% | 反向：>60利空,<40利多 |
| **模块3 需求因子（25%）** | 3.1 | 公路固投同比分位 | 月度 | 40% | 10% | >60利多,<40利空 |
| | 3.2 | 沥青表观消费量分位 | 月度 | 30% | 7.5% | >60利多,<40利空 |
| | 3.3 | 道路工程开工率分位 | 月度 | 20% | 5% | >60利多,<40利空 |
| | 3.4 | 房地产新开工面积分位 | 月度 | 10% | 2.5% | >60利多,<40利空 |
| **模块4 库存+区域价差（10%）** | 4.1 | 沥青厂库分位 | 周度 | 30% | 3% | 反向：>60利空,<40利多 |
| | 4.2 | 社会库存分位 | 周度 | 30% | 3% | 反向：>60利空,<40利多 |
| | 4.3 | 华东-华南价差分位 | 周度 | 20% | 2% | 极端值=套利信号 |
| | 4.4 | 山东-华东价差分位 | 周度 | 20% | 2% | 极端值=套利信号 |
| **模块5 政策+宏观（5%）** | 5.1 | 基建投资政策变量 | 事件 | 40% | 2% | 积极=+15 |
| | 5.2 | 环保限产政策变量 | 事件 | 30% | 1.5% | 限产=+10 |
| | 5.3 | GDP同比分位 | 季度 | 30% | 1.5% | >60利多,<40利空 |
| **模块6 盘面结构（0%）** | 6.1 | 基差分位 | 日度 | 50% | 0% | 辅助信号 |
| | 6.2 | 月间价差分位 | 日度 | 50% | 0% | 辅助信号 |

### 7.3 综合得分合成公式

```
模块1得分 = 1.1×0.5 + 1.2×0.3 + 1.3×0.2
模块2得分 = 2.1×0.4 + 2.2×0.3 + 2.3×0.3
模块3得分 = 3.1×0.4 + 3.2×0.3 + 3.3×0.2 + 3.4×0.1
模块4得分 = 4.1×0.3 + 4.2×0.3 + 4.3×0.2 + 4.4×0.2
模块5得分 = 5.1×0.4 + 5.2×0.3 + 5.3×0.3
模块6得分 = 6.1×0.5 + 6.2×0.5

总得分 = 模块1×0.40 + 模块2×0.20 + 模块3×0.25 + 模块4×0.10 + 模块5×0.05 + 模块6×0.00
```

### 7.4 交易信号规则

| 总得分区间 | 交易信号 | 操作建议 |
|------------|----------|----------|
| >65 | 多头区间 | 顺势开多，回落至60分止盈离场 |
| 35~65 | 震荡中性 | 观望为主，仅做区域套利 |
| <35 | 空头区间 | 顺势开空，回升至40分止损离场 |

---

## 八、常用套利逻辑

### 1. 跨品种套利：原油-沥青

| 市场状态 | 策略 | 逻辑 |
|---------|------|------|
| 裂解价差低位 | 多沥青空原油 | 沥青相对低估 |
| 裂解价差高位 | 空沥青多原油 | 沥青相对高估 |
| 基建旺季来临 | 多沥青空FU | 沥青需求强于燃料油 |

### 2. 跨区域套利

| 价差状态 | 策略 |
|---------|------|
| 山东-华东价差>150 | 卖山东买华东 |
| 山东-华东价差<-100 | 买山东卖华东 |
| 华东-华南价差>100 | 卖华东买华南 |

### 3. 跨月套利

根据月差结构：**Back拿多近空远，Contango拿空近多远**

---

## 九、季节性量化修正

| 时间区间 | 季节性调整 | 说明 |
|---------|-----------|------|
| 3~6月 | +8分 | 施工旺季备货 |
| 7~8月 | -5分 | 雨季施工放缓 |
| 9~11月 | +10分 | 施工旺季+冬储 |
| 12~2月 | -10分 | 冬季停工 |

---

## 十、Python计算代码

### 10.1 沥青打分器核心代码

```python
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional

@dataclass
class BitumenScore:
    """沥青综合打分结果"""
    total_score: float  # 总分 0-100
    cost_score: float    # 成本因子
    supply_score: float # 供应因子
    demand_score: float # 需求因子
    inventory_score: float # 库存+区域价差
    policy_score: float # 政策宏观
    structure_score: float # 盘面结构
    signal: str  # 信号：多头/震荡/空头

class BitumenScorer:
    """沥青六层量化打分器"""
    
    # 顶层权重
    WEIGHTS = {
        'cost': 0.40,
        'supply': 0.20,
        'demand': 0.25,
        'inventory': 0.10,
        'policy': 0.05,
        'structure': 0.00
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
    
    def calculate_cost_score(self, brent_20d_chg: pd.Series,
                            sc_brent_spread: pd.Series,
                            usdcny: pd.Series) -> float:
        """计算成本因子得分"""
        s1 = self.standard_score(brent_20d_chg, is_forward=True)
        s2 = self.standard_score(sc_brent_spread, is_forward=True)
        s3 = self.standard_score(usdcny, is_forward=True)
        return s1.iloc[-1] * 0.5 + s2.iloc[-1] * 0.3 + s3.iloc[-1] * 0.2
    
    def calculate_supply_score(self, production_yoy: pd.Series,
                               refinery_run: pd.Series,
                               import_yoy: pd.Series) -> float:
        """计算供应因子得分"""
        s1 = self.standard_score(production_yoy, is_forward=True)
        s2 = self.standard_score(refinery_run, is_forward=True)
        s3 = self.standard_score(import_yoy, is_forward=False)  # 反向
        return s1.iloc[-1] * 0.4 + s2.iloc[-1] * 0.3 + s3.iloc[-1] * 0.3
    
    def calculate_demand_score(self, highway_invest_yoy: pd.Series,
                               consumption: pd.Series,
                               project_start_rate: pd.Series,
                               property_starts: pd.Series) -> float:
        """计算需求因子得分"""
        s1 = self.standard_score(highway_invest_yoy, is_forward=True)
        s2 = self.standard_score(consumption, is_forward=True)
        s3 = self.standard_score(project_start_rate, is_forward=True)
        s4 = self.standard_score(property_starts, is_forward=True)
        return (s1.iloc[-1] * 0.4 + s2.iloc[-1] * 0.3 + 
                s3.iloc[-1] * 0.2 + s4.iloc[-1] * 0.1)
    
    def calculate_inventory_score(self, plant_stock: pd.Series,
                                  social_stock: pd.Series,
                                  east_south_spread: pd.Series,
                                  shandong_east_spread: pd.Series) -> float:
        """计算库存+区域价差因子得分"""
        s1 = self.standard_score(plant_stock, is_forward=False)
        s2 = self.standard_score(social_stock, is_forward=False)
        s3 = self.standard_score(east_south_spread, is_forward=True)
        s4 = self.standard_score(shandong_east_spread, is_forward=True)
        return (s1.iloc[-1] * 0.3 + s2.iloc[-1] * 0.3 + 
                s3.iloc[-1] * 0.2 + s4.iloc[-1] * 0.2)
    
    def calculate_policy_score(self, infra_policy: int,
                               env_policy: int,
                               gdp_yoy: pd.Series) -> float:
        """计算政策宏观因子得分"""
        s = self.standard_score(gdp_yoy, is_forward=True)
        return infra_policy * 0.4 + env_policy * 0.3 + s.iloc[-1] * 0.3
    
    def calculate_structure_score(self, basis: pd.Series,
                                   spread: pd.Series) -> float:
        """计算盘面结构因子得分（辅助）"""
        s1 = self.standard_score(basis, is_forward=True)
        s2 = self.standard_score(spread, is_forward=True)
        return s1.iloc[-1] * 0.5 + s2.iloc[-1] * 0.5
    
    def calculate_seasonal_adjustment(self, date: pd.Timestamp) -> float:
        """季节性调整"""
        month = date.month
        if month in [3, 4, 5, 6]:
            return 8
        elif month in [7, 8]:
            return -5
        elif month in [9, 10, 11]:
            return 10
        else:
            return -10
    
    def score(self, data: dict, date: Optional[pd.Timestamp] = None) -> BitumenScore:
        """
        计算沥青综合打分
        
        data: dict, 包含以下键：
            - brent_20d_chg: 布伦特20日涨跌幅
            - sc_brent_spread: SC-布伦特价差
            - usdcny: 美元兑人民币
            - production_yoy: 沥青产量同比
            - refinery_run: 炼厂开工率
            - import_yoy: 沥青进口同比
            - highway_invest_yoy: 公路固投同比
            - consumption: 沥青表观消费量
            - project_start_rate: 道路工程开工率
            - property_starts: 房地产新开工
            - plant_stock: 沥青厂库
            - social_stock: 社会库存
            - east_south_spread: 华东-华南价差
            - shandong_east_spread: 山东-华东价差
            - gdp_yoy: GDP同比
            - basis: 基差
            - spread: 月间价差
        """
        cost = self.calculate_cost_score(
            data['brent_20d_chg'], data['sc_brent_spread'], data['usdcny'])
        
        supply = self.calculate_supply_score(
            data['production_yoy'], data['refinery_run'], data['import_yoy'])
        
        demand = self.calculate_demand_score(
            data['highway_invest_yoy'], data['consumption'],
            data['project_start_rate'], data['property_starts'])
        
        inventory = self.calculate_inventory_score(
            data['plant_stock'], data['social_stock'],
            data['east_south_spread'], data['shandong_east_spread'])
        
        policy = self.calculate_policy_score(
            data.get('infra_policy', 0), data.get('env_policy', 0),
            data['gdp_yoy'])
        
        structure = self.calculate_structure_score(
            data['basis'], data['spread'])
        
        # 加权总分
        total = (cost * self.WEIGHTS['cost'] +
                supply * self.WEIGHTS['supply'] +
                demand * self.WEIGHTS['demand'] +
                inventory * self.WEIGHTS['inventory'] +
                policy * self.WEIGHTS['policy'] +
                structure * self.WEIGHTS['structure'])
        
        # 季节性调整
        if date is not None:
            seasonal_adj = self.calculate_seasonal_adjustment(date)
            total = (total * 10 + seasonal_adj) / 11  # 季节性权重约9%
        
        # 信号判定
        if total > 65:
            signal = "多头"
        elif total < 35:
            signal = "空头"
        else:
            signal = "震荡"
        
        return BitumenScore(
            total_score=round(total, 1),
            cost_score=round(cost, 1),
            supply_score=round(supply, 1),
            demand_score=round(demand, 1),
            inventory_score=round(inventory, 1),
            policy_score=round(policy, 1),
            structure_score=round(structure, 1),
            signal=signal
        )
```

---

## 版本历史

### v1.0.0 (2026-06-03) — 沥青框架初始版
- ⭐ **新增完整六层量化分析框架**：成本→供应→需求→库存区域价差→政策宏观→盘面结构
- ⭐ **量化打分体系**：标准化0~100分，消除量纲
- ⭐ **综合公式**：加权合成强弱指数，总分>65做多，<35做空
- ⭐ **季节性量化**：3~6月/9~11月旺季+分，7~8月/12~2月淡季-分
- ⭐ **区域套利量化规则**：华东-华南、山东-华东价差分位
- ⭐ **完整建模汇总表**：全指标量化明细表、交易信号规则、Python代码
