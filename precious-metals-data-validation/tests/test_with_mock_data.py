#!/usr/bin/env python3
"""
使用模拟数据测试贵金属数据标准化系统
"""

import os
import sys
from datetime import datetime

# 添加脚本目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from mock_data_collector import MockDataCollector
from data_difference_handler import DataDifferenceHandler
from data_validation_script import DataValidationScript

def test_with_mock_data():
    """使用模拟数据测试系统"""
    print("使用模拟数据测试贵金属数据标准化系统")
    print("=" * 60)
    
    # 1. 生成模拟数据
    print("1. 生成模拟数据...")
    collector = MockDataCollector()
    symbols = ['XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD']
    all_data = collector.collect_mock_data(symbols)
    
    for symbol, data_list in all_data.items():
        print(f"  {symbol}: 生成 {len(data_list)} 个数据源")
    
    # 2. 测试数据差异处理
    print("\n2. 测试数据差异处理...")
    difference_handler = DataDifferenceHandler()
    
    for symbol, data_list in all_data.items():
        print(f"\n  {symbol}:")
        
        # 检测差异
        differences = difference_handler.detect_differences(data_list)
        print(f"    检测到 {len(differences)} 个差异")
        
        # 处理差异
        processed_data = difference_handler.handle_differences(data_list, differences)
        print(f"    处理后保留 {len(processed_data)} 个数据源")
        
        # 计算加权平均
        weighted_avg = difference_handler.calculate_weighted_average(processed_data)
        if weighted_avg:
            print(f"    加权平均价格: {weighted_avg.get('weighted_price', 0):.2f}")
    
    # 3. 测试数据验证
    print("\n3. 测试数据验证...")
    validator = DataValidationScript()
    
    for symbol, data_list in all_data.items():
        print(f"\n  {symbol}:")
        
        # 运行验证
        validation_report = validator.run_full_validation(symbol, data_list)
        
        print(f"    验证状态: {validation_report['overall_status']}")
        print(f"    验证分数: {validation_report['validation_score']:.1f}/100")
        print(f"    检查项数: {validation_report['statistics']['total_checks']}")
        print(f"    通过: {validation_report['statistics']['pass_count']}")
        print(f"    警告: {validation_report['statistics']['warning_count']}")
        print(f"    失败: {validation_report['statistics']['fail_count']}")
    
    # 4. 生成综合报告
    print("\n4. 生成综合报告...")
    generate_comprehensive_report(all_data)
    
    print("\n" + "=" * 60)
    print("模拟数据测试完成")

def generate_comprehensive_report(all_data):
    """生成综合报告"""
    report_lines = []
    report_lines.append("贵金属数据标准化系统测试报告")
    report_lines.append("=" * 60)
    report_lines.append(f"测试时间: {datetime.now()}")
    report_lines.append("")
    
    for symbol, data_list in all_data.items():
        report_lines.append(f"{symbol} 数据摘要:")
        report_lines.append("-" * 40)
        
        # 价格数据
        prices = [d['price'] for d in data_list if 'price' in d]
        if prices:
            report_lines.append(f"  数据源数量: {len(data_list)}")
            report_lines.append(f"  价格范围: {min(prices):.2f} - {max(prices):.2f}")
            report_lines.append(f"  平均价格: {sum(prices)/len(prices):.2f}")
        
        # 技术指标
        rsi_values = [d.get('rsi', 0) for d in data_list if 'rsi' in d]
        if rsi_values:
            report_lines.append(f"  RSI范围: {min(rsi_values):.2f} - {max(rsi_values):.2f}")
            report_lines.append(f"  平均RSI: {sum(rsi_values)/len(rsi_values):.2f}")
        
        report_lines.append("")
    
    # 保存报告
    report_filename = f"F:/Commodities/Reports/validation/test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    os.makedirs(os.path.dirname(report_filename), exist_ok=True)
    
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print(f"  综合报告已保存: {report_filename}")

if __name__ == "__main__":
    test_with_mock_data()