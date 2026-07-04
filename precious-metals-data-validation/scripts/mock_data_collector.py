#!/usr/bin/env python3
"""
贵金属数据模拟采集器
用于测试和演示，提供模拟数据
"""

from datetime import datetime
from typing import Dict, List
import random
import numpy as np

class MockDataCollector:
    """模拟数据采集器"""
    
    def __init__(self):
        # 模拟基准价格（2026年6月22日）
        self.base_prices = {
            'XAUUSD': 4191.35,
            'XAGUSD': 66.438,
            'XPTUSD': 1680.40,
            'XPDUSD': 1273.25
        }
        
        # 模拟技术指标
        self.base_indicators = {
            'XAUUSD': {
                'rsi': 56.55,
                'macd': 4.17,
                'adx': 24.80,
                'cci': 95.91,
                'stoch_k': 75.36,
                'stoch_d': 65.42,
                'atr': 19.51
            },
            'XAGUSD': {
                'rsi': 56.90,
                'macd': 0.24,
                'adx': 18.28,
                'cci': 77.37,
                'stoch_k': 67.08,
                'stoch_d': 58.92,
                'atr': 0.68
            },
            'XPTUSD': {
                'rsi': 51.31,
                'macd': -0.97,
                'adx': 32.73,
                'cci': 84.65,
                'stoch_k': 59.18,
                'stoch_d': 52.34,
                'atr': 14.49
            },
            'XPDUSD': {
                'rsi': 47.18,
                'macd': -0.73,
                'adx': 31.71,
                'cci': 0.00,
                'stoch_k': 40.12,
                'stoch_d': 45.67,
                'atr': 11.07
            }
        }
    
    def collect_mock_data(self, symbols: List[str]) -> Dict[str, List[Dict]]:
        """采集模拟数据"""
        results = {}
        
        for symbol in symbols:
            if symbol not in self.base_prices:
                continue
            
            # 从多个模拟数据源采集
            data_list = []
            
            # 数据源1: Investing.com模拟
            data1 = self._generate_investing_com_mock(symbol)
            if data1:
                data_list.append(data1)
            
            # 数据源2: Barchart模拟
            data2 = self._generate_barchart_mock(symbol)
            if data2:
                data_list.append(data2)
            
            # 数据源3: TradingView模拟
            data3 = self._generate_tradingview_mock(symbol)
            if data3:
                data_list.append(data3)
            
            results[symbol] = data_list
        
        return results
    
    def _generate_investing_com_mock(self, symbol: str) -> Dict:
        """生成Investing.com模拟数据"""
        base_price = self.base_prices[symbol]
        indicators = self.base_indicators[symbol]
        
        # 添加随机波动
        price_variation = random.uniform(-0.5, 0.5)  # ±0.5%波动
        price = base_price * (1 + price_variation / 100)
        
        # 计算其他价格
        open_price = price * (1 + random.uniform(-0.3, 0.3) / 100)
        high_price = max(price, open_price) * (1 + random.uniform(0, 0.5) / 100)
        low_price = min(price, open_price) * (1 - random.uniform(0, 0.5) / 100)
        
        change = price - open_price
        change_percent = (change / open_price) * 100
        
        return {
            'symbol': symbol,
            'price': round(price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'open': round(open_price, 2),
            'close': round(price, 2),
            'volume': random.randint(100000, 200000),
            'source': 'investing_com',
            'timeframe': 'daily',
            'timestamp': datetime.now(),
            'rsi': indicators['rsi'] + random.uniform(-2, 2),
            'macd': indicators['macd'] + random.uniform(-0.5, 0.5),
            'adx': indicators['adx'] + random.uniform(-3, 3),
            'cci': indicators['cci'] + random.uniform(-10, 10)
        }
    
    def _generate_barchart_mock(self, symbol: str) -> Dict:
        """生成Barchart模拟数据"""
        base_price = self.base_prices[symbol]
        indicators = self.base_indicators[symbol]
        
        # 添加随机波动
        price_variation = random.uniform(-0.3, 0.3)  # ±0.3%波动
        price = base_price * (1 + price_variation / 100)
        
        # 计算其他价格
        open_price = price * (1 + random.uniform(-0.2, 0.2) / 100)
        high_price = max(price, open_price) * (1 + random.uniform(0, 0.4) / 100)
        low_price = min(price, open_price) * (1 - random.uniform(0, 0.4) / 100)
        
        change = price - open_price
        change_percent = (change / open_price) * 100
        
        return {
            'symbol': symbol,
            'price': round(price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'open': round(open_price, 2),
            'close': round(price, 2),
            'volume': random.randint(100000, 200000),
            'source': 'barchart',
            'timeframe': 'daily',
            'timestamp': datetime.now(),
            'rsi': indicators['rsi'] + random.uniform(-1, 1),
            'macd': indicators['macd'] + random.uniform(-0.3, 0.3),
            'adx': indicators['adx'] + random.uniform(-2, 2),
            'cci': indicators['cci'] + random.uniform(-5, 5)
        }
    
    def _generate_tradingview_mock(self, symbol: str) -> Dict:
        """生成TradingView模拟数据"""
        base_price = self.base_prices[symbol]
        indicators = self.base_indicators[symbol]
        
        # 添加随机波动
        price_variation = random.uniform(-0.4, 0.4)  # ±0.4%波动
        price = base_price * (1 + price_variation / 100)
        
        # 计算其他价格
        open_price = price * (1 + random.uniform(-0.25, 0.25) / 100)
        high_price = max(price, open_price) * (1 + random.uniform(0, 0.45) / 100)
        low_price = min(price, open_price) * (1 - random.uniform(0, 0.45) / 100)
        
        change = price - open_price
        change_percent = (change / open_price) * 100
        
        return {
            'symbol': symbol,
            'price': round(price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'open': round(open_price, 2),
            'close': round(price, 2),
            'volume': random.randint(100000, 200000),
            'source': 'tradingview',
            'timeframe': 'daily',
            'timestamp': datetime.now(),
            'rsi': indicators['rsi'] + random.uniform(-1.5, 1.5),
            'macd': indicators['macd'] + random.uniform(-0.4, 0.4),
            'adx': indicators['adx'] + random.uniform(-2.5, 2.5),
            'cci': indicators['cci'] + random.uniform(-8, 8)
        }

def main():
    """主函数"""
    collector = MockDataCollector()
    
    print("生成模拟数据...")
    print("=" * 50)
    
    symbols = ['XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD']
    results = collector.collect_mock_data(symbols)
    
    for symbol, data_list in results.items():
        print(f"\n{symbol}:")
        for data in data_list:
            print(f"  {data['source']}: {data['price']:.2f} ({data['change_percent']:+.2f}%)")
    
    print("\n" + "=" * 50)
    print("模拟数据生成完成")

if __name__ == "__main__":
    main()