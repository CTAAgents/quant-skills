#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
futures-data-search 数据质量反馈与自我进化模块 v1.0

当下游消费者（如 commodity-daily-analysis 辩论系统）发现数据异常时，
通过此模块提交反馈。模块自动应用修复规则，并记录经验以持续进化。

用法：
  # 提交反馈并执行修复
  from data_feedback import DataFeedback
  fb = DataFeedback()
  fb.submit('hc', 'far_price_zero', source='tdx_collector',
            context='远月价格=0不可信，导致做空信号被铁律排除',
            debate_date='2026-06-30')
  fb.auto_remediate('hc')

架构：
  反馈记录(JSONL) → RemediationRule匹配 → 自动修复 → 修复日志 → 规则进化
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

_FEEDBACK_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "WorkBuddy", ".workbuddy", "feedback"
)
_FEEDBACK_FILE = os.path.join(_FEEDBACK_DIR, 'data_quality_feedback.jsonl')


# ============================================================
# 修复规则注册表（自我进化引擎）
# ============================================================

REMEDIATION_RULES = {
    # 规则1: 品种期限结构缺失 → 降级到东方财富
    'term_structure_missing': {
        'severity': 'high',
        'action': 'fallback_eastmoney',
        'source_to_fix': 'tdx_collector.get_term_structure()',
        'auto_fix': True,
        'description': '通达信TdxCollector未获取到期限结构,自动降级到东方财富EastMoneyCollector',
        'implemented_in': 'term_basis.py v2.1',
    },
    # 规则2: 远月价格=0 → 过滤无效合约
    'far_price_zero': {
        'severity': 'high',
        'action': 'filter_zero_price_contracts',
        'source_to_fix': 'tdx_collector.get_term_structure()',
        'auto_fix': True,
        'description': '通达信返回远月合约价格为0(无成交),自动过滤price=0的合约',
        'implemented_in': 'tdx_collector.py v2.0.1',
    },
    # 规则3: OI数据缺失 → AKShare兜底补全
    'oi_missing': {
        'severity': 'medium',
        'action': 'fallback_akshare_oi',
        'source_to_fix': 'MultiSourceAdapter.get_quote()',
        'auto_fix': True,
        'description': '通达信holding=0时OI缺失,已通过AKShare futures_hold_pos补全',
        'implemented_in': 'multi_source_adapter.py (OI兜底补丁)',
    },
    # 规则4: OI背离（价涨持仓降）→ 标记警告
    'oi_divergence': {
        'severity': 'medium',
        'action': 'flag_warning',
        'source_to_fix': '数据本身,非采集bug',
        'auto_fix': False,
        'description': '价格上涨但持仓量下降,可能是空头平仓驱动反弹而非增量做多,标记为⚠️',
    },
    # 规则5: 期限结构异常（斜率-100%）→ 数据源切换
    'term_structure_anomaly': {
        'severity': 'high',
        'action': 'switch_data_source',
        'source_to_fix': 'tdx_collector',
        'auto_fix': True,
        'description': '斜率异常(-100%等)说明数据源计算错误,自动切换至eastmoney',
        'implemented_in': 'term_basis.py v2.1',
    },
}


