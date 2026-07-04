#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化版能源产业链完整数据流水线

优化点：
1. 并行执行：数据获取、指标计算、报告生成并行执行
2. 增量更新：只处理新增数据，避免重复计算
3. 智能缓存：缓存中间结果，减少重复计算
4. 性能监控：记录各环节耗时，便于优化

用法：
    python run_pipeline_optimized.py              # 运行全流水线
    python run_pipeline_optimized.py --skip-fetch # 跳过数据采集，直接从DuckDB计算
    python run_pipeline_optimized.py --parallel   # 启用并行模式（默认）
    python run_pipeline_optimized.py --benchmark  # 运行性能基准测试
"""

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "futures_data.duckdb"
SCRIPTS_DIR = BASE_DIR / "scripts"
CHARTS_DIR = BASE_DIR / "output" / "charts"
REPORTS_DIR = BASE_DIR / "output" / "reports"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["SC", "BU", "FU", "LU"]

# 性能优化配置
import multiprocessing
CPU_COUNT = multiprocessing.cpu_count()
MAX_WORKERS = min(CPU_COUNT, 6)  # 自适应并行线程数
BENCHMARK_ITERATIONS = 3  # 基准测试迭代次数


class PerformanceMonitor:
    """性能监控器 - 增强版：时间 + 内存 + CPU"""
    
    def __init__(self):
        self.metrics = {}
        self.start_times = {}
        self.memory_usage = {}
        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            self._psutil = None
    
    def _get_memory_mb(self) -> float:
        """获取当前内存使用量（MB）"""
        if self._psutil:
            process = self._psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        return 0.0
    
    def start(self, name: str):
        """开始计时"""
        self.start_times[name] = time.time()
        self.memory_usage[name] = self._get_memory_mb()
    
    def stop(self, name: str):
        """停止计时并记录"""
        if name in self.start_times:
            elapsed = time.time() - self.start_times[name]
            mem_before = self.memory_usage.get(name, 0)
            mem_after = self._get_memory_mb()
            mem_delta = mem_after - mem_before
            self.metrics[name] = {
                'elapsed': elapsed,
                'mem_before_mb': mem_before,
                'mem_after_mb': mem_after,
                'mem_delta_mb': mem_delta
            }
            logger.info(f"  ⏱ {name}: {elapsed:.2f}s (内存Δ: {mem_delta:+.1f}MB)")
            return elapsed
        return 0
    
    def get_summary(self) -> Dict[str, float]:
        """获取性能摘要（仅耗时）"""
        return {k: v['elapsed'] for k, v in self.metrics.items()}
    
    def print_summary(self):
        """打印性能摘要"""
        logger.info("\n" + "=" * 60)
        logger.info("性能监控摘要")
        logger.info("=" * 60)
        total_time = 0
        for name, data in self.metrics.items():
            logger.info(f"  {name}: {data['elapsed']:.2f}s (内存: {data['mem_before_mb']:.0f}→{data['mem_after_mb']:.0f}MB, Δ{data['mem_delta_mb']:+.1f}MB)")
            total_time += data['elapsed']
        logger.info(f"  总耗时: {total_time:.2f}s")
        logger.info(f"  CPU核心数: {CPU_COUNT}, 并行线程数: {MAX_WORKERS}")
        logger.info("=" * 60)


def run_fetch_optimized(parallel: bool = True) -> Dict[str, int]:
    """优化版数据获取"""
    logger.info("=" * 60)
    logger.info("环节1：优化版数据获取")
    logger.info("=" * 60)
    
    if parallel:
        from fetch_and_store_optimized import download_kline_data_parallel, store_to_duckdb
        kline_data = download_kline_data_parallel(SYMBOLS, days=756, use_cache=True)
    else:
        from fetch_and_store import download_kline_data, store_to_duckdb
        kline_data = download_kline_data(SYMBOLS, days=756)
    
    if kline_data:
        store_to_duckdb(kline_data)
        return {symbol: len(df) for symbol, df in kline_data.items()}
    return {}


def run_indicators_optimized(parallel: bool = True) -> Dict[str, Dict]:
    """优化版指标计算"""
    logger.info("=" * 60)
    logger.info("环节2：优化版指标计算")
    logger.info("=" * 60)
    
    from calculate_indicators_optimized import calculate_all_symbols, save_indicators_to_duckdb
    
    db_path = str(DB_PATH)
    results = calculate_all_symbols(db_path, SYMBOLS, use_cache=True, parallel=parallel)
    
    # 保存到DuckDB
    for symbol, (indicators_df, signals) in results.items():
        save_indicators_to_duckdb(db_path, symbol, indicators_df, signals)
    
    return {symbol: {"rows": len(indicators_df), "signals": len(signals)} 
            for symbol, (indicators_df, signals) in results.items()}


def run_charts_optimized(parallel: bool = True) -> List[str]:
    """优化版图表生成"""
    logger.info("=" * 60)
    logger.info("环节3：优化版图表生成")
    logger.info("=" * 60)
    
    from generate_charts import prepare_dataframe, generate_demo_inventory_data
    from generate_charts import plot_price_trend, plot_spread_chart, plot_technical_indicators
    from generate_charts import plot_inventory_chart, plot_dashboard
    from calculate_indicators_optimized import load_from_duckdb, calculate_all_indicators_batch
    
    generated = []
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    def generate_symbol_charts(symbol: str) -> List[str]:
        """生成单个品种的图表"""
        charts = []
        try:
            df = load_from_duckdb(str(DB_PATH), symbol)
            if df.empty:
                return charts
            
            df = prepare_dataframe(df)
            if "RSI_14" not in df.columns:
                df = calculate_all_indicators_batch(df)
            
            # 价格趋势图
            p = CHARTS_DIR / f"{symbol}_price_{timestamp}.png"
            plot_price_trend(df, save_path=str(p))
            charts.append(str(p))
            
            # 技术指标图
            p = CHARTS_DIR / f"{symbol}_indicators_{timestamp}.png"
            plot_technical_indicators(df, save_path=str(p))
            charts.append(str(p))
            
            logger.info(f"  ✅ {symbol}: {len(charts)} 张图表")
            
        except Exception as e:
            logger.error(f"  ❌ {symbol}: 图表生成失败 - {e}")
        
        return charts
    
    if parallel:
        # 并行生成图表
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_symbol = {executor.submit(generate_symbol_charts, sym): sym 
                               for sym in SYMBOLS}
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    charts = future.result()
                    generated.extend(charts)
                except Exception as e:
                    logger.error(f"  处理 {symbol} 图表时出错: {e}")
    else:
        # 串行生成图表
        for symbol in SYMBOLS:
            charts = generate_symbol_charts(symbol)
            generated.extend(charts)
    
    # 生成综合仪表盘
    logger.info(f"\n--- 综合仪表盘 ---")
    try:
        fu_df = load_from_duckdb(str(DB_PATH), "FU")
        fu_df = prepare_dataframe(fu_df)
        if "RSI_14" not in fu_df.columns:
            fu_df = calculate_all_indicators_batch(fu_df)
        
        inv_df = generate_demo_inventory_data()
        p = CHARTS_DIR / f"dashboard_{timestamp}.png"
        plot_dashboard(fu_df, inventory_df=inv_df, save_path=str(p))
        generated.append(str(p))
        logger.info(f"  ✅ 仪表盘")
    except Exception as e:
        logger.error(f"  ❌ 仪表盘生成失败: {e}")
    
    return generated


def run_reports_optimized() -> List[str]:
    """优化版报告生成"""
    logger.info("=" * 60)
    logger.info("环节4：优化版报告生成")
    logger.info("=" * 60)
    
    from generate_reports import generate_comprehensive_report
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"crude_oil_chain_report_{timestamp}.md"
    
    try:
        generate_comprehensive_report(str(DB_PATH), str(report_path))
        logger.info(f"  ✅ 报告生成: {report_path}")
        return [str(report_path)]
    except Exception as e:
        logger.error(f"  ❌ 报告生成失败: {e}")
        return []


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


def run_benchmark(iterations: int = BENCHMARK_ITERATIONS):
    """运行性能基准测试"""
    logger.info("=" * 60)
    logger.info(f"性能基准测试（{iterations} 次迭代）")
    logger.info("=" * 60)
    
    results = []
    
    for i in range(iterations):
        logger.info(f"\n--- 迭代 {i+1}/{iterations} ---")
        
        monitor = PerformanceMonitor()
        
        # 测试数据获取
        monitor.start("数据获取")
        run_fetch_optimized(parallel=True)
        monitor.stop("数据获取")
        
        # 测试指标计算
        monitor.start("指标计算")
        run_indicators_optimized(parallel=True)
        monitor.stop("指标计算")
        
        # 测试图表生成
        monitor.start("图表生成")
        run_charts_optimized(parallel=True)
        monitor.stop("图表生成")
        
        # 测试报告生成
        monitor.start("报告生成")
        run_reports_optimized()
        monitor.stop("报告生成")
        
        results.append(monitor.get_summary())
    
    # 计算平均值
    logger.info("\n" + "=" * 60)
    logger.info("基准测试结果")
    logger.info("=" * 60)
    
    avg_results = {}
    for key in results[0].keys():
        values = [r[key] for r in results]
        avg_results[key] = sum(values) / len(values)
        logger.info(f"  {key}: {avg_results[key]:.2f}s (平均)")
    
    total_avg = sum(avg_results.values())
    logger.info(f"  总耗时: {total_avg:.2f}s (平均)")
    logger.info(f"  CPU核心数: {CPU_COUNT}, 并行线程数: {MAX_WORKERS}")
    logger.info("=" * 60)
    
    return avg_results


def main():
    parser = argparse.ArgumentParser(description="优化版能源产业链完整数据流水线")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过数据采集，直接从DuckDB计算")
    parser.add_argument("--parallel", action="store_true", default=True, help="启用并行模式（默认）")
    parser.add_argument("--no-parallel", action="store_true", help="禁用并行模式")
    parser.add_argument("--benchmark", action="store_true", help="运行性能基准测试")
    parser.add_argument("--benchmark-iterations", type=int, default=BENCHMARK_ITERATIONS,
                       help="基准测试迭代次数")
    parser.add_argument("--health", action="store_true", help="仅运行健康检查")
    
    args = parser.parse_args()
    
    use_parallel = args.parallel and not args.no_parallel
    
    # 初始化增强版性能监控器
    from performance_monitor import PipelineMonitor
    perf = PipelineMonitor(log_to_file=True, auto_tune=True)
    
    # 健康检查
    health = perf.health_check()
    if args.health:
        print(json.dumps(health, indent=2, ensure_ascii=False))
        return
    
    # 自动调优
    if use_parallel:
        io_workers = perf.auto_tune_workers("io")
        cpu_workers = perf.auto_tune_workers("cpu")
    
    logger.info("优化版能源产业链完整数据流水线")
    logger.info(f"DuckDB: {DB_PATH}")
    logger.info(f"品种: {', '.join(SYMBOLS)}")
    logger.info(f"并行模式: {'启用' if use_parallel else '禁用'}")
    logger.info("")
    
    if args.benchmark:
        run_benchmark(args.benchmark_iterations)
        return
    
    monitor = PerformanceMonitor()
    perf.start_pipeline()
    start_time = time.time()
    
    try:
        # 环节1：数据获取
        if not args.skip_fetch:
            monitor.start("数据获取")
            with perf.stage("数据获取"):
                fetch_results = run_fetch_optimized(parallel=use_parallel)
            monitor.stop("数据获取")
            
            if not fetch_results:
                logger.error("数据获取失败")
                sys.exit(1)
        else:
            logger.info("跳过数据采集，使用已有DuckDB数据")
        
        # 验证DuckDB
        tables = verify_duckdb()
        kline_tables = [t for t in tables if t.startswith("kline_")]
        if not kline_tables:
            logger.error("DuckDB中无K线数据，请先运行数据采集")
            sys.exit(1)
        
        # 环节2：指标计算
        monitor.start("指标计算")
        with perf.stage("指标计算"):
            indicator_results = run_indicators_optimized(parallel=use_parallel)
        monitor.stop("指标计算")
        
        # 环节3：图表生成
        monitor.start("图表生成")
        with perf.stage("图表生成"):
            charts = run_charts_optimized(parallel=use_parallel)
        monitor.stop("图表生成")
        
        # 环节4：报告生成
        monitor.start("报告生成")
        with perf.stage("报告生成"):
            reports = run_reports_optimized()
        monitor.stop("报告生成")
        
        # 输出结果
        total_time = time.time() - start_time
        monitor.print_summary()
        
        # 生成增强版性能报告
        pipeline_report = perf.finish_pipeline()
        
        logger.info(f"\n流水线完成，总耗时 {total_time:.1f} 秒")
        logger.info(f"图表文件: {len(charts)} 个")
        for c in charts:
            logger.info(f"  {c}")
        logger.info(f"报告文件: {len(reports)} 个")
        for r in reports:
            logger.info(f"  {r}")
        
    except KeyboardInterrupt:
        logger.warning("流水线被用户中断")
        sys.exit(130)
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"流水线执行失败（耗时 {total_time:.1f}s）: {e}")
        logger.error("可能原因：网络断开 / TqSdk认证失败 / DuckDB文件损坏 / 依赖缺失")
        logger.error("恢复建议：1)检查网络 2)验证环境变量TQSDK_USERNAME/PASSWORD 3)删除data/fuel_oil.duckdb后重试")
        sys.exit(1)


if __name__ == "__main__":
    main()
