#!/usr/bin/env python3
"""
全品种数据采集脚本 — 辩论专家团数聚石(futures-data-engineer)
工作模式: full_scan
品种: 67标准商品期货
数据: get_quote + get_kline(days=200) + get_term_structure
校验: 价格合理性/持仓非零/期限结构类型/Z分数/缺失处理
输出: 结构化JSON → data/full_scan_result_{datetime}.json
"""

import json
import sys
import time
import math
import traceback
from datetime import datetime
from pathlib import Path

# 项目根目录
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR))

from scripts.multi_source_adapter import MultiSourceAdapter


# ========== 品种列表 ==========
ALL_VARIETIES = [
    "rb", "hc", "i", "j", "jm", "SF", "SM",
    "sc", "lu", "fu", "bu", "pg",
    "PX", "TA", "PF", "PR", "eg", "eb",
    "v", "pp", "l", "MA", "SH",
    "cu", "al", "zn", "pb", "ni", "sn", "ao", "SS",
    "au", "ag",
    "a", "b", "m", "y", "p", "OI", "RM", "PK",
    "c", "cs", "SR", "CF",
    "jd", "lh", "AP", "CJ",
    "FG", "SA", "UR",
    "ru", "nr", "br", "sp", "op",
    "lc", "si", "ps", "ec", "rr", "ad",
    "CY", "PL", "bz"
]


def parse_quote_result(quote_result):
    """从 get_quote 返回结果中提取价格信息"""
    if not quote_result or not quote_result.get("success"):
        return None, quote_result.get("error", "未知错误")

    data = quote_result.get("data", [])
    if not data:
        return None, "数据为空"

    # data可能是list或dict
    if isinstance(data, list):
        if len(data) == 0:
            return None, "数据列表为空"
        latest = data[-1]  # 取最新一条
    else:
        latest = data

    # 尝试提取 OHLCV
    price = {
        "open": _safe_float(latest.get("open")),
        "high": _safe_float(latest.get("high")),
        "low": _safe_float(latest.get("low")),
        "close": _safe_float(latest.get("close")),
        "volume": _safe_int(latest.get("volume")),
        "oi": _safe_int(latest.get("oi", latest.get("hold", latest.get("open_interest", 0)))),
        "change_pct": _safe_float(latest.get("change_pct", 0)),
        "data_source": quote_result.get("data_source", "unknown"),
    }
    return price, None


def parse_kline_result(kline_result):
    """从 get_kline 返回结果中提取K线序列"""
    if not kline_result or not kline_result.get("success"):
        return None, kline_result.get("error", "未知错误")

    data = kline_result.get("data", [])
    if not data or len(data) == 0:
        return None, "K线数据为空"

    records = []
    for k in data:
        records.append({
            "date": k.get("date", ""),
            "open": _safe_float(k.get("open")),
            "high": _safe_float(k.get("high")),
            "low": _safe_float(k.get("low")),
            "close": _safe_float(k.get("close")),
            "volume": _safe_int(k.get("volume")),
            "oi": _safe_int(k.get("oi", k.get("hold", 0))),
        })
    return records, None


def parse_term_structure(ts_result):
    """从 get_term_structure 返回结果中提取期限结构信息"""
    if not ts_result or not ts_result.get("success"):
        return {
            "type": "Unknown",
            "slope": 0,
            "near_month": "",
            "near_price": 0,
            "far_month": "",
            "far_price": 0,
            "contracts": [],
            "error": ts_result.get("error", "未知错误"),
        }

    return {
        "type": ts_result.get("type", "Unknown"),
        "slope": _safe_float(ts_result.get("slope", 0)),
        "near_month": ts_result.get("near_month", ""),
        "near_price": _safe_float(ts_result.get("near_price", 0)),
        "far_month": ts_result.get("far_month", ""),
        "far_price": _safe_float(ts_result.get("far_price", 0)),
        "contracts": ts_result.get("contracts", []),
        "data_source": ts_result.get("data_source", "unknown"),
    }


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def validate_price(price):
    """校验价格合理性 — 规则1"""
    notes = []
    if not price:
        return "❌缺失", ["无价格数据"]
    
    close = price.get("close", 0)
    open_ = price.get("open", 0)
    
    if close <= 0:
        notes.append("收盘价≤0")
        return "⚠️降级", notes
    
    if open_ > 0:
        ratio = close / open_
        if ratio < 0.8 or ratio > 1.2:
            notes.append(f"⚠️价格异常: close/open={ratio:.3f}")
    
    # 规则2: 持仓非零
    oi = price.get("oi", 0)
    if oi <= 0:
        notes.append("⚠️无持仓→流动性风险")
    
    return "✅正常", notes


