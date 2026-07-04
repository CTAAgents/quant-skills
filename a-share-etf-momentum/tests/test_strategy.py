"""
A股ETF双动量轮动策略 - 单元测试
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config import Config, ETFConfig
from scripts.momentum import MomentumCalculator, MomentumResult
from scripts.strategy import DualMomentumStrategy
from scripts.backtest import BacktestEngine


# 固定随机种子，确保测试确定性
np.random.seed(42)


def generate_mock_data(code: str, days: int = 300,
                       trend: str = "up", seed: int = 42,
                       end_date: datetime = None) -> pd.DataFrame:
    """生成模拟ETF数据（确定性）"""
    rng = np.random.RandomState(seed)
    if end_date is None:
        end_date = datetime.now()
    dates = pd.date_range(end=end_date, periods=days, freq="B")

    if trend == "up":
        base = 100
        noise = rng.randn(days) * 0.5
        trend_component = np.linspace(0, 30, days)
        close = base + trend_component + noise.cumsum() * 0.1
    elif trend == "down":
        base = 130
        noise = rng.randn(days) * 0.5
        trend_component = np.linspace(0, -30, days)
        close = base + trend_component + noise.cumsum() * 0.1
    elif trend == "strong_up":
        base = 100
        noise = rng.randn(days) * 0.3
        trend_component = np.linspace(0, 50, days)
        close = base + trend_component + noise.cumsum() * 0.05
    else:  # flat
        base = 100
        close = base + rng.randn(days) * 2

    close = np.maximum(close, 10)  # 防止负数

    return pd.DataFrame({
        "date": dates,
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": rng.randint(1000000, 10000000, days),
        "amount": rng.randint(10000000, 100000000, days)
    })


class TestConfig:
    """测试配置模块"""

    def test_default_config(self):
        config = Config()
        assert config.momentum_window == 252
        assert config.benchmark.code == "510300"
        assert len(config.industry_etfs) == 6
        assert config.defensive.code == "511880"

    def test_all_etf_codes(self):
        config = Config()
        codes = config.all_etf_codes
        assert "510300" in codes
        assert "511880" in codes
        assert "512400" in codes
        assert len(codes) == 8  # 1 benchmark + 6 industry + 1 defensive

    def test_industry_codes(self):
        config = Config()
        codes = config.industry_codes
        assert len(codes) == 6
        assert "512400" in codes
        assert "510300" not in codes  # benchmark not in industry
        assert "511880" not in codes  # defensive not in industry

    def test_get_etf_by_code(self):
        config = Config()
        etf = config.get_etf_by_code("510300")
        assert etf.name == "沪深300ETF"
        assert etf.category == "benchmark"

        etf = config.get_etf_by_code("512400")
        assert etf.name == "有色金属ETF"
        assert etf.category == "industry"

    def test_get_index_code(self):
        config = Config()
        assert config.get_index_code("510300") == "000300"
        assert config.get_index_code("512400") == "399395"
        assert config.get_index_code("511880") is None

    def test_valuation_enabled_default(self):
        config = Config()
        assert config.valuation_enabled is True


class TestMomentumCalculator:
    """测试动量计算模块"""

    def setup_method(self):
        self.config = Config()
        self.calc = MomentumCalculator(self.config)

    def test_absolute_momentum_bullish(self):
        """测试绝对动量 - 多头市场"""
        data = {
            "510300": generate_mock_data("510300", 300, "up")
        }
        is_bullish, return_252d = self.calc.calculate_absolute_momentum(data)
        assert bool(is_bullish) is True
        assert return_252d > 0

    def test_absolute_momentum_bearish(self):
        """测试绝对动量 - 空头市场"""
        data = {
            "510300": generate_mock_data("510300", 300, "down")
        }
        is_bullish, return_252d = self.calc.calculate_absolute_momentum(data)
        assert bool(is_bullish) is False
        assert return_252d <= 0

    def test_absolute_momentum_insufficient_data(self):
        """测试绝对动量 - 数据不足"""
        data = {
            "510300": generate_mock_data("510300", 100, "up")
        }
        is_bullish, return_252d = self.calc.calculate_absolute_momentum(data)
        assert is_bullish is False
        assert return_252d == 0.0

    def test_absolute_momentum_missing_benchmark(self):
        """测试绝对动量 - 缺少基准数据"""
        data = {
            "512400": generate_mock_data("512400", 300, "up")
        }
        is_bullish, return_252d = self.calc.calculate_absolute_momentum(data)
        assert is_bullish is False
        assert return_252d == 0.0

    def test_relative_momentum_ranking(self):
        """测试相对动量排名"""
        data = {}
        # 生成不同动量的ETF数据
        for i, etf in enumerate(self.config.industry_etfs):
            data[etf.code] = generate_mock_data(etf.code, 300, "up", seed=42+i)

        results = self.calc.calculate_relative_momentum(data)

        # 验证排序
        assert len(results) > 0
        for i in range(len(results) - 1):
            assert results[i].return_252d >= results[i+1].return_252d
            assert results[i].rank == i + 1

    def test_relative_momentum_missing_data(self):
        """测试相对动量 - 部分数据缺失"""
        data = {
            "512400": generate_mock_data("512400", 300, "up"),
            "510650": generate_mock_data("510650", 300, "up"),
        }
        results = self.calc.calculate_relative_momentum(data)
        assert len(results) == 2

    def test_valuation_brake_triggered(self):
        """测试估值刹车触发"""
        results = [
            MomentumResult(code="512400", name="有色金属ETF",
                          return_252d=0.35, rank=1),
            MomentumResult(code="510650", name="银行ETF",
                          return_252d=0.20, rank=2),
        ]

        pe_data = {"512400": 85.0, "510650": 50.0}  # 有色金属PE分位85%

        results = self.calc.apply_valuation_brake(results, pe_data)

        # 有色金属应触发刹车（PE 85% > 80% 且涨幅 35% > 30%）
        assert results[0].valuation_triggered is True
        # 银行不应触发刹车
        assert results[1].valuation_triggered is False

    def test_valuation_brake_not_triggered_low_pe(self):
        """测试估值刹车未触发 - PE分位不够高"""
        results = [
            MomentumResult(code="512400", name="有色金属ETF",
                          return_252d=0.35, rank=1),
        ]

        pe_data = {"512400": 70.0}  # PE分位70% < 80%

        results = self.calc.apply_valuation_brake(results, pe_data)
        assert results[0].valuation_triggered is False

    def test_valuation_brake_not_triggered_low_return(self):
        """测试估值刹车未触发 - 涨幅不够高"""
        results = [
            MomentumResult(code="512400", name="有色金属ETF",
                          return_252d=0.20, rank=1),  # 涨幅20% < 30%
        ]

        pe_data = {"512400": 85.0}  # PE分位85% > 80%

        results = self.calc.apply_valuation_brake(results, pe_data)
        assert results[0].valuation_triggered is False

    def test_valuation_brake_no_pe_data(self):
        """测试估值刹车 - 无PE数据"""
        results = [
            MomentumResult(code="512400", name="有色金属ETF",
                          return_252d=0.35, rank=1),
        ]

        results = self.calc.apply_valuation_brake(results, None)
        assert results[0].valuation_triggered is False

    def test_select_target(self):
        """测试选股逻辑"""
        # 场景1：第一名未触发刹车
        results = [
            MomentumResult(code="512400", name="有色金属ETF",
                          return_252d=0.35, rank=1, valuation_triggered=False),
            MomentumResult(code="510650", name="银行ETF",
                          return_252d=0.20, rank=2, valuation_triggered=False),
        ]
        target = self.calc.select_target(results)
        assert target == "512400"

        # 场景2：第一名触发刹车，选第二名
        results[0].valuation_triggered = True
        target = self.calc.select_target(results)
        assert target == "510650"

        # 场景3：全部触发刹车
        results[1].valuation_triggered = True
        target = self.calc.select_target(results)
        assert target is None

    def test_select_target_empty_list(self):
        """测试选股逻辑 - 空列表"""
        target = self.calc.select_target([])
        assert target is None


class TestDualMomentumStrategy:
    """测试策略核心逻辑"""

    def setup_method(self):
        self.config = Config()
        self.config.valuation_enabled = False  # 测试时禁用估值刹车（避免网络请求）
        self.strategy = DualMomentumStrategy(self.config)

    def test_should_rebalance_monthly(self):
        """测试月末调仓判断"""
        # 首次总是调仓
        date1 = pd.Timestamp("2026-06-01")
        assert self.strategy.should_rebalance(date1) is True

        # 月末应调仓
        date2 = pd.Timestamp("2026-06-30")
        last_rebalance = pd.Timestamp("2026-05-31")
        assert self.strategy.should_rebalance(date2, last_rebalance) is True

        # 同月内不应调仓
        date3 = pd.Timestamp("2026-06-15")
        last_rebalance = pd.Timestamp("2026-06-01")
        assert self.strategy.should_rebalance(date3, last_rebalance) is False

    def test_generate_signal_bearish(self):
        """测试空头市场信号生成"""
        # 生成下跌的基准数据
        data = {
            "510300": generate_mock_data("510300", 300, "down"),
            "512400": generate_mock_data("512400", 300, "up"),
            "510650": generate_mock_data("510650", 300, "up"),
            "516860": generate_mock_data("516860", 300, "up"),
            "159928": generate_mock_data("159928", 300, "up"),
            "512010": generate_mock_data("512010", 300, "up"),
            "515000": generate_mock_data("515000", 300, "up"),
            "511880": generate_mock_data("511880", 300, "flat"),
        }

        signal = self.strategy.generate_signal(data)

        # 空头市场应选择货币ETF
        assert signal.selected_etf == "511880"
        assert signal.is_bullish is False

    def test_generate_signal_bullish(self):
        """测试多头市场信号生成"""
        # 生成上涨的基准数据
        data = {
            "510300": generate_mock_data("510300", 300, "up"),
            "512400": generate_mock_data("512400", 300, "up"),
            "510650": generate_mock_data("510650", 300, "up"),
            "516860": generate_mock_data("516860", 300, "up"),
            "159928": generate_mock_data("159928", 300, "up"),
            "512010": generate_mock_data("512010", 300, "up"),
            "515000": generate_mock_data("515000", 300, "up"),
            "511880": generate_mock_data("511880", 300, "flat"),
        }

        signal = self.strategy.generate_signal(data)

        # 多头市场应选择行业ETF
        assert signal.selected_etf != "511880"
        assert signal.is_bullish is True
        assert signal.selected_etf in self.config.industry_codes

    def test_generate_signal_with_valuation_brake(self):
        """测试估值刹车功能"""
        self.config.valuation_enabled = True

        # 生成强上涨数据（所有行业ETF都要用strong_up确保涨幅>30%）
        data = {
            "510300": generate_mock_data("510300", 300, "strong_up"),
            "512400": generate_mock_data("512400", 300, "strong_up"),
            "510650": generate_mock_data("510650", 300, "strong_up"),
            "516860": generate_mock_data("516860", 300, "strong_up"),
            "159928": generate_mock_data("159928", 300, "strong_up"),
            "512010": generate_mock_data("512010", 300, "strong_up"),
            "515000": generate_mock_data("515000", 300, "strong_up"),
            "511880": generate_mock_data("511880", 300, "flat"),
        }

        # 模拟所有行业ETF都触发估值刹车
        pe_data = {code: 90.0 for code in self.config.industry_codes}

        signal = self.strategy.generate_signal(data, pe_data=pe_data)

        # 所有标的触发刹车，应选择货币ETF
        assert signal.selected_etf == "511880"

    def test_generate_signal_custom_date(self):
        """测试指定日期生成信号"""
        data = {
            "510300": generate_mock_data("510300", 300, "up"),
            "512400": generate_mock_data("512400", 300, "up"),
            "510650": generate_mock_data("510650", 300, "up"),
            "516860": generate_mock_data("516860", 300, "up"),
            "159928": generate_mock_data("159928", 300, "up"),
            "512010": generate_mock_data("512010", 300, "up"),
            "515000": generate_mock_data("515000", 300, "up"),
            "511880": generate_mock_data("511880", 300, "flat"),
        }

        custom_date = pd.Timestamp("2026-06-15")
        signal = self.strategy.generate_signal(data, current_date=custom_date)

        assert signal.date == custom_date

    def test_get_holding_at_date(self):
        """测试获取指定日期持仓"""
        # 无调仓记录
        holding = self.strategy.get_holding_at_date(pd.Timestamp("2026-06-01"))
        assert holding is None

        # 添加调仓记录
        data = {
            "510300": generate_mock_data("510300", 300, "up"),
            "512400": generate_mock_data("512400", 300, "up"),
            "510650": generate_mock_data("510650", 300, "up"),
            "516860": generate_mock_data("516860", 300, "up"),
            "159928": generate_mock_data("159928", 300, "up"),
            "512010": generate_mock_data("512010", 300, "up"),
            "515000": generate_mock_data("515000", 300, "up"),
            "511880": generate_mock_data("511880", 300, "flat"),
        }

        signal = self.strategy.generate_signal(data)

        # 查询调仓后的日期
        holding = self.strategy.get_holding_at_date(signal.date + pd.Timedelta(days=1))
        assert holding == signal.selected_etf


class TestBacktestEngine:
    """测试回测引擎"""

    def test_backtest_basic(self):
        """测试基本回测功能"""
        config = Config()
        config.backtest_start = "2025-01-01"
        config.backtest_end = "2026-06-26"
        config.valuation_enabled = False

        # 生成模拟数据，确保覆盖回测区间
        end_date = datetime(2026, 6, 26)
        data = {}
        for i, code in enumerate(config.all_etf_codes):
            data[code] = generate_mock_data(code, 400, "up", seed=42+i, end_date=end_date)

        strategy = DualMomentumStrategy(config)
        engine = BacktestEngine(config, strategy, data)
        result = engine.run()

        # 验证结果
        assert result.total_return is not None
        assert result.annual_return is not None
        assert result.max_drawdown <= 0
        assert result.sharpe_ratio is not None
        assert len(result.daily_records) > 0

    def test_backtest_performance_metrics(self):
        """测试绩效指标计算"""
        config = Config()
        config.backtest_start = "2025-01-01"
        config.backtest_end = "2026-06-26"
        config.valuation_enabled = False

        end_date = datetime(2026, 6, 26)
        data = {}
        for i, code in enumerate(config.all_etf_codes):
            data[code] = generate_mock_data(code, 400, "up", seed=42+i, end_date=end_date)

        strategy = DualMomentumStrategy(config)
        engine = BacktestEngine(config, strategy, data)
        result = engine.run()

        # 验证指标范围
        assert -1 <= result.max_drawdown <= 0
        assert result.volatility >= 0
        assert 0 <= result.win_rate <= 1
        assert result.total_trades >= 0
        assert result.turnover_rate >= 0

    def test_backtest_bearish_market(self):
        """测试空头市场回测"""
        config = Config()
        config.backtest_start = "2025-01-01"
        config.backtest_end = "2026-06-26"
        config.valuation_enabled = False

        end_date = datetime(2026, 6, 26)
        # 基准下跌，其他上涨
        data = {
            "510300": generate_mock_data("510300", 400, "down", seed=42, end_date=end_date),
        }
        for i, etf in enumerate(config.industry_etfs):
            data[etf.code] = generate_mock_data(etf.code, 400, "up", seed=43+i, end_date=end_date)
        data["511880"] = generate_mock_data("511880", 400, "flat", seed=50, end_date=end_date)

        strategy = DualMomentumStrategy(config)
        engine = BacktestEngine(config, strategy, data)
        result = engine.run()

        # 空头市场应主要持有货币ETF
        assert result.holding_distribution.get("银华日利", 0) > 0.5

    def test_backtest_transaction_costs(self):
        """测试交易成本扣除"""
        config = Config()
        config.backtest_start = "2025-01-01"
        config.backtest_end = "2026-06-26"
        config.commission_rate = 0.001
        config.slippage_rate = 0.0001
        config.valuation_enabled = False

        end_date = datetime(2026, 6, 26)
        data = {}
        for i, code in enumerate(config.all_etf_codes):
            data[code] = generate_mock_data(code, 400, "up", seed=42+i, end_date=end_date)

        strategy = DualMomentumStrategy(config)
        engine = BacktestEngine(config, strategy, data)
        result = engine.run()

        # 验证有交易发生
        assert result.total_trades > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
