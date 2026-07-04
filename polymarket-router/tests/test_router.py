#!/usr/bin/env python3
"""
PolyMarket多源数据集成路由系统测试脚本
"""

import asyncio
import time
import json
from datetime import datetime

from polymarket_router import (
    SourceManager, SourceConfig, SourceType, SourceStatus,
    SmartRouter, DataRequest, DataResponse, CacheStrategy,
    SourceDiscovery, DiscoveredSource
)


def test_source_manager():
    """测试数据源管理器"""
    print("=" * 60)
    print("测试数据源管理器")
    print("=" * 60)
    
    # 创建数据源管理器
    manager = SourceManager()
    
    # 列出默认数据源
    sources = manager.list_sources()
    print(f"默认数据源数量: {len(sources)}")
    
    for source in sources:
        print(f"  - {source.config.name}: {source.config.source_type.value} "
              f"(优先级: {source.config.priority}, 状态: {source.status.value})")
    
    # 测试注册新数据源
    new_config = SourceConfig(
        name="test-source",
        source_type=SourceType.WEB,
        priority=5,
        url="https://test.example.com",
        health_check_interval=60,
        timeout=5000
    )
    
    success = manager.register_source(new_config)
    print(f"\n注册新数据源: {'成功' if success else '失败'}")
    
    # 测试更新状态
    success = manager.update_source_status("test-source", SourceStatus.HEALTHY)
    print(f"更新数据源状态: {'成功' if success else '失败'}")
    
    # 测试记录请求
    success = manager.record_request_success("test-source", 150.0)
    print(f"记录成功请求: {'成功' if success else '失败'}")
    
    # 获取指标
    metrics = manager.get_source_metrics("test-source")
    print(f"数据源指标: {json.dumps(metrics, indent=2)}")
    
    # 测试导出配置
    config = manager.export_config()
    print(f"导出配置: 包含 {len(config['sources'])} 个数据源")
    
    print("\n数据源管理器测试完成\n")


def test_smart_router():
    """测试智能路由引擎"""
    print("=" * 60)
    print("测试智能路由引擎")
    print("=" * 60)
    
    # 创建路由器
    router = SmartRouter(SourceManager())
    
    # 测试同步请求
    request = DataRequest(
        query="WTI crude oil price prediction",
        data_type="market_odds",
        timeout=10000,
        max_retries=2
    )
    
    print("执行同步请求...")
    start_time = time.time()
    response = router.execute_request_sync(request)
    end_time = time.time()
    
    print(f"请求结果: {'成功' if response.success else '失败'}")
    print(f"数据源: {response.source}")
    print(f"响应时间: {response.response_time:.2f}ms")
    print(f"质量分数: {response.quality_score:.2f}")
    print(f"是否来自缓存: {response.from_cache}")
    print(f"总耗时: {(end_time - start_time) * 1000:.2f}ms")
    
    if response.error_message:
        print(f"错误信息: {response.error_message}")
    
    # 测试异步请求
    async def test_async():
        print("\n执行异步请求...")
        request2 = DataRequest(
            query="gold price prediction June 2026",
            data_type="market_odds",
            timeout=10000
        )
        
        response2 = await router.execute_request(request2)
        print(f"异步请求结果: {'成功' if response2.success else '失败'}")
        print(f"数据源: {response2.source}")
        print(f"响应时间: {response2.response_time:.2f}ms")
        
        return response2
    
    asyncio.run(test_async())
    
    # 测试缓存
    print("\n测试缓存功能...")
    request3 = DataRequest(
        query="WTI crude oil price prediction",  # 相同的查询
        data_type="market_odds",
        cache_strategy=CacheStrategy.LOCAL,
        cache_ttl=300
    )
    
    response3 = router.execute_request_sync(request3)
    print(f"缓存请求结果: {'成功' if response3.success else '失败'}")
    print(f"是否来自缓存: {response3.from_cache}")
    
    # 获取统计信息
    stats = router.get_stats()
    print(f"\n路由统计:")
    print(f"  总请求数: {stats['total_requests']}")
    print(f"  成功请求数: {stats['successful_requests']}")
    print(f"  缓存命中数: {stats['cache_hits']}")
    print(f"  数据源故障转移数: {stats['source_failovers']}")
    
    print("\n智能路由引擎测试完成\n")


def test_source_discovery():
    """测试数据源发现器"""
    print("=" * 60)
    print("测试数据源发现器")
    print("=" * 60)
    
    # 创建发现器
    discovery = SourceDiscovery(SourceManager())
    
    # 手动发现数据源
    print("手动发现数据源...")
    source = discovery.discover_source_manually(
        "https://polyspotter.com/api",
        SourceType.API
    )
    
    if source:
        print(f"发现数据源: {source.name}")
        print(f"类型: {source.source_type.value}")
        print(f"可靠性分数: {source.reliability_score:.2f}")
        print(f"能力: {source.capabilities}")
    else:
        print("未发现数据源")
    
    # 获取发现的数据源
    discovered = discovery.get_discovered_sources()
    print(f"\n发现的数据源数量: {len(discovered)}")
    
    for ds in discovered:
        print(f"  - {ds.name}: {ds.source_type.value} "
              f"(可靠性: {ds.reliability_score:.2f})")
    
    # 获取发现统计
    stats = discovery.get_discovery_stats()
    print(f"\n发现统计: {json.dumps(stats, indent=2)}")
    
    print("\n数据源发现器测试完成\n")


def test_integration():
    """集成测试"""
    print("=" * 60)
    print("集成测试")
    print("=" * 60)
    
    # 创建完整的系统
    source_manager = SourceManager()
    router = SmartRouter(source_manager)
    discovery = SourceDiscovery(source_manager)
    
    # 测试完整流程
    print("1. 初始数据源状态:")
    sources = source_manager.list_sources()
    for source in sources:
        print(f"   - {source.config.name}: {source.status.value}")
    
    # 测试故障转移
    print("\n2. 测试故障转移:")
    request = DataRequest(
        query="silver price prediction",
        data_type="market_odds",
        timeout=5000,
        max_retries=2
    )
    
    response = router.execute_request_sync(request)
    print(f"   请求结果: {'成功' if response.success else '失败'}")
    print(f"   使用数据源: {response.source}")
    
    # 测试动态发现
    print("\n3. 测试动态发现:")
    source = discovery.discover_source_manually(
        "https://new-polymarket-api.com",
        SourceType.API
    )
    
    if source:
        print(f"   发现新数据源: {source.name}")
        
        # 再次测试请求
        response2 = router.execute_request_sync(request)
        print(f"   再次请求结果: {'成功' if response2.success else '失败'}")
        print(f"   使用数据源: {response2.source}")
    
    # 最终状态
    print("\n4. 最终系统状态:")
    stats = router.get_stats()
    print(f"   总请求数: {stats['total_requests']}")
    print(f"   成功率: {stats['successful_requests'] / max(stats['total_requests'], 1) * 100:.1f}%")
    print(f"   数据源数量: {len(source_manager.list_sources())}")
    
    print("\n集成测试完成\n")


def main():
    """主测试函数"""
    print("PolyMarket多源数据集成路由系统测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 运行测试
        test_source_manager()
        test_smart_router()
        test_source_discovery()
        test_integration()
        
        print("=" * 60)
        print("所有测试完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()