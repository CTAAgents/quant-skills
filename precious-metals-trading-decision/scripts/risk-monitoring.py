"""
贵金属交易决策辅助系统 - 风险监控增强模块
实时风险计算和预警
"""

import json
import numpy as np
from datetime import datetime, timedelta

class RiskMonitoring:
    def __init__(self, account_balance=300000):
        self.account_balance = account_balance
        self.risk_limits = {
            "max_position_size": 0.20,  # 单品种最大持仓20%
            "max_total_exposure": 0.60,  # 总持仓最大60%
            "max_daily_loss": 0.05,  # 单日最大亏损5%
            "max_weekly_loss": 0.08,  # 周度最大亏损8%
            "max_drawdown": 0.15,  # 最大回撤15%
            "max_correlation": 0.70,  # 最大相关性70%
            "var_confidence": 0.95,  # VaR置信度95%
            "var_horizon": 1  # VaR时间窗口1天
        }

        self.risk_metrics = {}
        self.alerts = []
        self.equity_history = []
        self.peak_equity = account_balance

    def calculate_var(self, returns, confidence=0.95, horizon=1):
        """计算VaR（风险价值）"""
        if len(returns) < 10:
            return 0

        # 计算历史VaR
        sorted_returns = np.sort(returns)
        index = int((1 - confidence) * len(sorted_returns))
        var = abs(sorted_returns[index]) * np.sqrt(horizon)

        return var

    def calculate_cvar(self, returns, confidence=0.95):
        """计算CVaR（条件风险价值）"""
        if len(returns) < 10:
            return 0

        # 计算历史CVaR
        sorted_returns = np.sort(returns)
        index = int((1 - confidence) * len(sorted_returns))
        cvar = abs(np.mean(sorted_returns[:index]))

        return cvar

    def calculate_max_drawdown(self, equity_curve):
        """计算最大回撤"""
        if len(equity_curve) < 2:
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

    def calculate_sharpe_ratio(self, returns, risk_free_rate=0.02/252):
        """计算夏普比率"""
        if len(returns) < 10:
            return 0

        excess_returns = returns - risk_free_rate
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0

        return sharpe

    def calculate_sortino_ratio(self, returns, risk_free_rate=0.02/252):
        """计算索提诺比率"""
        if len(returns) < 10:
            return 0

        excess_returns = returns - risk_free_rate
        downside_returns = excess_returns[excess_returns < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0

        sortino = np.mean(excess_returns) / downside_std * np.sqrt(252) if downside_std > 0 else 0

        return sortino

    def calculate_calmar_ratio(self, returns, max_drawdown):
        """计算卡尔玛比率"""
        if len(returns) < 10 or max_drawdown == 0:
            return 0

        annual_return = np.mean(returns) * 252
        calmar = annual_return / max_drawdown

        return calmar

    def calculate_position_risk(self, position, current_price):
        """计算持仓风险"""
        # 计算持仓价值
        position_value = position["quantity"] * current_price * 100  # 假设合约大小100

        # 计算持仓占比
        position_pct = position_value / self.account_balance

        # 计算未实现盈亏
        unrealized_pnl = (current_price - position["avg_price"]) * position["quantity"] * 100

        # 计算风险指标
        risk = {
            "symbol": position["symbol"],
            "quantity": position["quantity"],
            "avg_price": position["avg_price"],
            "current_price": current_price,
            "position_value": position_value,
            "position_pct": position_pct,
            "unrealized_pnl": unrealized_pnl,
            "risk_level": "low" if position_pct < 0.10 else "medium" if position_pct < 0.15 else "high"
        }

        return risk

    def check_risk_limits(self, positions, current_prices):
        """检查风险限制"""
        alerts = []

        # 计算总持仓价值
        total_exposure = 0
        for symbol, position in positions.items():
            if position["quantity"] > 0:
                current_price = current_prices.get(symbol, position["avg_price"])
                position_value = position["quantity"] * current_price * 100
                total_exposure += position_value

        # 检查总持仓限制
        total_exposure_pct = total_exposure / self.account_balance
        if total_exposure_pct > self.risk_limits["max_total_exposure"]:
            alerts.append({
                "type": "total_exposure",
                "level": "high",
                "message": f"总持仓占比{total_exposure_pct:.1%}超过限制{self.risk_limits['max_total_exposure']:.1%}",
                "timestamp": datetime.now().isoformat()
            })

        # 检查单品种持仓限制
        for symbol, position in positions.items():
            if position["quantity"] > 0:
                current_price = current_prices.get(symbol, position["avg_price"])
                position_value = position["quantity"] * current_price * 100
                position_pct = position_value / self.account_balance

                if position_pct > self.risk_limits["max_position_size"]:
                    alerts.append({
                        "type": "position_size",
                        "level": "medium",
                        "message": f"{symbol}持仓占比{position_pct:.1%}超过限制{self.risk_limits['max_position_size']:.1%}",
                        "timestamp": datetime.now().isoformat()
                    })

        # 检查回撤限制
        current_equity = self.account_balance
        max_drawdown = self.calculate_max_drawdown(self.equity_history)
        if max_drawdown > self.risk_limits["max_drawdown"]:
            alerts.append({
                "type": "drawdown",
                "level": "high",
                "message": f"最大回撤{max_drawdown:.1%}超过限制{self.risk_limits['max_drawdown']:.1%}",
                "timestamp": datetime.now().isoformat()
            })

        self.alerts.extend(alerts)
        return alerts

    def calculate_risk_metrics(self, returns, positions, current_prices):
        """计算风险指标"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "account_balance": self.account_balance,
            "var_95": self.calculate_var(returns, 0.95),
            "cvar_95": self.calculate_cvar(returns, 0.95),
            "max_drawdown": self.calculate_max_drawdown(self.equity_history),
            "sharpe_ratio": self.calculate_sharpe_ratio(returns),
            "sortino_ratio": self.calculate_sortino_ratio(returns),
            "position_risks": {}
        }

        # 计算持仓风险
        for symbol, position in positions.items():
            if position["quantity"] > 0:
                current_price = current_prices.get(symbol, position["avg_price"])
                metrics["position_risks"][symbol] = self.calculate_position_risk(position, current_price)

        self.risk_metrics = metrics
        return metrics

    def generate_risk_report(self):
        """生成风险报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "account_balance": self.account_balance,
            "risk_limits": self.risk_limits,
            "risk_metrics": self.risk_metrics,
            "alerts": self.alerts[-10:],  # 最近10条警报
            "alert_summary": {
                "total": len(self.alerts),
                "high": len([a for a in self.alerts if a["level"] == "high"]),
                "medium": len([a for a in self.alerts if a["level"] == "medium"]),
                "low": len([a for a in self.alerts if a["level"] == "low"])
            }
        }

        return report

    def update_equity(self, equity):
        """更新权益曲线"""
        self.equity_history.append(equity)

        # 更新峰值权益
        if equity > self.peak_equity:
            self.peak_equity = equity

    def check_stop_loss(self, position, current_price):
        """检查止损"""
        if "stop_loss" not in position:
            return None

        stop_loss = position["stop_loss"]

        if position["side"] == "long" and current_price <= stop_loss:
            return {
                "triggered": True,
                "type": "stop_loss",
                "symbol": position["symbol"],
                "current_price": current_price,
                "stop_loss": stop_loss,
                "message": f"{position['symbol']}触及止损{stop_loss}"
            }
        elif position["side"] == "short" and current_price >= stop_loss:
            return {
                "triggered": True,
                "type": "stop_loss",
                "symbol": position["symbol"],
                "current_price": current_price,
                "stop_loss": stop_loss,
                "message": f"{position['symbol']}触及止损{stop_loss}"
            }

        return {"triggered": False}

    def check_take_profit(self, position, current_price):
        """检查止盈"""
        if "take_profit" not in position:
            return None

        take_profit = position["take_profit"]

        if position["side"] == "long" and current_price >= take_profit:
            return {
                "triggered": True,
                "type": "take_profit",
                "symbol": position["symbol"],
                "current_price": current_price,
                "take_profit": take_profit,
                "message": f"{position['symbol']}触及止盈{take_profit}"
            }
        elif position["side"] == "short" and current_price <= take_profit:
            return {
                "triggered": True,
                "type": "take_profit",
                "symbol": position["symbol"],
                "current_price": current_price,
                "take_profit": take_profit,
                "message": f"{position['symbol']}触及止盈{take_profit}"
            }

        return {"triggered": False}

