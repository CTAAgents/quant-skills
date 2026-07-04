"""
燃料油分析图表生成脚本

功能：
    生成燃料油分析所需的四类核心图表：
    1. 价格走势图（含MA均线、布林带、成交量）
    2. 价差图（高低硫价差、裂解价差、内外价差）
    3. 技术指标图（RSI/CCI/MACD/ATR）
    4. 库存变化图

依赖：
    matplotlib, pandas, numpy

用法：
    python generate_charts.py --input data.csv --output charts/
    python generate_charts.py --demo  # 使用演示数据生成示例图表
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

# ========== 全局配置 ==========

# 中文字体兼容（Windows优先使用微软雅黑）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 150
plt.rcParams["savefig.bbox"] = "tight"

# 配色方案
COLORS = {
    "price": "#1f77b4",
    "ma5": "#ff7f0e",
    "ma10": "#2ca02c",
    "ma20": "#d62728",
    "ma60": "#9467bd",
    "boll_mid": "#8c564b",
    "boll_band": "#c5b0d5",
    "volume_up": "#e74c3c",
    "volume_down": "#2ecc71",
    "rsi": "#e67e22",
    "cci": "#9b59b6",
    "macd_dif": "#2980b9",
    "macd_dea": "#e74c3c",
    "macd_pos": "#e74c3c",
    "macd_neg": "#27ae60",
    "atr": "#16a085",
    "spread_hl": "#2c3e50",
    "spread_crack": "#8e44ad",
    "spread_io": "#c0392b",
    "inventory": "#2980b9",
    "inventory_change_pos": "#27ae60",
    "inventory_change_neg": "#e74c3c",
    "grid": "#ecf0f1",
}

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "charts"


# ========== 数据准备工具 ==========

def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    标准化输入DataFrame的列名和日期格式

    参数：
        df: 原始K线DataFrame

    返回：
        标准化后的DataFrame
    """
    result = df.copy()

    # 列名标准化
    col_map = {}
    for col in result.columns:
        cl = col.lower().strip()
        if cl in ("date", "datetime", "time"):
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
        result = result.rename(columns=col_map)

    # 日期解析
    if "date" in result.columns:
        result["date"] = pd.to_datetime(result["date"])
        result = result.sort_values("date").reset_index(drop=True)

    return result


def generate_demo_data(days: int = 120) -> pd.DataFrame:
    """
    生成演示用K线数据（模拟燃料油FU走势）

    参数：
        days: 生成天数

    返回：
        模拟K线DataFrame，含技术指标
    """
    from calculate_indicators import calculate_all_indicators, generate_demo_data as gen_raw

    raw_df = gen_raw(days)
    result = calculate_all_indicators(raw_df)
    return result


# ========== 一、价格走势图 ==========

