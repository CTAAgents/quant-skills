"""
A股ETF双动量轮动策略 - 回测运行示例
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config import Config
from scripts.data_collector import ETFDataCollector
from scripts.strategy import DualMomentumStrategy
from scripts.backtest import BacktestEngine
from scripts.report import ReportGenerator


def main():
    """运行回测"""
    print("=" * 60)
    print("A股ETF双动量轮动策略 - 回测系统")
    print("=" * 60)

    # 1. 初始化配置
    config = Config()
    print(f"\n[配置] 动量窗口: {config.momentum_window}天")
    print(f"[配置] 初始资金: ¥{config.initial_capital:,.0f}")
    print(f"[配置] 回测区间: {config.backtest_start} 至 {config.backtest_end}")

    # 2. 获取数据
    print("\n[1/4] 正在获取ETF数据...")
    collector = ETFDataCollector(config)
    data = collector.collect_all()
    print(f"  成功获取 {len(data)} 只ETF数据")

    if len(data) < len(config.all_etf_codes):
        missing = set(config.all_etf_codes) - set(data.keys())
        print(f"  警告: 以下ETF数据缺失: {missing}")

    # 3. 初始化策略
    print("\n[2/4] 初始化策略...")
    strategy = DualMomentumStrategy(config)

    # 4. 运行回测
    print("\n[3/4] 运行回测...")
    engine = BacktestEngine(config, strategy, data)
    result = engine.run()

    # 5. 打印结果摘要
    print("\n[4/4] 回测完成!")
    report = ReportGenerator(result, config)
    report.print_summary()

    # 6. 生成HTML报告
    output_path = report.generate_html()
    print(f"\n[报告] HTML报告已生成: {output_path}")

    # 7. 显示最近调仓记录
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


if __name__ == "__main__":
    main()
