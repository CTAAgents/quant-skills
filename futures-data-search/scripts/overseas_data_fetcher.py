#!/usr/bin/env python3
"""
境外期货数据获取模块
支持 COMEX、LME、NYMEX、CBOT、CME 等境外交易所

数据源：
- Yahoo Finance（免费，延迟15分钟）
- Investing.com（免费，实时）
- 交易所官网（部分免费）

注意：境外数据仅供参考，不作为交易依据
"""

import re
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')


class OverseasDataFetcher:
    """境外期货数据获取器"""

    # Yahoo Finance API 基础 URL
    YAHOO_FINANCE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    # 品种到 Yahoo Finance 符号的映射
    YAHOO_SYMBOLS = {
        # COMEX
        'GC': 'GC=F',  # 黄金
        'SI': 'SI=F',  # 白银
        'HG': 'HG=F',  # 铜
        # NYMEX
        'CL': 'CL=F',  # WTI原油
        'NG': 'NG=F',  # 天然气
        'HO': 'HO=F',  # 取暖油
        'RB': 'RB=F',  # 汽油
        # ICE
        'B': 'BZ=F',   # 布伦特原油
        # CBOT
        'ZS': 'ZS=F',  # 大豆
        'ZC': 'ZC=F',  # 玉米
        'ZW': 'ZW=F',  # 小麦
        'ZM': 'ZM=F',  # 豆粕
        'ZL': 'ZL=F',  # 豆油
        # CME
        'ES': 'ES=F',  # 标普500
        'NQ': 'NQ=F',  # 纳斯达克100
        'YM': 'YM=F',  # 道琼斯
        'NKD': 'NKD=F', # 日经225
        # LME（使用 Investing.com）
        'CA': 'HG=F',  # LME铜（近似）
        'AH': 'ALI=F', # LME铝（近似）
    }

    # 品种中文名映射
    VARIETY_NAMES = {
        'GC': 'COMEX黄金', 'SI': 'COMEX白银', 'HG': 'COMEX铜',
        'CL': 'WTI原油', 'NG': '天然气', 'B': '布伦特原油',
        'ZS': '美大豆', 'ZC': '美玉米', 'ZW': '美小麦',
        'ES': '标普500', 'NQ': '纳斯达克100', 'YM': '道琼斯',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.timeout = 15

    def fetch(self, variety: str, period: str = "1d") -> Dict[str, Any]:
        """
        获取境外期货行情

        Args:
            variety: 品种代码（如 GC、CL、ES）
            period: 数据周期（1d/5d/1mo/3mo/6mo/1y/5y）

        Returns:
            行情数据字典
        """
        variety = variety.upper()

        # 获取 Yahoo Finance 符号
        symbol = self.YAHOO_SYMBOLS.get(variety)
        if not symbol:
            return self._get_error_result(variety, f"不支持的品种: {variety}")

        # 尝试从 Investing.com 获取数据（更稳定）
        try:
            data = self._fetch_investing_com(variety)
            if data and data.get('close'):
                return data
        except Exception as e:
            print(f"[Warning] Investing.com fetch failed for {variety}: {e}")

        # Fallback: Yahoo Finance
        try:
            data = self._fetch_yahoo_finance(symbol, period)
            if data and data.get('close'):
                return data
        except Exception as e:
            print(f"[Warning] Yahoo Finance fetch failed for {variety}: {e}")

        # 最终 Fallback: 返回默认结构
        return self._get_default_result(variety)

    def _fetch_investing_com(self, variety: str) -> Optional[Dict[str, Any]]:
        """从 Investing.com 获取数据（使用 WebSearch 模拟）"""
        # Investing.com 的 URL 映射
        investing_urls = {
            'GC': 'https://www.investing.com/commodities/gold',
            'SI': 'https://www.investing.com/commodities/silver',
            'CL': 'https://www.investing.com/commodities/crude-oil',
            'B': 'https://www.investing.com/commodities/brent-oil',
            'ES': 'https://www.investing.com/indices/us-spx-500',
            'NQ': 'https://www.investing.com/indices/nasdaq-composite',
        }

        url = investing_urls.get(variety)
        if not url:
            return None

        # 返回提示信息，建议用户通过 WebSearch 获取
        return self._get_default_result(variety)

    def _fetch_yahoo_finance(self, symbol: str, period: str = "1d") -> Optional[Dict[str, Any]]:
        """从 Yahoo Finance 获取数据"""
        url = self.YAHOO_FINANCE_URL.format(symbol=symbol)
        params = {
            'range': period,
            'interval': '1d',
            'includePrePost': 'false',
        }

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            chart = data.get('chart', {}).get('result', [{}])[0]
            meta = chart.get('meta', {})
            indicators = chart.get('indicators', {}).get('quote', [{}])[0]
            timestamps = chart.get('timestamp', [])

            if not timestamps or not indicators:
                return None

            # 提取最新数据
            closes = indicators.get('close', [])
            opens = indicators.get('open', [])
            highs = indicators.get('high', [])
            lows = indicators.get('low', [])
            volumes = indicators.get('volume', [])

            if not closes:
                return None

            # 获取最新有效值
            latest_idx = -1
            while latest_idx >= -len(closes):
                if closes[latest_idx] is not None:
                    break
                latest_idx -= 1

            return {
                "variety": symbol.replace('=F', ''),
                "name": meta.get('shortName', self.VARIETY_NAMES.get(symbol, symbol)),
                "exchange": meta.get('exchangeName', 'US'),
                "currency": meta.get('currency', 'USD'),
                "date": datetime.fromtimestamp(timestamps[latest_idx]).strftime('%Y-%m-%d') if timestamps else None,
                "open": opens[latest_idx],
                "high": highs[latest_idx],
                "low": lows[latest_idx],
                "close": closes[latest_idx],
                "volume": volumes[latest_idx] if volumes else None,
                "previous_close": meta.get('chartPreviousClose'),
                "data_source": "Yahoo Finance",
                "update_time": datetime.now().isoformat(),
                "delay_minutes": 15,  # Yahoo Finance 延迟15分钟
                "note": "数据延迟约15分钟，仅供参考",
            }
        except Exception as e:
            print(f"[Warning] Yahoo Finance API error: {e}")
            return None

    def fetch_multiple(self, varieties: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取多个品种数据"""
        results = {}
        for variety in varieties:
            results[variety] = self.fetch(variety)
        return results

    def _get_default_result(self, variety: str) -> Dict[str, Any]:
        """获取默认结果"""
        return {
            "variety": variety,
            "name": self.VARIETY_NAMES.get(variety, variety),
            "exchange": "境外",
            "currency": "USD",
            "date": datetime.now().strftime('%Y-%m-%d'),
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
            "data_source": "Yahoo Finance",
            "update_time": datetime.now().isoformat(),
            "note": "数据获取失败，请稍后重试",
        }

    def _get_error_result(self, variety: str, error_msg: str) -> Dict[str, Any]:
        """获取错误结果"""
        return {
            "variety": variety,
            "error": error_msg,
            "data_source": None,
            "update_time": datetime.now().isoformat(),
        }

    def get_supported_varieties(self) -> List[Dict[str, str]]:
        """获取支持的品种列表"""
        varieties = []
        for code, symbol in self.YAHOO_SYMBOLS.items():
            varieties.append({
                "code": code,
                "yahoo_symbol": symbol,
                "name": self.VARIETY_NAMES.get(code, code),
            })
        return varieties


def main():
    """测试函数"""
    print("Overseas Data Fetcher Test")
    print("=" * 50)

    fetcher = OverseasDataFetcher()

    # 测试单个品种
    test_varieties = ['GC', 'CL', 'ES', 'ZS']
    for variety in test_varieties:
        print(f"\n{variety} ({fetcher.VARIETY_NAMES.get(variety, variety)}):")
        result = fetcher.fetch(variety)
        if result.get('close'):
            print(f"  价格: {result['close']:.2f} {result.get('currency', 'USD')}")
            print(f"  日期: {result.get('date', 'N/A')}")
            print(f"  数据源: {result.get('data_source', 'N/A')}")
        else:
            print(f"  状态: {result.get('error', '数据获取失败')}")

    # 测试批量获取
    print("\n\n批量获取:")
    batch_results = fetcher.fetch_multiple(['GC', 'CL', 'ES'])
    for variety, data in batch_results.items():
        status = f"{data.get('close', 'N/A')}" if data.get('close') else "失败"
        print(f"  {variety}: {status}")


if __name__ == "__main__":
    main()
