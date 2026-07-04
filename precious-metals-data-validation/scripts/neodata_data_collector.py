#!/usr/bin/env python3
"""
NeoData贵金属数据采集器
使用neodata-financial-search skill作为主要数据源
"""

import subprocess
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

class DataTimeframe(Enum):
    """数据时间框架"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

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

@dataclass
class TechnicalIndicator:
    """技术指标数据类"""
    name: str
    value: float
    signal: str  # "buy", "sell", "neutral"
    source: str
    timeframe: DataTimeframe
    timestamp: datetime

class NeoDataPreciousMetalsCollector:
    """NeoData贵金属数据采集器"""
    
    def __init__(self, neodata_script_path: str = None):
        """
        初始化NeoData数据采集器
        
        Args:
            neodata_script_path: neodata查询脚本路径
        """
        # neodata脚本路径
        if neodata_script_path is None:
            # 默认路径：neodata skill目录下的scripts/query.py
            # 使用绝对路径避免相对路径问题
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.neodata_script_path = os.path.normpath(os.path.join(
                base_dir, 
                '..', '..', 
                'skill_2053082432761950208', 
                'scripts', 
                'query.py'
            ))
        else:
            self.neodata_script_path = neodata_script_path
        
        # 验证脚本路径是否存在
        if not os.path.exists(self.neodata_script_path):
            print(f"警告: NeoData脚本路径不存在: {self.neodata_script_path}")
        
        # 支持的贵金属品种
        self.symbols = {
            'XAUUSD': '黄金现货',
            'XAGUSD': '白银现货',
            'XPTUSD': '铂金现货',
            'XPDUSD': '钯金现货',
            'GC': 'COMEX黄金期货',
            'SI': 'COMEX白银期货',
            'AU9999': '上海金交所黄金',
            'AG9999': '上海金交所白银'
        }
        
        # 性能统计
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_time': 0
        }
    
    def _query_neodata(self, query: str) -> Optional[Dict]:
        """
        调用neodata API查询数据
        
        Args:
            query: 查询语句
            
        Returns:
            查询结果字典，失败返回None
        """
        try:
            # 构建命令
            cmd = [sys.executable, self.neodata_script_path, '--query', query]
            
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding='utf-8'
            )
            
            if result.returncode == 0 and result.stdout:
                # 解析JSON输出
                try:
                    data = json.loads(result.stdout)
                    if data.get('suc') and data.get('code') == '200':
                        return data
                except json.JSONDecodeError:
                    pass
            
            return None
            
        except Exception as e:
            print(f"NeoData查询失败: {e}")
            return None
    
    def _parse_price_data(self, api_content: str, symbol: str) -> Optional[PriceData]:
        """
        解析neodata返回的价格数据
        
        Args:
            api_content: API返回的内容
            symbol: 品种代码
            
        Returns:
            PriceData对象，解析失败返回None
        """
        try:
            # 解析表格数据
            lines = api_content.strip().split('\n')
            if len(lines) < 3:
                return None
            
            # 查找数据行（跳过表头和分隔符）
            # 表格格式：表头 | 分隔符 | 数据行1 | 数据行2 | ...
            data_lines = []
            for i, line in enumerate(lines):
                if i < 2:  # 跳过前两行（表头和分隔符）
                    continue
                if '|' in line:
                    # 检查是否是分隔符行（包含 :---:）
                    if ':---:' in line:
                        continue
                    data_lines.append(line)
            
            if not data_lines:
                return None
            
            # 使用第一个数据行
            data_line = data_lines[0]
            
            # 解析表格行
            cells = [cell.strip() for cell in data_line.split('|') if cell.strip()]
            if len(cells) < 10:
                return None
            
            # 提取数据
            try:
                price = float(cells[4]) if cells[4] != '--' else 0.0
                change = float(cells[15]) if cells[15] != '--' else 0.0
                change_percent = float(cells[16].replace('%', '')) if cells[16] != '--' else 0.0
                high = float(cells[17]) if cells[17] != '--' else 0.0
                low = float(cells[18]) if cells[18] != '--' else 0.0
                open_price = float(cells[7]) if cells[7] != '--' else 0.0
                close = float(cells[4]) if cells[4] != '--' else 0.0
                volume = int(float(cells[20])) if cells[20] != '--' else 0
            except (ValueError, IndexError):
                return None
            
            # 解析时间
            try:
                timestamp_str = cells[14] if len(cells) > 14 else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            except:
                timestamp = datetime.now()
            
            return PriceData(
                symbol=symbol,
                price=price,
                change=change,
                change_percent=change_percent,
                high=high,
                low=low,
                open=open_price,
                close=close,
                volume=volume,
                timestamp=timestamp,
                source='neodata'
            )
            
        except Exception as e:
            print(f"解析价格数据失败: {e}")
            return None
    
    def get_price(self, symbol: str) -> Optional[PriceData]:
        """
        获取指定品种的价格数据
        
        Args:
            symbol: 品种代码（如XAUUSD、XAGUSD等）
            
        Returns:
            PriceData对象，失败返回None
        """
        self.stats['total_queries'] += 1
        
        # 构建查询语句
        symbol_name = self.symbols.get(symbol, symbol)
        query = f"{symbol_name}最新价格"
        
        # 查询neodata
        result = self._query_neodata(query)
        if result is None:
            self.stats['failed_queries'] += 1
            return None
        
        # 解析结果
        try:
            api_data = result.get('data', {}).get('apiData', {})
            api_recall = api_data.get('apiRecall', [])
            
            if api_recall:
                content = api_recall[0].get('content', '')
                price_data = self._parse_price_data(content, symbol)
                
                if price_data:
                    self.stats['successful_queries'] += 1
                    return price_data
            
            self.stats['failed_queries'] += 1
            return None
            
        except Exception as e:
            print(f"处理查询结果失败: {e}")
            self.stats['failed_queries'] += 1
            return None
    
    def get_all_prices(self) -> Dict[str, Optional[PriceData]]:
        """
        获取所有支持品种的价格数据
        
        Returns:
            品种代码到PriceData的映射
        """
        results = {}
        for symbol in self.symbols.keys():
            results[symbol] = self.get_price(symbol)
        return results
    
    def get_technical_indicators(self, symbol: str) -> List[TechnicalIndicator]:
        """
        获取技术指标数据
        
        Args:
            symbol: 品种代码
            
        Returns:
            技术指标列表
        """
        indicators = []
        
        # 构建查询语句
        symbol_name = self.symbols.get(symbol, symbol)
        query = f"{symbol_name}技术指标 RSI MACD MA"
        
        # 查询neodata
        result = self._query_neodata(query)
        if result is None:
            return indicators
        
        # 解析技术指标
        try:
            api_data = result.get('data', {}).get('apiData', {})
            api_recall = api_data.get('apiRecall', [])
            
            for recall in api_recall:
                content = recall.get('content', '')
                # 这里需要解析技术指标数据
                # 简化处理：返回空列表
                pass
            
            return indicators
            
        except Exception as e:
            print(f"获取技术指标失败: {e}")
            return indicators
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取性能统计
        
        Returns:
            统计信息字典
        """
        return {
            'total_queries': self.stats['total_queries'],
            'successful_queries': self.stats['successful_queries'],
            'failed_queries': self.stats['failed_queries'],
            'success_rate': (
                self.stats['successful_queries'] / self.stats['total_queries'] * 100
                if self.stats['total_queries'] > 0 else 0
            ),
            'average_time': (
                self.stats['total_time'] / self.stats['total_queries']
                if self.stats['total_queries'] > 0 else 0
            )
        }

