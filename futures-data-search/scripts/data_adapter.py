#!/usr/bin/env python3
"""
futures-data-search 数据适配器
集成 exchange-futures-data 技能的数据获取能力

v2.2 (2026-06-28) - 新增长尾品种补录流
  - TqSdk 直连交易所行情（主流数据源不覆盖的品种）
  - WebSearch 降级试探（TqSdk 不可用时）
  - 品种状态标记：active / low_liquidity / policy_frozen / delisted
"""

import sys
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd

# 添加 exchange_data_collector 路径（已合并入 futures-data-search）
EXCHANGE_DATA_SKILL = Path.home() / ".workbuddy" / "skills" / "futures-data-search" / "collectors" / "exchange_data" / "scripts"
if str(EXCHANGE_DATA_SKILL) not in sys.path:
    sys.path.insert(0, str(EXCHANGE_DATA_SKILL))

# 导入 exchange_data_collector
try:
    from exchange_data_collector import ExchangeDataCollector
    EXCHANGE_DATA_AVAILABLE = True
except ImportError as e:
    print(f"[Warning] exchange-data-collector not available: {e}")
    EXCHANGE_DATA_AVAILABLE = False

# 长尾品种补录：TqSdk（数据源白名单之外的品种可通过它直连交易所）
# TqSdk 需要快期账户 auth，从环境变量读取。
# 环境变量: TQSDK_USERNAME (或 TQ_USER), TQSDK_PASSWORD (或 TQ_PASSWORD)
# ⚠️ 警告：tqsdk 导入（即使是 from xxx import）可能触发网络连接导致永久阻塞。
# 此处不直接导入，而是通过 _lazy_tqsdk_api() 按需导入，带线程超时保护。
_TQ_USER = os.environ.get('TQSDK_USERNAME') or os.environ.get('TQ_USER', '')
_TQ_PASS = os.environ.get('TQSDK_PASSWORD') or os.environ.get('TQ_PASSWORD', '')
_TQ_AUTH = (_TQ_USER, _TQ_PASS) if _TQ_USER and _TQ_PASS else None

TQSDK_USABLE = False
TQSDK_AVAILABLE = False
_TQ_AUTH_OBJ = None
_tqsdk_import_result = [None, None]  # [TqApi_class, TqAuth_class]

def _lazy_tqsdk_api():
    """
    按需导入 tqsdk 并建立连接。
    使用线程超时保护，防止 tqsdk 的 WebSocket 初始化永久阻塞。

    Returns:
        (TqApi, TqAuth) 或 (None, None)
    """
    global TQSDK_AVAILABLE, TQSDK_USABLE, _TQ_AUTH_OBJ
    if TQSDK_AVAILABLE:
        return (_tqsdk_import_result[0], _tqsdk_import_result[1])

    if not _TQ_USER or not _TQ_PASS:
        return (None, None)

    import threading
    tq_result = [None, None]  # [TqApi_class, TqAuth_class]

    def _import_tqsdk():
        try:
            # tqsdk.__init__ 包含免责声明打印和可能的网络初始化
            import tqsdk as _tqmod
            tq_result[0] = getattr(_tqmod, 'TqApi', None)
            tq_result[1] = getattr(_tqmod, 'TqAuth', None)
        except ImportError:
            pass

    t = threading.Thread(target=_import_tqsdk, daemon=True)
    t.start()
    t.join(timeout=20)
    if not t.is_alive() and tq_result[0] and tq_result[1]:
        _tqsdk_import_result[0] = tq_result[0]
        _tqsdk_import_result[1] = tq_result[1]
        TQSDK_AVAILABLE = True
        _TQ_AUTH_OBJ = tq_result[1](_TQ_USER, _TQ_PASS)
        TQSDK_USABLE = True
    return (_tqsdk_import_result[0], _tqsdk_import_result[1])

