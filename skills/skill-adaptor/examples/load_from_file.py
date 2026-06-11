"""
从文件加载轨迹的示例
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill_adaptor import SkillAdaptor


def main():
    print("=== 从文件加载轨迹示例 ===\n")
    
    # 初始化
    adaptor = SkillAdaptor()
    
    # 文件路径
    file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "example_trajectory.json"
    )
    
    if not os.path.exists(file_path):
        print(f"错误：文件不存在: {file_path}")
        return
    
    print(f"加载轨迹文件: {file_path}\n")
    
    # 运行分析
    result = adaptor.run(file_path)
    
    # 显示详细信息
    analysis = result['analysis']
    print(f"轨迹ID: {analysis['trajectory_id']}")
    print(f"任务ID: {analysis['task_id']}")
    print(f"总步数: {analysis['metrics']['total_steps']}")
    print(f"技能调用次数: {analysis['metrics']['skill_invocations_count']}")
    
    print("\n技能使用情况:")
    for skill, count in analysis['metrics']['skill_usage'].items():
        print(f"  - {skill}: {count} 次")
    
    print("\n累计奖励:")
    rewards = analysis['metrics']['cumulative_rewards']
    for i, reward in enumerate(rewards):
        print(f"  步骤 {i}: {reward:.2f}")
    
    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()