def calculate_z_score(close_prices):
    """计算Z分数 — 规则4"""
    if not close_prices or len(close_prices) < 20:
        return 0, ["样本不足20天，Z分数不可靠"]
    
    # 取最近200天的收盘价
    prices = [p for p in close_prices[-200:] if p > 0]
    if len(prices) < 20:
        return 0, ["有效价格样本不足20天"]
    
    n = len(prices)
    mean = sum(prices) / n
    variance = sum((p - mean) ** 2 for p in prices) / (n - 1)  # ddof=1
    std = math.sqrt(variance)
    
    if std == 0:
        return 0, ["标准差为0，无法计算Z分数"]
    
    latest_close = prices[-1]
    z = (latest_close - mean) / std
    
    notes = []
    if abs(z) > 3:
        notes.append(f"🔴极极端值: z-score={z:.2f}")
    elif abs(z) > 2:
        notes.append(f"⚠️极端值: z-score={z:.2f}")
    
    return z, notes


def determine_term_structure_type(ts_info):
    """判断期限结构类型 — 规则3"""
    ts_type = ts_info.get("type", "Unknown")
    if ts_type != "Unknown":
        return ts_type
    
    # fallback: 手动判断
    near_price = ts_info.get("near_price", 0)
    far_price = ts_info.get("far_price", 0)
    
    if near_price <= 0 or far_price <= 0:
        return "Unknown"
    
    spread_pct = abs(far_price - near_price) / near_price * 100
    if spread_pct < 0.5:
        return "flat"
    elif far_price > near_price:
        return "Contango"
    else:
        return "Back"


