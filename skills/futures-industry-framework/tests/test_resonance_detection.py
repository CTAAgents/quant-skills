"""
共振检测模块测试
"""
import unittest
import sys
import os
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
    ResonanceDetector,
    MultiTimeframeResonanceDetector,
    ResonanceHistoryAnalyzer,
    ResonanceVisualizer,
    ResonanceSignal,
    SignalDirection,
    ResonanceLevel
)


class TestSignalDirectionEnum(unittest.TestCase):
    """测试信号方向枚举"""
    
    def test_signal_direction_values(self):
        """测试信号方向值"""
        self.assertEqual(SignalDirection.BULLISH.value, "看多")
        self.assertEqual(SignalDirection.BEARISH.value, "看空")
        self.assertEqual(SignalDirection.NEUTRAL.value, "中性")


class TestResonanceLevelEnum(unittest.TestCase):
    """测试共振强度等级枚举"""
    
    def test_resonance_level_values(self):
        """测试共振强度等级值"""
        self.assertEqual(ResonanceLevel.NO_RESONANCE.value, "无共振")
        self.assertEqual(ResonanceLevel.WEAK_RESONANCE.value, "弱共振")
        self.assertEqual(ResonanceLevel.MODERATE_RESONANCE.value, "中等共振")
        self.assertEqual(ResonanceLevel.STRONG_RESONANCE.value, "强共振")
        self.assertEqual(ResonanceLevel.EXTREME_RESONANCE.value, "极强共振")


class TestResonanceDetectorInitialization(unittest.TestCase):
    """测试共振检测器初始化"""
    
    def test_thresholds(self):
        """测试阈值配置"""
        detector = ResonanceDetector()
        self.assertIn('industry_chain_bullish', detector.thresholds)
        self.assertIn('industry_chain_bearish', detector.thresholds)
        self.assertIn('fundamental_bullish', detector.thresholds)
        self.assertIn('fundamental_bearish', detector.thresholds)
        self.assertIn('technical_bullish', detector.thresholds)
        self.assertIn('technical_bearish', detector.thresholds)
    
    def test_default_weights(self):
        """测试默认权重"""
        detector = ResonanceDetector()
        self.assertIn('industry_chain', detector.weights)
        self.assertIn('fundamental', detector.weights)
        self.assertIn('technical', detector.weights)


class TestDimensionSignalDetection(unittest.TestCase):
    """测试单个维度信号检测"""
    
    def setUp(self):
        """测试前初始化"""
        self.detector = ResonanceDetector()
    
    def test_bullish_signal_high_score(self):
        """测试高分看涨信号"""
        direction, confidence = self.detector.get_dimension_signal(
            70, 55, 45
        )
        self.assertEqual(direction, SignalDirection.BULLISH)
        self.assertGreater(confidence, 0)
    
    def test_bearish_signal_low_score(self):
        """测试低分看空信号"""
        direction, confidence = self.detector.get_dimension_signal(
            30, 55, 45
        )
        self.assertEqual(direction, SignalDirection.BEARISH)
        self.assertGreater(confidence, 0)
    
    def test_neutral_signal_mid_score(self):
        """测试中等分数中性信号"""
        direction, confidence = self.detector.get_dimension_signal(
            50, 55, 45
        )
        self.assertEqual(direction, SignalDirection.NEUTRAL)
        self.assertEqual(confidence, 0.5)