def test_risk_monitoring():
    """测试风险监控"""
    print("\n" + "="*80)
    print("风险监控增强测试")
    print("="*80)

    rm = RiskMonitoring(account_balance=300000)

    # 模拟收益数据
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 252)  # 日收益

    # 模拟权益曲线
    equity_curve = [300000]
    for r in returns:
        equity_curve.append(equity_curve[-1] * (1 + r))
    rm.equity_history = equity_curve

    # 测试VaR计算
    print("\n1. VaR计算:")
    var_95 = rm.calculate_var(returns, 0.95)
    print(f"  95% VaR: {var_95:.2%}")

    # 测试CVaR计算
    print("\n2. CVaR计算:")
    cvar_95 = rm.calculate_cvar(returns, 0.95)
    print(f"  95% CVaR: {cvar_95:.2%}")

    # 测试最大回撤
    print("\n3. 最大回撤:")
    max_dd = rm.calculate_max_drawdown(equity_curve)
    print(f"  最大回撤: {max_dd:.2%}")

    # 测试夏普比率
    print("\n4. 夏普比率:")
    sharpe = rm.calculate_sharpe_ratio(returns)
    print(f"  夏普比率: {sharpe:.3f}")

    # 测试索提诺比率
    print("\n5. 索提诺比率:")
    sortino = rm.calculate_sortino_ratio(returns)
    print(f"  索提诺比率: {sortino:.3f}")

    # 测试卡尔玛比率
    print("\n6. 卡尔玛比率:")
    calmar = rm.calculate_calmar_ratio(returns, max_dd)
    print(f"  卡尔玛比率: {calmar:.3f}")

    # 测试持仓风险
    print("\n7. 持仓风险:")
    position = {"symbol": "gold", "quantity": 0.5, "avg_price": 3300, "side": "long", "stop_loss": 3280, "take_profit": 3340}
    current_price = 3310
    risk = rm.calculate_position_risk(position, current_price)
    print(f"  {risk['symbol']}: {risk['quantity']}手 @ {risk['avg_price']}")
    print(f"  当前价格: {risk['current_price']}")
    print(f"  持仓价值: {risk['position_value']:.0f}")
    print(f"  持仓占比: {risk['position_pct']:.1%}")
    print(f"  未实现盈亏: {risk['unrealized_pnl']:.0f}")
    print(f"  风险等级: {risk['risk_level']}")

    # 测试止损检查
    print("\n8. 止损检查:")
    sl_result = rm.check_stop_loss(position, 3279)
    print(f"  触发: {sl_result['triggered']}")
    if sl_result["triggered"]:
        print(f"  消息: {sl_result['message']}")

    # 测试止盈检查
    print("\n9. 止盈检查:")
    tp_result = rm.check_take_profit(position, 3341)
    print(f"  触发: {tp_result['triggered']}")
    if tp_result["triggered"]:
        print(f"  消息: {tp_result['message']}")

    # 测试风险限制检查
    print("\n10. 风险限制检查:")
    positions = {
        "gold": {"symbol": "gold", "quantity": 2.0, "avg_price": 3300},
        "silver": {"symbol": "silver", "quantity": 0.5, "avg_price": 35}
    }
    current_prices = {"gold": 3310, "silver": 35.5}
    alerts = rm.check_risk_limits(positions, current_prices)
    print(f"  警报数: {len(alerts)}")
    for alert in alerts:
        print(f"  - {alert['level']}: {alert['message']}")

    # 测试风险报告
    print("\n11. 风险报告:")
    report = rm.generate_risk_report()
    print(f"  账户余额: {report['account_balance']:.0f}")
    print(f"  警报总数: {report['alert_summary']['total']}")
    print(f"  高风险警报: {report['alert_summary']['high']}")
    print(f"  中风险警报: {report['alert_summary']['medium']}")

    return rm

if __name__ == "__main__":
    test_risk_monitoring()
