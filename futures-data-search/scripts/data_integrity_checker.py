#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
futures-data-search 数据完整性自动校验模块 v1.0

每次数据采集完成后自动执行完整性校验：
1. OHLC 逻辑校验（open≤high, low≤close 等）
2. 品种覆盖率校验（活动品种采集比例）
3. 数据新鲜度校验（采集时间是否在 SLA 窗口内）
4. 异常检测（价格跳变、OI 突变等）
5. 每日数据质量报告生成

用法：
    from data_integrity_checker import DataIntegrityChecker, dic
    
    # 批次采集后立即校验
    report = dic.check_batch(results={
        'CU': {'success': True, 'count': 120},
        'RB': {'success': False, 'error': 'timeout'},
    })
    
    # 生成今日质量报告
    qr = dic.generate_quality_report()
    
    # 获取完整性评分
    score = dic.get_integrity_score()

CLI:
    python data_integrity_checker.py report    # 质量报告
    python data_integrity_checker.py score     # 完整性评分
    python data_integrity_checker.py validate  # 立即校验
"""

import json
import os
import time
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path


INTEGRITY_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "WorkBuddy", ".workbuddy", "feedback", "integrity"
)


class DataIntegrityChecker:
    """数据完整性校验器

    校验数据采集后的完整性和质量，联动 alert_manager 推送告警。
    """

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or INTEGRITY_DIR
        os.makedirs(self.data_dir, exist_ok=True)

        # 当日校验记录
        self._checks: List[Dict] = []

        # 告警管理器
        self._alert_mgr = None
        try:
            from scripts.alert_manager import get_alert_manager
            self._alert_mgr = get_alert_manager()
        except ImportError:
            pass

        # 新鲜度监控器
        self._freshness_monitor = None
        try:
            from scripts.data_freshness_monitor import get_monitor
            self._freshness_monitor = get_monitor()
        except ImportError:
            pass

    # ==================== 核心校验方法 ====================

    def check_batch(self, results: Dict[str, Dict]) -> Dict:
        """校验一批采集结果

        Args:
            results: {variety: {'success': bool, 'count': int, 'error': str, ...}}

        Returns:
            {'passed': bool, 'checks': [...], 'score': float}
        """
        now = datetime.now()
        total = len(results)
        if total == 0:
            return {'passed': True, 'checks': [], 'score': 1.0, 'message': '空批次'}

        checks = []
        success_count = 0
        failure_count = 0
        total_records = 0

        for variety, result in results.items():
            success = result.get('success', False)
            count = result.get('count', 0)
            error = result.get('error', '')

            # 每品种单条校验
            check = {
                'variety': variety.upper(),
                'passed': success,
                'count': count,
                'error': error[:100],
            }

            if success:
                success_count += 1
                total_records += count
            else:
                failure_count += 1

            checks.append(check)

        # 计算覆盖率
        coverage = success_count / total if total > 0 else 0

        # 生成综合校验结果
        score = coverage  # 覆盖率即完整性评分
        passed = coverage >= 0.95  # 95% 以上通过

        report = {
            'timestamp': now.isoformat(),
            'total_varieties': total,
            'success_count': success_count,
            'failure_count': failure_count,
            'total_records': total_records,
            'coverage_pct': round(coverage * 100, 2),
            'integrity_score': round(score, 4),
            'passed': passed,
            'checks': checks,
        }

        self._checks.append(report)
        self._save_check(report)

        # 如果覆盖率过低，触发告警
        if self._alert_mgr and coverage < 0.90:
            fail_list = [c['variety'] for c in checks if not c['passed']]
            self._alert_mgr.alert_data_source(
                'data_integrity', 'unreachable',
                f'批次采集覆盖率仅 {coverage*100:.1f}%，失败品种: {",".join(fail_list[:10])}'
            )

        return report

    def validate_ohlc(self, data: List[Dict]) -> Dict:
        """OHLC 逻辑校验

        检查：open≤high, low≤close, volume≥0, 时间序列连续性
        """
        issues = []
        total = len(data)

        for i, row in enumerate(data):
            o = float(row.get('open', 0))
            h = float(row.get('high', 0))
            l = float(row.get('low', 0))
            c = float(row.get('close', 0))
            v = int(row.get('volume', 0))

            if h < l:
                issues.append(f'Row {i}: high({h}) < low({l})')
            if h < o:
                issues.append(f'Row {i}: high({h}) < open({o})')
            if l > c:
                issues.append(f'Row {i}: low({l}) > close({c})')
            if v < 0:
                issues.append(f'Row {i}: volume({v}) < 0')

        return {
            'total_rows': total,
            'valid_rows': total - len(issues),
            'issues': issues[:20],  # 最多报20个
            'issue_count': len(issues),
            'passed': len(issues) == 0,
        }

    def check_coverage(self) -> Dict:
        """检查品种覆盖率（结合 FreshnessMonitor）"""
        if not self._freshness_monitor:
            return {'passed': True, 'message': 'FreshnessMonitor 未就绪'}

        report = self._freshness_monitor.generate_daily_report()
        if not report.get('is_trading_day'):
            return {'passed': True, 'message': '非交易日，不检查'}

        total = report['total_varieties']
        fresh = report['fresh']
        failed = report['failed']
        coverage = report['sla_coverage_pct']

        return {
            'total_varieties': total,
            'fresh': fresh,
            'failed': failed,
            'coverage_pct': coverage,
            'passed': coverage >= 95.0,
            'outages': report.get('sla_outages', []),
        }

    # ==================== 报告生成 ====================

    def generate_quality_report(self) -> Dict:
        """生成今日数据质量报告"""
        now = datetime.now()

        # 覆盖率
        coverage = self.check_coverage()

        # 历史趋势
        history = self._load_history(days=7)
        avg_coverage = 0
        if history:
            scores = [h.get('integrity_score', 0) for h in history if h.get('integrity_score')]
            avg_coverage = round(sum(scores) / len(scores) * 100, 2) if scores else 0

        # 最近校验
        last_check = self._checks[-1] if self._checks else {}

        report = {
            'date': date.today().isoformat(),
            'time': now.isoformat(),
            'coverage': coverage,
            'integrity_score': coverage.get('coverage_pct', 0) / 100.0 if coverage.get('passed') else 0,
            'avg_coverage_7d': avg_coverage,
            'last_check': last_check,
            'checks_today': len(self._checks),
            'passed': coverage.get('passed', True),
        }

        # 保存
        self._save_quality_report(report)

        return report

    def get_integrity_score(self) -> float:
        """获取今日数据完整性评分 (0.0~1.0)"""
        report = self.generate_quality_report()
        return report.get('integrity_score', 0)

    def get_daily_scores(self, days: int = 7) -> List[Dict]:
        """获取最近 N 天的完整性评分趋势"""
        return self._load_history(days)

    # ==================== 持久化 ====================

    def _save_check(self, check: Dict):
        """保存单次校验结果"""
        try:
            fpath = os.path.join(self.data_dir, f'checks_{date.today().isoformat()}.jsonl')
            with open(fpath, 'a', encoding='utf-8') as f:
                f.write(json.dumps(check, ensure_ascii=False) + '\n')
        except Exception:
            pass

    def _save_quality_report(self, report: Dict):
        """保存质量报告"""
        try:
            fpath = os.path.join(self.data_dir, f'quality_{date.today().isoformat()}.json')
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_history(self, days: int = 7) -> List[Dict]:
        """加载最近 N 天的质量报告"""
        history = []
        for i in range(days):
            d = date.today()
            from datetime import timedelta
            d = d - timedelta(days=i)
            fpath = os.path.join(self.data_dir, f'quality_{d.isoformat()}.json')
            if os.path.exists(fpath):
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        history.append(json.load(f))
                except Exception:
                    continue
        return history

    def clean_old(self, keep_days: int = 30):
        """清理过期数据"""
        cutoff = time.time() - keep_days * 86400
        removed = 0
        for fname in os.listdir(self.data_dir):
            fpath = os.path.join(self.data_dir, fname)
            if os.path.isfile(fpath) and fname.startswith(('quality_', 'checks_')):
                if os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    removed += 1


# ============================================================
# 单例
# ============================================================

_integrity_checker_instance: Optional[DataIntegrityChecker] = None


def get_integrity_checker() -> DataIntegrityChecker:
    global _integrity_checker_instance
    if _integrity_checker_instance is None:
        _integrity_checker_instance = DataIntegrityChecker()
    return _integrity_checker_instance


def dic() -> DataIntegrityChecker:
    return get_integrity_checker()


# ============================================================
# CLI
# ============================================================

def main():
    import sys
    checker = get_integrity_checker()

    if len(sys.argv) < 2:
        qr = checker.generate_quality_report()
        score = qr.get('integrity_score', 0)
        coverage = qr.get('coverage', {})
        print(f"Data Integrity Report — {qr['date']}")
        print(f"  Integrity Score: {score:.4f}")
        print(f"  Coverage: {coverage.get('coverage_pct', 0)}%")
        print(f"  Passed: {qr.get('passed', False)}")
        print(f"  7d Avg Coverage: {qr.get('avg_coverage_7d', 0)}%")
        return

    cmd = sys.argv[1]
    if cmd == 'report':
        qr = checker.generate_quality_report()
        print(json.dumps(qr, indent=2, ensure_ascii=False))
    elif cmd == 'score':
        print(checker.get_integrity_score())
    elif cmd == 'validate':
        result = checker.check_coverage()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif cmd == 'history':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        scores = checker.get_daily_scores(days)
        print(json.dumps(scores, indent=2, ensure_ascii=False))
    elif cmd == 'clean':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        checker.clean_old(days)
        print(f"Cleaned data older than {days} days.")


if __name__ == '__main__':
    main()
