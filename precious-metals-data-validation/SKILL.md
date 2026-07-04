---
name: "precious-metals-data-validation"
description: "贵金属数据标准化采集与验证系统，确保技术指标数据准确性。从多个权威数据源采集日线数据，自动验证数据一致性、时间框架、市场逻辑，提供加权平均共识数据。"
version: "2.0.0"
agent_created: true
---

# 贵金属数据标准化采集与验证系统

## 技能描述

本技能提供贵金属（黄金、白银、铂金、钯金）数据的标准化采集、验证和处理功能。通过多源数据采集、差异处理和验证机制，确保技术指标数据的准确性和一致性。

## 核心功能

### 1. 多源数据采集
- **主要数据源**：NeoData API（权威金融数据服务）
- **备用数据源**：Investing.com、Barchart.com、TradingView
- 支持日线、周线、月线等多个时间框架
- 自动解析不同数据源的响应格式

### 2. 数据差异处理
- 检测价格差异、时间框架不匹配、异常值、数据一致性错误
- 提供数据源过滤和加权平均计算
- 生成差异报告和处理建议

### 3. 数据验证
- 验证价格数据范围、一致性
- 验证技术指标值范围（RSI 0-100，ADX等）
- 验证数据完整性、时间一致性、市场逻辑
- 生成验证报告和分数

### 4. 系统集成
- 整合所有功能，提供完整数据管道
- 生成系统级报告和建议
- 支持多品种批量处理

## 目录结构

```
precious-metals-data-validation/
├── SKILL.md                    # 技能说明文档
├── _user_meta.json             # 用户元数据
├── scripts/                    # 脚本目录
│   ├── neodata_data_collector.py            # NeoData数据采集器（主要）
│   ├── precious_metals_data_collector.py    # 多源数据采集器（备用）
│   ├── data_difference_handler.py           # 数据差异处理器
│   ├── data_validation_script.py            # 数据验证脚本
│   ├── precious_metals_data_system.py       # 主控制器
│   ├── mock_data_collector.py               # 模拟数据采集器
│   └── requirements.txt                     # 依赖包列表
├── tests/                      # 测试目录
│   ├── test_system.py                        # 系统测试脚本
│   └── test_with_mock_data.py                # 模拟数据测试脚本
└── references/                 # 参考文档
    └── data_sources.md                       # 数据源说明
```

## 使用方法

### 1. 安装依赖
```bash
cd precious-metals-data-validation/scripts
pip install -r requirements.txt
```

### 2. 使用NeoData数据采集器（推荐）
```bash
cd precious-metals-data-validation/scripts
python neodata_data_collector.py
```

### 3. 使用多源数据采集器（备用）
```bash
cd precious-metals-data-validation/scripts
python precious_metals_data_system.py
```

### 4. 运行测试
```bash
cd precious-metals-data-validation/tests
python test_with_mock_data.py
```

## 数据源配置

### 主要数据源（首选）
1. **NeoData API**: 权威金融数据服务，支持股票、期货、外汇、大宗商品
   - 数据源：实时行情、历史数据、技术指标
   - 优势：稳定、权威、覆盖全面
   - 权重：1.5（最高优先级）

### 备用数据源（降级使用）
2. **Investing.com**: 提供实时价格和技术指标（权重：1.0）
3. **Barchart.com**: 提供详细技术分析数据（权重：1.2）
4. **TradingView**: 提供多维度技术指标（权重：1.1）

### 数据源降级策略
1. **第一优先级**：NeoData API（主要数据源）
2. **第二优先级**：多源采集器（Investing.com、Barchart、TradingView）
3. **第三优先级**：WebSearch + WebFetch（权威金融网站）
4. **第四优先级**：本地模拟数据生成器（仅测试用）

## 验证机制

### 价格验证
- 价格范围验证：检查价格在合理范围内
- 价格一致性验证：计算价格变异系数

### 技术指标验证
- RSI验证：0-100范围
- ADX验证：0-100范围
- CCI验证：-200到+200范围

### 数据完整性验证
- 必需字段检查：symbol, price, change, change_percent, high, low, open, close, source
- 时间戳验证：确保数据时效性

### 市场逻辑验证
- 高低价逻辑：最高价 >= 最低价
- 开盘价范围：开盘价应在高低价范围内
- 收盘价范围：收盘价应在高低价范围内
- 涨跌逻辑：涨跌额 = 收盘价 - 开盘价

## 输出文件

### 验证报告
- JSON格式：详细验证数据
- TXT格式：可读摘要报告

### 输出目录
- 验证报告：`F:\Commodities\Reports\validation\`
- 系统报告：`F:\Commodities\Reports\validation\`

## 集成到贵金属晚报

### 更新数据源优先级
1. **第一优先级**：NeoData API（主要数据源，优先使用）
2. **第二优先级**：标准化数据采集系统（多源采集）
3. **第三优先级**：专业数据API（Investing.com、Barchart等）
4. **第四优先级**：WebSearch + WebFetch（权威金融网站）
5. **第五优先级**：本地模拟数据生成器（仅测试用）

### 数据质量保证机制
1. **NeoData优先**：优先使用NeoData API获取数据，确保数据权威性
2. **多源验证**：当NeoData数据不足时，使用多源采集器验证一致性
3. **时间框架验证**：确保所有数据为日线级别
4. **价格范围验证**：检查价格在合理范围内
5. **技术指标验证**：验证RSI、ADX等指标范围
6. **市场逻辑验证**：检查高低价、开盘收盘价逻辑关系
7. **加权平均计算**：根据数据源质量计算共识价格

## 故障排除

### 常见问题
1. **网络连接失败**：检查网络连接，使用模拟数据作为备用
2. **API限制**：调整请求频率，使用多个数据源分担负载
3. **数据格式错误**：检查数据源API响应格式，更新解析逻辑

### 调试模式
```bash
# 启用详细日志
python precious_metals_data_system.py --verbose

# 只验证特定品种
python precious_metals_data_system.py --symbol XAUUSD
```

## 更新日志

### v2.0.0 (2026-06-25)
- **重大更新**：集成NeoData API作为主要数据源
- 新增`neodata_data_collector.py`脚本，使用权威金融数据服务
- 优化数据源优先级：NeoData API > 多源采集 > WebSearch > 模拟数据
- 提升数据权威性和稳定性
- 优化Token消耗，减少网络请求失败风险

### v1.0.0 (2026-06-22)
- 初始版本发布
- 实现多源数据采集功能
- 实现数据差异处理机制
- 实现数据验证功能
- 创建完整测试套件

## 联系方式

如有问题或建议，请联系系统管理员。

---
*本技能由WorkBuddy系统创建，确保贵金属数据采集的准确性和可靠性。*