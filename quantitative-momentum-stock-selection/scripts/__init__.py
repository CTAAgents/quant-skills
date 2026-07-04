"""
量化动量选股系统
版本: 1.0.0
基于《构建量化动量选股系统的实用指南》
"""

from .config import get_config, SystemConfig
from .data_collector import DataCollector
from .scoring import MomentumScorer, MomentumScore
from .strategy import MomentumStrategy, TradeSignal

__version__ = "1.0.0"
__author__ = "WorkBuddy"

__all__ = [
    "get_config",
    "SystemConfig",
    "DataCollector",
    "MomentumScorer",
    "MomentumScore",
    "MomentumStrategy",
    "TradeSignal",
]