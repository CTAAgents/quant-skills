"""
运行所有测试并生成测试报告
"""
import unittest
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_test_suite():
    """创建测试套件"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试
    test_files = [
        'test_industry_chain.py',
        'test_weight_optimization.py',
        'test_resonance_detection.py',
        'test_integrated_analyzer.py'
    ]
    
    for test_file in test_files:
        test_path = os.path.join(os.path.dirname(__file__), test_file)
        if os.path.exists(test_path):
            tests = loader.loadTestsFromName(
                test_file.replace('.py', '')
            )
            suite.addTests(tests)
    
    return suite

def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("期货产业链分析框架 - 完整测试套件")
    print("=" * 60)
    print()
    
    suite = create_test_suite()
    
    # 创建测试运行器
    runner = unittest.TextTestRunner(verbosity=2)
    
    # 运行测试
    result = runner.run(suite)
    
    # 打印总结
    print()
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"运行测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print()
    
    if result.failures:
        print("失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}")
            print(f"    详情: {traceback[:100]}...")
        print()
    
    if result.errors:
        print("错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}")
            print(f"    详情: {traceback[:100]}...")
        print()
    
    # 返回是否成功
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
