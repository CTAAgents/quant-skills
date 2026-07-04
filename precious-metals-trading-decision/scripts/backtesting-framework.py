"""
贵金属交易决策辅助系统 - 回测框架模块
建立完整的回测框架，验证策略的历史表现
"""

import json
import numpy as np
from datetime import datetime, timedelta

class BacktestingFramework:
    def __init__(self, initial_capital=300000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.risk_metrics = {}

    def reset(self):
        """重置回测状态"""
        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.risk_metrics = {}

    def execute_trade(self, strategy, direction, entry_price, stop_loss, take_profit, position_size):
        """执行交易"""
        trade = {
            "id": len(self.trades) + 1,
            "strategy": strategy,
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_size": position_size,
            "entry_time": datetime.now(),
            "exit_time": None,
            "exit_price": None,
            "pnl": None,
            "status": "open"
        }

        self.trades.append(trade)
        self.positions[trade["id"]] = trade

        return trade

    def close_trade(self, trade_id, exit_price, exit_time=None):
        """平仓"""
        if trade_id not in self.positions:
            return None

        trade = self.positions[trade_id]
        trade["exit_price"] = exit_price
        trade["exit_time"] = exit_time or datetime.now()

        # 计算盈亏
        if trade["direction"] == "long":
            trade["pnl"] = (exit_price - trade["entry_price"]) * trade["position_size"]
        else:
            trade["pnl"] = (trade["entry_price"] - exit_price) * trade["position_size"]

        trade["status"] = "closed"

        # 更新资金
        self.capital += trade["pnl"]

        # 从持仓中移除
        del self.positions[trade_id]

        return trade

    def calculate_metrics(self):
        """计算回测指标"""
        if not self.trades:
            return {}

        closed_trades = [t for t in self.trades if t["status"] == "closed"]
        if not closed_trades:
            return {}

        # 计算收益
        returns = [t["pnl"] for t in closed_trades]
        total_return = sum(returns)
        avg_return = np.mean(returns)
        std_return = np.std(returns)

        # 计算胜率
        winning_trades = [r for r in returns if r > 0]
        win_rate = len(winning_trades) / len(returns) if returns else 0

        # 计算盈亏比
        avg_win = np.mean(winning_trades) if winning_trades else 0
        losing_trades = [r for r in returns if r < 0]
        avg_loss = abs(np.mean(losing_trades)) if losing_trades else 0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # 计算最大回撤
        equity_curve = np.cumsum(returns)
        max_drawdown = self._calculate_max_drawdown(equity_curve)

        # 计算夏普比率
        risk_free_rate = 0.02 / 252  # 日化无风险利率
        sharpe_ratio = (avg_return - risk_free_rate) / std_return if std_return > 0 else 0

        # 计算索提诺比率
        downside_returns = [r for r in returns if r < 0]
        downside_std = np.std(downside_returns) if downside_returns else 0
        sortino_ratio = (avg_return - risk_free_rate) / downside_std if downside_std > 0 else 0

        # 计算卡尔玛比率
        calmar_ratio = (avg_return * 252) / max_drawdown if max_drawdown > 0 else 0

        self.risk_metrics = {
            "total_return": total_return,
            "avg_return": avg_return,
            "std_return": std_return,
            "win_rate": win_rate,
            "profit_loss_ratio": profit_loss_ratio,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "total_trades": len(closed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades)
        }

        return self.risk_metrics

    def _calculate_max_drawdown(self, equity_curve):
        """计算最大回撤"""
        if len(equity_curve) == 0:
            return 0

        peak = equity_curve[0]
        max_dd = 0

        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def generate_report(self):
        """生成回测报告"""
        metrics = self.calculate_metrics()

        report = {
            "summary": {
                "initial_capital": self.initial_capital,
                "final_capital": self.capital,
                "total_return": metrics.get("total_return", 0),
                "total_return_pct": (metrics.get("total_return", 0) / self.initial_capital) * 100,
                "annualized_return": metrics.get("avg_return", 0) * 252,
                "annualized_return_pct": metrics.get("avg_return", 0) * 252 * 100
            },
            "risk_metrics": metrics,
            "trades": self.trades
        }

        return report

def simulate_backtest():
    """模拟回测"""
    print("\n" + "="*80)
    print("回测框架测试")
    print("="*80)

    bt = BacktestingFramework(initial_capital=300000)

    # 模拟100笔交易
    print("\n1. 模拟100笔交易...")
    np.random.seed(42)

    strategies = ["宏观利率波段", "均线顺势", "突破追单", "区间高抛低吸", "金银比均值回归"]

    for i in range(100):
        strategy = strategies[i % len(strategies)]
        direction = "long" if np.random.random() > 0.4 else "short"

        # 模拟价格
        entry_price = 3300 + np.random.normal(0, 50)
        stop_loss = entry_price - 20 if direction == "long" else entry_price + 20
        take_profit = entry_price + 40 if direction == "long" else entry_price - 40
        position_size = 0.5  # 0.5手

        # 执行交易
        trade = bt.execute_trade(strategy, direction, entry_price, stop_loss, take_profit, position_size)

        # 模拟平仓（随机盈亏）
        exit_price = entry_price + np.random.normal(10, 30)
        bt.close_trade(trade["id"], exit_price)

    # 计算指标
    print("\n2. 计算回测指标...")
    metrics = bt.calculate_metrics()

    print(f"  总收益: {metrics['total_return']:.2f}")
    print(f"  胜率: {metrics['win_rate']:.2%}")
    print(f"  盈亏比: {metrics['profit_loss_ratio']:.2f}")
    print(f"  最大回撤: {metrics['max_drawdown']:.2%}")
    print(f"  夏普比率: {metrics['sharpe_ratio']:.3f}")
    print(f"  索提诺比率: {metrics['sortino_ratio']:.3f}")
    print(f"  卡尔玛比率: {metrics['calmar_ratio']:.3f}")

    # 生成报告
    print("\n3. 生成回测报告...")
    report = bt.generate_report()

    print(f"  初始资金: {report['summary']['initial_capital']:.2f}")
    print(f"  最终资金: {report['summary']['final_capital']:.2f}")
    print(f"  总收益率: {report['summary']['total_return_pct']:.2f}%")
    print(f"  年化收益率: {report['summary']['annualized_return_pct']:.2f}%")

    # 分析各策略表现
    print("\n4. 分析各策略表现...")
    strategy_stats = {}
    for trade in bt.trades:
        strategy = trade["strategy"]
        if strategy not in strategy_stats:
            strategy_stats[strategy] = {"trades": 0, "pnl": 0, "wins": 0}

        strategy_stats[strategy]["trades"] += 1
        if trade["pnl"]:
            strategy_stats[strategy]["pnl"] += trade["pnl"]
            if trade["pnl"] > 0:
                strategy_stats[strategy]["wins"] += 1

    for strategy, stats in strategy_stats.items():
        win_rate = stats["wins"] / stats["trades"] if stats["trades"] > 0 else 0
        print(f"  {strategy}:")
        print(f"    交易次数: {stats['trades']}")
        print(f"    胜率: {win_rate:.2%}")
        print(f"    总盈亏: {stats['pnl']:.2f}")

    return bt

if __name__ == "__main__":
    simulate_backtest()
