#!/usr/bin/env python3
"""
优化版贵金属数据验证脚本
特点：批量验证、性能优化、更全面的验证规则
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

class ValidationStatus(Enum):
    """验证状态"""
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"

@dataclass
class ValidationResult:
    """验证结果"""
    check_name: str
    status: ValidationStatus
    message: str
    details: Dict
    recommendation: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class OptimizedDataValidationScript:
    """优化版数据验证脚本"""
    
    def __init__(self, max_workers: int = 4):
        self.validation_results = []
        self.validation_history = []
        self.max_workers = max_workers
        
        # 验证规则配置
        self.validation_rules = {
            'price_range': {
                'XAUUSD': {'min': 1000, 'max': 10000},
                'XAGUSD': {'min': 10, 'max': 100},
                'XPTUSD': {'min': 500, 'max': 3000},
                'XPDUSD': {'min': 500, 'max': 5000}
            },
            'technical_indicators': {
                'rsi': {'min': 0, 'max': 100},
                'adx': {'min': 0, 'max': 100},
                'cci': {'min': -200, 'max': 200},
                'stoch_k': {'min': 0, 'max': 100},
                'stoch_d': {'min': 0, 'max': 100},
                'atr': {'min': 0, 'max': 1000}
            },
            'price_consistency': {
                'max_cv': 0.01,  # 最大变异系数1%
                'min_sources': 2
            },
            'data_freshness': {
                'max_age_hours': 24
            }
        }
        
        # 性能统计
        self.stats = {
            'total_validations': 0,
            'passed_validations': 0,
            'warning_validations': 0,
            'failed_validations': 0,
            'total_time': 0
        }
    
    def validate_price_range(self, data_list: List[Dict], symbol: str) -> List[ValidationResult]:
        """验证价格范围"""
        results = []
        
        if not data_list:
            results.append(ValidationResult(
                check_name="价格范围验证",
                status=ValidationStatus.FAIL,
                message="无价格数据可验证",
                details={'data_count': 0},
                recommendation="需要从数据源获取价格数据"
            ))
            return results
        
        # 获取价格数据
        prices = [d.get('price', 0) for d in data_list if 'price' in d]
        if not prices:
            results.append(ValidationResult(
                check_name="价格范围验证",
                status=ValidationStatus.FAIL,
                message="无有效价格数据",
                details={'data_count': len(data_list)},
                recommendation="检查数据源是否提供价格字段"
            ))
            return results
        
        avg_price = np.mean(prices)
        min_price = min(prices)
        max_price = max(prices)
        
        # 获取价格范围规则
        price_rules = self.validation_rules['price_range'].get(symbol, {})
        if not price_rules:
            # 使用默认规则
            price_rules = {'min': 0, 'max': 100000}
        
        # 检查价格范围
        if avg_price < price_rules['min'] or avg_price > price_rules['max']:
            results.append(ValidationResult(
                check_name="价格范围验证",
                status=ValidationStatus.FAIL,
                message=f"价格范围异常: {avg_price:.2f} (合理范围: {price_rules['min']}-{price_rules['max']})",
                details={
                    'avg_price': avg_price,
                    'min_price': min_price,
                    'max_price': max_price,
                    'expected_range': price_rules
                },
                recommendation="检查数据源是否提供正确数据"
            ))
        else:
            results.append(ValidationResult(
                check_name="价格范围验证",
                status=ValidationStatus.PASS,
                message=f"价格范围正常: {avg_price:.2f}",
                details={
                    'avg_price': avg_price,
                    'min_price': min_price,
                    'max_price': max_price
                },
                recommendation=""
            ))
        
        return results
    
    def validate_price_consistency(self, data_list: List[Dict]) -> List[ValidationResult]:
        """验证价格一致性"""
        results = []
        
        if len(data_list) < 2:
            results.append(ValidationResult(
                check_name="价格一致性验证",
                status=ValidationStatus.WARNING,
                message="数据源不足，无法验证一致性",
                details={'data_count': len(data_list)},
                recommendation="增加数据源数量"
            ))
            return results
        
        # 提取价格数据
        prices = [d.get('price', 0) for d in data_list if 'price' in d]
        if not prices:
            results.append(ValidationResult(
                check_name="价格一致性验证",
                status=ValidationStatus.FAIL,
                message="无有效价格数据",
                details={'data_count': len(data_list)},
                recommendation="检查数据源是否提供价格字段"
            ))
            return results
        
        avg_price = np.mean(prices)
        price_std = np.std(prices)
        price_cv = price_std / avg_price if avg_price > 0 else 0
        
        # 检查一致性
        max_cv = self.validation_rules['price_consistency']['max_cv']
        if price_cv > max_cv:
            results.append(ValidationResult(
                check_name="价格一致性验证",
                status=ValidationStatus.WARNING,
                message=f"价格一致性差: 变异系数={price_cv:.4f} (阈值: {max_cv})",
                details={
                    'price_cv': price_cv,
                    'price_std': price_std,
                    'avg_price': avg_price,
                    'prices': prices
                },
                recommendation="检查不同数据源的数据一致性"
            ))
        else:
            results.append(ValidationResult(
                check_name="价格一致性验证",
                status=ValidationStatus.PASS,
                message=f"价格一致性良好: 变异系数={price_cv:.4f}",
                details={
                    'price_cv': price_cv,
                    'price_std': price_std,
                    'avg_price': avg_price
                },
                recommendation=""
            ))
        
        return results
    
    def validate_technical_indicators(self, data_list: List[Dict]) -> List[ValidationResult]:
        """验证技术指标"""
        results = []
        
        # 检查技术指标是否存在
        indicator_fields = list(self.validation_rules['technical_indicators'].keys())
        
        for field in indicator_fields:
            values = [d.get(field) for d in data_list if field in d]
            valid_values = [v for v in values if v is not None and v != 0]
            
            if not valid_values:
                results.append(ValidationResult(
                    check_name=f"技术指标{field}验证",
                    status=ValidationStatus.WARNING,
                    message=f"缺少{field}指标数据",
                    details={
                        'field': field,
                        'available_sources': len(valid_values),
                        'total_sources': len(data_list)
                    },
                    recommendation=f"从数据源获取{field}指标数据"
                ))
            else:
                # 检查指标值范围
                avg_value = np.mean(valid_values)
                min_value = min(valid_values)
                max_value = max(valid_values)
                
                # 获取指标范围规则
                indicator_rules = self.validation_rules['technical_indicators'].get(field, {})
                if not indicator_rules:
                    indicator_rules = {'min': -1000, 'max': 1000}
                
                # 检查范围
                if avg_value < indicator_rules['min'] or avg_value > indicator_rules['max']:
                    results.append(ValidationResult(
                        check_name=f"技术指标{field}验证",
                        status=ValidationStatus.FAIL,
                        message=f"{field}值异常: {avg_value:.2f} (合理范围: {indicator_rules['min']}-{indicator_rules['max']})",
                        details={
                            'field': field,
                            'avg_value': avg_value,
                            'min_value': min_value,
                            'max_value': max_value,
                            'expected_range': indicator_rules
                        },
                        recommendation=f"检查{field}指标计算是否正确"
                    ))
                else:
                    results.append(ValidationResult(
                        check_name=f"技术指标{field}验证",
                        status=ValidationStatus.PASS,
                        message=f"{field}值正常: {avg_value:.2f}",
                        details={
                            'field': field,
                            'avg_value': avg_value,
                            'min_value': min_value,
                            'max_value': max_value
                        },
                        recommendation=""
                    ))
        
        return results
    
    def validate_data_completeness(self, data_list: List[Dict]) -> List[ValidationResult]:
        """验证数据完整性"""
        results = []
        
        required_fields = ['symbol', 'price', 'change', 'change_percent', 'high', 'low', 'open', 'close', 'source']
        
        for field in required_fields:
            missing_sources = []
            for data in data_list:
                if field not in data or data[field] is None:
                    missing_sources.append(data.get('source', 'unknown'))
            
            if missing_sources:
                results.append(ValidationResult(
                    check_name=f"数据字段{field}完整性",
                    status=ValidationStatus.WARNING,
                    message=f"数据源{', '.join(missing_sources)}缺少{field}字段",
                    details={
                        'field': field,
                        'missing_sources': missing_sources,
                        'total_sources': len(data_list)
                    },
                    recommendation=f"从数据源获取{field}字段数据"
                ))
            else:
                results.append(ValidationResult(
                    check_name=f"数据字段{field}完整性",
                    status=ValidationStatus.PASS,
                    message=f"所有数据源包含{field}字段",
                    details={
                        'field': field,
                        'total_sources': len(data_list)
                    },
                    recommendation=""
                ))
        
        return results
    
    def validate_time_consistency(self, data_list: List[Dict]) -> List[ValidationResult]:
        """验证时间一致性"""
        results = []
        
        # 检查时间戳
        timestamps = []
        sources = []
        
        for data in data_list:
            if 'timestamp' in data:
                timestamps.append(data['timestamp'])
                sources.append(data.get('source', 'unknown'))
        
        if not timestamps:
            results.append(ValidationResult(
                check_name="时间一致性验证",
                status=ValidationStatus.WARNING,
                message="无时间戳数据",
                details={'data_count': len(data_list)},
                recommendation="检查数据源是否提供时间戳"
            ))
            return results
        
        # 检查时间范围
        now = datetime.now()
        max_age = timedelta(hours=self.validation_rules['data_freshness']['max_age_hours'])
        
        old_timestamps = []
        for i, ts in enumerate(timestamps):
            if isinstance(ts, datetime):
                if now - ts > max_age:
                    old_timestamps.append((sources[i], ts))
        
        if old_timestamps:
            results.append(ValidationResult(
                check_name="时间一致性验证",
                status=ValidationStatus.WARNING,
                message=f"{len(old_timestamps)}个数据源时间戳过旧",
                details={
                    'old_timestamps': old_timestamps,
                    'max_age_hours': self.validation_rules['data_freshness']['max_age_hours']
                },
                recommendation="更新数据源获取最新数据"
            ))
        else:
            results.append(ValidationResult(
                check_name="时间一致性验证",
                status=ValidationStatus.PASS,
                message="所有数据源时间戳新鲜",
                details={
                    'timestamp_count': len(timestamps),
                    'max_age_hours': self.validation_rules['data_freshness']['max_age_hours']
                },
                recommendation=""
            ))
        
        return results
    
    def validate_market_logic(self, data_list: List[Dict]) -> List[ValidationResult]:
        """验证市场逻辑"""
        results = []
        
        for data in data_list:
            source = data.get('source', 'unknown')
            
            # 检查高低价逻辑
            high = data.get('high', 0)
            low = data.get('low', 0)
            open_price = data.get('open', 0)
            close_price = data.get('close', 0)
            
            if high and low and high < low:
                results.append(ValidationResult(
                    check_name=f"市场逻辑验证({source})",
                    status=ValidationStatus.FAIL,
                    message=f"最高价低于最低价: {high} < {low}",
                    details={
                        'source': source,
                        'high': high,
                        'low': low
                    },
                    recommendation="检查数据源数据质量"
                ))
            
            # 检查开盘价范围
            if open_price and high and low:
                if open_price < low or open_price > high:
                    results.append(ValidationResult(
                        check_name=f"市场逻辑验证({source})",
                        status=ValidationStatus.WARNING,
                        message=f"开盘价不在高低价范围内: {open_price} (范围: {low}-{high})",
                        details={
                            'source': source,
                            'open': open_price,
                            'high': high,
                            'low': low
                        },
                        recommendation="检查数据源数据质量"
                    ))
            
            # 检查收盘价范围
            if close_price and high and low:
                if close_price < low or close_price > high:
                    results.append(ValidationResult(
                        check_name=f"市场逻辑验证({source})",
                        status=ValidationStatus.WARNING,
                        message=f"收盘价不在高低价范围内: {close_price} (范围: {low}-{high})",
                        details={
                            'source': source,
                            'close': close_price,
                            'high': high,
                            'low': low
                        },
                        recommendation="检查数据源数据质量"
                    ))
        
        return results
    
    def run_full_validation(self, symbol: str, data_list: List[Dict]) -> Dict:
        """运行完整验证"""
        start_time = time.time()
        
        all_results = []
        
        # 1. 价格范围验证
        price_range_results = self.validate_price_range(data_list, symbol)
        all_results.extend(price_range_results)
        
        # 2. 价格一致性验证
        price_consistency_results = self.validate_price_consistency(data_list)
        all_results.extend(price_consistency_results)
        
        # 3. 技术指标验证
        technical_results = self.validate_technical_indicators(data_list)
        all_results.extend(technical_results)
        
        # 4. 数据完整性验证
        completeness_results = self.validate_data_completeness(data_list)
        all_results.extend(completeness_results)
        
        # 5. 时间一致性验证
        time_results = self.validate_time_consistency(data_list)
        all_results.extend(time_results)
        
        # 6. 市场逻辑验证
        logic_results = self.validate_market_logic(data_list)
        all_results.extend(logic_results)
        
        # 计算验证分数
        total_checks = len(all_results)
        passed_checks = sum(1 for r in all_results if r.status == ValidationStatus.PASS)
        warning_checks = sum(1 for r in all_results if r.status == ValidationStatus.WARNING)
        failed_checks = sum(1 for r in all_results if r.status == ValidationStatus.FAIL)
        
        validation_score = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        # 更新统计信息
        self.stats['total_validations'] += 1
        self.stats['passed_validations'] += passed_checks
        self.stats['warning_validations'] += warning_checks
        self.stats['failed_validations'] += failed_checks
        self.stats['total_time'] += time.time() - start_time
        
        # 生成验证报告
        validation_report = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'validation_score': validation_score,
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'warning_checks': warning_checks,
            'failed_checks': failed_checks,
            'results': all_results,
            'summary': {
                'status': 'PASS' if validation_score >= 80 else 'WARNING' if validation_score >= 60 else 'FAIL',
                'message': f"验证得分: {validation_score:.1f}%"
            }
        }
        
        return validation_report
    
    def run_batch_validation(self, symbols_data: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """批量验证多个品种"""
        results = {}
        
        for symbol, data_list in symbols_data.items():
            print(f"验证 {symbol}...")
            results[symbol] = self.run_full_validation(symbol, data_list)
        
        return results
    
    def run_parallel_validation(self, symbols_data: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """并行验证多个品种"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有验证任务
            future_to_symbol = {}
            for symbol, data_list in symbols_data.items():
                future = executor.submit(self.run_full_validation, symbol, data_list)
                future_to_symbol[future] = symbol
            
            # 收集结果
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    results[symbol] = future.result()
                except Exception as e:
                    print(f"验证 {symbol} 失败: {e}")
                    results[symbol] = {
                        'symbol': symbol,
                        'timestamp': datetime.now(),
                        'validation_score': 0,
                        'error': str(e)
                    }
        
        return results
    
    def generate_validation_report(self, validation_results: Dict[str, Dict]) -> str:
        """生成验证报告"""
        report_lines = []
        report_lines.append("贵金属数据验证报告")
        report_lines.append("=" * 50)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # 总体统计
        total_symbols = len(validation_results)
        passed_symbols = sum(1 for r in validation_results.values() if r.get('validation_score', 0) >= 80)
        warning_symbols = sum(1 for r in validation_results.values() if 60 <= r.get('validation_score', 0) < 80)
        failed_symbols = sum(1 for r in validation_results.values() if r.get('validation_score', 0) < 60)
        
        report_lines.append("总体统计:")
        report_lines.append(f"  品种总数: {total_symbols}")
        report_lines.append(f"  通过品种: {passed_symbols}")
        report_lines.append(f"  警告品种: {warning_symbols}")
        report_lines.append(f"  失败品种: {failed_symbols}")
        report_lines.append("")
        
        # 各品种详情
        for symbol, result in validation_results.items():
            report_lines.append(f"品种: {symbol}")
            report_lines.append("-" * 30)
            
            if 'error' in result:
                report_lines.append(f"  错误: {result['error']}")
            else:
                report_lines.append(f"  验证得分: {result.get('validation_score', 0):.1f}%")
                report_lines.append(f"  检查总数: {result.get('total_checks', 0)}")
                report_lines.append(f"  通过检查: {result.get('passed_checks', 0)}")
                report_lines.append(f"  警告检查: {result.get('warning_checks', 0)}")
                report_lines.append(f"  失败检查: {result.get('failed_checks', 0)}")
                
                # 显示失败和警告的检查
                if 'results' in result:
                    failed_results = [r for r in result['results'] if r.status == ValidationStatus.FAIL]
                    warning_results = [r for r in result['results'] if r.status == ValidationStatus.WARNING]
                    
                    if failed_results:
                        report_lines.append("  失败检查:")
                        for r in failed_results:
                            report_lines.append(f"    - {r.check_name}: {r.message}")
                    
                    if warning_results:
                        report_lines.append("  警告检查:")
                        for r in warning_results:
                            report_lines.append(f"    - {r.check_name}: {r.message}")
            
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def get_performance_stats(self) -> Dict:
        """获取性能统计"""
        return {
            'total_validations': self.stats['total_validations'],
            'passed_validations': self.stats['passed_validations'],
            'warning_validations': self.stats['warning_validations'],
            'failed_validations': self.stats['failed_validations'],
            'pass_rate': self.stats['passed_validations'] / max(self.stats['total_validations'], 1),
            'total_time': self.stats['total_time'],
            'avg_time_per_validation': self.stats['total_time'] / max(self.stats['total_validations'], 1)
        }

