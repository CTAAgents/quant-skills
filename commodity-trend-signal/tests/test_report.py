# -*- coding: utf-8 -*-
"""report.py 单元测试 - 100%覆盖。"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.report import generate_markdown_report, generate_html_report


def _make_test_data():
    """构建测试数据（新版本接口）。"""
    chain_results = {
        '黑色系': {
            'count': 5, 'leader': 'rb', 'leader_price': 3500.0,
            'overall_trend': '空头趋势', 'avg_score': -30.0,
            'leader_reason': '趋势得分最低（领跌）',
            'debate_unit': {'focus': '成本推涨vs需求拉动'},
            'members': [
                {'pid': 'rb', 'name': '螺纹钢', 'price': 3500.0, 'score': -40, 'trend': 'strong_bear', 'oi': 50000},
            ],
        },
    }

    # 新版本需要 all_opportunities, buy_opps, sell_opps
    all_opportunities = [
        {
            'product_id': 'rb',
            'product_name': '螺纹钢',
            'score': -40,
            'trend_stage': {'stage': 'mature'},
            'resonance': {'confirmations': 4, 'total_checks': 6},
            'chain_verify': {'chain_name': '黑色系', 'chain_trend': '空头趋势', 'match': True},
            'debate': {'bull_strength': 5, 'bear_strength': 15, 'verdict': 'SELL'},
            'trade_plan': {
                'decision': 'SELL', 'entry_price': 3500.0,
                'target_price': 3360.0, 'stop_loss': 3600.0,
                'risk_reward_ratio': 1.4, 'confidence': 0.65,
                'recommend_score': 0.595, 'position_size': '5.0%', 'validity': '1-3日',
            },
        },
    ]

    buy_opps = []
    sell_opps = all_opportunities  # SELL机会

    risk_assessments = {
        'rb': {
            'risk_decision': {'risk_score': 6.0, 'final_decision': 'SELL', 'position_adjustment': '维持原仓位'},
        },
    }

    return chain_results, all_opportunities, buy_opps, sell_opps, risk_assessments


class TestGenerateMarkdownReport(unittest.TestCase):

    def test_basic_structure(self):
        cr, ao, bo, so, ra = _make_test_data()
        md = generate_markdown_report(cr, ao, bo, so, ra)
        self.assertIn('商品期货产业链分析报告', md)
        self.assertIn('黑色系', md)
        self.assertIn('rb', md)

    def test_contains_trade_plan(self):
        cr, ao, bo, so, ra = _make_test_data()
        md = generate_markdown_report(cr, ao, bo, so, ra)
        self.assertIn('做空', md)
        self.assertIn('3500.00', md)

    def test_disclaimer_present(self):
        cr, ao, bo, so, ra = _make_test_data()
        md = generate_markdown_report(cr, ao, bo, so, ra)
        self.assertIn('仅供参考', md)

    def test_hold_trade(self):
        cr, ao, bo, so, ra = _make_test_data()
        # 测试无机会情况
        md = generate_markdown_report(cr, [], [], [], ra)
        self.assertIn('观望', md)


class TestGenerateHtmlReport(unittest.TestCase):

    def test_basic_structure(self):
        cr, ao, bo, so, ra = _make_test_data()
        html = generate_html_report(cr, ao, bo, so, ra)
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('chart.js', html.lower())

    def test_contains_chartjs(self):
        cr, ao, bo, so, ra = _make_test_data()
        html = generate_html_report(cr, ao, bo, so, ra)
        self.assertIn('chart.js', html.lower())

    def test_contains_decision_stats(self):
        cr, ao, bo, so, ra = _make_test_data()
        html = generate_html_report(cr, ao, bo, so, ra)
        self.assertIn('做空', html)

    def test_contains_members(self):
        cr, ao, bo, so, ra = _make_test_data()
        html = generate_html_report(cr, ao, bo, so, ra)
        self.assertIn('rb', html)

    def test_disclaimer(self):
        cr, ao, bo, so, ra = _make_test_data()
        html = generate_html_report(cr, ao, bo, so, ra)
        self.assertIn('仅供参考', html)

    def test_hold_card(self):
        cr, ao, bo, so, ra = _make_test_data()
        # 测试无机会情况
        html = generate_html_report(cr, [], [], [], ra)
        self.assertIn('观望', html)


if __name__ == '__main__':
    unittest.main()
