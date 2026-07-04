#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚酯链投研分析主运行脚本 v1.0.0

功能：
1. 数据获取
2. 主驱动识别
3. 产业链分析
4. 套利信号识别
5. 报告生成

用法：
    python run_pipeline.py                    # 运行完整流程
    python run_pipeline.py --driver-only      # 仅运行主驱动识别
    python run_pipeline.py --arbitrage-only   # 仅运行套利信号识别
    python run_pipeline.py --report           # 生成完整报告
    python run_pipeline.py --checklist        # 生成主驱动诊断清单
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from driver_identification import run_driver_identification
from chain_analysis import run_chain_analysis
from arbitrage_signals import run_arbitrage_analysis
from report_generator import generate_reports

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_data() -> dict:
    """
    加载数据
    
    这里应该实现实际的数据获取逻辑，包括：
    - 交易所数据
    - 基本面数据
    - 技术指标数据
    
    为简化示例，这里返回模拟数据
    """
    logger.info("加载数据...")
    
    # 模拟数据
    data = {
        # 主驱动识别数据
        'px_capacity_growth': -5,  # PX产能收缩
        'pta_capacity_growth': 10,  # PTA产能温和增长
        'meg_capacity_growth': 25,  # MEG产能扩张
        'overseas_new_capacity': True,  # 海外新装置
        
        'pta_maintenance_rate': 25,  # PTA检修率高
        'px_maintenance_rate': 20,  # PX检修率高
        'gasoline_crack': 35,  # 调油逻辑强
        'geopolitical_risk': 60,  # 地缘风险中等
        'anti_involution_cut': False,  # 无反内卷减产
        
        'meg_port_inventory': 82,  # MEG港口库存偏低
        'polyester_load': 83,  # 聚酯负荷中等
        'weaving_order_days': 12,  # 织造订单中等
        'unit_shutdown': False,  # 无装置临停
        
        'pxn': 350,  # PXN偏高
        'px_operation_rate': 75,  # PX开工率偏低
        'pta_processing_fee': 450,  # PTA加工费中等
        'pta_operation_rate': 70,  # PTA开工率偏低
        'export_impact': True,  # 有出口影响
        'coal_to_meg_profit': -100,  # 煤制MEG利润中等
        'import_impact': False,  # 无进口影响
        'pf_processing_fee': 850,  # PF加工费中等
        'production_cut_letter': False,  # 无减产函
        'pr_processing_fee': 400,  # PR加工费中等
        
        'px_change': 2.5,  # PX涨幅
        'ta_change': 1.8,  # TA涨幅
        'eg_change': 0.5,  # EG涨幅
        'pf_change': 0.2,  # PF涨幅
        'oil_price_change': 1.0,  # 油价涨幅
        'ta_near_far_spread': 150,  # TA近远月价差（Back）
        'eg_near_far_spread': -80,  # EG近远月价差（Contango）
        'pf_near_far_spread': -20,  # PF近远月价差
        
        'old_driver': '中性',
        
        # 产业链分析数据
        'crude_price': 75,  # 原油价格（美元/桶）
        'naphtha_price': 600,  # 石脑油价格（美元/吨）
        'px_price': 900,  # PX价格（美元/吨）
        'pta_price': 6000,  # PTA价格（元/吨）
        
        'meg_operation_rate': 65,  # MEG开工率
        'pf_operation_rate': 80,  # PF开工率
        'pr_operation_rate': 75,  # PR开工率
        
        'pta_inventory_change': -8,  # PTA库存变化
        'pf_inventory_change': -2,  # PF库存变化
        'pr_inventory_change': 1,  # PR库存变化
        
        'pta_profit_change': 50,  # PTA利润变化
        'pf_profit_change': 30,  # PF利润变化
        
        # 套利分析数据
        'ta_price': 6000,  # TA价格
        'eg_price': 4500,  # EG价格
        'ta_eg_spread_percentile': 25,  # 历史分位
        
        'pf_price': 7000,  # PF价格
        'pf_ta_spread_percentile': 30,  # 历史分位
        
        'ta_near_price': 6000,  # TA近月价格
        'ta_far_price': 5800,  # TA远月价格
        'ta_spread_percentile': 40,  # 历史分位
        
        'ta_eg_spread': 1500,  # TA-EG价差
        'pf_ta_spread': 1000,  # PF-TA加工差
        'ta_spread': 200,  # TA月差
    }
    
    logger.info(f"数据加载完成，共{len(data)}个字段")
    
    return data


def run_full_pipeline(data: dict) -> dict:
    """
    运行完整流程
    
    返回：包含所有结果的字典
    """
    logger.info("=" * 50)
    logger.info("开始运行聚酯链投研分析完整流程")
    logger.info("=" * 50)
    
    start_time = time.time()
    
    # 1. 主驱动识别
    logger.info("步骤1：主驱动识别")
    driver_result = run_driver_identification(data)
    
    # 2. 产业链分析
    logger.info("步骤2：产业链分析")
    chain_result = run_chain_analysis(data)
    
    # 3. 套利信号识别
    logger.info("步骤3：套利信号识别")
    arbitrage_result = run_arbitrage_analysis(data)
    
    # 4. 报告生成
    logger.info("步骤4：报告生成")
    
    # 生成主驱动诊断清单
    checklist_report = generate_reports(
        driver_result, chain_result, arbitrage_result, data, "checklist"
    )
    
    # 生成完整分析报告
    full_report = generate_reports(
        driver_result, chain_result, arbitrage_result, data, "full"
    )
    
    # 生成套利信号报告
    arbitrage_report = generate_reports(
        driver_result, chain_result, arbitrage_result, data, "arbitrage"
    )
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    logger.info("=" * 50)
    logger.info(f"完整流程执行完成，耗时{execution_time:.2f}秒")
    logger.info("=" * 50)
    
    return {
        'driver_result': driver_result,
        'chain_result': chain_result,
        'arbitrage_result': arbitrage_result,
        'reports': {
            'checklist': checklist_report,
            'full': full_report,
            'arbitrage': arbitrage_report
        },
        'execution_time': execution_time
    }


