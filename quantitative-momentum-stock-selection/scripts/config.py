"""
量化动量选股系统 - 配置模块
版本: 1.0.0
基于《构建量化动量选股系统的实用指南》
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path


@dataclass
class DataConfig:
    """数据配置"""
    # 数据源优先级（A股优化：增加东方财富、北向资金等数据源）
    data_sources: List[str] = field(default_factory=lambda: [
        "local_cache",      # 本地缓存
        "akshare",          # AKShare
        "eastmoney",        # 东方财富（新增：更全面的A股数据）
        "tushare",          # Tushare
    ])
    
    # 缓存配置
    cache_dir: str = "data/cache"
    cache_expire_days: int = 1
    
    # 数据采集配置
    start_date: str = "2015-01-01"  # 延长回测区间至2015年，覆盖牛熊市
    end_date: str = "2025-12-31"
    
    # 股票池配置（A股优化：支持多种股票池）
    stock_pool: str = "hs300"  # all_a_shares, hs300, zz500, zz1000, custom
    exclude_st: bool = True
    exclude_new_stocks_days: int = 60  # 排除上市不足60天的新股
    
    # A股特有配置
    limit_pct: float = 0.10  # 涨跌停比例（主板10%，科创板/创业板20%）
    enable_limit_filter: bool = True  # 启用涨跌停数据过滤


@dataclass
class MomentumConfig:
    """动量配置（A股优化：调整窗口、权重、阈值）"""
    # 动量窗口（A股优化：缩短窗口，更敏感）
    short_window: int = 15      # 短期动量窗口（交易日）- 原20天
    medium_window: int = 45     # 中期动量窗口（交易日）- 原60天
    long_window: int = 150      # 长期动量窗口（交易日）- 原252天
    
    # 动量打分权重（A股优化：提高成交量和风险控制权重）
    weights: Dict[str, float] = field(default_factory=lambda: {
        "price_momentum": 0.25,      # 价格动量（降低：A股波动大，价格动量不稳定）
        "relative_strength": 0.20,   # 相对强度（降低：行业轮动明显）
        "volume_confirmation": 0.25, # 成交量确认（提高：散户交易活跃，成交量更重要）
        "trend_structure": 0.15,     # 趋势结构（保持）
        "risk_control": 0.15,        # 风险控制（提高：A股波动大，风险控制更重要）
    })
    
    # 动量阈值（A股优化：降低阈值，更早入场离场）
    momentum_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "strong_buy": 75,    # 强烈买入（降低：更宽松）
        "buy": 65,           # 买入
        "hold": 55,          # 持有
        "reduce": 45,        # 减仓
        "sell": 35,          # 卖出
    })


@dataclass
class TrendConfig:
    """趋势配置"""
    # 趋势阶段识别参数
    trend_stages: List[str] = field(default_factory=lambda: [
        "launch",       # 启动期
        "trending",     # 主升期
        "exhausted",    # 衰竭期
        "reversal",     # 反转期
    ])
    
    # 均线系统
    ma_short: int = 10    # 短期均线
    ma_medium: int = 20   # 中期均线
    ma_long: int = 60     # 长期均线
    
    # 通道参数
    channel_period: int = 20
    channel_std: float = 2.0


@dataclass
class ValuationConfig:
    """估值配置"""
    # 估值过滤参数
    pe_percentile_threshold: float = 80.0  # PE分位阈值（%）
    pb_percentile_threshold: float = 80.0  # PB分位阈值（%）
    
    # 估值数据回看年数
    lookback_years: int = 5
    
    # 估值过滤开关
    enable_valuation_filter: bool = True


@dataclass
class RiskConfig:
    """风险配置（A股优化：更紧的止损，更保守的仓位）"""
    # 仓位限制（A股优化：更分散的投资组合）
    max_position_per_stock: float = 0.15    # 单只股票最大仓位（降低：更分散）
    max_position_per_sector: float = 0.25   # 单个行业最大仓位（降低：更分散）
    max_total_position: float = 0.70        # 总仓位上限（降低：更保守）
    
    # 止损策略（A股优化：更紧的止损）
    initial_stop_loss_atr: float = 1.5      # 初始止损倍数（降低：更紧）
    trailing_stop_loss_atr: float = 0.75    # 移动止损倍数（降低：更紧）
    time_stop_days: int = 15                # 时间止损天数（降低：更短）
    
    # 涨跌停风险控制（新增）
    max_drawdown_limit: float = 0.15        # 最大回撤限制
    limit_down_stop: bool = True            # 跌停时强制止损
    
    # 止盈策略
    take_profit_levels: Dict[str, float] = field(default_factory=lambda: {
        "level1": 0.20,  # 第一目标：盈利20%
        "level2": 0.40,  # 第二目标：盈利40%
    })
    
    take_profit_ratios: Dict[str, float] = field(default_factory=lambda: {
        "level1": 0.30,  # 第一目标减仓比例
        "level2": 0.30,  # 第二目标减仓比例
    })


@dataclass
class BacktestConfig:
    """回测配置"""
    # 回测参数
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.001      # 佣金费率
    slippage_rate: float = 0.001        # 滑点
    stamp_tax_rate: float = 0.001       # 印花税（卖出）


@dataclass
class SystemConfig:
    """系统配置"""
    # 数据配置
    data: DataConfig = field(default_factory=DataConfig)
    
    # 动量配置
    momentum: MomentumConfig = field(default_factory=MomentumConfig)
    
    # 趋势配置
    trend: TrendConfig = field(default_factory=TrendConfig)
    
    # 估值配置
    valuation: ValuationConfig = field(default_factory=ValuationConfig)
    
    # 风险配置
    risk: RiskConfig = field(default_factory=RiskConfig)
    
    # 回测配置
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    
    # 报告配置
    report_dir: str = "reports"
    report_format: str = "html"
    
    # 日志配置
    log_level: str = "INFO"
    log_file: str = "logs/system.log"


def get_config() -> SystemConfig:
    """获取系统配置"""
    return SystemConfig()


def get_default_stock_pool() -> List[str]:
    """获取默认股票池"""
    # 这里可以返回沪深300、中证500等成分股
    # 实际实现需要从数据源获取
    return []


def get_sector_mapping() -> Dict[str, str]:
    """获取行业映射"""
    # 股票代码到行业的映射
    # 实际实现需要从数据源获取
    return {}