#!/usr/bin/env python3
"""
贵金属数据验证脚本
验证数据的准确性、一致性和完整性
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json

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

class DataValidationScript:
    """数据验证脚本"""
    
    def __init__(self):
        self.validation_results = []
        self.validation_history = []
    
    def validate_price_data(self, data_list: List[Dict]) -> List[ValidationResult]:
        """验证价格数据"""
        results = []
        
        if not data_list:
            results.append(ValidationResult(
                check_name="价格数据完整性",
                status=ValidationStatus.FAIL,
                message="无价格数据可验证",
                details={'data_count': 0},
                recommendation="需要从数据源获取价格数据"
            ))
            return results
        
        # 1. 检查价格范围
        prices = [d.get('price', 0) for d in data_list if 'price' in d]
        if prices:
            min_price = min(prices)
            max_price = max(prices)
            avg_price = np.mean(prices)
            
            # 黄金价格合理范围（2026年）
            if avg_price > 0:
                if avg_price < 1000 or avg_price > 10000:
                    results.append(ValidationResult(
                        check_name="价格范围验证",
                        status=ValidationStatus.FAIL,
                        message=f"价格范围异常: {avg_price:.2f} (合理范围: 1000-10000)",
                        details={'avg_price': avg_price, 'min_price': min_price, 'max_price': max_price},
                        recommendation="检查数据源是否提供正确数据"
                    ))
                else:
                    results.append(ValidationResult(
                        check_name="价格范围验证",
                        status=ValidationStatus.PASS,
                        message=f"价格范围正常: {avg_price:.2f}",
                        details={'avg_price': avg_price, 'min_price': min_price, 'max_price': max_price},
                        recommendation=""
                    ))
        
        # 2. 检查价格一致性
        if len(prices) > 1:
            price_std = np.std(prices)
            price_cv = price_std / avg_price if avg_price > 0 else 0
            
            if price_cv > 0.01:  # 变异系数大于1%
                results.append(ValidationResult(
                    check_name="价格一致性验证",
                    status=ValidationStatus.WARNING,
                    message=f"价格一致性差: 变异系数={price_cv:.4f}",
                    details={'price_cv': price_cv, 'price_std': price_std},
                    recommendation="检查不同数据源的数据一致性"
                ))
            else:
                results.append(ValidationResult(
                    check_name="价格一致性验证",
                    status=ValidationStatus.PASS,
                    message=f"价格一致性良好: 变异系数={price_cv:.4f}",
                    details={'price_cv': price_cv, 'price_std': price_std},
                    recommendation=""
                ))
        
        return results
    
    def validate_technical_indicators(self, data_list: List[Dict]) -> List[ValidationResult]:
        """验证技术指标"""
        results = []
        
        # 检查技术指标是否存在
        indicator_fields = ['rsi', 'macd', 'adx', 'cci', 'stoch_k', 'stoch_d', 'atr']
        
        for field in indicator_fields:
            values = [d.get(field) for d in data_list if field in d]
            valid_values = [v for v in values if v is not None]
            
            if not valid_values:
                results.append(ValidationResult(
                    check_name=f"技术指标{field}验证",
                    status=ValidationStatus.WARNING,
                    message=f"缺少{field}指标数据",
                    details={'field': field, 'available_sources': len(valid_values)},
                    recommendation=f"从数据源获取{field}指标数据"
                ))
            else:
                # 检查指标值范围
                avg_value = np.mean(valid_values)
                
                if field == 'rsi':
                    if avg_value < 0 or avg_value > 100:
                        results.append(ValidationResult(
                            check_name=f"技术指标{field}验证",
                            status=ValidationStatus.FAIL,
                            message=f"{field}值异常: {avg_value:.2f} (合理范围: 0-100)",
                            details={'field': field, 'avg_value': avg_value},
                            recommendation=f"检查{field}指标计算是否正确"
                        ))
                    else:
                        results.append(ValidationResult(
                            check_name=f"技术指标{field}验证",
                            status=ValidationStatus.PASS,
                            message=f"{field}值正常: {avg_value:.2f}",
                            details={'field': field, 'avg_value': avg_value},
                            recommendation=""
                        ))
                
                elif field in ['adx', 'cci']:
                    if avg_value < -200 or avg_value > 200:
                        results.append(ValidationResult(
                            check_name=f"技术指标{field}验证",
                            status=ValidationStatus.WARNING,
                            message=f"{field}值异常: {avg_value:.2f}",
                            details={'field': field, 'avg_value': avg_value},
                            recommendation=f"检查{field}指标计算是否正确"
                        ))
                    else:
                        results.append(ValidationResult(
                            check_name=f"技术指标{field}验证",
                            status=ValidationStatus.PASS,
                            message=f"{field}值正常: {avg_value:.2f}",
                            details={'field': field, 'avg_value': avg_value},
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
                    details={'field': field, 'missing_sources': missing_sources},
                    recommendation=f"从数据源获取{field}字段数据"
                ))
            else:
                results.append(ValidationResult(
                    check_name=f"数据字段{field}完整性",
                    status=ValidationStatus.PASS,
                    message=f"所有数据源包含{field}字段",
                    details={'field': field},
                    recommendation=""
                ))
        
        return results
    
    def validate_time_consistency(self, data_list: List[Dict]) -> List[ValidationResult]:
        """验证时间一致性"""
        results = []
        
        timestamps = []
        sources = []
        
        for data in data_list:
            if 'timestamp' in data:
                timestamps.append(data['timestamp'])
                sources.append(data.get('source', 'unknown'))
        
        if not timestamps:
            results.append(ValidationResult(
                check_name="时间戳完整性",
                status=ValidationStatus.WARNING,
                message="无时间戳数据",
                details={'timestamp_count': 0},
                recommendation="从数据源获取时间戳数据"
            ))
            return results
        
        # 检查时间戳是否在合理范围内
        now = datetime.now()
        max_age_hours = 24
        
        old_timestamps = []
        for i, ts in enumerate(timestamps):
            if isinstance(ts, datetime):
                age_hours = (now - ts).total_seconds() / 3600
                if age_hours > max_age_hours:
                    old_timestamps.append((sources[i], ts, age_hours))
        
        if old_timestamps:
            details = {s: {'timestamp': str(ts), 'age_hours': age} for s, ts, age in old_timestamps}
            results.append(ValidationResult(
                check_name="数据时效性验证",
                status=ValidationStatus.WARNING,
                message=f"发现{len(old_timestamps)}个数据源数据过期",
                details=details,
                recommendation="更新数据源数据到最新时间"
            ))
        else:
            results.append(ValidationResult(
                check_name="数据时效性验证",
                status=ValidationStatus.PASS,
                message="所有数据在时效范围内",
                details={'max_age_hours': max_age_hours},
                recommendation=""
            ))
        
        return results
    
    def validate_market_logic(self, data_list: List[Dict]) -> List[ValidationResult]:
        """验证市场逻辑"""
        results = []
        
        for data in data_list:
            source = data.get('source', 'unknown')
            
            # 检查价格逻辑
            if all(field in data for field in ['high', 'low', 'open', 'close']):
                # 高低价逻辑
                if data['high'] < data['low']:
                    results.append(ValidationResult(
                        check_name=f"市场逻辑{source}验证",
                        status=ValidationStatus.FAIL,
                        message=f"价格逻辑错误: 最高价({data['high']}) < 最低价({data['low']})",
                        details={'source': source, 'high': data['high'], 'low': data['low']},
                        recommendation=f"数据源{source}存在逻辑错误，应排除"
                    ))
                
                # 开盘价应在高低价范围内
                if data['open'] < data['low'] or data['open'] > data['high']:
                    results.append(ValidationResult(
                        check_name=f"市场逻辑{source}验证",
                        status=ValidationStatus.WARNING,
                        message=f"开盘价异常: {data['open']} 不在 [{data['low']}, {data['high']}] 范围内",
                        details={'source': source, 'open': data['open'], 'high': data['high'], 'low': data['low']},
                        recommendation=f"检查数据源{source}的开盘价数据"
                    ))
                
                # 收盘价应在高低价范围内
                if data['close'] < data['low'] or data['close'] > data['high']:
                    results.append(ValidationResult(
                        check_name=f"市场逻辑{source}验证",
                        status=ValidationStatus.WARNING,
                        message=f"收盘价异常: {data['close']} 不在 [{data['low']}, {data['high']}] 范围内",
                        details={'source': source, 'close': data['close'], 'high': data['high'], 'low': data['low']},
                        recommendation=f"检查数据源{source}的收盘价数据"
                    ))
            
            # 检查涨跌逻辑
            if all(field in data for field in ['change', 'change_percent', 'open', 'close']):
                expected_change = data['close'] - data['open']
                expected_change_percent = (expected_change / data['open']) * 100 if data['open'] != 0 else 0
                
                if abs(data['change'] - expected_change) > 0.01:
                    results.append(ValidationResult(
                        check_name=f"涨跌逻辑{source}验证",
                        status=ValidationStatus.WARNING,
                        message=f"涨跌额计算不一致: {data['change']} vs 预期{expected_change:.2f}",
                        details={'source': source, 'change': data['change'], 'expected_change': expected_change},
                        recommendation=f"检查数据源{source}的涨跌额计算"
                    ))
        
        return results
    
    def run_full_validation(self, symbol: str, data_list: List[Dict]) -> Dict:
        """运行完整验证"""
        print(f"开始验证 {symbol} 数据...")
        print("=" * 50)
        
        all_results = []
        
        # 1. 价格数据验证
        print("1. 价格数据验证...")
        price_results = self.validate_price_data(data_list)
        all_results.extend(price_results)
        
        # 2. 技术指标验证
        print("2. 技术指标验证...")
        indicator_results = self.validate_technical_indicators(data_list)
        all_results.extend(indicator_results)
        
        # 3. 数据完整性验证
        print("3. 数据完整性验证...")
        completeness_results = self.validate_data_completeness(data_list)
        all_results.extend(completeness_results)
        
        # 4. 时间一致性验证
        print("4. 时间一致性验证...")
        time_results = self.validate_time_consistency(data_list)
        all_results.extend(time_results)
        
        # 5. 市场逻辑验证
        print("5. 市场逻辑验证...")
        logic_results = self.validate_market_logic(data_list)
        all_results.extend(logic_results)
        
        # 生成验证报告
        report = self._generate_validation_report(symbol, all_results)
        
        # 打印验证结果
        self._print_validation_results(all_results)
        
        # 保存验证历史
        self.validation_history.append(report)
        
        return report
    
    def _generate_validation_report(self, symbol: str, results: List[ValidationResult]) -> Dict:
        """生成验证报告"""
        pass_count = sum(1 for r in results if r.status == ValidationStatus.PASS)
        warning_count = sum(1 for r in results if r.status == ValidationStatus.WARNING)
        fail_count = sum(1 for r in results if r.status == ValidationStatus.FAIL)
        
        # 计算总体验证分数
        total_checks = len(results)
        if total_checks > 0:
            validation_score = (pass_count * 100 + warning_count * 50) / total_checks
        else:
            validation_score = 0
        
        # 确定总体状态
        if fail_count > 0:
            overall_status = ValidationStatus.FAIL
        elif warning_count > 0:
            overall_status = ValidationStatus.WARNING
        else:
            overall_status = ValidationStatus.PASS
        
        report = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'overall_status': overall_status.value,
            'validation_score': validation_score,
            'statistics': {
                'total_checks': total_checks,
                'pass_count': pass_count,
                'warning_count': warning_count,
                'fail_count': fail_count
            },
            'results': []
        }
        
        for result in results:
            report['results'].append({
                'check_name': result.check_name,
                'status': result.status.value,
                'message': result.message,
                'details': result.details,
                'recommendation': result.recommendation
            })
        
        return report
    
    def _print_validation_results(self, results: List[ValidationResult]):
        """打印验证结果"""
        print("\n验证结果:")
        print("-" * 50)
        
        for i, result in enumerate(results, 1):
            status_symbol = {
                ValidationStatus.PASS: "✓",
                ValidationStatus.WARNING: "⚠",
                ValidationStatus.FAIL: "✗"
            }[result.status]
            
            print(f"{i:2d}. {status_symbol} {result.check_name}")
            print(f"    状态: {result.status.value}")
            print(f"    消息: {result.message}")
            
            if result.recommendation:
                print(f"    建议: {result.recommendation}")
            
            print()

def main():
    """主函数"""
    validator = DataValidationScript()
    
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
            'volume': 128380,
            'source': 'investing_com',
            'timestamp': datetime.now(),
            'rsi': 56.55,
            'macd': 4.17,
            'adx': 24.80,
            'cci': 95.91
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
            'timestamp': datetime.now(),
            'rsi': 56.55,
            'macd': 4.17,
            'adx': 35.38,
            'cci': 95.91
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
            'timestamp': datetime.now(),
            'rsi': 56.90,
            'macd': 0.24,
            'adx': 18.28,
            'cci': 77.37
        }
    ]
    
    # 运行完整验证
    report = validator.run_full_validation('XAUUSD', test_data)
    
    print("\n" + "=" * 50)
    print("验证报告摘要")
    print("=" * 50)
    print(f"品种: {report['symbol']}")
    print(f"总体状态: {report['overall_status']}")
    print(f"验证分数: {report['validation_score']:.1f}/100")
    print(f"检查项数: {report['statistics']['total_checks']}")
    print(f"通过: {report['statistics']['pass_count']}")
    print(f"警告: {report['statistics']['warning_count']}")
    print(f"失败: {report['statistics']['fail_count']}")
    
    # 保存报告到文件
    report_filename = f"F:/Commodities/Reports/validation/validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    import os
    os.makedirs(os.path.dirname(report_filename), exist_ok=True)
    
    with open(report_filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n验证报告已保存到: {report_filename}")

if __name__ == "__main__":
    main()