#!/usr/bin/env python3
"""
基本面数据采集脚本 — 每日盘后运行（~16:00）
采集：仓单日报、持仓排名、期限结构、产业资讯
存储：DuckDB（与 daily_data 共享数据库实例）

数据源：
  仓单 → 世铝网(cnal.com)/SHFE官网API
  持仓排名 → SHFE API / 同花顺
  期限结构 → MultiSourceAdapter

用法：
    python collect_fundamentals.py                             # 采集全部
    python collect_fundamentals.py --warehouse                 # 仅仓单
    python collect_fundamentals.py --oi-ranking                # 仅持仓排名
    python collect_fundamentals.py --term-structure            # 仅期限结构
    python collect_fundamentals.py --date 2026-06-29           # 指定日期
"""
import sys, os, json, re
from datetime import datetime
from typing import Dict, List, Optional, Any

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SKILL_DIR)
sys.path.insert(0, SCRIPT_DIR)

DUCKDB_PATH = r'C:\Users\yangd\Documents\WorkBuddy\futures_data.duckdb'


def get_db():
    import duckdb
    return duckdb.connect(DUCKDB_PATH)


# ==================== 仓单采集（世铝网 cnal.com） ====================

# 世铝网品种中文名 → 代码映射
CNAL_VARIETY_MAP = {
    '铜': 'CU', '铜(BC)': 'BC', '铝': 'AL', '锌': 'ZN', '铅': 'PB',
    '镍': 'NI', '锡': 'SN', '氧化铝(仓库)': 'AO',
    '黄金': 'AU', '白银': 'AG', '天然橡胶': 'RU', '螺纹钢': 'RB',
    '热轧卷板': 'HC', '不锈钢': 'SS', '纸浆': 'SP', '石油沥青': 'BU',
    '燃料油': 'FU', '线材': 'WR',
}

# 过滤词（非仓库名）
_SKIP_NAMES = {'合计', '总计', '保税商品总计', '完税商品总计', '完税', '保税'}


def _discover_warehouse_url(session, date_str: str) -> Optional[str]:
    """自动发现世铝网当日仓单日报URL。使用文章ID渐进扫描。"""
    import requests as req
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    # 策略：从已知基准ID线性扫描（世铝网文章ID逐日递增）
    # 已知: 665543 = 2026-06-29
    BASE_ID = 665543
    from datetime import date as datetype
    today = datetype.today()
    ref = datetype(2026, 6, 29)
    estimated_id = BASE_ID + (today - ref).days
    
    for offset in [0, 1, -1, 2, -2, -3, 3, -4, 4, -5, 5, -6, 6, -7, 7]:
        aid = estimated_id + offset
        try:
            r = req.get(f'https://m.cnal.com/news/{aid}/', headers=headers, timeout=10)
            if r.status_code == 200 and '仓单日报' in r.text and '上海期货交易所' in r.text:
                # 验证日期（页面中可能有多个日期格式）
                dm = re.search(r'(\d{4})[年-](\d{1,2})[月-](\d{1,2})日', r.text[:1000])
                if dm:
                    y, m, d = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
                    page_date = f'{y:04d}-{m:02d}-{d:02d}'
                    if page_date == date_str:
                        return f'https://m.cnal.com/news/{aid}/'
                else:
                    # 无日期匹配时，任何仓单页面都可用
                    return f'https://m.cnal.com/news/{aid}/'
        except:
            pass
    
    return None


