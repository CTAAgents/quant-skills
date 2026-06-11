# 共振检测模块 API 参考

## 核心类

### ResonanceDetector

共振检测器，用于检测产业链、基本面、技术面三维度信号的共振。

#### 初始化

```python
detector = ResonanceDetector()
```

#### 属性

##### thresholds

信号判定阈值配置。

```python
{
    'industry_chain_bullish': 55,  # 产业链看多阈值
    'industry_chain_bearish': 45,  # 产业链看空阈值
    'fundamental_bullish': 55,     # 基本面看多阈值
    'fundamental_bearish': 45,    # 基本面看空阈值
    'technical_bullish': 55,       # 技术面看多阈值
    'technical_bearish': 45,       # 技术面看空阈值
    'strong_resonance_min': 2,     # 强共振最少维度数
    'extreme_resonance_min': 3,    # 极强共振最少维度数
    'confidence_high': 0.8,        # 高置信度阈值
    'confidence_medium': 0.6,      # 中置信度阈值
    'confidence_low': 0.4          # 低置信度阈值
}
```

##### weights

各维度权重配置。

```python
{
    'industry_chain': 0.35,
    'fundamental': 0.30,
    'technical': 0.35
}
```

#### 方法

##### detect_resonance(industry_score, fundamental_score, technical_score)

检测三维度共振信号。

**参数：**
- `industry_score`: float - 产业链评分 (0-100)
- `fundamental_score`: float - 基本面评分 (0-100)
- `technical_score`: float - 技术面评分 (0-100)

**返回值：**
- ResonanceSignal - 共振信号对象

**示例：**
```python
signal = detector.detect_resonance(70, 65, 75)
print(f"方向: {signal.direction.value}")
print(f"共振强度: {signal.level.value}")
print(f"置信度: {signal.confidence:.2%}")
print(f"操作建议: {signal.action_recommendation}")
```

##### get_dimension_signal(score, bullish_thresh, bearish_thresh)

获取单个维度的信号方向。

**参数：**
- `score`: float - 评分 (0-100)
- `bullish_thresh`: float - 看多阈值
- `bearish_thresh`: float - 看空阈值

**返回值：**
- Tuple[SignalDirection, float] - (信号方向, 置信度)

---

## 多时间周期检测

### MultiTimeframeResonanceDetector

多时间周期共振检测器。

#### 方法

##### detect_multi_timeframe_resonance(timeframe_signals)

检测多时间周期的共振。

**参数：**
- `timeframe_signals`: Dict[str, ResonanceSignal] - 各时间周期的信号
  - 键: 时间周期 ('1d', '1w', '1m')
  - 值: ResonanceSignal 对象

**返回值：**
- Dict - 包含以下键的字典：
  - `bullish_count`: int - 看多信号数量
  - `bearish_count`: int - 看空信号数量
  - `neutral_count`: int - 中性信号数量
  - `multi_tf_resonance`: str - 多周期共振描述
  - `weighted_score`: float - 加权评分
  - `timeframe_signals`: Dict - 各时间周期信号详情

**示例：**
```python
mtf_detector = MultiTimeframeResonanceDetector()

signals = {
    '1d': detector.detect_resonance(70, 65, 75),
    '1w': detector.detect_resonance(60, 55, 62),
    '1m': detector.detect_resonance(55, 58, 60)
}

result = mtf_detector.detect_multi_timeframe_resonance(signals)
print(f"共振类型: {result['multi_tf_resonance']}")
print(f"加权评分: {result['weighted_score']:.1f}")
```

---

## 历史分析

### ResonanceHistoryAnalyzer

共振历史分析器，用于分析历史信号的表现。

#### 方法

##### add_signal(timestamp, signal)

添加信号到历史记录。

**参数：**
- `timestamp`: pd.Timestamp - 信号时间戳
- `signal`: ResonanceSignal - 共振信号

##### analyze_success_rate(price_history)

分析信号成功率。

**参数：**
- `price_history`: pd.DataFrame - 价格历史，需包含 'return' 列

**返回值：**
- Dict - 包含以下键的字典：
  - `total_signals`: int - 总信号数
  - `correct_signals`: int - 正确信号数
  - `success_rate`: float - 成功率
  - `level_success_rates`: Dict - 各强度等级的成功率

**示例：**
```python
analyzer = ResonanceHistoryAnalyzer()

# 添加历史信号
for timestamp, signal in historical_signals:
    analyzer.add_signal(timestamp, signal)

# 分析成功率
results = analyzer.analyze_success_rate(price_history)
print(f"总信号: {results['total_signals']}")
print(f"成功率: {results['success_rate']:.2%}")
```

---

## 可视化

### ResonanceVisualizer

共振信号可视化工具。

#### 方法

##### generate_resonance_matrix(signals)

生成共振信号矩阵表格。

**参数：**
- `signals`: List[ResonanceSignal] - 信号列表

**返回值：**
- str - 制表符分隔的表格字符串

##### generate_resonance_summary(signal)

生成单个信号的摘要。

**参数：**
- `signal`: ResonanceSignal - 共振信号

**返回值：**
- str - 信号摘要文本

---

## 数据类

### ResonanceSignal

共振信号数据类。

**属性：**
- `direction`: SignalDirection - 信号方向
- `level`: ResonanceLevel - 共振强度等级
- `confidence`: float - 置信度 (0-1)
- `strength_score`: float - 强度评分 (0-100)
- `contributing_factors`: List[str] - 贡献因子列表
- `conflicting_factors`: List[str] - 冲突因子列表
- `action_recommendation`: str - 操作建议

---

## 枚举类型

### SignalDirection

信号方向枚举。

**值：**
- `BULLISH`: "看多"
- `BEARISH`: "看空"
- `NEUTRAL`: "中性"

### ResonanceLevel

共振强度等级枚举。

**值：**
- `NO_RESONANCE`: "无共振"
- `WEAK_RESONANCE`: "弱共振"
- `MODERATE_RESONANCE`: "中等共振"
- `STRONG_RESONANCE`: "强共振"
- `EXTREME_RESONANCE`: "极强共振"

---

## 使用示例

### 完整共振检测流程

```python
from core import (
    ResonanceDetector,
    MultiTimeframeResonanceDetector,
    ResonanceHistoryAnalyzer,
    ResonanceVisualizer
)

# 1. 创建检测器
detector = ResonanceDetector()
mtf_detector = MultiTimeframeResonanceDetector()
history_analyzer = ResonanceHistoryAnalyzer()

# 2. 检测单周期共振
signal = detector.detect_resonance(70, 65, 75)
print(f"方向: {signal.direction.value}")
print(f"强度: {signal.level.value}")
print(f"建议: {signal.action_recommendation}")

# 3. 检测多周期共振
tf_signals = {
    '1d': detector.detect_resonance(70, 65, 75),
    '1w': detector.detect_resonance(60, 55, 62),
    '1m': detector.detect_resonance(55, 58, 60)
}
mtf_result = mtf_detector.detect_multi_timeframe_resonance(tf_signals)
print(f"多周期共振: {mtf_result['multi_tf_resonance']}")

# 4. 添加到历史
import pandas as pd
history_analyzer.add_signal(pd.Timestamp.now(), signal)

# 5. 生成可视化
summary = ResonanceVisualizer.generate_resonance_summary(signal)
print(summary)
```
