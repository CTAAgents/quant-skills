# -*- coding: utf-8 -*-
"""早期信号检测模块测试。"""

import unittest
import numpy as np
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.early_signal import (
    detect_volume_surge,
    detect_price_breakout,
    detect_volatility_expansion,
    detect_open_interest_change,
    detect_short_term_momentum,
    detect_ma_convergence,
    detect_early_signals,
    generate_early_signal_alert
)


class TestVolumeSurgeDetection(unittest.TestCase):
    """测试成交量异动检测。"""
    
    def test_no_surge(self):
        """测试没有成交量异动的情况。"""
        volumes = [1000, 1100, 1050, 1080, 1020, 1000, 1100, 1050, 1080, 1020,
                   1000, 1100, 1050, 1080, 1020, 1000, 1100, 1050, 1080, 1020, 1050]
        result = detect_volume_surge(volumes, threshold=1.5)
        self.assertFalse(result['surge'])
        self.assertAlmostEqual(result['ratio'], 1.0, places=1)
    
    def test_surge_detected(self):
        """测试检测到成交量异动。"""
        # 前20个成交量平均为1000，最后一个为2000（2倍）
        volumes = [1000] * 20 + [2000]
        result = detect_volume_surge(volumes, threshold=1.5)
        self.assertTrue(result['surge'])
        self.assertAlmostEqual(result['ratio'], 2.0, places=1)
        self.assertEqual(result['signal_strength'], 'strong')
    
    def test_moderate_surge(self):
        """测试中等程度的成交量异动。"""
        volumes = [1000] * 20 + [1600]
        result = detect_volume_surge(volumes, threshold=1.5)
        self.assertTrue(result['surge'])
        self.assertAlmostEqual(result['ratio'], 1.6, places=1)
        self.assertEqual(result['signal_strength'], 'moderate')
    
    def test_insufficient_data(self):
        """测试数据不足的情况。"""
        volumes = [1000, 1100, 1050]
        result = detect_volume_surge(volumes)
        self.assertFalse(result['surge'])
        self.assertEqual(result['signal_strength'], 'weak')


class TestPriceBreakoutDetection(unittest.TestCase):
    """测试价格突破检测。"""
    
    def test_no_breakout(self):
        """测试没有突破的情况。"""
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110,
                  111, 112, 113, 114, 115, 116, 117, 118, 119, 120]
        highs = [p * 1.01 for p in prices]
        lows = [p * 0.99 for p in prices]
        
        result = detect_price_breakout(prices, highs, lows)
        self.assertFalse(result['breakout_up'])
        self.assertFalse(result['breakout_down'])
    
    def test_upward_breakout(self):
        """测试向上突破。"""
        # 前20个价格在100-110之间，最后一个价格突破到115
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110,
                  109, 108, 107, 106, 105, 104, 103, 102, 101, 115]
        highs = [p * 1.01 for p in prices]
        lows = [p * 0.99 for p in prices]
        
        result = detect_price_breakout(prices, highs, lows)
        self.assertTrue(result['breakout_up'])
        self.assertFalse(result['breakout_down'])
        self.assertGreater(result['breakout_pct'], 0)
    
    def test_downward_breakout(self):
        """测试向下突破。"""
        # 前20个价格在100-110之间，最后一个价格跌破到95
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110,
                  109, 108, 107, 106, 105, 104, 103, 102, 101, 95]
        highs = [p * 1.01 for p in prices]
        lows = [p * 0.99 for p in prices]
        
        result = detect_price_breakout(prices, highs, lows)
        self.assertFalse(result['breakout_up'])
        self.assertTrue(result['breakout_down'])
        self.assertGreater(result['breakout_pct'], 0)
    
    def test_insufficient_data(self):
        """测试数据不足的情况。"""
        prices = [100, 101, 102]
        highs = [101, 102, 103]
        lows = [99, 100, 101]
        
        result = detect_price_breakout(prices, highs, lows)
        self.assertFalse(result['breakout_up'])
        self.assertFalse(result['breakout_down'])


