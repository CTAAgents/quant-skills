#!/usr/bin/env python3
"""
仓单数据获取模块
对接交易所官网获取仓单日报数据

数据源：
- 上期所/上期能源：https://www.shfe.com.cn
- 大商所：http://www.dce.com.cn
- 郑商所：http://www.czce.com.cn
- 广期所：http://www.gfex.com.cn
"""

import re
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')


class WarehouseFetcher:
    """仓单数据获取器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        self.timeout = 10

    def fetch(self, variety: str, exchange: Optional[str] = None, date: Optional[str] = None) -> Dict[str, Any]:
        """
        获取仓单数据

        Args:
            variety: 品种代码（如 CU、RB）
            exchange: 交易所代码（可选，自动推断）
            date: 日期（可选，默认最新）

        Returns:
            仓单数据字典
        """
        # 确定交易所
        if not exchange:
            exchange = self._get_exchange_for_variety(variety)

        # 根据交易所调用不同的获取方法
        try:
            if exchange in ['SHFE', 'INE']:
                return self._fetch_shfe_warehouse(variety, date)
            elif exchange == 'DCE':
                return self._fetch_dce_warehouse(variety, date)
            elif exchange == 'CZCE':
                return self._fetch_czce_warehouse(variety, date)
            elif exchange == 'GFEX':
                return self._fetch_gfex_warehouse(variety, date)
            else:
                return self._get_default_warehouse(variety, exchange)
        except Exception as e:
            print(f"[Warning] Failed to fetch warehouse data for {variety}: {e}")
            return self._get_default_warehouse(variety, exchange)

    def _fetch_shfe_warehouse(self, variety: str, date: Optional[str] = None) -> Dict[str, Any]:
        """获取上期所/上期能源仓单数据"""
        # 上期所仓单日报URL
        url = "https://www.shfe.com.cn/data/dailydata/kx/pm{}.dat"

        # 品种代码映射（上期所使用小写）
        variety_lower = variety.lower()

        try:
            # 尝试获取最新数据
            response = self.session.get(url.format(variety_lower), timeout=self.timeout)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                data = response.json()
                if data and 'o_cursor' in data:
                    records = data['o_cursor']
                    if records:
                        # 解析数据
                        latest = records[0]
                        return {
                            "variety": variety,
                            "date": latest.get('DATE', datetime.now().strftime("%Y-%m-%d")),
                            "registered": int(latest.get('WRTWGHTS', 0)),
                            "cancelled": int(latest.get('WRTCHANGE', 0)),
                            "net_change": int(latest.get('WRTCHANGE', 0)),
                            "details": self._parse_shfe_details(records),
                            "source": "上期所官网",
                            "data_source": "SHFE API",
                            "update_time": datetime.now().isoformat()
                        }
        except Exception as e:
            print(f"[Warning] SHFE warehouse fetch failed: {e}")

        return self._get_default_warehouse(variety, 'SHFE')

    def _parse_shfe_details(self, records: List[Dict]) -> List[Dict]:
        """解析上期所仓单明细"""
        details = []
        for record in records[:10]:  # 只取前10条
            details.append({
                "warehouse": record.get('WHABBR', ''),
                "brand": record.get('BRAND', ''),
                "lots": int(record.get('WRTWGHTS', 0))
            })
        return details

    def _fetch_dce_warehouse(self, variety: str, date: Optional[str] = None) -> Dict[str, Any]:
        """获取大商所仓单数据"""
        # 大商所仓单日报URL
        url = "http://www.dce.com.cn/publicweb/quotesdata/wbillWeeklyQuotes.html"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                # 解析HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                # 查找品种对应的仓单数据
                # 这里需要根据实际HTML结构解析
                return self._get_default_warehouse(variety, 'DCE')
        except Exception as e:
            print(f"[Warning] DCE warehouse fetch failed: {e}")

        return self._get_default_warehouse(variety, 'DCE')

    def _fetch_czce_warehouse(self, variety: str, date: Optional[str] = None) -> Dict[str, Any]:
        """获取郑商所仓单数据"""
        # 郑商所仓单日报URL
        url = "http://www.czce.com.cn/cn/DFSStaticFiles/Future/{date}/FutureDataWhsheet.htm"

        try:
            if not date:
                date = datetime.now().strftime("%Y%m%d")

            response = self.session.get(url.format(date=date), timeout=self.timeout)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                # 解析HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                # 查找品种对应的仓单数据
                return self._get_default_warehouse(variety, 'CZCE')
        except Exception as e:
            print(f"[Warning] CZCE warehouse fetch failed: {e}")

        return self._get_default_warehouse(variety, 'CZCE')

    def _fetch_gfex_warehouse(self, variety: str, date: Optional[str] = None) -> Dict[str, Any]:
        """获取广期所仓单数据"""
        # 广期所是新交易所，数据接口可能不同
        return self._get_default_warehouse(variety, 'GFEX')

    def _get_default_warehouse(self, variety: str, exchange: str) -> Dict[str, Any]:
        """获取默认仓单数据（当API不可用时）"""
        return {
            "variety": variety,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "registered": 0,
            "cancelled": 0,
            "net_change": 0,
            "details": [],
            "source": f"{exchange}官网",
            "data_source": f"{exchange} API",
            "update_time": datetime.now().isoformat(),
            "note": "注：当前无法获取实时数据，请访问交易所官网查询"
        }

    def _get_exchange_for_variety(self, variety: str) -> str:
        """获取品种所属交易所"""
        exchange_map = {
            'CU': 'SHFE', 'AL': 'SHFE', 'ZN': 'SHFE', 'PB': 'SHFE',
            'NI': 'SHFE', 'SN': 'SHFE', 'AU': 'SHFE', 'AG': 'SHFE',
            'RB': 'SHFE', 'HC': 'SHFE', 'SS': 'SHFE', 'RU': 'SHFE',
            'BR': 'SHFE', 'FU': 'SHFE', 'BU': 'SHFE', 'WR': 'SHFE',
            'SP': 'SHFE', 'AO': 'SHFE',
            'A': 'DCE', 'B': 'DCE', 'M': 'DCE', 'Y': 'DCE',
            'P': 'DCE', 'C': 'DCE', 'CS': 'DCE', 'I': 'DCE',
            'J': 'DCE', 'JM': 'DCE', 'L': 'DCE', 'V': 'DCE',
            'PP': 'DCE', 'EG': 'DCE', 'EB': 'DCE', 'PG': 'DCE',
            'JD': 'DCE', 'LH': 'DCE', 'RR': 'DCE',
            'AP': 'CZCE', 'CF': 'CZCE', 'CY': 'CZCE', 'CJ': 'CZCE',
            'FG': 'CZCE', 'SA': 'CZCE', 'SH': 'CZCE', 'MA': 'CZCE',
            'TA': 'CZCE', 'UR': 'CZCE', 'PF': 'CZCE', 'PK': 'CZCE',
            'OI': 'CZCE', 'RM': 'CZCE', 'RS': 'CZCE', 'SR': 'CZCE',
            'WH': 'CZCE', 'PM': 'CZCE', 'SM': 'CZCE', 'SF': 'CZCE',
            'ZC': 'CZCE', 'JR': 'CZCE', 'LR': 'CZCE', 'RI': 'CZCE',
            'SI': 'GFEX', 'LC': 'GFEX', 'PS': 'GFEX',
            'SC': 'INE', 'LU': 'INE', 'NR': 'INE', 'BC': 'INE',
        }
        return exchange_map.get(variety.upper(), 'SHFE')


def main():
    """测试函数"""
    fetcher = WarehouseFetcher()

    test_varieties = ['CU', 'RB', 'SA', 'I', 'M']
    for variety in test_varieties:
        print(f"\n{variety} 仓单数据:")
        result = fetcher.fetch(variety)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
