"""
A股ETF双动量轮动策略 - 配置模块
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ETFConfig:
    """ETF标的配置"""
    code: str
    name: str
    category: str  # benchmark / industry / defensive
    index_code: Optional[str] = None  # 跟踪指数代码（用于估值分位）


@dataclass
class Config:
    """策略主配置"""

    # ========== 标的池 ==========
    # 基准（金丝雀）
    benchmark: ETFConfig = field(default_factory=lambda: ETFConfig(
        code="510300",
        name="沪深300ETF",
        category="benchmark",
        index_code="000300"
    ))

    # 行业ETF池
    industry_etfs: List[ETFConfig] = field(default_factory=lambda: [
        ETFConfig(code="512400", name="有色金属ETF", category="industry", index_code="399395"),
        ETFConfig(code="510650", name="银行ETF", category="industry", index_code="000951"),
        ETFConfig(code="516860", name="高端制造ETF", category="industry", index_code="399808"),
        ETFConfig(code="159928", name="消费ETF", category="industry", index_code="000932"),
        ETFConfig(code="512010", name="医药ETF", category="industry", index_code="000933"),
        ETFConfig(code="515000", name="科技ETF", category="industry", index_code="931087"),
    ])

    # 防御资产
    defensive: ETFConfig = field(default_factory=lambda: ETFConfig(
        code="511880",
        name="银华日利",
        category="defensive",
        index_code=None
    ))

    # ========== 动量参数 ==========
    momentum_window: int = 90  # 绝对动量窗口（交易日，约4.5个月）
    relative_momentum_window: int = 50  # 相对动量窗口（交易日）- 参数优化最佳窗口
    rebalance_freq: str = "monthly"  # 调仓频率 - 参数优化最佳频率
    top_n: int = 1  # 相对动量选取数量

    # ========== 绝对动量参数 ==========
    abs_momentum_threshold: float = 0.0  # 绝对动量阈值（>0为多头市场）

    # ========== 估值刹车参数 ==========
    valuation_pe_threshold: float = 80.0  # PE分位刹车阈值（%）
    valuation_return_threshold: float = 0.30  # 涨幅刹车阈值（30%）
    valuation_lookback_years: int = 5  # 估值分位回看年数
    valuation_enabled: bool = True  # 是否启用估值刹车

    # ========== 资金与成本 ==========
    initial_capital: float = 1_000_000  # 初始资金
    commission_rate: float = 0.001  # 单边手续费（千分之一）
    slippage_rate: float = 0.0001  # 滑点（万分之一）

    # ========== 数据源配置 ==========
    data_source: str = "akshare"  # akshare / westock / local
    cache_dir: str = "cache"  # 本地缓存目录

    # ========== 回测配置 ==========
    backtest_start: str = "2013-01-01"  # 回测起始日期（首批行业ETF上市年份）
    backtest_end: str = "2026-06-26"  # 回测结束日期
    benchmark_index: str = "000300"  # 对比基准（沪深300指数）

    # ========== 输出配置 ==========
    output_dir: str = "reports"
    log_trades: bool = True

    @property
    def all_etf_codes(self) -> List[str]:
        """获取所有ETF代码"""
        return [self.benchmark.code] + \
               [etf.code for etf in self.industry_etfs] + \
               [self.defensive.code]

    @property
    def industry_codes(self) -> List[str]:
        """获取行业ETF代码列表"""
        return [etf.code for etf in self.industry_etfs]

    def get_etf_by_code(self, code: str) -> ETFConfig:
        """根据代码获取ETF配置"""
        if code == self.benchmark.code:
            return self.benchmark
        if code == self.defensive.code:
            return self.defensive
        for etf in self.industry_etfs:
            if etf.code == code:
                return etf
        raise ValueError(f"未知的ETF代码: {code}")

    def get_index_code(self, etf_code: str) -> Optional[str]:
        """获取ETF对应的跟踪指数代码"""
        etf = self.get_etf_by_code(etf_code)
        return etf.index_code
