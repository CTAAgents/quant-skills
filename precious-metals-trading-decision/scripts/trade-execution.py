"""
贵金属交易决策辅助系统 - 交易执行集成模块
实现自动下单和持仓管理
"""

import json
import numpy as np
from datetime import datetime, timedelta

class TradeExecution:
    def __init__(self, broker="simulated", account_id="DEMO001"):
        self.broker = broker
        self.account_id = account_id
        self.orders = []
        self.positions = {}
        self.trades = []
        self.account_balance = 300000
        self.margin_used = 0

    def place_order(self, symbol, side, quantity, order_type="market", price=None, stop_loss=None, take_profit=None):
        """下单"""
        order = {
            "order_id": len(self.orders) + 1,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "filled_at": None,
            "filled_price": None
        }

        self.orders.append(order)

        # 模拟订单执行
        if order_type == "market":
            self._execute_order(order)

        return order

    def cancel_order(self, order_id):
        """取消订单"""
        for order in self.orders:
            if order["order_id"] == order_id and order["status"] == "pending":
                order["status"] = "cancelled"
                return True
        return False

    def modify_order(self, order_id, **kwargs):
        """修改订单"""
        for order in self.orders:
            if order["order_id"] == order_id and order["status"] == "pending":
                for key, value in kwargs.items():
                    if key in order:
                        order[key] = value
                return True
        return False

    def _execute_order(self, order):
        """执行订单"""
        # 模拟执行价格
        np.random.seed(hash(str(order["order_id"])) % 2**32)
        base_price = order["price"] or 3300
        fill_price = base_price + np.random.normal(0, 1)

        order["status"] = "filled"
        order["filled_at"] = datetime.now().isoformat()
        order["filled_price"] = round(fill_price, 2)

        # 更新持仓
        symbol = order["symbol"]
        if symbol not in self.positions:
            self.positions[symbol] = {
                "symbol": symbol,
                "quantity": 0,
                "avg_price": 0,
                "unrealized_pnl": 0,
                "realized_pnl": 0
            }

        position = self.positions[symbol]

        if order["side"] == "buy":
            # 计算新的平均价格
            total_cost = position["avg_price"] * position["quantity"] + order["filled_price"] * order["quantity"]
            position["quantity"] += order["quantity"]
            position["avg_price"] = total_cost / position["quantity"] if position["quantity"] > 0 else 0
        else:  # sell
            # 计算盈亏
            pnl = (order["filled_price"] - position["avg_price"]) * order["quantity"]
            position["realized_pnl"] += pnl
            position["quantity"] -= order["quantity"]

            # 记录交易
            self.trades.append({
                "trade_id": len(self.trades) + 1,
                "order_id": order["order_id"],
                "symbol": symbol,
                "side": order["side"],
                "quantity": order["quantity"],
                "price": order["filled_price"],
                "pnl": pnl,
                "timestamp": datetime.now().isoformat()
            })

        # 更新账户余额
        self.account_balance -= order["filled_price"] * order["quantity"] * 0.12  # 保证金

    def get_positions(self):
        """获取持仓"""
        return self.positions

    def get_position(self, symbol):
        """获取指定品种的持仓"""
        return self.positions.get(symbol, None)

    def close_position(self, symbol, quantity=None):
        """平仓"""
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]
        close_quantity = quantity or position["quantity"]

        if close_quantity > position["quantity"]:
            close_quantity = position["quantity"]

        # 下卖出订单
        order = self.place_order(symbol, "sell", close_quantity)

        return order

    def get_account_summary(self):
        """获取账户摘要"""
        total_unrealized_pnl = sum(p["unrealized_pnl"] for p in self.positions.values())
        total_realized_pnl = sum(p["realized_pnl"] for p in self.positions.values())

        return {
            "account_id": self.account_id,
            "broker": self.broker,
            "balance": self.account_balance,
            "equity": self.account_balance + total_unrealized_pnl,
            "margin_used": self.margin_used,
            "free_margin": self.account_balance - self.margin_used,
            "unrealized_pnl": total_unrealized_pnl,
            "realized_pnl": total_realized_pnl,
            "open_positions": len([p for p in self.positions.values() if p["quantity"] > 0]),
            "pending_orders": len([o for o in self.orders if o["status"] == "pending"])
        }

    def get_trade_history(self, symbol=None, start_date=None, end_date=None):
        """获取交易历史"""
        trades = self.trades

        if symbol:
            trades = [t for t in trades if t["symbol"] == symbol]

        if start_date:
            trades = [t for t in trades if t["timestamp"] >= start_date]

        if end_date:
            trades = [t for t in trades if t["timestamp"] <= end_date]

        return trades

    def calculate_position_size(self, symbol, risk_amount, entry_price, stop_loss):
        """计算仓位大小"""
        # 获取合约规格
        contract_specs = {
            "gold": {"contract_size": 100, "tick_size": 0.01, "tick_value": 1.0},
            "silver": {"contract_size": 5000, "tick_size": 0.01, "tick_value": 50.0},
            "platinum": {"contract_size": 100, "tick_size": 0.01, "tick_value": 1.0},
            "palladium": {"contract_size": 100, "tick_size": 0.01, "tick_value": 1.0}
        }

        spec = contract_specs.get(symbol, contract_specs["gold"])

        # 计算止损点数
        stop_loss_points = abs(entry_price - stop_loss) / spec["tick_size"]

        # 计算每手风险
        risk_per_lot = stop_loss_points * spec["tick_value"]

        # 计算仓位大小
        position_size = risk_amount / risk_per_lot if risk_per_lot > 0 else 0

        return round(position_size, 2)

