#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实际数据测试脚本

验证优化后的脚本在实际数据上的功能完整性
"""

import sys
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import duckdb

def test_real_data():
    """测试实际数据"""
    
    print("="*60)
    print("实际数据测试")
    print("="*60)
    
    # 数据库路径
    db_path = Path(__file__).parent.parent / "data" / "futures_data.duckdb"
    
    if not db_path.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    print(f"✅ 数据库文件存在: {db_path}")
    
    # 连接数据库
    conn = duckdb.connect(str(db_path), read_only=True)
    
    try:
        # 检查表
        tables = conn.execute("SHOW TABLES").fetchdf()
        print(f"\n数据库表: {len(tables)} 个")
        for table in tables['name']:
            print(f"  - {table}")
        
        # 检查K线数据
        symbols = ['sc', 'bu', 'fu', 'lu', 'pg']
        
        for symbol in symbols:
            table_name = f"kline_{symbol}"
            try:
                df = conn.execute(f"SELECT * FROM {table_name} ORDER BY date").fetchdf()
                print(f"\n{symbol.upper()} K线数据: {len(df)} 行, {len(df.columns)} 列")
                
                if len(df) > 0:
                    print(f"  日期范围: {df['date'].min()} 到 {df['date'].max()}")
                    print(f"  最新收盘价: {df['close'].iloc[-1]:.2f}")
                    
                    # 测试技术指标计算
                    from calculate_indicators import calculate_all_indicators_batch, generate_comprehensive_signal
                    
                    indicators_df = calculate_all_indicators_batch(df)
                    signals = generate_comprehensive_signal(indicators_df)
                    
                    print(f"  技术指标: {len(indicators_df.columns)} 列")
                    print(f"  信号数量: {len(signals)}")
                    
                    # 打印信号
                    for signal in signals:
                        print(f"    {signal['name']}: {signal['description']} (强度: {signal['strength']})")
                    
                    # 测试打分功能
                    from scoring import CompleteFuelOilScorer
                    
                    if symbol == 'fu':
                        scorer = CompleteFuelOilScorer()
                        latest = indicators_df.iloc[-1]
                        
                        score = scorer.calculate(
                            fu_close=latest['close'],
                            lu_close=0,  # 需要LU数据
                            brent=70,  # 需要布伦特数据
                            sc=500,  # 需要SC数据
                            usdcny=7.2,
                            freight=50,
                            crack_fu=200,
                            crack_lu=300,
                            crack_refinery=60,
                            india_import_yoy=5,
                            bdi_percentile=55,
                            bunker_yoy=3,
                            month=6,
                            sg_inventory=2000,
                            sg_inventory_prev=1900,
                            sg_inventory_yoy=10,
                            arrival_yoy=-5,
                            mops_change=2,
                            production_yoy=3,
                            import_yoy=-2,
                            warehouse_level=45,
                            policy_factor=1,
                            basis=50,
                            month_spread=30,
                            geopolitics=1
                        )
                        
                        print(f"  燃料油打分: {score.total_score:.1f} ({score.signal})")
                
            except Exception as e:
                print(f"  ❌ {symbol.upper()} 数据获取失败: {e}")
        
        conn.close()
        print(f"\n{'='*60}")
        print("实际数据测试完成")
        print(f"{'='*60}")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        conn.close()
        return False

if __name__ == "__main__":
    success = test_real_data()
    sys.exit(0 if success else 1)
