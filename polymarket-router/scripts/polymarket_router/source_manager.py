"""
PolyMarket多源数据集成路由系统 - 数据源管理器
负责管理所有数据源的注册、配置和生命周期
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """数据源类型枚举"""
    API = "api"           # 直接API调用
    WEB = "web"           # Web搜索/WebFetch
    CACHE = "cache"       # 本地缓存
    CUSTOM = "custom"     # 自定义适配器


class SourceStatus(Enum):
    """数据源状态枚举"""
    HEALTHY = "healthy"           # 健康
    DEGRADED = "degraded"         # 降级
    UNHEALTHY = "unhealthy"       # 不健康
    UNKNOWN = "unknown"           # 未知
    DISABLED = "disabled"         # 已禁用


@dataclass
class SourceConfig:
    """数据源配置"""
    name: str
    source_type: SourceType
    priority: int
    endpoint: Optional[str] = None
    url: Optional[str] = None
    health_check_interval: int = 30  # 秒
    timeout: int = 5000  # 毫秒
    max_retries: int = 3
    retry_delay: int = 1000  # 毫秒
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['source_type'] = self.source_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SourceConfig':
        """从字典创建配置"""
        data['source_type'] = SourceType(data['source_type'])
        return cls(**data)


@dataclass
class SourceMetrics:
    """数据源指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0  # 毫秒
    last_health_check: Optional[datetime] = None
    last_successful_request: Optional[datetime] = None
    last_failed_request: Optional[datetime] = None
    consecutive_failures: int = 0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests
    
    @property
    def failure_rate(self) -> float:
        """失败率"""
        return 1.0 - self.success_rate
    
    def record_success(self, response_time: float):
        """记录成功请求"""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.last_successful_request = datetime.now()
        
        # 更新平均响应时间（指数移动平均）
        if self.avg_response_time == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = 0.9 * self.avg_response_time + 0.1 * response_time
    
    def record_failure(self):
        """记录失败请求"""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_failed_request = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 转换datetime对象为字符串
        for key in ['last_health_check', 'last_successful_request', 'last_failed_request']:
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data


@dataclass
class SourceState:
    """数据源状态"""
    config: SourceConfig
    status: SourceStatus = SourceStatus.UNKNOWN
    metrics: SourceMetrics = None
    last_updated: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = SourceMetrics()
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'config': self.config.to_dict(),
            'status': self.status.value,
            'metrics': self.metrics.to_dict(),
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'error_message': self.error_message
        }


