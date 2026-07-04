#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化打分器测试 — 15个测试用例
验证权重归一化、分位计算、信号判定
"""

import sys
import pytest
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scoring import (
    calculate_historical_percentile, calculate_fuel_oil_score,
    format_fuel_oil_score_report, CrackSpreadCalculator, format_crack_spread_report,
    CompleteFuelOilScorer, BitumenScorer, LPGScorer,
    calculate_all_scores, format_all_scores_report,
)


# ========== 测试1-3：基础工具函数 ==========

class TestBasicFunctions:
    """基础工具函数测试"""

    def test_calculate_historical_percentile_range(self):
        """测试1：calculate_historical_percentile 返回0-100"""
        series = pd.Series([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        result = calculate_historical_percentile(series, 55)
        assert 0 <= result <= 100, f"Percentile {result} out of range"

    def test_calculate_historical_percentile_insufficient_data(self):
        """测试2：数据不足时返回50"""
        series = pd.Series([10, 20, 30])
        result = calculate_historical_percentile(series, 25)
        assert result == 50.0

    def test_calculate_historical_percentile_boundary(self):
        """测试3：边界值处理"""
        series = pd.Series(range(100))
        result = calculate_historical_percentile(series, 150)
        assert result == 100.0


# ========== 测试4-7：CompleteFuelOilScorer ==========

class TestCompleteFuelOilScorer:
    """燃料油五层量化打分器测试"""

    def setup_method(self):
        self.scorer = CompleteFuelOilScorer()

    def test_scorer_returns_valid_range(self):
        """测试4：总分在0-100范围内"""
        result = self.scorer.calculate(
            fu_close=3000, lu_close=3500, brent=70, sc=500,
            usdcny=7.2, freight=50, crack_fu=200, crack_lu=300,
            crack_refinery=60, india_import_yoy=5, bdi_percentile=55,
            bunker_yoy=3, month=6, sg_inventory=2000, sg_inventory_prev=1900,
            sg_inventory_yoy=10, arrival_yoy=-5, mops_change=2,
            production_yoy=3, import_yoy=-2, warehouse_level=45,
            policy_factor=1, basis=50, month_spread=30, geopolitics=1
        )
        assert 0 <= result.total_score <= 100, f"Total score {result.total_score} out of range"

    def test_scorer_module_weights_sum(self):
        """测试5：顶层权重加权和 = total_score"""
        result = self.scorer.calculate(
            fu_close=3000, lu_close=3500, brent=70, sc=500,
            usdcny=7.2, freight=50, crack_fu=200, crack_lu=300,
            crack_refinery=60, india_import_yoy=5, bdi_percentile=55,
            bunker_yoy=3, month=6, sg_inventory=2000, sg_inventory_prev=1900,
            sg_inventory_yoy=10, arrival_yoy=-5, mops_change=2,
            production_yoy=3, import_yoy=-2, warehouse_level=45,
            policy_factor=1, basis=50, month_spread=30, geopolitics=1
        )
        expected = (
            result.cost_score * 0.25 +
            result.crack_score * 0.30 +
            result.sg_score * 0.20 +
            result.dom_score * 0.15 +
            result.struct_score * 0.10
        )
        assert abs(result.total_score - expected) < 0.2, \
            f"Total {result.total_score} != weighted sum {expected}"

    def test_scorer_signal_logic(self):
        """测试6：信号判定逻辑正确（通过calculate_fuel_oil_score验证）"""
        # 高分应为做多
        high = calculate_fuel_oil_score(
            brent_20d_chg_percentile=90, sc_brent_spread_percentile=80,
            usdcny_percentile=70, vlcc_freight_percentile=80, geopolitics_score=30,
            fu_crack_percentile=85, lu_crack_percentile=80, lu_fu_spread_percentile=70,
            refinery_util_percentile=80, india_import_percentile=75, bdi_percentile=70,
            sg_inventory_percentile=20, sg_inv_wow_percentile=15, arrival_percentile=20,
            mops_percentile=75, warehouse_percentile=20, import_percentile=20,
            production_percentile=20, bunker_percentile=70, basis_percentile=80,
            month_spread_percentile=75, singapore_inventory_percentile=20
        )
        assert high.signal == "做多", f"High score signal: {high.signal}, total={high.total_score}"

    def test_scorer_all_modules_present(self):
        """测试7：所有模块得分都有值"""
        result = self.scorer.calculate(
            fu_close=3000, lu_close=3500, brent=70, sc=500,
            usdcny=7.2, freight=50, crack_fu=200, crack_lu=300,
            crack_refinery=60, india_import_yoy=5, bdi_percentile=55,
            bunker_yoy=3, month=6, sg_inventory=2000, sg_inventory_prev=1900,
            sg_inventory_yoy=10, arrival_yoy=-5, mops_change=2,
            production_yoy=3, import_yoy=-2, warehouse_level=45,
            policy_factor=0, basis=0, month_spread=0, geopolitics=0
        )
        for attr in ['cost_score', 'crack_score', 'sg_score', 'dom_score', 'struct_score']:
            val = getattr(result, attr)
            assert val is not None, f"{attr} is None"
            assert 0 <= val <= 100, f"{attr}={val} out of range"


# ========== 测试8-9：BitumenScorer ==========

class TestBitumenScorer:
    """沥青打分器测试"""

    def setup_method(self):
        self.scorer = BitumenScorer()

    def test_bitumen_scorer_range(self):
        """测试8：沥青打分在0-100范围"""
        result = self.scorer.score({
            'brent_chg': 5, 'sc_brent_spread': 100, 'usdcny': 7.2,
            'production_yoy': 3, 'refinery_run': 60, 'import_yoy': -2,
            'highway_invest_yoy': 8, 'consumption': 55, 'project_start_rate': 60,
            'plant_stock': 40, 'social_stock': 45, 'basis': 30, 'spread': 20,
            'infra_policy': 1, 'env_policy': 0
        }, month=5)
        assert 0 <= result.total_score <= 100, f"Score {result.total_score} out of range"

    def test_bitumen_seasonal_summer(self):
        """测试9：沥青夏季（7月）得分低于春季（5月）"""
        params = {
            'brent_chg': 0, 'sc_brent_spread': 0, 'usdcny': 7.2,
            'production_yoy': 0, 'refinery_run': 50, 'import_yoy': 0,
            'highway_invest_yoy': 0, 'consumption': 50, 'project_start_rate': 50,
            'plant_stock': 50, 'social_stock': 50, 'basis': 0, 'spread': 0,
            'infra_policy': 0, 'env_policy': 0
        }
        spring = self.scorer.score(params, month=5)
        summer = self.scorer.score(params, month=7)
        assert spring.total_score >= summer.total_score, \
            f"Spring {spring.total_score} should >= Summer {summer.total_score}"


# ========== 测试10-11：LPGScorer ==========

class TestLPGScorer:
    """LPG打分器测试"""

    def setup_method(self):
        self.scorer = LPGScorer()

    def test_lpg_scorer_range(self):
        """测试10：LPG打分在0-100范围"""
        result = self.scorer.score({
            'cp_propane_chg': 5, 'cp_butane_chg': 3, 'usdcny': 7.2,
            'fei': 55, 'production_yoy': 2, 'import_yoy': -3,
            'refinery_run': 60, 'pdh_margin': 55, 'pdh_run': 60,
            'propylene_price': 55, 'domestic_consumption': 5,
            'east_stock': 40, 'south_stock': 45, 'coal_to_gas': 1,
            'import_quota': 0, 'basis': 20
        }, month=12)
        assert 0 <= result.total_score <= 100, f"Score {result.total_score} out of range"

    def test_lpg_seasonal_winter(self):
        """测试11：LPG冬季（12月）得分高于夏季（6月）"""
        params = {
            'cp_propane_chg': 0, 'cp_butane_chg': 0, 'usdcny': 7.2,
            'fei': 50, 'production_yoy': 0, 'import_yoy': 0,
            'refinery_run': 50, 'pdh_margin': 50, 'pdh_run': 50,
            'propylene_price': 50, 'domestic_consumption': 0,
            'east_stock': 50, 'south_stock': 50, 'coal_to_gas': 0,
            'import_quota': 0, 'basis': 0
        }
        winter = self.scorer.score(params, month=12)
        summer = self.scorer.score(params, month=6)
        assert winter.total_score >= summer.total_score, \
            f"Winter {winter.total_score} should >= Summer {summer.total_score}"


# ========== 测试12-13：calculate_fuel_oil_score ==========

class TestCalculateFuelOilScore:
    """独立函数版燃料油打分测试"""

    def test_fuel_oil_score_with_percentiles(self):
        """测试12：calculate_fuel_oil_score 接受分位参数并返回合理结果"""
        score = calculate_fuel_oil_score(
            fu_close=3000, lu_close=3500, brent_close=70,
            brent_20d_chg_percentile=65, sc_brent_spread_percentile=55,
            usdcny_percentile=50, vlcc_freight_percentile=45, geopolitics_score=15,
            fu_crack_percentile=70, lu_crack_percentile=60, lu_fu_spread_percentile=55,
            refinery_util_percentile=65, india_import_percentile=55, bdi_percentile=50,
            sg_inventory_percentile=40, sg_inv_wow_percentile=35, arrival_percentile=45,
            mops_percentile=55, warehouse_percentile=50, import_percentile=45,
            production_percentile=55, bunker_percentile=60, basis_percentile=65,
            month_spread_percentile=55, singapore_inventory_percentile=40
        )
        assert 0 <= score.total_score <= 100
        assert score.signal in ["做多", "做空", "观望"]

    def test_fuel_oil_score_weight_consistency(self):
        """测试13：calculate_fuel_oil_score 权重加和一致"""
        score = calculate_fuel_oil_score(
            brent_20d_chg_percentile=60, sc_brent_spread_percentile=50,
            usdcny_percentile=50, vlcc_freight_percentile=50, geopolitics_score=0,
            fu_crack_percentile=60, lu_crack_percentile=50, lu_fu_spread_percentile=50,
            refinery_util_percentile=50, india_import_percentile=50, bdi_percentile=50,
            sg_inventory_percentile=50, sg_inv_wow_percentile=50, arrival_percentile=50,
            mops_percentile=50, warehouse_percentile=50, import_percentile=50,
            production_percentile=50, bunker_percentile=50, basis_percentile=50,
            month_spread_percentile=50
        )
        expected = (
            score.cost_score * 0.25 +
            score.crack_score * 0.30 +
            score.sg_score * 0.20 +
            score.dom_score * 0.15 +
            score.struct_score * 0.10
        )
        assert abs(score.total_score - expected) < 0.2


# ========== 测试14-15：CrackSpreadCalculator ==========

class TestCrackSpreadCalculator:
    """裂解价差计算器测试"""

    def setup_method(self):
        self.calc = CrackSpreadCalculator()

    def test_crack_spread_range(self):
        """测试14：裂解得分在合理范围"""
        result = self.calc.calculate(
            fu_price=3000, lu_price=3500, brent=70, diesel_price=5000,
            usdcny=7.2, refinery_util=60, india_import_yoy=5,
            russia_supply_yoy=-3, bdi_percentile=55, bunker_yoy=3, month=6
        )
        assert 0 <= result.crack_total <= 100, f"Crack total {result.crack_total} out of range"

    def test_crack_spread_signal(self):
        """测试15：裂解信号判定正确"""
        result = self.calc.calculate(
            fu_price=3000, lu_price=3500, brent=70, diesel_price=5000,
            usdcny=7.2, refinery_util=60, india_import_yoy=5,
            russia_supply_yoy=-3, bdi_percentile=55, bunker_yoy=3, month=6
        )
        assert result.crack_signal in ["利多", "利空", "中性"], \
            f"Signal {result.crack_signal} invalid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
