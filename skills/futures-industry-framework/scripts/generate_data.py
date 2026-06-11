"""
示例数据生成脚本
Generate Sample Data Script
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from core import create_sample_data, IntegratedAnalyzer

def generate_sample_dataset(n_samples=100):
    """
    生成示例数据集
    
    Args:
        n_samples: 样本数量
    """
    print("=" * 60)
    print("生成示例数据集")
    print("=" * 60)
    print()
    
    # 生成模拟历史数据
    dates = pd.date_range(start='2020-01-01', periods=n_samples, freq='D')
    
    data = {
        'date': dates,
        'industry_chain_score': np.random.uniform(40, 70, n_samples),
        'fundamental_score': np.random.uniform(35, 75, n_samples),
        'technical_score': np.random.uniform(30, 80, n_samples),
        'future_return': np.random.uniform(-0.1, 0.15, n_samples)
    }
    
    df = pd.DataFrame(data)
    
    # 添加一些趋势
    df['industry_chain_score'] += np.linspace(0, 10, n_samples)
    df['fundamental_score'] += np.linspace(5, 15, n_samples)
    df['technical_score'] += np.linspace(-5, 20, n_samples)
    
    # 限制范围
    df['industry_chain_score'] = df['industry_chain_score'].clip(0, 100)
    df['fundamental_score'] = df['fundamental_score'].clip(0, 100)
    df['technical_score'] = df['technical_score'].clip(0, 100)
    
    # 保存数据
    output_dir = Path(__file__).parent.parent / 'data'
    output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / 'sample_historical_data.csv'
    df.to_csv(output_path, index=False)
    print(f"✅ 示例数据已保存至: {output_path}")
    print(f"   数据点数量: {len(df)}")
    print(f"   日期范围: {df['date'].min()} 至 {df['date'].max()}")
    
    return df

def generate_analysis_example():
    """生成分析示例"""
    print("\n生成分析示例...")
    
    # 创建示例数据
    chain_metrics, fund_metrics, tech_metrics = create_sample_data()
    
    # 创建分析器
    analyzer = IntegratedAnalyzer()
    
    # 执行分析
    result = analyzer.analyze(
        chain_metrics,
        fund_metrics,
        tech_metrics,
        "测试产业链"
    )
    
    # 输出结果
    print(f"\n产业链评分: {result.industry_chain_score:.1f}")
    print(f"基本面评分: {result.fundamental_score:.1f}")
    print(f"技术面评分: {result.technical_score:.1f}")
    print(f"共振方向: {result.resonance_signal.direction.value}")
    print(f"共振强度: {result.resonance_signal.level.value}")
    print(f"操作建议: {result.resonance_signal.action_recommendation}")
    
    # 保存报告
    report = analyzer.generate_report(result)
    
    output_dir = Path(__file__).parent.parent / 'output' / 'reports'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / 'sample_analysis_report.txt'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 分析报告已保存至: {output_path}")

def main():
    """主函数"""
    print("=" * 60)
    print("Futures Industry Framework - Data Generator")
    print("期货产业链框架 - 数据生成器")
    print("=" * 60)
    print()
    
    # 生成数据集
    df = generate_sample_dataset(n_samples=500)
    
    # 生成分析示例
    generate_analysis_example()
    
    print("\n" + "=" * 60)
    print("完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
