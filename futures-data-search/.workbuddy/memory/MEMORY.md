# futures-data-search 项目长期记忆

## 架构决策记录

### 2026-06-29 数据源优先级重构：通达信TQ-Local设为第一数据源

**变更**：
- 数据源优先级统一链：0=通达信TQ-Local(priority=0) → TqSDK → 东方财富 → 交易所API → AKShare → WebSearch → 缓存
- 盘中盘后统一：通达信TQ-Local不受交易时段限制，始终优先尝试
- `data_sources.yaml` 已配 `tdx_local` (priority_intraday:0, priority_afternoon:0)
- `data_adapter.py`: 长尾降级链首位插入 `_fallback_via_tdx()` + 模块级 `TDX_LOCAL_AVAILABLE`
- `multi_source_adapter.py`: `get_priority_list()` 自动按priority升序排列，tdx_local优先

**长尾品种降级流程更新**：
- 通达信TQ-Local → TqSDK定向合约ID → EastMoney合约API → 品种状态标记

**自动化任务 Prompt 修正**：
- Python路径：`C:/Users/yangd/.workbuddy/binaries/python/versions/3.13.12/python.exe`
- 数据源优先级：显式标注通达信第一
- 异常兜底：所有数据源不可用时回退至最近缓存数据

### 2026-06-28 多源数据集成路由系统 v3.1

**配置驱动路由**：
- `data_sources.yaml` 为数据源注册中心，所有数据源在此配置（启用/禁用、优先级、参数）
- `DataSourceConfig` 单例加载器，`reload()` 热重载
- `DataSource` 枚举与 YAML name 字段对齐
- `MultiSourceAdapter` 通过 `self.config.get_priority_list(is_trading_hour)` 获取路由链

**交易时段路由策略**：
- 盘中（09-15/21-23）：TqSDK → exchange → eastmoney → akshare → web → cache
- 盘后（15-21）：exchange → eastmoney → tqsdk → akshare → web → cache

**WH6已彻底移除**（从所有代码路径、文档、配置中清理）

**品种覆盖**：84个品种（2026-07-02 移除已停止交易的 ZC/动力煤），73个有数据 + 9个状态标记 + 2个待覆盖
- 状态标记：delisted/low_liquidity/active
- 长尾降级流程：TqSDK定向合约ID → EastMoney合约API → 状态标记

**主力映射**：双模式适配
- 合约级数据（CFFEX）：完整 DominantMappingCalculator 算法
- 品种级数据（AKShare）：直接 888/99 映射
- `DominantMappingArchive`：90天历史归档

**金十数据 MCP**：
- 配置已写入 mcp.json（Bearer Token 认证）
- **待用户手动激活后方可用**
- 如加入 data_sources.yaml 需经用户确认

**数据源变更规则**（详见用户级铁律）：
- 禁止擅自改动数据源，必须先向用户确认
