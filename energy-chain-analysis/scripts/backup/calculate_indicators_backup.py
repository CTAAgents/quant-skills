#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
燃料油技术指标计算脚本（Ta-Lib 增强版 + 五层量化打分框架）

功能：
    1. 计算核心技术指标（完整清单）：
       MA(5,10,20,60) / RSI(14) / STOCH(9,6) / STOCHRSI(14) / MACD(12,26) / ADX(14) /
       Williams %R / CCI(14) / ATR(14) / Highs/Lows(14) / Ultimate Oscillator / ROC /
       Bull/Bear Power(13)
    2. 计算价差指标：高低硫价差 / 裂解价差 / 内外价差
    3. 生成信号判断：超买超卖 / 趋势方向 / 价差回归
    4. 燃料油五层量化打分框架：成本(25%) + 裂解(30%) + 新加坡(20%) + 国内供需(15%) + 盘面结构(10%)

Ta-Lib 集成：
    优先使用 Ta-Lib C 库计算所有指标（性能更优、精度更高），
    若 Ta-Lib 未安装则自动回退到纯 numpy/pandas 实现。

    安装方式：
        pip install TA-Lib
    注意：TA-Lib Python 包依赖 C 语言底层库，Windows 用户需先安装预编译包，
    推荐：https://github.com/cgohlke/talib-build/releases

输入：
    K线数据（pandas DataFrame），需包含列：date, open, high, low, close, volume

输出：
    附加技术指标列的DataFrame，或保存为CSV/JSON

依赖：
    pandas, numpy
    可选：TA-Lib (推荐安装以获得更优性能)

用法：
    python calculate_indicators.py --input data.csv --output result.csv
    python calculate_indicators.py --demo
    python calculate_indicators.py --score  # 运行燃料油量化打分
"""

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

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


# ========== 二、核心技术指标计算 ==========

def calc_ma(close: pd.Series, periods: list[int] = None) -> pd.DataFrame:
    """MA(5,10,20,60) 多周期简单移动平均线"""
    if periods is None:
        periods = [5, 10, 20, 60]
    if HAS_TALIB:
        c = close.values.astype(float)
        data = {f"MA{p}": _to_series(talib.SMA(c, timeperiod=p), close.index, f"MA{p}")
                for p in periods}
        return pd.DataFrame(data, index=close.index)
    return pd.DataFrame({f"MA{p}": calc_sma(close, p) for p in periods})


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI(14) 相对强弱指数"""
    if HAS_TALIB:
        return _to_series(talib.RSI(close.values.astype(float), timeperiod=period),
                          close.index, "RSI")
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = calc_wilder_smooth(gain, period)
    avg_loss = calc_wilder_smooth(loss, period)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - 100.0 / (1.0 + rs)


def calc_stoch(high: pd.Series, low: pd.Series, close: pd.Series,
               k_period: int = 9, d_period: int = 6) -> pd.DataFrame:
    """STOCH(9,6) 随机指标"""
    if HAS_TALIB:
        h = high.values.astype(float)
        l = low.values.astype(float)
        c = close.values.astype(float)
        slowk, slowd = talib.STOCH(h, l, c,
                                   fastk_period=k_period,
                                   slowk_period=d_period,
                                   slowd_period=d_period)
        return pd.DataFrame({
            "STOCH_K": _to_series(slowk, high.index, "STOCH_K"),
            "STOCH_D": _to_series(slowd, high.index, "STOCH_D"),
        }, index=high.index)
    lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
    highest_high = high.rolling(window=k_period, min_periods=k_period).max()
    denominator = highest_high - lowest_low
    stoch_k = 100.0 * (close - lowest_low) / denominator.replace(0, np.nan)
    stoch_d = calc_sma(stoch_k, d_period)
    return pd.DataFrame({
        "STOCH_K": stoch_k,
        "STOCH_D": stoch_d,
    })


def calc_stoch_rsi(close: pd.Series, rsi_period: int = 14,
                   stoch_period: int = 14, k_period: int = 3, d_period: int = 3) -> pd.DataFrame:
    """STOCHRSI(14) 随机RSI指标"""
    if HAS_TALIB:
        c = close.values.astype(float)
        fastk, fastd = talib.STOCHRSI(c, timeperiod=rsi_period,
                                       fastk_period=k_period, fastd_period=d_period)
        return pd.DataFrame({
            "STOCHRSI_K": _to_series(fastk, close.index, "STOCHRSI_K"),
            "STOCHRSI_D": _to_series(fastd, close.index, "STOCHRSI_D"),
        }, index=close.index)
    rsi = calc_rsi(close, rsi_period)
    rsi_low = rsi.rolling(window=stoch_period, min_periods=stoch_period).min()
    rsi_high = rsi.rolling(window=stoch_period, min_periods=stoch_period).max()
    denominator = rsi_high - rsi_low
    stoch_rsi = (rsi - rsi_low) / denominator.replace(0, np.nan)
    stoch_rsi_k = calc_sma(stoch_rsi * 100, k_period)
    stoch_rsi_d = calc_sma(stoch_rsi_k, d_period)
    return pd.DataFrame({
        "STOCHRSI_K": stoch_rsi_k,
        "STOCHRSI_D": stoch_rsi_d,
    })


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD(12,26) 指数平滑异同移动平均线"""
    if HAS_TALIB:
        c = close.values.astype(float)
        macd, macdsignal, macdhist = talib.MACD(c, fastperiod=fast,
                                                 slowperiod=slow, signalperiod=signal)
        return pd.DataFrame({
            "MACD_DIF": _to_series(macd, close.index, "MACD_DIF"),
            "MACD_DEA": _to_series(macdsignal, close.index, "MACD_DEA"),
            "MACD_HIST": _to_series(macdhist * 2.0, close.index, "MACD_HIST"),
        }, index=close.index)
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    macd_hist = 2.0 * (dif - dea)
    return pd.DataFrame({
        "MACD_DIF": dif,
        "MACD_DEA": dea,
        "MACD_HIST": macd_hist,
    })


def calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.DataFrame:
    """ADX(14) 平均方向指数"""
    if HAS_TALIB:
        h = high.values.astype(float)
        l = low.values.astype(float)
        c = close.values.astype(float)
        adx = talib.ADX(h, l, c, timeperiod=period)
        plus_di = talib.PLUS_DI(h, l, c, timeperiod=period)
        minus_di = talib.MINUS_DI(h, l, c, timeperiod=period)
        return pd.DataFrame({
            "ADX": _to_series(adx, high.index, "ADX"),
            "PLUS_DI": _to_series(plus_di, high.index, "PLUS_DI"),
            "MINUS_DI": _to_series(minus_di, high.index, "MINUS_DI"),
        }, index=high.index)
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    plus_dm = high - prev_high
    minus_dm = prev_low - low

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = calc_wilder_smooth(tr, period)
    plus_di = 100.0 * calc_wilder_smooth(plus_dm, period) / atr.replace(0, np.nan)
    minus_di = 100.0 * calc_wilder_smooth(minus_dm, period) / atr.replace(0, np.nan)

    di_sum = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan)
    adx = calc_wilder_smooth(dx, period)

    return pd.DataFrame({
        "ADX": adx,
        "PLUS_DI": plus_di,
        "MINUS_DI": minus_di,
    })


def calc_williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Williams %R"""
    if HAS_TALIB:
        h = high.values.astype(float)
        l = low.values.astype(float)
        c = close.values.astype(float)
        return _to_series(talib.WILLR(h, l, c, timeperiod=period),
                          high.index, "WILLIAMS_R")
    highest_high = high.rolling(window=period, min_periods=period).max()
    lowest_low = low.rolling(window=period, min_periods=period).min()
    denominator = highest_high - lowest_low
    wr = -100.0 * (highest_high - close) / denominator.replace(0, np.nan)
    return wr


def calc_cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """CCI(14) 商品通道指数"""
    if HAS_TALIB:
        h = high.values.astype(float)
        l = low.values.astype(float)
        c = close.values.astype(float)
        return _to_series(talib.CCI(h, l, c, timeperiod=period),
                          high.index, "CCI")
    tp = (high + low + close) / 3.0
    sma_tp = tp.rolling(window=period, min_periods=period).mean()
    mad = tp.rolling(window=period, min_periods=period).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    return (tp - sma_tp) / (0.015 * mad)


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """ATR(14) 平均真实波幅"""
    if HAS_TALIB:
        h = high.values.astype(float)
        l = low.values.astype(float)
        c = close.values.astype(float)
        return _to_series(talib.ATR(h, l, c, timeperiod=period),
                          high.index, "ATR")
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return calc_wilder_smooth(tr, period)


def calc_highs_lows(high: pd.Series, low: pd.Series, period: int = 14) -> pd.DataFrame:
    """Highs/Lows(14) 最高价与最低价滚动统计"""
    if HAS_TALIB:
        h = high.values.astype(float)
        l = low.values.astype(float)
        highest = _to_series(talib.MAX(h, timeperiod=period), high.index, f"HIGHS_{period}")
        lowest = _to_series(talib.MIN(l, timeperiod=period), low.index, f"LOWS_{period}")
        hl_range = highest - lowest
        return pd.DataFrame({
            f"HIGHS_{period}": highest,
            f"LOWS_{period}": lowest,
            f"HL_RANGE_{period}": hl_range,
        }, index=high.index)
    highest = high.rolling(window=period, min_periods=period).max()
    lowest = low.rolling(window=period, min_periods=period).min()
    hl_range = highest - lowest
    return pd.DataFrame({
        f"HIGHS_{period}": highest,
        f"LOWS_{period}": lowest,
        f"HL_RANGE_{period}": hl_range,
    })


