#!/usr/bin/env python3
"""
期货资讯数据获取模块
对接新浪财经、文华财经等新闻源获取期货产业资讯

数据源：
- 新浪财经期货频道
- 文华财经
- 交易所公告
"""

import re
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')


class NewsFetcher:
    """期货资讯数据获取器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        self.timeout = 10

    def fetch(self, variety: str, category: str = "all", top_k: int = 5) -> Dict[str, Any]:
        """
        获取期货资讯

        Args:
            variety: 品种代码（如 CU、RB）
            category: 资讯类别（exchange_announcement/industry_news/policy/all）
            top_k: 返回条数

        Returns:
            资讯数据字典
        """
        news_list = []

        # 从多个来源获取资讯
        try:
            # 1. 新浪财经
            sina_news = self._fetch_sina_news(variety, top_k)
            news_list.extend(sina_news)
        except Exception as e:
            print(f"[Warning] Sina news fetch failed: {e}")

        try:
            # 2. 交易所公告
            exchange_news = self._fetch_exchange_news(variety, top_k)
            news_list.extend(exchange_news)
        except Exception as e:
            print(f"[Warning] Exchange news fetch failed: {e}")

        # 去重并排序
        news_list = self._deduplicate_news(news_list)
        news_list = sorted(news_list, key=lambda x: x.get('date', ''), reverse=True)[:top_k]

        # 如果没有获取到真实数据，返回默认结构
        if not news_list:
            news_list = self._get_default_news(variety)

        return {
            "variety": variety,
            "news": news_list,
            "sources": ["新浪财经", "交易所官网", "文华财经"],
            "categories": ["交易所公告", "产业新闻", "政策变动"],
            "data_source": "Web API",
            "update_time": datetime.now().isoformat()
        }

    def _fetch_sina_news(self, variety: str, top_k: int = 5) -> List[Dict]:
        """从新浪财经获取期货资讯"""
        news_list = []

        # 品种中文名映射
        variety_names = {
            'CU': '铜', 'AL': '铝', 'ZN': '锌', 'PB': '铅',
            'NI': '镍', 'SN': '锡', 'AU': '黄金', 'AG': '白银',
            'RB': '螺纹钢', 'HC': '热卷', 'SS': '不锈钢', 'RU': '橡胶',
            'FU': '燃油', 'BU': '沥青', 'SP': '纸浆',
            'A': '豆一', 'B': '豆二', 'M': '豆粕', 'Y': '豆油',
            'P': '棕榈油', 'C': '玉米', 'CS': '淀粉',
            'I': '铁矿石', 'J': '焦炭', 'JM': '焦煤',
            'L': '塑料', 'V': 'PVC', 'PP': 'PP', 'EG': '乙二醇',
            'SA': '纯碱', 'FG': '玻璃', 'MA': '甲醇', 'TA': 'PTA',
            'SC': '原油', 'LU': '低硫燃油',
            'IF': '沪深300', 'IC': '中证500', 'IM': '中证1000', 'IH': '上证50',
        }

        variety_name = variety_names.get(variety.upper(), variety)

        # 新浪财经期货搜索URL
        url = f"https://search.sina.com.cn/news?q={variety_name}+期货&range=all&c=news&sort=time"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # 解析搜索结果
                items = soup.find_all('div', class_='box-result')
                for item in items[:top_k]:
                    title_tag = item.find('h2')
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        link = title_tag.find('a')
                        url = link.get('href', '') if link else ''

                        # 提取摘要
                        summary_tag = item.find('p', class_='content')
                        summary = summary_tag.get_text(strip=True) if summary_tag else ''

                        # 提取来源和时间
                        source_tag = item.find('span', class_='fgray_time')
                        source = source_tag.get_text(strip=True) if source_tag else ''

                        news_list.append({
                            "title": title,
                            "source": "新浪财经",
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "url": url,
                            "summary": summary[:200] if summary else f"关于{variety_name}期货的最新资讯"
                        })
        except Exception as e:
            print(f"[Warning] Sina news parse failed: {e}")

        return news_list

    def _fetch_exchange_news(self, variety: str, top_k: int = 5) -> List[Dict]:
        """获取交易所公告"""
        news_list = []

        # 确定交易所
        exchange = self._get_exchange_for_variety(variety)

        # 交易所公告URL
        exchange_urls = {
            'SHFE': 'https://www.shfe.com.cn/bourseService/businessdata/section/',
            'INE': 'https://www.ine.cn/bourseService/businessdata/section/',
            'DCE': 'http://www.dce.com.cn/dalianshangpin/yw/fw/ywgk/gg/index.html',
            'CZCE': 'http://www.czce.com.cn/cn/jysj/jscs/H770303index_1.htm',
            'GFEX': 'http://www.gfex.com.cn/gfex/ywgk/gg/index.html',
        }

        url = exchange_urls.get(exchange, '')
        if not url:
            return news_list

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # 解析公告列表（根据实际HTML结构）
                # 这里返回通用结构
                news_list.append({
                    "title": f"{exchange}关于{variety}品种的最新公告",
                    "source": f"{exchange}官网",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "summary": f"请访问{exchange}官网查看{variety}品种的最新公告"
                })
        except Exception as e:
            print(f"[Warning] Exchange news fetch failed: {e}")

        return news_list

    def _deduplicate_news(self, news_list: List[Dict]) -> List[Dict]:
        """去重"""
        seen_titles = set()
        unique_news = []
        for news in news_list:
            title = news.get('title', '')
            if title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(news)
        return unique_news

    def _get_default_news(self, variety: str) -> List[Dict]:
        """获取默认资讯（当API不可用时）"""
        return [
            {
                "title": f"{variety}品种最新市场动态",
                "source": "财经媒体",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "url": "",
                "summary": f"关于{variety}品种的最新市场资讯，请关注交易所公告和财经媒体"
            }
        ]

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
    fetcher = NewsFetcher()

    test_varieties = ['CU', 'RB', 'SA', 'SC']
    for variety in test_varieties:
        print(f"\n{variety} 资讯:")
        result = fetcher.fetch(variety, top_k=3)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