class TestVolatilityExpansionDetection(unittest.TestCase):
    """测试波动率突破检测。"""
    
    def test_no_expansion(self):
        """测试没有波动率扩张的情况。"""
        atr_values = [1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.1,
                      1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0]
        result = detect_volatility_expansion(atr_values)
        self.assertFalse(result['expansion'])
        self.assertFalse(result['is_contraction'])
    
    def test_expansion_detected(self):
        """测试检测到波动率扩张。"""
        # 前20个ATR值较低（收缩状态），最后一个突然扩张
        atr_values = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5,
                      0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0]
        result = detect_volatility_expansion(atr_values, expansion_threshold=1.5)
        self.assertTrue(result['expansion'])
        self.assertTrue(result['is_contraction'])
        self.assertEqual(result['signal_strength'], 'moderate')
    
    def test_strong_expansion(self):
        """测试强波动率扩张。"""
        atr_values = [0.5] * 20 + [1.5]
        result = detect_volatility_expansion(atr_values, expansion_threshold=1.5)
        self.assertTrue(result['expansion'])
        self.assertEqual(result['signal_strength'], 'strong')


class TestOpenInterestChangeDetection(unittest.TestCase):
    """测试持仓量变化检测。"""
    
    def test_oi_increase_with_price_up(self):
        """测试持仓量增加且价格上涨。"""
        open_interests = [10000, 10100, 10200, 10300, 10400, 10500]
        prices = [100, 101, 102, 103, 104, 105]
        
        result = detect_open_interest_change(open_interests, prices, lookback=5)
        self.assertTrue(result['oi_increase'])
        self.assertEqual(result['price_direction'], 'up')
        self.assertFalse(result['divergence'])
    
    def test_oi_decrease_with_price_down(self):
        """测试持仓量减少且价格下跌。"""
        open_interests = [10000, 9900, 9800, 9700, 9600, 9500]
        prices = [100, 99, 98, 97, 96, 95]
        
        result = detect_open_interest_change(open_interests, prices, lookback=5)
        self.assertTrue(result['oi_decrease'])
        self.assertEqual(result['price_direction'], 'down')
        self.assertFalse(result['divergence'])
    
    def test_divergence(self):
        """测试量价背离。"""
        # 持仓量增加但价格下跌
        open_interests = [10000, 10100, 10200, 10300, 10400, 10500]
        prices = [100, 99, 98, 97, 96, 95]
        
        result = detect_open_interest_change(open_interests, prices, lookback=5)
        self.assertTrue(result['oi_increase'])
        self.assertEqual(result['price_direction'], 'down')
        self.assertTrue(result['divergence'])


class TestShortTermMomentumDetection(unittest.TestCase):
    """测试短期动量检测。"""
    
    def test_strong_up_momentum(self):
        """测试强上涨动量。"""
        # 价格持续上涨
        closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
        result = detect_short_term_momentum(closes, period=5)
        self.assertIn(result['momentum'], ['strong_up', 'up'])
        self.assertIn(result['signal_strength'], ['strong', 'moderate'])
    
    def test_strong_down_momentum(self):
        """测试强下跌动量。"""
        # 价格持续下跌
        closes = [110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100]
        result = detect_short_term_momentum(closes, period=5)
        self.assertIn(result['momentum'], ['strong_down', 'down'])
        self.assertIn(result['signal_strength'], ['strong', 'moderate'])
    
    def test_neutral_momentum(self):
        """测试中性动量。"""
        # 价格震荡
        closes = [100, 102, 98, 101, 99, 100, 102, 98, 101, 99, 100]
        result = detect_short_term_momentum(closes, period=5)
        self.assertEqual(result['momentum'], 'neutral')
        self.assertEqual(result['signal_strength'], 'weak')