# 长尾品种补录：通达信TQ-Local（本地HTTP，最高优先级）
TDX_LOCAL_AVAILABLE = False
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "collectors"))
    from tdx_collector import TdxCollector
    TDX_COLLECTOR = TdxCollector()
    TDX_LOCAL_AVAILABLE = TDX_COLLECTOR.is_available
except Exception:
    TDX_COLLECTOR = None

# 长尾品种补录：东方财富（品种级数据补充）
try:
    from eastmoney_collector import EastMoneyCollector
    EASTMONEY_AVAILABLE = True
except ImportError:
    EASTMONEY_AVAILABLE = False

# 品种状态定义
VARIETY_STATUS = {
    # 政策冻结/停产品种
    'ZC': {'status': 'delisted', 'reason': '2022年5月起政策性限制交易，2026年已实质停止交易'},
    # 事实停产品种
    'WR': {'status': 'delisted', 'reason': '多年持仓量 < 100 手，实质无成交'},
    # 冷门品种（数据源不收录，可尝试 TqSdk 直连）
    'BB': {'status': 'low_liquidity', 'reason': '数据源未收录，持仓量极低'},
    'FB': {'status': 'low_liquidity', 'reason': '数据源未收录，持仓量极低'},
    'LG': {'status': 'low_liquidity', 'reason': '数据源未收录，持仓量极低'},
    'CY': {'status': 'low_liquidity', 'reason': '数据源未收录，持仓量极低'},
    'RS': {'status': 'low_liquidity', 'reason': '数据源未收录，持仓量极低'},
    'WH': {'status': 'low_liquidity', 'reason': '数据源未收录，持仓量极低'},
    'PM': {'status': 'low_liquidity', 'reason': '数据源未收录，持仓量极低'},
    'JR': {'status': 'low_liquidity', 'reason': '数据源未收录，持仓量极低'},
    'LR': {'status': 'low_liquidity', 'reason': '数据源未收录，持仓量极低'},
    'RI': {'status': 'low_liquidity', 'reason': '数据源未收录，持仓量极低'},
    # 新品种（数据源尚未收录，但可能有流动性）
    'BR': {'status': 'active', 'reason': '新品种，主要数据源尚未收录'},
    'PT': {'status': 'active', 'reason': '新品种，主要数据源尚未收录'},
    'PD': {'status': 'active', 'reason': '新品种，主要数据源尚未收录'},
    'OP': {'status': 'active', 'reason': '新品种，主要数据源尚未收录'},
    'PR': {'status': 'active', 'reason': '新品种，主要数据源尚未收录'},
    'PX': {'status': 'active', 'reason': '新品种，数据源有数据但品种词典先前未收录'},
    'AD': {'status': 'active', 'reason': '新品种，东方财富可查'},
}


