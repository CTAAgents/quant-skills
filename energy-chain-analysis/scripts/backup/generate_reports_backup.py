#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原油系产业链报告生成脚本 v2.4.0
从DuckDB读取真实数据，生成5种报告
原油上游 + 沥青/FU/LU/PG下游并列！（PG为独立模块）
完整管线：TqSdk → DuckDB → Ta-Lib → 报告
本脚本负责最后一环节：从DuckDB读取真实K线+指标+信号，生成Markdown报告。
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
DEFAULT_DB = BASE_DIR / "data" / "crude_oil_chain.duckdb"
REPORTS_DIR = BASE_DIR / "output" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = {
    "SC": {"name": "SC原油（INE）", "exchange": "INE", "unit": "元/桶", "weight": 0.40},  # 权重40%
    "BU": {"name": "BU沥青主力", "exchange": "SHFE", "unit": "元/吨", "weight": 0.20},    # 权重20%
    "FU": {"name": "FU主力（高硫燃料油）", "exchange": "SHFE", "unit": "元/吨", "weight": 0.20},
    "LU": {"name": "LU主力（低硫燃料油）", "exchange": "INE", "unit": "元/吨", "weight": 0.20},
    "PG": {"name": "PG液化石油气", "exchange": "DCE", "unit": "元/吨", "weight": 0.00, "independent": True},  # 独立模块，不参与加权（大连商品交易所）
}

INDICATOR_CN = {
    "RSI(14)": "RSI",
    "STOCH(9,6)": "随机指标K/D",
    "STOCHRSI(14)": "随机RSI",
    "MACD": "MACD",
    "ADX(14)": "ADX趋势强度",
    "Williams %R": "威廉%R",
    "CCI(14)": "CCI",
    "Ultimate Osc": "终极震荡",
    "ROC": "变动率",
    "Bull/Bear": "多空力量",
    "ATR(14)": "波动率ATR",
    "均线排列": "均线排列",
}


def load_market_data(db_path, sym):
    import duckdb
    sym_lower = sym.lower()
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        kline = conn.execute(f"SELECT * FROM kline_{sym_lower} ORDER BY date").fetchdf()
        indicators = conn.execute(f"SELECT * FROM indicators_{sym_lower} ORDER BY date").fetchdf()
        signals = conn.execute(f"SELECT * FROM signals_{sym_lower}").fetchdf()
    finally:
        conn.close()
    return kline, indicators, signals


def fmt(val, decimals=2):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    return f"{val:,.{decimals}f}"