class TestMAConvergenceDetection(unittest.TestCase):
    """测试均线收敛检测。"""
    
    def test_convergence_detected(self):
        """测试检测到均线收敛。"""
        # 短期均线和长期均线接近，但价格有轻微变化
        # 这样spread不为0，convergence=True，signal_strength='strong'
        prices = [100, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7, 100.8, 100.9,
                  101, 101.1, 101.2, 101.3, 101.4, 101.5, 101.6, 101.7, 101.8, 101.9, 102]
        result = detect_ma_convergence(prices, short_period=5, long_period=20)
        self.assertTrue(result['convergence'])
        self.assertIn(result['signal_strength'], ['strong', 'moderate'])
    
    def test_no_convergence(self):
        """测试没有均线收敛。"""
        # 短期均线和长期均线差距较大
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110,
                  111, 112, 113, 114, 115, 116, 117, 118, 119, 120]
        result = detect_ma_convergence(prices, short_period=5, long_period=20)
        self.assertFalse(result['convergence'])
        self.assertEqual(result['signal_strength'], 'weak')


class TestEarlySignalsDetection(unittest.TestCase):
    """测试综合早期信号检测。"""
    
    def test_no_early_signals(self):
        """测试没有早期信号的情况。"""
        tech_data = {'ATR14': [1.0] * 20}
        volumes = [1000] * 21
        highs = [100] * 21
        lows = [99] * 21
        closes = [100] * 21
        open_interests = [10000] * 21
        
        result = detect_early_signals(tech_data, volumes, highs, lows, closes, open_interests)
        self.assertEqual(result['early_signals_detected'], 0)
        self.assertEqual(result['overall_signal_strength'], 'weak')
        self.assertEqual(result['early_direction'], 'neutral')
    
    def test_multiple_early_signals(self):
        """测试多个早期信号。"""
        # 创建多个早期信号条件
        tech_data = {'ATR14': [0.5] * 20 + [1.0]}  # 波动率扩张
        volumes = [1000] * 20 + [2000]  # 成交量异动
        highs = [100] * 20 + [105]  # 向上突破
        lows = [99] * 20 + [104]
        closes = [100] * 20 + [105]  # 价格上涨
        open_interests = [10000] * 20 + [12000]  # 持仓量增加
        
        result = detect_early_signals(tech_data, volumes, highs, lows, closes, open_interests)
        self.assertGreater(result['early_signals_detected'], 0)
        self.assertIn(result['overall_signal_strength'], ['strong', 'moderate'])
        self.assertIn(result['early_direction'], ['bullish', 'bearish', 'neutral'])
    
    def test_requires_confirmation(self):
        """测试需要确认的情况。"""
        # 只有少量信号
        tech_data = {'ATR14': [1.0] * 21}
        volumes = [1000] * 20 + [1600]  # 只有成交量异动
        highs = [100] * 21
        lows = [99] * 21
        closes = [100] * 21
        open_interests = [10000] * 21
        
        result = detect_early_signals(tech_data, volumes, highs, lows, closes, open_interests)
        self.assertTrue(result['requires_confirmation'])


class TestEarlySignalAlertGeneration(unittest.TestCase):
    """测试早期信号预警生成。"""
    
    def test_no_alert(self):
        """测试没有预警的情况。"""
        early_signals = {
            'early_signals_detected': 0,
            'signal_details': {},
            'overall_signal_strength': 'weak',
            'early_direction': 'neutral',
            'confidence': 0.2,
            'requires_confirmation': True,
        }
        
        alert = generate_early_signal_alert(early_signals, 'rb', '螺纹钢')
        self.assertEqual(alert, "")
    
    def test_alert_generated(self):
        """测试生成预警。"""
        early_signals = {
            'early_signals_detected': 3,
            'signal_details': {
                'volume': {'surge': True, 'ratio': 2.0},
                'breakout': {'breakout_up': True, 'breakout_pct': 2.5},
                'volatility': {'expansion': True, 'ratio': 1.8},
            },
            'overall_signal_strength': 'strong',
            'early_direction': 'bullish',
            'confidence': 0.8,
            'requires_confirmation': False,
        }
        
        alert = generate_early_signal_alert(early_signals, 'rb', '螺纹钢')
        self.assertIn('rb', alert)
        self.assertIn('螺纹钢', alert)
        self.assertIn('3', alert)  # 信号数量
        self.assertIn('strong', alert)  # 整体强度
        self.assertIn('bullish', alert)  # 早期方向


if __name__ == '__main__':
    unittest.main()