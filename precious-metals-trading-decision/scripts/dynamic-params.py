"""
贵金属交易决策辅助系统 - 动态参数调整模块
根据市场状态动态调整GVX/VXSLV阈值
"""

import json
import numpy as np
from datetime import datetime, timedelta

class DynamicParams:
    def __init__(self, lookback_days=90):
        self.lookback_days = lookback_days
        self.history = {
            "gvx": [],
            "vxslv": [],
            "gold_price": [],
            "silver_price": [],
            "tips_10y": [],
            "dxy": []
        }
        self.current_params = {
            "gvx_thresholds": {
                "25%": 13.5,
                "50%": 18.2,
                "75%": 24.8,
                "90%": 31.5,
                "95%": 38.2
            },
            "vxslv_thresholds": {
                "25%": 18.5,
                "50%": 26.3,
                "75%": 35.8,
                "90%": 45.2,
                "95%": 52.5
            },
            "position_multipliers": {
                "extreme_low": 1.0,
                "low": 1.0,
                "medium": 1.0,
                "high": 0.5,
                "extreme_high": 0.0
            },
            "stop_loss_multipliers": {
                "extreme_low": 1.5,
                "low": 1.5,
                "medium": 1.0,
                "high": 0.75,
                "extreme_high": 0.5
            }
        }

    def update_history(self, market_data):
        """更新历史数据"""
        for key in self.history:
            if key in market_data:
                self.history[key].append(market_data[key])
                # 保持历史数据在lookback_days内
                if len(self.history[key]) > self.lookback_days:
                    self.history[key] = self.history[key][-self.lookback_days:]

    def calculate_percentiles(self, data, percentiles=[25, 50, 75, 90, 95]):
        """计算分位数"""
        if len(data) < 10:
            return None
        return {f"{p}%": np.percentile(data, p) for p in percentiles}

    def detect_market_regime(self):
        """检测市场状态"""
        if len(self.history["tips_10y"]) < 5:
            return "unknown"

        # 计算TIPS趋势
        tips_trend = self.history["tips_10y"][-1] - self.history["tips_10y"][-5]

        # 计算DXY趋势
        dxy_trend = self.history["dxy"][-1] - self.history["dxy"][-5] if len(self.history["dxy"]) >= 5 else 0

        # 计算GVX水平
        gvx_current = self.history["gvx"][-1] if self.history["gvx"] else 20

        # 判断市场状态
        if tips_trend < -0.1 and dxy_trend < -0.5:
            return "R1"  # 降息式多头
        elif abs(tips_trend) < 0.05 and abs(dxy_trend) < 0.5:
            return "R2"  # 高利率震荡
        elif tips_trend > 0.1 and dxy_trend > 0.5:
            return "R3"  # 鹰派重定价
        elif gvx_current > 31.5:
            return "R5"  # 流动性危机
        else:
            return "R2"  # 默认震荡

    def adjust_gvx_thresholds(self):
        """动态调整GVX阈值"""
        if len(self.history["gvx"]) < 30:
            return self.current_params["gvx_thresholds"]

        # 计算当前GVX的分位数
        gvx_percentiles = self.calculate_percentiles(self.history["gvx"])

        if gvx_percentiles:
            # 使用滚动窗口分位数
            self.current_params["gvx_thresholds"] = gvx_percentiles

        # 根据市场状态调整
        market_regime = self.detect_market_regime()

        if market_regime == "R5":
            # 流动性危机时，降低阈值（更敏感）
            for key in self.current_params["gvx_thresholds"]:
                self.current_params["gvx_thresholds"][key] *= 0.8
        elif market_regime == "R1":
            # 降息式多头时，提高阈值（更宽容）
            for key in self.current_params["gvx_thresholds"]:
                self.current_params["gvx_thresholds"][key] *= 1.1

        return self.current_params["gvx_thresholds"]

    def adjust_vxslv_thresholds(self):
        """动态调整VXSLV阈值"""
        if len(self.history["vxslv"]) < 30:
            return self.current_params["vxslv_thresholds"]

        # 计算当前VXSLV的分位数
        vxslv_percentiles = self.calculate_percentiles(self.history["vxslv"])

        if vxslv_percentiles:
            # 使用滚动窗口分位数
            self.current_params["vxslv_thresholds"] = vxslv_percentiles

        # 根据市场状态调整
        market_regime = self.detect_market_regime()

        if market_regime == "R5":
            # 流动性危机时，降低阈值（更敏感）
            for key in self.current_params["vxslv_thresholds"]:
                self.current_params["vxslv_thresholds"][key] *= 0.8
        elif market_regime == "R1":
            # 降息式多头时，提高阈值（更宽容）
            for key in self.current_params["vxslv_thresholds"]:
                self.current_params["vxslv_thresholds"][key] *= 1.1

        return self.current_params["vxslv_thresholds"]

    def adjust_position_multipliers(self, gvx_level):
        """根据GVX水平动态调整仓位乘数"""
        if gvx_level == "extreme_low":
            return 1.0
        elif gvx_level == "low":
            return 1.0
        elif gvx_level == "medium":
            return 1.0
        elif gvx_level == "high":
            return 0.5
        elif gvx_level == "extreme_high":
            return 0.0
        else:
            return 1.0

    def adjust_stop_loss_multipliers(self, gvx_level):
        """根据GVX水平动态调整止损乘数"""
        if gvx_level == "extreme_low":
            return 1.5
        elif gvx_level == "low":
            return 1.5
        elif gvx_level == "medium":
            return 1.0
        elif gvx_level == "high":
            return 0.75
        elif gvx_level == "extreme_high":
            return 0.5
        else:
            return 1.0

    def get_gvx_level(self, gvx_value):
        """根据GVX值判断水平"""
        thresholds = self.current_params["gvx_thresholds"]

        if gvx_value < thresholds.get("25%", 13.5):
            return "extreme_low"
        elif gvx_value < thresholds.get("50%", 18.2):
            return "low"
        elif gvx_value < thresholds.get("75%", 24.8):
            return "medium"
        elif gvx_value < thresholds.get("90%", 31.5):
            return "high"
        else:
            return "extreme_high"

    def get_vxslv_level(self, vxslv_value):
        """根据VXSLV值判断水平"""
        thresholds = self.current_params["vxslv_thresholds"]

        if vxslv_value < thresholds.get("25%", 18.5):
            return "extreme_low"
        elif vxslv_value < thresholds.get("50%", 26.3):
            return "low"
        elif vxslv_value < thresholds.get("75%", 35.8):
            return "medium"
        elif vxslv_value < thresholds.get("90%", 45.2):
            return "high"
        else:
            return "extreme_high"

    def calculate_dynamic_params(self, market_data):
        """计算动态参数"""
        # 更新历史数据
        self.update_history(market_data)

        # 调整阈值
        gvx_thresholds = self.adjust_gvx_thresholds()
        vxslv_thresholds = self.adjust_vxslv_thresholds()

        # 获取当前水平
        gvx_current = market_data.get("gvx", 20)
        vxslv_current = market_data.get("vxslv", 25)

        gvx_level = self.get_gvx_level(gvx_current)
        vxslv_level = self.get_vxslv_level(vxslv_current)

        # 计算仓位乘数
        position_multiplier = self.adjust_position_multipliers(gvx_level)

        # 计算止损乘数
        stop_loss_multiplier = self.adjust_stop_loss_multipliers(gvx_level)

        # 检测市场状态
        market_regime = self.detect_market_regime()

        return {
            "gvx_thresholds": gvx_thresholds,
            "vxslv_thresholds": vxslv_thresholds,
            "gvx_level": gvx_level,
            "vxslv_level": vxslv_level,
            "position_multiplier": position_multiplier,
            "stop_loss_multiplier": stop_loss_multiplier,
            "market_regime": market_regime
        }

