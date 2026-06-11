"""
权重优化模块测试
"""
import unittest
import sys
import os
import tempfile
import json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
    WeightOptimizer,
    BayesianWeightOptimizer,
    WeightSaver,
    BacktestResult
)


class TestWeightOptimizerInitialization(unittest.TestCase):
    """测试权重优化器初始化"""
    
    def test_default_weights(self):
        """测试默认权重"""
        optimizer = WeightOptimizer()
        self.assertIn('industry_chain', optimizer.default_weights)
        self.assertIn('fundamental', optimizer.default_weights)
        self.assertIn('technical', optimizer.default_weights)
        self.assertEqual(
            sum(optimizer.default_weights.values()),
            1.0
        )
    
    def test_default_sub_weights(self):
        """测试默认子权重"""
        optimizer = WeightOptimizer()
        self.assertIn('industry_chain', optimizer.default_sub_weights)
        self.assertIn('fundamental', optimizer.default_sub_weights)
        self.assertIn('technical', optimizer.default_sub_weights)


class TestHistoricalDataGeneration(unittest.TestCase):
    """测试历史数据生成"""
    
    def setUp(self):
        """测试前初始化"""
        self.optimizer = WeightOptimizer()
    
    def test_generate_synthetic_data(self):
        """测试生成合成数据"""
        n_periods = 100
        df = self.optimizer.generate_synthetic_historical_data(n_periods)
        
        self.assertIsNotNone(df)
        self.assertEqual(len(df), n_periods)
        self.assertIn('industry_chain_score', df.columns)
        self.assertIn('fundamental_score', df.columns)
        self.assertIn('technical_score', df.columns)
        self.assertIn('future_return', df.columns)
        
        # 验证评分范围
        self.assertTrue((df['industry_chain_score'] >= 0).all())
        self.assertTrue((df['industry_chain_score'] <= 100).all())


class TestWeightOptimization(unittest.TestCase):
    """测试权重优化"""
    
    def setUp(self):
        """测试前初始化"""
        self.optimizer = WeightOptimizer()
        self.historical_data = self.optimizer.generate_synthetic_historical_data(n_periods=200)
    
    def test_optimize_top_level_weights(self):
        """测试顶层权重优化"""
        optimal_weights = self.optimizer.optimize_top_level_weights(self.historical_data)
        
        self.assertIsNotNone(optimal_weights)
        self.assertIn('industry_chain', optimal_weights)
        self.assertIn('fundamental', optimal_weights)
        self.assertIn('technical', optimal_weights)
        self.assertAlmostEqual(
            sum(optimal_weights.values()),
            1.0,
            places=6
        )
        # 验证权重在合理范围内
        for weight in optimal_weights.values():
            self.assertGreaterEqual(weight, 0.1)
            self.assertLessEqual(weight, 0.6)
    
    def test_optimize_sub_weights(self):
        """测试子权重优化"""
        sub_weights = self.optimizer.optimize_sub_weights(
            self.historical_data,
            'industry_chain'
        )
        
        self.assertIsNotNone(sub_weights)
        # 子权重应该和默认子权重结构相同
        self.assertEqual(
            set(sub_weights.keys()),
            set(self.optimizer.default_sub_weights['industry_chain'].keys())
        )


class TestBacktesting(unittest.TestCase):
    """测试回测功能"""
    
    def setUp(self):
        """测试前初始化"""
        self.optimizer = WeightOptimizer()
        self.historical_data = self.optimizer.generate_synthetic_historical_data(n_periods=150)
    
    def test_backtest_with_weights(self):
        """测试使用权重回测"""
        weights = {
            'industry_chain': 0.4,
            'fundamental': 0.3,
            'technical': 0.3
        }
        
        result = self.optimizer.backtest_with_weights(weights, self.historical_data)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, BacktestResult)
        self.assertIsNotNone(result.total_return)
        self.assertIsNotNone(result.sharpe_ratio)
        self.assertIsNotNone(result.max_drawdown)
        self.assertIsNotNone(result.win_rate)
        self.assertIsNotNone(result.profit_factor)
        self.assertEqual(result.weights, weights)
    
    def test_compare_default_vs_optimized(self):
        """测试对比默认权重和优化权重"""
        comparison = self.optimizer.compare_default_vs_optimized(self.historical_data)
        
        self.assertIsNotNone(comparison)
        self.assertIn('default', comparison)
        self.assertIn('optimized', comparison)
        self.assertIn('improvement', comparison)
        
        # 验证默认权重的结果
        self.assertIn('weights', comparison['default'])
        self.assertIn('performance', comparison['default'])
        
        # 验证优化权重的结果
        self.assertIn('weights', comparison['optimized'])
        self.assertIn('performance', comparison['optimized'])


