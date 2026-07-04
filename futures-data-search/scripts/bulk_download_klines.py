#!/usr/bin/env python3
"""
批量下载全部期货品种近5年日线数据，存入DuckDB
================================================
数据源：东方财富 push2his API（主力连续合约，前复权）
存储：DuckDB daily_kline 表
覆盖：SHFE/DCE/CZCE/GFEX/INE/CFFEX 全部品种

用法：python bulk_download_klines.py [--db-path PATH] [--years 5]
"""

import json
import time
import sys
import io
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# -- DuckDB --
try:
    import duckdb
except ImportError:
    print("[ERROR] duckdb not installed. Run: pip install duckdb")
    sys.exit(1)

# -- Config --
DEFAULT_DB_PATH = Path.home() / "Documents" / "WorkBuddy" / "futures_data.duckdb"
DEFAULT_YEARS = 5

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# All varieties with EastMoney exchange codes
# Exchange codes: 113=SHFE, 114=DCE, 115=CZCE, 225=GFEX, 142=INE, 220=CFFEX
ALL_VARIETIES = {
    # SHFE (113)
    "CU": 113, "AL": 113, "ZN": 113, "PB": 113, "NI": 113, "SN": 113,
    "AU": 113, "AG": 113, "RB": 113, "HC": 113, "SS": 113, "RU": 113,
    "BR": 113, "FU": 113, "BU": 113, "WR": 113, "SP": 113, "AO": 113,
    "AD": 113, "OP": 113,
    # DCE (114)
    "A": 114, "B": 114, "M": 114, "Y": 114, "P": 114, "C": 114, "CS": 114,
    "I": 114, "J": 114, "JM": 114, "L": 114, "V": 114, "PP": 114, "EG": 114,
    "EB": 114, "PG": 114, "JD": 114, "LH": 114, "RR": 114, "BB": 114, "FB": 114, "LG": 114,
    # CZCE (115)
    "AP": 115, "CF": 115, "CY": 115, "CJ": 115, "FG": 115, "SA": 115, "SH": 115,
    "MA": 115, "TA": 115, "UR": 115, "PF": 115, "PR": 115, "PX": 115, "PK": 115,
    "OI": 115, "RM": 115, "RS": 115, "SR": 115, "WH": 115, "PM": 115,
    "SM": 115, "SF": 115, "ZC": 115, "JR": 115, "LR": 115, "RI": 115,
    # GFEX (225)
    "SI": 225, "LC": 225, "PS": 225, "PT": 225, "PD": 225,
    # INE (142)
    "SC": 142, "LU": 142, "NR": 142, "BC": 142,
    # CFFEX (220)
    "IF": 220, "IC": 220, "IM": 220, "IH": 220,
    "TS": 220, "TF": 220, "T": 220, "TL": 220,
}

# Chinese names
VARIETY_NAMES = {
    "CU": "沪铜", "AL": "沪铝", "ZN": "沪锌", "PB": "沪铅", "NI": "沪镍", "SN": "沪锡",
    "AU": "沪金", "AG": "沪银", "RB": "螺纹钢", "HC": "热卷", "SS": "不锈钢",
    "RU": "橡胶", "BR": "合成橡胶", "FU": "燃油", "BU": "沥青", "WR": "线材",
    "SP": "纸浆", "AO": "氧化铝", "AD": "铸造铝合金", "OP": "胶版印刷纸",
    "A": "豆一", "B": "豆二", "M": "豆粕", "Y": "豆油", "P": "棕榈油",
    "C": "玉米", "CS": "淀粉", "I": "铁矿石", "J": "焦炭", "JM": "焦煤",
    "L": "塑料", "V": "PVC", "PP": "聚丙烯", "EG": "乙二醇", "EB": "苯乙烯",
    "PG": "LPG", "JD": "鸡蛋", "LH": "生猪", "RR": "粳米", "BB": "胶合板",
    "FB": "纤维板", "LG": "原木",
    "AP": "苹果", "CF": "棉花", "CY": "棉纱", "CJ": "红枣", "FG": "玻璃",
    "SA": "纯碱", "SH": "烧碱", "MA": "甲醇", "TA": "PTA", "UR": "尿素",
    "PF": "短纤", "PR": "瓶片", "PX": "对二甲苯", "PK": "花生",
    "OI": "菜油", "RM": "菜粕", "RS": "菜籽", "SR": "白糖",
    "WH": "强麦", "PM": "普麦", "SM": "锰硅", "SF": "硅铁", "ZC": "动力煤",
    "JR": "粳稻", "LR": "晚籼稻", "RI": "早籼稻",
    "SI": "工业硅", "LC": "碳酸锂", "PS": "多晶硅", "PT": "铂", "PD": "钯",
    "SC": "原油", "LU": "低硫燃油", "NR": "20号胶", "BC": "国际铜",
    "IF": "沪深300", "IC": "中证500", "IM": "中证1000", "IH": "上证50",
    "TS": "2年国债", "TF": "5年国债", "T": "10年国债", "TL": "30年国债",
}


