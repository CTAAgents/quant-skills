"""
SkillAdaptor 基础使用示例
"""
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill_adaptor import SkillAdaptor


def main():
    print("=== SkillAdaptor 基础使用示例 ===\n")
    
    # 初始化 SkillAdaptor
    adaptor = SkillAdaptor()
    
    # 示例1：从字典创建轨迹并分析
    print("1. 从字典数据创建并分析轨迹...")
    trajectory_data = {
        "trajectory_id": "example_001",
        "task_id": "test_task_001",
        "success": False,
        "final_reward": -0.5,
        "steps": [
            {
                "step_id": 0,
                "state": {"status": "start"},
                "action": "do_something",
                "observation": "Result A",
                "reward": 0.1,
                "skill_invoked": "skill_a"
            },
            {
                "step_id": 1,
                "state": {"status": "middle"},
                "action": "do_something_else",
                "observation": "Error occurred",
                "reward": -0.5,
                "skill_invoked": "skill_b"
            }
        ]
    }
    
    # 运行完整流程
    result = adaptor.run(trajectory_data)
    
    # 打印结果
    print("\n=== 分析结果 ===")
    print(f"轨迹ID: {result['analysis']['trajectory_id']}")
    print(f"是否成功: {result['analysis']['metrics']['success']}")
    print(f"最终奖励: {result['analysis']['metrics']['final_reward']}")
    
    print(f"\n=== 故障归因 ===")
    if result['fault_attribution']['has_fault']:
        fault = result['fault_attribution']['fault']
        print(f"故障步骤: {fault.step_id}")
        print(f"故障类型: {fault.fault_type.value}")
        print(f"责任技能:")
        for score in result['fault_attribution']['high_responsibility_skills']:
            print(f"  - {score.skill_name}: {score.score:.2f}")
    else:
        print("未检测到故障")
    
    print(f"\n=== 技能更新 ===")
    print(f"生成的更新数量: {len(result['skill_updates'])}")
    for update in result['skill_updates']:
        print(f"  - {update.skill_id}: {update.old_version} -> {update.new_version}")
    
    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()