class TestResonanceDetection(unittest.TestCase):
    """测试共振检测"""
    
    def setUp(self):
        """测试前初始化"""
        self.detector = ResonanceDetector()
    
    def test_extreme_bullish_resonance(self):
        """测试极强看涨共振"""
        signal = self.detector.detect_resonance(
            industry_score=75,
            fundamental_score=70,
            technical_score=80
        )
        
        self.assertEqual(signal.direction, SignalDirection.BULLISH)
        self.assertEqual(signal.level, ResonanceLevel.EXTREME_RESONANCE)
    
    def test_strong_bullish_resonance(self):
        """测试强看涨共振"""
        signal = self.detector.detect_resonance(
            industry_score=75,
            fundamental_score=50,
            technical_score=80
        )
        
        self.assertEqual(signal.direction, SignalDirection.BULLISH)
        self.assertEqual(signal.level, ResonanceLevel.STRONG_RESONANCE)
    
    def test_extreme_bearish_resonance(self):
        """测试极强看空共振"""
        signal = self.detector.detect_resonance(
            industry_score=25,
            fundamental_score=30,
            technical_score=20
        )
        
        self.assertEqual(signal.direction, SignalDirection.BEARISH)
        self.assertEqual(signal.level, ResonanceLevel.EXTREME_RESONANCE)
    
    def test_strong_bearish_resonance(self):
        """测试强看空共振"""
        signal = self.detector.detect_resonance(
            industry_score=25,
            fundamental_score=50,
            technical_score=20
        )
        
        self.assertEqual(signal.direction, SignalDirection.BEARISH)
        self.assertEqual(signal.level, ResonanceLevel.STRONG_RESONANCE)
    
    def test_moderate_resonance(self):
        """测试中等共振"""
        signal = self.detector.detect_resonance(
            industry_score=70,
            fundamental_score=50,
            technical_score=50
        )
        
        self.assertEqual(signal.direction, SignalDirection.BULLISH)
        self.assertEqual(signal.level, ResonanceLevel.MODERATE_RESONANCE)
    
    def test_no_resonance(self):
        """测试无共振"""
        signal = self.detector.detect_resonance(
            industry_score=50,
            fundamental_score=50,
            technical_score=50
        )
        
        self.assertEqual(signal.direction, SignalDirection.NEUTRAL)
        self.assertEqual(signal.level, ResonanceLevel.WEAK_RESONANCE)
    
    def test_conflicting_signals(self):
        """测试冲突信号"""
        signal = self.detector.detect_resonance(
            industry_score=75,
            fundamental_score=25,
            technical_score=50
        )
        
        # 冲突信号应该中性
        self.assertEqual(signal.direction, SignalDirection.NEUTRAL)
        self.assertTrue(len(signal.conflicting_factors) > 0)


class TestResonanceSignalProperties(unittest.TestCase):
    """测试共振信号属性"""
    
    def setUp(self):
        """测试前初始化"""
        self.detector = ResonanceDetector()
    
    def test_contributing_factors(self):
        """测试贡献因子"""
        signal = self.detector.detect_resonance(75, 70, 80)
        
        self.assertTrue(len(signal.contributing_factors) > 0)
        self.assertTrue(len(signal.conflicting_factors) == 0)
    
    def test_strength_score(self):
        """测试强度评分"""
        signal = self.detector.detect_resonance(75, 70, 80)
        
        self.assertGreaterEqual(signal.strength_score, 0)
        self.assertLessEqual(signal.strength_score, 100)
    
    def test_confidence(self):
        """测试置信度"""
        signal = self.detector.detect_resonance(75, 70, 80)
        
        self.assertGreaterEqual(signal.confidence, 0)
        self.assertLessEqual(signal.confidence, 1)


class TestActionRecommendations(unittest.TestCase):
    """测试操作建议"""
    
    def setUp(self):
        """测试前初始化"""
        self.detector = ResonanceDetector()
    
    def test_strong_bullish_recommendation(self):
        """测试强看涨操作建议"""
        signal = self.detector.detect_resonance(75, 70, 80)
        self.assertIn("买", signal.action_recommendation)
    
    def test_strong_bearish_recommendation(self):
        """测试强看空操作建议"""
        signal = self.detector.detect_resonance(25, 30, 20)
        self.assertIn("卖", signal.action_recommendation)
    
    def test_weak_recommendation(self):
        """测试弱信号操作建议"""
        signal = self.detector.detect_resonance(50, 50, 50)
        self.assertIn("观望", signal.action_recommendation)


