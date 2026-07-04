#!/usr/bin/env python3
"""
L1-L4权重网格搜索（commodity版）+ FactorEngine式交叉验证

期货品种分组:
  组A: 工业品 (黑色+有色+能化)
  组B: 农产品 (豆类+油脂+软商品)

用法:
    python -m scripts.backtest.optimize_weights          # 交叉验证(默认)
    python -m scripts.backtest.optimize_weights --single  # 单组全品种
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT_SKILLS = os.path.dirname(SKILL_DIR)
FDS_SCRIPTS = os.path.join(PARENT_SKILLS, 'futures-data-search', 'scripts')
for p in [SKILL_DIR, FDS_SCRIPTS]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
KNOWN_FDS = r'C:\Users\yangd\.workbuddy\skills\futures-data-search\scripts'
if KNOWN_FDS not in sys.path:
    sys.path.insert(0, KNOWN_FDS)

import numpy as np
import pandas as pd
from collections import defaultdict

try:
    from scripts.symbols import ALL_SYMBOLS
    from scripts.indicators import _compute_indicators_numpy
    from scripts.scoring_system import calculate_composite_score, WL1, WL2, WL3, WL4
except ImportError:
    from symbols import ALL_SYMBOLS
    from indicators import _compute_indicators_numpy
    from scoring_system import calculate_composite_score, WL1, WL2, WL3, WL4

# 期货品种分组
INDUSTRIAL_PIDS = {
    'RB','HC','I','JM','J','SF','SM',  # 黑色
    'CU','AL','ZN','PB','NI','SN','SS',  # 有色
    'SC','FU','LU','BU','TA','EG','MA','PP','L','V','EB',  # 能化
    'PG','UR','SA','PF','PX','SH',
}
AGRICULTURE_PIDS = {
    'A','B','M','Y','P','OI','RM','PK',  # 豆类油脂
    'SR','CF','RU','NR',  # 软商品
    'C','CS','JD','LH',  # 养殖
    'AP','CJ','JQ',  # 其他
}

INDUSTRIAL_SYMBOLS = [(s,n) for s,n in ALL_SYMBOLS if s in INDUSTRIAL_PIDS]
AGRICULTURE_SYMBOLS = [(s,n) for s,n in ALL_SYMBOLS if s in AGRICULTURE_PIDS]


def score_with_weights(sym, klines, w1, w2, w3, w4):
    """用指定权重评分。"""
    import pandas as pd
    df = pd.DataFrame({k: [float(r[k]) for r in klines] for k in ['open','high','low','close']})
    df['volume'] = [float(r.get('volume',0)) for r in klines]
    tech = _compute_indicators_numpy(df, sym)
    price = tech.get('last_price', float(df['close'].iloc[-1]))
    from scripts.scoring_system import calculate_composite_score as cs
    old = (WL1, WL2, WL3, WL4)
    import scripts.scoring_system as ss
    ss.WL1, ss.WL2, ss.WL3, ss.WL4 = w1, w2, w3, w4
    sc = cs(tech, {'last_price': price, 'open_interest': tech.get('open_interest',0)},
            0, df['close'].tolist(), None)
    ss.WL1, ss.WL2, ss.WL3, ss.WL4 = old
    return sc


def generate_grid():
    combos = []
    for l1 in range(30, 55, 5):
        for l2 in range(20, 40, 5):
            for l3 in range(10, 30, 5):
                l4 = 100 - l1 - l2 - l3
                if l4 < 5 or l4 > 25: continue
                if not (l1 >= l2 >= l3 >= l4): continue
                combos.append({'L1':l1,'L2':l2,'L3':l3,'L4':l4})
    return combos


def run_optimization(symbols: list = None, days: int = 180):
    """运行单组权重搜索。"""
    from multi_source_adapter import MultiSourceAdapter
    print(f"\n{'='*50}")
    print(f"权重网格搜索 ({len(symbols)}品种)")
    print(f"{'='*50}")

    adapter = MultiSourceAdapter()
    etf_all = {}
    for sym, name in (symbols or ALL_SYMBOLS):
        resp = adapter.get_kline(variety=sym, days=days)
        if isinstance(resp,dict) and resp.get('success'):
            klines = [r for r in resp['data'] if r.get('volume',0) > 0]
            if len(klines) >= 60:
                etf_all[sym] = {'klines': klines, 'name': name}
                print(f"  {sym}: {len(klines)}根")
        time.sleep(0.05)

    if not etf_all: return
    combos = generate_grid()
    print(f"  搜索 {len(combos)} 组合")

    # 基准
    bl = {}
    for sym, d in etf_all.items():
        sc = score_with_weights(sym, d['klines'], 40, 30, 20, 10)
        bl[sym] = {'total': sc['total'], 'grade': sc['grade']}
    bl_s = sum(1 for v in bl.values() if v['grade']=='STRONG')
    bl_w = sum(1 for v in bl.values() if v['grade']=='WATCH')

    results = []
    for c in combos:
        scores = {}
        for sym, d in etf_all.items():
            sc = score_with_weights(sym, d['klines'], c['L1'], c['L2'], c['L3'], c['L4'])
            scores[sym] = sc
        sc = sum(1 for s in scores.values() if s['grade']=='STRONG')
        wc = sum(1 for s in scores.values() if s['grade']=='WATCH')
        results.append({'L1':c['L1'],'L2':c['L2'],'L3':c['L3'],'L4':c['L4'],
                        'STRONG':sc,'WATCH':wc,
                        'sr':round((sc+wc)/max(len(scores),1),3),
                        'sw':sc*1.5+wc})

    results.sort(key=lambda x: x['sw'], reverse=True)
    print(f"\n[Top10]")
    print(f"{'L1':>3} {'L2':>3} {'L3':>3} {'L4':>3}  {'STRONG':>6} {'WATCH':>5} {'信噪比':>6}")
    print("-"*35)
    for r in results[:10]:
        print(f"{r['L1']:>3} {r['L2']:>3} {r['L3']:>3} {r['L4']:>3}  "
              f"{r['STRONG']:>6} {r['WATCH']:>5} {r['sr']:>6.1%}")
    print(f"\n[基准] 40/30/20/10 => STRONG:{bl_s} WATCH:{bl_w}")
    return results


def run_cross_validation(days: int = 180):
    """交叉验证：工业品 vs 农产品。"""
    print(f"\n{'='*60}")
    print(f"交叉验证: 工业品({len(INDUSTRIAL_SYMBOLS)}) vs 农产品({len(AGRICULTURE_SYMBOLS)})")
    print(f"{'='*60}")

    ra = run_optimization(symbols=INDUSTRIAL_SYMBOLS, days=days) or []
    rb = run_optimization(symbols=AGRICULTURE_SYMBOLS, days=days) or []

    top5_a = {(r['L1'],r['L2'],r['L3'],r['L4']):r for r in ra[:5]}
    top5_b = {(r['L1'],r['L2'],r['L3'],r['L4']):r for r in rb[:5]}

    common = set(top5_a.keys()) & set(top5_b.keys())
    if common:
        print(f"\n[审计通过] 两组交叉一致的权重:")
        for w in sorted(common, key=lambda x: x[0], reverse=True):
            print(f"  L1={w[0]} L2={w[1]} L3={w[2]} L4={w[3]}")

    combined = defaultdict(float)
    for r in ra: combined[(r['L1'],r['L2'],r['L3'],r['L4'])] += r['sw']
    for r in rb: combined[(r['L1'],r['L2'],r['L3'],r['L4'])] += r['sw']
    ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)

    print(f"\n[综合排名 Top10]")
    for i, ((l1,l2,l3,l4), sc) in enumerate(ranked[:10]):
        ia = (l1,l2,l3,l4) in top5_a
        ib = (l1,l2,l3,l4) in top5_b
        tag = "★" if ia and ib else ("A" if ia else("B" if ib else ""))
        print(f"  {l1:>3} {l2:>3} {l3:>3} {l4:>3}  {sc:>5.1f}  {tag}")

    print(f"\n[审计] 当前40/30/20/10 跨组分: {combined.get((40,30,20,10),0):.1f}")
    return ranked


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--days', type=int, default=180)
    p.add_argument('--single', action='store_true', help='单组全品种')
    args = p.parse_args()
    if args.single:
        run_optimization(days=args.days)
    else:
        run_cross_validation(days=args.days)
