#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚酯链报告生成模块 v1.0.0

核心功能：
1. 主驱动诊断清单生成
2. 完整分析报告生成
3. 套利信号报告生成
4. 交易建议报告生成

报告格式：
- Markdown格式
- HTML格式（可选）
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ========== 主驱动诊断清单 ==========

def generate_driver_checklist(driver_result: Dict) -> str:
    """
    生成主驱动诊断清单
    
    返回：Markdown格式的诊断清单
    """
    checklist = []
    checklist.append("# 聚酯链主驱动诊断清单")
    checklist.append(f"\n**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    checklist.append("")
    
    # L1年度层
    checklist.append("## 一、年度层（L1）")
    checklist.append("")
    checklist.append(f"- **PX/TA/EG投产表变化**：{driver_result['driver_score'].l1_score:.1f}分")
    checklist.append(f"  - 主驱动：{driver_result['driver_score'].primary_driver}")
    checklist.append("")
    
    # L2季度层
    checklist.append("## 二、季度层（L2）")
    checklist.append("")
    checklist.append(f"- **PX检修量vs TA检修量**：{driver_result['driver_score'].l2_score:.1f}分")
    checklist.append(f"  - 调油裂差动没动：{driver_result['driver_attribution'].px_driver}")
    checklist.append(f"  - 地缘有没有新消息：{driver_result['driver_attribution'].pta_driver}")
    checklist.append("")
    
    # L3周度层
    checklist.append("## 三、周度层（L3）")
    checklist.append("")
    checklist.append(f"- **PXN、TA加工费、EG港口、PF加工费**：{driver_result['driver_score'].l3_score:.1f}分")
    checklist.append(f"  - PX驱动：{driver_result['driver_attribution'].px_driver}")
    checklist.append(f"  - PTA驱动：{driver_result['driver_attribution'].pta_driver}")
    checklist.append(f"  - MEG驱动：{driver_result['driver_attribution'].meg_driver}")
    checklist.append(f"  - PF驱动：{driver_result['driver_attribution'].pf_driver}")
    checklist.append(f"  - PR驱动：{driver_result['driver_attribution'].pr_driver}")
    checklist.append("")
    
    # 盘面层
    checklist.append("## 四、盘面层")
    checklist.append("")
    checklist.append(f"- **昨夜是谁领涨**：{driver_result['market_verification'].lead_lag_order}")
    checklist.append(f"- **利润往哪头挤**：{driver_result['market_verification'].profit_distribution}")
    checklist.append(f"- **月差走扩还是收**：{driver_result['market_verification'].term_structure}")
    checklist.append("")
    
    # 结论
    checklist.append("## 五、结论")
    checklist.append("")
    checklist.append(f"- **主驱动**：{driver_result['driver_score'].primary_driver}")
    checklist.append(f"- **驱动强度**：{driver_result['driver_score'].driver_strength}")
    checklist.append(f"- **置信度**：{driver_result['driver_score'].confidence}")
    checklist.append(f"- **综合得分**：{driver_result['driver_score'].total_score:.1f}")
    checklist.append(f"- **验证信号**：{driver_result['market_verification'].verification_signal}")
    checklist.append("")
    
    # 驱动切换信号
    if driver_result['driver_switch']:
        checklist.append("## 六、驱动切换信号")
        checklist.append("")
        checklist.append(f"- **切换类型**：{driver_result['driver_switch'].switch_type}")
        checklist.append(f"- **旧主驱动**：{driver_result['driver_switch'].old_driver}")
        checklist.append(f"- **新主驱动**：{driver_result['driver_switch'].new_driver}")
        checklist.append(f"- **切换置信度**：{driver_result['driver_switch'].switch_confidence}")
        checklist.append(f"- **头寸动作**：{driver_result['driver_switch'].position_action}")
        checklist.append("")
    
    return "\n".join(checklist)


# ========== 完整分析报告 ==========

def generate_full_report(
    driver_result: Dict,
    chain_result: Dict,
    arbitrage_result: Dict,
    data: Dict
) -> str:
    """
    生成完整分析报告
    
    返回：Markdown格式的完整报告
    """
    report = []
    report.append("# 聚酯链投研分析报告")
    report.append(f"\n**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 一、主驱动识别
    report.append("## 一、主驱动识别")
    report.append("")
    report.append(f"**主驱动**：{driver_result['driver_score'].primary_driver}")
    report.append(f"**驱动强度**：{driver_result['driver_score'].driver_strength}")
    report.append(f"**置信度**：{driver_result['driver_score'].confidence}")
    report.append(f"**综合得分**：{driver_result['driver_score'].total_score:.1f}")
    report.append("")
    
    # 三层漏斗诊断
    report.append("### 三层漏斗诊断")
    report.append("")
    report.append(f"- L1年度层：{driver_result['driver_score'].l1_score:.1f}分")
    report.append(f"- L2季度层：{driver_result['driver_score'].l2_score:.1f}分")
    report.append(f"- L3周度层：{driver_result['driver_score'].l3_score:.1f}分")
    report.append("")
    
    # 驱动归属判定
    report.append("### 驱动归属判定")
    report.append("")
    report.append(f"- PX驱动：{driver_result['driver_attribution'].px_driver}")
    report.append(f"- PTA驱动：{driver_result['driver_attribution'].pta_driver}")
    report.append(f"- MEG驱动：{driver_result['driver_attribution'].meg_driver}")
    report.append(f"- PF驱动：{driver_result['driver_attribution'].pf_driver}")
    report.append(f"- PR驱动：{driver_result['driver_attribution'].pr_driver}")
    report.append("")
    
    # 盘面验证
    report.append("### 盘面验证")
    report.append("")
    report.append(f"- 领涨领跌顺序：{driver_result['market_verification'].lead_lag_order}")
    report.append(f"- 利润分配：{driver_result['market_verification'].profit_distribution}")
    report.append(f"- 月差结构：{driver_result['market_verification'].term_structure}")
    report.append(f"- 验证信号：{driver_result['market_verification'].verification_signal}")
    report.append("")
    
    # 二、产业链分析
    report.append("## 二、产业链分析")
    report.append("")
    
    # 成本传导
    report.append("### 成本传导分析")
    report.append("")
    report.append(f"- 原油→石脑油价差：{chain_result['cost_transmission'].crude_to_naphtha:.1f}美元")
    report.append(f"- 石脑油→PX价差：{chain_result['cost_transmission'].naphtha_to_px:.1f}美元")
    report.append(f"- PX→PTA价差：{chain_result['cost_transmission'].px_to_pta:.1f}元")
    report.append(f"- PXN：{chain_result['cost_transmission'].pxn:.1f}美元")
    report.append(f"- PTA加工费：{chain_result['cost_transmission'].pta_processing_fee:.1f}元")
    report.append(f"- 成本传导效率：{chain_result['cost_transmission'].cost_efficiency}")
    report.append(f"- 成本驱动：{chain_result['cost_transmission'].cost_driver}")
    report.append("")
    
    # 供需平衡
    report.append("### 供需平衡分析")
    report.append("")
    report.append(f"- PX供应：{chain_result['supply_demand'].px_supply}")
    report.append(f"- PTA供应：{chain_result['supply_demand'].pta_supply}")
    report.append(f"- MEG供应：{chain_result['supply_demand'].meg_supply}")
    report.append(f"- PF供应：{chain_result['supply_demand'].pf_supply}")
    report.append(f"- PR供应：{chain_result['supply_demand'].pr_supply}")
    report.append(f"- 聚酯需求：{chain_result['supply_demand'].polyester_demand}")
    report.append(f"- 整体平衡：{chain_result['supply_demand'].overall_balance}")
    report.append("")
    
    # 库存周期
    report.append("### 库存周期分析")
    report.append("")
    report.append(f"- PTA库存：{chain_result['inventory_cycle'].pta_inventory}")
    report.append(f"- MEG库存：{chain_result['inventory_cycle'].meg_inventory}")
    report.append(f"- PF库存：{chain_result['inventory_cycle'].pf_inventory}")
    report.append(f"- PR库存：{chain_result['inventory_cycle'].pr_inventory}")
    report.append(f"- 期限结构：{chain_result['inventory_cycle'].term_structure}")
    report.append(f"- 周期阶段：{chain_result['inventory_cycle'].cycle_phase}")
    report.append("")
    
    # 利润分配
    report.append("### 利润分配分析")
    report.append("")
    report.append(f"- PXN水平：{chain_result['profit_distribution'].pxn_level}")
    report.append(f"- PTA利润：{chain_result['profit_distribution'].pta_profit_level}")
    report.append(f"- PF利润：{chain_result['profit_distribution'].pf_profit_level}")
    report.append(f"- PR利润：{chain_result['profit_distribution'].pr_profit_level}")
    report.append(f"- 利润中心：{chain_result['profit_distribution'].profit_center}")
    report.append(f"- 利润趋势：{chain_result['profit_distribution'].profit_trend}")
    report.append("")
    
    # 三、套利信号
    report.append("## 三、套利信号")
    report.append("")
    
    # TA-EG价差
    report.append("### TA-EG价差套利")
    report.append("")
    report.append(f"- 当前价差：{arbitrage_result['ta_eg_signal'].current_spread}")
    report.append(f"- 历史分位：{arbitrage_result['ta_eg_signal'].historical_percentile}")
    report.append(f"- 进场区间：{arbitrage_result['ta_eg_signal'].entry_zone}")
    report.append(f"- 目标区间：{arbitrage_result['ta_eg_signal'].target_zone}")
    report.append(f"- 止损位：{arbitrage_result['ta_eg_signal'].stop_loss}")
    report.append(f"- 信号强度：{arbitrage_result['ta_eg_signal'].signal_strength}")
    report.append(f"- 驱动因素：{arbitrage_result['ta_eg_signal'].driver}")
    report.append("")
    
    # PF-TA加工差
    report.append("### PF-TA加工差套利")
    report.append("")
    report.append(f"- 当前加工差：{arbitrage_result['pf_ta_signal'].current_spread}")
    report.append(f"- 历史分位：{arbitrage_result['pf_ta_signal'].historical_percentile}")
    report.append(f"- 进场区间：{arbitrage_result['pf_ta_signal'].entry_zone}")
    report.append(f"- 目标区间：{arbitrage_result['pf_ta_signal'].target_zone}")
    report.append(f"- 止损位：{arbitrage_result['pf_ta_signal'].stop_loss}")
    report.append(f"- 信号强度：{arbitrage_result['pf_ta_signal'].signal_strength}")
    report.append(f"- 驱动因素：{arbitrage_result['pf_ta_signal'].driver}")
    report.append("")
    
    # TA月差
    report.append("### TA月差套利")
    report.append("")
    report.append(f"- 当前月差：{arbitrage_result['ta_term_signal'].current_spread}")
    report.append(f"- 历史分位：{arbitrage_result['ta_term_signal'].historical_percentile}")
    report.append(f"- 进场区间：{arbitrage_result['ta_term_signal'].entry_zone}")
    report.append(f"- 目标区间：{arbitrage_result['ta_term_signal'].target_zone}")
    report.append(f"- 止损位：{arbitrage_result['ta_term_signal'].stop_loss}")
    report.append(f"- 信号强度：{arbitrage_result['ta_term_signal'].signal_strength}")
    report.append(f"- 驱动因素：{arbitrage_result['ta_term_signal'].driver}")
    report.append("")
    
    # 四、交易建议
    report.append("## 四、交易建议")
    report.append("")
    
    # 多腿组合
    report.append("### 多腿组合建议")
    report.append("")
    report.append(f"- 腿数：{len(arbitrage_result['multi_leg'].legs)}")
    report.append(f"- 净敞口：{arbitrage_result['multi_leg'].net_exposure}")
    report.append(f"- 总风险：{arbitrage_result['multi_leg'].total_risk}")
    report.append(f"- 预期收益：{arbitrage_result['multi_leg'].expected_return}")
    report.append(f"- 盈亏比：{arbitrage_result['multi_leg'].risk_reward_ratio}")
    report.append(f"- 置信度：{arbitrage_result['multi_leg'].confidence}")
    report.append("")
    
    # 各腿详情
    if arbitrage_result['multi_leg'].legs:
        report.append("#### 各腿详情")
        report.append("")
        for i, leg in enumerate(arbitrage_result['multi_leg'].legs):
            report.append(f"**腿{i+1}**：{leg['type']} {leg['direction']}")
            report.append(f"- 权重：{leg['weight']}")
            report.append(f"- 风险：{leg['risk']}")
            report.append(f"- 预期收益：{leg['expected_return']}")
            report.append("")
    
    # 五、风险提示
    report.append("## 五、风险提示")
    report.append("")
    report.append("1. **数据质量风险**：基本面数据可能存在延迟或不准确")
    report.append("2. **市场风险**：市场条件可能快速变化")
    report.append("3. **流动性风险**：部分品种流动性较差，注意滑点")
    report.append("4. **政策风险**：政策变化可能影响产业链逻辑")
    report.append("5. **地缘风险**：地缘事件可能颠覆现有分析框架")
    report.append("")
    
    # 六、免责声明
    report.append("## 六、免责声明")
    report.append("")
    report.append("本报告仅供参考，不构成投资建议。投资者应独立判断并承担投资风险。")
    report.append("")
    
    return "\n".join(report)


# ========== 套利信号报告 ==========

def generate_arbitrage_report(arbitrage_result: Dict) -> str:
    """
    生成套利信号报告
    
    返回：Markdown格式的套利报告
    """
    report = []
    report.append("# 聚酯链套利信号报告")
    report.append(f"\n**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # TA-EG价差
    report.append("## 一、TA-EG价差套利")
    report.append("")
    report.append(f"- 当前价差：{arbitrage_result['ta_eg_signal'].current_spread}")
    report.append(f"- 历史分位：{arbitrage_result['ta_eg_signal'].historical_percentile}")
    report.append(f"- 进场区间：{arbitrage_result['ta_eg_signal'].entry_zone}")
    report.append(f"- 目标区间：{arbitrage_result['ta_eg_signal'].target_zone}")
    report.append(f"- 止损位：{arbitrage_result['ta_eg_signal'].stop_loss}")
    report.append(f"- 信号强度：{arbitrage_result['ta_eg_signal'].signal_strength}")
    report.append(f"- 驱动因素：{arbitrage_result['ta_eg_signal'].driver}")
    report.append("")
    
    # PF-TA加工差
    report.append("## 二、PF-TA加工差套利")
    report.append("")
    report.append(f"- 当前加工差：{arbitrage_result['pf_ta_signal'].current_spread}")
    report.append(f"- 历史分位：{arbitrage_result['pf_ta_signal'].historical_percentile}")
    report.append(f"- 进场区间：{arbitrage_result['pf_ta_signal'].entry_zone}")
    report.append(f"- 目标区间：{arbitrage_result['pf_ta_signal'].target_zone}")
    report.append(f"- 止损位：{arbitrage_result['pf_ta_signal'].stop_loss}")
    report.append(f"- 信号强度：{arbitrage_result['pf_ta_signal'].signal_strength}")
    report.append(f"- 驱动因素：{arbitrage_result['pf_ta_signal'].driver}")
    report.append("")
    
    # TA月差
    report.append("## 三、TA月差套利")
    report.append("")
    report.append(f"- 当前月差：{arbitrage_result['ta_term_signal'].current_spread}")
    report.append(f"- 历史分位：{arbitrage_result['ta_term_signal'].historical_percentile}")
    report.append(f"- 进场区间：{arbitrage_result['ta_term_signal'].entry_zone}")
    report.append(f"- 目标区间：{arbitrage_result['ta_term_signal'].target_zone}")
    report.append(f"- 止损位：{arbitrage_result['ta_term_signal'].stop_loss}")
    report.append(f"- 信号强度：{arbitrage_result['ta_term_signal'].signal_strength}")
    report.append(f"- 驱动因素：{arbitrage_result['ta_term_signal'].driver}")
    report.append("")
    
    # 多腿组合
    report.append("## 四、多腿组合建议")
    report.append("")
    report.append(f"- 腿数：{len(arbitrage_result['multi_leg'].legs)}")
    report.append(f"- 净敞口：{arbitrage_result['multi_leg'].net_exposure}")
    report.append(f"- 总风险：{arbitrage_result['multi_leg'].total_risk}")
    report.append(f"- 预期收益：{arbitrage_result['multi_leg'].expected_return}")
    report.append(f"- 盈亏比：{arbitrage_result['multi_leg'].risk_reward_ratio}")
    report.append(f"- 置信度：{arbitrage_result['multi_leg'].confidence}")
    report.append("")
    
    # 各腿详情
    if arbitrage_result['multi_leg'].legs:
        report.append("### 各腿详情")
        report.append("")
        for i, leg in enumerate(arbitrage_result['multi_leg'].legs):
            report.append(f"**腿{i+1}**：{leg['type']} {leg['direction']}")
            report.append(f"- 权重：{leg['weight']}")
            report.append(f"- 风险：{leg['risk']}")
            report.append(f"- 预期收益：{leg['expected_return']}")
            report.append("")
    
    # 风险提示
    report.append("## 五、风险提示")
    report.append("")
    report.append("1. **价差风险**：价差可能继续扩大或缩小")
    report.append("2. **流动性风险**：部分品种流动性较差，注意滑点")
    report.append("3. **保证金风险**：套利交易需要足够保证金")
    report.append("4. **展期风险**：合约到期需要展期")
    report.append("")
    
    return "\n".join(report)


# ========== 主函数 ==========

def generate_reports(
    driver_result: Dict,
    chain_result: Dict,
    arbitrage_result: Dict,
    data: Dict,
    report_type: str = "full"
) -> str:
    """
    生成报告
    
    参数：
    - driver_result: 主驱动识别结果
    - chain_result: 产业链分析结果
    - arbitrage_result: 套利分析结果
    - data: 原始数据
    - report_type: 报告类型（checklist/full/arbitrage）
    
    返回：报告内容
    """
    logger.info(f"生成{report_type}报告...")
    
    if report_type == "checklist":
        report = generate_driver_checklist(driver_result)
    elif report_type == "full":
        report = generate_full_report(driver_result, chain_result, arbitrage_result, data)
    elif report_type == "arbitrage":
        report = generate_arbitrage_report(arbitrage_result)
    else:
        raise ValueError(f"不支持的报告类型：{report_type}")
    
    # 保存报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"polyester_chain_{report_type}_{timestamp}.md"
    filepath = OUTPUT_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"报告已保存到：{filepath}")
    
    return report


# ========== 测试代码 ==========

if __name__ == "__main__":
    # 模拟数据
    from driver_identification import run_driver_identification
    from chain_analysis import run_chain_analysis
    from arbitrage_signals import run_arbitrage_analysis
    
    # 测试数据
    test_data = {
        # 主驱动识别
        'px_capacity_growth': -5,
        'pta_capacity_growth': 10,
        'meg_capacity_growth': 25,
        'overseas_new_capacity': True,
        'pta_maintenance_rate': 25,
        'px_maintenance_rate': 20,
        'gasoline_crack': 35,
        'geopolitical_risk': 60,
        'anti_involution_cut': False,
        'meg_port_inventory': 82,
        'polyester_load': 83,
        'weaving_order_days': 12,
        'unit_shutdown': False,
        'pxn': 350,
        'px_operation_rate': 75,
        'pta_processing_fee': 450,
        'pta_operation_rate': 70,
        'export_impact': True,
        'coal_to_meg_profit': -100,
        'import_impact': False,
        'pf_processing_fee': 850,
        'production_cut_letter': False,
        'pr_processing_fee': 400,
        'px_change': 2.5,
        'ta_change': 1.8,
        'eg_change': 0.5,
        'pf_change': 0.2,
        'oil_price_change': 1.0,
        'ta_near_far_spread': 150,
        'eg_near_far_spread': -80,
        'pf_near_far_spread': -20,
        'old_driver': '中性',
        
        # 产业链分析
        'crude_price': 75,
        'naphtha_price': 600,
        'px_price': 900,
        'pta_price': 6000,
        'meg_operation_rate': 65,
        'pf_operation_rate': 80,
        'pr_operation_rate': 75,
        'pta_inventory_change': -8,
        'pf_inventory_change': -2,
        'pr_inventory_change': 1,
        'pta_profit_change': 50,
        'pf_profit_change': 30,
        
        # 套利分析
        'ta_price': 6000,
        'eg_price': 4500,
        'ta_eg_spread_percentile': 25,
        'pf_price': 7000,
        'pf_ta_spread_percentile': 30,
        'pf_operation_rate': 80,
        'ta_near_price': 6000,
        'ta_far_price': 5800,
        'ta_spread_percentile': 40,
        'ta_eg_spread': 1500,
        'pf_ta_spread': 1000,
        'ta_spread': 200,
    }
    
    # 运行分析
    driver_result = run_driver_identification(test_data)
    chain_result = run_chain_analysis(test_data)
    arbitrage_result = run_arbitrage_analysis(test_data)
    
    # 生成报告
    checklist_report = generate_reports(driver_result, chain_result, arbitrage_result, test_data, "checklist")
    full_report = generate_reports(driver_result, chain_result, arbitrage_result, test_data, "full")
    arbitrage_report = generate_reports(driver_result, chain_result, arbitrage_result, test_data, "arbitrage")
    
    print("=" * 50)
    print("报告生成完成")
    print("=" * 50)
    print(f"主驱动诊断清单：{len(checklist_report)}字符")
    print(f"完整分析报告：{len(full_report)}字符")
    print(f"套利信号报告：{len(arbitrage_report)}字符")
