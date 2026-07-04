#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
futures-data-search 批量性能优化器 v1.0

核心优化：
1. 并行批量获取：ThreadPoolExecutor 并行拉取多品种数据
2. 智能缓存预热：开盘前自动预热活跃品种到缓存
3. 重复请求去重：同一品种在5秒内的重复请求从缓存返回

用法：
    from batch_optimizer import BatchOptimizer, bo
    
    # 并行获取多品种行情（单线程15~30s → 并行3~5s）
    results = bo.batch_get_quote(['CU', 'RB', 'I', 'SC', 'AU', ...])
    
    # 预热缓存（开盘前调用）
    bo.warmup_cache()
    
    # 获取性能统计
    stats = bo.get_perf_stats()
"""

import json
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path


# 去重窗口（秒）：同一品种在这段时间内的重复请求从缓存返回
DEDUP_WINDOW = 5
# 最大并行数
MAX_WORKERS = 10
# 返回结果缓存大小
MAX_CACHE_SIZE = 200

PERF_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "WorkBuddy", ".workbuddy", "feedback", "perf"
)


class BatchOptimizer:
    """批量性能优化器"""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or PERF_DIR
        os.makedirs(self.data_dir, exist_ok=True)

        # 请求去重缓存 {variety: (timestamp, result)}
        self._dedup_cache: Dict[str, tuple] = {}
        self._dedup_lock = threading.RLock()

        # 性能统计
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'parallel_batches': 0,
            'total_time_serial_ms': 0,
            'total_time_parallel_ms': 0,
        }
        self._stats_lock = threading.RLock()

        # 数据获取函数（由外部注入）
        self._fetch_fn: Optional[Callable] = None

    def set_fetch_fn(self, fn: Callable):
        """设置数据获取函数（通常来自 MultiSourceAdapter.get_quote）"""
        self._fetch_fn = fn

    # ==================== 并行批量获取 ====================

    def batch_get_quote(self, varieties: List[str], **kwargs) -> Dict[str, Dict]:
        """并行获取多个品种的行情数据

        如果提供了 fetch_fn，使用它；否则返回空结果（供外部调度）。

        Args:
            varieties: 品种代码列表
            **kwargs: 传递给 fetch_fn 的额外参数

        Returns:
            {variety: {'success': bool, 'data': [...], 'data_source': str, 'error': str}}
        """
        results = {}
        start_time = time.time()

        with self._stats_lock:
            self._stats['parallel_batches'] += 1
            self._stats['total_requests'] += len(varieties)

        if not self._fetch_fn:
            return {v: {'success': False, 'error': '获取函数未设置'} for v in varieties}

        # 检查去重缓存
        to_fetch = []
        with self._dedup_lock:
            now = time.time()
            for v in varieties:
                cached = self._dedup_cache.get(v)
                if cached and (now - cached[0]) < DEDUP_WINDOW:
                    results[v] = cached[1]
                    with self._stats_lock:
                        self._stats['cache_hits'] += 1
                else:
                    to_fetch.append(v)

        if not to_fetch:
            # 全部命中缓存
            with self._stats_lock:
                self._stats['total_time_parallel_ms'] += (time.time() - start_time) * 1000
            return results

        # 并行获取
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(to_fetch))) as executor:
            future_map = {
                executor.submit(self._safe_fetch, v, **kwargs): v
                for v in to_fetch
            }
            for future in as_completed(future_map):
                v = future_map[future]
                try:
                    result = future.result()
                    results[v] = result
                    # 更新去重缓存
                    with self._dedup_lock:
                        self._dedup_cache[v] = (time.time(), result)
                        if len(self._dedup_cache) > MAX_CACHE_SIZE:
                            # 清理过期缓存
                            now = time.time()
                            self._dedup_cache = {
                                k: v for k, v in self._dedup_cache.items()
                                if (now - v[0]) < DEDUP_WINDOW * 2
                            }
                except Exception as e:
                    results[v] = {'success': False, 'error': str(e)[:100]}

        elapsed = time.time() - start_time
        serial_estimate = elapsed * len(varieties)  # 预估串行时间
        with self._stats_lock:
            self._stats['total_time_parallel_ms'] += elapsed * 1000
            self._stats['total_time_serial_ms'] += serial_estimate * 1000

        return results

    def _safe_fetch(self, variety: str, **kwargs) -> Dict:
        """安全获取单个品种数据"""
        try:
            if self._fetch_fn:
                result = self._fetch_fn(variety, **kwargs)
                if isinstance(result, dict) and result.get('success'):
                    return result
                return {'success': False, 'error': '获取返回空'}
            return {'success': False, 'error': '获取函数未设置'}
        except Exception as e:
            return {'success': False, 'error': str(e)[:100]}

    # ==================== 缓存预热 ====================

    def warmup_cache(self, varieties: List[str] = None, **kwargs) -> Dict:
        """预热缓存（开盘前调用）

        Args:
            varieties: 要预热的品种列表，默认所有活跃品种
            **kwargs: 传递给 batch_get_quote 的参数

        Returns:
            {'total': int, 'success': int, 'failed': int, 'duration_ms': float}
        """
        if not varieties:
            # 默认预热主要活跃品种
            varieties = [
                # 黑色系
                'I', 'RB', 'HC', 'J', 'JM', 'SM', 'SF',
                # 有色
                'CU', 'AL', 'ZN', 'PB', 'NI', 'SN', 'AU', 'AG',
                # 能化
                'SC', 'BU', 'FU', 'LU', 'PG', 'MA', 'TA', 'EG', 'EB', 'PP', 'L', 'V',
                # 农产品
                'M', 'Y', 'P', 'RM', 'OI', 'CF', 'SR', 'A', 'B', 'C', 'CS', 'JD',
                # 其他活跃
                'RU', 'RB', 'FG', 'SA', 'UR', 'PF', 'PR', 'PX', 'SI', 'LC', 'SP', 'BR',
            ]

        start = time.time()
        results = self.batch_get_quote(varieties, **kwargs)

        success = sum(1 for r in results.values() if r.get('success'))
        failed = sum(1 for r in results.values() if not r.get('success'))

        return {
            'total': len(varieties),
            'success': success,
            'failed': failed,
            'duration_ms': round((time.time() - start) * 1000, 1),
        }

    # ==================== 统计 ====================

    def get_perf_stats(self) -> Dict:
        """获取性能统计"""
        with self._stats_lock:
            s = dict(self._stats)
            if s['cache_hits'] > 0 and s['total_requests'] > 0:
                s['cache_hit_rate'] = round(s['cache_hits'] / s['total_requests'] * 100, 2)
            else:
                s['cache_hit_rate'] = 0
            if s['parallel_batches'] > 0:
                s['avg_parallel_ms'] = round(s['total_time_parallel_ms'] / s['parallel_batches'], 1)
                s['avg_serial_estimate_ms'] = round(s['total_time_serial_ms'] / s['parallel_batches'], 1)
                if s['avg_serial_estimate_ms'] > 0:
                    s['speedup_ratio'] = round(s['avg_serial_estimate_ms'] / max(s['avg_parallel_ms'], 1), 2)
                else:
                    s['speedup_ratio'] = 1.0
            else:
                s['avg_parallel_ms'] = 0
                s['avg_serial_estimate_ms'] = 0
                s['speedup_ratio'] = 1.0
            return s

    def reset_stats(self):
        """重置性能统计"""
        with self._stats_lock:
            self._stats = {
                'total_requests': 0, 'cache_hits': 0,
                'parallel_batches': 0,
                'total_time_serial_ms': 0, 'total_time_parallel_ms': 0,
            }

    # ==================== 持久化 ====================

    def save_stats(self):
        """保存统计到磁盘"""
        try:
            stats = self.get_perf_stats()
            fpath = os.path.join(self.data_dir, f'perf_{date.today().isoformat()}.json')
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ============================================================
# 单例
# ============================================================

_batch_optimizer_instance: Optional[BatchOptimizer] = None


def get_batch_optimizer() -> BatchOptimizer:
    global _batch_optimizer_instance
    if _batch_optimizer_instance is None:
        _batch_optimizer_instance = BatchOptimizer()
    return _batch_optimizer_instance


def bo() -> BatchOptimizer:
    return get_batch_optimizer()
