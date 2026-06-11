# SkillAdaptor 工作流程

## 完整流程概览

```
原始轨迹 → 轨迹分析 → 故障识别 → 责任归因 → 技能更新生成 → 接受检查 → (可选) 应用更新
```

## 详细步骤说明

### 1. 轨迹数据准备

轨迹数据应该包含以下信息：

```json
{
  "trajectory_id": "唯一标识符",
  "task_id": "任务ID",
  "success": 是否成功,
  "final_reward": 最终奖励值,
  "steps": [
    {
      "step_id": 步骤序号,
      "state": 状态字典,
      "action": 动作描述,
      "observation": 观察结果,
      "reward": 奖励值,
      "skill_invoked": 调用的技能名(可选)
    }
  ],
  "metadata": {
    "environment": "环境名",
    "agent": "智能体版本"
  }
}
```

### 2. 轨迹分析 (TrajectoryAnalyzer)

**功能**：
- 解析和验证轨迹数据结构
- 提取技能调用模式
- 计算轨迹统计指标（奖励曲线、步数等）

**输出**：
- 结构化的 Trajectory 对象
- 轨迹指标字典
- 技能调用序列

### 3. 故障识别与归因 (FaultAttributor)

**功能**：
- 识别候选故障步骤（基于负奖励等信号）
- 对故障进行分类（动作错误、技能误用、观察误解等）
- 计算技能责任分数
- 找到第一个可操作的故障

**故障类型**：
- `ACTION_ERROR` - 动作执行错误
- `SKILL_MISUSE` - 技能调用不当
- `OBSERVATION_MISINTERPRETATION` - 观察理解错误
- `GOAL_MISALIGNMENT` - 目标对齐问题
- `UNKNOWN` - 未知类型

### 4. 技能适应 (SkillAdapter)

**功能**：
- 为责任技能生成更新建议
- 版本号递增管理
- 生成接受检查清单
- 管理技能更新生命周期

**更新状态**：
- `PENDING` - 待审核
- `ACCEPTED` - 已接受
- `REJECTED` - 已拒绝
- `APPLIED` - 已应用

### 5. 接受检查 (可选)

在应用更新前，建议进行以下验证：
1. 类似任务上的奖励改进验证
2. 已成功任务的回归测试
3. 人工审核变更内容
4. 安全性检查

## 使用示例

### 简单使用

```python
from skill_adaptor import SkillAdaptor

# 初始化
adaptor = SkillAdaptor(responsibility_threshold=0.3)

# 方式1: 从字典数据
trajectory_data = {...}
result = adaptor.run(trajectory_data)

# 方式2: 从文件
result = adaptor.run("path/to/trajectory.json")

# 方式3: 分步执行
analysis = adaptor.analyze_trajectory(trajectory_data)
fault_attr = adaptor.attribute_faults(analysis)
updates = adaptor.adapt_skills(fault_attr)
```

### 扩展组件

可以继承核心类进行自定义扩展：

```python
from core.fault_attributor import FaultAttributor

class CustomFaultAttributor(FaultAttributor):
    def identify_fault_steps(self, trajectory):
        # 自定义故障识别逻辑
        pass
```

## 配置选项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| responsibility_threshold | 0.3 | 技能责任分数阈值 |
| skills_dir | "./data/skills" | 技能库目录 |

## 最佳实践

1. **数据质量** - 确保轨迹数据包含完整的状态、动作和奖励信息
2. **技能粒度** - 将智能体能力划分为合理粒度的可复用技能
3. **阈值调整** - 根据具体场景调整责任阈值
4. **渐进更新** - 使用接受检查机制，逐步验证和应用技能更新
