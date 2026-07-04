#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品期货趋势信号发现管道 v2.13
运行完整管道：数据采集 → 期限结构/基差 → L1-L4四层打分 → 信号筛选 → 交易方案 → 报告
"""

import sys
import os
import json
import time
from datetime import datetime

# 添加skill根目录到路径（scripts/的父目录）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collect_data import collect_all_data, FUTURES_SYMBOLS
from scripts.scoring_system import calculate_composite_score
from scripts.signal_screener import screen_signals
from scripts.trade_plan import generate_trade_plan, rank_all_candidates
from scripts.report import generate_markdown_report

def run_pipeline():
    """运行完整管道"""
    print("=" * 60)
    print("商品期货趋势信号发现管道 v2.13 (L1-L4四层架构)")
    print("=" * 60)
    
    # 1. 数据采集（已包含技术指标）
    print("\n[1/6] 数据采集...")
    start_time = time.time()
    
    # 数据源自动降级：交易所官方API → TqSdk → AKShare
    # 执行时间为20:30，交易所日线数据已于17:00-18:00前更新完毕，优先使用官方数据
    data_source = 'auto'
    print(f"数据源: {data_source} (自动降级：交易所官方API > TqSdk > AKShare)")
    
    # 采集数据
    market_data = collect_all_data(source=data_source)
    symbols_data = market_data.get('symbols', [])
    print(f"采集到 {len(symbols_data)} 个品种数据")
    
    if not symbols_data:
        print("错误: 无有效数据，管道终止")
        return None
    
    # 2. 获取期限结构和基差数据（期货专属）
    print("\n[2/6] 获取期限结构和基差数据...")
    term_basis_data = {}
    try:
        from scripts.term_basis import compute_term_basis
        term_basis_data = compute_term_basis(FUTURES_SYMBOLS)
        print(f"获取到 {len(term_basis_data)} 个品种的期限结构数据")
    except Exception as e:
        print(f"[WARN] 期限结构数据获取失败: {e}")
    
    # 3. L1-L4四层打分（v2.13核心）
    print("\n[3/6] L1-L4四层打分...")
    for sym in symbols_data:
        tech = sym.get('tech', {})
        pid_lower = sym['product_id'].lower()

        sym_info = {
            'last_price': sym.get('last_price', 0),
            'open_interest': sym.get('open_interest', 0)
        }

        # 使用旧的trend score作为参考（v2.13不再依赖它判断方向）
        old_trend = sym.get('trend', {})
        score_direction = old_trend.get('score', 0)

        # v2.13: 从sym中提取kline_closes（如果有的话）
        kline_closes = sym.get('kline_closes', None)

        # 获取该品种的期限结构数据
        term_basis = term_basis_data.get(pid_lower, {})

        # 计算L1-L4综合得分
        composite = calculate_composite_score(
            tech=tech,
            sym=sym_info,
            score_direction=score_direction,
            kline_closes=kline_closes,
            term_basis=term_basis
        )

        # 更新sym数据
        sym['l1_l4_score'] = composite
        sym['score'] = composite['total']
        sym['direction'] = composite['direction']
        sym['grade'] = composite['grade']
        sym['term_basis'] = term_basis

        print(f"  {sym['product_id']}: L1={composite['L1_score']}, L2={composite['L2_score']}, "
              f"L3={composite['L3_score']}, L4={composite['L4_score']}, "
              f"Veto={composite['veto_score']}, Total={composite['total']} ({composite['grade']}) "
              f"Dir={composite['direction']}")
    
    # 4. 信号筛选（使用L1-L4得分）
    print("\n[4/6] 信号筛选...")
    candidates = screen_signals(symbols_data, score_threshold=20, min_resonance=0.5)
    print(f"筛选结果: {len(candidates)} 个候选信号")
    
    if not candidates:
        print("无符合条件的信号，管道终止")
        return None
    
    # 5. 生成交易方案
    print("\n[5/6] 生成交易方案...")
    all_plans = []
    for candidate in candidates:
        try:
            # v2.13: 使用L1-L4方向判断产业链方向
            direction = candidate.get('direction', '')
            chain_direction = '空头趋势' if direction == 'SELL' else '多头趋势'
            term_basis = candidate.get('term_basis', {})
            composite_score = candidate.get('l1_l4_score', {})

            plan = generate_trade_plan(
                symbol_data={
                    'pid': candidate['product_id'],
                    'price': candidate['last_price'],
                    'score': candidate.get('score', 0),
                    'atr': candidate['tech'].get('ATR14', 0),
                    'volatility': 0.02  # 默认波动率
                },
                chain_direction=chain_direction,
                tech_data=candidate['tech'],
                term_basis=term_basis,
                composite_score=composite_score  # v2.13: 传递L1-L4得分
            )
            
            if plan['decision'] != 'HOLD':
                # 保持嵌套结构，但添加决策信息到顶层
                candidate_with_plan = {
                    **candidate,
                    'trade_plan': plan,
                    'decision': plan['decision'],
                    'recommend_score': plan['recommend_score']
                }
                all_plans.append(candidate_with_plan)
        except Exception as e:
            print(f"  ✗ {candidate['product_id']}: {str(e)}")
    
    print(f"生成交易方案: {len(all_plans)} 个有效方案")
    
    # 6. 排序和报告
    print("\n[6/6] 生成报告...")
    ranked = rank_all_candidates(all_plans)
    
    # 生成Markdown报告
    markdown_report = generate_markdown_report(
        chain_results={},  # 简化版，不包含产业链详情
        all_opportunities=all_plans,
        buy_opps=ranked['bullish_top5'],
        sell_opps=ranked['bearish_top5'],
        risk_assessments={},
        data_source=data_source
    )
    
    # 保存报告
    report_date = datetime.now().strftime('%Y-%m-%d')
    report_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'Commodities', 'Reports', '商品期货深度分析', report_date)
    os.makedirs(report_dir, exist_ok=True)
    
    report_file = os.path.join(report_dir, f'trend_signal_{datetime.now().strftime("%Y%m%d")}.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(markdown_report)
    
    print(f"\n报告已保存: {report_file}")
    print("=" * 60)
    
    return {
        'candidates': len(candidates),
        'plans': len(all_plans),
        'bullish_top5': ranked['bullish_top5'],
        'bearish_top5': ranked['bearish_top5'],
        'report_file': report_file,
        'symbols_data': symbols_data,
        'term_basis_data': term_basis_data
    }

if __name__ == '__main__':
    result = run_pipeline()
    if result:
        print(f"\n管道执行完成:")
        print(f"  候选信号: {result['candidates']}")
        print(f"  有效方案: {result['plans']}")
        print(f"  多头Top5: {len(result['bullish_top5'])}")
        print(f"  空头Top5: {len(result['bearish_top5'])}")
    else:
        print("\n管道执行失败")