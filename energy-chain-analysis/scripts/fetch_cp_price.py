#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LPG CP价格获取脚本 — 从财经网站获取沙特阿美CP合同价

功能：
    1. 从同花顺/东方财富搜索LPG CP价格
    2. 解析丙烷/丁烷合同价
    3. 保存到DuckDB
    4. 支持手动输入和自动获取

数据源：
    - 同花顺期货频道：https://futures.10jqka.com.cn/
    - 东方财富期货频道：https://futures.eastmoney.com/
    - 隆众资讯：https://www.chem99.com/

用法：
    python fetch_cp_price.py --auto                    # 自动获取最新CP价格
    python fetch_cp_price.py --propane 520 --butane 480  # 手动输入
    python fetch_cp_price.py --history                 # 查看历史CP价格
"""

import argparse
import json
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

DB_PATH = Path(__file__).parent.parent / "data" / "futures_data.duckdb"
CP_CACHE_PATH = Path(__file__).parent.parent / "data" / "cp_price_cache.json"

# 沙特阿美CP价格典型范围（美元/吨）
CP_RANGES = {
    "propane": {"min": 400, "max": 700, "typical": 520},
    "butane": {"min": 350, "max": 650, "typical": 480},
}


def fetch_cp_from_web() -> dict:
    """从财经网站获取最新CP价格（需要网络连接）"""
    # 尝试从多个数据源获取
    sources = [
        _fetch_from_tonghuashun,
        _fetch_from_eastmoney,
        _fetch_from_cache,
    ]

    for source_func in sources:
        try:
            result = source_func()
            if result and result.get("propane") and result.get("butane"):
                logger.info(f"✅ 从 {source_func.__name__} 获取CP价格")
                return result
        except Exception as e:
            logger.debug(f"{source_func.__name__} 失败: {e}")
            continue

    logger.warning("⚠️ 所有数据源获取失败，返回None")
    return None


def _fetch_from_tonghuashun() -> dict:
    """从同花顺获取CP价格（占位函数，需实际实现）"""
    # TODO: 实现同花顺数据抓取
    # 需要分析网页结构，提取CP价格数据
    return None


def _fetch_from_eastmoney() -> dict:
    """从东方财富获取CP价格（占位函数，需实际实现）"""
    # TODO: 实现东方财富数据抓取
    # 需要分析网页结构，提取CP价格数据
    return None


def _fetch_from_cache() -> dict:
    """从本地缓存获取CP价格"""
    if CP_CACHE_PATH.exists():
        try:
            with open(CP_CACHE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("propane") and data.get("butane"):
                    return data
        except Exception:
            pass
    return None


def save_cp_to_cache(propane: float, butane: float, date: str = None):
    """保存CP价格到本地缓存"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    data = {
        "propane": propane,
        "butane": butane,
        "date": date,
        "source": "manual",
        "updated_at": datetime.now().isoformat(),
    }

    CP_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CP_CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ CP价格已保存: 丙烷{propane} 丁烷{butane} ({date})")


def save_cp_to_duckdb(propane: float, butane: float, date: str = None):
    """保存CP价格到DuckDB"""
    try:
        import duckdb
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        conn = duckdb.connect(str(DB_PATH))
        # 创建表（如果不存在）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cp_prices (
                date DATE PRIMARY KEY,
                propane_usd FLOAT,
                butane_usd FLOAT,
                propane_rmb FLOAT,
                butane_rmb FLOAT,
                source VARCHAR,
                updated_at TIMESTAMP
            )
        """)

        # 获取汇率（默认7.2）
        usdcny = 7.2
        propane_rmb = propane * usdcny
        butane_rmb = butane * usdcny

        # 插入数据
        conn.execute("""
            INSERT OR REPLACE INTO cp_prices VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [date, propane, butane, propane_rmb, butane_rmb, "manual", datetime.now().isoformat()])

        conn.close()
        logger.info(f"✅ CP价格已保存到DuckDB: {date}")
    except Exception as e:
        logger.error(f"保存到DuckDB失败: {e}")


