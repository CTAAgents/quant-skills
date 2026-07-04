#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚酯链套利信号模块 v1.0.0

核心功能：
1. TA-EG价差套利（芳烃vs烯烃错配）
2. PF-TA加工差套利（短纤无定价权）
3. TA月差套利（近端检修去库vs远端新产能）
4. 多腿组合交易建议

核心铁律：
- TA-EG价差：调油季PX强→TA强于EG
- PF-TA加工差：加工费均值回归+工厂行为博弈
- TA月差：Back结构交易
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

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
class ArbitrageSignal:
    """套利信号"""
    signal_type: str            # 信号类型：TA-EG价差/PF-TA加工差/TA月差
    direction: str              # 方向：做扩/做缩/正套/反套
    entry_condition: str        # 进场条件
    exit_condition: str         # 出场条件
    target_profit: float        # 目标收益（%）
    stop_loss: float            # 止损（%）
    confidence: str             # 置信度：高/中/低
    time_horizon: str           # 时间框架：短期/中期/长期


@dataclass
class TAEgSpreadSignal:
    """TA-EG价差信号"""
    current_spread: float       # 当前价差
    historical_percentile: float  # 历史分位
    entry_zone: Tuple[float, float]  # 进场区间
    target_zone: Tuple[float, float]  # 目标区间
    stop_loss: float            # 止损位
    signal_strength: str        # 信号强度
    driver: str                 # 驱动因素


@dataclass
class PfTaSpreadSignal:
    """PF-TA加工差信号"""
    current_spread: float       # 当前加工差
    historical_percentile: float  # 历史分位
    entry_zone: Tuple[float, float]  # 进场区间
    target_zone: Tuple[float, float]  # 目标区间
    stop_loss: float            # 止损位
    signal_strength: str        # 信号强度
    driver: str                 # 驱动因素


@dataclass
class TaTermStructureSignal:
    """TA月差信号"""
    current_spread: float       # 当前月差
    historical_percentile: float  # 历史分位
    entry_zone: Tuple[float, float]  # 进场区间
    target_zone: Tuple[float, float]  # 目标区间
    stop_loss: float            # 止损位
    signal_strength: str        # 信号强度
    driver: str                 # 驱动因素


@dataclass
class MultiLegCombination:
    """多腿组合建议"""
    legs: List[Dict]            # 各腿信息
    net_exposure: float         # 净敞口
    total_risk: float           # 总风险
    expected_return: float      # 预期收益
    risk_reward_ratio: float    # 盈亏比
    confidence: str             # 置信度


# ========== TA-EG价差套利 ==========

def analyze_ta_eg_spread(data: Dict) -> TAEgSpreadSignal:
    """
    TA-EG价差套利分析
    
    分析逻辑：
    - 本质：芳烃（PTA走PX路线）vs烯烃（EG走乙烯/煤路线）
    - 调油季PX强→TA强于EG
    - 煤制利润好+EG累库→EG弱于TA
    
    返回：TAEgSpreadSignal对象
    """
    # 获取数据
    ta_price = data.get('ta_price', 6000)  # TA价格
    eg_price = data.get('eg_price', 4500)  # EG价格
    ta_eg_spread = ta_price - eg_price  # TA-EG价差
    
    # 历史分位（简化处理）
    historical_percentile = data.get('ta_eg_spread_percentile', 50)  # 历史分位
    
    # 进场区间判断
    if historical_percentile < 20:
        entry_zone = (ta_eg_spread * 0.95, ta_eg_spread * 1.05)
        direction = "做扩"
        signal_strength = "强"
    elif historical_percentile > 80:
        entry_zone = (ta_eg_spread * 0.95, ta_eg_spread * 1.05)
        direction = "做缩"
        signal_strength = "强"
    else:
        entry_zone = (ta_eg_spread * 0.9, ta_eg_spread * 1.1)
        direction = "观望"
        signal_strength = "弱"
    
    # 目标区间
    if direction == "做扩":
        target_zone = (ta_eg_spread * 1.1, ta_eg_spread * 1.2)
        stop_loss = ta_eg_spread * 0.9
    elif direction == "做缩":
        target_zone = (ta_eg_spread * 0.8, ta_eg_spread * 0.9)
        stop_loss = ta_eg_spread * 1.1
    else:
        target_zone = (ta_eg_spread, ta_eg_spread)
        stop_loss = ta_eg_spread
    
    # 驱动因素判断
    gasoline_crack = data.get('gasoline_crack', 0)  # 汽油裂差
    coal_to_meg_profit = data.get('coal_to_meg_profit', 0)  # 煤制MEG利润
    meg_port_inventory = data.get('meg_port_inventory', 85)  # MEG港口库存
    
    if gasoline_crack > 30:
        driver = "调油逻辑"
    elif coal_to_meg_profit > 0 and meg_port_inventory > 100:
        driver = "煤制复产+EG累库"
    elif meg_port_inventory < 80:
        driver = "EG港口去库"
    else:
        driver = "中性"
    
    return TAEgSpreadSignal(
        current_spread=ta_eg_spread,
        historical_percentile=historical_percentile,
        entry_zone=entry_zone,
        target_zone=target_zone,
        stop_loss=stop_loss,
        signal_strength=signal_strength,
        driver=driver
    )


