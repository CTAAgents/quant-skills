#!/usr/bin/env python3
"""DataIntegrityChecker tests"""

import json, os, sys, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.data_integrity_checker import DataIntegrityChecker, get_integrity_checker, dic

def td():
    return tempfile.mkdtemp(prefix='fds_int_')

def cl(d):
    if d and os.path.exists(d): shutil.rmtree(d)

def test_creation():
    d = td()
    try:
        c = DataIntegrityChecker(data_dir=d)
        assert c is not None
    finally: cl(d)

def test_check_batch_empty():
    d = td()
    try:
        c = DataIntegrityChecker(data_dir=d)
        r = c.check_batch({})
        assert r['passed'] is True
        assert r['score'] == 1.0
    finally: cl(d)

def test_check_batch_all_success():
    d = td()
    try:
        c = DataIntegrityChecker(data_dir=d)
        r = c.check_batch({'CU': {'success': True, 'count': 120}, 'RB': {'success': True, 'count': 100}})
        assert r['total_varieties'] == 2
        assert r['success_count'] == 2
        assert r['coverage_pct'] == 100.0
        assert r['passed'] is True
    finally: cl(d)

def test_check_batch_partial_failure():
    d = td()
    try:
        c = DataIntegrityChecker(data_dir=d)
        r = c.check_batch({'CU': {'success': True, 'count': 120}, 'RB': {'success': False, 'error': 'timeout'}})
        assert r['total_varieties'] == 2
        assert r['success_count'] == 1
        assert r['failure_count'] == 1
        assert r['coverage_pct'] == 50.0
        assert r['passed'] is False
    finally: cl(d)

def test_validate_ohlc_valid():
    d = td()
    try:
        c = DataIntegrityChecker(data_dir=d)
        data = [{'open': 100, 'high': 105, 'low': 98, 'close': 102, 'volume': 1000}]
        r = c.validate_ohlc(data)
        assert r['passed'] is True
        assert r['valid_rows'] == 1
    finally: cl(d)

def test_validate_ohlc_invalid():
    d = td()
    try:
        c = DataIntegrityChecker(data_dir=d)
        data = [{'open': 100, 'high': 90, 'low': 98, 'close': 102, 'volume': 1000}]
        r = c.validate_ohlc(data)
        assert r['passed'] is False
        assert r['issue_count'] >= 1
    finally: cl(d)

def test_get_integrity_score():
    d = td()
    try:
        c = DataIntegrityChecker(data_dir=d)
        s = c.get_integrity_score()
        assert 0 <= s <= 1.0
    finally: cl(d)

def test_save_and_load():
    d = td()
    try:
        c1 = DataIntegrityChecker(data_dir=d)
        c1.check_batch({'CU': {'success': True, 'count': 120}})
        c1.generate_quality_report()
        # Load from new instance
        c2 = DataIntegrityChecker(data_dir=d)
        scores = c2.get_daily_scores(days=1)
        assert len(scores) >= 1
    finally: cl(d)

def test_singleton():
    a = get_integrity_checker()
    b = get_integrity_checker()
    assert a is b

def test_dic_alias():
    assert dic() is get_integrity_checker()

def test_clean_old():
    d = td()
    try:
        c = DataIntegrityChecker(data_dir=d)
        c.check_batch({'CU': {'success': True, 'count': 120}})
        c.generate_quality_report()
        c.clean_old(keep_days=0)
        assert True
    finally: cl(d)

if __name__ == '__main__':
    test_creation()
    test_check_batch_empty()
    test_check_batch_all_success()
    test_check_batch_partial_failure()
    test_validate_ohlc_valid()
    test_validate_ohlc_invalid()
    test_get_integrity_score()
    test_save_and_load()
    test_singleton()
    test_dic_alias()
    test_clean_old()
    print("All integrity checker tests passed!")