def fmt_pct(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"


def get_signal_emoji(signal):
    mapping = {
        "超买": "⚠️",
        "超卖": "📌",
        "多头": "🟢",
        "空头": "🔴",
        "偏多": "🟢",
        "偏空": "🔴",
        "中性": "⚪",
        "无趋势": "⚪",
        "强势下跌": "🔻",
        "强势上涨": "🔺",
        "空头强势": "🔴",
        "多头强势": "🟢",
        "空头排列": "🔴",
        "多头排列": "🟢",
        "高波动": "⚠️",
        "低波动": "⚪",
    }
    return mapping.get(signal, "⚪")


def get_technical_table(signals_df):
    rows = []
    for _, s in signals_df.iterrows():
        ind = s["indicator"]
        val = s["value"]
        sig = s["signal"]
        desc = s["description"]
        emoji = get_signal_emoji(sig)
        if ind == "均线排列":
            val_str = "—" if val is None or (isinstance(val, float) and pd.isna(val)) else fmt(val)
        elif ind in ("MACD",):
            val_str = fmt(val)
        elif ind in ("ROC",):
            val_str = fmt_pct(val)
        elif ind in ("ATR(14)",):
            val_str = fmt(val, 1)
        else:
            val_str = fmt(val)
        rows.append(f"| {ind} | {val_str} | {emoji} {sig} | {desc} |")
    return "\n".join(rows)


def calculate_conduction_coefficient(sc_overall, sc_ratio):
    """
    计算原油传导系数：原油信号对FU/LU的影响程度
    """
    if sc_overall in ("偏多", "多头", "多头强势", "强势上涨"):
        if sc_ratio > 0.5:
            return 0.90, "强多头传导"
        elif sc_ratio > 0.2:
            return 0.70, "偏多传导"
        else:
            return 0.50, "弱多传导"
    elif sc_overall in ("偏空", "空头", "空头强势", "强势下跌"):
        if sc_ratio < -0.5:
            return 0.90, "强空头传导"
        elif sc_ratio < -0.2:
            return 0.70, "偏空传导"
        else:
            return 0.50, "弱空传导"
    else:
        return 0.35, "震荡传导"


def compute_weighted_overall_signal(signals_df, weight=1.0):
    """
    计算综合信号，支持权重放大
    """
    score = 0
    count = 0
    for _, s in signals_df.iterrows():
        w = s.get("strength", 1)
        if w is None or (isinstance(w, float) and pd.isna(w)):
            w = 1
        sig = s["signal"]
        if sig in ("多头", "多头强势", "偏多", "强势上涨", "多头排列"):
            score += w
        elif sig in ("空头", "空头强势", "偏空", "强势下跌", "空头排列"):
            score -= w
        count += w
    if count == 0:
        return "中性", 0
    # 应用权重放大
    ratio = (score / count) * weight
    if ratio > 0.5:
        return "偏多", ratio
    elif ratio > 0.2:
        return "震荡偏多", ratio
    elif ratio > -0.2:
        return "中性震荡", ratio
    elif ratio > -0.5:
        return "震荡偏空", ratio
    else:
        return "偏空", ratio


def compute_overall_signal(signals_df):
    return compute_weighted_overall_signal(signals_df, 1.0)


def get_position_advice(overall, ratio):
    if ratio > 0.5:
        return "趋势多单", "逢低做多，控制仓位"
    elif ratio > 0.2:
        return "轻仓偏多", "等回调后轻仓试多"
    elif ratio > -0.2:
        return "观望为主", "信号矛盾，等待方向确认"
    elif ratio > -0.5:
        return "轻仓偏空", "反弹做空或观望"
    else:
        return "趋势空单", "顺势做空，严格止损"


def build_kline_summary(kline_df):
    if kline_df.empty:
        return {}
    latest = kline_df.iloc[-1]
    prev = kline_df.iloc[-2] if len(kline_df) > 1 else latest
    change = latest["close"] - prev["close"]
    change_pct = (change / prev["close"]) * 100 if prev["close"] != 0 else 0
    high_20 = kline_df.tail(20)["high"].max()
    low_20 = kline_df.tail(20)["low"].min()
    avg_vol = kline_df.tail(20)["volume"].mean()
    return {
        "date": str(latest["date"]),
        "open": latest["open"],
        "high": latest["high"],
        "low": latest["low"],
        "close": latest["close"],
        "volume": latest["volume"],
        "change": change,
        "change_pct": change_pct,
        "high_20": high_20,
        "low_20": low_20,
        "avg_vol": avg_vol,
    }


def analyze_crude_trend(ind_df):
    """
    分析原油趋势特征
    """
    if ind_df.empty:
        return "数据不足", "数据不足"

    recent = ind_df.tail(20)
    ma5 = recent["MA5"].iloc[-1]
    ma10 = recent["MA10"].iloc[-1]
    ma20 = recent["MA20"].iloc[-1]
    ma60 = recent["MA60"].iloc[-1]
    rsi = recent["RSI_14"].iloc[-1]
    macd_hist = recent["MACD_HIST"].iloc[-1]

    ma_status = ""
    if ma5 > ma10 > ma20 > ma60:
        ma_status = "均线完美多头排列"
    elif ma5 > ma10 > ma20:
        ma_status = "短期多头排列"
    elif ma5 < ma10 < ma20 < ma60:
        ma_status = "完美空头排列"
    elif ma5 < ma10 < ma20:
        ma_status = "短期空头排列"
    else:
        ma_status = "均线交织"

    trend_str = f"RSI: {fmt(rsi)}，MACD: {fmt(macd_hist)}，{ma_status}"
    return trend_str


def generate_morning_report(all_data, indicators_data, date_str):
    lines = []
    lines.append(f"# 原油系产业链早间快讯 v2.2.0")
    lines.append("")
    lines.append(f"> **💡 数据来源：TqSdk实盘K线 → DuckDB → Ta-Lib指标计算")
    lines.append(f"> **⚠️ 产业链权重：SC原油40%、BU沥青20%、FU/LU各20%")
    lines.append(f"> **⏰ 数据时效：{date_str}")
    lines.append(f"> **📊 数据质量评级：高（真实行情数据 + Ta-Lib计算指标）")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ========== 原油核心分析（永远置顶，第1章节）
    lines.append("## ⭐ 一、原油核心分析（权重40%）")
    lines.append("")
    sc_data = all_data.get("SC")
    if sc_data:
        sc_summary = sc_data["summary"]
        sc_overall, sc_ratio = sc_data["overall"]
        sc_emoji = get_signal_emoji(sc_overall)
        lines.append(f"### 1.1 SC原油主力 {sc_emoji} 综合信号：{sc_overall}（得分{sc_ratio:+.2f}）")
        lines.append("")
        if sc_summary:
            lines.append(f"- **最新价**：{fmt(sc_summary['close'], 2)} 元/桶")
            lines.append(f"- **涨跌**：{fmt(sc_summary['change'], 2)} 元（{fmt_pct(sc_summary['change_pct'])}）")
            lines.append(f"- **20日区间**：[{fmt(sc_summary['low_20'], 2)}, {fmt(sc_summary['high_20'], 2)}]")
        
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(sc_data["signals"]))
        lines.append("")

        # 原油趋势特征
        ind_sc = indicators_data.get("SC")
        if ind_sc is not None and not ind_sc.empty:
            trend_detail = analyze_crude_trend(ind_sc)
            lines.append(f"### 1.2 原油趋势特征：{trend_detail}")
            lines.append("")

    # ========== 沥青传导分析（第2章节）
    lines.append("## 🏗️ 二、沥青传导分析（权重20%）")
    lines.append("")
    bu_data = all_data.get("BU")
    if bu_data:
        bu_summary = bu_data["summary"]
        bu_overall, bu_ratio = bu_data["overall"]
        bu_emoji = get_signal_emoji(bu_overall)
        lines.append(f"### 2.1 BU沥青主力 {bu_emoji} 综合信号：{bu_overall}（得分{bu_ratio:+.2f}）")
        lines.append("")
        if bu_summary:
            lines.append(f"- **最新价**：{fmt(bu_summary['close'], 0)} 元/吨")
            lines.append(f"- **涨跌**：{fmt(bu_summary['change'], 0)} 元（{fmt_pct(bu_summary['change_pct'])}）")
            lines.append(f"- **20日区间**：[{fmt(bu_summary['low_20'], 0)}, {fmt(bu_summary['high_20'], 0)}]")
        
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(bu_data["signals"]))
        lines.append("")

        # 原油-沥青裂差分析
        if sc_data and sc_summary and bu_summary:
            sc_per_barrel = sc_summary['close']
            bu_per_barrel = bu_summary['close'] / 7.35
            crack_spread = sc_per_barrel - bu_per_barrel
            lines.append(f"### 2.2 原油-沥青裂差分析")
            lines.append("")
            lines.append(f"- **SC原油**：{fmt(sc_per_barrel, 2)} 元/桶")
            lines.append(f"- **BU沥青（桶换算）**：{fmt(bu_per_barrel, 2)} 元/桶")
            lines.append(f"- **裂差（SC-BU桶）**：{fmt(crack_spread, 2)} 元/桶")
            if crack_spread > 5:
                lines.append(f"- **判断**：炼化利润良好，沥青相对偏强")
            elif crack_spread < -5:
                lines.append(f"- **判断**：炼化利润压缩，沥青相对偏弱")
            else:
                lines.append(f"- **判断**：裂差处于正常区间")
            lines.append("")
    else:
        lines.append("*沥青数据暂缺，请检查数据源*")
        lines.append("")

    # ========== 燃料油行情速览
    lines.append("## 三、燃料油行情速览")
    lines.append("")
    lines.append("| 品种 | 最新价 | 涨跌 | 涨跌幅 | 20日高 | 20日低 |")
    lines.append("|------|--------|------|--------|--------|--------|")

    fu_data = all_data.get("FU")
    lu_data = all_data.get("LU")

    if fu_data:
        fu_summary = fu_data["summary"]
        fu_name = SYMBOLS["FU"]["name"]
        if fu_summary:
            lines.append(f"| {fu_name} | {fmt(fu_summary['close'], 0)} | {fmt(fu_summary['change'], 0)} | {fmt_pct(fu_summary['change_pct'])} | {fmt(fu_summary['high_20'], 0)} | {fmt(fu_summary['low_20'], 0)} |")

    if lu_data:
        lu_summary = lu_data["summary"]
        lu_name = SYMBOLS["LU"]["name"]
        if lu_summary:
            lines.append(f"| {lu_name} | {fmt(lu_summary['close'], 0)} | {fmt(lu_summary['change'], 0)} | {fmt_pct(lu_summary['change_pct'])} | {fmt(lu_summary['high_20'], 0)} | {fmt(lu_summary['low_20'], 0)} |")
    lines.append("")

    # ========== 燃料油技术分析
    lines.append("## 四、燃料油技术分析")
    lines.append("")
    for sym in ["FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        name = SYMBOLS[sym]["name"]
        overall, ratio = data["overall"]
        emoji = get_signal_emoji(overall)
        lines.append(f"### {name} {emoji} 综合信号：{overall}（得分{ratio:+.2f}）")
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(data["signals"]))
        lines.append("")

    # ========== 策略要点
    lines.append("## 五、早间策略要点（原油系产业链三层联动）")
    lines.append("")
    if sc_data:
        sc_overall, sc_ratio = sc_data["overall"]
        cond_coef, cond_desc = calculate_conduction_coefficient(sc_overall, sc_ratio)
        lines.append(f"> **🔗 传导系数**：{cond_coef:.0%}（{cond_desc}）")
        lines.append("")
        for sym in ["SC", "BU", "FU", "LU"]:
            data = all_data.get(sym)
            if not data:
                continue
            name = SYMBOLS[sym]["name"]
            overall, ratio = data["overall"]
            pos, advice = get_position_advice(overall, ratio)
            summary = data["summary"]
            if not summary:
                continue
            weight = SYMBOLS[sym]["weight"]
            lines.append(f"**{name}（权重{weight:.0%}）**：{overall}，建议{pos}")
            lines.append(f"- 最新价 {fmt(summary['close'], 0 if sym != 'SC' else 2)}，日涨跌 {fmt_pct(summary['change_pct'])}")
            lines.append(f"- {advice}")
            lines.append("")

    lines.append("## 六、今日关注")
    lines.append("")
    lines.append("- **SC原油**：原油是产业链成本端锚定，永远关注原油动向！")
    lines.append("- **BU沥青**：连接原油与燃料油的中间体，关注炼化利润")
    lines.append("- **高低硫价差**：关注LU-FU价差")
    lines.append("- **原油-沥青裂差**：评估炼化利润方向")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本报告基于TqSdk实盘K线 + Ta-Lib计算生成，仅供研究参考，不构成投资建议。*")

    return "\n".join(lines)


