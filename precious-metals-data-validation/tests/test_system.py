#!/usr/bin/env python3
"""
贵金属数据标准化系统测试脚本
测试系统的基本功能
"""

import os
import sys
import json
import pytest
from datetime import datetime

# 添加脚本目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
scripts_dir = os.path.join(parent_dir, 'scripts')
sys.path.append(scripts_dir)

def test_collector():
    """测试数据采集器"""
    print("测试数据采集器...")
    
    try:
        from precious_metals_data_collector import PreciousMetalsDataCollector
        
        collector = PreciousMetalsDataCollector()
        
        # 测试单个数据源
        print("  测试Investing.com数据源...")
        data = collector.fetch_investing_com_data('XAUUSD')
        
        if data:
            print(f"    ✓ 获取数据成功: {data.get('price', 0):.2f}")
            assert True
        else:
            print("    ✗ 获取数据失败")
            assert False, "获取数据失败"
            
    except Exception as e:
        print(f"    ✗ 测试失败: {e}")
        assert False, f"测试失败: {e}"

def test_difference_handler():
    """测试数据差异处理器"""
    print("测试数据差异处理器...")
    
    try:
        from data_difference_handler import DataDifferenceHandler
        
        handler = DataDifferenceHandler()
        
        # 测试数据
        test_data = [
            {
                'symbol': 'XAUUSD',
                'price': 4191.35,
                'source': 'investing_com',
                'timeframe': 'daily'
            },
            {
                'symbol': 'XAUUSD',
                'price': 4222.80,
                'source': 'barchart',
                'timeframe': 'daily'
            }
        ]
        
        # 测试差异检测
        print("  测试差异检测...")
        differences = handler.detect_differences(test_data)
        print(f"    ✓ 检测到 {len(differences)} 个差异")
        
        # 测试加权平均计算
        print("  测试加权平均计算...")
        weighted_avg = handler.calculate_weighted_average(test_data)
        
        if weighted_avg:
            print(f"    ✓ 加权平均价格: {weighted_avg.get('weighted_price', 0):.2f}")
            assert True
        else:
            print("    ✗ 加权平均计算失败")
            assert False, "加权平均计算失败"
            
    except Exception as e:
        print(f"    ✗ 测试失败: {e}")
        assert False, f"测试失败: {e}"

def test_validator():
    """测试数据验证器"""
    print("测试数据验证器...")
    
    try:
        from data_validation_script import DataValidationScript
        
        validator = DataValidationScript()
        
        # 测试数据
        test_data = [
            {
                'symbol': 'XAUUSD',
                'price': 4191.35,
                'change': -25.23,
                'change_percent': -0.60,
                'high': 4237.25,
                'low': 4153.10,
                'open': 4216.58,
                'close': 4191.35,
                'source': 'investing_com',
                'timestamp': datetime.now(),
                'rsi': 56.55,
                'macd': 4.17,
                'adx': 24.80,
                'cci': 95.91
            }
        ]
        
        # 测试验证
        print("  测试数据验证...")
        results = validator.validate_price_data(test_data)
        
        if results:
            print(f"    ✓ 验证完成，{len(results)} 个检查项")
            
            # 检查验证状态
            pass_count = sum(1 for r in results if r.status.value == 'pass')
            print(f"    ✓ 通过: {pass_count}")
            
            assert True
        else:
            print("    ✗ 验证失败")
            assert False, "验证失败"
            
    except Exception as e:
        print(f"    ✗ 测试失败: {e}")
        assert False, f"测试失败: {e}"

def test_system_integration():
    """测试系统集成"""
    print("测试系统集成...")
    
    try:
        from precious_metals_data_system import PreciousMetalsDataSystem
        
        system = PreciousMetalsDataSystem()
        
        # 测试配置
        print("  测试系统配置...")
        print(f"    ✓ 品种列表: {system.config['symbols']}")
        print(f"    ✓ 输出目录: {system.config['output_directory']}")
        
        # 测试目录创建
        print("  测试输出目录...")
        os.makedirs(system.config['output_directory'], exist_ok=True)
        print(f"    ✓ 目录创建成功")
        
        assert True
        
    except Exception as e:
        print(f"    ✗ 测试失败: {e}")
        assert False, f"测试失败: {e}"

def run_all_tests():
    """运行所有测试"""
    print("贵金属数据标准化系统测试")
    print("=" * 50)
    
    tests = [
        ("数据采集器", test_collector),
        ("数据差异处理器", test_difference_handler),
        ("数据验证器", test_validator),
        ("系统集成", test_system_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ✗ 测试异常: {e}")
            results.append((test_name, False))
    
    # 打印测试结果
    print("\n" + "=" * 50)
    print("测试结果摘要")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{test_name}: {status}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)