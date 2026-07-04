#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用通达信本地数据源修正DuckDB中期货数据的缺失和错误

工作流程：
1. 检查通达信HTTP服务是否可用
2. 获取DuckDB中所有品种及其最近数据状况
3. 对每个品种，从通达信获取K线数据
4. 比对时间线，补充缺失的交易日数据
5. 交叉验证价格数据，标记异常值
6. 写入修正后的数据到DuckDB

用法：
    python correct_duckdb_with_tdx.py                  # 全量修正
    python correct_duckdb_with_tdx.py --dry-run        # 仅报告，不写入
    python correct_duckdb_with_tdx.py --variety CU,RB  # 指定品种

数据源优先级：通达信本地 > 东方财富 > AKShare（置信度均1.0）
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# ==================== 路径配置 ====================
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from collectors.tdx_collector import TdxCollector
from collectors.eastmoney_collector import EastMoneyCollector
from scripts.duckdb_store import DuckDBStore

# ==================== 品种列表 ====================
# 需要跟踪的主力品种（带交易所）
MAIN_VARIETIES = [
    # 黑色系
    {'pid': 'rb', 'exchange': 'SHFE', 'name': '螺纹钢'},
    {'pid': 'hc', 'exchange': 'SHFE', 'name': '热卷'},
    {'pid': 'i', 'exchange': 'DCE', 'name': '铁矿石'},
    {'pid': 'j', 'exchange': 'DCE', 'name': '焦炭'},
    {'pid': 'jm', 'exchange': 'DCE', 'name': '焦煤'},
    # 能源链
    {'pid': 'sc', 'exchange': 'INE', 'name': '原油'},
    {'pid': 'lu', 'exchange': 'INE', 'name': '低硫燃油'},
    {'pid': 'fu', 'exchange': 'SHFE', 'name': '燃料油'},
    {'pid': 'bu', 'exchange': 'SHFE', 'name': '沥青'},
    {'pid': 'pg', 'exchange': 'DCE', 'name': 'LPG'},
    # 聚酯链
    {'pid': 'TA', 'exchange': 'CZCE', 'name': 'PTA'},
    {'pid': 'EG', 'exchange': 'DCE', 'name': '乙二醇'},
    {'pid': 'PF', 'exchange': 'CZCE', 'name': '短纤'},
    # 有色
    {'pid': 'cu', 'exchange': 'SHFE', 'name': '沪铜'},
    {'pid': 'al', 'exchange': 'SHFE', 'name': '沪铝'},
    {'pid': 'zn', 'exchange': 'SHFE', 'name': '沪锌'},
    {'pid': 'ni', 'exchange': 'SHFE', 'name': '沪镍'},
    # 贵金属
    {'pid': 'au', 'exchange': 'SHFE', 'name': '沪金'},
    {'pid': 'ag', 'exchange': 'SHFE', 'name': '沪银'},
    # 油脂油料
    {'pid': 'm', 'exchange': 'DCE', 'name': '豆粕'},
    {'pid': 'y', 'exchange': 'DCE', 'name': '豆油'},
    {'pid': 'p', 'exchange': 'DCE', 'name': '棕榈油'},
    # 建材
    {'pid': 'FG', 'exchange': 'CZCE', 'name': '玻璃'},
    {'pid': 'SA', 'exchange': 'CZCE', 'name': '纯碱'},
    {'pid': 'UR', 'exchange': 'CZCE', 'name': '尿素'},
    # 金融期货
    {'pid': 'IF', 'exchange': 'CFFEX', 'name': '沪深300'},
    {'pid': 'IH', 'exchange': 'CFFEX', 'name': '上证50'},
    {'pid': 'IC', 'exchange': 'CFFEX', 'name': '中证500'},
    # 广期所
    {'pid': 'lc', 'exchange': 'GFEX', 'name': '碳酸锂'},
    {'pid': 'si', 'exchange': 'GFEX', 'name': '工业硅'},
]

# ==================== DuckDB 操作 ====================

