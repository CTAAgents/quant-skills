"""
A股ETF双动量轮动策略 - 数据采集模块
支持AKShare / WeStock数据源，含本地缓存
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import json

from .config import Config


class ETFDataCollector:
    """ETF数据采集器"""

    def __init__(self, config: Config):
        self.config = config
        # 尝试多个缓存目录
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cache_dir = os.path.join(skill_dir, config.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

    def collect_all(self, force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        """
        采集所有ETF数据

        Returns:
            Dict[code, DataFrame] - 每个ETF的日线数据
            DataFrame columns: date, open, high, low, close, volume, amount
        """
        data = {}
        for code in self.config.all_etf_codes:
            df = self.collect_single(code, force_refresh)
            if df is not None and not df.empty:
                data[code] = df
            else:
                print(f"警告: 无法获取 {code} 数据")
        return data

    def collect_single(self, code: str, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """采集单个ETF数据"""
        # 检查缓存
        if not force_refresh:
            cached = self._load_cache(code)
            if cached is not None:
                return cached

        # 从数据源获取
        df = self._fetch_from_akshare(code)
        if df is not None and not df.empty:
            self._save_cache(code, df)
            return df

        return None

    def _fetch_from_akshare(self, code: str) -> Optional[pd.DataFrame]:
        """从AKShare获取ETF日线数据"""
        try:
            import akshare as ak

            # 计算起始日期（需要额外数据用于预热）
            start_date = (datetime.strptime(self.config.backtest_start, "%Y-%m-%d") -
                         timedelta(days=400)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")

            # 获取ETF日线
            df = ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="hfq"  # 后复权
            )

            if df.empty:
                return None

            # 标准化列名
            df = df.rename(columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount"
            })

            # 确保日期格式
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)

            return df[["date", "open", "high", "low", "close", "volume", "amount"]]

        except Exception as e:
            print(f"AKShare获取{code}失败: {e}")
            return None

    def load_from_cache(self, code: str) -> Optional[pd.DataFrame]:
        """从缓存加载数据（支持parquet/csv）"""
        return self._load_cache(code)

    def _load_cache(self, code: str) -> Optional[pd.DataFrame]:
        """加载本地缓存"""
        # 优先尝试parquet，降级到csv
        for ext in ["parquet", "csv"]:
            cache_file = os.path.join(self.cache_dir, f"{code}.{ext}")
            if os.path.exists(cache_file):
                try:
                    if ext == "parquet":
                        df = pd.read_parquet(cache_file)
                    else:
                        df = pd.read_csv(cache_file, parse_dates=["date"])
                    # 检查缓存是否过期（超过1天）
                    last_date = pd.to_datetime(df["date"]).max()
                    if (datetime.now() - last_date).days <= 1:
                        return df
                except Exception:
                    pass
        return None

    def _save_cache(self, code: str, df: pd.DataFrame):
        """保存到本地缓存"""
        # 优先尝试parquet，降级到csv
        try:
            cache_file = os.path.join(self.cache_dir, f"{code}.parquet")
            df.to_parquet(cache_file, index=False)
        except ImportError:
            cache_file = os.path.join(self.cache_dir, f"{code}.csv")
            df.to_csv(cache_file, index=False)

    def get_latest_price(self, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """获取最新收盘价"""
        prices = {}
        for code, df in data.items():
            if not df.empty:
                prices[code] = df["close"].iloc[-1]
        return prices

    def calculate_returns(self, data: Dict[str, pd.DataFrame],
                         window: int) -> Dict[str, pd.Series]:
        """
        计算各ETF的滚动收益率

        Args:
            data: ETF数据字典
            window: 回看窗口（交易日）

        Returns:
            Dict[code, Series] - 滚动收益率序列
        """
        returns = {}
        for code, df in data.items():
            if len(df) >= window:
                returns[code] = df["close"].pct_change(window)
        return returns
