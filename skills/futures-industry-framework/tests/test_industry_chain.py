"""
产业链标准化模块测试
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
    IndustryChainStandardAnalyzer,
    IndustryChainMetrics,
    InventoryCycle,
    ProfitStructure,
    create_sample_metrics
)


class TestIndustryChainMetrics(unittest.TestCase):
    """测试产业链指标类"""
    
    def test_create_metrics(self):
        """测试创建指标实例"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=-0.03,
            inventory_history_percentile=0.35,
            inventory_destocking_speed=0.8,
            price_change_rate=0.02,
            upstream_profit_margin=0.12,
            midstream_profit_margin=0.08,
            downstream_profit_margin=0.06,
            profit_conduction_index=0.6,
            operating_rate=0.75,
            operating_rate_change=0.01,
            enterprise_hedging_intensity=0.5,
            supply_change=-0.02,
            demand_change=0.04,
            supply_demand_gap=0.03,
            basis=-30,
            basis_history_percentile=0.25
        )
        
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.inventory_change_rate, -0.03)
        self.assertEqual(metrics.inventory_history_percentile, 0.35)
    
    def test_create_sample_metrics(self):
        """测试创建示例指标"""
        metrics = create_sample_metrics()
        self.assertIsNotNone(metrics)


class TestInventoryCycleDetermination(unittest.TestCase):
    """测试库存周期判定"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IndustryChainStandardAnalyzer()
    
    def test_active_destocking(self):
        """测试主动去库判定"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=-0.06,  # 库存快速下降
            inventory_history_percentile=0.3,
            inventory_destocking_speed=0.9,
            price_change_rate=-0.04,  # 价格下跌
            upstream_profit_margin=0.1,
            midstream_profit_margin=0.05,
            downstream_profit_margin=0.02,
            profit_conduction_index=0.3,
            operating_rate=0.6,  # 低开工
            operating_rate_change=-0.03,  # 开工下降
            enterprise_hedging_intensity=0.7,
            supply_change=-0.05,
            demand_change=-0.03,
            supply_demand_gap=-0.02,
            basis=20,
            basis_history_percentile=0.7
        )
        
        cycle, confidence = self.analyzer.determine_inventory_cycle(metrics)
        self.assertEqual(cycle, InventoryCycle.ACTIVE_DESTOCKING)
        self.assertGreater(confidence, 0.5)
    
    def test_passive_destocking(self):
        """测试被动去库判定"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=-0.04,
            inventory_history_percentile=0.2,
            inventory_destocking_speed=0.7,
            price_change_rate=0.05,  # 价格上涨
            upstream_profit_margin=0.15,
            midstream_profit_margin=0.12,
            downstream_profit_margin=0.08,
            profit_conduction_index=0.8,
            operating_rate=0.85,  # 高开工
            operating_rate_change=0.03,  # 开工上升
            enterprise_hedging_intensity=0.4,
            supply_change=-0.02,
            demand_change=0.08,
            supply_demand_gap=0.06,
            basis=-50,
            basis_history_percentile=0.1
        )
        
        cycle, confidence = self.analyzer.determine_inventory_cycle(metrics)
        self.assertEqual(cycle, InventoryCycle.PASSIVE_DESTOCKING)
    
    def test_active_restocking(self):
        """测试主动补库判定"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=0.06,  # 库存上升
            inventory_history_percentile=0.4,
            inventory_destocking_speed=0.2,
            price_change_rate=0.04,  # 价格上涨
            upstream_profit_margin=0.18,
            midstream_profit_margin=0.15,
            downstream_profit_margin=0.12,
            profit_conduction_index=0.9,
            operating_rate=0.9,
            operating_rate_change=0.05,
            enterprise_hedging_intensity=0.3,
            supply_change=0.05,
            demand_change=0.1,
            supply_demand_gap=0.08,
            basis=-40,
            basis_history_percentile=0.15
        )
        
        cycle, confidence = self.analyzer.determine_inventory_cycle(metrics)
        self.assertEqual(cycle, InventoryCycle.ACTIVE_RESTOCKING)
    
    def test_passive_restocking(self):
        """测试被动补库判定"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=0.07,  # 库存上升
            inventory_history_percentile=0.8,
            inventory_destocking_speed=0.1,
            price_change_rate=-0.05,  # 价格下跌
            upstream_profit_margin=0.02,
            midstream_profit_margin=-0.03,
            downstream_profit_margin=-0.05,
            profit_conduction_index=0.1,
            operating_rate=0.55,  # 低开工
            operating_rate_change=-0.04,  # 开工下降
            enterprise_hedging_intensity=0.9,
            supply_change=0.1,
            demand_change=-0.06,
            supply_demand_gap=-0.07,
            basis=60,
            basis_history_percentile=0.9
        )
        
        cycle, confidence = self.analyzer.determine_inventory_cycle(metrics)
        self.assertEqual(cycle, InventoryCycle.PASSIVE_RESTOCKING)


class TestProfitStructure(unittest.TestCase):
    """测试利润结构判定"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IndustryChainStandardAnalyzer()
    
    def test_upstream_profit(self):
        """测试上游盈利"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=-0.02,
            inventory_history_percentile=0.3,
            inventory_destocking_speed=0.6,
            price_change_rate=0.02,
            upstream_profit_margin=0.2,  # 上游高利润
            midstream_profit_margin=0.05,
            downstream_profit_margin=0.03,
            profit_conduction_index=0.4,
            operating_rate=0.75,
            operating_rate_change=0.01,
            enterprise_hedging_intensity=0.5,
            supply_change=-0.03,
            demand_change=0.02,
            supply_demand_gap=0.02,
            basis=-10,
            basis_history_percentile=0.4
        )
        
        structure, shares = self.analyzer.determine_profit_structure(metrics)
        self.assertEqual(structure, ProfitStructure.UPSTREAM_PROFIT)
    
    def test_midstream_profit(self):
        """测试中游盈利"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=-0.01,
            inventory_history_percentile=0.4,
            inventory_destocking_speed=0.5,
            price_change_rate=0.01,
            upstream_profit_margin=0.05,
            midstream_profit_margin=0.18,  # 中游高利润
            downstream_profit_margin=0.04,
            profit_conduction_index=0.6,
            operating_rate=0.8,
            operating_rate_change=0.02,
            enterprise_hedging_intensity=0.45,
            supply_change=0.01,
            demand_change=0.03,
            supply_demand_gap=0.03,
            basis=-15,
            basis_history_percentile=0.35
        )
        
        structure, shares = self.analyzer.determine_profit_structure(metrics)
        self.assertEqual(structure, ProfitStructure.MIDSTREAM_PROFIT)
    
    def test_downstream_profit(self):
        """测试下游盈利"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=-0.01,
            inventory_history_percentile=0.5,
            inventory_destocking_speed=0.4,
            price_change_rate=0.02,
            upstream_profit_margin=0.03,
            midstream_profit_margin=0.05,
            downstream_profit_margin=0.16,  # 下游高利润
            profit_conduction_index=0.7,
            operating_rate=0.82,
            operating_rate_change=0.03,
            enterprise_hedging_intensity=0.4,
            supply_change=0.02,
            demand_change=0.06,
            supply_demand_gap=0.04,
            basis=-20,
            basis_history_percentile=0.3
        )
        
        structure, shares = self.analyzer.determine_profit_structure(metrics)
        self.assertEqual(structure, ProfitStructure.DOWNSTREAM_PROFIT)
    
    def test_full_chain_loss(self):
        """测试全链亏损"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=0.05,
            inventory_history_percentile=0.8,
            inventory_destocking_speed=0.1,
            price_change_rate=-0.04,
            upstream_profit_margin=-0.03,
            midstream_profit_margin=-0.07,
            downstream_profit_margin=-0.1,
            profit_conduction_index=0.1,
            operating_rate=0.5,
            operating_rate_change=-0.03,
            enterprise_hedging_intensity=0.9,
            supply_change=0.05,
            demand_change=-0.06,
            supply_demand_gap=-0.07,
            basis=50,
            basis_history_percentile=0.85
        )
        
        structure, shares = self.analyzer.determine_profit_structure(metrics)
        self.assertEqual(structure, ProfitStructure.FULL_CHAIN_LOSS)
    
    def test_balanced_profit(self):
        """测试利润均衡"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=-0.02,
            inventory_history_percentile=0.4,
            inventory_destocking_speed=0.5,
            price_change_rate=0.01,
            upstream_profit_margin=0.08,
            midstream_profit_margin=0.07,
            downstream_profit_margin=0.06,
            profit_conduction_index=0.7,
            operating_rate=0.75,
            operating_rate_change=0.01,
            enterprise_hedging_intensity=0.5,
            supply_change=0.01,
            demand_change=0.02,
            supply_demand_gap=0.01,
            basis=-5,
            basis_history_percentile=0.5
        )
        
        structure, shares = self.analyzer.determine_profit_structure(metrics)
        self.assertEqual(structure, ProfitStructure.BALANCED)


class TestIndustryChainScoring(unittest.TestCase):
    """测试产业链评分"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IndustryChainStandardAnalyzer()
    
    def test_calculate_bullish_score(self):
        """测试看涨场景评分"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=-0.05,
            inventory_history_percentile=0.15,
            inventory_destocking_speed=0.9,
            price_change_rate=0.04,
            upstream_profit_margin=0.15,
            midstream_profit_margin=0.12,
            downstream_profit_margin=0.08,
            profit_conduction_index=0.85,
            operating_rate=0.88,
            operating_rate_change=0.04,
            enterprise_hedging_intensity=0.3,
            supply_change=-0.04,
            demand_change=0.08,
            supply_demand_gap=0.07,
            basis=-45,
            basis_history_percentile=0.1
        )
        
        total_score, dimension_scores = self.analyzer.calculate_industry_chain_score(metrics)
        self.assertIsNotNone(total_score)
        self.assertIsNotNone(dimension_scores)
        self.assertIn('inventory', dimension_scores)
        self.assertIn('profit', dimension_scores)
        self.assertIn('behavior', dimension_scores)
        self.assertIn('supply_demand', dimension_scores)
        self.assertIn('basis', dimension_scores)
        self.assertGreater(total_score, 50)  # 看涨场景应该高分
    
    def test_calculate_bearish_score(self):
        """测试看跌场景评分"""
        metrics = IndustryChainMetrics(
            inventory_change_rate=0.08,
            inventory_history_percentile=0.9,
            inventory_destocking_speed=0.05,
            price_change_rate=-0.06,
            upstream_profit_margin=-0.03,
            midstream_profit_margin=-0.07,
            downstream_profit_margin=-0.1,
            profit_conduction_index=0.1,
            operating_rate=0.45,
            operating_rate_change=-0.06,
            enterprise_hedging_intensity=0.95,
            supply_change=0.1,
            demand_change=-0.08,
            supply_demand_gap=-0.1,
            basis=80,
            basis_history_percentile=0.95
        )
        
        total_score, dimension_scores = self.analyzer.calculate_industry_chain_score(metrics)
        self.assertLess(total_score, 50)  # 看跌场景应该低分


class TestAnalysisReport(unittest.TestCase):
    """测试分析报告生成"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = IndustryChainStandardAnalyzer()
    
    def test_generate_report(self):
        """测试生成完整报告"""
        metrics = create_sample_metrics()
        report = self.analyzer.generate_standard_analysis_report(
            metrics, "测试产业链"
        )
        
        self.assertIsNotNone(report)
        self.assertEqual(report['chain_name'], "测试产业链")
        self.assertIn('inventory_cycle', report)
        self.assertIn('profit_structure', report)
        self.assertIn('trend', report)
        self.assertIn('score', report)


class TestEnumTypes(unittest.TestCase):
    """测试枚举类型"""
    
    def test_inventory_cycle_enum(self):
        """测试库存周期枚举"""
        self.assertEqual(InventoryCycle.ACTIVE_DESTOCKING.value, '主动去库')
        self.assertEqual(InventoryCycle.PASSIVE_DESTOCKING.value, '被动去库')
        self.assertEqual(InventoryCycle.ACTIVE_RESTOCKING.value, '主动补库')
        self.assertEqual(InventoryCycle.PASSIVE_RESTOCKING.value, '被动补库')
    
    def test_profit_structure_enum(self):
        """测试利润结构枚举"""
        self.assertEqual(ProfitStructure.UPSTREAM_PROFIT.value, '上游盈利')
        self.assertEqual(ProfitStructure.MIDSTREAM_PROFIT.value, '中游盈利')
        self.assertEqual(ProfitStructure.DOWNSTREAM_PROFIT.value, '下游盈利')
        self.assertEqual(ProfitStructure.FULL_CHAIN_LOSS.value, '全链亏损')
        self.assertEqual(ProfitStructure.BALANCED.value, '利润均衡')


if __name__ == '__main__':
    unittest.main()