def calc_ultimate_oscillator(high: pd.Series, low: pd.Series, close: pd.Series,
                             period1: int = 7, period2: int = 14, period3: int = 28) -> pd.Series:
    """Ultimate Oscillator 终极震荡指标"""
    if HAS_TALIB:
        h = high.values.astype(float)
        l = low.values.astype(float)
        c = close.values.astype(float)
        return _to_series(talib.ULTOSC(h, l, c,
                                       timeperiod1=period1,
                                       timeperiod2=period2,
                                       timeperiod3=period3),
                          high.index, "UO")
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    bp = close - pd.concat([low, prev_close], axis=1).min(axis=1)
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    avg1 = bp.rolling(window=period1, min_periods=period1).sum() / tr.rolling(window=period1, min_periods=period1).sum()
    avg2 = bp.rolling(window=period2, min_periods=period2).sum() / tr.rolling(window=period2, min_periods=period2).sum()
    avg3 = bp.rolling(window=period3, min_periods=period3).sum() / tr.rolling(window=period3, min_periods=period3).sum()

    uo = 100.0 * (4 * avg1 + 2 * avg2 + avg3) / 7.0
    return uo


def calc_roc(close: pd.Series, period: int = 12) -> pd.Series:
    """ROC 变动率指标"""
    if HAS_TALIB:
        return _to_series(talib.ROC(close.values.astype(float), timeperiod=period),
                          close.index, "ROC")
    prev_close = close.shift(period)
    return 100.0 * (close - prev_close) / prev_close.replace(0, np.nan)


def calc_bull_bear_power(high: pd.Series, low: pd.Series, close: pd.Series,
                         period: int = 13) -> pd.DataFrame:
    """Bull/Bear Power(13) 多空力量指标"""
    if HAS_TALIB:
        ema_close = _to_series(
            talib.EMA(close.values.astype(float), timeperiod=period),
            close.index, "EMA"
        )
    else:
        ema_close = calc_ema(close, period)
    bull_power = high - ema_close
    bear_power = low - ema_close
    return pd.DataFrame({
        "BULL_POWER": bull_power,
        "BEAR_POWER": bear_power,
    })


# ========== 三、全部技术指标计算入口 ==========

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """一次性计算全部技术指标（优先使用 Ta-Lib，自动回退纯 pandas）"""
    result = df.copy()

    col_map = {}
    for col in result.columns:
        col_lower = col.lower().strip()
        if col_lower in ("date", "datetime", "time"):
            col_map[col] = "date"
        elif col_lower == "open":
            col_map[col] = "open"
        elif col_lower == "high":
            col_map[col] = "high"
        elif col_lower == "low":
            col_map[col] = "low"
        elif col_lower == "close":
            col_map[col] = "close"
        elif col_lower in ("vol", "volume"):
            col_map[col] = "volume"
    if col_map:
        result = result.rename(columns=col_map)

    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in result.columns]
    if missing:
        raise ValueError(f"输入数据缺少必需列: {missing}，当前列: {result.columns.tolist()}")

    close = result["close"]
    high = result["high"]
    low = result["low"]

    engine = "Ta-Lib (C库)" if HAS_TALIB else "纯 pandas/numpy"
    logger.info(f"开始计算技术指标，计算引擎: {engine}")

    # 1. MA(5,10,20,60)
    result = pd.concat([result, calc_ma(close)], axis=1)
    logger.info("  ✓ MA(5,10,20,60)")

    # 2. RSI(14)
    result["RSI_14"] = calc_rsi(close, period=14)
    logger.info("  ✓ RSI(14)")

    # 3. STOCH(9,6)
    result = pd.concat([result, calc_stoch(high, low, close, k_period=9, d_period=6)], axis=1)
    logger.info("  ✓ STOCH(9,6)")

    # 4. STOCHRSI(14)
    result = pd.concat([result, calc_stoch_rsi(close)], axis=1)
    logger.info("  ✓ STOCHRSI(14)")

    # 5. MACD(12,26)
    result = pd.concat([result, calc_macd(close, fast=12, slow=26, signal=9)], axis=1)
    logger.info("  ✓ MACD(12,26)")

    # 6. ADX(14)
    result = pd.concat([result, calc_adx(high, low, close, period=14)], axis=1)
    logger.info("  ✓ ADX(14)")

    # 7. Williams %R
    result["WILLIAMS_R"] = calc_williams_r(high, low, close, period=14)
    logger.info("  ✓ Williams %R")

    # 8. CCI(14)
    result["CCI_14"] = calc_cci(high, low, close, period=14)
    logger.info("  ✓ CCI(14)")

    # 9. ATR(14)
    result["ATR_14"] = calc_atr(high, low, close, period=14)
    logger.info("  ✓ ATR(14)")

    # 10. Highs/Lows(14)
    result = pd.concat([result, calc_highs_lows(high, low, period=14)], axis=1)
    logger.info("  ✓ Highs/Lows(14)")

    # 11. Ultimate Oscillator
    result["UO"] = calc_ultimate_oscillator(high, low, close)
    logger.info("  ✓ Ultimate Oscillator")

    # 12. ROC
    result["ROC"] = calc_roc(close, period=12)
    logger.info("  ✓ ROC")

    # 13. Bull/Bear Power(13)
    result = pd.concat([result, calc_bull_bear_power(high, low, close, period=13)], axis=1)
    logger.info("  ✓ Bull/Bear Power(13)")

    # 附赠：均线排列判定
    result["MA_ALIGN"] = _judge_ma_alignment(result)
    logger.info("  ✓ 均线排列判定")

    logger.info(f"全部指标计算完成，共 {len(result.columns)} 列")
    return result


# ========== 四、价差指标计算 ==========

def calc_high_low_sulfur_spread(lu_price: pd.Series, fu_price: pd.Series) -> pd.Series:
    """高低硫价差（LU - FU）"""
    return lu_price - fu_price


def calc_crack_spread(crude_price: pd.Series, fuel_price: pd.Series,
                      conversion_ratio: float = 7.33) -> pd.Series:
    """裂解价差（原油 - 燃料油）"""
    return crude_price - fuel_price / conversion_ratio


def calc_domestic_foreign_spread(domestic_price: pd.Series, mops_price: pd.Series,
                                 fx_rate: pd.Series, misc_cost: float = 100.0) -> pd.Series:
    """内外价差（国内价 - 理论进口成本）"""
    import_parity = mops_price * fx_rate + misc_cost
    return domestic_price - import_parity


def calc_wti_brent_spread(wti_price: pd.Series, brent_price: pd.Series) -> pd.Series:
    """WTI-Brent价差"""
    return wti_price - brent_price


def calculate_spread_indicators(fu_df, lu_df=None, brent_df=None, mops_df=None, fx_df=None):
    """计算全部价差指标"""
    spreads = {}

    if lu_df is not None and fu_df is not None:
        merged = pd.merge(
            fu_df[["date", "close"]].rename(columns={"close": "fu_close"}),
            lu_df[["date", "close"]].rename(columns={"close": "lu_close"}),
            on="date", how="inner"
        )
        if not merged.empty:
            spread = calc_high_low_sulfur_spread(merged["lu_close"], merged["fu_close"])
            spreads["high_low_sulfur"] = {
                "type": "高低硫价差(LU-FU)",
                "values": spread,
                "unit": "元/吨",
                "normal_range": (300, 500),
            }

    if brent_df is not None and fu_df is not None:
        merged = pd.merge(
            fu_df[["date", "close"]].rename(columns={"close": "fu_close"}),
            brent_df[["date", "close"]].rename(columns={"close": "brent_close"}),
            on="date", how="inner"
        )
        if not merged.empty:
            spread = calc_crack_spread(merged["brent_close"], merged["fu_close"])
            spreads["crack_spread"] = {
                "type": "裂解价差(原油-燃料油)",
                "values": spread,
                "unit": "美元/桶",
                "normal_range": None,
            }

    if mops_df is not None and fu_df is not None and fx_df is not None:
        merged = pd.merge(
            fu_df[["date", "close"]].rename(columns={"close": "fu_close"}),
            mops_df[["date", "close"]].rename(columns={"close": "mops_close"}),
            on="date", how="inner"
        )
        merged = pd.merge(
            merged,
            fx_df[["date", "close"]].rename(columns={"close": "fx_rate"}),
            on="date", how="inner"
        )
        if not merged.empty:
            spread = calc_domestic_foreign_spread(
                merged["fu_close"], merged["mops_close"], merged["fx_rate"]
            )
            spreads["domestic_foreign"] = {
                "type": "内外价差(FU-MOPS)",
                "values": spread,
                "unit": "元/吨",
                "normal_range": (20, 40),
            }

    for key, data in spreads.items():
        vals = data["values"].dropna()
        if not vals.empty:
            data["latest"] = float(vals.iloc[-1])
            data["mean"] = float(vals.mean())
            data["std"] = float(vals.std())
            data["min"] = float(vals.min())
            data["max"] = float(vals.max())
            data["percentile"] = float((vals < vals.iloc[-1]).sum() / len(vals) * 100)

    return spreads


# ========== 五、信号判定逻辑 ==========

def _judge_ma_alignment(df: pd.DataFrame) -> pd.Series:
    """判定均线排列状态"""
    cond_bull = (df["MA5"] > df["MA10"]) & (df["MA10"] > df["MA20"]) & (df["MA20"] > df["MA60"])
    cond_bear = (df["MA5"] < df["MA10"]) & (df["MA10"] < df["MA20"]) & (df["MA20"] < df["MA60"])
    result = pd.Series("震荡", index=df.index)
    result = result.where(~cond_bull, "多头")
    result = result.where(~cond_bear, "空头")
    return result


def judge_rsi_signal(v: float) -> IndicatorSignal:
    if v > 70:
        return IndicatorSignal("RSI(14)", v, "超买", 4, "RSI进入超买区，价格有回调风险")
    elif v > 60:
        return IndicatorSignal("RSI(14)", v, "偏多", 2, "RSI偏强，多头动能占优")
    elif v < 30:
        return IndicatorSignal("RSI(14)", v, "超卖", 4, "RSI进入超卖区，价格有反弹需求")
    elif v < 40:
        return IndicatorSignal("RSI(14)", v, "偏空", 2, "RSI偏弱，空头动能占优")
    return IndicatorSignal("RSI(14)", v, "中性", 1, "RSI处于中性区间")


