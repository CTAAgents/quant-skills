"""
贵金属交易决策辅助系统 - 数据源集成模块
获取实时行情和宏观经济数据
"""

import json
import numpy as np
from datetime import datetime, timedelta
import urllib.request
import urllib.parse

class DataSourceIntegration:
    def __init__(self):
        self.data_sources = {
            "realtime": {
                "yahoo_finance": "https://query1.finance.yahoo.com/v8/finance/chart/",
                "alpha_vantage": "https://www.alphavantage.co/query",
                "investing_com": "https://api.investing.com/api/financialdata/"
            },
            "macro": {
                "fred": "https://api.stlouisfed.org/fred/series/observations",
                "treasury": "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
            },
            "cftc": {
                "cftc": "https://publicreporting.cftc.gov/resource/"
            }
        }

        self.symbols = {
            "gold": {"yahoo": "GC=F", "investing": "XAU/USD"},
            "silver": {"yahoo": "SI=F", "investing": "XAG/USD"},
            "platinum": {"yahoo": "PL=F", "investing": "XPT/USD"},
            "palladium": {"yahoo": "PA=F", "investing": "XPD/USD"},
            "dxy": {"yahoo": "DX-Y.NYB", "investing": "DXY"},
            "tips_10y": {"fred": "DFII10"},
            "treasury_10y": {"fred": "DGS10"},
            "sofr": {"fred": "SOFR"}
        }

        self.cache = {}
        self.cache_timeout = 300  # 5分钟缓存

    def get_realtime_price(self, symbol):
        """获取实时价格"""
        # 模拟实时价格获取
        np.random.seed(hash(symbol) % 2**32)
        base_prices = {
            "gold": 3300,
            "silver": 35,
            "platinum": 1100,
            "palladium": 1500,
            "dxy": 103
        }

        base_price = base_prices.get(symbol, 100)
        price = base_price + np.random.normal(0, base_price * 0.01)

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "timestamp": datetime.now().isoformat(),
            "source": "simulated"
        }

    def get_historical_prices(self, symbol, days=90):
        """获取历史价格"""
        # 模拟历史价格获取
        np.random.seed(hash(symbol) % 2**32)
        base_prices = {
            "gold": 3300,
            "silver": 35,
            "platinum": 1100,
            "palladium": 1500,
            "dxy": 103
        }

        base_price = base_prices.get(symbol, 100)
        prices = []

        for i in range(days):
            date = datetime.now() - timedelta(days=days-i)
            price = base_price + np.random.normal(0, base_price * 0.02)
            prices.append({
                "date": date.strftime("%Y-%m-%d"),
                "price": round(price, 2)
            })

        return prices

    def get_macro_data(self, indicator):
        """获取宏观经济数据"""
        # 模拟宏观经济数据获取
        np.random.seed(hash(indicator) % 2**32)

        macro_data = {
            "tips_10y": {"value": 1.8, "unit": "%", "description": "10年期TIPS收益率"},
            "treasury_10y": {"value": 4.2, "unit": "%", "description": "10年期美债收益率"},
            "sofr": {"value": 5.0, "unit": "%", "description": "SOFR利率"},
            "cpi": {"value": 3.2, "unit": "%", "description": "CPI年率"},
            "pce": {"value": 2.8, "unit": "%", "description": "PCE年率"},
            "unemployment": {"value": 3.8, "unit": "%", "description": "失业率"},
            "gdp": {"value": 2.5, "unit": "%", "description": "GDP年率"},
            "dxy": {"value": 103, "unit": "", "description": "美元指数"},
            "vix": {"value": 18, "unit": "", "description": "VIX恐慌指数"},
            "gvx": {"value": 20, "unit": "", "description": "GVX黄金波动率指数"},
            "vxslv": {"value": 25, "unit": "", "description": "VXSLV白银波动率指数"}
        }

        data = macro_data.get(indicator, {"value": 0, "unit": "", "description": "未知指标"})
        data["indicator"] = indicator
        data["timestamp"] = datetime.now().isoformat()
        data["source"] = "simulated"

        return data

    def get_cftc_data(self, metal):
        """获取CFTC持仓数据"""
        # 模拟CFTC持仓数据
        np.random.seed(hash(metal) % 2**32)

        cftc_data = {
            "gold": {
                "noncommercial_long": 200000,
                "noncommercial_short": 50000,
                "net_position": 150000,
                "percentile": 65
            },
            "silver": {
                "noncommercial_long": 50000,
                "noncommercial_short": 20000,
                "net_position": 30000,
                "percentile": 55
            },
            "platinum": {
                "noncommercial_long": 20000,
                "noncommercial_short": 10000,
                "net_position": 10000,
                "percentile": 45
            },
            "palladium": {
                "noncommercial_long": 10000,
                "noncommercial_short": 5000,
                "net_position": 5000,
                "percentile": 40
            }
        }

        data = cftc_data.get(metal, {"noncommercial_long": 0, "noncommercial_short": 0, "net_position": 0, "percentile": 50})
        data["metal"] = metal
        data["timestamp"] = datetime.now().isoformat()
        data["source"] = "simulated"

        return data

    def get_cb_purchasing_data(self):
        """获取央行购金数据"""
        # 模拟央行购金数据
        return {
            "monthly_tons": 80,
            "annual_tons": 960,
            "yoy_change": 15,
            "top_buyers": ["中国", "印度", "土耳其", "波兰"],
            "timestamp": datetime.now().isoformat(),
            "source": "simulated"
        }

    def get_market_data_bundle(self):
        """获取市场数据包"""
        bundle = {
            "timestamp": datetime.now().isoformat(),
            "realtime": {},
            "macro": {},
            "cftc": {},
            "cb_purchasing": {}
        }

        # 获取实时价格
        for symbol in ["gold", "silver", "platinum", "palladium", "dxy"]:
            bundle["realtime"][symbol] = self.get_realtime_price(symbol)

        # 获取宏观经济数据
        for indicator in ["tips_10y", "treasury_10y", "sofr", "cpi", "pce", "unemployment", "gdp", "vix", "gvx", "vxslv"]:
            bundle["macro"][indicator] = self.get_macro_data(indicator)

        # 获取CFTC数据
        for metal in ["gold", "silver", "platinum", "palladium"]:
            bundle["cftc"][metal] = self.get_cftc_data(metal)

        # 获取央行购金数据
        bundle["cb_purchasing"] = self.get_cb_purchasing_data()

        return bundle

