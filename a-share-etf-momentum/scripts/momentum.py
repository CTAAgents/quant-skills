"""
A股ETF双动量轮动策略 - 动量计算模块
计算绝对动量、相对动量、估值分位
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from .config import Config


@dataclass
class MomentumResult:
    """动量计算结果"""
    code: str
    name: str
    return_252d: float  # 252日累计收益率
    rank: int  # 相对动量排名
    pe_percentile: Optional[float] = None  # PE分位数
    pb_percentile: Optional[float] = None  # PB分位数
    valuation_triggered: bool = False  # 估值刹车是否触发


class MomentumCalculator:
    """动量计算器"""

    # ETF代码到跟踪指数代码的映射
    ETF_TO_INDEX = {
        "510300": "000300",  # 沪深300ETF → 沪深300
        "512400": "399395",  # 有色金属ETF → 中证申万有色金属
        "510650": "000951",  # 银行ETF → 中证银行
        "516860": "399808",  # 高端制造ETF → 中证高端制造
        "159928": "000932",  # 消费ETF → 中证消费
        "512010": "000933",  # 医药ETF → 中证医药
        "515000": "931087",  # 科技ETF → 中证科技
        "511880": None,      # 货币ETF无估值
    }

    def __init__(self, config: Config):
        self.config = config

    def calculate_absolute_momentum(self, data: Dict[str, pd.DataFrame]) -> Tuple[bool, float]:
        """
        计算绝对动量（金丝雀检查）

        Returns:
            (is_bullish, return_252d)
            is_bullish: 沪深300ETF 252日收益率 > 0
            return_252d: 252日累计收益率
        """
        benchmark_code = self.config.benchmark.code
        if benchmark_code not in data:
            return False, 0.0

        df = data[benchmark_code]
        if len(df) < self.config.momentum_window:
            return False, 0.0

        # 计算252日收益率
        close_now = df["close"].iloc[-1]
        close_252ago = df["close"].iloc[-self.config.momentum_window]
        return_252d = (close_now / close_252ago) - 1

        is_bullish = return_252d > self.config.abs_momentum_threshold
        return is_bullish, return_252d

    def calculate_relative_momentum(self, data: Dict[str, pd.DataFrame]) -> List[MomentumResult]:
        """
        计算相对动量（行业赛马）

        Returns:
            按252日收益率降序排列的动量结果列表
        """
        results = []
        for etf in self.config.industry_etfs:
            code = etf.code
            if code not in data:
                continue

            df = data[code]
            if len(df) < self.config.relative_momentum_window:
                continue

            # 计算相对动量收益率
            close_now = df["close"].iloc[-1]
            close_ago = df["close"].iloc[-self.config.relative_momentum_window]
            return_252d = (close_now / close_ago) - 1

            result = MomentumResult(
                code=code,
                name=etf.name,
                return_252d=return_252d,
                rank=0  # 后续排序赋值
            )
            results.append(result)

        # 按收益率降序排序
        results.sort(key=lambda x: x.return_252d, reverse=True)

        # 赋予排名
        for i, result in enumerate(results):
            result.rank = i + 1

        return results

    def fetch_index_valuation(self, index_code: str) -> Optional[pd.DataFrame]:
        """
        获取指数历史估值数据（PE/PB）

        Args:
            index_code: 指数代码

        Returns:
            DataFrame with columns: date, pe, pb, pe_percentile, pb_percentile
        """
        try:
            import akshare as ak

            # 使用AKShare获取指数估值数据
            # 尝试多种方式获取数据
            df = None

            # 方式1: stock_zh_index_value_csindex (中证指数)
            try:
                df = ak.stock_zh_index_value_csindex(symbol=index_code)
                if df is not None and not df.empty:
                    # 标准化列名
                    df = df.rename(columns={
                        "日期": "date",
                        "市盈率1": "pe",  # 市盈率1是静态PE
                    })
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                pass

            # 方式2: index_value_name_funddb (韭圈儿)
            try:
                all_indices = ak.index_value_name_funddb()
                if all_indices is not None and not all_indices.empty:
                    # 查找对应指数
                    idx_data = all_indices[all_indices['指数代码'].str.contains(index_code, na=False)]
                    if not idx_data.empty:
                        # 返回最新估值数据
                        latest = idx_data.iloc[0]
                        df = pd.DataFrame([{
                            'date': pd.Timestamp.now(),
                            'pe': latest.get('最新PE'),
                            'pe_percentile': latest.get('PE分位'),
                            'pb': latest.get('最新PB'),
                            'pb_percentile': latest.get('PB分位')
                        }])
                        return df
            except Exception:
                pass

            return None

        except Exception as e:
            print(f"获取指数{index_code}估值数据失败: {e}")
            return None

    def calculate_valuation_percentile(self, etf_code: str,
                                       lookback_years: Optional[int] = None) -> Tuple[Optional[float], Optional[float]]:
        """
        计算ETF跟踪指数的PE/PB历史分位数

        Args:
            etf_code: ETF代码
            lookback_years: 回看年数（默认使用配置值）

        Returns:
            (pe_percentile, pb_percentile) - 当前PE/PB在历史中的分位数（0-100）
        """
        if lookback_years is None:
            lookback_years = self.config.valuation_lookback_years

        # 获取跟踪指数代码（从配置中）
        index_code = self.config.get_index_code(etf_code)
        if index_code is None:
            return None, None

        # 获取估值数据
        val_df = self.fetch_index_valuation(index_code)
        if val_df is None or val_df.empty:
            return None, None

        # 检查是否有pe_percentile列（直接从数据源获取的分位数）
        if "pe_percentile" in val_df.columns:
            pe_percentile = val_df["pe_percentile"].iloc[-1]
            pb_percentile = val_df["pb_percentile"].iloc[-1] if "pb_percentile" in val_df.columns else None
            return pe_percentile, pb_percentile

        # 截取回看期间
        cutoff_date = pd.Timestamp.now() - pd.DateOffset(years=lookback_years)
        val_df = val_df[val_df["date"] >= cutoff_date]

        if len(val_df) < 10:
            return None, None

        # 计算当前PE在历史中的分位数
        current_pe = val_df["pe"].iloc[-1]
        pe_series = val_df["pe"].dropna()

        if len(pe_series) > 0:
            pe_percentile = (pe_series < current_pe).sum() / len(pe_series) * 100
        else:
            pe_percentile = None

        # 如果有PB数据
        pb_percentile = None
        if "pb" in val_df.columns:
            current_pb = val_df["pb"].iloc[-1]
            pb_series = val_df["pb"].dropna()
            if len(pb_series) > 0:
                pb_percentile = (pb_series < current_pb).sum() / len(pb_series) * 100

        return pe_percentile, pb_percentile

    def fetch_all_valuation_data(self, etf_codes: Optional[List[str]] = None) -> Dict[str, float]:
        """
        批量获取所有行业ETF的PE分位数据

        Args:
            etf_codes: ETF代码列表（默认使用行业ETF池）

        Returns:
            {etf_code: pe_percentile} 字典
        """
        if etf_codes is None:
            etf_codes = [etf.code for etf in self.config.industry_etfs]

        pe_data = {}
        for code in etf_codes:
            pe_pct, _ = self.calculate_valuation_percentile(code)
            if pe_pct is not None:
                pe_data[code] = pe_pct
            else:
                print(f"警告: 无法获取{code}的PE分位数据，估值刹车将跳过该标的")

        return pe_data

    def apply_valuation_brake(self, momentum_results: List[MomentumResult],
                             pe_data: Optional[Dict[str, float]] = None) -> List[MomentumResult]:
        """
        应用估值分位刹车

        Args:
            momentum_results: 动量排名结果
            pe_data: PE分位数据 {code: pe_percentile}，若为None则自动获取

        Returns:
            更新了估值刹车状态的结果列表
        """
        # 若未提供pe_data，自动获取
        if pe_data is None:
            pe_data = self.fetch_all_valuation_data()

        if not pe_data:
            # 无估值数据时跳过刹车检查
            return momentum_results

        for result in momentum_results:
            pe_pct = pe_data.get(result.code)
            if pe_pct is not None:
                result.pe_percentile = pe_pct
                # 刹车条件：PE分位 > 80% 且 涨幅 > 30%
                if (pe_pct > self.config.valuation_pe_threshold and
                    result.return_252d > self.config.valuation_return_threshold):
                    result.valuation_triggered = True

        return momentum_results

    def select_target(self, momentum_results: List[MomentumResult]) -> Optional[str]:
        """
        根据动量排名和估值刹车选择目标ETF

        Returns:
            选中的ETF代码，若无合适标的则返回None
        """
        for result in momentum_results:
            if not result.valuation_triggered:
                return result.code
        return None

    def generate_momentum_report(self, momentum_results: List[MomentumResult],
                                is_bullish: bool, benchmark_return: float) -> str:
        """生成动量排名报告"""
        lines = []
        lines.append("=" * 80)
        lines.append("双动量轮动策略 - 动量排名报告")
        lines.append("=" * 80)

        # 绝对动量状态
        status = "多头市场 ✓" if is_bullish else "空头市场 ✗"
        lines.append(f"\n【绝对动量】沪深300ETF 252日收益率: {benchmark_return:.2%} → {status}")

        # 相对动量排名
        lines.append(f"\n【相对动量】行业ETF排名（Top {self.config.top_n}）:")
        lines.append("-" * 80)
        lines.append(f"{'排名':<6}{'代码':<10}{'名称':<12}{'252日收益':<12}{'PE分位':<10}{'PB分位':<10}{'刹车':<8}")
        lines.append("-" * 80)

        for r in momentum_results:
            pe_str = f"{r.pe_percentile:.1f}%" if r.pe_percentile is not None else "N/A"
            pb_str = f"{r.pb_percentile:.1f}%" if r.pb_percentile is not None else "N/A"
            brake = "✓ 触发" if r.valuation_triggered else "✗"
            lines.append(f"{r.rank:<6}{r.code:<10}{r.name:<12}"
                        f"{r.return_252d:<12.2%}{pe_str:<10}{pb_str:<10}{brake:<8}")

        # 选股结果
        target = self.select_target(momentum_results)
        if target:
            etf_config = self.config.get_etf_by_code(target)
            lines.append(f"\n【选股结果】: {etf_config.name} ({target})")
        else:
            lines.append(f"\n【选股结果】: 无合适标的，建议持有货币ETF ({self.config.defensive.code})")

        return "\n".join(lines)