def main():
    print("=" * 60, flush=True)
    print(f"辩论专家团数据采集 — 全市场扫描", flush=True)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"品种数量: {len(ALL_VARIETIES)}", flush=True)
    print("=" * 60, flush=True)
    
    # 初始化适配器
    print("\n[初始化] MultiSourceAdapter ...", flush=True)
    adapter = MultiSourceAdapter()
    print("[初始化] 完成\n", flush=True)
    
    # 结果容器
    results = {}
    quality_stats = {"✅正常": 0, "⚠️降级": 0, "❌缺失": 0}
    errors = []
    
    start_time = time.time()
    
    for idx, variety in enumerate(ALL_VARIETIES, 1):
        var_start = time.time()
        print(f"\n[{idx:3d}/{len(ALL_VARIETIES)}] {variety.upper()} — 采集开始...", flush=True)
        
        result = {"price": None, "kline": None, "term_structure": None}
        notes = []
        data_quality = "✅正常"
        z_score = 0
        
        # 1. 获取实时报价
        try:
            print(f"  → get_quote({variety}) ...", flush=True)
            qr = adapter.get_quote(variety)
            price, err = parse_quote_result(qr)
            if price:
                # 价格校验
                pq, pn = validate_price(price)
                if pq == "⚠️降级":
                    data_quality = "⚠️降级"
                elif pq == "❌缺失":
                    data_quality = "❌缺失"
                notes.extend(pn)
                result["price"] = price
                print(f"  ✓ get_quote: close={price['close']}, oi={price['oi']}, src={price['data_source']}", flush=True)
            else:
                notes.append(f"❌缺失: get_quote失败 — {err}")
                data_quality = "❌缺失"
                print(f"  ✗ get_quote: 失败 — {err}", flush=True)
        except Exception as e:
            notes.append(f"❌缺失: get_quote异常 — {str(e)}")
            data_quality = "❌缺失"
            print(f"  ✗ get_quote: 异常 — {e}", flush=True)
            traceback.print_exc()
        
        # 2. 获取K线
        try:
            print(f"  → get_kline({variety}, days=200) ...", flush=True)
            kr = adapter.get_kline(variety, days=200)
            kline_records, k_err = parse_kline_result(kr)
            if kline_records and len(kline_records) > 0:
                result["kline"] = kline_records
                print(f"  ✓ get_kline: {len(kline_records)}条, src={kr.get('data_source','?')}", flush=True)
                
                # 计算Z分数
                close_prices = [r["close"] for r in kline_records if r["close"] > 0]
                z_score, zn = calculate_z_score(close_prices)
                notes.extend(zn)
                if abs(z_score) > 2 and data_quality == "✅正常":
                    data_quality = "⚠️降级"
            else:
                notes.append(f"❌缺失: get_kline失败 — {k_err}")
                if data_quality == "✅正常":
                    data_quality = "❌缺失"
                print(f"  ✗ get_kline: 失败 — {k_err}", flush=True)
        except Exception as e:
            notes.append(f"❌缺失: get_kline异常 — {str(e)}")
            if data_quality == "✅正常":
                data_quality = "❌缺失"
            print(f"  ✗ get_kline: 异常 — {e}", flush=True)
        
        # 3. 获取期限结构
        try:
            print(f"  → get_term_structure({variety}) ...", flush=True)
            ts = adapter.get_term_structure(variety)
            ts_info = parse_term_structure(ts)
            result["term_structure"] = ts_info
            
            ts_type = determine_term_structure_type(ts_info)
            ts_info["determined_type"] = ts_type
            print(f"  ✓ get_term_structure: {ts_type} (斜率{ts_info['slope']}%), 合约{len(ts_info['contracts'])}个", flush=True)
        except Exception as e:
            notes.append(f"❌缺失: get_term_structure异常 — {str(e)}")
            if data_quality == "✅正常":
                data_quality = "❌缺失"
            print(f"  ✗ get_term_structure: 异常 — {e}", flush=True)
            result["term_structure"] = {
                "type": "Unknown", "determined_type": "Unknown",
                "slope": 0, "contracts": [],
                "error": str(e)
            }
        
        elapsed = time.time() - var_start
        
        # 组装结果
        results[variety] = {
            "price": result["price"],
            "kline_count": len(result["kline"]) if result["kline"] else 0,
            "term_structure": result["term_structure"],
            "z_score": round(z_score, 4),
            "data_quality": data_quality,
            "notes": notes,
            "elapsed_sec": round(elapsed, 2),
        }
        
        quality_stats[data_quality] = quality_stats.get(data_quality, 0) + 1
        
        print(f"  [{elapsed:.1f}s] 质量: {data_quality}", flush=True)
    
    total_elapsed = time.time() - start_time
    
    # 汇总
    summary = {
        "mode": "full_scan",
        "collected_count": quality_stats.get("✅正常", 0) + quality_stats.get("⚠️降级", 0),
        "total_count": len(ALL_VARIETIES),
        "quality_ok": quality_stats.get("✅正常", 0),
        "quality_degraded": quality_stats.get("⚠️降级", 0),
        "quality_missing": quality_stats.get("❌缺失", 0),
        "quality": f"{quality_stats.get('✅正常', 0)}/{len(ALL_VARIETIES)} ✅正常",
        "elapsed_seconds": round(total_elapsed, 1),
        "timestamp": datetime.now().isoformat(),
        "errors": errors,
    }
    
    output = {
        "summary": summary,
        "varieties": results,
    }
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = SKILL_DIR / "data"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"full_scan_result_{timestamp}.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60, flush=True)
    print(f"全市场扫描完成!", flush=True)
    print(f"耗时: {total_elapsed:.1f}s", flush=True)
    print(f"质量统计: ✅正常={quality_stats['✅正常']} | ⚠️降级={quality_stats['⚠️降级']} | ❌缺失={quality_stats['❌缺失']}", flush=True)
    print(f"结果已保存: {output_path}", flush=True)
    print("=" * 60, flush=True)
    
    # 打印数据质量汇总
    print(f"\n{'='*60}", flush=True)
    print(f"数据质量汇总", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"{'品种':<6} {'质量':<10} {'收盘价':<10} {'持仓':<8} {'期限结构':<12} {'Z分数':<10} {'异常提示'}", flush=True)
    print(f"{'-'*80}", flush=True)
    
    for variety in ALL_VARIETIES:
        r = results.get(variety, {})
        dq = r.get("data_quality", "❌缺失")
        price = r.get("price", {}) or {}
        close = price.get("close", 0)
        oi = price.get("oi", 0)
        ts = r.get("term_structure", {}) or {}
        ts_type = ts.get("determined_type", ts.get("type", "?"))
        z = r.get("z_score", 0)
        note = r.get("notes", [])
        note_str = note[0][:30] if note else ""
        
        print(f"{variety.upper():<6} {dq:<10} {close:<10.0f} {oi:<8} {ts_type:<12} {z:<10.2f} {note_str}", flush=True)
    
    print(f"\n{'='*60}", flush=True)
    print(f"###END_DATA_COLLECTION", flush=True)
    print(f"{'='*60}", flush=True)
    
    return output


if __name__ == "__main__":
    result = main()
