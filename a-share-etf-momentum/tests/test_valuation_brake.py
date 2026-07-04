"""
测试估值刹车功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.config import Config
from scripts.data_collector import ETFDataCollector
from scripts.momentum import MomentumCalculator
from scripts.strategy import DualMomentumStrategy


def main():
    """测试估值刹车功能"""
    print("=" * 60)
    print("估值刹车功能测试")
    print("=" * 60)

    # 配置
    config = Config()
    config.valuation_enabled = True

    print(f"\n[配置]")
    print(f"  动量窗口: {config.momentum_window}天")
    print(f"  估值刹车: {'启用' if config.valuation_enabled else '禁用'}")
    print(f"  PE分位阈值: {config.valuation_pe_threshold}%")
    print(f"  涨幅阈值: {config.valuation_return_threshold:.0%}")

    # 加载数据
    print("\n[1/4] 加载ETF数据...")
    collector = ETFDataCollector(config)
    data = {}
    for code in config.all_etf_codes:
        df = collector.load_from_cache(code)
        if df is not None and not df.empty:
            data[code] = df

    # 计算动量
    print("\n[2/4] 计算动量指标...")
    calculator = MomentumCalculator(config)
    is_bullish, benchmark_return = calculator.calculate_absolute_momentum(data)
    momentum_results = calculator.calculate_relative_momentum(data)

    # 获取估值数据
    print("\n[3/4] 获取估值分位数据...")
    pe_data = calculator.fetch_all_valuation_data()
    print(f"  成功获取 {len(pe_data)} 只ETF的PE分位数据")

    # 应用估值刹车
    print("\n[4/4] 应用估值刹车...")
    momentum_results = calculator.apply_valuation_brake(momentum_results, pe_data)

    # 打印动量报告
    report = calculator.generate_momentum_report(momentum_results, is_bullish, benchmark_return)
    print(report)

    # 生成调仓信号
    print("\n" + "=" * 60)
    print("调仓建议（含估值刹车）")
    print("=" * 60)

    strategy = DualMomentumStrategy(config)
    strategy._pe_data_cache = pe_data
    signal = strategy.generate_signal(data, pe_data=pe_data)

    if signal.selected_etf:
        etf_config = config.get_etf_by_code(signal.selected_etf)
        print(f"  建议持有: {etf_config.name} ({signal.selected_etf})")
    else:
        print(f"  建议持有: {config.defensive.name} ({config.defensive.code})")

    print(f"  决策理由: {signal.reason}")

    return signal


if __name__ == "__main__":
    main()
