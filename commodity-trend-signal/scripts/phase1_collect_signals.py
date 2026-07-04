#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品期货每日深度分析 — Phase 1: 数据采集 + 趋势信号扫描
输出：intermediate_data.json（含行情数据、技术指标、信号筛选结果、基础产业链分类）
"""

import sys, os, json, time, traceback
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

# ==================== 交易时段判断（分钟精度） ====================
def _is_trading_session(now=None) -> bool:
    """判断是否在交易时段（含分钟精度）。
    中国期货标准交易时间：
      上午 09:00-11:30 / 下午 13:30-15:00
      夜盘 21:00-02:30（次日，覆盖全部品种：大多23:00/有色01:00/贵金属原油02:30）
    """
    import datetime as _dt
    if now is None:
        now = _dt.datetime.now()
    t = now.hour * 100 + now.minute
    return (900 <= t < 1130) or (1330 <= t < 1500) or (2100 <= t <= 2359) or (0 <= t <= 230)

# ==================== 配置 ====================
REPORT_DATE = datetime.now().strftime('%Y-%m-%d')
REPORT_DATE_COMPACT = datetime.now().strftime('%Y%m%d')
DATA_BENCHMARK = datetime.now().strftime('%Y%m%d')
PHASE1_TIMEOUT = 360  # 全局超时秒数（6分钟），防止TqSDK连接循环卡死

REPORT_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "WorkBuddy", "Commodities",
    "Reports", "商品期货深度分析", REPORT_DATE
)
os.makedirs(REPORT_DIR, exist_ok=True)

print(f"{'='*60}")
print(f"Phase 1: 数据采集 + 趋势信号扫描 — {REPORT_DATE}")
print(f"数据基准日: {DATA_BENCHMARK}")
print(f"{'='*60}")

# ==================== 0: 数据源配置状态 ====================
print("\n[0] 数据源配置状态...")
try:
    import importlib.util
    fds_dir = os.path.expanduser("~/.workbuddy/skills/futures-data-search")
    dsc_path = os.path.join(fds_dir, "scripts", "data_source_config.py")
    spec = importlib.util.spec_from_file_location("dsc_mod", dsc_path)
    dsc_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dsc_mod)
    config = dsc_mod.DataSourceConfig()
    is_trading = _is_trading_session()
    print(f"  时段: {'盘中' if is_trading else '盘后'}")
    print(f"  盘中链: {' → '.join(s.value for s in config.get_priority_list(True))}")
    print(f"  盘后链: {' → '.join(s.value for s in config.get_priority_list(False))}")
except Exception as e:
    print(f"  ⚠ 数据源配置加载失败: {e}")

# ── TQ-Local 桥接检测 ──
print("\n[0b] 通达信指标桥接检测...")
tdx_available = False
try:
    from commodity_trend_signal.scripts.tdx_bridge import get_bridge
    bridge = get_bridge()
    tdx_available = bridge.available
    if tdx_available:
        print(f"  ✅ TQ-Local可用 → DMI/RSI/CCI/MACD 来自通达信实盘公式")
    else:
        print(f"  ⚠️ TQ-Local不可用 → 指标降级为numpy计算（ADX/RSI可能与通达信软件有差异）")
except Exception as e:
    print(f"  ⚠️ TQ-Local桥接加载失败 → numpy兜底: {e}")

# ==================== 1a: 数据采集 ====================
print("\n[1a] 数据采集（futures-data-search MultiSourceAdapter 统一调度）...")
step_start = time.time()

from scripts.collect_data import collect_all_data, FUTURES_SYMBOLS as FS
from scripts.scoring_system import calculate_composite_score
from scripts.signal_screener import screen_signals
from scripts.trade_plan import generate_trade_plan, rank_all_candidates
from scripts.term_basis import compute_term_basis

market_data = collect_all_data(source='auto', timeout=PHASE1_TIMEOUT)  # 数据源由 MultiSourceAdapter 统一调度，带超时保护
symbols_data = market_data.get('symbols', [])
data_source_used = market_data.get('meta', {}).get('source', 'unknown')
print(f"  ✓ 采集到 {len(symbols_data)} 个品种, 数据源: {data_source_used}")

# ==================== 1b: 期限结构 ====================
print("\n[1b] 期限结构/基差...")
term_basis_data = {}
try:
    import threading as _tb_threading
    _tb_result = [None]; _tb_exc = [None]; _tb_done = [False]
    def _tb_worker():
        try:
            _tb_result[0] = compute_term_basis(FS)
            _tb_done[0] = True
        except Exception as e:
            _tb_exc[0] = e
            _tb_done[0] = True
    _tb_t = _tb_threading.Thread(target=_tb_worker, daemon=True)
    _tb_t.start(); _tb_t.join(timeout=60)  # 期限结构最多等60秒
    if not _tb_done[0]:
        print(f"  ⚠ 期限结构计算超时(60s)，跳过")
    elif _tb_exc[0]:
        print(f"  ⚠ 期限结构失败: {_tb_exc[0]}")
    else:
        term_basis_data = _tb_result[0] or {}
        print(f"  ✓ {len(term_basis_data)} 个品种")
except Exception as e:
    print(f"  ⚠ 期限结构获取失败: {e}")

# ==================== 1c: L1-L4打分 ====================
print("\n[1c] L1-L4四层打分 + fallback...")
for sym in symbols_data:
    tech = sym.get('tech', {})
    pid_lower = sym['product_id'].lower()
    old_trend = sym.get('trend', {})
    score_direction = old_trend.get('score', 0)
    kline_closes = sym.get('kline_closes', None)
    tb = term_basis_data.get(pid_lower, {})

    composite = calculate_composite_score(
        tech=tech,
        sym={'last_price': sym.get('last_price', 0), 'open_interest': sym.get('open_interest', 0)},
        score_direction=score_direction,
        kline_closes=kline_closes,
        term_basis=tb
    )

    sym['l1_l4_score'] = composite
    sym['l1_l4_total'] = composite.get('total', 0)
    sym['l1_l4_direction'] = composite.get('direction', '')

    if composite.get('total', 0) > 0:
        sym['score'] = composite['total']
        sym['direction'] = composite['direction'] or ('BUY' if score_direction > 0 else 'SELL')
        sym['grade'] = composite['grade']
    else:
        sym['score'] = abs(score_direction)
        sym['direction'] = 'BUY' if score_direction >= 30 else ('SELL' if score_direction <= -30 else 'HOLD')
        sym['grade'] = 'WATCH' if sym['score'] >= 30 else 'WEAK' if sym['score'] >= 15 else 'NOISE'
        sym['l1_l4_note'] = 'fallback_old_score'

# ==================== 1d: 信号筛选 ====================
print("\n[1d] 信号筛选...")
candidates = screen_signals(symbols_data, score_threshold=10, min_resonance=0.3)
BUY_signals = [s for s in candidates if s.get('direction') == 'BUY']
SELL_signals = [s for s in candidates if s.get('direction') == 'SELL']
print(f"  ✓ 总候选: {len(candidates)}, 多头: {len(BUY_signals)}, 空头: {len(SELL_signals)}")

# ==================== 1e: 交易方案 ====================
print("\n[1e] 交易方案计算...")
def normalize_sym(sym):
    s = dict(sym)
    s['pid'] = s.get('product_id', s.get('pid', ''))
    s['price'] = s.get('last_price', s.get('price', 0))
    s['atr'] = s.get('atr', s.get('tech', {}).get('ATR14', 0))
    s['tech'] = s.get('tech', {})
    return s

actionable_plans = []
for sym in symbols_data:
    direction = sym.get('direction', '')
    if not direction or direction == 'HOLD':
        continue
    nsym = normalize_sym(sym)
    composite = sym.get('l1_l4_score', {})
    tech = sym.get('tech', {})
    plan = generate_trade_plan(nsym, direction, tech_data=tech, composite_score=composite)
    if plan.get('decision') != 'HOLD':
        plan['product_id'] = sym.get('product_id', '')
        plan['direction'] = direction
        plan['last_price'] = sym.get('last_price', 0)
        plan['l1_l4'] = sym.get('l1_l4_score', {})
        plan['chain'] = ''
        actionable_plans.append(plan)

BUY_ranked = sorted([p for p in actionable_plans if p.get('decision') == 'BUY'],
                    key=lambda x: x.get('recommend_score', 0), reverse=True)[:5]
SELL_ranked = sorted([p for p in actionable_plans if p.get('decision') == 'SELL'],
                     key=lambda x: x.get('recommend_score', 0), reverse=True)[:5]
all_actionable = BUY_ranked[:5] + SELL_ranked[:5]

print(f"  ✓ 有效方案: {len(actionable_plans)}")
print(f"\n  Top 信号:")
for s in all_actionable[:12]:
    dir_icon = '🟢' if s.get('decision') == 'BUY' else '🔴'
    print(f"  {dir_icon} {s.get('decision','?')} {s.get('pid','?')} 推荐={s.get('recommend_score',0):.1f} 置信度={s.get('confidence',0):.1%}")

# ==================== 基础产业链分类 ====================
print("\n[1f] 基础产业链分类...")
CHAIN_PRODUCTS = {}
classify_chain = lambda s, d: 'HOLD'
select_leader = lambda s, d: ({}, 'N/A')

try:
    # Import chain modules
    old_path = sys.path.copy()
    CHAIN_DIR = os.path.expanduser("~/.workbuddy/skills/commodity-chain-analysis")
    sys.path.insert(0, CHAIN_DIR)
    saved_mods = {}
    for key in list(sys.modules.keys()):
        if key.startswith('scripts.') or key == 'scripts':
            saved_mods[key] = sys.modules.pop(key)
    import scripts.chains as _chains
    CHAIN_PRODUCTS = _chains.CHAIN_PRODUCTS
    classify_chain = _chains.classify_chain
    select_leader = _chains.select_leader
    sys.path = old_path
    print(f"  ✓ 产业链模块导入成功 ({len(CHAIN_PRODUCTS)}条)")
except Exception as e:
    print(f"  ⚠ 产业链模块导入失败: {e}")
    sys.path = old_path

chain_results = {}
for chain_name, products in CHAIN_PRODUCTS.items():
    chain_syms = [s for s in symbols_data if s.get('product_id') in products]
    if not chain_syms:
        continue
    dc = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
    for s in chain_syms:
        dc[s.get('direction', 'HOLD')] = dc.get(s.get('direction', 'HOLD'), 0) + 1
    scores = [s.get('score', 0) for s in chain_syms]
    avg = sum(scores) / len(scores) if scores else 0
    trend = classify_chain(avg, dc) if callable(classify_chain) else 'HOLD'
    leader, lr = select_leader(chain_syms, trend) if callable(select_leader) else ({}, 'N/A')
    chain_results[chain_name] = {
        'overall_trend': trend, 'avg_score': avg, 'count': len(chain_syms),
        'leader': leader.get('product_id', 'N/A'), 'leader_price': leader.get('last_price', 0),
        'direction_counts': dc,
        'members': [s.get('product_id') for s in chain_syms]
    }
    trend_label = {'BUY':'📈','SELL':'📉','HOLD':'➡'}.get(trend, '➡')
    print(f"    {chain_name}: {trend_label} {trend} avg={avg:.1f} {dc}")

# ==================== 保存中间数据 ====================
BUY_top5 = [s for s in symbols_data if s.get('direction') == 'BUY'][:5]
SELL_top5 = [s for s in symbols_data if s.get('direction') == 'SELL'][:5]

# Build serializable candidates list (from screen_signals)
candidates_serializable = []
for s in candidates:
    c = {
        'product_id': s.get('product_id', ''),
        'product_name': s.get('product_name', ''),
        'last_price': s.get('last_price', 0),
        'open_interest': s.get('open_interest', 0),
        'direction': s.get('direction', 'HOLD'),
        'score': s.get('score', 0),
        'grade': s.get('grade', ''),
        'change_pct': s.get('change_pct', 0),
        'data_source': s.get('data_source', ''),
        'exchange': s.get('exchange', ''),
        'trend_score': s.get('trend', {}).get('score', 0),
    }
    candidates_serializable.append(c)

# Build FULL debate candidates — ALL actionable plans with full detail
# These are all symbols where direction is BUY or SELL and trade_plan succeeded
debate_candidates = []
for p in actionable_plans:
    # Find matching symbol data for additional detail
    sym_detail = next((s for s in symbols_data if s.get('product_id') == p.get('pid')), {})
    chain_name = ''
    for cname, cinfo in chain_results.items():
        if p.get('pid') in cinfo.get('members', []):
            chain_name = cname
            break
    dc = {
        'pid': p.get('pid', ''),
        'product_name': sym_detail.get('product_name', p.get('pid', '')),
        'decision': p.get('decision', 'HOLD'),
        'confidence': p.get('confidence', 0),
        'recommend_score': p.get('recommend_score', 0),
        'price': p.get('price', p.get('last_price', 0)),
        'entry_price': p.get('entry_price', 0),
        'target_price': p.get('target_price', 0),
        'stop_loss_price': p.get('stop_loss_price', 0),
        'risk_reward': p.get('risk_reward', 0),
        'position_size': p.get('position_size', 0),
        'chain': chain_name,
        'data_source': sym_detail.get('data_source', ''),
        'exchange': sym_detail.get('exchange', ''),
        'score': sym_detail.get('score', 0),
        'trend_score': sym_detail.get('trend', {}).get('score', 0),
        'change_pct': sym_detail.get('change_pct', 0),
        'open_interest': sym_detail.get('open_interest', 0),
    }
    # 添期限结构与价差数据（通达信TdxCollector v2.0）
    tb = term_basis_data.get(dc['pid'].lower(), {})
    if tb.get('term_type', 'unknown') != 'unknown':
        dc['term_structure'] = {
            'type': tb.get('term_type'),
            'slope': tb.get('term_slope'),
            'near_price': tb.get('near_price'),
            'far_price': tb.get('far_price'),
            'contracts_count': tb.get('contracts_count', 0),
        }
    else:
        dc['term_structure'] = {'type': 'unknown'}
    if tb.get('spread') is not None:
        dc['spread'] = tb['spread']
        dc['spread_z_score'] = tb.get('spread_z_score')
        dc['spread_mean'] = tb.get('spread_mean')
        dc['spread_std'] = tb.get('spread_std')
    debate_candidates.append(dc)

intermediate = {
    'report_date': REPORT_DATE,
    'report_date_compact': REPORT_DATE_COMPACT,
    'data_benchmark': DATA_BENCHMARK,
    'data_source': data_source_used,
    'report_dir': REPORT_DIR,
    'generated_at': datetime.now().isoformat(),
    'symbols_count': len(symbols_data),
    'data_source_used': data_source_used,
    'data_source_config': {
        'trading_hour': '盘中' if _is_trading_session() else '盘后',
        'tdx_bridge_available': tdx_available,
        'indicator_source': 'TQ-Local formula_zb (通达信内核)' if tdx_available else 'numpy (TQ-Local不可用)',
    },
    'all_actionable': all_actionable,
    'candidates': candidates_serializable,
    'BUY_top5': [s.get('product_id') for s in BUY_top5],
    'SELL_top5': [s.get('product_id') for s in SELL_top5],
    'chain_results': chain_results,
    'debate_candidates': debate_candidates,  # 所有方向明确的信号，供专家团辩论
    'symbols_summary': [{
        'product_id': s.get('product_id', ''),
        'product_name': s.get('product_name', ''),
        'last_price': s.get('last_price', 0),
        'direction': s.get('direction', 'HOLD'),
        'score': s.get('score', 0),
        'data_source': s.get('data_source', ''),
        'trend_score': s.get('trend', {}).get('score', 0),
    } for s in symbols_data],
}

output_path = os.path.join(REPORT_DIR, 'intermediate_data.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(intermediate, f, ensure_ascii=False, indent=2, default=str)

print(f"\n{'='*60}")
print(f"✅ Phase 1 完成！")
print(f"📝 中间数据: {output_path}")
print(f"📊 品种: {len(symbols_data)}, 数据源: {data_source_used}")
print(f"🟢 BUY: {len(BUY_signals)}, 🔴 SELL: {len(SELL_signals)}, 有效方案: {len(actionable_plans)}")
print(f"{'='*60}")
