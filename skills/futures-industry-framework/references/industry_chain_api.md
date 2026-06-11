# 产业链标准化模块 API 参考

## 核心类

### IndustryChainStandardAnalyzer

产业链标准化分析器，用于对产业链进行定性标准化分析。

#### 初始化

```python
analyzer = IndustryChainStandardAnalyzer()
```

#### 方法

##### determine_inventory_cycle(metrics)

判定库存周期阶段。

**参数：**
- `metrics`: IndustryChainMetrics - 产业链指标对象

**返回值：**
- Tuple[InventoryCycle, float] - (库存周期类型, 置信度)

**示例：**
```python
cycle, confidence = analyzer.determine_inventory_cycle(metrics)
print(f"库存周期: {cycle.value}, 置信度: {confidence:.2%}")
```

##### determine_profit_structure(metrics)

判定利润结构。

**参数：**
- `metrics`: IndustryChainMetrics - 产业链指标对象

**返回值：**
- Tuple[ProfitStructure, float] - (利润结构类型, 置信度)

**示例：**
```python
structure, confidence = analyzer.determine_profit_structure(metrics)
print(f"利润结构: {structure.value}")
```

##### calculate_industry_chain_score(metrics)

计算产业链综合评分。

**参数：**
- `metrics`: IndustryChainMetrics - 产业链指标对象

**返回值：**
- Tuple[float, Dict[str, float]] - (总分, 各维度评分)

**示例：**
```python
total_score, dimension_scores = analyzer.calculate_industry_chain_score(metrics)
print(f"总分: {total_score:.1f}")
print(f"库存维度: {dimension_scores['inventory']:.1f}")
```

##### generate_standard_analysis_report(metrics, chain_name)

生成标准化分析报告。

**参数：**
- `metrics`: IndustryChainMetrics - 产业链指标对象
- `chain_name`: str - 产业链名称

**返回值：**
- Dict - 包含完整分析结果的字典

**示例：**
```python
report = analyzer.generate_standard_analysis_report(metrics, "黑色建材")
print(report['inventory_cycle']['stage'])
```

---

## 数据类

### IndustryChainMetrics

产业链指标数据类，包含所有产业链分析所需的量化指标。

**属性：**
- `inventory_change_rate`: float - 库存变化率
- `inventory_history_percentile`: float - 库存在历史中的分位
- `inventory_destocking_speed`: float - 去库速度
- `price_change_rate`: float - 价格变化率
- `upstream_profit_margin`: float - 上游利润率
- `midstream_profit_margin`: float - 中游利润率
- `downstream_profit_margin`: float - 下游利润率
- `profit_conduction_index`: float - 利润传导指数
- `operating_rate`: float - 开工率
- `operating_rate_change`: float - 开工率变化
- `enterprise_hedging_intensity`: float - 企业套保强度
- `supply_change`: float - 供应变化
- `demand_change`: float - 需求变化
- `supply_demand_gap`: float - 供需缺口
- `basis`: float - 基差
- `basis_history_percentile`: float - 基差历史分位

**创建示例：**
```python
metrics = IndustryChainMetrics(
    inventory_change_rate=-0.05,
    inventory_history_percentile=0.35,
    inventory_destocking_speed=0.8,
    price_change_rate=0.03,
    upstream_profit_margin=0.15,
    midstream_profit_margin=0.10,
    downstream_profit_margin=0.08,
    profit_conduction_index=0.7,
    operating_rate=0.85,
    operating_rate_change=0.02,
    enterprise_hedging_intensity=0.4,
    supply_change=-0.03,
    demand_change=0.05,
    supply_demand_gap=0.04,
    basis=-35,
    basis_history_percentile=0.25
)
```

---

## 枚举类型

### InventoryCycle

库存周期枚举。

**值：**
- `ACTIVE_DESTOCKING`: "主动去库"
- `PASSIVE_DESTOCKING`: "被动去库"
- `ACTIVE_RESTOCKING`: "主动补库"
- `PASSIVE_RESTOCKING`: "被动补库"

### ProfitStructure

利润结构枚举。

**值：**
- `UPSTREAM_PROFIT`: "上游盈利"
- `MIDSTREAM_PROFIT`: "中游盈利"
- `DOWNSTREAM_PROFIT`: "下游盈利"
- `FULL_CHAIN_LOSS`: "全链亏损"
- `BALANCED`: "利润均衡"

---

## 便捷函数

### create_sample_metrics()

创建示例产业链指标。

**返回值：**
- IndustryChainMetrics - 示例指标对象

**示例：**
```python
metrics = create_sample_metrics()
```