def generate_noon_report(all_data, indicators_data, date_str):
    lines = []
    lines.append(f"# 原油系产业链午间复盘 v2.2.0")
    lines.append("")
    lines.append(f"> **💡 数据来源：TqSdk实盘K线 → DuckDB → Ta-Lib指标计算")
    lines.append(f"> **⚠️ 产业链权重：SC原油40%、BU沥青20%、FU/LU各20%")
    lines.append(f"> **⏰ 数据时效：{date_str}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ========== 原油永远置顶
    lines.append("## ⭐ 一、原油核心分析")
    lines.append("")
    sc_data = all_data.get("SC")
    if sc_data:
        sc_summary = sc_data["summary"]
        sc_overall, sc_ratio = sc_data["overall"]
        sc_emoji = get_signal_emoji(sc_overall)
        lines.append(f"### 1.1 SC原油主力 {sc_emoji} 综合信号：{sc_overall}")
        lines.append("")
        if sc_summary:
            lines.append(f"- **最新价**：{fmt(sc_summary['close'], 2)} 元/桶")
            lines.append(f"- **涨跌**：{fmt_pct(sc_summary['change_pct'])}")
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(sc_data["signals"]))
        lines.append("")

    # ========== 沥青传导分析
    lines.append("## 🏗️ 二、沥青传导分析")
    lines.append("")
    bu_data = all_data.get("BU")
    if bu_data:
        bu_summary = bu_data["summary"]
        bu_overall, bu_ratio = bu_data["overall"]
        bu_emoji = get_signal_emoji(bu_overall)
        lines.append(f"### 2.1 BU沥青主力 {bu_emoji} 综合信号：{bu_overall}")
        lines.append("")
        if bu_summary:
            lines.append(f"- **最新价**：{fmt(bu_summary['close'], 0)} 元/吨")
            lines.append(f"- **涨跌**：{fmt_pct(bu_summary['change_pct'])}")
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(bu_data["signals"]))
        lines.append("")
    else:
        lines.append("*沥青数据暂缺*")
        lines.append("")

    # ========== 行情快照
    lines.append("## 三、午间行情快照")
    lines.append("")
    lines.append("| 品种 | 最新价 | 涨跌幅 | 开盘 | 最高 | 最低 | 成交量 |")
    lines.append("|------|--------|--------|------|------|------|--------|")

    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        summary = data["summary"]
        if not summary:
            continue
        name = SYMBOLS[sym]["name"]
        lines.append(
            f"| {name} | {fmt(summary['close'], 0 if sym != 'SC' else 2)} | {fmt_pct(summary['change_pct'])} | "
            f"{fmt(summary['open'], 0 if sym != 'SC' else 2)} | {fmt(summary['high'], 0 if sym != 'SC' else 2)} | {fmt(summary['low'], 0 if sym != 'SC' else 2)} | {fmt(summary['volume'], 0)} |"
        )
    lines.append("")

    # ========== 技术指标
    lines.append("## 四、技术指标实时状态")
    lines.append("")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        name = SYMBOLS[sym]["name"]
        overall, ratio = data["overall"]
        emoji = get_signal_emoji(overall)
        lines.append(f"### {name} — {emoji} {overall}")
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(data["signals"]))
        lines.append("")

    # ========== 策略建议
    lines.append("## 五、午间策略建议")
    lines.append("")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        name = SYMBOLS[sym]["name"]
        overall, ratio = data["overall"]
        pos, advice = get_position_advice(overall, ratio)
        summary = data["summary"]
        lines.append(f"### {name}")
        lines.append(f"- **综合信号**：{overall} → 建议**{pos}**")
        if summary:
            lines.append(f"- 当前价 {fmt(summary['close'], 0 if sym != 'SC' else 2)}")
        lines.append(f"- {advice}")
        lines.append("")

    lines.append("## 六、价差分析")
    lines.append("")
    fu_data = all_data.get("FU")
    lu_data = all_data.get("LU")
    bu_data = all_data.get("BU")
    sc_data = all_data.get("SC")
    if fu_data and lu_data:
        fu_sum = fu_data["summary"]
        lu_sum = lu_data["summary"]
        if fu_sum and lu_sum:
            spread_lu_fu = lu_sum["close"] - fu_sum["close"]
            lines.append(f"- **LU-FU价差**：{spread_lu_fu:.0f} 元/吨")
            lines.append(f"- **正常区间**：300~500 元/吨")
            if spread_lu_fu > 500:
                lines.append(f"- **判断**：价差偏高（{spread_lu_fu:.0f} > 500），存在回归动力")
            elif spread_lu_fu < 300:
                lines.append(f"- **判断**：价差偏低（{spread_lu_fu:.0f} < 300），LU被低估")
            else:
                lines.append(f"- **判断**：价差处于正常区间")
    if sc_data and bu_data:
        sc_sum = sc_data["summary"]
        bu_sum = bu_data["summary"]
        if sc_sum and bu_sum:
            sc_per_barrel = sc_sum['close']
            bu_per_barrel = bu_sum['close'] / 7.35
            crack_spread = sc_per_barrel - bu_per_barrel
            lines.append(f"- **原油-沥青裂差**：{fmt(crack_spread, 2)} 元/桶")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*本报告基于TqSdk实盘K线 + Ta-Lib计算生成，仅供研究参考，不构成投资建议。*")

    return "\n".join(lines)


