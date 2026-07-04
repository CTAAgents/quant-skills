"""
PolyMarket多源数据集成路由系统 - 智能路由引擎
负责根据策略选择最优数据源，实现故障转移和负载均衡
"""

import logging
import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from datetime import datetime, timedelta
import asyncio
import concurrent.futures

from .source_manager import SourceManager, SourceState, SourceStatus, SourceType

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """路由策略枚举"""
    PRIORITY = "priority"           # 优先级路由
    ROUND_ROBIN = "round_robin"     # 轮询路由
    LEAST_CONNECTIONS = "least_connections"  # 最少连接
    RANDOM = "random"               # 随机路由


class CacheStrategy(Enum):
    """缓存策略枚举"""
    NONE = "none"                   # 不缓存
    LOCAL = "local"                 # 本地缓存
    DISTRIBUTED = "distributed"     # 分布式缓存


@dataclass
class DataRequest:
    """数据请求"""
    query: str
    data_type: str = "market_data"
    timeout: int = 10000  # 毫秒
    max_retries: int = 3
    preferred_sources: Optional[List[str]] = None
    excluded_sources: Optional[List[str]] = None
    cache_strategy: CacheStrategy = CacheStrategy.LOCAL
    cache_ttl: int = 300  # 秒
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['cache_strategy'] = self.cache_strategy.value
        return data
    
    @property
    def cache_key(self) -> str:
        """生成缓存键"""
        key_data = {
            'query': self.query,
            'data_type': self.data_type
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()


@dataclass
class DataResponse:
    """数据响应"""
    success: bool
    data: Optional[Any] = None
    source: Optional[str] = None
    response_time: float = 0.0  # 毫秒
    timestamp: Optional[datetime] = None
    quality_score: float = 0.0  # 0-1
    from_cache: bool = False
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        if self.timestamp:
            data['timestamp'] = self.timestamp.isoformat()
        return data


class LocalCache:
    """本地缓存"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            # 检查是否过期
            if datetime.now() > entry['expires_at']:
                del self._cache[key]
                return None
            
            return entry['data']
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存"""
        with self._lock:
            try:
                # 检查缓存大小限制
                if len(self._cache) >= self._max_size:
                    # 删除最旧的条目
                    oldest_key = min(self._cache.keys(), 
                                   key=lambda k: self._cache[k]['created_at'])
                    del self._cache[oldest_key]
                
                expires_at = datetime.now() + timedelta(seconds=ttl or self._default_ttl)
                
                self._cache[key] = {
                    'data': data,
                    'created_at': datetime.now(),
                    'expires_at': expires_at
                }
                
                return True
                
            except Exception as e:
                logger.error(f"设置缓存失败: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
    
    def size(self) -> int:
        """获取缓存大小"""
        with self._lock:
            return len(self._cache)


class DataSourceAdapter:
    """数据源适配器基类"""
    
    def __init__(self, source_state: SourceState):
        self.source_state = source_state
    
    async def fetch_data(self, request: DataRequest) -> DataResponse:
        """获取数据 - 子类必须实现"""
        raise NotImplementedError
    
    def validate_response(self, data: Any) -> bool:
        """验证响应数据 - 子类可以重写"""
        return data is not None


class APIAdapter(DataSourceAdapter):
    """API数据源适配器"""
    
    def __init__(self, source_state: SourceState):
        super().__init__(source_state)
        self.session = None
        self._setup_session()
    
    def _setup_session(self):
        """设置HTTP会话"""
        try:
            import aiohttp
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.source_state.config.timeout / 1000),
                headers={'User-Agent': 'PolyMarket-Router/1.0'}
            )
            self._use_aiohttp = True
        except ImportError:
            logger.warning("aiohttp未安装，使用requests作为备用")
            import requests
            self.session = requests.Session()
            self.session.headers.update({'User-Agent': 'PolyMarket-Router/1.0'})
            self._use_aiohttp = False
    
    def __del__(self):
        """析构函数，关闭会话"""
        if hasattr(self, '_use_aiohttp') and self._use_aiohttp and self.session:
            try:
                import asyncio
                if self.session and not self.session.closed:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.session.close())
                    else:
                        loop.run_until_complete(self.session.close())
            except Exception:
                pass
        elif hasattr(self, 'session') and self.session:
            try:
                self.session.close()
            except Exception:
                pass
    
    async def fetch_data(self, request: DataRequest) -> DataResponse:
        """从API获取数据"""
        start_time = time.time()
        
        try:
            # 根据数据源类型构建请求
            endpoint = self.source_state.config.endpoint
            if not endpoint:
                raise ValueError(f"数据源 {self.source_state.config.name} 未配置端点")
            
            # 构建请求URL
            if 'gamma-api' in self.source_state.config.name:
                # Gamma API 搜索端点
                url = f"{endpoint}/public-search?q={request.query}&limit=50"
            elif 'clob-api' in self.source_state.config.name:
                # CLOB API 市场端点
                url = f"{endpoint}/markets?slug={request.query}"
            else:
                # 通用API端点
                url = f"{endpoint}/search?q={request.query}"
            
            # 执行请求
            if hasattr(self.session, 'get') and hasattr(self.session.get, '__call__'):
                # aiohttp session
                async with self.session.get(url) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}: {response.reason}")
                    data = await response.json()
            else:
                # requests session (同步)
                response = self.session.get(url, timeout=self.source_state.config.timeout / 1000)
                response.raise_for_status()
                data = response.json()
            
            # 处理响应数据
            processed_data = self._process_api_response(data, request.query)
            
            response_time = (time.time() - start_time) * 1000
            
            return DataResponse(
                success=True,
                data=processed_data,
                source=self.source_state.config.name,
                response_time=response_time,
                quality_score=0.9
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"API请求失败: {e}")
            
            return DataResponse(
                success=False,
                source=self.source_state.config.name,
                response_time=response_time,
                error_message=str(e)
            )
    
    def _process_api_response(self, data: dict, query: str) -> dict:
        """处理API响应数据"""
        processed = {
            'query': query,
            'source': self.source_state.config.name,
            'timestamp': datetime.now().isoformat(),
            'raw_data': data
        }
        
        # 根据API类型处理数据
        if 'events' in data:
            # Gamma API 搜索结果
            events = data.get('events', [])
            markets = []
            for event in events:
                if event.get('active') and not event.get('closed'):
                    for market in event.get('markets', []):
                        if market.get('active') and not market.get('closed'):
                            markets.append({
                                'question': market.get('question', ''),
                                'slug': market.get('slug', ''),
                                'outcomes': market.get('outcomes', []),
                                'outcome_prices': market.get('outcomePrices', []),
                                'volume': market.get('volumeNum', 0),
                                'liquidity': market.get('liquidity', 0),
                                'event_title': event.get('title', '')
                            })
            processed['markets'] = markets
            processed['events'] = events
        
        elif 'question' in data:
            # 单个市场数据
            processed['market'] = {
                'question': data.get('question', ''),
                'slug': data.get('slug', ''),
                'outcomes': data.get('outcomes', []),
                'outcome_prices': data.get('outcomePrices', []),
                'volume': data.get('volumeNum', 0),
                'liquidity': data.get('liquidity', 0)
            }
        
        return processed


