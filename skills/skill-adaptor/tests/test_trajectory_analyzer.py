"""
轨迹分析器测试
"""
import unittest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trajectory_analyzer import TrajectoryAnalyzer, Trajectory, TrajectoryStep


class TestTrajectoryAnalyzer(unittest.TestCase):
    """测试轨迹分析器"""
    
    def setUp(self):
        """设置测试环境"""
        self.analyzer = TrajectoryAnalyzer()
    
    def test_parse_trajectory(self):
        """测试解析轨迹"""
        raw_data = {
            "trajectory_id": "test_001",
            "task_id": "task_001",
            "success": False,
            "final_reward": -0.5,
            "steps": [
                {
                    "step_id": 0,
                    "state": {"x": 1},
                    "action": "move",
                    "observation": "moved",
                    "reward": 0.1,
                    "skill_invoked": "nav_skill"
                }
            ]
        }
        
        trajectory = self.analyzer.parse_trajectory(raw_data)
        
        self.assertEqual(trajectory.trajectory_id, "test_001")
        self.assertEqual(len(trajectory.steps), 1)
        self.assertFalse(trajectory.success)
    
    def test_extract_skill_invocations(self):
        """测试提取技能调用"""
        steps = [
            TrajectoryStep(0, {}, "act1", "obs1", 0.1, "skill1"),
            TrajectoryStep(1, {}, "act2", "obs2", 0.2, None),
            TrajectoryStep(2, {}, "act3", "obs3", -0.1, "skill2")
        ]
        trajectory = Trajectory("t1", "task1", steps, False, 0.0)
        
        invocations = self.analyzer.extract_skill_invocations(trajectory)
        
        self.assertEqual(len(invocations), 2)
        self.assertEqual(invocations[0]['skill'], 'skill1')
        self.assertEqual(invocations[1]['skill'], 'skill2')
    
    def test_compute_metrics(self):
        """测试计算指标"""
        steps = [
            TrajectoryStep(0, {}, "a", "o", 0.5, "s1"),
            TrajectoryStep(1, {}, "b", "o", -0.2, "s1"),
            TrajectoryStep(2, {}, "c", "o", 0.3, "s2")
        ]
        trajectory = Trajectory("t1", "task1", steps, True, 0.6)
        
        metrics = self.analyzer.compute_metrics(trajectory)
        
        self.assertEqual(metrics['total_steps'], 3)
        self.assertTrue(metrics['success'])
        self.assertEqual(metrics['final_reward'], 0.6)
        self.assertEqual(metrics['skill_invocations_count'], 3)
        self.assertEqual(metrics['skill_usage']['s1'], 2)
        self.assertEqual(metrics['skill_usage']['s2'], 1)
    
    def test_analyze(self):
        """测试完整分析"""
        steps = [
            TrajectoryStep(0, {}, "a", "o", 0.5, "s1"),
            TrajectoryStep(1, {}, "b", "o", -0.5, "s2")
        ]
        trajectory = Trajectory("t1", "task1", steps, False, 0.0)
        
        result = self.analyzer.analyze(trajectory)
        
        self.assertIn('trajectory_id', result)
        self.assertIn('metrics', result)
        self.assertIn('skill_invocations', result)


if __name__ == '__main__':
    unittest.main()
