"""
量化动量选股系统 - 策略模块
版本: 1.0.0
基于《构建量化动量选股系统的实用指南》
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

from .scoring import MomentumScorer, MomentumScore


@dataclass
class TradeSignal:
    """交易信号"""
    stock_code: str
    stock_name: str
    action: str  # BUY, SELL, HOLD
    score: MomentumScore
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    position_size: Optional[float] = None
    reason: str = ""
    timestamp: datetime = None


class MomentumStrategy:
    """动量选股策略（A股优化版）"""

    def __init__(self, config=None):
        """
        初始化策略

        Args:
            config: 系统配置对象
        """
        from .config import get_config
        self.config = config or get_config()
        self.scorer = MomentumScorer(self.config)

        # 策略状态
        self.portfolio = {}  # 当前持仓
        self.watchlist = {}  # 观察列表
        self.trade_history = []  # 交易历史

    def check_limit_risk(self, stock_data: pd.DataFrame,
                        current_price: float) -> Tuple[bool, str]:
        """
        检查涨跌停风险（A股特有功能）

        Args:
            stock_data: 股票历史数据
            current_price: 当前价格

        Returns:
            (是否触发风险, 风险原因)
        """
        if not self.config.risk.limit_down_stop:
            return False, ""

        # 计算涨跌幅
        if len(stock_data) >= 2:
            prev_close = stock_data['close'].iloc[-2]
            pct_change = (current_price - prev_close) / prev_close

            # 检查是否跌停
            if pct_change <= -self.config.data.limit_pct:
                return True, f"触发跌停风险：当日跌幅{pct_change:.2%}，接近跌停"

            # 检查是否接近跌停（跌幅超过8%）
            if pct_change <= -0.08:
                return True, f"触发跌停风险预警：当日跌幅{pct_change:.2%}，接近跌停"

        # 检查连续下跌风险
        if len(stock_data) >= 5:
            recent_returns = stock_data['close'].pct_change().tail(5)
            consecutive_down = (recent_returns < 0).sum()
            if consecutive_down >= 4:
                return True, f"触发连续下跌风险：近5日有{consecutive_down}日下跌"

        return False, ""
    
    def generate_signals(self, stock_data: Dict[str, pd.DataFrame],
                        benchmark_data: Optional[pd.DataFrame] = None,
                        sector_data: Optional[pd.DataFrame] = None) -> List[TradeSignal]:
        """
        生成交易信号
        
        Args:
            stock_data: 股票数据字典 {股票代码: DataFrame}
            benchmark_data: 基准指数数据
            sector_data: 行业板块数据
        
        Returns:
            交易信号列表
        """
        signals = []
        
        for stock_code, data in stock_data.items():
            if len(data) < self.config.momentum.long_window:
                continue
            
            # 计算动量分数
            score = self.scorer.score_stock(data, benchmark_data, sector_data)
            
            # 生成交易信号
            signal = self._generate_signal_for_stock(stock_code, data, score)
            
            if signal is not None:
                signals.append(signal)
        
        # 按分数排序
        signals.sort(key=lambda x: x.score.total_score, reverse=True)
        
        return signals
    
    def _generate_signal_for_stock(self, stock_code: str,
                                  stock_data: pd.DataFrame,
                                  score: MomentumScore) -> Optional[TradeSignal]:
        """为单只股票生成交易信号（A股优化版）"""
        current_price = stock_data['close'].iloc[-1]

        # 获取股票名称（实际使用时需要从数据源获取）
        stock_name = stock_code  # 临时使用代码作为名称

        # A股优化：检查涨跌停风险
        limit_risk, limit_reason = self.check_limit_risk(stock_data, current_price)
        if limit_risk:
            # 如果触发涨跌停风险，生成卖出信号
            return TradeSignal(
                stock_code=stock_code,
                stock_name=stock_name,
                action="SELL",
                score=score,
                reason=f"涨跌停风险：{limit_reason}",
                timestamp=datetime.now()
            )

        # 根据分数和趋势阶段决定操作
        if score.grade == "STRONG" and score.trend_stage in ["launch", "trending"]:
            # 强烈买入信号
            return TradeSignal(
                stock_code=stock_code,
                stock_name=stock_name,
                action="BUY",
                score=score,
                target_price=self._calculate_target_price(current_price, score),
                stop_loss_price=self._calculate_stop_loss_price(current_price, score),
                position_size=self._calculate_position_size(score),
                reason=f"动量分数{score.total_score:.1f}，趋势阶段{score.trend_stage}",
                timestamp=datetime.now()
            )
        
        elif score.grade == "BUY" and score.trend_stage in ["launch", "trending"]:
            # 买入信号
            return TradeSignal(
                stock_code=stock_code,
                stock_name=stock_name,
                action="BUY",
                score=score,
                target_price=self._calculate_target_price(current_price, score),
                stop_loss_price=self._calculate_stop_loss_price(current_price, score),
                position_size=self._calculate_position_size(score),
                reason=f"动量分数{score.total_score:.1f}，趋势健康",
                timestamp=datetime.now()
            )
        
        elif score.grade in ["REDUCE", "SELL"] or score.trend_stage in ["exhausted", "reversal"]:
            # 卖出或减仓信号
            return TradeSignal(
                stock_code=stock_code,
                stock_name=stock_name,
                action="SELL",
                score=score,
                reason=f"动量分数{score.total_score:.1f}，趋势减弱",
                timestamp=datetime.now()
            )
        
        # 其他情况不生成信号
        return None
    
    def _calculate_target_price(self, current_price: float, score: MomentumScore) -> float:
        """计算目标价格"""
        # 基于动量强度和趋势阶段计算目标价格
        if score.grade == "STRONG":
            multiplier = 1.3  # 强势股上涨30%
        elif score.grade == "BUY":
            multiplier = 1.2  # 买入信号上涨20%
        else:
            multiplier = 1.1  # 其他情况上涨10%
        
        return current_price * multiplier
    
    def _calculate_stop_loss_price(self, current_price: float, score: MomentumScore) -> float:
        """计算止损价格"""
        # 基于ATR计算止损（这里简化处理）
        if score.grade == "STRONG":
            stop_loss_pct = 0.08  # 止损8%
        elif score.grade == "BUY":
            stop_loss_pct = 0.10  # 止损10%
        else:
            stop_loss_pct = 0.12  # 止损12%
        
        return current_price * (1 - stop_loss_pct)
    
    def _calculate_position_size(self, score: MomentumScore) -> float:
        """计算仓位大小"""
        # 基于分数和风险配置计算仓位
        if score.grade == "STRONG":
            base_position = self.config.risk.max_position_per_stock
        elif score.grade == "BUY":
            base_position = self.config.risk.max_position_per_stock * 0.7
        else:
            base_position = self.config.risk.max_position_per_stock * 0.5
        
        # 根据分数调整仓位
        score_adjustment = score.total_score / 100
        return base_position * score_adjustment
    
    def filter_by_valuation(self, signals: List[TradeSignal],
                          valuation_data: Dict[str, pd.DataFrame]) -> List[TradeSignal]:
        """
        通过估值过滤信号
        
        Args:
            signals: 交易信号列表
            valuation_data: 估值数据字典
        
        Returns:
            过滤后的交易信号列表
        """
        if not self.config.valuation.enable_valuation_filter:
            return signals
        
        filtered_signals = []
        
        for signal in signals:
            if signal.stock_code not in valuation_data:
                filtered_signals.append(signal)
                continue
            
            val_data = valuation_data[signal.stock_code]
            
            if val_data.empty:
                filtered_signals.append(signal)
                continue
            
            # 检查PE分位
            if 'pe_percentile' in val_data.columns:
                pe_percentile = val_data['pe_percentile'].iloc[-1]
                if pe_percentile > self.config.valuation.pe_percentile_threshold:
                    # 估值过高，跳过
                    continue
            
            # 检查PB分位
            if 'pb_percentile' in val_data.columns:
                pb_percentile = val_data['pb_percentile'].iloc[-1]
                if pb_percentile > self.config.valuation.pb_percentile_threshold:
                    # 估值过高，跳过
                    continue
            
            filtered_signals.append(signal)
        
        return filtered_signals
    
    def apply_risk_management(self, signals: List[TradeSignal],
                            current_portfolio: Dict[str, float]) -> List[TradeSignal]:
        """
        应用风险管理
        
        Args:
            signals: 交易信号列表
            current_portfolio: 当前持仓 {股票代码: 仓位比例}
        
        Returns:
            调整后的交易信号列表
        """
        managed_signals = []
        
        # 计算总仓位
        total_position = sum(current_portfolio.values())
        
        for signal in signals:
            if signal.action == "BUY":
                # 检查仓位限制
                if total_position >= self.config.risk.max_total_position:
                    # 总仓位已满，跳过买入信号
                    continue
                
                # 检查单只股票仓位限制
                if signal.stock_code in current_portfolio:
                    current_position = current_portfolio[signal.stock_code]
                    if current_position >= self.config.risk.max_position_per_stock:
                        # 单只股票仓位已满，跳过
                        continue
                
                # 调整仓位大小
                available_position = self.config.risk.max_total_position - total_position
                adjusted_position = min(signal.position_size, available_position)
                
                # 更新信号
                signal.position_size = adjusted_position
                managed_signals.append(signal)
            
            elif signal.action == "SELL":
                managed_signals.append(signal)
        
        return managed_signals
    
    def backtest(self, stock_data: Dict[str, pd.DataFrame],
                start_date: str, end_date: str,
                initial_capital: float = 1_000_000.0) -> Dict:
        """
        回测策略
        
        Args:
            stock_data: 股票数据字典
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
        
        Returns:
            回测结果字典
        """
        # 实现回测逻辑
        # 这里只是示例框架，实际实现需要更复杂的逻辑
        
        results = {
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': initial_capital,
            'final_capital': initial_capital,
            'total_return': 0.0,
            'annual_return': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'trade_count': 0,
            'portfolio_history': [],
            'trade_history': [],
        }
        
        return results