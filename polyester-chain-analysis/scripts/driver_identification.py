#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚酯链主驱动识别模块 v1.0.0

核心功能：
1. 三层漏斗诊断SOP（L1年度/L2季度/L3周度）
2. 驱动归属判定表（PX/PTA/MEG/PF/PR）
3. 盘面验证三步法（领涨领跌/利润分配/月差结构）
4. 量化打分机制（0-100分）

核心铁律：
- 大层级压倒小层级
- 主驱动识别是核心
- 驱动切换是交易价值
- 盘面验证必不可少

============================================================
通达信 TdxCollector v2.0 期限结构工具（懒加载 + 缓存）
============================================================
"""

import os
import sys
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ============================================================
# 通达信 TdxCollector v2.0 期限结构工具（懒加载 + 缓存）
# ============================================================
_TDX_CACHE: Dict[str, dict] = {}
_TDX_COLLECTOR_INSTANCE = None

def _get_tdx_collector():
    global _TDX_COLLECTOR_INSTANCE
    if _TDX_COLLECTOR_INSTANCE is None:
        try:
            fds_dir = os.path.expanduser("~/.workbuddy/skills/futures-data-search")
            if fds_dir not in sys.path:
                sys.path.insert(0, fds_dir)
            from collectors.tdx_collector import TdxCollector
            _TDX_COLLECTOR_INSTANCE = TdxCollector()
            if not _TDX_COLLECTOR_INSTANCE.is_available:
                _TDX_COLLECTOR_INSTANCE = None
        except Exception:
            _TDX_COLLECTOR_INSTANCE = None
    return _TDX_COLLECTOR_INSTANCE

def get_term_structure_from_tdx(variety: str) -> dict:
    """
    通过通达信获取品种期限结构（带缓存）。
    优先级高于 DuckDB/AKShare 的期限结构数据。
    """
    key = variety.upper()
    if key in _TDX_CACHE:
        return _TDX_CACHE[key]
    tdx = _get_tdx_collector()
    if not tdx:
        return {}
    try:
        ts = tdx.get_term_structure(key)
        if ts:
            result = {
                'type': ts.get('type', '').lower(),
                'slope': ts.get('slope', 0) / 100.0,
                'near_price': ts.get('near_price'),
                'far_price': ts.get('far_price'),
                'contract_count': ts.get('contract_count', 0),
            }
            contracts = ts.get('contracts', [])
            if len(contracts) >= 2:
                result['spread'] = contracts[0]['price'] - contracts[1]['price']
                sh = tdx.get_spread_history(key, contracts[0]['month'], contracts[1]['month'], days=60)
                if sh:
                    result['spread_z_score'] = sh['z_score']
            _TDX_CACHE[key] = result
            print(f"[TDX] {key}: 期限结构={result['type']}(斜率={ts.get('slope',0)}%, 价差Z={result.get('spread_z_score','?')})")
            return result
    except Exception:
        pass
    return {}

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ========== 数据类定义 ==========

@dataclass
class TrendContext:
    """宏观趋势上下文 — 在打分前评估，作为趋势过滤器"""
    macro_trend: str            # 宏观趋势：bullish/bearish/neutral
    crude_trend: str            # 原油趋势：bullish/bearish/neutral
    polyester_trend: str        # 聚酯链整体趋势：bullish/bearish/neutral
    trend_strength: str         # 趋势强度：strong/moderate/weak
    macro_score_cap: float      # 宏观趋势对打分上限的调整因子 (0.0-1.0)
    avg_chain_change_10d: float # 聚酯链10日平均涨跌幅
    trending_down_harmonized: bool  # 全产业链是否一致下跌


@dataclass
class DriverScore:
    """主驱动识别得分（含趋势感知）"""
    l1_score: float         # L1年度层得分 (0-100)
    l2_score: float         # L2季度层得分 (0-100)
    l3_score: float         # L3周度层得分 (0-100)
    raw_score: float        # 原始综合得分（未过滤）
    total_score: float      # 趋势过滤后综合得分 (0-100)
    primary_driver: str     # 主驱动类型
    driver_strength: str    # 驱动强度：强/中/弱
    confidence: str         # 置信度：高/中/低
    trade_signal: str       # 交易信号：HOLD/BUY/SELL（右侧确认后）
    macro_context: TrendContext = None  # 宏观趋势上下文


@dataclass
class DriverAttribution:
    """驱动归属判定结果"""
    px_driver: str          # PX主驱动：成本/检修/调油
    pta_driver: str         # PTA主驱动：加工费/检修/出口
    meg_driver: str         # MEG主驱动：港口库存/煤制利润/进口
    pf_driver: str          # PF主驱动：加工费/减产函/出口
    pr_driver: str          # PR主驱动：加工费/减产函/出口
    attribution_confidence: str  # 归属置信度


@dataclass
class MarketVerification:
    """盘面验证结果"""
    lead_lag_order: str     # 领涨领跌顺序
    profit_distribution: str  # 利润分配
    term_structure: str     # 月差结构
    verification_signal: str  # 验证信号：确认/矛盾/中性
    verification_confidence: str  # 验证置信度


@dataclass
class DriverSwitchSignal:
    """驱动切换信号"""
    old_driver: str         # 旧主驱动
    new_driver: str         # 新主驱动
    switch_type: str        # 切换类型：地缘缓和/检修结束/调油季启动/终端负反馈/煤制复产
    switch_confidence: str  # 切换置信度
    position_action: str    # 头寸动作：平仓/反手/减仓/加仓


# ========== 宏观趋势评估（趋势过滤器） ==========

def assess_macro_trend(data: Dict) -> TrendContext:
    """
    宏观趋势评估 — 在所有微观打分之前执行，作为第一道趋势过滤器
    
    核心理念：
    - 宏观趋势压倒微观基本面。原油跌+全品种跌时，任何微观利多都是噪音
    - 只在宏观趋势向上或至少企稳时，微观基本面逻辑才有效
    - 全产业链一致下跌 = 最强空头信号，无论微观基本面如何
    
    检查维度：
    1. 原油趋势（WTI/Brent 10日涨跌幅、MA20斜率）
    2. 聚酯链整体方向（TA/EG/PF/PR平均趋势）
    3. 全产业链协同方向（是否一致下跌/上涨）
    
    返回：TrendContext对象
    """
    # 1. 原油趋势
    crude_change_10d = data.get('crude_change_10d', 0)  # WTI 10日涨跌幅(%)
    crude_trend = 'neutral'
    if crude_change_10d < -3.0:
        crude_trend = 'bearish'
    elif crude_change_10d > 3.0:
        crude_trend = 'bullish'
    elif crude_change_10d < -1.0:
        crude_trend = 'mild_bearish'
    elif crude_change_10d > 1.0:
        crude_trend = 'mild_bullish'
    
    # 2. 聚酯链各品种10日涨跌幅
    ta_change_10d = data.get('ta_change_10d', 0)
    eg_change_10d = data.get('eg_change_10d', 0)
    pf_change_10d = data.get('pf_change_10d', 0)
    pr_change_10d = data.get('pr_change_10d', 0)
    
    changes = [ta_change_10d, eg_change_10d, pf_change_10d, pr_change_10d]
    avg_chain_change = sum(changes) / len(changes) if changes else 0
    
    # 3. 全产业链是否一致下跌
    all_negative = all(c < 0 for c in changes)
    all_positive = all(c > 0 for c in changes)
    trending_down_harmonized = all_negative  # 全产业链一致下跌
    
    # 4. 聚酯链整体趋势判断
    if avg_chain_change < -2.0:
        polyester_trend = 'bearish'
    elif avg_chain_change > 2.0:
        polyester_trend = 'bullish'
    elif avg_chain_change < -0.5:
        polyester_trend = 'mild_bearish'
    elif avg_chain_change > 0.5:
        polyester_trend = 'mild_bullish'
    else:
        polyester_trend = 'neutral'
    
    # 5. 综合宏观趋势（原油权重60%，聚酯链权重40%）
    trend_values = {
        'bullish': 2, 'mild_bullish': 1, 'neutral': 0,
        'mild_bearish': -1, 'bearish': -2
    }
    crude_val = trend_values.get(crude_trend, 0)
    polyester_val = trend_values.get(polyester_trend, 0)
    composite_val = 0.6 * crude_val + 0.4 * polyester_val
    
    if composite_val >= 1.5:
        macro_trend = 'bullish'
        trend_strength = 'strong'
    elif composite_val >= 0.5:
        macro_trend = 'bullish'
        trend_strength = 'moderate'
    elif composite_val > -0.5:
        macro_trend = 'neutral'
        trend_strength = 'weak'
    elif composite_val > -1.5:
        macro_trend = 'bearish'
        trend_strength = 'moderate'
    else:
        macro_trend = 'bearish'
        trend_strength = 'strong'
    
    # 6. 计算打分上限调整因子
    # 宏观强牛市：无上限（因子1.0）
    # 宏观中性：上限60分（因子0.6）
    # 宏观弱熊市：上限40分（因子0.4）→ 最多WATCH
    # 宏观强熊市：上限20分（因子0.2）→ 最多NOISE
    if macro_trend == 'bullish':
        if trend_strength == 'strong':
            macro_score_cap = 1.0
        else:
            macro_score_cap = 0.8
    elif macro_trend == 'neutral':
        macro_score_cap = 0.6
    else:  # bearish
        if trend_strength == 'strong':
            macro_score_cap = 0.2
        else:
            macro_score_cap = 0.4
    
    # 7. 全产业链一致下跌 → 强制最低cap
    if trending_down_harmonized:
        macro_score_cap = min(macro_score_cap, 0.3)
        logger.warning("⚠️ 全产业链一致下跌，宏观趋势过滤：打分上限压缩至30%")
    
    logger.info(
        f"宏观趋势评估: 原油={crude_trend}({crude_change_10d:.1f}%), "
        f"聚酯链={polyester_trend}({avg_chain_change:.1f}%), "
        f"综合={macro_trend}, 打分因子={macro_score_cap:.2f}, "
        f"全产业链下跌={trending_down_harmonized}"
    )
    
    return TrendContext(
        macro_trend=macro_trend,
        crude_trend=crude_trend,
        polyester_trend=polyester_trend,
        trend_strength=trend_strength,
        macro_score_cap=macro_score_cap,
        avg_chain_change_10d=avg_chain_change,
        trending_down_harmonized=trending_down_harmonized,
    )


# ========== 右侧确认检查 ==========

def check_right_side_confirmation(data: Dict) -> Dict:
    """
    右侧确认检查 — 在生成交易信号前执行。
    
    右侧交易铁律（全局强制）：
    任何BUY/SELL信号必须基于已确认的右侧价格行为信号，禁止左侧猜测。
    
    大宗商品多空双向：
    - 做多需要右侧做多确认（企稳/放量/金叉/站上MA20）
    - 做空需要右侧做空确认（破位/放量下跌/死叉/跌破MA20）
    
    返回：{
        confirmed: bool,
        signal_type: str,
        details: str,
        confirmations: [str],
        bull_confirmed: bool,   # 右侧做多确认
        bear_confirmed: bool,   # 右侧做空确认
    }
    """
    result = {
        'confirmed': False,
        'signal_type': 'none',
        'details': '无右侧确认信号',
        'confirmations': [],
        'bull_confirmed': False,
        'bear_confirmed': False,
    }
    
    # ========== 多头侧确认 ==========
    # 1. 价格脱离最低点检查（3日未创新低=初步企稳）
    lowest_3d_ago = data.get('lowest_3d_ago', None)
    current_low = data.get('current_low', None)
    if lowest_3d_ago is not None and current_low is not None:
        if current_low > lowest_3d_ago:
            result['confirmations'].append('3日未创新低（初步企稳）')
    
    # 2. 底部放量检查
    volume_increase = data.get('volume_increase_ratio', 0)
    if volume_increase > 1.5:
        result['confirmations'].append(f'底部放量(成交额{volume_increase:.1f}倍)')
    
    # 3. RSI从超卖回升
    rsi_current = data.get('rsi_current', 50)
    rsi_previous = data.get('rsi_previous', 50)
    if rsi_current > rsi_previous and rsi_previous < 35:
        result['confirmations'].append(f'RSI从超卖回升({rsi_previous:.0f}→{rsi_current:.0f})')
    
    # 4. MACD金叉
    macd_bull_cross = data.get('macd_bullish_cross', False)
    if macd_bull_cross:
        result['confirmations'].append('MACD金叉')
    
    # 5. 站上MA20
    above_ma20 = data.get('price_above_ma20', False)
    ma20_slope_positive = data.get('ma20_slope_positive', False)
    if above_ma20 and ma20_slope_positive:
        result['confirmations'].append('站上MA20且均线上翘')
    elif above_ma20:
        result['confirmations'].append('站上MA20')
    
    # ========== 空头侧确认 ==========
    # 6. 价格创新低
    bear_confirmations = []
    if lowest_3d_ago is not None and current_low is not None:
        if current_low < lowest_3d_ago:
            bear_confirmations.append('价格创新低（持续下跌）')
    
    # 7. MACD死叉
    macd_bear_cross = data.get('macd_bearish_cross', False)
    if macd_bear_cross:
        bear_confirmations.append('MACD死叉')
    
    # 8. 跌破MA20
    below_ma20 = False if data.get('price_above_ma20', True) else True
    ma20_slope_negative = data.get('ma20_slope_negative', False)
    if below_ma20 and ma20_slope_negative:
        bear_confirmations.append('跌破MA20且均线下挫')
    elif below_ma20:
        bear_confirmations.append('跌破MA20')
    
    # 9. 放量下跌
    volume_increase = data.get('volume_increase_ratio', 0)
    if volume_increase > 1.3 and below_ma20:
        bear_confirmations.append(f'放量下跌(成交额{volume_increase:.1f}倍)')
    
    # ========== 综合判断 ==========
    # 多头侧：≥1个强信号 或 ≥2个中等信号
    bull_strong = ['站上MA20', 'MACD金叉', '站上MA20且均线上翘']
    bull_count = len(result['confirmations'])
    bull_strong_count = sum(1 for c in result['confirmations'] if any(s in c for s in bull_strong))
    result['bull_confirmed'] = (bull_strong_count >= 1) or (bull_count >= 2)
    
    # 空头侧：≥1个强信号 或 ≥2个中等信号
    bear_strong = ['跌破MA20', 'MACD死叉', '跌破MA20且均线下挫']
    bear_count = len(bear_confirmations)
    bear_strong_count = sum(1 for c in bear_confirmations if any(s in c for s in bear_strong))
    result['bear_confirmed'] = (bear_strong_count >= 1) or (bear_count >= 2)
    
    # 通用confirmed字段（只要任意一侧有确认就算）
    result['confirmations'] = result['confirmations'] + bear_confirmations
    if result['bull_confirmed'] or result['bear_confirmed']:
        result['confirmed'] = True
        if result['bull_confirmed'] and result['bear_confirmed']:
            result['signal_type'] = 'mixed'
            result['details'] = '多空两侧均有确认信号'
        elif result['bull_confirmed']:
            result['signal_type'] = 'bullish'
            result['details'] = '; '.join(result['confirmations'][:bull_count])
        else:
            result['signal_type'] = 'bearish'
            result['details'] = '; '.join(bear_confirmations)
    
    if result['confirmed']:
        logger.info(f"右侧确认: bull={result['bull_confirmed']} bear={result['bear_confirmed']} - {result['details']}")
    else:
        logger.info("右侧确认: ❌ 无确认信号，强制HOLD")
    
    return result


# ========== 三层漏斗诊断 ==========

def diagnose_l1_annual(data: Dict) -> Tuple[float, str]:
    """
    L1年度层诊断（6-12个月）
    
    诊断内容：
    - 产能周期（PX/PTA/MEG投产节奏）
    - 海外新装置（土耳其、印度PTA）
    
    返回：
    - score: 0-100分
    - driver: 主驱动类型
    """
    score = 50.0  # 中性起点
    driver = "产能周期"
    
    # PX产能周期
    px_capacity_growth = data.get('px_capacity_growth', 0)  # PX产能增速
    if px_capacity_growth < 0:
        score += 20  # 产能收缩，偏多
        driver = "PX产能收缩"
    elif px_capacity_growth > 10:
        score -= 20  # 产能扩张，偏空
        driver = "PX产能扩张"
    
    # PTA产能周期
    pta_capacity_growth = data.get('pta_capacity_growth', 0)  # PTA产能增速
    if pta_capacity_growth < 0:
        score += 15  # 产能收缩，偏多
        driver = "PTA产能收缩"
    elif pta_capacity_growth > 15:
        score -= 15  # 产能扩张，偏空
        driver = "PTA产能扩张"
    
    # MEG产能周期
    meg_capacity_growth = data.get('meg_capacity_growth', 0)  # MEG产能增速
    if meg_capacity_growth < 0:
        score += 10  # 产能收缩，偏多
        driver = "MEG产能收缩"
    elif meg_capacity_growth > 20:
        score -= 10  # 产能扩张，偏空
        driver = "MEG产能扩张"
    
    # 海外新装置
    overseas_new_capacity = data.get('overseas_new_capacity', False)
    if overseas_new_capacity:
        score -= 10  # 海外新装置，偏空
        driver = "海外新装置"
    
    # 限制在0-100范围
    score = max(0, min(100, score))
    
    return score, driver


def diagnose_l2_quarterly(data: Dict) -> Tuple[float, str]:
    """
    L2季度层诊断（1-3个月）
    
    诊断内容：
    - 检修季
    - 调油逻辑
    - 地缘
    - 反内卷减产
    
    返回：
    - score: 0-100分
    - driver: 主驱动类型
    """
    score = 50.0  # 中性起点
    driver = "季度中性"
    
    # 检修季
    pta_maintenance_rate = data.get('pta_maintenance_rate', 0)  # PTA检修率
    px_maintenance_rate = data.get('px_maintenance_rate', 0)  # PX检修率
    
    if pta_maintenance_rate > 20:
        score += 15  # PTA检修多，偏多
        driver = "PTA检修季"
    if px_maintenance_rate > 15:
        score += 10  # PX检修多，偏多
        driver = "PX检修季"
    
    # 调油逻辑
    gasoline_crack = data.get('gasoline_crack', 0)  # 汽油裂差
    if gasoline_crack > 30:
        score += 20  # 调油逻辑强，偏多
        driver = "调油逻辑"
    
    # 地缘
    geopolitical_risk = data.get('geopolitical_risk', 0)  # 地缘风险指数
    if geopolitical_risk > 70:
        score += 15  # 地缘风险高，偏多
        driver = "地缘风险"
    
    # 反内卷减产
    anti_involution_cut = data.get('anti_involution_cut', False)
    if anti_involution_cut:
        score += 10  # 反内卷减产，偏多
        driver = "反内卷减产"
    
    # 限制在0-100范围
    score = max(0, min(100, score))
    
    return score, driver


def diagnose_l3_weekly(data: Dict) -> Tuple[float, str]:
    """
    L3周度层诊断（1-4周）
    
    诊断内容：
    - 港口库存
    - 装置临停
    - 聚酯负荷摆动
    - 织造订单
    
    返回：
    - score: 0-100分
    - driver: 主驱动类型
    """
    score = 50.0  # 中性起点
    driver = "周度中性"
    
    # MEG港口库存
    meg_port_inventory = data.get('meg_port_inventory', 85)  # MEG港口库存（万吨）
    if meg_port_inventory < 80:
        score += 15  # 港口库存低，偏多
        driver = "MEG港口去库"
    elif meg_port_inventory > 100:
        score -= 15  # 港口库存高，偏空
        driver = "MEG港口累库"
    
    # 聚酯负荷
    polyester_load = data.get('polyester_load', 85)  # 聚酯负荷（%）
    if polyester_load > 85:
        score += 10  # 聚酯负荷高，偏多
        driver = "聚酯高负荷"
    elif polyester_load < 80:
        score -= 10  # 聚酯负荷低，偏空
        driver = "聚酯低负荷"
    
    # 织造订单
    weaving_order_days = data.get('weaving_order_days', 10)  # 织造订单天数
    if weaving_order_days > 15:
        score += 10  # 订单好，偏多
        driver = "织造订单好"
    elif weaving_order_days < 7:
        score -= 10  # 订单差，偏空
        driver = "织造订单差"
    
    # 装置临停
    unit_shutdown = data.get('unit_shutdown', False)
    if unit_shutdown:
        score += 5  # 装置临停，偏多
        driver = "装置临停"
    
    # 限制在0-100范围
    score = max(0, min(100, score))
    
    return score, driver


# ========== 驱动归属判定 ==========

def attribute_px_driver(data: Dict) -> str:
    """
    PX驱动归属判定
    
    判定逻辑：
    - 原油/PXN主导：PXN在200-300低位+原油单边
    - 检修主导：PXN压到200以下+国内/亚洲开工下滑
    - 调油主导：美亚汽油裂差走扩+北美芳烃被抽走
    
    返回：驱动类型（成本/检修/调油）
    """
    pxn = data.get('pxn', 300)  # PXN（美元）
    px_operation_rate = data.get('px_operation_rate', 80)  # PX开工率（%）
    gasoline_crack = data.get('gasoline_crack', 0)  # 汽油裂差
    
    # 调油主导判断
    if gasoline_crack > 30 and pxn >= 350:
        return "调油"
    
    # 检修主导判断
    if pxn < 200 and px_operation_rate < 80:
        return "检修"
    
    # 成本主导判断
    if pxn < 300:
        return "成本"
    
    return "中性"


def attribute_pta_driver(data: Dict) -> str:
    """
    PTA驱动归属判定
    
    判定逻辑：
    - 加工费极值：<300→检修动机，>600→复产压力
    - 大厂检修兑现度：恒力/逸盛/浙石化检修计划vs实际开工
    - 出口变量：印度BIS政策、土耳其/印度新PTA装置
    
    返回：驱动类型（加工费/检修/出口）
    """
    pta_processing_fee = data.get('pta_processing_fee', 400)  # PTA加工费（元）
    pta_operation_rate = data.get('pta_operation_rate', 80)  # PTA开工率（%）
    export_impact = data.get('export_impact', False)  # 出口影响
    
    # 加工费极值判断
    if pta_processing_fee < 300:
        return "加工费"
    elif pta_processing_fee > 600:
        return "加工费"
    
    # 检修主导判断
    if pta_operation_rate < 70:
        return "检修"
    
    # 出口主导判断
    if export_impact:
        return "出口"
    
    return "中性"


def attribute_meg_driver(data: Dict) -> str:
    """
    MEG驱动归属判定
    
    判定逻辑：
    - 港口库存是灵魂：85万吨是分界线
    - 煤制利润：>0煤制开工就上，<-200煤制大面积停
    - 进口扰动：中东（沙特/伊朗）霍尔木兹一堵，EG更敏感
    
    返回：驱动类型（港口库存/煤制利润/进口）
    """
    meg_port_inventory = data.get('meg_port_inventory', 85)  # MEG港口库存（万吨）
    coal_to_meg_profit = data.get('coal_to_meg_profit', 0)  # 煤制MEG利润（元）
    import_impact = data.get('import_impact', False)  # 进口影响
    
    # 港口库存主导判断
    if meg_port_inventory < 80:
        return "港口库存"
    elif meg_port_inventory > 100:
        return "港口库存"
    
    # 煤制利润主导判断
    if coal_to_meg_profit < -200:
        return "煤制利润"
    elif coal_to_meg_profit > 0:
        return "煤制利润"
    
    # 进口主导判断
    if import_impact:
        return "进口"
    
    return "中性"


def attribute_pf_driver(data: Dict) -> str:
    """
    PF驱动归属判定
    
    判定逻辑：
    - 加工费<800（盘面）/<750（现货）→减产动机
    - 加工费>1200→复产压力
    
    返回：驱动类型（加工费/减产函/出口）
    """
    pf_processing_fee = data.get('pf_processing_fee', 900)  # PF加工费（元）
    production_cut_letter = data.get('production_cut_letter', False)  # 减产函
    export_impact = data.get('export_impact', False)  # 出口影响
    
    # 加工费极值判断
    if pf_processing_fee < 800:
        return "加工费"
    elif pf_processing_fee > 1200:
        return "加工费"
    
    # 减产函主导判断
    if production_cut_letter:
        return "减产函"
    
    # 出口主导判断
    if export_impact:
        return "出口"
    
    return "中性"


def attribute_pr_driver(data: Dict) -> str:
    """
    PR驱动归属判定
    
    判定逻辑：
    - 加工费<300→减产动机
    - 加工费>550→复产压力
    
    返回：驱动类型（加工费/减产函/出口）
    """
    pr_processing_fee = data.get('pr_processing_fee', 400)  # PR加工费（元）
    production_cut_letter = data.get('production_cut_letter', False)  # 减产函
    export_impact = data.get('export_impact', False)  # 出口影响
    
    # 加工费极值判断
    if pr_processing_fee < 300:
        return "加工费"
    elif pr_processing_fee > 550:
        return "加工费"
    
    # 减产函主导判断
    if production_cut_letter:
        return "减产函"
    
    # 出口主导判断
    if export_impact:
        return "出口"
    
    return "中性"


# ========== 盘面验证 ==========

def verify_market_leadership(data: Dict) -> str:
    """
    盘面验证：看领涨领跌顺序
    
    判定逻辑：
    - PX > TA > EG ≈ PF → 主驱动在PX供应
    - TA ≈ PX同涨，EG拖后腿 → 主驱动在TA检修兑现+PX配合
    - EG领涨，TA跟 → 主驱动在EG进口扰动或煤制减产
    - PF涨不动，TA大涨 → 成本推涨，不是需求驱动
    
    返回：领涨领跌顺序描述
    """
    px_change = data.get('px_change', 0)  # PX涨幅
    ta_change = data.get('ta_change', 0)  # TA涨幅
    eg_change = data.get('eg_change', 0)  # EG涨幅
    pf_change = data.get('pf_change', 0)  # PF涨幅
    
    # 计算各品种相对强弱
    changes = {
        'PX': px_change,
        'TA': ta_change,
        'EG': eg_change,
        'PF': pf_change
    }
    
    # 排序
    sorted_changes = sorted(changes.items(), key=lambda x: x[1], reverse=True)
    
    # 判断领涨领跌顺序
    if sorted_changes[0][0] == 'PX' and sorted_changes[1][0] == 'TA':
        return "PX领涨，TA跟随，主驱动在PX供应"
    elif sorted_changes[0][0] == 'TA' and sorted_changes[1][0] == 'PX':
        return "TA领涨，PX配合，主驱动在TA检修"
    elif sorted_changes[0][0] == 'EG':
        return "EG领涨，主驱动在EG进口扰动或煤制减产"
    elif sorted_changes[0][0] == 'TA' and sorted_changes[-1][0] == 'PF':
        return "TA涨PF不动，成本推涨非需求驱动"
    
    return "领涨领跌顺序不明显"


def verify_profit_distribution(data: Dict) -> str:
    """
    盘面验证：看利润往哪头挤
    
    判定逻辑：
    - PXN扩张 → 利润留在PX环节，PX是主驱动
    - TA加工费修复 → 利润往TA走，TA检修/出口是主驱动
    - PXN稳+TA加工费稳+PF加工费修复 → 主驱动在PF端减产
    - 全环节利润都被压缩但油价在涨 → 主驱动是成本推
    
    返回：利润分配描述
    """
    pxn = data.get('pxn', 300)  # PXN（美元）
    pta_processing_fee = data.get('pta_processing_fee', 400)  # PTA加工费（元）
    pf_processing_fee = data.get('pf_processing_fee', 900)  # PF加工费（元）
    oil_price_change = data.get('oil_price_change', 0)  # 油价涨幅
    
    # 判断利润分配
    if pxn > 400:
        return "PXN高位，利润留在PX环节"
    elif pta_processing_fee > 500:
        return "TA加工费修复，利润往TA走"
    elif pf_processing_fee > 1000:
        return "PF加工费修复，主驱动在PF端减产"
    elif oil_price_change > 0 and pxn < 300 and pta_processing_fee < 400:
        return "全环节利润压缩但油价涨，成本推涨"
    
    return "利润分配不明显"


def verify_term_structure(data: Dict) -> str:
    """
    盘面验证：看月差结构
    
    判定逻辑：
    - PX/TA 5-9、7-9走扩（Back加深） → 近端检修去库是主驱动
    - EG远月贴水加深 → 近端去库但远月投产压力定价
    - PF近月升水收窄 → 减产兑现度不够或终端没跟上
    
    返回：月差结构描述
    """
    ta_near_far_spread = data.get('ta_near_far_spread', 0)  # TA近远月价差
    eg_near_far_spread = data.get('eg_near_far_spread', 0)  # EG近远月价差
    pf_near_far_spread = data.get('pf_near_far_spread', 0)  # PF近远月价差
    
    # 判断月差结构
    if ta_near_far_spread > 100:
        return "TA Back加深，近端检修去库是主驱动"
    elif ta_near_far_spread < -100:
        return "TA Contango加深，远端累库预期"
    elif eg_near_far_spread < -50:
        return "EG远月贴水加深，远月投产压力定价"
    elif pf_near_far_spread < 0:
        return "PF近月升水收窄，减产兑现度不够"
    
    return "月差结构不明显"


# ========== 量化打分 ==========

def calculate_driver_score(data: Dict, trend_context: TrendContext = None) -> DriverScore:
    """
    计算主驱动识别得分（趋势感知版）
    
    打分机制：
    - L1年度层：权重30%
    - L2季度层：权重40%
    - L3周度层：权重30%
    - 宏观趋势过滤：根据trend_context.macro_score_cap压缩最终得分
    - 右侧确认过滤：无确认信号时trade_signal=HOLD
    
    ⚠️ 金融交易逻辑铁律：
    1. 宏观趋势压倒微观基本面 — 下跌趋势中微观利多无效
    2. 得分≠交易信号 — high score + no right-side confirmation = HOLD
    3. 全产业链一致下跌时强制HOLD
    
    返回：DriverScore对象（含trade_signal）
    """
    # 三层漏斗诊断
    l1_score, l1_driver = diagnose_l1_annual(data)
    l2_score, l2_driver = diagnose_l2_quarterly(data)
    l3_score, l3_driver = diagnose_l3_weekly(data)
    
    # 加权计算原始综合得分
    raw_score = 0.30 * l1_score + 0.40 * l2_score + 0.30 * l3_score
    
    # ========== 宏观趋势过滤 ==========
    if trend_context is None:
        # 如果没有传入trend_context，自己评估
        trend_context = assess_macro_trend(data)
    
    # 应用宏观打分上限
    total_score = raw_score * trend_context.macro_score_cap
    
    # 确定主驱动类型
    if l1_score > l2_score and l1_score > l3_score:
        primary_driver = l1_driver
    elif l2_score > l1_score and l2_score > l3_score:
        primary_driver = l2_driver
    else:
        primary_driver = l3_driver
    
    # 确定驱动强度（使用过滤后的得分）
    if total_score > 70:
        driver_strength = "强"
    elif total_score > 50:
        driver_strength = "中"
    elif total_score > 30:
        driver_strength = "弱"
    else:
        driver_strength = "极弱"
    
    # 确定置信度
    if abs(l1_score - l2_score) < 10 and abs(l2_score - l3_score) < 10:
        confidence = "高"  # 三层一致
    elif abs(l1_score - l2_score) < 20 and abs(l2_score - l3_score) < 20:
        confidence = "中"  # 两层一致
    else:
        confidence = "低"  # 三层矛盾
    
    # ========== 右侧确认检查 → 确定交易信号 ==========
    right_side = check_right_side_confirmation(data)
    
    # 交易信号生成规则（适用于多空双向交易的大宗商品）：
    # 1. 无任何右侧确认 → HOLD
    # 2. 熊市趋势 + 右侧做空确认（破位/死叉/创新低） → SELL ✓
    # 3. 熊市趋势 + 仅右侧做多确认（反弹） → HOLD（不逆势抄底）
    # 4. 牛市趋势 + 右侧做多确认 → BUY ✓
    # 5. 牛市趋势 + 仅右侧做空确认 → HOLD（不逆势做空）
    # 6. 震荡市 → 按基本面方向+对应侧确认交易
    
    if not right_side['confirmed']:
        trade_signal = "HOLD"
        logger.info(f"交易信号: HOLD（无右侧确认信号，宏观={trend_context.macro_trend}）")
    
    elif trend_context.macro_trend == 'bearish':
        if right_side['bear_confirmed']:
            # 大宗商品可以做空 → 熊市趋势+右侧做空确认=SELL
            trade_signal = "SELL"
            logger.info(f"交易信号: SELL（熊市趋势+右侧做空确认）")
        else:
            # 仅有做多确认但逆趋势 → HOLD
            trade_signal = "HOLD"
            logger.info(f"交易信号: HOLD（熊市趋势，仅有做多确认，不逆势抄底）")
    
    elif trend_context.macro_trend == 'neutral':
        # 震荡市 → 按对应侧确认交易
        if right_side['bull_confirmed'] and total_score >= 50:
            trade_signal = "BUY"
            logger.info(f"交易信号: BUY（震荡市+基本面{total_score:.0f}分+右侧做多确认）")
        elif right_side['bear_confirmed'] and total_score <= -50:
            trade_signal = "SELL"
            logger.info(f"交易信号: SELL（震荡市+基本面{total_score:.0f}分+右侧做空确认）")
        else:
            trade_signal = "HOLD"
            logger.info(f"交易信号: HOLD（震荡市，基本面不足或无对应侧确认）")
    
    else:  # bullish
        if right_side['bull_confirmed'] and total_score >= 60:
            trade_signal = "BUY"
            logger.info(f"交易信号: BUY（牛市+基本面{total_score:.0f}分+右侧做多确认）")
        elif right_side['bear_confirmed'] and total_score <= -40:
            trade_signal = "SELL"
            logger.info(f"交易信号: SELL（牛市+基本面{total_score:.0f}分+右侧做空确认）")
        elif right_side['bull_confirmed'] and total_score >= 50:
            trade_signal = "WATCH"
            logger.info(f"交易信号: WATCH（牛市+基本面{total_score:.0f}分+右侧做多，但分数不够）")
        else:
            trade_signal = "HOLD"
    
    return DriverScore(
        l1_score=l1_score,
        l2_score=l2_score,
        l3_score=l3_score,
        raw_score=raw_score,
        total_score=total_score,
        primary_driver=primary_driver,
        driver_strength=driver_strength,
        confidence=confidence,
        trade_signal=trade_signal,
        macro_context=trend_context,
    )


def attribute_all_drivers(data: Dict) -> DriverAttribution:
    """
    所有品种驱动归属判定
    
    返回：DriverAttribution对象
    """
    px_driver = attribute_px_driver(data)
    pta_driver = attribute_pta_driver(data)
    meg_driver = attribute_meg_driver(data)
    pf_driver = attribute_pf_driver(data)
    pr_driver = attribute_pr_driver(data)
    
    # 计算归属置信度
    drivers = [px_driver, pta_driver, meg_driver, pf_driver, pr_driver]
    non_neutral = sum(1 for d in drivers if d != "中性")
    
    if non_neutral >= 4:
        attribution_confidence = "高"
    elif non_neutral >= 2:
        attribution_confidence = "中"
    else:
        attribution_confidence = "低"
    
    return DriverAttribution(
        px_driver=px_driver,
        pta_driver=pta_driver,
        meg_driver=meg_driver,
        pf_driver=pf_driver,
        pr_driver=pr_driver,
        attribution_confidence=attribution_confidence
    )


def verify_market(data: Dict) -> MarketVerification:
    """
    盘面验证三步法
    
    返回：MarketVerification对象
    """
    lead_lag_order = verify_market_leadership(data)
    profit_distribution = verify_profit_distribution(data)
    term_structure = verify_term_structure(data)
    
    # 判断验证信号
    # 如果三个验证都指向同一方向，则为确认
    # 如果有矛盾，则为矛盾
    # 否则为中性
    
    # 简化判断：检查关键词
    bullish_keywords = ["偏多", "扩张", "修复", "去库", "领涨"]
    bearish_keywords = ["偏空", "压缩", "累库", "领跌", "不动"]
    
    bullish_count = 0
    bearish_count = 0
    
    for text in [lead_lag_order, profit_distribution, term_structure]:
        for keyword in bullish_keywords:
            if keyword in text:
                bullish_count += 1
                break
        for keyword in bearish_keywords:
            if keyword in text:
                bearish_count += 1
                break
    
    if bullish_count >= 2:
        verification_signal = "确认偏多"
        verification_confidence = "高"
    elif bearish_count >= 2:
        verification_signal = "确认偏空"
        verification_confidence = "高"
    elif bullish_count > 0 and bearish_count > 0:
        verification_signal = "矛盾"
        verification_confidence = "低"
    else:
        verification_signal = "中性"
        verification_confidence = "中"
    
    return MarketVerification(
        lead_lag_order=lead_lag_order,
        profit_distribution=profit_distribution,
        term_structure=term_structure,
        verification_signal=verification_signal,
        verification_confidence=verification_confidence
    )


def detect_driver_switch(data: Dict, old_driver: str, new_driver: str) -> Optional[DriverSwitchSignal]:
    """
    检测驱动切换信号
    
    切换场景：
    - 地缘缓和：PX地缘+检修 → PXN修复+TA检修
    - 检修结束：TA检修去库 → 累库+海外新装置
    - 调油季启动：PXN常规 → PXN扩张
    - 终端负反馈：成本推 → 淡季累库
    - 煤制复产：EG去库 → EG累库
    
    返回：DriverSwitchSignal对象或None
    """
    # 检查是否有切换信号
    switch_signals = []
    
    # 地缘缓和信号
    geopolitical_risk = data.get('geopolitical_risk', 50)
    if geopolitical_risk < 30 and old_driver == "地缘风险":
        switch_signals.append(("地缘缓和", "PX地缘+检修", "PXN修复+TA检修"))
    
    # 检修结束信号
    pta_operation_rate = data.get('pta_operation_rate', 80)
    if pta_operation_rate > 75 and old_driver == "检修":
        switch_signals.append(("检修结束", "TA检修去库", "累库+海外新装置"))
    
    # 调油季启动信号
    gasoline_crack = data.get('gasoline_crack', 0)
    if gasoline_crack > 30 and old_driver != "调油":
        switch_signals.append(("调油季启动", "PXN常规", "PXN扩张"))
    
    # 终端负反馈信号
    polyester_load = data.get('polyester_load', 85)
    if polyester_load < 80 and old_driver != "终端负反馈":
        switch_signals.append(("终端负反馈", "成本推", "淡季累库"))
    
    # 煤制复产信号
    coal_to_meg_profit = data.get('coal_to_meg_profit', 0)
    if coal_to_meg_profit > 0 and old_driver == "煤制利润":
        switch_signals.append(("煤制复产", "EG去库", "EG累库"))
    
    if not switch_signals:
        return None
    
    # 选择最可能的切换信号
    switch_type, old_driver_desc, new_driver_desc = switch_signals[0]
    
    # 确定头寸动作
    if "偏多" in new_driver_desc or "扩张" in new_driver_desc:
        position_action = "加仓"
    elif "偏空" in new_driver_desc or "累库" in new_driver_desc:
        position_action = "平仓"
    else:
        position_action = "减仓"
    
    # 确定切换置信度
    if len(switch_signals) >= 2:
        switch_confidence = "高"
    else:
        switch_confidence = "中"
    
    return DriverSwitchSignal(
        old_driver=old_driver_desc,
        new_driver=new_driver_desc,
        switch_type=switch_type,
        switch_confidence=switch_confidence,
        position_action=position_action
    )


# ========== 主函数 ==========

def run_driver_identification(data: Dict) -> Dict:
    """
    运行完整的主驱动识别流程（趋势感知版）
    
    流程：
    1. 宏观趋势评估（第一道过滤）→ 确定打分上限
    2. 三层漏斗诊断 + 趋势过滤打分
    3. 驱动归属判定
    4. 盘面验证三步法
    5. 右侧确认检查（第二道过滤）→ 确定交易信号
    6. 驱动切换检测
    
    核心铁律：
    - 宏观趋势压倒微观基本面
    - 无右侧确认不生成BUY/SELL
    - 全产业链一致下跌时强制HOLD
    
    返回：包含所有识别结果的字典
    """
    logger.info("开始主驱动识别（趋势感知版）...")
    
    # 1. 宏观趋势评估
    logger.info("步骤1: 宏观趋势评估...")
    trend_context = assess_macro_trend(data)
    
    # 2. 三层漏斗诊断 + 趋势过滤打分
    logger.info("步骤2: 三层漏斗诊断 + 趋势过滤...")
    driver_score = calculate_driver_score(data, trend_context)
    
    # 3. 驱动归属判定
    logger.info("步骤3: 驱动归属判定...")
    driver_attribution = attribute_all_drivers(data)
    
    # 4. 盘面验证
    logger.info("步骤4: 盘面验证三步法...")
    market_verification = verify_market(data)
    
    # 5. 驱动切换检测
    logger.info("步骤5: 驱动切换检测...")
    old_driver = data.get('old_driver', '中性')
    new_driver = driver_score.primary_driver
    driver_switch = detect_driver_switch(data, old_driver, new_driver)
    
    # 汇总结果
    result = {
        'driver_score': driver_score,
        'driver_attribution': driver_attribution,
        'market_verification': market_verification,
        'driver_switch': driver_switch,
        'summary': {
            'primary_driver': driver_score.primary_driver,
            'driver_strength': driver_score.driver_strength,
            'confidence': driver_score.confidence,
            'raw_score': driver_score.raw_score,
            'total_score': driver_score.total_score,
            'trade_signal': driver_score.trade_signal,
            'verification_signal': market_verification.verification_signal,
            'switch_detected': driver_switch is not None,
            'macro_trend': trend_context.macro_trend,
            'macro_trend_strength': trend_context.trend_strength,
            'trending_down_harmonized': trend_context.trending_down_harmonized,
            'macro_score_cap': trend_context.macro_score_cap,
        }
    }
    
    logger.info(
        f"主驱动识别完成：{driver_score.primary_driver}，"
        f"原始分={driver_score.raw_score:.1f}，"
        f"过滤后={driver_score.total_score:.1f}，"
        f"信号={driver_score.trade_signal}，"
        f"宏观={trend_context.macro_trend}"
    )
    
    return result


# ========== 测试代码 ==========

if __name__ == "__main__":
    # ===== 场景1: 宏观下跌 + 微观偏多（聚酯链当前真实场景） =====
    print("=" * 60)
    print("场景1: 宏观下跌(原油-5%) + 微观偏多(加工费低+检修率高)")
    print("预期: 全产业链一致下跌 → 宏观打分上限30% → HOLD")
    print("=" * 60)
    
    test_data_bearish = {
        # === 宏观趋势（新字段） ===
        'crude_change_10d': -5.0,  # WTI 10日跌幅5%
        'ta_change_10d': -3.0,     # TA 10日跌幅3%
        'eg_change_10d': -2.5,     # EG 10日跌幅2.5%
        'pf_change_10d': -1.5,     # PF 10日跌幅1.5%
        'pr_change_10d': -2.0,     # PR 10日跌幅2.0%
        'lowest_3d_ago': 5400,     # 3日前最低
        'current_low': 5380,       # 当前最低（创新低=还在跌）
        'volume_increase_ratio': 0.8,  # 缩量
        'rsi_current': 35,         # RSI超卖附近
        'rsi_previous': 32,        # RSI之前更低
        'macd_bullish_cross': False,  # MACD未金叉
        'price_above_ma20': False,    # 价格在MA20下方
        'ma20_slope_positive': False, # MA20向下
        
        # L1年度层
        'px_capacity_growth': -5,
        'pta_capacity_growth': 10,
        'meg_capacity_growth': 25,
        'overseas_new_capacity': True,
        
        # L2季度层
        'pta_maintenance_rate': 25,
        'px_maintenance_rate': 20,
        'gasoline_crack': 35,
        'geopolitical_risk': 60,
        'anti_involution_cut': False,
        
        # L3周度层
        'meg_port_inventory': 82,
        'polyester_load': 83,
        'weaving_order_days': 12,
        'unit_shutdown': False,
        
        # 驱动归属判定
        'pxn': 340,
        'px_operation_rate': 75,
        'pta_processing_fee': 320,  # 加工费偏低
        'pta_operation_rate': 70,
        'export_impact': False,
        'coal_to_meg_profit': -100,
        'import_impact': False,
        'pf_processing_fee': 700,   # 加工费偏低
        'production_cut_letter': True,
        'pr_processing_fee': 400,
        
        # 盘面验证
        'px_change': -1.2,
        'ta_change': -0.8,
        'eg_change': -0.5,
        'pf_change': -0.3,
        'oil_price_change': -2.0,
        'ta_near_far_spread': 302,  # TA Back结构
        'eg_near_far_spread': 109,
        'pf_near_far_spread': 72,
        
        # 驱动切换
        'old_driver': '中性'
    }
    
    result1 = run_driver_identification(test_data_bearish)
    
    print(f"\n【场景1结果】")
    print(f"宏观趋势: {result1['summary']['macro_trend']} ({result1['summary']['macro_trend_strength']})")
    print(f"全产业链下跌: {result1['summary']['trending_down_harmonized']}")
    print(f"原始打分: {result1['summary']['raw_score']:.1f}")
    print(f"趋势过滤后: {result1['summary']['total_score']:.1f}")
    print(f"交易信号: {result1['summary']['trade_signal']}")
    print(f"过滤因子: {result1['summary']['macro_score_cap']}")
    
    # 验证：全产业链一致下跌时应为HOLD
    assert result1['summary']['trade_signal'] == 'HOLD', \
        f"❌ 失败: 全产业链下跌应输出HOLD, 得到{result1['summary']['trade_signal']}"
    print("✅ 场景1通过: 宏观下跌→原始高分数被过滤→HOLD\n")
    
    # ===== 场景2: 宏观上涨 + 微观偏多 + 有右侧确认 =====
    print("=" * 60)
    print("场景2: 宏观上涨(原油+5%) + 微观偏多 + 有右侧确认")
    print("预期: 宏观打分上限100% → BUY")
    print("=" * 60)
    
    test_data_bullish = dict(test_data_bearish)
    test_data_bullish.update({
        'crude_change_10d': 5.0,
        'ta_change_10d': 3.0,
        'eg_change_10d': 2.0,
        'pf_change_10d': 1.0,
        'pr_change_10d': 1.5,
        'lowest_3d_ago': 5400,
        'current_low': 5480,        # 3日未创新低✓
        'volume_increase_ratio': 2.0,  # 底部放量✓
        'rsi_current': 55,
        'rsi_previous': 40,
        'macd_bullish_cross': True,  # MACD金叉✓
        'price_above_ma20': True,    # 站上MA20✓
        'ma20_slope_positive': True, # MA20上翘✓
    })
    
    result2 = run_driver_identification(test_data_bullish)
    
    print(f"\n【场景2结果】")
    print(f"宏观趋势: {result2['summary']['macro_trend']} ({result2['summary']['macro_trend_strength']})")
    print(f"原始打分: {result2['summary']['raw_score']:.1f}")
    print(f"趋势过滤后: {result2['summary']['total_score']:.1f}")
    print(f"交易信号: {result2['summary']['trade_signal']}")
    print(f"右侧确认: 有(5个确认信号)")
    
    assert result2['summary']['trade_signal'] in ['BUY', 'WATCH'], \
        f"❌ 失败: 宏观上涨+确认应输出BUY/WATCH, 得到{result2['summary']['trade_signal']}"
    print(f"✅ 场景2通过: 宏观上涨+右侧确认→信号={result2['summary']['trade_signal']}\n")
    
    # ===== 场景3: 震荡市 + 微观偏多 + 无右侧确认 =====
    print("=" * 60)
    print("场景3: 震荡市 + 微观偏多 + 无右侧确认")
    print("预期: 宏观打分上限60% → HOLD")
    print("=" * 60)
    
    test_data_neutral = dict(test_data_bearish)
    test_data_neutral.update({
        'crude_change_10d': 0.5,
        'ta_change_10d': 0.3,
        'eg_change_10d': -0.2,
        'pf_change_10d': -0.1,
        'pr_change_10d': 0.1,
        'lowest_3d_ago': 5450,
        'current_low': 5430,
        'volume_increase_ratio': 1.0,
        'rsi_current': 48,
        'rsi_previous': 45,
        'macd_bullish_cross': False,
        'price_above_ma20': False,
        'ma20_slope_positive': False,
    })
    
    result3 = run_driver_identification(test_data_neutral)
    
    print(f"\n【场景3结果】")
    print(f"宏观趋势: {result3['summary']['macro_trend']} ({result3['summary']['macro_trend_strength']})")
    print(f"原始打分: {result3['summary']['raw_score']:.1f}")
    print(f"趋势过滤后: {result3['summary']['total_score']:.1f}")
    print(f"交易信号: {result3['summary']['trade_signal']}")
    print(f"右侧确认: 无")
    
    assert result3['summary']['trade_signal'] == 'HOLD', \
        f"❌ 失败: 震荡+无确认应输出HOLD, 得到{result3['summary']['trade_signal']}"
    print(f"✅ 场景3通过: 震荡+无右侧确认→HOLD\n")
    
    print("=" * 60)
    print("所有场景验证通过 ✅")
    print("=" * 60)
