#!/usr/bin/env python3
"""
辩论专家团 — 数聚石 全品种数据采集 (full_scan)
日期: 2026-07-01
全67品种扫描 → 产出结构化JSON报告
"""

import json
import sys
import os
from pathlib import Path

# 添加技能路径
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "collectors"))

from debate_data_collector import DebateDataCollector

# 全67品种列表（来自SKILL.md辩论专家团数据采集接口）
FULL_VARIETIES = [
    "rb","hc","i","j","jm","SF","SM",
    "sc","lu","fu","bu","pg",
    "PX","TA","PF","PR","eg","eb",
    "v","pp","l","MA","SH",
    "cu","al","zn","pb","ni","sn","ao","SS",
    "au","ag",
    "a","b","m","y","p","OI","RM","PK",
    "c","cs","SR","CF",
    "jd","lh","AP","CJ","FG","SA","UR",
    "ru","nr","br","sp","op",
    "lc","si","ps","ec",
    "rr","ad","CY","PL","bz"
]

def main():
    print("=" * 70)
    print("📊 数聚石 — 辩论专家团全品种数据采集")
    print(f"   模式: full_scan")
    print(f"   日期: 2026-07-01")
    print(f"   品种数: {len(FULL_VARIETIES)}")
    print(f"   数据源: tdx_local(优先) → TqSDK → 东方财富 → AKShare")
    print("=" * 70)
    
    collector = DebateDataCollector()
    results = collector.run(FULL_VARIETIES)
    
    return results

if __name__ == "__main__":
    main()
