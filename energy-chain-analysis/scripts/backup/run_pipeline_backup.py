#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
能源产业链完整数据流水线（两层产业链：上游原油+下游并列产品）
TqSdk → DuckDB → Ta-Lib → 图表 → 报告

用法：
    python run_pipeline.py              # 运行全流水线
    python run_pipeline.py --skip-fetch # 跳过数据采集，直接从DuckDB计算
"""

import argparse
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "crude_oil_chain.duckdb"
SCRIPTS_DIR = BASE_DIR / "scripts"
CHARTS_DIR = BASE_DIR / "output" / "charts"
REPORTS_DIR = BASE_DIR / "output" / "reports"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["SC", "BU", "FU", "LU"]


def run_fetch():
    """环节1：TqSdk → DuckDB"""
    logger.info("=" * 60)
    logger.info("环节1：TqSdk → DuckDB")
    logger.info("=" * 60)
    from fetch_and_store import download_kline_data, store_to_duckdb
    kline_data = download_kline_data(SYMBOLS, days=120)
    if kline_data:
        store_to_duckdb(kline_data)
    return len(kline_data)


def run_indicators():
    """环节2：DuckDB → Ta-Lib → DuckDB"""
    logger.info("=" * 60)
    logger.info("环节2：DuckDB → Ta-Lib → DuckDB")
    logger.info("=" * 60)
    from calculate_indicators import load_from_duckdb, calculate_all_indicators, generate_comprehensive_signal, save_indicators_to_duckdb

    results = {}
    for sym in SYMBOLS:
        logger.info(f"\n--- {sym} 技术指标计算 ---")
        df = load_from_duckdb(str(DB_PATH), sym)
        if df.empty:
            logger.warning(f"  ⚠ {sym}: 无数据，跳过")
            continue
        result = calculate_all_indicators(df)
        signals = generate_comprehensive_signal(result)
        save_indicators_to_duckdb(str(DB_PATH), sym, result, signals)
        results[sym] = {"rows": len(result), "signals": len(signals)}
    return results


def run_charts():
    """环节3：DuckDB → 图表"""
    logger.info("=" * 60)
    logger.info("环节3：DuckDB → 图表")
    logger.info("=" * 60)
    from generate_charts import prepare_dataframe, generate_demo_inventory_data
    from generate_charts import plot_price_trend, plot_spread_chart, plot_technical_indicators
    from generate_charts import plot_inventory_chart, plot_dashboard
    from calculate_indicators import load_from_duckdb, calculate_all_indicators
    import duckdb

    generated = []
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    for sym in SYMBOLS:
        logger.info(f"\n--- {sym} 图表生成 ---")
        df = load_from_duckdb(str(DB_PATH), sym)
        if df.empty:
            continue
        df = prepare_dataframe(df)
        if "RSI_14" not in df.columns:
            df = calculate_all_indicators(df)

        charts = []
        p = CHARTS_DIR / f"{sym}_price_{timestamp}.png"
        plot_price_trend(df, save_path=str(p)); charts.append(str(p))
        p = CHARTS_DIR / f"{sym}_indicators_{timestamp}.png"
        plot_technical_indicators(df, save_path=str(p)); charts.append(str(p))
        generated.extend(charts)
        logger.info(f"  ✅ {sym}: {len(charts)} 张图表")

    logger.info(f"\n--- 综合仪表盘 ---")
    fu_df = load_from_duckdb(str(DB_PATH), "FU")
    fu_df = prepare_dataframe(fu_df)
    if "RSI_14" not in fu_df.columns:
        fu_df = calculate_all_indicators(fu_df)
    inv_df = generate_demo_inventory_data()
    p = CHARTS_DIR / f"dashboard_{timestamp}.png"
    plot_dashboard(fu_df, inventory_df=inv_df, save_path=str(p))
    generated.append(str(p))
    logger.info(f"  ✅ 仪表盘")

    return generated


def verify_duckdb():
    """验证DuckDB中的所有表"""
    import duckdb
    logger.info("=" * 60)
    logger.info("DuckDB 验证")
    logger.info("=" * 60)
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        logger.info(f"数据库: {DB_PATH}")
        logger.info(f"表数量: {len(tables)}")
        for t in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
            cols = conn.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{t[0]}'").fetchall()
            col_count = len(cols)
            logger.info(f"  {t[0]:20s}  {count:>5} 行  {col_count:>3} 列")
    finally:
        conn.close()
    return [t[0] for t in tables]


def run_reports():
    """环节4：DuckDB → 分析报告"""
    logger.info("=" * 60)
    logger.info("环节4：DuckDB → 分析报告")
    logger.info("=" * 60)
    from generate_reports import generate_comprehensive_report
    import duckdb
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"crude_oil_chain_report_{timestamp}.md"
    
    generate_comprehensive_report(str(DB_PATH), str(report_path))
    logger.info(f"  ✅ 报告生成: {report_path}")
    return [str(report_path)]


def main():
    parser = argparse.ArgumentParser(description="能源产业链完整数据流水线（两层产业链：上游原油+下游并列产品）")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过数据采集，直接从DuckDB计算")
    args = parser.parse_args()

    logger.info("能源产业链完整数据流水线（两层产业链：上游原油+下游并列产品）：TqSdk → DuckDB → Ta-Lib → 图表 → 报告")
    logger.info(f"DuckDB: {DB_PATH}")
    logger.info(f"品种: {', '.join(SYMBOLS)}")
    logger.info("")

    start = time.time()

    try:
        if not args.skip_fetch:
            run_fetch()
        else:
            logger.info("跳过数据采集，使用已有DuckDB数据")

        tables = verify_duckdb()

        kline_tables = [t for t in tables if t.startswith("kline_")]
        if not kline_tables:
            logger.error("DuckDB中无K线数据，请先运行数据采集: python fetch_and_store.py")
            sys.exit(1)

        run_indicators()
        verify_duckdb()

        charts = run_charts()
        reports = run_reports()

        elapsed = time.time() - start
        logger.info("=" * 60)
        logger.info(f"流水线完成，耗时 {elapsed:.1f} 秒")
        logger.info(f"图表文件: {len(charts)} 个")
        for c in charts:
            logger.info(f"  {c}")
        logger.info(f"报告文件: {len(reports)} 个")
        for r in reports:
            logger.info(f"  {r}")
        logger.info("=" * 60)
    except KeyboardInterrupt:
        logger.warning("流水线被用户中断")
        sys.exit(130)
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"流水线执行失败（耗时 {elapsed:.1f}s）: {e}")
        logger.error("可能原因：网络断开 / TqSdk认证失败 / DuckDB文件损坏 / 依赖缺失")
        logger.error("恢复建议：1)检查网络 2)验证环境变量TQSDK_USERNAME/PASSWORD 3)删除data/fuel_oil.duckdb后重试")
        sys.exit(1)


if __name__ == "__main__":
    main()
