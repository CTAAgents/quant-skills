# -*- coding: utf-8 -*-
"""scoring_system.py v2.13 L1-L4四层打分系统测试。"""

import unittest
from scripts.scoring_system import (
    score_L1_germination,
    score_L2_volume_price,
    score_L3_structure,
    score_L4_confirmation,
    score_veto_dimension,
    calculate_composite_score,
    _calc_time_decay,
    estimate_days_since_breakout,
)


class TestL1Germination(unittest.TestCase):
    """L1 萌芽/资金结构维度（满分40分）。"""

    def test_oi_building_embryo(self):
        """OI建仓胚：价横+OI增 → +3分。"""
        tech = {'OI_RATE': 1.15, 'OI_INCREASING': True, 'PRICE_CHANGE_5D': 0.5}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 3)
        self.assertTrue(any('OI建仓胚' in r for r in result['reasons']))

    def test_oi_confirmation(self):
        """OI确认胚：价涨+OI增 → +2分。"""
        tech = {'OI_RATE': 1.08, 'PRICE_CHANGE_5D': 1.0}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 2)
        self.assertTrue(any('OI确认胚' in r for r in result['reasons']))

    def test_oi_divergence_penalty(self):
        """OI背离：价涨+OI降 → -2分。"""
        tech = {'OI_RATE': 0.85, 'PRICE_CHANGE_5D': 2.0}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertTrue(any('OI背离' in r for r in result['reasons']))

    def test_basis_strengthening(self):
        """基差走强 → +2分（v2.17调整）。"""
        tech = {}
        sym = {'last_price': 100}
        term_basis = {'basis_ma5': 50, 'basis_ma20': 40}
        result = score_L1_germination(tech, sym, is_bull=True, term_basis=term_basis)
        self.assertGreaterEqual(result['score'], 2)
        self.assertTrue(any('基差走强' in r for r in result['reasons']))

    def test_term_structure_back(self):
        """期限Back → +3分（v2.17调整）。"""
        tech = {}
        sym = {'last_price': 100}
        term_basis = {'term_structure': 'back'}
        result = score_L1_germination(tech, sym, is_bull=True, term_basis=term_basis)
        self.assertGreaterEqual(result['score'], 3)
        self.assertTrue(any('期限Back' in r for r in result['reasons']))

    def test_spread_acceleration(self):
        """Spread加速 → +2分（v2.17调整）。"""
        tech = {}
        sym = {'last_price': 100}
        term_basis = {'spread_slope_5d': 0.6}
        result = score_L1_germination(tech, sym, is_bull=True, term_basis=term_basis)
        self.assertGreaterEqual(result['score'], 2)

    def test_roc_just_turned_positive(self):
        """ROC10刚转正 → +4分（v2.17调整）。"""
        tech = {'ROC10': 1.5}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 4)
        self.assertTrue(any('ROC10刚转正' in r for r in result['reasons']))

    def test_bb_pctb_above_middle(self):
        """%b刚过0.5 → +3分（v2.17调整）。"""
        tech = {'BB_PCTB': 0.55}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 3)

    def test_atr_percentile_low(self):
        """ATR百分位脱低位 → +2分（v2.17调整）。"""
        tech = {'ATR_PERCENTILE': 25}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 2)

    def test_ma_slope_flat(self):
        """MA20斜率转平 → +4分（v2.17调整）。"""
        tech = {'MA20_SLOPE': 0.2}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 4)

    def test_higher_low(self):
        """Higher Low形成 → +6分（v2.12保留）。"""
        tech = {'HIGHER_LOW': True}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 6)

    def test_obv_leading(self):
        """OBV领先价 → +3分。"""
        tech = {'OBV': 1000, 'OBV_MA20': 800}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 3)

    def test_cmf_positive(self):
        """CMF脱零 → +3分。"""
        tech = {'CMF21': 0.1}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 3)

    def test_near_dc_upper(self):
        """接近DC20上轨 → +3分（v2.17调整）。"""
        tech = {'DC_UPPER': 101, 'DC_LOWER': 90}
        sym = {'last_price': 100.5}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 3)

    def test_volume_price_divergence(self):
        """量能先兆 → +5分（v2.12保留）。"""
        tech = {'VOL_PRICE_DIVERGENCE': True, 'VOL_5D_RATIO': 2.0, 'PRICE_CHANGE_5D': 0.5}
        sym = {'last_price': 100}
        result = score_L1_germination(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 5)

    def test_l1_cap_at_40(self):
        """L1分数上限40分。"""
        tech = {
            'OI_RATE': 1.2, 'PRICE_CHANGE_5D': 0.5,
            'ROC10': 1.5, 'BB_PCTB': 0.55, 'ATR_PERCENTILE': 25,
            'MA20_SLOPE': 0.2, 'HIGHER_LOW': True,
            'OBV': 1000, 'OBV_MA20': 800, 'CMF21': 0.1,
            'DC_UPPER': 101, 'DC_LOWER': 90,
            'VOL_PRICE_DIVERGENCE': True, 'VOL_5D_RATIO': 2.0,
        }
        sym = {'last_price': 100.5}
        term_basis = {'basis_ma5': 50, 'basis_ma20': 40, 'term_structure': 'back', 'spread_slope_5d': 0.6}
        result = score_L1_germination(tech, sym, is_bull=True, term_basis=term_basis)
        self.assertLessEqual(result['score'], 40)


