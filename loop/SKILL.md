---
name: loop
description: 复刻 Claude Code /loop 命令。反复执行用户任务直到达成或终止。支持固定间隔、动态间隔、停滞检测、熔断机制。当用户输入 /loop 或 /loop <间隔> <任务> 时触发。
agent_created: true
---

# Loop Skill v2 — 真正自动循环（无需用户手动触发下一轮）

## 身份

当本skill被激活时，作为 **Loop-Harness**：自动反复执行用户任务直到达成或终止。

**核心区别 vs v1**：不再依赖用户手动发消息触发下一轮。改为后台进程驱动自动循环。

## 命令解析

| 输入 | 行为 |
|------|------|
| `/loop` | 裸 loop：显示当前状态或启动新loop |
| `/loop <间隔> <任务>` | 例 `/loop 5m 跑 pytest 直到全绿` |
| `/loop <任务> every <间隔>` | 例 `/loop 跑 pytest every 10m` |
| `/loop stop` | 停止当前 loop |
| `/loop status` | 查看loop当前执行状态 |
| `/loop help` | 显示用法 |

**间隔单位**：`s`、`m`、`h`、`d`。最小间隔1m。

## 自动循环架构（核心改动）

```
第一次调用 (/loop 5m run tests):
  ├─ 创建后台循环脚本 (loop_driver.py)
  ├─ 以 run_in_background 启动
  ├─ 输出「📋 Loop 已启动：每5分钟一次，最多30轮」
  └─ 执行第1轮

后台循环脚本自动运行:
  while 未达成目标 and 轮次 < 上限:
    ① 等待间隔时间
    ② 执行用户任务命令
    ③ 检查结果
    ④ 记录进度到 state.json
    ⑤ 若达成 → 自动停止 + 通知
  
用户可随时 /loop status 查看进度
用户可随时 /loop stop 终止循环
```

## 启动流程（当用户输入 /loop 时）

### Step 1: 解析参数
- 间隔：默认5m，最小1m
- 任务：用户指定的命令/目标
- 最大轮次：30（可配置）
- 停滞检测：连续3轮相同状态

### Step 2: 准备运行环境

```bash
mkdir -p ~/.workbuddy/loop/
# 状态文件路径: ~/.workbuddy/loop/state.json
# 循环脚本路径: ~/.workbuddy/loop/loop_driver.py
```

### Step 3: 生成后台循环脚本

生成 Python 脚本 `~/.workbuddy/loop/loop_driver.py`，内容结构：

```python
#!/usr/bin/env python3
"""
Loop Driver — 由 /loop skill 自动生成，后台执行
"""
import subprocess, time, json, os, sys
from datetime import datetime, timezone

STATE_FILE = os.path.expanduser("~/.workbuddy/loop/state.json")
INTERVAL = {interval_seconds}     # 由 /loop 参数决定
MAX_ROUNDS = 30
CMD = {user_task_command}         # 用户指定的任务命令
SUCCESS_MARKER = {success_pattern} # 判定达成的标志

def load_state():
    try:
        with open(STATE_FILE) as f: return json.load(f)
    except: return {{"round": 0, "status": "running", "started_at": datetime.now(timezone.utc).isoformat()}}

def save_state(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f: json.dump(s, f, indent=2, default=str)

def run_task():
    try:
        result = subprocess.run(CMD, shell=True, capture_output=True, text=True, timeout=300)
        output = (result.stdout + result.stderr)[-2000:]
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)

state = load_state()
round_num = state["round"] + 1
state["round"] = round_num
state["last_run"] = datetime.now(timezone.utc).isoformat()

print(f"--- Round {round_num}/{MAX_ROUNDS} ---")
success, output = run_task()

# 判断是否达成
if success:
    state["status"] = "completed"
    state["conclusion"] = "✅ 目标达成"
    print("✅ 目标达成！")
    save_state(state)
    sys.exit(0)

# 未达成 — 检查停滞
state["last_output"] = output[:500]
prev_output = state.get("prev_output", "")
if prev_output and prev_output == state["last_output"]:
    state["stall_count"] = state.get("stall_count", 0) + 1
else:
    state["stall_count"] = 0
state["prev_output"] = state["last_output"]

if state.get("stall_count", 0) >= 3:
    state["status"] = "stalled"
    state["conclusion"] = "⚠️ 连续3轮无进展，自动停止"
    print("⚠️ 停滞：连续3轮相同输出，自动停止")
    save_state(state)
    sys.exit(1)

if round_num >= MAX_ROUNDS:
    state["status"] = "max_rounds"
    state["conclusion"] = "⏹ 已达最大轮次上限"
    save_state(state)
    sys.exit(1)

print(f"⏭ Round {round_num} 未完成")
print(f"⏳ 下次运行：{INTERVAL}秒后")
state["status"] = "running"
save_state(state)
```

### Step 4: 使用 Bash(run_in_background) 启动后台循环

关键命令结构：
```bash
cd {workspace} && nohup python3 ~/.workbuddy/loop/loop_driver.py &
```

但更健壮的方式是用 shell 脚本包装，因为后台 bash 任务会持续运行：

