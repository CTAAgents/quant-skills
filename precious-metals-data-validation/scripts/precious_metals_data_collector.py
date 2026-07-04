#!/usr/bin/env python3
"""
贵金属多源数据采集器
从多个权威数据源获取日线级别技术指标，确保数据准确性
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum

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

class PreciousMetalsDataCollector:
    """贵金属多源数据采集器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.data_sources = {
            'investing_com': 'https://api.investing.com/api/financialdata/',
            'barchart': 'https://marketdata.websol.barchart.com/',
            'tradingview': 'https://scanner.tradingview.com/forex/scan',
            'yahoo_finance': 'https://query1.finance.yahoo.com/v8/finance/chart/'
        }
        
    def fetch_investing_com_data(self, symbol: str, timeframe: DataTimeframe = DataTimeframe.DAILY) -> Optional[Dict]:
        """从Investing.com获取数据"""
        try:
            # Investing.com API endpoints (使用更可靠的端点)
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
            if response.status_code == 200:
                data = response.json()
                return self._parse_investing_com_response(data, symbol)
            
        except Exception as e:
            print(f"Investing.com fetch error for {symbol}: {e}")
            
        return None
    
    def fetch_barchart_data(self, symbol: str, timeframe: DataTimeframe = DataTimeframe.DAILY) -> Optional[Dict]:
        """从Barchart获取数据"""
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
            if response.status_code == 200:
                data = response.json()
                return self._parse_barchart_response(data, symbol)
            
        except Exception as e:
            print(f"Barchart fetch error for {symbol}: {e}")
            
        return None
    
    def fetch_tradingview_data(self, symbol: str, timeframe: DataTimeframe = DataTimeframe.DAILY) -> Optional[Dict]:
        """从TradingView获取数据"""
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
            if response.status_code == 200:
                data = response.json()
                return self._parse_tradingview_response(data, symbol)
            
        except Exception as e:
            print(f"TradingView fetch error for {symbol}: {e}")
            
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
    
    def collect_multi_source_data(self, symbols: List[str]) -> Dict[str, List[Dict]]:
        """多源数据采集"""
        results = {symbol: [] for symbol in symbols}
        
        for symbol in symbols:
            print(f"采集 {symbol} 数据...")
            
            # 从多个数据源采集
            sources = [
                ('investing_com', self.fetch_investing_com_data),
                ('barchart', self.fetch_barchart_data),
                ('tradingview', self.fetch_tradingview_data)
            ]
            
            for source_name, fetch_func in sources:
                try:
                    data = fetch_func(symbol)
                    if data:
                        results[symbol].append(data)
                        print(f"  ✓ {source_name}: {data['price']:.2f}")
                    else:
                        print(f"  ✗ {source_name}: 无数据")
                except Exception as e:
                    print(f"  ✗ {source_name}: 错误 - {e}")
            
            # 避免请求过快
            time.sleep(1)
        
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
        
        # 价格共识（加权平均）
        prices = []
        weights = []
        
        for data in data_list:
            source = data.get('source', '')
            weight = 1.0
            
            # 根据数据源设置权重
            if source == 'barchart':
                weight = 1.2  # Barchart权重较高
            elif source == 'tradingview':
                weight = 1.1
            elif source == 'investing_com':
                weight = 1.0
            
            prices.append(data['price'])
            weights.append(weight)
        
        consensus_price = np.average(prices, weights=weights)
        
        # 计算共识指标
        consensus_data = {
            'symbol': data_list[0]['symbol'],
            'consensus_price': consensus_price,
            'price_sources': len(data_list),
            'price_std': np.std(prices),
            'price_cv': np.std(prices) / consensus_price if consensus_price > 0 else 0,
            'timestamp': datetime.now(),
            'data_sources': [d['source'] for d in data_list]
        }
        
        # 融合技术指标（如果可用）
        for data in data_list:
            if 'rsi' in data:
                consensus_data['rsi'] = data['rsi']
            if 'macd' in data:
                consensus_data['macd'] = data['macd']
            if 'adx' in data:
                consensus_data['adx'] = data['adx']
            if 'cci' in data:
                consensus_data['cci'] = data['cci']
        
        return consensus_data
    
    def generate_validation_report(self, symbol: str, data_list: List[Dict]) -> Dict:
        """生成数据验证报告"""
        report = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'data_count': len(data_list),
            'sources': [d['source'] for d in data_list],
            'validation_results': {}
        }
        
        # 数据一致性验证
        is_consistent, message = self.validate_data_consistency(data_list)
        report['validation_results']['consistency'] = {
            'is_consistent': is_consistent,
            'message': message
        }
        
        # 计算共识数据
        consensus = self.calculate_consensus_data(data_list)
        report['consensus_data'] = consensus
        
        # 价格范围分析
        if data_list:
            prices = [d['price'] for d in data_list]
            report['price_analysis'] = {
                'min_price': min(prices),
                'max_price': max(prices),
                'avg_price': np.mean(prices),
                'price_range': max(prices) - min(prices),
                'price_range_percent': ((max(prices) - min(prices)) / np.mean(prices)) * 100
            }
        
        return report

def main():
    """主函数"""
    collector = PreciousMetalsDataCollector()
    
    # 采集贵金属数据
    symbols = ['XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD']
    
    print("开始多源数据采集...")
    print("=" * 50)
    
    results = collector.collect_multi_source_data(symbols)
    
    print("\n" + "=" * 50)
    print("数据验证报告")
    print("=" * 50)
    
    for symbol, data_list in results.items():
        if data_list:
            report = collector.generate_validation_report(symbol, data_list)
            print(f"\n{symbol}:")
            print(f"  数据源数量: {report['data_count']}")
            print(f"  数据源: {', '.join(report['sources'])}")
            print(f"  一致性验证: {report['validation_results']['consistency']['message']}")
            
            if 'price_analysis' in report:
                pa = report['price_analysis']
                print(f"  价格范围: {pa['min_price']:.2f} - {pa['max_price']:.2f}")
                print(f"  平均价格: {pa['avg_price']:.2f}")
                print(f"  价格范围百分比: {pa['price_range_percent']:.2f}%")
            
            if 'consensus_data' in report and report['consensus_data']:
                cd = report['consensus_data']
                print(f"  共识价格: {cd['consensus_price']:.2f}")
                print(f"  价格标准差: {cd['price_std']:.2f}")
        else:
            print(f"\n{symbol}: 无数据")
    
    print("\n" + "=" * 50)
    print("数据采集完成")

if __name__ == "__main__":
    main()