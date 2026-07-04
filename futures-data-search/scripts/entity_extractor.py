#!/usr/bin/env python3
"""
实体抽取模块
从用户自然语言输入中提取期货查询实体
"""

import re
import yaml
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

# 配置路径
SKILL_DIR = Path(__file__).parent.parent
VARIETIES_FILE = SKILL_DIR / "references" / "varieties.yaml"


@dataclass
class QueryEntity:
    """查询实体"""
    variety: Optional[str] = None  # 品种代码
    variety_name: Optional[str] = None  # 品种中文名
    contract_type: str = "main"  # main/next_main/index_continuous/specific_month/all
    specific_month: Optional[str] = None  # 具体月份 YYMM
    metrics: List[str] = None  # 查询指标列表
    start_date: Optional[str] = None  # 开始日期
    end_date: Optional[str] = None  # 结束日期
    relative_time: Optional[str] = None  # 相对时间
    exchange: Optional[str] = None  # 交易所
    pair: Optional[str] = None  # 套利品种对
    arb_type: Optional[str] = None  # 套利类型

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = []


class EntityExtractor:
    """实体抽取器"""

    def __init__(self):
        self.varieties = self._load_varieties()
        self._build_patterns()

    def _load_varieties(self) -> Dict[str, Dict[str, Any]]:
        """加载品种词典并构建映射"""
        if not VARIETIES_FILE.exists():
            raise FileNotFoundError(f"品种词典文件不存在: {VARIETIES_FILE}")

        with open(VARIETIES_FILE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        varieties = {}
        for v in data.get('varieties', []):
            code = v['code']
            # 代码映射
            varieties[code.upper()] = v
            # 别名映射
            for alias in v.get('aliases', []):
                varieties[alias] = v

        return varieties

    def _build_patterns(self):
        """构建匹配模式"""
        # 指标关键词映射
        self.metric_keywords = {
            "quote": ["行情", "价格", "报价", "涨跌", "开盘", "收盘", "最高", "最低", "成交量", "K线", "k线"],
            "oi_ranking": ["持仓", "排名", "前20", "前二十", "多空", "净多", "净空", "会员持仓"],
            "warehouse": ["仓单", "注册仓单", "注销仓单", "库存"],
            "delivery": ["交割", "交割日", "最后交易日", "交割预报", "持仓限制"],
            "spread": ["价差", "期限结构", "跨月", "月差", "back", "contango", "backwardation"],
            "arbitrage": ["套利", "螺卷差", "豆棕差", "铜锌比", "比价", "跨品种"],
            "news": ["资讯", "新闻", "公告", "政策", "消息", "动态"]
        }

        # 合约类型关键词
        self.contract_type_keywords = {
            "main": ["主力", "主力连续", "主力合约"],
            "next_main": ["次主力", "次主力合约"],
            "index_continuous": ["指数", "指数连续", "连续"],
            "all": ["全部", "所有合约", "所有"]
        }

        # 相对时间关键词
        self.relative_time_keywords = {
            "latest": ["最新", "今天", "今日", "当日"],
            "today": ["今天", "今日"],
            "last_5_days": ["最近", "近期", "近5日", "近五日", "近一周"],
            "this_month": ["本月", "这个月"],
            "last_month": ["上月", "上个月"]
        }

        # 交易所关键词
        self.exchange_keywords = {
            "SHFE": ["上期所", "上海期货"],
            "DCE": ["大商所", "大连商品"],
            "CZCE": ["郑商所", "郑州商品"],
            "GFEX": ["广期所", "广州期货"],
            "INE": ["上期能源", "能源中心"],
            "CFFEX": ["中金所", "中国金融"]
        }

        # 套利品种对
        self.arb_pairs = {
            "螺卷差": "RB-HC",
            "豆棕差": "M-P",
            "铜锌比": "CU-ZN",
            "油粕比": "Y-M",
            "焦煤焦炭比": "JM-J"
        }

    def extract(self, user_input: str) -> QueryEntity:
        """
        从用户输入中抽取实体

        Args:
            user_input: 用户输入文本

        Returns:
            抽取的实体
        """
        entity = QueryEntity()
        text = user_input.strip()

        # 1. 提取品种
        variety, variety_name = self._extract_variety(text)
        entity.variety = variety
        entity.variety_name = variety_name

        # 2. 提取合约类型
        entity.contract_type = self._extract_contract_type(text)

        # 3. 提取具体月份
        specific_month = self._extract_specific_month(text)
        if specific_month:
            entity.contract_type = "specific_month"
            entity.specific_month = specific_month

        # 4. 提取指标类型
        entity.metrics = self._extract_metrics(text)

        # 5. 提取时间范围
        entity.relative_time = self._extract_relative_time(text)
        entity.start_date, entity.end_date = self._extract_date_range(text)

        # 6. 提取交易所
        entity.exchange = self._extract_exchange(text)

        # 7. 提取套利信息
        entity.pair, entity.arb_type = self._extract_arbitrage(text)

        return entity

    def _extract_variety(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """提取品种信息"""
        # 按长度排序，优先匹配长的别名
        sorted_keys = sorted(self.varieties.keys(), key=len, reverse=True)

        for key in sorted_keys:
            if key in text:
                v = self.varieties[key]
                return v['code'], v['name']

        # 尝试正则匹配合约代码（如 CU2609）
        match = re.search(r'([A-Z]{1,3})\d{4}', text, re.IGNORECASE)
        if match:
            code = match.group(1).upper()
            if code in self.varieties:
                v = self.varieties[code]
                return v['code'], v['name']

        return None, None

    def _extract_contract_type(self, text: str) -> str:
        """提取合约类型"""
        for ctype, keywords in self.contract_type_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return ctype
        return "main"  # 默认主力

    def _extract_specific_month(self, text: str) -> Optional[str]:
        """提取具体月份"""
        # 匹配 YYMM 格式，如 2609、09
        match = re.search(r'(\d{2})(0[1-9]|1[0-2])\b', text)
        if match:
            return match.group(0)

        # 匹配中文格式，如 "9月"、"09月"
        match = re.search(r'(\d{1,2})月', text)
        if match:
            month = int(match.group(1))
            if 1 <= month <= 12:
                # 推断年份（当前年或下一年）
                from datetime import datetime
                now = datetime.now()
                year = now.year % 100
                if month < now.month:
                    year += 1
                return f"{year:02d}{month:02d}"

        return None

    def _extract_metrics(self, text: str) -> List[str]:
        """提取指标类型"""
        metrics = []
        for metric, keywords in self.metric_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    if metric not in metrics:
                        metrics.append(metric)
                    break

        # 如果没有匹配到任何指标，默认根据上下文推断
        if not metrics:
            metrics = ["quote"]  # 默认行情

        return metrics

    def _extract_relative_time(self, text: str) -> Optional[str]:
        """提取相对时间"""
        for time_type, keywords in self.relative_time_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return time_type
        return None

    def _extract_date_range(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """提取日期范围"""
        # 匹配 YYYY-MM-DD 格式
        dates = re.findall(r'(\d{4})-(\d{2})-(\d{2})', text)
        if len(dates) >= 2:
            return f"{dates[0][0]}-{dates[0][1]}-{dates[0][2]}", f"{dates[1][0]}-{dates[1][1]}-{dates[1][2]}"
        elif len(dates) == 1:
            return f"{dates[0][0]}-{dates[0][1]}-{dates[0][2]}", None

        # 匹配 MM-DD 格式
        dates = re.findall(r'(\d{2})-(\d{2})', text)
        if len(dates) >= 2:
            from datetime import datetime
            year = datetime.now().year
            return f"{year}-{dates[0][0]}-{dates[0][1]}", f"{year}-{dates[1][0]}-{dates[1][1]}"

        return None, None

    def _extract_exchange(self, text: str) -> Optional[str]:
        """提取交易所"""
        for exchange, keywords in self.exchange_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return exchange
        return None

    def _extract_arbitrage(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """提取套利信息"""
        # 匹配预定义的套利对
        for name, pair in self.arb_pairs.items():
            if name in text:
                # 判断是价差还是比价
                if "比" in name or "比价" in text:
                    return pair, "ratio"
                else:
                    return pair, "price_diff"

        # 匹配自定义格式，如 RB-HC
        match = re.search(r'([A-Z]{1,3})-([A-Z]{1,3})', text, re.IGNORECASE)
        if match:
            pair = f"{match.group(1).upper()}-{match.group(2).upper()}"
            if "比" in text:
                return pair, "ratio"
            else:
                return pair, "price_diff"

        return None, None

    def select_tools(self, entity: QueryEntity) -> List[Dict[str, Any]]:
        """
        根据实体选择要调用的工具

        Args:
            entity: 查询实体

        Returns:
            工具调用列表
        """
        tools = []

        # 如果是套利查询
        if entity.pair:
            tools.append({
                "tool": "futures-arbitrage",
                "params": {
                    "pair": entity.pair,
                    "type": entity.arb_type or "price_diff"
                }
            })
            return tools

        # 根据指标类型选择工具
        for metric in entity.metrics:
            if metric == "quote":
                tools.append({
                    "tool": "futures-quote",
                    "params": {
                        "variety": entity.variety,
                        "contract_type": entity.contract_type,
                        "specific_month": entity.specific_month,
                        "start_date": entity.start_date,
                        "end_date": entity.end_date
                    }
                })
            elif metric == "oi_ranking":
                tools.append({
                    "tool": "futures-oi-ranking",
                    "params": {
                        "variety": entity.variety,
                        "contract_type": entity.contract_type,
                        "specific_month": entity.specific_month
                    }
                })
            elif metric == "warehouse":
                tools.append({
                    "tool": "futures-warehouse",
                    "params": {
                        "variety": entity.variety
                    }
                })
            elif metric == "delivery":
                tools.append({
                    "tool": "futures-delivery",
                    "params": {
                        "variety": entity.variety,
                        "delivery_month": entity.specific_month
                    }
                })
            elif metric == "spread":
                tools.append({
                    "tool": "futures-spread",
                    "params": {
                        "variety": entity.variety,
                        "type": "term_structure"
                    }
                })
            elif metric == "news":
                tools.append({
                    "tool": "futures-news",
                    "params": {
                        "variety": entity.variety
                    }
                })

        # 如果需要合约列表
        if entity.contract_type == "all" or "合约" in str(entity.metrics):
            tools.append({
                "tool": "futures-contracts",
                "params": {
                    "variety": entity.variety
                }
            })

        return tools


def main():
    """测试函数"""
    extractor = EntityExtractor()

    test_cases = [
        "铜今天行情",
        "铁矿石主力前20持仓",
        "铜的仓单和交割信息",
        "螺卷差多少",
        "豆粕近期走势",
        "CU2609价格",
        "上期所铜合约列表",
    ]

    for case in test_cases:
        print(f"\n输入: {case}")
        entity = extractor.extract(case)
        print(f"  品种: {entity.variety} ({entity.variety_name})")
        print(f"  合约类型: {entity.contract_type}")
        print(f"  指标: {entity.metrics}")
        print(f"  时间: {entity.relative_time or entity.start_date}")
        print(f"  交易所: {entity.exchange}")

        tools = extractor.select_tools(entity)
        print(f"  工具: {[t['tool'] for t in tools]}")


if __name__ == "__main__":
    main()
