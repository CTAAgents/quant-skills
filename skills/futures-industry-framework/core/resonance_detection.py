"""
问题3：共振信号清晰化判定模块
通过明确的量化规则消除模糊地带
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class SignalDirection(Enum):
    """信号方向"""
    BULLISH = "看多"
    BEARISH = "看空"
    NEUTRAL = "中性"


class ResonanceLevel(Enum):
    """共振强度等级"""
    NO_RESONANCE = "无共振"
    WEAK_RESONANCE = "弱共振"
    MODERATE_RESONANCE = "中等共振"
    STRONG_RESONANCE = "强共振"
    EXTREME_RESONANCE = "极强共振"


@dataclass
class ResonanceSignal:
    """共振信号"""
    direction: SignalDirection
    level: ResonanceLevel
    confidence: float  # 0-1
    strength_score: float  # 0-100
    contributing_factors: List[str]
    conflicting_factors: List[str]
    action_recommendation: str


class ResonanceDetector:
    """共振检测器 - 清晰化判定"""
    
    def __init__(self):
        # 判定阈值
        self.thresholds = {
            'industry_chain_bullish': 55,
            'industry_chain_bearish': 45,
            'fundamental_bullish': 55,
            'fundamental_bearish': 45,
            'technical_bullish': 55,
            'technical_bearish': 45,
            'strong_resonance_min': 2,
            'extreme_resonance_min': 3,
            'confidence_high': 0.8,
            'confidence_medium': 0.6,
            'confidence_low': 0.4
        }
        
        self.weights = {
            'industry_chain': 0.35,
            'fundamental': 0.30,
            'technical': 0.35
        }
    
    def get_dimension_signal(self, score: float, 
                          bullish_thresh: float, 
                          bearish_thresh: float) -> Tuple[SignalDirection, float]:
        if score > bullish_thresh:
            confidence = min(1.0, (score - 50) / (100 - bullish_thresh))
            return SignalDirection.BULLISH, confidence
        elif score < bearish_thresh:
            confidence = min(1.0, (50 - score) / (50 - bearish_thresh))
            return SignalDirection.BEARISH, confidence
        else:
            return SignalDirection.NEUTRAL, 0.5
    
    def detect_resonance(self,
                      industry_score: float,
                      fundamental_score: float,
                      technical_score: float) -> ResonanceSignal:
        industry_signal, industry_conf = self.get_dimension_signal(
            industry_score,
            self.thresholds['industry_chain_bullish'],
            self.thresholds['industry_chain_bearish']
        )
        
        fundamental_signal, fundamental_conf = self.get_dimension_signal(
            fundamental_score,
            self.thresholds['fundamental_bullish'],
            self.thresholds['fundamental_bearish']
        )
        
        technical_signal, technical_conf = self.get_dimension_signal(
            technical_score,
            self.thresholds['technical_bullish'],
            self.thresholds['technical_bearish']
        )
        
        signals = [
            ('industry_chain', industry_signal, industry_conf),
            ('fundamental', fundamental_signal, fundamental_conf),
            ('technical', technical_signal, technical_conf)
        ]
        
        bullish_count = sum(1 for _, sig, _ in signals if sig == SignalDirection.BULLISH)
        bearish_count = sum(1 for _, sig, _ in signals if sig == SignalDirection.BEARISH)
        neutral_count = sum(1 for _, sig, _ in signals if sig == SignalDirection.NEUTRAL)
        
        # 优先处理有明确方向的信号，忽略中性信号的计数
        if bullish_count > bearish_count:
            main_direction = SignalDirection.BULLISH
        elif bearish_count > bullish_count:
            main_direction = SignalDirection.BEARISH
        else:
            main_direction = SignalDirection.NEUTRAL
        
        confidences = []
        contributing = []
        conflicting = []
        
        for name, sig, conf in signals:
            if sig == main_direction and sig != SignalDirection.NEUTRAL:
                # 只统计有明确方向且与主方向一致的信号
                confidences.append(conf)
                contributing.append(name)
            elif sig != SignalDirection.NEUTRAL and sig != main_direction:
                conflicting.append(name)
        
        if confidences:
            total_confidence = np.mean(confidences)
        else:
            total_confidence = 0.5
        
        agree_count = len(contributing)
        # 如果主方向是中性，特殊处理
        if main_direction == SignalDirection.NEUTRAL:
            if neutral_count == 3:
                resonance_level = ResonanceLevel.WEAK_RESONANCE
            else:
                resonance_level = ResonanceLevel.MODERATE_RESONANCE
        elif agree_count == 3:
            resonance_level = ResonanceLevel.EXTREME_RESONANCE
        elif agree_count == 2:
            resonance_level = ResonanceLevel.STRONG_RESONANCE
        elif agree_count == 1:
            resonance_level = ResonanceLevel.MODERATE_RESONANCE
        else:
            resonance_level = ResonanceLevel.WEAK_RESONANCE
        
        weighted_score = (
            self.weights['industry_chain'] * industry_score +
            self.weights['fundamental'] * fundamental_score +
            self.weights['technical'] * technical_score
        )
        
        action = self._generate_action_recommendation(
            main_direction, resonance_level, total_confidence, weighted_score
        )
        
        return ResonanceSignal(
            direction=main_direction,
            level=resonance_level,
            confidence=float(total_confidence),
            strength_score=float(weighted_score),
            contributing_factors=contributing,
            conflicting_factors=conflicting,
            action_recommendation=action
        )
    
    def _generate_action_recommendation(self,
                                   direction: SignalDirection,
                                   level: ResonanceLevel,
                                   confidence: float,
                                   score: float) -> str:
        if level in [ResonanceLevel.STRONG_RESONANCE, ResonanceLevel.EXTREME_RESONANCE]:
            if direction == SignalDirection.BULLISH:
                if confidence > self.thresholds['confidence_high']:
                    return "强烈建议买入"
                else:
                    return "建议买入"
            elif direction == SignalDirection.BEARISH:
                if confidence > self.thresholds['confidence_high']:
                    return "强烈建议卖出"
                else:
                    return "建议卖出"
            else:
                return "观望"
        elif level == ResonanceLevel.MODERATE_RESONANCE:
            if direction == SignalDirection.BULLISH:
                return "轻仓尝试买入"
            elif direction == SignalDirection.BEARISH:
                return "轻仓尝试卖出"
            else:
                return "观望"
        elif level == ResonanceLevel.WEAK_RESONANCE:
            return "观望，等待更明确信号"
        else:
            return "观望"


class MultiTimeframeResonanceDetector:
    """多时间周期共振检测器"""
    
    def __init__(self):
        self.timeframes = ['1d', '1w', '1m']
        self.timeframe_weights = {
            '1d': 0.3,
            '1w': 0.4,
            '1m': 0.3
        }
    
    def detect_multi_timeframe_resonance(self,
                                      timeframe_signals: Dict[str, ResonanceSignal]) -> Dict:
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        
        for tf, signal in timeframe_signals.items():
            if signal.direction == SignalDirection.BULLISH:
                bullish_count += 1
            elif signal.direction == SignalDirection.BEARISH:
                bearish_count += 1
            else:
                neutral_count += 1
        
        weighted_score = 0
        for tf, signal in timeframe_signals.items():
            weight = self.timeframe_weights.get(tf, 1/len(timeframe_signals))
            if signal:
                if signal.direction == SignalDirection.BULLISH:
                    weighted_score += signal.strength_score * weight
                elif signal.direction == SignalDirection.BEARISH:
                    weighted_score -= (100 - signal.strength_score) * weight
                else:
                    weighted_score += 50 * weight
        
        if bullish_count == 3:
            multi_tf_resonance = "多周期强看多"
        elif bullish_count == 2:
            multi_tf_resonance = "多周期偏多"
        elif bearish_count == 3:
            multi_tf_resonance = "多周期强看空"
        elif bearish_count == 2:
            multi_tf_resonance = "多周期偏空"
        else:
            multi_tf_resonance = "多周期分歧"
        
        return {
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'neutral_count': neutral_count,
            'multi_tf_resonance': multi_tf_resonance,
            'weighted_score': weighted_score,
            'timeframe_signals': {
                tf: {
                    'direction': sig.direction.value,
                    'level': sig.level.value,
                    'confidence': sig.confidence
                } for tf, sig in timeframe_signals.items()
            }
        }


class ResonanceHistoryAnalyzer:
    """共振历史分析器"""
    
    def __init__(self):
        self.history = []
    
    def add_signal(self, timestamp: pd.Timestamp, signal: ResonanceSignal):
        self.history.append({
            'timestamp': timestamp,
            'signal': signal
        })
    
    def analyze_success_rate(self, price_history: pd.DataFrame) -> Dict:
        if len(self.history) < 10:
            return {'message': '历史数据不足，无法分析'}
        
        results = []
        for i, entry in enumerate(self.history[:-1]):
            next_entry = self.history[i + 1]
            
            try:
                start_idx = price_history.index.get_loc(entry['timestamp'])
                end_idx = price_history.index.get_loc(next_entry['timestamp'])
                future_return = price_history.iloc[start_idx:end_idx]['return'].sum()
            except:
                continue
            
            signal = entry['signal']
            
            if signal.direction == SignalDirection.BULLISH:
                is_correct = future_return > 0
            elif signal.direction == SignalDirection.BEARISH:
                is_correct = future_return < 0
            else:
                is_correct = abs(future_return) < 0.01
            
            results.append({
                'timestamp': entry['timestamp'],
                'direction': signal.direction.value,
                'level': signal.level.value,
                'is_correct': is_correct
            })
        
        total = len(results)
        correct = sum(1 for r in results if r['is_correct'])
        success_rate = correct / total if total > 0 else 0
        
        level_success = {}
        for level in ResonanceLevel:
            level_results = [r for r in results if r['level'] == level.value]
            level_correct = sum(1 for r in level_results if r['is_correct'])
            level_total = len(level_results)
            level_success[level.value] = level_correct / level_total if level_total > 0 else 0
        
        return {
            'total_signals': total,
            'correct_signals': correct,
            'success_rate': success_rate,
            'level_success_rates': level_success
        }


class ResonanceVisualizer:
    """共振信号可视化"""
    
    @staticmethod
    def generate_resonance_matrix(signals: List[ResonanceSignal]) -> str:
        matrix = []
        for signal in signals:
            row = [
                signal.direction.value,
                signal.level.value,
                f"{signal.confidence:.2f}",
                f"{signal.strength_score:.1f}",
                signal.action_recommendation
            ]
            matrix.append(row)
        
        headers = ["方向", "共振等级", "置信度", "强度评分", "操作建议"]
        table = "\t".join(headers) + "\n"
        for row in matrix:
            table += "\t".join(row) + "\n"
        
        return table
    
    @staticmethod
    def generate_resonance_summary(signal: ResonanceSignal) -> str:
        summary = f"""
共振信号摘要
============
方向: {signal.direction.value}
共振等级: {signal.level.value}
置信度: {signal.confidence:.2%}
强度评分: {signal.strength_score:.1f}/100
贡献因子: {', '.join(signal.contributing_factors)}
冲突因子: {', '.join(signal.conflicting_factors) if signal.conflicting_factors else '无'}
操作建议: {signal.action_recommendation}
"""
        return summary.strip()
