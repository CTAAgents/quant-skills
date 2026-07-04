#!/usr/bin/env python3
"""
快速权重网格搜索 v2（commodity版）— 一次指标计算，多次权重评分

优化点：先对所有品种计算一次技术指标（~2s/品种），
缓存 tech dict，然后对每个权重组合只跑 scoring（~0.01s/品种）。
预期：62品种 × 1次指标 + 33组合 × 62品种 × 评分 ≈ 2分钟
"""

import sys, os, json, time
sys.path.insert(0, r'C:\Users\yangd\.workbuddy\skills\futures-data-search\scripts')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from multi_source_adapter import MultiSourceAdapter
from symbols import ALL_SYMBOLS
from indicators import _compute_indicators_numpy
from scoring_system import calculate_composite_score

# ── 权重组合生成 ──
def generate_grid():
    combos = []
    for l1 in range(30, 55, 5):
        for l2 in range(20, 40, 5):
            for l3 in range(10, 30, 5):
                l4 = 100 - l1 - l2 - l3
                if l4 < 5 or l4 > 25: continue
                if not (l1 >= l2 >= l3 >= l4): continue
                combos.append((l1, l2, l3, l4))
    return combos

# ── 一次采集 + 一次指标计算 ──
print("Phase 1: 数据采集 + 指标计算...")
a = MultiSourceAdapter()
cache = {}
for i, (sym, name) in enumerate(ALL_SYMBOLS):
    resp = a.get_kline(variety=sym, days=120)
    if not (isinstance(resp, dict) and resp.get('success')):
        continue
    klines = [r for r in resp['data'] if r.get('volume', 0) > 0]
    if len(klines) < 60:
        continue
    df = pd.DataFrame({k: [float(r[k]) for r in klines] for k in ['open', 'high', 'low', 'close']})
    df['volume'] = [float(r.get('volume', 0)) for r in klines]
    tech = _compute_indicators_numpy(df, sym)
    price = tech.get('last_price', float(df['close'].iloc[-1]))
    cache[sym] = {
        'tech': tech,
        'sym_dict': {'last_price': price, 'open_interest': tech.get('open_interest', 0)},
        'kline_closes': df['close'].tolist(),
    }
    if (i + 1) % 15 == 0:
        print(f"  [{i+1}/{len(ALL_SYMBOLS)}] {len(cache)} cached")

print(f"  Cached: {len(cache)} symbols")

# ── 基准 ├──
import scripts.scoring_system as ss
combos = generate_grid()
print(f"combinations: {len(combos)}")

print("\nPhase 2: 基准 40/30/20/10...")
bl = {'STRONG': 0, 'WATCH': 0, 'WEAK': 0, 'NOISE': 0}
for d in cache.values():
    sc = calculate_composite_score(d['tech'], d['sym_dict'], 0, d['kline_closes'], None)
    bl[sc['grade']] += 1
print(f"  {bl}")

# ── 网格搜索（只需重加权）──
print("\nPhase 3: 网格搜索...")
results = []
t0 = time.time()

for i, (l1, l2, l3, l4) in enumerate(combos):
    old = (ss.WL1, ss.WL2, ss.WL3, ss.WL4)
    ss.WL1, ss.WL2, ss.WL3, ss.WL4 = l1, l2, l3, l4

    gs = {'STRONG': 0, 'WATCH': 0, 'WEAK': 0, 'NOISE': 0}
    for d in cache.values():
        sc = calculate_composite_score(d['tech'], d['sym_dict'], 0, d['kline_closes'], None)
        gs[sc['grade']] += 1

    ss.WL1, ss.WL2, ss.WL3, ss.WL4 = old

    results.append({
        'L1': l1, 'L2': l2, 'L3': l3, 'L4': l4,
        'STRONG': gs['STRONG'], 'WATCH': gs['WATCH'],
        'WEAK': gs['WEAK'], 'NOISE': gs['NOISE'],
    })
    if (i + 1) % 5 == 0:
        elapsed = time.time() - t0
        print(f"  [{i+1}/{len(combos)}] L1={l1} L2={l2} L3={l3} L4={l4} "
              f"→ S={gs['STRONG']} W={gs['WATCH']} ({elapsed:.0f}s)")

# ── 结果 ──
results.sort(key=lambda x: x['STRONG'] * 1.5 + x['WATCH'], reverse=True)

print(f"\n{'='*50}")
print(f"TOP 10 权重组合")
print(f"{'='*50}")
print(f"{'L1':>3} {'L2':>3} {'L3':>3} {'L4':>3}  "
      f"{'STRONG':>6} {'WATCH':>5} {'WEAK':>4} {'NOISE':>5}  {'得分':>5}")
print("-" * 45)
for r in results[:10]:
    s = r['STRONG'] * 1.5 + r['WATCH']
    print(f"{r['L1']:>3} {r['L2']:>3} {r['L3']:>3} {r['L4']:>3}  "
          f"{r['STRONG']:>6} {r['WATCH']:>5} {r['WEAK']:>4} {r['NOISE']:>5}  {s:>5.1f}")

print(f"\n基准 40/30/20/10: {bl}")
elapsed = time.time() - t0
print(f"总耗时: {elapsed:.0f}s")

# 保存
out_dir = os.path.join(os.path.dirname(__file__), 'backtest', 'results')
os.makedirs(out_dir, exist_ok=True)
path = os.path.join(out_dir, 'optimize_weights_v2.json')
with open(path, 'w') as f:
    json.dump({'baseline': bl, 'top10': results[:10], 'all': results}, f, ensure_ascii=False, indent=2)
print(f"结果已保存: {path}")
