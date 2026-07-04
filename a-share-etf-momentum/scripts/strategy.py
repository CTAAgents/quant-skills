"""
A股ETF双动量轮动策略 - 策略核心逻辑模块
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .config import Config
from .momentum import MomentumCalculator, MomentumResult


@dataclass
class TradeSignal:
    """交易信号"""
    date: datetime
    action: str  # buy / sell / hold
    code: str
    name: str
    weight: float  # 仓位权重 (0-1)
    reason: str


@dataclass
class RebalanceRecord:
    """调仓记录"""
    date: datetime
    is_bullish: bool
    benchmark_return: float
    momentum_ranking: List[MomentumResult]
    selected_etf: Optional[str]
    trade_signals: List[TradeSignal]
    reason: str


class DualMomentumStrategy:
    """双动量轮动策略"""

    def __init__(self, config: Config):
        self.config = config
        self.momentum_calc = MomentumCalculator(config)
        self.rebalance_records: List[RebalanceRecord] = []
        self.current_holding: Optional[str] = None
        self._pe_data_cache: Optional[Dict[str, float]] = None

    def should_rebalance(self, current_date: datetime, last_rebalance: Optional[datetime] = None) -> bool:
        """判断是否需要调仓"""
        if last_rebalance is None:
            return True
        
        # 根据调仓频率判断
        if self.config.rebalance_freq == "weekly":
            # 每周五调仓（或者如果周五不是交易日，则在最近的交易日）
            # 简化实现：每周调仓一次，不考虑具体星期几
            days_since_last = (current_date - last_rebalance).days
            return days_since_last >= 7
        
        elif self.config.rebalance_freq == "biweekly":
            # 每两周调仓一次
            days_since_last = (current_date - last_rebalance).days
            return days_since_last >= 14
        
        else:  # monthly
            # 月末调仓（原有逻辑）
            next_day = current_date + pd.Timedelta(days=1)
            return current_date.month != next_day.month

    def generate_signal(self, data: Dict[str, pd.DataFrame],
                       current_date: Optional[datetime] = None,
                       pe_data: Optional[Dict[str, float]] = None) -> RebalanceRecord:
        """
        生成调仓信号

        Args:
            data: ETF数据字典
            current_date: 当前日期（默认取数据最新日期）
            pe_data: PE分位数据，若为None且启用估值刹车则自动获取

        Returns:
            调仓记录
        """
        if current_date is None:
            # 取所有数据的最新日期
            dates = [df["date"].max() for df in data.values() if not df.empty]
            current_date = max(dates)

        # Step 1: 绝对动量检查
        is_bullish, benchmark_return = self.momentum_calc.calculate_absolute_momentum(data)

        if not is_bullish:
            # 空头市场，全仓货币ETF
            record = RebalanceRecord(
                date=current_date,
                is_bullish=False,
                benchmark_return=benchmark_return,
                momentum_ranking=[],
                selected_etf=self.config.defensive.code,
                trade_signals=[TradeSignal(
                    date=current_date,
                    action="buy",
                    code=self.config.defensive.code,
                    name=self.config.defensive.name,
                    weight=1.0,
                    reason=f"绝对动量不满足（沪深300收益率={benchmark_return:.2%}≤0），切换至防御"
                )],
                reason=f"空头市场，沪深300ETF 252日收益率={benchmark_return:.2%}"
            )
            self.rebalance_records.append(record)
            self.current_holding = self.config.defensive.code
            return record

        # Step 2: 相对动量计算
        momentum_results = self.momentum_calc.calculate_relative_momentum(data)

        # Step 3: 估值分位刹车（若启用）
        if self.config.valuation_enabled:
            # 使用缓存的PE数据或自动获取
            if pe_data is None and self._pe_data_cache is None:
                self._pe_data_cache = self.momentum_calc.fetch_all_valuation_data()
            effective_pe_data = pe_data or self._pe_data_cache
            momentum_results = self.momentum_calc.apply_valuation_brake(momentum_results, effective_pe_data)

        # Step 4: 选股
        selected_code = self.momentum_calc.select_target(momentum_results)

        if selected_code is None:
            # 所有标的均触发刹车，持有货币ETF
            record = RebalanceRecord(
                date=current_date,
                is_bullish=True,
                benchmark_return=benchmark_return,
                momentum_ranking=momentum_results,
                selected_etf=self.config.defensive.code,
                trade_signals=[TradeSignal(
                    date=current_date,
                    action="buy",
                    code=self.config.defensive.code,
                    name=self.config.defensive.name,
                    weight=1.0,
                    reason="所有行业ETF均触发估值刹车，切换至货币ETF"
                )],
                reason="所有行业ETF估值过高，防御性持有货币ETF"
            )
        else:
            # 买入选中的行业ETF
            etf_config = self.config.get_etf_by_code(selected_code)
            record = RebalanceRecord(
                date=current_date,
                is_bullish=True,
                benchmark_return=benchmark_return,
                momentum_ranking=momentum_results,
                selected_etf=selected_code,
                trade_signals=[TradeSignal(
                    date=current_date,
                    action="buy",
                    code=selected_code,
                    name=etf_config.name,
                    weight=1.0,
                    reason=f"动量排名第一（{momentum_results[0].return_252d:.2%}），估值未触发刹车"
                )],
                reason=f"多头市场，选择动量最强的{etf_config.name}"
            )

        self.rebalance_records.append(record)
        self.current_holding = record.selected_etf
        return record

    def get_holding_at_date(self, date: datetime) -> Optional[str]:
        """获取指定日期的持仓"""
        for record in reversed(self.rebalance_records):
            if record.date <= date:
                return record.selected_etf
        return None

    def get_all_trade_signals(self) -> List[TradeSignal]:
        """获取所有交易信号"""
        signals = []
        for record in self.rebalance_records:
            signals.extend(record.trade_signals)
        return signals
