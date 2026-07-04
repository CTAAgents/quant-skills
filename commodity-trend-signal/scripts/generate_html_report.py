#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成商品期货每日深度分析HTML报告
"""

import os
import json
import time
from datetime import datetime

def generate_html_report():
    """生成HTML报告"""
    print("=" * 60)
    print("生成商品期货每日深度分析HTML报告")
    print("=" * 60)
    
    # 读取趋势信号报告
    report_date = datetime.now().strftime('%Y-%m-%d')
    report_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'Commodities', 'Reports', '商品期货深度分析', report_date)
    
    # 查找最新的报告文件
    report_files = [f for f in os.listdir(report_dir) if f.startswith('trend_signal_') and f.endswith('.md')]
    if not report_files:
        print("未找到趋势信号报告")
        return None
    
    latest_report = sorted(report_files)[-1]
    report_path = os.path.join(report_dir, latest_report)
    
    # 读取报告内容
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析报告内容
    lines = content.split('\n')
    
    # 提取数据
    data = {
        'date': report_date,
        'data_source': 'AKShare（futures_main_sina）',
        'analysis_logic': '自下而上（品种信号→产业链验证→置信度排序）',
        'opportunities': [],
        'statistics': {
            'total_scanned': 0,
            'candidates': 0,
            'buy_opportunities': 0,
            'sell_opportunities': 0
        }
    }
    
    # 解析表格数据
    in_table = False
    for line in lines:
        if '| 排名 | 品种 | 方向 |' in line:
            in_table = True
            continue
        
        if in_table and line.startswith('|'):
            # 解析表格行
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 11:
                try:
                    opportunity = {
                        'rank': int(parts[1]),
                        'symbol': parts[2],
                        'direction': parts[3],
                        'confidence': parts[4],
                        'risk_reward': parts[5],
                        'recommend_score': parts[6],
                        'entry_price': parts[7],
                        'target_price': parts[8],
                        'stop_loss': parts[9],
                        'position': parts[10],
                        'trend_stage': parts[11]
                    }
                    data['opportunities'].append(opportunity)
                except:
                    pass
        
        if in_table and not line.startswith('|'):
            in_table = False
    
    # 解析统计信息
    for line in lines:
        if '扫描品种总数' in line:
            try:
                data['statistics']['total_scanned'] = int(line.split('：')[1].replace('个', ''))
            except:
                pass
        elif '通过筛选的候选信号' in line:
            try:
                data['statistics']['candidates'] = int(line.split('：')[1].replace('个', ''))
            except:
                pass
        elif '做多机会' in line:
            try:
                data['statistics']['buy_opportunities'] = int(line.split('：')[1].replace('个', ''))
            except:
                pass
        elif '做空机会' in line:
            try:
                data['statistics']['sell_opportunities'] = int(line.split('：')[1].replace('个', ''))
            except:
                pass
    
    # 生成HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>商品期货每日深度分析 - {data['date']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .header .subtitle {{
            font-size: 1.2em;
            opacity: 0.8;
        }}
        
        .header .meta {{
            margin-top: 20px;
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
        }}
        
        .meta-item {{
            background: rgba(255,255,255,0.1);
            padding: 10px 20px;
            border-radius: 10px;
            font-size: 0.9em;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .section {{
            margin-bottom: 40px;
        }}
        
        .section-title {{
            font-size: 1.8em;
            color: #1a1a2e;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #3a7bd5;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .section-title .icon {{
            font-size: 1.2em;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
        }}
        
        .stat-card .number {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-card .label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        
        .opportunities-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .opportunities-table th {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        
        .opportunities-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        
        .opportunities-table tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        
        .opportunities-table tr:hover {{
            background: #f0f0f0;
        }}
        
        .direction-buy {{
            color: #27ae60;
            font-weight: bold;
        }}
        
        .direction-sell {{
            color: #e74c3c;
            font-weight: bold;
        }}
        
        .confidence-high {{
            background: #27ae60;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8em;
        }}
        
        .confidence-medium {{
            background: #f39c12;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8em;
        }}
        
        .confidence-low {{
            background: #e74c3c;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8em;
        }}
        
        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            margin-top: 20px;
        }}
        
        .risk-warning {{
            background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
            padding: 25px;
            border-radius: 15px;
            margin-top: 30px;
        }}
        
        .risk-warning h3 {{
            color: #c0392b;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .risk-warning ul {{
            list-style: none;
            padding: 0;
        }}
        
        .risk-warning li {{
            padding: 8px 0;
            padding-left: 20px;
            position: relative;
        }}
        
        .risk-warning li:before {{
            content: "⚠️";
            position: absolute;
            left: 0;
        }}
        
        .footer {{
            background: #1a1a2e;
            color: white;
            padding: 30px;
            text-align: center;
            font-size: 0.9em;
        }}
        
        .footer .disclaimer {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.2);
            opacity: 0.8;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8em;
            }}
            
            .header .meta {{
                flex-direction: column;
                gap: 10px;
            }}
            
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .opportunities-table {{
                font-size: 0.9em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 商品期货每日深度分析</h1>
            <div class="subtitle">趋势信号发现 + 产业链验证 + 置信度排序</div>
            <div class="meta">
                <div class="meta-item">📅 日期: {data['date']}</div>
                <div class="meta-item">📡 数据源: {data['data_source']}</div>
                <div class="meta-item">🔍 分析逻辑: {data['analysis_logic']}</div>
                <div class="meta-item">⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2 class="section-title"><span class="icon">📈</span> 交易机会汇总</h2>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="number">{data['statistics']['candidates']}</div>
                        <div class="label">有效交易机会</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{data['statistics']['buy_opportunities']}</div>
                        <div class="label">做多机会</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{data['statistics']['sell_opportunities']}</div>
                        <div class="label">做空机会</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{data['statistics']['total_scanned']}</div>
                        <div class="label">扫描品种总数</div>
                    </div>
                </div>
                
                <table class="opportunities-table">
                    <thead>
                        <tr>
                            <th>排名</th>
                            <th>品种</th>
                            <th>方向</th>
                            <th>置信度</th>
                            <th>盈亏比</th>
                            <th>推荐分</th>
                            <th>入场价</th>
                            <th>目标价</th>
                            <th>止损价</th>
                            <th>仓位</th>
                            <th>趋势阶段</th>
                        </tr>
                    </thead>
                    <tbody>
"""
    
    # 添加表格行
    for opp in data['opportunities']:
        direction_class = 'direction-buy' if opp['direction'] == '做多' else 'direction-sell'
        
        # 置信度样式
        conf_value = opp['confidence'].replace('%', '')
        try:
            conf_num = int(conf_value)
            if conf_num >= 70:
                conf_class = 'confidence-high'
            elif conf_num >= 50:
                conf_class = 'confidence-medium'
            else:
                conf_class = 'confidence-low'
        except:
            conf_class = 'confidence-medium'
        
        html += f"""
                        <tr>
                            <td>{opp['rank']}</td>
                            <td><strong>{opp['symbol']}</strong></td>
                            <td class="{direction_class}">{opp['direction']}</td>
                            <td><span class="{conf_class}">{opp['confidence']}</span></td>
                            <td>{opp['risk_reward']}</td>
                            <td>{opp['recommend_score']}</td>
                            <td>{opp['entry_price']}</td>
                            <td>{opp['target_price']}</td>
                            <td>{opp['stop_loss']}</td>
                            <td>{opp['position']}</td>
                            <td>{opp['trend_stage']}</td>
                        </tr>
"""
    
    html += """
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h2 class="section-title"><span class="icon">📊</span> 信号分布图表</h2>
                
                <div class="chart-container">
                    <canvas id="signalChart" width="400" height="200"></canvas>
                </div>
            </div>
            
            <div class="risk-warning">
                <h3>⚠️ 风险提示</h3>
                <ul>
                    <li>技术指标有滞后性，需结合市场情绪判断</li>
                    <li>期货交易具有高杠杆特性，风险较大</li>
                    <li>产业链基本面变化可能影响价格走势</li>
                    <li>宏观经济政策变化可能带来系统性风险</li>
                    <li>以上内容由 AI 基于公开信息整理生成，仅供参考，不构成任何投资建议</li>
                </ul>
            </div>
        </div>
        
        <div class="footer">
            <div>商品期货每日深度分析系统 v2.11</div>
            <div class="disclaimer">
                ⚠️ 免责声明：本报告仅供参考，不构成任何投资建议。投资有风险，决策需谨慎。
            </div>
        </div>
    </div>
    
    <script>
        // 信号分布图表
        const ctx = document.getElementById('signalChart').getContext('2d');
        
        // 准备数据
        const buyCount = """ + str(data['statistics']['buy_opportunities']) + """;
        const sellCount = """ + str(data['statistics']['sell_opportunities']) + """;
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['做多机会', '做空机会'],
                datasets: [{
                    data: [buyCount, sellCount],
                    backgroundColor: [
                        'rgba(39, 174, 96, 0.8)',
                        'rgba(231, 76, 60, 0.8)'
                    ],
                    borderColor: [
                        'rgba(39, 174, 96, 1)',
                        'rgba(231, 76, 60, 1)'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                            pointStyleWidth: 10,
                            font: {
                                size: 14
                            }
                        }
                    },
                    title: {
                        display: true,
                        text: '交易机会分布',
                        font: {
                            size: 18,
                            weight: 'bold'
                        },
                        padding: {
                            top: 10,
                            bottom: 30
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>
"""
    
    # 保存HTML文件
    html_file = os.path.join(report_dir, f'daily_analysis_{datetime.now().strftime("%Y%m%d")}.html')
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"HTML报告已保存: {html_file}")
    print("=" * 60)
    
    return html_file

if __name__ == '__main__':
    result = generate_html_report()
    if result:
        print(f"\nHTML报告生成完成: {result}")
    else:
        print("\nHTML报告生成失败")