def plot_price_trend(
    df: pd.DataFrame,
    title: str = "燃料油价格走势",
    show_volume: bool = True,
    show_boll: bool = True,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    绘制价格走势图（含MA均线、布林带、成交量）

    子图布局：
        主图：K线/收盘价 + MA5/10/20/60 + 布林带
        副图：成交量柱状图

    参数：
        df: 含技术指标的K线DataFrame
        title: 图表标题
        show_volume: 是否显示成交量子图
        show_boll: 是否显示布林带
        save_path: 保存路径，None则不保存

    返回：
        matplotlib Figure对象
    """
    df = prepare_dataframe(df)
    has_volume = show_volume and "volume" in df.columns

    # 布局：主图 + 可选成交量子图
    if has_volume:
        fig = plt.figure(figsize=(14, 8))
        gs = gridspec.GridSpec(3, 1, height_ratios=[3, 1, 0.05], hspace=0.08)
        ax_main = fig.add_subplot(gs[0])
        ax_vol = fig.add_subplot(gs[1], sharex=ax_main)
    else:
        fig, ax_main = plt.subplots(figsize=(14, 6))
        ax_vol = None

    dates = df["date"]

    # ---- 主图：收盘价 + 均线 ----
    ax_main.plot(dates, df["close"], color=COLORS["price"], linewidth=1.5, label="收盘价", zorder=5)

    ma_configs = [
        ("MA5", COLORS["ma5"], 0.8, "--"),
        ("MA10", COLORS["ma10"], 0.8, "--"),
        ("MA20", COLORS["ma20"], 1.0, "-"),
        ("MA60", COLORS["ma60"], 1.0, "-"),
    ]
    for col, color, lw, ls in ma_configs:
        if col in df.columns:
            ax_main.plot(dates, df[col], color=color, linewidth=lw, linestyle=ls, label=col, alpha=0.8)

    # 布林带
    if show_boll and "BOLL_UP" in df.columns:
        ax_main.plot(dates, df["BOLL_MID"], color=COLORS["boll_mid"], linewidth=0.8, linestyle=":", label="BOLL中轨")
        ax_main.fill_between(
            dates, df["BOLL_DN"], df["BOLL_UP"],
            color=COLORS["boll_band"], alpha=0.15, label="布林带"
        )

    ax_main.set_title(title, fontsize=14, fontweight="bold", pad=10)
    ax_main.set_ylabel("价格", fontsize=11)
    ax_main.legend(loc="upper left", fontsize=8, ncol=3, framealpha=0.8)
    ax_main.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)
    ax_main.tick_params(labelbottom=not has_volume)

    # ---- 副图：成交量 ----
    if ax_vol is not None and "volume" in df.columns:
        # 根据涨跌着色
        colors = []
        for i in range(len(df)):
            if df["close"].iloc[i] >= df["open"].iloc[i]:
                colors.append(COLORS["volume_up"])
            else:
                colors.append(COLORS["volume_down"])

        ax_vol.bar(dates, df["volume"], color=colors, alpha=0.7, width=0.8)
        ax_vol.set_ylabel("成交量", fontsize=10)
        ax_vol.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)

        # X轴日期格式
        ax_vol.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax_vol.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax_vol.get_xticklabels(), rotation=45, ha="right", fontsize=8)

    if save_path:
        fig.savefig(save_path)
        logger.info(f"价格走势图已保存: {save_path}")

    return fig


# ========== 二、价差图 ==========

def plot_spread_chart(
    fu_df: pd.DataFrame,
    lu_df: Optional[pd.DataFrame] = None,
    title: str = "燃料油价差分析",
    spread_data: Optional[dict] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    绘制价差分析图（高低硫价差、裂解价差、内外价差）

    参数：
        fu_df: FU主力合约K线DataFrame
        lu_df: LU主力合约K线DataFrame（可选，用于高低硫价差）
        title: 图表标题
        spread_data: 外部计算好的价差数据字典（可选）
        save_path: 保存路径

    返回：
        matplotlib Figure对象
    """
    fu_df = prepare_dataframe(fu_df)
    has_lu = lu_df is not None
    if has_lu:
        lu_df = prepare_dataframe(lu_df)

    # 确定子图数量
    n_plots = 1  # 至少有FU价格
    if has_lu:
        n_plots += 1  # 高低硫价差
    if spread_data and "crack_spread" in spread_data:
        n_plots += 1
    if spread_data and "domestic_foreign" in spread_data:
        n_plots += 1

    fig, axes = plt.subplots(n_plots, 1, figsize=(14, 4 * n_plots), sharex=True)
    if n_plots == 1:
        axes = [axes]

    fig.suptitle(title, fontsize=14, fontweight="bold", y=1.01)
    plot_idx = 0

    # ---- 子图1：FU价格走势 ----
    ax = axes[plot_idx]
    ax.plot(fu_df["date"], fu_df["close"], color=COLORS["price"], linewidth=1.2, label="FU收盘价")
    if "MA20" in fu_df.columns:
        ax.plot(fu_df["date"], fu_df["MA20"], color=COLORS["ma20"], linewidth=0.8, linestyle="--", label="FU MA20")
    ax.set_ylabel("FU价格 (元/吨)", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)
    plot_idx += 1

    # ---- 子图2：高低硫价差 ----
    if has_lu and plot_idx < n_plots:
        ax = axes[plot_idx]
        merged = pd.merge(
            fu_df[["date", "close"]].rename(columns={"close": "fu"}),
            lu_df[["date", "close"]].rename(columns={"close": "lu"}),
            on="date", how="inner"
        )
        if not merged.empty:
            spread = merged["lu"] - merged["fu"]
            ax.plot(merged["date"], spread, color=COLORS["spread_hl"], linewidth=1.2, label="高低硫价差(LU-FU)")
            ax.axhline(y=300, color="green", linestyle=":", alpha=0.6, label="正常下沿(300)")
            ax.axhline(y=500, color="red", linestyle=":", alpha=0.6, label="正常上沿(500)")
            ax.fill_between(merged["date"], 300, 500, alpha=0.08, color="blue")
            ax.set_ylabel("价差 (元/吨)", fontsize=10)
            ax.legend(loc="upper left", fontsize=8)
        ax.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)
        plot_idx += 1

    # ---- 子图3/4：外部提供的价差数据 ----
    if spread_data:
        for key, color, label in [
            ("crack_spread", COLORS["spread_crack"], "裂解价差"),
            ("domestic_foreign", COLORS["spread_io"], "内外价差"),
        ]:
            if key in spread_data and plot_idx < n_plots:
                ax = axes[plot_idx]
                sd = spread_data[key]
                if "values" in sd and isinstance(sd["values"], pd.Series):
                    vals = sd["values"].dropna()
                    x = fu_df["date"].iloc[:len(vals)] if len(vals) <= len(fu_df) else range(len(vals))
                    ax.plot(x, vals.values[:len(x)], color=color, linewidth=1.2, label=label)
                    ax.axhline(y=0, color="gray", linestyle="-", alpha=0.3)
                    if "normal_range" in sd and sd["normal_range"]:
                        lo, hi = sd["normal_range"]
                        ax.axhline(y=lo, color="green", linestyle=":", alpha=0.5)
                        ax.axhline(y=hi, color="red", linestyle=":", alpha=0.5)
                        ax.fill_between(
                            x if hasattr(x, "__len__") else range(len(vals)),
                            lo, hi, alpha=0.06, color="blue"
                        )
                    ax.set_ylabel(f"{label} ({sd.get('unit', '')})", fontsize=10)
                    ax.legend(loc="upper left", fontsize=8)
                ax.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)
                plot_idx += 1

    # X轴日期格式
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(axes[-1].get_xticklabels(), rotation=45, ha="right", fontsize=8)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path)
        logger.info(f"价差分析图已保存: {save_path}")

    return fig


