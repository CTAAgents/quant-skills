# 权重优化模块 API 参考

## 核心类

### WeightOptimizer

权重优化器，使用网格搜索和回测来优化评分权重配置。

#### 初始化

```python
optimizer = WeightOptimizer()
```

#### 属性

##### default_weights

默认权重配置。

```python
{
    'industry_chain': 0.40,
    'fundamental': 0.30,
    'technical': 0.30
}
```

##### default_sub_weights

默认子权重配置，包含各维度的详细权重。

#### 方法

##### optimize_top_level_weights(historical_data)

优化顶层权重配置。

**参数：**
- `historical_data`: pd.DataFrame - 历史数据，需包含：
  - `industry_chain_score`: 产业链评分
  - `fundamental_score`: 基本面评分
  - `technical_score`: 技术面评分
  - `future_return`: 未来收益

**返回值：**
- Tuple[Dict[str, float], List[Dict]] - (最优权重, 所有测试结果)

**示例：**
```python
optimal_weights, results = optimizer.optimize_top_level_weights(hist_data)
print(f"最优权重: {optimal_weights}")
```

##### optimize_sub_weights(historical_data, dimension)

优化指定维度的子权重。

**参数：**
- `historical_data`: pd.DataFrame - 历史数据
- `dimension`: str - 维度名称 ('industry_chain', 'fundamental', 'technical')

**返回值：**
- Tuple[Dict[str, float], float, float] - (最优子权重, 5%分位, 95%分位)

##### backtest_with_weights(weights, historical_data)

使用指定权重进行回测。

**参数：**
- `weights`: Dict[str, float] - 权重配置
- `historical_data`: pd.DataFrame - 历史数据

**返回值：**
- BacktestResult - 回测结果对象

##### compare_default_vs_optimized(historical_data)

比较默认权重和优化权重的表现。

**参数：**
- `historical_data`: pd.DataFrame - 历史数据

**返回值：**
- Dict - 包含对比结果的字典

**示例：**
```python
comparison = optimizer.compare_default_vs_optimized(hist_data)
print(f"默认收益: {comparison['default']['performance']['total_return']:.2%}")
print(f"优化收益: {comparison['optimized']['performance']['total_return']:.2%}")
```

##### generate_synthetic_historical_data(n_periods=500)

生成合成历史数据用于测试。

**参数：**
- `n_periods`: int - 数据点数量，默认500

**返回值：**
- pd.DataFrame - 合成历史数据

---

### BayesianWeightOptimizer

贝叶斯权重优化器，提供不确定性估计。

#### 方法

##### bayesian_update(historical_data, n_samples=1000)

执行贝叶斯权重更新。

**参数：**
- `historical_data`: pd.DataFrame - 历史数据
- `n_samples`: int - 采样数量，默认1000

**返回值：**
- Dict - 包含后验分布的字典

---

### WeightSaver

权重保存和加载工具。

#### 方法

##### save_weights(weights, filepath, metadata=None)

保存权重到文件。

**参数：**
- `weights`: Dict[str, float] - 权重配置
- `filepath`: str - 文件路径
- `metadata`: Optional[Dict] - 元数据（可选）

**示例：**
```python
WeightSaver.save_weights(
    weights,
    'weights.json',
    metadata={'optimized_date': '2026-05-31'}
)
```

##### load_weights(filepath)

从文件加载权重。

**参数：**
- `filepath`: str - 文件路径

**返回值：**
- Tuple[Dict[str, float], Dict] - (权重配置, 元数据)

**示例：**
```python
weights, metadata = WeightSaver.load_weights('weights.json')
print(f"权重: {weights}")
print(f"优化日期: {metadata.get('optimized_date')}")
```

---

## 数据类

### BacktestResult

回测结果数据类。

**属性：**
- `total_return`: float - 总收益率
- `sharpe_ratio`: float - 夏普比率
- `max_drawdown`: float - 最大回撤
- `win_rate`: float - 胜率
- `n_trades`: int - 交易次数
- `avg_trade_return`: float - 平均交易收益率

---

## 使用示例

### 完整权重优化流程

```python
from core import WeightOptimizer, WeightSaver

# 1. 创建优化器
optimizer = WeightOptimizer()

# 2. 生成或加载历史数据
historical_data = optimizer.generate_synthetic_historical_data(n_periods=500)

# 3. 优化顶层权重
optimal_weights, results = optimizer.optimize_top_level_weights(historical_data)

# 4. 优化子权重
for dimension in ['industry_chain', 'fundamental', 'technical']:
    optimal_sub, p5, p95 = optimizer.optimize_sub_weights(historical_data, dimension)
    print(f"{dimension}: {optimal_sub} (90% CI: [{p5:.3f}, {p95:.3f}])")

# 5. 比较优化前后
comparison = optimizer.compare_default_vs_optimized(historical_data)

# 6. 保存优化后的权重
WeightSaver.save_weights(
    optimal_weights,
    'optimized_weights.json',
    metadata={
        'optimized_date': '2026-05-31',
        'n_samples': len(historical_data)
    }
)

# 7. 加载并使用
loaded_weights, metadata = WeightSaver.load_weights('optimized_weights.json')
print(f"加载时间: {metadata.get('timestamp')}")
```
