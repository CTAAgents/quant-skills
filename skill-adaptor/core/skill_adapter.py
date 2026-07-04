"""
技能适配器模块
"""
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
from enum import Enum


class UpdateStatus(Enum):
    """更新状态"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass
class Skill:
    """技能定义"""
    skill_id: str
    name: str
    description: str
    version: str = "1.0.0"
    code: str = ""
    examples: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillUpdate:
    """技能更新"""
    update_id: str
    skill_id: str
    old_version: str
    new_version: str
    changes: str
    reasoning: str
    status: UpdateStatus = UpdateStatus.PENDING
    acceptance_checks: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    applied_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillAdapter:
    """
    技能适配器
    
    功能：
    - 生成有针对性的技能更新
    - 根据接受标准验证变更
    - 管理技能库版本控制
    """
    
    def __init__(self, skills_dir: str = "./data/skills"):
        self.skills_dir = skills_dir
        self.skills: Dict[str, Skill] = {}
        self.updates: List[SkillUpdate] = []
        self._load_skills()
        
    def _load_skills(self):
        """加载技能库"""
        # 这里可以实现从文件系统加载技能的逻辑
        pass
        
    def load_skill(self, skill_id: str) -> Optional[Skill]:
        """加载单个技能"""
        if skill_id in self.skills:
            return self.skills[skill_id]
        return None
        
    def save_skill(self, skill: Skill):
        """保存技能"""
        self.skills[skill.skill_id] = skill
        # 这里可以实现保存到文件系统的逻辑
        
    def generate_update(self, skill: Skill, fault_info: Dict[str, Any],
                       reasoning: str) -> SkillUpdate:
        """生成技能更新建议"""
        # 简单的版本递增
        major, minor, patch = map(int, skill.version.split('.'))
        new_version = f"{major}.{minor}.{patch + 1}"
        
        # 基于故障信息生成变更描述
        changes = self._generate_changes_description(skill, fault_info)
        
        update = SkillUpdate(
            update_id=f"update_{skill.skill_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            skill_id=skill.skill_id,
            old_version=skill.version,
            new_version=new_version,
            changes=changes,
            reasoning=reasoning,
            status=UpdateStatus.PENDING
        )
        
        # 添加接受检查
        update.acceptance_checks = self._generate_acceptance_checks(skill, fault_info)
        
        self.updates.append(update)
        return update
    
    def _generate_changes_description(self, skill: Skill, 
                                     fault_info: Dict[str, Any]) -> str:
        """生成变更描述"""
        fault = fault_info.get('fault')
        if fault:
            return f"修复技能 {skill.name} 在故障类型 {fault.fault_type.value} 中的问题"
        return f"技能 {skill.name} 的改进更新"
    
    def _generate_acceptance_checks(self, skill: Skill, 
                                    fault_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成接受检查列表"""
        checks = [
            {
                'check_id': 'reward_improvement',
                'description': '在类似任务上验证奖励提升',
                'status': 'pending'
            },
            {
                'check_id': 'no_regression',
                'description': '验证在已有成功任务上无回归',
                'status': 'pending'
            },
            {
                'check_id': 'human_review',
                'description': '人工审查变更内容',
                'status': 'pending'
            }
        ]
        return checks
    
    def validate_update(self, update: SkillUpdate, 
                       validation_results: Dict[str, bool]) -> bool:
        """验证技能更新是否满足接受标准"""
        all_passed = all(validation_results.values())
        
        if all_passed:
            update.status = UpdateStatus.ACCEPTED
        else:
            update.status = UpdateStatus.REJECTED
        
        return all_passed
    
    def apply_update(self, update: SkillUpdate, new_skill_code: str) -> Optional[Skill]:
        """应用技能更新"""
        if update.status != UpdateStatus.ACCEPTED:
            return None
        
        skill = self.skills.get(update.skill_id)
        if not skill:
            return None
        
        # 更新技能
        skill.version = update.new_version
        skill.code = new_skill_code
        skill.updated_at = datetime.now()
        update.status = UpdateStatus.APPLIED
        update.applied_at = datetime.now()
        
        self.save_skill(skill)
        return skill
    
    def adapt(self, fault_attribution: Dict[str, Any]) -> List[SkillUpdate]:
        """完整的技能适应流程"""
        updates = []
        
        if not fault_attribution.get('has_fault'):
            return updates
        
        # 对每个高责任技能生成更新
        high_skills = fault_attribution.get('high_responsibility_skills', [])
        for resp_score in high_skills:
            skill = self.load_skill(resp_score.skill_name)
            if skill:
                update = self.generate_update(
                    skill,
                    fault_attribution,
                    resp_score.reasoning
                )
                updates.append(update)
        
        return updates