```bash
# 创建包装脚本
cat > ~/.workbuddy/loop/runner.sh << 'SCRIPT_EOF'
#!/bin/bash
INTERVAL={seconds}
MAX=30
for ((i=1; i<=MAX; i++)); do
  echo "--- Round $i/$MAX ---"
  python3 ~/.workbuddy/loop/loop_driver.py
  STATUS=$?
  if [ $STATUS -eq 0 ]; then
    echo "✅ 目标达成"
    break
  fi
  if [ $STATUS -eq 1 ] && [ -f ~/.workbuddy/loop/state.json ]; then
    ST=$(python3 -c "import json; s=json.load(open('$HOME/.workbuddy/loop/state.json')); print(s.get('status',''))")
    if [ "$ST" = "stalled" ] || [ "$ST" = "max_rounds" ]; then break; fi
  fi
  echo "Sleeping $INTERVAL seconds..."
  sleep $INTERVAL
done
SCRIPT_EOF
chmod +x ~/.workbuddy/loop/runner.sh
```

然后启动：`Bash(description="启动 loop 后台进程", command="bash ~/.workbuddy/loop/runner.sh", run_in_background=true)`

## 每轮迭代协议（智能诊断模式）

当任务涉及代码修改/测试修复（不仅仅是跑命令），每轮也做智能诊断：

```
--- 第 N 轮 ---
① 状态检查：读取 state.json + 检查输出
② 诊断：基于上轮输出，一句话根因
③ 修复：最小改动修复问题
④ 验证：运行验证命令
⑤ 写入 state.json 记录进度
```

**注意**：智能诊断修复需要 agent 参与。在这种情况下：
1. agent 完成一轮诊断+修复
2. 写入 state.json 更新状态
3. 在回复末尾输出本轮结果
4. **后台 runner.sh 的循环会按间隔自动触发下一轮**
5. 下一轮时 agent 读取 state.json 继续工作

## 终止条件

| 条件 | 处理 |
|------|------|
| 目标达成 | ✅ 自动停止 + state.json status=completed |
| 连续 3 轮相同状态无进展 | ⚠️ 停滞，自动停止 |
| 最大轮次 30 | ⏹ 已达上限，停止 |
| 用户 `/loop stop` | 写入 state.json status=stopped + kill runner.sh |
| 用户 `/loop status` | 读取 state.json 显示当前进度 |

## 安全护栏

- **不可逆操作**：必须先列计划，等用户输入「确认执行」
- **不捏造**：诊断基于真实文件/输出
- **不扩大范围**：只改任务相关

## 使用示例

### 示例1：固定间隔循环（自动运行）

```
用户：/loop 5m 修改代码直到pytest全绿

你：📋 Loop v2 已启动！
   间隔：每5分钟
   任务：修改代码直到pytest全绿
   最大轮次：30

--- 第 1 轮 ---
① 运行 pytest → 失败 3/10
② 诊断：test_calc.py:42 断言失败，add()未处理负数
③ 修复：calc.py:10 添加负数处理
④ 验证：pytest → 失败 1/10（其他错误）
⑤ 状态：round=1, stall=0
========================================
⏭ 第1轮未完成
⏳ 后台循环已启动：5分钟后自动执行第2轮
查看进度: /loop status | 停止: /loop stop
========================================

（5分钟后后台自动执行第2轮，agent读取state.json继续）
```

### 示例2：纯命令循环（后台全自动）

```
用户：/loop 10m 运行 "curl -s http://localhost:8080/health" 直到返回200

你：📋 Loop v2 已启动！
   间隔：每10分钟
   命令：curl -s http://localhost:8080/health 直到返回200

--- 第 1 轮 ---
curl → 连接拒绝
⏭ 未完成
========================================
后台循环已启动，第2轮将在10分钟后自动执行。
使用 /loop status 查看进度 | /loop stop 停止
========================================
```

### 示例3：停止 loop

```
用户：/loop stop
你：⏹ 正在停止 loop...
   ✅ 后台进程已终止
   ✅ state.json status=stopped
```

### 示例4：查看状态

```
用户：/loop status
你：📊 Loop 状态
   轮次：5/30
   状态：running
   最近输出：仍有2个测试失败
   上次运行：2026-07-04T22:30:00
```

## 实现要点（agent 执行时必须遵守）

1. **启动时**：
   - 先创建 `~/.workbuddy/loop/` 目录
   - 生成 `state.json` 和 `runner.sh`
   - 用 `Bash(run_in_background=true)` 启动 runner.sh
   - 输出启动摘要 + 第一轮结果

2. **运行时（每轮 agent 触发）**：
   - 读取 `state.json` 了解当前进度
   - 智能判断（诊断+修复）
   - 写入最新状态
   - 回复末尾提示「后台循环继续，X分钟后下一轮」

3. **/loop stop**：
   - 写入 `state.json` status=stopped
   - 用 `TaskStop` 终止后台任务
   - 清理 runner.sh 进程

4. **/loop status**：
   - 读取 `state.json` 显示状态摘要

5. **最简兼容模式**（当无法创建后台脚本时）：
   - 降级为agent自循环：使用 `automation_update` 创建 one-time automation 调度下一轮
   - 每个自动化运行同一prompt + 轮次状态
   - 达成目标后删除自动化

## 快速参考

| 命令 | 效果 |
|------|------|
| `/loop <间隔> <任务>` | 启动自动循环（后台driver） |
| `/loop` | 裸循环（智能维护模式） |
| `/loop status` | 查看当前循环状态 |
| `/loop stop` | 停止循环 |
| `/loop help` | 显示帮助 |
