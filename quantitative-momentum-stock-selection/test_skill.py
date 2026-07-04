"""
量化动量选股系统 - 测试脚本
版本: 1.0.0
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    
    try:
        from scripts import get_config, DataCollector, MomentumScorer, MomentumStrategy
        print("✓ 模块导入成功")
        return True
    except Exception as e:
        print(f"✗ 模块导入失败: {e}")
        return False

def test_config():
    """测试配置加载"""
    print("\n测试配置加载...")
    
    try:
        from scripts import get_config
        config = get_config()
        
        # 检查配置属性
        assert hasattr(config, 'data'), "缺少data配置"
        assert hasattr(config, 'momentum'), "缺少momentum配置"
        assert hasattr(config, 'trend'), "缺少trend配置"
        assert hasattr(config, 'valuation'), "缺少valuation配置"
        assert hasattr(config, 'risk'), "缺少risk配置"
        
        print("✓ 配置加载成功")
        print(f"  - 动量窗口: {config.momentum.short_window}/{config.momentum.medium_window}/{config.momentum.long_window}")
        print(f"  - 仓位限制: 单股{config.risk.max_position_per_stock*100:.0f}%，行业{config.risk.max_position_per_sector*100:.0f}%")
        return True
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        return False

def test_scorer():
    """测试动量打分器"""
    print("\n测试动量打分器...")
    
    try:
        from scripts import get_config, MomentumScorer
        import pandas as pd
        import numpy as np
        
        config = get_config()
        scorer = MomentumScorer(config)
        
        # 创建测试数据
        np.random.seed(42)
        dates = pd.date_range('2020-01-01', periods=500, freq='B')
        price = 100 + np.cumsum(np.random.randn(500) * 0.5)
        
        test_data = pd.DataFrame({
            'date': dates,
            'open': price + np.random.randn(500) * 0.5,
            'high': price + abs(np.random.randn(500)) * 0.5,
            'low': price - abs(np.random.randn(500)) * 0.5,
            'close': price,
            'volume': np.random.randint(1000000, 5000000, 500),
        })
        
        # 计算动量分数
        score = scorer.score_stock(test_data)
        
        print("✓ 动量打分成功")
        print(f"  - 总分: {score.total_score:.1f}")
        print(f"  - 等级: {score.grade}")
        print(f"  - 趋势阶段: {score.trend_stage}")
        print(f"  - 各维度分数:")
        for component, value in score.components.items():
            print(f"    {component}: {value:.1f}")
        
        return True
    except Exception as e:
        print(f"✗ 动量打分失败: {e}")
        return False

def test_strategy():
    """测试策略模块"""
    print("\n测试策略模块...")
    
    try:
        from scripts import get_config, MomentumStrategy, MomentumScorer
        import pandas as pd
        import numpy as np
        
        config = get_config()
        strategy = MomentumStrategy(config)
        
        # 创建测试股票数据
        np.random.seed(42)
        stock_data = {}
        
        for i in range(5):  # 5只测试股票
            stock_code = f"00000{i}"
            dates = pd.date_range('2020-01-01', periods=500, freq='B')
            price = 100 + np.cumsum(np.random.randn(500) * 0.5)
            
            stock_data[stock_code] = pd.DataFrame({
                'date': dates,
                'open': price + np.random.randn(500) * 0.5,
                'high': price + abs(np.random.randn(500)) * 0.5,
                'low': price - abs(np.random.randn(500)) * 0.5,
                'close': price,
                'volume': np.random.randint(1000000, 5000000, 500),
            })
        
        # 生成交易信号
        signals = strategy.generate_signals(stock_data)
        
        print("✓ 策略信号生成成功")
        print(f"  - 生成信号数量: {len(signals)}")
        
        if signals:
            print(f"  - 第一个信号:")
            signal = signals[0]
            print(f"    股票代码: {signal.stock_code}")
            print(f"    操作: {signal.action}")
            print(f"    动量分数: {signal.score.total_score:.1f}")
            print(f"    原因: {signal.reason}")
        
        return True
    except Exception as e:
        print(f"✗ 策略测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("量化动量选股系统 v1.0.0 - 测试脚本")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_config,
        test_scorer,
        test_strategy,
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
        print("✓ 所有测试通过！")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())