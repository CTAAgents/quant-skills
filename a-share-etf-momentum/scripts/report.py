"""
A股ETF双动量轮动策略 - 报告生成模块
生成HTML格式的回测报告
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List

from .backtest import BacktestResult
from .config import Config


class ReportGenerator:
    """报告生成器"""

    def __init__(self, result: BacktestResult, config: Config = None):
        self.result = result
        self.config = config or Config()

    def generate_html(self, output_path: str = None) -> str:
        """生成HTML报告"""
        if output_path is None:
            output_dir = os.path.join(os.path.dirname(__file__), self.config.output_dir)
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"dual_momentum_backtest_{timestamp}.html")

        html_content = self._build_html()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path

    def _build_html(self) -> str:
        """构建HTML内容"""
        r = self.result

        # 准备图表数据
        dates = [record.date.strftime("%Y-%m-%d") for record in r.daily_records]
        navs = [record.nav for record in r.daily_records]
        benchmark_navs = [record.benchmark_nav for record in r.daily_records]
        holdings = [record.holding_name for record in r.daily_records]

        # 调仓记录表格
        rebalance_rows = ""
        for record in r.rebalance_records:
            etf_name = record.selected_etf or "N/A"
            try:
                etf_name = self.config.get_etf_by_code(record.selected_etf).name
            except (ValueError, AttributeError):
                pass

            rebalance_rows += f"""
            <tr>
                <td>{record.date.strftime("%Y-%m-%d")}</td>
                <td>{"多头" if record.is_bullish else "空头"}</td>
                <td>{record.benchmark_return:.2%}</td>
                <td>{etf_name}</td>
                <td>{record.reason}</td>
            </tr>"""

        # 持仓分布
        holding_dist_rows = ""
        for name, pct in sorted(r.holding_distribution.items(), key=lambda x: x[1], reverse=True):
            holding_dist_rows += f"""
            <tr>
                <td>{name}</td>
                <td>{pct:.1%}</td>
                <td><div class="bar" style="width: {pct*100}%"></div></td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A股ETF双动量轮动策略 - 回测报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
               background: #f5f5f5; color: #333; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ text-align: center; color: #2c3e50; margin-bottom: 30px; font-size: 28px; }}
        h2 {{ color: #34495e; margin: 25px 0 15px; padding-bottom: 10px;
              border-bottom: 2px solid #3498db; font-size: 20px; }}

        /* 卡片样式 */
        .card {{ background: white; border-radius: 10px; padding: 20px;
                 box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }}

        /* 指标网格 */
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                         gap: 15px; margin: 20px 0; }}
        .metric-card {{ background: #f8f9fa; border-radius: 8px; padding: 15px;
                        text-align: center; border-left: 4px solid #3498db; }}
        .metric-card.positive {{ border-left-color: #27ae60; }}
        .metric-card.negative {{ border-left-color: #e74c3c; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ font-size: 12px; color: #7f8c8d; margin-top: 5px; }}

        /* 表格 */
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ecf0f1; }}
        th {{ background: #34495e; color: white; font-weight: 600; }}
        tr:hover {{ background: #f5f6fa; }}

        /* 图表容器 */
        .chart-container {{ position: relative; height: 400px; margin: 20px 0; }}

        /* 进度条 */
        .bar {{ height: 20px; background: linear-gradient(90deg, #3498db, #2ecc71);
                border-radius: 10px; min-width: 5px; }}

        /* 图例 */
        .legend {{ display: flex; justify-content: center; gap: 20px; margin: 15px 0; }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; }}
        .legend-color {{ width: 15px; height: 15px; border-radius: 3px; }}

        /* 页脚 */
        .footer {{ text-align: center; color: #7f8c8d; margin-top: 30px;
                    padding-top: 20px; border-top: 1px solid #ecf0f1; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 A股ETF双动量轮动策略 - 回测报告</h1>

        <!-- 概览指标 -->
        <div class="card">
            <h2>📈 绩效概览</h2>
            <div class="metrics-grid">
                <div class="metric-card {"positive" if r.total_return > 0 else "negative"}">
                    <div class="metric-value">{r.total_return:.1%}</div>
                    <div class="metric-label">累计收益</div>
                </div>
                <div class="metric-card {"positive" if r.annual_return > 0 else "negative"}">
                    <div class="metric-value">{r.annual_return:.1%}</div>
                    <div class="metric-label">年化收益</div>
                </div>
                <div class="metric-card negative">
                    <div class="metric-value">{r.max_drawdown:.1%}</div>
                    <div class="metric-label">最大回撤</div>
                </div>
                <div class="metric-card {"positive" if r.sharpe_ratio > 1 else ""}">
                    <div class="metric-value">{r.sharpe_ratio:.2f}</div>
                    <div class="metric-label">夏普比率</div>
                </div>
                <div class="metric-card {"positive" if r.alpha > 0 else "negative"}">
                    <div class="metric-value">{r.alpha:.1%}</div>
                    <div class="metric-label">年化Alpha</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{r.win_rate:.1%}</div>
                    <div class="metric-label">月度胜率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{r.volatility:.1%}</div>
                    <div class="metric-label">年化波动率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{r.total_trades}</div>
                    <div class="metric-label">调仓次数</div>
                </div>
            </div>
        </div>

        <!-- 净值曲线 -->
        <div class="card">
            <h2>📉 净值曲线</h2>
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color" style="background: #3498db;"></div>
                    <span>策略净值</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #e74c3c;"></div>
                    <span>沪深300基准</span>
                </div>
            </div>
            <div class="chart-container">
                <canvas id="navChart"></canvas>
            </div>
        </div>

        <!-- 持仓分布 -->
        <div class="card">
            <h2>🥧 持仓分布</h2>
            <table>
                <thead>
                    <tr>
                        <th>ETF名称</th>
                        <th>持仓占比</th>
                        <th>分布</th>
                    </tr>
                </thead>
                <tbody>
                    {holding_dist_rows}
                </tbody>
            </table>
        </div>

        <!-- 调仓记录 -->
        <div class="card">
            <h2>📋 调仓记录（最近20次）</h2>
            <table>
                <thead>
                    <tr>
                        <th>日期</th>
                        <th>市场状态</th>
                        <th>基准收益</th>
                        <th>选中ETF</th>
                        <th>决策理由</th>
                    </tr>
                </thead>
                <tbody>
                    {rebalance_rows}
                </tbody>
            </table>
        </div>

        <!-- 回测信息 -->
        <div class="card">
            <h2>ℹ️ 回测信息</h2>
            <table>
                <tr><td><strong>回测区间</strong></td>
                    <td>{r.start_date.strftime("%Y-%m-%d")} 至 {r.end_date.strftime("%Y-%m-%d")}</td></tr>
                <tr><td><strong>初始资金</strong></td>
                    <td>¥{r.initial_capital:,.0f}</td></tr>
                <tr><td><strong>最终资金</strong></td>
                    <td>¥{r.final_capital:,.0f}</td></tr>
                <tr><td><strong>基准总收益</strong></td>
                    <td>{r.benchmark_total_return:.1%}</td></tr>
                <tr><td><strong>基准年化收益</strong></td>
                    <td>{r.benchmark_annual_return:.1%}</td></tr>
                <tr><td><strong>年化换手率</strong></td>
                    <td>{r.turnover_rate:.1f}倍</td></tr>
                <tr><td><strong>最大回撤持续</strong></td>
                    <td>{r.max_drawdown_duration}个交易日</td></tr>
            </table>
        </div>

        <div class="footer">
            <p>报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>⚠️ 回测结果不代表未来收益，策略仅供研究参考</p>
        </div>
    </div>

    <script>
        // 净值曲线图
        const ctx = document.getElementById('navChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {dates},
                datasets: [
                    {{
                        label: '策略净值',
                        data: {navs},
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        pointRadius: 0
                    }},
                    {{
                        label: '沪深300基准',
                        data: {benchmark_navs},
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        pointRadius: 0
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    mode: 'index',
                    intersect: false
                }},
                scales: {{
                    x: {{
                        display: true,
                        ticks: {{
                            maxTicksLimit: 10
                        }}
                    }},
                    y: {{
                        display: true,
                        title: {{
                            display: true,
                            text: '净值'
                        }}
                    }}
                }},
                plugins: {{
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                return context.dataset.label + ': ' + context.parsed.y.toFixed(4);
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
        return html

    def print_summary(self):
        """打印摘要信息"""
        r = self.result
        print("=" * 60)
        print("A股ETF双动量轮动策略 - 回测结果摘要")
        print("=" * 60)
        print(f"回测区间: {r.start_date.strftime('%Y-%m-%d')} 至 {r.end_date.strftime('%Y-%m-%d')}")
        print(f"初始资金: ¥{r.initial_capital:,.0f}")
        print(f"最终资金: ¥{r.final_capital:,.0f}")
        print("-" * 60)
        print(f"累计收益:   {r.total_return:>10.2%}  (基准: {r.benchmark_total_return:.2%})")
        print(f"年化收益:   {r.annual_return:>10.2%}  (基准: {r.benchmark_annual_return:.2%})")
        print(f"年化Alpha:  {r.alpha:>10.2%}")
        print(f"最大回撤:   {r.max_drawdown:>10.2%}")
        print(f"夏普比率:   {r.sharpe_ratio:>10.2f}")
        print(f"卡尔玛比率: {r.calmar_ratio:>10.2f}")
        print(f"月度胜率:   {r.win_rate:>10.2%}")
        print(f"年化波动率: {r.volatility:>10.2%}")
        print(f"调仓次数:   {r.total_trades:>10d}")
        print(f"年化换手:   {r.turnover_rate:>10.1f}倍")
        print("=" * 60)
