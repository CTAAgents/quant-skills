"""
问题2：评分权重客观化模块
通过机器学习和历史回测确定最优权重
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy.optimize import minimize
import json


@dataclass
class BacktestResult:
    """回测结果"""
    weights: Dict[str, float]
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float


class WeightOptimizer:
    """权重优化器 - 基于历史回测和机器学习"""
    
    def __init__(self):
        # 默认权重（作为初始值）
        self.default_weights = {
            'industry_chain': 0.35,
            'fundamental': 0.30,
            'technical': 0.35
        }
        
        # 各维度内部的子权重
        self.default_sub_weights = {
            'industry_chain': {
                'inventory': 0.20,
                'profit': 0.20,
                'supply_demand': 0.25,
                'basis': 0.20,
                'behavior': 0.15
            },
            'fundamental': {
                'supply_demand_gap': 0.30,
                'inventory_change': 0.25,
                'profit_margin': 0.20,
                'basis_structure': 0.25
            },
            'technical': {
                'trend': 0.25,
                'momentum': 0.20,
                'volatility': 0.15,
                'volume': 0.20,
                'pattern': 0.20
            }
        }
    
    def generate_synthetic_historical_data(self, n_periods: int = 200) -> pd.DataFrame:
        """
        生成合成历史数据用于回测（实际使用时应替换为真实数据
        """
        np.random.seed(42)
        
        data = []
        for i in range(n_periods):
            # 生成因子值
            industry_score = 50 + np.random.randn() * 20
            fundamental_score = 50 + np.random.randn() * 20
            technical_score = 50 + np.random.randn() * 20
            
            # 生成未来收益（与综合评分有一定相关性）
            combined_score = 0.4 * industry_score + 0.3 * fundamental_score + 0.3 * technical_score
            future_return = (combined_score - 50) * 0.002 + np.random.randn() * 0.015
            
            data.append({
                'period': i,
                'industry_chain_score': max(0, min(100, industry_score)),
                'fundamental_score': max(0, min(100, fundamental_score)),
                'technical_score': max(0, min(100, technical_score)),
                'future_return': future_return
            })
        
        return pd.DataFrame(data)
    
    def objective_function(self, weights: np.ndarray, historical_data: pd.DataFrame) -> float:
        """
        目标函数：最大化风险调整后收益（夏普比率）
        
        参数：
            weights: 权重数组 [w_industry, w_fundamental, w_technical]
        """
        # 归一化权重（确保和为1）
        weights = weights / np.sum(weights)
        
        # 计算加权综合评分
        combined_scores = (
            weights[0] * historical_data['industry_chain_score'] +
            weights[1] * historical_data['fundamental_score'] +
            weights[2] * historical_data['technical_score']
        )
        
        # 生成交易信号：评分高于50买入，低于50卖出
        signals = np.where(combined_scores > 50, 1, np.where(combined_scores < 50, -1, 0))
        
        # 计算策略收益
        strategy_returns = signals * historical_data['future_return']
        
        # 计算夏普比率（简化版）
        excess_returns = strategy_returns - 0.0001  # 假设无风险利率
        if np.std(excess_returns) == 0:
            return 0
        
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        
        # 同时考虑最大回撤惩罚
        cumulative = (1 + strategy_returns).cumprod()
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)
        
        # 目标函数：最大化夏普比率，同时惩罚最大回撤
        objective = sharpe * (1 + max_drawdown * 2)  # 回撤越大惩罚越重
        
        return -objective  # 最小化负目标函数（因为minimize函数找最小值
    
    def optimize_top_level_weights(self, historical_data: pd.DataFrame) -> Dict[str, float]:
        """
        优化顶层权重（产业链/基本面/技术面）
        
        使用scipy优化器寻找最优权重
        """
        # 初始猜测
        initial_weights = np.array([0.35, 0.30, 0.35])
        
        # 约束：权重和为1，每个权重在[0.1, 0.6]之间
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        ]
        bounds = [(0.1, 0.6), (0.1, 0.6), (0.1, 0.6)]
        
        # 优化
        result = minimize(
            self.objective_function,
            initial_weights,
            args=(historical_data,),
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        optimal_weights = result.x / np.sum(result.x)
        
        return {
            'industry_chain': float(optimal_weights[0]),
            'fundamental': float(optimal_weights[1]),
            'technical': float(optimal_weights[2])
        }
    
    def optimize_sub_weights(self, historical_data: pd.DataFrame, dimension: str) -> Dict[str, float]:
        """
        优化各维度内部子权重
        这里使用简单的因子IC（信息系数）方法
        """
        sub_weights = self.default_sub_weights[dimension].copy()
        
        # 计算每个子因子与未来收益的相关性
        # 实际使用时应替换为真实子因子数据
        # 这里简化处理
        
        return sub_weights
    
    def backtest_with_weights(self, weights: Dict[str, float], 
                              historical_data: pd.DataFrame) -> BacktestResult:
        """
        使用给定权重进行回测
        """
        # 计算加权评分
        combined_scores = (
            weights['industry_chain'] * historical_data['industry_chain_score'] +
            weights['fundamental'] * historical_data['fundamental_score'] +
            weights['technical'] * historical_data['technical_score']
        )
        
        # 交易信号
        signals = np.where(combined_scores > 50, 1, np.where(combined_scores < 50, -1, 0))
        
        # 计算收益
        strategy_returns = signals * historical_data['future_return']
        
        # 计算绩效指标
        total_return = (1 + strategy_returns).prod() - 1
        
        # 夏普比率
        excess_returns = strategy_returns - 0.0001
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0
        
        # 最大回撤
        cumulative = (1 + strategy_returns).cumprod()
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)
        
        # 胜率
        winning_trades = strategy_returns > 0
        win_rate = np.mean(winning_trades) if len(winning_trades) > 0 else 0
        
        # 盈亏比
        profits = strategy_returns[strategy_returns > 0]
        losses = -strategy_returns[strategy_returns < 0]
        profit_factor = np.sum(profits) / np.sum(losses) if len(losses) > 0 and np.sum(losses) > 0 else float('inf')
        
        return BacktestResult(
            weights=weights,
            total_return=float(total_return),
            sharpe_ratio=float(sharpe),
            max_drawdown=float(max_drawdown),
            win_rate=float(win_rate),
            profit_factor=float(profit_factor)
        )
    
    def grid_search_weights(self, historical_data: pd.DataFrame, 
                          grid_step: float = 0.05) -> Tuple[Dict[str, float], List[Dict]]:
        """
        网格搜索法寻找最优权重
        比单纯优化器更稳健，可以探索更多可能性
        """
        results = []
        
        # 生成网格
        for w1 in np.arange(0.2, 0.6, grid_step):
            for w2 in np.arange(0.2, 0.6, grid_step):
                w3 = 1 - w1 - w2
                if 0.2 <= w3 <= 0.6:
                    weights = {
                        'industry_chain': float(w1),
                        'fundamental': float(w2),
                        'technical': float(w3)
                    }
                    
                    # 回测
                    result = self.backtest_with_weights(weights, historical_data)
                    results.append({
                        'weights': weights,
                        'sharpe': result.sharpe_ratio,
                        'return': result.total_return,
                        'max_drawdown': result.max_drawdown
                    })
        
        # 按夏普比率排序
        results.sort(key=lambda x: x['sharpe'], reverse=True)
        
        return results[0]['weights'], results
    
    def compare_default_vs_optimized(self, historical_data: pd.DataFrame) -> Dict:
        """
        比较默认权重和优化权重的对比
        """
        # 优化权重
        optimized_weights = self.optimize_top_level_weights(historical_data)
        
        # 回测两者
        default_result = self.backtest_with_weights(self.default_weights, historical_data)
        optimized_result = self.backtest_with_weights(optimized_weights, historical_data)
        
        return {
            'default': {
                'weights': self.default_weights,
                'performance': {
                    'total_return': default_result.total_return,
                    'sharpe_ratio': default_result.sharpe_ratio,
                    'max_drawdown': default_result.max_drawdown,
                    'win_rate': default_result.win_rate
                }
            },
            'optimized': {
                'weights': optimized_weights,
                'performance': {
                    'total_return': optimized_result.total_return,
                    'sharpe_ratio': optimized_result.sharpe_ratio,
                    'max_drawdown': optimized_result.max_drawdown,
                    'win_rate': optimized_result.win_rate
                }
            },
            'improvement': {
                'return_improvement': optimized_result.total_return - default_result.total_return,
                'sharpe_improvement': optimized_result.sharpe_ratio - default_result.sharpe_ratio,
                'drawdown_improvement': optimized_result.max_drawdown - default_result.max_drawdown
            }
        }


class BayesianWeightOptimizer:
    """
    贝叶斯权重优化器
    使用贝叶斯方法进行权重优化，提供不确定性估计
    """
    
    def __init__(self):
        self.prior_mean = np.array([0.35, 0.30, 0.35])
        self.prior_std = np.array([0.1, 0.1, 0.1])
    
    def bayesian_update(self, historical_data: pd.DataFrame, n_samples: int = 1000):
        """
        贝叶斯更新权重
        """
        # 简化的贝叶斯采样
        # 实际使用可采用MCMC等更复杂的方法
        
        samples = []
        for _ in range(n_samples):
            # 从先验分布采样
            sample = self.prior_mean + np.random.randn(3) * self.prior_std
            
            # 确保权重有效
            sample = np.clip(sample, 0.1, 0.6)
            sample = sample / np.sum(sample)
            
            samples.append(sample)
        
        # 计算每个样本的表现
        performances = []
        for sample in samples:
            weights = {
                'industry_chain': sample[0],
                'fundamental': sample[1],
                'technical': sample[2]
            }
            
            combined_scores = (
                sample[0] * historical_data['industry_chain_score'] +
                               sample[1] * historical_data['fundamental_score'] +
                               sample[2] * historical_data['technical_score']
            )
            
            signals = np.where(combined_scores > 50, 1, np.where(combined_scores < 50, -1, 0))
            strategy_returns = signals * historical_data['future_return']
            
            sharpe = np.mean(strategy_returns) / np.std(strategy_returns) * np.sqrt(252) if np.std(strategy_returns) > 0 else 0
            
            performances.append(sharpe)
        
        # 选择表现最好的样本
        best_idx = np.argmax(performances)
        best_weights = samples[best_idx]
        
        return {
            'industry_chain': float(best_weights[0]),
            'fundamental': float(best_weights[1]),
            'technical': float(best_weights[2])
        }, np.percentile(performances, 5), np.percentile(performances, 95)


class WeightSaver:
    """权重保存和加载"""
    
    @staticmethod
    def save_weights(weights: Dict[str, float], filepath: str, 
                    metadata: Optional[Dict] = None):
        """保存权重到文件"""
        full_metadata = metadata or {}
        full_metadata['timestamp'] = pd.Timestamp.now().isoformat()
        data = {
            'weights': weights,
            'metadata': full_metadata
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_weights(filepath: str) -> Tuple[Dict[str, float], Dict]:
        """从文件加载权重"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['weights'], data.get('metadata', {})
