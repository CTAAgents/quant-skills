"""
期货产业链+基本面+技术面 一体化分析框架 - Skill Module
整合了三个核心模块：
1. 产业链定性标准化 (industry_chain_standardization)
2. 评分权重客观化 (weight_optimization)
3. 共振信号清晰化 (resonance_detection)

主要使用方式：
1. 直接使用集成引擎：from .integrated_analyzer import IntegratedAnalyzer, quick_analyze
2. 单独使用各模块：
   - from .industry_chain_standardization import IndustryChainStandardAnalyzer
   - from .weight_optimization import WeightOptimizer
   - from .resonance_detection import ResonanceDetector
"""

# 版本信息
__version__ = "2.0.0"
__author__ = "Futures Analysis Team"

# 导入主要类和函数，方便用户使用
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
    AnalysisResult,
    FundamentalMetrics,
    TechnicalMetrics,
    quick_analyze,
    create_sample_data
)

# 导出清单
__all__ = [
    # 产业链分析
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
    'AnalysisResult',
    'FundamentalMetrics',
    'TechnicalMetrics',
    'quick_analyze',
    'create_sample_data'
]