def run_driver_only(data: dict) -> dict:
    """
    仅运行主驱动识别
    
    返回：主驱动识别结果
    """
    logger.info("仅运行主驱动识别...")
    
    start_time = time.time()
    driver_result = run_driver_identification(data)
    end_time = time.time()
    
    logger.info(f"主驱动识别完成，耗时{end_time - start_time:.2f}秒")
    
    return driver_result


def run_arbitrage_only(data: dict) -> dict:
    """
    仅运行套利信号识别
    
    返回：套利信号识别结果
    """
    logger.info("仅运行套利信号识别...")
    
    start_time = time.time()
    arbitrage_result = run_arbitrage_analysis(data)
    end_time = time.time()
    
    logger.info(f"套利信号识别完成，耗时{end_time - start_time:.2f}秒")
    
    return arbitrage_result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="聚酯链投研分析主运行脚本")
    parser.add_argument("--driver-only", action="store_true", help="仅运行主驱动识别")
    parser.add_argument("--arbitrage-only", action="store_true", help="仅运行套利信号识别")
    parser.add_argument("--report", action="store_true", help="生成完整报告")
    parser.add_argument("--checklist", action="store_true", help="生成主驱动诊断清单")
    
    args = parser.parse_args()
    
    # 加载数据
    data = load_data()
    
    # 根据参数运行不同流程
    if args.driver_only:
        result = run_driver_only(data)
        print("\n" + "=" * 50)
        print("主驱动识别结果")
        print("=" * 50)
        print(f"主驱动：{result.primary_driver}")
        print(f"驱动强度：{result.driver_strength}")
        print(f"置信度：{result.confidence}")
        print(f"综合得分：{result.total_score:.1f}")
        
    elif args.arbitrage_only:
        result = run_arbitrage_only(data)
        print("\n" + "=" * 50)
        print("套利信号识别结果")
        print("=" * 50)
        print(f"TA-EG信号：{result['ta_eg_signal'].signal_strength}")
        print(f"PF-TA信号：{result['pf_ta_signal'].signal_strength}")
        print(f"TA月差信号：{result['ta_term_signal'].signal_strength}")
        print(f"多腿组合置信度：{result['multi_leg'].confidence}")
        
    elif args.report:
        result = run_full_pipeline(data)
        print("\n" + "=" * 50)
        print("报告生成完成")
        print("=" * 50)
        print(f"执行时间：{result['execution_time']:.2f}秒")
        print(f"主驱动：{result['driver_result'].primary_driver}")
        print(f"产业链平衡：{result['chain_result'].summary['overall_balance']}")
        print(f"套利腿数：{len(result['arbitrage_result']['multi_leg'].legs)}")
        
    elif args.checklist:
        driver_result = run_driver_only(data)
        chain_result = run_chain_analysis(data)
        arbitrage_result = run_arbitrage_analysis(data)
        
        checklist_report = generate_reports(
            driver_result, chain_result, arbitrage_result, data, "checklist"
        )
        
        print("\n" + "=" * 50)
        print("主驱动诊断清单")
        print("=" * 50)
        print(checklist_report)
        
    else:
        # 默认运行完整流程
        result = run_full_pipeline(data)
        
        print("\n" + "=" * 50)
        print("聚酯链投研分析完成")
        print("=" * 50)
        print(f"执行时间：{result['execution_time']:.2f}秒")
        print(f"\n【主驱动识别】")
        print(f"主驱动：{result['driver_result']['driver_score'].primary_driver}")
        print(f"驱动强度：{result['driver_result']['driver_score'].driver_strength}")
        print(f"置信度：{result['driver_result']['driver_score'].confidence}")
        print(f"综合得分：{result['driver_result']['driver_score'].total_score:.1f}")
        
        print(f"\n【产业链分析】")
        print(f"成本驱动：{result['chain_result']['summary']['cost_driver']}")
        print(f"整体供需：{result['chain_result']['summary']['overall_balance']}")
        print(f"库存周期：{result['chain_result']['summary']['cycle_phase']}")
        print(f"利润中心：{result['chain_result']['summary']['profit_center']}")
        
        print(f"\n【套利信号】")
        print(f"TA-EG信号：{result['arbitrage_result']['ta_eg_signal'].signal_strength}")
        print(f"PF-TA信号：{result['arbitrage_result']['pf_ta_signal'].signal_strength}")
        print(f"TA月差信号：{result['arbitrage_result']['ta_term_signal'].signal_strength}")
        print(f"多腿组合：{len(result['arbitrage_result']['multi_leg'].legs)}腿")
        
        print(f"\n【报告生成】")
        print(f"主驱动诊断清单：{len(result['reports']['checklist'])}字符")
        print(f"完整分析报告：{len(result['reports']['full'])}字符")
        print(f"套利信号报告：{len(result['reports']['arbitrage'])}字符")


if __name__ == "__main__":
    main()
