"""
贵金属交易决策辅助系统 - 策略组合优化模块
研究多策略组合的风险收益特征，分析策略间的相关性
"""

import json
import numpy as np
from datetime import datetime, timedelta

class StrategyCombination:
    def __init__(self):
        self.strategies = {
            "宏观利率波段": {"regime": ["R1", "R3"], "weight": 0.20},
            "央行抄底长线多": {"regime": ["R4"], "weight": 0.10},
            "金银比均值回归": {"regime": ["R1/R2"], "weight": 0.10},
            "均线顺势波段": {"regime": ["R1", "R3"], "weight": 0.15},
            "区间高抛低吸": {"regime": ["R2"], "weight": 0.10},
            "突破追单": {"regime": ["R1", "R3"], "weight": 0.10},
            "事件避险短多": {"regime": ["Any"], "weight": 0.05},
            "逆势抄底": {"regime": ["R3→R1", "R1→R3"], "weight": 0.05},
            "跨品种套利": {"regime": ["R1/R2"], "weight": 0.05},
            "季节性策略": {"regime": ["R1/R4"], "weight": 0.05},
            "技术形态策略": {"regime": ["R1", "R3"], "weight": 0.05},
            "波动率交易策略": {"regime": ["R2"], "weight": 0.05},
            "资金流向策略": {"regime": ["R3→R1", "R1→R3"], "weight": 0.05}
        }

        self.strategy_returns = {}
        self.correlation_matrix = None

    def calculate_strategy_returns(self, historical_data):
        """计算各策略的历史收益"""
        returns = {}

        for strategy_name, strategy_info in self.strategies.items():
            # 模拟策略收益（实际应用中应从历史数据计算）
            # 这里使用随机数据模拟
            np.random.seed(hash(strategy_name) % 2**32)
            returns[strategy_name] = np.random.normal(0.05, 0.15, 252)  # 年化5%收益，15%波动

        self.strategy_returns = returns
        return returns

    def calculate_correlation_matrix(self):
        """计算策略间的相关性矩阵"""
        if not self.strategy_returns:
            return None

        strategy_names = list(self.strategy_returns.keys())
        n = len(strategy_names)

        # 构建收益矩阵
        returns_matrix = np.array([self.strategy_returns[name] for name in strategy_names])

        # 计算相关性矩阵
        self.correlation_matrix = np.corrcoef(returns_matrix)

        return self.correlation_matrix

    def optimize_portfolio_weights(self, risk_free_rate=0.02):
        """优化投资组合权重（均值-方差优化）"""
        if not self.strategy_returns:
            return None

        strategy_names = list(self.strategy_returns.keys())
        n = len(strategy_names)

        # 计算各策略的年化收益和波动率
        returns_array = np.array([self.strategy_returns[name] for name in strategy_names])
        mean_returns = np.mean(returns_array, axis=1) * 252  # 年化收益
        cov_matrix = np.cov(returns_array) * 252  # 年化协方差矩阵

        # 简化的均值-方差优化（实际应用中应使用更复杂的优化算法）
        # 这里使用等权重作为基准
        equal_weights = np.ones(n) / n

        # 计算组合收益和风险
        portfolio_return = np.dot(equal_weights, mean_returns)
        portfolio_risk = np.sqrt(np.dot(equal_weights.T, np.dot(cov_matrix, equal_weights)))

        # 计算夏普比率
        sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_risk

        # 优化权重（最大化夏普比率）
        # 这里使用简化的梯度下降
        optimized_weights = self._optimize_sharpe_ratio(mean_returns, cov_matrix, risk_free_rate)

        return {
            "equal_weights": {name: weight for name, weight in zip(strategy_names, equal_weights)},
            "optimized_weights": {name: weight for name, weight in zip(strategy_names, optimized_weights)},
            "portfolio_return": portfolio_return,
            "portfolio_risk": portfolio_risk,
            "sharpe_ratio": sharpe_ratio
        }

    def _optimize_sharpe_ratio(self, mean_returns, cov_matrix, risk_free_rate, iterations=1000):
        """优化夏普比率"""
        n = len(mean_returns)
        weights = np.ones(n) / n
        learning_rate = 0.01

        for _ in range(iterations):
            # 计算组合收益和风险
            portfolio_return = np.dot(weights, mean_returns)
            portfolio_risk = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

            # 计算夏普比率
            sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_risk

            # 计算梯度
            # dS/dw = (mu - rf) / sigma - (mu - rf) * Sigma * w / sigma^3
            excess_return = mean_returns - risk_free_rate
            sigma = portfolio_risk
            sigma_squared = sigma ** 2

            gradient = (excess_return / sigma) - (np.dot(cov_matrix, weights) * (portfolio_return - risk_free_rate) / (sigma ** 3))

            # 更新权重
            weights += learning_rate * gradient

            # 归一化权重（确保总和为1）
            weights = np.maximum(weights, 0)  # 确保非负
            weights /= np.sum(weights)

        return weights

    def analyze_strategy_combination(self, current_regime):
        """分析当前Regime下的策略组合"""
        suitable_strategies = []

        for strategy_name, strategy_info in self.strategies.items():
            if current_regime in strategy_info["regime"] or "Any" in strategy_info["regime"]:
                suitable_strategies.append({
                    "name": strategy_name,
                    "weight": strategy_info["weight"],
                    "regime": strategy_info["regime"]
                })

        # 按权重排序
        suitable_strategies.sort(key=lambda x: x["weight"], reverse=True)

        return suitable_strategies

    def calculate_diversification_benefit(self):
        """计算分散化收益"""
        if self.correlation_matrix is None:
            return None

        # 计算平均相关性
        n = self.correlation_matrix.shape[0]
        avg_correlation = (np.sum(self.correlation_matrix) - n) / (n * (n - 1))

        # 分散化比率
        diversification_ratio = 1 / (1 + avg_correlation * (n - 1))

        return {
            "average_correlation": avg_correlation,
            "diversification_ratio": diversification_ratio,
            "number_of_strategies": n
        }

