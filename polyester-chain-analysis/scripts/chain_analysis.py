#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚酯链产业链分析模块 v1.0.0

核心功能：
1. 成本传导分析（原油→石脑油→PX→PTA）
2. 供需平衡分析（PX/PTA/MEG/PF/PR）
3. 库存周期分析（Back/Contango切换）
4. 利润分配分析（PXN/TA加工费/PF加工费）

核心铁律：
- 原油定估值中枢
- PX定成本弹性
- PTA/MEG自身检修与库存定近月强弱
- 聚酯终端定上涨持续性
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
class CostTransmission:
    """成本传导分析结果"""
    crude_to_naphtha: float     # 原油→石脑油价差
    naphtha_to_px: float        # 石脑油→PX价差
    px_to_pta: float            # PX→PTA价差
    pxn: float                  # PXN（PX-石脑油价差）
    pta_processing_fee: float   # PTA加工费
    cost_efficiency: str        # 成本传导效率：高/中/低
    cost_driver: str            # 成本驱动：原油/PX/PTA


@dataclass
class SupplyDemandBalance:
    """供需平衡分析结果"""
    px_supply: str              # PX供应状态：宽松/平衡/紧张
    pta_supply: str             # PTA供应状态
    meg_supply: str             # MEG供应状态
    pf_supply: str              # PF供应状态
    pr_supply: str              # PR供应状态
    polyester_demand: str       # 聚酯需求状态
    overall_balance: str        # 整体供需平衡：供过于求/平衡/供不应求
    balance_confidence: str     # 平衡置信度


@dataclass
class InventoryCycle:
    """库存周期分析结果"""
    pta_inventory: str          # PTA库存状态：累库/平衡/去库
    meg_inventory: str          # MEG库存状态
    pf_inventory: str           # PF库存状态
    pr_inventory: str           # PR库存状态
    term_structure: str         # 期限结构：Back/Contango/平坦
    cycle_phase: str            # 周期阶段：主动补库/被动补库/主动去库/被动去库
    cycle_confidence: str       # 周期置信度


@dataclass
class ProfitDistribution:
    """利润分配分析结果"""
    pxn_level: str              # PXN水平：低/中/高
    pta_profit_level: str       # PTA利润水平
    pf_profit_level: str        # PF利润水平
    pr_profit_level: str        # PR利润水平
    profit_center: str          # 利润中心：PX/PTA/PF/PR
    profit_trend: str           # 利润趋势：扩张/稳定/压缩
    profit_confidence: str      # 利润置信度


# ========== 成本传导分析 ==========

def analyze_cost_transmission(data: Dict) -> CostTransmission:
    """
    成本传导分析
    
    分析逻辑：
    - 原油→石脑油：裂解价差
    - 石脑油→PX：PXN
    - PX→PTA：PTA加工费
    
    返回：CostTransmission对象
    """
    # 获取数据
    crude_price = data.get('crude_price', 75)  # 原油价格（美元/桶）
    naphtha_price = data.get('naphtha_price', 600)  # 石脑油价格（美元/吨）
    px_price = data.get('px_price', 900)  # PX价格（美元/吨）
    pta_price = data.get('pta_price', 6000)  # PTA价格（元/吨）
    
    # 计算价差
    # 原油→石脑油（转换：1吨原油≈7.33桶）
    crude_to_naphtha = naphtha_price - crude_price * 7.33
    
    # 石脑油→PX
    naphtha_to_px = px_price - naphtha_price
    
    # PX→PTA（转换：1吨PTA≈0.65吨PX）
    px_to_pta = pta_price - px_price * 0.65 * 7.5  # 假设汇率7.5
    
    # PXN
    pxn = px_price - naphtha_price
    
    # PTA加工费
    pta_processing_fee = pta_price - px_price * 0.65 * 7.5
    
    # 判断成本传导效率
    if abs(crude_to_naphtha) < 50 and abs(naphtha_to_px) < 100:
        cost_efficiency = "高"
    elif abs(crude_to_naphtha) < 100 and abs(naphtha_to_px) < 200:
        cost_efficiency = "中"
    else:
        cost_efficiency = "低"
    
    # 判断成本驱动
    if abs(crude_to_naphtha) > abs(naphtha_to_px):
        cost_driver = "原油"
    elif abs(naphtha_to_px) > abs(px_to_pta):
        cost_driver = "PX"
    else:
        cost_driver = "PTA"
    
    return CostTransmission(
        crude_to_naphtha=crude_to_naphtha,
        naphtha_to_px=naphtha_to_px,
        px_to_pta=px_to_pta,
        pxn=pxn,
        pta_processing_fee=pta_processing_fee,
        cost_efficiency=cost_efficiency,
        cost_driver=cost_driver
    )


