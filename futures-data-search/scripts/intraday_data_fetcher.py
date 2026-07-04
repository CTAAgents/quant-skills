#!/usr/bin/env python3
"""
分钟级数据获取模块
支持国内期货分钟K线数据

数据源：
- TqSdk（天勤量化）：实时行情
- AKShare（降级方案）：历史数据
- 交易所官方API（部分支持）

注意：分钟级数据仅在交易时段可用
"""

import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


class IntradayDataFetcher:
    """分钟级数据获取器"""

    # 支持的周期
    SUPPORTED_PERIODS = ['1m', '5m', '15m', '30m', '60m']

    # 交易时段定义
    TRADING_SESSIONS = {
        'day': {'start': '09:00', 'end': '15:00'},  # 日盘
        'night': {'start': '21:00', 'end': '02:30'},  # 夜盘
    }

    def __init__(self, use_tqsdk: bool = True):
        """
        初始化分钟级数据获取器

        Args:
            use_tqsdk: 是否使用 TqSdk（需要安装 + 环境变量 auth）
        """
        self.use_tqsdk = use_tqsdk
        self.tqsdk_api = None

        # 尝试导入 TqSdk
        if use_tqsdk:
            try:
                from tqsdk import TqApi, TqAuth
                import os
                _user = os.environ.get('TQSDK_USERNAME') or os.environ.get('TQ_USER', '')
                _pass = os.environ.get('TQSDK_PASSWORD') or os.environ.get('TQ_PASSWORD', '')
                self.tqsdk_available = bool(_user and _pass)
                if self.tqsdk_available:
                    self.tqsdk_auth = TqAuth(_user, _pass)
                    print("[Info] TqSdk available for intraday data")
                else:
                    print("[Info] TqSdk env vars not set, using fallback")
            except ImportError:
                self.tqsdk_available = False
                print("[Info] TqSdk not installed, using fallback")
        else:
            self.tqsdk_available = False

    def fetch(self, variety: str, period: str = "1m", count: int = 100, 
              specific_month: Optional[str] = None) -> Dict[str, Any]:
        """
        获取分钟级数据

        Args:
            variety: 品种代码（如 CU、RB）
            period: 周期（1m/5m/15m/30m/60m）
            count: 数据条数
            specific_month: 具体合约月份（如 2609）

        Returns:
            分钟级数据字典
        """
        if period not in self.SUPPORTED_PERIODS:
            return self._get_error_result(variety, f"不支持的周期: {period}，支持: {self.SUPPORTED_PERIODS}")

        # 构造合约代码
        contract = self._build_contract_code(variety, specific_month)

        # 尝试使用 TqSdk 获取数据
        if self.tqsdk_available and self.use_tqsdk:
            try:
                data = self._fetch_tqsdk(contract, period, count)
                if data:
                    return data
            except Exception as e:
                print(f"[Warning] TqSdk fetch failed: {e}")

        # Fallback: 返回模拟数据结构
        return self._get_simulated_data(variety, period, count)

    def _build_contract_code(self, variety: str, specific_month: Optional[str] = None) -> str:
        """构造合约代码"""
        if specific_month:
            return f"{variety.upper()}{specific_month}"
        else:
            # 默认使用主力合约（需要从映射表获取）
            return f"{variety.upper()}888"  # 888 表示主力连续

    def _fetch_tqsdk(self, contract: str, period: str, count: int) -> Optional[Dict[str, Any]]:
        """使用 TqSdk 获取分钟级K线（支持 auth 配置）"""
        if not self.tqsdk_available:
            return None

        try:
            from tqsdk import TqApi
            import tqsdk

            # 周期映射
            period_map = {
                '1m': tqsdk.objs.KLine_Duration.ONE_MINUTE,
                '5m': tqsdk.objs.KLine_Duration.FIVE_MINUTES,
                '15m': tqsdk.objs.KLine_Duration.FIFTEEN_MINUTES,
                '30m': tqsdk.objs.KLine_Duration.THIRTY_MINUTES,
                '60m': tqsdk.objs.KLine_Duration.ONE_HOUR,
            }

            # 初始化 API（使用环境变量 auth）
            api = TqApi(auth=self.tqsdk_auth)

            # 获取K线数据
            klines = api.get_kline_serial(contract, period_map[period], count)

            if klines is not None and len(klines) > 0:
                data_list = []
                for i in range(len(klines)):
                    data_list.append({
                        "datetime": datetime.fromtimestamp(klines.iloc[i]['datetime'] / 1e9).strftime('%Y-%m-%d %H:%M:%S'),
                        "open": float(klines.iloc[i]['open']),
                        "high": float(klines.iloc[i]['high']),
                        "low": float(klines.iloc[i]['low']),
                        "close": float(klines.iloc[i]['close']),
                        "volume": int(klines.iloc[i]['volume']),
                        "open_interest": int(klines.iloc[i]['close_oi']),
                    })

                api.close()
                return {
                    "variety": contract,
                    "period": period,
                    "count": len(data_list),
                    "data": data_list,
                    "data_source": "TqSdk",
                    "update_time": datetime.now().isoformat(),
                    "is_trading_hour": self._is_trading_hour(),
                }

            api.close()
            return None

        except Exception as e:
            print(f"[Warning] TqSdk intraday error: {e}")
            return None

    def _is_trading_hour(self) -> bool:
        """检查当前是否为交易时段"""
        now = datetime.now()
        current_time = now.strftime('%H:%M')

        # 日盘
        if '09:00' <= current_time <= '15:00':
            return True

        # 夜盘
        if current_time >= '21:00' or current_time <= '02:30':
            return True

        return False

    def _get_simulated_data(self, variety: str, period: str, count: int) -> Dict[str, Any]:
        """获取模拟数据（用于测试）"""
        import numpy as np

        # 生成模拟数据
        base_price = 50000  # 基础价格
        data_list = []

        for i in range(count):
            timestamp = datetime.now() - timedelta(minutes=(count - i) * int(period.replace('m', '')))
            noise = np.random.randn() * 100
            price = base_price + noise

            data_list.append({
                "datetime": timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                "open": round(price - 50, 2),
                "high": round(price + 100, 2),
                "low": round(price - 100, 2),
                "close": round(price, 2),
                "volume": int(np.random.randint(100, 10000)),
                "open_interest": int(np.random.randint(10000, 100000)),
            })

        return {
            "variety": variety,
            "period": period,
            "count": count,
            "data": data_list,
            "data_source": "Simulated",
            "update_time": datetime.now().isoformat(),
            "is_trading_hour": self._is_trading_hour(),
            "note": "当前为模拟数据，实际数据需要配置 TqSdk",
        }

    def _get_error_result(self, variety: str, error_msg: str) -> Dict[str, Any]:
        """获取错误结果"""
        return {
            "variety": variety,
            "error": error_msg,
            "data_source": None,
            "update_time": datetime.now().isoformat(),
        }

    def get_supported_periods(self) -> List[str]:
        """获取支持的周期列表"""
        return self.SUPPORTED_PERIODS


def main():
    """测试函数"""
    print("Intraday Data Fetcher Test")
    print("=" * 50)

    fetcher = IntradayDataFetcher(use_tqsdk=False)  # 不使用 TqSdk

    # 测试不同周期
    test_cases = [
        ('CU', '1m', 10),
        ('RB', '5m', 20),
        ('AU', '15m', 10),
    ]

    for variety, period, count in test_cases:
        print(f"\n{variety} {period} K线（{count}条）:")
        result = fetcher.fetch(variety, period, count)
        if result.get('data'):
            print(f"  数据源: {result.get('data_source', 'N/A')}")
            print(f"  数据条数: {result.get('count', 0)}")
            print(f"  交易时段: {result.get('is_trading_hour', False)}")
            if result.get('data'):
                latest = result['data'][-1]
                print(f"  最新数据: {latest.get('datetime')} 收盘 {latest.get('close')}")
        else:
            print(f"  错误: {result.get('error', '数据获取失败')}")


if __name__ == "__main__":
    main()