def test_trade_execution():
    """测试交易执行"""
    print("\n" + "="*80)
    print("交易执行集成测试")
    print("="*80)

    te = TradeExecution()

    # 测试下单
    print("\n1. 下单测试:")
    order1 = te.place_order("gold", "buy", 0.5, price=3300, stop_loss=3280, take_profit=3340)
    print(f"  订单 {order1['order_id']}: {order1['side']} {order1['quantity']} {order1['symbol']} @ {order1['filled_price']}")

    order2 = te.place_order("silver", "buy", 0.1, price=35, stop_loss=34, take_profit=36)
    print(f"  订单 {order2['order_id']}: {order2['side']} {order2['quantity']} {order2['symbol']} @ {order2['filled_price']}")

    # 测试持仓
    print("\n2. 持仓查询:")
    positions = te.get_positions()
    for symbol, pos in positions.items():
        if pos["quantity"] > 0:
            print(f"  {symbol}: {pos['quantity']}手 @ {pos['avg_price']}")

    # 测试账户摘要
    print("\n3. 账户摘要:")
    summary = te.get_account_summary()
    print(f"  账户余额: {summary['balance']:.2f}")
    print(f"  权益: {summary['equity']:.2f}")
    print(f"  未实现盈亏: {summary['unrealized_pnl']:.2f}")
    print(f"  已实现盈亏: {summary['realized_pnl']:.2f}")
    print(f"  持仓数: {summary['open_positions']}")

    # 测试平仓
    print("\n4. 平仓测试:")
    close_order = te.close_position("gold", 0.3)
    if close_order:
        print(f"  平仓订单: {close_order['order_id']}")

    # 测试仓位计算
    print("\n5. 仓位计算:")
    position_size = te.calculate_position_size("gold", 4500, 3300, 3280)
    print(f"  风险金额: 4500")
    print(f"  入场价: 3300")
    print(f"  止损价: 3280")
    print(f"  建议仓位: {position_size}手")

    # 测试交易历史
    print("\n6. 交易历史:")
    trades = te.get_trade_history()
    for trade in trades:
        print(f"  {trade['timestamp'][:19]}: {trade['side']} {trade['quantity']} {trade['symbol']} @ {trade['price']}")

    return te

if __name__ == "__main__":
    test_trade_execution()
