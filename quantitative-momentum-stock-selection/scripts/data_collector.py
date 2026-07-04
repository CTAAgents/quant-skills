"""
量化动量选股系统 - 数据采集模块
版本: 1.0.0
基于《构建量化动量选股系统的实用指南》
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import os

try:
    import akshare as ak
except ImportError:
    ak = None

try:
    import tushare as ts
except ImportError:
    ts = None

# 东方财富数据接口（A股特有）
try:
    import requests
except ImportError:
    requests = None


class DataCollector:
    """数据采集器（A股优化版）"""

    def __init__(self, config=None):
        """
        初始化数据采集器

        Args:
            config: 系统配置对象
        """
        from .config import get_config
        self.config = config or get_config()

        # 确保缓存目录存在
        cache_dir = Path(self.config.data.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

    def get_north_flow_data(self, stock_code: str,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取北向资金数据（A股特有）

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            包含北向资金净流入数据的DataFrame
        """
        # 从AKShare获取北向资金数据
        if ak:
            try:
                # 获取沪股通/深股通资金流向
                if stock_code.startswith('6'):
                    # 上海股票，使用沪股通
                    df = ak.stock_hsgt_north_net_flow_in_em(symbol="沪股通")
                else:
                    # 深圳股票，使用深股通
                    df = ak.stock_hsgt_north_net_flow_in_em(symbol="深股通")

                if df is not None and not df.empty:
                    # 标准化列名
                    df = df.rename(columns={
                        '日期': 'date',
                        '当日资金流入': 'net_flow',
                        '当日余额': 'remaining_quota'
                    })

                    # 筛选日期范围
                    if start_date and 'date' in df.columns:
                        df = df[df['date'] >= start_date]
                    if end_date and 'date' in df.columns:
                        df = df[df['date'] <= end_date]

                    return df
            except Exception as e:
                print(f"从AKShare获取北向资金数据失败: {e}")

        return pd.DataFrame()

    def get_margin_data(self, stock_code: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取融资融券数据（A股特有）

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            包含融资融券数据的DataFrame
        """
        # 从AKShare获取融资融券数据
        if ak:
            try:
                # 获取个股融资融券数据
                df = ak.stock_margin_detail_szse()

                if df is not None and not df.empty:
                    # 筛选指定股票
                    df = df[df['证券代码'] == stock_code]

                    # 标准化列名
                    df = df.rename(columns={
                        '日期': 'date',
                        '融资余额': 'margin_balance',
                        '融资买入额': 'margin_buy',
                        '融券余量': 'short_selling_balance',
                        '融券卖出量': 'short_selling_sell'
                    })

                    # 筛选日期范围
                    if start_date and 'date' in df.columns:
                        df = df[df['date'] >= start_date]
                    if end_date and 'date' in df.columns:
                        df = df[df['date'] <= end_date]

                    return df
            except Exception as e:
                print(f"从AKShare获取融资融券数据失败: {e}")

        return pd.DataFrame()

    def get_sector_flow_data(self, sector_name: str,
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取行业资金流向数据（A股特有）

        Args:
            sector_name: 行业名称
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            包含行业资金流向数据的DataFrame
        """
        # 从AKShare获取行业资金流向数据
        if ak:
            try:
                # 获取行业板块资金流向
                df = ak.stock_sector_fund_flow_rank(indicator="今日")

                if df is not None and not df.empty:
                    # 筛选指定行业
                    df = df[df['名称'] == sector_name]

                    return df
            except Exception as e:
                print(f"从AKShare获取行业资金流向数据失败: {e}")

        return pd.DataFrame()

    def get_limit_up_down_data(self, date: Optional[str] = None) -> pd.DataFrame:
        """
        获取涨跌停数据（A股特有）

        Args:
            date: 日期（YYYYMMDD格式）

        Returns:
            包含涨跌停数据的DataFrame
        """
        # 从AKShare获取涨跌停数据
        if ak:
            try:
                # 获取涨停板数据
                df_limit_up = ak.stock_zt_pool_em(date=date)

                # 获取跌停板数据
                df_limit_down = ak.stock_zt_pool_dtgc_em(date=date)

                # 合并数据
                if df_limit_up is not None and df_limit_down is not None:
                    df_limit_up['type'] = 'limit_up'
                    df_limit_down['type'] = 'limit_down'
                    df = pd.concat([df_limit_up, df_limit_down], ignore_index=True)
                    return df
                elif df_limit_up is not None:
                    df_limit_up['type'] = 'limit_up'
                    return df_limit_up
                elif df_limit_down is not None:
                    df_limit_down['type'] = 'limit_down'
                    return df_limit_down
            except Exception as e:
                print(f"从AKShare获取涨跌停数据失败: {e}")

        return pd.DataFrame()
    
    def get_stock_list(self) -> pd.DataFrame:
        """
        获取股票列表
        
        Returns:
            包含股票代码、名称、行业等信息的DataFrame
        """
        cache_file = Path(self.config.data.cache_dir) / "stock_list.parquet"
        
        # 检查缓存
        if cache_file.exists():
            cached_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if (datetime.now() - cached_time).days < self.config.data.cache_expire_days:
                return pd.read_parquet(cache_file)
        
        # 从AKShare获取股票列表
        if ak:
            try:
                # 获取A股股票列表
                stock_info = ak.stock_info_a_code_name()
                
                # 获取行业分类
                industry_info = ak.stock_board_industry_name_em()
                
                # 合并数据
                stock_list = self._merge_stock_industry(stock_info, industry_info)
                
                # 缓存数据
                stock_list.to_parquet(cache_file, index=False)
                
                return stock_list
            except Exception as e:
                print(f"从AKShare获取股票列表失败: {e}")
        
        # 降级到本地缓存或默认列表
        return self._get_default_stock_list()
    
    def _merge_stock_industry(self, stock_info: pd.DataFrame, 
                             industry_info: pd.DataFrame) -> pd.DataFrame:
        """合并股票信息和行业信息"""
        # 实现股票与行业的合并逻辑
        # 这里需要根据实际的数据结构进行实现
        return stock_info
    
    def _get_default_stock_list(self) -> pd.DataFrame:
        """获取默认股票列表"""
        # 返回一个空的DataFrame，实际使用时需要从数据源获取
        return pd.DataFrame(columns=['code', 'name', 'industry'])
    
    def get_stock_history(self, stock_code: str, 
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         adjust: str = "qfq") -> pd.DataFrame:
        """
        获取股票历史数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型 (qfq: 前复权, hfq: 后复权, 空: 不复权)
        
        Returns:
            包含OHLCV数据的DataFrame
        """
        if start_date is None:
            start_date = self.config.data.start_date
        if end_date is None:
            end_date = self.config.data.end_date
        
        # 构建缓存文件名
        cache_file = Path(self.config.data.cache_dir) / f"{stock_code}_{start_date}_{end_date}_{adjust}.parquet"
        
        # 检查缓存
        if cache_file.exists():
            cached_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if (datetime.now() - cached_time).days < self.config.data.cache_expire_days:
                return pd.read_parquet(cache_file)
        
        # 从AKShare获取数据
        if ak:
            try:
                # 获取股票历史数据
                df = ak.stock_zh_a_hist(
                    symbol=stock_code,
                    period="daily",
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                    adjust=adjust
                )
                
                # 标准化列名
                df = self._standardize_columns(df)
                
                # 缓存数据
                df.to_parquet(cache_file, index=False)
                
                return df
            except Exception as e:
                print(f"从AKShare获取{stock_code}历史数据失败: {e}")
        
        # 降级到其他数据源
        return self._get_history_from_other_source(stock_code, start_date, end_date)
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名"""
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '振幅': 'amplitude',
            '涨跌幅': 'pct_change',
            '涨跌额': 'change',
            '换手率': 'turnover',
        }
        
        # 重命名列
        df = df.rename(columns=column_mapping)
        
        # 确保日期格式
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        return df
    
    def _get_history_from_other_source(self, stock_code: str,
                                      start_date: str,
                                      end_date: str) -> pd.DataFrame:
        """从其他数据源获取历史数据"""
        # 实现其他数据源的降级逻辑
        return pd.DataFrame()
    
    def get_index_history(self, index_code: str,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取指数历史数据
        
        Args:
            index_code: 指数代码
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            包含OHLCV数据的DataFrame
        """
        if start_date is None:
            start_date = self.config.data.start_date
        if end_date is None:
            end_date = self.config.data.end_date
        
        # 从AKShare获取指数数据
        if ak:
            try:
                df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
                
                # 标准化列名
                df = self._standardize_columns(df)
                
                # 筛选日期范围
                if 'date' in df.columns:
                    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
                
                return df
            except Exception as e:
                print(f"从AKShare获取指数{index_code}数据失败: {e}")
        
        return pd.DataFrame()
    
    def get_valuation_data(self, stock_code: str) -> pd.DataFrame:
        """
        获取估值数据
        
        Args:
            stock_code: 股票代码
        
        Returns:
            包含PE、PB等估值数据的DataFrame
        """
        # 从AKShare获取估值数据
        if ak:
            try:
                # 获取个股估值数据
                df = ak.stock_a_lg_indicator(symbol=stock_code)
                return df
            except Exception as e:
                print(f"从AKShare获取{stock_code}估值数据失败: {e}")
        
        return pd.DataFrame()
    
    def get_sector_data(self) -> pd.DataFrame:
        """
        获取行业板块数据
        
        Returns:
            包含行业板块信息的DataFrame
        """
        # 从AKShare获取行业板块数据
        if ak:
            try:
                df = ak.stock_board_industry_name_em()
                return df
            except Exception as e:
                print(f"从AKShare获取行业板块数据失败: {e}")
        
        return pd.DataFrame()
    
    def get_fund_flow_data(self, stock_code: str) -> pd.DataFrame:
        """
        获取资金流向数据
        
        Args:
            stock_code: 股票代码
        
        Returns:
            包含资金流向数据的DataFrame
        """
        # 从AKShare获取资金流向数据
        if ak:
            try:
                df = ak.stock_individual_fund_flow(stock=stock_code, market="sh")
                return df
            except Exception as e:
                print(f"从AKShare获取{stock_code}资金流向数据失败: {e}")
        
        return pd.DataFrame()
    
    def clear_cache(self, older_than_days: Optional[int] = None):
        """
        清理缓存
        
        Args:
            older_than_days: 清理多少天前的缓存，None表示清理所有缓存
        """
        cache_dir = Path(self.config.data.cache_dir)
        
        if not cache_dir.exists():
            return
        
        for cache_file in cache_dir.glob("*.parquet"):
            if older_than_days is not None:
                file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if (datetime.now() - file_time).days < older_than_days:
                    continue
            
            try:
                cache_file.unlink()
                print(f"已删除缓存文件: {cache_file}")
            except Exception as e:
                print(f"删除缓存文件失败 {cache_file}: {e}")