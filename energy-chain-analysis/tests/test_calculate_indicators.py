#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术指标计算测试 — 优化版
验证批量指标计算、信号生成功能
"""

import sys
import pytest
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from calculate_indicators import (
    generate_demo_data, calculate_all_indicators_batch,
    generate_comprehensive_signal,
)


# ========== 测试1-3：基础工具函数 ==========

class TestBasicFunctions:
    """基础工具函数测试"""

    def test_generate_demo_data_length(self):
        """测试1：generate_demo_data 返回正确行数"""
        df = generate_demo_data(60)
        assert len(df) == 60, f"Expected 60 rows, got {len(df)}"

    def test_calculate_all_indicators_batch_columns(self):
        """测试2：calculate_all_indicators_batch 返回完整列"""
        df = generate_demo_data(60)
        result = calculate_all_indicators_batch(df)
        assert len(result.columns) >= 25, f"Expected >=25 columns, got {len(result.columns)}"
        assert "close" in result.columns
        assert "RSI_14" in result.columns

    def test_calculate_all_indicators_batch_empty_input(self):
        """测试3：calculate_all_indicators_batch 处理空输入"""
        df = pd.DataFrame()
        result = calculate_all_indicators_batch(df)
        assert result.empty


# ========== 测试4-6：信号生成 ==========

class TestSignalGeneration:
    """信号生成测试"""

    def test_generate_comprehensive_signal_returns_list(self):
        """测试4：generate_comprehensive_signal 返回列表"""
        df = generate_demo_data(60)
        indicators_df = calculate_all_indicators_batch(df)
        signals = generate_comprehensive_signal(indicators_df)
        assert isinstance(signals, list)

    def test_generate_comprehensive_signal_structure(self):
        """测试5：信号结构正确"""
        df = generate_demo_data(60)
        indicators_df = calculate_all_indicators_batch(df)
        signals = generate_comprehensive_signal(indicators_df)
        
        for signal in signals:
            assert 'type' in signal
            assert 'name' in signal
            assert 'value' in signal
            assert 'strength' in signal
            assert 'description' in signal

    def test_generate_comprehensive_signal_empty_input(self):
        """测试6：generate_comprehensive_signal 处理空输入"""
        df = pd.DataFrame()
        signals = generate_comprehensive_signal(df)
        assert signals == []


# ========== 测试7-9：指标计算正确性 ==========

class TestIndicatorCalculation:
    """指标计算正确性测试"""

    def test_rsi_range(self):
        """测试7：RSI在0-100范围内"""
        df = generate_demo_data(60)
        result = calculate_all_indicators_batch(df)
        rsi = result['RSI_14'].dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_macd_calculation(self):
        """测试8：MACD计算正确"""
        df = generate_demo_data(60)
        result = calculate_all_indicators_batch(df)
        assert 'MACD_DIF' in result.columns
        assert 'MACD_DEA' in result.columns
        assert 'MACD_HIST' in result.columns

    def test_atr_positive(self):
        """测试9：ATR为正数"""
        df = generate_demo_data(60)
        result = calculate_all_indicators_batch(df)
        atr = result['ATR_14'].dropna()
        assert (atr > 0).all()


# ========== 测试10-12：性能测试 ==========

class TestPerformance:
    """性能测试"""

    def test_batch_calculation_performance(self):
        """测试10：批量计算性能"""
        import time
        df = generate_demo_data(1000)
        start_time = time.time()
        result = calculate_all_indicators_batch(df)
        elapsed = time.time() - start_time
        
        # 应该在2秒内完成
        assert elapsed < 2.0, f"Batch calculation took {elapsed:.2f} seconds"

    def test_signal_generation_performance(self):
        """测试11：信号生成性能"""
        import time
        df = generate_demo_data(1000)
        indicators_df = calculate_all_indicators_batch(df)
        
        start_time = time.time()
        signals = generate_comprehensive_signal(indicators_df)
        elapsed = time.time() - start_time
        
        # 应该在1秒内完成
        assert elapsed < 1.0, f"Signal generation took {elapsed:.2f} seconds"

    def test_cache_mechanism(self):
        """测试12：缓存机制"""
        # 测试缓存目录创建
        from calculate_indicators import CACHE_DIR
        assert CACHE_DIR.exists()


# ========== 测试13-15：边界条件 ==========

class TestEdgeCases:
    """边界条件测试"""

    def test_minimum_data_points(self):
        """测试13：最小数据点"""
        df = generate_demo_data(20)  # 小于最小周期
        result = calculate_all_indicators_batch(df)
        # 应该仍然能计算，但可能有NaN
        assert len(result) == 20

    def test_missing_columns(self):
        """测试14：缺少必要列"""
        df = generate_demo_data(60)
        df = df.drop(columns=['volume'])
        result = calculate_all_indicators_batch(df)
        # 应该返回原数据
        assert len(result.columns) == len(df.columns)

    def test_zero_volume(self):
        """测试15：零成交量"""
        df = generate_demo_data(60)
        df['volume'] = 0
        result = calculate_all_indicators_batch(df)
        # 应该仍然能计算
        assert len(result) == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