def validate_cp_price(propane: float, butane: float) -> bool:
    """验证CP价格是否在合理范围内"""
    p_range = CP_RANGES["propane"]
    b_range = CP_RANGES["butane"]

    if not (p_range["min"] <= propane <= p_range["max"]):
        logger.warning(f"丙烷价格{propane}超出合理范围({p_range['min']}-{p_range['max']})")
        return False

    if not (b_range["min"] <= butane <= b_range["max"]):
        logger.warning(f"丁烷价格{butane}超出合理范围({b_range['min']}-{b_range['max']})")
        return False

    return True


def get_latest_cp() -> dict:
    """获取最新CP价格（优先从缓存，其次从Web）"""
    # 先从缓存获取
    cached = _fetch_from_cache()
    if cached:
        return cached

    # 再从Web获取
    return fetch_cp_from_web()


def format_cp_report(propane: float, butane: float, date: str = None) -> str:
    """格式化CP价格报告"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    usdcny = 7.2
    propane_rmb = propane * usdcny
    butane_rmb = butane * usdcny

    lines = [
        "=" * 60,
        "  沙特阿美LPG CP价格",
        "=" * 60,
        f"  日期: {date}",
        "",
        "  ── 美元计价 ──",
        f"  丙烷CP: {propane:.0f} 美元/吨",
        f"  丁烷CP: {butane:.0f} 美元/吨",
        "",
        "  ── 人民币计价（汇率{usdcny}）──",
        f"  丙烷CP: {propane_rmb:.0f} 元/吨",
        f"  丁烷CP: {butane_rmb:.0f} 元/吨",
        "",
        "  ── 历史分位 ──",
        f"  丙烷: 典型范围{CP_RANGES['propane']['min']}-{CP_RANGES['propane']['max']}美元/吨",
        f"  丁烷: 典型范围{CP_RANGES['butane']['min']}-{CP_RANGES['butane']['max']}美元/吨",
        "=" * 60,
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="LPG CP价格获取")
    parser.add_argument("--auto", action="store_true", help="自动获取最新CP价格")
    parser.add_argument("--propane", type=float, help="丙烷CP价格（美元/吨）")
    parser.add_argument("--butane", type=float, help="丁烷CP价格（美元/吨）")
    parser.add_argument("--date", type=str, help="日期（YYYY-MM-DD）")
    parser.add_argument("--history", action="store_true", help="查看历史CP价格")
    args = parser.parse_args()

    if args.history:
        # 显示历史CP价格
        try:
            import duckdb
            conn = duckdb.connect(str(DB_PATH), read_only=True)
            df = conn.execute("SELECT * FROM cp_prices ORDER BY date DESC LIMIT 12").fetchdf()
            conn.close()
            if not df.empty:
                print("\n历史CP价格：")
                print(df.to_string(index=False))
            else:
                print("暂无历史数据")
        except Exception as e:
            logger.error(f"读取历史数据失败: {e}")
        return

    if args.propane and args.butane:
        # 手动输入模式
        propane = args.propane
        butane = args.butane

        if not validate_cp_price(propane, butane):
            logger.warning("价格超出典型范围，继续保存")

        save_cp_to_cache(propane, butane, args.date)
        save_cp_to_duckdb(propane, butane, args.date)
        print(format_cp_report(propane, butane, args.date))

    elif args.auto:
        # 自动获取模式
        result = get_latest_cp()
        if result:
            propane = result["propane"]
            butane = result["butane"]
            date = result.get("date", datetime.now().strftime("%Y-%m-%d"))
            print(format_cp_report(propane, butane, date))
        else:
            logger.error("自动获取失败，请手动输入：python fetch_cp_price.py --propane 520 --butane 480")

    else:
        # 默认显示最新价格
        result = get_latest_cp()
        if result:
            print(format_cp_report(result["propane"], result["butane"], result.get("date")))
        else:
            print("暂无CP价格数据，请使用 --propane 和 --butane 参数输入")


if __name__ == "__main__":
    main()
