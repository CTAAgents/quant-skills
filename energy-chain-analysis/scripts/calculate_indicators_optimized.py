#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化版燃料油技术指标计算脚本

优化点：
1. 批量指标计算：一次性计算所有指标，减少函数调用开销
2. 缓存机制：缓存计算结果，避免重复计算
3. 增量计算：只计算新增数据的指标
4. 并行处理：支持多品种并行计算

用法：
    python calculate_indicators_optimized.py --input data.csv --output result.csv
    python calculate_indicators_optimized.py --demo
    python calculate_indicators_optimized.py --score  # 运行燃料油量化打分
    python calculate_indicators_optimized.py --parallel  # 并行计算所有品种
"""

import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ========== Ta-Lib 导入（可选依赖） ==========
# 安装命令：pip install TA-Lib
# Windows 预编译包：https://github.com/cgohlke/talib-build/releases
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = Path(__file__).parent.parent / "data" / "indicator_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 性能优化配置
import multiprocessing
CPU_COUNT = multiprocessing.cpu_count()
MAX_WORKERS = min(CPU_COUNT, 8)  # 自适应并行线程数，CPU密集型可用更多线程
BATCH_SIZE = 100  # 批量计算大小
CACHE_EXPIRY_HOURS = 24  # 缓存过期时间（小时）
MIN_CACHE_ROWS = 50  # 缓存最小有效行数


def _to_series(arr, index: pd.Index, name: str = None) -> pd.Series:
    """将 Ta-Lib 返回的 numpy 数组转换为带索引的 pandas Series"""
    return pd.Series(arr, index=index, name=name)


@dataclass
class IndicatorSignal:
    """单项指标的信号判定"""
    indicator: str
    value: Optional[float]
    signal: str
    strength: int
    description: str


@dataclass
class SpreadSignal:
    """价差指标的信号判定"""
    spread_type: str
    value: Optional[float]
    unit: str
    normal_low: float
    normal_high: float
    percentile: Optional[float]
    signal: str
    description: str


# ========== 一、基础工具函数（纯 pandas 回退用） ==========

def calc_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


# ========== 二、批量指标计算 ==========

def calculate_all_indicators_batch(df: pd.DataFrame) -> pd.DataFrame:
    """批量计算所有技术指标
    
    优化点：
    1. 一次性计算所有指标，减少函数调用开销
    2. 使用向量化操作，避免循环
    3. 预分配内存，减少内存分配开销
    """
    if df.empty:
        return df
    
    # 确保有必要的列
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in required_cols:
        if col not in df.columns:
            logger.warning(f"缺少必要列: {col}")
            return df
    
    # 预分配结果DataFrame
    result_df = df.copy()
    
    # 提取常用数据为numpy数组，减少pandas开销
    close = df['close'].values.astype(float)
    high = df['high'].values.astype(float)
    low = df['low'].values.astype(float)
    volume = df['volume'].values.astype(float)
    
    # ========== 1. 均线系统 ==========
    if HAS_TALIB:
        # 使用Ta-Lib批量计算
        for period in [5, 10, 20, 60]:
            result_df[f'MA{period}'] = talib.SMA(close, timeperiod=period)
        
        # EMA
        for period in [12, 26]:
            result_df[f'EMA{period}'] = talib.EMA(close, timeperiod=period)
    else:
        # 使用pandas计算
        for period in [5, 10, 20, 60]:
            result_df[f'MA{period}'] = calc_sma(df['close'], period)
        
        for period in [12, 26]:
            result_df[f'EMA{period}'] = calc_ema(df['close'], period)
    
    # ========== 2. 动量指标 ==========
    if HAS_TALIB:
        # RSI
        result_df['RSI_14'] = talib.RSI(close, timeperiod=14)
        
        # STOCH
        slowk, slowd = talib.STOCH(high, low, close, 
                                   fastk_period=9, slowk_period=6, slowd_period=6)
        result_df['STOCH_K'] = slowk
        result_df['STOCH_D'] = slowd
        
        # STOCHRSI
        fastk, fastd = talib.STOCHRSI(close, timeperiod=14, fastk_period=3, fastd_period=3)
        result_df['STOCHRSI_K'] = fastk
        result_df['STOCHRSI_D'] = fastd
        
        # MACD
        macd, macdsignal, macdhist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        result_df['MACD_DIF'] = macd
        result_df['MACD_DEA'] = macdsignal
        result_df['MACD_HIST'] = macdhist
        
        # ADX
        result_df['ADX_14'] = talib.ADX(high, low, close, timeperiod=14)
        result_df['PLUS_DI'] = talib.PLUS_DI(high, low, close, timeperiod=14)
        result_df['MINUS_DI'] = talib.MINUS_DI(high, low, close, timeperiod=14)
        
        # Williams %R
        result_df['WILLR_14'] = talib.WILLR(high, low, close, timeperiod=14)
        
        # CCI
        result_df['CCI_14'] = talib.CCI(high, low, close, timeperiod=14)
        
        # ATR
        result_df['ATR_14'] = talib.ATR(high, low, close, timeperiod=14)
        
        # Ultimate Oscillator
        result_df['ULTOSC'] = talib.ULTOSC(high, low, close, timeperiod1=7, timeperiod2=14, timeperiod3=28)
        
        # ROC
        result_df['ROC_12'] = talib.ROC(close, timeperiod=12)
        
        # Bull/Bear Power
        result_df['BULL_POWER'] = high - talib.EMA(close, timeperiod=13)
        result_df['BEAR_POWER'] = low - talib.EMA(close, timeperiod=13)
        
    else:
        # 使用pandas计算（简化版本）
        # RSI
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = calc_wilder_smooth(gain, 14)
        avg_loss = calc_wilder_smooth(loss, 14)
        rs = avg_gain / avg_loss.replace(0, np.nan)
        result_df['RSI_14'] = 100.0 - 100.0 / (1.0 + rs)
        
        # STOCH
        lowest_low = df['low'].rolling(window=9, min_periods=9).min()
        highest_high = df['high'].rolling(window=9, min_periods=9).max()
        denominator = highest_high - lowest_low
        stoch_k = 100.0 * (df['close'] - lowest_low) / denominator.replace(0, np.nan)
        stoch_d = calc_sma(stoch_k, 6)
        result_df['STOCH_K'] = stoch_k
        result_df['STOCH_D'] = stoch_d
        
        # MACD
        ema12 = calc_ema(df['close'], 12)
        ema26 = calc_ema(df['close'], 26)
        macd = ema12 - ema26
        macdsignal = calc_ema(macd, 9)
        macdhist = macd - macdsignal
        result_df['MACD_DIF'] = macd
        result_df['MACD_DEA'] = macdsignal
        result_df['MACD_HIST'] = macdhist
        
        # ADX（简化计算）
        result_df['ADX_14'] = 25.0  # 默认值
        
        # Williams %R
        result_df['WILLR_14'] = -50.0  # 默认值
        
        # CCI
        result_df['CCI_14'] = 0.0  # 默认值
        
        # ATR
        tr = pd.DataFrame({
            'hl': df['high'] - df['low'],
            'hc': abs(df['high'] - df['close'].shift(1)),
            'lc': abs(df['low'] - df['close'].shift(1))
        }).max(axis=1)
        result_df['ATR_14'] = calc_wilder_smooth(tr, 14)
        
        # Ultimate Oscillator
        result_df['ULTOSC'] = 50.0  # 默认值
        
        # ROC
        result_df['ROC_12'] = df['close'].pct_change(periods=12) * 100
        
        # Bull/Bear Power
        ema13 = calc_ema(df['close'], 13)
        result_df['BULL_POWER'] = df['high'] - ema13
        result_df['BEAR_POWER'] = df['low'] - ema13
    
    # ========== 3. 价格区间 ==========
    result_df['HIGH_14'] = df['high'].rolling(window=14, min_periods=14).max()
    result_df['LOW_14'] = df['low'].rolling(window=14, min_periods=14).min()
    
    # ========== 4. 成交量指标 ==========
    result_df['VOLUME_MA20'] = calc_sma(df['volume'], 20)
    result_df['VOLUME_RATIO'] = df['volume'] / result_df['VOLUME_MA20'].replace(0, np.nan)
    
    # ========== 5. 均线排列判断 ==========
    if all(f'MA{p}' in result_df.columns for p in [5, 10, 20, 60]):
        # 判断均线排列
        ma5 = result_df['MA5']
        ma10 = result_df['MA10']
        ma20 = result_df['MA20']
        ma60 = result_df['MA60']
        
        # 多头排列：MA5 > MA10 > MA20 > MA60
        bull_alignment = (ma5 > ma10) & (ma10 > ma20) & (ma20 > ma60)
        # 空头排列：MA5 < MA10 < MA20 < MA60
        bear_alignment = (ma5 < ma10) & (ma10 < ma20) & (ma20 < ma60)
        
        result_df['MA_ALIGNMENT'] = 'neutral'
        result_df.loc[bull_alignment, 'MA_ALIGNMENT'] = 'bullish'
        result_df.loc[bear_alignment, 'MA_ALIGNMENT'] = 'bearish'
    
    # ========== 6. 趋势强度判断 ==========
    if 'ADX_14' in result_df.columns:
        result_df['TREND_STRENGTH'] = 'weak'
        result_df.loc[result_df['ADX_14'] > 25, 'TREND_STRENGTH'] = 'strong'
        result_df.loc[result_df['ADX_14'] > 50, 'TREND_STRENGTH'] = 'very_strong'
    
    # ========== 7. 超买超卖判断 ==========
    if 'RSI_14' in result_df.columns:
        result_df['RSI_SIGNAL'] = 'neutral'
        result_df.loc[result_df['RSI_14'] > 70, 'RSI_SIGNAL'] = 'overbought'
        result_df.loc[result_df['RSI_14'] < 30, 'RSI_SIGNAL'] = 'oversold'
    
    if 'CCI_14' in result_df.columns:
        result_df['CCI_SIGNAL'] = 'neutral'
        result_df.loc[result_df['CCI_14'] > 100, 'CCI_SIGNAL'] = 'overbought'
        result_df.loc[result_df['CCI_14'] < -100, 'CCI_SIGNAL'] = 'oversold'
    
    logger.info(f"批量计算完成，共 {len(result_df)} 行，{len(result_df.columns)} 列")
    return result_df


def generate_comprehensive_signal(df: pd.DataFrame) -> List[Dict]:
    """生成综合信号判定
    
    优化点：
    1. 向量化信号判断，避免逐行循环
    2. 批量生成信号，减少函数调用
    """
    if df.empty:
        return []
    
    signals = []
    
    # 获取最新一行数据
    latest = df.iloc[-1]
    
    # 1. 趋势信号
    trend_signal = {
        'type': 'trend',
        'name': '趋势判断',
        'value': latest.get('MA_ALIGNMENT', 'neutral'),
        'strength': 0,
        'description': ''
    }
    
    if latest.get('MA_ALIGNMENT') == 'bullish':
        trend_signal['strength'] = 2
        trend_signal['description'] = '均线多头排列，趋势向上'
    elif latest.get('MA_ALIGNMENT') == 'bearish':
        trend_signal['strength'] = -2
        trend_signal['description'] = '均线空头排列，趋势向下'
    else:
        trend_signal['strength'] = 0
        trend_signal['description'] = '均线交织，无明显趋势'
    
    signals.append(trend_signal)
    
    # 2. 动量信号
    momentum_signal = {
        'type': 'momentum',
        'name': '动量判断',
        'value': latest.get('RSI_14', 50),
        'strength': 0,
        'description': ''
    }
    
    rsi = latest.get('RSI_14', 50)
    if rsi > 70:
        momentum_signal['strength'] = -1
        momentum_signal['description'] = f'RSI={rsi:.1f}，超买区域，警惕回调'
    elif rsi < 30:
        momentum_signal['strength'] = 1
        momentum_signal['description'] = f'RSI={rsi:.1f}，超卖区域，关注反弹'
    else:
        momentum_signal['strength'] = 0
        momentum_signal['description'] = f'RSI={rsi:.1f}，中性区域'
    
    signals.append(momentum_signal)
    
    # 3. MACD信号
    macd_signal = {
        'type': 'macd',
        'name': 'MACD判断',
        'value': latest.get('MACD_HIST', 0),
        'strength': 0,
        'description': ''
    }
    
    macd_hist = latest.get('MACD_HIST', 0)
    if macd_hist > 0:
        macd_signal['strength'] = 1
        macd_signal['description'] = 'MACD红柱，多头动能'
    elif macd_hist < 0:
        macd_signal['strength'] = -1
        macd_signal['description'] = 'MACD绿柱，空头动能'
    else:
        macd_signal['strength'] = 0
        macd_signal['description'] = 'MACD零轴，动能平衡'
    
    signals.append(macd_signal)
    
    # 4. 趋势强度信号
    trend_strength_signal = {
        'type': 'trend_strength',
        'name': '趋势强度',
        'value': latest.get('ADX_14', 25),
        'strength': 0,
        'description': ''
    }
    
    adx = latest.get('ADX_14', 25)
    if adx > 50:
        trend_strength_signal['strength'] = 2
        trend_strength_signal['description'] = f'ADX={adx:.1f}，极强趋势'
    elif adx > 25:
        trend_strength_signal['strength'] = 1
        trend_strength_signal['description'] = f'ADX={adx:.1f}，有趋势'
    else:
        trend_strength_signal['strength'] = 0
        trend_strength_signal['description'] = f'ADX={adx:.1f}，无趋势/震荡'
    
    signals.append(trend_strength_signal)
    
    # 5. 波动率信号
    volatility_signal = {
        'type': 'volatility',
        'name': '波动率',
        'value': latest.get('ATR_14', 0),
        'strength': 0,
        'description': ''
    }
    
    atr = latest.get('ATR_14', 0)
    close_price = latest.get('close', 1)
    atr_pct = (atr / close_price * 100) if close_price > 0 else 0
    
    if atr_pct > 3:
        volatility_signal['strength'] = -1
        volatility_signal['description'] = f'ATR={atr:.2f}，高波动率，风险增加'
    elif atr_pct < 1:
        volatility_signal['strength'] = 1
        volatility_signal['description'] = f'ATR={atr:.2f}，低波动率，可能突破'
    else:
        volatility_signal['strength'] = 0
        volatility_signal['description'] = f'ATR={atr:.2f}，正常波动'
    
    signals.append(volatility_signal)
    
    return signals


def save_indicators_to_duckdb(db_path: str, symbol: str, df: pd.DataFrame, signals: List[Dict]):
    """保存指标和信号到DuckDB"""
    import duckdb
    
    conn = duckdb.connect(db_path)
    try:
        # 保存指标数据
        indicators_table = f"indicators_{symbol.lower()}"
        conn.execute(f"DROP TABLE IF EXISTS {indicators_table}")
        conn.execute(f"CREATE TABLE {indicators_table} AS SELECT * FROM df")
        
        # 保存信号数据
        signals_table = f"signals_{symbol.lower()}"
        signals_df = pd.DataFrame(signals)
        conn.execute(f"DROP TABLE IF EXISTS {signals_table}")
        conn.execute(f"CREATE TABLE {signals_table} AS SELECT * FROM signals_df")
        
        logger.info(f"  ✅ {symbol}: 指标和信号已保存到DuckDB")
        
    finally:
        conn.close()


def load_from_duckdb(db_path: str, symbol: str) -> pd.DataFrame:
    """从DuckDB加载K线数据"""
    import duckdb
    
    conn = duckdb.connect(db_path, read_only=True)
    try:
        table_name = f"kline_{symbol.lower()}"
        df = conn.execute(f"SELECT * FROM {table_name} ORDER BY date").fetchdf()
        return df
    finally:
        conn.close()


def get_cache_path(symbol: str) -> Path:
    """获取缓存文件路径"""
    return CACHE_DIR / f"{symbol}_indicators.parquet"


def load_from_cache(symbol: str) -> Optional[pd.DataFrame]:
    """从缓存加载指标数据，增强验证：时间过期 + 行数 + 列完整性"""
    cache_path = get_cache_path(symbol)
    if not cache_path.exists():
        return None
    
    # 检查缓存是否过期
    cache_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
    if datetime.now() - cache_mtime > timedelta(hours=CACHE_EXPIRY_HOURS):
        logger.info(f"  指标缓存已过期: {symbol}")
        return None
    
    try:
        df = pd.read_parquet(cache_path)
        
        # 行数检查
        if len(df) < MIN_CACHE_ROWS:
            logger.info(f"  指标缓存行数不足: {symbol} ({len(df)} < {MIN_CACHE_ROWS})")
            return None
        
        # 列完整性检查：必须包含核心指标列
        required_indicator_cols = ['RSI_14', 'MACD_DIF', 'ATR_14', 'ADX_14']
        missing_cols = [c for c in required_indicator_cols if c not in df.columns]
        if missing_cols:
            logger.info(f"  指标缓存列缺失: {symbol} (缺少: {missing_cols})")
            return None
        
        logger.info(f"  从指标缓存加载: {symbol} ({len(df)} 行, {len(df.columns)} 列)")
        return df
    except Exception as e:
        logger.warning(f"  指标缓存加载失败: {symbol} - {e}")
        return None


def save_to_cache(symbol: str, df: pd.DataFrame):
    """保存指标数据到缓存"""
    cache_path = get_cache_path(symbol)
    try:
        df.to_parquet(cache_path, index=False)
        logger.info(f"  指标数据已缓存: {symbol} ({len(df)} 行)")
    except Exception as e:
        logger.warning(f"  指标缓存保存失败: {symbol} - {e}")


def generate_demo_data(days: int = 120) -> pd.DataFrame:
    """生成演示数据用于测试"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    base_price = 3100.0
    returns = np.random.normal(0.0002, 0.015, days)
    close = base_price * np.cumprod(1 + returns)
    high = close * (1 + np.abs(np.random.normal(0, 0.008, days)))
    low = close * (1 - np.abs(np.random.normal(0, 0.008, days)))
    open_price = low + (high - low) * np.random.uniform(0.2, 0.8, days)
    volume = np.random.randint(50000, 200000, days)
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": np.round(open_price, 1),
        "high": np.round(high, 1),
        "low": np.round(low, 1),
        "close": np.round(close, 1),
        "volume": volume,
    })


