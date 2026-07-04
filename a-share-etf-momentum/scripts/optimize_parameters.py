"""
A股ETF双动量轮动策略 - 参数优化脚本
支持批量运行不同参数组合的回测对比
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config import Config
from scripts.data_collector import ETFDataCollector
from scripts.momentum import MomentumCalculator
from scripts.strategy import DualMomentumStrategy
from scripts.backtest import BacktestEngine, BacktestResult
from scripts.report import ReportGenerator


class ParameterOptimizer:
    """参数优化器"""
    
    def __init__(self):
        self.results = []
        self.data_cache = None
        
    def run_optimization(self, 
                        abs_momentum_window: int = 90,
                        relative_momentum_windows: List[int] = [20, 30, 40, 50, 60, 75, 90],
                        rebalance_frequencies: List[str] = ["weekly", "biweekly", "monthly"],
                        valuation_enabled: bool = False,
                        backtest_start: str = "2013-01-01",
                        backtest_end: str = "2026-06-26"):
        """
        运行参数优化
        
        Args:
            abs_momentum_window: 绝对动量窗口（固定）
            relative_momentum_windows: 相对动量窗口列表
            rebalance_frequencies: 调仓频率列表
            valuation_enabled: 是否启用估值刹车
            backtest_start: 回测开始日期
            backtest_end: 回测结束日期
        """
        print("=" * 80)
        print("A股ETF双动量轮动策略 - 参数优化")
        print("=" * 80)
        print(f"绝对动量窗口: {abs_momentum_window}天（固定）")
        print(f"相对动量窗口: {relative_momentum_windows}")
        print(f"调仓频率: {rebalance_frequencies}")
        print(f"估值刹车: {'启用' if valuation_enabled else '禁用'}")
        print(f"回测区间: {backtest_start} 至 {backtest_end}")
        print(f"总组合数: {len(relative_momentum_windows) * len(rebalance_frequencies)}")
        print("=" * 80)
        
        # 预加载数据（所有组合共享相同数据）
        print("\n[1/3] 预加载ETF数据...")
        self._preload_data(backtest_start, backtest_end)
        
        # 运行所有参数组合
        print("\n[2/3] 运行参数组合回测...")
        total_combinations = len(relative_momentum_windows) * len(rebalance_frequencies)
        current_combination = 0
        
        for rel_window in relative_momentum_windows:
            for rebalance_freq in rebalance_frequencies:
                current_combination += 1
                print(f"\n--- 组合 {current_combination}/{total_combinations} ---")
                print(f"相对动量窗口: {rel_window}天, 调仓频率: {rebalance_freq}")
                
                # 运行单次回测
                result = self._run_single_backtest(
                    abs_momentum_window=abs_momentum_window,
                    relative_momentum_window=rel_window,
                    rebalance_freq=rebalance_freq,
                    valuation_enabled=valuation_enabled,
                    backtest_start=backtest_start,
                    backtest_end=backtest_end
                )
                
                if result:
                    self.results.append({
                        'abs_momentum_window': abs_momentum_window,
                        'relative_momentum_window': rel_window,
                        'rebalance_freq': rebalance_freq,
                        'result': result
                    })
                    print(f"✓ 完成 - 年化收益: {result.annual_return:.2%}, 最大回撤: {result.max_drawdown:.2%}")
                else:
                    print("✗ 失败 - 数据不足或计算错误")
        
        # 生成对比报告
        print("\n[3/3] 生成对比报告...")
        if self.results:
            report_path = self._generate_comparison_report()
            print(f"\n✓ 优化完成! 共完成 {len(self.results)} 个组合")
            print(f"✓ 对比报告已生成: {report_path}")
            return report_path
        else:
            print("\n✗ 优化失败 - 没有有效的回测结果")
            return None
    
    def _preload_data(self, start_date: str, end_date: str):
        """预加载所有ETF数据（避免重复加载）"""
        config = Config()
        config.backtest_start = start_date
        config.backtest_end = end_date
        
        collector = ETFDataCollector(config)
        self.data_cache = collector.collect_all()
        print(f"  成功加载 {len(self.data_cache)} 只ETF数据")
    
    def _run_single_backtest(self,
                            abs_momentum_window: int,
                            relative_momentum_window: int,
                            rebalance_freq: str,
                            valuation_enabled: bool,
                            backtest_start: str,
                            backtest_end: str) -> Optional[BacktestResult]:
        """运行单次回测"""
        try:
            # 创建配置
            config = Config()
            config.momentum_window = abs_momentum_window
            config.relative_momentum_window = relative_momentum_window
            config.rebalance_freq = rebalance_freq
            config.valuation_enabled = valuation_enabled
            config.backtest_start = backtest_start
            config.backtest_end = backtest_end
            
            # 使用缓存数据
            if not self.data_cache:
                print("  错误: 数据未预加载")
                return None
            
            # 初始化策略
            strategy = DualMomentumStrategy(config)
            
            # 获取估值数据（若启用）
            if valuation_enabled:
                calculator = MomentumCalculator(config)
                pe_data = calculator.fetch_all_valuation_data()
                strategy._pe_data_cache = pe_data
            
            # 运行回测
            engine = BacktestEngine(config, strategy, self.data_cache)
            result = engine.run()
            
            return result
            
        except Exception as e:
            print(f"  错误: {str(e)}")
            return None
    
    def _generate_comparison_report(self) -> str:
        """生成对比报告"""
        # 准备数据
        report_data = []
        for item in self.results:
            result = item['result']
            report_data.append({
                'abs_momentum_window': item['abs_momentum_window'],
                'relative_momentum_window': item['relative_momentum_window'],
                'rebalance_freq': item['rebalance_freq'],
                'total_return': result.total_return,
                'annual_return': result.annual_return,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'calmar_ratio': result.calmar_ratio,
                'volatility': result.volatility,
                'win_rate': result.win_rate,
                'trade_count': result.total_trades,
                'alpha': result.alpha
            })
        
        df = pd.DataFrame(report_data)
        
        # 生成HTML报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = "reports"
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"parameter_optimization_{timestamp}.html")
        
        html_content = self._create_html_report(df)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return report_path
    
    def _create_html_report(self, df: pd.DataFrame) -> str:
        """创建HTML报告"""
        # 计算统计信息
        best_return = df.loc[df['annual_return'].idxmax()]
        best_sharpe = df.loc[df['sharpe_ratio'].idxmax()]
        best_calmar = df.loc[df['calmar_ratio'].idxmax()]
        lowest_drawdown = df.loc[df['max_drawdown'].idxmin()]
        
        # 按调仓频率分组统计
        freq_stats = df.groupby('rebalance_freq').agg({
            'annual_return': ['mean', 'std', 'min', 'max'],
            'max_drawdown': ['mean', 'min'],
            'sharpe_ratio': ['mean', 'max']
        }).round(4)
        
        # 按相对动量窗口分组统计
        window_stats = df.groupby('relative_momentum_window').agg({
            'annual_return': ['mean', 'std', 'min', 'max'],
            'max_drawdown': ['mean', 'min'],
            'sharpe_ratio': ['mean', 'max']
        }).round(4)
        
        # 准备JSON数据用于JavaScript
        import json
        df_json = df.to_json(orient='records')
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A股ETF双动量策略 - 参数优化对比报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/datatables.net@1.11.5/js/jquery.dataTables.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/datatables.net-dt@1.11.5/css/jquery.dataTables.min.css">
    <style>
        :root {{
            --bg-color: #0f1117;
            --card-bg: #1a1d28;
            --accent-color: #f59e0b;
            --text-color: #e4e6ed;
            --border-color: #2a2e3f;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            margin: 0;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: linear-gradient(135deg, var(--card-bg) 0%, #2d1f3d 100%);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            border-left: 4px solid var(--accent-color);
        }}
        
        .header h1 {{
            margin: 0 0 10px 0;
            color: var(--accent-color);
            font-size: 28px;
        }}
        
        .header p {{
            margin: 5px 0;
            opacity: 0.8;
        }}
        
        .section {{
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 25px;
            border: 1px solid var(--border-color);
        }}
        
        .section-title {{
            color: var(--accent-color);
            font-size: 20px;
            margin: 0 0 20px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--accent-color);
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric-card {{
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 20px;
            border: 1px solid var(--border-color);
        }}
        
        .metric-label {{
            font-size: 14px;
            opacity: 0.7;
            margin-bottom: 8px;
        }}
        
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: var(--accent-color);
        }}
        
        .metric-detail {{
            font-size: 12px;
            opacity: 0.6;
            margin-top: 5px;
        }}
        
        /* 可折叠章节 */
        .collapsible {{
            cursor: pointer;
            user-select: none;
        }}
        
        .collapsible::after {{
            content: ' ▼';
            font-size: 12px;
            transition: transform 0.3s;
        }}
        
        .collapsible.active::after {{
            transform: rotate(180deg);
        }}
        
        .collapsible-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}
        
        .collapsible-content.active {{
            max-height: 2000px;
        }}
        
        /* 筛选控件 */
        .filter-container {{
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            border: 1px solid var(--border-color);
        }}
        
        .filter-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
        }}
        
        .filter-group {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        
        .filter-label {{
            font-size: 12px;
            opacity: 0.7;
        }}
        
        .filter-select {{
            background-color: rgba(255, 255, 255, 0.1);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 8px 12px;
            color: var(--text-color);
            min-width: 150px;
        }}
        
        .filter-btn {{
            background-color: var(--accent-color);
            color: #000;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            cursor: pointer;
            font-weight: 600;
            margin-top: 15px;
        }}
        
        .filter-btn:hover {{
            opacity: 0.9;
        }}
        
        /* 表格样式 */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }}
        
        th {{
            background-color: rgba(255, 255, 255, 0.1);
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid var(--border-color);
            cursor: pointer;
            position: relative;
        }}
        
        th:hover {{
            background-color: rgba(255, 255, 255, 0.15);
        }}
        
        th.sort-asc::after {{
            content: ' ▲';
            font-size: 10px;
        }}
        
        th.sort-desc::after {{
            content: ' ▼';
            font-size: 10px;
        }}
        
        td {{
            padding: 10px 15px;
            border-bottom: 1px solid var(--border-color);
        }}
        
        tr:hover {{
            background-color: rgba(255, 255, 255, 0.05);
        }}
        
        .positive {{
            color: var(--success-color);
        }}
        
        .negative {{
            color: var(--danger-color);
        }}
        
        .highlight {{
            background-color: rgba(245, 158, 11, 0.1);
            font-weight: bold;
        }}
        
        .chart-container {{
            height: 400px;
            margin: 20px 0;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px dashed var(--border-color);
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        
        .stats-card {{
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 20px;
            border: 1px solid var(--border-color);
        }}
        
        .stats-title {{
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 15px;
            color: var(--accent-color);
        }}
        
        .tag {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}
        
        .tag-weekly {{
            background-color: rgba(16, 185, 129, 0.2);
            color: #10b981;
        }}
        
        .tag-biweekly {{
            background-color: rgba(59, 130, 246, 0.2);
            color: #3b82f6;
        }}
        
        .tag-monthly {{
            background-color: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            opacity: 0.6;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>A股ETF双动量策略 - 参数优化对比报告</h1>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>优化组合数: {len(df)} 个 | 绝对动量窗口: 90天（固定） | 相对动量窗口: {sorted(df['relative_momentum_window'].unique())} 天</p>
            <p>调仓频率: {sorted(df['rebalance_freq'].unique())} | 回测区间: 2013-01-01 至 2026-06-26</p>
        </div>
        
        <!-- 核心指标概览 -->
        <div class="section">
            <h2 class="section-title">📊 核心指标概览</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">最佳年化收益</div>
                    <div class="metric-value {('positive' if best_return['annual_return'] > 0 else 'negative')}">{best_return['annual_return']:.2%}</div>
                    <div class="metric-detail">相对动量窗口: {best_return['relative_momentum_window']}天 | 调仓频率: {best_return['rebalance_freq']}</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">最佳夏普比率</div>
                    <div class="metric-value">{best_sharpe['sharpe_ratio']:.3f}</div>
                    <div class="metric-detail">相对动量窗口: {best_sharpe['relative_momentum_window']}天 | 调仓频率: {best_sharpe['rebalance_freq']}</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">最佳卡尔玛比率</div>
                    <div class="metric-value">{best_calmar['calmar_ratio']:.3f}</div>
                    <div class="metric-detail">相对动量窗口: {best_calmar['relative_momentum_window']}天 | 调仓频率: {best_calmar['rebalance_freq']}</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">最低最大回撤</div>
                    <div class="metric-value negative">{lowest_drawdown['max_drawdown']:.2%}</div>
                    <div class="metric-detail">相对动量窗口: {lowest_drawdown['relative_momentum_window']}天 | 调仓频率: {lowest_drawdown['rebalance_freq']}</div>
                </div>
            </div>
        </div>
        
        <!-- 参数组合详细结果 -->
        <div class="section">
            <h2 class="section-title collapsible">📋 参数组合详细结果</h2>
            <div class="collapsible-content active">
                <div class="filter-container">
                    <div class="filter-row">
                        <div class="filter-group">
                            <label class="filter-label">相对动量窗口</label>
                            <select id="windowFilter" class="filter-select">
                                <option value="all">全部窗口</option>
                                {chr(10).join([f'<option value="{w}">{w}天</option>' for w in sorted(df['relative_momentum_window'].unique())])}
                            </select>
                        </div>
                        <div class="filter-group">
                            <label class="filter-label">调仓频率</label>
                            <select id="freqFilter" class="filter-select">
                                <option value="all">全部频率</option>
                                <option value="weekly">周频调仓</option>
                                <option value="biweekly">2周频调仓</option>
                                <option value="monthly">月频调仓</option>
                            </select>
                        </div>
                        <button id="applyFilter" class="filter-btn">应用筛选</button>
                        <button id="resetFilter" class="filter-btn" style="background-color: rgba(255, 255, 255, 0.1);">重置</button>
                    </div>
                </div>
                <table>
                <thead>
                    <tr>
                        <th>相对动量窗口</th>
                        <th>调仓频率</th>
                        <th>年化收益</th>
                        <th>最大回撤</th>
                        <th>夏普比率</th>
                        <th>卡尔玛比率</th>
                        <th>波动率</th>
                        <th>胜率</th>
                        <th>交易次数</th>
                        <th>超额收益</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # 按年化收益降序排列
        df_sorted = df.sort_values('annual_return', ascending=False)
        
        for _, row in df_sorted.iterrows():
            # 确定调仓频率标签样式
            freq_class = f"tag-{row['rebalance_freq']}"
            freq_label = {
                'weekly': '周频',
                'biweekly': '2周频', 
                'monthly': '月频'
            }.get(row['rebalance_freq'], row['rebalance_freq'])
            
            # 确定是否为最佳组合
            is_best = (row['annual_return'] == best_return['annual_return'] and 
                      row['rebalance_freq'] == best_return['rebalance_freq'])
            row_class = 'highlight' if is_best else ''
            
            html += f"""
                    <tr class="{row_class}">
                        <td>{row['relative_momentum_window']}天</td>
                        <td><span class="tag {freq_class}">{freq_label}</span></td>
                        <td class="{('positive' if row['annual_return'] > 0 else 'negative')}">{row['annual_return']:.2%}</td>
                        <td class="negative">{row['max_drawdown']:.2%}</td>
                        <td>{row['sharpe_ratio']:.3f}</td>
                        <td>{row['calmar_ratio']:.3f}</td>
                        <td>{row['volatility']:.2%}</td>
                        <td>{row['win_rate']:.1%}</td>
                        <td>{row['trade_count']}</td>
                        <td class="{('positive' if row['alpha'] > 0 else 'negative')}">{row['alpha']:.2%}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
            </div>
        </div>
        
        <!-- 调仓频率分析 -->
        <div class="section">
            <h2 class="section-title">📈 调仓频率分析</h2>
            <div class="stats-grid">
        """
        
        # 调仓频率统计
        for freq in df['rebalance_freq'].unique():
            freq_data = df[df['rebalance_freq'] == freq]
            freq_label = {
                'weekly': '周频调仓',
                'biweekly': '2周频调仓',
                'monthly': '月频调仓'
            }.get(freq, freq)
            
            html += f"""
                <div class="stats-card">
                    <div class="stats-title">{freq_label}</div>
                    <p>组合数量: {len(freq_data)}</p>
                    <p>平均年化收益: {freq_data['annual_return'].mean():.2%}</p>
                    <p>收益标准差: {freq_data['annual_return'].std():.2%}</p>
                    <p>最佳年化收益: {freq_data['annual_return'].max():.2%}</p>
                    <p>最差年化收益: {freq_data['annual_return'].min():.2%}</p>
                    <p>平均最大回撤: {freq_data['max_drawdown'].mean():.2%}</p>
                    <p>最低最大回撤: {freq_data['max_drawdown'].min():.2%}</p>
                    <p>平均夏普比率: {freq_data['sharpe_ratio'].mean():.3f}</p>
                    <p>最高夏普比率: {freq_data['sharpe_ratio'].max():.3f}</p>
                </div>
            """
        
        html += """
            </div>
        </div>
        
        <!-- 相对动量窗口分析 -->
        <div class="section">
            <h2 class="section-title">🔍 相对动量窗口分析</h2>
            <div class="stats-grid">
        """
        
        # 相对动量窗口统计
        for window in sorted(df['relative_momentum_window'].unique()):
            window_data = df[df['relative_momentum_window'] == window]
            
            html += f"""
                <div class="stats-card">
                    <div class="stats-title">{window}天窗口</div>
                    <p>组合数量: {len(window_data)}</p>
                    <p>平均年化收益: {window_data['annual_return'].mean():.2%}</p>
                    <p>收益标准差: {window_data['annual_return'].std():.2%}</p>
                    <p>最佳年化收益: {window_data['annual_return'].max():.2%}</p>
                    <p>最差年化收益: {window_data['annual_return'].min():.2%}</p>
                    <p>平均最大回撤: {window_data['max_drawdown'].mean():.2%}</p>
                    <p>最低最大回撤: {window_data['max_drawdown'].min():.2%}</p>
                    <p>平均夏普比率: {window_data['sharpe_ratio'].mean():.3f}</p>
                    <p>最高夏普比率: {window_data['sharpe_ratio'].max():.3f}</p>
                </div>
            """
        
        html += """
            </div>
        </div>
        
        <!-- 图表占位 -->
        <div class="section">
            <h2 class="section-title">📊 可视化分析</h2>
            <div class="chart-container">
                <canvas id="returnChart" width="800" height="400"></canvas>
            </div>
            <div class="chart-container" style="margin-top: 20px;">
                <canvas id="sharpeChart" width="800" height="400"></canvas>
            </div>
        </div>
        
        <!-- 结论与建议 -->
        <div class="section">
            <h2 class="section-title">💡 结论与建议</h2>
            <div class="stats-card">
                <div class="stats-title">参数优化总结</div>
                <p><strong>1. 最佳收益组合:</strong> 相对动量窗口{best_return['relative_momentum_window']}天 + {best_return['rebalance_freq']}调仓，年化收益{best_return['annual_return']:.2%}</p>
                <p><strong>2. 最佳风险调整收益:</strong> 相对动量窗口{best_sharpe['relative_momentum_window']}天 + {best_sharpe['rebalance_freq']}调仓，夏普比率{best_sharpe['sharpe_ratio']:.3f}</p>
                <p><strong>3. 最低风险组合:</strong> 相对动量窗口{lowest_drawdown['relative_momentum_window']}天 + {lowest_drawdown['rebalance_freq']}调仓，最大回撤{lowest_drawdown['max_drawdown']:.2%}</p>
                <p><strong>4. 调仓频率影响:</strong> 周频调仓通常收益更高但交易成本也更高，月频调仓更稳定</p>
                <p><strong>5. 动量窗口影响:</strong> 较短窗口（20-40天）对市场变化更敏感，较长窗口（60-90天）更稳定</p>
            </div>
        </div>
        
        <div class="footer">
            <p>A股ETF双动量轮动策略 - 参数优化报告 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>免责声明: 本报告基于历史数据回测，不代表未来收益。投资有风险，入市需谨慎。</p>
        </div>
    </div>
    
    <script>
        // 准备图表数据
        const windows = {sorted(df['relative_momentum_window'].unique().tolist())};
        const freqs = {sorted(df['rebalance_freq'].unique().tolist())};
        
        // 为每个调仓频率准备数据
        const datasets = {{}};
        freqs.forEach(freq => {{
            datasets[freq] = {{
                returns: [],
                sharpes: [],
                drawdowns: []
            }};
        }});
        
        // 填充数据
        {chr(10).join([f"        datasets['{row['rebalance_freq']}'].returns.push({row['annual_return']:.4f});" 
                      for _, row in df.iterrows()])}
        {chr(10).join([f"        datasets['{row['rebalance_freq']}'].sharpes.push({row['sharpe_ratio']:.4f});" 
                      for _, row in df.iterrows()])}
        {chr(10).join([f"        datasets['{row['rebalance_freq']}'].drawdowns.push({row['max_drawdown']:.4f});" 
                      for _, row in df.iterrows()])}
        
        // 年化收益图表
        const returnCtx = document.getElementById('returnChart').getContext('2d');
        new Chart(returnCtx, {{
            type: 'bar',
            data: {{
                labels: windows.map(w => w + '天'),
                datasets: freqs.map((freq, index) => ({{
                    label: freq === 'weekly' ? '周频调仓' : freq === 'biweekly' ? '2周频调仓' : '月频调仓',
                    data: datasets[freq].returns.map(r => (r * 100).toFixed(2)),
                    backgroundColor: [
                        'rgba(16, 185, 129, 0.7)',
                        'rgba(59, 130, 246, 0.7)',
                        'rgba(245, 158, 11, 0.7)'
                    ][index],
                    borderColor: [
                        'rgba(16, 185, 129, 1)',
                        'rgba(59, 130, 246, 1)',
                        'rgba(245, 158, 11, 1)'
                    ][index],
                    borderWidth: 1
                }}))
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: '不同参数组合的年化收益对比',
                        color: '#e4e6ed',
                        font: {{ size: 16 }}
                    }},
                    legend: {{
                        labels: {{
                            color: '#e4e6ed'
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#e4e6ed' }},
                        grid: {{ color: 'rgba(255, 255, 255, 0.1)' }}
                    }},
                    y: {{
                        ticks: {{ 
                            color: '#e4e6ed',
                            callback: function(value) {{
                                return value + '%';
                            }}
                        }},
                        grid: {{ color: 'rgba(255, 255, 255, 0.1)' }}
                    }}
                }}
            }}
        }});
        
        // 夏普比率图表
        const sharpeCtx = document.getElementById('sharpeChart').getContext('2d');
        new Chart(sharpeCtx, {{
            type: 'line',
            data: {{
                labels: windows.map(w => w + '天'),
                datasets: freqs.map((freq, index) => ({{
                    label: freq === 'weekly' ? '周频调仓' : freq === 'biweekly' ? '2周频调仓' : '月频调仓',
                    data: datasets[freq].sharpes.map(s => s.toFixed(3)),
                    borderColor: [
                        'rgba(16, 185, 129, 1)',
                        'rgba(59, 130, 246, 1)',
                        'rgba(245, 158, 11, 1)'
                    ][index],
                    backgroundColor: [
                        'rgba(16, 185, 129, 0.1)',
                        'rgba(59, 130, 246, 0.1)',
                        'rgba(245, 158, 11, 0.1)'
                    ][index],
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                }}))
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: '不同参数组合的夏普比率对比',
                        color: '#e4e6ed',
                        font: {{ size: 16 }}
                    }},
                    legend: {{
                        labels: {{
                            color: '#e4e6ed'
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#e4e6ed' }},
                        grid: {{ color: 'rgba(255, 255, 255, 0.1)' }}
                    }},
                    y: {{
                        ticks: {{ color: '#e4e6ed' }},
                        grid: {{ color: 'rgba(255, 255, 255, 0.1)' }}
                    }}
                }}
            }}
        }});
        
        // 交互功能
        $(document).ready(function() {{
            // 可折叠章节
            $('.collapsible').click(function() {{
                $(this).toggleClass('active');
                $(this).next('.collapsible-content').toggleClass('active');
            }});
            
            // 表格排序
            $('th').click(function() {{
                var table = $(this).parents('table');
                var rows = table.find('tbody > tr').toArray();
                var index = $(this).index();
                var ascending = !$(this).hasClass('sort-asc');
                
                // 移除所有排序指示器
                table.find('th').removeClass('sort-asc sort-desc');
                
                // 添加当前排序指示器
                $(this).addClass(ascending ? 'sort-asc' : 'sort-desc');
                
                // 排序函数
                rows.sort(function(a, b) {{
                    var aVal = $(a).children('td').eq(index).text();
                    var bVal = $(b).children('td').eq(index).text();
                    
                    // 尝试转换为数字
                    var aNum = parseFloat(aVal.replace(/[^0-9.-]/g, ''));
                    var bNum = parseFloat(bVal.replace(/[^0-9.-]/g, ''));
                    
                    if (!isNaN(aNum) && !isNaN(bNum)) {{
                        return ascending ? aNum - bNum : bNum - aNum;
                    }} else {{
                        return ascending ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                    }}
                }});
                
                // 重新插入排序后的行
                $.each(rows, function(index, row) {{
                    table.children('tbody').append(row);
                }});
            }});
            
            // 参数筛选
            $('#applyFilter').click(function() {{
                var windowFilter = $('#windowFilter').val();
                var freqFilter = $('#freqFilter').val();
                
                $('table tbody tr').each(function() {{
                    var row = $(this);
                    var windowVal = row.find('td:first').text().replace('天', '');
                    var freqVal = row.find('td:nth-child(2) span').text();
                    
                    var showRow = true;
                    
                    if (windowFilter !== 'all' && windowVal !== windowFilter) {{
                        showRow = false;
                    }}
                    
                    if (freqFilter !== 'all') {{
                        var freqMap = {{
                            'weekly': '周频调仓',
                            'biweekly': '2周频调仓',
                            'monthly': '月频调仓'
                        }};
                        if (freqVal !== freqMap[freqFilter]) {{
                            showRow = false;
                        }}
                    }}
                    
                    row.toggle(showRow);
                }});
            }});
            
            // 重置筛选
            $('#resetFilter').click(function() {{
                $('#windowFilter').val('all');
                $('#freqFilter').val('all');
                $('table tbody tr').show();
            }});
            
            // 图表交互 - 点击高亮
            $('#returnChart, #sharpeChart').click(function(evt) {{
                var activePoints = this.getElementsAtEventForMode(evt, 'nearest', {{ intersect: true }}, true);
                if (activePoints.length > 0) {{
                    var firstPoint = activePoints[0];
                    var label = this.data.labels[firstPoint.index];
                    var dataset = this.data.datasets[firstPoint.datasetIndex];
                    var value = dataset.data[firstPoint.index];
                    
                    alert(dataset.label + '\\n' + label + ': ' + value + (this.id === 'returnChart' ? '%' : ''));
                }}
            }});
        }});
    </script>
