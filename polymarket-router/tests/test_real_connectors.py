#!/usr/bin/env python3
"""
测试实际数据源连接器
"""

import sys
import asyncio
import json
from pathlib import Path

# 添加scripts目录到Python路径
current_dir = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(current_dir))

from polymarket_router import SmartRouter, DataRequest, DataResponse
from polymarket_router.source_manager import SourceManager, SourceConfig, SourceType, SourceStatus

async def test_gamma_api_adapter():
    """测试Gamma API适配器"""
    print("测试Gamma API适配器...")
    
    # 创建源管理器
    source_manager = SourceManager()
    
    # 创建路由器
    router = SmartRouter(source_manager)
    
    # 创建请求
    request = DataRequest(
        query="crude oil",
        data_type="search",
        timeout=10000
    )
    
    # 执行请求
    try:
        response = await router.execute_request(request)
        print(f"请求成功: {response.success}")
        print(f"数据源: {response.source}")
        print(f"响应时间: {response.response_time:.2f}ms")
        print(f"数据质量: {response.quality_score:.2f}")
        
        if response.success and response.data:
            print(f"数据预览: {json.dumps(response.data, indent=2)[:500]}...")
        
        return response
    except Exception as e:
        print(f"测试失败: {e}")
        return None

async def test_web_adapter():
    """测试Web适配器"""
    print("\n测试Web适配器...")
    
    # 创建源管理器
    source_manager = SourceManager()
    
    # 创建路由器
    router = SmartRouter(source_manager)
    
    # 创建请求
    request = DataRequest(
        query="gold",
        data_type="web_search",
        timeout=15000
    )
    
    # 执行请求
    try:
        response = await router.execute_request(request)
        print(f"请求成功: {response.success}")
        print(f"数据源: {response.source}")
        print(f"响应时间: {response.response_time:.2f}ms")
        print(f"数据质量: {response.quality_score:.2f}")
        
        if response.success and response.data:
            print(f"数据预览: {json.dumps(response.data, indent=2)[:500]}...")
        
        return response
    except Exception as e:
        print(f"测试失败: {e}")
        return None

async def test_cache_adapter():
    """测试缓存适配器"""
    print("\n测试缓存适配器...")
    
    # 创建源管理器
    source_manager = SourceManager()
    
    # 创建路由器
    router = SmartRouter(source_manager)
    
    # 先执行一次请求来填充缓存
    request1 = DataRequest(
        query="silver",
        data_type="market_data",
        timeout=10000
    )
    
    try:
        response1 = await router.execute_request(request1)
        print(f"第一次请求成功: {response1.success}")
        print(f"数据源: {response1.source}")
        
        # 再次执行相同请求，应该从缓存获取
        request2 = DataRequest(
            query="silver",
            data_type="market_data",
            timeout=10000
        )
        
        response2 = await router.execute_request(request2)
        print(f"第二次请求成功: {response2.success}")
        print(f"数据源: {response2.source}")
        print(f"来自缓存: {response2.from_cache}")
        
        return response2
    except Exception as e:
        print(f"测试失败: {e}")
        return None

async def main():
    """主测试函数"""
    print("开始测试实际数据源连接器...")
    
    # 测试Gamma API适配器
    gamma_response = await test_gamma_api_adapter()
    
    # 测试Web适配器
    web_response = await test_web_adapter()
    
    # 测试缓存适配器
    cache_response = await test_cache_adapter()
    
    # 汇总结果
    print("\n测试汇总:")
    print(f"Gamma API测试: {'成功' if gamma_response and gamma_response.success else '失败'}")
    print(f"Web适配器测试: {'成功' if web_response and web_response.success else '失败'}")
    print(f"缓存适配器测试: {'成功' if cache_response and cache_response.success else '失败'}")
    
    # 测试故障转移
    print("\n测试故障转移机制...")
    source_manager = SourceManager()
    router = SmartRouter(source_manager)
    
    # 禁用主要数据源
    gamma_source = source_manager.get_source("gamma-api")
    if gamma_source:
        gamma_source.config.enabled = False
        source_manager.update_source_status("gamma-api", SourceStatus.DISABLED)
    
    # 执行请求，应该故障转移到备用数据源
    request = DataRequest(
        query="bitcoin",
        data_type="search",
        timeout=10000
    )
    
    try:
        response = await router.execute_request(request)
        print(f"故障转移测试: {'成功' if response.success else '失败'}")
        print(f"使用的数据源: {response.source}")
    except Exception as e:
        print(f"故障转移测试失败: {e}")
    
    print("\n所有测试完成!")

if __name__ == "__main__":
    asyncio.run(main())