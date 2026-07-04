#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
能源产业链量化打分模块

功能:
1. 燃料油五层量化打分框架
2. 沥青量化打分器
3. LPG量化打分器
4. 裂解价差计算器
5. 历史分位计算

权重结构:
- 成本因子 (25%)
- 裂解因子 (30%)

通达信期限结构支持:
在调用 scoring 前可用 _get_contango_from_tdx(pid) 获取真实的期限结构状态
"""

import os
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd
import numpy as np


# ============================================================
# 通达信 TdxCollector 期限结构工具(懒加载)
# ============================================================
_TDX_TS_CACHE: Dict[str, dict] = {}

def _get_contango_from_tdx(pid: str) -> bool:
    """
    通过通达信TdxCollector v2.0 获取品种的期限结构状态。
    
    返回 True=Contango(远月升水), False=Backwardation(近月升水)
    通达信不可用或查询失败时，默认返回 False(保守假设Backwardation)。
    """
    global _TDX_TS_CACHE
    pid_upper = pid.upper()
    
    if pid_upper in _TDX_TS_CACHE:
        return _TDX_TS_CACHE[pid_upper]['contango']
    
    try:
        fds_dir = os.path.expanduser("~/.workbuddy/skills/futures-data-search")
        if fds_dir not in sys.path:
            sys.path.insert(0, fds_dir)
        from collectors.tdx_collector import TdxCollector
        tdx = TdxCollector()
        if not tdx.is_available:
            return False
        
        ts = tdx.get_term_structure(pid_upper)
        if ts and ts.get('type'):
            contango = ts['type'].lower() == 'contango'
            _TDX_TS_CACHE[pid_upper] = {
                'contango': contango,
                'slope': ts.get('slope', 0),
                'near_price': ts.get('near_price'),
                'far_price': ts.get('far_price'),
                'contracts_count': ts.get('contract_count', 0),
                'source': 'tdx_local',
            }
            sig = '+' if ts.get('slope', 0) > 0 else ''
            print(f"[scoring] {pid}: 期限结构={'Contango' if contango else 'Back'}({sig}{ts.get('slope',0)}%)")
            return contango
    except Exception as e:
        print(f"[scoring] {pid}: 通达信期限结构获取失败: {str(e)[:60]}")
    
    return False

# 量化打分模块顶层权重配置
# - 新加坡外盘 (20%)
# - 国内供需 (15%)
# - 盘面结构 (10%)

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ========== 数据类定义 ==========

@dataclass
class FuelOilScore:
    """燃料油五层量化打分结果"""
    cost_score: float       # 成本因子得分 (0-100)
    crack_score: float      # 裂解因子得分 (0-100)
    sg_score: float         # 新加坡外盘得分 (0-100)
    dom_score: float        # 国内供需得分 (0-100)
    struct_score: float     # 盘面结构得分 (0-100)
    total_score: float      # 综合得分 (0-100)
    signal: str             # 信号:做多/做空/观望
    confidence: str         # 置信度:高/中/低


@dataclass
class BitumenScore:
    """沥青量化打分结果"""
    cost_score: float       # 成本因子得分 (0-100)
    demand_score: float     # 需求因子得分 (0-100)
    supply_score: float     # 供给因子得分 (0-100)
    seasonal_score: float   # 季节性因子得分 (0-100)
    total_score: float      # 综合得分 (0-100)
    signal: str             # 信号
    confidence: str         # 置信度


@dataclass
class LPGScore:
    """LPG量化打分结果"""
    cost_score: float       # 成本因子得分 (0-100)
    demand_score: float     # 需求因子得分 (0-100)
    supply_score: float     # 供给因子得分 (0-100)
    seasonal_score: float   # 季节性因子得分 (0-100)
    total_score: float      # 综合得分 (0-100)
    signal: str             # 信号
    confidence: str         # 置信度


@dataclass
class CrackSpreadScore:
    """裂解价差因子打分结果"""
    fu_crack_score: float      # FU主裂解得分 (0-100)
    fu_crack_value: float      # FU裂解绝对值
    refinery_util_score: float  # 地炼开工得分
    india_import_score: float  # 印度进口得分
    russia_supply_score: float # 俄油到货得分 (反向)
    lu_crack_score: float      # LU主裂解得分
    lu_crack_value: float      # LU裂解绝对值
    bdi_score: float           # BDI航运得分
    bunker_score: float        # 保税加注得分
    lu_fu_spread_score: float  # LU-FU价差得分
    lu_fu_spread_value: float  # LU-FU价差值
    crack_total: float         # 裂解模块综合得分
    crack_signal: str          # 信号


# ========== 工具函数 ==========

def calculate_historical_percentile(series: pd.Series, current_value: float, 
                                   lookback_days: int = 756) -> float:
    """计算近N日历史分位(默认3年=756交易日)"""
    if len(series) < 20:
        return 50.0  # 数据不足返回中性
    recent = series.tail(lookback_days)
    percentile = (recent < current_value).sum() / len(recent) * 100
    return min(100, max(0, percentile))


# ========== 燃料油打分器 ==========

def calculate_fuel_oil_score(
    fu_close: float = 0.0,
    lu_close: float = 0.0,
    brent_close: float = 0.0,
    crack_spread_fu: float = 0.0,
    crack_spread_lu: float = 0.0,
    lu_fu_spread: float = 0.0,
    singapore_inventory_percentile: float = 50.0,
    basis: float = 0.0,
    contango: bool = False,
    shandong_refinery_util: float = 50.0,
    india_fuel_oil_import_yoy: float = 0.0,
    bdi_index_percentile: float = 50.0,
    policy_factor: float = 0.0,
    brent_20d_chg_percentile: float = 50.0,
    sc_brent_spread_percentile: float = 50.0,
    usdcny_percentile: float = 50.0,
    vlcc_freight_percentile: float = 50.0,
    geopolitics_score: float = 0.0,
    fu_crack_percentile: float = 50.0,
    lu_crack_percentile: float = 50.0,
    lu_fu_spread_percentile: float = 50.0,
    refinery_util_percentile: float = 50.0,
    india_import_percentile: float = 50.0,
    bdi_percentile: float = 50.0,
    sg_inventory_percentile: float = 50.0,
    sg_inv_wow_percentile: float = 50.0,
    arrival_percentile: float = 50.0,
    mops_percentile: float = 50.0,
    warehouse_percentile: float = 50.0,
    import_percentile: float = 50.0,
    production_percentile: float = 50.0,
    bunker_percentile: float = 50.0,
    basis_percentile: float = 50.0,
    month_spread_percentile: float = 50.0,
) -> FuelOilScore:
    """
    燃料油五层量化打分(v2.14.0 修正版)

    所有分位参数(0-100)需由调用方基于历史数据预先计算后传入。
    本函数仅负责加权合成和信号判定，不自行计算分位。

    参数:
        fu_close: FU主力收盘价(元/吨)
        lu_close: LU主力收盘价(元/吨)
        brent_close: 布伦特原油价格(美元/桶)
        crack_spread_fu: FU裂解价差(元/吨)
        crack_spread_lu: LU柴油裂差(元/吨)
        lu_fu_spread: 高低硫价差(LU-FU，元/吨)
        singapore_inventory_percentile: 新加坡库存分位(0-100，越高库存越多)
        basis: 基差(现货-期货，元/吨)
        contango: 是否Contango结构
        shandong_refinery_util: 山东地炼开工率分位(0-100)
        india_fuel_oil_import_yoy: 印度燃料油进口同比(%)
        bdi_index_percentile: BDI指数分位(0-100)
        policy_factor: 政策因子(-20 to +20)
        brent_20d_chg_percentile: 布伦特20日涨跌幅分位(0-100)
        sc_brent_spread_percentile: SC/布伦特价差分位(0-100)
        usdcny_percentile: USDCNY汇率分位(0-100)
        vlcc_freight_percentile: VLCC运价分位(0-100)
        geopolitics_score: 中东地缘得分(0-40)
        fu_crack_percentile: FU原油裂解分位(0-100)
        lu_crack_percentile: LU柴油裂解分位(0-100)
        lu_fu_spread_percentile: LU-FU价差分位(0-100)
        refinery_util_percentile: 地炼开工分位(0-100)
        india_import_percentile: 印度进口分位(0-100)
        bdi_percentile: BDI分位(0-100)
        sg_inventory_percentile: 新加坡库存分位(0-100，反向:越高越利空)
        sg_inv_wow_percentile: 库存周环比分位(0-100，反向)
        arrival_percentile: 到港量分位(0-100，反向)
        mops_percentile: MOPS现货涨跌分位(0-100)
        warehouse_percentile: 仓单分位(0-100，反向)
        import_percentile: 进口分位(0-100，反向)
        production_percentile: 炼厂产出分位(0-100，反向)
        bunker_percentile: 保税加注分位(0-100)
        basis_percentile: 基差分位(0-100)
        month_spread_percentile: 月间价差分位(0-100)

    返回:
        FuelOilScore: 量化打分结果
    """
    # ===== 模块1: 成本因子 (顶层权重25%, 模块内权重和=100%) =====
    # 布伦特20日涨跌幅分位 40%、SC/布伦特价差分位 20%、USDCNY汇率分位 20%、VLCC运价分位 15%、地缘 5%
    cost_score = (
        brent_20d_chg_percentile * 0.40 +
        sc_brent_spread_percentile * 0.20 +
        usdcny_percentile * 0.20 +
        vlcc_freight_percentile * 0.15 +
        geopolitics_score * 0.05
    )

    # ===== 模块2: 裂解因子 (顶层权重30%, 模块内权重和=100%) =====
    # FU裂解 40%、LU裂解 25%、LU-FU价差 5%、地炼开工 10%、印度进口 10%、BDI 10%
    crack_score = (
        fu_crack_percentile * 0.40 +
        lu_crack_percentile * 0.25 +
        lu_fu_spread_percentile * 0.05 +
        refinery_util_percentile * 0.10 +
        india_import_percentile * 0.10 +
        bdi_percentile * 0.10
    )

    # ===== 模块3: 新加坡外盘因子 (顶层权重20%, 模块内权重和=100%) =====
    # 库存 50%、库存周环比 20%、到港量 20%、MOPS 10%
    # 库存和到港量反向:库存越高/到港越多 → 越利空
    sg_score = (
        (100 - sg_inventory_percentile) * 0.50 +
        (100 - sg_inv_wow_percentile) * 0.20 +
        (100 - arrival_percentile) * 0.20 +
        mops_percentile * 0.10
    )

    # ===== 模块4: 国内供需+政策因子 (顶层权重15%, 模块内权重和=100%) =====
    # 仓单 30%、进口 25%、炼厂产出 20%、保税加注 15%、政策 10%
    dom_score = (
        (100 - warehouse_percentile) * 0.30 +
        (100 - import_percentile) * 0.25 +
        (100 - production_percentile) * 0.20 +
        bunker_percentile * 0.15 +
        (policy_factor + 50) * 0.10
    )

    # ===== 模块5: 盘面结构因子 (顶层权重10%, 模块内权重和=100%) =====
    struct_score = (
        basis_percentile * 0.50 +
        month_spread_percentile * 0.50
    )

    # ===== 综合得分 =====
    total_score = (
        cost_score * 0.25 +
        crack_score * 0.30 +
        sg_score * 0.20 +
        dom_score * 0.15 +
        struct_score * 0.10
    )

    # 信号判定
    if total_score > 65:
        signal = "做多"
        confidence = "高" if total_score > 75 else "中"
    elif total_score < 35:
        signal = "做空"
        confidence = "高" if total_score < 25 else "中"
    else:
        signal = "观望"
        confidence = "-"

    return FuelOilScore(
        cost_score=round(cost_score, 1),
        crack_score=round(crack_score, 1),
        sg_score=round(sg_score, 1),
        dom_score=round(dom_score, 1),
        struct_score=round(struct_score, 1),
        total_score=round(total_score, 1),
        signal=signal,
        confidence=confidence
    )


def format_fuel_oil_score_report(score: FuelOilScore) -> str:
    """格式化燃料油打分报告"""
    lines = [
        "=" * 60,
        "  燃料油五层量化打分报告",
        "=" * 60,
        f"  综合得分: {score.total_score:.1f} ({score.signal})",
        f"  置信度: {score.confidence}",
        "",
        "  ── 分项得分 ──",
        f"  成本因子 (25%):  {score.cost_score:.1f}",
        f"  裂解因子 (30%):  {score.crack_score:.1f}",
        f"  新加坡外盘(20%):  {score.sg_score:.1f}",
        f"  国内供需 (15%):  {score.dom_score:.1f}",
        f"  盘面结构 (10%):  {score.struct_score:.1f}",
        "=" * 60,
    ]
    return "\n".join(lines)


# ========== 裂解价差计算器 ==========

class CrackSpreadCalculator:
    """裂解价差因子计算器(FU/LU分开量化)"""
    
    # 换算系数
    BARREL_TO_TON = 7.33  # 桶/吨换算
    
    def __init__(self, lookback_days: int = 756):  # 默认3年
        self.lookback_days = lookback_days
    
    def calculate(
        self,
        fu_price: float,
        lu_price: float,
        brent: float,
        diesel_price: float,
        usdcny: float,
        refinery_util: float,
        india_import_yoy: float,
        russia_supply_yoy: float,
        bdi_percentile: float,
        bunker_yoy: float,
        month: int
    ) -> CrackSpreadScore:
        """计算裂解价差得分"""
        
        # 计算裂解价差
        # FU裂解 = FU价格 - 布伦特价格 × 换算系数 × 汇率
        fu_crack = fu_price - brent * self.BARREL_TO_TON * usdcny
        
        # LU裂解 = LU价格 - 柴油价格 × 0.8(简化)
        lu_crack = lu_price - diesel_price * 0.8
        
        # 裂解得分(简化计算)
        # 实际应该基于历史分位
        fu_crack_score = min(100, max(0, 50 + fu_crack / 100))
        lu_crack_score = min(100, max(0, 50 + lu_crack / 100))
        
        # 其他因子得分
        refinery_util_score = min(100, max(0, refinery_util))
        india_import_score = min(100, max(0, 50 + india_import_yoy * 5))
        russia_supply_score = min(100, max(0, 50 - russia_supply_yoy * 5))
        bdi_score = min(100, max(0, bdi_percentile))
        bunker_score = min(100, max(0, 50 + bunker_yoy * 5))
        
        # LU-FU价差得分
        lu_fu_spread = lu_price - fu_price
        lu_fu_spread_score = min(100, max(0, 50 + lu_fu_spread / 100))
        
        # 综合得分
        crack_total = (
            fu_crack_score * 0.30 +
            lu_crack_score * 0.25 +
            refinery_util_score * 0.15 +
            india_import_score * 0.10 +
            russia_supply_score * 0.10 +
            bdi_score * 0.05 +
            bunker_score * 0.05
        )
        
        # 信号判定
        if crack_total > 65:
            crack_signal = "利多"
        elif crack_total < 35:
            crack_signal = "利空"
        else:
            crack_signal = "中性"
        
        return CrackSpreadScore(
            fu_crack_score=round(fu_crack_score, 1),
            fu_crack_value=round(fu_crack, 1),
            refinery_util_score=round(refinery_util_score, 1),
            india_import_score=round(india_import_score, 1),
            russia_supply_score=round(russia_supply_score, 1),
            lu_crack_score=round(lu_crack_score, 1),
            lu_crack_value=round(lu_crack, 1),
            bdi_score=round(bdi_score, 1),
            bunker_score=round(bunker_score, 1),
            lu_fu_spread_score=round(lu_fu_spread_score, 1),
            lu_fu_spread_value=round(lu_fu_spread, 1),
            crack_total=round(crack_total, 1),
            crack_signal=crack_signal
        )


def format_crack_spread_report(score: CrackSpreadScore) -> str:
    """格式化裂解价差报告"""
    lines = [
        "=" * 60,
        "  裂解价差因子报告",
        "=" * 60,
        f"  综合得分: {score.crack_total:.1f} ({score.crack_signal})",
        "",
        "  ── FU高硫裂解 ──",
        f"  FU裂解得分: {score.fu_crack_score:.1f}",
        f"  FU裂解值: {score.fu_crack_value:.1f} 元/吨",
        f"  地炼开工得分: {score.refinery_util_score:.1f}",
        f"  印度进口得分: {score.india_import_score:.1f}",
        f"  俄油到货得分: {score.russia_supply_score:.1f}",
        "",
        "  ── LU低硫裂解 ──",
        f"  LU裂解得分: {score.lu_crack_score:.1f}",
        f"  LU裂解值: {score.lu_crack_value:.1f} 元/吨",
        f"  BDI航运得分: {score.bdi_score:.1f}",
        f"  保税加注得分: {score.bunker_score:.1f}",
        "",
        "  ── 跨品种 ──",
        f"  LU-FU价差得分: {score.lu_fu_spread_score:.1f}",
        f"  LU-FU价差值: {score.lu_fu_spread_value:.1f} 元/吨",
        "=" * 60,
    ]
    return "\n".join(lines)


# ========== 沥青打分器 ==========

class BitumenScorer:
    """沥青量化打分器"""
    
    def __init__(self):
        pass
    
    def score(self, params: Dict, month: int) -> BitumenScore:
        """计算沥青得分"""
        
        # 成本因子
        cost_score = (
            params.get('brent_chg', 0) * 0.40 +
            params.get('sc_brent_spread', 0) * 0.20 +
            params.get('usdcny', 7.2) * 0.20 +
            params.get('production_yoy', 0) * 0.20
        )
        
        # 需求因子
        demand_score = (
            params.get('highway_invest_yoy', 0) * 0.30 +
            params.get('consumption', 50) * 0.40 +
            params.get('project_start_rate', 50) * 0.30
        )
        
        # 供给因子
        supply_score = (
            params.get('refinery_run', 50) * 0.40 +
            params.get('import_yoy', 0) * 0.30 +
            params.get('plant_stock', 50) * 0.30
        )
        
        # 季节性因子(5-9月印度发电旺季)
        if month in [5, 6, 7, 8, 9]:
            seasonal_score = 58  # 旺季(基础50 + 8)
        else:
            seasonal_score = 50  # 平季
        
        # 综合得分
        total_score = (
            cost_score * 0.25 +
            demand_score * 0.30 +
            supply_score * 0.25 +
            seasonal_score * 0.20
        )
        
        # 信号判定
        if total_score > 65:
            signal = "做多"
            confidence = "高" if total_score > 75 else "中"
        elif total_score < 35:
            signal = "做空"
            confidence = "高" if total_score < 25 else "中"
        else:
            signal = "观望"
            confidence = "-"
        
        return BitumenScore(
            cost_score=round(cost_score, 1),
            demand_score=round(demand_score, 1),
            supply_score=round(supply_score, 1),
            seasonal_score=round(seasonal_score, 1),
            total_score=round(total_score, 1),
            signal=signal,
            confidence=confidence
        )


# ========== LPG打分器 ==========

class LPGScorer:
    """LPG量化打分器"""
    
    def __init__(self):
        pass
    
    def score(self, params: Dict, month: int) -> LPGScore:
        """计算LPG得分"""
        
        # 成本因子
        cost_score = (
            params.get('cp_propane_chg', 0) * 0.30 +
            params.get('cp_butane_chg', 0) * 0.20 +
            params.get('usdcny', 7.2) * 0.20 +
            params.get('fei', 50) * 0.30
        )
        
        # 需求因子
        demand_score = (
            params.get('pdh_margin', 50) * 0.30 +
            params.get('pdh_run', 50) * 0.30 +
            params.get('propylene_price', 50) * 0.20 +
            params.get('domestic_consumption', 0) * 0.20
        )
        
        # 供给因子
        supply_score = (
            params.get('production_yoy', 0) * 0.30 +
            params.get('import_yoy', 0) * 0.30 +
            params.get('refinery_run', 50) * 0.20 +
            params.get('east_stock', 50) * 0.20
        )
        
        # 季节性因子(冬季需求旺盛)
        if month in [11, 12, 1, 2]:
            seasonal_score = 70  # 冬季旺季
        elif month in [6, 7, 8]:
            seasonal_score = 40  # 夏季淡季
        else:
            seasonal_score = 55  # 平季
        
        # 综合得分
        total_score = (
            cost_score * 0.25 +
            demand_score * 0.30 +
            supply_score * 0.25 +
            seasonal_score * 0.20
        )
        
        # 信号判定
        if total_score > 65:
            signal = "做多"
            confidence = "高" if total_score > 75 else "中"
        elif total_score < 35:
            signal = "做空"
            confidence = "高" if total_score < 25 else "中"
        else:
            signal = "观望"
            confidence = "-"
        
        return LPGScore(
            cost_score=round(cost_score, 1),
            demand_score=round(demand_score, 1),
            supply_score=round(supply_score, 1),
            seasonal_score=round(seasonal_score, 1),
            total_score=round(total_score, 1),
            signal=signal,
            confidence=confidence
        )


# ========== 综合打分器 ==========

class CompleteFuelOilScorer:
    """燃料油五层量化打分器"""
    
    def __init__(self):
        pass
    
    def calculate(
        self,
        fu_close: float,
        lu_close: float,
        brent: float,
        sc: float,
        usdcny: float,
        freight: float,
        crack_fu: float,
        crack_lu: float,
        crack_refinery: float,
        india_import_yoy: float,
        bdi_percentile: float,
        bunker_yoy: float,
        month: int,
        sg_inventory: float,
        sg_inventory_prev: float,
        sg_inventory_yoy: float,
        arrival_yoy: float,
        mops_change: float,
        production_yoy: float,
        import_yoy: float,
        warehouse_level: float,
        policy_factor: float,
        basis: float,
        month_spread: float,
        geopolitics: float
    ) -> FuelOilScore:
        """计算燃料油综合得分"""
        
        # 计算历史分位(简化)
        brent_20d_chg_percentile = 50.0
        sc_brent_spread_percentile = 50.0
        usdcny_percentile = 50.0
        vlcc_freight_percentile = 50.0
        fu_crack_percentile = 50.0
        lu_crack_percentile = 50.0
        lu_fu_spread_percentile = 50.0
        refinery_util_percentile = 50.0
        india_import_percentile = 50.0
        sg_inventory_percentile = 50.0
        sg_inv_wow_percentile = 50.0
        arrival_percentile = 50.0
        mops_percentile = 50.0
        warehouse_percentile = 50.0
        import_percentile = 50.0
        production_percentile = 50.0
        bunker_percentile = 50.0
        basis_percentile = 50.0
        month_spread_percentile = 50.0
        
        return calculate_fuel_oil_score(
            fu_close=fu_close,
            lu_close=lu_close,
            brent_close=brent,
            crack_spread_fu=crack_fu,
            crack_spread_lu=crack_lu,
            lu_fu_spread=lu_close - fu_close,
            singapore_inventory_percentile=sg_inventory_percentile,
            basis=basis,
            contango=_get_contango_from_tdx('SC'),
            shandong_refinery_util=crack_refinery,
            india_fuel_oil_import_yoy=india_import_yoy,
            bdi_index_percentile=bdi_percentile,
            policy_factor=policy_factor,
            brent_20d_chg_percentile=brent_20d_chg_percentile,
            sc_brent_spread_percentile=sc_brent_spread_percentile,
            usdcny_percentile=usdcny_percentile,
            vlcc_freight_percentile=vlcc_freight_percentile,
            geopolitics_score=geopolitics,
            fu_crack_percentile=fu_crack_percentile,
            lu_crack_percentile=lu_crack_percentile,
            lu_fu_spread_percentile=lu_fu_spread_percentile,
            refinery_util_percentile=refinery_util_percentile,
            india_import_percentile=india_import_percentile,
            bdi_percentile=bdi_percentile,
            sg_inventory_percentile=sg_inventory_percentile,
            sg_inv_wow_percentile=sg_inv_wow_percentile,
            arrival_percentile=arrival_percentile,
            mops_percentile=mops_percentile,
            warehouse_percentile=warehouse_percentile,
            import_percentile=import_percentile,
            production_percentile=production_percentile,
            bunker_percentile=bunker_percentile,
            basis_percentile=basis_percentile,
            month_spread_percentile=month_spread_percentile
        )


def calculate_all_scores(
    fu_close: float,
    lu_close: float,
    brent: float,
    sc: float,
    usdcny: float,
    freight: float,
    crack_fu: float,
    crack_lu: float,
    crack_refinery: float,
    india_import_yoy: float,
    bdi_percentile: float,
    bunker_yoy: float,
    month: int,
    sg_inventory: float,
    sg_inventory_prev: float,
    sg_inventory_yoy: float,
    arrival_yoy: float,
    mops_change: float,
    production_yoy: float,
    import_yoy: float,
    warehouse_level: float,
    policy_factor: float,
    basis: float,
    month_spread: float,
    geopolitics: float
) -> Dict[str, FuelOilScore]:
    """计算所有品种得分"""
    
    # 燃料油得分
    fuel_oil_scorer = CompleteFuelOilScorer()
    fuel_oil_score = fuel_oil_scorer.calculate(
        fu_close=fu_close,
        lu_close=lu_close,
        brent=brent,
        sc=sc,
        usdcny=usdcny,
        freight=freight,
        crack_fu=crack_fu,
        crack_lu=crack_lu,
        crack_refinery=crack_refinery,
        india_import_yoy=india_import_yoy,
        bdi_percentile=bdi_percentile,
        bunker_yoy=bunker_yoy,
        month=month,
        sg_inventory=sg_inventory,
        sg_inventory_prev=sg_inventory_prev,
        sg_inventory_yoy=sg_inventory_yoy,
        arrival_yoy=arrival_yoy,
        mops_change=mops_change,
        production_yoy=production_yoy,
        import_yoy=import_yoy,
        warehouse_level=warehouse_level,
        policy_factor=policy_factor,
        basis=basis,
        month_spread=month_spread,
        geopolitics=geopolitics
    )
    
    return {
        'fuel_oil': fuel_oil_score
    }


def format_all_scores_report(scores: Dict[str, FuelOilScore]) -> str:
    # 格式化所有品种得分报告
    lines = [
        "=" * 60,
        "  能源产业链量化打分报告",
        "=" * 60,
    ]
    
    for name, score in scores.items():
        lines.append(f"\n  {name}: {score.total_score:.1f} ({score.signal})")
        lines.append(f"    置信度: {score.confidence}")
    
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)