# 测试函数
def test_neodata_collector():
    """测试NeoData数据采集器"""
    print("测试NeoData贵金属数据采集器...")
    
    collector = NeoDataPreciousMetalsCollector()
    
    # 测试获取黄金价格
    print("\n1. 获取黄金现货价格:")
    gold_price = collector.get_price('XAUUSD')
    if gold_price:
        print(f"   价格: ${gold_price.price:.2f}")
        print(f"   涨跌: {gold_price.change:.2f} ({gold_price.change_percent:.2f}%)")
        print(f"   最高: ${gold_price.high:.2f}")
        print(f"   最低: ${gold_price.low:.2f}")
        print(f"   数据源: {gold_price.source}")
    else:
        print("   获取失败")
    
    # 测试获取白银价格
    print("\n2. 获取白银现货价格:")
    silver_price = collector.get_price('XAGUSD')
    if silver_price:
        print(f"   价格: ${silver_price.price:.2f}")
        print(f"   涨跌: {silver_price.change:.2f} ({silver_price.change_percent:.2f}%)")
    else:
        print("   获取失败")
    
    # 测试获取上海金价格
    print("\n3. 获取上海金交所黄金价格:")
    sh_gold_price = collector.get_price('AU9999')
    if sh_gold_price:
        print(f"   价格: ¥{sh_gold_price.price:.2f}")
        print(f"   涨跌: {sh_gold_price.change:.2f} ({sh_gold_price.change_percent:.2f}%)")
    else:
        print("   获取失败")
    
    # 显示统计信息
    print("\n4. 性能统计:")
    stats = collector.get_stats()
    print(f"   总查询次数: {stats['total_queries']}")
    print(f"   成功次数: {stats['successful_queries']}")
    print(f"   失败次数: {stats['failed_queries']}")
    print(f"   成功率: {stats['success_rate']:.1f}%")

if __name__ == '__main__':
    test_neodata_collector()
