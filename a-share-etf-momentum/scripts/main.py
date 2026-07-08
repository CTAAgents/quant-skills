"""
A股ETF双动量轮动策略 - 主入口脚本
提供命令行接口，支持回测、信号生成、数据更新等操作
"""

import argparse
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config import Config
from scripts.data_collector import ETFDataCollector
from scripts.momentum import MomentumCalculator
from scripts.strategy import DualMomentumStrategy
from scripts.backtest import BacktestEngine
from scripts.report import ReportGenerator


def run_backtest(config: Config, output_dir: str = None):
    """运行回测"""
    print("=" * 60)
    print("A股ETF双动量轮动策略 - 回测系统")
    print("=" * 60)

    # 1. 初始化配置
    print(f"\n[配置] 数据源: {config.data_source}（主）, {config.backup_data_source}（备）")
    print(f"[配置] 动量窗口: {config.momentum_window}天（绝对）/ {config.relative_momentum_window}天（相对）")
    print(f"[配置] 初始资金: ¥{config.initial_capital:,.0f}")
    print(f"[配置] 回测区间: {config.backtest_start} 至 {config.backtest_end}")
    print(f"[配置] 估值刹车: {'启用' if config.valuation_enabled else '禁用'}")

    # 2. 获取数据
    print("\n[1/5] 正在获取ETF数据...")
    collector = ETFDataCollector(config)
    data = collector.collect_all()
    print(f"  成功获取 {len(data)} 只ETF数据")

    if len(data) < len(config.all_etf_codes):
        missing = set(config.all_etf_codes) - set(data.keys())
        print(f"  警告: 以下ETF数据缺失: {missing}")

    # 3. 初始化策略
    print("\n[2/5] 初始化策略...")
    strategy = DualMomentumStrategy(config)

    # 4. 获取估值数据（若启用）
    if config.valuation_enabled:
        print("\n[3/5] 获取估值分位数据...")
        calculator = MomentumCalculator(config)
        pe_data = calculator.fetch_all_valuation_data()
        print(f"  成功获取 {len(pe_data)} 只ETF的PE分位数据")
        strategy._pe_data_cache = pe_data
    else:
        print("\n[3/5] 跳过估值数据获取（已禁用）")

    # 5. 运行回测
    print("\n[4/5] 运行回测...")
    engine = BacktestEngine(config, strategy, data)
    result = engine.run()

    # 6. 打印结果摘要
    print("\n[5/5] 回测完成!")
    report = ReportGenerator(result, config)
    report.print_summary()

    # 7. 生成HTML报告
    if output_dir:
        config.output_dir = output_dir
    output_path = report.generate_html()
    print(f"\n[报告] HTML报告已生成: {output_path}")

    # 8. 显示最近调仓记录
    print("\n" + "=" * 60)
    print("最近5次调仓记录:")
    print("=" * 60)
    for record in strategy.rebalance_records[-5:]:
        print(f"日期: {record.date.strftime('%Y-%m-%d')}")
        print(f"  市场状态: {'多头' if record.is_bullish else '空头'}")
        print(f"  选中ETF: {record.selected_etf}")
        print(f"  决策理由: {record.reason}")
        print()

    return result


def generate_signal(config: Config):
    """生成当前调仓信号"""
    print("=" * 60)
    print("A股ETF双动量轮动策略 - 实时调仓信号")
    print("=" * 60)
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"数据源: {config.data_source}（主）, {config.backup_data_source}（备）")

    # 1. 初始化
    collector = ETFDataCollector(config)
    calculator = MomentumCalculator(config)
    strategy = DualMomentumStrategy(config)

    # 2. 获取最新数据
    print("\n[1/4] 正在获取最新数据...")
    data = collector.collect_all()
    print(f"  成功获取 {len(data)} 只ETF数据")

    # 3. 计算动量
    print("\n[2/4] 计算动量指标...")
    is_bullish, benchmark_return = calculator.calculate_absolute_momentum(data)
    momentum_results = calculator.calculate_relative_momentum(data)

    # 4. 获取估值数据
    if config.valuation_enabled:
        print("\n[3/4] 获取估值分位数据...")
        pe_data = calculator.fetch_all_valuation_data()
        momentum_results = calculator.apply_valuation_brake(momentum_results, pe_data)
    else:
        pe_data = None
        print("\n[3/4] 跳过估值数据获取（已禁用）")

    # 打印动量报告
    report = calculator.generate_momentum_report(momentum_results, is_bullish, benchmark_return)
    print(report)

    # 5. 生成调仓信号
    print("\n[4/4] 生成调仓建议...")
    signal = strategy.generate_signal(data, pe_data=pe_data)

    print("\n" + "=" * 60)
    print("📋 今日调仓建议")
    print("=" * 60)

    if signal.selected_etf:
        etf_config = config.get_etf_by_code(signal.selected_etf)
        print(f"  建议持有: {etf_config.name} ({signal.selected_etf})")
    else:
        print(f"  建议持有: {config.defensive.name} ({config.defensive.code})")

    print(f"  决策理由: {signal.reason}")

    # 交易信号
    print("\n📝 交易信号:")
    for trade in signal.trade_signals:
        print(f"  {trade.action.upper()}: {trade.name} ({trade.code})")
        print(f"    仓位: {trade.weight:.0%}")
        print(f"    原因: {trade.reason}")

    # 风险提示
    print("\n⚠️ 风险提示:")
    print("  1. 策略基于历史数据，不代表未来收益")
    print("  2. 请根据个人风险承受能力调整仓位")
    print("  3. 建议设置止损线，控制单笔亏损")

    return signal


