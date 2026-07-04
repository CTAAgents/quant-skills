"""
A股ETF双动量轮动策略 - 回测引擎模块
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .config import Config
from .strategy import DualMomentumStrategy, RebalanceRecord


@dataclass
class DailyRecord:
    """每日净值记录"""
    date: datetime
    nav: float  # 净值
    holding: Optional[str]  # 当前持仓代码
    holding_name: str  # 持仓名称
    daily_return: float  # 日收益率
    benchmark_nav: float  # 基准净值
    benchmark_return: float  # 基准日收益率


@dataclass
class BacktestResult:
    """回测结果"""
    # 基本信息
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float

    # 收益指标
    total_return: float  # 总收益率
    annual_return: float  # 年化收益率
    benchmark_total_return: float  # 基准总收益率
    benchmark_annual_return: float  # 基准年化收益率
    alpha: float  # 超额收益

    # 风险指标
    max_drawdown: float  # 最大回撤
    max_drawdown_duration: int  # 最大回撤持续天数
    volatility: float  # 年化波动率
    sharpe_ratio: float  # 夏普比率
    calmar_ratio: float  # 卡尔玛比率

    # 交易指标
    total_trades: int  # 总交易次数
    win_rate: float  # 月度胜率
    turnover_rate: float  # 年化换手率

    # 持仓统计
    holding_distribution: Dict[str, float]  # 各ETF持仓占比

    # 详细记录
    daily_records: List[DailyRecord]
    rebalance_records: List[RebalanceRecord]


class BacktestEngine:
    """回测引擎"""

    def __init__(self, config: Config, strategy: DualMomentumStrategy,
                 data: Dict[str, pd.DataFrame]):
        self.config = config
        self.strategy = strategy
        self.data = data
        self.daily_records: List[DailyRecord] = []

    def run(self) -> BacktestResult:
        """运行回测"""
        # 确定回测日期范围
        start_date = pd.Timestamp(self.config.backtest_start)
        end_date = pd.Timestamp(self.config.backtest_end)

        # 获取所有ETF的共同日期
        all_dates = self._get_common_dates(start_date, end_date)

        # 检查是否有足够的数据
        if len(all_dates) < 2:
            raise ValueError(f"回测数据不足，仅有 {len(all_dates)} 个交易日，需要至少2个")

        # 初始化
        capital = self.config.initial_capital
        nav = 1.0
        benchmark_nav = 1.0
        current_holding = None
        last_rebalance_date = None
        rebalance_count = 0

        # 基准数据
        benchmark_code = self.config.benchmark.code

        # 每日循环
        for i, date in enumerate(all_dates):
            if i == 0:
                # 第一天初始化
                self.daily_records.append(DailyRecord(
                    date=date,
                    nav=nav,
                    holding=None,
                    holding_name="初始状态",
                    daily_return=0.0,
                    benchmark_nav=benchmark_nav,
                    benchmark_return=0.0
                ))
                continue

            # 获取当日数据
            prev_date = all_dates[i-1]

            # 计算基准日收益率
            benchmark_return = self._get_daily_return(benchmark_code, date, prev_date)
            benchmark_nav *= (1 + benchmark_return)

            # 判断是否需要调仓
            if self.strategy.should_rebalance(date, last_rebalance_date):
                # 截取到当日的数据用于策略计算
                data_slice = self._slice_data_to_date(date)
                signal = self.strategy.generate_signal(data_slice, date)
                current_holding = signal.selected_etf
                last_rebalance_date = date
                rebalance_count += 1

            # 计算持仓日收益率
            if current_holding:
                holding_return = self._get_daily_return(current_holding, date, prev_date)
                # 扣除交易成本（仅在调仓日，买卖双边）
                if last_rebalance_date == date:
                    # 卖出旧持仓手续费 + 买入新持仓手续费 + 滑点
                    holding_return -= (self.config.commission_rate * 2 + self.config.slippage_rate * 2)
            else:
                holding_return = 0.0

            nav *= (1 + holding_return)

            # 获取持仓名称
            holding_name = ""
            if current_holding:
                try:
                    holding_name = self.config.get_etf_by_code(current_holding).name
                except ValueError:
                    holding_name = current_holding

            # 记录每日净值
            self.daily_records.append(DailyRecord(
                date=date,
                nav=nav,
                holding=current_holding,
                holding_name=holding_name,
                daily_return=holding_return,
                benchmark_nav=benchmark_nav,
                benchmark_return=benchmark_return
            ))

        # 计算绩效指标
        result = self._calculate_performance(nav, benchmark_nav, all_dates)
        return result

    def _get_common_dates(self, start_date: pd.Timestamp,
                          end_date: pd.Timestamp) -> List[pd.Timestamp]:
        """获取所有ETF的共同交易日期"""
        date_sets = []
        for code, df in self.data.items():
            dates = set(df[
                (df["date"] >= start_date) & (df["date"] <= end_date)
            ]["date"].tolist())
            if dates:
                date_sets.append(dates)

        if not date_sets:
            return []

        common_dates = sorted(set.intersection(*date_sets))
        return common_dates

    def _get_daily_return(self, code: str, date: pd.Timestamp,
                          prev_date: pd.Timestamp) -> float:
        """获取指定ETF的日收益率"""
        df = self.data.get(code)
        if df is None:
            return 0.0

        today_price = df[df["date"] == date]["close"]
        prev_price = df[df["date"] == prev_date]["close"]

        if today_price.empty or prev_price.empty:
            return 0.0

        return (today_price.iloc[0] / prev_price.iloc[0]) - 1

    def _slice_data_to_date(self, date: pd.Timestamp) -> Dict[str, pd.DataFrame]:
        """截取到指定日期的数据"""
        sliced = {}
        for code, df in self.data.items():
            sliced[code] = df[df["date"] <= date].copy()
        return sliced

    def _calculate_performance(self, final_nav: float, final_benchmark_nav: float,
                               all_dates: List[pd.Timestamp]) -> BacktestResult:
        """计算绩效指标"""
        navs = [r.nav for r in self.daily_records]
        benchmark_navs = [r.benchmark_nav for r in self.daily_records]
        daily_returns = [r.daily_return for r in self.daily_records]
        benchmark_returns = [r.benchmark_return for r in self.daily_records]

        # 总收益率
        total_return = final_nav - 1.0
        benchmark_total_return = final_benchmark_nav - 1.0

        # 年化收益率
        years = len(all_dates) / 252
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        benchmark_annual_return = (1 + benchmark_total_return) ** (1 / years) - 1 if years > 0 else 0

        # 超额收益
        alpha = annual_return - benchmark_annual_return

        # 最大回撤
        max_drawdown, max_drawdown_duration = self._calculate_max_drawdown(navs)

        # 波动率
        volatility = np.std(daily_returns) * np.sqrt(252)

        # 夏普比率（假设无风险利率2%）
        risk_free_rate = 0.02
        sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0

        # 卡尔玛比率
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # 交易统计
        total_trades = len(self.strategy.rebalance_records)
        win_rate = self._calculate_win_rate()
        turnover_rate = total_trades / years if years > 0 else 0

        # 持仓分布
        holding_distribution = self._calculate_holding_distribution()

        return BacktestResult(
            start_date=all_dates[0],
            end_date=all_dates[-1],
            initial_capital=self.config.initial_capital,
            final_capital=self.config.initial_capital * final_nav,
            total_return=total_return,
            annual_return=annual_return,
            benchmark_total_return=benchmark_total_return,
            benchmark_annual_return=benchmark_annual_return,
            alpha=alpha,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_drawdown_duration,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            calmar_ratio=calmar_ratio,
            total_trades=total_trades,
            win_rate=win_rate,
            turnover_rate=turnover_rate,
            holding_distribution=holding_distribution,
            daily_records=self.daily_records,
            rebalance_records=self.strategy.rebalance_records
        )

    def _calculate_max_drawdown(self, navs: List[float]) -> Tuple[float, int]:
        """计算最大回撤和持续天数"""
        peak = navs[0]
        max_dd = 0
        current_dd_duration = 0
        max_dd_duration = 0

        for nav in navs:
            if nav > peak:
                peak = nav
                current_dd_duration = 0
            else:
                dd = (peak - nav) / peak
                max_dd = max(max_dd, dd)
                current_dd_duration += 1
                max_dd_duration = max(max_dd_duration, current_dd_duration)

        return -max_dd, max_dd_duration

    def _calculate_win_rate(self) -> float:
        """计算月度胜率"""
        if not self.daily_records:
            return 0.0

        # 按月统计收益
        monthly_returns = {}
        for record in self.daily_records:
            month_key = record.date.strftime("%Y-%m")
            if month_key not in monthly_returns:
                monthly_returns[month_key] = 1.0
            monthly_returns[month_key] *= (1 + record.daily_return)

        # 计算胜率
        wins = sum(1 for ret in monthly_returns.values() if ret > 1.0)
        total = len(monthly_returns)
        return wins / total if total > 0 else 0.0

    def _calculate_holding_distribution(self) -> Dict[str, float]:
        """计算持仓分布"""
        holding_days = {}
        total_days = len(self.daily_records)

        for record in self.daily_records:
            if record.holding:
                holding_days[record.holding] = holding_days.get(record.holding, 0) + 1

        # 转换为百分比
        distribution = {}
        for code, days in holding_days.items():
            try:
                name = self.config.get_etf_by_code(code).name
            except ValueError:
                name = code
            distribution[name] = days / total_days if total_days > 0 else 0.0

        return distribution
