#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信号回测框架 — 验证量化打分信号的历史有效性

功能：
    1. 从DuckDB加载历史K线数据
    2. 滚动计算技术指标和量化得分
    3. 生成做多/做空/观望信号
    4. 统计胜率、盈亏比、最大回撤
    5. 输出回测报告

用法：
    python backtest_signals.py --symbol FU --days 756
    python backtest_signals.py --all
"""

import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "futures_data.duckdb"

# 信号阈值
LONG_THRESHOLD = 65
SHORT_THRESHOLD = 35
# 止损参数
STOP_LOSS_ATR_MULT = 1.5
TAKE_PROFIT_ATR_MULT = 3.0
# 交易成本
COMMISSION_RATE = 0.0001  # 万分之一手续费
SLIPPAGE_TICKS = 1  # 1跳滑点
TICK_SIZE = 1  # 最小变动价位（元/吨）
MARGIN_RATE = 0.12  # 保证金比例12%


@dataclass
class TradeRecord:
    """单笔交易记录"""
    entry_date: str
    exit_date: str
    direction: str  # "long" / "short"
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    pnl: float  # 盈亏（元/吨）
    pnl_pct: float  # 盈亏百分比
    exit_reason: str  # "signal" / "stop_loss" / "take_profit" / "timeout"
    holding_days: int
    signal_score: float


@dataclass
class BacktestResult:
    """回测结果"""
    symbol: str
    total_days: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float  # 胜率
    avg_win: float  # 平均盈利
    avg_loss: float  # 平均亏损
    profit_loss_ratio: float  # 盈亏比
    total_return_pct: float  # 总收益率
    max_drawdown_pct: float  # 最大回撤
    sharpe_ratio: float  # 夏普比率
    avg_holding_days: float  # 平均持仓天数
    trades: list = field(default_factory=list)


def load_kline_from_duckdb(symbol: str) -> Optional[pd.DataFrame]:
    """从DuckDB加载K线数据"""
    import duckdb
    if not DB_PATH.exists():
        logger.warning(f"DuckDB数据库不存在: {DB_PATH}，将使用demo数据")
        return None

    table_name = f"kline_{symbol.lower()}"
    try:
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        df = conn.execute(f"SELECT * FROM {table_name} ORDER BY date").fetchdf()
        conn.close()
        if df.empty:
            logger.warning(f"表 {table_name} 无数据")
            return None
        logger.info(f"✅ 加载 {table_name}: {len(df)} 条记录")
        return df
    except Exception as e:
        logger.error(f"加载 {table_name} 失败: {e}")
        return None


def generate_backtest_data(symbol: str, days: int = 756) -> pd.DataFrame:
    """生成回测用demo数据（模拟真实期货行情特征）"""
    np.random.seed(42)  # 可复现

    # 基础价格参数（基于真实品种特征）
    params = {
        "SC": {"base": 500, "vol": 0.02, "trend": 0.0001},
        "BU": {"base": 3200, "vol": 0.018, "trend": 0.00005},
        "FU": {"base": 3000, "vol": 0.022, "trend": 0.00008},
        "LU": {"base": 3500, "vol": 0.02, "trend": 0.00006},
        "PG": {"base": 4500, "vol": 0.025, "trend": 0.00003},
    }
    p = params.get(symbol, params["FU"])

    # 生成价格序列（GBM + 均值回归 + 趋势）
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq='B')
    close = [p["base"]]
    for i in range(1, days):
        # 随机波动 + 趋势 + 均值回归
        shock = np.random.normal(0, p["vol"])
        mean_rev = -0.001 * (close[-1] / p["base"] - 1)  # 均值回归
        trend = p["trend"]
        ret = shock + mean_rev + trend
        close.append(close[-1] * (1 + ret))

    close = np.array(close)
    high = close * (1 + np.abs(np.random.normal(0, 0.005, days)))
    low = close * (1 - np.abs(np.random.normal(0, 0.005, days)))
    open_price = close * (1 + np.random.normal(0, 0.002, days))
    volume = np.random.randint(10000, 100000, days)

    df = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    logger.info(f"✅ 生成 {symbol} demo数据: {len(df)} 条，价格范围 {close.min():.0f}-{close.max():.0f}")
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算技术指标（简化版，用于回测）"""
    # 确保有必要的列
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col not in df.columns:
            logger.error(f"缺少列: {col}")
            return df

    close = df['close']
    high = df['high']
    low = df['low']

    # MA
    df['MA5'] = close.rolling(5).mean()
    df['MA10'] = close.rolling(10).mean()
    df['MA20'] = close.rolling(20).mean()
    df['MA60'] = close.rolling(60).mean()

    # RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df['MACD_DIF'] = ema12 - ema26
    df['MACD_DEA'] = df['MACD_DIF'].ewm(span=9).mean()
    df['MACD_HIST'] = df['MACD_DIF'] - df['MACD_DEA']

    # ADX(14)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()

    # 价格变化率
    df['ROC_20'] = close.pct_change(20) * 100

    # 布林带
    df['BB_mid'] = close.rolling(20).mean()
    df['BB_std'] = close.rolling(20).std()
    df['BB_upper'] = df['BB_mid'] + 2 * df['BB_std']
    df['BB_lower'] = df['BB_mid'] - 2 * df['BB_std']

    return df


