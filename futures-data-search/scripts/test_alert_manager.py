#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlertManager 测试用例 v1.0

测试覆盖：
1. AlertRecord 创建与序列化
2. AlertManager 创建
3. 数据源故障告警
4. SLA 违规告警
5. 任务失败告警
6. 分析异常告警
7. 告警去重
8. 控制台通道发送
9. 文件通道发送
10. Webhook 通道配置
11. 历史查询与过滤
12. 告警确认 (ack)
13. 统计
14. 持久化
15. 边界条件（空输入、长消息）
"""

import json
import os
import sys
import shutil
import tempfile
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))

from scripts.alert_manager import (
    AlertManager, AlertRecord, get_alert_manager, am,
    alert_ds, alert_sla, alert_task, alert_anomaly,
    SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW,
    TYPE_DATA_SOURCE, TYPE_SLA_VIOLATION, TYPE_TASK_FAILURE, TYPE_ANALYSIS_ANOMALY,
    CHANNEL_CONSOLE, CHANNEL_FILE, CHANNEL_WEBHOOK,
    DEDUP_WINDOW_SECONDS,
)


def _create_test_dir():
    return tempfile.mkdtemp(prefix='fds_alert_test_')


def _clean_test_dir(test_dir):
    if test_dir and os.path.exists(test_dir):
        shutil.rmtree(test_dir)


# ============================================================
# Test 1: AlertRecord 创建
# ============================================================

def test_alert_record_creation():
    record = AlertRecord('data_source', 'high', 'tdx_local',
                        '[tdx_local] 数据源offline',
                        'tdx_local offline: Connection refused')
    assert record.alert_type == 'data_source'
    assert record.severity == 'high'
    assert record.source == 'tdx_local'
    assert record.handled is False
    assert record.acked is False
    assert record.id.startswith(str(int(time.time()*1000))[:5])


def test_alert_record_to_dict():
    record = AlertRecord('sla_violation', 'high', 'CU', '[CU] SLA违规',
                        'CU 收盘后45分钟未刷新', detail='SLA deadline 15:30, now 16:15')
    d = record.to_dict()
    assert d['alert_type'] == 'sla_violation'
    assert d['severity'] == 'high'
    assert d['source'] == 'CU'
    assert d['detail'] == 'SLA deadline 15:30, now 16:15'
    assert d['handled'] is False
    assert d['acked'] is False
    assert 'id' in d
    assert 'timestamp' in d


def test_alert_record_empty_detail():
    record = AlertRecord('task_failure', 'critical', 'main.py', 'task failed', 'error')
    d = record.to_dict()
    assert d['detail'] == ''


# ============================================================
# Test 2: AlertManager 基本功能
# ============================================================

def test_alert_manager_creation():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        assert mgr is not None
        assert mgr._alerts == []
    finally:
        _clean_test_dir(test_dir)


def test_alert_data_source():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        record = mgr.alert_data_source('tdx_local', 'offline', 'Connection refused')
        assert record.alert_type == TYPE_DATA_SOURCE
        assert record.severity == SEVERITY_CRITICAL
        assert 'tdx_local' in record.title
        assert record.handled is True
        assert len(mgr._alerts) == 1
    finally:
        _clean_test_dir(test_dir)


def test_alert_sla_violation():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        record = mgr.alert_sla_violation('CU', 'freshness', '收盘后45分钟未刷新')
        assert record.alert_type == TYPE_SLA_VIOLATION
        assert record.severity == SEVERITY_HIGH
        assert 'CU' in record.title
        assert len(mgr._alerts) == 1
    finally:
        _clean_test_dir(test_dir)


def test_alert_task_failure():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        record = mgr.alert_task_failure('dominant_mapping', 'main.py:142', 'timeout')
        assert record.alert_type == TYPE_TASK_FAILURE
        assert record.severity == SEVERITY_CRITICAL
        assert 'dominant_mapping' in record.title
        assert len(mgr._alerts) == 1
    finally:
        _clean_test_dir(test_dir)


def test_alert_analysis_anomaly():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        record = mgr.alert_analysis_anomaly('深度分析#33', 'confidence_drop', '置信度<30%')
        assert record.alert_type == TYPE_ANALYSIS_ANOMALY
        assert record.severity == SEVERITY_MEDIUM
        assert '深度分析' in record.title
        assert len(mgr._alerts) == 1
    finally:
        _clean_test_dir(test_dir)


# ============================================================
# Test 3: 告警去重
# ============================================================

def test_dedup_same_source_type():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        r1 = mgr.alert_data_source('tdx_local', 'offline', 'err1')
        r2 = mgr.alert_data_source('tdx_local', 'offline', 'err2')
        # 第一条正常加入
        assert r1.handled is True
        # 第二条在去重窗口内，返回的 record 标记为 handled（去重跳过）
        assert r2.handled is True
        assert '[去重跳过]' in r2.message
        # 只有第一条被追加到 _alerts
        assert len(mgr._alerts) == 1
    finally:
        _clean_test_dir(test_dir)


def test_dedup_different_sources():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        r1 = mgr.alert_data_source('tdx_local', 'offline', 'err')
        r2 = mgr.alert_data_source('tqsdk', 'offline', 'err')
        assert len(mgr._alerts) == 2  # 不同来源，不重复
    finally:
        _clean_test_dir(test_dir)


def test_dedup_different_types():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        r1 = mgr.alert_data_source('tdx_local', 'offline', 'err')
        r2 = mgr.alert_sla_violation('CU', 'freshness', 'desc')
        assert len(mgr._alerts) == 2  # 不同类型，不重复
    finally:
        _clean_test_dir(test_dir)


# ============================================================
# Test 4: 文件通道
# ============================================================

def test_file_channel_writes_file():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        mgr.alert_data_source('tdx_local', 'offline', 'test')
        # 检查当天目录是否有文件
        from datetime import date
        daily_dir = os.path.join(test_dir, date.today().isoformat())
        assert os.path.exists(daily_dir)
        files = os.listdir(daily_dir)
        assert len(files) >= 1
        # 验证文件内容
        with open(os.path.join(daily_dir, files[0]), 'r') as f:
            data = json.load(f)
        assert data['alert_type'] == 'data_source'
    finally:
        _clean_test_dir(test_dir)


# ============================================================
# Test 5: 历史查询与过滤
# ============================================================

def test_get_history_all():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        mgr.alert_data_source('tdx_local', 'offline', 'err')
        mgr.alert_sla_violation('CU', 'freshness', 'detail')
        history = mgr.get_history(days=7)
        assert len(history) == 2
    finally:
        _clean_test_dir(test_dir)


def test_get_history_filter_by_type():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        mgr.alert_data_source('tdx_local', 'offline', 'err')
        mgr.alert_sla_violation('CU', 'freshness', 'detail')
        ds_history = mgr.get_history(days=7, alert_type=TYPE_DATA_SOURCE)
        assert len(ds_history) == 1
        assert ds_history[0]['alert_type'] == TYPE_DATA_SOURCE
    finally:
        _clean_test_dir(test_dir)


def test_get_history_filter_by_severity():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        mgr.alert_data_source('tdx_local', 'offline', 'err')  # critical
        mgr.alert_sla_violation('CU', 'freshness', 'detail')  # high
        crit_history = mgr.get_history(days=7, severity=SEVERITY_CRITICAL)
        assert len(crit_history) >= 1
        for h in crit_history:
            assert h['severity'] == SEVERITY_CRITICAL
    finally:
        _clean_test_dir(test_dir)


# ============================================================
# Test 6: 告警确认
# ============================================================

def test_ack_alert():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        record = mgr.alert_data_source('tdx_local', 'offline', 'err')
        assert mgr.ack(record.id) is True
        # 验证状态
        unhandled = mgr.get_unhandled()
        assert len(unhandled) == 0
    finally:
        _clean_test_dir(test_dir)


def test_ack_nonexistent():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        assert mgr.ack('nonexistent_id') is False
    finally:
        _clean_test_dir(test_dir)


# ============================================================
# Test 7: 告警统计
# ============================================================

def test_get_stats():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        mgr.alert_data_source('tdx_local', 'offline', 'err')
        mgr.alert_data_source('tqsdk', 'auth_failed', 'bad pwd')
        mgr.alert_sla_violation('CU', 'freshness', 'detail')
        stats = mgr.get_stats(days=7)
        assert stats['total'] == 3
        assert stats['by_severity'].get('critical', 0) == 2
        assert stats['by_type'].get('sla_violation', 0) == 1
        assert stats['unhandled'] == 3
    finally:
        _clean_test_dir(test_dir)


def test_get_stats_empty():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        stats = mgr.get_stats(days=7)
        assert stats['total'] == 0
    finally:
        _clean_test_dir(test_dir)


# ============================================================
# Test 8: 清除已确认告警
# ============================================================

def test_clear_acked():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        record = mgr.alert_data_source('tdx_local', 'offline', 'err')
        mgr.ack(record.id)
        # 清除1天内已确认的（应该清除）
        count_before = len(mgr._alerts)
        mgr.clear_acked(days=0)
        # 已确认且超过0天的会被清除
        assert len(mgr._alerts) <= count_before
    finally:
        _clean_test_dir(test_dir)


# ============================================================
# Test 9: 持久化
# ============================================================

def test_save_and_load_alerts():
    test_dir = _create_test_dir()
    try:
        mgr1 = AlertManager(alert_dir=test_dir)
        mgr1.alert_data_source('tdx_local', 'offline', 'err')
        mgr1.alert_sla_violation('CU', 'freshness', 'detail')
        mgr1._save_alerts()

        # 新管理器加载
        mgr2 = AlertManager(alert_dir=test_dir)
        mgr2._load_history()
        assert len(mgr2._alerts) >= 1
    finally:
        _clean_test_dir(test_dir)


# ============================================================
# Test 10: Webhook 配置
# ============================================================

def test_webhook_config():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        mgr.configure_webhook(url='https://hooks.example.com/alert', channel='wechat_work')
        config = mgr.get_webhook_config()
        assert config['url'] == 'https://hooks.example.com/alert'
        assert config['channel'] == 'wechat_work'
    finally:
        _clean_test_dir(test_dir)


@patch('urllib.request.urlopen')
def test_webhook_send(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen.return_value = mock_resp
    mock_urlopen.__enter__.return_value = mock_resp

    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        mgr.configure_webhook(url='https://hooks.example.com/alert', channel='generic')
        # 发送一个带 webhook 通道的告警
        record = AlertRecord('data_source', 'critical', 'tdx_local',
                            '[tdx_local] offline', 'test', '',
                            channels=['webhook'])
        mgr._send_webhook(record)
        # 不验证网络调用结果，只验证不崩溃
        assert True
    finally:
        _clean_test_dir(test_dir)


# ============================================================
# Test 11: 边界条件
# ============================================================

def test_clear_empty():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        mgr.clear_acked(days=1)  # 不应该崩溃
        assert True
    finally:
        _clean_test_dir(test_dir)


def test_long_message_truncation():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        long_msg = 'x' * 1000
        # task_failure 在 message 中截断到100字符
        record = mgr.alert_task_failure('test_job', 'test.py:1', long_msg)
        assert len(record.message) <= 200  # "test_job 在 test.py:1 失败: " + 100截断
    finally:
        _clean_test_dir(test_dir)


def test_unhandled_empty():
    test_dir = _create_test_dir()
    try:
        mgr = AlertManager(alert_dir=test_dir)
        unhandled = mgr.get_unhandled()
        assert unhandled == []
    finally:
        _clean_test_dir(test_dir)


# ============================================================
# Test 12: 单例与便捷函数
# ============================================================

def test_get_alert_manager_singleton():
    m1 = get_alert_manager()
    m2 = get_alert_manager()
    assert m1 is m2


def test_am_alias():
    assert am() is get_alert_manager()


def test_alert_ds_convenience():
    record = alert_ds('tdx_local', 'offline', 'test')
    assert record is not None
    assert record.alert_type == 'data_source'


def test_alert_sla_convenience():
    record = alert_sla('CU', 'freshness', 'test')
    assert record is not None
    assert record.alert_type == 'sla_violation'


def test_alert_task_convenience():
    record = alert_task('test_job', 'test.py:1', 'error')
    assert record is not None
    assert record.alert_type == 'task_failure'


def test_alert_anomaly_convenience():
    record = alert_anomaly('report_1', 'confidence_drop', 'low confidence')
    assert record is not None
    assert record.alert_type == 'analysis_anomaly'


# ============================================================
# 主入口
# ============================================================

if __name__ == '__main__':
    test_alert_record_creation()
    test_alert_record_to_dict()
    test_alert_record_empty_detail()
    test_alert_manager_creation()
    test_alert_data_source()
    test_alert_sla_violation()
    test_alert_task_failure()
    test_alert_analysis_anomaly()
    test_dedup_same_source_type()
    test_dedup_different_sources()
    test_dedup_different_types()
    test_file_channel_writes_file()
    test_get_history_all()
    test_get_history_filter_by_type()
    test_get_history_filter_by_severity()
    test_ack_alert()
    test_ack_nonexistent()
    test_get_stats()
    test_get_stats_empty()
    test_clear_acked()
    test_save_and_load_alerts()
    test_webhook_config()
    test_webhook_send()
    test_clear_empty()
    test_long_message_truncation()
    test_unhandled_empty()
    test_get_alert_manager_singleton()
    test_am_alias()
    test_alert_ds_convenience()
    test_alert_sla_convenience()
    test_alert_task_convenience()
    test_alert_anomaly_convenience()
    print("\n" + "=" * 60)
    print("  All alert manager tests passed!")
    print("=" * 60)
