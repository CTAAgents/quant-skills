"""
快速入门示例
Quick Start Example
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
    IntegratedAnalyzer,
    quick_analyze,
    create_sample_data
)

def main():
    print("=" * 60)
    print("Futures Industry Framework - Quick Start")
    print("期货产业链框架 - 快速入门")
    print("=" * 60)
    print()
    
    # 创建示例数据
    print("1. 创建示例数据...")
    chain_metrics, fund_metrics, tech_metrics = create_sample_data()
    
    # 方式1：使用便捷函数
    print("\n2. 使用便捷函数分析...")
    report = quick_analyze(chain_metrics, fund_metrics, tech_metrics, "黑色建材产业链")
    print(report)
    
    # 方式2：使用集成分析器
    print("\n3. 使用集成分析器...")
    analyzer = IntegratedAnalyzer()
    result = analyzer.analyze(chain_metrics, fund_metrics, tech_metrics, "能化产业链")
    
    # 访问具体结果
    print(f"产业链评分: {result.industry_chain_score:.1f}")
    print(f"基本面评分: {result.fundamental_score:.1f}")
    print(f"技术面评分: {result.technical_score:.1f}")
    print(f"共振方向: {result.resonance_signal.direction.value}")
    print(f"操作建议: {result.resonance_signal.action_recommendation}")
    
    print("\n完成！")

if __name__ == "__main__":
    main()