def generate_signal_score(row: pd.Series, history: pd.DataFrame, idx: int) -> float:
    """基于技术指标生成量化得分（简化版）"""
    score = 50.0  # 基准分

    # RSI信号
    rsi = row.get('RSI', 50)
    if pd.notna(rsi):
        if rsi > 70:
            score -= 10  # 超买
        elif rsi < 30:
            score += 10  # 超卖
        elif rsi > 50:
            score += 3
        elif rsi < 50:
            score -= 3

    # MACD信号
    macd_hist = row.get('MACD_HIST', 0)
    if pd.notna(macd_hist):
        if macd_hist > 0:
            score += 5
        else:
            score -= 5

    # MA趋势
    ma5 = row.get('MA5')
    ma20 = row.get('MA20')
    ma60 = row.get('MA60')
    if pd.notna(ma5) and pd.notna(ma20) and pd.notna(ma60):
        if ma5 > ma20 > ma60:
            score += 10  # 多头排列
        elif ma5 < ma20 < ma60:
            score -= 10  # 空头排列

    # 价格动量（20日ROC）
    roc = row.get('ROC_20', 0)
    if pd.notna(roc):
        if roc > 5:
            score += 5
        elif roc < -5:
            score -= 5

    # 布林带位置
    close = row.get('close', 0)
    bb_upper = row.get('BB_upper')
    bb_lower = row.get('BB_lower')
    if pd.notna(bb_upper) and pd.notna(bb_lower) and bb_upper != bb_lower:
        bb_pos = (close - bb_lower) / (bb_upper - bb_lower) * 100
        score = score * 0.7 + bb_pos * 0.3  # 混合布林带位置

    return min(100, max(0, score))


