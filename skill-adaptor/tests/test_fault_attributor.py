"""
故障归因器测试
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trajectory_analyzer import Trajectory, TrajectoryStep
from core.fault_attributor import FaultAttributor, FaultType


class TestFaultAttributor(unittest.TestCase):
    """测试故障归因器"""
    
    def setUp(self):
        """设置测试环境"""
        self.attributor = FaultAttributor(responsibility_threshold=0.3)
    
    def test_identify_fault_steps(self):
        """测试识别故障步骤"""
        steps = [
            TrajectoryStep(0, {}, "a", "o", 0.1, None),
            TrajectoryStep(1, {}, "b", "o", -0.5, "skill1"),
            TrajectoryStep(2, {}, "c", "o", 0.2, None)
        ]
        trajectory = Trajectory("t1", "task1", steps, False, -0.2)
        
        fault_steps = self.attributor.identify_fault_steps(trajectory)
        
        self.assertEqual(len(fault_steps), 1)
        self.assertEqual(fault_steps[0].step_id, 1)
    
    def test_classify_fault(self):
        """测试故障分类"""
        step1 = TrajectoryStep(0, {}, "a", "o", -0.6, "skill1")
        step2 = TrajectoryStep(1, {}, "b", "o", -0.1, "skill2")
        step3 = TrajectoryStep(2, {}, "c", "o", 0.1, None)
        
        self.assertEqual(self.attributor.classify_fault(step1), FaultType.SKILL_MISUSE)
        self.assertEqual(self.attributor.classify_fault(step2), FaultType.OBSERVATION_MISINTERPRETATION)
        self.assertEqual(self.attributor.classify_fault(step3), FaultType.ACTION_ERROR)
    
    def test_calculate_responsibility(self):
        """测试计算责任"""
        steps = [
            TrajectoryStep(0, {}, "a", "o", 0.1, "skill_a"),
            TrajectoryStep(1, {}, "b", "o", -0.5, "skill_b")
        ]
        trajectory = Trajectory("t1", "task1", steps, False, -0.4)
        
        scores = self.attributor.calculate_responsibility(steps[1], trajectory)
        
        self.assertEqual(len(scores), 2)
        # 直接调用的技能分数应该更高
        self.assertEqual(scores[0].skill_name, "skill_b")
        self.assertGreater(scores[0].score, scores[1].score)
    
    def test_find_first_actionable_fault(self):
        """测试找到第一个可操作故障"""
        steps = [
            TrajectoryStep(0, {}, "a", "o", 0.1, "skill1"),
            TrajectoryStep(1, {}, "b", "o", -0.5, "skill2"),
            TrajectoryStep(2, {}, "c", "o", -0.3, "skill3")
        ]
        trajectory = Trajectory("t1", "task1", steps, False, -0.7)
        
        fault = self.attributor.find_first_actionable_fault(trajectory)
        
        self.assertIsNotNone(fault)
        self.assertEqual(fault.step_id, 1)
    
    def test_attribute(self):
        """测试完整归因"""
        steps = [
            TrajectoryStep(0, {}, "a", "o", 0.1, "s1"),
            TrajectoryStep(1, {}, "b", "o", -0.5, "s2")
        ]
        trajectory = Trajectory("t1", "task1", steps, False, -0.4)
        analysis = {"trajectory": trajectory}
        
        result = self.attributor.attribute(trajectory, analysis)
        
        self.assertTrue(result['has_fault'])
        self.assertIn('fault', result)
        self.assertIn('high_responsibility_skills', result)


if __name__ == '__main__':
    unittest.main()