def collect_warehouse(date: Optional[str] = None) -> int:
    """从世铝网采集SHFE仓单日报。返回插入行数。"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    print(f'\n[仓单采集] {date} → 世铝网(cnal.com)')
    inserted = 0

    try:
        import requests
    except ImportError:
        print('  ✗ requests not installed. Run: pip install requests')
        return 0

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    # 自动发现URL
    warehouse_url = _discover_warehouse_url(session, date)

    if not warehouse_url:
        print('  ⚠ 未找到当日仓单页面URL，跳过')
        return 0

    print(f'  URL: {warehouse_url}')

    # 3. 获取并解析仓单页面
    try:
        r = requests.get(warehouse_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        if r.status_code != 200:
            print(f'  ✗ HTTP {r.status_code}')
            return 0
    except Exception as e:
        print(f'  ✗ 请求失败: {e}')
        return 0

    text = r.text
    con = get_db()

    for chinese_name, code in CNAL_VARIETY_MAP.items():
        start = text.find(f'>{chinese_name}<')
        if start < 0:
            continue

        # 确定section边界
        end_markers = [f'>{v}<' for v in CNAL_VARIETY_MAP.keys() if v != chinese_name]
        end_positions = [text.find(m, start + 10) for m in end_markers]
        end_positions = [p for p in end_positions if p > 0]
        section_end = min(end_positions) if end_positions else start + 8000
        section = text[start:section_end]

        # 提取"总计"行
        total_match = re.search(
            r'>总计</[^>]*>\s*<td>(\d+)</td>\s*<td>([+-]?\d+)</td>',
            section
        )
        total_lots = int(total_match.group(1)) if total_match else 0
        total_change = int(total_match.group(2)) if total_match else 0

        if total_lots > 0:
            # 写入总量
            con.execute('''
                INSERT INTO warehouse
                (exchange, symbol, trade_date, warehouse_name, registered_lots, net_change, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ['SHFE', code, date, '总计', total_lots, total_change, 'cnal.com'])
            inserted += 1

        # 提取明细行
        rows = re.findall(
            r'<tr[^>]*>\s*<td[^>]*>([^<\d][^<]*)</td>\s*<td>(\d+)</td>\s*<td>([+-]?\d+)</td>',
            section
        )
        for wh_name, lots_str, chg_str in rows:
            wh_name = wh_name.strip()
            lots = int(lots_str)
            chg = int(chg_str)
            if wh_name in _SKIP_NAMES or lots == 0:
                continue
            con.execute('''
                INSERT INTO warehouse
                (exchange, symbol, trade_date, warehouse_name, registered_lots, net_change, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ['SHFE', code, date, wh_name, lots, chg, 'cnal.com'])
            inserted += 1

        print(f'  ✓ {code}({chinese_name}): {total_lots}吨, Δ{total_change}')

    con.close()
    return inserted


# ==================== 持仓排名采集 ====================

def collect_oi_ranking(varieties: Optional[List[str]] = None, date: Optional[str] = None) -> int:
    """
    采集持仓排名。优先从 daily_data 的 OI 数据生成品种级排名摘要。
    会员级排名需通过 --oi-ranking-url 传入同花顺页面URL。
    Returns: number of rows inserted.
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    print(f'\n[持仓排名采集] {date} → daily_data OI 内部数据')
    inserted = 0
    con = get_db()

    # 从 daily_data 提取最新日期的 OI 排名
    latest_date = con.execute('SELECT MAX(trade_date) FROM daily_data WHERE open_interest > 0').fetchone()[0]
    if not latest_date:
        print('  ⚠ daily_data 中无 OI 数据')
        con.close()
        return 0

    rankings = con.execute(f'''
        SELECT symbol, exchange, open_interest, volume, close
        FROM daily_data 
        WHERE trade_date = '{latest_date}' AND open_interest > 0
        ORDER BY open_interest DESC
    ''').fetchall()

    if not rankings:
        print('  ⚠ 当日无 OI 数据')
        con.close()
        return 0

    # 写入 oi_ranking 表（品种级摘要）
    for rank, (sym, ex, oi, vol, close) in enumerate(rankings[:50], 1):
        try:
            con.execute('''
                INSERT INTO oi_ranking
                (exchange, symbol, trade_date, contract, rank, member, net_lots, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', [ex, sym, latest_date, 'MAIN', rank, f'品种OI排名', int(oi), 'daily_data'])
        except:
            pass
        inserted += 1

    con.close()
    print(f'  ✓ OI排名: {inserted} 品种 (数据来源: daily_data, 日期: {latest_date})')
    return inserted


def collect_oi_from_url(oi_url: str, date: Optional[str] = None) -> int:
    """从同花顺持仓分析页面采集会员级OI排名。"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    print(f'\n[持仓排名采集] {date} → 同花顺: {oi_url}')
    inserted = 0

    try:
        import requests
    except ImportError:
        print('  ✗ requests not installed')
        return 0

    try:
        r = requests.get(oi_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=15)
        if r.status_code != 200:
            print(f'  ✗ HTTP {r.status_code}')
            return 0
    except Exception as e:
        print(f'  ✗ {e}')
        return 0

    text = r.text

    # 提取品种
    sym_match = re.search(r'(\S+?)前20期商', text)
    symbol = sym_match.group(1) if sym_match else 'UNKNOWN'

    # 提取排名行: 会员名 + 净持仓
    patterns = [
        r'<td[^>]*>([^<]{2,10}(?:期货|证券)[^<]{0,5})</td>\s*<td[^>]*>([+-]?\d[\d,]*)</td>',
        r'>([^<]{2,8}期货)</td>\s*<td[^>]*>([+-]?[\d,]+)</td>',
    ]

    con = get_db()
    rank = 0
    for pattern in patterns:
        rows = re.findall(pattern, text)
        for member, net_str in rows:
            rank += 1
            try:
                net = int(net_str.replace(',', ''))
                con.execute('''
                    INSERT INTO oi_ranking
                    (exchange, symbol, trade_date, contract, rank, member, net_lots, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', ['SHFE', symbol, date, 'MAIN', rank, member.strip(), net, '10jqka'])
                inserted += 1
            except:
                pass
        if inserted > 0:
            break

    con.close()
    print(f'  ✓ {symbol}: {inserted} members')
    return inserted


# ==================== 期限结构采集 ====================

def collect_term_structure(varieties: Optional[List[str]] = None, date: Optional[str] = None) -> int:
    """
    Collect term structure data from MultiSourceAdapter.
    Stores in term_structure table.
    Returns: number of rows inserted.
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    if varieties is None:
        varieties = ['CU', 'AL', 'ZN', 'RB', 'HC', 'AU', 'AG',
                     'RU', 'SP', 'FU', 'BU', 'NI', 'SN', 'PB',
                     'M', 'Y', 'P', 'A', 'I', 'J', 'JM', 'FG', 'SA',
                     'TA', 'MA', 'SR', 'CF', 'SC', 'LU']

    print(f'\n[期限结构采集] {date}')

    try:
        from multi_source_adapter import MultiSourceAdapter
        adapter = MultiSourceAdapter()
    except Exception as e:
        print(f'  ⚠ MultiSourceAdapter不可用: {e}')
        return 0

    inserted = 0
    for symbol in varieties:
        try:
            result = adapter.get_term_structure(symbol)
            if not result or not result.get('contracts'):
                continue

            con = get_db()
            for c in result.get('contracts', []):
                month = c.get('month', '')
                price = c.get('price', 0)
                if month and price > 0:
                    con.execute('''
                        INSERT INTO term_structure
                        (exchange, symbol, trade_date, contract_month, close_price, source)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', [result.get('exchange', 'UNKNOWN'), symbol, date,
                          month, price, result.get('data_source', 'adapter')])
                    inserted += 1

            con.close()
            if inserted > 0:
                print(f'  ✓ {symbol}: {len(result["contracts"])} contracts')

        except Exception as e:
            pass  # silent skip for unavailable

    return inserted


# ==================== 资讯采集 ====================

def collect_news(varieties: Optional[List[str]] = None, date: Optional[str] = None) -> int:
    """
    Collect industry news from WebSearch and store in futures_news.
    Note: This requires WebSearch capabilities at runtime.
    Returns: number of rows inserted.
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    print(f'\n[资讯采集] {date}')
    print('  ⚠ 资讯采集需要在Agent上下文中通过WebSearch实现')
    print('  → 自动化调用时由辩论Agent补充')
    return 0


# ==================== 主入口 ====================

def collect_all(date: Optional[str] = None, warehouse: bool = True,
                oi_ranking: bool = True, term_structure: bool = True,
                news: bool = False) -> Dict[str, Any]:
    """
    Collect all fundamental data types.
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    results = {
        'date': date,
        'warehouse': 0,
        'oi_ranking': 0,
        'term_structure': 0,
        'futures_news': 0,
        'errors': [],
    }

    print(f'{"="*60}')
    print(f'基本面数据采集 — {date}')
    print(f'{"="*60}')

    if warehouse:
        try:
            results['warehouse'] = collect_warehouse(date)
        except Exception as e:
            results['errors'].append(f'warehouse: {e}')

    if oi_ranking:
        try:
            results['oi_ranking'] = collect_oi_ranking(date=date)
        except Exception as e:
            results['errors'].append(f'oi_ranking: {e}')

    if term_structure:
        try:
            results['term_structure'] = collect_term_structure(date=date)
        except Exception as e:
            results['errors'].append(f'term_structure: {e}')

    if news:
        try:
            results['futures_news'] = collect_news(date=date)
        except Exception as e:
            results['errors'].append(f'news: {e}')

    print(f'\n{"="*60}')
    print(f'采集完成: 仓单={results["warehouse"]}, 持仓={results["oi_ranking"]}, '
          f'期限结构={results["term_structure"]}, 资讯={results["futures_news"]}')
    if results['errors']:
        print(f'错误: {results["errors"]}')
    print(f'{"="*60}')

    return results


def collect_warehouse_from_url(warehouse_url: str, date: Optional[str] = None) -> int:
    """从指定世铝网URL采集仓单数据。"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    print(f'\n[仓单采集] {date} → {warehouse_url}')
    inserted = 0

    try:
        import requests
    except ImportError:
        print('  ✗ requests not installed')
        return 0

    try:
        r = requests.get(warehouse_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=15)
        if r.status_code != 200:
            print(f'  ✗ HTTP {r.status_code}')
            return 0
    except Exception as e:
        print(f'  ✗ 请求失败: {e}')
        return 0

    text = r.text

    # Extract date from page content
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text[:500])
    if date_match:
        page_date = date_match.group(1)
        print(f'  页面日期: {page_date}')
        date = page_date

    con = get_db()

    for chinese_name, code in CNAL_VARIETY_MAP.items():
        start = text.find(f'>{chinese_name}<')
        if start < 0:
            continue

        end_markers = [f'>{v}<' for v in CNAL_VARIETY_MAP.keys() if v != chinese_name]
        end_positions = [text.find(m, start + 10) for m in end_markers]
        end_positions = [p for p in end_positions if p > 0]
        section_end = min(end_positions) if end_positions else start + 8000
        section = text[start:section_end]

        # 总计行
        total_match = re.search(
            r'>总计</[^>]*>\s*<td>(\d+)</td>\s*<td>([+-]?\d+)</td>', section
        )
        total_lots = int(total_match.group(1)) if total_match else 0
        total_change = int(total_match.group(2)) if total_match else 0

        if total_lots > 0:
            con.execute('''
                INSERT INTO warehouse
                (exchange, symbol, trade_date, warehouse_name, registered_lots, net_change, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ['SHFE', code, date, '总计', total_lots, total_change, 'cnal.com'])
            inserted += 1

        # 明细行
        rows = re.findall(
            r'<tr[^>]*>\s*<td[^>]*>([^<\d][^<]*)</td>\s*<td>(\d+)</td>\s*<td>([+-]?\d+)</td>',
            section
        )
        for wh_name, lots_str, chg_str in rows:
            wh_name = wh_name.strip()
            lots = int(lots_str)
            chg = int(chg_str)
            if wh_name in _SKIP_NAMES:
                continue
            con.execute('''
                INSERT INTO warehouse
                (exchange, symbol, trade_date, warehouse_name, registered_lots, net_change, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ['SHFE', code, date, wh_name, lots, chg, 'cnal.com'])
            inserted += 1

        print(f'  ✓ {code}({chinese_name}): {total_lots}吨, Δ{total_change}')

    con.close()
    return inserted


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='基本面数据采集')
    parser.add_argument('--warehouse', action='store_true', help='仅采集仓单')
    parser.add_argument('--warehouse-url', type=str, default=None,
                        help='仓单页面URL(世铝网)')
    parser.add_argument('--oi-ranking', action='store_true', help='仅采集持仓排名')
    parser.add_argument('--oi-ranking-url', type=str, default=None, help='同花顺OI排名页面URL')
    parser.add_argument('--term-structure', action='store_true', help='仅采集期限结构')
    parser.add_argument('--news', action='store_true', help='采集资讯')
    parser.add_argument('--date', type=str, default=None, help='日期(YYYY-MM-DD)')

    args = parser.parse_args()
    all_default = not any([args.warehouse, args.oi_ranking, args.term_structure, args.news])

    if args.warehouse_url:
        n = collect_warehouse_from_url(args.warehouse_url, args.date)
        print(f'\n仓单采集完成: {n} 行')
        if not (args.oi_ranking or args.term_structure or args.news or all_default):
            sys.exit(0)

    if args.oi_ranking_url:
        n = collect_oi_from_url(args.oi_ranking_url, args.date)
        print(f'\nOI排名采集完成: {n} 行')
        if not (args.warehouse or args.term_structure or args.news or all_default):
            sys.exit(0)

    collect_all(
        date=args.date,
        warehouse=args.warehouse or (all_default and not args.warehouse_url),
        oi_ranking=args.oi_ranking or all_default,
        term_structure=args.term_structure or all_default,
        news=args.news or all_default,
    )