class TestMultiTimeframeDetector(unittest.TestCase):
    """测试多时间周期检测器"""
    
    def setUp(self):
        """测试前初始化"""
        self.detector = MultiTimeframeResonanceDetector()
    
    def test_multi_timeframe_detection(self):
        """测试多时间周期检测"""
        # 创建不同时间周期的信号
        detector1 = ResonanceDetector()
        detector2 = ResonanceDetector()
        detector3 = ResonanceDetector()
        
        signal1d = detector1.detect_resonance(70, 65, 75)
        signal1w = detector2.detect_resonance(72, 68, 78)
        signal1m = detector3.detect_resonance(74, 70, 80)
        
        # 测试多时间周期检测
        result = self.detector.detect_multi_timeframe_resonance({
            '1d': signal1d,
            '1w': signal1w,
            '1m': signal1m
        })
        
        self.assertIsNotNone(result)
        self.assertIn('bullish_count', result)
        self.assertIn('bearish_count', result)
        self.assertIn('multi_tf_resonance', result)
        self.assertIn('weighted_score', result)
    
    def test_mixed_timeframe_signals(self):
        """测试混合时间周期信号"""
        detector1 = ResonanceDetector()
        detector2 = ResonanceDetector()
        detector3 = ResonanceDetector()
        
        signal1d = detector1.detect_resonance(70, 65, 75)  # BULLISH
        signal1w = detector2.detect_resonance(40, 35, 38)  # BEARISH
        signal1m = detector3.detect_resonance(50, 50, 50)  # NEUTRAL
        
        result = self.detector.detect_multi_timeframe_resonance({
            '1d': signal1d,
            '1w': signal1w,
            '1m': signal1m
        })
        
        self.assertIn('multi_tf_resonance', result)
        self.assertIn('分歧', result['multi_tf_resonance'])


class TestResonanceHistoryAnalyzer(unittest.TestCase):
    """测试共振历史分析器"""
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = ResonanceHistoryAnalyzer()
        self.detector = ResonanceDetector()
    
    def test_add_signal(self):
        """测试添加信号"""
        signal = self.detector.detect_resonance(70, 65, 75)
        timestamp = pd.Timestamp.now()
        
        self.analyzer.add_signal(timestamp, signal)
        self.assertEqual(len(self.analyzer.history), 1)
    
    def test_success_rate_analysis_insufficient_data(self):
        """测试数据不足时的成功率分析"""
        signal = self.detector.detect_resonance(70, 65, 75)
        self.analyzer.add_signal(pd.Timestamp.now(), signal)
        
        result = self.analyzer.analyze_success_rate(pd.DataFrame())
        self.assertIn('message', result)


class TestResonanceVisualizer(unittest.TestCase):
    """测试共振可视化"""
    
    def setUp(self):
        """测试前初始化"""
        self.visualizer = ResonanceVisualizer()
        self.detector = ResonanceDetector()
    
    def test_generate_resonance_matrix(self):
        """测试生成共振矩阵"""
        signals = [
            self.detector.detect_resonance(70, 65, 75),
            self.detector.detect_resonance(30, 35, 25),
            self.detector.detect_resonance(50, 50, 50)
        ]
        
        matrix = self.visualizer.generate_resonance_matrix(signals)
        self.assertIsNotNone(matrix)
        self.assertGreater(len(matrix), 0)
    
    def test_generate_resonance_summary(self):
        """测试生成共振摘要"""
        signal = self.detector.detect_resonance(70, 65, 75)
        summary = self.visualizer.generate_resonance_summary(signal)
        
        self.assertIsNotNone(summary)
        self.assertIn('方向', summary)
        self.assertIn('共振等级', summary)
        self.assertIn('置信度', summary)
        self.assertIn('强度评分', summary)
        self.assertIn('操作建议', summary)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""
    
    def setUp(self):
        """测试前初始化"""
        self.detector = ResonanceDetector()
    
    def test_extreme_scores(self):
        """测试极端分数"""
        # 最高分数
        signal_high = self.detector.detect_resonance(100, 100, 100)
        self.assertEqual(signal_high.direction, SignalDirection.BULLISH)
        self.assertEqual(signal_high.level, ResonanceLevel.EXTREME_RESONANCE)
        
        # 最低分数
        signal_low = self.detector.detect_resonance(0, 0, 0)
        self.assertEqual(signal_low.direction, SignalDirection.BEARISH)
        self.assertEqual(signal_low.level, ResonanceLevel.EXTREME_RESONANCE)
    
    def test_exact_thresholds(self):
        """测试恰好等于阈值"""
        # 恰好等于看涨阈值
        signal_bullish = self.detector.detect_resonance(55, 55, 55)
        
        # 恰好等于看空阈值
        signal_bearish = self.detector.detect_resonance(45, 45, 45)
    
    def test_two_agree_one_disagree(self):
        """测试两个同意一个反对"""
        signal = self.detector.detect_resonance(75, 70, 30)
        self.assertEqual(len(signal.conflicting_factors), 1)
        self.assertEqual(len(signal.contributing_factors), 2)


if __name__ == '__main__':
    unittest.main()