class TestL2VolumePrice(unittest.TestCase):
    """L2 量价领先维度（满分15分）。"""

    def test_vortex_bull(self):
        """Vortex多头 → +4分。"""
        tech = {'VI_PLUS': 1.1, 'VI_MINUS': 0.9}
        sym = {'last_price': 100}
        result = score_L2_volume_price(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 4)

    def test_cci_break_100(self):
        """CCI破+100 → +3分。"""
        tech = {'CCI20': 150}
        sym = {'last_price': 100}
        result = score_L2_volume_price(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 3)

    def test_supertrend_bull(self):
        """Supertrend多头 → +4分。"""
        tech = {'SUPERTREND_DIR': 1}
        sym = {'last_price': 100}
        result = score_L2_volume_price(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 4)

    def test_hma_cross_bull(self):
        """HMA多头交叉 → +3分。"""
        tech = {'HMA_CROSS': 'bull'}
        sym = {'last_price': 100}
        result = score_L2_volume_price(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 3)

    @unittest.skip("v2.17移除KAMA量价信号，保留test作为参考")
    def test_kama_bull(self):
        """KAMA多头（v2.17已移除）。"""
        pass

    def test_l2_cap_at_25(self):
        """L2分数上限25分。"""
        tech = {
            'VI_PLUS': 1.1, 'VI_MINUS': 0.9,
            'CCI20': 150, 'SUPERTREND_DIR': 1,
            'HMA_CROSS': 'bull', 'KAMA_CROSS': 'bull',
        }
        sym = {'last_price': 100}
        result = score_L2_volume_price(tech, sym, is_bull=True)
        self.assertLessEqual(result['score'], 25)


class TestL3Structure(unittest.TestCase):
    """L3 价格结构维度（满分25分）。"""

    def test_rsi_healthy(self):
        """RSI健康区 → +8分。"""
        tech = {'RSI14': 55}
        result = score_L3_structure(tech, is_bull=True)
        self.assertGreaterEqual(result['score'], 8)

    def test_dmi_direction(self):
        """DMI方向确认 → +4分。"""
        tech = {'DMI_PDI': 30, 'DMI_MDI': 15}
        result = score_L3_structure(tech, is_bull=True)
        self.assertGreaterEqual(result['score'], 4)

    def test_new_high_60(self):
        """突破60日新高 → +3分。"""
        tech = {'NEW_HIGH_60': True}
        result = score_L3_structure(tech, is_bull=True)
        self.assertGreaterEqual(result['score'], 3)

    def test_l3_cap_at_25(self):
        """L3分数上限25分。"""
        tech = {'RSI14': 55, 'DMI_PDI': 30, 'DMI_MDI': 15, 'NEW_HIGH_60': True}
        result = score_L3_structure(tech, is_bull=True)
        self.assertLessEqual(result['score'], 25)


