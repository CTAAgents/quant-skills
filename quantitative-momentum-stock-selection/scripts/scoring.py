"""
量化动量选股系统 - 动量打分模块
版本: 1.0.0
基于《构建量化动量选股系统的实用指南》
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class MomentumScore:
    """动量分数结果"""
    total_score: float  # 总分（0-100）
    components: Dict[str, float]  # 各维度分数
    grade: str  # 等级：STRONG/BUY/HOLD/REDUCE/SELL
    trend_stage: str  # 趋势阶段
    details: Dict[str, any]  # 详细信息


class MomentumScorer:
    """动量打分器（A股优化版）"""
    
    def __init__(self, config=None):
        """
        初始化动量打分器
        
        Args:
            config: 动量配置对象
        """
        from .config import get_config
        self.config = config or get_config()
        self.momentum_config = self.config.momentum
        self.trend_config = self.config.trend
    
    def filter_limit_up_down(self, data: pd.DataFrame, limit_pct: float = 0.10) -> pd.DataFrame:
        """
        过滤涨跌停数据（A股特有功能）
        
        Args:
            data: 股票历史数据
            limit_pct: 涨跌停比例（默认10%）
        
        Returns:
            过滤后的数据
        """
        if not self.config.data.enable_limit_filter:
            return data
        
        # 计算涨跌幅
        data = data.copy()
        data['pct_change'] = data['close'].pct_change()
        
        # 标记涨跌停
        data['is_limit_up'] = data['pct_change'] >= limit_pct
        data['is_limit_down'] = data['pct_change'] <= -limit_pct
        
        # 过滤涨跌停数据（保留非涨跌停数据用于计算）
        filtered_data = data[~(data['is_limit_up'] | data['is_limit_down'])].copy()
        
        # 如果过滤后数据不足，返回原始数据
        if len(filtered_data) < self.momentum_config.long_window:
            return data
        
        return filtered_data
    
    def score_stock(self, stock_data: pd.DataFrame,
                   benchmark_data: Optional[pd.DataFrame] = None,
                   sector_data: Optional[pd.DataFrame] = None) -> MomentumScore:
        """
        计算单只股票的动量分数（A股优化版）
        
        Args:
            stock_data: 股票历史数据（包含OHLCV）
            benchmark_data: 基准指数数据（如沪深300）
            sector_data: 行业板块数据
        
        Returns:
            MomentumScore: 动量分数结果
        """
        # A股优化：过滤涨跌停数据
        filtered_data = self.filter_limit_up_down(stock_data, self.config.data.limit_pct)
        
        # 使用过滤后的数据计算各维度分数
        price_score = self._calculate_price_momentum(filtered_data)
        relative_score = self._calculate_relative_strength(
            filtered_data, benchmark_data, sector_data
        )
        volume_score = self._calculate_volume_confirmation(filtered_data)
        trend_score = self._calculate_trend_structure(filtered_data)
        risk_score = self._calculate_risk_control(filtered_data)
        
        # 加权计算总分
        total_score = (
            price_score * self.momentum_config.weights['price_momentum'] +
            relative_score * self.momentum_config.weights['relative_strength'] +
            volume_score * self.momentum_config.weights['volume_confirmation'] +
            trend_score * self.momentum_config.weights['trend_structure'] +
            risk_score * self.momentum_config.weights['risk_control']
        )
        
        # 确定等级
        grade = self._determine_grade(total_score)
        
        # 识别趋势阶段
        trend_stage = self._identify_trend_stage(stock_data)
        
        # 构建详细信息
        details = {
            'price_momentum_detail': self._get_price_momentum_detail(stock_data),
            'relative_strength_detail': self._get_relative_strength_detail(
                stock_data, benchmark_data, sector_data
            ),
            'volume_detail': self._get_volume_detail(stock_data),
            'trend_detail': self._get_trend_detail(stock_data),
            'risk_detail': self._get_risk_detail(stock_data),
        }
        
        return MomentumScore(
            total_score=total_score,
            components={
                'price_momentum': price_score,
                'relative_strength': relative_score,
                'volume_confirmation': volume_score,
                'trend_structure': trend_score,
                'risk_control': risk_score,
            },
            grade=grade,
            trend_stage=trend_stage,
            details=details
        )
    
    def _calculate_price_momentum(self, stock_data: pd.DataFrame) -> float:
        """
        计算价格动量分数（30分）
        
        基于不同时间窗口的收益率
        """
        if len(stock_data) < self.momentum_config.long_window:
            return 0.0
        
        # 计算不同时间窗口的收益率
        short_return = self._calculate_return(stock_data, self.momentum_config.short_window)
        medium_return = self._calculate_return(stock_data, self.momentum_config.medium_window)
        long_return = self._calculate_return(stock_data, self.momentum_config.long_window)
        
        # 归一化到0-30分
        short_score = self._normalize_return_to_score(short_return, max_score=10)
        medium_score = self._normalize_return_to_score(medium_return, max_score=10)
        long_score = self._normalize_return_to_score(long_return, max_score=10)
        
        # 加权平均
        total_price_score = short_score * 0.4 + medium_score * 0.35 + long_score * 0.25
        
        return total_price_score
    
    def _calculate_return(self, data: pd.DataFrame, window: int) -> float:
        """计算收益率"""
        if len(data) < window:
            return 0.0
        
        current_price = data['close'].iloc[-1]
        past_price = data['close'].iloc[-window]
        
        return (current_price - past_price) / past_price
    
    def _normalize_return_to_score(self, ret: float, max_score: float = 30.0) -> float:
        """将收益率归一化到分数"""
        # 使用sigmoid函数进行归一化
        # 收益率越高，分数越高
        normalized = 1 / (1 + np.exp(-ret * 10))
        return normalized * max_score
    
    def _calculate_relative_strength(self, stock_data: pd.DataFrame,
                                   benchmark_data: Optional[pd.DataFrame] = None,
                                   sector_data: Optional[pd.DataFrame] = None) -> float:
        """
        计算相对强度分数（25分）
        
        相对于基准和行业的表现
        """
        # 计算股票相对于基准的强度
        benchmark_strength = 0.0
        if benchmark_data is not None and len(benchmark_data) > 0:
            stock_return = self._calculate_return(stock_data, self.momentum_config.medium_window)
            benchmark_return = self._calculate_return(benchmark_data, self.momentum_config.medium_window)
            
            if benchmark_return != 0:
                relative_return = stock_return - benchmark_return
                benchmark_strength = self._normalize_return_to_score(relative_return, max_score=12.5)
        
        # 计算股票相对于行业的强度
        sector_strength = 0.0
        if sector_data is not None and len(sector_data) > 0:
            # 这里需要实现行业相对强度的计算
            sector_strength = 6.25  # 默认中等分数
        
        return benchmark_strength + sector_strength
    
    def _calculate_volume_confirmation(self, stock_data: pd.DataFrame) -> float:
        """
        计算成交量确认分数（20分）
        
        量价配合、成交量趋势
        """
        if len(stock_data) < 20:
            return 0.0
        
        # 计算成交量变化
        recent_volume = stock_data['volume'].iloc[-5:].mean()
        past_volume = stock_data['volume'].iloc[-20:-5].mean()
        
        volume_change = (recent_volume - past_volume) / past_volume if past_volume > 0 else 0
        
        # 计算量价配合
        price_change = (stock_data['close'].iloc[-1] - stock_data['close'].iloc[-5]) / stock_data['close'].iloc[-5]
        
        # 量价同向为正，量价背离为负
        if price_change > 0 and volume_change > 0:
            # 上涨放量，健康
            volume_score = 15.0
        elif price_change < 0 and volume_change < 0:
            # 下跌缩量，相对健康
            volume_score = 10.0
        elif price_change > 0 and volume_change < 0:
            # 上涨缩量，不健康
            volume_score = 5.0
        else:
            # 下跌放量，不健康
            volume_score = 2.0
        
        # 考虑成交量趋势
        volume_trend = self._calculate_volume_trend(stock_data)
        volume_score += volume_trend * 5.0
        
        return min(volume_score, 20.0)
    
    def _calculate_volume_trend(self, data: pd.DataFrame) -> float:
        """计算成交量趋势"""
        if len(data) < 20:
            return 0.0
        
        # 计算5日成交量均值和20日成交量均值
        vol_5 = data['volume'].iloc[-5:].mean()
        vol_20 = data['volume'].iloc[-20:].mean()
        
        if vol_20 == 0:
            return 0.0
        
        # 计算成交量比率
        vol_ratio = vol_5 / vol_20
        
        # 归一化到-1到1
        return np.clip((vol_ratio - 1) * 2, -1, 1)
    
    def _calculate_trend_structure(self, stock_data: pd.DataFrame) -> float:
        """
        计算趋势结构分数（15分）
        
        均线排列、通道位置
        """
        if len(stock_data) < self.trend_config.ma_long:
            return 0.0
        
        # 计算均线
        ma_short = stock_data['close'].rolling(self.trend_config.ma_short).mean()
        ma_medium = stock_data['close'].rolling(self.trend_config.ma_medium).mean()
        ma_long = stock_data['close'].rolling(self.trend_config.ma_long).mean()
        
        # 当前价格和均线值
        current_price = stock_data['close'].iloc[-1]
        ma_short_val = ma_short.iloc[-1]
        ma_medium_val = ma_medium.iloc[-1]
        ma_long_val = ma_long.iloc[-1]
        
        # 均线排列打分
        ma_score = 0.0
        
        # 多头排列：短期 > 中期 > 长期
        if ma_short_val > ma_medium_val > ma_long_val:
            ma_score = 10.0
        # 空头排列：短期 < 中期 < 长期
        elif ma_short_val < ma_medium_val < ma_long_val:
            ma_score = 2.0
        # 其他情况
        else:
            ma_score = 6.0
        
        # 价格相对均线位置
        price_vs_ma = 0.0
        if current_price > ma_short_val:
            price_vs_ma += 2.5
        if current_price > ma_medium_val:
            price_vs_ma += 2.5
        if current_price > ma_long_val:
            price_vs_ma += 2.5
        
        return ma_score + price_vs_ma
    
    def _calculate_risk_control(self, stock_data: pd.DataFrame) -> float:
        """
        计算风险控制分数（10分）
        
        波动率、回撤控制
        """
        if len(stock_data) < 20:
            return 0.0
        
        # 计算波动率
        returns = stock_data['close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252)  # 年化波动率
        
        # 波动率越低，分数越高（在合理范围内）
        if volatility < 0.2:
            vol_score = 5.0
        elif volatility < 0.3:
            vol_score = 4.0
        elif volatility < 0.4:
            vol_score = 3.0
        else:
            vol_score = 2.0
        
        # 计算最大回撤
        cumulative = (1 + returns).cumprod()
        rolling_max = cumulative.expanding().max()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # 回撤越小，分数越高
        if max_drawdown > -0.1:
            dd_score = 5.0
        elif max_drawdown > -0.2:
            dd_score = 4.0
        elif max_drawdown > -0.3:
            dd_score = 3.0
        else:
            dd_score = 2.0
        
        return vol_score + dd_score
    
    def _determine_grade(self, score: float) -> str:
        """确定动量等级"""
        thresholds = self.momentum_config.momentum_thresholds
        
        if score >= thresholds['strong_buy']:
            return "STRONG"
        elif score >= thresholds['buy']:
            return "BUY"
        elif score >= thresholds['hold']:
            return "HOLD"
        elif score >= thresholds['reduce']:
            return "REDUCE"
        else:
            return "SELL"
    
    def _identify_trend_stage(self, stock_data: pd.DataFrame) -> str:
        """识别趋势阶段"""
        if len(stock_data) < self.trend_config.ma_long:
            return "unknown"
        
        # 计算技术指标
        ma_short = stock_data['close'].rolling(self.trend_config.ma_short).mean()
        ma_medium = stock_data['close'].rolling(self.trend_config.ma_medium).mean()
        ma_long = stock_data['close'].rolling(self.trend_config.ma_long).mean()
        
        # 计算动量
        momentum = stock_data['close'].pct_change(20).iloc[-1]
        
        # 判断趋势阶段
        if ma_short.iloc[-1] > ma_medium.iloc[-1] > ma_long.iloc[-1]:
            if momentum > 0.1:
                return "trending"  # 主升期
            else:
                return "launch"  # 启动期
        elif ma_short.iloc[-1] < ma_medium.iloc[-1] < ma_long.iloc[-1]:
            if momentum < -0.1:
                return "reversal"  # 反转期
            else:
                return "exhausted"  # 衰竭期
        else:
            return "transition"  # 过渡期
    
    def _get_price_momentum_detail(self, stock_data: pd.DataFrame) -> Dict:
        """获取价格动量详细信息"""
        return {
            'short_return': self._calculate_return(stock_data, self.momentum_config.short_window),
            'medium_return': self._calculate_return(stock_data, self.momentum_config.medium_window),
            'long_return': self._calculate_return(stock_data, self.momentum_config.long_window),
        }
    
    def _get_relative_strength_detail(self, stock_data: pd.DataFrame,
                                    benchmark_data: Optional[pd.DataFrame] = None,
                                    sector_data: Optional[pd.DataFrame] = None) -> Dict:
        """获取相对强度详细信息"""
        return {
            'vs_benchmark': 0.0,  # 需要实现
            'vs_sector': 0.0,     # 需要实现
        }
    
    def _get_volume_detail(self, stock_data: pd.DataFrame) -> Dict:
        """获取成交量详细信息"""
        return {
            'volume_change': 0.0,  # 需要实现
            'volume_trend': 0.0,   # 需要实现
        }
    
    def _get_trend_detail(self, stock_data: pd.DataFrame) -> Dict:
        """获取趋势详细信息"""
        return {
            'ma_alignment': 'unknown',  # 需要实现
            'price_vs_ma': 0.0,         # 需要实现
        }
    
    def _get_risk_detail(self, stock_data: pd.DataFrame) -> Dict:
        """获取风险详细信息"""
        return {
            'volatility': 0.0,     # 需要实现
            'max_drawdown': 0.0,   # 需要实现
        }