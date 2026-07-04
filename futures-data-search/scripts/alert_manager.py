#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
futures-data-search 告警推送系统 v1.0

多通道告警推送，覆盖以下场景：
1. 数据源故障（TDX离线/TqSDK凭据失效/东方财富不可达）
2. SLA 违规（品种在截止时间后仍未采集）
3. 自动化任务失败
4. 辩论结果异常（置信度过低）

告警通道（可并行）：
- CHANNEL_CONSOLE: 终端输出
- CHANNEL_FILE: JSON事件文件
- CHANNEL_WEBHOOK: HTTP Webhook（通用）

用法：
    from alert_manager import AlertManager, get_alert_manager
    
    am = get_alert_manager()
    
    # 发送数据源故障告警
    am.alert_data_source('tdx_local', 'offline', 'HTTP 127.0.0.1:17709 不可达')
    
    # 发送SLA违规告警
    am.alert_sla_violation('CU', 'freshness', '收盘后45分钟未刷新')
    
    # 发送任务失败告警
    am.alert_task_failure('dominant_mapping', 'main.py:142', '交易所API超时')
    
    # 发送分析异常告警
    am.alert_analysis_anomaly('深度分析 #33', 'confidence_drop', '综合置信度<30%')
    
    # 配置Webhook
    am.configure_webhook(url='https://hooks.example.com/alert', channel='wechat')
    
    # 查看告警历史
    history = am.get_history(days=7)
    
    # 未处理告警
    unhandled = am.get_unhandled()

CLI:
    python alert_manager.py history [days]   # 查看告警历史
    python alert_manager.py unhandled         # 未处理告警
    python alert_manager.py ack <alert_id>    # 确认告警
    python alert_manager.py clear             # 清理已处理告警