# ========== 供需平衡分析 ==========

def analyze_supply_demand(data: Dict) -> SupplyDemandBalance:
    """
    供需平衡分析
    
    分析逻辑：
    - PX：亚洲PX开工、日韩货源、进口量、调油季
    - PTA：开工率、装置动态、仓单
    - MEG：国产煤制开工+进口到港量双驱动
    - PF/PR：开工、减产挺价动作
    - 聚酯：长丝/短纤/瓶片各自的开工、减产挺价
    
    返回：SupplyDemandBalance对象
    """
    # 获取数据
    px_operation_rate = data.get('px_operation_rate', 80)  # PX开工率
    pta_operation_rate = data.get('pta_operation_rate', 80)  # PTA开工率
    meg_operation_rate = data.get('meg_operation_rate', 70)  # MEG开工率
    pf_operation_rate = data.get('pf_operation_rate', 85)  # PF开工率
    pr_operation_rate = data.get('pr_operation_rate', 80)  # PR开工率
    polyester_load = data.get('polyester_load', 85)  # 聚酯负荷
    
    # 判断PX供应状态
    if px_operation_rate < 75:
        px_supply = "紧张"
    elif px_operation_rate > 85:
        px_supply = "宽松"
    else:
        px_supply = "平衡"
    
    # 判断PTA供应状态
    if pta_operation_rate < 70:
        pta_supply = "紧张"
    elif pta_operation_rate > 85:
        pta_supply = "宽松"
    else:
        pta_supply = "平衡"
    
    # 判断MEG供应状态
    if meg_operation_rate < 65:
        meg_supply = "紧张"
    elif meg_operation_rate > 75:
        meg_supply = "宽松"
    else:
        meg_supply = "平衡"
    
    # 判断PF供应状态
    if pf_operation_rate < 80:
        pf_supply = "紧张"
    elif pf_operation_rate > 90:
        pf_supply = "宽松"
    else:
        pf_supply = "平衡"
    
    # 判断PR供应状态
    if pr_operation_rate < 75:
        pr_supply = "紧张"
    elif pr_operation_rate > 85:
        pr_supply = "宽松"
    else:
        pr_supply = "平衡"
    
    # 判断聚酯需求状态
    if polyester_load > 85:
        polyester_demand = "旺盛"
    elif polyester_load < 80:
        polyester_demand = "疲软"
    else:
        polyester_demand = "平稳"
    
    # 判断整体供需平衡
    supply_scores = []
    for supply in [px_supply, pta_supply, meg_supply, pf_supply, pr_supply]:
        if supply == "紧张":
            supply_scores.append(1)
        elif supply == "宽松":
            supply_scores.append(-1)
        else:
            supply_scores.append(0)
    
    avg_supply_score = np.mean(supply_scores)
    
    if avg_supply_score > 0.3:
        overall_balance = "供不应求"
    elif avg_supply_score < -0.3:
        overall_balance = "供过于求"
    else:
        overall_balance = "平衡"
    
    # 判断平衡置信度
    if abs(avg_supply_score) > 0.5:
        balance_confidence = "高"
    elif abs(avg_supply_score) > 0.2:
        balance_confidence = "中"
    else:
        balance_confidence = "低"
    
    return SupplyDemandBalance(
        px_supply=px_supply,
        pta_supply=pta_supply,
        meg_supply=meg_supply,
        pf_supply=pf_supply,
        pr_supply=pr_supply,
        polyester_demand=polyester_demand,
        overall_balance=overall_balance,
        balance_confidence=balance_confidence
    )


