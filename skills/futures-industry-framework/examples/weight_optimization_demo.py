"""
权重优化示例
Weight Optimization Demo
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
    IntegratedAnalyzer,
    WeightOptimizer,
    WeightSaver
)

def main():
    print("=" * 60)
    print("Weight Optimization Demo")
    print("权重优化示例")
    print("=" * 60)
    print()
    
    # 创建优化器
    optimizer = WeightOptimizer()
    
    # 生成模拟历史数据
    print("1. 生成模拟历史数据...")
    historical_data = optimizer.generate_synthetic_historical_data(n_periods=500)
    print(f"   数据点数量: {len(historical_data)}")
    print(f"   列名: {list(historical_data.columns)}")
    
    # 优化权重
    print("\n2. 优化权重...")
    analyzer = IntegratedAnalyzer()
    comparison = analyzer.optimize_weights(historical_data)
    
    # 显示结果
    print("\n3. 结果对比:")
    print(f"   默认权重: {comparison['default']['weights']}")
    print(f"   优化权重: {comparison['optimized']['weights']}")
    print()
    print(f"   默认表现:")
    print(f"     总收益: {comparison['default']['performance']['total_return']:.2%}")
    print(f"     夏普比率: {comparison['default']['performance']['sharpe_ratio']:.2f}")
    print(f"   优化表现:")
    print(f"     总收益: {comparison['optimized']['performance']['total_return']:.2%}")
    print(f"     夏普比率: {comparison['optimized']['performance']['sharpe_ratio']:.2f}")
    
    # 保存权重
    print("\n4. 保存优化权重...")
    weight_path = os.path.join(os.path.dirname(__file__), "..", "optimized_weights.json")
    WeightSaver.save_weights(
        comparison['optimized']['weights'],
        weight_path,
        metadata={"optimized_date": "2026-05-31", "source": "demo"}
    )
    print(f"   权重已保存至: {weight_path}")
    
    print("\n完成！")

if __name__ == "__main__":
    main()