# ========== PF-TA加工差套利 ==========

def analyze_pf_ta_spread(data: Dict) -> PfTaSpreadSignal:
    """
    PF-TA加工差套利分析
    
    分析逻辑：
    - 本质：短纤无定价权，加工费均值回归
    - 加工费压到极致→工厂联合减产→供应收缩→加工费修复
    - 加工费拉到高位→工厂复产/新装置开→供应释放→加工费压缩
    
    返回：PfTaSpreadSignal对象
    """
    # 获取数据
    pf_price = data.get('pf_price', 7000)  # PF价格
    ta_price = data.get('ta_price', 6000)  # TA价格
    pf_ta_spread = pf_price - ta_price  # PF-TA加工差
    
    # 历史分位（简化处理）
    historical_percentile = data.get('pf_ta_spread_percentile', 50)  # 历史分位
    
    # 进场区间判断
    if historical_percentile < 20:
        entry_zone = (pf_ta_spread * 0.95, pf_ta_spread * 1.05)
        direction = "做扩"
        signal_strength = "强"
    elif historical_percentile > 80:
        entry_zone = (pf_ta_spread * 0.95, pf_ta_spread * 1.05)
        direction = "做缩"
        signal_strength = "强"
    else:
        entry_zone = (pf_ta_spread * 0.9, pf_ta_spread * 1.1)
        direction = "观望"
        signal_strength = "弱"
    
    # 目标区间
    if direction == "做扩":
        target_zone = (pf_ta_spread * 1.1, pf_ta_spread * 1.2)
        stop_loss = pf_ta_spread * 0.9
    elif direction == "做缩":
        target_zone = (pf_ta_spread * 0.8, pf_ta_spread * 0.9)
        stop_loss = pf_ta_spread * 1.1
    else:
        target_zone = (pf_ta_spread, pf_ta_spread)
        stop_loss = pf_ta_spread
    
    # 驱动因素判断
    production_cut_letter = data.get('production_cut_letter', False)  # 减产函
    pf_operation_rate = data.get('pf_operation_rate', 85)  # PF开工率
    
    if production_cut_letter and pf_operation_rate <= 80:
        driver = "工厂减产"
    elif pf_ta_spread < 800:
        driver = "加工费极值"
    elif pf_ta_spread > 1200:
        driver = "加工费高位"
    else:
        driver = "中性"
    
    return PfTaSpreadSignal(
        current_spread=pf_ta_spread,
        historical_percentile=historical_percentile,
        entry_zone=entry_zone,
        target_zone=target_zone,
        stop_loss=stop_loss,
        signal_strength=signal_strength,
        driver=driver
    )


# ========== TA月差套利 ==========

def analyze_ta_term_structure(data: Dict) -> TaTermStructureSignal:
    """
    TA月差套利分析
    
    分析逻辑：
    - 近端检修去库vs远端新产能
    - Back结构：近高远低，做正套
    - Contango结构：近低远高，做反套
    
    返回：TaTermStructureSignal对象
    """
    # 获取数据
    ta_near_price = data.get('ta_near_price', 6000)  # TA近月价格
    ta_far_price = data.get('ta_far_price', 5800)  # TA远月价格
    ta_spread = ta_near_price - ta_far_price  # TA月差
    
    # 历史分位（简化处理）
    historical_percentile = data.get('ta_spread_percentile', 50)  # 历史分位
    
    # 进场区间判断
    if historical_percentile < 20:
        entry_zone = (ta_spread * 0.95, ta_spread * 1.05)
        direction = "正套"
        signal_strength = "强"
    elif historical_percentile > 80:
        entry_zone = (ta_spread * 0.95, ta_spread * 1.05)
        direction = "反套"
        signal_strength = "强"
    else:
        entry_zone = (ta_spread * 0.9, ta_spread * 1.1)
        direction = "观望"
        signal_strength = "弱"
    
    # 目标区间
    if direction == "正套":
        target_zone = (ta_spread * 1.1, ta_spread * 1.2)
        stop_loss = ta_spread * 0.9
    elif direction == "反套":
        target_zone = (ta_spread * 0.8, ta_spread * 0.9)
        stop_loss = ta_spread * 1.1
    else:
        target_zone = (ta_spread, ta_spread)
        stop_loss = ta_spread
    
    # 驱动因素判断
    pta_maintenance_rate = data.get('pta_maintenance_rate', 0)  # PTA检修率
    overseas_new_capacity = data.get('overseas_new_capacity', False)  # 海外新装置
    
    if pta_maintenance_rate > 20:
        driver = "近端检修去库"
    elif overseas_new_capacity:
        driver = "远端新产能"
    elif ta_spread > 100:
        driver = "Back结构"
    elif ta_spread < -100:
        driver = "Contango结构"
    else:
        driver = "中性"
    
    return TaTermStructureSignal(
        current_spread=ta_spread,
        historical_percentile=historical_percentile,
        entry_zone=entry_zone,
        target_zone=target_zone,
        stop_loss=stop_loss,
        signal_strength=signal_strength,
        driver=driver
    )