# ========== 库存周期分析 ==========

def analyze_inventory_cycle(data: Dict) -> InventoryCycle:
    """
    库存周期分析
    
    分析逻辑：
    - PTA：社会库存、工厂库存、仓单
    - MEG：港口库存
    - PF/PR：工厂库存
    - 期限结构：Back/Contango切换
    
    返回：InventoryCycle对象
    """
    # 获取数据
    pta_inventory_change = data.get('pta_inventory_change', 0)  # PTA库存变化
    meg_port_inventory = data.get('meg_port_inventory', 85)  # MEG港口库存
    pf_inventory_change = data.get('pf_inventory_change', 0)  # PF库存变化
    pr_inventory_change = data.get('pr_inventory_change', 0)  # PR库存变化
    ta_near_far_spread = data.get('ta_near_far_spread', 0)  # TA近远月价差
    
    # 判断PTA库存状态
    if pta_inventory_change > 5:
        pta_inventory = "累库"
    elif pta_inventory_change < -5:
        pta_inventory = "去库"
    else:
        pta_inventory = "平衡"
    
    # 判断MEG库存状态
    if meg_port_inventory > 100:
        meg_inventory = "累库"
    elif meg_port_inventory < 80:
        meg_inventory = "去库"
    else:
        meg_inventory = "平衡"
    
    # 判断PF库存状态
    if pf_inventory_change > 3:
        pf_inventory = "累库"
    elif pf_inventory_change < -3:
        pf_inventory = "去库"
    else:
        pf_inventory = "平衡"
    
    # 判断PR库存状态
    if pr_inventory_change > 3:
        pr_inventory = "累库"
    elif pr_inventory_change < -3:
        pr_inventory = "去库"
    else:
        pr_inventory = "平衡"
    
    # 判断期限结构
    if ta_near_far_spread > 50:
        term_structure = "Back"
    elif ta_near_far_spread < -50:
        term_structure = "Contango"
    else:
        term_structure = "平坦"
    
    # 判断周期阶段
    # 主动补库：需求好+库存累
    # 被动补库：需求差+库存累
    # 主动去库：需求差+库存去
    # 被动去库：需求好+库存去
    
    polyester_load = data.get('polyester_load', 85)  # 聚酯负荷
    inventory_changes = [pta_inventory_change, pf_inventory_change, pr_inventory_change]
    avg_inventory_change = np.mean(inventory_changes)
    
    if polyester_load > 85 and avg_inventory_change > 0:
        cycle_phase = "主动补库"
    elif polyester_load < 80 and avg_inventory_change > 0:
        cycle_phase = "被动补库"
    elif polyester_load < 80 and avg_inventory_change < 0:
        cycle_phase = "主动去库"
    elif polyester_load > 85 and avg_inventory_change < 0:
        cycle_phase = "被动去库"
    else:
        cycle_phase = "过渡期"
    
    # 判断周期置信度
    if abs(avg_inventory_change) > 5:
        cycle_confidence = "高"
    elif abs(avg_inventory_change) > 2:
        cycle_confidence = "中"
    else:
        cycle_confidence = "低"
    
    return InventoryCycle(
        pta_inventory=pta_inventory,
        meg_inventory=meg_inventory,
        pf_inventory=pf_inventory,
        pr_inventory=pr_inventory,
        term_structure=term_structure,
        cycle_phase=cycle_phase,
        cycle_confidence=cycle_confidence
    )


# ========== 利润分配分析 ==========

