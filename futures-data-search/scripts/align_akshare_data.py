#!/usr/bin/env python3
"""
对齐清洗 AKShare 期货日线数据 (v2 - 修正版)
==============================================
1. 重新下载 AKShare 品种（覆盖损坏数据）
2. 前复权对齐：在换月缺口处反向调整历史价格
3. NULL 语义统一
4. data_source 标记

前复权算法（正确版）：
- 从最新日期往回遍历
- 遇到换月缺口（>3%）：adjust = close_after_gap / close_before_gap
- 缺口之前所有历史 OHLC 乘以 adjust
"""

import sys
import io
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import duckdb
import pandas as pd
import numpy as np

DB_PATH = Path.home() / "Documents" / "WorkBuddy" / "futures_data.duckdb"
GAP_THRESHOLD = 0.03  # 3% = contract rollover

# 34 AKShare varieties
AKS_VARIETIES = [
    'BC','IC','IF','IH','IM','JR','LC','LR','LU','NR',
    'OI','PD','PF','PK','PM','PR','PS','PT','PX','RI',
    'RM','RS','SC','SF','SI','SM','SR','T','TF','TL',
    'TS','UR','WH','ZC',
]


def download_akshare(variety: str) -> pd.DataFrame:
    """Download fresh data from AKShare."""
    import akshare as ak
    symbol = variety + "0"
    df = ak.futures_main_sina(symbol=symbol)
    if df is None or len(df) == 0:
        return pd.DataFrame()
    
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
                "data_source": "akshare",
            })
        except (ValueError, TypeError):
            continue
    
    df_out = pd.DataFrame(records)
    if len(df_out) > 0:
        df_out = df_out.sort_values("trade_date").reset_index(drop=True)
    return df_out


def apply_forward_adjustment(df: pd.DataFrame) -> tuple:
    """
    Forward adjustment (前复权) for futures main continuous:
    Work backwards from latest date.
    At each rollover gap, adjust all OLDER prices by the gap ratio.
    """
    if len(df) < 2:
        return df, False
    
    df = df.copy()
    df = df.reset_index(drop=True)
    
    # Work backwards: identify rollover gaps
    # Gap detection needs both sides to have valid prices
    df['next_close'] = df['close'].shift(-1)
    
    adjusted = False
    gaps_found = 0
    
    # Iterate from newest-1 to oldest
    for i in range(len(df) - 2, -1, -1):
        this_close = df.iloc[i]['close']
        next_close = df.iloc[i + 1]['close']
        
        if (this_close and this_close > 0 and 
            next_close and next_close > 0):
            gap = abs(next_close / this_close - 1)
            if gap > GAP_THRESHOLD:
                # Rollover detected: adjust all prices BEFORE this gap
                ratio = next_close / this_close
                gaps_found += 1
                
                for col in ['open', 'high', 'low', 'close']:
                    for j in range(0, i + 1):  # rows 0..i inclusive
                        val = df.iloc[j][col]
                        if val is not None and not pd.isna(val) and val > 0:
                            df.at[j, col] = round(float(val) * ratio, 4)
                
                adjusted = True
    
    return df, adjusted


def null_standardize(df: pd.DataFrame) -> pd.DataFrame:
    """volume=0 with invalid close -> NULL"""
    df = df.copy()
    mask = (
        df['volume'].notna() & 
        (df['volume'].astype(float) == 0) &
        (df['close'].isna() | (df['close'].astype(float) == 0))
    )
    df.loc[mask, 'volume'] = None
    return df


def save_to_db(conn, variety: str, df: pd.DataFrame):
    conn.execute("DELETE FROM daily_kline WHERE variety = ?", [variety])
    
    rows = []
    for _, r in df.iterrows():
        rows.append((
            variety,
            str(r['trade_date']),
            _sf(r['open']),
            _sf(r['high']),
            _sf(r['low']),
            _sf(r['close']),
            _si(r['volume']),
            _sf(r['amount']),
            _sf(r['amplitude']),
            _sf(r['change_pct']),
            _sf(r['change_val']),
            _sf(r['turnover']),
        ))
    
    conn.executemany("""
        INSERT INTO daily_kline
        (variety, trade_date, open, high, low, close, volume, 
         amount, amplitude, change_pct, change_val, turnover)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    
    # Fix data_source
    conn.execute(
        "UPDATE daily_kline SET data_source = 'akshare' WHERE variety = ?",
        [variety]
    )


def _sf(val):
    if val is None: return None
    try:
        f = float(val)
        return None if pd.isna(f) or np.isinf(f) else f
    except: return None


def _si(val):
    if val is None: return None
    try:
        i = int(val)
        return None if pd.isna(i) else i
    except: return None


def main():
    conn = duckdb.connect(str(DB_PATH))
    
    print(f"Step 1: Re-downloading {len(AKS_VARIETIES)} AKShare varieties...\n")
    
    success = 0
    fail = 0
    adj_count = 0
    
    for i, variety in enumerate(AKS_VARIETIES, 1):
        print(f"  [{i:2d}/{len(AKS_VARIETIES)}] {variety:<4} ... ", end="", flush=True)
        
        try:
            df = download_akshare(variety)
            if len(df) == 0:
                print("NO DATA")
                fail += 1
                continue
        except Exception as e:
            print(f"ERROR: {e}")
            fail += 1
            continue
        
        # Forward adjustment
        df, adjusted = apply_forward_adjustment(df)
        
        # NULL standardization
        df = null_standardize(df)
        
        # Save
        save_to_db(conn, variety, df)
        
        status = "adjusted" if adjusted else "raw"
        print(f"OK {len(df):>6,} [{status}]")
        success += 1
        if adjusted:
            adj_count += 1
    
    print(f"\nStep 2: Tagging EastMoney varieties...")
    conn.execute("""
        UPDATE daily_kline 
        SET data_source = 'eastmoney' 
        WHERE data_source IS NULL OR data_source = ''
    """)
    
    # Verify
    print(f"\n{'='*60}")
    print(f"Alignment v2 complete!")
    print(f"  Downloaded: {success}/{len(AKS_VARIETIES)}")
    print(f"  Forward-adjusted: {adj_count}")
    
    src_stats = conn.execute("""
        SELECT data_source, COUNT(DISTINCT variety), COUNT(*) 
        FROM daily_kline GROUP BY data_source ORDER BY data_source
    """).fetchall()
    
    print(f"\n  Source breakdown:")
    for src, vc, rc in src_stats:
        print(f"    {src}: {vc} varieties, {rc:,} records")
    
    total_var = conn.execute("SELECT COUNT(DISTINCT variety) FROM daily_kline").fetchone()[0]
    total_rec = conn.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
    print(f"\n  Total: {total_var} varieties, {total_rec:,} records")
    
    # Spot check
    print(f"\n  Spot check (last 3 days):")
    for v in ['SC', 'IF', 'SR', 'UR']:
        rows = conn.execute(
            "SELECT trade_date, open, close, volume, data_source FROM daily_kline "
            "WHERE variety = ? ORDER BY trade_date DESC LIMIT 3",
            [v]
        ).fetchall()
        print(f"    {v} [{rows[0][4] if rows else '?'}]:")
        for r in rows:
            print(f"      {r[0]}  O={r[1]}  C={r[2]}  V={r[3]}")
    
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