def update_data(config: Config, force_refresh: bool = False):
    """更新ETF数据缓存"""
    print("=" * 60)
    print("A股ETF双动量轮动策略 - 数据更新")
    print("=" * 60)

    collector = ETFDataCollector(config)
    data = collector.collect_all(force_refresh=force_refresh)

    print(f"\n数据更新完成:")
    for code, df in data.items():
        etf = config.get_etf_by_code(code)
        print(f"  {etf.name} ({code}): {len(df)} 条记录, "
              f"最新日期 {df['date'].max().strftime('%Y-%m-%d')}")

    return data


def show_config(config: Config):
    """显示当前配置"""
    print("=" * 60)
    print("A股ETF双动量轮动策略 - 当前配置")
    print("=" * 60)

    print("\n【标的池】")
    print(f"  基准: {config.benchmark.name} ({config.benchmark.code})")
    print(f"  行业ETF:")
    for etf in config.industry_etfs:
        print(f"    - {etf.name} ({etf.code})")
    print(f"  防御资产: {config.defensive.name} ({config.defensive.code})")

    print("\n【动量参数】")
    print(f"  动量窗口: {config.momentum_window}天")
    print(f"  绝对动量阈值: {config.abs_momentum_threshold}")
    print(f"  选取数量: Top {config.top_n}")

    print("\n【估值刹车】")
    print(f"  启用状态: {'是' if config.valuation_enabled else '否'}")
    print(f"  PE分位阈值: {config.valuation_pe_threshold}%")
    print(f"  涨幅阈值: {config.valuation_return_threshold:.0%}")
    print(f"  回看年数: {config.valuation_lookback_years}年")

    print("\n【资金与成本】")
    print(f"  初始资金: ¥{config.initial_capital:,.0f}")
    print(f"  单边手续费: {config.commission_rate:.2%}")
    print(f"  滑点: {config.slippage_rate:.2%}")

    print("\n【数据源配置】")
    print(f"  主数据源: {config.data_source}（腾讯自选股）")
    print(f"  备用数据源: {config.backup_data_source}（通达信TQ-Local）")
    print(f"  通达信复权: {config.tdx_dividend_type}（前复权）")
    print(f"  WeStock复权: {config.westock_dividend_type}（前复权）")
    print(f"  缓存目录: {config.cache_dir}")

    print("\n【回测配置】")
    print(f"  回测区间: {config.backtest_start} 至 {config.backtest_end}")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="A股ETF双动量轮动策略",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m scripts.main backtest                    # 运行回测（默认westock数据源）
  python -m scripts.main signal                      # 生成实时信号
  python -m scripts.main update                      # 更新数据缓存
  python -m scripts.main config                      # 显示当前配置
  python -m scripts.main backtest --no-valuation     # 禁用估值刹车回测
  python -m scripts.main backtest --start 2020-01-01 # 指定回测起始日期
  python -m scripts.main backtest --source tdx       # 使用通达信数据源回测
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # backtest 子命令
    bt_parser = subparsers.add_parser("backtest", help="运行回测")
    bt_parser.add_argument("--start", help="回测起始日期 (YYYY-MM-DD)")
    bt_parser.add_argument("--end", help="回测结束日期 (YYYY-MM-DD)")
    bt_parser.add_argument("--capital", type=float, help="初始资金")
    bt_parser.add_argument("--no-valuation", action="store_true", help="禁用估值刹车")
    bt_parser.add_argument("--output", help="输出目录")
    bt_parser.add_argument("--source", choices=["westock", "tdx", "akshare"],
                          help="指定数据源（覆盖默认配置）")

    # signal 子命令
    sig_parser = subparsers.add_parser("signal", help="生成实时调仓信号")
    sig_parser.add_argument("--no-valuation", action="store_true", help="禁用估值刹车")
    sig_parser.add_argument("--source", choices=["westock", "tdx", "akshare"],
                          help="指定数据源（覆盖默认配置）")

    # update 子命令
    upd_parser = subparsers.add_parser("update", help="更新ETF数据缓存")
    upd_parser.add_argument("--force", action="store_true", help="强制刷新缓存")
    upd_parser.add_argument("--source", choices=["westock", "tdx", "akshare"],
                          help="指定数据源（覆盖默认配置）")

    # config 子命令
    subparsers.add_parser("config", help="显示当前配置")

    args = parser.parse_args()

    # 创建配置
    config = Config()

    if args.command == "backtest":
        if args.start:
            config.backtest_start = args.start
        if args.end:
            config.backtest_end = args.end
        if args.capital:
            config.initial_capital = args.capital
        if args.no_valuation:
            config.valuation_enabled = False
        if args.source:
            config.data_source = args.source
        run_backtest(config, args.output)

    elif args.command == "signal":
        if args.no_valuation:
            config.valuation_enabled = False
        if args.source:
            config.data_source = args.source
        generate_signal(config)

    elif args.command == "update":
        if args.source:
            config.data_source = args.source
        update_data(config, args.force)

    elif args.command == "config":
        show_config(config)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
