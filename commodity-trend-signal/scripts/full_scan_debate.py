#!/usr/bin/env python3
"""
全品种趋势信号扫描 v3（辩论专家团版）
======================================
评分委派 scoring_system.py，趋势委派 indicators.assess_trend_maturity，否决委派 score_veto_dimension
"""
import sys, os, json, numpy as np, pandas as pd
from datetime import date

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_ROOT = os.path.dirname(SKILL_DIR)
FDS_DIR = os.path.join(os.path.dirname(SKILLS_ROOT), 'futures-data-search', 'scripts')
for p in [SKILL_DIR, FDS_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from scripts.indicators import _compute_indicators_numpy, assess_trend_maturity
    from scripts.tdx_bridge import get_bridge
    from scripts.scoring_system import calculate_composite_score, score_veto_dimension
    from scripts.symbols import ALL_SYMBOLS
except ImportError:
    from indicators import _compute_indicators_numpy, assess_trend_maturity
    from tdx_bridge import get_bridge
    from scoring_system import calculate_composite_score, score_veto_dimension
    from symbols import ALL_SYMBOLS
from multi_source_adapter import MultiSourceAdapter
from scan_all import collect_kline_for_all


def l1_l4_score(tech, sym_scoring=None, kline_closes=None):
    """完整版评分：委派 scoring_system.py 的 calculate_composite_score"""
    if sym_scoring is None:
        sym_scoring = {'last_price': tech.get('last_price', 0), 'open_interest': tech.get('open_interest', 0)}
    sc = calculate_composite_score(tech, sym_scoring, 0, kline_closes, None)
    direction = 'bull' if sc['direction'] == 'BUY' else ('bear' if sc['direction'] == 'SELL' else 'neutral')
    s = 1 if direction == 'bull' else (-1 if direction == 'bear' else 0)
    return {
        'total': sc['total'] * s, 'abs': sc['total'],
        'l1': sc['L1_score'] * s, 'l2': sc['L2_score'] * s,
        'l3': sc['L3_score'] * s, 'l4': sc['L4_score'] * s,
        'veto': sc['veto_score'],
        'direction': direction, 'grade': sc['grade'],
        '_stage': sc['maturity']['stage'],
    }


def determine_trend_stage(tech: dict) -> str:
    """趋势阶段判断 — 委派 assess_trend_maturity"""
    try:
        price = tech.get('last_price', 0)
        sym = {'last_price': price, 'open_interest': tech.get('open_interest', 0)}
        # 根据价格相对MA20位置决定方向
        ma20 = tech.get('MA20', price)
        direction = 1 if price > ma20 else -1
        maturity = assess_trend_maturity(tech, sym, direction)
        return maturity.get('stage', 'chop')
    except Exception:
        pass
    return 'chop'


def check_veto(tech: dict, direction: str, score_dict: dict) -> dict:
    """
    否决项检查（Step 3）— 委派 score_veto_dimension
    """
    is_bull = direction == 'bull'
    sym = {'last_price': tech.get('last_price', 0), 'open_interest': tech.get('open_interest', 0)}
    result = score_veto_dimension(tech, sym, is_bull, None)
    reasons = result['reasons']
    veto_score = result['score']
    
    fatal = veto_score <= -10
    if fatal:
        status = "否决"
    elif len(reasons) > 0:
        status = "注意"
    else:
        status = "通过"
    
    conf = "低" if veto_score <= -15 else ("中" if veto_score <= -5 else "高")
    
    return {'status': status, 'reasons': reasons, 'fatal': fatal, 'confidence': conf}


def annotate_key_levels(tech: dict, price: float) -> dict:
    """关键价位标注（Step 4）"""
    dc_l = tech.get('DC_LOWER', price * 0.95)
    dc_u = tech.get('DC_UPPER', price * 1.05)
    ma60 = tech.get('MA60', price)
    atr = tech.get('ATR14', price * 0.02)
    bb_lower = tech.get('BB_LOWER', price * 0.95)
    bb_upper = tech.get('BB_UPPER', price * 1.05)

    return {
        'support': min(dc_l, bb_lower) if dc_l and bb_lower else dc_l,
        'resistance': max(dc_u, bb_upper) if dc_u and bb_upper else dc_u,
        'ma60': ma60,
        'atr': round(atr, 2),
        'stop_loss_1_5x_atr': round(atr * 1.5, 2),
    }


def detailed_verification(sym_result: dict, tech: dict) -> dict:
    """
    对单个品种执行Step 1-4详细核验
    Step 1: 得分评估
    Step 2: 趋势阶段判断
    Step 3: 否决项检查
    Step 4: 关键价位标注
    """
    direction = sym_result['direction']
    price = sym_result['price']

    # Step 1: 得分评估 — 异常标注
    notes = []
    l1 = sym_result['l1']
    l3 = sym_result['l3']
    l4 = sym_result['l4']

    if abs(l1) > 30 and abs(l3) < 5:
        notes.append("L1高分(>30)但L3低分(<5)，结构不确认，降级考虑")
    if abs(l4) > 10 and abs(l1) < 15:
        notes.append("L4高分(>10)但L1低分(<15)，趋势已走远，注意时间衰减")
    if sym_result['veto'] <= -15:
        notes.append("否决分触发(<=-15)，信号矛盾较大")

    # Step 2: 趋势阶段
    trend_stage = determine_trend_stage(tech)

    # Step 3: 否决检查
    veto_check = check_veto(tech, direction, {
        'veto': sym_result['veto'],
        'l1': l1, 'l3': l3, 'l4': l4
    })

    # Step 4: 关键价位
    key_levels = annotate_key_levels(tech, price)

    # 综合置信度
    if veto_check['fatal']:
        overall_conf = "低"
    elif sym_result['grade'] == 'STRONG' and veto_check['confidence'] == '高':
        overall_conf = "高"
    elif sym_result['grade'] == 'WATCH':
        overall_conf = "中"
    else:
        overall_conf = "低"

    return {
        'verdict': 'BUY' if direction == 'bull' else ('SELL' if direction == 'bear' else 'HOLD'),
        'trend_stage': trend_stage,
        'confidence': overall_conf,
        'veto_status': veto_check['status'],
        'veto_reasons': veto_check['reasons'],
        'key_levels': {
            'support': round(key_levels['support'], 1),
            'resistance': round(key_levels['resistance'], 1),
            'ma60': round(key_levels['ma60'], 1),
            'atr': key_levels['atr'],
            'stop_loss_1_5x_atr': key_levels['stop_loss_1_5x_atr'],
        },
        'notes': notes,
    }


def run_scan(symbols: list = None):
    """执行全品种扫描 + 辩论报告输出

    Args:
        symbols: 指定品种列表 [(sym, name), ...]，None则扫描ALL_SYMBOLS(全67品种)
    """
    today = date.today()
    today_str = today.strftime('%Y%m%d')

    target_symbols = symbols if symbols is not None else ALL_SYMBOLS
    mode_label = "自定义品种扫描" if symbols else "全品种扫描"

    print("=" * 60)
    print(f"辩论专家团{mode_label} v3 (Enhanced) -- {today}")
    print(f"目标品种: {len(target_symbols)}")
    print("=" * 60)

    bridge = get_bridge()
    tdx_ok = bridge.available
    print("TQ-Local: %s 可用" % ("[OK]" if tdx_ok else "[WARN] 不可用->numpy兜底"))

    adapter = MultiSourceAdapter()
    print("\n[1] 数据采集...")
    adapter = MultiSourceAdapter()
    kline_data = collect_kline_for_all(adapter, target_symbols, days=120, min_bars=50)
    failed_symbols = [(sym, name, "no data") for sym, name in target_symbols if sym not in kline_data]
    print("  成功: %d/%d" % (len(kline_data), len(target_symbols)))

    print("\n[2] 指标计算 + L1-L4评分...")
    results = []
    raw_tech_data = {}
    for i, (sym, name) in enumerate(target_symbols):
        if sym not in kline_data:
            continue
        try:
            _, dlist = kline_data[sym]
            df = pd.DataFrame({k: [float(r[k]) for r in dlist]
                               for k in ['open', 'high', 'low', 'close']})
            df['volume'] = [float(r.get('volume', 0)) for r in dlist]
            tech = _compute_indicators_numpy(df, sym)
            price = tech.get('last_price', float(df['close'].iloc[-1]))
            prev = float(df['close'].iloc[-2]) if len(df) > 1 else price
            tech['price'] = price
            tech['change_pct'] = (price / prev - 1) * 100
            sym_scoring = {'last_price': price, 'open_interest': tech.get('open_interest', 0)}
            kline_closes = df['close'].tolist()
            sc = l1_l4_score(tech, sym_scoring, kline_closes)
            entry = dict(
                symbol=sym, name=name, price=round(price, 1),
                change_pct=round(tech.get('change_pct', 0), 2),
                total=sc['total'], abs=sc['abs'], l1=sc['l1'], l2=sc['l2'], l3=sc['l3'],
                l4=sc['l4'], veto=sc['veto'], direction=sc['direction'], grade=sc['grade'],
                adx=round(tech.get('ADX', 0), 1), rsi=round(tech.get('RSI14', 0), 1),
                cci=round(tech.get('CCI20', 0), 1), ma_slope=round(tech.get('MA20_SLOPE', 0), 2),
                macd_cross=tech.get('macd_cross', 'none'), dc20_break=tech.get('dc20_break', 'none'),
                ma_align=tech.get('ma_align', 'mixed'),
                _tdx_patched=tech.get('_tdx_patched', False),
            )
            results.append(entry)
            raw_tech_data[sym] = tech
        except Exception as e:
            print("  [%s] error: %s" % (sym, e))
        if (i + 1) % 15 == 0:
            print("  [%d/%d] %d OK" % (i+1, len(target_symbols), len(results)))

    # ── v2.14 双排行：early_top5 (L1+L2-成熟度罚分) + established_top5 (abs(total)) ──
    from scoring_system import compute_early_score
    for r in results:
        es, penalty, ereasons = compute_early_score(
            r['l1'], r['l2'], r['l3'], r['l4'], r['rsi'], r['adx'])
        r['early_score'] = es
        r['maturity_penalty'] = penalty
        r['maturity_reasons'] = ereasons

    all_ranked = sorted(results, key=lambda x: abs(x['total']), reverse=True)
    early_ranked = sorted(results, key=lambda x: x.get('early_score', 0), reverse=True)
    
    bull = [r for r in all_ranked if r['direction'] == 'bull']
    bear = [r for r in all_ranked if r['direction'] == 'bear']
    
    # 双排行：前5取early_ranked，后5取all_ranked排除前5已有
    early_top5 = early_ranked[:5]
    early_ids = {r['symbol'] for r in early_top5}
    established_top5 = [r for r in all_ranked if r['symbol'] not in early_ids][:5]
    top10 = early_top5 + established_top5
    tdx_ct = sum(1 for r in all_ranked if r.get('_tdx_patched'))

    # ── [3] Top10详细核验 ──
    print("\n[3] Top10 详细核验 (Step 1-4)...")
    top10_verification = {}
    for r in top10:
        sym = r['symbol']
        tech = raw_tech_data.get(sym, {})
        v = detailed_verification(r, tech)
        top10_verification[sym] = v
        d = "多头" if r['direction'] == 'bull' else ("空头" if r['direction'] == 'bear' else "中性")
        print("  %s(%s) %s | %s | 置信度%s | 否决:%s" % (
            sym, r['name'], d, v['trend_stage'], v['confidence'], v['veto_status']))

    # ── 汇总输出 ──
    summary = {
        '_meta': {
            'date': today_str,
            'total_symbols': len(target_symbols),
            'data_ok': len(results),
            'data_failed': len(failed_symbols),
            'bull': len(bull),
            'bear': len(bear),
            'neutral': len(results) - len(bull) - len(bear),
            'tdx_patched_count': tdx_ct,
            'data_source': '通达信本地->MultiSourceAdapter',
            'indicators': 'TQ-Local bridge v2.15 + numpy',
            'mode': 'full_scan',
            'top10_count': len(top10),
            'failed_symbols': [{'symbol': s, 'name': n, 'reason': r}
                              for s, n, r in failed_symbols],
        },
        'bull_signals': bull,
        'bear_signals': bear,
        'all_ranked': all_ranked,
        'top10': top10,
        'early_top5': [r['symbol'] for r in early_top5],
        'established_top5': [r['symbol'] for r in established_top5],
        'top10_verification': top10_verification,
        'trend_analyst': '技研锋(futures-trend-analyst)',
    }

    # ── 终端输出：全排行 ──
    print("\n" + "=" * 60)
    print("完成: %d品种(接口%d OK) | 多头%d 空头%d | TDX桥接%d" % (
        len(results), len(failed_symbols), len(bull), len(bear), tdx_ct))
    print("=" * 60)
    header = "%3s %-8s %-6s %8s %6s %5s %4s %4s %4s %4s %4s %5s %5s %6s" % \
             ("#","品种","方向","价格","涨跌","总分","L1","L2","L3","L4","否决","ADX","RSI","等级")
    print(header)
    print("-" * 90)
    for i, r in enumerate(all_ranked):
        d = "多头" if r['direction'] == 'bull' else ("空头" if r['direction'] == 'bear' else "中性")
        line = "%3d %-8s %-6s %8.0f %+5.1f%% %+4.0f %+3d %+3d %+3d %+3d %+3d %5.1f %5.1f %6s" % \
               (i+1, r["symbol"], d, r["price"], r["change_pct"], r["total"],
                r["l1"], r["l2"], r["l3"], r["l4"], r["veto"], r["adx"], r["rsi"], r["grade"])
        print(line)

    # ── Top10 ──
    print("\n" + "=" * 60)
    print("Top 10 辩论候选 (按 |总分| 降序)")
    print("=" * 60)
    h2 = "%3s %-8s %-6s %5s %4s %4s %4s %4s %4s %5s %5s %-8s %-6s" % \
         ("#","品种","方向","总分","L1","L2","L3","L4","否决","ADX","RSI","等级","趋势阶段")
    print(h2)
    print("-" * 80)
    for i, r in enumerate(top10):
        d = "多头" if r['direction'] == 'bull' else ("空头" if r['direction'] == 'bear' else "中性")
        ts = top10_verification.get(r['symbol'], {}).get('trend_stage', '?')
        line = "%3d %-8s %-6s %+4.0f %+3d %+3d %+3d %+3d %+3d %5.1f %5.1f %-8s %-6s" % \
               (i+1, r["symbol"], d, r["total"], r["l1"], r["l2"], r["l3"],
                r["l4"], r["veto"], r["adx"], r["rsi"], r["grade"], ts)
        print(line)

    # ── Top10详细核验 ──
    print("\n" + "=" * 80)
    print("Top 10 详细核验报告")
    print("=" * 80)
    for i, r in enumerate(top10):
        sym = r['symbol']
        v = top10_verification.get(sym, {})
        print("\n--- [#%d] %s (%s) ---" % (i+1, sym, r['name']))
        print("  方向: %s | 总分: %+d | L1: %+d L2: %+d L3: %+d L4: %+d | 否决: %+d" % (
            "多头" if r['direction'] == 'bull' else ("空头" if r['direction'] == 'bear' else "中性"),
            r['total'], r['l1'], r['l2'], r['l3'], r['l4'], r['veto']))
        print("  ADX: %.1f | RSI: %.1f | CCI: %.1f | MA斜率: %.2f" % (
            r['adx'], r['rsi'], r['cci'], r['ma_slope']))
        print("  裁决: %s | 趋势阶段: %s | 置信度: %s" % (
            v.get('verdict','?'), v.get('trend_stage','?'), v.get('confidence','?')))
        print("  否决状态: %s" % v.get('veto_status','?'))
        for reason in v.get('veto_reasons', []):
            print("    - %s" % reason)
        kl = v.get('key_levels', {})
        print("  关键价位: 支撑 %.0f | 阻力 %.0f | MA60 %.0f | ATR %.2f | 止损参考 %.2f" % (
            kl.get('support',0), kl.get('resistance',0), kl.get('ma60',0),
            kl.get('atr',0), kl.get('stop_loss_1_5x_atr',0)))
        for note in v.get('notes', []):
            print("  [异常] %s" % note)

    # ── 输出JSON ──
    out_path = os.path.join(os.path.dirname(SKILL_DIR), 'Reports')
    os.makedirs(out_path, exist_ok=True)
    json_path = os.path.join(out_path, 'debate_scan_%s.json' % today_str)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\nJSON: %s (%d bytes)" % (json_path, os.path.getsize(json_path)))

    return summary


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='辩论模式趋势信号扫描（支持全品种或自定义品种）')
    parser.add_argument('--symbols', '-s', help='指定品种代码(逗号分隔)，如: PK,RB,B,UR。不指定则扫描全67品种',
                        default=None)
    args = parser.parse_args()

    symbol_list = None
    if args.symbols:
        pids = [s.strip().upper() for s in args.symbols.split(',') if s.strip()]
        symbol_list = [(sym, name) for sym, name in ALL_SYMBOLS if sym in pids]
        if not symbol_list:
            print(f'❌ 未找到指定品种: {pids}')
            sys.exit(1)
        print(f'🎯 自定义品种扫描: {[s for s,_ in symbol_list]}')

    run_scan(symbols=symbol_list)
