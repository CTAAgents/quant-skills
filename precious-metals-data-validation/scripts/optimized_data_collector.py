#!/usr/bin/env python3
"""
优化版贵金属多源数据采集器
特点：并行采集、缓存机制、更好的错误处理、备用数据源
"""

import requests
import json
import time
import hashlib
import pickle
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

class DataTimeframe(Enum):
    """数据时间框架"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

@dataclass
class TechnicalIndicator:
    """技术指标数据类"""
    name: str
    value: float
    signal: str  # "buy", "sell", "neutral"
    source: str
    timeframe: DataTimeframe
    timestamp: datetime

@dataclass
class PriceData:
    """价格数据类"""
    symbol: str
    price: float
    change: float
    change_percent: float
    high: float
    low: float
    open: float
    close: float
    volume: int
    timestamp: datetime
    source: str

class OptimizedPreciousMetalsDataCollector:
    """优化版贵金属多源数据采集器"""
    
    def __init__(self, cache_dir: str = None, max_workers: int = 4):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 数据源配置
        self.data_sources = {
            'investing_com': 'https://api.investing.com/api/financialdata/',
            'barchart': 'https://marketdata.websol.barchart.com/',
            'tradingview': 'https://scanner.tradingview.com/forex/scan',
            'yahoo_finance': 'https://query1.finance.yahoo.com/v8/finance/chart/',
            'kitco': 'https://www.kitco.com/charts/',
            'goldprice': 'https://goldprice.org/'
        }
        
        # 缓存配置
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_duration = timedelta(minutes=5)  # 缓存5分钟
        
        # 并行配置
        self.max_workers = max_workers
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 性能统计
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'total_time': 0
        }
    
    def _get_cache_key(self, symbol: str, source: str, timeframe: str) -> str:
        """生成缓存键"""
        key = f"{symbol}_{source}_{timeframe}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.pkl")
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """从缓存加载数据"""
        cache_path = self._get_cache_path(cache_key)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    cache_data = pickle.load(f)
                    # 检查缓存是否过期
                    if datetime.now() - cache_data['timestamp'] < self.cache_duration:
                        self.stats['cache_hits'] += 1
                        return cache_data['data']
            except Exception:
                pass
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict):
        """保存数据到缓存"""
        cache_path = self._get_cache_path(cache_key)
        try:
            cache_data = {
                'timestamp': datetime.now(),
                'data': data
            }
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
        except Exception as e:
            print(f"Cache save error: {e}")
    
    def fetch_investing_com_data(self, symbol: str, timeframe: DataTimeframe = DataTimeframe.DAILY) -> Optional[Dict]:
        """从Investing.com获取数据"""
        cache_key = self._get_cache_key(symbol, 'investing_com', timeframe.value)
        
        # 尝试从缓存加载
        cached_data = self._load_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        try:
            # Investing.com API endpoints
            endpoints = {
                'XAUUSD': 'gold',
                'XAGUSD': 'silver',
                'XPTUSD': 'platinum',
                'XPDUSD': 'palladium'
            }
            
            if symbol not in endpoints:
                return None
                
            instrument_symbol = endpoints[symbol]
            
            # 获取实时数据
            url = f"https://api.investing.com/api/financialdata/assets/{instrument_symbol}"
            headers = {
                'domain-id': 'www',
                'accept': 'application/json'
            }
            
            response = self.session.get(url, headers=headers, timeout=10)
            self.stats['total_requests'] += 1
            
            if response.status_code == 200:
                data = response.json()
                result = self._parse_investing_com_response(data, symbol)
                if result:
                    self.stats['successful_requests'] += 1
                    self._save_to_cache(cache_key, result)
                    return result
            
            self.stats['failed_requests'] += 1
            
        except Exception as e:
            print(f"Investing.com fetch error for {symbol}: {e}")
            self.stats['failed_requests'] += 1
            
        return None
    
    def fetch_barchart_data(self, symbol: str, timeframe: DataTimeframe = DataTimeframe.DAILY) -> Optional[Dict]:
        """从Barchart获取数据"""
        cache_key = self._get_cache_key(symbol, 'barchart', timeframe.value)
        
        # 尝试从缓存加载
        cached_data = self._load_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        try:
            # Barchart API endpoints
            symbols = {
                'XAUUSD': 'GCUSD',
                'XAGUSD': 'SIUSD',
                'XPTUSD': 'PLUSD',
                'XPDUSD': 'PAUSD'
            }
            
            if symbol not in symbols:
                return None
                
            barchart_symbol = symbols[symbol]
            
            # 获取技术分析数据
            url = f"{self.data_sources['barchart']}getTechnicals.json"
            params = {
                'symbol': barchart_symbol,
                'fields': 'open,high,low,close,volume,change,changePercent',
                'type': 'daily',
                'limit': 120
            }
            
            response = self.session.get(url, params=params, timeout=10)
            self.stats['total_requests'] += 1
            
            if response.status_code == 200:
                data = response.json()
                result = self._parse_barchart_response(data, symbol)
                if result:
                    self.stats['successful_requests'] += 1
                    self._save_to_cache(cache_key, result)
                    return result
            
            self.stats['failed_requests'] += 1
            
        except Exception as e:
            print(f"Barchart fetch error for {symbol}: {e}")
            self.stats['failed_requests'] += 1
            
        return None
    
    def fetch_tradingview_data(self, symbol: str, timeframe: DataTimeframe = DataTimeframe.DAILY) -> Optional[Dict]:
        """从TradingView获取数据"""
        cache_key = self._get_cache_key(symbol, 'tradingview', timeframe.value)
        
        # 尝试从缓存加载
        cached_data = self._load_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        try:
            # TradingView Scanner API
            symbols = {
                'XAUUSD': 'FX:XAUUSD',
                'XAGUSD': 'FX:XAGUSD',
                'XPTUSD': 'COMEX:PL1!',
                'XPDUSD': 'COMEX:PA1!'
            }
            
            if symbol not in symbols:
                return None
                
            tv_symbol = symbols[symbol]
            
            # 获取技术指标
            url = self.data_sources['tradingview']
            payload = {
                "symbols": {"tickers": [tv_symbol], "query": {"types": []}},
                "columns": [
                    "close", "change", "change_abs", "high", "low", "open",
                    "volume", "Recommend.All", "RSI", "MACD.macd", "MACD.signal",
                    "ADX", "ADX_DI+", "ADX_DI-", "CCI", "Stoch.K", "Stoch.D",
                    "ATR", "BB.upper", "BB.lower"
                ]
            }
            
            response = self.session.post(url, json=payload, timeout=10)
            self.stats['total_requests'] += 1
            
            if response.status_code == 200:
                data = response.json()
                result = self._parse_tradingview_response(data, symbol)
                if result:
                    self.stats['successful_requests'] += 1
                    self._save_to_cache(cache_key, result)
                    return result
            
            self.stats['failed_requests'] += 1
            
        except Exception as e:
            print(f"TradingView fetch error for {symbol}: {e}")
            self.stats['failed_requests'] += 1
            
        return None
    
    def fetch_kitco_data(self, symbol: str, timeframe: DataTimeframe = DataTimeframe.DAILY) -> Optional[Dict]:
        """从Kitco获取数据（备用数据源）"""
        cache_key = self._get_cache_key(symbol, 'kitco', timeframe.value)
        
        # 尝试从缓存加载
        cached_data = self._load_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        try:
            # Kitco数据获取
            symbols = {
                'XAUUSD': 'gold',
                'XAGUSD': 'silver',
                'XPTUSD': 'platinum',
                'XPDUSD': 'palladium'
            }
            
            if symbol not in symbols:
                return None
            
            # 这里可以添加Kitco的具体API调用
            # 暂时返回None，表示该数据源不可用
            self.stats['total_requests'] += 1
            self.stats['failed_requests'] += 1
            
        except Exception as e:
            print(f"Kitco fetch error for {symbol}: {e}")
            self.stats['failed_requests'] += 1
            
        return None
    
    def _parse_investing_com_response(self, data: Dict, symbol: str) -> Optional[Dict]:
        """解析Investing.com响应"""
        try:
            # 处理不同的响应格式
            if 'last' in data:
                # 实时数据格式
                latest = data
                return {
                    'symbol': symbol,
                    'price': float(latest.get('last', 0)),
                    'change': float(latest.get('change', 0)),
                    'change_percent': float(latest.get('changePercent', 0)),
                    'high': float(latest.get('high', 0)),
                    'low': float(latest.get('low', 0)),
                    'open': float(latest.get('open', 0)),
                    'close': float(latest.get('last', 0)),
                    'volume': int(latest.get('volume', 0)),
                    'timestamp': datetime.now(),
                    'source': 'investing_com',
                    'timeframe': DataTimeframe.DAILY
                }
            elif 'data' in data:
                # 历史数据格式
                candles = data['data']
                if not candles:
                    return None
                    
                latest = candles[-1]
                return {
                    'symbol': symbol,
                    'price': float(latest.get('close', 0)),
                    'open': float(latest.get('open', 0)),
                    'high': float(latest.get('high', 0)),
                    'low': float(latest.get('low', 0)),
                    'volume': int(latest.get('volume', 0)),
                    'change': float(latest.get('close', 0)) - float(latest.get('open', 0)),
                    'change_percent': ((float(latest.get('close', 0)) - float(latest.get('open', 0))) / float(latest.get('open', 1))) * 100,
                    'timestamp': datetime.fromtimestamp(latest.get('time', 0)),
                    'source': 'investing_com',
                    'timeframe': DataTimeframe.DAILY
                }
            
        except Exception as e:
            print(f"Parse Investing.com error: {e}")
            return None
    
    def _parse_barchart_response(self, data: Dict, symbol: str) -> Optional[Dict]:
        """解析Barchart响应"""
        try:
            if 'results' not in data:
                return None
                
            results = data['results']
            if not results:
                return None
                
            latest = results[-1]
            
            return {
                'symbol': symbol,
                'price': latest.get('close', 0),
                'open': latest.get('open', 0),
                'high': latest.get('high', 0),
                'low': latest.get('low', 0),
                'volume': latest.get('volume', 0),
                'change': latest.get('change', 0),
                'change_percent': latest.get('changePercent', 0),
                'timestamp': datetime.now(),
                'source': 'barchart',
                'timeframe': DataTimeframe.DAILY
            }
            
        except Exception as e:
            print(f"Parse Barchart error: {e}")
            return None
    
    def _parse_tradingview_response(self, data: Dict, symbol: str) -> Optional[Dict]:
        """解析TradingView响应"""
        try:
            if 'data' not in data:
                return None
                
            data_list = data['data']
            if not data_list:
                return None
                
            latest = data_list[0]
            columns = latest.get('d', [])
            
            if len(columns) < 20:
                return None
                
            return {
                'symbol': symbol,
                'price': columns[0] if columns[0] else 0,
                'change': columns[2] if columns[2] else 0,
                'change_percent': columns[1] if columns[1] else 0,
                'high': columns[3] if columns[3] else 0,
                'low': columns[4] if columns[4] else 0,
                'open': columns[5] if columns[5] else 0,
                'volume': columns[6] if columns[6] else 0,
                'rsi': columns[8] if columns[8] else 0,
                'macd': columns[9] if columns[9] else 0,
                'macd_signal': columns[10] if columns[10] else 0,
                'adx': columns[11] if columns[11] else 0,
                'adx_plus': columns[12] if columns[12] else 0,
                'adx_minus': columns[13] if columns[13] else 0,
                'cci': columns[14] if columns[14] else 0,
                'stoch_k': columns[15] if columns[15] else 0,
                'stoch_d': columns[16] if columns[16] else 0,
                'atr': columns[17] if columns[17] else 0,
                'bb_upper': columns[18] if columns[18] else 0,
                'bb_lower': columns[19] if columns[19] else 0,
                'timestamp': datetime.now(),
                'source': 'tradingview',
                'timeframe': DataTimeframe.DAILY
            }
            
        except Exception as e:
            print(f"Parse TradingView error: {e}")
            return None
    
    def collect_single_source(self, symbol: str, source_name: str, fetch_func) -> Optional[Dict]:
        """采集单个数据源"""
        try:
            data = fetch_func(symbol)
            if data:
                print(f"  ✓ {source_name}: {data['price']:.2f}")
                return data
            else:
                print(f"  ✗ {source_name}: 无数据")
                return None
        except Exception as e:
            print(f"  ✗ {source_name}: 错误 - {e}")
            return None
    
    def collect_multi_source_data_parallel(self, symbols: List[str]) -> Dict[str, List[Dict]]:
        """并行多源数据采集"""
        results = {symbol: [] for symbol in symbols}
        
        # 定义数据源
        sources = [
            ('investing_com', self.fetch_investing_com_data),
            ('barchart', self.fetch_barchart_data),
            ('tradingview', self.fetch_tradingview_data),
            ('kitco', self.fetch_kitco_data)
        ]
        
        # 使用线程池并行采集
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_symbol_source = {}
            for symbol in symbols:
                for source_name, fetch_func in sources:
                    future = executor.submit(self.collect_single_source, symbol, source_name, fetch_func)
                    future_to_symbol_source[future] = (symbol, source_name)
            
            # 收集结果
            for future in as_completed(future_to_symbol_source):
                symbol, source_name = future_to_symbol_source[future]
                try:
                    data = future.result()
                    if data:
                        with self._lock:
                            results[symbol].append(data)
                except Exception as e:
                    print(f"  ✗ {source_name} for {symbol}: 异常 - {e}")
        
        return results
    
    def collect_multi_source_data_sequential(self, symbols: List[str]) -> Dict[str, List[Dict]]:
        """顺序多源数据采集（备用方法）"""
        results = {symbol: [] for symbol in symbols}
        
        for symbol in symbols:
            print(f"采集 {symbol} 数据...")
            
            # 从多个数据源采集
            sources = [
                ('investing_com', self.fetch_investing_com_data),
                ('barchart', self.fetch_barchart_data),
                ('tradingview', self.fetch_tradingview_data),
                ('kitco', self.fetch_kitco_data)
            ]
            
            for source_name, fetch_func in sources:
                data = self.collect_single_source(symbol, source_name, fetch_func)
                if data:
                    results[symbol].append(data)
            
            # 避免请求过快
            time.sleep(0.5)
        
        return results
    
    def collect_multi_source_data(self, symbols: List[str], parallel: bool = True) -> Dict[str, List[Dict]]:
        """多源数据采集（主方法）"""
        start_time = time.time()
        
        if parallel:
            results = self.collect_multi_source_data_parallel(symbols)
        else:
            results = self.collect_multi_source_data_sequential(symbols)
        
        # 更新统计信息
        self.stats['total_time'] = time.time() - start_time
        
        return results
    
    def validate_data_consistency(self, data_list: List[Dict]) -> Tuple[bool, str]:
        """验证数据一致性"""
        if not data_list:
            return False, "无数据"
        
        # 检查价格一致性
        prices = [d['price'] for d in data_list if 'price' in d]
        if not prices:
            return False, "无价格数据"
        
        avg_price = np.mean(prices)
        price_std = np.std(prices)
        price_cv = price_std / avg_price if avg_price > 0 else 0
        
        # 检查时间框架
        timeframes = [d.get('timeframe') for d in data_list]
        daily_count = sum(1 for tf in timeframes if tf == DataTimeframe.DAILY)
        
        # 数据一致性判断
        if price_cv > 0.01:  # 价格变异系数大于1%
            return False, f"价格不一致: 变异系数={price_cv:.4f}"
        
        if daily_count < len(data_list) * 0.5:
            return False, f"非日线数据过多: {daily_count}/{len(data_list)}"
        
        return True, f"数据一致: 价格变异系数={price_cv:.4f}"
    
    def calculate_consensus_data(self, data_list: List[Dict]) -> Dict:
        """计算共识数据（多源数据融合）"""
        if not data_list:
            return {}
        
        # 提取价格数据
        prices = [d['price'] for d in data_list if 'price' in d]
        if not prices:
            return {}
        
        # 计算加权平均价格（基于数据源权重）
        source_weights = {
            'barchart': 1.2,
            'tradingview': 1.1,
            'investing_com': 1.0,
            'kitco': 0.9
        }
        
        weighted_sum = 0
        weight_total = 0
        
        for data in data_list:
            source = data.get('source', 'unknown')
            weight = source_weights.get(source, 1.0)
            price = data.get('price', 0)
            
            if price > 0:
                weighted_sum += price * weight
                weight_total += weight
        
        if weight_total == 0:
            return {}
        
        consensus_price = weighted_sum / weight_total
        
        # 计算其他指标的共识值
        consensus_data = {
            'symbol': data_list[0].get('symbol', ''),
            'price': consensus_price,
            'timestamp': datetime.now(),
            'sources_count': len(data_list),
            'price_range': (min(prices), max(prices)),
            'price_std': np.std(prices)
        }
        
        return consensus_data
    
    def get_performance_stats(self) -> Dict:
        """获取性能统计"""
        return {
            'total_requests': self.stats['total_requests'],
            'successful_requests': self.stats['successful_requests'],
            'failed_requests': self.stats['failed_requests'],
            'success_rate': self.stats['successful_requests'] / max(self.stats['total_requests'], 1),
            'cache_hits': self.stats['cache_hits'],
            'cache_hit_rate': self.stats['cache_hits'] / max(self.stats['total_requests'], 1),
            'total_time': self.stats['total_time'],
            'avg_time_per_request': self.stats['total_time'] / max(self.stats['total_requests'], 1)
        }
    
    def clear_cache(self):
        """清除缓存"""
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.pkl'):
                    os.remove(os.path.join(self.cache_dir, filename))
            print(f"缓存已清除: {self.cache_dir}")
        except Exception as e:
            print(f"清除缓存失败: {e}")

# 测试函数
def test_optimized_collector():
    """测试优化版数据采集器"""
    print("测试优化版数据采集器")
    print("=" * 50)
    
    collector = OptimizedPreciousMetalsDataCollector()
    
    # 测试单个数据源
    print("\n1. 测试单个数据源:")
    symbols = ['XAUUSD', 'XAGUSD']
    
    for symbol in symbols:
        print(f"\n{symbol}:")
        data = collector.fetch_investing_com_data(symbol)
        if data:
            print(f"  ✓ Investing.com: {data['price']:.2f}")
        else:
            print(f"  ✗ Investing.com: 无数据")
    
    # 测试并行采集
    print("\n2. 测试并行采集:")
    results = collector.collect_multi_source_data_parallel(symbols)
    
    for symbol, data_list in results.items():
        print(f"\n{symbol}: {len(data_list)} 个数据源")
        for data in data_list:
            print(f"  - {data['source']}: {data['price']:.2f}")
    
    # 测试数据验证
    print("\n3. 测试数据验证:")
    for symbol, data_list in results.items():
        if data_list:
            is_valid, message = collector.validate_data_consistency(data_list)
            print(f"{symbol}: {message}")
    
    # 测试共识数据计算
    print("\n4. 测试共识数据计算:")
    for symbol, data_list in results.items():
        if data_list:
            consensus = collector.calculate_consensus_data(data_list)
            if consensus:
                print(f"{symbol}: 共识价格 = {consensus['price']:.2f}")
    
    # 性能统计
    print("\n5. 性能统计:")
    stats = collector.get_performance_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    
    return collector

if __name__ == "__main__":
    test_optimized_collector()