class FuturesDataAdapter:
    """
    期货数据适配器
    对接 exchange-futures-data 技能获取交易所官方数据
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化适配器

        Args:
            db_path: DuckDB 数据库路径，默认使用 exchange-futures-data 的默认路径
        """
        self._cached_df = None
        self._cached_trade_date = None
        self._tq_api = None

        if EXCHANGE_DATA_AVAILABLE:
            # 如果未指定 db_path，使用 exchange-futures-data 的默认路径
            if db_path is None:
                exchange_data_dir = Path.home() / ".workbuddy" / "skills" / "exchange-futures-data" / "data"
                exchange_data_dir.mkdir(parents=True, exist_ok=True)
                db_path = str(exchange_data_dir / "futures_data.duckdb")
            self.collector = ExchangeDataCollector(db_path)
        else:
            self.collector = None
            print("[Warning] ExchangeDataCollector not available, data fetching will be limited")

    def get_quote(
        self,
        variety: str,
        contract_type: str = "main",
        specific_month: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        exchange: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取期货行情数据

        Args:
            variety: 品种代码（如 CU、RB）
            contract_type: 合约类型 (main/next_main/index_continuous/specific_month/all)
            specific_month: 具体月份 YYMM
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            exchange: 交易所代码

        Returns:
            行情数据列表
        """
        if not self.collector:
            return []

        # 确定日期范围
        if not start_date and not end_date:
            # 默认获取最新交易日
            trade_date = self.collector.get_latest_trading_day()
            # trade_date 格式可能是 YYYYMMDD 或 YYYY-MM-DD
            if len(trade_date) == 8 and '-' not in trade_date:
                trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
            start_date = trade_date
            end_date = trade_date
        elif start_date and not end_date:
            end_date = start_date

        # 确保日期格式为 YYYY-MM-DD
        if start_date and len(start_date) == 8 and '-' not in start_date:
            start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        if end_date and len(end_date) == 8 and '-' not in end_date:
            end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

        # 转换日期格式
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # 判断是否为金融期货（中金所）
        cffex_varieties = ['IF', 'IC', 'IM', 'IH', 'T', 'TF', 'TS', 'TL']
        is_financial = variety.upper() in cffex_varieties

        # 优化：根据品种确定交易所，只获取该交易所的数据
        exchange = self._get_exchange_for_variety(variety)

        results = []
        current_dt = start_dt

        while current_dt <= end_dt:
            trade_date = current_dt.strftime("%Y%m%d")

            # 优化：只获取相关交易所的数据
            if exchange:
                # 根据交易所调用对应的方法
                exchange_methods = {
                    'DCE': self.collector.get_dce_daily_data,
                    'SHFE': self.collector.get_shfe_daily_data,
                    'CZCE': self.collector.get_czce_daily_data,
                    'CFFEX': self.collector.get_cffex_daily_data,
                    'GFEX': self.collector.get_gfex_daily_data,
                }
                get_data = exchange_methods.get(exchange)
                if get_data:
                    df = get_data(trade_date, use_cache=True)
                else:
                    df = self.collector.get_all_exchange_data(trade_date, use_cache=True)
            else:
                df = self.collector.get_all_exchange_data(trade_date, use_cache=True)

            if df is not None and len(df) > 0:
                variety_upper = variety.upper()

                if is_financial:
                    # 金融期货：数据库中有具体合约（如 IF2607, IF2608）
                    # 需要精确匹配，避免 T 匹配到 TA
                    import re
                    pattern = f"^{variety_upper}\\d{{4}}$"
                    variety_contracts = df[df['symbol'].str.match(pattern, case=False)].copy()

                    if len(variety_contracts) > 0:
                        # 按成交量排序，找到主力合约
                        variety_contracts = variety_contracts.sort_values('volume', ascending=False)
                        main_contract = variety_contracts.iloc[0]
                        main_symbol = main_contract['symbol']

                        results.append({
                            "date": datetime.strptime(main_contract['trade_date'], "%Y%m%d").strftime("%Y-%m-%d"),
                            "contract_tag": f"主力({main_symbol})",
                            "contract": main_symbol,
                            "open": float(main_contract['open']),
                            "high": float(main_contract['high']),
                            "low": float(main_contract['low']),
                            "close": float(main_contract['close']),
                            "settle": float(main_contract.get('settle', 0)),
                            "volume": int(main_contract['volume']),
                            "oi": int(main_contract['open_interest']),
                            "turnover": float(main_contract.get('turnover', 0))
                        })
                else:
                    # 商品期货：数据库中的 symbol 是小写的主力连续合约代码（如 cu, rb, au）
                    variety_lower = variety.lower()
                    variety_df = df[df['symbol'] == variety_lower]

                    if len(variety_df) > 0:
                        for _, row in variety_df.iterrows():
                            # 数据库存储的是主力连续合约数据
                            results.append({
                                "date": datetime.strptime(row['trade_date'], "%Y%m%d").strftime("%Y-%m-%d"),
                                "contract_tag": f"主力({variety.upper()}888)",
                                "contract": f"{variety.upper()}888",
                                "open": float(row['open']),
                                "high": float(row['high']),
                                "low": float(row['low']),
                                "close": float(row['close']),
                                "settle": float(row.get('settle', 0)),
                                "volume": int(row['volume']),
                                "oi": int(row['open_interest']),
                                "turnover": float(row.get('turnover', 0))
                            })

            current_dt += timedelta(days=1)

        return results

    def get_contracts(self, variety: str) -> List[Dict[str, Any]]:
        """
        获取品种下所有上市合约

        注意：当前数据库只存储主力连续合约，不存储全部合约
        需要从交易所规则或额外数据源获取完整合约列表

        Args:
            variety: 品种代码

        Returns:
            合约列表
        """
        if not self.collector:
            return []

        # 获取最新交易日数据
        trade_date = self.collector.get_latest_trading_day()
        df = self.collector.get_all_exchange_data(trade_date, use_cache=True)

        if df is None or len(df) == 0:
            return []

        # 过滤品种
        variety_lower = variety.lower()
        variety_df = df[df['symbol'] == variety_lower]

        contracts = []
        for _, row in variety_df.iterrows():
            contracts.append({
                "contract": f"{variety.upper()}888",
                "tag": "主力",
                "last_trade_date": "",  # 需要从交易所规则推断
                "volume": int(row['volume']),
                "open_interest": int(row['open_interest'])
            })

        return contracts

    def get_dominant_mapping(self, variety: str) -> Dict[str, Any]:
        """
        获取品种的主力/次主力映射

        数据链路：交易所API → DuckDB缓存 → EastMoney → TqSdk直连
        对长尾品种（数据源白名单不覆盖），自动尝试 TqSdk 降级。

        内部缓存 exchange_data 结果，避免同交易日重复获取。

        Args:
            variety: 品种代码

        Returns:
            映射信息（含 source 和 status 标注）
        """
        if not self.collector:
            return self._fallback_long_tail(variety)

        # 获取最新交易日数据（带缓存，避免重复 fetch）
        trade_date = self.collector.get_latest_trading_day()
        trade_date_fmt = datetime.strptime(trade_date, "%Y%m%d").strftime("%Y-%m-%d")

        if self._cached_trade_date != trade_date:
            self._cached_df = self.collector.get_all_exchange_data(trade_date, use_cache=True)
            self._cached_trade_date = trade_date
        df = self._cached_df

        # 判断是否为金融期货（中金所）
        cffex_varieties = ['IF', 'IC', 'IM', 'IH', 'T', 'TF', 'TS', 'TL']
        variety_upper = variety.upper()
        is_financial = variety_upper in cffex_varieties

        if df is not None and len(df) > 0:
            if is_financial:
                # 金融期货：数据库中有具体合约（如 IF2607, IF2608）
                # 需要精确匹配，避免 T 匹配到 TA
                pattern = f"^{variety_upper}\\d{{4}}$"
                variety_contracts = df[df['symbol'].str.match(pattern, case=False)].copy()

                if len(variety_contracts) > 0:
                    # 按成交量排序，找到主力合约
                    variety_contracts = variety_contracts.sort_values('volume', ascending=False)
                    main_contract = variety_contracts.iloc[0]
                    main_symbol = main_contract['symbol']

                    # 找到次主力（成交量第二的合约）
                    next_main_symbol = None
                    if len(variety_contracts) > 1:
                        next_main_symbol = variety_contracts.iloc[1]['symbol']

                    return {
                        "variety": variety,
                        "main": main_symbol,
                        "next_main": next_main_symbol,
                        "index": f"{variety.upper()}99",
                        "index_price": float(main_contract['close']),
                        "trade_date": datetime.strptime(main_contract['trade_date'], "%Y%m%d").strftime("%Y-%m-%d"),
                        "volume": int(main_contract['volume']),
                        "open_interest": int(main_contract['open_interest']),
                        "metric_name": "volume",
                        "metric_value": int(main_contract['volume']),
                        "is_financial": True,
                        "source": "exchange_api",
                    }
            else:
                # 商品期货：数据库中的 symbol 是小写的主力连续合约代码（如 cu, rb, au）
                variety_lower = variety.lower()
                variety_df = df[df['symbol'] == variety_lower]

                if len(variety_df) > 0:
                    main_row = variety_df.iloc[0]
                    return {
                        "variety": variety,
                        "main": f"{variety.upper()}888",
                        "next_main": None,
                        "index": f"{variety.upper()}99",
                        "index_price": float(main_row['close']),
                        "trade_date": datetime.strptime(main_row['trade_date'], "%Y%m%d").strftime("%Y-%m-%d"),
                        "volume": int(main_row['volume']),
                        "open_interest": int(main_row['open_interest']),
                        "metric_name": "open_interest",
                        "metric_value": int(main_row['open_interest']),
                        "is_financial": False,
                        "source": "akshare_cache",
                    }

        # ===== 主流数据源无数据 → 进入长尾品种补录流 =====
        result = self._fallback_long_tail(variety, is_financial, trade_date_fmt)
        return result

    def get_oi_ranking(
        self,
        variety: str,
        contract_type: str = "main",
        specific_month: Optional[str] = None,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取持仓排名数据

        注意：交易所API不直接提供持仓排名，需要从其他数据源获取
        这里返回基础持仓数据作为参考

        Args:
            variety: 品种代码
            contract_type: 合约类型
            specific_month: 具体月份
            date: 日期

        Returns:
            持仓数据
        """
        if not self.collector:
            return {}

        # 获取行情数据
        quotes = self.get_quote(variety, contract_type, specific_month, date, date)

        if not quotes:
            return {}

        # 返回基础持仓信息
        # 注意：真正的持仓排名需要从交易所公布的会员持仓数据获取
        return {
            "date": quotes[0]["date"] if quotes else "",
            "contract": quotes[0]["contract"] if quotes else "",
            "note": "持仓排名数据需要从交易所会员持仓报告获取，当前返回基础持仓量",
            "open_interest": quotes[0]["oi"] if quotes else 0,
            "volume": quotes[0]["volume"] if quotes else 0
        }

    # ==================== 长尾品种补录流 ====================

    def _fallback_long_tail(
        self, variety: str,
        is_financial: bool = False,
        trade_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        长尾品种补录流：尝试 TqSdk → EastMoney → WebSearch 逐级降级。

        当前端数据源（交易所API/AKShare）不收录的品种，
        通过 TqSdk 直连交易所行情获取合约数据。

        Args:
            variety: 品种代码
            is_financial: 是否为金融期货
            trade_date: 交易日 YYYYMMDD（带连线的 YYYY-MM-DD）

        Returns:
            映射结果，含 source 和 status 标注
        """
        variety_upper = variety.upper()
        if not trade_date:
            trade_date = datetime.now().strftime("%Y-%m-%d")

        # 查询品种状态
        vstatus = VARIETY_STATUS.get(variety_upper, {'status': 'unknown', 'reason': ''})

        # --- 优先级 1: 通达信TQ-Local（第一数据源） ---
        if TDX_LOCAL_AVAILABLE:
            result = self._fallback_via_tdx(variety_upper, is_financial, trade_date)
            if result:
                result['status'] = vstatus['status']
                return result

        # --- 优先级 2: TqSdk 直连 ---
        tqapi_kls, _ = _lazy_tqsdk_api()
        if tqapi_kls is not None:
            result = self._fallback_via_tqsdk(variety_upper, is_financial, trade_date)
            if result:
                result['status'] = vstatus['status']
                return result

        # --- 优先级 2: EastMoney 合约级 ---
        if EASTMONEY_AVAILABLE:
            result = self._fallback_via_eastmoney(variety_upper, is_financial, trade_date)
            if result:
                result['status'] = vstatus['status']
                return result

        # --- 优先级 3: 返回品种状态说明 ---
        return {
            "variety": variety_upper,
            "main": None,
            "next_main": None,
            "index": None,
            "index_price": None,
            "trade_date": trade_date,
            "volume": 0,
            "open_interest": 0,
            "is_financial": is_financial,
            "source": "none",
            "status": vstatus['status'],
            "status_reason": vstatus['reason'],
            "updated_at": datetime.now().isoformat(),
        }

    def _fallback_via_tqsdk(
        self, variety_upper: str,
        is_financial: bool,
        trade_date: str
    ) -> Optional[Dict[str, Any]]:
        """
        通过 TqSdk 直连交易所获取品种合约数据。
        不受数据源白名单限制，所有上市合约均可查询。

        策略：根据品种所在交易所和已知合约月份模式，
        直接构建 instrument_id 列表，订阅后获取行情。
        避免全量扫描（TqSdk 有 267k+ 合约/期权/指数）。

        Args:
            variety_upper: 品种大写代码
            is_financial: 是否为金融期货
            trade_date: 交易日 YYYY-MM-DD

        Returns:
            映射结果或 None
        """
        TqApi_kls, TqAuth_kls = _lazy_tqsdk_api()
        if TqApi_kls is None:
            return None

        # 复用持久 TqApi 连接（避免每次建立 websocket 开销）
        if self._tq_api is None:
            try:
                import threading
                result = [None]
                exc_info = [None]

                def _connect():
                    try:
                        result[0] = TqApi_kls(auth=_TQ_AUTH_OBJ)
                    except Exception as e:
                        exc_info[0] = e

                t = threading.Thread(target=_connect, daemon=True)
                t.start()
                t.join(timeout=15)  # 15秒超时，防止永久阻塞
                if t.is_alive():
                    print(f"  [TqSDK] 连接超时 ({variety_upper})")
                    return None
                if exc_info[0]:
                    print(f"  [TqSDK] 连接失败 ({variety_upper}): {exc_info[0]}")
                    return None
                self._tq_api = result[0]
            except Exception as e:
                print(f"  [TqSDK] 连接异常 ({variety_upper}): {e}")
                return None
        api = self._tq_api

        # 确定交易所和代码格式
        exchange_code = self._get_exchange_for_variety(variety_upper)
        if not exchange_code:
            return None

        exchange_prefix = {
            'SHFE': 'SHFE', 'DCE': 'DCE', 'CZCE': 'CZCE',
            'GFEX': 'GFEX', 'INE': 'INE', 'CFFEX': 'CFFEX',
        }.get(exchange_code, '')

        if not exchange_prefix:
            return None

        # 构建可能的合约代码列表（当前月 ~ 未来12个月）
        now = datetime.now()
        contract_candidates = []
        for offset in range(1, 13):
            m = now.month + offset
            y_offset = (m - 1) // 12
            month = ((m - 1) % 12) + 1
            year = (now.year + y_offset) % 100

            if exchange_code == 'CZCE':
                # CZCE: 品种代码大写，3位交割月后缀（YMM）
                year_digit = str(year)[-1]
                code = f"{exchange_prefix}.{variety_upper}{year_digit}{month:02d}"
            else:
                # 其他交易所: 品种代码小写，4位YYMM后缀
                code = f"{exchange_prefix}.{variety_upper.lower()}{year:02d}{month:02d}"

            contract_candidates.append(code)

        # 尝试获取每个候选合约的行情
        contracts = []
        for cc in contract_candidates:
            try:
                q = api.get_quote(cc)
                if not q:
                    continue
                ins_class = str(q.get('ins_class', ''))
                if ins_class not in ('FUTURE', '期货'):
                    continue
                last_price = float(q.get('last_price', 0) or 0)
                if last_price <= 0:
                    continue
                contracts.append({
                    'code': cc.split('.')[-1],
                    'volume': int(q.get('volume', 0) or 0),
                    'oi': int(q.get('open_interest', 0) or 0),
                    'last_price': last_price,
                })
            except Exception:
                continue

        if not contracts:
            return None

        # 按成交量/持仓量排序选主力
        key = 'volume' if is_financial else 'oi'
        contracts.sort(key=lambda x: x[key], reverse=True)
        main_c = contracts[0]
        next_c = contracts[1] if len(contracts) > 1 else None

        return {
            "variety": variety_upper,
            "main": main_c['code'],
            "next_main": next_c['code'] if next_c else None,
            "index": f"{variety_upper}99",
            "index_price": main_c['last_price'],
            "trade_date": trade_date,
            "volume": main_c['volume'],
            "open_interest": main_c['oi'],
            "metric_name": key,
            "metric_value": main_c[key],
            "is_financial": is_financial,
            "source": "tqsdk_fallback",
        }

    def _fallback_via_eastmoney(
        self, variety_upper: str,
        is_financial: bool,
        trade_date: str
    ) -> Optional[Dict[str, Any]]:
        """
        通过东方财富 API 查询品种合约级数据。
        """
        try:
            em = EastMoneyCollector()
            contracts = em.get_contract_list(variety_upper)
            if not contracts:
                return None

            # 按成交量/持仓量排序选主力
            key = 'volume' if is_financial else 'oi'
            contracts.sort(key=lambda x: int(x.get(key, 0) or 0), reverse=True)
            main_c = contracts[0]
            next_c = contracts[1] if len(contracts) > 1 else None

            # 估算指数价格（按持仓量加权）
            total_oi = sum(int(c.get('oi', 0) or 0) for c in contracts)
            if total_oi > 0:
                index_price = sum(
                    int(c.get('oi', 0) or 0) * float(c.get('last_price', 0) or 0)
                    for c in contracts
                ) / total_oi
            else:
                index_price = main_c.get('last_price', 0)

            return {
                "variety": variety_upper,
                "main": main_c['code'],
                "next_main": next_c['code'] if next_c else None,
                "index": f"{variety_upper}99",
                "index_price": float(index_price),
                "trade_date": trade_date,
                "volume": int(main_c.get('volume', 0) or 0),
                "open_interest": int(main_c.get('oi', 0) or 0),
                "metric_name": key,
                "metric_value": int(main_c.get(key, 0) or 0),
                "is_financial": is_financial,
                "source": "eastmoney_fallback",
            }
        except Exception as e:
            return None

    def _fallback_via_tdx(
        self, variety_upper: str,
        is_financial: bool,
        trade_date: str
    ) -> Optional[Dict[str, Any]]:
        """
        通过通达信TQ-Local本地HTTP服务查询品种行情。
        作为第一优先级的降级数据源（ priority=0 ）。
        通达信提供 volume 数据但不提供 open_interest，
        因此对金融期货（CFFEX，按volume判主力）效果最佳，
        对商品期货仅提供价格参考。
        """
        global TDX_LOCAL_AVAILABLE, TDX_COLLECTOR
        if not TDX_LOCAL_AVAILABLE or TDX_COLLECTOR is None:
            return None

        try:
            # 获取品种行情快照
            result = TDX_COLLECTOR.get_quote(variety_upper)
            if not result:
                return None

            rec = result[0]
            volume = int(rec.get('volume', 0) or 0)
            price = float(rec.get('price', 0) or 0)

            return {
                "variety": variety_upper,
                "main": rec.get('code', ''),
                "next_main": None,
                "index": f"{variety_upper}99",
                "index_price": price,
                "trade_date": trade_date,
                "volume": volume,
                "open_interest": 0,
                "metric_name": "volume",
                "metric_value": volume,
                "is_financial": is_financial,
                "source": "tdx_local_fallback",
            }
        except Exception:
            TDX_LOCAL_AVAILABLE = False
            return None

    def _get_exchange_for_variety(self, variety: str) -> Optional[str]:
        """根据品种代码获取交易所"""
        exchange_map = {
            # SHFE 上期所
            'CU': 'SHFE', 'AL': 'SHFE', 'ZN': 'SHFE', 'PB': 'SHFE',
            'NI': 'SHFE', 'SN': 'SHFE', 'AU': 'SHFE', 'AG': 'SHFE',
            'RB': 'SHFE', 'HC': 'SHFE', 'SS': 'SHFE', 'RU': 'SHFE',
            'BR': 'SHFE', 'FU': 'SHFE', 'BU': 'SHFE', 'WR': 'SHFE',
            'SP': 'SHFE', 'AO': 'SHFE', 'AD': 'SHFE', 'OP': 'SHFE',
            # DCE 大商所
            'A': 'DCE', 'B': 'DCE', 'M': 'DCE', 'Y': 'DCE',
            'P': 'DCE', 'C': 'DCE', 'CS': 'DCE', 'I': 'DCE',
            'J': 'DCE', 'JM': 'DCE', 'L': 'DCE', 'V': 'DCE',
            'PP': 'DCE', 'EG': 'DCE', 'EB': 'DCE', 'PG': 'DCE',
            'JD': 'DCE', 'LH': 'DCE', 'RR': 'DCE',
            # CZCE 郑商所
            'AP': 'CZCE', 'CF': 'CZCE', 'CY': 'CZCE', 'CJ': 'CZCE',
            'FG': 'CZCE', 'SA': 'CZCE', 'SH': 'CZCE', 'MA': 'CZCE',
            'TA': 'CZCE', 'UR': 'CZCE', 'PF': 'CZCE', 'PR': 'CZCE',
            'PX': 'CZCE', 'PK': 'CZCE',
            'OI': 'CZCE', 'RM': 'CZCE', 'RS': 'CZCE', 'SR': 'CZCE',
            'WH': 'CZCE', 'PM': 'CZCE', 'SM': 'CZCE', 'SF': 'CZCE',
            'ZC': 'CZCE', 'JR': 'CZCE', 'LR': 'CZCE', 'RI': 'CZCE',
            # GFEX 广期所
            'SI': 'GFEX', 'LC': 'GFEX', 'PS': 'GFEX', 'PT': 'GFEX', 'PD': 'GFEX',
            # INE 上期能源
            'SC': 'INE', 'LU': 'INE', 'NR': 'INE', 'BC': 'INE',
            # CFFEX 中金所
            'IF': 'CFFEX', 'IC': 'CFFEX', 'IM': 'CFFEX', 'IH': 'CFFEX',
            'T': 'CFFEX', 'TF': 'CFFEX', 'TS': 'CFFEX', 'TL': 'CFFEX',
        }
        return exchange_map.get(variety.upper())

    def is_trading_day(self, date_str: str) -> bool:
        """检查是否为交易日"""
        if not self.collector:
            return False
        return self.collector.is_trading_day(date_str.replace("-", ""))

    def get_latest_trading_day(self) -> str:
        """获取最新交易日"""
        if not self.collector:
            return datetime.now().strftime("%Y-%m-%d")
        trade_date = self.collector.get_latest_trading_day()
        return datetime.strptime(trade_date, "%Y%m%d").strftime("%Y-%m-%d")


def main():
    """测试函数"""
    print("Testing FuturesDataAdapter...")
    adapter = FuturesDataAdapter()

    # 测试获取最新交易日
    latest = adapter.get_latest_trading_day()
    print(f"Latest trading day: {latest}")

    # 测试获取铜行情
    print("\nFetching CU quotes...")
    quotes = adapter.get_quote("CU", start_date=latest, end_date=latest)
    if quotes:
        print(f"Found {len(quotes)} records")
        for q in quotes[:3]:
            print(f"  {q['contract_tag']}: {q['close']} (OI: {q['oi']})")
    else:
        print("No data found")

    # 测试获取主力映射
    print("\nFetching CU dominant mapping...")
    mapping = adapter.get_dominant_mapping("CU")
    if mapping:
        print(f"  Main: {mapping.get('main')}")
        print(f"  Index Price: {mapping.get('index_price', 0):.2f}")
        print(f"  Volume: {mapping.get('volume', 0)}")
        print(f"  OI: {mapping.get('open_interest', 0)}")
    else:
        print("No mapping found")


if __name__ == "__main__":
    main()
