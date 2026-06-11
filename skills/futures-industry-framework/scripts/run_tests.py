"""
测试运行脚本
Test Runner Script
"""
import unittest
import sys
import os
from pathlib import Path

def run_all_tests():
    """运行所有测试"""
    # 添加项目根目录到路径
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 加载所有测试模块
    test_modules = [
        'tests.test_industry_chain',
        'tests.test_weight_optimization',
        'tests.test_resonance_detection',
        'tests.test_integrated_analyzer'
    ]
    
    for module in test_modules:
        try:
            tests = loader.loadTestsFromName(module)
            suite.addTests(tests)
            print(f"✅ 加载测试: {module}")
        except Exception as e:
            print(f"❌ 加载失败: {module} - {e}")
    
    # 运行测试
    print("\n" + "=" * 60)
    print("期货产业链分析框架 - 完整测试套件")
    print("=" * 60)
    print()
    
    # 使用详细输出
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"运行测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  ❌ {test}")
            print(f"     详情: {traceback.split('\\n')[-2]}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"  💥 {test}")
            print(f"     详情: {traceback.split('\\n')[-2]}")
    
    # 返回退出码
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
