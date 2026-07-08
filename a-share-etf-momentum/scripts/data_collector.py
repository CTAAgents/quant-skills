"""
A股ETF双动量轮动策略 - 数据采集模块
支持腾讯自选股(westock)主数据源 + 通达信TQ-Local(tdx)备用数据源，含本地缓存
"""

import os
import sys
import subprocess
import json
import urllib.request
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from .config import Config


class ETFDataCollector:
    """ETF数据采集器 — 多数据源自动降级"""

    def __init__(self, config: Config):
        self.config = config
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
        """
        采集单个ETF数据
        优先级: 本地缓存 → 腾讯自选股(westock) → 通达信TQ-Local(tdx)
        """
        # 1) 检查本地缓存（未强制刷新时）
        if not force_refresh:
            cached = self._load_cache(code)
            if cached is not None:
                return cached

        # 2) 主数据源: 腾讯自选股
        df = self._fetch_from_westock(code)
        if df is not None and not df.empty:
            self._save_cache(code, df)
            return df

        # 3) 备用数据源: 通达信TQ-Local（前复权）
        df = self._fetch_from_tdx(code)
        if df is not None and not df.empty:
            self._save_cache(code, df)
            return df

        # 4) 兜底: 尝试加载过期缓存
        df = self._load_cache(code, ignore_expiry=True)
        if df is not None and not df.empty:
            print(f"  [兜底] {code} 使用过期缓存数据")
            return df

        return None

    # ==================== 腾讯自选股 (WeStock) ====================

    def _fetch_from_westock(self, code: str) -> Optional[pd.DataFrame]:
        """从腾讯自选股获取ETF日线数据（前复权），解析Markdown表格输出"""
        try:
            westock_code = Config.to_westock_code(code)

            # 使用系统 Node.js 的 npx（避免 managed Node 版本不匹配）
            npx_cmd = "C:/Program Files/nodejs/npx.cmd"

            result = subprocess.run(
                [
                    npx_cmd, "-y", "westock-data-clawhub@1.0.4", "kline",
                    westock_code,
                    "--period", "day",
                    "--limit", "2000",
                    "--fq", self.config.westock_dividend_type,
                ],
                capture_output=True,
                text=True,
                timeout=60,
                shell=(sys.platform == "win32"),
            )

            if result.returncode != 0:
                print(f"  WeStock CLI 返回非零 ({code}): {result.stderr[:200]}")
                return None

            raw = result.stdout.strip()
            if not raw:
                print(f"  WeStock 空响应 ({code})")
                return None

            # WeStock CLI 输出 Markdown 表格格式:
            # | date | open | last | high | low | volume | amount | exchange |
            # | --- | --- | --- | --- | --- | --- | --- | --- |
            # | 2026-07-08 | 4.84 | 4.80 | 4.87 | 4.79 | 4846848 | 2337287019 | 2.84 |
            return self._parse_markdown_table(raw, code, source="WeStock")

        except subprocess.TimeoutExpired:
            print(f"  WeStock CLI 超时 ({code})")
            return None
        except Exception as e:
            print(f"  WeStock 获取失败 ({code}): {e}")
            return None

    def _parse_markdown_table(self, text: str, code: str, source: str = "") -> Optional[pd.DataFrame]:
        """解析Markdown表格为DataFrame"""
        lines = text.strip().split("\n")
        # 跳过表头分隔线（第二行包含 ---|---）
        data_lines = []
        header_found = False
        for line in lines:
            line = line.strip()
            if not line.startswith("|"):
                continue
            if "---" in line and "|" in line:
                header_found = True
                continue
            data_lines.append(line)

        if not data_lines:
            print(f"  {source} 无数据行 ({code})")
            return None

        # 第一行是表头
        headers = [h.strip().lower() for h in data_lines[0].split("|") if h.strip()]
        rows = []
        for line in data_lines[1:]:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= len(headers):
                rows.append(dict(zip(headers, cells)))

        if not rows:
            print(f"  {source} 无数据行 ({code})")
            return None

        df = pd.DataFrame(rows)

        # 列名映射: westock 用 "last" 表示收盘价（最新价）
        col_map = {}
        for col in df.columns:
            if col in ("date", "日期", "time"):
                col_map[col] = "date"
            elif col in ("open", "开盘"):
                col_map[col] = "open"
            elif col in ("last", "close", "收盘", "最新价"):
                col_map[col] = "close"
            elif col in ("high", "最高"):
                col_map[col] = "high"
            elif col in ("low", "最低"):
                col_map[col] = "low"
            elif col in ("volume", "成交量"):
                col_map[col] = "volume"
            elif col in ("amount", "成交额"):
                col_map[col] = "amount"
        df = df.rename(columns=col_map)

        # 确保必要列存在
        required = ["date", "open", "high", "low", "close"]
        for col in required:
            if col not in df.columns:
                print(f"  {source} 缺少列 ({code}): {col} (available: {list(df.columns)})")
                return None

        # 类型转换
        df["date"] = pd.to_datetime(df["date"])
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

        df = df.sort_values("date").reset_index(drop=True)
        df = df.dropna(subset=["close"])

        out_cols = ["date", "open", "high", "low", "close"]
        if "volume" in df.columns:
            out_cols.append("volume")
        if "amount" in df.columns:
            out_cols.append("amount")

        return df[out_cols]

    # ==================== 通达信TQ-Local ====================

    def _fetch_from_tdx(self, code: str) -> Optional[pd.DataFrame]:
        """从通达信TQ-Local获取ETF日线数据（默认前复权），解析列式数组格式"""
        try:
            tdx_code = Config.to_tdx_code(code)

            start_date = (datetime.strptime(self.config.backtest_start, "%Y-%m-%d") -
                         timedelta(days=400)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")

            payload = {
                "id": 1,
                "method": "get_market_data",
                "params": {
                    "stock_list": [tdx_code],
                    "count": -1,
                    "start_time": start_date,
                    "end_time": end_date,
                    "period": "1d",
                    "dividend_type": self.config.tdx_dividend_type,
                },
            }

            req = urllib.request.Request(
                self.config.tdx_host,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            if "error" in result and result["error"]:
                print(f"  TDX RPC错误 ({code}): {result['error']}")
                return None

            r = result.get("result", {})
            if not isinstance(r, dict):
                print(f"  TDX result非dict ({code})")
                return None

            # TDX返回列式数组: Value[code] = {Date:[], Open:[], High:[], Low:[], Close:[], Volume:[], Amount:[]}
            value = r.get("Value", {})
            if isinstance(value, dict):
                stock_data = value.get(tdx_code, value)
            else:
                stock_data = value

            if not isinstance(stock_data, dict) or "Date" not in stock_data:
                # 可能error或空数据
                err_id = stock_data.get("ErrorId", "") if isinstance(stock_data, dict) else ""
                if err_id and err_id != "0":
                    print(f"  TDX ErrorId={err_id} ({code})")
                else:
                    print(f"  TDX 格式异常 ({code})")
                return None

            # 转置列式数组为行式DataFrame
            dates = stock_data.get("Date", [])
            if not dates:
                print(f"  TDX 无数据 ({code})")
                return None

            records = []
            n = len(dates)
            opens = stock_data.get("Open", ["0"] * n)
            highs = stock_data.get("High", ["0"] * n)
            lows = stock_data.get("Low", ["0"] * n)
            closes = stock_data.get("Close", ["0"] * n)
            volumes = stock_data.get("Volume", ["0"] * n)
            amounts = stock_data.get("Amount", ["0"] * n)  # TDX Amount 单位: 万元

            for i in range(n):
                records.append({
                    "date": pd.to_datetime(str(dates[i]), format="%Y%m%d"),
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(closes[i]),
                    "volume": float(volumes[i]),
                    "amount": float(amounts[i]) * 10000 if float(amounts[i]) > 0 else 0,  # 万元→元
                })

            df = pd.DataFrame(records)
            df = df.dropna(subset=["date", "close"])
            df = df.sort_values("date").reset_index(drop=True)

            return df[["date", "open", "high", "low", "close", "volume", "amount"]]

        except urllib.error.URLError as e:
            print(f"  TDX 连接失败 ({code}): 通达信客户端可能未运行")
            return None
        except Exception as e:
            print(f"  TDX 获取失败 ({code}): {e}")
            return None

    # ==================== AKShare（保留向后兼容） ====================

    def _fetch_from_akshare(self, code: str) -> Optional[pd.DataFrame]:
        """从AKShare获取ETF日线数据（保留向后兼容）"""
        try:
            import akshare as ak

            start_date = (datetime.strptime(self.config.backtest_start, "%Y-%m-%d") -
                         timedelta(days=400)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")

            df = ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="hfq"
            )

            if df.empty:
                return None

            df = df.rename(columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount"
            })

            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)

            return df[["date", "open", "high", "low", "close", "volume", "amount"]]

        except Exception as e:
            print(f"  AKShare获取失败 ({code}): {e}")
            return None

    # ==================== 缓存管理 ====================

    def load_from_cache(self, code: str) -> Optional[pd.DataFrame]:
        """从缓存加载数据（支持parquet/csv）"""
        return self._load_cache(code)

    def _load_cache(self, code: str, ignore_expiry: bool = False) -> Optional[pd.DataFrame]:
        """加载本地缓存"""
        for ext in ["parquet", "csv"]:
            cache_file = os.path.join(self.cache_dir, f"{code}.{ext}")
            if os.path.exists(cache_file):
                try:
                    if ext == "parquet":
                        df = pd.read_parquet(cache_file)
                    else:
                        df = pd.read_csv(cache_file, parse_dates=["date"])
                    if ignore_expiry:
                        return df
                    # 检查缓存是否过期（超过1天）
                    last_date = pd.to_datetime(df["date"]).max()
                    if (datetime.now() - last_date).days <= 1:
                        return df
                except Exception:
                    pass
        return None

    def _save_cache(self, code: str, df: pd.DataFrame):
        """保存到本地缓存"""
        try:
            cache_file = os.path.join(self.cache_dir, f"{code}.parquet")
            df.to_parquet(cache_file, index=False)
        except ImportError:
            cache_file = os.path.join(self.cache_dir, f"{code}.csv")
            df.to_csv(cache_file, index=False)

    # ==================== 工具方法 ====================

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