# ========== 多腿组合建议 ==========

def generate_multi_leg_combination(data: Dict) -> MultiLegCombination:
    """
    生成多腿组合建议
    
    组合逻辑：
    - 基础层：TA-EG价差、PF-TA加工差
    - 高级层：三腿组合（近月TA正套+远月空TA+多TA空PR）
    
    返回：MultiLegCombination对象
    """
    # 获取数据
    ta_eg_spread = data.get('ta_eg_spread', 1500)  # TA-EG价差
    pf_ta_spread = data.get('pf_ta_spread', 1000)  # PF-TA加工差
    ta_spread = data.get('ta_spread', 200)  # TA月差
    
    # 判断组合类型
    legs = []
    total_risk = 0
    expected_return = 0
    
    # TA-EG价差腿
    if ta_eg_spread < 1400:
        legs.append({
            'type': 'TA-EG价差',
            'direction': '做扩',
            'weight': 1.0,
            'risk': 5,
            'expected_return': 10
        })
        total_risk += 5
        expected_return += 10
    
    # PF-TA加工差腿
    if pf_ta_spread < 800:
        legs.append({
            'type': 'PF-TA加工差',
            'direction': '做扩',
            'weight': 1.0,
            'risk': 5,
            'expected_return': 10
        })
        total_risk += 5
        expected_return += 10
    
    # TA月差腿
    if ta_spread > 100:
        legs.append({
            'type': 'TA月差',
            'direction': '正套',
            'weight': 1.0,
            'risk': 3,
            'expected_return': 8
        })
        total_risk += 3
        expected_return += 8
    
    # 如果没有腿，返回空组合
    if not legs:
        return MultiLegCombination(
            legs=[],
            net_exposure=0,
            total_risk=0,
            expected_return=0,
            risk_reward_ratio=0,
            confidence="低"
        )
    
    # 计算净敞口
    net_exposure = sum(leg['weight'] for leg in legs if leg['direction'] in ['做扩', '正套'])
    net_exposure -= sum(leg['weight'] for leg in legs if leg['direction'] in ['做缩', '反套'])
    
    # 计算盈亏比
    risk_reward_ratio = expected_return / total_risk if total_risk > 0 else 0
    
    # 判断置信度
    if len(legs) >= 3:
        confidence = "高"
    elif len(legs) >= 2:
        confidence = "中"
    else:
        confidence = "低"
    
    return MultiLegCombination(
        legs=legs,
        net_exposure=net_exposure,
        total_risk=total_risk,
        expected_return=expected_return,
        risk_reward_ratio=risk_reward_ratio,
        confidence=confidence
    )


# ========== 主函数 ==========

def run_arbitrage_analysis(data: Dict) -> Dict:
    """
    运行完整的套利分析流程
    
    返回：包含所有分析结果的字典
    """
    logger.info("开始套利分析...")
    
    # 1. TA-EG价差分析
    logger.info("执行TA-EG价差分析...")
    ta_eg_signal = analyze_ta_eg_spread(data)
    
    # 2. PF-TA加工差分析
    logger.info("执行PF-TA加工差分析...")
    pf_ta_signal = analyze_pf_ta_spread(data)
    
    # 3. TA月差分析
    logger.info("执行TA月差分析...")
    ta_term_signal = analyze_ta_term_structure(data)
    
    # 4. 多腿组合建议
    logger.info("生成多腿组合建议...")
    multi_leg = generate_multi_leg_combination(data)
    
    # 汇总结果
    result = {
        'ta_eg_signal': ta_eg_signal,
        'pf_ta_signal': pf_ta_signal,
        'ta_term_signal': ta_term_signal,
        'multi_leg': multi_leg,
        'summary': {
            'ta_eg_direction': ta_eg_signal.signal_strength,
            'pf_ta_direction': pf_ta_signal.signal_strength,
            'ta_term_direction': ta_term_signal.signal_strength,
            'multi_leg_confidence': multi_leg.confidence,
            'total_legs': len(multi_leg.legs)
        }
    }
    
    logger.info(f"套利分析完成：TA-EG{ta_eg_signal.signal_strength}，PF-TA{pf_ta_signal.signal_strength}，TA月差{ta_term_signal.signal_strength}，多腿组合{len(multi_leg.legs)}腿")
    
    return result


