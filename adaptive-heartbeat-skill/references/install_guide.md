# Adaptive Heartbeat Skill — 安装指南

## 目录结构

```
adaptive-heartbeat-skill/
├── SKILL.md                              ← 通用 8 步工作流引擎
├── references/
│   └── config_schema.md                  ← monitor_config.json 完整 Schema
├── examples/
│   ├── oil_gold_config.json              ← 原油+贵金属配置模板
│   └── black_metals_config.json          ← 黑色系配置模板
└── scripts/
    └── (预留：配置验证脚本)
```

## 安装到 Agent

### 新 Agent
1. 将此 Skill 安装到目标 Agent
2. 从 `examples/` 中选择一个配置模板，复制到 Agent workspace 根目录，命名为 `monitor_config.json`
3. 根据实际品种/数据源修改配置
4. 创建 cron 任务（隔离模式），prompt 指向 `SKILL.md`

### 已有 Agent（从旧版迁移）
1. 安装 Skill
2. 使用 `examples/` 中的 JSON 配置替换旧的硬编码 workflow + config
3. 删除旧目录（`adaptive_heartbeat/` 或 `adaptive_heartbeat_black/`）
4. 保留旧 `state.json` 的 signal_history（迁移到新的 `adaptive_heartbeat_state.json`）
5. 更新 cron 任务的 prompt，改为引用新 SKILL.md

## cron 任务配置

```json
{
  "name": "AdaptiveHeartbeat_XXX",
  "schedule": { "kind": "cron", "expr": "0 */2 * * *", "tz": "Asia/Shanghai" },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "严格按照 adaptive-heartbeat-skill/SKILL.md 执行自适应心跳监控。读取 {workspace}/monitor_config.json 获取品种和数据源配置。",
    "timeoutSeconds": 600
  },
  "delivery": { "mode": "none" }
}
```

## 扩展新市场

只需新建一个 `monitor_config.json`：

1. 定义 `products`（品种代码→品种信息+URL参数）
2. 定义 `data_sources`（实时/基本面/新闻源）
3. 定义 `focus_types`（触发条件+置信度公式）
4. 定义 `tech_signals`（该品种的技术信号）
5. 设置 `report_path` 和 `schedule`
6. 创建 cron → 完成

引擎完全不需修改。

## 支持的品种类型扩展

| 市场 | products 示例 | 特有信号 |
|------|-------------|---------|
| 能化 | SC/FU/LU/PG/LPG | 跨区价差、裂解价差 |
| 有色 | CU/AL/ZN/NI/SN | LME升贴水、TC加工费 |
| 农产品 | M/Y/P/OI/RM | 压榨利润、基差率 |
| 股指 | IF/IC/IH/IM | 基差率、分红影响 |
| 外汇 | EUR/USD/JPY | 利差、央行决议 |

只需写一份 config，不需要改引擎。
