"""
SkillAdaptor：基于轨迹的LLM智能体自适应技能框架

基于论文 "SkillAdaptor: Self-Adapting Skills for LLM Agents from Trajectories"（arXiv:2606.01311）
"""
from .core import (
    TrajectoryAnalyzer, Trajectory, TrajectoryStep,
    FaultAttributor, Fault, ResponsibilityScore,
    SkillAdapter, Skill, SkillUpdate
)

__version__ = "1.0.0"
__all__ = [
    "SkillAdaptor",
    "TrajectoryAnalyzer", "Trajectory", "TrajectoryStep",
    "FaultAttributor", "Fault", "ResponsibilityScore",
    "SkillAdapter", "Skill", "SkillUpdate",
]


class SkillAdaptor:
    """
    SkillAdaptor 主类
    
    完整的技能适应框架，整合轨迹分析、故障归因和技能适应功能
    """
    
    def __init__(self, responsibility_threshold: float = 0.3, 
                 skills_dir: str = "./data/skills"):
        self.trajectory_analyzer = TrajectoryAnalyzer()
        self.fault_attributor = FaultAttributor(responsibility_threshold)
        self.skill_adapter = SkillAdapter(skills_dir)
        
    def load_trajectory(self, file_path: str) -> Trajectory:
        """加载轨迹文件"""
        return self.trajectory_analyzer.load_trajectory(file_path)
    
    def analyze_trajectory(self, trajectory_data) -> dict:
        """分析轨迹"""
        if isinstance(trajectory_data, str):
            trajectory = self.load_trajectory(trajectory_data)
        elif isinstance(trajectory_data, dict):
            trajectory = self.trajectory_analyzer.parse_trajectory(trajectory_data)
        else:
            trajectory = trajectory_data
        
        return self.trajectory_analyzer.analyze(trajectory)
    
    def attribute_faults(self, analysis: dict) -> dict:
        """故障归因"""
        trajectory = analysis.get('trajectory')
        return self.fault_attributor.attribute(trajectory, analysis)
    
    def adapt_skills(self, fault_attribution: dict) -> list:
        """技能适应"""
        return self.skill_adapter.adapt(fault_attribution)
    
    def run(self, trajectory_data) -> dict:
        """
        完整的 SkillAdaptor 流程
        
        Args:
            trajectory_data: 轨迹数据（文件路径、字典或 Trajectory 对象）
            
        Returns:
            完整的分析和适应结果
        """
        # 步骤1：分析轨迹
        analysis = self.analyze_trajectory(trajectory_data)
        
        # 步骤2：故障归因
        fault_attribution = self.attribute_faults(analysis)
        
        # 步骤3：技能适应
        skill_updates = self.adapt_skills(fault_attribution)
        
        return {
            'analysis': analysis,
            'fault_attribution': fault_attribution,
            'skill_updates': skill_updates
        }
