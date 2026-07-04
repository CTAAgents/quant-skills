#!/usr/bin/env python3
"""
辩论专家团 数聚石 — 数据采集与校验脚本 (v2)
为指定品种列表采集行情/K线/期限结构，校验数据质量，输出结构化JSON报告。

改进要点：
- OI从AKShare K-line提取（TDX本地holding=0已知问题）
- 期限结构从TDX Collector直接获取（EastMoney不可用时降级）
- 数据质量判定更加精确
"""

import json
import sys
import os
import traceback
from datetime import datetime
from pathlib import Path
import numpy as np

# 添加技能路径
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "collectors"))
sys.path.insert(0, str(SKILL_DIR / "collectors" / "exchange_data" / "scripts"))

from multi_source_adapter import MultiSourceAdapter


class DebateDataCollector:
    """辩论专家团数据采集器 — 数聚石"""

    def __init__(self):
        print("=" * 60, flush=True)
        print(f"📊 数聚石 — 辩论数据采集启动 at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print("=" * 60, flush=True)
        self.adapter = MultiSourceAdapter()
        
        # 尝试加载TDX Collector（用于期限结构）
        self.tdx_collector = None
        try:
            from tdx_collector import TdxCollector
            tc = TdxCollector()
            if tc.is_available:
                self.tdx_collector = tc
                print("[Init] 通达信本地采集器已加载（用于期限结构）", flush=True)
            else:
                print("[Init] 通达信本地采集器不可用", flush=True)
        except Exception as e:
            print(f"[Init] 通达信本地采集器加载失败: {e}", flush=True)
        
        self.results = {}

    def _get_oi_from_akshare_kline(self, pid):
        """从AKShare K-line最新记录提取持仓量(OI)"""
        try:
            import akshare as ak
            ak_symbol = pid.lower() + "0"
            df = ak.futures_zh_daily_sina(symbol=ak_symbol)
            if df is not None and len(df) > 0:
                latest = df.iloc[-1]
                oi = int(latest.get('hold', 0) or 0)
                date = str(latest.get('date', ''))
                if oi > 0:
                    print(f"  [{pid.upper()}] AKShare OI兜底: {oi} (date={date})", flush=True)
                    return oi
        except Exception as e:
            print(f"  [{pid.upper()}] AKShare OI提取失败: {e}", flush=True)
        return 0

    def _get_term_structure_from_tdx(self, pid):
        """从通达信本地采集器获取期限结构"""
        if not self.tdx_collector:
            return None
        try:
            ts = self.tdx_collector.get_term_structure(pid.upper())
            if ts and ts.get('type') and ts['type'] != 'Unknown':
                print(f"  [{pid.upper()}] TDX期限结构: {ts['type']} (斜率={ts['slope']}%)", flush=True)
                return ts
        except Exception as e:
            print(f"  [{pid.upper()}] TDX期限结构失败: {e}", flush=True)
        return None

    def collect_variety(self, pid):
        """采集单个品种的全部数据"""
        pid_u = pid.upper()
        print(f"\n{'─' * 50}", flush=True)
        print(f"[{pid_u}] 开始数据采集...", flush=True)

        result = {
            "price": {},
            "term_structure": "Unknown",
            "z_score": None,
            "data_quality": "✅正常",
            "notes": [],
            "data_source": {}
        }

        # ============ 1. 获取实时报价 ============
        quote_data = None
        try:
            print(f"  [{pid_u}] 获取实时报价...", flush=True)
            qr = self.adapter.get_quote(pid, contract_type="main")
            if qr and qr.get("success") and qr.get("data"):
                quote_data = qr["data"]
                result["data_source"]["quote"] = qr.get("data_source", "unknown")
                print(f"  [{pid_u}] 报价来源: {qr.get('data_source')}, {len(quote_data)}条", flush=True)
            else:
                result["data_source"]["quote"] = "none"
                result["notes"].append(f"❌ 报价数据缺失: {qr.get('error', '未知错误')}")
                print(f"  [{pid_u}] ⚠ 报价数据获取失败", flush=True)
        except Exception as e:
            result["data_source"]["quote"] = "error"
            result["notes"].append(f"❌ 报价获取异常: {str(e)[:100]}")
            print(f"  [{pid_u}] ❌ 报价获取异常: {e}", flush=True)

        # 解析报价
        if quote_data and len(quote_data) > 0:
            try:
                row = quote_data[0] if isinstance(quote_data, list) else quote_data
                price = {
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "close": float(row.get("close", 0) or 0),
                    "volume": int(row.get("volume", 0) or 0),
                    "oi": int(row.get("open_interest", 0) or row.get("oi", 0) or row.get("holding", 0) or 0),
                }
                result["price"] = price
                result["contract_tag"] = row.get("contract", row.get("contract_tag", "main"))

                # ----- 校验1: 价格合理性 -----
                o, h, l, c = price["open"], price["high"], price["low"], price["close"]
                if o > 0 and c > 0:
                    if c < o * 0.8 or c > o * 1.2:
                        result["notes"].append(f"⚠️ 价格异常: close={c}, open={o}, 偏离={(c/o-1)*100:.1f}%")
                        print(f"  [{pid_u}] ⚠️ 价格异常", flush=True)
                    else:
                        print(f"  [{pid_u}] ✅ 价格合理 (close/open偏差={(c/o-1)*100:.2f}%)", flush=True)

                # ----- OI缺失处理: 从AKShare K-line兜底 -----
                if price["oi"] <= 0:
                    print(f"  [{pid_u}] ⚠️ TDX本地holding=0, 尝试AKShare OI兜底...", flush=True)
                    akshare_oi = self._get_oi_from_akshare_kline(pid)
                    if akshare_oi > 0:
                        price["oi"] = akshare_oi
                        result["data_source"]["oi_supplement"] = "akshare"
                        print(f"  [{pid_u}] ✅ AKShare OI兜底成功: {akshare_oi}", flush=True)
                    else:
                        result["notes"].append("⚠️ 无持仓(oi=0) → 流动性风险")
                        print(f"  [{pid_u}] ⚠️ 无法获取OI", flush=True)

                print(f"  [{pid_u}] 报价: O={price['open']} H={price['high']} L={price['low']} C={price['close']} Vol={price['volume']} OI={price['oi']}", flush=True)

            except Exception as e:
                result["notes"].append(f"❌ 报价解析异常: {str(e)[:100]}")
                print(f"  [{pid_u}] ❌ 报价解析异常: {e}", flush=True)

        # ============ 2. 获取200日K线（Z分数计算） ============
        kline_data = None
        try:
            print(f"  [{pid_u}] 获取200日K线...", flush=True)
            kr = self.adapter.get_kline(pid, days=200)
            if kr and kr.get("success") and kr.get("data"):
                kline_data = kr["data"]
                result["data_source"]["kline"] = kr.get("data_source", "unknown")
                print(f"  [{pid_u}] K线来源: {kr.get('data_source')}, {len(kline_data)}条", flush=True)
            else:
                result["data_source"]["kline"] = "none"
                result["notes"].append(f"❌ K线数据缺失")
                print(f"  [{pid_u}] ⚠ K线数据获取失败", flush=True)
        except Exception as e:
            result["data_source"]["kline"] = "error"
            result["notes"].append(f"❌ K线获取异常: {str(e)[:100]}")
            print(f"  [{pid_u}] ❌ K线获取异常: {e}", flush=True)

        # ----- Z分数计算 -----
        if kline_data and len(kline_data) >= 20:
            try:
                closes = [float(k.get("close", 0) or 0) for k in kline_data if float(k.get("close", 0) or 0) > 0]
                if len(closes) >= 20:
                    closes_arr = np.array(closes)
                    mean = np.mean(closes_arr)
                    std = np.std(closes_arr, ddof=1)
                    latest_close = closes[-1]
                    if std > 0:
                        z = (latest_close - mean) / std
                        result["z_score"] = round(z, 4)
                        print(f"  [{pid_u}] Z分数: {z:.4f} (mean={mean:.2f}, std={std:.2f}, n={len(closes)})", flush=True)
                        if abs(z) > 2:
                            result["notes"].append(f"⚠️ 极端Z分数: z={z:.2f} > 2")
                            print(f"  [{pid_u}] ⚠️ 极端Z分数: {z:.2f}", flush=True)
                    else:
                        print(f"  [{pid_u}] Z分数: std=0", flush=True)
                else:
                    print(f"  [{pid_u}] Z分数跳过: 有效收盘价={len(closes)} < 20", flush=True)
            except Exception as e:
                print(f"  [{pid_u}] Z分数异常: {e}", flush=True)

        # ============ 3. 获取期限结构 ============
        # 策略: 优先TDX本地 → 次选EastMoney(MultiSourceAdapter) → 最后AKShare估算
        ts_data = None
        ts_source = None

        # 3a) 尝试TDX本地直接获取
        ts_data = self._get_term_structure_from_tdx(pid)
        if ts_data:
            ts_source = "tdx_local"
            result["data_source"]["term_structure"] = "tdx_local"
            ts_type = ts_data.get('type', 'Unknown')
            result["term_structure"] = ts_type
            result["term_structure_detail"] = {
                "near_month": ts_data.get('near_month', ''),
                "near_price": ts_data.get('near_price', 0),
                "far_month": ts_data.get('far_month', ''),
                "far_price": ts_data.get('far_price', 0),
                "slope": ts_data.get('slope', 0),
                "contracts_count": ts_data.get('contract_count', 0),
            }
            print(f"  [{pid_u}] ✅ TDX期限结构: {ts_type} (斜率={ts_data.get('slope', 0)}%)", flush=True)

        # 3b) TDX失败，尝试MultiSourceAdapter（东方财富）
        if not ts_data:
            try:
                print(f"  [{pid_u}] 尝试东方财富期限结构...", flush=True)
                ts = self.adapter.get_term_structure(pid)
                if ts and ts.get("success"):
                    ts_data = ts
                    ts_source = ts.get("data_source", "eastmoney")
                    result["data_source"]["term_structure"] = ts_source
                    ts_type = ts.get('type', 'Unknown')
                    result["term_structure"] = ts_type
                    result["term_structure_detail"] = {
                        "near_month": ts.get('near_month', ''),
                        "near_price": ts.get('near_price', 0),
                        "far_month": ts.get('far_month', ''),
                        "far_price": ts.get('far_price', 0),
                        "slope": ts.get('slope', 0),
                        "contracts_count": len(ts.get('contracts', [])),
                    }
                    print(f"  [{pid_u}] ✅ 东方财富期限结构: {ts_type}", flush=True)
            except Exception as e:
                print(f"  [{pid_u}] 东方财富期限结构失败: {e}", flush=True)

        # 3c) 都失败
        if not ts_data:
            result["data_source"]["term_structure"] = "none"
            result["notes"].append("❌ 期限结构数据缺失(所有数据源不可用)")
            print(f"  [{pid_u}] ❌ 期限结构: 所有数据源均不可用", flush=True)

        # ============ 数据质量综合判定 ============
        error_notes = [n for n in result["notes"] if n.startswith("❌")]
        warn_notes = [n for n in result["notes"] if n.startswith("⚠️")]

        if len(error_notes) > 0:
            result["data_quality"] = "❌缺失"
        elif len(warn_notes) > 0:
            result["data_quality"] = "⚠️降级"
        else:
            # 检查关键字段
            has_price = result["price"].get("close", 0) > 0
            has_oi = result["price"].get("oi", 0) > 0
            has_ts = result.get("term_structure") != "Unknown"
            has_z = result.get("z_score") is not None

            if not has_price:
                result["data_quality"] = "❌缺失"
                result["notes"].append("❌ 无有效收盘价")
            elif not has_oi or not has_ts or not has_z:
                result["data_quality"] = "⚠️降级"
                if not has_oi:
                    result["notes"].append("⚠️ OI数据缺失")
                if not has_ts:
                    result["notes"].append("⚠️ 期限结构缺失")
                if not has_z:
                    result["notes"].append("⚠️ Z分数未计算")
            else:
                result["data_quality"] = "✅正常"

        print(f"  [{pid_u}] ✅ 采集完成 | 质量: {result['data_quality']} | 结构: {result['term_structure']}", flush=True)
        return result

    def run(self, varieties):
        """运行全品种采集"""
        print(f"\n📋 待采集品种: {varieties}", flush=True)
        print(f"⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"⚠️  TDX本地可用: {'是' if self.tdx_collector else '否'}", flush=True)
        print(f"⚠️  降级策略: TDX报价+AKShare OI兜底+TDX期限结构", flush=True)

        for pid in varieties:
            try:
                self.results[pid.upper()] = self.collect_variety(pid)
            except Exception as e:
                print(f"\n❌ [{pid.upper()}] 采集崩溃: {traceback.format_exc()}", flush=True)
                self.results[pid.upper()] = {
                    "price": {},
                    "term_structure": "Unknown",
                    "z_score": None,
                    "data_quality": "❌缺失",
                    "notes": [f"❌ 采集崩溃: {str(e)[:200]}"],
                    "data_source": {"error": str(e)[:200]}
                }

        self._generate_report(varieties)
        return self.results

    def _generate_report(self, varieties):
        """生成汇总报告"""
        print("\n" + "=" * 70, flush=True)
        print("📊 数聚石 — 数据采集最终报告", flush=True)
        print(f"   采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"   品种总数: {len(varieties)}", flush=True)
        print("=" * 70, flush=True)

        quality_counts = {"✅正常": 0, "⚠️降级": 0, "❌缺失": 0}
        ts_counts = {"Contango": 0, "Back": 0, "flat": 0, "Unknown": 0}

        summary_rows = []
        for pid in varieties:
            pid_u = pid.upper()
            r = self.results.get(pid_u, {})
            q = r.get("data_quality", "❌缺失")
            ts = r.get("term_structure", "Unknown")
            z = r.get("z_score")
            c = r.get("price", {}).get("close", "N/A")
            v = r.get("price", {}).get("volume", "N/A")
            oi = r.get("price", {}).get("oi", "N/A")
            ds = r.get("data_source", {})

            quality_counts[q] = quality_counts.get(q, 0) + 1
            ts_counts[ts] = ts_counts.get(ts, 0) + 1

            notes_str = "; ".join(r.get("notes", []))[:80] if r.get("notes") else ""
            ds_str = f"报价:{ds.get('quote','-')} K线:{ds.get('kline','-')} 期限:{ds.get('term_structure','-')}"
            print(f"  {q} {pid_u:4s} | C={str(c):>8s} Vol={str(v):>8s} OI={str(oi):>6s} | Z={str(z):>8s} | TS={ts:>10s} | {ds_str}", flush=True)
            if notes_str:
                print(f"      ├─ {notes_str}", flush=True)

        print("-" * 70, flush=True)
        print(f"  质量分布: ✅正常={quality_counts.get('✅正常',0)} ⚠️降级={quality_counts.get('⚠️降级',0)} ❌缺失={quality_counts.get('❌缺失',0)}", flush=True)
        print(f"  期限结构: Contango={ts_counts.get('Contango',0)} Back={ts_counts.get('Back',0)} flat={ts_counts.get('flat',0)} Unknown={ts_counts.get('Unknown',0)}", flush=True)

        # 保留简洁版本到debate_phase_data.json
        output = {
            "report_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "varieties": varieties,
            "summary": {
                "total": len(varieties),
                "quality_normal": quality_counts.get("✅正常", 0),
                "quality_degraded": quality_counts.get("⚠️降级", 0),
                "quality_missing": quality_counts.get("❌缺失", 0),
                "contango": ts_counts.get("Contango", 0),
                "backwardation": ts_counts.get("Back", 0),
                "flat": ts_counts.get("flat", 0),
            },
            "data": {}
        }

        # 按议定格式输出
        for pid in varieties:
            pid_u = pid.upper()
            r = self.results.get(pid_u, {})
            output["data"][pid_u] = {
                "price": {
                    "open": r.get("price", {}).get("open"),
                    "high": r.get("price", {}).get("high"),
                    "low": r.get("price", {}).get("low"),
                    "close": r.get("price", {}).get("close"),
                    "volume": r.get("price", {}).get("volume"),
                    "oi": r.get("price", {}).get("oi"),
                },
                "term_structure": r.get("term_structure", "Unknown"),
                "z_score": r.get("z_score"),
                "data_quality": r.get("data_quality", "❌缺失"),
                "notes": r.get("notes", []),
            }

        # 保存
        output_dir = SKILL_DIR / "Temp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "debate_phase_data.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n💾 数据已保存至: {output_path}", flush=True)

        print("\n" + "=" * 70, flush=True)
        print("###END_DATA_COLLECTION", flush=True)
        print("=" * 70, flush=True)


def main():
    varieties = ['cs', 'sp', 'rb', 'hc', 'FG', 'a', 'PK', 'SA', 'i', 'si']
    collector = DebateDataCollector()
    results = collector.run(varieties)
    return results


if __name__ == "__main__":
    main()
