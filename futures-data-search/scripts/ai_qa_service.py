#!/usr/bin/env python3
"""
AI 金融问答服务 v2.0
面向 LLM Agent 的自然语言接口

改进：
- 完整的价差查询支持（含历史值）
- 仓单、资讯数据对接
- 更智能的未知品种拒绝
"""

import json
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

# 导入本地模块（仅导入核心轻量模块；网络/数据库相关模块在 property 中延迟导入）
import sys
sys.path.insert(0, str(Path(__file__).parent))

from nl2fql_engine import NL2FQLEngine, FQLQuery, QueryType
from rule_engine import FinancialRuleEngine
from multi_source_adapter import MultiSourceAdapter


class AIQAService:
    """AI 金融问答服务"""

    def __init__(self):
        """初始化服务（轻量，不触发网络/数据库连接）"""
        self.nl2fql = NL2FQLEngine()
        self.rule_engine = FinancialRuleEngine()
        self.conversation_history = []
        self._query_cache = {}  # 内存查询缓存

        # 以下适配器延迟初始化（避免构造函数阻塞）
        self._data_adapter = None
        self._multi_source = None
        self._db = None
        self._warehouse_fetcher = None
        self._news_fetcher = None
        self._overseas_fetcher = None
        self._intraday_fetcher = None

    @property
    def data_adapter(self):
        if self._data_adapter is None:
            from data_adapter import FuturesDataAdapter
            self._data_adapter = FuturesDataAdapter()
        return self._data_adapter

    @property
    def multi_source(self):
        if self._multi_source is None:
            self._multi_source = MultiSourceAdapter()
        return self._multi_source

    @property
    def db(self):
        if self._db is None:
            from duckdb_store import DuckDBStore
            self._db = DuckDBStore()
        return self._db

    @property
    def warehouse_fetcher(self):
        if self._warehouse_fetcher is None:
            from warehouse_fetcher import WarehouseFetcher
            self._warehouse_fetcher = WarehouseFetcher()
        return self._warehouse_fetcher

    @property
    def news_fetcher(self):
        if self._news_fetcher is None:
            from news_fetcher import NewsFetcher
            self._news_fetcher = NewsFetcher()
        return self._news_fetcher

    @property
    def overseas_fetcher(self):
        if self._overseas_fetcher is None:
            from overseas_data_fetcher import OverseasDataFetcher
            self._overseas_fetcher = OverseasDataFetcher()
        return self._overseas_fetcher

    @property
    def intraday_fetcher(self):
        if self._intraday_fetcher is None:
            from intraday_data_fetcher import IntradayDataFetcher
            self._intraday_fetcher = IntradayDataFetcher(use_tqsdk=True)
        return self._intraday_fetcher

    def query(self, question: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        处理自然语言查询

        Args:
            question: 自然语言问题
            context: 上下文信息（可选）

        Returns:
            查询结果
        """
        start_time = datetime.now()

        # 1. 解析自然语言
        fql = self.nl2fql.parse(question)

        # 2. 检查是否有解析错误（如未知品种）
        if fql.parse_errors:
            return {
                "success": False,
                "error": fql.parse_errors[0],
                "data": [],
                "query_type": fql.query_type.value,
                "metadata": {
                    "fql": fql.to_dict(),
                    "execution_time_ms": 0
                }
            }

        # 3. 搜索相似历史查询（基于DuckDB query_cache）
        similar_queries = []
        try:
            cached = self.db.get_cached("query", question, ttl_hours=24*7)
            if cached:
                similar_queries = cached[:3]
        except Exception:
            pass

        # 4. 执行查询
        result = self._execute_query(fql)

        # 5. 数据校验
        if result.get("data"):
            validation_results = []
            data = result["data"]
            if isinstance(data, list):
                for record in data[:5]:
                    if isinstance(record, dict):
                        validation = self.rule_engine.validate_quote(record)
                        validation_results.extend(validation)
            elif isinstance(data, dict):
                validation = self.rule_engine.validate_quote(data)
                validation_results.extend(validation)
            result["validation"] = [
                {"rule": r.rule_name, "level": r.level.value, "passed": r.passed, "message": r.message}
                for r in validation_results
            ]

        # 6. 计算执行时间
        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        # 7. 存储查询记录到缓存
        try:
            self.db.set_cached("query", question, {
                "query_id": hashlib.md5(question.encode()).hexdigest()[:16],
                "query_text": question,
                "query_type": fql.query_type.value if fql else "",
                "success": result.get("success", False),
                "timestamp": datetime.now().isoformat(),
            }, ttl_hours=24*7)
        except Exception:
            pass

        # 8. 更新对话历史
        self.conversation_history.append({
            "role": "user",
            "content": question,
            "timestamp": datetime.now().isoformat()
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": result,
            "timestamp": datetime.now().isoformat()
        })

        # 9. 添加元数据
        result["metadata"] = {
            "query_id": hashlib.md5(question.encode()).hexdigest()[:16],
            "fql": fql.to_dict(),
            "execution_time_ms": execution_time,
            "similar_queries": [
                {"text": q.get("query_text", ""), "type": q.get("query_type", "")}
                for q in similar_queries
            ]
        }

        return result

    def _execute_query(self, fql: FQLQuery) -> Dict[str, Any]:
        """执行 FQL 查询"""
        try:
            if fql.query_type == QueryType.QUOTE:
                return self._execute_quote_query(fql)
            elif fql.query_type == QueryType.SPREAD:
                return self._execute_spread_query(fql)
            elif fql.query_type == QueryType.OI_RANKING:
                return self._execute_oi_query(fql)
            elif fql.query_type == QueryType.WAREHOUSE:
                return self._execute_warehouse_query(fql)
            elif fql.query_type == QueryType.TERM_STRUCTURE:
                return self._execute_term_structure_query(fql)
            elif fql.query_type == QueryType.NEWS:
                return self._execute_news_query(fql)
            else:
                return self._execute_quote_query(fql)
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    def _execute_quote_query(self, fql: FQLQuery) -> Dict[str, Any]:
        """执行行情查询（带多源降级）"""
        if not fql.varieties:
            return {"success": False, "error": "未识别到品种", "data": []}

        variety = fql.varieties[0]
        start_date = fql.start_date
        end_date = fql.end_date or start_date

        # 检查是否为境外品种
        if self._is_overseas_variety(variety):
            return self._execute_overseas_quote(variety)

        # 检查是否需要分钟级数据
        if fql.filters.get('period') in ['1m', '5m', '15m', '30m', '60m']:
            return self._execute_intraday_quote(variety, fql.filters['period'])

        # 使用多源数据适配器（带自动降级）
        result = self.multi_source.get_quote(
            variety=variety,
            contract_type=fql.contract_types[0] if fql.contract_types else "main",
            start_date=start_date,
            end_date=end_date
        )

        # 如果多源适配器失败，回退到原始适配器
        if not result.get('success'):
            quotes = self.data_adapter.get_quote(
                variety=variety,
                contract_type=fql.contract_types[0] if fql.contract_types else "main",
                start_date=start_date,
                end_date=end_date
            )
            return {
                "success": True,
                "data": quotes,
                "query_type": "quote",
                "variety": variety,
                "count": len(quotes),
                "data_source": "exchange_api",
            }

        return {
            "success": True,
            "data": result.get('data', []),
            "query_type": "quote",
            "variety": variety,
            "count": len(result.get('data', [])),
            "data_source": result.get('data_source'),
            "confidence": result.get('confidence'),
        }

    def _is_overseas_variety(self, variety: str) -> bool:
        """检查是否为境外品种"""
        overseas_varieties = [
            'GC', 'SI', 'HG',  # COMEX
            'CL', 'NG', 'HO', 'RB',  # NYMEX
            'B',  # ICE
            'ZS', 'ZC', 'ZW', 'ZM', 'ZL',  # CBOT
            'ES', 'NQ', 'YM', 'NKD',  # CME
            'CA', 'AH', 'NI', 'ZN', 'PB', 'SN',  # LME
        ]
        return variety.upper() in overseas_varieties

    def _execute_overseas_quote(self, variety: str) -> Dict[str, Any]:
        """执行境外期货行情查询"""
        result = self.overseas_fetcher.fetch(variety)

        if result.get('close'):
            return {
                "success": True,
                "data": [result],
                "query_type": "quote",
                "variety": variety,
                "count": 1,
                "is_overseas": True,
            }
        else:
            return {
                "success": False,
                "error": result.get('error', '境外数据获取失败'),
                "data": [],
                "query_type": "quote",
            }

    def _execute_intraday_quote(self, variety: str, period: str) -> Dict[str, Any]:
        """执行分钟级行情查询"""
        result = self.intraday_fetcher.fetch(variety, period=period, count=100)

        if result.get('data'):
            return {
                "success": True,
                "data": result['data'],
                "query_type": "intraday",
                "variety": variety,
                "period": period,
                "count": result.get('count', 0),
                "data_source": result.get('data_source'),
                "is_trading_hour": result.get('is_trading_hour'),
            }
        else:
            return {
                "success": False,
                "error": result.get('error', '分钟级数据获取失败'),
                "data": [],
                "query_type": "intraday",
            }

    def _execute_spread_query(self, fql: FQLQuery) -> Dict[str, Any]:
        """执行价差查询（含历史值）"""
        if not fql.spread_pair:
            return {"success": False, "error": "未识别到价差对", "data": []}

        variety1, variety2 = fql.spread_pair

        # 获取最近5个交易日的数据
        today = datetime.now()
        start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        # 获取两个品种的行情
        quotes1 = self.data_adapter.get_quote(variety1, start_date=start_date, end_date=end_date)
        quotes2 = self.data_adapter.get_quote(variety2, start_date=start_date, end_date=end_date)

        if quotes1 and quotes2:
            # 计算当前价差
            current_spread = quotes1[0].get("close", 0) - quotes2[0].get("close", 0)

            # 计算历史价差（最近5天）
            history_5d = []
            for i in range(min(5, len(quotes1), len(quotes2))):
                spread = quotes1[i].get("close", 0) - quotes2[i].get("close", 0)
                history_5d.append(spread)

            # 计算 Z-Score
            import numpy as np
            if len(history_5d) >= 2:
                mean = np.mean(history_5d)
                std = np.std(history_5d)
                z_score = (current_spread - mean) / std if std > 0 else 0
            else:
                z_score = 0

            return {
                "success": True,
                "data": {
                    "pair": f"{variety1}-{variety2}",
                    "type": "price_diff",
                    "value": current_spread,
                    "history_5d": history_5d,
                    "z_score": round(z_score, 2),
                    "variety1": {
                        "code": variety1,
                        "close": quotes1[0].get("close", 0),
                        "date": quotes1[0].get("date", "")
                    },
                    "variety2": {
                        "code": variety2,
                        "close": quotes2[0].get("close", 0),
                        "date": quotes2[0].get("date", "")
                    },
                    "source": f"{self._get_exchange_for_variety(variety1)} + {self._get_exchange_for_variety(variety2)}"
                },
                "query_type": "spread"
            }

        return {"success": False, "error": "无法获取价差数据", "data": []}

    def _execute_oi_query(self, fql: FQLQuery) -> Dict[str, Any]:
        """执行持仓查询"""
        if not fql.varieties:
            return {"success": False, "error": "未识别到品种", "data": []}

        variety = fql.varieties[0]
        oi_data = self.data_adapter.get_oi_ranking(variety)

        return {
            "success": True,
            "data": oi_data,
            "query_type": "oi_ranking",
            "variety": variety
        }

    def _execute_warehouse_query(self, fql: FQLQuery) -> Dict[str, Any]:
        """执行仓单查询"""
        if not fql.varieties:
            return {"success": False, "error": "未识别到品种", "data": []}

        variety = fql.varieties[0]

        # 从交易所官网获取仓单数据
        # 当前返回模拟数据，实际应对接交易所API
        warehouse_data = self._fetch_warehouse_data(variety)

        return {
            "success": True,
            "data": warehouse_data,
            "query_type": "warehouse",
            "variety": variety
        }

    def _fetch_warehouse_data(self, variety: str) -> Dict[str, Any]:
        """
        获取仓单数据
        
        对接交易所官网API获取真实数据
        """
        return self.warehouse_fetcher.fetch(variety)

    def _execute_term_structure_query(self, fql: FQLQuery) -> Dict[str, Any]:
        """执行期限结构查询"""
        if not fql.varieties:
            return {"success": False, "error": "未识别到品种", "data": []}

        variety = fql.varieties[0]

        # 获取所有合约数据
        contracts = self.data_adapter.get_contracts(variety)

        if contracts:
            # 按合约月份排序
            contracts.sort(key=lambda x: x.get('contract', ''))

            # 计算较主力升贴水
            main_price = None
            for c in contracts:
                if c.get('tag') == '主力':
                    main_price = c.get('close', 0)
                    break

            if main_price:
                for c in contracts:
                    c['premium_to_main'] = c.get('close', 0) - main_price

            return {
                "success": True,
                "data": {
                    "variety": variety,
                    "contracts": contracts,
                    "main_price": main_price
                },
                "query_type": "term_structure",
                "variety": variety
            }

        return {
            "success": False,
            "error": "无法获取期限结构数据",
            "data": [],
            "query_type": "term_structure"
        }

    def _execute_news_query(self, fql: FQLQuery) -> Dict[str, Any]:
        """执行资讯查询"""
        if not fql.varieties:
            return {"success": False, "error": "未识别到品种", "data": []}

        variety = fql.varieties[0]

        # 从新闻源获取资讯数据
        news_data = self._fetch_news_data(variety)

        return {
            "success": True,
            "data": news_data,
            "query_type": "news",
            "variety": variety
        }

    def _fetch_news_data(self, variety: str, top_k: int = 5) -> Dict[str, Any]:
        """
        获取资讯数据
        
        对接新浪财经、交易所公告等获取真实数据
        """
        return self.news_fetcher.fetch(variety, top_k=top_k)

    def batch_query(self, questions: List[str]) -> List[Dict[str, Any]]:
        """
        批量查询

        Args:
            questions: 问题列表

        Returns:
            结果列表
        """
        results = []
        for question in questions:
            result = self.query(question)
            results.append(result)
        return results

    def get_conversation_history(self, limit: int = 10) -> List[Dict]:
        """获取对话历史"""
        return self.conversation_history[-limit * 2:]

    def clear_conversation(self):
        """清空对话历史"""
        self.conversation_history = []

    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "nl2fql": {
                "available": True,
                "variety_count": len(self.nl2fql.variety_aliases)
            },
            "data_adapter": {
                "available": self.data_adapter.collector is not None,
                "latest_trading_day": self.data_adapter.get_latest_trading_day() if self.data_adapter.collector else None
            },
            "rule_engine": {
                "available": True,
                "contract_types": len(self.rule_engine.CONTRACT_UNITS)
            },
            "db_cache": {
                "available": self.db is not None,
                "type": "DuckDB"
            },
            "conversation_turns": len(self.conversation_history) // 2
        }

    def format_response(self, result: Dict, format_type: str = "text") -> str:
        """
        格式化响应

        Args:
            result: 查询结果
            format_type: 格式类型 (text/markdown/json)

        Returns:
            格式化后的文本
        """
        if format_type == "json":
            return json.dumps(result, ensure_ascii=False, indent=2)

        if not result.get("success"):
            return f"查询失败: {result.get('error', '未知错误')}"

        data = result.get("data", [])
        query_type = result.get("query_type", "")

        if format_type == "markdown":
            return self._format_markdown(data, query_type, result)
        else:
            return self._format_text(data, query_type, result)

    def _format_text(self, data: Any, query_type: str, result: Dict) -> str:
        """纯文本格式"""
        if not data:
            return "未查询到数据"

        # 数据来源标注
        source_info = self._get_source_info(result)

        if query_type == "quote":
            if isinstance(data, list) and len(data) > 0:
                quote = data[0]
                return (
                    f"{result.get('variety', '')} 行情（{quote.get('contract_tag', '主力')}）:\n"
                    f"  日期: {quote.get('date', 'N/A')}\n"
                    f"  开盘: {quote.get('open', 'N/A')}\n"
                    f"  收盘: {quote.get('close', 'N/A')}\n"
                    f"  最高: {quote.get('high', 'N/A')}\n"
                    f"  最低: {quote.get('low', 'N/A')}\n"
                    f"  成交量: {quote.get('volume', 'N/A'):,}\n"
                    f"  持仓量: {quote.get('oi', 'N/A'):,}\n"
                    f"\n{source_info}"
                )
        elif query_type == "spread":
            if isinstance(data, dict):
                history_str = ", ".join([str(v) for v in data.get('history_5d', [])])
                return (
                    f"价差分析: {data.get('pair', '')}\n"
                    f"  当前价差: {data.get('value', 'N/A')}\n"
                    f"  Z-Score: {data.get('z_score', 'N/A')}\n"
                    f"  近5日历史: [{history_str}]\n"
                    f"  {data.get('variety1', {}).get('code', '')}: {data.get('variety1', {}).get('close', 'N/A')}\n"
                    f"  {data.get('variety2', {}).get('code', '')}: {data.get('variety2', {}).get('close', 'N/A')}\n"
                    f"\n{source_info}"
                )
        elif query_type == "warehouse":
            if isinstance(data, dict):
                details_str = "\n".join([
                    f"    {d.get('warehouse', '')}: {d.get('lots', 0):,} 手"
                    for d in data.get('details', [])
                ])
                return (
                    f"仓单信息: {data.get('variety', '')}\n"
                    f"  日期: {data.get('date', 'N/A')}\n"
                    f"  注册仓单: {data.get('registered', 0):,} 手\n"
                    f"  注销仓单: {data.get('cancelled', 0):,} 手\n"
                    f"  净变化: {data.get('net_change', 0):+,} 手\n"
                    f"  分仓库明细:\n{details_str}\n"
                    f"\n{source_info}"
                )
        elif query_type == "term_structure":
            if isinstance(data, dict):
                contracts = data.get('contracts', [])
                lines = [f"期限结构: {data.get('variety', '')}"]
                for c in contracts[:5]:
                    lines.append(f"  {c.get('contract', '')}: {c.get('close', 'N/A')} (升贴水: {c.get('premium_to_main', 'N/A')})")
                lines.append(f"\n{source_info}")
                return "\n".join(lines)
        elif query_type == "news":
            if isinstance(data, dict):
                news_items = data.get('news', [])
                news_str = "\n".join([
                    f"  [{n.get('date', '')}] {n.get('title', '')}\n    来源: {n.get('source', '')}\n    摘要: {n.get('summary', '')}"
                    for n in news_items
                ])
                return (
                    f"资讯信息: {data.get('variety', '')}\n"
                    f"{news_str}\n"
                    f"\n{source_info}"
                )

        return json.dumps(data, ensure_ascii=False, indent=2)

    def _get_source_info(self, result: Dict) -> str:
        """获取数据来源信息"""
        metadata = result.get('metadata', {})
        fql = metadata.get('fql', {})

        data = result.get('data', [])
        if isinstance(data, list) and len(data) > 0:
            first_record = data[0]
            date = first_record.get('date', '')
            exchange = self._get_exchange_for_variety(fql.get('varieties', [''])[0] if fql.get('varieties') else '')
            return f"数据来源: {exchange} {date} 盘后"
        elif isinstance(data, dict):
            date = data.get('date', data.get('trade_date', ''))
            exchange = self._get_exchange_for_variety(data.get('variety', ''))
            return f"数据来源: {exchange} {date} 盘后"

        return "数据来源: 交易所官方API"

    def _get_exchange_for_variety(self, variety: str) -> str:
        """获取品种所属交易所"""
        exchange_map = {
            'CU': '上期所', 'AL': '上期所', 'ZN': '上期所', 'PB': '上期所',
            'NI': '上期所', 'SN': '上期所', 'AU': '上期所', 'AG': '上期所',
            'RB': '上期所', 'HC': '上期所', 'SS': '上期所', 'RU': '上期所',
            'BR': '上期所', 'FU': '上期所', 'BU': '上期所', 'WR': '上期所',
            'SP': '上期所', 'AO': '上期所',
            'A': '大商所', 'B': '大商所', 'M': '大商所', 'Y': '大商所',
            'P': '大商所', 'C': '大商所', 'CS': '大商所', 'I': '大商所',
            'J': '大商所', 'JM': '大商所', 'L': '大商所', 'V': '大商所',
            'PP': '大商所', 'EG': '大商所', 'EB': '大商所', 'PG': '大商所',
            'JD': '大商所', 'LH': '大商所', 'RR': '大商所',
            'AP': '郑商所', 'CF': '郑商所', 'CY': '郑商所', 'CJ': '郑商所',
            'FG': '郑商所', 'SA': '郑商所', 'SH': '郑商所', 'MA': '郑商所',
            'TA': '郑商所', 'UR': '郑商所', 'PF': '郑商所', 'PK': '郑商所',
            'OI': '郑商所', 'RM': '郑商所', 'RS': '郑商所', 'SR': '郑商所',
            'WH': '郑商所', 'PM': '郑商所', 'SM': '郑商所', 'SF': '郑商所',
            'ZC': '郑商所', 'JR': '郑商所', 'LR': '郑商所', 'RI': '郑商所',
            'SI': '广期所', 'LC': '广期所', 'PS': '广期所',
            'SC': '上期能源', 'LU': '上期能源', 'NR': '上期能源', 'BC': '上期能源',
            'IF': '中金所', 'IC': '中金所', 'IM': '中金所', 'IH': '中金所',
            'T': '中金所', 'TF': '中金所', 'TS': '中金所', 'TL': '中金所',
        }
        return exchange_map.get(variety.upper(), '交易所')

    def _format_markdown(self, data: Any, query_type: str, result: Dict) -> str:
        """Markdown 格式"""
        if not data:
            return "未查询到数据"

        if query_type == "quote":
            if isinstance(data, list) and len(data) > 0:
                quote = data[0]
                return (
                    f"## {result.get('variety', '')} 行情\n\n"
                    f"| 指标 | 值 |\n|------|-----|\n"
                    f"| 收盘价 | {quote.get('close', 'N/A')} |\n"
                    f"| 成交量 | {quote.get('volume', 'N/A'):,} |\n"
                    f"| 持仓量 | {quote.get('oi', 'N/A'):,} |\n"
                )
        elif query_type == "spread":
            if isinstance(data, dict):
                return (
                    f"## 价差分析: {data.get('pair', '')}\n\n"
                    f"| 指标 | 值 |\n|------|------|\n"
                    f"| 当前价差 | {data.get('value', 'N/A')} |\n"
                    f"| Z-Score | {data.get('z_score', 'N/A')} |\n"
                    f"| {data.get('variety1', {}).get('code', '')} | {data.get('variety1', {}).get('close', 'N/A')} |\n"
                    f"| {data.get('variety2', {}).get('code', '')} | {data.get('variety2', {}).get('close', 'N/A')} |\n"
                )

        return f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"


def main():
    """测试函数"""
    print("AI QA Service Test")
    print("=" * 50)

    service = AIQAService()

    # 获取服务状态
    status = service.get_service_status()
    print(f"Service Status: {json.dumps(status, indent=2, ensure_ascii=False)}")

    # 测试查询
    test_queries = [
        "铜今天行情",
        "螺纹钢最新价格",
        "螺卷差",
        "纯碱仓单",
        "铜今天有什么新闻",
        "铜锌合金行情",  # 应该拒绝
        "XYZ行情",  # 应该拒绝
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        result = service.query(query)
        print(f"Result: {service.format_response(result, 'text')}")


if __name__ == "__main__":
    main()
