#!/usr/bin/env python3
"""
贵金属数据标准化采集与验证系统
整合多源数据采集、差异处理和验证功能
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, List

# 添加脚本目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from precious_metals_data_collector import PreciousMetalsDataCollector, DataTimeframe
from data_difference_handler import DataDifferenceHandler
from data_validation_script import DataValidationScript, ValidationStatus

class PreciousMetalsDataSystem:
    """贵金属数据标准化系统"""
    
    def __init__(self):
        self.collector = PreciousMetalsDataCollector()
        self.difference_handler = DataDifferenceHandler(tolerance_percent=0.5)
        self.validator = DataValidationScript()
        
        # 系统配置
        self.config = {
            'symbols': ['XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD'],
            'min_data_sources': 2,
            'max_price_difference_percent': 1.0,
            'required_validation_score': 80.0,
            'output_directory': os.path.join(script_dir, '..', 'output', 'validation')
        }
        
        # 确保输出目录存在
        os.makedirs(self.config['output_directory'], exist_ok=True)
    
    def run_data_collection_pipeline(self) -> Dict:
        """运行数据采集管道"""
        print("启动贵金属数据标准化采集系统")
        print("=" * 60)
        
        all_results = {}
        
        for symbol in self.config['symbols']:
            print(f"\n处理 {symbol}...")
            print("-" * 40)
            
            # 1. 多源数据采集
            print("1. 多源数据采集...")
            data_list = self.collector.collect_multi_source_data([symbol])
            symbol_data = data_list.get(symbol, [])
            
            if not symbol_data:
                print(f"  ✗ {symbol}: 无数据")
                all_results[symbol] = {'status': 'no_data'}
                continue
            
            print(f"  ✓ 采集到 {len(symbol_data)} 个数据源")
            
            # 2. 数据差异检测与处理
            print("2. 数据差异检测与处理...")
            differences = self.difference_handler.detect_differences(symbol_data)
            
            if differences:
                print(f"  ⚠ 检测到 {len(differences)} 个差异")
                for diff in differences:
                    print(f"    - {diff.severity}: {diff.description}")
            
            # 处理差异
            processed_data = self.difference_handler.handle_differences(symbol_data, differences)
            print(f"  ✓ 处理后保留 {len(processed_data)} 个数据源")
            
            # 3. 数据验证
            print("3. 数据验证...")
            validation_report = self.validator.run_full_validation(symbol, processed_data)
            
            # 4. 计算共识数据
            print("4. 计算共识数据...")
            consensus_data = self.difference_handler.calculate_weighted_average(processed_data)
            
            # 5. 生成最终报告
            print("5. 生成最终报告...")
            final_report = self._generate_final_report(
                symbol, 
                symbol_data, 
                differences, 
                validation_report, 
                consensus_data
            )
            
            all_results[symbol] = final_report
            
            # 打印摘要
            self._print_symbol_summary(symbol, final_report)
        
        # 生成系统级报告
        system_report = self._generate_system_report(all_results)
        
        # 保存报告
        self._save_reports(system_report)
        
        print("\n" + "=" * 60)
        print("数据采集系统运行完成")
        print("=" * 60)
        
        return system_report
    
    def _generate_final_report(self, symbol: str, raw_data: List[Dict], 
                              differences: List, validation_report: Dict, 
                              consensus_data: Dict) -> Dict:
        """生成最终报告"""
        return {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'raw_data_count': len(raw_data),
            'processed_data_count': len([d for d in raw_data]),  # 简化处理
            'differences_count': len(differences),
            'validation_status': validation_report.get('overall_status', 'unknown'),
            'validation_score': validation_report.get('validation_score', 0),
            'consensus_data': consensus_data,
            'data_sources': [d.get('source', 'unknown') for d in raw_data],
            'differences_summary': {
                'high': len([d for d in differences if d.severity == 'high']),
                'medium': len([d for d in differences if d.severity == 'medium']),
                'low': len([d for d in differences if d.severity == 'low'])
            },
            'raw_data': raw_data,
            'validation_details': validation_report.get('results', [])
        }
    
    def _print_symbol_summary(self, symbol: str, report: Dict):
        """打印品种摘要"""
        print(f"\n{symbol} 处理结果:")
        print(f"  数据源数量: {report['raw_data_count']}")
        print(f"  差异数量: {report['differences_count']}")
        print(f"  验证状态: {report['validation_status']}")
        print(f"  验证分数: {report['validation_score']:.1f}/100")
        
        if report['consensus_data']:
            cd = report['consensus_data']
            print(f"  共识价格: {cd.get('weighted_price', 0):.2f}")
            print(f"  数据源: {', '.join(report['data_sources'])}")
        
        # 验证结果摘要
        if report['validation_details']:
            pass_count = sum(1 for r in report['validation_details'] if r.get('status') == 'pass')
            warning_count = sum(1 for r in report['validation_details'] if r.get('status') == 'warning')
            fail_count = sum(1 for r in report['validation_details'] if r.get('status') == 'fail')
            
            print(f"  验证结果: {pass_count}通过, {warning_count}警告, {fail_count}失败")
    
    def _generate_system_report(self, all_results: Dict) -> Dict:
        """生成系统级报告"""
        # 统计数据
        total_symbols = len(all_results)
        successful_symbols = sum(1 for r in all_results.values() if r.get('validation_status') != 'no_data')
        
        # 计算平均验证分数
        validation_scores = [r.get('validation_score', 0) for r in all_results.values() 
                           if r.get('validation_score', 0) > 0]
        avg_validation_score = sum(validation_scores) / len(validation_scores) if validation_scores else 0
        
        # 系统状态
        if avg_validation_score >= self.config['required_validation_score']:
            system_status = "PASS"
        elif avg_validation_score >= 60:
            system_status = "WARNING"
        else:
            system_status = "FAIL"
        
        return {
            'timestamp': datetime.now(),
            'system_status': system_status,
            'configuration': self.config,
            'statistics': {
                'total_symbols': total_symbols,
                'successful_symbols': successful_symbols,
                'failed_symbols': total_symbols - successful_symbols,
                'average_validation_score': avg_validation_score
            },
            'symbol_results': all_results,
            'recommendations': self._generate_recommendations(all_results)
        }
    
    def _generate_recommendations(self, all_results: Dict) -> List[str]:
        """生成系统建议"""
        recommendations = []
        
        # 检查验证分数
        low_score_symbols = [symbol for symbol, result in all_results.items() 
                           if result.get('validation_score', 0) < 70]
        
        if low_score_symbols:
            recommendations.append(f"以下品种验证分数较低，需要检查数据源: {', '.join(low_score_symbols)}")
        
        # 检查数据源数量
        low_data_symbols = [symbol for symbol, result in all_results.items() 
                          if result.get('raw_data_count', 0) < self.config['min_data_sources']]
        
        if low_data_symbols:
            recommendations.append(f"以下品种数据源不足，需要增加数据源: {', '.join(low_data_symbols)}")
        
        # 检查差异处理
        high_diff_symbols = [symbol for symbol, result in all_results.items() 
                           if result.get('differences_count', 0) > 3]
        
        if high_diff_symbols:
            recommendations.append(f"以下品种数据差异较多，需要检查数据源一致性: {', '.join(high_diff_symbols)}")
        
        return recommendations
    
    def _save_reports(self, system_report: Dict):
        """保存报告"""
        timestamp = system_report['timestamp'].strftime('%Y%m%d_%H%M%S')
        
        # 保存JSON报告
        json_filename = f"{self.config['output_directory']}/system_report_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(system_report, f, indent=2, ensure_ascii=False, default=str)
        
        # 保存摘要报告
        summary_filename = f"{self.config['output_directory']}/summary_report_{timestamp}.txt"
        with open(summary_filename, 'w', encoding='utf-8') as f:
            f.write("贵金属数据标准化采集系统报告\n")
            f.write("=" * 60 + "\n")
            f.write(f"报告时间: {system_report['timestamp']}\n")
            f.write(f"系统状态: {system_report['system_status']}\n")
            f.write(f"平均验证分数: {system_report['statistics']['average_validation_score']:.1f}/100\n")
            f.write(f"处理品种数: {system_report['statistics']['total_symbols']}\n")
            f.write(f"成功品种数: {system_report['statistics']['successful_symbols']}\n")
            f.write(f"失败品种数: {system_report['statistics']['failed_symbols']}\n\n")
            
            # 写入品种结果
            for symbol, result in system_report['symbol_results'].items():
                f.write(f"{symbol}:\n")
                f.write(f"  数据源数量: {result.get('raw_data_count', 0)}\n")
                f.write(f"  验证状态: {result.get('validation_status', 'unknown')}\n")
                f.write(f"  验证分数: {result.get('validation_score', 0):.1f}\n")
                
                if result.get('consensus_data'):
                    cd = result['consensus_data']
                    f.write(f"  共识价格: {cd.get('weighted_price', 0):.2f}\n")
                f.write("\n")
            
            # 写入建议
            if system_report['recommendations']:
                f.write("系统建议:\n")
                for i, rec in enumerate(system_report['recommendations'], 1):
                    f.write(f"{i}. {rec}\n")
        
        print(f"\n报告已保存:")
        print(f"  JSON报告: {json_filename}")
        print(f"  摘要报告: {summary_filename}")

def main():
    """主函数"""
    system = PreciousMetalsDataSystem()
    system.run_data_collection_pipeline()

if __name__ == "__main__":
    main()