# ========== 三、技术指标图 ==========

def plot_technical_indicators(
    df: pd.DataFrame,
    title: str = "燃料油技术指标",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    绘制技术指标子图（RSI/CCI/MACD/ATR）

    子图布局（4子图共享X轴）：
        RSI(14) + CCI(14) 合并为一个子图
        MACD(12,26,9)
        ATR(14)

    参数：
        df: 含技术指标的K线DataFrame
        title: 图表标题
        save_path: 保存路径

    返回：
        matplotlib Figure对象
    """
    df = prepare_dataframe(df)
    dates = df["date"]

    fig = plt.figure(figsize=(14, 12))
    gs = gridspec.GridSpec(4, 1, height_ratios=[2, 2, 2, 1.2], hspace=0.12)

    # ---- 子图1：RSI(14) ----
    ax_rsi = fig.add_subplot(gs[0])
    if "RSI_14" in df.columns:
        ax_rsi.plot(dates, df["RSI_14"], color=COLORS["rsi"], linewidth=1.2, label="RSI(14)")
        ax_rsi.axhline(y=70, color="red", linestyle="--", alpha=0.6, linewidth=0.8, label="超买(70)")
        ax_rsi.axhline(y=30, color="green", linestyle="--", alpha=0.6, linewidth=0.8, label="超卖(30)")
        ax_rsi.axhline(y=50, color="gray", linestyle=":", alpha=0.4)
        ax_rsi.fill_between(dates, 70, 100, alpha=0.05, color="red")
        ax_rsi.fill_between(dates, 0, 30, alpha=0.05, color="green")
        ax_rsi.set_ylim(0, 100)
        ax_rsi.set_ylabel("RSI", fontsize=10)
        ax_rsi.legend(loc="upper left", fontsize=8, ncol=3)
    ax_rsi.set_title(f"{title}", fontsize=14, fontweight="bold", pad=8)
    ax_rsi.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)
    ax_rsi.tick_params(labelbottom=False)

    # ---- 子图2：CCI(14) ----
    ax_cci = fig.add_subplot(gs[1], sharex=ax_rsi)
    cci_col = "CCI_14" if "CCI_14" in df.columns else "CCI_20"
    if cci_col in df.columns:
        ax_cci.plot(dates, df[cci_col], color=COLORS["cci"], linewidth=1.2, label="CCI(14)")
        ax_cci.axhline(y=100, color="red", linestyle="--", alpha=0.6, linewidth=0.8, label="强势(+100)")
        ax_cci.axhline(y=-100, color="green", linestyle="--", alpha=0.6, linewidth=0.8, label="弱势(-100)")
        ax_cci.axhline(y=0, color="gray", linestyle=":", alpha=0.4)
        ax_cci.fill_between(dates, 100, df[cci_col].max() * 1.1, alpha=0.05, color="red")
        ax_cci.fill_between(dates, df[cci_col].min() * 1.1, -100, alpha=0.05, color="green")
        ax_cci.set_ylabel("CCI", fontsize=10)
        ax_cci.legend(loc="upper left", fontsize=8, ncol=3)
    ax_cci.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)
    ax_cci.tick_params(labelbottom=False)

    # ---- 子图3：MACD(12,26,9) ----
    ax_macd = fig.add_subplot(gs[2], sharex=ax_rsi)
    if all(col in df.columns for col in ["MACD_DIF", "MACD_DEA", "MACD_HIST"]):
        ax_macd.plot(dates, df["MACD_DIF"], color=COLORS["macd_dif"], linewidth=1.0, label="DIF")
        ax_macd.plot(dates, df["MACD_DEA"], color=COLORS["macd_dea"], linewidth=1.0, label="DEA")

        # MACD柱状图着色
        hist = df["MACD_HIST"]
        colors = [COLORS["macd_pos"] if v >= 0 else COLORS["macd_neg"] for v in hist]
        ax_macd.bar(dates, hist, color=colors, alpha=0.6, width=0.8, label="MACD柱")
        ax_macd.axhline(y=0, color="gray", linestyle="-", alpha=0.3)
        ax_macd.set_ylabel("MACD", fontsize=10)
        ax_macd.legend(loc="upper left", fontsize=8, ncol=3)
    ax_macd.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)
    ax_macd.tick_params(labelbottom=False)

    # ---- 子图4：ATR(14) ----
    ax_atr = fig.add_subplot(gs[3], sharex=ax_rsi)
    if "ATR_14" in df.columns:
        ax_atr.fill_between(dates, 0, df["ATR_14"], color=COLORS["atr"], alpha=0.3)
        ax_atr.plot(dates, df["ATR_14"], color=COLORS["atr"], linewidth=1.0, label="ATR(14)")
        ax_atr.set_ylabel("ATR", fontsize=10)
        ax_atr.legend(loc="upper left", fontsize=8)
    ax_atr.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)

    # X轴日期格式
    ax_atr.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax_atr.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax_atr.get_xticklabels(), rotation=45, ha="right", fontsize=8)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path)
        logger.info(f"技术指标图已保存: {save_path}")

    return fig


# ========== 四、库存变化图 ==========

def plot_inventory_chart(
    inventory_df: pd.DataFrame,
    title: str = "燃料油库存变化",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    绘制库存变化图（柱状图 + 变化量折线）

    子图布局：
        主图：库存量柱状图
        副图：周变化量柱状图（涨红跌绿）

    参数：
        inventory_df: 库存数据DataFrame，需包含 date, inventory, change 列
        title: 图表标题
        save_path: 保存路径

    返回：
        matplotlib Figure对象

    DataFrame预期列：
        date: 日期
        region: 区域（如"新加坡"/"舟山保税区"）
        inventory: 库存量
        unit: 单位
    """
    fig = plt.figure(figsize=(14, 7))
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1], hspace=0.12)
    ax_main = fig.add_subplot(gs[0])
    ax_change = fig.add_subplot(gs[1], sharex=ax_main)

    inventory_df = inventory_df.copy()
    if "date" in inventory_df.columns:
        inventory_df["date"] = pd.to_datetime(inventory_df["date"])
        inventory_df = inventory_df.sort_values("date").reset_index(drop=True)

    dates = inventory_df["date"]

    # ---- 主图：库存量 ----
    ax_main.bar(
        dates, inventory_df["inventory"],
        color=COLORS["inventory"], alpha=0.7, width=5, label="库存量"
    )

    # 添加趋势线
    if len(inventory_df) > 5:
        z = np.polyfit(range(len(inventory_df)), inventory_df["inventory"], 1)
        trend = np.poly1d(z)(range(len(inventory_df)))
        ax_main.plot(dates, trend, color="red", linewidth=1.5, linestyle="--", label="趋势线")

    ax_main.set_title(title, fontsize=14, fontweight="bold", pad=8)
    unit_str = inventory_df["unit"].iloc[0] if "unit" in inventory_df.columns else ""
    ax_main.set_ylabel(f"库存量 ({unit_str})", fontsize=10)
    ax_main.legend(loc="upper left", fontsize=9)
    ax_main.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)
    ax_main.tick_params(labelbottom=False)

    # ---- 副图：周变化量 ----
    if "change" in inventory_df.columns:
        changes = inventory_df["change"]
    else:
        changes = inventory_df["inventory"].diff()

    colors = [
        COLORS["inventory_change_pos"] if v >= 0 else COLORS["inventory_change_neg"]
        for v in changes.fillna(0)
    ]
    ax_change.bar(dates, changes.fillna(0), color=colors, alpha=0.7, width=5)
    ax_change.axhline(y=0, color="gray", linestyle="-", alpha=0.3)
    ax_change.set_ylabel("变化量", fontsize=10)
    ax_change.grid(True, color=COLORS["grid"], alpha=0.5, linewidth=0.5)

    # X轴日期格式
    ax_change.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax_change.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax_change.get_xticklabels(), rotation=45, ha="right", fontsize=8)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path)
        logger.info(f"库存变化图已保存: {save_path}")

    return fig


