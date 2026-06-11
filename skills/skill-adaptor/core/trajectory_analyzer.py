"""
轨迹分析器模块
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class TrajectoryStep:
    """轨迹中的单个步骤"""
    step_id: int
    state: Dict[str, Any] = field(default_factory=dict)
    action: str = ""
    observation: str = ""
    reward: float = 0.0
    skill_invoked: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trajectory:
    """完整的执行轨迹"""
    trajectory_id: str
    task_id: str
    steps: List[TrajectoryStep] = field(default_factory=list)
    success: bool = False
    final_reward: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class TrajectoryAnalyzer:
    """
    轨迹分析器
    
    功能：
    - 解析和分析智能体执行轨迹
    - 提取技能调用模式
    - 计算轨迹级指标
    """
    
    def __init__(self):
        self.trajectories: List[Trajectory] = []
        
    def load_trajectory(self, file_path: str) -> Trajectory:
        """从文件加载轨迹"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        steps = []
        for step_data in data.get('steps', []):
            step = TrajectoryStep(
                step_id=step_data.get('step_id'),
                state=step_data.get('state', {}),
                action=step_data.get('action', ''),
                observation=step_data.get('observation', ''),
                reward=step_data.get('reward', 0.0),
                skill_invoked=step_data.get('skill_invoked'),
                metadata=step_data.get('metadata', {})
            )
            steps.append(step)
        
        trajectory = Trajectory(
            trajectory_id=data.get('trajectory_id', ''),
            task_id=data.get('task_id', ''),
            steps=steps,
            success=data.get('success', False),
            final_reward=data.get('final_reward', 0.0),
            metadata=data.get('metadata', {})
        )
        
        self.trajectories.append(trajectory)
        return trajectory
    
    def parse_trajectory(self, raw_data: Dict[str, Any]) -> Trajectory:
        """解析原始轨迹数据"""
        steps = []
        for i, step_data in enumerate(raw_data.get('steps', [])):
            step = TrajectoryStep(
                step_id=i,
                state=step_data.get('state', {}),
                action=step_data.get('action', ''),
                observation=step_data.get('observation', ''),
                reward=step_data.get('reward', 0.0),
                skill_invoked=step_data.get('skill_invoked')
            )
            steps.append(step)
        
        return Trajectory(
            trajectory_id=raw_data.get('trajectory_id', ''),
            task_id=raw_data.get('task_id', ''),
            steps=steps,
            success=raw_data.get('success', False),
            final_reward=raw_data.get('final_reward', 0.0)
        )
    
    def extract_skill_invocations(self, trajectory: Trajectory) -> List[Dict[str, Any]]:
        """从轨迹中提取技能调用"""
        invocations = []
        for step in trajectory.steps:
            if step.skill_invoked:
                invocations.append({
                    'step_id': step.step_id,
                    'skill': step.skill_invoked,
                    'state': step.state,
                    'action': step.action,
                    'reward': step.reward
                })
        return invocations
    
    def compute_metrics(self, trajectory: Trajectory) -> Dict[str, Any]:
        """计算轨迹级指标"""
        total_steps = len(trajectory.steps)
        skill_invocations = self.extract_skill_invocations(trajectory)
        
        # 计算累计奖励
        cumulative_rewards = []
        total_reward = 0.0
        for step in trajectory.steps:
            total_reward += step.reward
            cumulative_rewards.append(total_reward)
        
        # 技能使用统计
        skill_usage = {}
        for inv in skill_invocations:
            skill = inv['skill']
            skill_usage[skill] = skill_usage.get(skill, 0) + 1
        
        return {
            'total_steps': total_steps,
            'success': trajectory.success,
            'final_reward': trajectory.final_reward,
            'cumulative_rewards': cumulative_rewards,
            'skill_invocations_count': len(skill_invocations),
            'skill_usage': skill_usage,
            'avg_reward_per_step': total_reward / total_steps if total_steps > 0 else 0.0
        }
    
    def analyze(self, trajectory: Trajectory) -> Dict[str, Any]:
        """完整的轨迹分析"""
        metrics = self.compute_metrics(trajectory)
        skill_invocations = self.extract_skill_invocations(trajectory)
        
        return {
            'trajectory_id': trajectory.trajectory_id,
            'task_id': trajectory.task_id,
            'metrics': metrics,
            'skill_invocations': skill_invocations,
            'trajectory': trajectory
        }