def init_database(db_path: Path):
    """Initialize DuckDB and daily_kline table"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_kline (
            variety     VARCHAR NOT NULL,
            trade_date  DATE NOT NULL,
            open        DOUBLE,
            high        DOUBLE,
            low         DOUBLE,
            close       DOUBLE,
            volume      BIGINT,
            amount      DOUBLE,
            amplitude   DOUBLE,
            change_pct  DOUBLE,
            change_val  DOUBLE,
            turnover    DOUBLE,
            data_source VARCHAR DEFAULT 'eastmoney',
            fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (variety, trade_date)
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_kline_variety ON daily_kline(variety)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kline_date ON daily_kline(trade_date)")

    print(f"[DB] Database ready: {db_path}")
    return conn


def fetch_kline_eastmoney(variety: str, exchange_code: int, beg: str, end: str) -> list:
    """Try EastMoney push2his API first."""
    secid = f"{exchange_code}.{variety}m"
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}"
        "&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        f"&klt=101&fqt=1&beg={beg}&end={end}"
    )
    req = Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://quote.eastmoney.com/",
        "Accept": "*/*",
    })
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
    except Exception:
        return []

    resp_data = data.get("data")
    if resp_data is None:
        return []
    klines = resp_data.get("klines", [])
    return _parse_eastmoney_klines(klines)


def _parse_eastmoney_klines(klines: list) -> list:
    """Parse EastMoney kline strings to records."""
    records = []
    for kline_str in klines:
        parts = kline_str.split(",")
        if len(parts) < 6:
            continue
        try:
            record = {
                "trade_date": parts[0],
                "open": float(parts[1]) if parts[1] != "-" else None,
                "close": float(parts[2]) if parts[2] != "-" else None,
                "high": float(parts[3]) if parts[3] != "-" else None,
                "low": float(parts[4]) if parts[4] != "-" else None,
                "volume": int(float(parts[5])) if parts[5] != "-" else 0,
                "amount": float(parts[6]) if len(parts) > 6 and parts[6] != "-" else None,
                "amplitude": float(parts[7]) if len(parts) > 7 and parts[7] != "-" else None,
                "change_pct": float(parts[8]) if len(parts) > 8 and parts[8] != "-" else None,
                "change_val": float(parts[9]) if len(parts) > 9 and parts[9] != "-" else None,
                "turnover": float(parts[10]) if len(parts) > 10 and parts[10] != "-" else None,
            }
            records.append(record)
        except (ValueError, IndexError):
            continue
    return records


def fetch_kline_akshare(variety: str) -> list:
    """Fallback: use AKShare futures_main_sina."""
    try:
        import akshare as ak
        symbol = variety.upper() + "0"
        df = ak.futures_main_sina(symbol=symbol)
        if df is None or len(df) == 0:
            return []
        records = []
        for _, row in df.iterrows():
            try:
                date_val = str(row.get("日期", row.get("date", "")))
                records.append({
                    "trade_date": date_val,
                    "open": float(row.get("开盘价", row.get("open", 0)) or 0),
                    "high": float(row.get("最高价", row.get("high", 0)) or 0),
                    "low": float(row.get("最低价", row.get("low", 0)) or 0),
                    "close": float(row.get("收盘价", row.get("close", 0)) or 0),
                    "volume": int(float(row.get("成交量", row.get("volume", 0)) or 0)),
                    "amount": None,
                    "amplitude": None,
                    "change_pct": None,
                    "change_val": None,
                    "turnover": None,
                })
            except (ValueError, TypeError):
                continue
        return records
    except Exception as e:
        return []


def fetch_kline(variety: str, exchange_code: int, beg: str, end: str) -> list:
    """
    Fetch main-contract daily kline. Tries EastMoney first, falls back to AKShare.
    """
    # Try EastMoney
    records = fetch_kline_eastmoney(variety, exchange_code, beg, end)
    if records:
        return records
    
    # Fallback: AKShare
    records = fetch_kline_akshare(variety)
    if records:
        return records
    
    return []


def save_to_db(conn, variety: str, records: list) -> int:
    """Batch insert into DuckDB (idempotent: delete old data first)"""
    if not records:
        return 0

    conn.execute("DELETE FROM daily_kline WHERE variety = ?", [variety])

    rows = []
    for r in records:
        rows.append((
            variety,
            r["trade_date"],
            r.get("open"),
            r.get("high"),
            r.get("low"),
            r.get("close"),
            r.get("volume", 0),
            r.get("amount"),
            r.get("amplitude"),
            r.get("change_pct"),
            r.get("change_val"),
            r.get("turnover"),
        ))

    conn.executemany("""
        INSERT INTO daily_kline
        (variety, trade_date, open, high, low, close, volume, amount, amplitude, change_pct, change_val, turnover)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Batch download futures daily kline to DuckDB")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB_PATH),
                        help=f"DuckDB path (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS,
                        help=f"Years of history (default: {DEFAULT_YEARS})")
    parser.add_argument("--variety", type=str, default=None,
                        help="Download single variety only (e.g. CU)")
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="Sleep seconds between varieties (default: 0.5)")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    years = args.years

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=years * 365 + 30)).strftime("%Y%m%d")

    conn = init_database(db_path)

    if args.variety:
        v = args.variety.upper()
        if v not in ALL_VARIETIES:
            print(f"[ERROR] Unknown variety: {args.variety}")
            conn.close()
            sys.exit(1)
        varieties = {v: ALL_VARIETIES[v]}
    else:
        varieties = ALL_VARIETIES

    total = len(varieties)
    success_count = 0
    fail_count = 0
    total_records = 0
    start_time = datetime.now()

    print(f"\n{'='*70}")
    print(f"  Batch Download Futures Daily Kline")
    print(f"  Varieties: {total}   Range: {start_date} ~ {end_date}")
    print(f"  Database: {db_path}")
    print(f"{'='*70}\n")

    for i, (variety, exchange_code) in enumerate(varieties.items(), 1):
        name = VARIETY_NAMES.get(variety, variety)
        print(f"[{i:3d}/{total}] {variety:<4} ({name:<8}) ... ", end="", flush=True)

        try:
            records = fetch_kline(variety, exchange_code, start_date, end_date)
            if records:
                n = save_to_db(conn, variety, records)
                # EastMoney API returns newest first
                first_date = records[-1]["trade_date"]
                last_date = records[0]["trade_date"]
                print(f"OK {n:>5d} records [{first_date} ~ {last_date}]")
                success_count += 1
                total_records += n
            else:
                print("NO DATA")
                fail_count += 1
        except Exception as e:
            print(f"FAILED: {e}")
            fail_count += 1

        if i < total:
            time.sleep(args.sleep)

    elapsed = (datetime.now() - start_time).total_seconds()

    # Summary stats
    stats = conn.execute("""
        SELECT variety, COUNT(*) as cnt, MIN(trade_date) as first_dt, MAX(trade_date) as last_dt
        FROM daily_kline
        GROUP BY variety
        ORDER BY variety
    """).fetchall()

    print(f"\n{'='*70}")
    print(f"  Download Complete!")
    print(f"  Success: {success_count}/{total}   Failed: {fail_count}")
    print(f"  Total records: {total_records:,}   Time: {elapsed:.0f}s")
    print(f"{'='*70}")

    print(f"\n  Variety Summary:")
    print(f"  {'Var':<6} {'Name':<10} {'Records':>7}  {'First':>12}  {'Last':>12}")
    print(f"  {'-'*55}")
    for row in stats:
        v, cnt, fd, ld = row
        name = VARIETY_NAMES.get(v, v)
        print(f"  {v:<6} {name:<10} {cnt:>7,}  {str(fd):>12}  {str(ld):>12}")

    db_size = db_path.stat().st_size if db_path.exists() else 0
    if db_size > 1024 * 1024:
        print(f"\n  Database file: {db_size / 1024 / 1024:.1f} MB")
    else:
        print(f"\n  Database file: {db_size / 1024:.1f} KB")

    conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