def judge_stoch_signal(k: float, d: float) -> IndicatorSignal:
    if k > 80 and d > 80:
        return IndicatorSignal("STOCH(9,6)", k, "超买", 4, "随机指标进入超买区")
    elif k < 20 and d < 20:
        return IndicatorSignal("STOCH(9,6)", k, "超卖", 4, "随机指标进入超卖区")
    elif k > d:
        return IndicatorSignal("STOCH(9,6)", k, "偏多", 2, "K线在D线上方")
    elif k < d:
        return IndicatorSignal("STOCH(9,6)", k, "偏空", 2, "K线在D线下方")
    return IndicatorSignal("STOCH(9,6)", k, "中性", 1, "随机指标中性")


def judge_stochrsi_signal(k: float) -> IndicatorSignal:
    if k > 80:
        return IndicatorSignal("STOCHRSI(14)", k, "超买", 4, "随机RSI超买")
    elif k < 20:
        return IndicatorSignal("STOCHRSI(14)", k, "超卖", 4, "随机RSI超卖")
    return IndicatorSignal("STOCHRSI(14)", k, "中性", 1, "随机RSI中性")


def judge_adx_signal(adx: float, plus_di: float, minus_di: float) -> IndicatorSignal:
    if adx > 25 and plus_di > minus_di:
        return IndicatorSignal("ADX(14)", adx, "强多头趋势", 4, f"ADX={adx:.1f}>25且+DI>-DI，强多头")
    elif adx > 25 and minus_di > plus_di:
        return IndicatorSignal("ADX(14)", adx, "强空头趋势", 4, f"ADX={adx:.1f}>25且-DI>+DI，强空头")
    elif adx > 20:
        return IndicatorSignal("ADX(14)", adx, "趋势形成中", 3, f"ADX={adx:.1f}，趋势正在形成")
    return IndicatorSignal("ADX(14)", adx, "无趋势", 1, f"ADX={adx:.1f}<20，市场震荡")


def judge_williams_r_signal(v: float) -> IndicatorSignal:
    if v > -20:
        return IndicatorSignal("Williams %R", v, "超买", 4, "Williams %R进入超买区")
    elif v < -80:
        return IndicatorSignal("Williams %R", v, "超卖", 4, "Williams %R进入超卖区")
    return IndicatorSignal("Williams %R", v, "中性", 1, "Williams %R中性")


def judge_cci_signal(v: float) -> IndicatorSignal:
    if v > 100:
        return IndicatorSignal("CCI(14)", v, "超买", 4, "CCI突破+100")
    elif v < -100:
        return IndicatorSignal("CCI(14)", v, "超卖", 4, "CCI跌破-100")
    elif v > 0:
        return IndicatorSignal("CCI(14)", v, "偏多", 2, "CCI为正")
    elif v < 0:
        return IndicatorSignal("CCI(14)", v, "偏空", 2, "CCI为负")
    return IndicatorSignal("CCI(14)", v, "中性", 1, "CCI中性")


def judge_uo_signal(v: float) -> IndicatorSignal:
    if v > 70:
        return IndicatorSignal("Ultimate Osc", v, "超买", 4, "终极震荡指标超买")
    elif v < 30:
        return IndicatorSignal("Ultimate Osc", v, "超卖", 4, "终极震荡指标超卖")
    return IndicatorSignal("Ultimate Osc", v, "中性", 1, "终极震荡指标中性")


def judge_roc_signal(v: float) -> IndicatorSignal:
    if v > 5:
        return IndicatorSignal("ROC", v, "强势上涨", 3, f"ROC={v:.2f}%，动能强劲")
    elif v < -5:
        return IndicatorSignal("ROC", v, "强势下跌", 3, f"ROC={v:.2f}%，下跌动能强")
    elif v > 0:
        return IndicatorSignal("ROC", v, "偏多", 2, f"ROC={v:.2f}%")
    elif v < 0:
        return IndicatorSignal("ROC", v, "偏空", 2, f"ROC={v:.2f}%")
    return IndicatorSignal("ROC", v, "中性", 1, "ROC接近零轴")


def judge_bull_bear_signal(bull: float, bear: float) -> IndicatorSignal:
    if bull > 0 and bear > 0:
        return IndicatorSignal("Bull/Bear", bull, "多头强势", 4, "多空力量均为正，多头占优")
    elif bull < 0 and bear < 0:
        return IndicatorSignal("Bull/Bear", bull, "空头强势", 4, "多空力量均为负，空头占优")
    elif bull > 0 and bear < 0:
        return IndicatorSignal("Bull/Bear", bull, "多头转强", 3, "多头力量转正，空头力量为负")
    elif bull < 0 and bear > 0:
        return IndicatorSignal("Bull/Bear", bull, "空头转强", 3, "空头力量转正，多头力量为负")
    return IndicatorSignal("Bull/Bear", bull, "中性", 1, "多空力量均衡")


def judge_macd_signal(dif: float, dea: float, hist: float) -> IndicatorSignal:
    if dif > dea and hist > 0:
        return IndicatorSignal("MACD", hist, "多头", 3, "DIF在DEA上方，MACD柱为正")
    elif dif < dea and hist < 0:
        return IndicatorSignal("MACD", hist, "空头", 3, "DIF在DEA下方，MACD柱为负")
    elif dif > dea and hist < 0:
        return IndicatorSignal("MACD", hist, "多头衰减", 2, "MACD柱缩短，多头动能衰减")
    elif dif < dea and hist > 0:
        return IndicatorSignal("MACD", hist, "空头衰减", 2, "MACD柱缩短，空头动能衰减")
    return IndicatorSignal("MACD", hist, "中性", 1, "MACD无明确方向")


def generate_comprehensive_signal(df: pd.DataFrame) -> list[IndicatorSignal]:
    """综合所有技术指标生成信号判定"""
    if df.empty:
        return []

    latest = df.iloc[-1]
    signals = []

    if "RSI_14" in latest and pd.notna(latest["RSI_14"]):
        signals.append(judge_rsi_signal(latest["RSI_14"]))

    if "STOCH_K" in latest and pd.notna(latest["STOCH_K"]):
        signals.append(judge_stoch_signal(latest["STOCH_K"], latest.get("STOCH_D", 50)))

    if "STOCHRSI_K" in latest and pd.notna(latest["STOCHRSI_K"]):
        signals.append(judge_stochrsi_signal(latest["STOCHRSI_K"]))

    if all(col in latest for col in ["MACD_DIF", "MACD_DEA", "MACD_HIST"]):
        if all(pd.notna(latest[col]) for col in ["MACD_DIF", "MACD_DEA", "MACD_HIST"]):
            signals.append(judge_macd_signal(latest["MACD_DIF"], latest["MACD_DEA"], latest["MACD_HIST"]))

    if all(col in latest for col in ["ADX", "PLUS_DI", "MINUS_DI"]):
        if all(pd.notna(latest[col]) for col in ["ADX", "PLUS_DI", "MINUS_DI"]):
            signals.append(judge_adx_signal(latest["ADX"], latest["PLUS_DI"], latest["MINUS_DI"]))

    if "WILLIAMS_R" in latest and pd.notna(latest["WILLIAMS_R"]):
        signals.append(judge_williams_r_signal(latest["WILLIAMS_R"]))

    if "CCI_14" in latest and pd.notna(latest["CCI_14"]):
        signals.append(judge_cci_signal(latest["CCI_14"]))

    if "UO" in latest and pd.notna(latest["UO"]):
        signals.append(judge_uo_signal(latest["UO"]))

    if "ROC" in latest and pd.notna(latest["ROC"]):
        signals.append(judge_roc_signal(latest["ROC"]))

    if "BULL_POWER" in latest and "BEAR_POWER" in latest:
        if pd.notna(latest["BULL_POWER"]) and pd.notna(latest["BEAR_POWER"]):
            signals.append(judge_bull_bear_signal(latest["BULL_POWER"], latest["BEAR_POWER"]))

    if "ATR_14" in latest and pd.notna(latest["ATR_14"]):
        atr_pct = latest["ATR_14"] / latest["close"] * 100 if latest["close"] != 0 else 0
        if atr_pct > 3:
            signals.append(IndicatorSignal("ATR(14)", latest["ATR_14"], "高波动", 3, f"ATR占比{atr_pct:.1f}%"))
        elif atr_pct < 1:
            signals.append(IndicatorSignal("ATR(14)", latest["ATR_14"], "低波动", 2, f"ATR占比{atr_pct:.1f}%"))
        else:
            signals.append(IndicatorSignal("ATR(14)", latest["ATR_14"], "正常波动", 1, f"ATR占比{atr_pct:.1f}%"))

    if "MA_ALIGN" in latest:
        align = latest["MA_ALIGN"]
        if align == "多头":
            signals.append(IndicatorSignal("均线排列", None, "多头排列", 4, "MA5>MA10>MA20>MA60"))
        elif align == "空头":
            signals.append(IndicatorSignal("均线排列", None, "空头排列", 4, "MA5<MA10<MA20<MA60"))
        else:
            signals.append(IndicatorSignal("均线排列", None, "震荡", 2, "均线交织"))

    return signals


# ========== 六、演示数据生成 ==========

def generate_demo_data(days: int = 120) -> pd.DataFrame:
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


# ========== 七、结果格式化输出 ==========

