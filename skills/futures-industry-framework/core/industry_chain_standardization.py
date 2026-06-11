"""
产业链定性分析标准化模块
通过量化指标体系替代主观判断
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class InventoryCycle(Enum):
    """库存周期四阶段 - 量化定义"""
    ACTIVE_DESTOCKING = "主动去库"
    PASSIVE_DESTOCKING = "被动去库"
    ACTIVE_RESTOCKING = "主动补库"
    PASSIVE_RESTOCKING = "被动补库"


class ProfitStructure(Enum):
    """利润结构 - 量化定义"""
    UPSTREAM_PROFIT = "上游盈利"
    MIDSTREAM_PROFIT = "中游盈利"
    DOWNSTREAM_PROFIT = "下游盈利"
    FULL_CHAIN_LOSS = "全链亏损"
    BALANCED = "利润均衡"


@dataclass
class IndustryChainMetrics:
    """产业链标准化指标体系"""
    # 库存相关指标
    inventory_change_rate: float  # 库存变化率（环比）
    inventory_history_percentile: float  # 库存历史分位
    inventory_destocking_speed: float  # 去库速度
    price_change_rate: float  # 价格变化率
    
    # 利润相关指标
    upstream_profit_margin: float  # 上游利润率
    midstream_profit_margin: float  # 中游利润率
    downstream_profit_margin: float  # 下游利润率
    profit_conduction_index: float  # 利润传导指数
    
    # 产业行为指标
    operating_rate: float  # 开工率
    operating_rate_change: float  # 开工率变化
    enterprise_hedging_intensity: float  # 企业套保强度
    
    # 供需指标
    supply_change: float  # 供给变化
    demand_change: float  # 需求变化
    supply_demand_gap: float  # 供需缺口
    basis: float  # 基差
    basis_history_percentile: float  # 基差历史分位


class IndustryChainStandardAnalyzer:
    """产业链定性分析标准化器"""
    
    def __init__(self):
        # 阈值配置 - 基于历史数据统计确定
        self.thresholds = {
            'inventory': {
                'fast_destocking': -0.05,  # 快速去库：月环比降5%以上
                'slow_destocking': -0.02,  # 缓慢去库
                'stable': 0.02,  # 库存稳定
                'slow_restocking': 0.05,  # 缓慢补库
                'fast_restocking': 0.08,  # 快速补库
            },
            'price': {
                'strong_rise': 0.03,  # 强势上涨：月涨3%以上
                'moderate_rise': 0.01,  # 温和上涨
                'stable': 0.01,  # 价格稳定
                'moderate_fall': -0.01,  # 温和下跌
                'strong_fall': -0.03,  # 强势下跌
            },
            'profit': {
                'high': 0.15,  # 高利润率：15%以上
                'medium': 0.08,  # 中等利润率
                'low': 0.03,  # 低利润率
                'loss': 0,  # 亏损
            },
            'operating_rate': {
                'high': 0.85,  # 高开工：85%以上
                'medium': 0.70,  # 中等开工
                'low': 0.55,  # 低开工
            }
        }
    
    def determine_inventory_cycle(self, metrics: IndustryChainMetrics) -> Tuple[InventoryCycle, float]:
        """
        量化判定库存周期
        
        判定规则：
        - 主动去库：库存下降 + 价格下跌 + 开工下降
        - 被动去库：库存下降 + 价格上涨 + 开工稳定或上升
        - 主动补库：库存上升 + 价格上涨 + 开工上升
        - 被动补库：库存上升 + 价格下跌 + 开工下降
        """
        inv_change = metrics.inventory_change_rate
        price_change = metrics.price_change_rate
        op_rate_change = metrics.operating_rate_change
        
        # 计算各阶段的匹配度（0-1）
        scores = {}
        
        # 主动去库评分
        ad_score = 0
        if inv_change < self.thresholds['inventory']['slow_destocking']:
            ad_score += 0.4
        if price_change < self.thresholds['price']['moderate_fall']:
            ad_score += 0.3
        if op_rate_change < 0:
            ad_score += 0.3
        scores[InventoryCycle.ACTIVE_DESTOCKING] = ad_score
        
        # 被动去库评分
        pd_score = 0
        if inv_change < self.thresholds['inventory']['slow_destocking']:
            pd_score += 0.4
        if price_change > self.thresholds['price']['moderate_rise']:
            pd_score += 0.3
        if op_rate_change >= 0:
            pd_score += 0.3
        scores[InventoryCycle.PASSIVE_DESTOCKING] = pd_score
        
        # 主动补库评分
        ar_score = 0
        if inv_change > self.thresholds['inventory']['slow_restocking']:
            ar_score += 0.4
        if price_change > self.thresholds['price']['moderate_rise']:
            ar_score += 0.3
        if op_rate_change > 0:
            ar_score += 0.3
        scores[InventoryCycle.ACTIVE_RESTOCKING] = ar_score
        
        # 被动补库评分
        pr_score = 0
        if inv_change > self.thresholds['inventory']['slow_restocking']:
            pr_score += 0.4
        if price_change < self.thresholds['price']['moderate_fall']:
            pr_score += 0.3
        if op_rate_change < 0:
            pr_score += 0.3
        scores[InventoryCycle.PASSIVE_RESTOCKING] = pr_score
        
        # 选出最高分的阶段
        best_cycle = max(scores.keys(), key=lambda k: scores[k])
        confidence = scores[best_cycle]
        
        return best_cycle, confidence
    
    def determine_profit_structure(self, metrics: IndustryChainMetrics) -> Tuple[ProfitStructure, Dict[str, float]]:
        """
        量化判定利润结构
        
        基于上中下游利润率的相对比较
        """
        profits = {
            'upstream': metrics.upstream_profit_margin,
            'midstream': metrics.midstream_profit_margin,
            'downstream': metrics.downstream_profit_margin
        }
        
        # 检查是否全链亏损
        if all(p < self.thresholds['profit']['loss'] for p in profits.values()):
            return ProfitStructure.FULL_CHAIN_LOSS, profits
        
        # 计算各环节利润占比
        total_profit = sum(max(0, p) for p in profits.values())
        if total_profit == 0:
            return ProfitStructure.BALANCED, profits
        
        profit_shares = {
            k: max(0, v) / total_profit 
            for k, v in profits.items()
        }
        
        # 判断利润集中环节
        max_share = max(profit_shares.values())
        if max_share > 0.5:  # 某一环节占比超过50%
            if profit_shares['upstream'] == max_share:
                return ProfitStructure.UPSTREAM_PROFIT, profit_shares
            elif profit_shares['midstream'] == max_share:
                return ProfitStructure.MIDSTREAM_PROFIT, profit_shares
            else:
                return ProfitStructure.DOWNSTREAM_PROFIT, profit_shares
        else:
            return ProfitStructure.BALANCED, profit_shares
    
    def calculate_industry_chain_score(self, metrics: IndustryChainMetrics) -> Tuple[float, Dict[str, float]]:
        """
        量化计算产业链综合评分（0-100分）
        
        各维度评分标准化，避免主观判断
        """
        dimension_scores = {}
        
        # 1. 库存维度评分 (20分)
        # 库存分位越低，去库越快，评分越高（看多）
        inv_score = (1 - metrics.inventory_history_percentile) * 15  # 0-15分
        if metrics.inventory_change_rate < 0:
            inv_score += abs(metrics.inventory_change_rate) * 100 * 0.5  # 去库加速加分
        else:
            inv_score -= metrics.inventory_change_rate * 100 * 0.5  # 累库减分
        dimension_scores['inventory'] = max(0, min(20, inv_score))
        
        # 2. 利润维度评分 (20分)
        # 利润传导越顺畅，评分越高
        profit_spread = max(profits := [
            metrics.upstream_profit_margin,
            metrics.midstream_profit_margin,
            metrics.downstream_profit_margin
        ]) - min(profits)
        profit_score = 20 * (1 - min(1, profit_spread / 0.2))  # 利润差越小越好
        dimension_scores['profit'] = max(0, min(20, profit_score))
        
        # 3. 供需维度评分 (25分)
        # 供需缺口越大（供不应求），评分越高
        s_d_score = 12.5 + metrics.supply_demand_gap * 50  # 供需缺口标准化到0-25
        dimension_scores['supply_demand'] = max(0, min(25, s_d_score))
        
        # 4. 基差维度评分 (20分)
        # 贴水越深（现货强），评分越高
        basis_score = (1 - metrics.basis_history_percentile) * 20
        dimension_scores['basis'] = max(0, min(20, basis_score))
        
        # 5. 产业行为维度评分 (15分)
        # 开工率合理，套保强度适中
        op_score = 15 * (1 - abs(metrics.operating_rate - 0.7) / 0.3)  # 70%开工最优
        dimension_scores['behavior'] = max(0, min(15, op_score))
        
        total_score = sum(dimension_scores.values())
        return total_score, dimension_scores
    
    def generate_standard_analysis_report(self, 
                                         metrics: IndustryChainMetrics,
                                         chain_name: str = "某产业链") -> Dict:
        """生成标准化产业链分析报告"""
        
        inventory_cycle, inv_confidence = self.determine_inventory_cycle(metrics)
        profit_structure, profit_shares = self.determine_profit_structure(metrics)
        total_score, dimension_scores = self.calculate_industry_chain_score(metrics)
        
        # 趋势判断（基于评分）
        if total_score >= 70:
            trend = "看多"
            trend_strength = "强"
        elif total_score >= 50:
            trend = "偏多"
            trend_strength = "中等"
        elif total_score >= 30:
            trend = "震荡"
            trend_strength = "弱"
        elif total_score >= 15:
            trend = "偏空"
            trend_strength = "中等"
        else:
            trend = "看空"
            trend_strength = "强"
        
        return {
            'chain_name': chain_name,
            'inventory_cycle': {
                'stage': inventory_cycle.value,
                'confidence': round(inv_confidence, 2),
                'metrics': {
                    'inventory_change': round(metrics.inventory_change_rate * 100, 2),
                    'price_change': round(metrics.price_change_rate * 100, 2),
                    'operating_rate_change': round(metrics.operating_rate_change * 100, 2)
                }
            },
            'profit_structure': {
                'structure': profit_structure.value,
                'shares': {k: round(v, 2) for k, v in profit_shares.items()}
            },
            'score': {
                'total': round(total_score, 1),
                'dimensions': {k: round(v, 1) for k, v in dimension_scores.items()}
            },
            'trend': {
                'direction': trend,
                'strength': trend_strength
            },
            'analysis_timestamp': pd.Timestamp.now().isoformat()
        }


def create_sample_metrics() -> IndustryChainMetrics:
    """创建示例指标数据用于测试"""
    return IndustryChainMetrics(
        inventory_change_rate=-0.03,  # 库存环比降3%
        inventory_history_percentile=0.35,  # 库存处于历史35%分位
        inventory_destocking_speed=0.8,
        price_change_rate=0.02,  # 价格月涨2%
        
        upstream_profit_margin=0.12,  # 上游利润率12%
        midstream_profit_margin=0.08,  # 中游8%
        downstream_profit_margin=0.05,  # 下游5%
        profit_conduction_index=0.7,
        
        operating_rate=0.78,  # 开工率78%
        operating_rate_change=0.02,  # 开工率上升2%
        enterprise_hedging_intensity=0.6,
        
        supply_change=-0.01,  # 供给降1%
        demand_change=0.03,  # 需求增3%
        supply_demand_gap=0.02,  # 供不应求2%
        basis=-25,  # 贴水25元
        basis_history_percentile=0.25  # 基差处于历史25%分位（贴水偏深）
    )