def run_backtest(symbol: str, days: int = 756, use_demo: bool = False) -> Optional[BacktestResult]:
    """运行单品种回测"""
    df = load_kline_from_duckdb(symbol)
    if df is None or len(df) < 60:
        if use_demo or df is None:
            logger.info(f"{symbol}: DuckDB无数据，使用demo数据回测")
            df = generate_backtest_data(symbol, days)
        else:
            logger.warning(f"{symbol}: 数据不足（{len(df)}条），跳过")
            return None

    # 计算指标
    df = compute_indicators(df)

    # 生成信号得分
    scores = []
    for i in range(len(df)):
        score = generate_signal_score(df.iloc[i], df, i)
        scores.append(score)
    df['signal_score'] = scores

    # 生成信号
    df['signal'] = '观望'
    df.loc[df['signal_score'] > LONG_THRESHOLD, 'signal'] = '做多'
    df.loc[df['signal_score'] < SHORT_THRESHOLD, 'signal'] = '做空'

    # 模拟交易
    trades = []
    position = None  # None / {"direction": "long"/"short", "entry_price": ..., "entry_date": ..., "stop_loss": ..., "take_profit": ...}

    for i in range(60, len(df)):
        row = df.iloc[i]
        date = str(row.get('date', i))
        close = row['close']
        atr = row.get('ATR', close * 0.02)
        signal = row['signal']
        score = row['signal_score']

        # 开仓逻辑
        if position is None:
            if signal == '做多':
                entry_price = close + SLIPPAGE_TICKS * TICK_SIZE
                stop_loss = entry_price - STOP_LOSS_ATR_MULT * atr
                take_profit = entry_price + TAKE_PROFIT_ATR_MULT * atr
                position = {
                    "direction": "long",
                    "entry_price": entry_price,
                    "entry_date": date,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "entry_score": score,
                }
            elif signal == '做空':
                entry_price = close - SLIPPAGE_TICKS * TICK_SIZE
                stop_loss = entry_price + STOP_LOSS_ATR_MULT * atr
                take_profit = entry_price - TAKE_PROFIT_ATR_MULT * atr
                position = {
                    "direction": "short",
                    "entry_price": entry_price,
                    "entry_date": date,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "entry_score": score,
                }

        # 平仓逻辑
        elif position is not None:
            exit_reason = None
            exit_price = close

            if position["direction"] == "long":
                # 止损
                if low := row.get('low', close):
                    if low <= position["stop_loss"]:
                        exit_price = position["stop_loss"]
                        exit_reason = "stop_loss"
                # 止盈
                if high := row.get('high', close):
                    if high >= position["take_profit"]:
                        exit_price = position["take_profit"]
                        exit_reason = "take_profit"
                # 信号反转
                if signal == '做空':
                    exit_price = close - SLIPPAGE_TICKS * TICK_SIZE
                    exit_reason = "signal"
                # 超时（30天）
                if exit_reason is None and i - df.index[df['date'].astype(str) == position["entry_date"]].tolist()[0] > 30:
                    exit_reason = "timeout"

            elif position["direction"] == "short":
                # 止损
                if high := row.get('high', close):
                    if high >= position["stop_loss"]:
                        exit_price = position["stop_loss"]
                        exit_reason = "stop_loss"
                # 止盈
                if low := row.get('low', close):
                    if low <= position["take_profit"]:
                        exit_price = position["take_profit"]
                        exit_reason = "take_profit"
                # 信号反转
                if signal == '做多':
                    exit_price = close + SLIPPAGE_TICKS * TICK_SIZE
                    exit_reason = "signal"
                # 超时
                if exit_reason is None and i - df.index[df['date'].astype(str) == position["entry_date"]].tolist()[0] > 30:
                    exit_reason = "timeout"

            if exit_reason:
                # 计算盈亏
                if position["direction"] == "long":
                    pnl = exit_price - position["entry_price"]
                else:
                    pnl = position["entry_price"] - exit_price

                # 扣除交易成本（开仓+平仓手续费）
                commission = (position["entry_price"] + exit_price) * COMMISSION_RATE
                pnl_net = pnl - commission
                pnl_pct = pnl_net / position["entry_price"] * 100

                # 计算持仓天数
                try:
                    entry_idx = df.index[df['date'].astype(str) == position["entry_date"]].tolist()[0]
                    holding_days = i - entry_idx
                except (IndexError, ValueError):
                    holding_days = 0

                trades.append(TradeRecord(
                    entry_date=position["entry_date"],
                    exit_date=date,
                    direction=position["direction"],
                    entry_price=position["entry_price"],
                    exit_price=exit_price,
                    stop_loss=position["stop_loss"],
                    take_profit=position["take_profit"],
                    pnl=pnl_net,
                    pnl_pct=pnl_pct,
                    exit_reason=exit_reason,
                    holding_days=holding_days,
                    signal_score=position["entry_score"],
                ))
                position = None

    # 计算统计指标
    if not trades:
        logger.warning(f"{symbol}: 无交易记录")
        return BacktestResult(
            symbol=symbol, total_days=len(df), total_trades=0,
            winning_trades=0, losing_trades=0, win_rate=0,
            avg_win=0, avg_loss=0, profit_loss_ratio=0,
            total_return_pct=0, max_drawdown_pct=0, sharpe_ratio=0,
            avg_holding_days=0, trades=[]
        )

    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl <= 0]

    win_rate = len(winning) / len(trades) * 100
    avg_win = np.mean([t.pnl for t in winning]) if winning else 0
    avg_loss = abs(np.mean([t.pnl for t in losing])) if losing else 1
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

    # 总收益率（假设每笔交易1手=10吨，初始资金10万）
    total_pnl = sum(t.pnl for t in trades)
    total_return_pct = total_pnl / 100000 * 100

    # 最大回撤
    cumulative = np.cumsum([t.pnl for t in trades])
    peak = np.maximum.accumulate(cumulative)
    drawdown = (peak - cumulative) / (peak + 100000) * 100
    max_drawdown_pct = np.max(drawdown) if len(drawdown) > 0 else 0

    # 夏普比率（年化，假设252个交易日）
    if len(trades) > 1:
        returns = [t.pnl_pct for t in trades]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 / len(trades)) if np.std(returns) > 0 else 0
    else:
        sharpe = 0

    avg_holding = np.mean([t.holding_days for t in trades])

    return BacktestResult(
        symbol=symbol,
        total_days=len(df),
        total_trades=len(trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        win_rate=round(win_rate, 1),
        avg_win=round(avg_win, 1),
        avg_loss=round(avg_loss, 1),
        profit_loss_ratio=round(profit_loss_ratio, 2),
        total_return_pct=round(total_return_pct, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
        sharpe_ratio=round(sharpe, 2),
        avg_holding_days=round(avg_holding, 1),
        trades=trades
    )


def analyze_seasonality(df: pd.DataFrame, symbol: str) -> str:
    """季节性分析 — 统计各月份的收益率和波动率"""
    if 'date' not in df.columns or 'close' not in df.columns:
        return "数据不足，无法进行季节性分析"

    df = df.copy()
    df['month'] = pd.to_datetime(df['date']).dt.month
    df['return'] = df['close'].pct_change()

    lines = [
        "=" * 60,
        f"  {symbol} 季节性分析",
        "=" * 60,
        "  月份 | 平均收益率 | 波动率 | 胜率 | 交易天数",
        "  " + "-" * 50,
    ]

    month_stats = {}
    for m in range(1, 13):
        month_data = df[df['month'] == m]['return'].dropna()
        if len(month_data) > 0:
            avg_ret = month_data.mean() * 100
            vol = month_data.std() * 100
            win_rate = (month_data > 0).mean() * 100
            month_stats[m] = {
                'avg_ret': avg_ret,
                'vol': vol,
                'win_rate': win_rate,
                'days': len(month_data)
            }
            lines.append(
                f"  {m:2d}月  | {avg_ret:+.3f}%    | {vol:.3f}% | {win_rate:.1f}% | {len(month_data)}"
            )

    # 找出最强/最弱月份
    if month_stats:
        best = max(month_stats.items(), key=lambda x: x[1]['avg_ret'])
        worst = min(month_stats.items(), key=lambda x: x[1]['avg_ret'])
        lines.append("")
        lines.append(f"  最强月份: {best[0]}月 (平均{best[1]['avg_ret']:+.3f}%)")
        lines.append(f"  最弱月份: {worst[0]}月 (平均{worst[1]['avg_ret']:+.3f}%)")

        # 季节性强度评分
        seasonal_strength = abs(best[1]['avg_ret'] - worst[1]['avg_ret'])
        lines.append(f"  季节性强度: {seasonal_strength:.3f}% (月度收益差)")
        if seasonal_strength > 0.5:
            lines.append("  判定: 强季节性（可用于策略）")
        elif seasonal_strength > 0.2:
            lines.append("  判定: 中等季节性（辅助参考）")
        else:
            lines.append("  判定: 弱季节性（不建议单独使用）")

    lines.append("=" * 60)
    return "\n".join(lines)


def format_backtest_report(result: BacktestResult) -> str:
    """格式化回测报告"""
    lines = [
        "=" * 60,
        f"  {result.symbol} 信号回测报告",
        "=" * 60,
        f"  回测天数: {result.total_days}",
        f"  总交易次数: {result.total_trades}",
        f"  盈利次数: {result.winning_trades}",
        f"  亏损次数: {result.losing_trades}",
        "",
        "  ── 核心指标 ──",
        f"  胜率: {result.win_rate:.1f}%",
        f"  平均盈利: {result.avg_win:.1f} 元/吨",
        f"  平均亏损: {result.avg_loss:.1f} 元/吨",
        f"  盈亏比: {result.profit_loss_ratio:.2f}",
        f"  总收益率: {result.total_return_pct:.2f}%",
        f"  最大回撤: {result.max_drawdown_pct:.2f}%",
        f"  夏普比率: {result.sharpe_ratio:.2f}",
        f"  平均持仓天数: {result.avg_holding_days:.1f}",
        "",
    ]

    if result.trades:
        lines.append("  ── 最近5笔交易 ──")
        for t in result.trades[-5:]:
            direction = "多" if t.direction == "long" else "空"
            lines.append(
                f"  {t.entry_date}→{t.exit_date} {direction} "
                f"入场{t.entry_price:.0f} 出场{t.exit_price:.0f} "
                f"盈亏{t.pnl:+.0f}({t.pnl_pct:+.1f}%) "
                f"原因:{t.exit_reason}"
            )

    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="信号回测框架")
    parser.add_argument("--symbol", type=str, help="品种代码 (SC/BU/FU/LU/PG)")
    parser.add_argument("--all", action="store_true", help="回测所有品种")
    parser.add_argument("--days", type=int, default=756, help="回测天数")
    parser.add_argument("--demo", action="store_true", help="使用demo数据（无需DuckDB）")
    args = parser.parse_args()

    symbols = ["SC", "BU", "FU", "LU", "PG"] if args.all else [args.symbol or "FU"]

    results = []
    for sym in symbols:
        logger.info(f"\n{'='*40} {sym} {'='*40}")
        result = run_backtest(sym, args.days, use_demo=args.demo)
        if result:
            results.append(result)
            print(format_backtest_report(result))

            # 季节性分析
            df = load_kline_from_duckdb(sym) if not args.demo else generate_backtest_data(sym, args.days)
            if df is not None:
                print(analyze_seasonality(df, sym))

    # 汇总报告
    if results:
        print("\n" + "=" * 60)
        print("  汇总统计")
        print("=" * 60)
        for r in results:
            print(f"  {r.symbol}: 胜率{r.win_rate}% 盈亏比{r.profit_loss_ratio} "
                  f"收益率{r.total_return_pct}% 回撤{r.max_drawdown_pct}% "
                  f"夏普{r.sharpe_ratio} 交易{r.total_trades}次")


if __name__ == "__main__":
    main()