def analyze_profit_distribution(data: Dict) -> ProfitDistribution:
    """
    利润分配分析
    
    分析逻辑：
    - PXN：PX-石脑油价差
    - PTA加工费：PX-PTA价差
    - PF加工费：PF-TA价差
    - PR加工费：PR-TA价差
    
    返回：ProfitDistribution对象
    """
    # 获取数据
    pxn = data.get('pxn', 300)  # PXN
    pta_processing_fee = data.get('pta_processing_fee', 400)  # PTA加工费
    pf_processing_fee = data.get('pf_processing_fee', 900)  # PF加工费
    pr_processing_fee = data.get('pr_processing_fee', 400)  # PR加工费
    
    # 判断PXN水平
    if pxn < 200:
        pxn_level = "低"
    elif pxn > 400:
        pxn_level = "高"
    else:
        pxn_level = "中"
    
    # 判断PTA利润水平
    if pta_processing_fee < 300:
        pta_profit_level = "低"
    elif pta_processing_fee > 600:
        pta_profit_level = "高"
    else:
        pta_profit_level = "中"
    
    # 判断PF利润水平
    if pf_processing_fee < 800:
        pf_profit_level = "低"
    elif pf_processing_fee > 1200:
        pf_profit_level = "高"
    else:
        pf_profit_level = "中"
    
    # 判断PR利润水平
    if pr_processing_fee < 300:
        pr_profit_level = "低"
    elif pr_processing_fee > 550:
        pr_profit_level = "高"
    else:
        pr_profit_level = "中"
    
    # 判断利润中心
    profit_levels = {
        'PX': pxn_level,
        'PTA': pta_profit_level,
        'PF': pf_profit_level,
        'PR': pr_profit_level
    }
    
    # 找出利润最高的环节
    high_profit环节 = [k for k, v in profit_levels.items() if v == "高"]
    if high_profit环节:
        profit_center = high_profit环节[0]
    else:
        profit_center = "平衡"
    
    # 判断利润趋势
    # 简化判断：检查各环节利润变化
    pta_profit_change = data.get('pta_profit_change', 0)  # PTA利润变化
    pf_profit_change = data.get('pf_profit_change', 0)  # PF利润变化
    
    if pta_profit_change > 0 and pf_profit_change > 0:
        profit_trend = "扩张"
    elif pta_profit_change < 0 and pf_profit_change < 0:
        profit_trend = "压缩"
    else:
        profit_trend = "稳定"
    
    # 判断利润置信度
    if profit_center != "平衡":
        profit_confidence = "高"
    elif profit_trend != "稳定":
        profit_confidence = "中"
    else:
        profit_confidence = "低"
    
    return ProfitDistribution(
        pxn_level=pxn_level,
        pta_profit_level=pta_profit_level,
        pf_profit_level=pf_profit_level,
        pr_profit_level=pr_profit_level,
        profit_center=profit_center,
        profit_trend=profit_trend,
        profit_confidence=profit_confidence
    )


# ========== 主函数 ==========

def run_chain_analysis(data: Dict) -> Dict:
    """
    运行完整的产业链分析流程
    
    返回：包含所有分析结果的字典
    """
    logger.info("开始产业链分析...")
    
    # 1. 成本传导分析
    logger.info("执行成本传导分析...")
    cost_transmission = analyze_cost_transmission(data)
    
    # 2. 供需平衡分析
    logger.info("执行供需平衡分析...")
    supply_demand = analyze_supply_demand(data)
    
    # 3. 库存周期分析
    logger.info("执行库存周期分析...")
    inventory_cycle = analyze_inventory_cycle(data)
    
    # 4. 利润分配分析
    logger.info("执行利润分配分析...")
    profit_distribution = analyze_profit_distribution(data)
    
    # 汇总结果
    result = {
        'cost_transmission': cost_transmission,
        'supply_demand': supply_demand,
        'inventory_cycle': inventory_cycle,
        'profit_distribution': profit_distribution,
        'summary': {
            'cost_driver': cost_transmission.cost_driver,
            'overall_balance': supply_demand.overall_balance,
            'cycle_phase': inventory_cycle.cycle_phase,
            'profit_center': profit_distribution.profit_center,
            'profit_trend': profit_distribution.profit_trend
        }
    }
    
    logger.info(f"产业链分析完成：成本驱动{cost_transmission.cost_driver}，供需{supply_demand.overall_balance}，周期{inventory_cycle.cycle_phase}，利润中心{profit_distribution.profit_center}")
    
    return result


# ========== 测试代码 ==========

