"""
贵金属交易决策辅助系统 - 测试用例生成器 v2
生成更多历史行情场景，覆盖所有Regime类型和策略类型
"""

import json
from datetime import datetime, timedelta
import random

def generate_comprehensive_test_cases():
    """生成全面的测试用例"""
    test_cases = []

    # ==================== R1降息式多头场景 ====================
    # TC-001: R1标准降息式多头
    test_cases.append({
        "id": "TC-001",
        "name": "R1标准降息式多头 - 黄金做多",
        "regime": "R1",
        "market_data": {
            "gold_price": 3350,
            "tips_10y": 1.8,
            "tips_10y_prev": 2.0,
            "dxy": 100.5,
            "dxy_prev": 102.0,
            "sofr": 5.0,
            "sofr_change": 0,
            "vix": 18,
            "gvx": 12,
            "vxslv": 18,
            "gold_200ma": 3200,
            "gold_above_200ma": True,
            "cftc_net_long": 200000,
            "cftc_net_long_prev": 195000,
            "cb_purchasing": True,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1",
            "strategy": ["宏观利率波段做多", "均线顺势"],
            "forbidden": ["趋势做空"],
            "position_range": [5, 10],
            "stop_loss_type": "结构止损"
        }
    })

    # TC-002: R1降息+金银比高位
    test_cases.append({
        "id": "TC-002",
        "name": "R1降息+金银比高位 - 金银比套利",
        "regime": "R1/R2",
        "market_data": {
            "gold_price": 3300,
            "silver_price": 33,
            "gold_silver_ratio": 100,
            "tips_10y": 1.9,
            "tips_10y_prev": 2.1,
            "dxy": 101,
            "dxy_prev": 102.5,
            "sofr": 5.0,
            "gvx": 14,
            "vxslv": 19,
            "gold_200ma": 3200,
            "gold_above_200ma": True,
            "cftc_net_long": 190000,
            "cb_purchasing": True,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1/R2",
            "strategy": ["金银比均值回归"],
            "ratio_trigger": 95,
            "ratio_target": 82,
            "position_type": "对冲"
        }
    })

    # TC-003: R1均线顺势+金叉
    test_cases.append({
        "id": "TC-003",
        "name": "R1均线顺势 - 金叉做多",
        "regime": "R1",
        "market_data": {
            "gold_price": 3320,
            "ma20": 3300,
            "ma60": 3280,
            "ma20_above_ma60": True,
            "ma20_cross_ma60_days": 3,
            "atr_14": 25,
            "atr_percentile": 55,
            "tips_10y": 1.8,
            "dxy": 100.5,
            "gvx": 14,
            "vxslv": 20,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1",
            "strategy": ["均线顺势波段"],
            "entry": "回踩MA20做多",
            "stop_loss": "MA20下方1.5×ATR",
            "hold_period": "1-10日"
        }
    })

    # TC-004: R1突破追单
    test_cases.append({
        "id": "TC-004",
        "name": "R1突破追单 - 放量突破",
        "regime": "R1",
        "market_data": {
            "gold_price": 3385,
            "resistance": 3380,
            "volume_ratio": 1.8,
            "oi_change": 5000,
            "tips_10y": 1.7,
            "dxy": 100,
            "gvx": 15,
            "vxslv": 22,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1",
            "strategy": ["突破追单"],
            "entry": "突破回测入场",
            "stop_loss": "突破起点",
            "confirmation": "放量+OI上升"
        }
    })

    # TC-005: R1季节性策略
    test_cases.append({
        "id": "TC-005",
        "name": "R1季节性策略 - 央行购金高峰",
        "regime": "R1/R4",
        "market_data": {
            "gold_price": 3200,
            "quarter": "Q1",
            "tips_10y": 1.8,
            "dxy": 100.5,
            "sofr": 5.0,
            "gvx": 15,
            "vxslv": 22,
            "cb_purchasing": True,
            "seasonal_low": True,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1/R4",
            "strategy": ["季节性策略"],
            "entry": "季节性低位入场",
            "hold_period": "季度",
            "stop_loss": "前低或季节性窗口结束"
        }
    })

    # ==================== R2高利率震荡场景 ====================
    # TC-006: R2标准震荡
    test_cases.append({
        "id": "TC-006",
        "name": "R2高利率震荡 - 区间交易",
        "regime": "R2",
        "market_data": {
            "gold_price": 3300,
            "tips_10y": 2.0,
            "tips_10y_prev": 2.0,
            "dxy": 104,
            "dxy_prev": 103.5,
            "sofr": 5.2,
            "sofr_change": 0,
            "vix": 16,
            "gvx": 18,
            "vxslv": 25,
            "gold_200ma": 3250,
            "gold_above_200ma": True,
            "cftc_net_long": 180000,
            "cftc_net_long_prev": 178000,
            "cb_purchasing": True,
            "fed_divided": True,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R2",
            "strategy": ["区间高抛低吸", "期权Iron Condor"],
            "forbidden": ["趋势追单"],
            "position_range": [2.5, 5],
            "stop_loss_type": "箱体外侧止损"
        }
    })

    # TC-007: R2波动率交易策略
    test_cases.append({
        "id": "TC-007",
        "name": "R2波动率交易策略 - GVX均值回归",
        "regime": "R2",
        "market_data": {
            "gold_price": 3300,
            "gvx": 35,
            "gvx_percentile": 92,
            "vxslv": 42,
            "vxslv_percentile": 88,
            "gold_in_box": True,
            "tips_10y": 2.0,
            "dxy": 103,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R2",
            "strategy": ["波动率交易策略"],
            "entry": "卖Iron Condor/卖Strangle",
            "target": "GVX回归50%分位",
            "stop_loss": "GVX突破95%分位"
        }
    })

    # TC-008: R2金银比套利
    test_cases.append({
        "id": "TC-008",
        "name": "R2金银比套利 - 比价回归",
        "regime": "R1/R2",
        "market_data": {
            "gold_price": 3300,
            "silver_price": 33,
            "gold_silver_ratio": 100,
            "tips_10y": 2.0,
            "dxy": 104,
            "sofr": 5.2,
            "gvx": 18,
            "vxslv": 25,
            "industrial_demand": "normal",
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1/R2",
            "strategy": ["金银比均值回归"],
            "ratio_trigger": 95,
            "ratio_target": 82,
            "position_type": "对冲"
        }
    })

    # ==================== R3鹰派重定价场景 ====================
    # TC-009: R3标准鹰派
    test_cases.append({
        "id": "TC-009",
        "name": "R3鹰派重定价 - 黄金做空",
        "regime": "R3",
        "market_data": {
            "gold_price": 3200,
            "tips_10y": 2.5,
            "tips_10y_prev": 2.2,
            "dxy": 106,
            "dxy_prev": 104,
            "sofr": 5.5,
            "sofr_change": 0,
            "vix": 22,
            "gvx": 28,
            "vxslv": 32,
            "gold_200ma": 3250,
            "gold_above_200ma": False,
            "cftc_net_long": 150000,
            "cftc_net_long_prev": 160000,
            "cb_purchasing": False,
            "fed_hawkish": True,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R3",
            "strategy": ["宏观利率波段做空", "反弹做空"],
            "forbidden": ["趋势做多", "央行抄底"],
            "position_range": [5, 10],
            "stop_loss_type": "结构止损"
        }
    })

    # TC-010: R3均线顺势做空
    test_cases.append({
        "id": "TC-010",
        "name": "R3均线顺势 - 死叉做空",
        "regime": "R3",
        "market_data": {
            "gold_price": 3180,
            "ma20": 3200,
            "ma60": 3220,
            "ma20_above_ma60": False,
            "ma20_cross_ma60_days": 5,
            "atr_14": 28,
            "atr_percentile": 60,
            "tips_10y": 2.4,
            "tips_10y_prev": 2.1,
            "dxy": 106,
            "dxy_prev": 104,
            "gvx": 26,
            "vxslv": 30,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R3",
            "strategy": ["均线顺势波段"],
            "entry": "反弹MA20做空",
            "stop_loss": "MA20上方1.5×ATR",
            "hold_period": "1-10日"
        }
    })

    # TC-011: R3突破追单做空
    test_cases.append({
        "id": "TC-011",
        "name": "R3突破追单 - 放量下破",
        "regime": "R3",
        "market_data": {
            "gold_price": 3150,
            "support": 3160,
            "volume_ratio": 1.6,
            "oi_change": 4000,
            "tips_10y": 2.5,
            "dxy": 106,
            "gvx": 28,
            "vxslv": 32,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R3",
            "strategy": ["突破追单"],
            "entry": "下破回测入场",
            "stop_loss": "突破起点",
            "confirmation": "放量+OI上升"
        }
    })

    # ==================== R4信用折价场景 ====================
    # TC-012: R4标准信用折价
    test_cases.append({
        "id": "TC-012",
        "name": "R4信用折价 - 央行抄底",
        "regime": "R4",
        "market_data": {
            "gold_price": 3100,
            "gold_price_prev": 3263,
            "tips_10y": 2.1,
            "tips_10y_prev": 2.0,
            "dxy": 103,
            "dxy_prev": 102,
            "sofr": 5.3,
            "sofr_change": 0,
            "vix": 25,
            "gvx": 30,
            "vxslv": 38,
            "gold_200ma": 3200,
            "gold_above_200ma": False,
            "cftc_net_long": 120000,
            "cftc_net_long_prev": 140000,
            "cb_purchasing": True,
            "geopolitical": True,
            "us_debt_concern": True,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R4",
            "strategy": ["央行抄底长线多"],
            "forbidden": ["卖Vol"],
            "position_range": [2.5, 5],
            "stop_loss_type": "前低外侧止损"
        }
    })

    # TC-013: R4季节性策略
    test_cases.append({
        "id": "TC-013",
        "name": "R4季节性策略 - 央行购金高峰",
        "regime": "R1/R4",
        "market_data": {
            "gold_price": 3200,
            "quarter": "Q3",
            "tips_10y": 2.2,
            "tips_10y_prev": 2.1,
            "dxy": 104,
            "sofr": 5.3,
            "gvx": 22,
            "vxslv": 30,
            "cb_purchasing": True,
            "seasonal_low": True,
            "geopolitical": True,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1/R4",
            "strategy": ["季节性策略"],
            "entry": "季节性低位入场",
            "hold_period": "季度",
            "stop_loss": "前低或季节性窗口结束"
        }
    })

    # ==================== R5流动性危机场景 ====================
    # TC-014: R5标准流动性危机
    test_cases.append({
        "id": "TC-014",
        "name": "R5流动性危机 - 只平不开",
        "regime": "R5",
        "market_data": {
            "gold_price": 3000,
            "tips_10y": 2.2,
            "tips_10y_prev": 2.1,
            "dxy": 108,
            "dxy_prev": 105,
            "sofr": 5.8,
            "sofr_change": 0.15,
            "vix": 35,
            "gvx": 40,
            "vxslv": 55,
            "gold_200ma": 3200,
            "gold_above_200ma": False,
            "cftc_net_long": 100000,
            "cftc_net_long_prev": 110000,
            "cb_purchasing": False,
            "basis_widening": True,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R5",
            "strategy": ["只平仓不开新仓"],
            "forbidden": ["所有策略"],
            "position_range": [0, 0],
            "stop_loss_type": "无"
        }
    })

    # TC-015: R5 GVX极端波动
    test_cases.append({
        "id": "TC-015",
        "name": "R5 GVX极端波动 - 只平不开",
        "regime": "R5",
        "market_data": {
            "gold_price": 3050,
            "tips_10y": 2.1,
            "dxy": 107,
            "sofr": 5.5,
            "sofr_change": 0.03,
            "gvx": 42,
            "gvx_percentile": 97,
            "vxslv": 48,
            "vxslv_percentile": 93,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R5",
            "strategy": ["只平仓不开新仓"],
            "forbidden": ["所有策略"],
            "position_range": [0, 0]
        }
    })

    # ==================== 事件驱动场景 ====================
    # TC-016: 地缘冲突事件驱动
    test_cases.append({
        "id": "TC-016",
        "name": "事件驱动避险 - 地缘冲突",
        "regime": "Any",
        "market_data": {
            "gold_price": 3350,
            "gold_price_1h_ago": 3320,
            "tips_10y": 2.0,
            "dxy": 103,
            "sofr": 5.2,
            "sofr_change": 0,
            "vix": 30,
            "gvx": 28,
            "vxslv": 35,
            "geopolitical_event": "中东冲突升级",
            "event_time": "2小时前",
            "first_wave_done": True,
            "callback_support": 3330,
            "event_risk": "地缘冲突"
        },
        "expected": {
            "regime": "Any",
            "strategy": ["事件避险短多"],
            "entry_timing": "回调支撑入场",
            "hold_period": "短线",
            "stop_loss": "入场点下方1-2ATR"
        }
    })

    # TC-017: 银行危机事件驱动
    test_cases.append({
        "id": "TC-017",
        "name": "事件驱动避险 - 银行危机",
        "regime": "Any",
        "market_data": {
            "gold_price": 3400,
            "gold_price_2h_ago": 3360,
            "tips_10y": 1.9,
            "dxy": 101,
            "sofr": 5.5,
            "sofr_change": 0.08,
            "vix": 40,
            "gvx": 35,
            "vxslv": 42,
            "bank_crisis": True,
            "event_time": "3小时前",
            "first_wave_done": True,
            "callback_support": 3380,
            "event_risk": "银行危机"
        },
        "expected": {
            "regime": "Any",
            "strategy": ["事件避险短多"],
            "entry_timing": "回调支撑入场",
            "hold_period": "短线",
            "stop_loss": "入场点下方1-2ATR"
        }
    })

    # ==================== 技术形态场景 ====================
    # TC-018: 头肩底突破
    test_cases.append({
        "id": "TC-018",
        "name": "技术形态策略 - 头肩底突破",
        "regime": "R1",
        "market_data": {
            "gold_price": 3350,
            "neckline": 3340,
            "pattern": "头肩底",
            "pattern_height": 80,
            "neckline_break": True,
            "volume_ratio": 1.6,
            "tips_10y": 1.7,
            "dxy": 100,
            "gvx": 16,
            "vxslv": 24,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1",
            "strategy": ["技术形态策略"],
            "entry": "颈线突破入场",
            "target": "形态高度1倍投影",
            "stop_loss": "颈线反侧1×ATR"
        }
    })

    # TC-019: 头肩顶突破
    test_cases.append({
        "id": "TC-019",
        "name": "技术形态策略 - 头肩顶突破",
        "regime": "R3",
        "market_data": {
            "gold_price": 3150,
            "neckline": 3160,
            "pattern": "头肩顶",
            "pattern_height": 70,
            "neckline_break": True,
            "volume_ratio": 1.5,
            "tips_10y": 2.5,
            "dxy": 106,
            "gvx": 28,
            "vxslv": 34,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R3",
            "strategy": ["技术形态策略"],
            "entry": "颈线突破入场",
            "target": "形态高度1倍投影",
            "stop_loss": "颈线反侧1×ATR"
        }
    })

    # ==================== 跨品种套利场景 ====================
    # TC-020: 金铂比套利
    test_cases.append({
        "id": "TC-020",
        "name": "跨品种套利 - 金铂比回归",
        "regime": "R1/R2",
        "market_data": {
            "gold_price": 3300,
            "platinum_price": 2750,
            "gold_platinum_ratio": 1.2,
            "tips_10y": 1.9,
            "dxy": 101,
            "sofr": 5.0,
            "gvx": 14,
            "vxslv": 19,
            "industrial_demand": "normal",
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1/R2",
            "strategy": ["跨品种套利"],
            "ratio_trigger": 1.2,
            "ratio_target": 1.0,
            "position_type": "对冲"
        }
    })

    # ==================== 资金流向场景 ====================
    # TC-021: CFTC极值反转
    test_cases.append({
        "id": "TC-021",
        "name": "资金流向策略 - CFTC极值反转",
        "regime": "R3→R1",
        "market_data": {
            "gold_price": 3150,
            "cftc_net_long": 90000,
            "cftc_percentile": 7,
            "cftc_change_week1": 5000,
            "cftc_change_week2": 8000,
            "support_zone": [3100, 3150],
            "tips_10y": 2.3,
            "tips_10y_prev": 2.5,
            "dxy": 104,
            "dxy_prev": 106,
            "gvx": 28,
            "vxslv": 36,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R3→R1",
            "strategy": ["资金流向策略"],
            "entry": "结构支撑带入场",
            "target": "CFTC回归50%分位",
            "stop_loss": "反向突破结构"
        }
    })

    # TC-022: CFTC极值反转（多头极端）
    test_cases.append({
        "id": "TC-022",
        "name": "资金流向策略 - CFTC多头极端",
        "regime": "R1→R3",
        "market_data": {
            "gold_price": 3450,
            "cftc_net_long": 280000,
            "cftc_percentile": 95,
            "cftc_change_week1": -8000,
            "cftc_change_week2": -12000,
            "resistance_zone": [3440, 3480],
            "tips_10y": 1.6,
            "tips_10y_prev": 1.4,
            "dxy": 99,
            "dxy_prev": 98,
            "gvx": 22,
            "vxslv": 28,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1→R3",
            "strategy": ["资金流向策略"],
            "entry": "结构阻力带入场",
            "target": "CFTC回归50%分位",
            "stop_loss": "反向突破结构"
        }
    })

    # ==================== 逆势抄底场景 ====================
    # TC-023: Regime拐点逆势抄底
    test_cases.append({
        "id": "TC-023",
        "name": "逆势抄底 - Regime拐点",
        "regime": "R3→R1",
        "market_data": {
            "gold_price": 3100,
            "gold_price_5d_ago": 3200,
            "tips_10y": 2.3,
            "tips_10y_prev": 2.5,
            "dxy": 104,
            "dxy_prev": 106,
            "dot_plot_shift": True,
            "cftc_net_long": 95000,
            "cftc_percentile": 8,
            "support_zone": [3080, 3120],
            "gvx": 32,
            "vxslv": 40,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R3→R1",
            "strategy": ["逆势抄底"],
            "entry": "结构支撑带入场",
            "stop_loss": "反向突破结构",
            "risk_level": "高风险",
            "position": "买Call/Put"
        }
    })

    # ==================== 白银专项场景 ====================
    # TC-024: 白银工业需求强劲
    test_cases.append({
        "id": "TC-024",
        "name": "白银工业需求强劲 - 做多白银",
        "regime": "R1",
        "market_data": {
            "silver_price": 35,
            "gold_price": 3300,
            "gold_silver_ratio": 94,
            "tips_10y": 1.8,
            "dxy": 100.5,
            "sofr": 5.0,
            "gvx": 14,
            "vxslv": 22,
            "industrial_demand": "strong",
            "solar_installation": "high",
            "auto_sales": "strong",
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1",
            "strategy": ["宏观利率波段做多"],
            "position_range": [2, 5],
            "stop_loss_type": "结构止损"
        }
    })

    # TC-025: 白银工业需求疲软
    test_cases.append({
        "id": "TC-025",
        "name": "白银工业需求疲软 - 做空白银",
        "regime": "R3",
        "market_data": {
            "silver_price": 28,
            "gold_price": 3200,
            "gold_silver_ratio": 114,
            "tips_10y": 2.5,
            "dxy": 106,
            "sofr": 5.5,
            "gvx": 28,
            "vxslv": 38,
            "industrial_demand": "weak",
            "solar_installation": "low",
            "auto_sales": "weak",
            "event_risk": "None"
        },
        "expected": {
            "regime": "R3",
            "strategy": ["宏观利率波段做空"],
            "position_range": [1, 2.5],
            "stop_loss_type": "结构止损"
        }
    })

    # ==================== 铂金钯金场景 ====================
    # TC-026: 铂金催化剂需求
    test_cases.append({
        "id": "TC-026",
        "name": "铂金催化剂需求 - 做多铂金",
        "regime": "R1",
        "market_data": {
            "platinum_price": 1100,
            "gold_price": 3300,
            "gold_platinum_ratio": 3.0,
            "tips_10y": 1.8,
            "dxy": 100.5,
            "sofr": 5.0,
            "gvx": 14,
            "vxslv": 20,
            "catalyst_demand": "strong",
            "auto_sales": "strong",
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1",
            "strategy": ["宏观利率波段做多"],
            "position_range": [1, 2.5],
            "stop_loss_type": "结构止损"
        }
    })

    # TC-027: 钯金催化剂需求
    test_cases.append({
        "id": "TC-027",
        "name": "钯金催化剂需求 - 做多钯金",
        "regime": "R1",
        "market_data": {
            "palladium_price": 1500,
            "gold_price": 3300,
            "gold_palladium_ratio": 2.2,
            "tips_10y": 1.8,
            "dxy": 100.5,
            "sofr": 5.0,
            "gvx": 14,
            "vxslv": 20,
            "catalyst_demand": "strong",
            "auto_sales": "strong",
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1",
            "strategy": ["宏观利率波段做多"],
            "position_range": [1, 2.5],
            "stop_loss_type": "结构止损"
        }
    })

    # ==================== 沪金沪银场景 ====================
    # TC-028: 沪金内外盘套利
    test_cases.append({
        "id": "TC-028",
        "name": "沪金内外盘套利 - 溢价过高",
        "regime": "R1/R2",
        "market_data": {
            "gold_price_cny": 800,
            "gold_price_usd": 3300,
            "usdcny": 7.2,
            "implied_premium": 2.5,
            "normal_premium": 1.0,
            "tips_10y": 1.9,
            "dxy": 101,
            "sofr": 5.0,
            "gvx": 14,
            "vxslv": 19,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1/R2",
            "strategy": ["内外盘套利"],
            "entry": "卖沪金/买国际金",
            "target": "溢价回归正常",
            "stop_loss": "溢价继续扩大"
        }
    })

    # TC-029: 沪银内外盘套利
    test_cases.append({
        "id": "TC-029",
        "name": "沪银内外盘套利 - 溢价过高",
        "regime": "R1/R2",
        "market_data": {
            "silver_price_cny": 8500,
            "silver_price_usd": 35,
            "usdcny": 7.2,
            "implied_premium": 500,
            "normal_premium": 200,
            "tips_10y": 1.9,
            "dxy": 101,
            "sofr": 5.0,
            "gvx": 14,
            "vxslv": 19,
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1/R2",
            "strategy": ["内外盘套利"],
            "entry": "卖沪银/买国际银",
            "target": "溢价回归正常",
            "stop_loss": "溢价继续扩大"
        }
    })

    # ==================== 期权专项场景 ====================
    # TC-030: 期权买权替代期货
    test_cases.append({
        "id": "TC-030",
        "name": "期权买权替代期货 - R1做多",
        "regime": "R1",
        "market_data": {
            "gold_price": 3350,
            "tips_10y": 1.8,
            "dxy": 100.5,
            "sofr": 5.0,
            "gvx": 12,
            "gvx_percentile": 20,
            "vxslv": 18,
            "vxslv_percentile": 22,
            "option_liquidity": "good",
            "event_risk": "None"
        },
        "expected": {
            "regime": "R1",
            "strategy": ["期权买权替代期货"],
            "entry": "买Call",
            "stop_loss": "时间止损3天",
            "position": "Premium≤账户1%"
        }
    })

    # TC-031: 期权卖权收入策略
    test_cases.append({
        "id": "TC-031",
        "name": "期权卖权收入策略 - R2横盘",
        "regime": "R2",
        "market_data": {
            "gold_price": 3300,
            "tips_10y": 2.0,
            "dxy": 103,
            "sofr": 5.2,
            "gvx": 28,
            "gvx_percentile": 78,
            "vxslv": 35,
            "vxslv_percentile": 75,
            "option_liquidity": "good",
            "event_risk": "None"
        },
        "expected": {
            "regime": "R2",
            "strategy": ["期权卖权收入策略"],
            "entry": "卖Covered Call/Iron Condor",
            "stop_loss": "GVX突破90%分位",
            "position": "保证金缓冲40%"
        }
    })

    # TC-032: 期权保护性保险
    test_cases.append({
        "id": "TC-032",
        "name": "期权保护性保险 - 事件窗口",
        "regime": "R1",
        "market_data": {
            "gold_price": 3350,
            "tips_10y": 1.8,
            "dxy": 100.5,
            "sofr": 5.0,
            "gvx": 18,
            "vxslv": 25,
            "option_liquidity": "good",
            "event_risk": "CPI数据",
            "event_time": "明天20:30"
        },
        "expected": {
            "regime": "R1",
            "strategy": ["期权保护性保险"],
            "entry": "期货多单+买Put",
            "stop_loss": "Put成本",
            "position": "Premium≤账户0.5%"
        }
    })

    return test_cases

def save_test_cases(test_cases, output_path):
    """保存测试用例"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(test_cases, f, ensure_ascii=False, indent=2)
    print(f"已生成 {len(test_cases)} 个测试用例")

if __name__ == "__main__":
    test_cases = generate_comprehensive_test_cases()
    output_path = r"C:\Users\Administrator\.workbuddy\temp\test-cases-v2.json"
    save_test_cases(test_cases, output_path)