class TestL4Confirmation(unittest.TestCase):
    """L4 确认维度（满分10分）。"""

    def test_dc_breakout(self):
        """突破DC20上轨 → +6分。"""
        tech = {'DC_UPPER': 100, 'DC_LOWER': 80, 'DC55_TREND': 'up'}
        sym = {'last_price': 102}
        result = score_L4_confirmation(tech, sym, is_bull=True, days_since_breakout=0)
        self.assertGreaterEqual(result['score'], 6)

    def test_ma_alignment(self):
        """均线多头排列 → +4分。"""
        tech = {
            'MA5': 110, 'MA10': 105, 'MA20': 100,
            'DC_UPPER': 100, 'DC_LOWER': 80,
        }
        sym = {'last_price': 112}
        result = score_L4_confirmation(tech, sym, is_bull=True, days_since_breakout=0)
        self.assertGreaterEqual(result['score'], 4)

    def test_macd_confirmation(self):
        """MACD多头 → +1分（v2.17调整）。"""
        tech = {'MACD_DIF': 5, 'MACD_DEA': 3, 'DC_UPPER': 100, 'DC_LOWER': 80}
        sym = {'last_price': 90}
        result = score_L4_confirmation(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 1)

    def test_dc55_resonance(self):
        """DC55同步扩张 → +2分。"""
        tech = {'DC_UPPER': 100, 'DC_LOWER': 80, 'DC55_TREND': 'up'}
        sym = {'last_price': 90}
        result = score_L4_confirmation(tech, sym, is_bull=True)
        self.assertGreaterEqual(result['score'], 2)

    def test_time_decay(self):
        """突破20天+ → 衰减到30%。"""
        decay = _calc_time_decay(25)
        self.assertAlmostEqual(decay, 0.3, places=1)

    def test_l4_cap_at_10(self):
        """L4分数上限10分。"""
        tech = {
            'DC_UPPER': 100, 'DC_LOWER': 80, 'DC55_TREND': 'up',
            'MA5': 110, 'MA10': 105, 'MA20': 100,
            'MACD_DIF': 5, 'MACD_DEA': 3,
        }
        sym = {'last_price': 102}
        result = score_L4_confirmation(tech, sym, is_bull=True, days_since_breakout=0)
        self.assertLessEqual(result['score'], 10)


class TestVetoDimension(unittest.TestCase):
    """否决维度（最多-20分）。"""

    def test_adx_squeeze_veto(self):
        """ADX<15+Squeeze → -6分 (v2.17)。"""
        tech = {'ADX': 12, 'BB_SQUEEZE': True}
        sym = {'last_price': 100}
        result = score_veto_dimension(tech, sym, is_bull=True)
        self.assertLessEqual(result['score'], -6)

    def test_rsi_extreme_veto(self):
        """RSI>80超买 → -6分。"""
        tech = {'RSI14': 85}
        sym = {'last_price': 100}
        result = score_veto_dimension(tech, sym, is_bull=True)
        self.assertLessEqual(result['score'], -6)

    def test_price_deviation_veto(self):
        """偏离MA20>15% → -4分。"""
        tech = {'MA20': 100}
        sym = {'last_price': 120}
        result = score_veto_dimension(tech, sym, is_bull=True)
        self.assertLessEqual(result['score'], -4)

    def test_low_volume_veto(self):
        """严重缩量 → -2分。"""
        tech = {'VOL_RATIO': 0.3}
        sym = {'last_price': 100}
        result = score_veto_dimension(tech, sym, is_bull=True)
        self.assertLessEqual(result['score'], -2)

    @unittest.skip("v2.17移除OI背离否决，保留test作为参考")
    def test_oi_divergence_veto(self):
        """OI背离（价新高+OI降）— v2.17已移除。"""
        pass

    def test_structure_alert_veto(self):
        """结构切换预警 → -2分。"""
        tech = {}
        sym = {'last_price': 100}
        term_basis = {'structure_alert': 'super_back_to_flat'}
        result = score_veto_dimension(tech, sym, is_bull=True, term_basis=term_basis)
        self.assertLessEqual(result['score'], -2)

    def test_veto_floor_at_minus_20(self):
        """否决维度下限-20分。"""
        tech = {'ADX': 10, 'BB_SQUEEZE': True, 'RSI14': 90, 'MA20': 100, 'VOL_RATIO': 0.2, 'OI_RATE': 0.7, 'NEW_HIGH_60': True}
        sym = {'last_price': 120}
        term_basis = {'structure_alert': 'super_back_to_flat'}
        result = score_veto_dimension(tech, sym, is_bull=True, term_basis=term_basis)
        self.assertGreaterEqual(result['score'], -20)


