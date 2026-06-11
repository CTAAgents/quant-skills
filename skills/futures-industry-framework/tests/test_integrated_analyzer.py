"""
集成分析引擎测试
"""
import unittest
import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
    IntegratedAnalyzer,
    FundamentalMetrics,
    TechnicalMetrics,
    quick_analyze,
    create_sample_data,
    create_sample_metrics,
    IndustryChainMetrics
)


class TestDataClasses(unittest.TestCase):
    """测试数据类"""
    
    def test_fundamental_metrics(self):
        """测试基本面指标"""
        metrics = FundamentalMetrics(
            supply_demand_gap=0.15,
            inventory_change=-0.03,
            profit_margin=0.12,
            basis_structure=-0.2,
            historical_price_percentile=0.35
        )
        
        self.assertEqual(metrics.supply_demand_gap, 0.15)
        self.assertEqual(metrics.inventory_change, -0.03)
        self.assertEqual(metrics.profit_margin, 0.12)
        self.assertEqual(metrics.basis_structure, -0.2)
        self.assertEqual(metrics.historical_price_percentile, 0.35)
    
    def test_technical_metrics(self):
        """测试技术面指标"""
        metrics = TechnicalMetrics(
            trend_score=65,
            momentum_score=58,
            volatility_score=45,
            volume_score=60,
            pattern_score=55
        )
        
        self.assertEqual(metrics.trend_score, 65)
        self.assertEqual(metrics.momentum_score, 58)
        self.assertEqual(metrics.volatility_score, 45)
        self.assertEqual(metrics.volume_score, 60)
        self.assertEqual(metrics.pattern_score, 55)


