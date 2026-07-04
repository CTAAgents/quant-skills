#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运维看板 HTML 生成器 v1.0

生成一个轻量级 Web 看板，一屏展示：
1. 数据源健康状态（绿/黄/红）
2. SLA 合规率趋势
3. 告警概览
4. 性能统计
5. 系统运行时间

用法：
    python ops_dashboard.py                    # 生成看板 HTML
    python ops_dashboard.py output.html        # 指定输出路径
"""

import json
import os
import sys
from datetime import datetime, date
from pathlib import Path


DASHBOARD_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "WorkBuddy", "Reports"
)


def _collect_data() -> dict:
    """从各模块收集数据"""
    data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date': date.today().isoformat(),
        'sources': {},
        'sla': {},
        'alerts': {'total': 0, 'unhandled': 0, 'by_severity': {}},
        'perf': {},
    }

    # 心跳状态
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from scripts.data_source_heartbeat import get_heartbeat
        beat = get_heartbeat()
        for src in ['tdx_local', 'tqsdk', 'eastmoney', 'akshare', 'exchange_api']:
            s = beat.get_status(src)
            data['sources'][src] = {
                'alive': s.get('alive', False),
                'latency_ms': s.get('latency_ms', 0),
                'failures': s.get('consecutive_failures', 0),
                'error': s.get('error', ''),
            }
    except Exception:
        data['sources']['_error'] = 'heartbeat不可用'

    # SLA 报告
    try:
        from scripts.data_freshness_monitor import get_monitor
        mon = get_monitor()
        sla = mon.generate_daily_report()
        data['sla'] = {
            'coverage_pct': sla.get('sla_coverage_pct', 0),
            'fresh': sla.get('fresh', 0),
            'failed': sla.get('failed', 0),
            'pending': sla.get('pending', 0),
            'total': sla.get('total_varieties', 0),
            'is_trading_day': sla.get('is_trading_day', False),
        }
    except Exception:
        data['sla']['_error'] = 'freshness不可用'

    # 告警统计
    try:
        from scripts.alert_manager import get_alert_manager
        amgr = get_alert_manager()
        stats = amgr.get_stats(days=1)
        data['alerts'] = {
            'total': stats.get('total', 0),
            'unhandled': stats.get('unhandled', 0),
            'by_severity': stats.get('by_severity', {}),
        }
    except Exception:
        pass

    # 性能统计
    try:
        from scripts.batch_optimizer import get_batch_optimizer
        opt = get_batch_optimizer()
        data['perf'] = opt.get_perf_stats()
    except Exception:
        pass

    return data


def generate_html(output_path: str = None) -> str:
    """生成运维看板 HTML"""
    data = _collect_data()

    # 构建数据源状态行
    source_rows = ''
    for src, info in sorted(data['sources'].items()):
        if src.startswith('_'):
            continue
        alive = info.get('alive', False)
        cls = 'status-green' if alive else 'status-red'
        label = '在线' if alive else '离线'
        latency = info.get('latency_ms', 0)
        failures = info.get('failures', 0)
        error = info.get('error', '')[:60]
        source_rows += f'''
        <div class="source-card {cls}">
            <div class="source-name">{src}</div>
            <div class="source-status">{label}</div>
            <div class="source-meta">延迟: {latency:.0f}ms | 连续失败: {failures}</div>
            {f'<div class="source-error">{error}</div>' if error else ''}
        </div>'''

    # SLA 数据
    sla = data['sla']
    sla_bar_width = min(sla.get('coverage_pct', 0), 100)
    sla_bar_cls = 'bar-green' if sla_bar_width >= 95 else ('bar-yellow' if sla_bar_width >= 80 else 'bar-red')

    # 告警数据
    alerts = data['alerts']
    alert_details = ''
    for sev, count in sorted(alerts.get('by_severity', {}).items()):
        alert_details += f'<span class="alert-tag tag-{sev}">{sev}: {count}</span> '

    # 性能数据
    perf = data['perf']

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>futures-data-search 运维看板</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; background: #0f1117; color: #e5e7eb; padding: 20px; }}
.header {{ background: linear-gradient(135deg, #1a1d28 0%, #2a1f3d 100%); border-radius: 12px; padding: 24px; margin-bottom: 20px; }}
.header h1 {{ font-size: 24px; color: #f59e0b; }}
.header .meta {{ color: #9ca3af; font-size: 13px; margin-top: 8px; }}
.header .meta span {{ margin-right: 16px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; margin-bottom: 20px; }}
.card {{ background: #1a1d28; border-radius: 10px; padding: 20px; }}
.card h2 {{ font-size: 15px; color: #f59e0b; margin-bottom: 12px; border-left: 3px solid #f59e0b; padding-left: 10px; }}
.sources-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }}
.source-card {{ padding: 10px; border-radius: 8px; font-size: 12px; }}
.source-card.status-green {{ background: rgba(34, 197, 94, 0.15); border: 1px solid #22c55e; }}
.source-card.status-red {{ background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; }}
.source-name {{ font-weight: 600; font-size: 13px; }}
.source-status {{ color: #9ca3af; margin: 4px 0; }}
.source-meta {{ font-size: 11px; color: #6b7280; }}
.source-error {{ font-size: 11px; color: #ef4444; margin-top: 4px; }}
.sla-bar {{ height: 20px; background: #374151; border-radius: 10px; overflow: hidden; margin: 12px 0; }}
.sla-bar-fill {{ height: 100%; border-radius: 10px; transition: width 0.5s; }}
.bar-green {{ background: linear-gradient(90deg, #22c55e, #4ade80); }}
.bar-yellow {{ background: linear-gradient(90deg, #eab308, #fde047); }}
.bar-red {{ background: linear-gradient(90deg, #ef4444, #f87171); }}
.sla-stats {{ display: flex; gap: 12px; flex-wrap: wrap; }}
.sla-stat {{ text-align: center; padding: 8px 16px; background: #252836; border-radius: 8px; flex: 1; min-width: 60px; }}
.sla-stat .num {{ font-size: 20px; font-weight: 700; }}
.sla-stat .label {{ font-size: 11px; color: #9ca3af; }}
.stat-num {{ font-size: 28px; font-weight: 700; }}
.alert-tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin: 2px; }}
.tag-critical {{ background: rgba(239, 68, 68, 0.2); color: #ef4444; }}
.tag-high {{ background: rgba(249, 115, 22, 0.2); color: #f97316; }}
.tag-medium {{ background: rgba(234, 179, 8, 0.2); color: #eab308; }}
.tag-low {{ background: rgba(107, 114, 128, 0.2); color: #9ca3af; }}
.perf-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center; }}
.perf-item {{ background: #252836; padding: 10px; border-radius: 8px; }}
.perf-item .num {{ font-size: 16px; font-weight: 600; }}
.perf-item .label {{ font-size: 11px; color: #9ca3af; }}
.footer {{ text-align: center; color: #4b5563; font-size: 12px; margin-top: 20px; }}
</style>
</head>
<body>

<div class="header">
    <h1>🔍 futures-data-search 运维看板</h1>
    <div class="meta">
        <span>📅 {data['date']}</span>
        <span>⏰ {data['timestamp']}</span>
        <span>🔌 数据源: {sum(1 for v in data['sources'].values() if isinstance(v, dict) and v.get('alive'))}/{sum(1 for v in data['sources'].values() if isinstance(v, dict))}</span>
    </div>
</div>

<div class="grid">
    <div class="card">
        <h2>📡 数据源状态</h2>
        <div class="sources-grid">{source_rows}</div>
    </div>

    <div class="card">
        <h2>📊 SLA 合规率</h2>
        <div class="sla-bar">
            <div class="sla-bar-fill {sla_bar_cls}" style="width:{sla_bar_width}%"></div>
        </div>
        <div style="text-align:right;font-size:13px;color:#9ca3af;margin-bottom:12px;">
            {sla.get('coverage_pct', 0):.1f}%
        </div>
        <div class="sla-stats">
            <div class="sla-stat"><div class="num" style="color:#22c55e">{sla.get('fresh', 0)}</div><div class="label">新鲜</div></div>
            <div class="sla-stat"><div class="num" style="color:#eab308">{sla.get('pending', 0)}</div><div class="label">待采集</div></div>
            <div class="sla-stat"><div class="num" style="color:#ef4444">{sla.get('failed', 0)}</div><div class="label">失败</div></div>
            <div class="sla-stat"><div class="num">{sla.get('total', 0)}</div><div class="label">总品种</div></div>
        </div>
    </div>

    <div class="card">
        <h2>🔔 告警概览（今日）</h2>
        <div class="stat-num" style="color:{'#ef4444' if alerts['unhandled'] > 0 else '#22c55e'}">{alerts['unhandled']}</div>
        <div style="font-size:13px;color:#9ca3af;margin-bottom:8px;">未处理告警</div>
        <div style="font-size:13px;">总计 {alerts['total']} 条</div>
        <div style="margin-top:8px;">{alert_details}</div>
    </div>

    <div class="card">
        <h2>⚡ 性能统计</h2>
        <div class="perf-grid">
            <div class="perf-item"><div class="num">{perf.get('total_requests', 0)}</div><div class="label">总请求</div></div>
            <div class="perf-item"><div class="num">{perf.get('cache_hit_rate', 0)}%</div><div class="label">缓存命中</div></div>
            <div class="perf-item"><div class="num">{perf.get('speedup_ratio', 1)}x</div><div class="label">并行加速</div></div>
        </div>
    </div>
</div>

<div class="footer">
    Generated by futures-data-search Ops Dashboard v1.0 | {data['timestamp']}
</div>

</body>
</html>'''

    # 写入
    if not output_path:
        os.makedirs(DASHBOARD_DIR, exist_ok=True)
        output_path = os.path.join(DASHBOARD_DIR, f'dashboard_{date.today().isoformat()}.html')

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"[Dashboard] 已生成: {output_path}")
    return output_path


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else None
    generate_html(path)