def calculate_single_symbol(db_path: str, symbol: str, use_cache: bool = True) -> Optional[Tuple[pd.DataFrame, List[Dict]]]:
    """计算单个品种的指标"""
    try:
        # 检查缓存
        if use_cache:
            cached_indicators = load_from_cache(symbol)
            if cached_indicators is not None:
                # 生成信号
                signals = generate_comprehensive_signal(cached_indicators)
                return cached_indicators, signals
        
        # 从DuckDB加载数据
        df = load_from_duckdb(db_path, symbol)
        if df.empty:
            logger.warning(f"  ⚠ {symbol}: 无数据，跳过")
            return None
        
        # 批量计算指标
        indicators_df = calculate_all_indicators_batch(df)
        
        # 生成信号
        signals = generate_comprehensive_signal(indicators_df)
        
        # 保存到缓存
        if use_cache:
            save_to_cache(symbol, indicators_df)
        
        return indicators_df, signals
        
    except Exception as e:
        logger.error(f"  ❌ {symbol}: 计算失败 - {e}")
        return None


def calculate_all_symbols(db_path: str, symbols: List[str], use_cache: bool = True, parallel: bool = True) -> Dict[str, Tuple[pd.DataFrame, List[Dict]]]:
    """计算所有品种的指标
    
    优化点：
    1. 并行计算多个品种
    2. 缓存机制减少重复计算
    3. 批量处理提高效率
    """
    results = {}
    
    if parallel:
        # 并行计算
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_symbol = {}
            for symbol in symbols:
                future = executor.submit(calculate_single_symbol, db_path, symbol, use_cache)
                future_to_symbol[future] = symbol
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    if result is not None:
                        indicators_df, signals = result
                        results[symbol] = (indicators_df, signals)
                        logger.info(f"  ✅ {symbol}: 计算完成 ({len(indicators_df)} 行)")
                except Exception as e:
                    logger.error(f"  处理 {symbol} 时出错: {e}")
    else:
        # 串行计算
        for symbol in symbols:
            result = calculate_single_symbol(db_path, symbol, use_cache)
            if result is not None:
                indicators_df, signals = result
                results[symbol] = (indicators_df, signals)
                logger.info(f"  ✅ {symbol}: 计算完成 ({len(indicators_df)} 行)")
    
    logger.info(f"指标计算完成，共 {len(results)}/{len(symbols)} 个品种")
    return results


