#!/usr/bin/env python3
"""
NeoData贵金属数据采集器测试
测试优化后的数据采集功能
"""

import sys
import os
import time
from datetime import datetime

# 添加scripts目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

def test_neodata_collector():
    """测试NeoData数据采集器"""
    print("=" * 60)
    print("NeoData贵金属数据采集器测试")
    print("=" * 60)
    
    try:
        from neodata_data_collector import NeoDataPreciousMetalsCollector
        
        # 初始化采集器
        print("\n1. 初始化NeoData数据采集器...")
        collector = NeoDataPreciousMetalsCollector()
        print("   ✓ 采集器初始化成功")
        
        # 测试单品种数据采集
        print("\n2. 测试单品种数据采集...")
        test_symbols = ['XAUUSD', 'XAGUSD', 'AU9999']
        
        for symbol in test_symbols:
            print(f"\n   测试 {symbol}:")
            start_time = time.time()
            price_data = collector.get_price(symbol)
            elapsed = time.time() - start_time
            
            if price_data:
                print(f"   ✓ 获取成功 ({elapsed:.2f}秒)")
                print(f"     价格: {price_data.price}")
                print(f"     涨跌: {price_data.change} ({price_data.change_percent:.2f}%)")
                print(f"     最高: {price_data.high}")
                print(f"     最低: {price_data.low}")
                print(f"     数据源: {price_data.source}")
            else:
                print(f"   ✗ 获取失败 ({elapsed:.2f}秒)")
        
        # 测试批量数据采集
        print("\n3. 测试批量数据采集...")
        start_time = time.time()
        all_prices = collector.get_all_prices()
        elapsed = time.time() - start_time
        
        successful = sum(1 for p in all_prices.values() if p is not None)
        total = len(all_prices)
        
        print(f"   批量采集完成: {successful}/{total} 成功 ({elapsed:.2f}秒)")
        
        # 显示统计信息
        print("\n4. 性能统计:")
        stats = collector.get_stats()
        print(f"   总查询次数: {stats['total_queries']}")
        print(f"   成功次数: {stats['successful_queries']}")
        print(f"   失败次数: {stats['failed_queries']}")
        print(f"   成功率: {stats['success_rate']:.1f}%")
        
        # 计算性能指标
        if stats['total_queries'] > 0:
            avg_time = elapsed / stats['total_queries']
            print(f"   平均查询时间: {avg_time:.2f}秒")
        
        return stats['success_rate'] > 0
        
    except ImportError as e:
        print(f"   ✗ 导入模块失败: {e}")
        return False
    except Exception as e:
        print(f"   ✗ 测试异常: {e}")
        return False

def test_data_validation():
    """测试数据验证功能"""
    print("\n" + "=" * 60)
    print("数据验证功能测试")
    print("=" * 60)
    
    try:
        from neodata_data_collector import NeoDataPreciousMetalsCollector
        
        collector = NeoDataPreciousMetalsCollector()
        
        # 获取黄金数据进行验证
        print("\n1. 获取黄金数据进行验证...")
        gold_data = collector.get_price('XAUUSD')
        
        if not gold_data:
            print("   ✗ 无法获取黄金数据，跳过验证测试")
            return False
        
        print("   ✓ 黄金数据获取成功")
        
        # 验证价格范围
        print("\n2. 验证价格范围...")
        if gold_data.price > 0:
            print(f"   ✓ 价格有效: {gold_data.price}")
        else:
            print(f"   ✗ 价格无效: {gold_data.price}")
            return False
        
        # 验证高低价逻辑
        print("\n3. 验证高低价逻辑...")
        if gold_data.high >= gold_data.low:
            print(f"   ✓ 高低价逻辑正确: 最高 {gold_data.high} >= 最低 {gold_data.low}")
        else:
            print(f"   ✗ 高低价逻辑错误: 最高 {gold_data.high} < 最低 {gold_data.low}")
            return False
        
        # 验证涨跌幅
        print("\n4. 验证涨跌幅...")
        if abs(gold_data.change_percent) < 50:  # 涨跌幅应小于50%
            print(f"   ✓ 涨跌幅合理: {gold_data.change_percent:.2f}%")
        else:
            print(f"   ✗ 涨跌幅异常: {gold_data.change_percent:.2f}%")
            return False
        
        # 验证数据完整性
        print("\n5. 验证数据完整性...")
        required_fields = ['symbol', 'price', 'change', 'change_percent', 'high', 'low', 'source']
        missing_fields = [f for f in required_fields if not hasattr(gold_data, f)]
        
        if not missing_fields:
            print("   ✓ 数据完整性验证通过")
        else:
            print(f"   ✗ 缺失字段: {missing_fields}")
            return False
        
        print("\n   ✓ 所有验证测试通过")
        return True
        
    except Exception as e:
        print(f"   ✗ 验证测试异常: {e}")
        return False

def test_performance():
    """测试性能指标"""
    print("\n" + "=" * 60)
    print("性能测试")
    print("=" * 60)
    
    try:
        from neodata_data_collector import NeoDataPreciousMetalsCollector
        
        collector = NeoDataPreciousMetalsCollector()
        
        # 测试连续查询性能
        print("\n1. 测试连续查询性能...")
        symbols = ['XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD']
        times = []
        
        for symbol in symbols:
            start_time = time.time()
            result = collector.get_price(symbol)
            elapsed = time.time() - start_time
            times.append(elapsed)
            
            status = "✓" if result else "✗"
            print(f"   {status} {symbol}: {elapsed:.2f}秒")
        
        # 计算性能统计
        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        
        print(f"\n2. 性能统计:")
        print(f"   平均查询时间: {avg_time:.2f}秒")
        print(f"   最大查询时间: {max_time:.2f}秒")
        print(f"   最小查询时间: {min_time:.2f}秒")
        
        # 性能基准检查
        print(f"\n3. 性能基准检查:")
        if avg_time < 5.0:
            print(f"   ✓ 平均查询时间 < 5秒: {avg_time:.2f}秒")
        else:
            print(f"   ✗ 平均查询时间过长: {avg_time:.2f}秒")
            return False
        
        if max_time < 10.0:
            print(f"   ✓ 最大查询时间 < 10秒: {max_time:.2f}秒")
        else:
            print(f"   ✗ 最大查询时间过长: {max_time:.2f}秒")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ✗ 性能测试异常: {e}")
        return False

def main():
    """主测试函数"""
    print("贵金属数据采集系统优化验证测试")
    print("测试时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    results = []
    
    # 运行各项测试
    results.append(("NeoData数据采集器", test_neodata_collector()))
    results.append(("数据验证功能", test_data_validation()))
    results.append(("性能测试", test_performance()))
    
    # 显示测试结果摘要
    print("\n" + "=" * 60)
    print("测试结果摘要")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("\n🎉 所有测试通过！优化效果验证成功。")
        return 0
    else:
        print(f"\n⚠️  {failed} 个测试失败，需要进一步优化。")
        return 1

if __name__ == '__main__':
    sys.exit(main())
