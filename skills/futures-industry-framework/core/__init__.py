"""
期货产业链分析框架 - 核心模块
整合产业链定性标准化、评分权重优化、共振信号检测三个核心模块
"""

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

from .integrated_analyzer import (
    IntegratedAnalyzer,
    FundamentalMetrics,
    TechnicalMetrics,
    AnalysisResult,
    quick_analyze,
    create_sample_data
)

__version__ = "2.0.0"
__all__ = [
    # 产业链标准化
    'IndustryChainStandardAnalyzer',
    'IndustryChainMetrics',
    'InventoryCycle',
    'ProfitStructure',
    'create_sample_metrics',
    
    # 权重优化
    'WeightOptimizer',
    'BayesianWeightOptimizer',
    'WeightSaver',
    'BacktestResult',
    
    # 共振检测
    'ResonanceDetector',
    'MultiTimeframeResonanceDetector',
    'ResonanceHistoryAnalyzer',
    'ResonanceVisualizer',
    'ResonanceSignal',
    'SignalDirection',
    'ResonanceLevel',
    
    # 集成分析
    'IntegratedAnalyzer',
    'FundamentalMetrics',
    'TechnicalMetrics',
    'AnalysisResult',
    'quick_analyze',
    'create_sample_data',
]