</body>
</html>
        """
        
        return html


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="A股ETF双动量策略参数优化")
    parser.add_argument("--abs-window", type=int, default=90, help="绝对动量窗口（默认90天）")
    parser.add_argument("--rel-windows", nargs="+", type=int, default=[20, 30, 40, 50, 60, 75, 90], 
                       help="相对动量窗口列表（默认: 20 30 40 50 60 75 90）")
    parser.add_argument("--freq", nargs="+", default=["weekly", "biweekly", "monthly"],
                       help="调仓频率列表（默认: weekly biweekly monthly）")
    parser.add_argument("--no-valuation", action="store_true", help="禁用估值刹车")
    parser.add_argument("--start", default="2013-01-01", help="回测开始日期")
    parser.add_argument("--end", default="2026-06-26", help="回测结束日期")
    
    args = parser.parse_args()
    
    # 创建优化器并运行
    optimizer = ParameterOptimizer()
    report_path = optimizer.run_optimization(
        abs_momentum_window=args.abs_window,
        relative_momentum_windows=args.rel_windows,
        rebalance_frequencies=args.freq,
        valuation_enabled=not args.no_valuation,
        backtest_start=args.start,
        backtest_end=args.end
    )
    
    if report_path:
        print(f"\n优化完成！报告已保存到: {report_path}")
    else:
        print("\n优化失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