def test_data_source():
    """测试数据源集成"""
    print("\n" + "="*80)
    print("数据源集成测试")
    print("="*80)

    ds = DataSourceIntegration()

    # 测试实时价格
    print("\n1. 实时价格:")
    for symbol in ["gold", "silver", "platinum", "palladium", "dxy"]:
        price = ds.get_realtime_price(symbol)
        print(f"  {symbol}: {price['price']}")

    # 测试历史价格
    print("\n2. 历史价格（最近5天）:")
    prices = ds.get_historical_prices("gold", 5)
    for p in prices:
        print(f"  {p['date']}: {p['price']}")

    # 测试宏观经济数据
    print("\n3. 宏观经济数据:")
    for indicator in ["tips_10y", "treasury_10y", "sofr", "dxy", "vix", "gvx", "vxslv"]:
        data = ds.get_macro_data(indicator)
        print(f"  {data['description']}: {data['value']}{data['unit']}")

    # 测试CFTC数据
    print("\n4. CFTC持仓数据:")
    for metal in ["gold", "silver", "platinum", "palladium"]:
        data = ds.get_cftc_data(metal)
        print(f"  {metal}: 净持仓={data['net_position']}, 分位数={data['percentile']}%")

    # 测试央行购金数据
    print("\n5. 央行购金数据:")
    data = ds.get_cb_purchasing_data()
    print(f"  月度购金: {data['monthly_tons']}吨")
    print(f"  年度购金: {data['annual_tons']}吨")
    print(f"  同比变化: {data['yoy_change']}%")
    print(f"  主要买家: {', '.join(data['top_buyers'])}")

    # 测试市场数据包
    print("\n6. 市场数据包:")
    bundle = ds.get_market_data_bundle()
    print(f"  时间戳: {bundle['timestamp']}")
    print(f"  实时数据: {len(bundle['realtime'])}个品种")
    print(f"  宏观数据: {len(bundle['macro'])}个指标")
    print(f"  CFTC数据: {len(bundle['cftc'])}个品种")

    return ds

if __name__ == "__main__":
    test_data_source()