def test_dynamic_params():
    """测试动态参数调整"""
    print("\n" + "="*80)
    print("动态参数调整测试")
    print("="*80)

    params = DynamicParams(lookback_days=90)

    # 模拟历史数据
    test_data = [
        {"gvx": 12, "vxslv": 18, "tips_10y": 2.0, "dxy": 103},
        {"gvx": 14, "vxslv": 20, "tips_10y": 1.9, "dxy": 102.5},
        {"gvx": 16, "vxslv": 22, "tips_10y": 1.8, "dxy": 102},
        {"gvx": 18, "vxslv": 25, "tips_10y": 1.7, "dxy": 101.5},
        {"gvx": 20, "vxslv": 28, "tips_10y": 1.6, "dxy": 101},
        {"gvx": 22, "vxslv": 30, "tips_10y": 1.5, "dxy": 100.5},
        {"gvx": 25, "vxslv": 33, "tips_10y": 1.4, "dxy": 100},
        {"gvx": 28, "vxslv": 36, "tips_10y": 1.3, "dxy": 99.5},
        {"gvx": 32, "vxslv": 40, "tips_10y": 1.2, "dxy": 99},
        {"gvx": 35, "vxslv": 45, "tips_10y": 1.1, "dxy": 98.5},
    ]

    # 更新历史数据
    for data in test_data:
        params.update_history(data)

    # 测试当前状态
    current_data = {"gvx": 28, "vxslv": 35, "tips_10y": 1.5, "dxy": 101}
    result = params.calculate_dynamic_params(current_data)

    print(f"\n当前市场数据: {current_data}")
    print(f"\n动态参数:")
    print(f"  GVX阈值: {result['gvx_thresholds']}")
    print(f"  VXSLV阈值: {result['vxslv_thresholds']}")
    print(f"  GVX水平: {result['gvx_level']}")
    print(f"  VXSLV水平: {result['vxslv_level']}")
    print(f"  仓位乘数: {result['position_multiplier']}")
    print(f"  止损乘数: {result['stop_loss_multiplier']}")
    print(f"  市场状态: {result['market_regime']}")

    # 测试不同市场状态
    print("\n不同市场状态下的参数:")
    test_scenarios = [
        {"name": "降息式多头", "tips_10y": 1.5, "dxy": 100},
        {"name": "高利率震荡", "tips_10y": 2.0, "dxy": 103},
        {"name": "鹰派重定价", "tips_10y": 2.5, "dxy": 106},
    ]

    for scenario in test_scenarios:
        test_data = {"gvx": 25, "vxslv": 32, **scenario}
        result = params.calculate_dynamic_params(test_data)
        print(f"\n  {scenario['name']}:")
        print(f"    市场状态: {result['market_regime']}")
        print(f"    仓位乘数: {result['position_multiplier']}")

    return result

if __name__ == "__main__":
    test_dynamic_params()
