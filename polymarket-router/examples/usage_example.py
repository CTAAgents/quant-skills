#!/usr/bin/env python3
"""
PolyMarket多源数据集成路由系统使用示例
"""

import sys
import os
import asyncio
import json
from datetime import datetime

# 添加scripts目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

from polymarket_router import (
    create_router, get_market_data, DataRequest, CacheStrategy
)


def basic_usage_example():
    """基本使用示例"""
    print("=" * 60)
    print("基本使用示例")
    print("=" * 60)
    
    # 示例1: 使用便捷函数获取数据
    print("\n1. 使用便捷函数获取WTI原油预测数据:")
    response = get_market_data("WTI crude oil price prediction June 2026")
    
    print(f"   成功: {response.success}")
    print(f"   数据源: {response.source}")
    print(f"   响应时间: {response.response_time:.2f}ms")
    print(f"   质量分数: {response.quality_score:.2f}")
    
    if response.success and response.data:
        print(f"   数据预览: {str(response.data)[:100]}...")
    
    # 示例2: 使用路由器获取数据
    print("\n2. 使用路由器获取黄金预测数据:")
    router = create_router()
    request = DataRequest(
        query="gold price prediction June 2026",
        data_type="market_odds",
        timeout=10000,
        max_retries=3
    )
    
    response = router.execute_request_sync(request)
    print(f"   成功: {response.success}")
    print(f"   数据源: {response.source}")
    
    # 示例3: 获取白银预测数据
    print("\n3. 获取白银预测数据:")
    response = get_market_data("silver price prediction June 2026")
    print(f"   成功: {response.success}")
    print(f"   数据源: {response.source}")
    
    print("\n基本使用示例完成\n")


def advanced_usage_example():
    """高级使用示例"""
    print("=" * 60)
    print("高级使用示例")
    print("=" * 60)
    
    # 示例1: 自定义请求配置
    print("\n1. 自定义请求配置:")
    request = DataRequest(
        query="crude oil inventory prediction",
        data_type="inventory_forecast",
        timeout=15000,
        max_retries=2,
        preferred_sources=["gamma-api", "polyspotter"],
        excluded_sources=["local-cache"],
        cache_strategy=CacheStrategy.LOCAL,
        cache_ttl=600,  # 10分钟缓存
        metadata={
            "user": "analyst",
            "purpose": "daily_report"
        }
    )
    
    response = get_market_data(request.query, 
                              timeout=request.timeout,
                              max_retries=request.max_retries)
    
    print(f"   成功: {response.success}")
    print(f"   数据源: {response.source}")
    print(f"   缓存: {response.from_cache}")
    
    # 示例2: 批量获取多个数据
    print("\n2. 批量获取多个预测数据:")
    queries = [
        "WTI crude oil price prediction",
        "gold price prediction June 2026",
        "silver price prediction June 2026",
        "natural gas price prediction"
    ]
    
    results = []
    for query in queries:
        response = get_market_data(query)
        results.append({
            'query': query,
            'success': response.success,
            'source': response.source,
            'response_time': response.response_time
        })
        print(f"   {query[:30]}... -> {'✓' if response.success else '✗'} "
              f"({response.source}, {response.response_time:.1f}ms)")
    
    # 示例3: 错误处理
    print("\n3. 错误处理示例:")
    try:
        # 模拟一个可能失败的请求
        response = get_market_data("nonexistent prediction market", 
                                  timeout=5000, 
                                  max_retries=1)
        
        if not response.success:
            print(f"   请求失败: {response.error_message}")
            print(f"   尝试了其他数据源")
        else:
            print(f"   请求成功: {response.source}")
            
    except Exception as e:
        print(f"   发生异常: {e}")
    
    print("\n高级使用示例完成\n")


def async_usage_example():
    """异步使用示例"""
    print("=" * 60)
    print("异步使用示例")
    print("=" * 60)
    
    async def fetch_multiple_data():
        """异步获取多个数据"""
        router = create_router()
        
        queries = [
            "WTI crude oil price prediction",
            "gold price prediction June 2026",
            "silver price prediction June 2026"
        ]
        
        # 创建异步请求任务
        tasks = []
        for query in queries:
            request = DataRequest(
                query=query,
                data_type="market_odds",
                timeout=10000
            )
            tasks.append(router.execute_request(request))
        
        # 并发执行所有请求
        print("   并发执行多个请求...")
        start_time = datetime.now()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = datetime.now()
        
        # 处理结果
        successful = 0
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                print(f"   {queries[i][:30]}... -> 异常: {response}")
            else:
                if response.success:
                    successful += 1
                    print(f"   {queries[i][:30]}... -> ✓ "
                          f"({response.source}, {response.response_time:.1f}ms)")
                else:
                    print(f"   {queries[i][:30]}... -> ✗ {response.error_message}")
        
        total_time = (end_time - start_time).total_seconds() * 1000
        print(f"\n   总耗时: {total_time:.2f}ms")
        print(f"   成功率: {successful}/{len(queries)}")
        
        return responses
    
    # 运行异步示例
    asyncio.run(fetch_multiple_data())
    
    print("\n异步使用示例完成\n")


def monitoring_example():
    """监控和统计示例"""
    print("=" * 60)
    print("监控和统计示例")
    print("=" * 60)
    
    # 创建路由器
    router = create_router()
    
    # 执行一些请求
    queries = [
        "crude oil price prediction",
        "gold price prediction",
        "silver price prediction"
    ]
    
    for query in queries:
        get_market_data(query)
    
    # 获取统计信息
    print("\n1. 路由器统计:")
    stats = router.get_stats()
    print(f"   总请求数: {stats['total_requests']}")
    print(f"   成功请求数: {stats['successful_requests']}")
    print(f"   失败请求数: {stats['failed_requests']}")
    print(f"   缓存命中数: {stats['cache_hits']}")
    print(f"   缓存未命中数: {stats['cache_misses']}")
    print(f"   数据源故障转移数: {stats['source_failovers']}")
    print(f"   缓存大小: {stats['cache_size']}")
    
    # 获取数据源指标
    print("\n2. 数据源指标:")
    metrics = router.source_manager.get_all_metrics()
    for source_name, source_metrics in metrics.items():
        print(f"   {source_name}:")
        print(f"     状态: {source_metrics['status']}")
        if source_metrics['metrics']['total_requests'] > 0:
            success_rate = source_metrics['metrics']['successful_requests'] / source_metrics['metrics']['total_requests']
            print(f"     成功率: {success_rate:.2%}")
        else:
            print(f"     成功率: N/A (无请求)")
        print(f"     平均响应时间: {source_metrics['metrics']['avg_response_time']:.2f}ms")
        print(f"     总请求数: {source_metrics['metrics']['total_requests']}")
    
    # 清空缓存
    print("\n3. 清空缓存:")
    router.clear_cache()
    print("   缓存已清空")
    
    print("\n监控和统计示例完成\n")


def main():
    """主函数"""
    print("PolyMarket多源数据集成路由系统使用示例")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 运行各种示例
        basic_usage_example()
        advanced_usage_example()
        async_usage_example()
        monitoring_example()
        
        print("=" * 60)
        print("所有示例执行完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"执行示例时发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()