---
name: "skill-adaptor"
description: "基于轨迹的LLM智能体自适应技能框架，具有显式故障归因。当需要分析执行轨迹、识别故障并改进智能体技能时调用。"
---
# SkillAdaptor：基于轨迹的LLM智能体自适应技能

SkillAdaptor 是一个免训练、步级别的技能适应框架，为 LLM 智能体提供显式的故障归因。

## 概述

基于论文 "SkillAdaptor: Self-Adapting Skills for LLM Agents from Trajectories"（arXiv:2606.01311），本技能实现了：

1. **轨迹分析**：解析和分析智能体执行轨迹
2. **故障归因**：识别第一个可操作的故障步骤，并将责任链接到相关技能
3. **技能适应**：通过接受检查应用有针对性的技能更新
4. **OpenClaw 集成**：兼容 OpenClaw 类智能体框架

## 核心特性

- **步级别归因**：细粒度的故障识别，而非会话级反馈
- **免训练**：无需模型微调
- **显式接受检查**：安全的人类在环验证
- **骨干冻结**：保留基础模型能力
- **性能提升**：PinchBench +1.5分，Claw-Eval +1.8分，WebShop +1.7分

## 核心组件

### 1. 轨迹分析器（`core.trajectory_analyzer`）
- 解析包含状态、动作、观察、奖励的执行轨迹
- 从智能体行为中提取技能调用
- 计算轨迹级指标

### 2. 故障归因器（`core.fault_attributor`）
- 识别第一个可操作的故障步骤
- 将责任链接到候选技能
- 计算责任分数

### 3. 技能适配器（`core.skill_adapter`）
- 生成有针对性的技能更新
- 根据接受标准验证变更
- 管理技能库版本控制

## 使用方法

```python
from skill_adaptor import SkillAdaptor

# 初始化
adaptor = SkillAdaptor()

# 分析失败的轨迹
analysis = adaptor.analyze_trajectory(trajectory_data)

# 识别责任技能
faults = adaptor.attribute_faults(analysis)

# 适应技能
updated_skills = adaptor.adapt_skills(faults)
```

## 评估基准

- **WebShop**：电子商务任务成功率
- **PinchBench**：网页导航任务
- **Claw-Eval**：开放领域交互任务

## 论文引用

```
@article{yu2026skilladaptor,
  title={SkillAdaptor: Self-Adapting Skills for LLM Agents from Trajectories},
  author={Yu, Zhuoyun and Xie, Xin and Yao, Wuguannan and Wang, Chenxi and Liang, Lei and Qi, Xiang and Deng, Shumin},
  journal={arXiv preprint arXiv:2606.01311},
  year={2026}
}
```
