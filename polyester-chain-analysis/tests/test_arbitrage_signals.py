#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
套利信号模块单元测试 v1.0.0

测试用例：
1. TA-EG价差套利测试
2. PF-TA加工差套利测试
3. TA月差套利测试
4. 多腿组合建议测试
5. 完整流程测试
"""

import pytest
import sys
from pathlib import Path

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from arbitrage_signals import (
    analyze_ta_eg_spread,
    analyze_pf_ta_spread,
    analyze_ta_term_structure,
    generate_multi_leg_combination,
    run_arbitrage_analysis,
    TAEgSpreadSignal,
    PfTaSpreadSignal,
    TaTermStructureSignal,
    MultiLegCombination
)


class TestTAEgSpread:
    """TA-EG价差套利测试"""
    
    def test_low_percentile(self):
        """测试低历史分位"""
        data = {
            'ta_price': 6000,
            'eg_price': 4500,
            'ta_eg_spread_percentile': 15,
            'gasoline_crack': 35,
            'coal_to_meg_profit': -100,
            'meg_port_inventory': 82
        }
        result = analyze_ta_eg_spread(data)
        
        assert isinstance(result, TAEgSpreadSignal)
        assert result.current_spread == 1500  # 6000 - 4500
        assert result.historical_percentile == 15
        assert result.signal_strength == "强"
        assert result.driver == "调油逻辑"
    
    def test_high_percentile(self):
        """测试高历史分位"""
        data = {
            'ta_price': 6000,
            'eg_price': 4500,
            'ta_eg_spread_percentile': 85,
            'gasoline_crack': 20,
            'coal_to_meg_profit': 100,
            'meg_port_inventory': 110
        }
        result = analyze_ta_eg_spread(data)
        
        assert result.historical_percentile == 85
        assert result.signal_strength == "强"
        assert result.driver == "煤制复产+EG累库"
    
    def test_neutral_percentile(self):
        """测试中性历史分位"""
        data = {
            'ta_price': 6000,
            'eg_price': 4500,
            'ta_eg_spread_percentile': 50,
            'gasoline_crack': 20,
            'coal_to_meg_profit': 0,
            'meg_port_inventory': 85
        }
        result = analyze_ta_eg_spread(data)
        
        assert result.historical_percentile == 50
        assert result.signal_strength == "弱"
        assert result.driver == "中性"
    
    def test_eg_port_drawdown(self):
        """测试EG港口去库"""
        data = {
            'ta_price': 6000,
            'eg_price': 4500,
            'ta_eg_spread_percentile': 25,
            'gasoline_crack': 20,
            'coal_to_meg_profit': 0,
            'meg_port_inventory': 75
        }
        result = analyze_ta_eg_spread(data)
        
        assert result.driver == "EG港口去库"


class TestPfTaSpread:
    """PF-TA加工差套利测试"""
    
    def test_low_percentile(self):
        """测试低历史分位"""
        data = {
            'pf_price': 7000,
            'ta_price': 6000,
            'pf_ta_spread_percentile': 15,
            'production_cut_letter': True,
            'pf_operation_rate': 80
        }
        result = analyze_pf_ta_spread(data)
        
        assert isinstance(result, PfTaSpreadSignal)
        assert result.current_spread == 1000  # 7000 - 6000
        assert result.historical_percentile == 15
        assert result.signal_strength == "强"
        assert result.driver == "工厂减产"
    
    def test_high_percentile(self):
        """测试高历史分位"""
        data = {
            'pf_price': 7000,
            'ta_price': 6000,
            'pf_ta_spread_percentile': 85,
            'production_cut_letter': False,
            'pf_operation_rate': 90
        }
        result = analyze_pf_ta_spread(data)
        
        assert result.historical_percentile == 85
        assert result.signal_strength == "强"
        assert result.driver == "中性"  # pf_ta_spread=1000，不在高位区间
    
    def test_extreme_low_spread(self):
        """测试极低加工差"""
        data = {
            'pf_price': 6700,
            'ta_price': 6000,
            'pf_ta_spread_percentile': 10,
            'production_cut_letter': False,
            'pf_operation_rate': 85
        }
        result = analyze_pf_ta_spread(data)
        
        assert result.current_spread == 700
        assert result.driver == "加工费极值"
    
    def test_extreme_high_spread(self):
        """测试极高加工差"""
        data = {
            'pf_price': 7300,
            'ta_price': 6000,
            'pf_ta_spread_percentile': 90,
            'production_cut_letter': False,
            'pf_operation_rate': 85
        }
        result = analyze_pf_ta_spread(data)
        
        assert result.current_spread == 1300
        assert result.driver == "加工费高位"


class TestTaTermStructure:
    """TA月差套利测试"""
    
    def test_back_structure(self):
        """测试Back结构"""
        data = {
            'ta_near_price': 6000,
            'ta_far_price': 5800,
            'ta_spread_percentile': 15,
            'pta_maintenance_rate': 25,
            'overseas_new_capacity': True
        }
        result = analyze_ta_term_structure(data)
        
        assert isinstance(result, TaTermStructureSignal)
        assert result.current_spread == 200  # 6000 - 5800
        assert result.historical_percentile == 15
        assert result.signal_strength == "强"
        assert result.driver == "近端检修去库"
    
    def test_contango_structure(self):
        """测试Contango结构"""
        data = {
            'ta_near_price': 5800,
            'ta_far_price': 6000,
            'ta_spread_percentile': 85,
            'pta_maintenance_rate': 10,
            'overseas_new_capacity': False
        }
        result = analyze_ta_term_structure(data)
        
        assert result.current_spread == -200  # 5800 - 6000
        assert result.signal_strength == "强"
        assert result.driver == "Contango结构"
    
    def test_flat_structure(self):
        """测试平坦结构"""
        data = {
            'ta_near_price': 6000,
            'ta_far_price': 6000,
            'ta_spread_percentile': 50,
            'pta_maintenance_rate': 15,
            'overseas_new_capacity': False
        }
        result = analyze_ta_term_structure(data)
        
        assert result.current_spread == 0
        assert result.signal_strength == "弱"
        assert result.driver == "中性"


class TestMultiLegCombination:
    """多腿组合建议测试"""
    
    def test_three_legs(self):
        """测试三腿组合"""
        data = {
            'ta_eg_spread': 1300,
            'pf_ta_spread': 750,
            'ta_spread': 250
        }
        result = generate_multi_leg_combination(data)
        
        assert isinstance(result, MultiLegCombination)
        assert len(result.legs) == 3
        assert result.confidence == "高"
        assert result.risk_reward_ratio > 0
    
    def test_two_legs(self):
        """测试两腿组合"""
        data = {
            'ta_eg_spread': 1300,
            'pf_ta_spread': 1100,
            'ta_spread': 250
        }
        result = generate_multi_leg_combination(data)
        
        assert len(result.legs) == 2
        assert result.confidence == "中"
    
    def test_one_leg(self):
        """测试单腿组合"""
        data = {
            'ta_eg_spread': 1300,
            'pf_ta_spread': 1100,
            'ta_spread': 50
        }
        result = generate_multi_leg_combination(data)
        
        assert len(result.legs) == 1
        assert result.confidence == "低"
    
    def test_no_legs(self):
        """测试无腿组合"""
        data = {
            'ta_eg_spread': 1600,
            'pf_ta_spread': 1100,
            'ta_spread': 50
        }
        result = generate_multi_leg_combination(data)
        
        assert len(result.legs) == 0
        assert result.confidence == "低"
        assert result.risk_reward_ratio == 0


class TestRunArbitrageAnalysis:
    """套利分析完整流程测试"""
    
    def test_full_pipeline(self):
        """测试完整流程"""
        data = {
            'ta_price': 6000,
            'eg_price': 4500,
            'ta_eg_spread_percentile': 25,
            'gasoline_crack': 35,
            'coal_to_meg_profit': -100,
            'meg_port_inventory': 82,
            'pf_price': 7000,
            'pf_ta_spread_percentile': 30,
            'production_cut_letter': True,
            'pf_operation_rate': 80,
            'ta_near_price': 6000,
            'ta_far_price': 5800,
            'ta_spread_percentile': 40,
            'pta_maintenance_rate': 25,
            'overseas_new_capacity': True,
            'ta_eg_spread': 1500,
            'pf_ta_spread': 1000,
            'ta_spread': 200
        }
        result = run_arbitrage_analysis(data)
        
        assert 'ta_eg_signal' in result
        assert 'pf_ta_signal' in result
        assert 'ta_term_signal' in result
        assert 'multi_leg' in result
        assert 'summary' in result
        
        assert isinstance(result['ta_eg_signal'], TAEgSpreadSignal)
        assert isinstance(result['pf_ta_signal'], PfTaSpreadSignal)
        assert isinstance(result['ta_term_signal'], TaTermStructureSignal)
        assert isinstance(result['multi_leg'], MultiLegCombination)
        
        assert result['summary']['ta_eg_direction'] in ["强", "弱"]
        assert result['summary']['pf_ta_direction'] in ["强", "弱"]
        assert result['summary']['ta_term_direction'] in ["强", "弱"]
        assert result['summary']['multi_leg_confidence'] in ["高", "中", "低"]
        assert result['summary']['total_legs'] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
