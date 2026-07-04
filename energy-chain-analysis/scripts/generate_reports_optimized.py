#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原油系产业链报告生成脚本 v3.0.0 (优化版)
优化目标：减少token消耗50%，保持核心信息完整性
优化策略：
1. 模板化报告结构，减少重复代码
2. 压缩技术指标表格，只显示关键指标
3. 缓存信号计算，避免重复计算
4. 简化格式化逻辑
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
DEFAULT_DB = BASE_DIR / "data" / "futures_data.duckdb"
REPORTS_DIR = BASE_DIR / "output" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = {
    "SC": {"name": "SC原油", "exchange": "INE", "unit": "元/桶", "weight": 0.40},
    "BU": {"name": "BU沥青", "exchange": "SHFE", "unit": "元/吨", "weight": 0.20},
    "FU": {"name": "FU燃料油", "exchange": "SHFE", "unit": "元/吨", "weight": 0.20},
    "LU": {"name": "LU低硫油", "exchange": "INE", "unit": "元/吨", "weight": 0.20},
    "PG": {"name": "PG液化气", "exchange": "DCE", "unit": "元/吨", "weight": 0.00, "independent": True},
}

# 关键指标列表（减少表格行数）
KEY_INDICATORS = [
    "RSI(14)", "MACD", "ADX(14)", "ATR(14)", "CCI(14)",
    "Williams %R", "均线排列", "STOCH(9,6)"
]

# 信号映射（简化输出）
SIGNAL_MAP = {
    "超买": "⚠️超买", "超卖": "📌超卖",
    "多头": "🟢多头", "空头": "🔴空头",
    "偏多": "🟢偏多", "偏空": "🔴偏空",
    "中性": "⚪中性", "无趋势": "⚪无趋势",
    "强势下跌": "🔻强跌", "强势上涨": "🔺强涨",
    "空头强势": "🔴空强", "多头强势": "🟢多强",
    "空头排列": "🔴空排", "多头排列": "🟢多排",
    "高波动": "⚠️高波", "低波动": "⚪低波",
}

# 位置建议映射
POSITION_MAP = {
    (0.5, float('inf')): ("趋势多单", "逢低做多"),
    (0.2, 0.5): ("轻仓偏多", "回调试多"),
    (-0.2, 0.2): ("观望为主", "等待信号"),
    (-0.5, -0.2): ("轻仓偏空", "反弹做空"),
    (float('-inf'), -0.5): ("趋势空单", "顺势做空"),
}