class TestCompositeScore(unittest.TestCase):
    """综合打分测试。"""

    def test_strong_germination_signal(self):
        """萌芽型信号：L1高分+L2-L4中等 → 应该是STRONG。"""
        tech = {
            # L1 萌芽因子
            'ROC10': 1.5, 'BB_PCTB': 0.55, 'ATR_PERCENTILE': 25,
            'MA20_SLOPE': 0.3, 'HIGHER_LOW': True,
            'OBV': 1000, 'OBV_MA20': 800, 'CMF21': 0.1,
            'DC_UPPER': 105, 'DC_LOWER': 90,
            'VOL_PRICE_DIVERGENCE': True, 'VOL_5D_RATIO': 2.0,
            'PRICE_CHANGE_5D': 0.5,
            # L2 量价
            'VI_PLUS': 1.1, 'VI_MINUS': 0.9,
            'CCI20': 120, 'SUPERTREND_DIR': 1,
            # L3 结构
            'RSI14': 55, 'DMI_PDI': 30, 'DMI_MDI': 15,
            # L4 确认
            'MA5': 102, 'MA10': 100, 'MA20': 98,
            'MACD_DIF': 2, 'MACD_DEA': 1,
        }
        sym = {'last_price': 100}
        result = calculate_composite_score(tech, sym, 50)
        # 萌芽型信号应该得分较高
        self.assertGreaterEqual(result['total'], 50)
        self.assertIn(result['grade'], ['STRONG', 'WATCH', 'WEAK'])

    def test_already_advanced_signal_low_score(self):
        """已走远信号：L1低分+L4高分+否决扣分 → 应该低分。"""
        tech = {
            # L1 萌芽因子（无早期信号）
            'ROC10': 15,  # 已经走远
            'MA20_SLOPE': 5.0,  # 斜率已陡
            # L4 确认（但已走远）
            'DC_UPPER': 95, 'DC_LOWER': 80,
            'MA5': 115, 'MA10': 110, 'MA20': 105,
            'MACD_DIF': 10, 'MACD_DEA': 8,
            # 否决因子
            'RSI14': 82,  # 超买
            'MA20': 100,
        }
        sym = {'last_price': 118}
        result = calculate_composite_score(tech, sym, 80)
        # 已走远信号应该被否决维度打压
        self.assertLessEqual(result['total'], 70)

    def test_noise_signal(self):
        """无信号 → 低分。"""
        tech = {}
        sym = {'last_price': 100}
        result = calculate_composite_score(tech, sym, 5)
        self.assertLess(result['total'], 50)
        self.assertEqual(result['grade'], 'NOISE')

    def test_dimensions_structure(self):
        """返回结构包含所有四层+否决。"""
        tech = {'RSI14': 55}
        sym = {'last_price': 100}
        result = calculate_composite_score(tech, sym, 20)
        self.assertIn('L1_germination', result['dimensions'])
        self.assertIn('L2_volume_price', result['dimensions'])
        self.assertIn('L3_structure', result['dimensions'])
        self.assertIn('L4_confirmation', result['dimensions'])
        self.assertIn('veto', result['dimensions'])

    def test_total_bounded_0_100(self):
        """总分在0-100之间。"""
        tech = {}
        sym = {'last_price': 100}
        result = calculate_composite_score(tech, sym, 0)
        self.assertGreaterEqual(result['total'], 0)
        self.assertLessEqual(result['total'], 100)


class TestTimeDecay(unittest.TestCase):
    """时间衰减函数测试。"""

    def test_day_0_no_decay(self):
        self.assertEqual(_calc_time_decay(0), 1.0)

    def test_day_3_slight_decay(self):
        self.assertAlmostEqual(_calc_time_decay(3), 0.9, places=1)

    def test_day_7_moderate_decay(self):
        self.assertAlmostEqual(_calc_time_decay(7), 0.7, places=1)

    def test_day_14_half(self):
        self.assertAlmostEqual(_calc_time_decay(14), 0.5, places=1)

    def test_day_20_plus_floor(self):
        self.assertAlmostEqual(_calc_time_decay(25), 0.3, places=1)


class TestEstimateDaysSinceBreakout(unittest.TestCase):
    """突破天数估算测试。"""

    def test_no_breakout(self):
        """未突破 → 0天。"""
        tech = {'DC_UPPER': 100, 'DC_LOWER': 80, 'last_price': 90}
        result = estimate_days_since_breakout(tech, is_bull=True)
        self.assertEqual(result, 0)

    def test_extreme_breakout(self):
        """极度偏离 → 18天。"""
        tech = {'DC_UPPER': 100, 'DC_LOWER': 80, 'last_price': 115, 'PRICE_DEVIATION_PCT': 15}
        result = estimate_days_since_breakout(tech, is_bull=True)
        self.assertGreaterEqual(result, 10)


if __name__ == '__main__':
    unittest.main()