if __name__ == "__main__":
    # 测试数据
    test_data = {
        # 成本传导
        'crude_price': 75,  # 原油价格（美元/桶）
        'naphtha_price': 600,  # 石脑油价格（美元/吨）
        'px_price': 900,  # PX价格（美元/吨）
        'pta_price': 6000,  # PTA价格（元/吨）
        
        # 供需平衡
        'px_operation_rate': 75,  # PX开工率
        'pta_operation_rate': 70,  # PTA开工率
        'meg_operation_rate': 65,  # MEG开工率
        'pf_operation_rate': 80,  # PF开工率
        'pr_operation_rate': 75,  # PR开工率
        'polyester_load': 83,  # 聚酯负荷
        
        # 库存周期
        'pta_inventory_change': -8,  # PTA库存变化
        'meg_port_inventory': 82,  # MEG港口库存
        'pf_inventory_change': -2,  # PF库存变化
        'pr_inventory_change': 1,  # PR库存变化
        'ta_near_far_spread': 150,  # TA近远月价差
        
        # 利润分配
        'pxn': 350,  # PXN
        'pta_processing_fee': 450,  # PTA加工费
        'pf_processing_fee': 850,  # PF加工费
        'pr_processing_fee': 400,  # PR加工费
        'pta_profit_change': 50,  # PTA利润变化
        'pf_profit_change': 30,  # PF利润变化
    }
    
    # 运行产业链分析
    result = run_chain_analysis(test_data)
    
    # 输出结果
    print("=" * 50)
    print("产业链分析结果")
    print("=" * 50)
    
    print(f"\n【成本传导分析】")
    print(f"原油→石脑油价差：{result['cost_transmission'].crude_to_naphtha:.1f}美元")
    print(f"石脑油→PX价差：{result['cost_transmission'].naphtha_to_px:.1f}美元")
    print(f"PX→PTA价差：{result['cost_transmission'].px_to_pta:.1f}元")
    print(f"PXN：{result['cost_transmission'].pxn:.1f}美元")
    print(f"PTA加工费：{result['cost_transmission'].pta_processing_fee:.1f}元")
    print(f"成本传导效率：{result['cost_transmission'].cost_efficiency}")
    print(f"成本驱动：{result['cost_transmission'].cost_driver}")
    
    print(f"\n【供需平衡分析】")
    print(f"PX供应：{result['supply_demand'].px_supply}")
    print(f"PTA供应：{result['supply_demand'].pta_supply}")
    print(f"MEG供应：{result['supply_demand'].meg_supply}")
    print(f"PF供应：{result['supply_demand'].pf_supply}")
    print(f"PR供应：{result['supply_demand'].pr_supply}")
    print(f"聚酯需求：{result['supply_demand'].polyester_demand}")
    print(f"整体平衡：{result['supply_demand'].overall_balance}")
    print(f"平衡置信度：{result['supply_demand'].balance_confidence}")
    
    print(f"\n【库存周期分析】")
    print(f"PTA库存：{result['inventory_cycle'].pta_inventory}")
    print(f"MEG库存：{result['inventory_cycle'].meg_inventory}")
    print(f"PF库存：{result['inventory_cycle'].pf_inventory}")
    print(f"PR库存：{result['inventory_cycle'].pr_inventory}")
    print(f"期限结构：{result['inventory_cycle'].term_structure}")
    print(f"周期阶段：{result['inventory_cycle'].cycle_phase}")
    print(f"周期置信度：{result['inventory_cycle'].cycle_confidence}")
    
    print(f"\n【利润分配分析】")
    print(f"PXN水平：{result['profit_distribution'].pxn_level}")
    print(f"PTA利润：{result['profit_distribution'].pta_profit_level}")
    print(f"PF利润：{result['profit_distribution'].pf_profit_level}")
    print(f"PR利润：{result['profit_distribution'].pr_profit_level}")
    print(f"利润中心：{result['profit_distribution'].profit_center}")
    print(f"利润趋势：{result['profit_distribution'].profit_trend}")
    print(f"利润置信度：{result['profit_distribution'].profit_confidence}")
    
    print(f"\n【汇总】")
    print(f"成本驱动：{result['summary']['cost_driver']}")
    print(f"整体供需：{result['summary']['overall_balance']}")
    print(f"库存周期：{result['summary']['cycle_phase']}")
    print(f"利润中心：{result['summary']['profit_center']}")
    print(f"利润趋势：{result['summary']['profit_trend']}")