class WebAdapter(DataSourceAdapter):
    """Web数据源适配器"""
    
    def __init__(self, source_state: SourceState):
        super().__init__(source_state)
        self.session = None
        self._setup_session()
    
    def _setup_session(self):
        """设置HTTP会话"""
        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
        except ImportError:
            logger.warning("requests未安装，Web抓取功能将不可用")
    
    def __del__(self):
        """析构函数，关闭会话"""
        if hasattr(self, 'session') and self.session:
            try:
                self.session.close()
            except Exception:
                pass
    
    async def fetch_data(self, request: DataRequest) -> DataResponse:
        """从Web获取数据"""
        start_time = time.time()
        
        try:
            if not self.session:
                raise Exception("requests库未安装，无法执行Web抓取")
            
            # 根据数据源类型和查询内容构建请求
            url = self._build_url(request.query)
            if not url:
                raise Exception(f"无法为查询 '{request.query}' 构建URL")
            
            # 执行Web请求
            response = self.session.get(url, timeout=self.source_state.config.timeout / 1000)
            response.raise_for_status()
            
            # 解析HTML响应
            html = response.text
            processed_data = self._parse_html_response(html, request.query)
            
            response_time = (time.time() - start_time) * 1000
            
            return DataResponse(
                success=True,
                data=processed_data,
                source=self.source_state.config.name,
                response_time=response_time,
                quality_score=0.7
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Web请求失败: {e}")
            
            return DataResponse(
                success=False,
                source=self.source_state.config.name,
                response_time=response_time,
                error_message=str(e)
            )
    
    def _build_url(self, query: str) -> str:
        """根据查询构建URL"""
        base_url = self.source_state.config.url
        if not base_url:
            return None
        
        # 根据查询内容构建特定URL
        query_lower = query.lower()
        
        if 'crude oil' in query_lower or 'oil' in query_lower:
            if 'polyspotter' in base_url:
                return f"{base_url}/event/cl-hit-jun-2026"
            elif 'polymarketanalytics' in base_url:
                return f"{base_url}/markets/crude-oil"
        elif 'gold' in query_lower:
            if 'polyspotter' in base_url:
                return f"{base_url}/event/gc-hit-jun-2026"
            elif 'polymarketanalytics' in base_url:
                return f"{base_url}/markets/gold"
        elif 'silver' in query_lower:
            if 'polyspotter' in base_url:
                return f"{base_url}/event/si-hit-jun-2026"
            elif 'polymarketanalytics' in base_url:
                return f"{base_url}/markets/silver"
        
        # 默认返回主页
        return base_url
    
    def _parse_html_response(self, html: str, query: str) -> dict:
        """解析HTML响应"""
        import re
        
        processed = {
            'query': query,
            'source': self.source_state.config.name,
            'timestamp': datetime.now().isoformat(),
            'html_length': len(html),
            'markets': []
        }
        
        # 清理HTML
        html_clean = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        # 根据查询内容提取市场数据
        query_lower = query.lower()
        
        if 'crude oil' in query_lower or 'oil' in query_lower:
            markets = self._extract_oil_markets(html_clean)
            processed['markets'] = markets
            processed['asset'] = 'Crude Oil'
        elif 'gold' in query_lower:
            markets = self._extract_gold_markets(html_clean)
            processed['markets'] = markets
            processed['asset'] = 'Gold'
        elif 'silver' in query_lower:
            markets = self._extract_silver_markets(html_clean)
            processed['markets'] = markets
            processed['asset'] = 'Silver'
        
        # 提取摘要信息
        summary_pattern = r'(\d+) signals across (\d+) markets ·?\$([\d,]+) tracked'
        summary_match = re.search(summary_pattern, html)
        if summary_match:
            processed['total_signals'] = int(summary_match.group(1))
            processed['total_markets'] = int(summary_match.group(2))
            processed['total_volume'] = int(summary_match.group(3).replace(',', ''))
        
        return processed
    
    def _extract_oil_markets(self, html: str) -> list:
        """提取原油市场数据"""
        import re
        markets = []
        
        # 提取市场名称
        market_pattern = r'Will Crude Oil \(CL\) hit \(?(HIGH|LOW)\)? \$(\d[\d,]*) by end of June\?'
        market_matches = re.findall(market_pattern, html)
        
        # 提取信号和成交量
        signal_pattern = r'\[(\d+)," signal","s?"," ·"," ","\$\$([\d,]+)"," tracked"\]'
        signal_matches = re.findall(signal_pattern, html)
        
        signal_pattern_singular = r'\[(\d+)," signal",""," ·"," ","\$\$([\d,]+)"," tracked"\]'
        signal_matches_singular = re.findall(signal_pattern_singular, html)
        
        all_signal_matches = signal_matches + signal_matches_singular
        
        # 创建市场列表
        if len(market_matches) == len(all_signal_matches):
            for i, (direction, price_str) in enumerate(market_matches):
                signals_str, volume_str = all_signal_matches[i]
                price = int(price_str.replace(',', ''))
                signals = int(signals_str)
                volume = int(volume_str.replace(',', ''))
                
                markets.append({
                    'question': f"Will Crude Oil (CL) hit ${price:,} by end of June?",
                    'direction': direction,
                    'price': price,
                    'signals': signals,
                    'volume': volume,
                    'probability': self._estimate_probability(signals, volume)
                })
        
        return markets
    
    def _extract_gold_markets(self, html: str) -> list:
        """提取黄金市场数据"""
        import re
        markets = []
        
        # 提取市场名称
        market_pattern = r'Will Gold \(GC\) hit \(?(HIGH|LOW)\)? \$(\d[\d,]*) by end of June\?'
        market_matches = re.findall(market_pattern, html)
        
        # 提取信号和成交量
        signal_pattern = r'\[(\d+)," signal","s?"," ·"," ","\$\$([\d,]+)"," tracked"\]'
        signal_matches = re.findall(signal_pattern, html)
        
        signal_pattern_singular = r'\[(\d+)," signal",""," ·"," ","\$\$([\d,]+)"," tracked"\]'
        signal_matches_singular = re.findall(signal_pattern_singular, html)
        
        all_signal_matches = signal_matches + signal_matches_singular
        
        # 创建市场列表
        if len(market_matches) == len(all_signal_matches):
            for i, (direction, price_str) in enumerate(market_matches):
                signals_str, volume_str = all_signal_matches[i]
                price = int(price_str.replace(',', ''))
                signals = int(signals_str)
                volume = int(volume_str.replace(',', ''))
                
                markets.append({
                    'question': f"Will Gold (GC) hit ${price:,} by end of June?",
                    'direction': direction,
                    'price': price,
                    'signals': signals,
                    'volume': volume,
                    'probability': self._estimate_probability(signals, volume)
                })
        
        return markets
    
    def _extract_silver_markets(self, html: str) -> list:
        """提取白银市场数据"""
        import re
        markets = []
        
        # 提取市场名称
        market_pattern = r'Will Silver \(SI\) hit \(?(HIGH|LOW)\)? \$(\d[\d,]*) by end of June\?'
        market_matches = re.findall(market_pattern, html)
        
        # 提取信号和成交量
        signal_pattern = r'\[(\d+)," signal","s?"," ·"," ","\$\$([\d,]+)"," tracked"\]'
        signal_matches = re.findall(signal_pattern, html)
        
        signal_pattern_singular = r'\[(\d+)," signal",""," ·"," ","\$\$([\d,]+)"," tracked"\]'
        signal_matches_singular = re.findall(signal_pattern_singular, html)
        
        all_signal_matches = signal_matches + signal_matches_singular
        
        # 创建市场列表
        if len(market_matches) == len(all_signal_matches):
            for i, (direction, price_str) in enumerate(market_matches):
                signals_str, volume_str = all_signal_matches[i]
                price = int(price_str.replace(',', ''))
                signals = int(signals_str)
                volume = int(volume_str.replace(',', ''))
                
                markets.append({
                    'question': f"Will Silver (SI) hit ${price:,} by end of June?",
                    'direction': direction,
                    'price': price,
                    'signals': signals,
                    'volume': volume,
                    'probability': self._estimate_probability(signals, volume)
                })
        
        return markets
    
    def _estimate_probability(self, signals: int, volume: int) -> float:
        """基于信号和成交量估算概率"""
        if signals == 0:
            return 0.0
        elif signals == 1:
            return 0.1 if volume < 10000 else 0.2
        elif signals <= 5:
            return 0.3 if volume < 50000 else 0.4
        elif signals <= 10:
            return 0.5 if volume < 100000 else 0.6
        else:
            return 0.7 if volume < 200000 else 0.8


class CacheAdapter(DataSourceAdapter):
    """缓存数据源适配器"""
    
    def __init__(self, source_state: SourceState, cache: LocalCache):
        super().__init__(source_state)
        self.cache = cache
    
    async def fetch_data(self, request: DataRequest) -> DataResponse:
        """从缓存获取数据"""
        start_time = time.time()
        
        try:
            cached_data = self.cache.get(request.cache_key)
            
            response_time = (time.time() - start_time) * 1000
            
            if cached_data is not None:
                return DataResponse(
                    success=True,
                    data=cached_data,
                    source=self.source_state.config.name,
                    response_time=response_time,
                    quality_score=0.6,
                    from_cache=True
                )
            else:
                return DataResponse(
                    success=False,
                    source=self.source_state.config.name,
                    response_time=response_time,
                    error_message="缓存未命中"
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"缓存请求失败: {e}")
            
            return DataResponse(
                success=False,
                source=self.source_state.config.name,
                response_time=response_time,
                error_message=str(e)
            )


class SmartRouter:
    """智能路由引擎"""
    
    def __init__(self, source_manager: SourceManager):
        self.source_manager = source_manager
        self.cache = LocalCache()
        self.adapters: Dict[str, DataSourceAdapter] = {}
        self._lock = threading.RLock()
        
        # 路由统计
        self._stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'source_failovers': 0
        }
        
        # 初始化适配器
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """初始化数据源适配器"""
        with self._lock:
            for state in self.source_manager.list_sources():
                adapter = self._create_adapter(state)
                if adapter:
                    self.adapters[state.config.name] = adapter
    
    def _create_adapter(self, state: SourceState) -> Optional[DataSourceAdapter]:
        """创建数据源适配器"""
        if state.config.source_type == SourceType.API:
            return APIAdapter(state)
        elif state.config.source_type == SourceType.WEB:
            return WebAdapter(state)
        elif state.config.source_type == SourceType.CACHE:
            return CacheAdapter(state, self.cache)
        else:
            logger.warning(f"未知的数据源类型: {state.config.source_type}")
            return None
    
    def get_adapter(self, source_name: str) -> Optional[DataSourceAdapter]:
        """获取数据源适配器"""
        return self.adapters.get(source_name)
    
    def select_source(self, request: DataRequest, 
                     exclude_sources: Optional[List[str]] = None) -> Optional[SourceState]:
        """选择数据源"""
        with self._lock:
            # 获取可用数据源
            available_sources = self.source_manager.get_sources_by_priority()
            
            # 过滤排除的数据源
            if exclude_sources:
                available_sources = [
                    s for s in available_sources
                    if s.config.name not in exclude_sources
                ]
            
            # 过滤首选数据源
            if request.preferred_sources:
                preferred = [
                    s for s in available_sources
                    if s.config.name in request.preferred_sources
                ]
                if preferred:
                    available_sources = preferred
            
            # 过滤健康的数据源
            healthy_sources = [
                s for s in available_sources
                if s.status in [SourceStatus.HEALTHY, SourceStatus.DEGRADED]
                and s.config.enabled
            ]
            
            if not healthy_sources:
                logger.warning("没有健康的数据源可用")
                # 尝试使用不健康的数据源
                healthy_sources = [
                    s for s in available_sources
                    if s.config.enabled
                ]
            
            if not healthy_sources:
                return None
            
            # 选择第一个健康的数据源（按优先级排序）
            return healthy_sources[0]
    
    async def execute_request(self, request: DataRequest) -> DataResponse:
        """执行数据请求"""
        self._stats['total_requests'] += 1
        
        # 检查缓存
        if request.cache_strategy == CacheStrategy.LOCAL:
            cached_data = self.cache.get(request.cache_key)
            if cached_data is not None:
                self._stats['cache_hits'] += 1
                return DataResponse(
                    success=True,
                    data=cached_data,
                    source="local-cache",
                    response_time=0.0,
                    quality_score=0.6,
                    from_cache=True
                )
            self._stats['cache_misses'] += 1
        
        # 选择数据源
        exclude_sources = list(request.excluded_sources or [])
        last_error = None
        
        for attempt in range(request.max_retries):
            source = self.select_source(request, exclude_sources)
            
            if source is None:
                logger.error("没有可用的数据源")
                break
            
            adapter = self.get_adapter(source.config.name)
            if adapter is None:
                logger.error(f"没有找到数据源适配器: {source.config.name}")
                exclude_sources.append(source.config.name)
                continue
            
            try:
                response = await adapter.fetch_data(request)
                
                if response.success:
                    # 记录成功
                    self.source_manager.record_request_success(
                        source.config.name, 
                        response.response_time
                    )
                    
                    # 缓存响应
                    if (request.cache_strategy == CacheStrategy.LOCAL and 
                        response.data is not None):
                        self.cache.set(
                            request.cache_key, 
                            response.data, 
                            request.cache_ttl
                        )
                    
                    self._stats['successful_requests'] += 1
                    return response
                else:
                    # 记录失败
                    self.source_manager.record_request_failure(
                        source.config.name, 
                        response.error_message
                    )
                    
                    last_error = response.error_message
                    exclude_sources.append(source.config.name)
                    self._stats['source_failovers'] += 1
                    
                    logger.warning(f"数据源 {source.config.name} 请求失败: {response.error_message}")
                    
                    # 等待重试延迟
                    if attempt < request.max_retries - 1:
                        await asyncio.sleep(source.config.retry_delay / 1000)
                    
            except Exception as e:
                # 记录异常
                self.source_manager.record_request_failure(
                    source.config.name, 
                    str(e)
                )
                
                last_error = str(e)
                exclude_sources.append(source.config.name)
                self._stats['source_failovers'] += 1
                
                logger.error(f"数据源 {source.config.name} 请求异常: {e}")
                
                # 等待重试延迟
                if attempt < request.max_retries - 1:
                    await asyncio.sleep(source.config.retry_delay / 1000)
        
        # 所有重试都失败
        self._stats['failed_requests'] += 1
        
        return DataResponse(
            success=False,
            error_message=last_error or "所有数据源请求失败",
            metadata={'attempts': request.max_retries, 'excluded_sources': exclude_sources}
        )
    
    def execute_request_sync(self, request: DataRequest) -> DataResponse:
        """同步执行数据请求"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.execute_request(request))
        finally:
            loop.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        with self._lock:
            stats = self._stats.copy()
            stats['cache_size'] = self.cache.size()
            stats['adapter_count'] = len(self.adapters)
            return stats
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        logger.info("缓存已清空")
    
    def update_source_config(self, source_name: str, **kwargs) -> bool:
        """更新数据源配置"""
        try:
            state = self.source_manager.get_source(source_name)
            if state is None:
                return False
            
            # 更新配置
            for key, value in kwargs.items():
                if hasattr(state.config, key):
                    setattr(state.config, key, value)
            
            # 重新创建适配器
            adapter = self._create_adapter(state)
            if adapter:
                self.adapters[source_name] = adapter
            
            return True
            
        except Exception as e:
            logger.error(f"更新数据源配置失败: {e}")
            return False
    
    def add_source(self, config) -> bool:
        """添加新数据源"""
        try:
            # 注册数据源
            success = self.source_manager.register_source(config)
            if not success:
                return False
            
            # 创建适配器
            state = self.source_manager.get_source(config.name)
            if state:
                adapter = self._create_adapter(state)
                if adapter:
                    self.adapters[config.name] = adapter
            
            logger.info(f"成功添加数据源: {config.name}")
            return True
            
        except Exception as e:
            logger.error(f"添加数据源失败: {e}")
            return False
    
    def remove_source(self, source_name: str) -> bool:
        """移除数据源"""
        try:
            # 移除适配器
            if source_name in self.adapters:
                del self.adapters[source_name]
            
            # 注销数据源
            success = self.source_manager.unregister_source(source_name)
            
            if success:
                logger.info(f"成功移除数据源: {source_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"移除数据源失败: {e}")
            return False