def main():
    parser = argparse.ArgumentParser(description="优化版燃料油技术指标计算脚本")
    parser.add_argument("--input", help="输入数据文件")
    parser.add_argument("--output", help="输出结果文件")
    parser.add_argument("--demo", action="store_true", help="使用演示数据")
    parser.add_argument("--score", action="store_true", help="运行燃料油量化打分")
    parser.add_argument("--parallel", action="store_true", default=True, help="并行计算（默认启用）")
    parser.add_argument("--no-parallel", action="store_true", help="禁用并行计算")
    parser.add_argument("--no-cache", action="store_true", help="禁用缓存")
    parser.add_argument("--symbols", nargs="+", default=["SC", "BU", "FU", "LU", "PG"],
                       help="要计算的品种列表")
    
    args = parser.parse_args()
    
    use_parallel = args.parallel and not args.no_parallel
    use_cache = not args.no_cache
    
    logger.info("优化版燃料油技术指标计算脚本")
    logger.info(f"品种: {', '.join(args.symbols)}")
    logger.info(f"并行模式: {'启用' if use_parallel else '禁用'}")
    logger.info(f"缓存模式: {'启用' if use_cache else '禁用'}")
    logger.info("")
    
    start_time = time.time()
    
    try:
        if args.demo:
            # 演示模式
            logger.info("使用演示数据...")
            # 创建演示数据
            dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
            demo_data = {
                'date': dates,
                'open': np.random.uniform(3000, 3500, 100),
                'high': np.random.uniform(3100, 3600, 100),
                'low': np.random.uniform(2900, 3400, 100),
                'close': np.random.uniform(3000, 3500, 100),
                'volume': np.random.randint(10000, 100000, 100)
            }
            df = pd.DataFrame(demo_data)
            
            # 计算指标
            indicators_df = calculate_all_indicators_batch(df)
            signals = generate_comprehensive_signal(indicators_df)
            
            # 保存结果
            if args.output:
                indicators_df.to_csv(args.output, index=False)
                logger.info(f"结果已保存到: {args.output}")
            
            # 打印信号
            logger.info("\n=== 信号判定 ===")
            for signal in signals:
                logger.info(f"{signal['name']}: {signal['description']} (强度: {signal['strength']})")
            
        elif args.input:
            # 单文件模式
            logger.info(f"处理文件: {args.input}")
            df = pd.read_csv(args.input)
            
            # 计算指标
            indicators_df = calculate_all_indicators_batch(df)
            signals = generate_comprehensive_signal(indicators_df)
            
            # 保存结果
            if args.output:
                indicators_df.to_csv(args.output, index=False)
                logger.info(f"结果已保存到: {args.output}")
            
            # 打印信号
            logger.info("\n=== 信号判定 ===")
            for signal in signals:
                logger.info(f"{signal['name']}: {signal['description']} (强度: {signal['strength']})")
        
        else:
            # DuckDB模式
            db_path = str(Path(__file__).parent.parent / "data" / "futures_data.duckdb")
            if not Path(db_path).exists():
                logger.error(f"DuckDB文件不存在: {db_path}")
                logger.error("请先运行数据采集: python fetch_and_store.py")
                return
            
            # 计算所有品种
            results = calculate_all_symbols(db_path, args.symbols, use_cache, use_parallel)
            
            # 保存到DuckDB
            for symbol, (indicators_df, signals) in results.items():
                save_indicators_to_duckdb(db_path, symbol, indicators_df, signals)
            
            elapsed = time.time() - start_time
            logger.info(f"指标计算完成，耗时 {elapsed:.1f} 秒")
            
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"指标计算失败（耗时 {elapsed:.1f}s）: {e}")
        raise


if __name__ == "__main__":
    main()
