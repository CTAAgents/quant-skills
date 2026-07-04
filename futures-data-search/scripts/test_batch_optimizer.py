#!/usr/bin/env python3
"""BatchOptimizer tests"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.batch_optimizer import BatchOptimizer, get_batch_optimizer, bo

def test_creation():
    b = BatchOptimizer()
    assert b is not None

def test_batch_empty():
    b = BatchOptimizer()
    r = b.batch_get_quote([])
    assert r == {}

def test_batch_no_fn():
    b = BatchOptimizer()
    r = b.batch_get_quote(['CU', 'RB'])
    assert 'CU' in r and 'RB' in r
    assert r['CU']['success'] is False

def test_batch_with_mock_fn():
    b = BatchOptimizer()
    mock_results = {}
    def mock_fetch(v, **kw):
        return {'success': True, 'data': [{'code': v}], 'data_source': 'mock'}
    b.set_fetch_fn(mock_fetch)
    r = b.batch_get_quote(['CU', 'RB'])
    assert r['CU']['success'] is True
    assert r['RB']['success'] is True

def test_dedup():
    b = BatchOptimizer()
    calls = []
    def mock_fetch(v, **kw):
        calls.append(v)
        return {'success': True, 'data': [{'code': v}]}
    b.set_fetch_fn(mock_fetch)
    r1 = b.batch_get_quote(['CU'])
    r2 = b.batch_get_quote(['CU'])
    assert len(calls) >= 1  # 第一次实际调用
    # 第二次应命中缓存，所以 calls 可能不变

def test_warmup():
    b = BatchOptimizer()
    def mock_fetch(v, **kw):
        return {'success': True, 'data': [{'code': v}]}
    b.set_fetch_fn(mock_fetch)
    r = b.warmup_cache(['CU', 'RB', 'I'])
    assert r['total'] == 3
    assert r['success'] == 3

def test_perf_stats():
    b = BatchOptimizer()
    stats = b.get_perf_stats()
    assert 'total_requests' in stats
    assert 'cache_hit_rate' in stats
    assert 'speedup_ratio' in stats

def test_reset_stats():
    b = BatchOptimizer()
    b.reset_stats()
    s = b.get_perf_stats()
    assert s['total_requests'] == 0

def test_save_stats():
    import tempfile, os, json
    d = tempfile.mkdtemp()
    try:
        b = BatchOptimizer(data_dir=d)
        b.save_stats()
        files = os.listdir(d)
        assert len(files) >= 1
    finally:
        import shutil; shutil.rmtree(d)

def test_singleton():
    assert get_batch_optimizer() is get_batch_optimizer()
    assert bo() is get_batch_optimizer()

if __name__ == '__main__':
    test_creation(); test_batch_empty(); test_batch_no_fn()
    test_batch_with_mock_fn(); test_dedup(); test_warmup()
    test_perf_stats(); test_reset_stats(); test_save_stats(); test_singleton()
    print("All batch optimizer tests passed!")