# 测试函数
def test_optimized_validation():
    """测试优化版数据验证脚本"""
    print("测试优化版数据验证脚本")
    print("=" * 50)
    
    validator = OptimizedDataValidationScript()
    
    # 测试数据
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
            'source': 'investing_com',
            'timestamp': datetime.now(),
            'rsi': 56.55,
            'macd': 4.17,
            'adx': 24.80,
            'cci': 95.91
        },
        {
            'symbol': 'XAUUSD',
            'price': 4200.50,
            'change': -16.08,
            'change_percent': -0.38,
            'high': 4240.00,
            'low': 4160.00,
            'open': 4216.58,
            'close': 4200.50,
            'source': 'barchart',
            'timestamp': datetime.now(),
            'rsi': 58.20,
            'macd': 5.30,
            'adx': 25.50,
            'cci': 102.50
        }
    ]
    
    # 测试完整验证
    print("\n1. 测试完整验证:")
    report = validator.run_full_validation('XAUUSD', test_data)
    
    print(f"  验证得分: {report['validation_score']:.1f}%")
    print(f"  检查总数: {report['total_checks']}")
    print(f"  通过检查: {report['passed_checks']}")
    print(f"  警告检查: {report['warning_checks']}")
    print(f"  失败检查: {report['failed_checks']}")
    
    # 测试批量验证
    print("\n2. 测试批量验证:")
    symbols_data = {
        'XAUUSD': test_data,
        'XAGUSD': [
            {
                'symbol': 'XAGUSD',
                'price': 32.50,
                'change': -0.30,
                'change_percent': -0.91,
                'high': 33.00,
                'low': 32.00,
                'open': 32.80,
                'close': 32.50,
                'source': 'investing_com',
                'timestamp': datetime.now(),
                'rsi': 45.20,
                'macd': -0.15,
                'adx': 18.50,
                'cci': -25.30
            }
        ]
    }
    
    batch_results = validator.run_batch_validation(symbols_data)
    
    for symbol, result in batch_results.items():
        print(f"  {symbol}: {result['validation_score']:.1f}%")
    
    # 测试并行验证
    print("\n3. 测试并行验证:")
    parallel_results = validator.run_parallel_validation(symbols_data)
    
    for symbol, result in parallel_results.items():
        print(f"  {symbol}: {result['validation_score']:.1f}%")
    
    # 生成报告
    print("\n4. 生成验证报告:")
    report_text = validator.generate_validation_report(batch_results)
    print(report_text)
    
    # 性能统计
    print("\n5. 性能统计:")
    stats = validator.get_performance_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    
    return validator

if __name__ == "__main__":
    test_optimized_validation()