# ========== 五、综合仪表盘 ==========

def plot_dashboard(
    df: pd.DataFrame,
    lu_df: Optional[pd.DataFrame] = None,
    inventory_df: Optional[pd.DataFrame] = None,
    spread_data: Optional[dict] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    生成综合分析仪表盘（一张图包含所有关键信息）

    布局（2x2网格）：
        左上：价格走势 + MA + 布林带 + 成交量
        右上：RSI + CCI + MACD
        左下：价差分析
        右下：库存变化 / 综合信号评分

    参数：
        df: 含技术指标的K线DataFrame
        lu_df: LU数据（可选）
        inventory_df: 库存数据（可选）
        spread_data: 价差数据（可选）
        save_path: 保存路径

    返回：
        matplotlib Figure对象
    """
    df = prepare_dataframe(df)
    dates = df["date"]

    fig = plt.figure(figsize=(18, 12))
    fig.suptitle("燃料油综合分析仪表盘", fontsize=16, fontweight="bold", y=0.98)
    gs = gridspec.GridSpec(2, 2, hspace=0.25, wspace=0.2)

    # ---- 左上：价格走势 ----
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(dates, df["close"], color=COLORS["price"], linewidth=1.3, label="收盘价")
    for col, color, ls in [("MA5", COLORS["ma5"], "--"), ("MA20", COLORS["ma20"], "-")]:
        if col in df.columns:
            ax1.plot(dates, df[col], color=color, linewidth=0.8, linestyle=ls, label=col)
    if "BOLL_UP" in df.columns:
        ax1.fill_between(dates, df["BOLL_DN"], df["BOLL_UP"], alpha=0.1, color="blue", label="布林带")
    ax1.set_title("价格走势", fontsize=11, fontweight="bold")
    ax1.set_ylabel("价格", fontsize=9)
    ax1.legend(loc="upper left", fontsize=7, ncol=2)
    ax1.grid(True, color=COLORS["grid"], alpha=0.4, linewidth=0.5)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.setp(ax1.get_xticklabels(), rotation=30, ha="right", fontsize=7)

    # ---- 右上：RSI + MACD组合 ----
    ax2 = fig.add_subplot(gs[0, 1])
    if "RSI_14" in df.columns:
        ax2_rsi = ax2
        ax2_rsi.plot(dates, df["RSI_14"], color=COLORS["rsi"], linewidth=1.0, label="RSI(14)")
        ax2_rsi.axhline(y=70, color="red", linestyle="--", alpha=0.5, linewidth=0.7)
        ax2_rsi.axhline(y=30, color="green", linestyle="--", alpha=0.5, linewidth=0.7)
        ax2_rsi.set_ylim(0, 100)
        ax2_rsi.set_ylabel("RSI", fontsize=9)
        ax2_rsi.legend(loc="upper left", fontsize=7)
    ax2.set_title("RSI 指标", fontsize=11, fontweight="bold")
    ax2.grid(True, color=COLORS["grid"], alpha=0.4, linewidth=0.5)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.setp(ax2.get_xticklabels(), rotation=30, ha="right", fontsize=7)

    # ---- 左下：价差或MACD ----
    ax3 = fig.add_subplot(gs[1, 0])
    if lu_df is not None:
        lu_df = prepare_dataframe(lu_df)
        merged = pd.merge(
            df[["date", "close"]].rename(columns={"close": "fu"}),
            lu_df[["date", "close"]].rename(columns={"close": "lu"}),
            on="date", how="inner"
        )
        if not merged.empty:
            spread = merged["lu"] - merged["fu"]
            ax3.plot(merged["date"], spread, color=COLORS["spread_hl"], linewidth=1.2)
            ax3.axhline(y=400, color="gray", linestyle=":", alpha=0.5)
            ax3.fill_between(merged["date"], 300, 500, alpha=0.08, color="blue")
            ax3.set_ylabel("高低硫价差", fontsize=9)
    elif "MACD_HIST" in df.columns:
        hist = df["MACD_HIST"]
        colors = [COLORS["macd_pos"] if v >= 0 else COLORS["macd_neg"] for v in hist]
        ax3.bar(dates, hist, color=colors, alpha=0.6, width=0.8)
        ax3.plot(dates, df["MACD_DIF"], color=COLORS["macd_dif"], linewidth=0.8, label="DIF")
        ax3.plot(dates, df["MACD_DEA"], color=COLORS["macd_dea"], linewidth=0.8, label="DEA")
        ax3.axhline(y=0, color="gray", linestyle="-", alpha=0.3)
        ax3.set_ylabel("MACD", fontsize=9)
        ax3.legend(loc="upper left", fontsize=7)
    ax3.set_title("价差 / MACD", fontsize=11, fontweight="bold")
    ax3.grid(True, color=COLORS["grid"], alpha=0.4, linewidth=0.5)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.setp(ax3.get_xticklabels(), rotation=30, ha="right", fontsize=7)

    # ---- 右下：库存或成交量 ----
    ax4 = fig.add_subplot(gs[1, 1])
    if inventory_df is not None and not inventory_df.empty:
        inv = inventory_df.copy()
        if "date" in inv.columns:
            inv["date"] = pd.to_datetime(inv["date"])
            ax4.bar(inv["date"], inv["inventory"], color=COLORS["inventory"], alpha=0.7, width=5)
            ax4.set_ylabel("库存量", fontsize=9)
    elif "volume" in df.columns:
        vol_colors = [
            COLORS["volume_up"] if df["close"].iloc[i] >= df["open"].iloc[i]
            else COLORS["volume_down"]
            for i in range(len(df))
        ]
        ax4.bar(dates, df["volume"], color=vol_colors, alpha=0.6, width=0.8)
        ax4.set_ylabel("成交量", fontsize=9)
    ax4.set_title("库存 / 成交量", fontsize=11, fontweight="bold")
    ax4.grid(True, color=COLORS["grid"], alpha=0.4, linewidth=0.5)
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.setp(ax4.get_xticklabels(), rotation=30, ha="right", fontsize=7)

    # 底部标注
    fig.text(0.5, 0.01, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 数据仅供参考",
             ha="center", fontsize=8, color="gray")

    if save_path:
        fig.savefig(save_path)
        logger.info(f"综合仪表盘已保存: {save_path}")

    return fig


# ========== 六、生成演示库存数据 ==========

def generate_demo_inventory_data(weeks: int = 30) -> pd.DataFrame:
    """
    生成演示用库存数据

    参数：
        weeks: 数据周数

    返回：
        库存DataFrame
    """
    np.random.seed(123)
    dates = pd.date_range(end=datetime.now(), periods=weeks, freq="W")

    # 新加坡燃料油库存：2000~2500万桶区间波动
    base_sg = 2200
    sg_changes = np.random.normal(0, 40, weeks)
    sg_inventory = base_sg + np.cumsum(sg_changes)

    # 舟山保税库存：300~500万吨区间
    base_zs = 400
    zs_changes = np.random.normal(0, 15, weeks)
    zs_inventory = base_zs + np.cumsum(zs_changes)

    sg_df = pd.DataFrame({
        "date": dates,
        "region": "新加坡",
        "inventory": np.round(sg_inventory, 1),
        "change": np.round(np.concatenate([[0], np.diff(sg_inventory)]), 1),
        "unit": "万桶",
    })

    zs_df = pd.DataFrame({
        "date": dates,
        "region": "舟山保税区",
        "inventory": np.round(zs_inventory, 1),
        "change": np.round(np.concatenate([[0], np.diff(zs_inventory)]), 1),
        "unit": "万吨",
    })

    return pd.concat([sg_df, zs_df], ignore_index=True)


# ========== 七、主入口 ==========

def main():
    """主函数：解析参数 → 生成图表 → 保存文件"""
    parser = argparse.ArgumentParser(
        description="燃料油分析图表生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", "-i", type=str, help="输入含技术指标的CSV文件路径")
    parser.add_argument("--db", type=str, help="DuckDB数据库路径")
    parser.add_argument("--symbol", type=str, help="品种代码（配合--db使用）")
    parser.add_argument("--output", "-o", type=str, help="图表输出目录", default=str(OUTPUT_DIR))
    parser.add_argument("--demo", action="store_true", help="使用演示数据生成示例图表")
    parser.add_argument("--charts", nargs="+", default=["all"],
                        choices=["all", "price", "spread", "indicators", "inventory", "dashboard"],
                        help="要生成的图表类型")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    charts_to_gen = set(args.charts)
    gen_all = "all" in charts_to_gen

    if args.db and args.symbol:
        import duckdb
        logger.info(f"从DuckDB加载数据: {args.db} -> kline_{args.symbol.lower()}")
        conn = duckdb.connect(args.db, read_only=True)
        try:
            df = conn.execute(f"SELECT * FROM kline_{args.symbol.lower()} ORDER BY date").fetchdf()
        finally:
            conn.close()
        df = prepare_dataframe(df)
        if "RSI_14" not in df.columns:
            logger.info("数据缺少技术指标列，自动计算中...")
            from calculate_indicators import calculate_all_indicators
            df = calculate_all_indicators(df)
    elif args.input:
        logger.info(f"加载数据: {args.input}")
        df = pd.read_csv(args.input)
        df = prepare_dataframe(df)

        # 如果缺少指标列，尝试自动计算
        if "RSI_14" not in df.columns:
            logger.info("数据缺少技术指标列，自动计算中...")
            from calculate_indicators import calculate_all_indicators
            df = calculate_all_indicators(df)
    elif args.demo:
        logger.info("使用演示数据...")
        df = generate_demo_data(120)
    else:
        logger.info("未指定参数，自动使用演示数据...")
        df = generate_demo_data(120)

    logger.info(f"数据行数: {len(df)}, 列数: {len(df.columns)}")

    # 生成演示库存数据
    inventory_df = generate_demo_inventory_data()

    generated = []

    # 1. 价格走势图
    if gen_all or "price" in charts_to_gen:
        path = output_dir / f"price_trend_{timestamp}.png"
        plot_price_trend(df, save_path=str(path))
        generated.append(str(path))

    # 2. 价差图
    if gen_all or "spread" in charts_to_gen:
        path = output_dir / f"spreads_{timestamp}.png"
        plot_spread_chart(df, title="燃料油价差分析", save_path=str(path))
        generated.append(str(path))

    # 3. 技术指标图
    if gen_all or "indicators" in charts_to_gen:
        path = output_dir / f"indicators_{timestamp}.png"
        plot_technical_indicators(df, save_path=str(path))
        generated.append(str(path))

    # 4. 库存变化图
    if gen_all or "inventory" in charts_to_gen:
        for region in inventory_df["region"].unique():
            region_df = inventory_df[inventory_df["region"] == region]
            path = output_dir / f"inventory_{region}_{timestamp}.png"
            plot_inventory_chart(region_df, title=f"燃料油库存变化 - {region}", save_path=str(path))
            generated.append(str(path))

    # 5. 综合仪表盘
    if gen_all or "dashboard" in charts_to_gen:
        path = output_dir / f"dashboard_{timestamp}.png"
        plot_dashboard(df, inventory_df=inventory_df, save_path=str(path))
        generated.append(str(path))

    # 汇总输出
    logger.info("=" * 50)
    logger.info(f"图表生成完成，共 {len(generated)} 个文件")
    for f in generated:
        logger.info(f"  → {f}")
    logger.info("=" * 50)

    print(f"\n__CHARTS__:{';;'.join(generated)}")

    return generated


if __name__ == "__main__":
    main()
