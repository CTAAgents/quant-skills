"""
贵金属交易决策辅助系统 - 实时回测模块
实现实时回测和策略优化
"""

import json
import numpy as np
from datetime import datetime, timedelta
import threading
import time

class RealtimeBacktesting:
    def __init__(self, initial_capital=300000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.risk_metrics = {}
        self.is_running = False
        self.update_interval = 1  # 更新间隔（秒）

    def start(self):
        """启动实时回测"""
        self.is_running = True
        print("实时回测已启动...")

    def stop(self):
        """停止实时回测"""
        self.is_running = False
        print("实时回测已停止...")

    def update_market_data(self, market_data):
        """更新市场数据"""
        if not self.is_running:
            return

        # 更新持仓盈亏
        self._update_positions_pnl(market_data)

        # 检查止损/止盈
        self._check_stop_loss_take_profit(market_data)

        # 更新权益曲线
        self._update_equity_curve()

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

    def _update_positions_pnl(self, market_data):
        """更新持仓盈亏"""
        for trade_id, trade in self.positions.items():
            current_price = market_data.get("gold_price", 3300)

            if trade["direction"] == "long":
                unrealized_pnl = (current_price - trade["entry_price"]) * trade["position_size"]
            else:
                unrealized_pnl = (trade["entry_price"] - current_price) * trade["position_size"]

            trade["unrealized_pnl"] = unrealized_pnl

    def _check_stop_loss_take_profit(self, market_data):
        """检查止损/止盈"""
        current_price = market_data.get("gold_price", 3300)

        trades_to_close = []
        for trade_id, trade in self.positions.items():
            # 检查止损
            if trade["direction"] == "long" and current_price <= trade["stop_loss"]:
                trades_to_close.append((trade_id, "stop_loss"))
            elif trade["direction"] == "short" and current_price >= trade["stop_loss"]:
                trades_to_close.append((trade_id, "stop_loss"))

            # 检查止盈
            if trade["direction"] == "long" and current_price >= trade["take_profit"]:
                trades_to_close.append((trade_id, "take_profit"))
            elif trade["direction"] == "short" and current_price <= trade["take_profit"]:
                trades_to_close.append((trade_id, "take_profit"))

        # 平仓
        for trade_id, reason in trades_to_close:
            self.close_trade(trade_id, current_price)
            print(f"  交易 {trade_id} 已平仓，原因: {reason}")

    def _update_equity_curve(self):
        """更新权益曲线"""
        # 计算当前权益
        unrealized_pnl = sum(trade.get("unrealized_pnl", 0) for trade in self.positions.values())
        current_equity = self.capital + unrealized_pnl

        self.equity_curve.append({
            "timestamp": datetime.now(),
            "equity": current_equity
        })

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
        equity_values = [e["equity"] for e in self.equity_curve]
        max_drawdown = self._calculate_max_drawdown(equity_values)

        # 计算夏普比率
        risk_free_rate = 0.02 / 252
        sharpe_ratio = (avg_return - risk_free_rate) / std_return if std_return > 0 else 0

        self.risk_metrics = {
            "total_return": total_return,
            "avg_return": avg_return,
            "std_return": std_return,
            "win_rate": win_rate,
            "profit_loss_ratio": profit_loss_ratio,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "total_trades": len(closed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "open_positions": len(self.positions)
        }

        return self.risk_metrics

    def _calculate_max_drawdown(self, equity_values):
        """计算最大回撤"""
        if len(equity_values) == 0:
            return 0

        peak = equity_values[0]
        max_dd = 0

        for value in equity_values:
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
                "total_return_pct": (metrics.get("total_return", 0) / self.initial_capital) * 100
            },
            "risk_metrics": metrics,
            "trades": self.trades,
            "equity_curve": self.equity_curve
        }

        return report

def simulate_realtime_backtest():
    """模拟实时回测"""
    print("\n" + "="*80)
    print("实时回测测试")
    print("="*80)

    bt = RealtimeBacktesting(initial_capital=300000)

    # 启动实时回测
    print("\n1. 启动实时回测...")
    bt.start()

    # 模拟100次市场数据更新
    print("\n2. 模拟100次市场数据更新...")
    np.random.seed(42)

    strategies = ["宏观利率波段", "均线顺势", "突破追单", "区间高抛低吸", "金银比均值回归"]

    for i in range(100):
        # 生成市场数据
        market_data = {
            "gold_price": 3300 + np.random.normal(0, 50),
            "tips_10y": 2.0 + np.random.normal(0, 0.1),
            "dxy": 103 + np.random.normal(0, 1)
        }

        # 更新市场数据
        bt.update_market_data(market_data)

        # 随机执行交易
        if np.random.random() > 0.7:
            strategy = strategies[i % len(strategies)]
            direction = "long" if np.random.random() > 0.4 else "short"
            entry_price = market_data["gold_price"]
            stop_loss = entry_price - 20 if direction == "long" else entry_price + 20
            take_profit = entry_price + 40 if direction == "long" else entry_price - 40
            position_size = 0.5

            bt.execute_trade(strategy, direction, entry_price, stop_loss, take_profit, position_size)

    # 停止实时回测
    print("\n3. 停止实时回测...")
    bt.stop()

    # 计算指标
    print("\n4. 计算回测指标...")
    metrics = bt.calculate_metrics()

    if metrics:
        print(f"  总收益: {metrics['total_return']:.2f}")
        print(f"  胜率: {metrics['win_rate']:.2%}")
        print(f"  盈亏比: {metrics['profit_loss_ratio']:.2f}")
        print(f"  最大回撤: {metrics['max_drawdown']:.2%}")
        print(f"  夏普比率: {metrics['sharpe_ratio']:.3f}")
        print(f"  开仓数: {metrics['open_positions']}")

    # 生成报告
    print("\n5. 生成回测报告...")
    report = bt.generate_report()

    print(f"  初始资金: {report['summary']['initial_capital']:.2f}")
    print(f"  最终资金: {report['summary']['final_capital']:.2f}")
    print(f"  总收益率: {report['summary']['total_return_pct']:.2f}%")

    return bt

if __name__ == "__main__":
    simulate_realtime_backtest()
