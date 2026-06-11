"""
故障归因器模块
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from .trajectory_analyzer import Trajectory, TrajectoryStep


class FaultType(Enum):
    """故障类型"""
    ACTION_ERROR = "action_error"
    SKILL_MISUSE = "skill_misuse"
    OBSERVATION_MISINTERPRETATION = "observation_misinterpretation"
    GOAL_MISALIGNMENT = "goal_misalignment"
    UNKNOWN = "unknown"


@dataclass
class ResponsibilityScore:
    """技能责任分数"""
    skill_name: str
    score: float
    reasoning: str = ""
    evidence: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Fault:
    """故障信息"""
    fault_id: str
    step_id: int
    fault_type: FaultType
    description: str
    responsible_skills: List[ResponsibilityScore]
    is_actionable: bool = True
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class FaultAttributor:
    """
    故障归因器
    
    功能：
    - 识别第一个可操作的故障步骤
    - 将责任链接到候选技能
    - 计算责任分数
    """
    
    def __init__(self, responsibility_threshold: float = 0.3):
        self.responsibility_threshold = responsibility_threshold
        self.faults: List[Fault] = []
        
    def identify_fault_steps(self, trajectory: Trajectory) -> List[TrajectoryStep]:
        """识别可能的故障步骤"""
        fault_candidates = []
        
        for i, step in enumerate(trajectory.steps):
            # 检查负奖励
            if step.reward < 0:
                fault_candidates.append(step)
            
            # 检查技能调用后的不良结果
            if step.skill_invoked and i + 1 < len(trajectory.steps):
                next_step = trajectory.steps[i + 1]
                if next_step.reward < step.reward:
                    fault_candidates.append(step)
        
        return fault_candidates
    
    def classify_fault(self, step: TrajectoryStep) -> FaultType:
        """对故障进行分类"""
        if not step.skill_invoked:
            return FaultType.ACTION_ERROR
        
        # 简单的故障分类逻辑（实际使用时可根据需要扩展）
        if step.reward < -0.5:
            return FaultType.SKILL_MISUSE
        elif step.reward < 0:
            return FaultType.OBSERVATION_MISINTERPRETATION
        else:
            return FaultType.UNKNOWN
    
    def calculate_responsibility(self, step: TrajectoryStep, 
                               trajectory: Trajectory) -> List[ResponsibilityScore]:
        """计算技能的责任分数"""
        scores = []
        
        if step.skill_invoked:
            # 直接调用的技能责任最高
            direct_score = ResponsibilityScore(
                skill_name=step.skill_invoked,
                score=0.8,
                reasoning="直接调用的技能在故障步骤被使用",
                evidence=[{
                    'step_id': step.step_id,
                    'skill': step.skill_invoked,
                    'reward': step.reward
                }]
            )
            scores.append(direct_score)
        
        # 查找之前调用过的相关技能
        for prev_step in trajectory.steps[:step.step_id]:
            if prev_step.skill_invoked and prev_step.skill_invoked != step.skill_invoked:
                # 相关技能可能有部分责任
                score = ResponsibilityScore(
                    skill_name=prev_step.skill_invoked,
                    score=0.2,
                    reasoning=f"在故障前调用的技能（步骤 {prev_step.step_id}）",
                    evidence=[{
                        'step_id': prev_step.step_id,
                        'skill': prev_step.skill_invoked,
                        'reward': prev_step.reward
                    }]
                )
                scores.append(score)
        
        return scores
    
    def find_first_actionable_fault(self, trajectory: Trajectory) -> Optional[Fault]:
        """找到第一个可操作的故障"""
        fault_candidates = self.identify_fault_steps(trajectory)
        
        for step in fault_candidates:
            fault_type = self.classify_fault(step)
            responsibility_scores = self.calculate_responsibility(step, trajectory)
            
            if responsibility_scores:
                fault = Fault(
                    fault_id=f"fault_{trajectory.trajectory_id}_{step.step_id}",
                    step_id=step.step_id,
                    fault_type=fault_type,
                    description=f"在步骤 {step.step_id} 检测到潜在故障",
                    responsible_skills=responsibility_scores,
                    is_actionable=True,
                    timestamp=step.timestamp.timestamp() if step.timestamp else 0.0
                )
                self.faults.append(fault)
                return fault
        
        return None
    
    def attribute(self, trajectory: Trajectory, 
                trajectory_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """完整的故障归因流程"""
        # 找到第一个可操作的故障
        fault = self.find_first_actionable_fault(trajectory)
        
        if not fault:
            return {
                'has_fault': False,
                'message': '未检测到可操作的故障',
                'trajectory_id': trajectory.trajectory_id
            }
        
        # 筛选责任分数超过阈值的技能
        high_responsibility = [
            score for score in fault.responsible_skills
            if score.score >= self.responsibility_threshold
        ]
        
        return {
            'has_fault': True,
            'fault': fault,
            'high_responsibility_skills': high_responsibility,
            'trajectory_id': trajectory.trajectory_id
        }
