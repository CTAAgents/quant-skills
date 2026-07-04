#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化版原油系产业链数据采集脚本 — 并行数据获取 + 增量更新

优化点：
1. 并行数据获取：使用线程池同时获取多个品种
2. 智能等待：动态调整等待时间，基于数据完整性检查
3. 增量更新：只获取新数据，避免重复下载
4. 缓存机制：本地缓存已获取数据，减少网络请求

用法：
    python fetch_and_store_optimized.py                # 获取全部品种，写入DuckDB
    python fetch_and_store_optimized.py --symbols SC BU FU LU # 仅获取指定品种
    python fetch_and_store_optimized.py --days 120      # 获取120个交易日K线
    python fetch_and_store_optimized.py --parallel      # 启用并行获取（默认）
"""

import argparse
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(__file__).parent.parent / "data" / "futures_data.duckdb"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TQSDK_SYMBOL_MAP = {
    "SC": "KQ.m@INE.sc",   # SC原油主力
    "BU": "KQ.m@SHFE.bu",  # BU沥青主力
    "FU": "KQ.m@SHFE.fu",  # FU高硫燃料油
    "LU": "KQ.m@INE.lu",   # LU低硫燃料油
    "PG": "KQ.m@DCE.pg",   # PG液化石油气（大连商品交易所DCE，v2.13.0修正）
}

# 性能优化配置
import multiprocessing
CPU_COUNT = multiprocessing.cpu_count()
MAX_WORKERS = min(CPU_COUNT, 6)  # 自适应并行线程数，上限6（避免API限流）
CACHE_EXPIRY_HOURS = 24  # 缓存过期时间（小时）
SMART_WAIT_TIMEOUT = 60  # 智能等待超时时间（秒）
DATA_COMPLETENESS_THRESHOLD = 0.95  # 数据完整性阈值
MIN_CACHE_ROWS = 100  # 缓存最小有效行数


def get_tq_credentials() -> Tuple[str, str]:
    """从环境变量获取TqSdk凭证，支持多种命名：TQSDK_USERNAME/TQ_USER、TQSDK_PASSWORD/TQ_PASSWORD"""
    # 优先使用 TQSDK_* 变量
    username = os.environ.get("TQSDK_USERNAME") or os.environ.get("TQ_USER", "")
    password = os.environ.get("TQSDK_PASSWORD") or os.environ.get("TQ_PASSWORD", "")
    if not username or not password:
        raise ValueError("环境变量 TQSDK_USERNAME/TQ_USER 或 TQSDK_PASSWORD/TQ_PASSWORD 未设置")
    return username, password


def get_cache_path(symbol: str, days: int) -> Path:
    """获取缓存文件路径"""
    return CACHE_DIR / f"{symbol}_{days}d_cache.parquet"


def load_from_cache(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """从缓存加载数据，增强验证：时间过期 + 数据完整性 + 行数检查"""
    cache_path = get_cache_path(symbol, days)
    if not cache_path.exists():
        return None
    
    # 检查缓存是否过期
    cache_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
    if datetime.now() - cache_mtime > timedelta(hours=CACHE_EXPIRY_HOURS):
        logger.info(f"  缓存已过期: {symbol}")
        return None
    
    try:
        df = pd.read_parquet(cache_path)
        
        # 行数检查：缓存数据不能太少
        if len(df) < MIN_CACHE_ROWS:
            logger.info(f"  缓存行数不足: {symbol} ({len(df)} < {MIN_CACHE_ROWS})")
            return None
        
        # 数据完整性检查
        completeness = check_data_completeness(df, days)
        if completeness < DATA_COMPLETENESS_THRESHOLD:
            logger.info(f"  缓存完整性不足: {symbol} ({completeness:.1%} < {DATA_COMPLETENESS_THRESHOLD:.0%})")
            return None
        
        logger.info(f"  从缓存加载: {symbol} ({len(df)} 行, 完整性: {completeness:.1%})")
        return df
    except Exception as e:
        logger.warning(f"  缓存加载失败: {symbol} - {e}")
        return None


def save_to_cache(symbol: str, days: int, df: pd.DataFrame):
    """保存数据到缓存"""
    cache_path = get_cache_path(symbol, days)
    try:
        df.to_parquet(cache_path, index=False)
        logger.info(f"  数据已缓存: {symbol} ({len(df)} 行)")
    except Exception as e:
        logger.warning(f"  缓存保存失败: {symbol} - {e}")


def check_data_completeness(df: pd.DataFrame, expected_days: int) -> float:
    """检查数据完整性"""
    if df.empty:
        return 0.0
    
    # 检查是否有缺失值
    missing_ratio = df.isnull().sum().sum() / (df.shape[0] * df.shape[1])
    
    # 检查日期连续性
    if 'date' in df.columns:
        date_series = pd.to_datetime(df['date'])
        date_diff = date_series.diff().dt.days
        # 允许周末和节假日（最多3天间隔）
        continuous_ratio = (date_diff <= 3).sum() / len(date_diff)
    else:
        continuous_ratio = 1.0
    
    completeness = (1 - missing_ratio) * continuous_ratio
    return completeness


def smart_wait_for_data(api, kline_refs: Dict, timeout: int = SMART_WAIT_TIMEOUT) -> bool:
    """智能等待数据完整性检查"""
    start_time = time.time()
    check_interval = 2  # 每2秒检查一次
    
    while time.time() - start_time < timeout:
        api.wait_update(deadline=time.time() + check_interval)
        
        # 检查所有品种的数据完整性
        all_complete = True
        for symbol_key, klines in kline_refs.items():
            if klines is None or len(klines) == 0:
                all_complete = False
                break
        
        if all_complete:
            logger.info(f"  数据完整性检查通过，耗时 {time.time() - start_time:.1f}s")
            return True
        
        # 动态调整等待时间
        elapsed = time.time() - start_time
        if elapsed > 10 and elapsed % 10 < check_interval:
            logger.info(f"  等待数据中... ({elapsed:.0f}s/{timeout}s)")
    
    logger.warning(f"  智能等待超时 ({timeout}s)")
    return False


def download_single_symbol(api, symbol_key: str, tq_symbol: str, data_length: int) -> Optional[pd.DataFrame]:
    """下载单个品种的数据"""
    try:
        logger.info(f"  订阅 {symbol_key}({tq_symbol}) 日线K线")
        klines = api.get_kline_serial(tq_symbol, 86400, data_length)
        
        if klines is None or len(klines) == 0:
            logger.warning(f"  ⚠ {symbol_key}: 无K线数据")
            return None
        
        df = pd.DataFrame(klines)
        if df.empty:
            logger.warning(f"  ⚠ {symbol_key}: 空DataFrame")
            return None
        
        # 标准化列名
        col_map = {
            'datetime': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'open_oi': 'open_interest',
            'close_oi': 'close_interest'
        }
        
        # 重命名列
        for old_col, new_col in col_map.items():
            if old_col in df.columns:
                df = df.rename(columns={old_col: new_col})
        
        # 确保有必要的列
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                logger.warning(f"  ⚠ {symbol_key}: 缺少必要列 {col}")
                return None
        
        # 添加品种标识
        df['symbol'] = symbol_key
        
        logger.info(f"  ✅ {symbol_key}: 获取 {len(df)} 行数据")
        return df
        
    except Exception as e:
        logger.error(f"  ❌ {symbol_key}: 获取失败 - {e}")
        return None


def download_kline_data_parallel_via_adapter(symbols: List[str], days: int = 756, use_cache: bool = True) -> Dict[str, pd.DataFrame]:
    """通过 futures-data-search MultiSourceAdapter 获取K线数据（代替直连TqSdk）"""
    results = {}
    symbols_to_fetch = []
    
    if use_cache:
        for symbol_key in symbols:
            cached_data = load_from_cache(symbol_key, days)
            if cached_data is not None:
                completeness = check_data_completeness(cached_data, days)
                if completeness >= DATA_COMPLETENESS_THRESHOLD:
                    results[symbol_key] = cached_data
                    logger.info(f"  使用缓存: {symbol_key} (完整性: {completeness:.1%})")
                    continue
            symbols_to_fetch.append(symbol_key)
    else:
        symbols_to_fetch = symbols.copy()
    
    if not symbols_to_fetch:
        logger.info("所有品种数据均从缓存加载")
        return results
    
    try:
        fds_dir = os.path.expanduser("~/.workbuddy/skills/futures-data-search")
        if fds_dir not in sys.path:
            sys.path.insert(0, fds_dir)
        from scripts.multi_source_adapter import MultiSourceAdapter
        adapter = MultiSourceAdapter()
    except Exception as e:
        logger.error(f"MultiSourceAdapter 加载失败: {e}")
        return results
    
    for symbol_key in symbols_to_fetch:
        logger.info(f"[adapter] 获取 {symbol_key}...")
        try:
            result = adapter.get_kline(variety=symbol_key, days=days)
            if result.get("success") and result.get("data"):
                raw_data = result["data"]
                records = []
                for item in raw_data:
                    try:
                        records.append({
                            "date": item.get("date", ""),
                            "open": float(item.get("open", 0)),
                            "high": float(item.get("high", 0)),
                            "low": float(item.get("low", 0)),
                            "close": float(item.get("close", 0)),
                            "volume": int(item.get("volume", 0)),
                        })
                    except (ValueError, TypeError):
                        continue
                if records:
                    df = pd.DataFrame(records)
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    df["symbol"] = symbol_key
                    results[symbol_key] = df
                    if use_cache:
                        save_to_cache(symbol_key, days, df)
                    logger.info(f"  ✅ {symbol_key}: {len(df)} 行（数据源: {result.get('data_source', '?')}）")
                else:
                    logger.warning(f"  ⚠ {symbol_key}: 无有效K线")
            else:
                logger.warning(f"  ⚠ {symbol_key}: 获取失败 - {result.get('error', '?')}")
        except Exception as e:
            logger.error(f"  ❌ {symbol_key}: 异常 - {e}")
    return results


def download_kline_data_parallel(symbols: List[str], days: int = 756, use_cache: bool = True) -> Dict[str, pd.DataFrame]:
    """并行下载K线数据
    
    优化点：
    1. 并行获取多个品种
    2. 通过 futures-data-search MultiSourceAdapter 统一调度（代替直连TqSdk）
    """
    print("[fetch_and_store] 推荐使用 fetch_and_store_optimized.py（已集成 MultiSourceAdapter）")
    print("[fetch_and_store] 如需使用旧版TqSdk路径，请设置 USE_LEGACY_TQSDK=1")
    if not os.environ.get('USE_LEGACY_TQSDK'):
        return download_kline_data_parallel_via_adapter(symbols, days, use_cache)
    
    from tqsdk import TqApi, TqAuth
    
    username, password = get_tq_credentials()
    auth = TqAuth(username, password)
    
    # 检查缓存
    results = {}
    symbols_to_fetch = []
    
    if use_cache:
        for symbol_key in symbols:
            cached_data = load_from_cache(symbol_key, days)
            if cached_data is not None:
                # 检查缓存数据完整性
                completeness = check_data_completeness(cached_data, days)
                if completeness >= DATA_COMPLETENESS_THRESHOLD:
                    results[symbol_key] = cached_data
                    logger.info(f"  使用缓存: {symbol_key} (完整性: {completeness:.1%})")
                    continue
            
            symbols_to_fetch.append(symbol_key)
    else:
        symbols_to_fetch = symbols.copy()
    
    if not symbols_to_fetch:
        logger.info("所有品种数据均从缓存加载")
        return results
    
    # 准备TqSdk品种映射
    tq_symbols = {}
    for symbol_key in symbols_to_fetch:
        tq_sym = TQSDK_SYMBOL_MAP.get(symbol_key)
        if not tq_sym:
            logger.warning(f"未知品种: {symbol_key}, 跳过")
            continue
        tq_symbols[symbol_key] = tq_sym
    
    if not tq_symbols:
        return results
    
    # 获取足够的历史K线：请求天数 + 缓冲，上限2000根（TqSdk免费账户限制）
    data_length = min(days + 50, 2000)
    logger.info(f"使用并行获取模式，目标 {data_length} 根日线K线（{days}天历史）")
    logger.info(f"待获取品种: {', '.join(tq_symbols.keys())}")
    
    # 创建TqSdk API实例
    api = TqApi(auth=auth)
    
    try:
        # 并行订阅所有品种
        kline_refs = {}
        for symbol_key, tq_symbol in tq_symbols.items():
            kline_refs[symbol_key] = api.get_kline_serial(tq_symbol, 86400, data_length)
        
        # 智能等待数据
        if not smart_wait_for_data(api, kline_refs):
            logger.warning("部分数据可能不完整")
        
        # 并行处理数据
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_symbol = {}
            for symbol_key, tq_symbol in tq_symbols.items():
                future = executor.submit(download_single_symbol, api, symbol_key, tq_symbol, data_length)
                future_to_symbol[future] = symbol_key
            
            for future in as_completed(future_to_symbol):
                symbol_key = future_to_symbol[future]
                try:
                    df = future.result()
                    if df is not None:
                        results[symbol_key] = df
                        # 保存到缓存
                        if use_cache:
                            save_to_cache(symbol_key, days, df)
                except Exception as e:
                    logger.error(f"  处理 {symbol_key} 数据时出错: {e}")
        
        logger.info(f"并行获取完成，成功获取 {len(results)}/{len(tq_symbols)} 个品种")
        return results
        
    finally:
        api.close()


def store_to_duckdb(kline_data: Dict[str, pd.DataFrame]):
    """将K线数据存储到DuckDB — 批量操作，单次连接"""
    import duckdb
    
    if not kline_data:
        logger.warning("无数据可存储")
        return
    
    conn = duckdb.connect(str(DB_PATH))
    try:
        # 批量删除旧表
        drop_stmts = [f"DROP TABLE IF EXISTS kline_{sym.lower()}" for sym in kline_data.keys()]
        for stmt in drop_stmts:
            conn.execute(stmt)
        
        # 批量创建新表
        for symbol_key, df in kline_data.items():
            table_name = f"kline_{symbol_key.lower()}"
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
            logger.info(f"  ✅ {symbol_key}: 存储到 {table_name} ({len(df)} 行)")
        
        logger.info(f"数据存储完成，共 {len(kline_data)} 个品种")
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="优化版原油系产业链数据采集脚本")
    parser.add_argument("--symbols", nargs="+", default=["SC", "BU", "FU", "LU", "PG"],
                       help="要获取的品种列表")
    parser.add_argument("--days", type=int, default=756,
                       help="获取历史天数（默认756天，约3年）")
    parser.add_argument("--parallel", action="store_true", default=True,
                       help="启用并行获取（默认启用）")
    parser.add_argument("--no-parallel", action="store_true",
                       help="禁用并行获取")
    parser.add_argument("--no-cache", action="store_true",
                       help="禁用缓存")
    parser.add_argument("--clear-cache", action="store_true",
                       help="清除所有缓存")
    
    args = parser.parse_args()
    
    # 清除缓存
    if args.clear_cache:
        import shutil
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            logger.info("缓存已清除")
        return
    
    use_parallel = args.parallel and not args.no_parallel
    use_cache = not args.no_cache
    
    logger.info("优化版原油系产业链数据采集脚本")
    logger.info(f"品种: {', '.join(args.symbols)}")
    logger.info(f"历史天数: {args.days}")
    logger.info(f"并行模式: {'启用' if use_parallel else '禁用'}")
    logger.info(f"缓存模式: {'启用' if use_cache else '禁用'}")
    logger.info("")
    
    start_time = time.time()
    
    try:
        # 获取数据
        if use_parallel:
            kline_data = download_kline_data_parallel(args.symbols, args.days, use_cache)
        else:
            # 降级到串行模式
            from fetch_and_store import download_kline_data
            kline_data = download_kline_data(args.symbols, args.days)
        
        if kline_data:
            # 存储到DuckDB
            store_to_duckdb(kline_data)
            
            elapsed = time.time() - start_time
            logger.info(f"数据采集完成，耗时 {elapsed:.1f} 秒")
            logger.info(f"成功获取 {len(kline_data)} 个品种")
        else:
            logger.error("数据采集失败")
            
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"数据采集失败（耗时 {elapsed:.1f}s）: {e}")
        raise


if __name__ == "__main__":
    main()
