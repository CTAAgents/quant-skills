"""
期货产业链+基本面+技术面 集成分析引擎
整合了产业链定性标准化、评分权重优化、共振信号检测三个模块
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# 灵活导入方式 - 支持直接运行和作为模块导入
try:
    from industry_chain_standardization import (
        IndustryChainStandardAnalyzer,
        IndustryChainMetrics,
        InventoryCycle,
        ProfitStructure,
        create_sample_metrics
    )
    from weight_optimization import (
        WeightOptimizer,
        BayesianWeightOptimizer,
        WeightSaver,
        BacktestResult
    )
    from resonance_detection import (
        ResonanceDetector,
        MultiTimeframeResonanceDetector,
        ResonanceHistoryAnalyzer,
        ResonanceVisualizer,
        ResonanceSignal,
        SignalDirection,
        ResonanceLevel
    )
except ImportError:
    from .industry_chain_standardization import (
        IndustryChainStandardAnalyzer,
        IndustryChainMetrics,
        InventoryCycle,
        ProfitStructure,
        create_sample_metrics
    )
    from .weight_optimization import (
        WeightOptimizer,
        BayesianWeightOptimizer,
        WeightSaver,
        BacktestResult
    )
    from .resonance_detection import (
        ResonanceDetector,
        MultiTimeframeResonanceDetector,
        ResonanceHistoryAnalyzer,
        ResonanceVisualizer,
        ResonanceSignal,
        SignalDirection,
        ResonanceLevel
    )


@dataclass
class FundamentalMetrics:
    """基本面量化指标"""
    supply_demand_gap: float  # 供需缺口（标准化后）
    inventory_change: float  # 库存变化率
    profit_margin: float  # 利润率
    basis_structure: float  # 基差结构（标准化后）
    historical_price_percentile: float  # 当前价格历史分位


@dataclass
class TechnicalMetrics:
    """技术面指标"""
    trend_score: float  # 趋势评分（0-100）
    momentum_score: float  # 动量评分（0-100）
    volatility_score: float  # 波动率评分（0-100）
    volume_score: float  # 成交量评分（0-100）
    pattern_score: float  # 形态评分（0-100）


@dataclass
class AnalysisResult:
    """完整分析结果"""
    # 产业链分析
    industry_chain_report: Dict
    industry_chain_score: float
    
    # 基本面分析
    fundamental_score: float
    fundamental_metrics: FundamentalMetrics
    
    # 技术面分析
    technical_score: float
    technical_metrics: TechnicalMetrics
    
    # 共振检测
    resonance_signal: ResonanceSignal
    
    # 权重配置
    used_weights: Dict[str, float]
    
    # 交易建议
    trading_plan: Dict
    
    # 风险提示
    risk_warnings: List[str]


class IntegratedAnalyzer:
    """
    集成分析引擎 - 一站式解决方案
    """
    
    def __init__(self, weights_path: Optional[str] = None):
        """
        初始化分析引擎
        
        Args:
            weights_path: 权重文件路径（可选）
        """
        # 初始化各个分析器
        self.chain_analyzer = IndustryChainStandardAnalyzer()
        self.weight_optimizer = WeightOptimizer()
        self.resonance_detector = ResonanceDetector()
        self.multi_tf_detector = MultiTimeframeResonanceDetector()
        self.history_analyzer = ResonanceHistoryAnalyzer()
        self.visualizer = ResonanceVisualizer()
        
        # 默认权重
        self.weights = self.weight_optimizer.default_weights.copy()
        
        # 如果有保存的权重，加载它们
        if weights_path:
            try:
                loaded_weights, _ = WeightSaver.load_weights(weights_path)
                self.weights = loaded_weights
                print(f"成功加载权重: {self.weights}")
            except FileNotFoundError:
                print(f"权重文件 {weights_path} 不存在，使用默认权重")
        
        # 子权重配置
        self.sub_weights = self.weight_optimizer.default_sub_weights.copy()
    
    def analyze(self,
                chain_metrics: IndustryChainMetrics,
                fundamental_metrics: FundamentalMetrics,
                technical_metrics: TechnicalMetrics,
                chain_name: str = "某产业链") -> AnalysisResult:
        """
        执行完整的三层分析流程
        
        Args:
            chain_metrics: 产业链指标
            fundamental_metrics: 基本面指标
            technical_metrics: 技术面指标
            chain_name: 产业链名称
            
        Returns:
            完整分析结果
        """
        # 1. 产业链定性分析（标准化）
        chain_report = self.chain_analyzer.generate_standard_analysis_report(
            chain_metrics, chain_name
        )
        industry_chain_score = chain_report['score']['total']
        
        # 2. 基本面量化评分
        fundamental_score = self._calculate_fundamental_score(fundamental_metrics)
        
        # 3. 技术面评分
        technical_score = self._calculate_technical_score(technical_metrics)
        
        # 4. 共振信号检测
        resonance_signal = self.resonance_detector.detect_resonance(
            industry_chain_score,
            fundamental_score,
            technical_score
        )
        
        # 5. 生成交易计划
        trading_plan = self._generate_trading_plan(
            resonance_signal,
            industry_chain_score,
            fundamental_score,
            technical_score
        )
        
        # 6. 生成风险提示
        risk_warnings = self._generate_risk_warnings(
            resonance_signal,
            chain_report
        )
        
        # 整合结果
        result = AnalysisResult(
            industry_chain_report=chain_report,
            industry_chain_score=industry_chain_score,
            fundamental_score=fundamental_score,
            fundamental_metrics=fundamental_metrics,
            technical_score=technical_score,
            technical_metrics=technical_metrics,
            resonance_signal=resonance_signal,
            used_weights=self.weights.copy(),
            trading_plan=trading_plan,
            risk_warnings=risk_warnings
        )
        
        return result
    
    def _calculate_fundamental_score(self, metrics: FundamentalMetrics) -> float:
        """
        计算基本面综合评分
        """
        weights = self.sub_weights['fundamental']
        score = (
            weights['supply_demand_gap'] * (metrics.supply_demand_gap * 50 + 50) +
            weights['inventory_change'] * (50 - metrics.inventory_change * 50) +  # 库存下降加分
            weights['profit_margin'] * (metrics.profit_margin * 50 + 50) +
            weights['basis_structure'] * (metrics.basis_structure * 50 + 50)
        )
        return max(0, min(100, score))
    
    def _calculate_technical_score(self, metrics: TechnicalMetrics) -> float:
        """
        计算技术面综合评分
        """
        weights = self.sub_weights['technical']
        score = (
            weights['trend'] * metrics.trend_score +
            weights['momentum'] * metrics.momentum_score +
            weights['volatility'] * metrics.volatility_score +
            weights['volume'] * metrics.volume_score +
            weights['pattern'] * metrics.pattern_score
        )
        return max(0, min(100, score))
    
    def _generate_trading_plan(self,
                               signal: ResonanceSignal,
                               chain_score: float,
                               fundamental_score: float,
                               technical_score: float) -> Dict:
        """
        生成标准化交易计划
        """
        # 根据共振强度确定仓位
        if signal.level in [ResonanceLevel.STRONG_RESONANCE, ResonanceLevel.EXTREME_RESONANCE]:
            position_size = 0.3 if signal.confidence > 0.8 else 0.2
        elif signal.level == ResonanceLevel.MODERATE_RESONANCE:
            position_size = 0.15
        else:
            position_size = 0.0
        
        # 止盈止损设置
        if signal.direction == SignalDirection.BULLISH:
            stop_loss_pct = -0.05
            take_profit_1 = 0.08
            take_profit_2 = 0.15
            take_profit_3 = 0.25
        elif signal.direction == SignalDirection.BEARISH:
            stop_loss_pct = 0.05
            take_profit_1 = -0.08
            take_profit_2 = -0.15
            take_profit_3 = -0.25
        else:
            stop_loss_pct = 0
            take_profit_1 = 0
            take_profit_2 = 0
            take_profit_3 = 0
        
        return {
            'core_logic': f"{signal.level.value}共振: {signal.direction.value}",
            'direction': signal.direction.value,
            'position_size': position_size,
            'stop_loss': stop_loss_pct,
            'take_profit_levels': [take_profit_1, take_profit_2, take_profit_3],
            'recommendation': signal.action_recommendation,
            'confidence': signal.confidence
        }
    
    def _generate_risk_warnings(self,
                               signal: ResonanceSignal,
                               chain_report: Dict) -> List[str]:
        """
        生成风险提示列表
        """
        warnings = []
        
        # 检查冲突因子
        if signal.conflicting_factors:
            warnings.append(f"存在冲突因子: {', '.join(signal.conflicting_factors)}")
        
        # 检查置信度
        if signal.confidence < 0.6:
            warnings.append("信号置信度较低，请谨慎操作")
        
        # 检查库存周期
        inv_cycle = chain_report.get('inventory_cycle', {}).get('stage', '')
        if inv_cycle in ['主动去库', '被动补库'] and signal.direction == SignalDirection.BULLISH:
            warnings.append(f"当前处于{inv_cycle}周期，做多需谨慎")
        
        # 检查共振强度
        if signal.level in [ResonanceLevel.WEAK_RESONANCE, ResonanceLevel.NO_RESONANCE]:
            warnings.append("共振强度较弱，建议观望为主")
        
        return warnings
    
    def optimize_weights(self, historical_data: pd.DataFrame) -> Dict:
        """
        优化权重配置
        
        Args:
            historical_data: 历史数据，需包含以下列：
                - industry_chain_score: 产业链评分
                - fundamental_score: 基本面评分
                - technical_score: 技术面评分
                - future_return: 未来收益
                
        Returns:
            优化结果对比
        """
        # 优化权重
        comparison = self.weight_optimizer.compare_default_vs_optimized(historical_data)
        
        # 更新当前权重
        self.weights = comparison['optimized']['weights']
        
        return comparison
    
    def generate_report(self, result: AnalysisResult) -> str:
        """
        生成格式化分析报告
        """
        report = []
        report.append("=" * 60)
        report.append("期货产业链+基本面+技术面 综合分析报告")
        report.append("=" * 60)
        report.append("")
        
        # 1. 产业链分析
        report.append("【1. 产业链定性分析】")
        report.append(f"   产业链: {result.industry_chain_report['chain_name']}")
        report.append(f"   库存周期: {result.industry_chain_report['inventory_cycle']['stage']} "
                     f"(置信度: {result.industry_chain_report['inventory_cycle']['confidence']:.2%})")
        report.append(f"   利润结构: {result.industry_chain_report['profit_structure']['structure']}")
        report.append(f"   综合评分: {result.industry_chain_score:.1f}/100")
        report.append(f"   趋势方向: {result.industry_chain_report['trend']['direction']} "
                     f"({result.industry_chain_report['trend']['strength']})")
        report.append("")
        
        # 2. 基本面分析
        report.append("【2. 基本面量化分析】")
        report.append(f"   供需缺口: {result.fundamental_metrics.supply_demand_gap:.2f}")
        report.append(f"   库存变化: {result.fundamental_metrics.inventory_change:.2%}")
        report.append(f"   利润率: {result.fundamental_metrics.profit_margin:.2%}")
        report.append(f"   基差结构: {result.fundamental_metrics.basis_structure:.2f}")
        report.append(f"   价格分位: {result.fundamental_metrics.historical_price_percentile:.1%}")
        report.append(f"   综合评分: {result.fundamental_score:.1f}/100")
        report.append("")
        
        # 3. 技术面分析
        report.append("【3. 技术面择时分析】")
        report.append(f"   趋势评分: {result.technical_metrics.trend_score:.1f}")
        report.append(f"   动量评分: {result.technical_metrics.momentum_score:.1f}")
        report.append(f"   波动率: {result.technical_metrics.volatility_score:.1f}")
        report.append(f"   成交量: {result.technical_metrics.volume_score:.1f}")
        report.append(f"   形态评分: {result.technical_metrics.pattern_score:.1f}")
        report.append(f"   综合评分: {result.technical_score:.1f}/100")
        report.append("")
        
        # 4. 共振信号
        report.append("【4. 三层共振检测】")
        report.append(self.visualizer.generate_resonance_summary(result.resonance_signal))
        report.append("")
        
        # 5. 权重配置
        report.append("【5. 评分权重配置】")
        for name, weight in result.used_weights.items():
            report.append(f"   {name}: {weight:.1%}")
        report.append("")
        
        # 6. 交易计划
        report.append("【6. 交易计划】")
        plan = result.trading_plan
        report.append(f"   核心逻辑: {plan['core_logic']}")
        report.append(f"   交易方向: {plan['direction']}")
        report.append(f"   建议仓位: {plan['position_size']:.1%}")
        report.append(f"   止损幅度: {plan['stop_loss']:.1%}")
        report.append(f"   止盈目标: {', '.join([f'{tp:.1%}' for tp in plan['take_profit_levels']])}")
        report.append(f"   操作建议: {plan['recommendation']}")
        report.append("")
        
        # 7. 风险提示
        if result.risk_warnings:
            report.append("【7. 风险提示】")
            for warning in result.risk_warnings:
                report.append(f"   ⚠️  {warning}")
            report.append("")
        
        report.append("=" * 60)
        report.append(f"生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)
        
        return "\n".join(report)


# ==================== 便捷使用函数 ====================

def quick_analyze(chain_metrics: IndustryChainMetrics,
                 fundamental_metrics: FundamentalMetrics,
                 technical_metrics: TechnicalMetrics,
                 chain_name: str = "某产业链") -> str:
    """
    快速分析便捷函数
    
    Returns:
        格式化分析报告
    """
    analyzer = IntegratedAnalyzer()
    result = analyzer.analyze(chain_metrics, fundamental_metrics, technical_metrics, chain_name)
    return analyzer.generate_report(result)


def create_sample_data() -> Tuple[IndustryChainMetrics, FundamentalMetrics, TechnicalMetrics]:
    """
    创建示例数据用于测试
    """
    # 产业链示例数据
    chain_metrics = create_sample_metrics()
    
    # 基本面示例数据
    fundamental_metrics = FundamentalMetrics(
        supply_demand_gap=0.15,  # 轻微供不应求
        inventory_change=-0.03,  # 库存下降3%
        profit_margin=0.12,  # 12%利润率
        basis_structure=-0.2,  # 期货贴水
        historical_price_percentile=0.35  # 处于历史35%分位
    )
    
    # 技术面示例数据
    technical_metrics = TechnicalMetrics(
        trend_score=65,  # 偏多趋势
        momentum_score=58,  # 中等动量
        volatility_score=45,  # 中等波动率
        volume_score=60,  # 成交量配合
        pattern_score=55  # 中性形态
    )
    
    return chain_metrics, fundamental_metrics, technical_metrics


if __name__ == "__main__":
    # 示例用法
    print("=" * 60)
    print("集成分析引擎 - 示例演示")
    print("=" * 60)
    print()
    
    # 创建示例数据
    chain_metrics, fund_metrics, tech_metrics = create_sample_data()
    
    # 执行分析
    report = quick_analyze(chain_metrics, fund_metrics, tech_metrics, "黑色建材产业链")
    
    # 输出报告
    print(report)
