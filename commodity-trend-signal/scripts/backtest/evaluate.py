# -*- coding: utf-8 -*-
"""量化回测框架 v1.0（commodity版）— 历史信号回放 + 绩效评估 + 权重优化

期货版与ETF版的差异：
  1. 数据源: MultiSourceAdapter (TqSDK/交易所/东方财富/AKShare)
  2. 评分参数: calculate_composite_score 需传 term_basis
  3. 品种分组: 工业品 vs 农产品（替代ETF的金融+科技 vs 周期+消费）

用法:
    python -m scripts.backtest.evaluate --days 250 --forward 5
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from collections import defaultdict
from typing import List, Dict

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT_SKILLS = os.path.dirname(SKILL_DIR)  # ~/.workbuddy/skills/
FDS_SCRIPTS = os.path.join(PARENT_SKILLS, 'futures-data-search', 'scripts')
# 强制添加路径（兼容 python -c 模式）
for p in [SKILL_DIR, FDS_SCRIPTS]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
# 最后兜底：已知路径
KNOWN_FDS = r'C:\Users\yangd\.workbuddy\skills\futures-data-search\scripts'
if KNOWN_FDS not in sys.path:
    sys.path.insert(0, KNOWN_FDS)

try:
    from scripts.symbols import ALL_SYMBOLS, ALL_PIDS
    from scripts.config import CONFIG_MANAGER
    from scripts.indicators import _compute_indicators_numpy
    from scripts.early_signal import inject_early_signals_to_tech
    from scripts.scoring_system import calculate_composite_score, WL1, WL2, WL3, WL4
except ImportError:
    from symbols import ALL_SYMBOLS, ALL_PIDS
    from config import CONFIG_MANAGER
    from indicators import _compute_indicators_numpy
    from early_signal import inject_early_signals_to_tech
    from scoring_system import calculate_composite_score, WL1, WL2, WL3, WL4


# ── 期货品种分组（用于交叉验证）──
# 工业品：黑色(螺纹钢RB/热卷HC/铁矿I/焦煤JM/焦炭J/硅铁SF/锰硅SM)
#         + 有色(CU/AL/ZN/PB/NI/SN) + 能化(SC/FU/TA/EG/MA/PP/PE/PVC/EB)
INDUSTRIAL_PIDS = {
    # 黑色
    'RB', 'HC', 'I', 'JM', 'J', 'SF', 'SM',
    # 有色
    'CU', 'AL', 'ZN', 'PB', 'NI', 'SN', 'SS',
    # 能化
    'SC', 'FU', 'LU', 'BU', 'TA', 'EG', 'MA', 'PP', 'L', 'V', 'EB',
    'PG', 'UR', 'SA', 'PF', 'PX', 'SH',
}

# 农产品：豆类(A/B/M/Y) + 油脂(OI/P) + 软商品(SR/CF/RU) + 玉米/淀粉/鸡蛋/生猪
AGRICULTURE_PIDS = {
    'A', 'B', 'M', 'Y', 'P', 'OI', 'RM', 'PK',
    'SR', 'CF', 'RU', 'NR', 'C', 'CS', 'JD', 'LH',
    'AP', 'CJ', 'JQ',
}


def collect_data(days: int = 250) -> dict:
    """从 MultiSourceAdapter 采集全品种历史K线。"""
    from multi_source_adapter import MultiSourceAdapter

    print(f"\n{'='*50}")
    print(f"[采集] MultiSourceAdapter — 期货回测数据 (days={days})")
    print(f"{'='*50}")

    adapter = MultiSourceAdapter()
    all_data = {}

    for i, (sym, name) in enumerate(ALL_SYMBOLS):
        print(f"  [{i+1}/{len(ALL_SYMBOLS)}] {sym} {name}...", end=' ', flush=True)
        try:
            resp = adapter.get_kline(variety=sym, days=days)
            if isinstance(resp, dict) and resp.get('success'):
                klines = resp['data']
                valid = [r for r in klines if r.get('date','') and r.get('volume',0) > 0]
                if len(valid) >= 60:
                    all_data[sym] = {'name': name, 'klines': valid}
                    print(f"OK ({len(valid)}根K线)")
                else:
                    print(f"SKIP (仅{len(valid)}根)")
            else:
                print(f"SKIP (采集失败)")
        except Exception as e:
            print(f"SKIP ({e})")
        time.sleep(0.05)

    print(f"\n  完成: {len(all_data)}/{len(ALL_SYMBOLS)}")
    return all_data


def replay_scores(all_data: dict, min_bars: int = 60, step: int = 5) -> List[dict]:
    """逐日回放评分（无需 collector，仅用K线数据）。"""
    print(f"\n{'='*50}")
    print(f"[回放] 逐日评分 (step={step})")
    print(f"{'='*50}")

    import pandas as pd
    import numpy as np
    all_scores = []
    skipped = 0

    for sym, data in all_data.items():
        klines = data['klines']
        n = len(klines)
        if n < min_bars:
            skipped += 1
            continue

        for end in range(min_bars, n, step):
            try:
                window = klines[:end+1]
                df = pd.DataFrame({k: [float(r[k]) for r in window]
                                   for k in ['open', 'high', 'low', 'close']})
                df['volume'] = [float(r.get('volume', 0)) for r in window]

                tech = _compute_indicators_numpy(df, sym)
                price = tech.get('last_price', float(df['close'].iloc[-1]))
                sym_scoring = {'last_price': price, 'open_interest': tech.get('open_interest', 0)}
                kline_closes = df['close'].tolist()
                sc = calculate_composite_score(tech, sym_scoring, 0, kline_closes, None)

                direction = 'bull' if sc['direction'] == 'BUY' else 'bear'
                s = 1 if direction == 'bull' else -1
                all_scores.append({
                    'symbol': sym, 'name': data.get('name', ''),
                    'date': window[-1]['date'],
                    'total': sc['total'] * s,
                    'abs_total': sc['total'],
                    'grade': sc['grade'],
                    'direction': direction,
                    'l1': sc['L1_score'], 'l2': sc['L2_score'],
                    'l3': sc['L3_score'], 'l4': sc['L4_score'],
                    'veto': sc['veto_score'],
                    'adx': round(tech.get('ADX', 0), 1),
                    'rsi': round(tech.get('RSI14', 0), 1),
                    'stage': sc['maturity']['stage'],
                    'price': round(price, 1),
                })
            except Exception:
                continue

    print(f"  完成: {len(all_scores)} 信号 (跳过{skipped}品种)")
    return all_scores


def evaluate_performance(scores: List[dict], forward_days: int = 5) -> dict:
    """评估各等级信号的后N日收益率。"""
    print(f"\n{'='*50}")
    print(f"[评估] 后{forward_days}日收益率分析")
    print(f"{'='*50}")

    by_sym = defaultdict(list)
    for s in scores:
        by_sym[s['symbol']].append(s)
    for k in by_sym:
        by_sym[k].sort(key=lambda x: x['date'])

    results = []
    for sym, group in by_sym.items():
        for i, sig in enumerate(group):
            if i + forward_days >= len(group):
                break
            fr = group[i+forward_days]['price'] / group[i]['price'] - 1
            results.append({'grade': sig['grade'], 'forward_return': fr * 100, 'win': fr > 0})

    by_grade = defaultdict(lambda: {'count': 0, 'wins': 0, 'returns': []})
    for r in results:
        g = r['grade']
        by_grade[g]['count'] += 1
        if r['win']: by_grade[g]['wins'] += 1
        by_grade[g]['returns'].append(r['forward_return'])

    grade_stats = {}
    for grade in ['STRONG','WATCH','WEAK','NOISE']:
        g = by_grade[grade]
        n = g['count']
        if n == 0:
            grade_stats[grade] = {'count': 0}; continue
        wr = g['wins'] / n * 100
        ar = sum(g['returns']) / n
        gains = sum(r for r in g['returns'] if r > 0)
        losses = abs(sum(r for r in g['returns'] if r < 0))
        pf = gains / losses if losses > 0 else float('inf')
        grade_stats[grade] = {'count': n, 'win_rate': round(wr,1), 'avg_return': round(ar,2),
                              'profit_factor': round(pf,2)}
        print(f"  {grade:>7}: {n:>4}次 胜率{wr:>5.1f}%  均收益{ar:>+5.2f}%  盈亏比{pf:>4.2f}")

    print(f"\n  总样本: {len(results)}")
    return {'by_grade': grade_stats, 'summary': {'total_signals': len(results), 'forward_days': forward_days}}


def main():
    parser = argparse.ArgumentParser(description='期货趋势信号量化回测 v1.0')
    parser.add_argument('--days', type=int, default=250)
    parser.add_argument('--forward', type=int, default=5)
    parser.add_argument('--step', type=int, default=5)
    parser.add_argument('--mode', default='full', choices=['collect','eval','full'])
    args = parser.parse_args()

    all_data = collect_data(days=args.days)
    scores = replay_scores(all_data, step=args.step)

    if args.mode in ('eval','full'):
        stats = evaluate_performance(scores, forward_days=args.forward)
        out = os.path.join(SKILL_DIR, 'scripts', 'backtest', 'results')
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, f'backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(path, 'w') as f:
            json.dump({'performance': stats, 'total': len(scores)}, f, ensure_ascii=False, indent=2)
        print(f"\n结果: {path}")

    print(f"\n✅ 回测完成")


if __name__ == '__main__':
    main()
