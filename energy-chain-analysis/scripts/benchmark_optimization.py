#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化性能基准测试

比较优化前后的性能差异：
1. 技术指标计算性能
2. 信号生成性能
3. 内存使用情况
"""

import time
import sys
import psutil
import os
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np

def get_memory_usage():
    """获取当前内存使用量（MB）"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def benchmark_indicators_calculation(data_size: int = 1000):
    """基准测试：技术指标计算性能"""
    
    print(f"\n{'='*60}")
    print(f"基准测试：技术指标计算性能 (数据量: {data_size} 行)")
    print(f"{'='*60}")
    
    # 生成测试数据
    from calculate_indicators import generate_demo_data, calculate_all_indicators_batch
    
    df = generate_demo_data(data_size)
    print(f"生成测试数据: {len(df)} 行, {len(df.columns)} 列")
    
    # 测试优化版本
    print("\n1. 测试优化版本 (calculate_all_indicators_batch):")
    start_memory = get_memory_usage()
    start_time = time.time()
    
    result = calculate_all_indicators_batch(df)
    
    end_time = time.time()
    end_memory = get_memory_usage()
    
    elapsed = end_time - start_time
    memory_used = end_memory - start_memory
    
    print(f"   计算时间: {elapsed:.3f} 秒")
    print(f"   内存使用: {memory_used:.2f} MB")
    print(f"   输出列数: {len(result.columns)}")
    print(f"   性能: {data_size/elapsed:.0f} 行/秒")
    
    return {
        'data_size': data_size,
        'elapsed': elapsed,
        'memory_used': memory_used,
        'columns': len(result.columns),
        'performance': data_size/elapsed
    }

def benchmark_signal_generation(data_size: int = 1000):
    """基准测试：信号生成性能"""
    
    print(f"\n{'='*60}")
    print(f"基准测试：信号生成性能 (数据量: {data_size} 行)")
    print(f"{'='*60}")
    
    from calculate_indicators import generate_demo_data, calculate_all_indicators_batch, generate_comprehensive_signal
    
    df = generate_demo_data(data_size)
    indicators_df = calculate_all_indicators_batch(df)
    
    print(f"指标数据: {len(indicators_df)} 行, {len(indicators_df.columns)} 列")
    
    # 测试信号生成
    print("\n1. 测试信号生成 (generate_comprehensive_signal):")
    start_time = time.time()
    
    signals = generate_comprehensive_signal(indicators_df)
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print(f"   生成时间: {elapsed:.3f} 秒")
    print(f"   信号数量: {len(signals)}")
    print(f"   信号类型: {[s['type'] for s in signals]}")
    
    return {
        'data_size': data_size,
        'elapsed': elapsed,
        'signals_count': len(signals)
    }

def benchmark_scoring_performance():
    """基准测试：打分性能"""
    
    print(f"\n{'='*60}")
    print(f"基准测试：打分性能")
    print(f"{'='*60}")
    
    from scoring import CompleteFuelOilScorer, BitumenScorer, LPGScorer
    
    # 测试燃料油打分
    print("\n1. 测试燃料油打分 (CompleteFuelOilScorer):")
    scorer = CompleteFuelOilScorer()
    
    start_time = time.time()
    for _ in range(1000):
        result = scorer.calculate(
            fu_close=3000, lu_close=3500, brent=70, sc=500,
            usdcny=7.2, freight=50, crack_fu=200, crack_lu=300,
            crack_refinery=60, india_import_yoy=5, bdi_percentile=55,
            bunker_yoy=3, month=6, sg_inventory=2000, sg_inventory_prev=1900,
            sg_inventory_yoy=10, arrival_yoy=-5, mops_change=2,
            production_yoy=3, import_yoy=-2, warehouse_level=45,
            policy_factor=1, basis=50, month_spread=30, geopolitics=1
        )
    end_time = time.time()
    elapsed = end_time - start_time
    
    # 防止除零：如果elapsed太小，增加迭代次数重新测量
    if elapsed < 0.001:
        iterations_high = 100000
        start_time = time.time()
        for _ in range(iterations_high):
            result = scorer.calculate(
                fu_close=3000, lu_close=3500, brent=70, sc=500,
                usdcny=7.2, freight=50, crack_fu=200, crack_lu=300,
                crack_refinery=60, india_import_yoy=5, bdi_percentile=55,
                bunker_yoy=3, month=6, sg_inventory=2000, sg_inventory_prev=1900,
                sg_inventory_yoy=10, arrival_yoy=-5, mops_change=2,
                production_yoy=3, import_yoy=-2, warehouse_level=45,
                policy_factor=1, basis=50, month_spread=30, geopolitics=1
            )
        elapsed = time.time() - start_time
        print(f"   100000次计算时间: {elapsed:.3f} 秒")
        print(f"   单次计算时间: {elapsed/iterations_high*1000:.4f} 毫秒")
        print(f"   性能: {iterations_high/elapsed:.0f} 次/秒")
        return {
            'scorer': 'CompleteFuelOilScorer',
            'iterations': iterations_high,
            'elapsed': elapsed,
            'performance': iterations_high/elapsed
        }
    
    print(f"   1000次计算时间: {elapsed:.3f} 秒")
    print(f"   单次计算时间: {elapsed/1000*1000:.3f} 毫秒")
    print(f"   性能: {1000/elapsed:.0f} 次/秒")
    
    return {
        'scorer': 'CompleteFuelOilScorer',
        'iterations': 1000,
        'elapsed': elapsed,
        'performance': 1000/elapsed
    }

def run_comprehensive_benchmark():
    """运行综合基准测试"""
    
    print("能源产业链分析技能 - 优化性能基准测试")
    print("="*60)
    
    results = {}
    
    # 1. 技术指标计算性能
    for size in [100, 500, 1000, 2000]:
        results[f'indicators_{size}'] = benchmark_indicators_calculation(size)
    
    # 2. 信号生成性能
    for size in [100, 500, 1000]:
        results[f'signals_{size}'] = benchmark_signal_generation(size)
    
    # 3. 打分性能
    results['scoring'] = benchmark_scoring_performance()
    
    # 汇总结果
    print(f"\n{'='*60}")
    print("基准测试汇总")
    print(f"{'='*60}")
    
    print("\n技术指标计算性能:")
    for size in [100, 500, 1000, 2000]:
        r = results[f'indicators_{size}']
        print(f"  {size:>5} 行: {r['elapsed']:.3f} 秒 ({r['performance']:.0f} 行/秒)")
    
    print("\n信号生成性能:")
    for size in [100, 500, 1000]:
        r = results[f'signals_{size}']
        print(f"  {size:>5} 行: {r['elapsed']:.3f} 秒 ({r['signals_count']} 个信号)")
    
    print(f"\n打分性能:")
    r = results['scoring']
    print(f"  {r['scorer']}: {r['performance']:.0f} 次/秒")
    
    return results

if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("安装psutil用于内存监控...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
        import psutil
    
    results = run_comprehensive_benchmark()