def test_strategy_combination():
    """测试策略组合优化"""
    print("\n" + "="*80)
    print("策略组合优化测试")
    print("="*80)

    optimizer = StrategyCombination()

    # 生成模拟历史数据
    historical_data = {
        "gold_price": np.random.normal(3300, 100, 252),
        "tips_10y": np.random.normal(2.0, 0.3, 252),
        "dxy": np.random.normal(103, 2, 252)
    }

    # 计算策略收益
    print("\n1. 计算各策略的历史收益...")
    returns = optimizer.calculate_strategy_returns(historical_data)
    for strategy, ret in returns.items():
        print(f"  {strategy}: 年化收益={np.mean(ret)*252:.2%}, 波动率={np.std(ret)*np.sqrt(252):.2%}")

    # 计算相关性矩阵
    print("\n2. 计算策略间的相关性矩阵...")
    corr_matrix = optimizer.calculate_correlation_matrix()
    print(f"  平均相关性: {np.mean(corr_matrix):.3f}")

    # 优化投资组合权重
    print("\n3. 优化投资组合权重...")
    portfolio = optimizer.optimize_portfolio_weights()
    print(f"  等权重组合收益: {portfolio['portfolio_return']:.2%}")
    print(f"  等权重组合风险: {portfolio['portfolio_risk']:.2%}")
    print(f"  夏普比率: {portfolio['sharpe_ratio']:.3f}")

    print("\n  优化后权重:")
    for strategy, weight in portfolio['optimized_weights'].items():
        print(f"    {strategy}: {weight:.2%}")

    # 分析策略组合
    print("\n4. 分析当前Regime下的策略组合...")
    current_regime = "R1"
    suitable_strategies = optimizer.analyze_strategy_combination(current_regime)
    print(f"  当前Regime: {current_regime}")
    print(f"  适用策略:")
    for strategy in suitable_strategies:
        print(f"    {strategy['name']}: 权重={strategy['weight']:.2%}")

    # 计算分散化收益
    print("\n5. 计算分散化收益...")
    diversification = optimizer.calculate_diversification_benefit()
    print(f"  平均相关性: {diversification['average_correlation']:.3f}")
    print(f"  分散化比率: {diversification['diversification_ratio']:.3f}")
    print(f"  策略数量: {diversification['number_of_strategies']}")

    return optimizer

if __name__ == "__main__":
    test_strategy_combination()