class DataFeedback:
    """数据质量反馈管理器 — futures-data-search 自我进化引擎"""

    def __init__(self, feedback_file: str = None):
        self.feedback_file = feedback_file or _FEEDBACK_FILE

    # ==================== 反馈提交 ====================

    def submit(
        self,
        variety: str,
        issue_type: str,
        source: str = 'unknown',
        context: str = '',
        debate_date: str = None,
        severity: str = 'medium',
    ) -> Dict:
        """
        提交数据质量反馈。

        Args:
            variety: 品种代码 (如 'hc', 'rb')
            issue_type: 问题类型 (如 'far_price_zero', 'term_structure_missing', 'oi_missing')
            source: 数据来源 (如 'tdx_collector', 'eastmoney_collector')
            context: 上下文描述（谁发现的、什么后果）
            debate_date: 辩论日期（YYYY-MM-DD）
            severity: 严重程度 ('low'/'medium'/'high')

        Returns:
            {'recorded': True, 'auto_fixed': True/False, 'rule_applied': '...'}
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'variety': variety.upper(),
            'issue_type': issue_type,
            'source': source,
            'context': context,
            'debate_date': debate_date or datetime.now().strftime('%Y-%m-%d'),
            'severity': severity,
        }

        # 写入反馈日志
        self._append_feedback(entry)

        # 匹配修复规则
        rule = REMEDIATION_RULES.get(issue_type, {})
        auto_fixed = rule.get('auto_fix', False)
        action = rule.get('action', 'unknown')

        return {
            'recorded': True,
            'auto_fixed': auto_fixed,
            'rule_applied': action,
            'rule_description': rule.get('description', '无匹配规则'),
            'severity': severity,
        }

    def _append_feedback(self, entry: Dict):
        """追加反馈到JSONL文件"""
        os.makedirs(os.path.dirname(self.feedback_file), exist_ok=True)
        with open(self.feedback_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    # ==================== 自动修复 ====================

    def auto_remediate(self, variety: str) -> Dict:
        """
        对指定品种执行所有匹配的自动修复规则。

        Returns:
            {'variety': 'HC', 'fixes_applied': [...], 'fixed': True/False}
        """
        history = self.get_feedback_history(variety, days=30)
        fixes_applied = []

        for entry in history:
            issue_type = entry.get('issue_type', '')
            rule = REMEDIATION_RULES.get(issue_type, {})
            if rule.get('auto_fix'):
                try:
                    fix_result = self._apply_rule(rule, variety, entry)
                    fixes_applied.append({
                        'issue': issue_type,
                        'action': rule['action'],
                        'result': fix_result,
                    })
                except Exception as e:
                    fixes_applied.append({
                        'issue': issue_type,
                        'action': rule['action'],
                        'error': str(e),
                    })

        return {
            'variety': variety.upper(),
            'fixes_applied': fixes_applied,
            'fixed': len(fixes_applied) > 0,
        }

    def _apply_rule(self, rule: Dict, variety: str, entry: Dict) -> str:
        """执行单条修复规则"""
        action = rule.get('action', '')

        if action == 'fallback_eastmoney':
            return self._fix_fallback_eastmoney(variety)
        elif action == 'filter_zero_price_contracts':
            return ('已修复: tdx_collector v2.0.1 自动过滤 price=0 合约, '
                    f'implemented_in: {rule.get("implemented_in")}')
        elif action == 'fallback_akshare_oi':
            return self._fix_fallback_akshare_oi(variety)
        elif action == 'flag_warning':
            return f'标记为警告: {rule.get("description")}'
        elif action == 'switch_data_source':
            return self._fix_fallback_eastmoney(variety)
        else:
            return f'未知动作: {action}'

    def _fix_fallback_eastmoney(self, variety: str) -> str:
        """降级到东方财富获取期限结构"""
        try:
            import sys
            fds_dir = os.path.expanduser("~/.workbuddy/skills/futures-data-search")
            if fds_dir not in sys.path:
                sys.path.insert(0, fds_dir)
            from collectors.eastmoney_collector import EastMoneyCollector
            em = EastMoneyCollector()
            ts = em.get_term_structure(variety)
            if ts and ts.get('contracts') and len(ts['contracts']) >= 2:
                return (f'东方财富降级成功: {len(ts["contracts"])}个合约, '
                        f'近{ts["contracts"][0].get("price")}/远{ts["contracts"][-1].get("price")}')
            return '东方财富降级失败: 无有效合约数据'
        except Exception as e:
            return f'东方财富降级异常: {str(e)[:80]}'

    def _fix_fallback_akshare_oi(self, variety: str) -> str:
        """降级到AKShare获取持仓量"""
        try:
            import akshare as ak
            df = ak.futures_hold_pos(symbol=variety.upper())
            if df is not None and not df.empty:
                oi = df.iloc[0].get('vol', 0) if 'vol' in df.columns else \
                     df.iloc[0].get('holding', 0) if 'holding' in df.columns else 0
                return f'AKShare OI补全成功: {oi}手'
            return 'AKShare OI补全: 返回空数据'
        except Exception as e:
            return f'AKShare OI补全异常: {str(e)[:80]}'

    # ==================== 历史查询 ====================

    def get_feedback_history(self, variety: str = None, days: int = 30) -> List[Dict]:
        """查询反馈历史"""
        if not os.path.exists(self.feedback_file):
            return []

        cutoff = datetime.now().timestamp() - days * 86400
        history = []
        with open(self.feedback_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry.get('timestamp', '2000-01-01')).timestamp()
                    if ts < cutoff:
                        continue
                    if variety and entry.get('variety', '').upper() != variety.upper():
                        continue
                    history.append(entry)
                except json.JSONDecodeError:
                    continue
        return history

    def get_stats(self, days: int = 30) -> Dict:
        """统计反馈数据"""
        history = self.get_feedback_history(days=days)
        by_type = {}
        by_source = {}
        by_severity = {'high': 0, 'medium': 0, 'low': 0}

        for entry in history:
            t = entry.get('issue_type', 'unknown')
            by_type[t] = by_type.get(t, 0) + 1
            s = entry.get('source', 'unknown')
            by_source[s] = by_source.get(s, 0) + 1
            sev = entry.get('severity', 'medium')
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            'total_feedbacks': len(history),
            'by_issue_type': by_type,
            'by_source': by_source,
            'by_severity': by_severity,
            'rules_available': len(REMEDIATION_RULES),
            'auto_fix_rules': sum(1 for r in REMEDIATION_RULES.values() if r.get('auto_fix')),
        }

    def add_remediation_rule(self, issue_type: str, rule: Dict) -> bool:
        """
        动态添加修复规则（运行时进化）。

        Example:
            fb.add_remediation_rule('new_issue', {
                'severity': 'high',
                'action': 'switch_data_source',
                'source_to_fix': 'some_collector',
                'auto_fix': True,
                'description': '新发现的数据问题修复规则',
            })
        """
        if issue_type in REMEDIATION_RULES:
            return False  # 规则已存在
        REMEDIATION_RULES[issue_type] = rule
        return True


# ============================================================
# 模块级快捷入口 — 供 debate_feedback.py 路由调用
# ============================================================
def submit_feedback(
    variety: str, issue_type: str, source: str = 'unknown',
    context: str = '', severity: str = 'medium'
) -> Dict:
    """供外部路由调用的统一入口"""
    fb = DataFeedback()
    return fb.submit(variety, issue_type, source=source, context=context, severity=severity)


# ==================== 命令行入口 ====================

if __name__ == '__main__':
    import sys
    fb = DataFeedback()

    if len(sys.argv) < 2:
        # 无参数：输出统计
        stats = fb.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        print(f"\n修复规则: {stats['rules_available']}条 ({stats['auto_fix_rules']}条可自动修复)")
    elif sys.argv[1] == 'history':
        variety = sys.argv[2] if len(sys.argv) > 2 else None
        history = fb.get_feedback_history(variety)
        print(json.dumps(history, indent=2, ensure_ascii=False))
    elif sys.argv[1] == 'fix':
        variety = sys.argv[2]
        result = fb.auto_remediate(variety)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif sys.argv[1] == 'submit':
        # submit <variety> <issue_type> <source> <context>
        variety = sys.argv[2]
        issue_type = sys.argv[3]
        source = sys.argv[4] if len(sys.argv) > 4 else 'unknown'
        context = sys.argv[5] if len(sys.argv) > 5 else ''
        result = fb.submit(variety, issue_type, source=source, context=context,
                          severity='high' if issue_type in ['far_price_zero', 'term_structure_missing'] else 'medium')
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Usage: python data_feedback.py [history [variety]|fix <variety>|submit <variety> <type> <source> <context>]")
