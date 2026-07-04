"""
贵金属交易决策辅助系统 - 多品种扩展模块
扩展到铂金、钯金
"""

import json
import numpy as np
from datetime import datetime, timedelta

class MultiMetalExtension:
    def __init__(self):
        self.metals = {
            "gold": {
                "name": "黄金",
                "symbol": "XAU/USD",
                "domestic_symbol": "AU",
                "contract_size": 100,  # 盎司
                "tick_size": 0.01,
                "tick_value": 1.0,
                "margin_rate": 0.12,
                "volatility": 0.15
            },
            "silver": {
                "name": "白银",
                "symbol": "XAG/USD",
                "domestic_symbol": "AG",
                "contract_size": 5000,  # 盎司
                "tick_size": 0.01,
                "tick_value": 50.0,
                "margin_rate": 0.12,
                "volatility": 0.25
            },
            "platinum": {
                "name": "铂金",
                "symbol": "XPT/USD",
                "domestic_symbol": "PT",
                "contract_size": 100,  # 盎司
                "tick_size": 0.01,
                "tick_value": 1.0,
                "margin_rate": 0.15,
                "volatility": 0.20
            },
            "palladium": {
                "name": "钯金",
                "symbol": "XPD/USD",
                "domestic_symbol": "PA",
                "contract_size": 100,  # 盎司
                "tick_size": 0.01,
                "tick_value": 1.0,
                "margin_rate": 0.15,
                "volatility": 0.30
            }
        }

        self.strategies = {
            "宏观利率波段": {"metals": ["gold", "silver", "platinum", "palladium"]},
            "央行抄底长线多": {"metals": ["gold", "silver"]},
            "金银比均值回归": {"metals": ["gold", "silver"]},
            "均线顺势波段": {"metals": ["gold", "silver", "platinum", "palladium"]},
            "区间高抛低吸": {"metals": ["gold", "silver", "platinum", "palladium"]},
            "突破追单": {"metals": ["gold", "silver", "platinum", "palladium"]},
            "事件避险短多": {"metals": ["gold", "silver"]},
            "逆势抄底": {"metals": ["gold", "silver"]},
            "跨品种套利": {"metals": ["gold", "silver", "platinum", "palladium"]},
            "季节性策略": {"metals": ["gold", "silver"]},
            "技术形态策略": {"metals": ["gold", "silver", "platinum", "palladium"]},
            "波动率交易策略": {"metals": ["gold", "silver"]},
            "资金流向策略": {"metals": ["gold", "silver"]}
        }

    def get_metal_info(self, metal):
        """获取金属信息"""
        return self.metals.get(metal, None)

    def get_applicable_strategies(self, metal):
        """获取适用策略"""
        applicable = []
        for strategy, info in self.strategies.items():
            if metal in info["metals"]:
                applicable.append(strategy)
        return applicable

    def calculate_position_size(self, metal, capital, risk_per_trade, entry_price, stop_loss):
        """计算仓位大小"""
        metal_info = self.metals.get(metal)
        if not metal_info:
            return 0

        # 计算每点价值
        point_value = metal_info["tick_value"]

        # 计算止损点数
        stop_loss_points = abs(entry_price - stop_loss) / metal_info["tick_size"]

        # 计算每手风险
        risk_per_lot = stop_loss_points * point_value

        # 计算仓位大小
        position_size = (capital * risk_per_trade) / risk_per_lot

        return position_size

    def calculate_margin_requirement(self, metal, position_size, price):
        """计算保证金要求"""
        metal_info = self.metals.get(metal)
        if not metal_info:
            return 0

        # 计算合约价值
        contract_value = position_size * metal_info["contract_size"] * price

        # 计算保证金
        margin = contract_value * metal_info["margin_rate"]

        return margin

    def analyze_correlation(self, metal1, metal2, historical_data):
        """分析两个金属的相关性"""
        if metal1 not in historical_data or metal2 not in historical_data:
            return None

        # 计算收益率
        returns1 = np.diff(historical_data[metal1]) / historical_data[metal1][:-1]
        returns2 = np.diff(historical_data[metal2]) / historical_data[metal2][:-1]

        # 计算相关系数
        correlation = np.corrcoef(returns1, returns2)[0, 1]

        return correlation

    def generate_portfolio(self, capital, risk_tolerance):
        """生成投资组合"""
        portfolio = {}

        # 根据风险承受能力分配资金
        if risk_tolerance == "conservative":
            allocation = {"gold": 0.5, "silver": 0.3, "platinum": 0.1, "palladium": 0.1}
        elif risk_tolerance == "moderate":
            allocation = {"gold": 0.4, "silver": 0.3, "platinum": 0.2, "palladium": 0.1}
        else:  # aggressive
            allocation = {"gold": 0.3, "silver": 0.3, "platinum": 0.2, "palladium": 0.2}

        for metal, weight in allocation.items():
            portfolio[metal] = {
                "weight": weight,
                "capital": capital * weight,
                "strategies": self.get_applicable_strategies(metal)
            }

        return portfolio

def test_multi_metal():
    """测试多品种扩展"""
    print("\n" + "="*80)
    print("多品种扩展测试")
    print("="*80)

    mme = MultiMetalExtension()

    # 测试金属信息
    print("\n1. 金属信息:")
    for metal, info in mme.metals.items():
        print(f"  {info['name']} ({info['symbol']}):")
        print(f"    合约大小: {info['contract_size']} 盎司")
        print(f"    最小变动: {info['tick_size']}")
        print(f"    每点价值: {info['tick_value']}")
        print(f"    保证金率: {info['margin_rate']}")
        print(f"    波动率: {info['volatility']}")

    # 测试适用策略
    print("\n2. 适用策略:")
    for metal in mme.metals:
        strategies = mme.get_applicable_strategies(metal)
        print(f"  {mme.metals[metal]['name']}: {len(strategies)} 种策略")

    # 测试仓位计算
    print("\n3. 仓位计算:")
    capital = 300000
    risk_per_trade = 0.015
    entry_price = 3300
    stop_loss = 3280

    for metal in mme.metals:
        position_size = mme.calculate_position_size(metal, capital, risk_per_trade, entry_price, stop_loss)
        margin = mme.calculate_margin_requirement(metal, position_size, entry_price)
        print(f"  {mme.metals[metal]['name']}:")
        print(f"    仓位大小: {position_size:.2f} 手")
        print(f"    保证金要求: {margin:.2f}")

    # 测试投资组合
    print("\n4. 投资组合:")
    for risk_tolerance in ["conservative", "moderate", "aggressive"]:
        portfolio = mme.generate_portfolio(capital, risk_tolerance)
        print(f"  {risk_tolerance}:")
        for metal, info in portfolio.items():
            print(f"    {mme.metals[metal]['name']}: {info['weight']:.0%} ({info['capital']:.0f})")

    return mme

if __name__ == "__main__":
    test_multi_metal()
