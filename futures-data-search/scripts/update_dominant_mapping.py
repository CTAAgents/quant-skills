#!/usr/bin/env python3
"""
主力映射定时更新脚本 v3.0
每日收盘后运行，覆盖全部6个交易所（SHFE/DCE/CZCE/GFEX/INE/CFFEX）
更新主力/次主力合约映射表

核心设计（2026-06-29 重构）：
1. 数据源优先级：通达信TQ-Local（第一）→ 交易所API（OI补全）→ TqSdk/EastMoney（长尾降级）
2. 三阶段数据合并：
   - Phase 1: 通达信 get_all_contracts() → 获取合约级 volume + holding
   - Phase 2: 交易所API → 补全 OI 数据（通达信 holding=0 时覆盖）
   - Phase 3: 长尾降级（TqSdk / EastMoney / 状态标记）
3. CFFEX 按成交量判主力，其余交易所按持仓量判主力
4. 覆盖全部品种，无品种遗漏

版本历史：
  v2.1 (2026-06-28): 修复AKShare品种级数据匹配，双模式适配
  v3.0 (2026-06-29): 通达信优先 + 交易所API OI补全，数据源优先级重构
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from dominant_mapping import DominantMappingCalculator, ContractInfo

# ==================== 配置 ====================

# 品种-交易所映射
EXCHANGE_MAP: Dict[str, str] = {
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
    # ZC（动力煤）已于2022年政策性暂停，2026年起不再同步
    'JR': 'CZCE', 'LR': 'CZCE', 'RI': 'CZCE',
    # GFEX 广期所
    'SI': 'GFEX', 'LC': 'GFEX', 'PS': 'GFEX', 'PT': 'GFEX', 'PD': 'GFEX',
    # INE 上期能源
    'SC': 'INE', 'LU': 'INE', 'NR': 'INE', 'BC': 'INE',
    # CFFEX 中金所
    'IF': 'CFFEX', 'IC': 'CFFEX', 'IM': 'CFFEX', 'IH': 'CFFEX',
    'T': 'CFFEX', 'TF': 'CFFEX', 'TS': 'CFFEX', 'TL': 'CFFEX',
    # DCE 冷门品种（有合约但交易极不活跃）
    'BB': 'DCE', 'FB': 'DCE', 'LG': 'DCE',
}

# 金融期货品种（中金所所有品种）
CFFEX_VARIETIES = ['IF', 'IC', 'IM', 'IH', 'T', 'TF', 'TS', 'TL']

# 交易所中文名
EXCHANGE_NAMES = {
    'SHFE': '上期所', 'DCE': '大商所', 'CZCE': '郑商所',
    'GFEX': '广期所', 'INE': '能源中心', 'CFFEX': '中金所',
}


def get_varieties() -> List[str]:
    """获取完整的品种列表"""
    varieties_file = Path(__file__).parent.parent / "references" / "varieties.yaml"
    if varieties_file.exists():
        try:
            import yaml
            with open(varieties_file, 'r', encoding='utf-8') as f:
                varieties_data = yaml.safe_load(f)
            return [v['code'] for v in varieties_data.get('varieties', [])]
        except Exception:
            pass
    return list(EXCHANGE_MAP.keys())


def is_contract_level(symbol: str, variety_upper: str) -> bool:
    """
    判断 symbol 是否为合约级数据（含交割月信息）。
    合约级: cu2609, TA609, IF2609
    品种级: cu, TA, a (AKShare/pre-computed continuous)
    """
    suffix = symbol[len(variety_upper):]
    return bool(suffix and suffix.isdigit() and len(suffix) >= 3)


def extract_variety_contracts(
    df,
    variety_upper: str,
    is_czce: bool = False
) -> List[Dict]:
    """从交易所数据中提取指定品种的所有合约记录。"""
    if df is None or len(df) == 0:
        return []

    variety_lower = variety_upper.lower()
    match_records = []

    for _, row in df.iterrows():
        symbol = str(row.get('symbol', '')).strip()
        if not symbol:
            continue

        matched = False

        # CZCE 合约级: TA609, TA611
        if is_czce:
            if re.match(rf'^{re.escape(variety_upper)}\d{{3}}$', symbol):
                matched = True
            elif symbol.upper() == variety_upper and not re.search(r'\d', symbol):
                matched = True
        else:
            # 其他交易所:
            # 合约级: cu2609, a2609, IF2609 | 品种级: cu, a, IF
            sym_prefix = symbol[:len(variety_upper)]
            if (re.match(rf'^{re.escape(sym_prefix)}\d{{4}}$', symbol, re.IGNORECASE)
                    and sym_prefix.upper() == variety_upper):
                matched = True
            elif symbol.lower() == variety_lower and not re.search(r'\d', symbol):
                matched = True

        if matched:
            match_records.append({
                'symbol': symbol,
                'open': float(row.get('open', 0) or 0),
                'high': float(row.get('high', 0) or 0),
                'low': float(row.get('low', 0) or 0),
                'close': float(row.get('close', 0) or 0),
                'settle': float(row.get('settle', 0) or 0),
                'volume': int(row.get('volume', 0) or 0),
                'open_interest': int(row.get('open_interest', 0) or 0),
                'turnover': float(row.get('turnover', 0) or 0),
                'source': row.get('source', 'unknown'),
            })

    return match_records


def extract_delivery_month(symbol: str, variety_upper: str, is_czce: bool = False) -> str:
    """从合约代码中提取交割月 YYMM 格式。"""
    suffix = symbol[len(variety_upper):]
    if not suffix or not suffix.isdigit():
        # 品种级代码，使用当前日期之后第2个月（确保在 T+3 之后）
        now = datetime.now()
        next_month = now.month + 2
        year_offset = (next_month - 1) // 12
        m = ((next_month - 1) % 12) + 1
        y = (now.year + year_offset) % 100
        return f"{y:02d}{m:02d}"

    if is_czce and len(suffix) == 3:
        year_digit = suffix[0]
        month = suffix[1:3]
        current_year_last = datetime.now().strftime("%y")[-1]
        if year_digit == current_year_last:
            full_year = datetime.now().strftime("%y")
        else:
            full_year = f"2{year_digit}"
        return f"{full_year}{month}"
    elif len(suffix) >= 4:
        return suffix[:4]
    else:
        return datetime.now().strftime("%y%m")


def estimate_last_trade_date(delivery_month: str) -> str:
    """估算最后交易日：交割月第15天。"""
    if len(delivery_month) < 4:
        delivery_month = datetime.now().strftime("%y%m")
    year_str = delivery_month[:2]
    month_str = delivery_month[2:4]
    try:
        year = int(f"20{year_str}")
        month = int(month_str)
        month = max(1, min(12, month))
    except (ValueError, IndexError):
        now = datetime.now()
        year = now.year
        month = now.month
    return f"{year:04d}-{month:02d}-15"


def build_simple_mapping(
    variety: str, records: List[Dict], latest_date: str, is_financial: bool
) -> Dict[str, Any]:
    """
    Mode B: 品种级数据（AKShare）的直接映射。
    使用 888/99 合成代码，不经过完整主力算法。
    """
    # 取第一条记录（品种级数据通常只有一条主力连续数据）
    rec = records[0] if records else None
    if not rec:
        return {}

    close_price = rec['close'] if rec else 0
    return {
        "variety": variety,
        "main": f"{variety}888",
        "next_main": None,
        "index": f"{variety}99",
        "index_price": close_price,
        "prev_main": None,
        "switched": False,
        "switch_date": None,
        "prev_close": None,
        "new_open": None,
        "gap": None,
        "updated_at": datetime.now().isoformat(),
        "trade_date": latest_date,
        "volume": rec['volume'],
        "open_interest": rec['open_interest'],
        "is_financial": is_financial,
        "exchange": EXCHANGE_MAP.get(variety, 'UNKNOWN'),
    }


def build_calculated_mapping(
    variety: str, records: List[Dict], latest_date: str,
    is_financial: bool, is_czce: bool, current_main: Optional[str]
) -> Dict[str, Any]:
    """
    Mode A: 合约级数据的完整主力算法计算。
    使用 DominantMappingCalculator。
    """
    contracts = []
    seen_codes = set()
    main_vol = 0
    main_oi = 0

    for rec in records:
        symbol = rec['symbol'].upper()
        if symbol in seen_codes:
            continue
        seen_codes.add(symbol)

        delivery_month = extract_delivery_month(rec['symbol'], variety, is_czce=is_czce)
        last_trade_date = estimate_last_trade_date(delivery_month)
        vol = rec['volume']
        oi = rec['open_interest']

        # 以第一条（通常是成交量/持仓量最大的）作为主力指标参考
        if main_vol == 0:
            main_vol = vol
            main_oi = oi

        contracts.append(ContractInfo(
            code=symbol,
            volume=vol,
            open_interest=oi,
            last_trade_date=last_trade_date,
            close_price=rec['close'],
            delivery_month=delivery_month,
        ))

    if not contracts:
        return {}

    calculator = DominantMappingCalculator()
    result = calculator.calculate_dominant(
        variety=variety,
        contracts=contracts,
        current_main=current_main,
        trade_date=latest_date,
        is_financial=is_financial,
    )

    result['is_financial'] = is_financial
    result['exchange'] = EXCHANGE_MAP.get(variety, 'UNKNOWN')
    result['volume'] = main_vol
    result['open_interest'] = main_oi
    return result


def update_dominant_mapping():
    """
    主力映射更新主函数。
    双模式：合约级数据→Calculator，品种级数据→简单映射。
    """
    print("=" * 60)
    print(f"主力映射更新 v2.1 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ===== 初始化数据适配器 =====
    from data_adapter import FuturesDataAdapter
    adapter = FuturesDataAdapter()
    collector = adapter.collector

    # ===== 初始化通达信TQ-Local（第一数据源）=====
    tdx_collector = None
    tdx_available = False
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "collectors"))
        from tdx_collector import TdxCollector
        tdx_collector = TdxCollector()
        tdx_available = tdx_collector.is_available
        print(f"  通达信TQ-Local: {'✅ 已连接' if tdx_available else '⚠️ 不可用'}")
    except Exception as e:
        print(f"  通达信TQ-Local: ❌ 初始化失败: {e}")

    # ===== 初始化交易所数据采集器 =====
    if not collector:
        print("❌ ExchangeDataCollector 不可用，将完全依赖通达信")
    else:
        print(f"  ExchangeDataCollector: ✅ 就绪")
        print(f"  DB路径: {adapter.collector.db_path if hasattr(adapter.collector, 'db_path') else '默认'}")

    # 获取最新交易日
    trade_date_str = ""
    if collector:
        try:
            latest_trade_date_raw = collector.get_latest_trading_day()
            trade_date_str = f"{latest_trade_date_raw[:4]}-{latest_trade_date_raw[4:6]}-{latest_trade_date_raw[6:]}"
        except Exception:
            pass
    if not trade_date_str:
        trade_date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"最新交易日: {trade_date_str}")

    # 获取品种列表
    varieties = get_varieties()
    print(f"品种总数: {len(varieties)}")

    # 按交易所分组
    exchange_varieties: Dict[str, List[str]] = {}
    for v in varieties:
        exch = EXCHANGE_MAP.get(v, 'UNKNOWN')
        exchange_varieties.setdefault(exch, []).append(v)
    print(f"交易所分布: {', '.join(f'{e}={len(vs)}' for e, vs in exchange_varieties.items())}")

    # ===== 尝试从交易所API获取数据（作为通达信OI补全）=====
    exchange_api_data = {}
    if collector:
        print("\n===== 分交易所获取数据（API补全） =====")
        exchange_methods = {
            'DCE': collector.get_dce_daily_data,
            'SHFE': collector.get_shfe_daily_data,
            'CZCE': collector.get_czce_daily_data,
            'CFFEX': collector.get_cffex_daily_data,
            'GFEX': collector.get_gfex_daily_data,
        }
        for exch in ['DCE', 'SHFE', 'CZCE', 'CFFEX', 'GFEX']:
            method = exchange_methods[exch]
            try:
                df = method(latest_trade_date_raw, use_cache=True)
                if df is not None and len(df) > 0:
                    exchange_api_data[exch] = df
                    print(f"  {EXCHANGE_NAMES[exch]} ({exch}): ✓ {len(df)} 条")
                else:
                    print(f"  {EXCHANGE_NAMES[exch]} ({exch}): - 无数据")
            except Exception as e:
                print(f"  {EXCHANGE_NAMES[exch]} ({exch}): ✗ {e}")

        # 全量补充（跳过 get_all_exchange_data 以避免AKShare重获取挂起，直接使用已有数据）
        try:
            if exchange_api_data:
                combined_dfs = []
                for exch_df in exchange_api_data.values():
                    if isinstance(exch_df, pd.DataFrame) and len(exch_df) > 0:
                        combined_dfs.append(exch_df)
                if combined_dfs and len(combined_dfs) > 1:
                    import pandas as pd
                    full_df = pd.concat(combined_dfs, ignore_index=True)
                    exchange_api_data['FULL'] = full_df
                    print(f"  全量补充（组合）: ✓ {len(full_df)} 条")
        except Exception as e:
            print(f"  全量补充（组合）跳过: {e}")

        # INE DB直读（单独获取）
        try:
            ine_df = collector._read_from_db(latest_trade_date_raw, 'INE')
            if ine_df is not None and len(ine_df) > 0:
                exchange_api_data['INE'] = ine_df
                print(f"  INE DB直读: ✓ {len(ine_df)} 条")
            else:
                print(f"  INE DB直读: - 无数据")
        except Exception:
            pass

        # INE DB直读
        try:
            ine_df = collector._read_from_db(latest_trade_date_raw, 'INE')
            if ine_df is not None and len(ine_df) > 0:
                exchange_api_data['INE'] = ine_df
        except Exception:
            pass

    # ===== 读取当前映射表 =====
    current_mappings = {}
    latest_file = Path(__file__).parent.parent / "data" / "dominant_maps" / "dominant_map_latest.json"
    if latest_file.exists():
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                current_mappings = json.load(f)
            print(f"  当前映射: {len(current_mappings)} 个品种")
        except Exception:
            pass

    # ===== 计算主力映射（通达信优先）=====
    print("\n===== 计算主力映射（数据源: 通达信→API补全）=====")
    new_mappings: Dict[str, Dict] = {}
    contract_level_count = 0
    variety_level_count = 0

    for variety in varieties:
        variety_upper = variety
        is_cffex = variety_upper in CFFEX_VARIETIES
        exchange = EXCHANGE_MAP.get(variety_upper, 'UNKNOWN')
        is_czce = exchange == 'CZCE'
        current_main = current_mappings.get(variety, {}).get("main") if current_mappings else None

        # === Step 1: 通达信优先获取合约级数据 ===
        tdx_contracts = []
        if tdx_available:
            try:
                tdx_data = tdx_collector.get_all_contracts(variety_upper)
                if tdx_data:
                    tdx_contracts = tdx_data
            except Exception:
                pass

        # === Step 2: 尝试从交易所API获取OI数据（补全/修正）===
        api_records = []
        if exchange in exchange_api_data:
            api_records = extract_variety_contracts(
                exchange_api_data[exchange], variety_upper, is_czce=is_czce
            )
        if not api_records and 'FULL' in exchange_api_data:
            api_records = extract_variety_contracts(
                exchange_api_data['FULL'], variety_upper, is_czce=is_czce
            )
        if exchange == 'INE' and not api_records and 'INE' in exchange_api_data:
            api_records = extract_variety_contracts(
                exchange_api_data['INE'], variety_upper, is_czce=is_czce
            )

        # CFFEX: 过滤期权合约
        if is_cffex:
            api_records = [r for r in api_records if '-' not in r.get('symbol', '')]
            tdx_contracts = [r for r in tdx_contracts if '-' not in r.get('code', '')]

        # === Step 3: 合并数据 ===
        # 通达信数据用作主力判断主力（volume/holding），
        # 交易所API数据用作 OI 补全。
        merged_contracts = []
        seen_symbols = set()

        # 3a. 先处理通达信数据（主力数据源）
        for tc in tdx_contracts:
            code = tc['code']
            if code in seen_symbols:
                continue
            seen_symbols.add(code)
            merged_contracts.append({
                'symbol': code,
                'volume': tc['volume'],
                'open_interest': tc['holding'],  # 通达信"holding"对应持仓量
                'close': tc['close'],
                'high': tc['high'],
                'low': tc['low'],
                'open': tc['open'],
                'price': tc['price'],
                'source': 'tdx_local',
            })

        # 3b. 用交易所API数据补全 OI（通达信holding可能为0）
        if api_records:
            api_by_symbol = {r['symbol']: r for r in api_records}
            for mc in merged_contracts:
                sym = mc['symbol']
                if sym in api_by_symbol:
                    api_r = api_by_symbol[sym]
                    if mc['open_interest'] == 0:
                        mc['open_interest'] = api_r['open_interest']
                    if mc['close'] == 0:
                        mc['close'] = api_r['close']
                    mc['source'] = 'tdx+api'

            # 补充通达信未覆盖的合约
            for r in api_records:
                if r['symbol'] not in seen_symbols:
                    seen_symbols.add(r['symbol'])
                    merged_contracts.append({
                        'symbol': r['symbol'],
                        'volume': r['volume'],
                        'open_interest': r['open_interest'],
                        'close': r['close'],
                        'high': r['high'],
                        'low': r['low'],
                        'open': r['open'],
                        'price': r['close'],
                        'source': 'exchange_api',
                    })

        # 3c. 通达信和交易所API均无数据 → 尝试长尾降级
        if not merged_contracts:
            fallback = adapter.get_dominant_mapping(variety_upper)
            if fallback and fallback.get('main'):
                new_mappings[variety] = fallback
                new_mappings[variety]['updated_at'] = datetime.now().isoformat()
                new_mappings[variety]['mode'] = 'fallback_tail'
                contract_level_count += 1
                fb_main = fallback.get('main', '?')
                fb_src = fallback.get('source', '?')
                print(f'  [fallback] {variety}: {fb_main} via {fb_src}')
                continue
            elif fallback and fallback.get('status') in ('policy_frozen', 'delisted'):
                new_mappings[variety] = fallback
                new_mappings[variety]['mode'] = 'status_only'
                variety_level_count += 1
                continue

        # 判断数据级别
        first_rec = merged_contracts[0]
        is_contract_data = is_contract_level(first_rec['symbol'], variety_upper)

        if is_contract_data:
            result = build_calculated_mapping(
                variety_upper, merged_contracts, trade_date_str,
                is_cffex, is_czce, current_main
            )
            contract_level_count += 1
        else:
            result = build_simple_mapping(
                variety_upper, merged_contracts, trade_date_str, is_cffex
            )
            variety_level_count += 1

        if result:
            new_mappings[variety] = result

    print(f"✓ 计算完成: 合约级={contract_level_count}, 品种级={variety_level_count}, "
          f"合计={len(new_mappings)}/{len(varieties)}")

    # ===== 保存映射表 =====
    output_dir = Path(__file__).parent.parent / "data" / "dominant_maps"
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = trade_date_str.replace("-", "")
    filename = f"dominant_map_{date_str}.json"
    filepath = output_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(new_mappings, f, ensure_ascii=False, indent=2)

    latest_filepath = output_dir / "dominant_map_latest.json"
    with open(latest_filepath, 'w', encoding='utf-8') as f:
        json.dump(new_mappings, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 映射表已保存: {filepath}")
    print(f"✓ 最新映射表已更新: {latest_filepath}")

    # ===== 覆盖统计 =====
    print("\n===== 覆盖统计 =====")
    for exch in ['SHFE', 'DCE', 'CZCE', 'GFEX', 'INE', 'CFFEX']:
        vs = exchange_varieties.get(exch, [])
        mapped = [v for v in vs if v in new_mappings]
        pct = len(mapped) / len(vs) * 100 if vs else 0
        status = "✅" if len(mapped) == len(vs) else "⚠️"
        missed = [v for v in vs if v not in new_mappings]
        missed_str = f", 缺失={missed}" if missed else ""
        print(f"  {EXCHANGE_NAMES[exch]:6s} ({exch}): {status} {len(mapped)}/{len(vs)} ({pct:.0f}%){missed_str}")

    # ===== 打印结果样例 =====
    print("\n品种映射样例:")
    for variety in ['CU', 'RB', 'AU', 'I', 'M', 'TA', 'IF', 'T', 'SC', 'SA']:
        if variety in new_mappings:
            m = new_mappings[variety]
            main = m.get('main', 'N/A')
            price = m.get('index_price') or 0
            vol = m.get('volume') or 0
            oi = m.get('open_interest') or 0
            level = "合约级" if main and '888' not in str(main) else "品种级"
            print(f"  {variety}: 主力={main}, 价格={price:.2f}, 量={vol}, 仓={oi} [{level}]")

    # ===== 换月报告 =====
    calculator = DominantMappingCalculator()
    switches = calculator.get_switch_report(current_mappings, new_mappings)
    if switches:
        print(f"\n⚠️ 换月事件 ({len(switches)} 个):")
        for s in switches:
            print(f"  {s['variety']}: {s['prev_main']} → {s['new_main']} (价差={s.get('gap', 'N/A')})")
    else:
        print("\n✓ 无换月事件")

    print("\n✅ 主力映射更新完成 (v2.1)")
    return True


if __name__ == "__main__":
    success = update_dominant_mapping()
    sys.exit(0 if success else 1)
