# 贵金属数据源说明

## 主要数据源

### 1. Investing.com
- **网站**: https://www.investing.com
- **数据类型**: 实时价格、技术指标、历史数据
- **API端点**: https://api.investing.com/api/financialdata/
- **数据质量**: 高
- **更新频率**: 实时
- **覆盖品种**: XAUUSD, XAGUSD, XPTUSD, XPDUSD

### 2. Barchart.com
- **网站**: https://www.barchart.com
- **数据类型**: 技术分析、价格数据、成交量
- **API端点**: https://marketdata.websol.barchart.com/
- **数据质量**: 高
- **更新频率**: 实时
- **覆盖品种**: GCUSD (黄金), SIUSD (白银), PLUSD (铂金), PAUSD (钯金)

### 3. TradingView
- **网站**: https://www.tradingview.com
- **数据类型**: 技术指标、图表数据
- **API端点**: https://scanner.tradingview.com/forex/scan
- **数据质量**: 高
- **更新频率**: 实时
- **覆盖品种**: FX:XAUUSD, FX:XAGUSD, COMEX:PL1!, COMEX:PA1!

## 数据源对比

| 数据源 | 价格准确性 | 技术指标 | 历史数据 | API稳定性 | 权重 |
|--------|------------|----------|----------|------------|------|
| Investing.com | 高 | 完整 | 丰富 | 中等 | 1.0 |
| Barchart.com | 高 | 详细 | 丰富 | 高 | 1.2 |
| TradingView | 高 | 完整 | 中等 | 高 | 1.1 |

## 数据采集策略

### 多源验证
- 至少从2个数据源采集数据
- 验证价格一致性（变异系数 < 1%）
- 验证时间框架一致性（日线数据）

### 权重计算
```python
# 数据源权重
source_weights = {
    'barchart': 1.2,      # 最高权重
    'tradingview': 1.1,   # 中等权重
    'investing_com': 1.0  # 基础权重
}

# 加权平均价格计算
weighted_price = sum(price * weight for price, weight in zip(prices, weights)) / sum(weights)
```

### 数据验证规则
1. **价格范围验证**: 价格应在合理范围内（如黄金: 1000-10000）
2. **价格一致性验证**: 价格变异系数应 < 1%
3. **技术指标验证**: RSI (0-100), ADX (0-100), CCI (-200 to +200)
4. **数据完整性验证**: 必需字段应完整
5. **时间一致性验证**: 数据应在24小时内
6. **市场逻辑验证**: 高低价、开盘收盘价逻辑关系

## 备用数据源

### 4. Yahoo Finance
- **网站**: https://finance.yahoo.com
- **数据类型**: 价格数据、历史数据
- **API端点**: https://query1.finance.yahoo.com/v8/finance/chart/
- **数据质量**: 中等
- **更新频率**: 15分钟延迟
- **覆盖品种**: GC=F (黄金), SI=F (白银)

### 5. 新浪财经
- **网站**: https://finance.sina.com.cn
- **数据类型**: 国内期货数据
- **数据质量**: 中等
- **更新频率**: 实时
- **覆盖品种**: 沪金AU, 沪银AG

## 数据格式标准

### 价格数据格式
```json
{
  "symbol": "XAUUSD",
  "price": 4191.35,
  "change": -25.23,
  "change_percent": -0.60,
  "high": 4237.25,
  "low": 4153.10,
  "open": 4216.58,
  "close": 4191.35,
  "volume": 128380,
  "source": "investing_com",
  "timeframe": "daily",
  "timestamp": "2026-06-22T20:30:00"
}
```

### 技术指标格式
```json
{
  "rsi": 56.55,
  "macd": 4.17,
  "adx": 24.80,
  "cci": 95.91,
  "stoch_k": 75.36,
  "stoch_d": 65.42,
  "atr": 19.51
}
```

## 错误处理

### 常见错误
1. **网络连接失败**: 使用备用数据源或模拟数据
2. **API限制**: 调整请求频率，使用多个数据源
3. **数据格式错误**: 更新解析逻辑，处理异常格式
4. **数据缺失**: 使用其他数据源补充

### 降级策略
1. **第一级**: 使用标准化数据采集系统
2. **第二级**: 使用专业数据API
3. **第三级**: 使用WebSearch + WebFetch
4. **第四级**: 使用本地模拟数据生成器

## 更新维护

### 定期检查
- 每周检查数据源API状态
- 每月更新数据源权重配置
- 每季度评估数据源质量

### 版本管理
- 记录数据源API变更
- 更新解析逻辑适配新格式
- 维护向后兼容性

---
*数据源说明文档 v1.0.0 - 2026-06-22*