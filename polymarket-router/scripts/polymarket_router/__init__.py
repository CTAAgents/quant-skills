"""
PolyMarket多源数据集成路由系统
确保下游应用和技能能够无缝、可靠地获取PolyMarket预测市场数据
"""

from .source_manager import SourceManager, SourceConfig, SourceType, SourceStatus
from .router import SmartRouter, DataRequest, DataResponse, RoutingStrategy, CacheStrategy
from .discovery import SourceDiscovery, DiscoveredSource

__version__ = "1.0.0"
__author__ = "PolyMarket Router Team"

# 默认路由器实例
_default_router: SmartRouter = None


def get_default_router() -> SmartRouter:
    """获取默认路由器实例"""
    global _default_router
    if _default_router is None:
        source_manager = SourceManager()
        _default_router = SmartRouter(source_manager)
    return _default_router


def create_router() -> SmartRouter:
    """创建新的路由器实例"""
    source_manager = SourceManager()
    return SmartRouter(source_manager)


def get_market_data(query: str, **kwargs) -> DataResponse:
    """获取PolyMarket市场数据（便捷函数）"""
    router = get_default_router()
    request = DataRequest(query=query, **kwargs)
    return router.execute_request_sync(request)


# 导出主要类
__all__ = [
    'SourceManager',
    'SourceConfig', 
    'SourceType',
    'SourceStatus',
    'SmartRouter',
    'DataRequest',
    'DataResponse',
    'RoutingStrategy',
    'CacheStrategy',
    'SourceDiscovery',
    'DiscoveredSource',
    'get_default_router',
    'create_router',
    'get_market_data'
]