"""
A股ETF双动量轮动策略
"""

from .config import Config, ETFConfig
from .data_collector import ETFDataCollector
from .momentum import MomentumCalculator, MomentumResult
from .strategy import DualMomentumStrategy, TradeSignal, RebalanceRecord
from .backtest import BacktestEngine, BacktestResult
from .report import ReportGenerator

__version__ = "1.1.0"
__all__ = [
    "Config",
    "ETFConfig",
    "ETFDataCollector",
    "MomentumCalculator",
    "MomentumResult",
    "DualMomentumStrategy",
    "TradeSignal",
    "RebalanceRecord",
    "BacktestEngine",
    "BacktestResult",
    "ReportGenerator",
]