class TestGridSearch(unittest.TestCase):
    """测试网格搜索"""
    
    def setUp(self):
        """测试前初始化"""
        self.optimizer = WeightOptimizer()
        self.historical_data = self.optimizer.generate_synthetic_historical_data(n_periods=100)
    
    def test_grid_search_weights(self):
        """测试网格搜索权重"""
        best_weights, all_results = self.optimizer.grid_search_weights(
            self.historical_data,
            grid_step=0.1
        )
        
        self.assertIsNotNone(best_weights)
        self.assertIsNotNone(all_results)
        self.assertGreater(len(all_results), 0)
        
        # 最佳权重应该是第一个结果的权重
        self.assertEqual(best_weights, all_results[0]['weights'])


class TestBayesianOptimizer(unittest.TestCase):
    """测试贝叶斯优化器"""
    
    def test_bayesian_optimizer_initialization(self):
        """测试贝叶斯优化器初始化"""
        optimizer = BayesianWeightOptimizer()
        self.assertIsNotNone(optimizer)
    
    def test_bayesian_update(self):
        """测试贝叶斯更新"""
        optimizer = BayesianWeightOptimizer()
        weight_optimizer = WeightOptimizer()
        historical_data = weight_optimizer.generate_synthetic_historical_data(n_periods=100)
        
        optimal_weights, lower_percentile, upper_percentile = optimizer.bayesian_update(
            historical_data,
            n_samples=50
        )
        
        self.assertIsNotNone(optimal_weights)
        self.assertIsInstance(lower_percentile, float)
        self.assertIsInstance(upper_percentile, float)
        self.assertLessEqual(lower_percentile, upper_percentile)
        
        # 验证权重
        self.assertIn('industry_chain', optimal_weights)
        self.assertIn('fundamental', optimal_weights)
        self.assertIn('technical', optimal_weights)


class TestWeightSaver(unittest.TestCase):
    """测试权重保存和加载"""
    
    def test_save_and_load_weights(self):
        """测试保存和加载权重"""
        weights = {
            'industry_chain': 0.35,
            'fundamental': 0.30,
            'technical': 0.35
        }
        metadata = {
            'test': 'example',
            'version': '1.0'
        }
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # 保存权重
            WeightSaver.save_weights(weights, temp_path, metadata)
            self.assertTrue(os.path.exists(temp_path))
            
            # 加载权重
            loaded_weights, loaded_metadata = WeightSaver.load_weights(temp_path)
            
            # 验证
            self.assertEqual(loaded_weights, weights)
            self.assertEqual(loaded_metadata.get('test'), 'example')
            self.assertIn('timestamp', loaded_metadata)
            
        finally:
            # 清理
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def test_save_weights_without_metadata(self):
        """测试不保存元数据"""
        weights = {
            'industry_chain': 0.4,
            'fundamental': 0.3,
            'technical': 0.3
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            WeightSaver.save_weights(weights, temp_path)
            loaded_weights, loaded_metadata = WeightSaver.load_weights(temp_path)
            
            self.assertEqual(loaded_weights, weights)
            self.assertIn('timestamp', loaded_metadata)  # timestamp 总是存在
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""
    
    def setUp(self):
        """测试前初始化"""
        self.optimizer = WeightOptimizer()
    
    def test_minimal_historical_data(self):
        """测试最小化历史数据"""
        df = self.optimizer.generate_synthetic_historical_data(n_periods=10)
        self.assertEqual(len(df), 10)
    
    def test_objective_function(self):
        """测试目标函数"""
        weights = np.array([0.35, 0.3, 0.35])
        df = self.optimizer.generate_synthetic_historical_data(n_periods=50)
        
        # 目标函数应该返回一个可以被最小化的值
        result = self.optimizer.objective_function(weights, df)
        self.assertIsInstance(result, float)
    
    def test_different_weight_combinations(self):
        """测试不同的权重组合"""
        test_weights = [
            {'industry_chain': 0.2, 'fundamental': 0.2, 'technical': 0.6},
            {'industry_chain': 0.5, 'fundamental': 0.25, 'technical': 0.25},
            {'industry_chain': 0.33, 'fundamental': 0.33, 'technical': 0.34},
        ]
        
        df = self.optimizer.generate_synthetic_historical_data(n_periods=100)
        
        for weights in test_weights:
            result = self.optimizer.backtest_with_weights(weights, df)
            self.assertIsNotNone(result)


class TestBacktestResult(unittest.TestCase):
    """测试回测结果类"""
    
    def test_backtest_result_creation(self):
        """测试创建回测结果"""
        result = BacktestResult(
            weights={'industry_chain': 0.35, 'fundamental': 0.30, 'technical': 0.35},
            total_return=0.15,
            sharpe_ratio=1.5,
            max_drawdown=-0.10,
            win_rate=0.55,
            profit_factor=1.2
        )
        
        self.assertEqual(result.total_return, 0.15)
        self.assertEqual(result.sharpe_ratio, 1.5)
        self.assertEqual(result.max_drawdown, -0.10)
        self.assertEqual(result.win_rate, 0.55)
        self.assertEqual(result.profit_factor, 1.2)


if __name__ == '__main__':
    unittest.main()
