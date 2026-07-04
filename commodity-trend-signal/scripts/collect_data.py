# -*- coding: utf-8 -*-
"""
商品期货数据采集脚本。
从 TqSdk（首选）或 通达信MCP（降级）获取实时行情 + 技术指标，
输出 market_data.json 供 run_pipeline.py 消费。

用法:
    python -m scripts.collect_data [--output-dir DIR] [--data-dir DIR] [--source SOURCE]

数据源优先级: tqsdk > exchange_api > eastmoney > akshare > websearch > cache
期间路由：盘中(09:00-11:30/13:30-15:00/21:00-02:30) TqSDK优先；盘后 交易所API/东方财富优先
参见 futures-data-search/references/data_sources.yaml
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# ============================================================
# 品种定义：从 symbols.py 单一来源导入
# ============================================================
try:
    from symbols import ALL_SYMBOLS, ALL_PIDS, SYMBOL_DETAILS
except ImportError:
    from scripts.symbols import ALL_SYMBOLS, ALL_PIDS, SYMBOL_DETAILS

# 从单一来源构建 FUTURES_SYMBOLS（含交易所/通达信代码）
FUTURES_SYMBOLS: List[dict] = []
for pid, name in ALL_SYMBOLS:
    details = SYMBOL_DETAILS.get(pid, {})
    FUTURES_SYMBOLS.append({
        'pid': pid, 'name': name,
        'exchange': details.get('exchange', ''),
        'tdx_code': details.get('tdx_code', f'{pid}0'),
        'tdx_setcode': '8',
    })

# 校验：FUTURES_SYMBOLS 与 symbols.ALL_PIDS 必须一致
_pids_set = {s['pid'] for s in FUTURES_SYMBOLS}
assert _pids_set == ALL_PIDS, (
    f"FUTURES_SYMBOLS pid集合({len(_pids_set)})与ALL_PIDS({len(ALL_PIDS)})不一致。"
    f" 多出: {_pids_set - ALL_PIDS}, 缺少: {ALL_PIDS - _pids_set}"
)

def compute_indicators_from_klines(klines: List[dict]) -> dict:
    """指标计算 — 委派 indicators._compute_indicators_numpy()"""
    import pandas as pd
    from indicators import _compute_indicators_numpy
    df = pd.DataFrame({k: [float(r[k]) for r in klines] for k in ['open', 'high', 'low', 'close']})
    df['volume'] = [float(r.get('volume', 0)) for r in klines]
    return _compute_indicators_numpy(df, sym='')


def get_empty_kline() -> dict:
    """空K线占位。"""
    return {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0, 'date': ''}
# ============================================================
# 数据源：TqSdk
# ============================================================

def fetch_from_tqsdk(symbols: List[dict], batch_size: int = 10) -> List[dict]:
    """通过 TqSdk 获取实时行情 + K线 + 技术指标。支持分批订阅以避免超时。"""
    try:
        from tqsdk import TqApi, TqAuth
        from tqsdk.ta import MA, MACD, RSI, DMI, ATR
    except ImportError:
        print("[ERROR] TqSdk 未安装，请 pip install tqsdk")
        return []

    tq_user = os.environ.get('TQSDK_USERNAME') or os.environ.get('TQ_USER')
    tq_password = os.environ.get('TQSDK_PASSWORD') or os.environ.get('TQ_PASSWORD')
    if not tq_user or not tq_password:
        print("[ERROR] TQSDK_USERNAME/TQSDK_PASSWORD 或 TQ_USER/TQ_PASSWORD 环境变量未设置")
        return []

    print(f"[TqSdk] 连接中... 用户: {tq_user[:3]}***")
    auth = TqAuth(tq_user, tq_password)

    try:
        api = TqApi(auth=auth)
    except Exception as e:
        print(f"[ERROR] TqSdk 连接失败: {e}")
        return []

    results = []
    total_symbols = len(symbols)
    total_batches = (total_symbols + batch_size - 1) // batch_size
    
    print(f"[TqSdk] 分批订阅: {total_symbols} 个品种, 批次大小: {batch_size}, 总批次: {total_batches}")
    
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, total_symbols)
        batch_symbols = symbols[start_idx:end_idx]
        
        print(f"\n[批次 {batch_idx + 1}/{total_batches}] 订阅 {len(batch_symbols)} 个品种...")
        
        quotes_map = {}
        klines_map = {}
        
        # 订阅当前批次
        for sym in batch_symbols:
            pid = sym['pid']
            exchange = sym['exchange']
            tq_symbol = f"KQ.m@{exchange}.{pid}"
            try:
                quote = api.get_quote(tq_symbol)
                klines = api.get_kline_serial(tq_symbol, 24 * 3600, 80)
                quotes_map[pid] = quote
                klines_map[pid] = klines
            except Exception as e:
                print(f"  [WARN] 订阅 {tq_symbol} 失败: {e}")
        
        # 等待数据到达
        try:
            deadline = time.time() + 30  # 增加超时时间到30秒
            data_received = set()
            while time.time() < deadline:
                api.wait_update(deadline=time.time() + 1)
                # 检查哪些品种数据已到达
                for pid in klines_map:
                    if pid not in data_received and api.is_changing(klines_map[pid], "close"):
                        data_received.add(pid)
                # 如果所有品种数据都到达，提前退出
                if len(data_received) >= len(klines_map):
                    break
        except Exception as e:
            print(f"  [TIMEOUT] 批次 {batch_idx + 1} 超时: {e}")
        
        # 提取数据
        for sym in batch_symbols:
            pid = sym['pid']
            if pid not in quotes_map:
                print(f"  [SKIP] {pid} 无行情数据")
                continue

            q = quotes_map[pid]
            kl = klines_map.get(pid)

            last_price = float(q.last_price) if q.last_price else 0
            if last_price <= 0:
                print(f"  [SKIP] {pid} 价格为0")
                continue

            # 从K线计算技术指标
            tech = {}
            if kl is not None and len(kl) > 0:
                closes = kl['close'].tolist()
                highs = kl['high'].tolist()
                lows = kl['low'].tolist()
                volumes = kl['volume'].tolist()
                # 过滤 NaN
                valid = [(c, h, l, v) for c, h, l, v in zip(closes, highs, lows, volumes)
                         if c == c and h == h and l == l and v == v]  # NaN != NaN
                if len(valid) >= 30:
                    vc, vh, vl, vv = zip(*valid)
                    kline_dicts = [{'close': c, 'high': h, 'low': l, 'volume': v}
                                   for c, h, l, v in zip(vc, vh, vl, vv)]
                    tech = compute_indicators_from_klines(kline_dicts)

            open_interest = int(q.open_interest) if hasattr(q, 'open_interest') and q.open_interest else 0

            # 趋势评分 — 使用 scoring_system
            from scoring_system import calculate_composite_score
            sym_data = {'last_price': last_price, 'open_interest': open_interest}
            sc = calculate_composite_score(tech, sym_data, 0, None, None)
            s = 1 if sc['direction'] == 'BUY' else -1
            trend = {
                'score': sc['total'] * s, 'direction': sc['direction'],
                'L1': sc['L1_score'] * s, 'L2': sc['L2_score'] * s,
                'L3': sc['L3_score'] * s, 'L4': sc['L4_score'] * s,
                'veto': sc['veto_score'], 'grade': sc['grade'],
            }

            results.append({
                'product_id': pid,
                'product_name': sym['name'],
                'last_price': last_price,
                'open_interest': open_interest,
                'change_pct': round((last_price / float(q.pre_close) - 1) * 100, 2) if hasattr(q, 'pre_close') and q.pre_close else 0,
                'tech': tech,
                'trend': trend,
            })
            print(f"  [OK] {pid} ({sym['name']}): {last_price}, 得分={sc['total'] * s}")
        
        # 短暂等待，避免API过载
        if batch_idx < total_batches - 1:
            time.sleep(1)
    
    api.close()
    print(f"\n[TqSdk] 完成: 获取 {len(results)}/{total_symbols} 个品种数据")
    return results


# ============================================================
# 数据源：通达信 MCP (tdx-connector)
# ============================================================

def _tdx_fetch_kline(tdx_code: str, setcode: str = '8', want_num: int = 80) -> List[dict]:
    """通过通达信获取日K线数据。返回 [{open, high, low, close, volume}, ...]"""
    import subprocess
    import json as _json

    # 使用 Python 调用 tdx-connector MCP 是不现实的，这里用 subprocess 调用
    # 实际上需要通过 MCP 协议。降级方案：直接用 AKShare
    return []


def fetch_from_tdx(symbols: List[dict]) -> List[dict]:
    """通过通达信获取数据（降级）。实际使用时通过 MCP 工具调用。"""
    # 此函数作为占位，实际在 agent 模式下通过 mcp__tdx-connector 工具调用
    print("[TDX] 通达信数据源需要通过 MCP 工具调用，请使用 agent 模式")
    return []


# ============================================================
# 数据源：AKShare
# ============================================================

def fetch_from_akshare(symbols: List[dict]) -> List[dict]:
    """通过 AKShare 获取期货数据（使用 futures_main_sina 接口）。"""
    try:
        import akshare as ak
    except ImportError:
        print("[ERROR] AKShare 未安装，请 pip install akshare")
        return []

    print("[AKShare] 获取期货行情（futures_main_sina）...")
    results = []

    # 取120天K线用于技术指标计算
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=150)).strftime('%Y%m%d')

    for sym in symbols:
        pid = sym['pid']
        # AKShare 主力连续合约格式: {pid小写}0，如 rb0, i0, sc0, sf0, ma0
        ak_symbol = pid.lower() + '0'

        try:
            df = ak.futures_main_sina(symbol=ak_symbol, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                print(f"  [SKIP] {pid} ({ak_symbol}) 无数据")
                continue

            # 提取最新行情
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            last_price = float(last['收盘价'])
            prev_close = float(prev['收盘价'])
            change_pct = round((last_price / prev_close - 1) * 100, 2) if prev_close > 0 else 0
            open_interest = int(last.get('持仓量', 0) or 0)

            if last_price <= 0:
                print(f"  [SKIP] {pid} 价格为0")
                continue

            # 从K线计算技术指标
            klines = []
            oi_history = []
            for _, row in df.iterrows():
                klines.append({
                    'open': float(row.get('开盘价', 0) or 0),
                    'high': float(row.get('最高价', 0) or 0),
                    'low': float(row.get('最低价', 0) or 0),
                    'close': float(row.get('收盘价', 0) or 0),
                    'volume': int(row.get('成交量', 0) or 0),
                })
                oi_history.append(int(row.get('持仓量', 0) or 0))

            tech = compute_indicators_from_klines(klines)
            
            # 计算OI相关指标（期货专属）
            if len(oi_history) >= 20:
                oi_ma20 = sum(oi_history[-20:]) / 20
                if oi_ma20 > 0:
                    tech['OI_RATE'] = round(oi_history[-1] / oi_ma20, 4)
                    tech['OI_INCREASING'] = oi_history[-1] > oi_history[-2] if len(oi_history) > 1 else False
                    tech['OI_CHANGE_PCT'] = round((oi_history[-1] / oi_history[-2] - 1) * 100, 2) if len(oi_history) > 1 and oi_history[-2] > 0 else 0

            # 趋势评分 — 使用 scoring_system
            from scoring_system import calculate_composite_score
            sym_data = {'last_price': last_price, 'open_interest': open_interest}
            sc = calculate_composite_score(tech, sym_data, 0, kline_closes if klines else None, None)
            s = 1 if sc['direction'] == 'BUY' else -1
            trend = {
                'score': sc['total'] * s, 'direction': sc['direction'],
                'L1': sc['L1_score'] * s, 'L2': sc['L2_score'] * s,
                'L3': sc['L3_score'] * s, 'L4': sc['L4_score'] * s,
                'veto': sc['veto_score'], 'grade': sc['grade'],
            }

            results.append({
                'product_id': pid,
                'product_name': sym['name'],
                'last_price': last_price,
                'open_interest': open_interest,
                'change_pct': change_pct,
                'tech': tech,
                'trend': trend,
                'kline_closes': kline_closes,  # v2.13: 保存K线收盘价序列
            })
            print(f"  [OK] {pid} ({sym['name']}): {last_price}, 得分={sc['total'] * s}")

            # AKShare 有频率限制，短暂延时
            time.sleep(0.3)

        except Exception as e:
            print(f"  [WARN] {pid} ({ak_symbol}) 获取失败: {e}")

    return results


# ============================================================
# 数据源：交易所官方API（最权威，无爬虫合规风险）
# ============================================================

def fetch_from_exchange_official(symbols: List[dict]) -> List[dict]:
    """
    通过交易所官方API获取期货数据（最权威数据源）。
    
    支持交易所：
    - 大商所 (DCE)
    - 上期所 (SHFE)
    - 郑商所 (CZCE)
    - 中金所 (CFFEX)
    - 广期所 (GFEX)
    
    数据源优先级：交易所官方API > AKShare > TqSdk
    """
    try:
        # 导入交易所数据采集模块（已合并到 futures-data-search）
        futures_data_search_dir = os.path.expanduser("~/.workbuddy/skills/futures-data-search")
        collector_scripts = os.path.join(futures_data_search_dir, 'collectors', 'exchange_data', 'scripts')
        sys.path.insert(0, collector_scripts)
        from exchange_data_collector import ExchangeDataCollector
    except ImportError as e:
        print(f"[ERROR] 交易所数据采集模块导入失败 (futures-data-search 未安装): {e}")
        return []
    
    print("[交易所官方API] 开始获取数据...")
    
    collector = ExchangeDataCollector()
    
    # 获取最近交易日
    trade_date = collector.get_latest_trading_day()
    print(f"  交易日: {trade_date}")
    
    # 获取所有交易所数据
    exchange_df = collector.get_all_exchange_data(trade_date)
    
    if exchange_df is None or len(exchange_df) == 0:
        print("[交易所官方API] 数据获取失败")
        return []
    
    print(f"[交易所官方API] 获取到 {len(exchange_df)} 条记录")
    
    # 将交易所数据转换为内部格式
    results = []
    
    for sym in symbols:
        pid = sym['pid']
        exchange = sym['exchange']
        
        # 从交易所数据中查找匹配的品种
        # 匹配规则：交易所 + 品种代码
        matched = exchange_df[
            (exchange_df['exchange'] == exchange) & 
            (exchange_df['symbol'].str.contains(pid, case=False, na=False))
        ]
        
        if matched.empty:
            # 尝试模糊匹配
            matched = exchange_df[
                exchange_df['symbol'].str.contains(pid.lower(), case=False, na=False)
            ]
        
        if matched.empty:
            print(f"  [SKIP] {pid} ({sym['name']}) 未找到交易所数据")
            continue
        
        # 取最新一条数据
        latest = matched.iloc[-1]
        
        last_price = float(latest.get('close', 0))
        if last_price <= 0:
            print(f"  [SKIP] {pid} 价格为0")
            continue
        
        open_interest = int(latest.get('open_interest', 0))
        
        # 构建K线数据（如果有历史数据）
        klines = []
        if len(matched) > 1:
            for _, row in matched.iterrows():
                klines.append({
                    'open': float(row.get('open', 0)),
                    'high': float(row.get('high', 0)),
                    'low': float(row.get('low', 0)),
                    'close': float(row.get('close', 0)),
                    'volume': int(row.get('volume', 0)),
                })
        
        # 计算技术指标
        tech = {}
        if len(klines) >= 30:
            tech = compute_indicators_from_klines(klines)
        
        # 趋势评分 — 使用 scoring_system
        from scoring_system import calculate_composite_score
        sym_data = {'last_price': last_price, 'open_interest': open_interest}
        sc = calculate_composite_score(tech, sym_data, 0, None, None)
        s = 1 if sc['direction'] == 'BUY' else -1
        trend = {
            'score': sc['total'] * s, 'direction': sc['direction'],
            'L1': sc['L1_score'] * s, 'L2': sc['L2_score'] * s,
            'L3': sc['L3_score'] * s, 'L4': sc['L4_score'] * s,
            'veto': sc['veto_score'], 'grade': sc['grade'],
        }
        
        # 计算涨跌幅
        change_pct = 0
        if len(matched) > 1:
            prev_close = float(matched.iloc[-2].get('close', 0))
            if prev_close > 0:
                change_pct = round((last_price / prev_close - 1) * 100, 2)
        
        results.append({
            'product_id': pid,
            'product_name': sym['name'],
            'last_price': last_price,
            'open_interest': open_interest,
            'change_pct': change_pct,
            'tech': tech,
            'trend': trend,
            'data_source': '交易所官方API',
            'exchange': exchange,
            'trade_date': trade_date,
        })
        print(f"  [OK] {pid} ({sym['name']}): {last_price}, 得分={sc['total'] * s}")
    
    return results


# ============================================================
# 数据源组合：交易所官方API → TqSdk → AKShare
# ============================================================

def _run_with_timeout(func, timeout: int, *args, **kwargs):
    """
    线程超时包装器。func 在独立线程中运行，超时则立即返回 None。
    用于防止 TqSDK WebSocket 连接循环等网络操作无限期挂起。
    """
    import threading
    result = [None]
    exception = [None]
    completed = [False]
    
    def target():
        try:
            result[0] = func(*args, **kwargs)
            completed[0] = True
        except Exception as e:
            exception[0] = e
            completed[0] = True
    
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if not completed[0]:
        print(f"[TIMEOUT] 操作超时({timeout}s)，跳过")
        return None, True  # (result, timed_out)
    if exception[0]:
        raise exception[0]
    return result[0], False


def collect_all_data(source: str = 'auto', min_oi: int = 10000, timeout: int = 300) -> dict:
    """采集所有品种数据。返回 market_data.json 格式的 dict。
    
    数据源由 futures-data-search 的 MultiSourceAdapter 统一调度。
    数据源优先级（由 data_sources.yaml 配置驱动）：
      盘中链(09:00-11:30/13:30-15:00/21:00-02:30): TqSDK → 交易所API → 东方财富 → AKShare → WebSearch → 缓存
      盘后链: 交易所API → 东方财富 → TqSDK → AKShare → WebSearch → 缓存
    
    技术指标（L1-L4打分所需）从 AKShare 150天K线获取，与行情数据源解耦。
    
    Args:
        source: 数据源选择 ('auto'/'akshare'/'exchange'/'tqsdk')
        min_oi: 最低持仓量过滤阈值
        timeout: 超时秒数（默认300秒），超时后返回当前已采集的数据
    """
    print(f"\n{'='*60}")
    print(f"商品期货数据采集 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"数据源调度: MultiSourceAdapter（统一降级链路） | 最低持仓量: {min_oi}")
    print(f"{'='*60}\n")

    symbols = []
    data_source = 'none'

    adapter = _load_adapter()
    if adapter:
        # 超时保护：防止 TqSDK WebSocket 连接循环导致无限挂起
        symbols, timed_out = _run_with_timeout(
            _fetch_all_via_adapter, timeout, adapter, FUTURES_SYMBOLS
        )
        if timed_out:
            print(f"  ⚠ 数据采集超时({timeout}s)，使用已采集的 {len(symbols) if symbols else 0} 个品种")
        if symbols is None:
            symbols = []
        data_source = symbols[0].get('data_source', 'unknown') if symbols else 'none'
        if not timed_out:
            print(f"  ✓ 采集到 {len(symbols)} 个品种, 数据源: {data_source}")

    # 降级路径：MultiSourceAdapter 失败时直用 AKShare（周日/非交易日常见）
    if not symbols:
        print("\n  ⚠ MultiSourceAdapter 无数据，降级到 AKShare 直接采集...")
        akshare_data = fetch_from_akshare(FUTURES_SYMBOLS)
        if akshare_data:
            symbols = akshare_data
            data_source = 'akshare'
            print(f"  ✓ AKShare 降级采集: {len(symbols)} 个品种")
        else:
            print("[ERROR] AKShare 降级也失败，无法获取数据")
            return {'symbols': [], 'meta': {'source': 'none', 'timestamp': datetime.now().isoformat()}}
    else:
        # 有适配器数据：补充技术指标（带超时保护）
        print(f"\n[技术指标补充] 从AKShare获取历史K线计算指标...")
        akshare_data, ak_timed_out = _run_with_timeout(
            fetch_from_akshare, timeout, FUTURES_SYMBOLS
        )
        if ak_timed_out:
            print(f"  ⚠ AKShare技术指标获取超时({timeout}s)")
        if akshare_data:
            akshare_by_pid = {s['product_id']: s for s in akshare_data}
            enriched = 0
            for s in symbols:
                pid = s['product_id'].lower()
                ak_sym = akshare_by_pid.get(pid) or akshare_by_pid.get(s['product_id'])
                if ak_sym and ak_sym.get('tech'):
                    s['tech'] = ak_sym['tech']
                    s['trend'] = ak_sym.get('trend', s.get('trend', 0))
                    s['kline_closes'] = ak_sym.get('kline_closes', [])
                    enriched += 1
            print(f"  → 技术指标补充完成: {enriched}/{len(symbols)} 品种")

            # OI批量兜底: 通达信本地API不返回持仓量(Holding=0)，从AKShare补充
            if akshare_data:
                oi_patched = 0
                for s in symbols:
                    if s.get('open_interest', 0) <= 0 or s.get('open_interest') is None:
                        pid = s['product_id'].lower()
                        ak_sym = akshare_by_pid.get(pid) or akshare_by_pid.get(s['product_id'])
                        if ak_sym and ak_sym.get('open_interest', 0) > 0:
                            s['open_interest'] = ak_sym['open_interest']
                            if s.get('data_source') == 'tdx_local':
                                s['data_source'] = 'tdx_local+akshare_oi'
                            oi_patched += 1
                if oi_patched > 0:
                    print(f"  → OI兜底补丁: {oi_patched}/{len(symbols)} 品种 (tdx_local→AKShare)")
    
    if not symbols:
        print("[ERROR] 所有数据源均失败，无法获取数据")
        return {'symbols': [], 'meta': {'source': 'none', 'timestamp': datetime.now().isoformat()}}

    # 过滤持仓量 + 数据有效性验证
    valid_symbols = []
    rejected_reasons = {'zero_price': 0, 'stale_data': 0, 'low_oi': 0}
    
    for s in symbols:
        price = s.get('last_price', 0)
        oi = s.get('open_interest', 0)
        
        if price <= 0:
            rejected_reasons['zero_price'] += 1
            continue
        
        if min_oi > 0 and oi < min_oi:
            rejected_reasons['low_oi'] += 1
            continue
        
        s['source'] = s.get('data_source', 'unknown')
        s['timestamp'] = datetime.now().isoformat()
        valid_symbols.append(s)
    
    if rejected_reasons['zero_price'] > 0:
        print(f"[VALIDATION] 剔除零价格品种: {rejected_reasons['zero_price']} 个")
    if rejected_reasons['low_oi'] > 0:
        print(f"[VALIDATION] 剔除低持仓品种: {rejected_reasons['low_oi']} 个")
    
    symbols = valid_symbols
    if not symbols:
        print("[VALIDATION] 所有品种均被剔除，返回空数据")

    print(f"\n采集完成: {len(symbols)} 个品种, 数据源: {data_source}")

    return {
        'symbols': symbols,
        'meta': {
            'source': data_source,
            'timestamp': datetime.now().isoformat(),
            'count': len(symbols),
            'min_open_interest': min_oi,
        },
    }


def _load_adapter():
    """
    加载 futures-data-search 的 MultiSourceAdapter。
    适配器内置完整降级链路（配置驱动，见 data_sources.yaml）：
      盘中(09:00-11:30/13:30-15:00/21:00-02:30): TqSDK → 交易所API → 东方财富 → AKShare → WebSearch → 缓存
      盘后: 交易所API → 东方财富 → TqSDK → AKShare → WebSearch → 缓存

    使用临时命名空间切换避免 scripts 包冲突：
      commodity-trend-signal/scripts 和 futures-data-search/scripts 同名，
      importlib 加载 multi_source_adapter.py 前需临时让 scripts 指向 futures-data-search。
    """
    saved_mods = {}
    saved_path = list(sys.path)
    try:
        fds_dir = os.path.expanduser("~/.workbuddy/skills/futures-data-search")

        # 1. 保存当前 scripts 包相关模块，从 sys.modules 中移除
        for key in list(sys.modules.keys()):
            if key == 'scripts' or key.startswith('scripts.'):
                saved_mods[key] = sys.modules.pop(key)

        # 2. 确保 futures-data-search 在 path 首位
        if fds_dir in sys.path:
            sys.path.remove(fds_dir)
        sys.path.insert(0, fds_dir)
        # 同时移除 commodity-trend-signal 避免干扰
        trend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if trend_dir in sys.path:
            sys.path.remove(trend_dir)

        # 3. 用 importlib 加载（此时 scripts → futures-data-search/scripts）
        import importlib.util
        msa_path = os.path.join(fds_dir, "scripts", "multi_source_adapter.py")
        spec = importlib.util.spec_from_file_location("multi_source_adapter", msa_path)
        msa = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(msa)
        adapter = msa.MultiSourceAdapter()

        # 同时加载 DataSourceConfig 供后续使用
        dsc_path = os.path.join(fds_dir, "scripts", "data_source_config.py")
        spec2 = importlib.util.spec_from_file_location("data_source_config", dsc_path)
        dsc_mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(dsc_mod)
        adapter._config = dsc_mod.DataSourceConfig()

        return adapter
    except Exception as e:
        print(f"[WARNING] MultiSourceAdapter 加载失败: {e}")
        return None
    finally:
        # 4. 恢复 sys.path 和 sys.modules
        sys.path.clear()
        sys.path.extend(saved_path)
        for key, mod in saved_mods.items():
            sys.modules[key] = mod


def _fetch_all_via_adapter(adapter, symbols: List[dict]) -> List[dict]:
    """
    通过 MultiSourceAdapter 采集所有品种数据。
    适配器自动根据参数配置选择最优可用数据源，实现统一的降级链路。
    当前路由时段由 DataSourceConfig 决定（data_sources.yaml）。
    """
    results = []
    errors = 0
    total = len(symbols)

    # 记录数据源配置状态
    source_chain = 'unknown'
    if hasattr(adapter, '_config') and adapter._config:
        now = datetime.now()
        t = now.hour * 100 + now.minute
        is_trading = (900 <= t < 1130) or (1330 <= t < 1500) or (2100 <= t <= 2359) or (0 <= t <= 230)
        try:
            sources = adapter._config.get_priority_list(is_trading_hour=is_trading)
            source_chain = ' → '.join(s.value for s in sources)
        except Exception:
            pass
    print(f"  [路由] 当前时段: {'盘中' if is_trading else '盘后'}, 数据源链: {source_chain}")

    for idx, sym in enumerate(symbols):
        pid = sym['pid']
        exchange = sym.get('exchange', '')
        if idx % 10 == 0:
            print(f"  [{idx+1}/{total}] 采集 {pid}...", end='\r' if idx < total - 1 else '\n')

        try:
            data = adapter.get_quote(variety=pid)
            if data.get('success') and data.get('data'):
                record = data['data'][-1]
                oi = int(record.get('oi', record.get('open_interest', record.get('holding', 0))))
                data_src = data.get('data_source', 'unknown')

                results.append({
                    'product_id': pid,
                    'name': sym.get('name', pid),
                    'exchange': exchange,
                    'last_price': float(record.get('close', record.get('price', 0))),
                    'open_interest': oi,
                    'volume': int(record.get('volume', 0)),
                    'change_pct': float(record.get('change_pct', 0)),
                    'data_source': data_src,
                })
            else:
                errors += 1
                if errors <= 5:
                    print(f"  [SKIP] {pid} 无数据 ({data.get('error', '未知错误')})")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  [SKIP] {pid} 采集异常: {e}")

    if errors > 0:
        print(f"  跳过 {errors}/{total} 个品种")

    return results


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='商品期货数据采集')
    parser.add_argument('--output-dir', default=None, help='输出目录（默认: data_dir 参数）')
    parser.add_argument('--data-dir', default=None, help='数据目录（默认: 技能目录下的 data/）')
    parser.add_argument('--source', default='auto', choices=['auto', 'exchange', 'tqsdk', 'akshare'],
                        help='数据源（默认: auto 自动降级）')
    parser.add_argument('--min-oi', type=int, default=10000, help='最低持仓量过滤（默认: 10000）')
    args = parser.parse_args()

    # 确定输出目录
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = args.data_dir or os.path.join(skill_dir, 'data')
    output_dir = args.output_dir or data_dir

    os.makedirs(output_dir, exist_ok=True)

    # 采集数据
    market_data = collect_all_data(source=args.source, min_oi=args.min_oi)

    # 保存
    output_path = os.path.join(output_dir, 'market_data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(market_data, f, ensure_ascii=False, indent=2)

    print(f"\n数据已保存: {output_path}")
    print(f"品种数: {market_data['meta']['count']}")
    print(f"数据源: {market_data['meta']['source']}")

    return market_data


if __name__ == '__main__':
    main()