def format_indicator_report(df: pd.DataFrame, signals: list[IndicatorSignal]) -> str:
    latest = df.iloc[-1]
    engine = "Ta-Lib" if HAS_TALIB else "pandas"
    lines = [
        "=" * 60,
        "  燃料油技术指标分析报告",
        "=" * 60,
        f"  数据截止: {latest.get('date', 'N/A')}",
        f"  最新收盘: {latest['close']}",
        f"  计算引擎: {engine}",
        "",
        "  ── 技术指标一览 ──",
    ]

    indicators = [
        ("RSI_14", "RSI(14)"), ("STOCH_K", "STOCH %K"), ("STOCH_D", "STOCH %D"),
        ("STOCHRSI_K", "STOCHRSI %K"), ("STOCHRSI_D", "STOCHRSI %D"),
        ("MACD_DIF", "MACD DIF"), ("MACD_DEA", "MACD DEA"), ("MACD_HIST", "MACD柱"),
        ("ADX", "ADX(14)"), ("PLUS_DI", "+DI"), ("MINUS_DI", "-DI"),
        ("WILLIAMS_R", "Williams %R"), ("CCI_14", "CCI(14)"), ("ATR_14", "ATR(14)"),
        ("UO", "Ultimate Osc"), ("ROC", "ROC"),
        ("BULL_POWER", "Bull Power"), ("BEAR_POWER", "Bear Power"),
    ]
    for col, name in indicators:
        if col in latest and pd.notna(latest[col]):
            lines.append(f"  {name:16s} = {latest[col]:>10.2f}")

    lines.append("")
    lines.append("  ── 均线系统 ──")
    for p in [5, 10, 20, 60]:
        col = f"MA{p}"
        if col in latest and pd.notna(latest[col]):
            diff_pct = (latest["close"] - latest[col]) / latest[col] * 100
            lines.append(f"  MA{p:2d} = {latest[col]:>10.2f}  (偏离 {diff_pct:+.2f}%)")
    if "MA_ALIGN" in latest:
        lines.append(f"  排列状态: {latest['MA_ALIGN']}")

    lines.append("")
    lines.append("  ── 信号判定 ──")
    for sig in signals:
        lines.append(f"  [{sig.signal:6s}] {sig.indicator:16s} | {sig.description}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


# ========== 八、主入口 ==========

def load_from_duckdb(db_path: str, symbol: str) -> pd.DataFrame:
    """从DuckDB读取K线数据"""
    import duckdb
    conn = duckdb.connect(db_path, read_only=True)
    try:
        table_name = f"kline_{symbol.lower()}"
        df = conn.execute(f"SELECT * FROM {table_name} ORDER BY date").fetchdf()
    finally:
        conn.close()
    return df


def save_indicators_to_duckdb(db_path: str, symbol: str, df: pd.DataFrame, signals: list[IndicatorSignal]):
    """将计算后的指标数据和信号存入DuckDB"""
    import duckdb
    conn = duckdb.connect(db_path)
    try:
        indicator_table = f"indicators_{symbol.lower()}"
        conn.execute(f"DROP TABLE IF EXISTS {indicator_table}")
        conn.execute(f"CREATE TABLE {indicator_table} AS SELECT * FROM df")
        count = conn.execute(f"SELECT COUNT(*) FROM {indicator_table}").fetchone()[0]
        logger.info(f"  ✅ {indicator_table}: {count} 条记录已入库")

        signals_data = []
        for s in signals:
            signals_data.append({
                "indicator": s.indicator, "value": s.value, "signal": s.signal,
                "strength": s.strength, "description": s.description,
            })
        if signals_data:
            signals_df = pd.DataFrame(signals_data)
            signals_table = f"signals_{symbol.lower()}"
            conn.execute(f"DROP TABLE IF EXISTS {signals_table}")
            conn.execute(f"CREATE TABLE {signals_table} AS SELECT * FROM signals_df")
            logger.info(f"  ✅ {signals_table}: {len(signals_data)} 条信号已入库")
    finally:
        conn.close()


# ========== 七、燃料油五层量化打分框架 ==========

@dataclass
class FuelOilScore:
    """燃料油量化打分结果"""
    cost_score: float      # 成本因子得分 (0-100)
    crack_score: float    # 裂解因子得分 (0-100)
    sg_score: float       # 新加坡外盘得分 (0-100)
    dom_score: float      # 国内供需得分 (0-100)
    struct_score: float    # 盘面结构得分 (0-100)
    total_score: float     # 综合得分 (0-100)
    signal: str           # 信号：做多/观望/做空
    confidence: str       # 置信度：高/中/低


def calculate_historical_percentile(series: pd.Series, current_value: float, 
                                   lookback_days: int = 756) -> float:
    """计算近N日历史分位（默认3年=756交易日）"""
    if len(series) < 20:
        return 50.0  # 数据不足返回中性
    recent = series.tail(lookback_days)
    percentile = (recent < current_value).sum() / len(recent) * 100
    return min(100, max(0, percentile))


def calculate_fuel_oil_score(
    fu_close: float = 0.0,
    lu_close: float = 0.0,
    brent_close: float = 0.0,
    crack_spread_fu: float = 0.0,
    crack_spread_lu: float = 0.0,
    lu_fu_spread: float = 0.0,
    singapore_inventory_percentile: float = 50.0,
    basis: float = 0.0,
    contango: bool = False,
    shandong_refinery_util: float = 50.0,
    india_fuel_oil_import_yoy: float = 0.0,
    bdi_index_percentile: float = 50.0,
    policy_factor: float = 0.0,
    # 以下为各指标的历史分位（0-100），需由调用方预先计算
    brent_20d_chg_percentile: float = 50.0,
    sc_brent_spread_percentile: float = 50.0,
    usdcny_percentile: float = 50.0,
    vlcc_freight_percentile: float = 50.0,
    geopolitics_score: float = 0.0,
    fu_crack_percentile: float = 50.0,
    lu_crack_percentile: float = 50.0,
    lu_fu_spread_percentile: float = 50.0,
    refinery_util_percentile: float = 50.0,
    india_import_percentile: float = 50.0,
    bdi_percentile: float = 50.0,
    sg_inventory_percentile: float = 50.0,
    sg_inv_wow_percentile: float = 50.0,
    arrival_percentile: float = 50.0,
    mops_percentile: float = 50.0,
    warehouse_percentile: float = 50.0,
    import_percentile: float = 50.0,
    production_percentile: float = 50.0,
    bunker_percentile: float = 50.0,
    basis_percentile: float = 50.0,
    month_spread_percentile: float = 50.0,
) -> FuelOilScore:
    """
    燃料油五层量化打分（v2.14.0 修正版）

    所有分位参数(0-100)需由调用方基于历史数据预先计算后传入。
    本函数仅负责加权合成和信号判定，不自行计算分位。

    参数:
        fu_close: FU主力收盘价（元/吨）
        lu_close: LU主力收盘价（元/吨）
        brent_close: 布伦特原油价格（美元/桶）
        crack_spread_fu: FU裂解价差（元/吨）
        crack_spread_lu: LU柴油裂差（元/吨）
        lu_fu_spread: 高低硫价差（LU-FU，元/吨）
        singapore_inventory_percentile: 新加坡库存分位（0-100，越高库存越多）
        basis: 基差（现货-期货，元/吨）
        contango: 是否Contango结构
        shandong_refinery_util: 山东地炼开工率分位（0-100）
        india_fuel_oil_import_yoy: 印度燃料油进口同比（%）
        bdi_index_percentile: BDI指数分位（0-100）
        policy_factor: 政策因子（-20 to +20）
        brent_20d_chg_percentile: 布伦特20日涨跌幅分位（0-100）
        sc_brent_spread_percentile: SC/布伦特价差分位（0-100）
        usdcny_percentile: USDCNY汇率分位（0-100）
        vlcc_freight_percentile: VLCC运价分位（0-100）
        geopolitics_score: 中东地缘得分（0-40）
        fu_crack_percentile: FU原油裂解分位（0-100）
        lu_crack_percentile: LU柴油裂解分位（0-100）
        lu_fu_spread_percentile: LU-FU价差分位（0-100）
        refinery_util_percentile: 地炼开工分位（0-100）
        india_import_percentile: 印度进口分位（0-100）
        bdi_percentile: BDI分位（0-100）
        sg_inventory_percentile: 新加坡库存分位（0-100，反向：越高越利空）
        sg_inv_wow_percentile: 库存周环比分位（0-100，反向）
        arrival_percentile: 到港量分位（0-100，反向）
        mops_percentile: MOPS现货涨跌分位（0-100）
        warehouse_percentile: 仓单分位（0-100，反向）
        import_percentile: 进口分位（0-100，反向）
        production_percentile: 炼厂产出分位（0-100，反向）
        bunker_percentile: 保税加注分位（0-100）
        basis_percentile: 基差分位（0-100）
        month_spread_percentile: 月间价差分位（0-100）

    返回:
        FuelOilScore: 量化打分结果
    """
    # ===== 模块1: 成本因子 (顶层权重25%, 模块内权重和=100%) =====
    # 布伦特20日涨跌幅分位 40%、SC/布伦特价差分位 20%、USDCNY汇率分位 20%、VLCC运价分位 15%、地缘 5%
    cost_score = (
        brent_20d_chg_percentile * 0.40 +
        sc_brent_spread_percentile * 0.20 +
        usdcny_percentile * 0.20 +
        vlcc_freight_percentile * 0.15 +
        geopolitics_score * 0.05
    )

    # ===== 模块2: 裂解因子 (顶层权重30%, 模块内权重和=100%) =====
    # FU裂解 40%、LU裂解 25%、LU-FU价差 5%、地炼开工 10%、印度进口 10%、BDI 10%
    crack_score = (
        fu_crack_percentile * 0.40 +
        lu_crack_percentile * 0.25 +
        lu_fu_spread_percentile * 0.05 +
        refinery_util_percentile * 0.10 +
        india_import_percentile * 0.10 +
        bdi_percentile * 0.10
    )

    # ===== 模块3: 新加坡外盘因子 (顶层权重20%, 模块内权重和=100%) =====
    # 库存 50%、库存周环比 20%、到港量 20%、MOPS 10%
    # 库存和到港量反向：库存越高/到港越多 → 越利空
    sg_score = (
        (100 - sg_inventory_percentile) * 0.50 +
        (100 - sg_inv_wow_percentile) * 0.20 +
        (100 - arrival_percentile) * 0.20 +
        mops_percentile * 0.10
    )

    # ===== 模块4: 国内供需+政策因子 (顶层权重15%, 模块内权重和=100%) =====
    # 仓单 30%、进口 25%、炼厂产出 20%、保税加注 15%、政策 10%
    dom_score = (
        (100 - warehouse_percentile) * 0.30 +
        (100 - import_percentile) * 0.25 +
        (100 - production_percentile) * 0.20 +
        bunker_percentile * 0.15 +
        (policy_factor + 50) * 0.10
    )

    # ===== 模块5: 盘面结构因子 (顶层权重10%, 模块内权重和=100%) =====
    struct_score = (
        basis_percentile * 0.50 +
        month_spread_percentile * 0.50
    )

    # ===== 综合得分 =====
    total_score = (
        cost_score * 0.25 +
        crack_score * 0.30 +
        sg_score * 0.20 +
        dom_score * 0.15 +
        struct_score * 0.10
    )

    # 信号判定
    if total_score > 65:
        signal = "做多"
        confidence = "高" if total_score > 75 else "中"
    elif total_score < 35:
        signal = "做空"
        confidence = "高" if total_score < 25 else "中"
    else:
        signal = "观望"
        confidence = "-"

    return FuelOilScore(
        cost_score=round(cost_score, 1),
        crack_score=round(crack_score, 1),
        sg_score=round(sg_score, 1),
        dom_score=round(dom_score, 1),
        struct_score=round(struct_score, 1),
        total_score=round(total_score, 1),
        signal=signal,
        confidence=confidence
    )


def format_fuel_oil_score_report(score: FuelOilScore) -> str:
    """格式化燃料油打分报告"""
    lines = [
        "=" * 60,
        "  燃料油五层量化打分报告",
        "=" * 60,
        f"  综合得分: {score.total_score:.1f} ({score.signal})",
        f"  置信度: {score.confidence}",
        "",
        "  ── 分项得分 ──",
        f"  成本因子 (25%):  {score.cost_score:.1f}",
        f"  裂解因子 (30%):  {score.crack_score:.1f}",
        f"  新加坡外盘(20%):  {score.sg_score:.1f}",
        f"  国内供需 (15%):  {score.dom_score:.1f}",
        f"  盘面结构 (10%):  {score.struct_score:.1f}",
        "=" * 60,
    ]
    return "\n".join(lines)


# ========== 八、裂解价差因子详细计算 ==========

@dataclass
class CrackSpreadScore:
    """裂解价差因子打分结果"""
    # FU高硫裂解
    fu_crack_score: float      # FU主裂解得分 (0-100)
    fu_crack_value: float      # FU裂解绝对值
    refinery_util_score: float  # 地炼开工得分
    india_import_score: float  # 印度进口得分
    russia_supply_score: float # 俄油到货得分 (反向)
    # LU低硫裂解
    lu_crack_score: float      # LU主裂解得分
    lu_crack_value: float      # LU裂解绝对值
    bdi_score: float           # BDI航运得分
    bunker_score: float        # 保税加注得分
    # 跨品种
    lu_fu_spread_score: float  # LU-FU价差得分
    lu_fu_spread_value: float  # LU-FU价差值
    # 综合
    crack_total: float         # 裂解模块综合得分
    crack_signal: str          # 信号


class CrackSpreadCalculator:
    """裂解价差因子计算器（FU/LU分开量化）"""
    
    # 换算系数
    BARREL_TO_TON = 7.33  # 桶/吨换算
    
    def __init__(self, lookback_days: int = 756):  # 默认3年
        self.lookback_days = lookback_days
    
    def calc_fu_crack_spread(self, fu_price: float, brent: float, 
                             usdcny: float = 7.2) -> float:
        """计算FU裂解价差 = FU现货 - 布伦特折算成本"""
        crude_cost = brent * self.BARREL_TO_TON * usdcny
        return fu_price - crude_cost
    
    def calc_lu_crack_spread(self, lu_price: float, diesel_price: float) -> float:
        """计算LU裂解价差 = LU现货 - 柴油折算成本"""
        return lu_price - diesel_price
    
    def calc_lu_fu_spread(self, lu_price: float, fu_price: float) -> float:
        """计算高低硫价差 = LU - FU"""
        return lu_price - fu_price
    
    def calc_historical_percentile(self, series: pd.Series, current: float) -> float:
        """计算近N日历史分位"""
        if len(series) < 20:
            return 50.0
        recent = series.tail(self.lookback_days)
        percentile = (recent < current).sum() / len(recent) * 100
        return min(100, max(0, percentile))
    
    def calc_seasonal_factor(self, month: int) -> float:
        """计算季节性因子（5-9月印度发电旺季）"""
        if month in [5, 6, 7, 8, 9]:
            return 8.0  # 发电旺季加分
        return 0.0
    
    def calculate(
        self,
        fu_price: float,
        lu_price: float,
        brent: float,
        diesel_price: float,
        usdcny: float = 7.2,
        refinery_util: float = 50.0,      # 山东地炼开工分位
        india_import_yoy: float = 0.0,    # 印度进口同比
        russia_supply_yoy: float = 0.0,  # 俄油到货同比
        bdi_percentile: float = 50.0,     # BDI分位
        bunker_yoy: float = 0.0,          # 保税加注同比
        month: int = None,                # 当前月份
    ) -> CrackSpreadScore:
        """
        计算裂解价差因子综合得分
        
        参数:
            fu_price: FU现货价(元/吨)
            lu_price: LU现货价(元/吨)
            brent: 布伦特原油(美元/桶)
            diesel_price: 柴油价格(元/吨)
            usdcny: 美元兑人民币汇率
            refinery_util: 山东地炼开工率分位(0-100)
            india_import_yoy: 印度高硫燃料油进口同比(%)
            russia_supply_yoy: 俄高硫燃料油亚太到货同比(%)
            bdi_percentile: BDI指数分位(0-100)
            bunker_yoy: 国内保税船用油加注同比(%)
            month: 当前月份(1-12)
        
        返回:
            CrackSpreadScore: 裂解因子打分结果
        """
        # 计算裂解价差
        fu_crack = self.calc_fu_crack_spread(fu_price, brent, usdcny)
        lu_crack = self.calc_lu_crack_spread(lu_price, diesel_price)
        lu_fu_spread = self.calc_lu_fu_spread(lu_price, fu_price)
        
        # FU裂解得分 (模块内权重40%)
        fu_crack_score = self.calc_historical_percentile(
            pd.Series([fu_crack]), fu_crack
        )

        # 地炼开工得分 (模块内权重10%)
        refinery_util_score = refinery_util

        # 印度进口得分 (模块内权重10%)
        india_import_score = min(100, max(0, 50 + india_import_yoy))

        # 俄油到货得分 (模块内权重5%，反向)
        russia_supply_score = min(100, max(0, 50 - russia_supply_yoy * 2))

        # 季节性因子 (模块内权重5%)
        seasonal_factor = self.calc_seasonal_factor(month) if month else 0

        # LU裂解得分 (模块内权重25%)
        lu_crack_score = self.calc_historical_percentile(
            pd.Series([lu_crack]), lu_crack
        )

        # BDI得分 (模块内权重10%)
        bdi_score = bdi_percentile

        # 保税加注得分 (模块内权重5%)
        bunker_score = min(100, max(0, 50 + bunker_yoy))

        # LU-FU价差得分 (模块内权重5%)
        lu_fu_spread_score = self.calc_historical_percentile(
            pd.Series([lu_fu_spread]), lu_fu_spread
        )
        
        # 综合裂解得分（模块内权重归一化，和=100%）
        # 原始顶层权重和=44%，归一化系数=1/0.44≈2.2727
        crack_total = (
            fu_crack_score * 0.40 +    # FU主裂解 (原12%/44%)
            lu_crack_score * 0.25 +    # LU主裂解 (原8%/44%)
            lu_fu_spread_score * 0.05 + # LU-FU价差 (原5%/44%)
            refinery_util_score * 0.10 + # 地炼开工 (原5%/44%)
            india_import_score * 0.10 + # 印度进口 (原4%/44%)
            bdi_score * 0.10           # BDI航运 (原4%/44%)
        )
        crack_total = min(100, max(0, crack_total))
        
        # 信号判定
        if crack_total > 65:
            crack_signal = "偏多"
        elif crack_total < 35:
            crack_signal = "偏空"
        else:
            crack_signal = "中性"
        
        return CrackSpreadScore(
            fu_crack_score=round(fu_crack_score, 1),
            fu_crack_value=round(fu_crack, 2),
            refinery_util_score=round(refinery_util_score, 1),
            india_import_score=round(india_import_score, 1),
            russia_supply_score=round(russia_supply_score, 1),
            lu_crack_score=round(lu_crack_score, 1),
            lu_crack_value=round(lu_crack, 2),
            bdi_score=round(bdi_score, 1),
            bunker_score=round(bunker_score, 1),
            lu_fu_spread_score=round(lu_fu_spread_score, 1),
            lu_fu_spread_value=round(lu_fu_spread, 2),
            crack_total=round(crack_total, 1),
            crack_signal=crack_signal
        )


def format_crack_spread_report(score: CrackSpreadScore) -> str:
    """格式化裂解价差因子报告"""
    lines = [
        "=" * 60,
        "  裂解价差因子详细报告",
        "=" * 60,
        f"  综合得分: {score.crack_total:.1f} ({score.crack_signal})",
        "",
        "  ── FU高硫裂解 ──",
        f"  FU裂解分位: {score.fu_crack_score:.1f}",
        f"  FU裂解值: {score.fu_crack_value:.2f} 元/吨",
        f"  地炼开工分位: {score.refinery_util_score:.1f}",
        f"  印度进口得分: {score.india_import_score:.1f}",
        f"  俄油到货得分: {score.russia_supply_score:.1f}",
        "",
        "  ── LU低硫裂解 ──",
        f"  LU裂解分位: {score.lu_crack_score:.1f}",
        f"  LU裂解值: {score.lu_crack_value:.2f} 元/吨",
        f"  BDI航运分位: {score.bdi_score:.1f}",
        f"  保税加注得分: {score.bunker_score:.1f}",
        "",
        "  ── 跨品种价差 ──",
        f"  LU-FU价差分位: {score.lu_fu_spread_score:.1f}",
        f"  LU-FU价差值: {score.lu_fu_spread_value:.2f} 元/吨",
        "=" * 60,
    ]
    return "\n".join(lines)


# ========== 九、完整五层量化打分框架 ==========

@dataclass
class CompleteFuelOilScore:
    """完整燃料油五层量化打分结果"""
    # 成本因子
    cost_score: float           # 成本因子总分
    brent_score: float         # 布伦特得分
    fx_score: float            # 汇率得分
    freight_score: float      # 运费得分
    geopolitics_score: float  # 地缘得分
    # 裂解因子
    crack_score: float         # 裂解因子总分
    fu_crack_score: float     # FU主裂解
    lu_crack_score: float     # LU主裂解
    lu_fu_spread_score: float # LU-FU价差
    refinery_score: float     # 地炼开工
    india_score: float        # 印度进口
    bdi_score: float          # BDI航运
    bunker_score: float       # 保税加注
    # 新加坡外盘
    sg_score: float           # 新加坡外盘总分
    inventory_score: float   # 新加坡库存
    arrival_score: float     # 到港船货
    mops_score: float        # MOPS现货
    # 国内供需
    dom_score: float          # 国内供需总分
    production_score: float  # 炼厂产出
    import_score: float       # 进口
    warehouse_score: float   # 仓单
    policy_score: float      # 政策
    # 盘面结构
    struct_score: float       # 盘面结构总分
    basis_score: float       # 基差
    spread_score: float      # 月差
    # 综合
    total_score: float       # 综合得分
    signal: str              # 信号
    confidence: str          # 置信度


class CompleteFuelOilScorer:
    """
    完整燃料油五层量化打分计算器
    
    顶层权重：
    - 成本因子: 25%
    - 裂解因子: 30%
    - 新加坡外盘: 20%
    - 国内供需: 15%
    - 盘面结构: 10%
    """
    
    BARREL_TO_TON = 7.33  # 桶/吨换算
    
    def __init__(self, lookback_days: int = 756):
        self.lookback_days = lookback_days
    
    def _calc_percentile(self, series: pd.Series, value: float) -> float:
        """计算历史分位"""
        if len(series) < 20:
            return 50.0
        recent = series.tail(self.lookback_days)
        percentile = (recent < value).sum() / len(recent) * 100
        return min(100, max(0, percentile))
    
    def _calc_reverse_percentile(self, series: pd.Series, value: float) -> float:
        """计算反向历史分位（值越大得分越低）"""
        return 100 - self._calc_percentile(series, value)
    
    def calculate(
        self,
        # 行情数据
        fu_close: float = 0.0,
        lu_close: float = 0.0,
        brent: float = 0.0,
        sc: float = 0.0,
        usdcny: float = 7.2,
        freight: float = 0.0,  # VLCC运费
        # 裂解价差
        crack_fu: float = 0.0,
        crack_lu: float = 0.0,
        crack_refinery: float = 50.0,  # 地炼开工分位
        india_import_yoy: float = 0.0,
        bdi_percentile: float = 50.0,
        bunker_yoy: float = 0.0,
        russia_yoy: float = 0.0,
        month: int = None,
        # 新加坡外盘
        sg_inventory: float = 0.0,
        sg_inventory_prev: float = 0.0,
        sg_inventory_yoy: float = 0.0,
        arrival_yoy: float = 0.0,
        mops_change: float = 0.0,
        # 国内供需
        production_yoy: float = 0.0,
        import_yoy: float = 0.0,
        warehouse_level: float = 50.0,  # 仓单分位
        policy_factor: int = 0,  # -1=退税收紧, 0=正常, 1=混兑放开
        # 盘面结构
        basis: float = 0.0,
        month_spread: float = 0.0,
        # 地缘
        geopolitics: int = 0,  # 0=无, 1=局部, 2=红海, 3=霍尔木兹
        # 历史数据（用于分位计算，key为指标名，value为pd.Series）
        history: dict = None,
    ) -> CompleteFuelOilScore:
        """
        计算完整五层量化打分
        
        参数:
            fu_close: FU收盘价
            lu_close: LU收盘价
            brent: 布伦特原油价格
            sc: SC原油价格
            usdcny: 美元兑人民币汇率
            freight: VLCC运费分位
            crack_fu: FU裂解价差
            crack_lu: LU裂解价差
            crack_refinery: 地炼开工分位
            india_import_yoy: 印度进口同比
            bdi_percentile: BDI分位
            bunker_yoy: 保税加注同比
            russia_yoy: 俄油到货同比
            month: 当前月份
            sg_inventory: 新加坡库存
            sg_inventory_prev: 上周新加坡库存
            sg_inventory_yoy: 新加坡库存同比
            arrival_yoy: 到港船货同比
            mops_change: MOPS涨跌幅
            production_yoy: 炼厂产出同比
            import_yoy: 进口同比
            warehouse_level: 仓单分位
            policy_factor: 政策因子
            basis: 基差
            month_spread: 月差
            geopolitics: 地缘冲突等级
        """
        
        # 辅助函数：优先使用历史数据计算分位，无历史则用值本身
        def _pct(key: str, value: float, reverse: bool = False) -> float:
            """计算分位数：有历史数据用真实分位，无历史用值本身（假设50中性）"""
            if history and key in history and len(history[key]) >= 20:
                return self._calc_reverse_percentile(history[key], value) if reverse else self._calc_percentile(history[key], value)
            return 50.0  # 无历史数据时返回中性值

        # ===== 1. 成本因子 (顶层权重25%, 模块内权重和=100%) =====
        # 模块内权重: 布伦特涨跌幅40%、SC/布伦特价差20%、汇率20%、VLCC运价15%、地缘5%
        sc_brent_diff = sc * usdcny - brent
        brent_score = _pct('brent', brent)
        sc_brent_score = _pct('sc_brent_diff', sc_brent_diff)
        crude_score = brent_score * 0.67 + sc_brent_score * 0.33  # 布伦特+价差合并

        fx_score = _pct('usdcny', usdcny)
        freight_score = _pct('freight', freight)

        geopolitics_scores = {0: 0, 1: 15, 2: 25, 3: 40}
        geopolitics_score = geopolitics_scores.get(geopolitics, 0)

        # 模块内加权（和=100%）
        cost_score = (
            crude_score * 0.60 +
            fx_score * 0.20 +
            freight_score * 0.15 +
            geopolitics_score * 0.05
        )

        # ===== 2. 裂解因子 (顶层权重30%, 模块内权重和=100%) =====
        # 模块内权重: FU裂解40%、LU裂解25%、LU-FU价差5%、地炼开工10%、印度进口10%、BDI 10%
        lu_fu_spread = lu_close - fu_close
        fu_crack_score = _pct('crack_fu', crack_fu)
        lu_crack_score = _pct('crack_lu', crack_lu)
        lu_fu_spread_score = _pct('lu_fu_spread', lu_fu_spread)

        refinery_score = crack_refinery
        india_score = min(100, max(0, 50 + india_import_yoy))
        bdi_score = bdi_percentile

        # 模块内加权（和=100%）
        crack_score = (
            fu_crack_score * 0.40 +
            lu_crack_score * 0.25 +
            lu_fu_spread_score * 0.05 +
            refinery_score * 0.10 +
            india_score * 0.10 +
            bdi_score * 0.10
        )
        
        # ===== 3. 新加坡外盘 (20%) =====
        # 库存 (10%)
        inv_chg = (sg_inventory - sg_inventory_prev) / sg_inventory_prev if sg_inventory_prev else 0
        inv_raw = _pct('sg_inventory', sg_inventory, reverse=True)
        inv_chg_score = _pct('sg_inv_chg', inv_chg, reverse=True)
        inv_yoy_score = _pct('sg_inventory_yoy', sg_inventory_yoy, reverse=True)
        inventory_score = inv_raw * 0.6 + inv_chg_score * 0.2 + inv_yoy_score * 0.2

        # 到港 (5%)
        arrival_score = _pct('arrival_yoy', arrival_yoy, reverse=True)

        # MOPS (5%)
        mops_score = _pct('mops_change', mops_change)

        sg_score = inventory_score * 0.5 + arrival_score * 0.25 + mops_score * 0.25

        # ===== 4. 国内供需+政策 (顶层权重15%, 模块内权重和=100%) =====
        # 模块内权重: 仓单30%、进口25%、炼厂产出20%、保税加注15%、政策10%
        production_score = _pct('production_yoy', production_yoy, reverse=True)
        import_score = _pct('import_yoy', import_yoy, reverse=True)
        warehouse_score = _pct('warehouse_level', warehouse_level, reverse=True)

        bunker_dom_score = min(100, max(0, 50 + bunker_yoy))
        policy_scores = {-1: -20, 0: 0, 1: 20}
        policy_score = policy_scores.get(policy_factor, 0) + 50  # 归一化到0-100

        # 模块内加权（和=100%）
        dom_score = (
            warehouse_score * 0.30 +
            import_score * 0.25 +
            production_score * 0.20 +
            bunker_dom_score * 0.15 +
            policy_score * 0.10
        )
        dom_score = min(100, max(0, dom_score))

        # ===== 5. 盘面结构 (10%) =====
        basis_score = _pct('basis', basis)
        month_spread_score = _pct('month_spread', month_spread)
        struct_score = (basis_score + month_spread_score) / 2

        # ===== 为返回值准备的辅助变量 =====
        bunker_score = min(100, max(0, 50 + bunker_yoy))
        mops_score_val = _pct('mops_change', mops_change)
        inventory_score_val = _pct('sg_inventory', sg_inventory, reverse=True)
        arrival_score_val = _pct('arrival_yoy', arrival_yoy, reverse=True)
        production_score_val = _pct('production_yoy', production_yoy, reverse=True)
        import_score_val = _pct('import_yoy', import_yoy, reverse=True)
        warehouse_score_val = _pct('warehouse_level', warehouse_level, reverse=True)
        policy_score_val = {-1: -20, 0: 0, 1: 20}.get(policy_factor, 0)

        # ===== 综合得分 =====
        total_score = (
            cost_score * 0.25 +
            crack_score * 0.30 +
            sg_score * 0.20 +
            dom_score * 0.15 +
            struct_score * 0.10
        )
        
        # 信号判定
        if total_score > 65:
            signal = "做多"
            confidence = "高" if total_score > 75 else "中"
        elif total_score < 35:
            signal = "做空"
            confidence = "高" if total_score < 25 else "中"
        else:
            signal = "观望"
            confidence = "-"
        
        return CompleteFuelOilScore(
            cost_score=round(cost_score, 1),
            brent_score=round(crude_score, 1),
            fx_score=round(fx_score, 1),
            freight_score=round(freight_score, 1),
            geopolitics_score=round(geopolitics_score, 1),
            crack_score=round(crack_score, 1),
            fu_crack_score=round(fu_crack_score, 1),
            lu_crack_score=round(lu_crack_score, 1),
            lu_fu_spread_score=round(lu_fu_spread_score, 1),
            refinery_score=round(refinery_score, 1),
            india_score=round(india_score, 1),
            bdi_score=round(bdi_score, 1),
            bunker_score=round(bunker_score, 1),
            sg_score=round(sg_score, 1),
            inventory_score=round(inventory_score_val, 1),
            arrival_score=round(arrival_score_val, 1),
            mops_score=round(mops_score_val, 1),
            dom_score=round(dom_score, 1),
            production_score=round(production_score_val, 1),
            import_score=round(import_score_val, 1),
            warehouse_score=round(warehouse_score_val, 1),
            policy_score=round(policy_score_val, 1),
            struct_score=round(struct_score, 1),
            basis_score=round(basis_score, 1),
            spread_score=round(month_spread_score, 1),
            total_score=round(total_score, 1),
            signal=signal,
            confidence=confidence
        )


def format_complete_score_report(score: CompleteFuelOilScore) -> str:
    """格式化完整五层打分报告"""
    lines = [
        "=" * 60,
        "  燃料油五层量化打分完整报告",
        "=" * 60,
        f"  综合得分: {score.total_score:.1f} ({score.signal})",
        f"  置信度: {score.confidence}",
        "",
        "  ── 成本因子 (25%) ──",
        f"  原油成本得分: {score.brent_score:.1f}",
        f"  汇率得分: {score.fx_score:.1f}",
        f"  运费得分: {score.freight_score:.1f}",
        f"  地缘得分: {score.geopolitics_score:.1f}",
        "",
        "  ── 裂解因子 (30%) ──",
        f"  FU裂解得分: {score.fu_crack_score:.1f}",
        f"  LU裂解得分: {score.lu_crack_score:.1f}",
        f"  LU-FU价差得分: {score.lu_fu_spread_score:.1f}",
        f"  地炼开工得分: {score.refinery_score:.1f}",
        f"  印度进口得分: {score.india_score:.1f}",
        f"  BDI航运得分: {score.bdi_score:.1f}",
        "",
        "  ── 新加坡外盘 (20%) ──",
        f"  新加坡库存得分: {score.inventory_score:.1f}",
        f"  到港船货得分: {score.arrival_score:.1f}",
        f"  MOPS得分: {score.mops_score:.1f}",
        "",
        "  ── 国内供需 (15%) ──",
        f"  炼厂产出得分: {score.production_score:.1f}",
        f"  进口得分: {score.import_score:.1f}",
        f"  仓单得分: {score.warehouse_score:.1f}",
        f"  政策得分: {score.policy_score:.1f}",
        "",
        "  ── 盘面结构 (10%) ──",
        f"  基差得分: {score.basis_score:.1f}",
        f"  月差得分: {score.spread_score:.1f}",
        "=" * 60,
    ]
    return "\n".join(lines)


# ========== 十、沥青六层量化打分框架 ==========
# 详见: references/BITUMEN_FRAMEWORK.md

@dataclass
class BitumenScore:
    """沥青综合打分结果"""
    total_score: float  # 总分 0-100
    cost_score: float    # 成本因子
    supply_score: float # 供应因子
    demand_score: float # 需求因子
    inventory_score: float # 库存+区域价差
    policy_score: float # 政策宏观
    structure_score: float # 盘面结构
    signal: str  # 信号：多头/震荡/空头


class BitumenScorer:
    """
    沥青六层量化打分计算器

    顶层权重：
    - 成本因子: 40%
    - 供应因子: 20%
    - 需求因子: 25%
    - 库存+区域价差: 10%
    - 政策宏观: 5%
    - 盘面结构: 0%
    """

    WEIGHTS = {
        'cost': 0.40,
        'supply': 0.20,
        'demand': 0.25,
        'inventory': 0.10,
        'policy': 0.05,
        'structure': 0.00
    }

    def __init__(self, lookback_days: int = 756):
        self.lookback_days = lookback_days

    def _calc_percentile(self, series: pd.Series, value: float, is_forward: bool = True) -> float:
        """计算历史分位"""
        if len(series) < 20:
            return 50.0
        recent = series.tail(self.lookback_days)
        percentile = (recent < value).sum() / len(recent) * 100
        if not is_forward:
            percentile = 100 - percentile
        return min(100, max(0, percentile))

    def calculate_seasonal_adjustment(self, month: int) -> float:
        """季节性调整"""
        if month in [3, 4, 5, 6]:
            return 8.0
        elif month in [7, 8]:
            return -5.0
        elif month in [9, 10, 11]:
            return 10.0
        else:
            return -10.0

    def score(self, data: dict, month: int = None) -> BitumenScore:
        """
        计算沥青综合打分

        data: dict, 包含以下键：
            - brent_chg: 布伦特20日涨跌幅
            - sc_brent_spread: SC-布伦特价差
            - usdcny: 美元兑人民币
            - production_yoy: 沥青产量同比
            - refinery_run: 炼厂开工率分位
            - import_yoy: 沥青进口同比
            - highway_invest_yoy: 公路固投同比
            - consumption: 沥青表观消费量分位
            - project_start_rate: 道路工程开工率分位
            - plant_stock: 沥青厂库分位
            - social_stock: 社会库存分位
            - basis: 基差
            - spread: 月间价差
            - infra_policy: 基建政策（-1/0/1）
            - env_policy: 环保政策（-1/0/1）
        """
        # 1. 成本因子 (40%)
        brent_score = self._calc_percentile(pd.Series([data.get('brent_chg', 0)]), data.get('brent_chg', 0))
        spread_score = self._calc_percentile(pd.Series([data.get('sc_brent_spread', 0)]), data.get('sc_brent_spread', 0))
        fx_score = self._calc_percentile(pd.Series([data.get('usdcny', 7.2)]), data.get('usdcny', 7.2))
        cost_score = brent_score * 0.5 + spread_score * 0.3 + fx_score * 0.2

        # 2. 供应因子 (20%)
        prod_score = self._calc_percentile(pd.Series([data.get('production_yoy', 0)]), data.get('production_yoy', 0), is_forward=False)
        refinery_score = data.get('refinery_run', 50.0)
        import_score = self._calc_percentile(pd.Series([data.get('import_yoy', 0)]), data.get('import_yoy', 0), is_forward=False)
        supply_score = prod_score * 0.4 + refinery_score * 0.3 + import_score * 0.3

        # 3. 需求因子 (25%)
        highway_score = self._calc_percentile(pd.Series([data.get('highway_invest_yoy', 0)]), data.get('highway_invest_yoy', 0))
        consumption_score = data.get('consumption', 50.0)
        project_score = data.get('project_start_rate', 50.0)
        demand_score = highway_score * 0.4 + consumption_score * 0.3 + project_score * 0.2 + 50 * 0.1

        # 4. 库存+区域价差 (10%)
        plant_score = self._calc_percentile(pd.Series([data.get('plant_stock', 50)]), data.get('plant_stock', 50), is_forward=False)
        social_score = self._calc_percentile(pd.Series([data.get('social_stock', 50)]), data.get('social_stock', 50), is_forward=False)
        inventory_score = plant_score * 0.5 + social_score * 0.5

        # 5. 政策宏观 (5%)
        infra = data.get('infra_policy', 0) * 15
        env = data.get('env_policy', 0) * 10
        policy_score = 50 + infra + env

        # 6. 盘面结构 (0%)
        basis_score = self._calc_percentile(pd.Series([data.get('basis', 0)]), data.get('basis', 0))
        spread_score2 = self._calc_percentile(pd.Series([data.get('spread', 0)]), data.get('spread', 0))
        structure_score = (basis_score + spread_score2) / 2

        # 综合得分
        total = (cost_score * self.WEIGHTS['cost'] +
                supply_score * self.WEIGHTS['supply'] +
                demand_score * self.WEIGHTS['demand'] +
                inventory_score * self.WEIGHTS['inventory'] +
                policy_score * self.WEIGHTS['policy'] +
                structure_score * self.WEIGHTS['structure'])

        # 季节性调整
        if month is not None:
            seasonal_adj = self.calculate_seasonal_adjustment(month)
            total = (total * 10 + seasonal_adj) / 11

        # 信号判定
        if total > 65:
            signal = "多头"
        elif total < 35:
            signal = "空头"
        else:
            signal = "震荡"

        return BitumenScore(
            total_score=round(total, 1),
            cost_score=round(cost_score, 1),
            supply_score=round(supply_score, 1),
            demand_score=round(demand_score, 1),
            inventory_score=round(inventory_score, 1),
            policy_score=round(policy_score, 1),
            structure_score=round(structure_score, 1),
            signal=signal
        )


# ========== 十一、LPG五层量化打分框架 ==========
# 详见: references/LPG_FRAMEWORK.md

@dataclass
class LPGScore:
    """LPG综合打分结果"""
    total_score: float  # 总分 0-100
    external_score: float  # 外部市场与成本
    supply_score: float    # 国内供应
    demand_score: float    # 终端需求
    inventory_score: float # 库存与区域价差
    policy_score: float     # 政策与市场结构
    signal: str  # 信号：多头/震荡/空头


class LPGScorer:
    """
    LPG五层量化打分计算器

    顶层权重：
    - 外部市场与成本: 25%
    - 国内供应: 20%
    - 终端需求: 30%
    - 库存与区域价差: 15%
    - 政策与市场结构: 10%
    """

    WEIGHTS = {
        'external': 0.25,
        'supply': 0.20,
        'demand': 0.30,
        'inventory': 0.15,
        'policy': 0.10
    }

    def __init__(self, lookback_days: int = 756):
        self.lookback_days = lookback_days

    def _calc_percentile(self, series: pd.Series, value: float, is_forward: bool = True) -> float:
        """计算历史分位"""
        if len(series) < 20:
            return 50.0
        recent = series.tail(self.lookback_days)
        percentile = (recent < value).sum() / len(recent) * 100
        if not is_forward:
            percentile = 100 - percentile
        return min(100, max(0, percentile))

    def calculate_seasonal_adjustment(self, month: int) -> float:
        """季节性调整"""
        if month in [11, 12, 1, 2, 3]:
            return 10.0
        elif month in [9, 10]:
            return 5.0
        else:
            return -5.0

    def score(self, data: dict, month: int = None) -> LPGScore:
        """
        计算LPG综合打分

        data: dict, 包含以下键：
            - cp_propane_chg: CP丙烷20日涨跌幅
            - cp_butane_chg: CP丁烷20日涨跌幅
            - usdcny: 美元兑人民币
            - fei: FEI远东指数分位
            - production_yoy: LPG产量同比
            - import_yoy: LPG进口同比
            - refinery_run: 炼厂开工率分位
            - pdh_margin: PDH利润分位
            - pdh_run: PDH开工率分位
            - propylene_price: 丙烯价格分位
            - domestic_consumption: 民用消费同比分位
            - east_stock: 华东库存分位
            - south_stock: 华南库存分位
            - coal_to_gas: 煤改气政策（负值=推进）
            - import_quota: 进口配额政策（正值=收紧）
            - basis: 基差
        """
        # 1. 外部市场与成本 (25%)
        cp_propane_score = self._calc_percentile(pd.Series([data.get('cp_propane_chg', 0)]), data.get('cp_propane_chg', 0))
        cp_butane_score = self._calc_percentile(pd.Series([data.get('cp_butane_chg', 0)]), data.get('cp_butane_chg', 0))
        fx_score = self._calc_percentile(pd.Series([data.get('usdcny', 7.2)]), data.get('usdcny', 7.2))
        fei_score = data.get('fei', 50.0)
        external_score = cp_propane_score * 0.4 + cp_butane_score * 0.25 + fx_score * 0.2 + fei_score * 0.15

        # 2. 国内供应 (20%)
        prod_score = self._calc_percentile(pd.Series([data.get('production_yoy', 0)]), data.get('production_yoy', 0), is_forward=False)
        import_score = self._calc_percentile(pd.Series([data.get('import_yoy', 0)]), data.get('import_yoy', 0), is_forward=False)
        refinery_score = data.get('refinery_run', 50.0)
        supply_score = prod_score * 0.35 + import_score * 0.35 + refinery_score * 0.30

        # 3. 终端需求 (30%)
        pdh_margin_score = data.get('pdh_margin', 50.0)
        pdh_run_score = data.get('pdh_run', 50.0)
        propylene_score = data.get('propylene_price', 50.0)
        domestic_score = self._calc_percentile(pd.Series([data.get('domestic_consumption', 0)]), data.get('domestic_consumption', 0))
        demand_score = pdh_margin_score * 0.35 + pdh_run_score * 0.30 + propylene_score * 0.20 + domestic_score * 0.15

        # 4. 库存与区域价差 (15%)
        east_stock_score = self._calc_percentile(pd.Series([data.get('east_stock', 50)]), data.get('east_stock', 50), is_forward=False)
        south_stock_score = self._calc_percentile(pd.Series([data.get('south_stock', 50)]), data.get('south_stock', 50), is_forward=False)
        inventory_score = east_stock_score * 0.5 + south_stock_score * 0.5

        # 5. 政策与市场结构 (10%)
        coal_to_gas = data.get('coal_to_gas', 0)
        import_quota = data.get('import_quota', 0)
        basis_score = self._calc_percentile(pd.Series([data.get('basis', 0)]), data.get('basis', 0))
        policy_score = coal_to_gas * 0.3 + import_quota * 0.3 + basis_score * 0.4

        # 综合得分
        total = (external_score * self.WEIGHTS['external'] +
                supply_score * self.WEIGHTS['supply'] +
                demand_score * self.WEIGHTS['demand'] +
                inventory_score * self.WEIGHTS['inventory'] +
                policy_score * self.WEIGHTS['policy'])

        # 季节性调整
        if month is not None:
            seasonal_adj = self.calculate_seasonal_adjustment(month)
            total = (total * 10 + seasonal_adj) / 11

        # 信号判定
        if total > 65:
            signal = "多头"
        elif total < 35:
            signal = "空头"
        else:
            signal = "震荡"

        return LPGScore(
            total_score=round(total, 1),
            external_score=round(external_score, 1),
            supply_score=round(supply_score, 1),
            demand_score=round(demand_score, 1),
            inventory_score=round(inventory_score, 1),
            policy_score=round(policy_score, 1),
            signal=signal
        )


# ========== 十二、统一打分入口 ==========

def calculate_all_scores(
    fu_data: dict = None,
    bu_data: dict = None,
    pg_data: dict = None,
    month: int = None
) -> dict:
    """
    统一计算原油系产业链所有品种打分

    参数:
        fu_data: 燃料油打分数据（见 CompleteFuelOilScorer.calculate）
        bu_data: 沥青打分数据（见 BitumenScorer.score）
        pg_data: LPG打分数据（见 LPGScorer.score）
        month: 当前月份(1-12)

    返回:
        dict: {
            'fuel_oil': CompleteFuelOilScore or None,
            'bitumen': BitumenScore or None,
            'lpg': LPGScore or None
        }
    """
    results = {}

    if fu_data:
        scorer = CompleteFuelOilScorer()
        results['fuel_oil'] = scorer.calculate(**fu_data)
    else:
        results['fuel_oil'] = None

    if bu_data:
        scorer = BitumenScorer()
        results['bitumen'] = scorer.score(bu_data, month=month)
    else:
        results['bitumen'] = None

    if pg_data:
        scorer = LPGScorer()
        results['lpg'] = scorer.score(pg_data, month=month)
    else:
        results['lpg'] = None

    return results


def format_all_scores_report(scores: dict) -> str:
    """格式化所有品种打分报告"""
    lines = [
        "=" * 60,
        "  原油系产业链综合打分报告",
        "=" * 60,
    ]

    if scores.get('fuel_oil'):
        fs = scores['fuel_oil']
        lines.extend([
            "",
            "【燃料油 FU/LU】",
            f"  综合得分: {fs.total_score:.1f} ({fs.signal})",
            f"  成本(25%): {fs.cost_score:.1f} | 裂解(30%): {fs.crack_score:.1f}",
            f"  新加坡(20%): {fs.sg_score:.1f} | 国内供需(15%): {fs.dom_score:.1f}",
            f"  盘面结构(10%): {fs.struct_score:.1f}",
        ])

    if scores.get('bitumen'):
        bs = scores['bitumen']
        lines.extend([
            "",
            "【沥青 BU】",
            f"  综合得分: {bs.total_score:.1f} ({bs.signal})",
            f"  成本(40%): {bs.cost_score:.1f} | 供应(20%): {bs.supply_score:.1f}",
            f"  需求(25%): {bs.demand_score:.1f} | 库存(10%): {bs.inventory_score:.1f}",
            f"  政策(5%): {bs.policy_score:.1f}",
        ])

    if scores.get('lpg'):
        ls = scores['lpg']
        lines.extend([
            "",
            "【液化气 PG】（独立模块）",
            f"  综合得分: {ls.total_score:.1f} ({ls.signal})",
            f"  外部市场(25%): {ls.external_score:.1f} | 供应(20%): {ls.supply_score:.1f}",
            f"  需求(30%): {ls.demand_score:.1f} | 库存(15%): {ls.inventory_score:.1f}",
            f"  政策(10%): {ls.policy_score:.1f}",
        ])

    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="燃料油技术指标计算工具（Ta-Lib增强版）")
    parser.add_argument("--input", "-i", type=str, help="输入K线CSV文件路径")
    parser.add_argument("--output", "-o", type=str, help="输出结果CSV文件路径")
    parser.add_argument("--db", type=str, help="DuckDB数据库路径（从DuckDB读取K线）")
    parser.add_argument("--symbol", type=str, help="品种代码（配合--db使用，如 FU/LU/SC）")
    parser.add_argument("--demo", action="store_true", help="使用演示数据运行")
    parser.add_argument("--json", action="store_true", help="同时输出JSON格式信号")
    parser.add_argument("--score", action="store_true", help="运行燃料油量化打分")
    args = parser.parse_args()

    if HAS_TALIB:
        logger.info("Ta-Lib 已加载，将使用 C 库加速计算")
    else:
        logger.warning("Ta-Lib 未安装，使用纯 pandas/numpy 实现")

    if args.db and args.symbol:
        logger.info(f"从DuckDB加载数据: {args.db} -> kline_{args.symbol.lower()}")
        df = load_from_duckdb(args.db, args.symbol)
    elif args.input:
        logger.info(f"加载数据: {args.input}")
        df = pd.read_csv(args.input)
    else:
        logger.info("使用演示数据...")
        df = generate_demo_data()

    result = calculate_all_indicators(df)
    signals = generate_comprehensive_signal(result)
    report = format_indicator_report(result, signals)
    print(report)

    if args.db and args.symbol:
        save_indicators_to_duckdb(args.db, args.symbol, result, signals)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_DIR / f"indicators_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"结果已保存: {output_path}")

    if args.json:
        json_path = output_path.with_suffix(".json")
        signals_dict = [
            {"indicator": s.indicator, "value": s.value, "signal": s.signal,
             "strength": s.strength, "description": s.description}
            for s in signals
        ]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(signals_dict, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"JSON信号已保存: {json_path}")

    signal_summary = {s.indicator: {"signal": s.signal, "value": s.value} for s in signals}
    print(f"\n__SIGNALS__:{json.dumps(signal_summary, ensure_ascii=False, default=str)}")

    return result, signals


if __name__ == "__main__":
    main()
