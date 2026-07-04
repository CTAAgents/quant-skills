#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原油系产业链数据采集脚本 — TqSdk 实盘K线 → DuckDB
支持原油→沥青→燃料油两层产业链（上游原油+下游并列产品）

完整流水线：TqSdk → DuckDB → Ta-Lib → 图表 → 报告
本脚本负责第一环节：TqSdk → DuckDB，不产生任何中间CSV文件。

用法：
    python fetch_and_store.py                # 获取全部品种，写入DuckDB
    python fetch_and_store.py --symbols SC BU FU LU # 仅获取指定品种
    python fetch_and_store.py --days 120      # 获取120个交易日K线
"""

import argparse
import json
import logging
import os
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(__file__).parent.parent / "data" / "crude_oil_chain.duckdb"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

TQSDK_SYMBOL_MAP = {
    "SC": "KQ.m@INE.sc",   # SC原油主力
    "BU": "KQ.m@SHFE.bu",  # BU沥青主力
    "FU": "KQ.m@SHFE.fu",  # FU高硫燃料油
    "LU": "KQ.m@INE.lu",   # LU低硫燃料油
    "PG": "KQ.m@DCE.pg",   # PG液化石油气（大连商品交易所DCE，v2.13.0修正）
}

def get_tq_credentials() -> tuple[str, str]:
    """从环境变量获取TqSdk凭证，支持多种命名：TQSDK_USERNAME/TQ_USER、TQSDK_PASSWORD/TQ_PASSWORD"""
    # 优先使用 TQSDK_* 变量
    username = os.environ.get("TQSDK_USERNAME") or os.environ.get("TQ_USER", "")
    password = os.environ.get("TQSDK_PASSWORD") or os.environ.get("TQ_PASSWORD", "")
    if not username or not password:
        raise ValueError("环境变量 TQSDK_USERNAME/TQ_USER 或 TQSDK_PASSWORD/TQ_PASSWORD 未设置")
    return username, password


def download_kline_data(symbols: list[str], days: int = 756) -> dict[str, pd.DataFrame]:
    """通过TqSdk get_kline_serial获取历史K线数据

    默认获取756个交易日（约3年），满足分位计算所需的历史深度。
    免费账户支持最近约2000根K线，付费账户无限制。
    """
    from tqsdk import TqApi, TqAuth
    from datetime import timezone

    username, password = get_tq_credentials()
    auth = TqAuth(username, password)

    tq_symbols = {}
    for symbol_key in symbols:
        tq_sym = TQSDK_SYMBOL_MAP.get(symbol_key)
        if not tq_sym:
            logger.warning(f"未知品种: {symbol_key}, 跳过")
            continue
        tq_symbols[symbol_key] = tq_sym

    if not tq_symbols:
        return {}

    # 获取足够的历史K线：请求天数 + 缓冲，上限2000根（TqSdk免费账户限制）
    data_length = min(days + 50, 2000)
    logger.info(f"使用 get_kline_serial 获取最近 {data_length} 根日线K线（目标{days}天历史）")

    api = TqApi(auth=auth)
    try:
        kline_refs = {}
        for symbol_key, tq_symbol in tq_symbols.items():
            logger.info(f"  订阅 {symbol_key}({tq_symbol}) 日线K线")
            kline_refs[symbol_key] = api.get_kline_serial(tq_symbol, 86400, data_length)

        import time
        deadline = time.time() + 30
        api.wait_update(deadline=deadline)

        results = {}
        for symbol_key, klines in kline_refs.items():
            try:
                df = pd.DataFrame(klines)
                if df.empty:
                    logger.warning(f"  ⚠ {symbol_key}: 无K线数据")
                    continue

                col_map = {}
                for col in df.columns:
                    cl = col.lower().strip()
                    if cl in ("datetime", "date", "time"):
                        col_map[col] = "date"
                    elif cl == "open":
                        col_map[col] = "open"
                    elif cl == "high":
                        col_map[col] = "high"
                    elif cl == "low":
                        col_map[col] = "low"
                    elif cl == "close":
                        col_map[col] = "close"
                    elif cl in ("vol", "volume"):
                        col_map[col] = "volume"
                if col_map:
                    df = df.rename(columns=col_map)

                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"], unit="ns", origin="unix").dt.strftime("%Y-%m-%d")

                results[symbol_key] = df
                logger.info(f"  ✅ {symbol_key}: {len(df)} 条K线, 最新收盘: {df['close'].iloc[-1]}")
            except Exception as e:
                logger.error(f"  ❌ {symbol_key}数据处理失败: {e}")
    finally:
        api.close()
    return results


def fetch_realtime_quotes(symbols: list[str]) -> dict[str, dict]:
    """通过TqSdk获取实时行情快照"""
    from tqsdk import TqApi, TqAuth

    username, password = get_tq_credentials()
    auth = TqAuth(username, password)

    try:
        api = TqApi(auth=auth)
        quotes = {}
        for symbol_key in symbols:
            tq_symbol = TQSDK_SYMBOL_MAP.get(symbol_key)
            if not tq_symbol:
                continue
            quote = api.get_quote(tq_symbol)
            quotes[symbol_key] = quote

        api.wait_update()

        results = {}
        for symbol_key, quote in quotes.items():
            try:
                results[symbol_key] = {
                    "last_price": float(quote.last_price) if quote.last_price == quote.last_price else None,
                    "pre_close": float(quote.pre_close) if hasattr(quote, 'pre_close') and quote.pre_close == quote.pre_close else None,
                    "open": float(quote.open) if hasattr(quote, 'open') and quote.open == quote.open else None,
                    "high": float(quote.highest) if hasattr(quote, 'highest') and quote.highest == quote.highest else None,
                    "low": float(quote.lowest) if hasattr(quote, 'lowest') and quote.lowest == quote.lowest else None,
                    "volume": int(quote.volume) if hasattr(quote, 'volume') and quote.volume == quote.volume else None,
                    "open_interest": int(quote.open_interest) if hasattr(quote, 'open_interest') and quote.open_interest == quote.open_interest else None,
                    "datetime": str(quote.datetime) if hasattr(quote, 'datetime') else None,
                }
                logger.info(f"  ✅ {symbol_key}: {results[symbol_key]['last_price']}")
            except Exception as e:
                logger.warning(f"  ⚠ {symbol_key}字段读取失败: {e}")

        api.close()
        return results
    except Exception as e:
        logger.error(f"实时行情获取失败: {e}")
        return {}


def store_to_duckdb(kline_data: dict[str, pd.DataFrame], quotes: dict[str, dict] = None):
    """将数据存入DuckDB"""
    import duckdb

    conn = duckdb.connect(str(DB_PATH))
    try:
        for symbol_key, df in kline_data.items():
            table_name = f"kline_{symbol_key.lower()}"
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            logger.info(f"  ✅ {table_name}: {count} 条记录已入库")

        if quotes:
            quote_records = []
            for symbol_key, q in quotes.items():
                record = {"symbol": symbol_key}
                record.update(q)
                quote_records.append(record)
            if quote_records:
                quote_df = pd.DataFrame(quote_records)
                conn.execute("DROP TABLE IF EXISTS realtime_quotes")
                conn.execute("CREATE TABLE realtime_quotes AS SELECT * FROM quote_df")
                logger.info(f"  ✅ realtime_quotes: {len(quote_records)} 条记录已入库")

        tables = conn.execute("SHOW TABLES").fetchall()
        logger.info(f"\nDuckDB数据库: {DB_PATH}")
        logger.info(f"表列表: {[t[0] for t in tables]}")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="能源产业链历史数据获取+DuckDB存储")
    parser.add_argument("--symbols", nargs="+", default=["SC", "BU", "FU", "LU"],
                        help="品种列表 (默认: SC BU FU LU)")
    parser.add_argument("--days", type=int, default=756, help="获取天数 (默认: 756，约3年)")
    parser.add_argument("--skip-realtime", action="store_true", help="跳过实时行情获取")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("能源产业链历史数据获取 + DuckDB存储")
    logger.info("=" * 60)
    logger.info(f"品种: {args.symbols}")
    logger.info(f"天数: {args.days}")
    logger.info(f"数据库: {DB_PATH}")

    logger.info("\n--- 第1步：下载历史K线数据 ---")
    kline_data = download_kline_data(args.symbols, args.days)

    quotes = {}
    if not args.skip_realtime:
        logger.info("\n--- 第2步：获取实时行情快照 ---")
        try:
            quotes = fetch_realtime_quotes(args.symbols)
        except Exception as e:
            logger.warning(f"实时行情获取失败（非交易时段）: {e}")

    logger.info("\n--- 第3步：存入DuckDB ---")
    store_to_duckdb(kline_data, quotes)

    print(f"\n__DONE__:{json.dumps({'db_path': str(DB_PATH), 'symbols': list(kline_data.keys()), 'kline_counts': {k: len(v) for k, v in kline_data.items()}})}")


if __name__ == "__main__":
    main()