# ========== 测试代码 ==========

if __name__ == "__main__":
    # 测试数据
    test_data = {
        # TA-EG价差
        'ta_price': 6000,  # TA价格
        'eg_price': 4500,  # EG价格
        'ta_eg_spread_percentile': 25,  # 历史分位
        'gasoline_crack': 35,  # 汽油裂差
        'coal_to_meg_profit': -100,  # 煤制MEG利润
        'meg_port_inventory': 82,  # MEG港口库存
        
        # PF-TA加工差
        'pf_price': 7000,  # PF价格
        'pf_ta_spread_percentile': 30,  # 历史分位
        'production_cut_letter': True,  # 减产函
        'pf_operation_rate': 80,  # PF开工率
        
        # TA月差
        'ta_near_price': 6000,  # TA近月价格
        'ta_far_price': 5800,  # TA远月价格
        'ta_spread_percentile': 40,  # 历史分位
        'pta_maintenance_rate': 25,  # PTA检修率
        'overseas_new_capacity': True,  # 海外新装置
        
        # 多腿组合
        'ta_eg_spread': 1500,  # TA-EG价差
        'pf_ta_spread': 1000,  # PF-TA加工差
        'ta_spread': 200,  # TA月差
    }
    
    # 运行套利分析
    result = run_arbitrage_analysis(test_data)
    
    # 输出结果
    print("=" * 50)
    print("套利分析结果")
    print("=" * 50)
    
    print(f"\n【TA-EG价差分析】")
    print(f"当前价差：{result['ta_eg_signal'].current_spread}")
    print(f"历史分位：{result['ta_eg_signal'].historical_percentile}")
    print(f"进场区间：{result['ta_eg_signal'].entry_zone}")
    print(f"目标区间：{result['ta_eg_signal'].target_zone}")
    print(f"止损位：{result['ta_eg_signal'].stop_loss}")
    print(f"信号强度：{result['ta_eg_signal'].signal_strength}")
    print(f"驱动因素：{result['ta_eg_signal'].driver}")
    
    print(f"\n【PF-TA加工差分析】")
    print(f"当前加工差：{result['pf_ta_signal'].current_spread}")
    print(f"历史分位：{result['pf_ta_signal'].historical_percentile}")
    print(f"进场区间：{result['pf_ta_signal'].entry_zone}")
    print(f"目标区间：{result['pf_ta_signal'].target_zone}")
    print(f"止损位：{result['pf_ta_signal'].stop_loss}")
    print(f"信号强度：{result['pf_ta_signal'].signal_strength}")
    print(f"驱动因素：{result['pf_ta_signal'].driver}")
    
    print(f"\n【TA月差分析】")
    print(f"当前月差：{result['ta_term_signal'].current_spread}")
    print(f"历史分位：{result['ta_term_signal'].historical_percentile}")
    print(f"进场区间：{result['ta_term_signal'].entry_zone}")
    print(f"目标区间：{result['ta_term_signal'].target_zone}")
    print(f"止损位：{result['ta_term_signal'].stop_loss}")
    print(f"信号强度：{result['ta_term_signal'].signal_strength}")
    print(f"驱动因素：{result['ta_term_signal'].driver}")
    
    print(f"\n【多腿组合建议】")
    print(f"腿数：{len(result['multi_leg'].legs)}")
    print(f"净敞口：{result['multi_leg'].net_exposure}")
    print(f"总风险：{result['multi_leg'].total_risk}")
    print(f"预期收益：{result['multi_leg'].expected_return}")
    print(f"盈亏比：{result['multi_leg'].risk_reward_ratio}")
    print(f"置信度：{result['multi_leg'].confidence}")
    
    print(f"\n【各腿详情】")
    for i, leg in enumerate(result['multi_leg'].legs):
        print(f"腿{i+1}: {leg['type']} {leg['direction']}，权重{leg['weight']}，风险{leg['risk']}，预期收益{leg['expected_return']}")
    
    print(f"\n【汇总】")
    print(f"TA-EG信号：{result['summary']['ta_eg_direction']}")
    print(f"PF-TA信号：{result['summary']['pf_ta_direction']}")
    print(f"TA月差信号：{result['summary']['ta_term_direction']}")
    print(f"多腿组合置信度：{result['summary']['multi_leg_confidence']}")
    print(f"总腿数：{result['summary']['total_legs']}")