def generate_evening_report(all_data, indicators_data, date_str):
    lines = []
    lines.append(f"# 原油系产业链晚间收盘报告 v2.2.0")
    lines.append("")
    lines.append(f"> **💡 数据来源：TqSdk实盘K线 → DuckDB → Ta-Lib指标计算")
    lines.append(f"> **⚠️ 产业链权重：SC原油40%、BU沥青20%、FU/LU各20%")
    lines.append(f"> **⏰ 数据时效：{date_str}")
    lines.append(f"> **📊 覆盖品种：SC、BU、FU、LU")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ========== 原油永远置顶
    lines.append("## ⭐ 一、原油核心分析（权重40%）")
    lines.append("")
    sc_data = all_data.get("SC")
    if sc_data:
        sc_summary = sc_data["summary"]
        sc_overall, sc_ratio = sc_data["overall"]
        sc_emoji = get_signal_emoji(sc_overall)
        lines.append(f"### 1.1 SC原油主力 {sc_emoji} 综合信号：{sc_overall}（得分{sc_ratio:+.2f}）")
        lines.append("")
        if sc_summary:
            amplitude = ((sc_summary["high"] - sc_summary["low"]) / sc_summary["close"] * 100) if sc_summary["close"] != 0 else 0
            lines.append(f"- **收盘价**：{fmt(sc_summary['close'], 2)} 元/桶")
            lines.append(f"- **涨跌**：{fmt(sc_summary['change'], 2)} 元（{fmt_pct(sc_summary['change_pct'])}）")
            lines.append(f"- **振幅**：{fmt_pct(amplitude)}")
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(sc_data["signals"]))
        lines.append("")

    # ========== 沥青传导分析
    lines.append("## 🏗️ 二、沥青传导分析（权重20%）")
    lines.append("")
    bu_data = all_data.get("BU")
    if bu_data:
        bu_summary = bu_data["summary"]
        bu_overall, bu_ratio = bu_data["overall"]
        bu_emoji = get_signal_emoji(bu_overall)
        lines.append(f"### 2.1 BU沥青主力 {bu_emoji} 综合信号：{bu_overall}（得分{bu_ratio:+.2f}）")
        lines.append("")
        if bu_summary:
            amplitude = ((bu_summary["high"] - bu_summary["low"]) / bu_summary["close"] * 100) if bu_summary["close"] != 0 else 0
            lines.append(f"- **收盘价**：{fmt(bu_summary['close'], 0)} 元/吨")
            lines.append(f"- **涨跌**：{fmt(bu_summary['change'], 0)} 元（{fmt_pct(bu_summary['change_pct'])}）")
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(bu_data["signals"]))
        lines.append("")

        # 原油-沥青裂差
        if sc_data and sc_summary:
            sc_per_barrel = sc_summary['close']
            bu_per_barrel = bu_summary['close'] / 7.35
            crack_spread = sc_per_barrel - bu_per_barrel
            lines.append(f"### 2.2 原油-沥青裂差")
            lines.append("")
            lines.append(f"- **裂差（SC-BU桶）**：{fmt(crack_spread, 2)} 元/桶")
            if crack_spread > 5:
                lines.append(f"- **判断**：炼化利润良好")
            elif crack_spread < -5:
                lines.append(f"- **判断**：炼化利润压缩")
            else:
                lines.append(f"- **判断**：裂差正常")
            lines.append("")
    else:
        lines.append("*沥青数据暂缺*")
        lines.append("")

    # ========== 今日行情总结
    lines.append("## 三、今日行情总结")
    lines.append("")
    lines.append("| 品种 | 收盘价 | 涨跌 | 涨跌幅 | 开盘 | 最高 | 最低 | 振幅 |")
    lines.append("|------|--------|------|--------|------|------|------|------|")

    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        summary = data["summary"]
        if not summary:
            continue
        name = SYMBOLS[sym]["name"]
        amplitude = ((summary["high"] - summary["low"]) / summary["close"] * 100) if summary["close"] != 0 else 0
        lines.append(
            f"| {name} | {fmt(summary['close'], 0 if sym != 'SC' else 2)} | {fmt(summary['change'], 0 if sym != 'SC' else 2)} | {fmt_pct(summary['change_pct'])} | "
            f"{fmt(summary['open'], 0 if sym != 'SC' else 2)} | {fmt(summary['high'], 0 if sym != 'SC' else 2)} | {fmt(summary['low'], 0 if sym != 'SC' else 2)} | {fmt_pct(amplitude)} |"
        )
    lines.append("")

    # ========== 技术指标完整分析
    lines.append("## 四、技术指标完整分析（13项）")
    lines.append("")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        name = SYMBOLS[sym]["name"]
        overall, ratio = data["overall"]
        emoji = get_signal_emoji(overall)
        lines.append(f"### {name} — {emoji} 综合信号：{overall}")
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(data["signals"]))
        lines.append("")

    # ========== 品种强弱对比
    lines.append("## 五、品种强弱对比")
    lines.append("")
    fu_data = all_data.get("FU")
    lu_data = all_data.get("LU")
    sc_data = all_data.get("SC")
    bu_data = all_data.get("BU")
    if fu_data and lu_data:
        fu_sum = fu_data["summary"]
        lu_sum = lu_data["summary"]
        sc_sum = sc_data["summary"] if sc_data else None
        bu_sum = bu_data["summary"] if bu_data else None
        spread = (lu_sum["close"] - fu_sum["close"]) if (fu_sum and lu_sum) else 0
        lines.append(f"| 品种 | 价格 | 涨跌 | 信号 |")
        lines.append(f"|------|------|------|------|")
        if sc_sum:
            sc_overall, _ = sc_data["overall"]
            lines.append(f"| SC原油 | {fmt(sc_sum['close'], 2)} | {fmt_pct(sc_sum['change_pct'])} | {sc_overall} |")
        if bu_sum:
            bu_overall, _ = bu_data["overall"]
            lines.append(f"| BU沥青 | {fmt(bu_sum['close'], 0)} | {fmt_pct(bu_sum['change_pct'])} | {bu_overall} |")
        if fu_sum:
            fu_overall, _ = fu_data["overall"]
            lines.append(f"| FU主力 | {fmt(fu_sum['close'], 0)} | {fmt_pct(fu_sum['change_pct'])} | {fu_overall} |")
        if lu_sum:
            lu_overall, _ = lu_data["overall"]
            lines.append(f"| LU主力 | {fmt(lu_sum['close'], 0)} | {fmt_pct(lu_sum['change_pct'])} | {lu_overall} |")
        lines.append("")
        lines.append(f"**高低硫价差（LU-FU）**：{spread:.0f} 元/吨")
    lines.append("")

    # ========== 风险管理提醒
    lines.append("## 六、风险管理提醒")
    lines.append("")
    lines.append("### 仓位建议")
    lines.append("")
    lines.append("| 品种 | 综合信号 | 建议仓位 | 止损参考 |")
    lines.append("|------|---------|---------|---------|")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        name = SYMBOLS[sym]["name"]
        overall, ratio = data["overall"]
        pos, _ = get_position_advice(overall, ratio)
        summary = data["summary"]
        if ratio < -0.5:
            pos_limit = "≤5%（空头趋势）"
        elif ratio < -0.2:
            pos_limit = "≤8%（偏空）"
        elif ratio < 0.2:
            pos_limit = "≤6%（震荡）"
        elif ratio < 0.5:
            pos_limit = "≤10%（偏多）"
        else:
            pos_limit = "≤12%（多头趋势）"
        if summary:
            stop_loss = f"{summary['low']:.0f}下方" if sym != "SC" else f"{summary['low']:.2f}下方"
        else:
            stop_loss = "N/A"
        lines.append(f"| {name} | {overall} | {pos_limit} | {stop_loss} |")
    lines.append("")

    lines.append("## 七、明日展望")
    lines.append("")
    lines.append("### 关键观察点")
    lines.append("")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        name = SYMBOLS[sym]["name"]
        overall, ratio = data["overall"]
        summary = data["summary"]
        if not summary:
            continue
        if ratio < -0.3:
            outlook = "空头延续风险，关注支撑位是否有效"
        elif ratio > 0.3:
            outlook = "多头延续可能，关注阻力位突破情况"
        else:
            outlook = "震荡格局，关注方向选择"
        lines.append(f"- **{name}**：{outlook}，支撑 {fmt(summary['low'], 0 if sym != 'SC' else 2)} / 阻力 {fmt(summary['high'], 0 if sym != 'SC' else 2)}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本报告基于TqSdk实盘K线 + Ta-Lib计算生成，仅供研究参考，不构成投资建议。*")

    return "\n".join(lines)


