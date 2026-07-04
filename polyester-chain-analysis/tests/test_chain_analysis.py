#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
产业链分析模块单元测试 v1.0.0

测试用例：
1. 成本传导分析测试
2. 供需平衡分析测试
3. 库存周期分析测试
4. 利润分配分析测试
5. 完整流程测试
"""

import pytest
import sys
from pathlib import Path

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from chain_analysis import (
    analyze_cost_transmission,
    analyze_supply_demand,
    analyze_inventory_cycle,
    analyze_profit_distribution,
    run_chain_analysis,
    CostTransmission,
    SupplyDemandBalance,
    InventoryCycle,
    ProfitDistribution
)


class TestCostTransmission:
    """成本传导分析测试"""
    
    def test_normal_scenario(self):
        """测试正常场景"""
        data = {
            'crude_price': 75,
            'naphtha_price': 600,
            'px_price': 900,
            'pta_price': 6000
        }
        result = analyze_cost_transmission(data)
        
        assert isinstance(result, CostTransmission)
        assert result.pxn == 300  # 900 - 600
        assert result.cost_efficiency in ["高", "中", "低"]
        assert result.cost_driver in ["原油", "PX", "PTA"]
    
    def test_high_pxn(self):
        """测试高PXN场景"""
        data = {
            'crude_price': 75,
            'naphtha_price': 500,
            'px_price': 900,
            'pta_price': 6000
        }
        result = analyze_cost_transmission(data)
        
        assert result.pxn == 400  # 900 - 500
        assert result.cost_driver == "PTA"  # PTA价差最大
    
    def test_low_pxn(self):
        """测试低PXN场景"""
        data = {
            'crude_price': 75,
            'naphtha_price': 700,
            'px_price': 900,
            'pta_price': 6000
        }
        result = analyze_cost_transmission(data)
        
        assert result.pxn == 200  # 900 - 700
        assert result.cost_driver == "PTA"  # PTA价差最大


class TestSupplyDemand:
    """供需平衡分析测试"""
    
    def test_tight_supply(self):
        """测试供应紧张场景"""
        data = {
            'px_operation_rate': 70,
            'pta_operation_rate': 65,
            'meg_operation_rate': 60,
            'pf_operation_rate': 75,
            'pr_operation_rate': 70,
            'polyester_load': 88
        }
        result = analyze_supply_demand(data)
        
        assert isinstance(result, SupplyDemandBalance)
        assert result.px_supply == "紧张"
        assert result.pta_supply == "紧张"
        assert result.meg_supply == "紧张"
        assert result.polyester_demand == "旺盛"
        assert result.overall_balance == "供不应求"
    
    def test_loose_supply(self):
        """测试供应宽松场景"""
        data = {
            'px_operation_rate': 90,
            'pta_operation_rate': 88,
            'meg_operation_rate': 80,
            'pf_operation_rate': 92,
            'pr_operation_rate': 88,
            'polyester_load': 78
        }
        result = analyze_supply_demand(data)
        
        assert result.px_supply == "宽松"
        assert result.pta_supply == "宽松"
        assert result.polyester_demand == "疲软"
        assert result.overall_balance == "供过于求"
    
    def test_balanced_scenario(self):
        """测试平衡场景"""
        data = {
            'px_operation_rate': 80,
            'pta_operation_rate': 80,
            'meg_operation_rate': 70,
            'pf_operation_rate': 85,
            'pr_operation_rate': 80,
            'polyester_load': 83
        }
        result = analyze_supply_demand(data)
        
        assert result.px_supply == "平衡"
        assert result.pta_supply == "平衡"
        assert result.polyester_demand == "平稳"
        assert result.overall_balance == "平衡"


class TestInventoryCycle:
    """库存周期分析测试"""
    
    def test_inventory_buildup(self):
        """测试累库场景"""
        data = {
            'pta_inventory_change': 10,
            'meg_port_inventory': 110,
            'pf_inventory_change': 5,
            'pr_inventory_change': 3,
            'ta_near_far_spread': -100,
            'polyester_load': 78
        }
        result = analyze_inventory_cycle(data)
        
        assert isinstance(result, InventoryCycle)
        assert result.pta_inventory == "累库"
        assert result.meg_inventory == "累库"
        assert result.term_structure == "Contango"
        assert result.cycle_phase == "被动补库"
    
    def test_inventory_drawdown(self):
        """测试去库场景"""
        data = {
            'pta_inventory_change': -10,
            'meg_port_inventory': 75,
            'pf_inventory_change': -5,
            'pr_inventory_change': -2,
            'ta_near_far_spread': 150,
            'polyester_load': 88
        }
        result = analyze_inventory_cycle(data)
        
        assert result.pta_inventory == "去库"
        assert result.meg_inventory == "去库"
        assert result.term_structure == "Back"
        assert result.cycle_phase == "被动去库"
    
    def test_balanced_inventory(self):
        """测试平衡库存场景"""
        data = {
            'pta_inventory_change': 0,
            'meg_port_inventory': 85,
            'pf_inventory_change': 0,
            'pr_inventory_change': 0,
            'ta_near_far_spread': 0,
            'polyester_load': 83
        }
        result = analyze_inventory_cycle(data)
        
        assert result.pta_inventory == "平衡"
        assert result.meg_inventory == "平衡"
        assert result.term_structure == "平坦"
        assert result.cycle_phase == "过渡期"


class TestProfitDistribution:
    """利润分配分析测试"""
    
    def test_high_pxn(self):
        """测试高PXN场景"""
        data = {
            'pxn': 450,
            'pta_processing_fee': 400,
            'pf_processing_fee': 900,
            'pr_processing_fee': 400,
            'pta_profit_change': 50,
            'pf_profit_change': 30
        }
        result = analyze_profit_distribution(data)
        
        assert isinstance(result, ProfitDistribution)
        assert result.pxn_level == "高"
        assert result.profit_center == "PX"
        assert result.profit_trend == "扩张"
    
    def test_high_pta_profit(self):
        """测试高PTA利润场景"""
        data = {
            'pxn': 300,
            'pta_processing_fee': 650,
            'pf_processing_fee': 900,
            'pr_processing_fee': 400,
            'pta_profit_change': 50,
            'pf_profit_change': 30
        }
        result = analyze_profit_distribution(data)
        
        assert result.pta_profit_level == "高"
        assert result.profit_center == "PTA"
    
    def test_low_pf_profit(self):
        """测试低PF利润场景"""
        data = {
            'pxn': 300,
            'pta_processing_fee': 400,
            'pf_processing_fee': 750,
            'pr_processing_fee': 400,
            'pta_profit_change': -20,
            'pf_profit_change': -30
        }
        result = analyze_profit_distribution(data)
        
        assert result.pf_profit_level == "低"
        assert result.profit_trend == "压缩"
    
    def test_balanced_profit(self):
        """测试平衡利润场景"""
        data = {
            'pxn': 300,
            'pta_processing_fee': 400,
            'pf_processing_fee': 900,
            'pr_processing_fee': 400,
            'pta_profit_change': 0,
            'pf_profit_change': 0
        }
        result = analyze_profit_distribution(data)
        
        assert result.pxn_level == "中"
        assert result.pta_profit_level == "中"
        assert result.profit_center == "平衡"
        assert result.profit_trend == "稳定"


class TestRunChainAnalysis:
    """产业链分析完整流程测试"""
    
    def test_full_pipeline(self):
        """测试完整流程"""
        data = {
            'crude_price': 75,
            'naphtha_price': 600,
            'px_price': 900,
            'pta_price': 6000,
            'px_operation_rate': 75,
            'pta_operation_rate': 70,
            'meg_operation_rate': 65,
            'pf_operation_rate': 80,
            'pr_operation_rate': 75,
            'polyester_load': 83,
            'pta_inventory_change': -8,
            'meg_port_inventory': 82,
            'pf_inventory_change': -2,
            'pr_inventory_change': 1,
            'ta_near_far_spread': 150,
            'pxn': 350,
            'pta_processing_fee': 450,
            'pf_processing_fee': 850,
            'pr_processing_fee': 400,
            'pta_profit_change': 50,
            'pf_profit_change': 30
        }
        result = run_chain_analysis(data)
        
        assert 'cost_transmission' in result
        assert 'supply_demand' in result
        assert 'inventory_cycle' in result
        assert 'profit_distribution' in result
        assert 'summary' in result
        
        assert isinstance(result['cost_transmission'], CostTransmission)
        assert isinstance(result['supply_demand'], SupplyDemandBalance)
        assert isinstance(result['inventory_cycle'], InventoryCycle)
        assert isinstance(result['profit_distribution'], ProfitDistribution)
        
        assert result['summary']['cost_driver'] in ["原油", "PX", "PTA"]
        assert result['summary']['overall_balance'] in ["供过于求", "平衡", "供不应求"]
        assert result['summary']['cycle_phase'] in ["主动补库", "被动补库", "主动去库", "被动去库", "过渡期"]
        assert result['summary']['profit_center'] in ["PX", "PTA", "PF", "PR", "平衡"]
        assert result['summary']['profit_trend'] in ["扩张", "稳定", "压缩"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
