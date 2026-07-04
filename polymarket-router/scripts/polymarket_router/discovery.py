"""
PolyMarket多源数据集成路由系统 - 动态数据源发现器
负责运行时发现新的可用PolyMarket数据源
"""

import logging
import time
import json
import re
import asyncio
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading

from .source_manager import SourceManager, SourceConfig, SourceType

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredSource:
    """发现的数据源"""
    name: str
    source_type: SourceType
    endpoint: Optional[str] = None
    url: Optional[str] = None
    capabilities: List[str] = None
    reliability_score: float = 0.0  # 0-1
    last_seen: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.last_seen is None:
            self.last_seen = datetime.now()


class SourceDiscovery:
    """数据源发现器"""
    
    def __init__(self, source_manager: SourceManager):
        self.source_manager = source_manager
        self._discovered_sources: Dict[str, DiscoveredSource] = {}
        self._lock = threading.RLock()
        
        # 发现配置
        self._config = {
            'discovery_interval': 3600,  # 秒
            'search_queries': [
                'Polymarket prediction market API',
                'alternative to polymarket data',
                'Polymarket data source',
                'Polymarket API alternative',
                'prediction market data API'
            ],
            'source_verification_interval': 86400,  # 秒
            'max_sources': 20,
            'min_reliability_score': 0.3
        }
        
        # 已知的权威数据源模式
        self._known_authoritative_patterns = [
            r'polymarket\.com',
            r'polymarket\.io',
            r'polymarketapi\.com',
            r'polyspotter\.com',
            r'polymarketanalytics\.com',
            r'polymarkettrade\.app',
            r'polymarket-alternative\.com'
        ]
        
        # 启动发现线程
        self._discovery_thread: Optional[threading.Thread] = None
        self._stop_discovery = threading.Event()
    
    def start_discovery(self):
        """启动发现线程"""
        if self._discovery_thread and self._discovery_thread.is_alive():
            logger.warning("发现线程已在运行")
            return
        
        self._stop_discovery.clear()
        self._discovery_thread = threading.Thread(
            target=self._discovery_loop,
            daemon=True,
            name="source-discovery-thread"
        )
        self._discovery_thread.start()
        logger.info("数据源发现线程已启动")
    
    def stop_discovery(self):
        """停止发现线程"""
        if self._discovery_thread:
            self._stop_discovery.set()
            self._discovery_thread.join(timeout=5)
            logger.info("数据源发现线程已停止")
    
    def _discovery_loop(self):
        """发现循环"""
        while not self._stop_discovery.is_set():
            try:
                self._perform_discovery()
                time.sleep(self._config['discovery_interval'])
            except Exception as e:
                logger.error(f"发现循环异常: {e}")
                time.sleep(300)
    
    def _perform_discovery(self):
        """执行数据源发现"""
        logger.info("开始执行数据源发现...")
        
        try:
            # 1. 搜索新的数据源
            new_sources = self._search_for_sources()
            
            # 2. 验证发现的数据源
            verified_sources = self._verify_sources(new_sources)
            
            # 3. 注册验证通过的数据源
            registered_count = 0
            for source in verified_sources:
                if self._register_discovered_source(source):
                    registered_count += 1
            
            logger.info(f"发现完成: 搜索到 {len(new_sources)} 个源，"
                       f"验证通过 {len(verified_sources)} 个，"
                       f"注册成功 {registered_count} 个")
            
        except Exception as e:
            logger.error(f"数据源发现失败: {e}")
    
    def _search_for_sources(self) -> List[DiscoveredSource]:
        """搜索新的数据源"""
        discovered = []
        
        # 这里应该实现具体的搜索逻辑
        # 目前返回模拟数据
        
        # 模拟搜索结果
        mock_sources = [
            DiscoveredSource(
                name="mock-api-1",
                source_type=SourceType.API,
                endpoint="https://api.example.com/polymarket",
                capabilities=["search", "markets"],
                reliability_score=0.5,
                metadata={"source": "web_search", "query": "Polymarket API"}
            ),
            DiscoveredSource(
                name="mock-web-1",
                source_type=SourceType.WEB,
                url="https://example.com/polymarket-data",
                capabilities=["web_scrape"],
                reliability_score=0.4,
                metadata={"source": "web_search", "query": "Polymarket alternative"}
            )
        ]
        
        discovered.extend(mock_sources)
        
        return discovered
    
    def _verify_sources(self, sources: List[DiscoveredSource]) -> List[DiscoveredSource]:
        """验证数据源"""
        verified = []
        
        for source in sources:
            try:
                # 验证数据源的可靠性和可用性
                reliability_score = self._calculate_reliability_score(source)
                
                if reliability_score >= self._config['min_reliability_score']:
                    source.reliability_score = reliability_score
                    verified.append(source)
                    logger.info(f"数据源 {source.name} 验证通过，可靠性: {reliability_score:.2f}")
                else:
                    logger.info(f"数据源 {source.name} 验证失败，可靠性: {reliability_score:.2f}")
                    
            except Exception as e:
                logger.error(f"验证数据源 {source.name} 失败: {e}")
        
        return verified
    
    def _calculate_reliability_score(self, source: DiscoveredSource) -> float:
        """计算数据源可靠性分数"""
        score = 0.0
        
        # 1. 检查是否匹配已知权威模式
        endpoint = source.endpoint or source.url or ""
        for pattern in self._known_authoritative_patterns:
            if re.search(pattern, endpoint, re.IGNORECASE):
                score += 0.4
                break
        
        # 2. 检查数据源类型
        if source.source_type == SourceType.API:
            score += 0.2
        elif source.source_type == SourceType.WEB:
            score += 0.1
        
        # 3. 检查能力
        if source.capabilities:
            if "search" in source.capabilities:
                score += 0.1
            if "markets" in source.capabilities:
                score += 0.1
        
        # 4. 随机因素（模拟不确定性）
        score += 0.1
        
        # 限制在0-1范围内
        return min(max(score, 0.0), 1.0)
    
    def _register_discovered_source(self, source: DiscoveredSource) -> bool:
        """注册发现的数据源"""
        try:
            # 检查是否已存在
            existing_state = self.source_manager.get_source(source.name)
            if existing_state:
                logger.info(f"数据源 {source.name} 已存在，跳过注册")
                return False
            
            # 检查是否达到最大数量限制
            all_sources = self.source_manager.list_sources()
            if len(all_sources) >= self._config['max_sources']:
                logger.warning(f"已达到最大数据源数量限制: {self._config['max_sources']}")
                return False
            
            # 创建配置
            config = SourceConfig(
                name=source.name,
                source_type=source.source_type,
                priority=self._calculate_priority(source),
                endpoint=source.endpoint,
                url=source.url,
                health_check_interval=300,
                timeout=10000,
                max_retries=2,
                metadata={
                    **(source.metadata or {}),
                    'discovered_at': datetime.now().isoformat(),
                    'reliability_score': source.reliability_score,
                    'capabilities': source.capabilities
                }
            )
            
            # 注册数据源
            success = self.source_manager.register_source(config)
            
            if success:
                self._discovered_sources[source.name] = source
                logger.info(f"成功注册发现的数据源: {source.name}")
            
            return success
            
        except Exception as e:
            logger.error(f"注册发现的数据源失败: {e}")
            return False
    
    def _calculate_priority(self, source: DiscoveredSource) -> int:
        """计算数据源优先级"""
        # 基于可靠性分数计算优先级
        # 可靠性越高，优先级数字越小（优先级越高）
        
        if source.reliability_score >= 0.8:
            return 3  # 高优先级
        elif source.reliability_score >= 0.6:
            return 5  # 中优先级
        elif source.reliability_score >= 0.4:
            return 7  # 低优先级
        else:
            return 10  # 最低优先级
    
    def discover_source_manually(self, endpoint: str, source_type: SourceType = SourceType.WEB) -> Optional[DiscoveredSource]:
        """手动发现数据源"""
        try:
            # 创建发现源对象
            source = DiscoveredSource(
                name=self._generate_source_name(endpoint),
                source_type=source_type,
                endpoint=endpoint if source_type == SourceType.API else None,
                url=endpoint if source_type == SourceType.WEB else None,
                metadata={
                    'discovery_method': 'manual',
                    'discovered_at': datetime.now().isoformat()
                }
            )
            
            # 验证数据源
            reliability_score = self._calculate_reliability_score(source)
            source.reliability_score = reliability_score
            
            # 注册数据源
            if self._register_discovered_source(source):
                return source
            
            return None
            
        except Exception as e:
            logger.error(f"手动发现数据源失败: {e}")
            return None
    
    def _generate_source_name(self, endpoint: str) -> str:
        """生成数据源名称"""
        # 从endpoint提取域名
        try:
            from urllib.parse import urlparse
            parsed = urlparse(endpoint)
            domain = parsed.netloc or parsed.path
            
            # 清理域名
            name = re.sub(r'[^a-zA-Z0-9]', '-', domain)
            name = re.sub(r'-+', '-', name).strip('-')
            
            # 添加时间戳
            timestamp = int(time.time())
            return f"{name}-{timestamp}"
            
        except Exception:
            # 如果解析失败，使用时间戳
            return f"discovered-source-{int(time.time())}"
    
    def get_discovered_sources(self) -> List[DiscoveredSource]:
        """获取发现的数据源"""
        with self._lock:
            return list(self._discovered_sources.values())
    
    def remove_discovered_source(self, name: str) -> bool:
        """移除发现的数据源"""
        try:
            # 从发现列表中移除
            with self._lock:
                if name in self._discovered_sources:
                    del self._discovered_sources[name]
            
            # 从源管理器中移除
            return self.source_manager.unregister_source(name)
            
        except Exception as e:
            logger.error(f"移除发现的数据源失败: {e}")
            return False
    
    def update_config(self, config: Dict[str, Any]):
        """更新发现配置"""
        with self._lock:
            self._config.update(config)
            logger.info("发现配置已更新")
    
    def get_config(self) -> Dict[str, Any]:
        """获取发现配置"""
        with self._lock:
            return self._config.copy()
    
    def get_discovery_stats(self) -> Dict[str, Any]:
        """获取发现统计"""
        with self._lock:
            return {
                'discovered_sources_count': len(self._discovered_sources),
                'config': self._config,
                'last_discovery': datetime.now().isoformat()
            }
    
    def __del__(self):
        """析构函数"""
        self.stop_discovery()