def load_market_data(db_path: Path, sym: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """从DuckDB加载市场数据"""
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


def fmt(val, decimals: int = 2) -> str:
    """格式化数值"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    return f"{val:,.{decimals}f}"


def fmt_pct(val) -> str:
    """格式化百分比"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"


def get_signal_emoji(signal: str) -> str:
    """获取信号表情符号"""
    return SIGNAL_MAP.get(signal, "⚪")


def get_position_advice(overall: str, ratio: float) -> Tuple[str, str]:
    """获取仓位建议"""
    for (low, high), (pos, advice) in POSITION_MAP.items():
        if low <= ratio < high:
            return pos, advice
    return "观望", "等待信号"


def build_kline_summary(kline_df: pd.DataFrame) -> Dict:
    """构建K线摘要"""
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


def compute_weighted_overall_signal(signals_df: pd.DataFrame, weight: float = 1.0) -> Tuple[str, float]:
    """计算综合信号（带权重）"""
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


def calculate_conduction_coefficient(sc_overall: str, sc_ratio: float) -> Tuple[float, str]:
    """计算原油传导系数"""
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


def get_technical_table_optimized(signals_df: pd.DataFrame) -> str:
    """优化技术指标表格（只显示关键指标）"""
    rows = []
    for _, s in signals_df.iterrows():
        ind = s["indicator"]
        # 只显示关键指标
        if ind not in KEY_INDICATORS:
            continue
        val = s["value"]
        sig = s["signal"]
        emoji = get_signal_emoji(sig)
        # 简化数值格式
        if ind in ("MACD", "ATR(14)", "CCI(14)"):
            val_str = fmt(val)
        elif ind in ("ROC",):
            val_str = fmt_pct(val)
        else:
            val_str = fmt(val)
        rows.append(f"| {ind} | {val_str} | {emoji} |")
    if not rows:
        return "| 指标 | 数值 | 信号 |\n|------|------|------|\n| 数据暂缺 | - | - |"
    return "| 指标 | 数值 | 信号 |\n|------|------|------|\n" + "\n".join(rows)


def generate_report_header(report_type: str, date_str: str, version: str = "v3.0") -> List[str]:
    """生成报告头（模板化）"""
    lines = [
        f"# {report_type} {version}",
        "",
        f"> 数据来源：TqSdk实盘K线 → DuckDB → Ta-Lib",
        f"> 产业链权重：SC原油40%、BU沥青20%、FU/LU各20%",
        f"> 数据时效：{date_str}",
        "",
        "---",
        "",
    ]
    return lines


def generate_symbol_section(sym: str, data: Dict, indicators_data: Dict, show_details: bool = True) -> List[str]:
    """生成单个品种的分析部分（模板化）"""
    lines = []
    name = SYMBOLS[sym]["name"]
    weight = SYMBOLS[sym]["weight"]
    
    if not data:
        lines.append(f"## {name}（权重{weight:.0%}）")
        lines.append("")
        lines.append("*数据暂缺*")
        lines.append("")
        return lines
    
    summary = data["summary"]
    overall, ratio = data["overall"]
    emoji = get_signal_emoji(overall)
    
    # 品种标题
    lines.append(f"## {name} {emoji} {overall}（{ratio:+.2f}）")
    lines.append("")
    
    # 价格信息（压缩格式）
    if summary:
        amplitude = ((summary["high"] - summary["low"]) / summary["close"] * 100) if summary["close"] != 0 else 0
        lines.append(f"**收盘**：{fmt(summary['close'], 2 if sym == 'SC' else 0)} {SYMBOLS[sym]['unit']} | "
                    f"**涨跌**：{fmt_pct(summary['change_pct'])} | "
                    f"**振幅**：{fmt_pct(amplitude)}")
        lines.append("")
    
    # 技术指标表格（优化版）
    lines.append("### 技术指标")
    lines.append("")
    lines.append(get_technical_table_optimized(data["signals"]))
    lines.append("")
    
    # 原油趋势特征（仅SC显示）
    if sym == "SC" and show_details:
        ind_sc = indicators_data.get("SC")
        if ind_sc is not None and not ind_sc.empty:
            recent = ind_sc.tail(20)
            ma5 = recent["MA5"].iloc[-1]
            ma10 = recent["MA10"].iloc[-1]
            ma20 = recent["MA20"].iloc[-1]
            rsi = recent["RSI_14"].iloc[-1]
            
            ma_status = ""
            if ma5 > ma10 > ma20:
                ma_status = "短期多头排列"
            elif ma5 < ma10 < ma20:
                ma_status = "短期空头排列"
            else:
                ma_status = "均线交织"
            
            lines.append(f"**趋势特征**：RSI={fmt(rsi)}，{ma_status}")
            lines.append("")
    
    return lines


def generate_spread_analysis(all_data: Dict) -> List[str]:
    """生成价差分析（压缩版）"""
    lines = ["## 价差分析", ""]
    
    fu_data = all_data.get("FU")
    lu_data = all_data.get("LU")
    sc_data = all_data.get("SC")
    bu_data = all_data.get("BU")
    
    # LU-FU价差
    if fu_data and lu_data:
        fu_sum = fu_data["summary"]
        lu_sum = lu_data["summary"]
        if fu_sum and lu_sum:
            spread = lu_sum["close"] - fu_sum["close"]
            status = "偏高" if spread > 500 else "偏低" if spread < 300 else "正常"
            lines.append(f"**LU-FU价差**：{spread:.0f}元/吨（{status}，正常区间300-500）")
    
    # 原油-沥青裂差
    if sc_data and bu_data:
        sc_sum = sc_data["summary"]
        bu_sum = bu_data["summary"]
        if sc_sum and bu_sum:
            crack = sc_sum['close'] - bu_sum['close'] / 7.35
            status = "良好" if crack > 5 else "压缩" if crack < -5 else "正常"
            lines.append(f"**原油-沥青裂差**：{fmt(crack, 2)}元/桶（{status}）")
    
    lines.append("")
    return lines


def generate_strategy_summary(all_data: Dict) -> List[str]:
    """生成策略总结（压缩版）"""
    lines = ["## 策略建议", ""]
    
    sc_data = all_data.get("SC")
    if sc_data:
        sc_overall, sc_ratio = sc_data["overall"]
        cond_coef, cond_desc = calculate_conduction_coefficient(sc_overall, sc_ratio)
        lines.append(f"**传导系数**：{cond_coef:.0%}（{cond_desc}）")
        lines.append("")
    
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if not data:
            continue
        name = SYMBOLS[sym]["name"]
        overall, ratio = data["overall"]
        pos, advice = get_position_advice(overall, ratio)
        summary = data["summary"]
        
        if summary:
            price_str = fmt(summary['close'], 2 if sym == 'SC' else 0)
            lines.append(f"**{name}**：{overall} → {pos} | 价格{price_str} | {advice}")
        else:
            lines.append(f"**{name}**：{overall} → {pos} | {advice}")
    
    lines.append("")
    return lines


def generate_risk_reminder() -> List[str]:
    """生成风险提醒（压缩版）"""
    lines = [
        "## 风险提醒",
        "",
        "- 单笔风险≤2%，日度亏损≤3%，周度亏损≤5%",
        "- 连续亏损3次降仓50%，5次暂停交易",
        "- OVX>35%仓位减半，>45%降至1/3",
        "",
    ]
    return lines


def generate_morning_report_optimized(all_data: Dict, indicators_data: Dict, date_str: str) -> str:
    """生成优化版早间报告"""
    lines = generate_report_header("原油系产业链早间快讯", date_str)
    
    # 原油核心分析（权重40%）
    lines.extend(generate_symbol_section("SC", all_data.get("SC"), indicators_data))
    
    # 沥青传导分析（权重20%）
    lines.extend(generate_symbol_section("BU", all_data.get("BU"), indicators_data, show_details=False))
    
    # 燃料油行情速览
    lines.append("## 燃料油行情")
    lines.append("")
    for sym in ["FU", "LU"]:
        data = all_data.get(sym)
        if data and data["summary"]:
            summary = data["summary"]
            lines.append(f"**{SYMBOLS[sym]['name']}**：{fmt(summary['close'], 0)}元/吨 | {fmt_pct(summary['change_pct'])}")
    lines.append("")
    
    # 策略总结
    lines.extend(generate_strategy_summary(all_data))
    
    # 风险提醒
    lines.extend(generate_risk_reminder())
    
    lines.append("---")
    lines.append("*本报告基于TqSdk实盘K线 + Ta-Lib计算生成，仅供研究参考，不构成投资建议。*")
    
    return "\n".join(lines)


def generate_evening_report_optimized(all_data: Dict, indicators_data: Dict, date_str: str) -> str:
    """生成优化版晚间报告"""
    lines = generate_report_header("原油系产业链晚间收盘报告", date_str)
    
    # 原油核心分析（权重40%）
    lines.extend(generate_symbol_section("SC", all_data.get("SC"), indicators_data))
    
    # 沥青传导分析（权重20%）
    lines.extend(generate_symbol_section("BU", all_data.get("BU"), indicators_data, show_details=False))
    
    # 行情总结表格
    lines.append("## 今日行情总结")
    lines.append("")
    lines.append("| 品种 | 收盘价 | 涨跌幅 | 振幅 |")
    lines.append("|------|--------|--------|------|")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if data and data["summary"]:
            summary = data["summary"]
            amplitude = ((summary["high"] - summary["low"]) / summary["close"] * 100) if summary["close"] != 0 else 0
            lines.append(f"| {SYMBOLS[sym]['name']} | {fmt(summary['close'], 2 if sym == 'SC' else 0)} | {fmt_pct(summary['change_pct'])} | {fmt_pct(amplitude)} |")
    lines.append("")
    
    # 技术指标分析（压缩版）
    lines.append("## 技术指标分析")
    lines.append("")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if data:
            name = SYMBOLS[sym]["name"]
            overall, ratio = data["overall"]
            emoji = get_signal_emoji(overall)
            lines.append(f"### {name} {emoji} {overall}")
            lines.append("")
            lines.append(get_technical_table_optimized(data["signals"]))
            lines.append("")
    
    # 价差分析
    lines.extend(generate_spread_analysis(all_data))
    
    # 策略总结
    lines.extend(generate_strategy_summary(all_data))
    
    # 风险提醒
    lines.extend(generate_risk_reminder())
    
    lines.append("---")
    lines.append("*本报告基于TqSdk实盘K线 + Ta-Lib计算生成，仅供研究参考，不构成投资建议。*")
    
    return "\n".join(lines)


def generate_noon_report_optimized(all_data: Dict, indicators_data: Dict, date_str: str) -> str:
    """生成优化版午间报告"""
    lines = generate_report_header("原油系产业链午间复盘", date_str)
    
    # 原油核心分析
    lines.extend(generate_symbol_section("SC", all_data.get("SC"), indicators_data))
    
    # 沥青传导分析
    lines.extend(generate_symbol_section("BU", all_data.get("BU"), indicators_data, show_details=False))
    
    # 行情快照
    lines.append("## 午间行情快照")
    lines.append("")
    lines.append("| 品种 | 最新价 | 涨跌幅 |")
    lines.append("|------|--------|--------|")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if data and data["summary"]:
            summary = data["summary"]
            lines.append(f"| {SYMBOLS[sym]['name']} | {fmt(summary['close'], 2 if sym == 'SC' else 0)} | {fmt_pct(summary['change_pct'])} |")
    lines.append("")
    
    # 策略建议
    lines.extend(generate_strategy_summary(all_data))
    
    # 价差分析
    lines.extend(generate_spread_analysis(all_data))
    
    lines.append("---")
    lines.append("*本报告基于TqSdk实盘K线 + Ta-Lib计算生成，仅供研究参考，不构成投资建议。*")
    
    return "\n".join(lines)


def generate_weekly_report_optimized(all_data: Dict, indicators_data: Dict, date_str: str) -> str:
    """生成优化版周度报告"""
    lines = generate_report_header("原油系产业链周度深度报告", date_str)
    
    # 原油核心分析（详细版）
    lines.extend(generate_symbol_section("SC", all_data.get("SC"), indicators_data))
    
    # 沥青传导分析
    lines.extend(generate_symbol_section("BU", all_data.get("BU"), indicators_data, show_details=False))
    
    # 周度行情总结
    lines.append("## 周度行情总结")
    lines.append("")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        ind_data = indicators_data.get(sym)
        if data and ind_data is not None and not ind_data.empty:
            name = SYMBOLS[sym]["name"]
            week_data = ind_data.tail(5)
            if not week_data.empty:
                week_open = week_data.iloc[0]["open"]
                week_close = week_data.iloc[-1]["close"]
                week_change = week_close - week_open
                week_change_pct = (week_change / week_open * 100) if week_open != 0 else 0
                lines.append(f"**{name}**：周收盘{fmt(week_close, 2 if sym == 'SC' else 0)} | 周涨跌{fmt_pct(week_change_pct)}")
    lines.append("")
    
    # 技术指标分析
    lines.append("## 技术指标分析")
    lines.append("")
    for sym in ["SC", "BU", "FU", "LU"]:
        data = all_data.get(sym)
        if data:
            name = SYMBOLS[sym]["name"]
            overall, ratio = data["overall"]
            emoji = get_signal_emoji(overall)
            lines.append(f"### {name} {emoji} {overall}")
            lines.append("")
            lines.append(get_technical_table_optimized(data["signals"]))
            lines.append("")
    
    # 价差分析
    lines.extend(generate_spread_analysis(all_data))
    
    # 策略总结
    lines.extend(generate_strategy_summary(all_data))
    
    # 风险提醒
    lines.extend(generate_risk_reminder())
    
    lines.append("---")
    lines.append("*本报告基于TqSdk实盘K线 + Ta-Lib计算生成，仅供研究参考，不构成投资建议。*")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="原油系产业链报告生成（优化版）")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB), help="DuckDB数据库路径")
    parser.add_argument("--report", type=str, choices=["morning", "noon", "evening", "weekly"], 
                       default="evening", help="报告类型")
    parser.add_argument("--date", type=str, default=None, help="日期字符串")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径")
    args = parser.parse_args()
    
    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"数据库不存在: {db_path}")
        return
    
    date_str = args.date or datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 加载数据
    all_data = {}
    indicators_data = {}
    for sym in ["SC", "BU", "FU", "LU", "PG"]:
        try:
            kline, indicators, signals = load_market_data(db_path, sym)
            summary = build_kline_summary(kline)
            overall, ratio = compute_weighted_overall_signal(signals)
            all_data[sym] = {
                "summary": summary,
                "overall": (overall, ratio),
                "signals": signals,
            }
            indicators_data[sym] = indicators
            logger.info(f"加载{sym}数据成功")
        except Exception as e:
            logger.warning(f"加载{sym}数据失败: {e}")
    
    # 生成报告
    if args.report == "morning":
        report = generate_morning_report_optimized(all_data, indicators_data, date_str)
    elif args.report == "noon":
        report = generate_noon_report_optimized(all_data, indicators_data, date_str)
    elif args.report == "evening":
        report = generate_evening_report_optimized(all_data, indicators_data, date_str)
    elif args.report == "weekly":
        report = generate_weekly_report_optimized(all_data, indicators_data, date_str)
    else:
        logger.error(f"未知报告类型: {args.report}")
        return
    
    # 输出报告
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"报告已保存到: {output_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
