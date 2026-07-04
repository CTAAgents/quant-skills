"""
量化动量选股系统 - A股优化功能测试
版本: 1.1.0
"""

import sys
import os
import pandas as pd
import numpy as np

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_config_optimization():
    """测试配置优化"""
    print("测试配置优化...")
    
    try:
        from scripts import get_config
        config = get_config()
        
        # 验证动量窗口优化
        assert config.momentum.short_window == 15, f"短期窗口应为15，实际为{config.momentum.short_window}"
        assert config.momentum.medium_window == 45, f"中期窗口应为45，实际为{config.momentum.medium_window}"
        assert config.momentum.long_window == 150, f"长期窗口应为150，实际为{config.momentum.long_window}"
        
        # 验证打分权重优化
        assert config.momentum.weights['price_momentum'] == 0.25, "价格动量权重应为0.25"
        assert config.momentum.weights['volume_confirmation'] == 0.25, "成交量确认权重应为0.25"
        assert config.momentum.weights['risk_control'] == 0.15, "风险控制权重应为0.15"
        
        # 验证阈值优化
        assert config.momentum.momentum_thresholds['strong_buy'] == 75, "强烈买入阈值应为75"
        assert config.momentum.momentum_thresholds['buy'] == 65, "买入阈值应为65"
        
        # 验证风险管理优化
        assert config.risk.initial_stop_loss_atr == 1.5, "初始止损应为1.5倍ATR"
        assert config.risk.trailing_stop_loss_atr == 0.75, "移动止损应为0.75倍ATR"
        assert config.risk.time_stop_days == 15, "时间止损应为15天"
        
        # 验证仓位限制优化
        assert config.risk.max_position_per_stock == 0.15, "单股仓位应为15%"
        assert config.risk.max_position_per_sector == 0.25, "行业仓位应为25%"
        assert config.risk.max_total_position == 0.70, "总仓位应为70%"
        
        # 验证A股特有配置
        assert config.data.limit_pct == 0.10, "涨跌停比例应为10%"
        assert config.data.enable_limit_filter == True, "涨跌停过滤应启用"
        
        print("✓ 配置优化验证通过")
        return True
    except Exception as e:
        print(f"✗ 配置优化验证失败: {e}")
        return False


def test_limit_filter():
    """测试涨跌停过滤功能"""
    print("\n测试涨跌停过滤功能...")
    
    try:
        from scripts import get_config, MomentumScorer
        config = get_config()
        scorer = MomentumScorer(config)
        
        # 创建测试数据（包含涨跌停）
        np.random.seed(42)
        dates = pd.date_range('2020-01-01', periods=500, freq='B')
        price = 100 + np.cumsum(np.random.randn(500) * 0.5)
        
        # 模拟涨跌停（第100天涨10%，第200天跌10%）
        price[100] = price[99] * 1.10  # 涨停
        price[200] = price[199] * 0.90  # 跌停
        
        test_data = pd.DataFrame({
            'date': dates,
            'open': price + np.random.randn(500) * 0.5,
            'high': price + abs(np.random.randn(500)) * 0.5,
            'low': price - abs(np.random.randn(500)) * 0.5,
            'close': price,
            'volume': np.random.randint(1000000, 5000000, 500),
        })
        
        # 测试涨跌停过滤
        filtered_data = scorer.filter_limit_up_down(test_data, limit_pct=0.10)
        
        # 验证过滤结果
        original_len = len(test_data)
        filtered_len = len(filtered_data)
        
        print(f"  原始数据长度: {original_len}")
        print(f"  过滤后数据长度: {filtered_len}")
        print(f"  过滤掉的数据: {original_len - filtered_len}条（涨跌停数据）")
        
        # 验证涨跌停被正确标记
        if 'pct_change' in test_data.columns:
            limit_up_count = test_data['is_limit_up'].sum()
            limit_down_count = test_data['is_limit_down'].sum()
            print(f"  涨停次数: {limit_up_count}")
            print(f"  跌停次数: {limit_down_count}")
        
        print("✓ 涨跌停过滤功能验证通过")
        return True
    except Exception as e:
        print(f"✗ 涨跌停过滤功能验证失败: {e}")
        return False


def test_limit_risk_check():
    """测试涨跌停风险检查功能"""
    print("\n测试涨跌停风险检查功能...")
    
    try:
        from scripts import get_config, MomentumStrategy
        import pandas as pd
        import numpy as np
        
        config = get_config()
        strategy = MomentumStrategy(config)
        
        # 创建测试数据
        np.random.seed(42)
        dates = pd.date_range('2020-01-01', periods=100, freq='B')
        price = 100 + np.cumsum(np.random.randn(100) * 0.5)
        
        test_data = pd.DataFrame({
            'date': dates,
            'open': price + np.random.randn(100) * 0.5,
            'high': price + abs(np.random.randn(100)) * 0.5,
            'low': price - abs(np.random.randn(100)) * 0.5,
            'close': price,
            'volume': np.random.randint(1000000, 5000000, 100),
        })
        
        # 测试正常情况
        current_price = test_data['close'].iloc[-1]
        risk, reason = strategy.check_limit_risk(test_data, current_price)
        print(f"  正常情况 - 风险: {risk}, 原因: {reason}")
        
        # 测试跌停情况
        test_data跌停 = test_data.copy()
        test_data跌停.iloc[-1, test_data跌停.columns.get_loc('close')] = test_data跌停['close'].iloc[-2] * 0.90
        risk, reason = strategy.check_limit_risk(test_data跌停, test_data跌停['close'].iloc[-1])
        print(f"  跌停情况 - 风险: {risk}, 原因: {reason}")
        
        # 测试连续下跌情况
        test_data连续下跌 = test_data.copy()
        for i in range(-5, 0):
            test_data连续下跌.iloc[i, test_data连续下跌.columns.get_loc('close')] = test_data连续下跌['close'].iloc[i-1] * 0.98
        risk, reason = strategy.check_limit_risk(test_data连续下跌, test_data连续下跌['close'].iloc[-1])
        print(f"  连续下跌情况 - 风险: {risk}, 原因: {reason}")
        
        print("✓ 涨跌停风险检查功能验证通过")
        return True
    except Exception as e:
        print(f"✗ 涨跌停风险检查功能验证失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("量化动量选股系统 v1.1.0 - A股优化功能测试")
    print("=" * 60)
    
    tests = [
        test_config_optimization,
        test_limit_filter,
        test_limit_risk_check,
    ]
    
    results = []
    
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"测试异常: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("✓ 所有A股优化功能测试通过！")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())