class TestIntegratedAnalyzerInitialization(unittest.TestCase):
    """测试集成分析引擎初始化"""
    
    def test_default_initialization(self):
        """测试默认初始化"""
        analyzer = IntegratedAnalyzer()
        
        self.assertIsNotNone(analyzer.chain_analyzer)
        self.assertIsNotNone(analyzer.weight_optimizer)
        self.assertIsNotNone(analyzer.resonance_detector)
        self.assertIsNotNone(analyzer.weights)
    
    def test_initialization_with_custom_weights(self):
        """测试使用自定义权重初始化"""
        # 先创建并保存权重
        import tempfile
        from core import WeightSaver
        
        custom_weights = {
            'industry_chain': 0.4,
            'fundamental': 0.3,
            'technical': 0.3
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            WeightSaver.save_weights(custom_weights, temp_path)
            analyzer = IntegratedAnalyzer(weights_path=temp_path)
            self.assertEqual(analyzer.weights, custom_weights)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def test_initialization_with_nonexistent_weights(self):
        """测试使用不存在的权重文件初始化"""
        analyzer = IntegratedAnalyzer(weights_path='nonexistent.json')
        # 应该使用默认权重
        self.assertEqual(analyzer.weights, analyzer.weight_optimizer.default_weights)


class TestDataCreation(unittest.TestCase):
    """测试数据创建"""
    
    def test_create_sample_data(self):
        """测试创建示例数据"""
        chain_metrics, fund_metrics, tech_metrics = create_sample_data()
        
        self.assertIsNotNone(chain_metrics)
        self.assertIsNotNone(fund_metrics)
        self.assertIsNotNone(tech_metrics)


class TestFullAnalysis(unittest.TestCase):
    """测试完整分析流程"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IntegratedAnalyzer()
        self.chain_metrics, self.fund_metrics, self.tech_metrics = create_sample_data()
    
    def test_full_analysis(self):
        """测试完整分析"""
        result = self.analyzer.analyze(
            self.chain_metrics,
            self.fund_metrics,
            self.tech_metrics,
            "测试产业链"
        )
        
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.industry_chain_report)
        self.assertIsNotNone(result.fundamental_metrics)
        self.assertIsNotNone(result.technical_metrics)
        self.assertIsNotNone(result.resonance_signal)
        self.assertIsNotNone(result.trading_plan)
        self.assertIsNotNone(result.risk_warnings)
    
    def test_industry_chain_score(self):
        """测试产业链评分"""
        result = self.analyzer.analyze(
            self.chain_metrics,
            self.fund_metrics,
            self.tech_metrics
        )
        
        self.assertGreaterEqual(result.industry_chain_score, 0)
        self.assertLessEqual(result.industry_chain_score, 100)
    
    def test_fundamental_score(self):
        """测试基本面评分"""
        result = self.analyzer.analyze(
            self.chain_metrics,
            self.fund_metrics,
            self.tech_metrics
        )
        
        self.assertGreaterEqual(result.fundamental_score, 0)
        self.assertLessEqual(result.fundamental_score, 100)
    
    def test_technical_score(self):
        """测试技术面评分"""
        result = self.analyzer.analyze(
            self.chain_metrics,
            self.fund_metrics,
            self.tech_metrics
        )
        
        self.assertGreaterEqual(result.technical_score, 0)
        self.assertLessEqual(result.technical_score, 100)


class TestTradingPlan(unittest.TestCase):
    """测试交易计划"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IntegratedAnalyzer()
        self.chain_metrics, self.fund_metrics, self.tech_metrics = create_sample_data()
    
    def test_trading_plan_creation(self):
        """测试交易计划创建"""
        result = self.analyzer.analyze(
            self.chain_metrics,
            self.fund_metrics,
            self.tech_metrics
        )
        
        plan = result.trading_plan
        
        self.assertIn('core_logic', plan)
        self.assertIn('direction', plan)
        self.assertIn('position_size', plan)
        self.assertIn('stop_loss', plan)
        self.assertIn('take_profit_levels', plan)
        self.assertIn('recommendation', plan)
        self.assertIn('confidence', plan)
    
    def test_position_size_logic(self):
        """测试仓位大小逻辑"""
        # 创建一个强看涨的场景
        chain_metrics = create_sample_metrics()
        fund_metrics = FundamentalMetrics(0.3, -0.1, 0.2, -0.5, 0.2)
        tech_metrics = TechnicalMetrics(90, 85, 70, 80, 75)
        
        result = self.analyzer.analyze(chain_metrics, fund_metrics, tech_metrics)
        plan = result.trading_plan
        
        self.assertGreaterEqual(plan['position_size'], 0)
        self.assertLessEqual(plan['position_size'], 0.3)


class TestRiskWarnings(unittest.TestCase):
    """测试风险提示"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IntegratedAnalyzer()
        self.chain_metrics, self.fund_metrics, self.tech_metrics = create_sample_data()
    
    def test_risk_warnings_creation(self):
        """测试风险提示创建"""
        result = self.analyzer.analyze(
            self.chain_metrics,
            self.fund_metrics,
            self.tech_metrics
        )
        
        self.assertIsInstance(result.risk_warnings, list)


class TestReportGeneration(unittest.TestCase):
    """测试报告生成"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IntegratedAnalyzer()
        self.chain_metrics, self.fund_metrics, self.tech_metrics = create_sample_data()
    
    def test_generate_report(self):
        """测试生成报告"""
        result = self.analyzer.analyze(
            self.chain_metrics,
            self.fund_metrics,
            self.tech_metrics
        )
        
        report = self.analyzer.generate_report(result)
        
        self.assertIsNotNone(report)
        self.assertIn('产业链定性分析', report)
        self.assertIn('基本面量化分析', report)
        self.assertIn('技术面择时分析', report)
        self.assertIn('三层共振检测', report)
        self.assertIn('交易计划', report)
        self.assertIn('风险提示', report)


class TestQuickAnalyze(unittest.TestCase):
    """测试快速分析"""
    
    def test_quick_analyze(self):
        """测试快速分析"""
        chain_metrics, fund_metrics, tech_metrics = create_sample_data()
        
        report = quick_analyze(chain_metrics, fund_metrics, tech_metrics, "快速测试")
        
        self.assertIsNotNone(report)
        self.assertGreater(len(report), 0)


class TestWeightOptimization(unittest.TestCase):
    """测试权重优化"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IntegratedAnalyzer()
        self.weight_optimizer = self.analyzer.weight_optimizer
        self.historical_data = self.weight_optimizer.generate_synthetic_historical_data(n_periods=100)
    
    def test_optimize_weights(self):
        """测试优化权重"""
        comparison = self.analyzer.optimize_weights(self.historical_data)
        
        self.assertIsNotNone(comparison)
        self.assertIn('default', comparison)
        self.assertIn('optimized', comparison)
        self.assertIn('improvement', comparison)
        
        # 验证权重已更新
        self.assertEqual(self.analyzer.weights, comparison['optimized']['weights'])


class TestDifferentScenarios(unittest.TestCase):
    """测试不同场景"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IntegratedAnalyzer()
    
    def test_bullish_scenario(self):
        """测试看涨场景"""
        chain_metrics = create_sample_metrics()
        fund_metrics = FundamentalMetrics(0.3, -0.1, 0.2, -0.5, 0.2)
        tech_metrics = TechnicalMetrics(90, 85, 70, 80, 75)
        
        result = self.analyzer.analyze(chain_metrics, fund_metrics, tech_metrics)
        
        # 共振信号应该看涨
        self.assertIn('多', result.resonance_signal.direction.value)
    
    def test_bearish_scenario(self):
        """测试看跌场景"""
        # 创建明显看跌的产业链指标
        chain_metrics = IndustryChainMetrics(
            inventory_change_rate=0.08,  # 库存增加
            inventory_history_percentile=0.85,
            inventory_destocking_speed=0.1,
            price_change_rate=-0.06,
            upstream_profit_margin=-0.03,
            midstream_profit_margin=-0.07,
            downstream_profit_margin=-0.1,
            profit_conduction_index=0.1,
            operating_rate=0.45,
            operating_rate_change=-0.06,
            enterprise_hedging_intensity=0.9,
            supply_change=0.1,
            demand_change=-0.08,
            supply_demand_gap=-0.1,
            basis=60,
            basis_history_percentile=0.9
        )
        fund_metrics = FundamentalMetrics(-0.3, 0.1, -0.2, 0.5, 0.8)
        tech_metrics = TechnicalMetrics(10, 15, 30, 20, 25)
        
        result = self.analyzer.analyze(chain_metrics, fund_metrics, tech_metrics)
        
        # 共振信号应该看跌
        self.assertIn('空', result.resonance_signal.direction.value)
    
    def test_neutral_scenario(self):
        """测试中性场景"""
        chain_metrics = create_sample_metrics()
        fund_metrics = FundamentalMetrics(0, 0, 0.1, 0, 0.5)
        tech_metrics = TechnicalMetrics(50, 50, 50, 50, 50)
        
        result = self.analyzer.analyze(chain_metrics, fund_metrics, tech_metrics)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IntegratedAnalyzer()
    
    def test_extreme_scores(self):
        """测试极端分数"""
        chain_metrics = create_sample_metrics()
        fund_metrics = FundamentalMetrics(1, -1, 1, -1, 1)
        tech_metrics = TechnicalMetrics(100, 100, 100, 100, 100)
        
        result = self.analyzer.analyze(chain_metrics, fund_metrics, tech_metrics)
        
        # 分数应该在0-100之间
        self.assertGreaterEqual(result.industry_chain_score, 0)
        self.assertLessEqual(result.industry_chain_score, 100)
        self.assertGreaterEqual(result.fundamental_score, 0)
        self.assertLessEqual(result.fundamental_score, 100)
        self.assertGreaterEqual(result.technical_score, 0)
        self.assertLessEqual(result.technical_score, 100)


if __name__ == '__main__':
    unittest.main()