"""

import json
import os
import time
import urllib.request
import urllib.error
import threading
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


# ============================================================
# 常量
# ============================================================

ALERT_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "WorkBuddy", ".workbuddy", "feedback", "alerts"
)

# 告警严重级别
SEVERITY_CRITICAL = 'critical'
SEVERITY_HIGH = 'high'
SEVERITY_MEDIUM = 'medium'
SEVERITY_LOW = 'low'

# 告警类型
TYPE_DATA_SOURCE = 'data_source'
TYPE_SLA_VIOLATION = 'sla_violation'
TYPE_TASK_FAILURE = 'task_failure'
TYPE_ANALYSIS_ANOMALY = 'analysis_anomaly'

# 通道
CHANNEL_CONSOLE = 'console'
CHANNEL_FILE = 'file'
CHANNEL_WEBHOOK = 'webhook'

# 默认启用通道
DEFAULT_CHANNELS = [CHANNEL_CONSOLE, CHANNEL_FILE]

# 告警去重窗口（同一来源+同一类型 5 分钟内不重复推送）
DEDUP_WINDOW_SECONDS = 300

# 最大历史保留
MAX_HISTORY = 1000


class AlertRecord:
    """单条告警记录"""

    def __init__(
        self,
        alert_type: str,
        severity: str,
        source: str,
        title: str,
        message: str,
        detail: str = '',
        channels: List[str] = None,
    ):
        self.id = f"{int(time.time()*1000)}_{source}_{alert_type}"
        self.timestamp = datetime.now()
        self.alert_type = alert_type
        self.severity = severity
        self.source = source
        self.title = title
        self.message = message
        self.detail = detail
        self.channels = channels or DEFAULT_CHANNELS[:]
        self.handled = False
        self.acked = False
        self.ack_time = None
        self.alert_key = f"{source}:{alert_type}"  # 去重键

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'alert_type': self.alert_type,
            'severity': self.severity,
            'source': self.source,
            'title': self.title,
            'message': self.message,
            'detail': self.detail,
            'channels': self.channels,
            'handled': self.handled,
            'acked': self.acked,
            'ack_time': self.ack_time.isoformat() if self.ack_time else None,
        }


class AlertManager:
    """多通道告警管理器"""

    def __init__(self, alert_dir: str = None):
        self.alert_dir = alert_dir or ALERT_DIR
        os.makedirs(self.alert_dir, exist_ok=True)

        # 内存中的告警历史
        self._alerts: List[AlertRecord] = []
        self._lock = threading.RLock()

        # 去重缓存 {alert_key: last_send_time}
        self._dedup_cache: Dict[str, float] = {}

        # Webhook 配置
        self._webhook_url: Optional[str] = None
        self._webhook_channel: str = 'generic'
        self._webhook_headers: Dict[str, str] = {}

        # 加载历史
        self._load_history()

    # ==================== Webhook 配置 ====================

    def configure_webhook(self, url: str, channel: str = 'generic',
                          headers: Dict[str, str] = None):
        """配置 Webhook 推送

        Args:
            url: Webhook URL (如企业微信/钉钉/Slack Webhook)
            channel: 渠道标识 ('wechat_work', 'dingtalk', 'slack', 'custom')
            headers: 自定义HTTP头
        """
        self._webhook_url = url
        self._webhook_channel = channel
        if headers:
            self._webhook_headers.update(headers)

    def get_webhook_config(self) -> Dict:
        """获取当前 Webhook 配置"""
        return {
            'url': self._webhook_url,
            'channel': self._webhook_channel,
            'headers': dict(self._webhook_headers),
        }

    # ==================== 核心告警方法 ====================

    def alert_data_source(self, source: str, status: str, error: str = '') -> AlertRecord:
        """数据源故障告警

        Args:
            source: 数据源名称 (tdx_local/tqsdk/eastmoney)
            status: 状态 (offline/unreachable/auth_failed)
            error: 错误信息
        """
        severity_map = {
            'offline': SEVERITY_CRITICAL,
            'unreachable': SEVERITY_HIGH,
            'auth_failed': SEVERITY_CRITICAL,
        }
        severity = severity_map.get(status, SEVERITY_HIGH)
        title = f"[{source}] 数据源{status}"
        message = f"{source} {status}: {error}" if error else f"{source} {status}"
        return self._alert(TYPE_DATA_SOURCE, severity, source, title, message, error)

    def alert_sla_violation(self, variety: str, violation_type: str,
                            detail: str = '') -> AlertRecord:
        """SLA 违规告警

        Args:
            variety: 品种代码
            violation_type: 违规类型 (freshness/coverage/accuracy)
            detail: 详细描述
        """
        title = f"[{variety}] SLA 违规 - {violation_type}"
        message = f"{variety} {violation_type} 不达标"
        return self._alert(TYPE_SLA_VIOLATION, SEVERITY_HIGH, variety, title, message, detail)

    def alert_task_failure(self, task_name: str, location: str,
                           error: str = '') -> AlertRecord:
        """自动化任务失败告警

        Args:
            task_name: 任务名称
            location: 失败位置 (文件:行号)
            error: 错误信息
        """
        title = f"[{task_name}] 任务执行失败"
        message = f"{task_name} 在 {location} 失败: {error[:100]}"
        return self._alert(TYPE_TASK_FAILURE, SEVERITY_CRITICAL, task_name,
                          title, message, f"location={location}, error={error}")

    def alert_analysis_anomaly(self, report_name: str, anomaly_type: str,
                               detail: str = '') -> AlertRecord:
        """分析结果异常告警

        Args:
            report_name: 报告名称
            anomaly_type: 异常类型 (confidence_drop/signal_divergence/data_gap)
            detail: 详细描述
        """
        title = f"[{report_name}] 分析异常 - {anomaly_type}"
        message = f"{report_name} 检测到 {anomaly_type}"
        return self._alert(TYPE_ANALYSIS_ANOMALY, SEVERITY_MEDIUM, report_name,
                          title, message, detail)

    def _alert(self, alert_type: str, severity: str, source: str,
               title: str, message: str, detail: str = '') -> AlertRecord:
        """内部告警方法（带去重和通道分发）"""
        with self._lock:
            # 去重检查：同一来源+同类型 5 分钟内不重复
            dedup_key = f"{source}:{alert_type}"
            last_time = self._dedup_cache.get(dedup_key, 0)
            now = time.time()
            if now - last_time < DEDUP_WINDOW_SECONDS:
                # 重复告警：创建一个 suppressed 标记的记录
                record = AlertRecord(alert_type, severity, source, title,
                                    f"[去重跳过] {message}", detail)
                record.handled = True  # 标记为已处理（未实际发送）
                return record

            # 创建告警记录
            record = AlertRecord(alert_type, severity, source, title, message, detail)

            # 更新去重缓存
            self._dedup_cache[dedup_key] = now
            if len(self._dedup_cache) > 500:
                self._dedup_cache.clear()

            # 通过各通道发送
            for channel in record.channels:
                try:
                    if channel == CHANNEL_CONSOLE:
                        self._send_console(record)
                    elif channel == CHANNEL_FILE:
                        self._send_file(record)
                    elif channel == CHANNEL_WEBHOOK:
                        self._send_webhook(record)
                except Exception as e:
                    print(f"[AlertManager] 通道 {channel} 发送失败: {e}")

            # 保存到历史和磁盘
            record.handled = True
            self._alerts.append(record)
            if len(self._alerts) > MAX_HISTORY:
                self._alerts = self._alerts[-MAX_HISTORY:]
            self._save_alerts()

            return record

    # ==================== 通道实现 ====================

    def _send_console(self, record: AlertRecord):
        """控制台输出告警"""
        symbol = {'critical': '!!', 'high': '!', 'medium': '-', 'low': '?'}.get(record.severity, '?')
        time_str = record.timestamp.strftime('%H:%M:%S')
        print(f"[{symbol} ALERT {time_str}] [{record.severity.upper():8s}] "
              f"{record.title}")
        print(f"   {record.message}")
        if record.detail:
            print(f"   detail: {record.detail}")

    def _send_file(self, record: AlertRecord):
        """写入 JSON 事件文件"""
        daily_dir = os.path.join(self.alert_dir, date.today().isoformat())
        os.makedirs(daily_dir, exist_ok=True)
        fpath = os.path.join(daily_dir, f"{record.id}.json")
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)

    def _send_webhook(self, record: AlertRecord):
        """通过 HTTP Webhook 发送告警"""
        if not self._webhook_url:
            return

        # 根据通道类型格式化消息
        if self._webhook_channel == 'wechat_work':
            payload = json.dumps({
                'msgtype': 'markdown',
                'markdown': {
                    'content': (
                        f"## {record.title}\n"
                        f"> **严重级别**: {record.severity}\n"
                        f"> **来源**: {record.source}\n"
                        f"> **时间**: {record.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"> **详情**: {record.message}\n"
                        f"{'  \n> '+record.detail[:200] if record.detail else ''}"
                    ),
                },
            }).encode('utf-8')
        elif self._webhook_channel == 'dingtalk':
            payload = json.dumps({
                'msgtype': 'text',
                'text': {
                    'content': (
                        f"[{record.severity.upper()}] {record.title}\n"
                        f"{record.message}\n"
                        f"来源: {record.source} | {record.timestamp.strftime('%H:%M:%S')}"
                    ),
                },
            }).encode('utf-8')
        else:
            payload = json.dumps(record.to_dict()).encode('utf-8')

        try:
            headers = {'Content-Type': 'application/json'}
            headers.update(self._webhook_headers)
            req = urllib.request.Request(
                self._webhook_url, data=payload, headers=headers, method='POST'
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"[AlertManager] Webhook send failed: {e}")

    # ==================== 历史查询 ====================

    def get_history(self, days: int = 7, alert_type: str = None,
                    severity: str = None, unhandled_only: bool = False) -> List[Dict]:
        """查询告警历史"""
        cutoff = time.time() - days * 86400
        with self._lock:
            results = []
            for a in self._alerts:
                if a.timestamp.timestamp() < cutoff:
                    continue
                if alert_type and a.alert_type != alert_type:
                    continue
                if severity and a.severity != severity:
                    continue
                if unhandled_only and a.acked:
                    continue
                results.append(a.to_dict())
            return results

    def get_unhandled(self) -> List[Dict]:
        """获取未确认告警"""
        return self.get_history(days=7, unhandled_only=True)

    def ack(self, alert_id: str) -> bool:
        """确认（ack）告警"""
        with self._lock:
            for a in self._alerts:
                if a.id == alert_id:
                    a.acked = True
                    a.ack_time = datetime.now()
                    self._save_alerts()
                    return True
            return False

    def clear_acked(self, days: int = 30):
        """清理已确认的告警（超过 days 天的删除）"""
        cutoff = time.time() - days * 86400
        with self._lock:
            self._alerts = [
                a for a in self._alerts
                if not (a.acked and a.timestamp.timestamp() < cutoff)
            ]
            self._save_alerts()

    def get_stats(self, days: int = 7) -> Dict:
        """告警统计"""
        history = self.get_history(days=days)
        stats = {
            'total': len(history),
            'by_severity': {},
            'by_type': {},
            'by_source': {},
            'unhandled': 0,
        }
        for a in history:
            sev = a.get('severity', 'unknown')
            stats['by_severity'][sev] = stats['by_severity'].get(sev, 0) + 1
            tp = a.get('alert_type', 'unknown')
            stats['by_type'][tp] = stats['by_type'].get(tp, 0) + 1
            src = a.get('source', 'unknown')
            stats['by_source'][src] = stats['by_source'].get(src, 0) + 1
            if not a.get('acked', False):
                stats['unhandled'] += 1
        return stats

    # ==================== 持久化 ====================

    def _save_alerts(self):
        """保存告警到磁盘"""
        try:
            fpath = os.path.join(self.alert_dir, 'alert_history.json')
            data = [a.to_dict() for a in self._alerts[-500:]]  # 只存最近500条
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_history(self):
        """从磁盘加载告警历史"""
        try:
            fpath = os.path.join(self.alert_dir, 'alert_history.json')
            if os.path.exists(fpath):
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for d in data[-MAX_HISTORY:]:
                    record = AlertRecord(
                        d.get('alert_type', 'unknown'),
                        d.get('severity', 'low'),
                        d.get('source', ''),
                        d.get('title', ''),
                        d.get('message', ''),
                        d.get('detail', ''),
                        d.get('channels', DEFAULT_CHANNELS[:]),
                    )
                    record.id = d.get('id', record.id)
                    record.timestamp = datetime.fromisoformat(d.get('timestamp', datetime.now().isoformat()))
                    record.handled = d.get('handled', True)
                    record.acked = d.get('acked', False)
                    if d.get('ack_time'):
                        record.ack_time = datetime.fromisoformat(d['ack_time'])
                    self._alerts.append(record)
        except Exception:
            pass


# ============================================================
# 单例 + 便捷入口
# ============================================================

_alert_manager_instance: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    global _alert_manager_instance
    if _alert_manager_instance is None:
        _alert_manager_instance = AlertManager()
    return _alert_manager_instance


def am() -> AlertManager:
    return get_alert_manager()


# 便捷函数
def alert_ds(source: str, status: str, error: str = ''):
    return get_alert_manager().alert_data_source(source, status, error)

def alert_sla(variety: str, vtype: str, detail: str = ''):
    return get_alert_manager().alert_sla_violation(variety, vtype, detail)

def alert_task(task: str, location: str, error: str = ''):
    return get_alert_manager().alert_task_failure(task, location, error)

def alert_anomaly(report: str, atype: str, detail: str = ''):
    return get_alert_manager().alert_analysis_anomaly(report, atype, detail)


# ============================================================
# CLI 入口
# ============================================================

def main():
    import sys
    mgr = get_alert_manager()

    if len(sys.argv) < 2:
        stats = mgr.get_stats()
        unhandled = len(mgr.get_unhandled())
        print(f"Total alerts (7d): {stats['total']} | Unhandled: {unhandled}")
        print(f"By severity: {stats['by_severity']}")
        print(f"By type: {stats['by_type']}")
        print("Usage: python alert_manager.py [history|unhandled|ack|clear|stats]")
        return

    cmd = sys.argv[1]
    if cmd == 'history':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        history = mgr.get_history(days=days)
        print(f"Alert history ({days}d): {len(history)} entries")
        for a in history[-20:]:  # 只显示最近20条
            ack = '✓' if a.get('acked') else '○'
            sev = a.get('severity', '?').upper()[:4]
            print(f"  [{ack}] [{sev}] {a.get('title','')} @ {a.get('timestamp','')[:19]}")

    elif cmd == 'unhandled':
        unhandled = mgr.get_unhandled()
        if not unhandled:
            print("No unhandled alerts.")
        else:
            print(f"Unhandled alerts: {len(unhandled)}")
            for a in unhandled:
                print(f"  {a['id'][:20]}... [{a['severity']}] {a['title']}")

    elif cmd == 'ack':
        if len(sys.argv) < 3:
            print("Usage: python alert_manager.py ack <alert_id>")
            return
        ok = mgr.ack(sys.argv[2])
        print("Alert acknowledged." if ok else "Alert not found.")

    elif cmd == 'clear':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        mgr.clear_acked(days)
        print(f"Cleared acknowledged alerts older than {days} days.")

    elif cmd == 'stats':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        stats = mgr.get_stats(days)
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown: {cmd}")


if __name__ == '__main__':
    main()
