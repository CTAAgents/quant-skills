#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主驱动识别模块单元测试 v1.0.0

测试用例：
1. 三层漏斗诊断测试
2. 驱动归属判定测试
3. 盘面验证测试
4. 量化打分测试
5. 驱动切换检测测试
"""

import pytest
import sys
from pathlib import Path

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from driver_identification import (
    diagnose_l1_annual,
    diagnose_l2_quarterly,
    diagnose_l3_weekly,
    attribute_px_driver,
    attribute_pta_driver,
    attribute_meg_driver,
    attribute_pf_driver,
    attribute_pr_driver,
    verify_market_leadership,
    verify_profit_distribution,
    verify_term_structure,
    calculate_driver_score,
    attribute_all_drivers,
    verify_market,
    detect_driver_switch,
    run_driver_identification,
    DriverScore,
    DriverAttribution,
    MarketVerification,
    DriverSwitchSignal
)


class TestDiagnoseL1Annual:
    """L1年度层诊断测试"""
    
    def test_px_capacity_contraction(self):
        """测试PX产能收缩"""
        data = {'px_capacity_growth': -5}
        score, driver = diagnose_l1_annual(data)
        assert score > 50
        assert driver == "PX产能收缩"
    
    def test_px_capacity_expansion(self):
        """测试PX产能扩张"""
        data = {'px_capacity_growth': 15}
        score, driver = diagnose_l1_annual(data)
        assert score < 50
        assert driver == "PX产能扩张"
    
    def test_pta_capacity_contraction(self):
        """测试PTA产能收缩"""
        data = {'pta_capacity_growth': -5}
        score, driver = diagnose_l1_annual(data)
        assert score > 50
        assert driver == "PTA产能收缩"
    
    def test_meg_capacity_expansion(self):
        """测试MEG产能扩张"""
        data = {'meg_capacity_growth': 25}
        score, driver = diagnose_l1_annual(data)
        assert score < 50
        assert driver == "MEG产能扩张"
    
    def test_overseas_new_capacity(self):
        """测试海外新装置"""
        data = {'overseas_new_capacity': True}
        score, driver = diagnose_l1_annual(data)
        assert score < 50
        assert driver == "海外新装置"
    
    def test_neutral_scenario(self):
        """测试中性场景"""
        data = {
            'px_capacity_growth': 0,
            'pta_capacity_growth': 5,
            'meg_capacity_growth': 10,
            'overseas_new_capacity': False
        }
        score, driver = diagnose_l1_annual(data)
        assert score == 50
        assert driver == "产能周期"


class TestDiagnoseL2Quarterly:
    """L2季度层诊断测试"""
    
    def test_pta_maintenance(self):
        """测试PTA检修"""
        data = {'pta_maintenance_rate': 25}
        score, driver = diagnose_l2_quarterly(data)
        assert score > 50
        assert driver == "PTA检修季"
    
    def test_px_maintenance(self):
        """测试PX检修"""
        data = {'px_maintenance_rate': 20}
        score, driver = diagnose_l2_quarterly(data)
        assert score > 50
        assert driver == "PX检修季"
    
    def test_gasoline_crack(self):
        """测试调油逻辑"""
        data = {'gasoline_crack': 35}
        score, driver = diagnose_l2_quarterly(data)
        assert score > 50
        assert driver == "调油逻辑"
    
    def test_geopolitical_risk(self):
        """测试地缘风险"""
        data = {'geopolitical_risk': 75}
        score, driver = diagnose_l2_quarterly(data)
        assert score > 50
        assert driver == "地缘风险"
    
    def test_anti_involution_cut(self):
        """测试反内卷减产"""
        data = {'anti_involution_cut': True}
        score, driver = diagnose_l2_quarterly(data)
        assert score > 50
        assert driver == "反内卷减产"
    
    def test_neutral_scenario(self):
        """测试中性场景"""
        data = {
            'pta_maintenance_rate': 10,
            'px_maintenance_rate': 10,
            'gasoline_crack': 20,
            'geopolitical_risk': 50,
            'anti_involution_cut': False
        }
        score, driver = diagnose_l2_quarterly(data)
        assert score == 50
        assert driver == "季度中性"


class TestDiagnoseL3Weekly:
    """L3周度层诊断测试"""
    
    def test_meg_port_inventory_low(self):
        """测试MEG港口库存低"""
        data = {'meg_port_inventory': 75}
        score, driver = diagnose_l3_weekly(data)
        assert score > 50
        assert driver == "MEG港口去库"
    
    def test_meg_port_inventory_high(self):
        """测试MEG港口库存高"""
        data = {'meg_port_inventory': 110}
        score, driver = diagnose_l3_weekly(data)
        assert score < 50
        assert driver == "MEG港口累库"
    
    def test_polyester_load_high(self):
        """测试聚酯负荷高"""
        data = {'polyester_load': 88}
        score, driver = diagnose_l3_weekly(data)
        assert score > 50
        assert driver == "聚酯高负荷"
    
    def test_polyester_load_low(self):
        """测试聚酯负荷低"""
        data = {'polyester_load': 78}
        score, driver = diagnose_l3_weekly(data)
        assert score < 50
        assert driver == "聚酯低负荷"
    
    def test_weaving_order_days_good(self):
        """测试织造订单好"""
        data = {'weaving_order_days': 18}
        score, driver = diagnose_l3_weekly(data)
        assert score > 50
        assert driver == "织造订单好"
    
    def test_weaving_order_days_bad(self):
        """测试织造订单差"""
        data = {'weaving_order_days': 5}
        score, driver = diagnose_l3_weekly(data)
        assert score < 50
        assert driver == "织造订单差"
    
    def test_unit_shutdown(self):
        """测试装置临停"""
        data = {'unit_shutdown': True}
        score, driver = diagnose_l3_weekly(data)
        assert score > 50
        assert driver == "装置临停"
    
    def test_neutral_scenario(self):
        """测试中性场景"""
        data = {
            'meg_port_inventory': 85,
            'polyester_load': 83,
            'weaving_order_days': 10,
            'unit_shutdown': False
        }
        score, driver = diagnose_l3_weekly(data)
        assert score == 50
        assert driver == "周度中性"


class TestAttributeDrivers:
    """驱动归属判定测试"""
    
    def test_px_driver_cost(self):
        """测试PX成本驱动"""
        data = {'pxn': 250, 'px_operation_rate': 85, 'gasoline_crack': 20}
        driver = attribute_px_driver(data)
        assert driver == "成本"
    
    def test_px_driver_maintenance(self):
        """测试PX检修驱动"""
        data = {'pxn': 180, 'px_operation_rate': 75, 'gasoline_crack': 20}
        driver = attribute_px_driver(data)
        assert driver == "检修"
    
    def test_px_driver_oil_blending(self):
        """测试PX调油驱动"""
        data = {'pxn': 350, 'px_operation_rate': 85, 'gasoline_crack': 35}
        driver = attribute_px_driver(data)
        assert driver == "调油"
    
    def test_pta_driver_processing_fee(self):
        """测试PTA加工费驱动"""
        data = {'pta_processing_fee': 250, 'pta_operation_rate': 80, 'export_impact': False}
        driver = attribute_pta_driver(data)
        assert driver == "加工费"
    
    def test_pta_driver_maintenance(self):
        """测试PTA检修驱动"""
        data = {'pta_processing_fee': 400, 'pta_operation_rate': 65, 'export_impact': False}
        driver = attribute_pta_driver(data)
        assert driver == "检修"
    
    def test_pta_driver_export(self):
        """测试PTA出口驱动"""
        data = {'pta_processing_fee': 400, 'pta_operation_rate': 80, 'export_impact': True}
        driver = attribute_pta_driver(data)
        assert driver == "出口"
    
    def test_meg_driver_port_inventory(self):
        """测试MEG港口库存驱动"""
        data = {'meg_port_inventory': 75, 'coal_to_meg_profit': 0, 'import_impact': False}
        driver = attribute_meg_driver(data)
        assert driver == "港口库存"
    
    def test_meg_driver_coal_profit(self):
        """测试MEG煤制利润驱动"""
        data = {'meg_port_inventory': 85, 'coal_to_meg_profit': -250, 'import_impact': False}
        driver = attribute_meg_driver(data)
        assert driver == "煤制利润"
    
    def test_pf_driver_processing_fee(self):
        """测试PF加工费驱动"""
        data = {'pf_processing_fee': 750, 'production_cut_letter': False, 'export_impact': False}
        driver = attribute_pf_driver(data)
        assert driver == "加工费"
    
    def test_pf_driver_production_cut(self):
        """测试PF减产函驱动"""
        data = {'pf_processing_fee': 900, 'production_cut_letter': True, 'export_impact': False}
        driver = attribute_pf_driver(data)
        assert driver == "减产函"


class TestMarketVerification:
    """盘面验证测试"""
    
    def test_px_leads(self):
        """测试PX领涨"""
        data = {'px_change': 3.0, 'ta_change': 2.0, 'eg_change': 1.0, 'pf_change': 0.5}
        result = verify_market_leadership(data)
        assert "PX领涨" in result
    
    def test_ta_leads(self):
        """测试TA领涨"""
        data = {'px_change': 1.0, 'ta_change': 2.5, 'eg_change': 0.5, 'pf_change': 0.2}
        result = verify_market_leadership(data)
        assert "TA领涨" in result
    
    def test_eg_leads(self):
        """测试EG领涨"""
        data = {'px_change': 0.5, 'ta_change': 1.0, 'eg_change': 2.5, 'pf_change': 0.2}
        result = verify_market_leadership(data)
        assert "EG领涨" in result
    
    def test_ta_up_pf_down(self):
        """测试TA涨PF不动"""
        data = {'px_change': 0.3, 'ta_change': 2.0, 'eg_change': 0.5, 'pf_change': 0.1}
        result = verify_market_leadership(data)
        assert "TA涨PF不动" in result
    
    def test_pxn_high(self):
        """测试PXN高位"""
        data = {'pxn': 450, 'pta_processing_fee': 400, 'pf_processing_fee': 900, 'oil_price_change': 1.0}
        result = verify_profit_distribution(data)
        assert "PXN高位" in result
    
    def test_ta_processing_fee_recovery(self):
        """测试TA加工费修复"""
        data = {'pxn': 300, 'pta_processing_fee': 550, 'pf_processing_fee': 900, 'oil_price_change': 1.0}
        result = verify_profit_distribution(data)
        assert "TA加工费修复" in result
    
    def test_ta_back_structure(self):
        """测试TA Back结构"""
        data = {'ta_near_far_spread': 150, 'eg_near_far_spread': -50, 'pf_near_far_spread': -20}
        result = verify_term_structure(data)
        assert "TA Back加深" in result


class TestCalculateDriverScore:
    """量化打分测试"""
    
    def test_bullish_scenario(self):
        """测试偏多场景（牛市+右侧确认）"""
        data = {
            'crude_change_10d': 5.0,
            'ta_change_10d': 3.0,
            'eg_change_10d': 2.0, 'pf_change_10d': 1.5, 'pr_change_10d': 2.0,
            'lowest_3d_ago': 5400, 'current_low': 5480,
            'volume_increase_ratio': 2.0, 'rsi_current': 55, 'rsi_previous': 40,
            'macd_bullish_cross': True, 'price_above_ma20': True, 'ma20_slope_positive': True,
            'px_capacity_growth': -5,
            'pta_capacity_growth': 10,
            'meg_capacity_growth': 25,
            'overseas_new_capacity': True,
            'pta_maintenance_rate': 25,
            'px_maintenance_rate': 20,
            'gasoline_crack': 35,
            'geopolitical_risk': 60,
            'anti_involution_cut': False,
            'meg_port_inventory': 82,
            'polyester_load': 83,
            'weaving_order_days': 12,
            'unit_shutdown': False
        }
        score = calculate_driver_score(data)
        assert score.total_score > 50
        assert score.driver_strength in ["强", "中"]
        assert score.confidence in ["高", "中", "低"]
    
    def test_bearish_scenario(self):
        """测试偏空场景（熊市+无右侧确认）"""
        data = {
            'crude_change_10d': -5.0,
            'ta_change_10d': -4.0, 'eg_change_10d': -3.0,
            'pf_change_10d': -2.5, 'pr_change_10d': -3.0,
            'lowest_3d_ago': 5500, 'current_low': 5300,
            'volume_increase_ratio': 0.6, 'rsi_current': 30, 'rsi_previous': 35,
            'macd_bullish_cross': False, 'price_above_ma20': False, 'ma20_slope_positive': False,
            'px_capacity_growth': 15,
            'pta_capacity_growth': 20,
            'meg_capacity_growth': 30,
            'overseas_new_capacity': True,
            'pta_maintenance_rate': 10,
            'px_maintenance_rate': 10,
            'gasoline_crack': 20,
            'geopolitical_risk': 50,
            'anti_involution_cut': False,
            'meg_port_inventory': 110,
            'polyester_load': 78,
            'weaving_order_days': 5,
            'unit_shutdown': False
        }
        score = calculate_driver_score(data)
        assert score.total_score < 50
        # 熊市趋势+右侧做空确认（价格创新低+跌破MA20）= SELL
        assert score.trade_signal == 'SELL', f"预期SELL但得到{score.trade_signal}"
    
    def test_neutral_scenario(self):
        """测试中性场景（震荡+无右侧确认）"""
        data = {
            'crude_change_10d': 0.5, 'ta_change_10d': 0.3,
            'eg_change_10d': -0.2, 'pf_change_10d': -0.1, 'pr_change_10d': 0.1,
            'lowest_3d_ago': 5450, 'current_low': 5430,
            'volume_increase_ratio': 1.0, 'rsi_current': 48, 'rsi_previous': 45,
            'macd_bullish_cross': False, 'price_above_ma20': False, 'ma20_slope_positive': False,
            'px_capacity_growth': 0,
            'pta_capacity_growth': 5,
            'meg_capacity_growth': 10,
            'overseas_new_capacity': False,
            'pta_maintenance_rate': 15,
            'px_maintenance_rate': 15,
            'gasoline_crack': 25,
            'geopolitical_risk': 55,
            'anti_involution_cut': False,
            'meg_port_inventory': 85,
            'polyester_load': 83,
            'weaving_order_days': 10,
            'unit_shutdown': False
        }
        score = calculate_driver_score(data)
        assert score.trade_signal == 'HOLD'
        assert score.confidence in ["高", "中", "低"]


class TestAttributeAllDrivers:
    """所有品种驱动归属判定测试"""
    
    def test_multiple_drivers(self):
        """测试多品种驱动"""
        data = {
            'pxn': 250,
            'px_operation_rate': 85,
            'gasoline_crack': 20,
            'pta_processing_fee': 250,
            'pta_operation_rate': 80,
            'export_impact': False,
            'meg_port_inventory': 75,
            'coal_to_meg_profit': 0,
            'import_impact': False,
            'pf_processing_fee': 750,
            'production_cut_letter': False,
            'export_impact': False,
            'pr_processing_fee': 400
        }
        result = attribute_all_drivers(data)
        assert result.px_driver == "成本"
        assert result.pta_driver == "加工费"
        assert result.meg_driver == "港口库存"
        assert result.pf_driver == "加工费"
        assert result.attribution_confidence in ["高", "中", "低"]


class TestDetectDriverSwitch:
    """驱动切换检测测试"""
    
    def test_no_switch(self):
        """测试无切换"""
        data = {
            'geopolitical_risk': 50,
            'pta_operation_rate': 80,
            'gasoline_crack': 25,
            'polyester_load': 83,
            'coal_to_meg_profit': 0
        }
        result = detect_driver_switch(data, "中性", "中性")
        assert result is None
    
    def test_geopolitical_easing(self):
        """测试地缘缓和"""
        data = {
            'geopolitical_risk': 25,
            'pta_operation_rate': 80,
            'gasoline_crack': 25,
            'polyester_load': 83,
            'coal_to_meg_profit': 0
        }
        result = detect_driver_switch(data, "地缘风险", "中性")
        assert result is not None
        assert result.switch_type == "地缘缓和"
    
    def test_maintenance_end(self):
        """测试检修结束"""
        data = {
            'geopolitical_risk': 50,
            'pta_operation_rate': 80,
            'gasoline_crack': 25,
            'polyester_load': 83,
            'coal_to_meg_profit': 0
        }
        result = detect_driver_switch(data, "检修", "中性")
        assert result is not None
        assert result.switch_type == "检修结束"


class TestRunDriverIdentification:
    """主驱动识别完整流程测试"""
    
    def test_full_pipeline(self):
        """测试完整流程"""
        data = {
            'px_capacity_growth': -5,
            'pta_capacity_growth': 10,
            'meg_capacity_growth': 25,
            'overseas_new_capacity': True,
            'pta_maintenance_rate': 25,
            'px_maintenance_rate': 20,
            'gasoline_crack': 35,
            'geopolitical_risk': 60,
            'anti_involution_cut': False,
            'meg_port_inventory': 82,
            'polyester_load': 83,
            'weaving_order_days': 12,
            'unit_shutdown': False,
            'pxn': 350,
            'px_operation_rate': 75,
            'pta_processing_fee': 450,
            'pta_operation_rate': 70,
            'export_impact': True,
            'coal_to_meg_profit': -100,
            'import_impact': False,
            'pf_processing_fee': 850,
            'production_cut_letter': False,
            'pr_processing_fee': 400,
            'px_change': 2.5,
            'ta_change': 1.8,
            'eg_change': 0.5,
            'pf_change': 0.2,
            'oil_price_change': 1.0,
            'ta_near_far_spread': 150,
            'eg_near_far_spread': -80,
            'pf_near_far_spread': -20,
            'old_driver': '中性'
        }
        result = run_driver_identification(data)
        
        assert 'driver_score' in result
        assert 'driver_attribution' in result
        assert 'market_verification' in result
        assert 'driver_switch' in result
        assert 'summary' in result
        
        assert isinstance(result['driver_score'], DriverScore)
        assert isinstance(result['driver_attribution'], DriverAttribution)
        assert isinstance(result['market_verification'], MarketVerification)
        
        assert result['summary']['primary_driver'] is not None
        assert result['summary']['driver_strength'] in ["强", "中", "弱"]
        assert result['summary']['confidence'] in ["高", "中", "低"]
        assert result['summary']['total_score'] >= 0
        assert result['summary']['total_score'] <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