def generate_weekly_report(all_data, indicators_data, date_str):
    lines = []
    lines.append(f"# 原油系产业链周度深度报告 v2.2.0")
    lines.append("")
    lines.append(f"> **💡 数据来源：TqSdk实盘K线 → DuckDB → Ta-Lib指标计算")
    lines.append(f"> **⚠️ 产业链权重：SC原油40%、BU沥青20%、FU/LU各20%")
    lines.append(f"> **⏰ 数据时效：{date_str}")
    lines.append(f"> **📊 分析周期：近120个交易日")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ========== 原油永远置顶！
    lines.append("## ⭐ 一、原油核心分析（权重40%）")
    lines.append("")
    sc_data = all_data.get("SC")
    if sc_data:
        sc_summary = sc_data["summary"]
        sc_overall, sc_ratio = sc_data["overall"]
        sc_emoji = get_signal_emoji(sc_overall)
        ind_sc = indicators_data.get("SC")

        lines.append(f"### 1.1 SC原油主力 {sc_emoji} 综合信号：{sc_overall}（得分{sc_ratio:+.2f}）")
        lines.append("")

        if ind_sc is not None and not ind_sc.empty:
            week_sc = ind_sc.tail(5)
            if not week_sc.empty:
                week_open = week_sc.iloc[0]["open"]
                week_close = week_sc.iloc[-1]["close"]
                week_high = week_sc["high"].max()
                week_low = week_sc["low"].min()
                week_change = week_close - week_open
                week_change_pct = (week_change / week_open * 100) if week_open != 0 else 0
                week_amplitude = ((week_high - week_low) / week_close * 100) if week_close != 0 else 0
                lines.append(f"| 项目 | 数值 |")
                lines.append(f"|------|------|")
                lines.append(f"| **本周收盘 | {fmt(week_close, 2)} 元/桶 |")
                lines.append(f"| **周涨跌 | {fmt(week_change, 2)} 元（{fmt_pct(week_change_pct)}） |")
                lines.append(f"| **周振幅 | {fmt_pct(week_amplitude)} |")
                lines.append("")

        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(sc_data["signals"]))
        lines.append("")

        if ind_sc is not None and not ind_sc.empty:
            recent_sc = ind_sc.tail(20)
            ma5_sc = recent_sc["MA5"].iloc[-1]
            ma10_sc = recent_sc["MA10"].iloc[-1]
            ma20_sc = recent_sc["MA20"].iloc[-1]
            ma60_sc = recent_sc["MA60"].iloc[-1]
            latest_rsi_sc = recent_sc["RSI_14"].iloc[-1]
            latest_macd_sc = recent_sc["MACD_HIST"].iloc[-1]

            lines.append("### 1.2 近期原油趋势特征")
            lines.append("")
            lines.append(f"- **均线结构**：MA5={fmt(ma5_sc, 2)}, MA10={fmt(ma10_sc, 2)}, MA20={fmt(ma20_sc, 2)}, MA60={fmt(ma60_sc, 2)}")
            if ma5_sc > ma10_sc > ma20_sc:
                lines.append(f"  - 短期均线多头排列，原油短期趋势强劲！")
            elif ma5_sc < ma10_sc < ma20_sc:
                lines.append(f"  - 短期均线空头排列，原油弱势！")
            else:
                lines.append(f"  - 均线交织，震荡")
            lines.append(f"- **RSI(14)**：{fmt(latest_rsi_sc)}")
            lines.append(f"- **MACD**：{fmt(latest_macd_sc)}")
            lines.append("")

    # ========== 沥青传导分析
    lines.append("## 🏗️ 二、沥青传导分析（权重20%）")
    lines.append("")
    bu_data = all_data.get("BU")
    if bu_data:
        bu_summary = bu_data["summary"]
        bu_overall, bu_ratio = bu_data["overall"]
        bu_emoji = get_signal_emoji(bu_overall)
        ind_bu = indicators_data.get("BU")

        lines.append(f"### 2.1 BU沥青主力 {bu_emoji} 综合信号：{bu_overall}（得分{bu_ratio:+.2f}）")
        lines.append("")

        if ind_bu is not None and not ind_bu.empty:
            week_bu = ind_bu.tail(5)
            if not week_bu.empty:
                week_open = week_bu.iloc[0]["open"]
                week_close = week_bu.iloc[-1]["close"]
                week_high = week_bu["high"].max()
                week_low = week_bu["low"].min()
                week_change = week_close - week_open
                week_change_pct = (week_change / week_open * 100) if week_open != 0 else 0
                lines.append(f"| 项目 | 数值 |")
                lines.append(f"|------|------|")
                lines.append(f"| **本周收盘 | {fmt(week_close, 0)} 元/吨 |")
                lines.append(f"| **周涨跌 | {fmt(week_change, 0)} 元（{fmt_pct(week_change_pct)}） |")
                lines.append("")

        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(bu_data["signals"]))
        lines.append("")

        # 原油-沥青裂差
        if sc_data and sc_summary:
            sc_per_barrel = sc_summary['close']
            bu_per_barrel = bu_summary['close'] / 7.35
            crack_spread = sc_per_barrel - bu_per_barrel
            lines.append("### 2.2 原油-沥青裂差周度分析")
            lines.append("")
            lines.append(f"- **本周裂差均值**：{fmt(crack_spread, 2)} 元/桶")
            if crack_spread > 5:
                lines.append(f"- **判断**：炼化利润良好，沥青相对偏强")
            elif crack_spread < -5:
                lines.append(f"- **判断**：炼化利润压缩，沥青相对偏弱")
            else:
                lines.append(f"- **判断**：裂差处于正常区间")
            lines.append("")
    else:
        lines.append("*沥青数据暂缺*")
        lines.append("")

    # ========== 本周行情回顾
    lines.append("## 三、本周行情回顾")
    lines.append("")
    lines.append("| 品种 | 本周收盘 | 周涨跌 | 周涨跌幅 | 本周最高 | 本周最低 |")
    lines.append("|------|---------|--------|--------|--------|------|")

    for sym in ["SC", "BU", "FU", "LU"]:
        ind_df = indicators_data.get(sym)
        if ind_df is None or ind_df.empty:
            continue
        name = SYMBOLS[sym]["name"]
        week = ind_df.tail(5)
        if week.empty:
            continue
        week_open = week.iloc[0]["open"]
        week_close = week.iloc[-1]["close"]
        week_high = week["high"].max()
        week_low = week["low"].min()
        week_change = week_close - week_open
        week_change_pct = (week_change / week_open * 100) if week_open != 0 else 0
        lines.append(
            f"| {name} | {fmt(week_close, 0 if sym != 'SC' else 2)} | {fmt(week_change, 0 if sym != 'SC' else 2)} | {fmt_pct(week_change_pct)} | "
            f"{fmt(week_high, 0 if sym != 'SC' else 2)} | {fmt(week_low, 0 if sym != 'SC' else 2)} |"
        )
    lines.append("")

    # ========== 技术面深度分析
    lines.append("## 四、技术面深度分析")
    lines.append("")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        name = SYMBOLS[sym]["name"]
        overall, ratio = data["overall"]
        emoji = get_signal_emoji(overall)
        ind_df = indicators_data.get(sym)
        lines.append(f"### {name} — {emoji} {overall}")
        lines.append("")
        lines.append("#### 完整技术指标（13项）")
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 | 说明 |")
        lines.append("|------|------|------|------|")
        lines.append(get_technical_table(data["signals"]))
        lines.append("")
        if ind_df is not None and not ind_df.empty:
            lines.append("#### 近期趋势特征")
            lines.append("")
            recent = ind_df.tail(20)
            ma5 = recent["MA5"].iloc[-1]
            ma10 = recent["MA10"].iloc[-1]
            ma20 = recent["MA20"].iloc[-1]
            ma60 = recent["MA60"].iloc[-1]
            latest_rsi = recent["RSI_14"].iloc[-1]
            latest_macd = recent["MACD_HIST"].iloc[-1]
            lines.append(f"- **均线结构**：MA5={fmt(ma5, 0 if sym != 'SC' else 2)}, MA10={fmt(ma10, 0 if sym != 'SC' else 2)}, MA20={fmt(ma20, 0 if sym != 'SC' else 2)}, MA60={fmt(ma60, 0 if sym != 'SC' else 2)}")
            if ma5 < ma10 < ma20:
                lines.append(f"  - 短期均线空头排列")
            elif ma5 > ma10 > ma20:
                lines.append(f"  - 短期均线多头排列")
            else:
                lines.append(f"  - 均线交织")
            lines.append(f"- **RSI(14)**：{fmt(latest_rsi)}")
            lines.append(f"- **MACD**：{fmt(latest_macd)}")
            lines.append("")

    # ========== 价差分析
    lines.append("## 五、品种间价差分析")
    lines.append("")
    fu_data = all_data.get("FU")
    lu_data = all_data.get("LU")
    sc_data = all_data.get("SC")
    bu_data = all_data.get("BU")
    if fu_data and lu_data:
        fu_sum = fu_data["summary"]
        lu_sum = lu_data["summary"]
        sc_sum = sc_data["summary"] if sc_data else None
        bu_sum = bu_data["summary"] if bu_data else None
        spread_lu_fu = lu_sum["close"] - fu_sum["close"] if (fu_sum and lu_sum) else 0
        lines.append(f"### 5.1 高低硫价差（LU-FU）")
        lines.append("")
        lines.append(f"- **当前值**：{spread_lu_fu:.0f} 元/吨")
        lines.append(f"- **正常区间**：300~500 元/吨")
        if spread_lu_fu > 600:
            lines.append(f"- **状态**：高位（>600），存在回归动力")
            lines.append(f"- **策略**：可考虑买FU卖LU价差回归策略")
        elif spread_lu_fu > 500:
            lines.append(f"- **状态**：偏高（500~600），关注回归信号")
        elif spread_lu_fu > 300:
            lines.append(f"- **状态**：正常区间（300~500），无明显套利机会")
        else:
            lines.append(f"- **状态**：偏低（<300），LU被低估")
        lines.append("")

    if sc_data and bu_data:
        lines.append(f"### 5.2 原油-沥青裂差")
        lines.append("")
        sc_sum = sc_data["summary"] if sc_data else None
        bu_sum = bu_data["summary"] if bu_data else None
        if sc_sum and bu_sum:
            sc_per_barrel = sc_sum['close']
            bu_per_barrel = bu_sum['close'] / 7.35
            crack_spread = sc_per_barrel - bu_per_barrel
            lines.append(f"- SC原油：{fmt(sc_per_barrel, 2)} 元/桶（桶换算）")
            lines.append(f"- BU沥青：{fmt(bu_per_barrel, 2)} 元/桶（桶换算）")
            lines.append(f"- 裂差：{fmt(crack_spread, 2)} 元/桶")
            if crack_spread > 5:
                lines.append(f"- **状态**：炼化利润良好")
            elif crack_spread < -5:
                lines.append(f"- **状态**：炼化利润压缩")
            else:
                lines.append(f"- **状态**：正常")
        lines.append("")

    if fu_data and sc_data:
        lines.append(f"### 5.3 原油-燃料油联动")
        lines.append("")
        fu_sum = fu_data["summary"]
        sc_sum = sc_data["summary"] if sc_data else None
        if fu_sum and sc_sum:
            lines.append(f"- FU主力：{fmt(fu_sum['close'], 0)} 元/吨")
            lines.append(f"- SC原油：{fmt(sc_sum['close'], 2)} 元/桶")
            lines.append(f"- FU涨跌幅：{fmt_pct(fu_sum['change_pct'])} | SC涨跌幅：{fmt_pct(sc_sum['change_pct'])}")
            if abs(fu_sum['change_pct'] - sc_sum['change_pct']) > 2:
                lines.append(f"- **内外分化明显，关注区域供需因素**")
            else:
                lines.append(f"- **内外联动正常**")
        lines.append("")

    # ========== 综合策略建议
    lines.append("## 六、综合策略建议")
    lines.append("")
    lines.append("### 6.1 本周策略总结")
    lines.append("")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        name = SYMBOLS[sym]["name"]
        overall, ratio = data["overall"]
        pos, advice = get_position_advice(overall, ratio)
        summary = data["summary"]
        if not summary:
            continue
        weight = SYMBOLS[sym]["weight"]
        lines.append(f"#### {name}（权重{weight:.0%}）")
        lines.append(f"- **综合信号**：{overall}（得分{ratio:+.2f}）")
        lines.append(f"- **操作建议**：{pos} — {advice}")
        lines.append(f"- **20日区间**：[{fmt(summary['low_20'], 0 if sym != 'SC' else 2)}, {fmt(summary['high_20'], 0 if sym != 'SC' else 2)}]")
        lines.append("")

    lines.append("### 6.2 下周关注要点")
    lines.append("")
    lines.append("1. **SC原油**：永远第一权重！原油是成本端锚定！")
    lines.append("2. **BU沥青**：连接原油与燃料油的中间体，关注炼化利润")
    lines.append("3. **高低硫价差**：关注LU-FU价差方向")
    lines.append("4. **原油-沥青裂差**：评估炼化利润变化")
    lines.append("5. **持仓变化**：关注资金流向")
    lines.append("6. **库存数据**：关注沥青厂库、燃料油库存变化")
    lines.append("7. **传导关系**：关注原油→沥青→燃料油三层传导强度")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本报告基于TqSdk实盘K线 + Ta-Lib计算生成，仅供研究参考，不构成投资建议。*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="原油系产业链报告生成v2.2.0 - 含沥青分析")
    parser.add_argument("--type", choices=["morning", "noon", "evening", "weekly", "all"], default="all")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"DuckDB文件不存在: {db_path}")
        logger.error("请先运行数据采集: python fetch_and_store.py")
        logger.error("再运行指标计算: python run_pipeline.py --skip-fetch")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y%m%d")

    logger.info(f"从DuckDB加载数据: {db_path}")
    all_data = {}
    indicators_data = {}
    for sym in SYMBOLS:
        kline_df, ind_df, sig_df = load_market_data(db_path, sym)
        summary = build_kline_summary(kline_df)
        weight = SYMBOLS[sym]["weight"]
        overall, ratio = compute_weighted_overall_signal(sig_df, weight)
        all_data[sym] = {
            "kline": kline_df,
            "indicators": ind_df,
            "signals": sig_df,
            "summary": summary,
            "overall": (overall, ratio),
        }
        indicators_data[sym] = ind_df
        logger.info(f"  {sym}: {len(kline_df)} K线, {len(ind_df)} 指标, {len(sig_df)} 信号 | 权重{weight:.0%} | 综合: {overall}")

    report_types = {
        "morning": ("早间快讯", generate_morning_report),
        "noon": ("午间复盘", generate_noon_report),
        "evening": ("晚间收盘", generate_evening_report),
        "weekly": ("周度深度", generate_weekly_report),
    }

    to_generate = report_types.keys() if args.type == "all" else [args.type]

    for rtype in to_generate:
        label, generator = report_types[rtype]
        logger.info(f"\n生成{label}报告...")
        content = generator(all_data, indicators_data, date_str)

        suffix = "weekly" if rtype == "weekly" else rtype
        filename = f"{suffix}_report_{timestamp}.md"
        filepath = REPORTS_DIR / filename
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"  ✅ {label}报告已保存: {filepath}")

    logger.info(f"\n全部报告生成完成，共 {len(to_generate)} 份（v2.2.0 原油系产业链版）")


if __name__ == "__main__":
    main()
