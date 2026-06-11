"""
集成测试
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill_adaptor import SkillAdaptor


class TestSkillAdaptorIntegration(unittest.TestCase):
    """SkillAdaptor 集成测试"""
    
    def test_full_workflow(self):
        """测试完整工作流"""
        adaptor = SkillAdaptor()
        
        # 创建测试数据
        trajectory_data = {
            "trajectory_id": "integration_test_001",
            "task_id": "test_task",
            "success": False,
            "final_reward": -0.5,
            "steps": [
                {
                    "step_id": 0,
                    "state": {"x": 1},
                    "action": "start",
                    "observation": "started",
                    "reward": 0.1,
                    "skill_invoked": "init_skill"
                },
                {
                    "step_id": 1,
                    "state": {"x": 2},
                    "action": "process",
                    "observation": "error",
                    "reward": -0.5,
                    "skill_invoked": "process_skill"
                }
            ]
        }
        
        # 运行完整流程
        result = adaptor.run(trajectory_data)
        
        # 验证结果
        self.assertIn('analysis', result)
        self.assertIn('fault_attribution', result)
        self.assertIn('skill_updates', result)
        
        # 验证分析结果
        self.assertEqual(result['analysis']['trajectory_id'], 'integration_test_001')
        self.assertEqual(result['analysis']['metrics']['total_steps'], 2)
        
        # 验证故障归因
        self.assertTrue(result['fault_attribution']['has_fault'])


if __name__ == '__main__':
    unittest.main()