class SourceManager:
    """数据源管理器"""
    
    def __init__(self):
        self._sources: Dict[str, SourceState] = {}
        self._lock = threading.RLock()
        self._health_check_thread: Optional[threading.Thread] = None
        self._stop_health_check = threading.Event()
        
        # 默认数据源配置
        self._default_sources = [
            SourceConfig(
                name="gamma-api",
                source_type=SourceType.API,
                priority=1,
                endpoint="https://gamma-api.polymarket.com",
                health_check_interval=30,
                timeout=5000,
                max_retries=3,
                metadata={
                    "description": "PolyMarket官方Gamma API",
                    "capabilities": ["search", "events", "markets", "tags"],
                    "requires_auth": False
                }
            ),
            SourceConfig(
                name="clob-api",
                source_type=SourceType.API,
                priority=2,
                endpoint="https://clob.polymarket.com",
                health_check_interval=30,
                timeout=5000,
                max_retries=3,
                metadata={
                    "description": "PolyMarket CLOB订单簿API",
                    "capabilities": ["price", "book", "trades"],
                    "requires_auth": True
                }
            ),
            SourceConfig(
                name="polyspotter",
                source_type=SourceType.WEB,
                priority=3,
                url="https://polyspotter.com",
                health_check_interval=60,
                timeout=10000,
                max_retries=2,
                metadata={
                    "description": "Polyspotter替代数据源",
                    "capabilities": ["search", "markets"],
                    "scrape_method": "python"
                }
            ),
            SourceConfig(
                name="polymarketanalytics",
                source_type=SourceType.WEB,
                priority=4,
                url="https://polymarketanalytics.com",
                health_check_interval=120,
                timeout=10000,
                max_retries=2,
                metadata={
                    "description": "Polymarket分析网站",
                    "capabilities": ["analytics", "markets"],
                    "scrape_method": "webfetch"
                }
            ),
            SourceConfig(
                name="local-cache",
                source_type=SourceType.CACHE,
                priority=10,
                health_check_interval=300,
                timeout=100,
                max_retries=1,
                metadata={
                    "description": "本地数据缓存",
                    "capabilities": ["cached_data"],
                    "ttl": 3600  # 1小时
                }
            )
        ]
        
        # 注册默认数据源
        for source_config in self._default_sources:
            self.register_source(source_config)
    
    def register_source(self, config: SourceConfig) -> bool:
        """注册数据源"""
        with self._lock:
            try:
                if config.name in self._sources:
                    logger.warning(f"数据源 {config.name} 已存在，将被更新")
                
                state = SourceState(config=config)
                self._sources[config.name] = state
                
                logger.info(f"数据源 {config.name} 已注册，优先级: {config.priority}")
                return True
                
            except Exception as e:
                logger.error(f"注册数据源失败: {e}")
                return False
    
    def unregister_source(self, name: str) -> bool:
        """注销数据源"""
        with self._lock:
            try:
                if name not in self._sources:
                    logger.warning(f"数据源 {name} 不存在")
                    return False
                
                del self._sources[name]
                logger.info(f"数据源 {name} 已注销")
                return True
                
            except Exception as e:
                logger.error(f"注销数据源失败: {e}")
                return False
    
    def get_source(self, name: str) -> Optional[SourceState]:
        """获取数据源状态"""
        with self._lock:
            return self._sources.get(name)
    
    def list_sources(self) -> List[SourceState]:
        """列出所有数据源"""
        with self._lock:
            return list(self._sources.values())
    
    def get_healthy_sources(self) -> List[SourceState]:
        """获取健康的数据源"""
        with self._lock:
            return [
                state for state in self._sources.values()
                if state.status in [SourceStatus.HEALTHY, SourceStatus.DEGRADED]
                and state.config.enabled
            ]
    
    def get_sources_by_priority(self) -> List[SourceState]:
        """按优先级排序获取数据源"""
        with self._lock:
            sources = [
                state for state in self._sources.values()
                if state.config.enabled
            ]
            return sorted(sources, key=lambda x: x.config.priority)
    
    def update_source_status(self, name: str, status: SourceStatus, 
                           error_message: Optional[str] = None) -> bool:
        """更新数据源状态"""
        with self._lock:
            try:
                if name not in self._sources:
                    logger.warning(f"数据源 {name} 不存在")
                    return False
                
                state = self._sources[name]
                state.status = status
                state.last_updated = datetime.now()
                state.error_message = error_message
                
                logger.info(f"数据源 {name} 状态更新为: {status.value}")
                return True
                
            except Exception as e:
                logger.error(f"更新数据源状态失败: {e}")
                return False
    
    def record_request_success(self, name: str, response_time: float) -> bool:
        """记录成功请求"""
        with self._lock:
            try:
                if name not in self._sources:
                    return False
                
                state = self._sources[name]
                state.metrics.record_success(response_time)
                
                # 如果之前是不健康状态，恢复为健康
                if state.status == SourceStatus.UNHEALTHY:
                    state.status = SourceStatus.HEALTHY
                    logger.info(f"数据源 {name} 恢复为健康状态")
                
                return True
                
            except Exception as e:
                logger.error(f"记录成功请求失败: {e}")
                return False
    
    def record_request_failure(self, name: str, error_message: Optional[str] = None) -> bool:
        """记录失败请求"""
        with self._lock:
            try:
                if name not in self._sources:
                    return False
                
                state = self._sources[name]
                state.metrics.record_failure()
                
                # 检查是否需要更新状态
                if state.metrics.consecutive_failures >= 3:
                    state.status = SourceStatus.UNHEALTHY
                    state.error_message = error_message or "连续失败次数过多"
                    logger.warning(f"数据源 {name} 变为不健康状态")
                elif state.metrics.consecutive_failures >= 1:
                    state.status = SourceStatus.DEGRADED
                    logger.info(f"数据源 {name} 变为降级状态")
                
                return True
                
            except Exception as e:
                logger.error(f"记录失败请求失败: {e}")
                return False
    
    def start_health_check(self):
        """启动健康检查线程"""
        if self._health_check_thread and self._health_check_thread.is_alive():
            logger.warning("健康检查线程已在运行")
            return
        
        self._stop_health_check.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="health-check-thread"
        )
        self._health_check_thread.start()
        logger.info("健康检查线程已启动")
    
    def stop_health_check(self):
        """停止健康检查线程"""
        if self._health_check_thread:
            self._stop_health_check.set()
            self._health_check_thread.join(timeout=5)
            logger.info("健康检查线程已停止")
    
    def _health_check_loop(self):
        """健康检查循环"""
        while not self._stop_health_check.is_set():
            try:
                self._perform_health_checks()
                time.sleep(10)  # 每10秒检查一次
            except Exception as e:
                logger.error(f"健康检查循环异常: {e}")
                time.sleep(30)
    
    def _perform_health_checks(self):
        """执行健康检查"""
        current_time = datetime.now()
        
        with self._lock:
            for name, state in self._sources.items():
                if not state.config.enabled:
                    continue
                
                # 检查是否需要执行健康检查
                last_check = state.metrics.last_health_check
                interval = state.config.health_check_interval
                
                if last_check is None or (current_time - last_check).total_seconds() >= interval:
                    # 在实际实现中，这里会调用具体的健康检查逻辑
                    # 目前只是更新时间戳
                    state.metrics.last_health_check = current_time
                    logger.debug(f"数据源 {name} 健康检查已更新")
    
    def get_source_metrics(self, name: str) -> Optional[Dict[str, Any]]:
        """获取数据源指标"""
        with self._lock:
            state = self._sources.get(name)
            if state:
                return state.metrics.to_dict()
            return None
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """获取所有数据源指标"""
        with self._lock:
            metrics = {}
            for name, state in self._sources.items():
                metrics[name] = {
                    'status': state.status.value,
                    'metrics': state.metrics.to_dict(),
                    'config': state.config.to_dict()
                }
            return metrics
    
    def export_config(self) -> Dict[str, Any]:
        """导出配置"""
        with self._lock:
            config = {
                'sources': [],
                'metadata': {
                    'export_time': datetime.now().isoformat(),
                    'version': '1.0.0'
                }
            }
            
            for state in self._sources.values():
                config['sources'].append(state.config.to_dict())
            
            return config
    
    def import_config(self, config: Dict[str, Any]) -> bool:
        """导入配置"""
        try:
            with self._lock:
                # 清空现有数据源
                self._sources.clear()
                
                # 导入新配置
                for source_data in config.get('sources', []):
                    source_config = SourceConfig.from_dict(source_data)
                    state = SourceState(config=source_config)
                    self._sources[source_config.name] = state
                
                logger.info(f"成功导入配置，包含 {len(self._sources)} 个数据源")
                return True
                
        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return False
    
    def __del__(self):
        """析构函数"""
        self.stop_health_check()