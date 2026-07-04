#!/usr/bin/env python3
"""
futures-data-search 数据获取脚本
用于从各交易所获取期货行情、持仓、仓单等数据
"""

import json
import yaml
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

# 配置路径
SKILL_DIR = Path(__file__).parent.parent
VARIETIES_FILE = SKILL_DIR / "references" / "varieties.yaml"
DOMINANT_MAP_DIR = SKILL_DIR / "data" / "dominant_maps"


class FuturesDataFetcher:
    """期货数据获取器"""

    def __init__(self):
        self.varieties = self._load_varieties()
        self.dominant_map = self._load_latest_dominant_map()

    def _load_varieties(self) -> Dict[str, Any]:
        """加载品种词典"""
        if not VARIETIES_FILE.exists():
            raise FileNotFoundError(f"品种词典文件不存在: {VARIETIES_FILE}")

        with open(VARIETIES_FILE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # 构建别名映射
        varieties = {}
        for v in data.get('varieties', []):
            code = v['code']
            varieties[code] = v
            # 添加别名映射
            for alias in v.get('aliases', []):
                varieties[alias] = v

        return varieties

    def _load_latest_dominant_map(self) -> Dict[str, Any]:
        """加载最新的主力映射表"""
        if not DOMINANT_MAP_DIR.exists():
            DOMINANT_MAP_DIR.mkdir(parents=True, exist_ok=True)
            return {}

        # 查找最新的映射文件
        map_files = sorted(DOMINANT_MAP_DIR.glob("dominant_map_*.json"), reverse=True)
        if not map_files:
            return {}

        with open(map_files[0], 'r', encoding='utf-8') as f:
            return json.load(f)

    def resolve_variety(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        解析用户输入的品种名称，返回标准品种信息

        Args:
            user_input: 用户输入的品种名称（中文或代码）

        Returns:
            品种信息字典，包含 code, exchange, name 等
        """
        # 直接匹配代码
        if user_input.upper() in self.varieties:
            return self.varieties[user_input.upper()]

        # 匹配中文别名
        if user_input in self.varieties:
            return self.varieties[user_input]

        # 模糊匹配
        for key, value in self.varieties.items():
            if user_input in key or user_input in value.get('name', ''):
                return value

        return None

    def get_contract_tag(self, variety_code: str, contract_code: str) -> str:
        """
        获取合约标签（主力/次主力/具体月份）

        Args:
            variety_code: 品种代码
            contract_code: 合约代码

        Returns:
            合约标签字符串
        """
        if not self.dominant_map or variety_code not in self.dominant_map:
            return contract_code

        mapping = self.dominant_map[variety_code]

        if contract_code == mapping.get('main'):
            return f"主力({contract_code})"
        elif contract_code == mapping.get('next_main'):
            return f"次主力({contract_code})"
        elif contract_code == mapping.get('index'):
            return f"指数连续({variety_code})"
        else:
            return contract_code

    def fetch_quote(
        self,
        variety: str,
        contract_type: str = "main",
        specific_month: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "1d",
        adjusted: bool = True
    ) -> List[Dict[str, Any]]:
        """
        获取期货行情数据（真实数据源：AKShare futures_hist_em）
        """
        records = []

        # 尝试从 exchange DuckDB 读取（优先级最高）
        try:
            from duckdb_store import DuckDBStore
            db = DuckDBStore()
            if start_date and end_date:
                rows = db.conn.execute(f"""
                    SELECT trade_date, open, high, low, close, volume, open_interest
                    FROM exchange_futures_data.futures_data
                    WHERE variety = ? AND trade_date BETWEEN ? AND ?
                    ORDER BY trade_date
                """, [variety, start_date, end_date]).fetchdf()
            else:
                rows = db.conn.execute(f"""
                    SELECT trade_date, open, high, low, close, volume, open_interest
                    FROM exchange_futures_data.futures_data
                    WHERE variety = ? ORDER BY trade_date DESC LIMIT 60
                """, [variety]).fetchdf()
            if len(rows) > 0:
                for _, r in rows.iterrows():
                    records.append({
                        "date": str(r['trade_date']),
                        "open": float(r['open']), "high": float(r['high']),
                        "low": float(r['low']), "close": float(r['close']),
                        "volume": int(r['volume']), "open_interest": int(r['open_interest']),
                        "data_source": "exchange_api", "confidence": 1.0,
                    })
                return records
        except Exception:
            pass

        # 降级：AKShare futures_hist_em
        try:
            import akshare as ak
            symbol_map = {
                'CU': 'CU888', 'AL': 'AL888', 'ZN': 'ZN888', 'PB': 'PB888',
                'NI': 'NI888', 'SN': 'SN888', 'AU': 'AU888', 'AG': 'AG888',
                'RB': 'RB888', 'HC': 'HC888', 'SS': 'SS888', 'RU': 'RU888',
                'I': 'I888', 'J': 'J888', 'JM': 'JM888',
                'M': 'M888', 'Y': 'Y888', 'P': 'P888',
                'CF': 'CF888', 'SR': 'SR888', 'TA': 'TA888', 'MA': 'MA888',
                'FG': 'FG888', 'SA': 'SA888',
            }
            symbol = symbol_map.get(variety.upper(), f"{variety.upper()}888")
            df = ak.futures_hist_em(symbol=symbol, period=period, start_date=start_date or "20260601",
                                     end_date=end_date or datetime.now().strftime('%Y%m%d'), adjust='1' if adjusted else '0')
            if df is not None and len(df) > 0:
                for _, r in df.iterrows():
                    records.append({
                        "date": str(r.get('日期', '')),
                        "open": float(r.get('开盘价', 0)),
                        "high": float(r.get('最高价', 0)),
                        "low": float(r.get('最低价', 0)),
                        "close": float(r.get('收盘价', 0)),
                        "volume": int(r.get('成交量', 0)),
                        "open_interest": int(r.get('持仓量', 0)),
                        "data_source": "AKShare", "confidence": 0.85,
                    })
        except Exception as e:
            print(f"[Warning] AKShare quote error: {e}")

        return records

    def fetch_contracts(self, variety: str) -> List[Dict[str, Any]]:
        """
        获取品种下所有上市合约列表（真实数据源：AKShare）
        """
        contracts = []
        exchange_info = self.varieties.get(variety.upper(), {})
        exchange = exchange_info.get('exchange', '')

        try:
            import akshare as ak
            exchange_map = {
                'SHFE': ak.futures_contract_info_shfe,
                'DCE': ak.futures_contract_info_dce,
                'CZCE': ak.futures_contract_info_czce,
                'GFEX': ak.futures_contract_info_gfex,
                'INE': ak.futures_contract_info_ine,
                'CFFEX': ak.futures_contract_info_cffex,
            }
            if exchange in exchange_map:
                df = exchange_map[exchange]()
                if df is not None and len(df) > 0:
                    # 按品种代码过滤
                    variety_col = [c for c in df.columns if '代码' in c or 'symbol' in c.lower() or 'product' in c.lower()]
                    if variety_col:
                        filtered = df[df[variety_col[0]].str.startswith(variety.upper())]
                        for _, r in filtered.iterrows():
                            code = str(r.get(variety_col[0], ''))
                            contracts.append({
                                "contract": code,
                                "name": str(r.get(df.columns[1], '')),
                                "tag": self.get_contract_tag(variety.upper(), code),
                            })
        except Exception as e:
            print(f"[Warning] Contracts error: {e}")

        if not contracts:
            # 兜底：返回主力信息
            contracts.append({
                "contract": f"{variety.upper()}888",
                "name": f"{variety.upper()}主力连续",
                "tag": "主力(888)"
            })

        return contracts

    def _exchange_for_variety(self, variety: str) -> str:
        """获取品种对应的交易所代码"""
        info = self.varieties.get(variety.upper(), {})
        return info.get('exchange', '')

    def fetch_oi_ranking(
        self,
        variety: str,
        contract_type: str = "main",
        specific_month: Optional[str] = None,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取前20会员持仓排名（真实数据源：AKShare 交易所排名API）
        """
        exchange = self._exchange_for_variety(variety)
        result = {"variety": variety, "exchange": exchange, "date": date or "latest",
                   "long": [], "short": [], "net_position": 0, "source": "AKShare"}

        try:
            import akshare as ak
            rank_map = {
                'SHFE': lambda: getattr(ak, 'get_shfe_rank_table')(),
                'DCE': lambda: getattr(ak, 'get_dce_rank_table')(),
                'CZCE': lambda: getattr(ak, 'get_rank_table_czce')(),
                'CFFEX': lambda: getattr(ak, 'get_cffex_rank_table')(),
                'GFEX': lambda: ak.futures_gfex_position_rank(symbol=variety),
            }
            if exchange in rank_map:
                df = rank_map[exchange]()
                if df is not None and len(df) > 0:
                    # 过滤品种
                    symbol_col = [c for c in df.columns if any(k in c for k in ['合约', '品种', 'symbol', 'code'])]
                    if symbol_col:
                        df = df[df[symbol_col[0]].astype(str).str.contains(variety.upper(), na=False)]

                    # 提取多头/空头
                    for direction, label in [('long', '多'), ('short', '空')]:
                        member_col = [c for c in df.columns if '会员' in c or '席位' in c or 'member' in c.lower()]
                        lots_col = [c for c in df.columns if direction in c.lower() or f'{label}' in c]
                        rank_col = [c for c in df.columns if '排名' in c or 'rank' in c.lower()]

                        if member_col and lots_col:
                            for i in range(min(20, len(df))):
                                row = df.iloc[i]
                                result[direction].append({
                                    "rank": i + 1,
                                    "member": str(row.get(member_col[0], '')),
                                    "lots": int(row.get(lots_col[0], 0)),
                                })

                    # 净持仓
                    long_total = sum(r['lots'] for r in result['long'])
                    short_total = sum(r['lots'] for r in result['short'])
                    result['net_position'] = long_total - short_total
                    result['source'] = f"{exchange}官方API"
        except Exception as e:
            print(f"[Warning] OI ranking error for {variety}: {e}")

        return result

    def fetch_warehouse(
        self,
        variety: str,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取仓单日报数据（真实数据源：AKShare 仓单API）
        """
        exchange = self._exchange_for_variety(variety)
        result = {"variety": variety, "exchange": exchange, "date": date or "latest",
                   "registered": 0, "cancelled": 0, "net_change": 0, "details": [], "source": "AKShare"}

        try:
            import akshare as ak
            wh_map = {
                'SHFE': lambda: ak.futures_shfe_warehouse_receipt(date=date),
                'DCE': lambda: ak.futures_warehouse_receipt_dce(date=date),
                'CZCE': lambda: ak.futures_warehouse_receipt_czce(date=date),
                'GFEX': lambda: ak.futures_gfex_warehouse_receipt(date=date),
            }
            if exchange in wh_map:
                df = wh_map[exchange]()
                if df is not None and len(df) > 0:
                    # 过滤品种
                    variety_col = [c for c in df.columns if any(k in c for k in ['品种', '商品', 'code'])]
                    if variety_col:
                        df = df[df[variety_col[0]].astype(str).str.contains(variety.upper(), na=False)]

                    if len(df) > 0:
                        row = df.iloc[0]
                        result['registered'] = int(row.get(df.columns[2], 0)) if len(df.columns) > 2 else 0
                        result['cancelled'] = int(row.get(df.columns[3], 0)) if len(df.columns) > 3 else 0
                        result['net_change'] = result['registered'] - result['cancelled']
                        result['date'] = str(row.get(df.columns[0], ''))
                        result['source'] = f"{exchange}仓单API"
        except Exception as e:
            print(f"[Warning] Warehouse error for {variety}: {e}")

        return result

    def fetch_delivery(
        self,
        variety: str,
        delivery_month: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取交割信息（真实数据源：AKShare 交割API）
        """
        exchange = self._exchange_for_variety(variety)
        result = {"variety": variety, "exchange": exchange, "delivery_month": delivery_month or "",
                   "data": [], "source": "AKShare"}

        try:
            import akshare as ak
            delivery_map = {
                'SHFE': lambda: ak.futures_delivery_shfe(date=delivery_month),
                'DCE': lambda: ak.futures_delivery_dce(symbol=variety),
                'CZCE': lambda: ak.futures_delivery_czce(symbol=variety),
            }
            if exchange in delivery_map:
                df = delivery_map[exchange]()
                if df is not None and len(df) > 0:
                    for _, r in df.head(10).iterrows():
                        result['data'].append({str(k): str(v) for k, v in r.items()})
        except Exception as e:
            print(f"[Warning] Delivery error for {variety}: {e}")

        return result

    def fetch_spread(
        self,
        variety: str,
        spread_type: str = "term_structure",
        month1: Optional[str] = None,
        month2: Optional[str] = None,
        date: Optional[str] = None
    ) -> Any:
        """
        获取跨月价差/期限结构（真实数据源：AKShare + DuckDB）
        """
        if spread_type == "term_structure":
            # 从 DuckDB 交易所数据读取期限结构
            try:
                from duckdb_store import DuckDBStore
                db = DuckDBStore()
                rows = db.get_term_structure(variety, trade_date=date)
                if rows:
                    return rows
            except Exception:
                pass

            # 降级：从AKShare获取主力+次主力价格
            try:
                import akshare as ak
                import pandas as pd
                today = date or datetime.now().strftime('%Y%m%d')
                main_contract = ak.futures_display_main_sina()
                if main_contract is not None and variety.upper() in main_contract.values:
                    df = ak.futures_hist_em(symbol=f"{variety.upper()}888", period="1d",
                                             start_date=today, end_date=today, adjust='1')
                    if df is not None and len(df) > 0:
                        return [{"contract": f"{variety.upper()}主力", "price": float(df.iloc[-1]['收盘价'])}]
            except Exception as e:
                print(f"[Warning] Spread error: {e}")

            return []

        # calendar_spread: 获取两合约价差
        if month1 and month2:
            try:
                import akshare as ak
                df1 = ak.futures_hist_em(symbol=f"{variety.upper()}{month1}", period="1d",
                                          start_date=date or "20260601", end_date=date or datetime.now().strftime('%Y%m%d'), adjust='1')
                df2 = ak.futures_hist_em(symbol=f"{variety.upper()}{month2}", period="1d",
                                          start_date=date or "20260601", end_date=date or datetime.now().strftime('%Y%m%d'), adjust='1')
                if df1 is not None and df2 is not None and len(df1) > 0 and len(df2) > 0:
                    p1 = float(df1.iloc[-1]['收盘价'])
                    p2 = float(df2.iloc[-1]['收盘价'])
                    return {"pair": f"{variety}{month1}-{variety}{month2}", "spread": round(p1 - p2, 2),
                            "near_price": p1, "far_price": p2, "source": "AKShare"}
            except Exception as e:
                print(f"[Warning] Calendar spread error: {e}")

        return {}

    def fetch_arbitrage(
        self,
        pair: str,
        arb_type: str = "price_diff",
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取跨品种套利数据（真实数据源：AKShare两个品种分别取价格）
        """
        result = {"pair": pair, "type": arb_type, "value": 0, "source": "AKShare"}

        try:
            v1, v2 = pair.split('-')
            import akshare as ak
            today = date or datetime.now().strftime('%Y%m%d')

            df1 = ak.futures_hist_em(symbol=f"{v1.upper()}888", period="1d", start_date=today, end_date=today, adjust='1')
            df2 = ak.futures_hist_em(symbol=f"{v2.upper()}888", period="1d", start_date=today, end_date=today, adjust='1')

            if df1 is not None and df2 is not None and len(df1) > 0 and len(df2) > 0:
                p1 = float(df1.iloc[-1]['收盘价'])
                p2 = float(df2.iloc[-1]['收盘价'])
                if arb_type == "price_diff":
                    result['value'] = round(p1 - p2, 2)
                else:
                    result['value'] = round(p1 / p2, 4) if p2 != 0 else 0
        except Exception as e:
            print(f"[Warning] Arbitrage error: {e}")

        return result

    def fetch_news(
        self,
        variety: str,
        category: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取产业资讯（真实数据源：AKShare + DuckDB缓存）
        """
        news_list = []

        # 1. 从DuckDB缓存读取
        try:
            from duckdb_store import DuckDBStore
            db = DuckDBStore()
            cached = db.get_latest_news(variety, top_k=top_k)
            if cached:
                return cached
        except Exception:
            pass

        # 2. AKShare 期货新闻
        try:
            import akshare as ak
            df = ak.futures_news_shmet()
            if df is not None and len(df) > 0:
                for _, r in df.head(top_k).iterrows():
                    title = str(r.get('title', r.get(df.columns[1], '')))
                    news_list.append({
                        "title": title,
                        "date": str(r.get('date', r.get(df.columns[0], ''))),
                        "source": "上海有色网",
                        "summary": title[:100],
                        "sentiment": "neutral",
                    })
        except Exception as e:
            print(f"[Info] AKShare news not available: {e}")

        # 3. AI自动标注sentiment（简单关键词匹配）
        bullish_kw = ['涨', '增', '扩', '利好', '加', '升', '突破', '放量']
        bearish_kw = ['跌', '减', '缩', '利空', '降', '限', '破位', '萎缩']
        for item in news_list:
            title = item.get('title', '')
            if any(k in title for k in bullish_kw):
                item['sentiment'] = 'bullish'
            elif any(k in title for k in bearish_kw):
                item['sentiment'] = 'bearish'

        # 4. 缓存到DuckDB
        if news_list:
            try:
                from duckdb_store import DuckDBStore
                db = DuckDBStore()
                db.save_news([(
                    hash(item['title']), datetime.now().date(), variety,
                    item['title'], item['source'], '',
                    item['summary'], item['sentiment']
                ) for item in news_list])
            except Exception:
                pass

        return news_list[:top_k]


def main():
    """CLI入口: python fetch_futures_data.py sp rb lc PX al"""
    import sys
    if len(sys.argv) > 1:
        targets = sys.argv[1:]
    else:
        targets = ["sp", "rb", "lc", "PX", "al"]
    
    import akshare as ak
    import pandas as pd
    import numpy as np
    from datetime import datetime
    
    print(f"futures-data-search — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"数据源: AKShare (盘后 MultiSourceAdapter 退化为降级)")
    print(f"品种: {', '.join(targets)}")
    print()
    
    for pid in targets:
        try:
            symbol = f"{pid.lower()}0"
            df = ak.futures_main_sina(symbol=symbol)
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            close = df['收盘价'].astype(float).values
            high = df['最高价'].astype(float).values
            low = df['最低价'].astype(float).values
            vol = df['成交量'].astype(float).values
            oi = df['持仓量'].astype(float).values
            n = len(close)
            
            if n < 20:
                print(f"  {pid}: 数据不足({n}条)")
                continue
            
            print(f"  {pid} | {last['日期']} O={last['开盘价']:.0f} H={last['最高价']:.0f} "
                  f"L={last['最低价']:.0f} C={last['收盘价']:.0f} "
                  f"V={last['成交量']:.0f} OI={last['持仓量']:.0f}")
            
            # Basic indicators (pure numpy, no external deps)
            def sma(x,p): return pd.Series(x).rolling(p).mean().values
            ma5,ma10,ma20 = sma(close,5),sma(close,10),sma(close,20)
            tp=(high+low+close)/3
            cci20=(tp-sma(tp,20))/(0.015*pd.Series(tp).rolling(20).apply(
                lambda x:np.mean(np.abs(x-np.mean(x))),raw=True).values)
            delta=close-np.roll(close,1);g=np.clip(delta,0,None);l=np.clip(-delta,0,None)
            rsi=100-100/(1+sma(g,14)[-1]/sma(l,14)[-1]) if sma(l,14)[-1]>0 else 100
            oi_chg=(oi[-1]/oi[-6]-1)*100 if oi[-6]>0 else 0
            
            print(f"    MA5={ma5[-1]:.0f} MA10={ma10[-1]:.0f} MA20={ma20[-1]:.0f} "
                  f"排列={'多头' if ma5[-1]>ma10[-1]>ma20[-1] else '空头' if ma5[-1]<ma10[-1]<ma20[-1] else '交叉'}")
            print(f"    RSI14={rsi:.1f}  CCI20={cci20[-1]:.0f}  "
                  f"OI5d={oi_chg:+.1f}%  20日涨跌={(close[-1]/close[-21]-1)*100:+.1f}%")
            print()
        except Exception as e:
            print(f"  {pid}: 查询失败 — {e}\n")


if __name__ == "__main__":
    main()
