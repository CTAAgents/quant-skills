#!/usr/bin/env python3
"""全市场67品种数据采集运行脚本"""
import sys, os, json, traceback
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "collectors"))
sys.path.insert(0, str(SKILL_DIR / "collectors" / "exchange_data" / "scripts"))

from debate_data_collector import DebateDataCollector

# 完整67品种列表（来自用户输入）
FULL_VARIETIES = [
    "au","ag","cu","al","zn","pb","ni","sn","ao","SS",
    "rb","hc","i","j","jm","SF","SM",
    "sc","lu","fu","bu","pg","ec",
    "PX","TA","PF","PR","eg","eb","pp","l","PL","bz","v",
    "MA","SH",
    "lc","si","ps",
    "ru","nr","br",
    "a","b","m","y","p","OI","RM","PK",
    "c","cs","SR","CF",
    "jd","lh","AP","CJ","rr",
    "FG","SA","UR","sp"
]

print("=" * 70, flush=True)
print(f"📊 数聚石 — 辩论专家团全市场扫描", flush=True)
print(f"   品种数: {len(FULL_VARIETIES)}", flush=True)
print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
print(f"   模式: full_scan", flush=True)
print("=" * 70, flush=True)

collector = DebateDataCollector()
results = collector.run(FULL_VARIETIES)

# 额外输出结构化JSON到stdout（供主agent读取）
output = {
    "mode": "full_scan",
    "collected_count": len([k for k, v in results.items() if v.get("data_quality") != "❌缺失"]),
    "total_count": len(FULL_VARIETIES),
    "quality": f"{len([k for k, v in results.items() if v.get('data_quality') == '✅正常'])}/{len(FULL_VARIETIES)} ✅正常",
    "summary": {
        "normal": len([k for k, v in results.items() if v.get('data_quality') == '✅正常']),
        "degraded": len([k for k, v in results.items() if v.get('data_quality') == '⚠️降级']),
        "missing": len([k for k, v in results.items() if v.get('data_quality') == '❌缺失']),
        "contango": len([k for k, v in results.items() if v.get('term_structure') == 'Contango']),
        "back": len([k for k, v in results.items() if v.get('term_structure') == 'Back']),
        "flat": len([k for k, v in results.items() if v.get('term_structure') == 'flat']),
    }
}
print("\n" + "=" * 70, flush=True)
print("📤 结构化数据集输出:", flush=True)
print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)
print("###END_DATA_COLLECTION", flush=True)
print("=" * 70, flush=True)
