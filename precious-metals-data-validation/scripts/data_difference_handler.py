#!/usr/bin/env python3
"""
贵金属数据差异处理机制
处理不同数据源之间的差异，提供标准化数据输出
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class DifferenceType(Enum):
    """差异类型"""
    PRICE_DIFFERENCE = "price_difference"
    TIMEFRAME_MISMATCH = "timeframe_mismatch"
    DATA_MISSING = "data_missing"
    OUTLIER = "outlier"
    CONSISTENCY_ERROR = "consistency_error"

@dataclass
class DataDifference:
    """数据差异"""
    difference_type: DifferenceType
    description: str
    severity: str  # "low", "medium", "high"
    affected_sources: List[str]
    recommendation: str

class DataDifferenceHandler:
    """数据差异处理器"""
    
    def __init__(self, tolerance_percent: float = 0.5):
        """
        初始化差异处理器
        
        Args:
            tolerance_percent: 价格差异容忍度百分比
        """
        self.tolerance_percent = tolerance_percent
        self.difference_history = []
    
    def detect_differences(self, data_list: List[Dict]) -> List[DataDifference]:
        """检测数据差异"""
        differences = []
        
        if not data_list:
            differences.append(DataDifference(
                difference_type=DifferenceType.DATA_MISSING,
                description="无数据可比较",
                severity="high",
                affected_sources=[],
                recommendation="需要从至少一个数据源获取数据"
            ))
            return differences
        
        # 1. 检测价格差异
        price_differences = self._detect_price_differences(data_list)
        differences.extend(price_differences)
        
        # 2. 检测时间框架不匹配
        timeframe_differences = self._detect_timeframe_differences(data_list)
        differences.extend(timeframe_differences)
        
        # 3. 检测异常值
        outlier_differences = self._detect_outliers(data_list)
        differences.extend(outlier_differences)
        
        # 4. 检测数据一致性
        consistency_differences = self._detect_consistency_errors(data_list)
        differences.extend(consistency_differences)
        
        return differences
    
    def _detect_price_differences(self, data_list: List[Dict]) -> List[DataDifference]:
        """检测价格差异"""
        differences = []
        
        if len(data_list) < 2:
            return differences
        
        prices = []
        sources = []
        
        for data in data_list:
            if 'price' in data and data['price'] > 0:
                prices.append(data['price'])
                sources.append(data.get('source', 'unknown'))
        
        if len(prices) < 2:
            return differences
        
        # 计算价格统计
        avg_price = np.mean(prices)
        price_std = np.std(prices)
        price_cv = price_std / avg_price if avg_price > 0 else 0
        
        # 检查价格差异是否超过容忍度
        for i, price1 in enumerate(prices):
            for j, price2 in enumerate(prices[i+1:], i+1):
                price_diff_percent = abs(price1 - price2) / avg_price * 100
                
                if price_diff_percent > self.tolerance_percent:
                    severity = "low"
                    if price_diff_percent > 1.0:
                        severity = "medium"
                    if price_diff_percent > 2.0:
                        severity = "high"
                    
                    differences.append(DataDifference(
                        difference_type=DifferenceType.PRICE_DIFFERENCE,
                        description=f"价格差异: {sources[i]}={price1:.2f} vs {sources[j]}={price2:.2f} (差异{price_diff_percent:.2f}%)",
                        severity=severity,
                        affected_sources=[sources[i], sources[j]],
                        recommendation=f"检查数据源准确性，差异超过{self.tolerance_percent}%容忍度"
                    ))
        
        return differences
    
    def _detect_timeframe_differences(self, data_list: List[Dict]) -> List[DataDifference]:
        """检测时间框架不匹配"""
        differences = []
        
        timeframes = []
        sources = []
        
        for data in data_list:
            if 'timeframe' in data:
                # 处理时间框架，可能是枚举对象或字符串
                tf = data['timeframe']
                if hasattr(tf, 'value'):
                    tf_value = tf.value
                else:
                    tf_value = str(tf).lower()
                
                timeframes.append(tf_value)
                sources.append(data.get('source', 'unknown'))
        
        if not timeframes:
            return differences
        
        # 检查是否有非日线数据
        daily_count = sum(1 for tf in timeframes if tf == 'daily')
        non_daily_count = len(timeframes) - daily_count
        
        if non_daily_count > 0:
            non_daily_sources = [sources[i] for i, tf in enumerate(timeframes) if tf != 'daily']
            
            differences.append(DataDifference(
                difference_type=DifferenceType.TIMEFRAME_MISMATCH,
                description=f"检测到{non_daily_count}个非日线数据源: {', '.join(non_daily_sources)}",
                severity="high",
                affected_sources=non_daily_sources,
                recommendation="只使用日线数据，过滤非日线数据源"
            ))
        
        return differences
    
    def _detect_outliers(self, data_list: List[Dict]) -> List[DataDifference]:
        """检测异常值"""
        differences = []
        
        if len(data_list) < 3:
            return differences
        
        prices = []
        sources = []
        
        for data in data_list:
            if 'price' in data and data['price'] > 0:
                prices.append(data['price'])
                sources.append(data.get('source', 'unknown'))
        
        if len(prices) < 3:
            return differences
        
        # 使用IQR方法检测异常值
        q1 = np.percentile(prices, 25)
        q3 = np.percentile(prices, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        for i, price in enumerate(prices):
            if price < lower_bound or price > upper_bound:
                differences.append(DataDifference(
                    difference_type=DifferenceType.OUTLIER,
                    description=f"异常价格: {sources[i]}={price:.2f} (正常范围: {lower_bound:.2f} - {upper_bound:.2f})",
                    severity="medium",
                    affected_sources=[sources[i]],
                    recommendation="检查数据源是否提供正确数据，考虑排除该数据源"
                ))
        
        return differences
    
    def _detect_consistency_errors(self, data_list: List[Dict]) -> List[DataDifference]:
        """检测数据一致性错误"""
        differences = []
        
        # 检查数据完整性
        required_fields = ['price', 'change', 'change_percent', 'high', 'low', 'open', 'close']
        
        for data in data_list:
            source = data.get('source', 'unknown')
            missing_fields = [field for field in required_fields if field not in data or data[field] is None]
            
            if missing_fields:
                differences.append(DataDifference(
                    difference_type=DifferenceType.CONSISTENCY_ERROR,
                    description=f"数据不完整: {source}缺少字段 {', '.join(missing_fields)}",
                    severity="medium",
                    affected_sources=[source],
                    recommendation="检查数据源API响应，确保返回完整数据"
                ))
        
        # 检查价格逻辑一致性
        for data in data_list:
            source = data.get('source', 'unknown')
            
            if all(field in data for field in ['high', 'low', 'open', 'close']):
                if data['high'] < data['low']:
                    differences.append(DataDifference(
                        difference_type=DifferenceType.CONSISTENCY_ERROR,
                        description=f"价格逻辑错误: {source} 最高价({data['high']}) < 最低价({data['low']})",
                        severity="high",
                        affected_sources=[source],
                        recommendation="数据源存在逻辑错误，应排除该数据源"
                    ))
                
                if data['high'] < max(data['open'], data['close']):
                    differences.append(DataDifference(
                        difference_type=DifferenceType.CONSISTENCY_ERROR,
                        description=f"价格逻辑错误: {source} 最高价({data['high']}) < 开盘价/收盘价",
                        severity="high",
                        affected_sources=[source],
                        recommendation="数据源存在逻辑错误，应排除该数据源"
                    ))
        
        return differences
    
    def handle_differences(self, data_list: List[Dict], differences: List[DataDifference]) -> List[Dict]:
        """处理数据差异，返回处理后的数据"""
        if not data_list:
            return []
        
        # 记录差异
        self.difference_history.extend(differences)
        
        # 按严重程度处理差异
        high_severity_differences = [d for d in differences if d.severity == "high"]
        medium_severity_differences = [d for d in differences if d.severity == "medium"]
        
        # 处理高严重性差异
        if high_severity_differences:
            print(f"警告: 检测到{len(high_severity_differences)}个高严重性差异")
            for diff in high_severity_differences:
                print(f"  - {diff.description}")
                print(f"    建议: {diff.recommendation}")
        
        # 过滤数据源
        filtered_data = self._filter_data_sources(data_list, differences)
        
        # 如果过滤后数据不足，使用原始数据
        if len(filtered_data) < 2:
            print("警告: 过滤后数据不足，使用原始数据")
            filtered_data = data_list
        
        return filtered_data
    
    def _filter_data_sources(self, data_list: List[Dict], differences: List[DataDifference]) -> List[Dict]:
        """根据差异过滤数据源"""
        # 收集需要排除的数据源
        sources_to_exclude = set()
        
        for diff in differences:
            if diff.severity == "high":
                sources_to_exclude.update(diff.affected_sources)
        
        # 过滤数据
        filtered_data = []
        for data in data_list:
            source = data.get('source', 'unknown')
            if source not in sources_to_exclude:
                filtered_data.append(data)
        
        return filtered_data
    
    def calculate_weighted_average(self, data_list: List[Dict]) -> Dict:
        """计算加权平均值"""
        if not data_list:
            return {}
        
        # 根据数据源质量设置权重
        source_weights = {
            'barchart': 1.2,
            'tradingview': 1.1,
            'investing_com': 1.0,
            'yahoo_finance': 0.9
        }
        
        total_weight = 0
        weighted_price = 0
        weighted_change = 0
        weighted_change_percent = 0
        
        for data in data_list:
            source = data.get('source', 'unknown')
            weight = source_weights.get(source, 1.0)
            
            if 'price' in data and data['price'] > 0:
                weighted_price += data['price'] * weight
                total_weight += weight
            
            if 'change' in data:
                weighted_change += data['change'] * weight
            
            if 'change_percent' in data:
                weighted_change_percent += data['change_percent'] * weight
        
        if total_weight > 0:
            return {
                'weighted_price': weighted_price / total_weight,
                'weighted_change': weighted_change / total_weight,
                'weighted_change_percent': weighted_change_percent / total_weight,
                'data_sources': len(data_list),
                'timestamp': datetime.now()
            }
        
        return {}
    
    def generate_difference_report(self, symbol: str, differences: List[DataDifference]) -> Dict:
        """生成差异报告"""
        report = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'total_differences': len(differences),
            'differences_by_severity': {
                'high': len([d for d in differences if d.severity == 'high']),
                'medium': len([d for d in differences if d.severity == 'medium']),
                'low': len([d for d in differences if d.severity == 'low'])
            },
            'differences': []
        }
        
        for diff in differences:
            report['differences'].append({
                'type': diff.difference_type.value,
                'description': diff.description,
                'severity': diff.severity,
                'affected_sources': diff.affected_sources,
                'recommendation': diff.recommendation
            })
        
        return report

def main():
    """主函数"""
    # 测试数据差异处理
    handler = DataDifferenceHandler(tolerance_percent=0.5)
    
    # 模拟多源数据
    test_data = [
        {
            'symbol': 'XAUUSD',
            'price': 4191.35,
            'change': -25.23,
            'change_percent': -0.60,
            'high': 4237.25,
            'low': 4153.10,
            'open': 4216.58,
            'close': 4191.35,
            'volume': 128380,
            'source': 'investing_com',
            'timeframe': 'daily'
        },
        {
            'symbol': 'XAUUSD',
            'price': 4222.80,
            'change': -23.10,
            'change_percent': -0.54,
            'high': 4237.25,
            'low': 4153.10,
            'open': 4245.90,
            'close': 4222.80,
            'volume': 138064,
            'source': 'barchart',
            'timeframe': 'daily'
        },
        {
            'symbol': 'XAUUSD',
            'price': 4222.90,
            'change': -23.00,
            'change_percent': -0.54,
            'high': 4237.25,
            'low': 4153.10,
            'open': 4245.90,
            'close': 4222.90,
            'volume': 138064,
            'source': 'tradingview',
            'timeframe': 'daily'
        }
    ]
    
    print("数据差异处理测试")
    print("=" * 50)
    
    # 检测差异
    differences = handler.detect_differences(test_data)
    
    print(f"检测到 {len(differences)} 个差异:")
    for i, diff in enumerate(differences, 1):
        print(f"{i}. {diff.difference_type.value}: {diff.description}")
        print(f"   严重程度: {diff.severity}")
        print(f"   影响源: {', '.join(diff.affected_sources)}")
        print(f"   建议: {diff.recommendation}")
        print()
    
    # 处理差异
    processed_data = handler.handle_differences(test_data, differences)
    
    print(f"处理后数据源数量: {len(processed_data)}")
    
    # 计算加权平均
    weighted_avg = handler.calculate_weighted_average(processed_data)
    if weighted_avg:
        print(f"加权平均价格: {weighted_avg.get('weighted_price', 0):.2f}")
        print(f"加权平均涨跌: {weighted_avg.get('weighted_change', 0):.2f}")
        print(f"加权平均涨跌幅: {weighted_avg.get('weighted_change_percent', 0):.2f}%")
    
    # 生成报告
    report = handler.generate_difference_report('XAUUSD', differences)
    print(f"\n差异报告:")
    print(f"总差异数: {report['total_differences']}")
    print(f"高严重性: {report['differences_by_severity']['high']}")
    print(f"中严重性: {report['differences_by_severity']['medium']}")
    print(f"低严重性: {report['differences_by_severity']['low']}")

if __name__ == "__main__":
    main()