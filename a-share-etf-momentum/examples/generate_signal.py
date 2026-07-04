"""
A股ETF双动量轮动策略 - 实时调仓信号生成
"""

import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config import Config
from scripts.data_collector import ETFDataCollector
from scripts.momentum import MomentumCalculator
from scripts.strategy import DualMomentumStrategy


def main():
    """生成当前调仓信号"""
    print("=" * 60)
    print("A股ETF双动量轮动策略 - 实时调仓信号")
    print("=" * 60)
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 初始化
    config = Config()
    collector = ETFDataCollector(config)
    calculator = MomentumCalculator(config)
    strategy = DualMomentumStrategy(config)

    # 2. 获取最新数据
    print("\n[1/3] 正在获取最新数据...")
    data = collector.collect_all()
    print(f"  成功获取 {len(data)} 只ETF数据")

    # 3. 计算动量
    print("\n[2/3] 计算动量指标...")
    is_bullish, benchmark_return = calculator.calculate_absolute_momentum(data)
    momentum_results = calculator.calculate_relative_momentum(data)

    # 打印动量报告
    report = calculator.generate_momentum_report(momentum_results, is_bullish, benchmark_return)
    print(report)

    # 4. 生成调仓信号
    print("\n[3/3] 生成调仓建议...")
    signal = strategy.generate_signal(data)

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


if __name__ == "__main__":
    main()