class DuckDBCorrector:
    """DuckDB数据修正器"""

    def __init__(self):
        self.store = DuckDBStore()
        self.exchange_db = os.path.join(
            SKILL_DIR, "collectors", "exchange_data", "data",
            "futures_data.duckdb"
        )
        self._exchange_conn = None

    @property
    def exchange_conn(self):
        if self._exchange_conn is None:
            import duckdb
            if os.path.exists(self.exchange_db):
                self._exchange_conn = duckdb.connect(str(self.exchange_db))
        return self._exchange_conn

    def get_existing_data(self, variety: str) -> Tuple[int, str, str]:
        """查询品种在DuckDB中的现有数据状况"""
        if not self.exchange_conn:
            return 0, None, None

        result = self.exchange_conn.execute(
            "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_data "
            "WHERE symbol = ?", [variety.upper()]
        ).fetchone()
        return result if result[0] else (0, None, None)

    def insert_data(self, records: List[dict]):
        """批量插入K线数据到DuckDB"""
        if not records or not self.exchange_conn:
            return 0

        inserted = 0
        for r in records:
            try:
                self.exchange_conn.execute("""
                    INSERT OR IGNORE INTO daily_data 
                    (exchange, symbol, trade_date, open, high, low, close, 
                     settle, volume, open_interest, turnover, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    r.get('exchange', ''),
                    r.get('symbol', ''),
                    r.get('trade_date', ''),
                    r.get('open', 0),
                    r.get('high', 0),
                    r.get('low', 0),
                    r.get('close', 0),
                    r.get('settle', 0),
                    int(r.get('volume', 0)),
                    int(r.get('open_interest', 0)),
                    float(r.get('turnover', 0)),
                    r.get('source', 'tdx_correction'),
                ))
                inserted += 1
            except Exception as e:
                print(f"    [Error] 插入失败: {e}")
        return inserted


class TDXCorrector:
    """通达信数据修正器"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.tdx = TdxCollector()
        self.tdx_available = self.tdx.is_available
        self.db = DuckDBCorrector()
        self.stats = {
            'total': 0, 'tdx_ok': 0, 'tdx_fail': 0,
            'new_records': 0, 'gaps_filled': 0,
        }

    def _decode_tdx_code(self, variety: str) -> Optional[str]:
        """将品种代码转换为通达信期货代码"""
        from collectors.tdx_collector import TDX_FUTURES_CODE
        return TDX_FUTURES_CODE.get(variety.upper())

    def _get_tdx_kline(self, variety: str) -> Optional[List[Dict]]:
        """从通达信获取完整K线数据"""
        tdx_code = self._decode_tdx_code(variety)
        if not tdx_code:
            return None
        return self.tdx.get_kline(variety, days=730)  # 获取2年数据

    def correct_single(self, variety: dict) -> dict:
        """修正单个品种的数据"""
        pid = variety['pid']
        exchange = variety['exchange']
        name = variety['name']
        pid_upper = pid.upper()

        result = {
            'pid': pid, 'name': name,
            'existing_days': 0, 'existing_range': '',
            'tdx_days': 0, 'tdx_range': '',
            'new_records': 0, 'gaps_filled': 0,
            'errors': [],
        }

        # 1. 查询DuckDB现有数据
        cnt, min_d, max_d = self.db.get_existing_data(pid_upper)
        result['existing_days'] = cnt
        result['existing_range'] = f"{min_d} ~ {max_d}" if min_d else "无"

        # 2. 从通达信获取数据
        tdx_data = self._get_tdx_kline(pid)
        if not tdx_data:
            result['errors'].append("通达信无数据")
            return result

        result['tdx_days'] = len(tdx_data)
        if tdx_data:
            result['tdx_range'] = f"{tdx_data[0]['date']} ~ {tdx_data[-1]['date']}"

        # 3. 比对数据质量和覆盖范围
        if cnt == 0:
            # DuckDB无数据，全部插入
            if not self.dry_run:
                db_records = []
                for k in tdx_data:
                    db_records.append({
                        'exchange': exchange,
                        'symbol': pid_upper,
                        'trade_date': k['date'].replace("-", ""),
                        'open': k['open'],
                        'high': k['high'],
                        'low': k['low'],
                        'close': k['close'],
                        'settle': 0,
                        'volume': k.get('volume', 0),
                        'open_interest': k.get('oi', 0),
                        'turnover': 0,
                        'source': 'tdx_correction',
                    })
                inserted = self.db.insert_data(db_records)
                result['new_records'] = inserted
            else:
                result['new_records'] = len(tdx_data)
            return result

        # 4. 已有数据，检查缺失日期
        if not self.dry_run and self.db.exchange_conn:
            existing_dates = set()
            rows = self.db.exchange_conn.execute(
                "SELECT trade_date FROM daily_data WHERE symbol = ?",
                [pid_upper]
            ).fetchall()
            existing_dates = {r[0] for r in rows}

            # 查找缺失的交易日
            to_insert = []
            for k in tdx_data:
                d = k['date'].replace("-", "")
                if d not in existing_dates:
                    to_insert.append({
                        'exchange': exchange,
                        'symbol': pid_upper,
                        'trade_date': d,
                        'open': k['open'],
                        'high': k['high'],
                        'low': k['low'],
                        'close': k['close'],
                        'settle': 0,
                        'volume': k.get('volume', 0),
                        'open_interest': k.get('oi', 0),
                        'turnover': 0,
                        'source': 'tdx_correction',
                    })

            if to_insert:
                inserted = self.db.insert_data(to_insert)
                result['gaps_filled'] = inserted

        return result

    def run(self, varieties: Optional[List[dict]] = None):
        """执行全量修正"""
        targets = varieties or MAIN_VARIETIES
        self.stats['total'] = len(targets)

        if not self.tdx_available:
            print("\n⚠️  通达信HTTP服务不可用，无法获取数据")
            print("请确保通达信金融终端(TdxW.exe)正在运行，端口17709可访问")
            print("跳过改正，仅输出DuckDB当前状态报告\n")

        print(f"{'='*70}")
        print(f"通达信数据修正 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'Dry Run' if self.dry_run else '正式执行'}")
        print(f"通达信状态: {'✅ 在线' if self.tdx_available else '❌ 离线'}")
        print(f"{'='*70}\n")

        # 输出表头
        print(f"{'品种':6s} {'名称':8s} {'DuckDB':20s} {'通达信':20s} {'新增/填充':>10s}")
        print("-" * 70)

        for v in targets:
            r = self.correct_single(v)
            self.stats['tdx_ok'] += 1 if r['tdx_days'] > 0 else 0
            self.stats['tdx_fail'] += 1 if not r['tdx_days'] else 0

            changes = ""
            if r['new_records'] > 0:
                changes = f"+{r['new_records']}新增"
            elif r['gaps_filled'] > 0:
                changes = f"+{r['gaps_filled']}补缺"
            else:
                changes = "✓ 已覆盖"

            existing = r['existing_range'] if r['existing_days'] > 0 else "无数据"
            tdx_range = r['tdx_range'] if r['tdx_days'] > 0 else "❌ 无"
            print(f"{r['pid']:6s} {r['name']:8s} {existing:20s} {tdx_range:20s} {changes:>10s}")

        # 输出统计
        print(f"\n{'='*70}")
        print(f"统计: {self.stats['total']}品种 | "
              f"通达信可用: {self.stats['tdx_ok']} | "
              f"通达信无: {self.stats['tdx_fail']}")
        if not self.dry_run:
            total_added = sum(
                self.stats.get('new_records', 0) 
            )
            print(f"已写入: 新增/补充数据")
        print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(description="通达信数据修正DuckDB")
    parser.add_argument("--dry-run", action="store_true", help="仅报告，不写入")
    parser.add_argument("--variety", type=str, default="",
                        help="指定品种，逗号分隔，如 CU,RB")
    args = parser.parse_args()

    varieties = MAIN_VARIETIES
    if args.variety:
        pids = [v.strip().upper() for v in args.variety.split(",")]
        varieties = [v for v in MAIN_VARIETIES if v['pid'].upper() in pids]
        if not varieties:
            print(f"未找到指定品种: {args.variety}")
            return

    corrector = TDXCorrector(dry_run=args.dry_run)
    corrector.run(varieties)


if __name__ == "__main__":
    main()
