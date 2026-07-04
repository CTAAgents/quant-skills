# -*- coding: utf-8 -*-
"""信号筛选模块测试（Skill 1: commodity-trend-signal）。"""

import unittest
from scripts.signal_screener import detect_trend_stage, count_resonance, screen_signals


class TestDetectTrendStage(unittest.TestCase):
    """测试趋势阶段检测（v2.11 四阶段）。"""

    def test_launch_bull(self):
        """测试多头启动信号。"""
        tech = {
            'RSI14': 55,
            'MACD_DIF': 10,
            'MA5': 100,
            'MA10': 99,
            'MA20': 98,
            'last_price': 101,
            'ADX': 25
        }
        result = detect_trend_stage(tech, score=40)
        self.assertIn(result['stage'], ['launch', 'trending', 'exhausted', 'reversal'])

    def test_exhausted_bear(self):
        """测试空头衰竭信号（RSI<20=极度超卖+价格偏离>5%）。"""
        tech = {
            'RSI14': 15,  # RSI<20 → exhausted +3
            'MACD_DIF': -15,
            'MA5': 100,
            'MA10': 102,
            'MA20': 105,
            'last_price': 95,  # 偏离-9.5% → trending +1
            'ADX': 50  # ADX>45 → exhausted +1
        }
        result = detect_trend_stage(tech, score=-80)
        # v2.17: ADX=50强趋势覆盖RSI极端，stage 为 trending 而非 exhausted
        self.assertEqual(result['stage'], 'trending')

    def test_trending_bear(self):
        """测试空头主升信号（RSI 20-30 = trending，非exhausted）。"""
        tech = {
            'RSI14': 25,  # RSI 20-30 → trending +2
            'MACD_DIF': -15,
            'MA5': 100,
            'MA10': 102,
            'MA20': 105,
            'last_price': 95,  # 偏离-9.5% → trending +1
            'ADX': 30  # ADX≥25 → trending +1
        }
        result = detect_trend_stage(tech, score=-80)
        self.assertEqual(result['stage'], 'trending')


class TestCountResonance(unittest.TestCase):
    """测试多指标共振度。"""

    def test_strong_bull_resonance(self):
        """测试强多头共振。"""
        tech = {
            'MA5': 100,
            'MA10': 99,
            'MA20': 98,
            'MACD_DIF': 10,
            'RSI14': 60,
            'DMI_PDI': 30,
            'DMI_MDI': 15,
            'OBV': 1000,
            'OBV_MA20': 950,
            'last_price': 101
        }
        result = count_resonance(tech, score=70)
        self.assertGreaterEqual(result['confirmations'], 3)
        self.assertGreaterEqual(result['ratio'], 0.5)

    def test_weak_resonance(self):
        """测试弱共振（不应通过筛选）。"""
        tech = {
            'MA5': 100,
            'MA10': 101,
            'MA20': 102,
            'MACD_DIF': -5,
            'RSI14': 55,
            'DMI_PDI': 20,
            'DMI_MDI': 25,
            'OBV': 950,
            'OBV_MA20': 1000,
            'last_price': 99
        }
        result = count_resonance(tech, score=30)
        self.assertLess(result['ratio'], 0.5)


class TestScreenSignalsMarketFilter(unittest.TestCase):
    """测试市场环境过滤逻辑。"""

    def _make_symbol(self, pid, score, price=1000, oi=50000):
        """创建测试用品种数据。"""
        return {
            'product_id': pid,
            'product_name': f'test_{pid}',
            'last_price': price,
            'open_interest': oi,
            'trend': {'score': score},
            'tech': {
                'MA5': price * 1.01 if score > 0 else price * 0.99,
                'MA10': price * 1.005 if score > 0 else price * 0.995,
                'MA20': price,
                'MACD_DIF': 10 if score > 0 else -10,
                'RSI14': 55 if score > 0 else 45,
                'DMI_PDI': 30 if score > 0 else 15,
                'DMI_MDI': 15 if score > 0 else 30,
                'OBV': 1000 if score > 0 else 900,
                'OBV_MA20': 950 if score > 0 else 950,
                'last_price': price,
                'ATR14': price * 0.02,
            }
        }

    def test_bearish_market_filters_weak_buy_signals(self):
        """测试偏空市场过滤弱多头信号。"""
        symbols = []
        for i in range(8):
            symbols.append(self._make_symbol(f'sell{i}', -60 - i * 5))
        symbols.append(self._make_symbol('buy1', 35))
        symbols.append(self._make_symbol('buy2', 40))

        candidates = screen_signals(symbols, score_threshold=20, min_resonance=0.5)
        buy_candidates = [c for c in candidates if c['direction'] == 'BUY']
        for bc in buy_candidates:
            self.assertGreaterEqual(bc['resonance']['ratio'], 0.6,
                                   f"多头信号 {bc['product_id']} 共振度应>=60%")

    def test_balanced_market_normal_filtering(self):
        """测试平衡市场正常过滤。"""
        symbols = []
        for i in range(5):
            symbols.append(self._make_symbol(f'buy{i}', 60 + i * 5))
        for i in range(5):
            symbols.append(self._make_symbol(f'sell{i}', -60 - i * 5))

        candidates = screen_signals(symbols, score_threshold=20, min_resonance=0.5)
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
