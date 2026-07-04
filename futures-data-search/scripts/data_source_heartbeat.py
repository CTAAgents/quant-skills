#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
futures-data-search 数据源心跳保活与自动重连模块 v1.0

核心功能：
1. TDX TQ-Local 连通性心跳检测（每 60s 检查 HTTP 127.0.0.1:17709）
2. TqSDK 凭据有效性定期验证（每 5min 检查环境变量和导入）
3. 数据源状态自动恢复（可用→不可用→自动恢复→再次可用）
4. 延迟标记：刚启动时给数据源 30s 预热时间
5. 健康状态变更推送（供告警系统使用）
6. 守护线程模式（自动在后台运行心跳检查）

用法：
    from data_source_heartbeat import DataSourceHeartbeat, td

    # 启动后台心跳守护线程
    td.start()

    # 检查当前数据源状态
    status = td.check_all()
    print(status)  # {'tdx_local': True, 'tqsdk': True, ...}

    # 等待数据源就绪（超时）
    if td.wait_ready(timeout=60):
        print('所有数据源已就绪')
    else:
        print('部分数据源未就绪:', td.get_unready())

CLI:
    python data_source_heartbeat.py status     # 当前数据源状态
    python data_source_heartbeat.py wait       # 等待就绪
    python data_source_heartbeat.py check      # 强制立刻检查
"""

import json
import os
import time
import threading
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path


# ============================================================
# 配置常量
# ============================================================

TDX_HTTP_URL = "http://127.0.0.1:17709/"
TDX_TIMEOUT = 5        # TDX 心跳超时（秒）
TDX_HEARTBEAT_INTERVAL = 60  # TDX 心跳间隔（秒）
TDX_RETRY_INTERVAL = 30      # TDX 重试间隔（秒）

TQSDK_CHECK_INTERVAL = 300   # TqSDK 凭据检查间隔（5 分钟）
TQSDK_RETRY_INTERVAL = 60    # TqSDK 重试间隔

STARTUP_GRACE_SECONDS = 30   # 启动预热时间（秒）
MAX_HEARTBEAT_HISTORY = 100  # 保留的最新心跳记录数

HEARTBEAT_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "WorkBuddy", ".workbuddy", "feedback"
)


class HeartbeatRecord:
    """单次心跳记录"""

    def __init__(
        self,
        source: str,
        alive: bool,
        latency_ms: float = 0,
        error: str = '',
    ):
        self.timestamp = datetime.now()
        self.source = source
        self.alive = alive
        self.latency_ms = round(latency_ms, 1)
        self.error = error[:100]

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'alive': self.alive,
            'latency_ms': self.latency_ms,
            'error': self.error,
        }


class DataSourceHeartbeat:
    """数据源心跳保活监控器

    管理 TDX TQ-Local 和 TqSDK 的连通性心跳检测和自动重连。
    支持可注册的告警回调函数。
    """

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or HEARTBEAT_DIR
        os.makedirs(self.data_dir, exist_ok=True)

        # 数据源状态 {source_name: {'alive': bool, 'last_check': datetime, ...}}
        self._status: Dict[str, Dict[str, Any]] = {}
        for src in ['tdx_local', 'tqsdk', 'eastmoney', 'akshare', 'exchange_api']:
            self._status[src] = {
                'alive': False,          # 当前是否可用
                'last_check': None,      # 最后检查时间
                'last_alive': None,      # 最后可用时间
                'consecutive_failures': 0,
                'consecutive_successes': 0,
                'latency_ms': 0,
                'error': '',
                'startup_grace_done': False,
                'startup_time': datetime.now(),
            }

        # 心跳历史
        self._history: List[HeartbeatRecord] = []

        # 状态变更告警回调
        self._alarm_callbacks: List[Callable[[str, bool, str], None]] = []

        # 守护线程控制
        self._daemon_thread: Optional[threading.Thread] = None
        self._daemon_running = False
        self._daemon_stop = threading.Event()

        # 锁
        self._lock = threading.RLock()

    # ==================== 告警回调 ====================

    def on_state_change(self, callback: Callable[[str, bool, str], None]):
        """注册状态变更回调

        callback 签名: callback(source_name: str, alive: bool, error: str)
        当数据源从 alive→dead 或 dead→alive 时触发。
        """
        with self._lock:
            self._alarm_callbacks.append(callback)

    def _fire_state_change(self, source: str, alive: bool, error: str):
        """触发状态变更告警"""
        for cb in self._alarm_callbacks:
            try:
                cb(source, alive, error)
            except Exception:
                pass

    # ==================== 单次检测 ====================

    def check_tdx_local(self) -> bool:
        """检查通达信 TQ-Local HTTP 服务是否在线"""
        try:
            start = time.time()
            data = json.dumps({
                "id": 1, "method": "get_match_stkinfo",
                "params": {"key_word": "铜"}
            }).encode("utf-8")
            req = urllib.request.Request(
                TDX_HTTP_URL, data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=TDX_TIMEOUT)
            elapsed = (time.time() - start) * 1000
            result = json.loads(resp.read().decode("utf-8"))
            alive = result is not None and 'result' in result
            self._record_result('tdx_local', alive, elapsed, error='')
            return alive
        except (urllib.error.URLError, urllib.error.HTTPError,
                ConnectionError, TimeoutError, OSError, json.JSONDecodeError) as e:
            elapsed = (time.time() - start) * 1000 if 'start' in dir() else 0
            self._record_result('tdx_local', False, elapsed, error=str(e)[:100])
            return False

    def check_tqsdk(self) -> bool:
        """检查 TqSDK 凭据和导入是否正常"""
        try:
            start = time.time()
            # 1. 检查模块是否可导入
            import importlib.util
            if importlib.util.find_spec("tqsdk") is None:
                self._record_result('tqsdk', False, 0, error='tqsdk 模块未安装')
                return False

            # 2. 检查环境变量
            user = os.environ.get('TQSDK_USERNAME') or os.environ.get('TQ_USER', '')
            pwd = os.environ.get('TQSDK_PASSWORD') or os.environ.get('TQ_PASSWORD', '')
            if not user or not pwd:
                self._record_result('tqsdk', False, 0, error='TqSDK 凭据未配置（TQSDK_USERNAME/PASSWORD）')
                return False

            elapsed = (time.time() - start) * 1000
            self._record_result('tqsdk', True, elapsed, error='')
            return True
        except Exception as e:
            elapsed = (time.time() - start) * 1000 if 'start' in dir() else 0
            self._record_result('tqsdk', False, elapsed, error=str(e)[:100])
            return False

    def check_eastmoney(self) -> bool:
        """检查东方财富 API 是否可达"""
        try:
            start = time.time()
            # 轻量级连通性检查：尝试访问东方财富公开接口
            url = "https://push2.eastmoney.com/api/qt/clist/get"
            params = "?pn=1&pz=1&np=1&fltt=2&invt=2&fid=f3&fs=m:113"
            req = urllib.request.Request(url + params, method="GET",
                                         headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=5)
            elapsed = (time.time() - start) * 1000
            alive = resp.status == 200
            self._record_result('eastmoney', alive, elapsed, error='')
            return alive
        except Exception as e:
            elapsed = (time.time() - start) * 1000 if 'start' in dir() else 0
            self._record_result('eastmoney', False, elapsed, error=str(e)[:100])
            return False

    def check_akshare(self) -> bool:
        """检查 AKShare 模块是否可导入"""
        try:
            import importlib.util
            alive = importlib.util.find_spec("akshare") is not None
            self._record_result('akshare', alive, 0, error='')
            return alive
        except Exception as e:
            self._record_result('akshare', False, 0, error=str(e)[:100])
            return False

    def check_exchange_api(self) -> bool:
        """检查交易所API采集器是否可用"""
        try:
            # 检查 exchange_data_collector 模块
            scripts_dir = str(Path(__file__).parent.parent / "collectors" / "exchange_data" / "scripts")
            sys_path_backup = list(__import__('sys').path)
            if scripts_dir not in __import__('sys').path:
                __import__('sys').path.insert(0, scripts_dir)
            import importlib
            spec = importlib.util.find_spec("exchange_data_collector")
            alive = spec is not None
            self._record_result('exchange_api', alive, 0, error='')
            return alive
        except Exception as e:
            self._record_result('exchange_api', False, 0, error=str(e)[:100])
            return False

    def _record_result(self, source: str, alive: bool, latency_ms: float, error: str):
        """记录一次检测结果并更新状态"""
        now = datetime.now()
        with self._lock:
            status = self._status.get(source, {})
            prev_alive = status.get('alive', False)
            was_in_grace = not status.get('startup_grace_done', False)

            # 更新状态
            status['last_check'] = now
            status['latency_ms'] = latency_ms
            status['error'] = error

            if alive:
                status['alive'] = True
                status['last_alive'] = now
                status['consecutive_failures'] = 0
                status['consecutive_successes'] = status.get('consecutive_successes', 0) + 1
            else:
                status['alive'] = False
                status['consecutive_failures'] = status.get('consecutive_failures', 0) + 1
                status['consecutive_successes'] = 0

            # 启动预热标记：首次成功或超过启动预热时间
            if not was_in_grace and (alive or
               (datetime.now() - status.get('startup_time', now)).total_seconds() > STARTUP_GRACE_SECONDS):
                status['startup_grace_done'] = True

            self._status[source] = status

            # 记录心跳历史
            record = HeartbeatRecord(source, alive, latency_ms, error)
            self._history.append(record)
            if len(self._history) > MAX_HEARTBEAT_HISTORY:
                self._history = self._history[-MAX_HEARTBEAT_HISTORY:]

            # 状态变更告警（忽略预热期的首次变化）
            if was_in_grace:
                status['startup_grace_done'] = True
            elif prev_alive != alive:
                self._fire_state_change(source, alive, error)

            # 保存到磁盘
            self._save_checkpoint()

    # ==================== 批量检测 ====================

    def check_all(self) -> Dict[str, bool]:
        """检测所有数据源并返回状态"""
        return {
            'tdx_local': self.check_tdx_local(),
            'tqsdk': self.check_tqsdk(),
            'eastmoney': self.check_eastmoney(),
            'akshare': self.check_akshare(),
            'exchange_api': self.check_exchange_api(),
        }

    def check_required(self) -> Dict[str, bool]:
        """仅检测必要数据源（优先级链中的核心）"""
        return {
            'tdx_local': self.check_tdx_local(),
            'tqsdk': self.check_tqsdk(),
            'eastmoney': self.check_eastmoney(),
        }

    # ==================== 状态查询 ====================

    def get_status(self, source: str) -> Dict[str, Any]:
        """获取单个数据源的状态"""
        with self._lock:
            return dict(self._status.get(source, {}))

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有数据源的状态"""
        with self._lock:
            return {k: dict(v) for k, v in self._status.items()}

    def is_alive(self, source: str) -> bool:
        """检查特定数据源是否可用"""
        with self._lock:
            src = self._status.get(source, {})
            # 在启动预热期内，认为可用（避免过早降级）
            if not src.get('startup_grace_done', True):
                return True
            return src.get('alive', False)

    def get_unready(self) -> List[str]:
        """获取仍未就绪的数据源列表"""
        return [s for s in ['tdx_local', 'tqsdk', 'eastmoney']
                if not self.is_alive(s)]

    def get_alive_count(self) -> int:
        """获取当前可用数据源数量"""
        return sum(1 for s in ['tdx_local', 'tqsdk', 'eastmoney', 'akshare', 'exchange_api']
                   if self.is_alive(s))

    def get_total_count(self) -> int:
        """获取总数据源数量"""
        return 5  # tdx_local, tqsdk, eastmoney, akshare, exchange_api

    def wait_ready(self, timeout: float = 60, required_sources: List[str] = None) -> bool:
        """等待指定数据源就绪

        Args:
            timeout: 超时秒数
            required_sources: 需要等待的源列表，默认 ['tdx_local', 'tqsdk', 'eastmoney']

        Returns:
            True=全部就绪, False=超时
        """
        if required_sources is None:
            required_sources = ['tdx_local', 'tqsdk', 'eastmoney']

        deadline = time.time() + timeout
        while time.time() < deadline:
            all_ready = True
            for src in required_sources:
                if not self.is_alive(src):
                    all_ready = False
                    # 立刻对未就绪的源做一次检测
                    check_fn = getattr(self, f'check_{src}', None)
                    if check_fn:
                        try:
                            check_fn()
                        except Exception:
                            pass
                    break
            if all_ready:
                return True
            time.sleep(2)
        return False

    # ==================== 后台守护线程 ====================

    def start(self, interval: int = TDX_HEARTBEAT_INTERVAL, daemon: bool = True):
        """启动后台心跳守护线程

        Args:
            interval: 心跳检查间隔（秒），默认 60s
            daemon: 是否为守护线程（主线程退出时自动退出）
        """
        if self._daemon_running:
            return

        self._daemon_running = True
        self._daemon_stop.clear()
        self._daemon_thread = threading.Thread(
            target=self._daemon_loop,
            args=(interval,),
            daemon=daemon,
            name='DataSourceHeartbeat',
        )
        self._daemon_thread.start()

    def stop(self):
        """停止后台心跳守护线程"""
        self._daemon_running = False
        self._daemon_stop.set()
        if self._daemon_thread:
            self._daemon_thread.join(timeout=5)
            self._daemon_thread = None

    def is_running(self) -> bool:
        """检查守护线程是否在运行"""
        return self._daemon_running and (self._daemon_thread is not None
                                         and self._daemon_thread.is_alive())

    def _daemon_loop(self, interval: int):
        """守护线程主循环"""
        last_check_tdx = 0
        last_check_tqsdk = 0
        last_check_eastmoney = 0

        while not self._daemon_stop.is_set():
            now = time.time()

            try:
                # 按不同间隔检查不同数据源
                if now - last_check_tdx >= TDX_HEARTBEAT_INTERVAL:
                    self.check_tdx_local()
                    last_check_tdx = now

                if now - last_check_tqsdk >= TQSDK_CHECK_INTERVAL:
                    self.check_tqsdk()
                    last_check_tqsdk = now

                if now - last_check_eastmoney >= TDX_HEARTBEAT_INTERVAL * 2:
                    self.check_eastmoney()
                    last_check_eastmoney = now
            except Exception:
                pass  # 守护线程不能崩溃

            # 等待下一轮（每 10s 检查一次是否需要退出）
            self._daemon_stop.wait(timeout=10)

    # ==================== 持久化 ====================

    def _save_checkpoint(self):
        """将当前状态保存到磁盘"""
        try:
            checkpoint = {
                'timestamp': datetime.now().isoformat(),
                'status': {k: {
                    'alive': v.get('alive', False),
                    'last_check': str(v.get('last_check', '')),
                    'last_alive': str(v.get('last_alive', '')),
                    'consecutive_failures': v.get('consecutive_failures', 0),
                    'latency_ms': v.get('latency_ms', 0),
                    'error': v.get('error', ''),
                } for k, v in self._status.items()},
                'alive_count': self.get_alive_count(),
                'total_count': self.get_total_count(),
            }
            fpath = os.path.join(self.data_dir, 'heartbeat_checkpoint.json')
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_history(self, source: str = None, limit: int = 20) -> List[Dict]:
        """获取心跳历史"""
        with self._lock:
            records = self._history
            if source:
                records = [r for r in records if r.source == source]
            return [r.to_dict() for r in records[-limit:]]

    def get_uptime(self, source: str) -> float:
        """计算数据源的可用率（最近100次心跳）"""
        with self._lock:
            records = [r for r in self._history if r.source == source]
            if not records:
                return 1.0
            recent = records[-100:]
            alive = sum(1 for r in recent if r.alive)
            return alive / len(recent) if recent else 1.0


# ============================================================
# 告警通知（默认实现：生成 JSON 事件文件供外部读取）
# ============================================================

def _default_alarm_callback(source: str, alive: bool, error: str):
    """默认告警回调：写入事件日志"""
    event = {
        'timestamp': datetime.now().isoformat(),
        'source': source,
        'type': 'recovered' if alive else 'failure',
        'error': error,
    }
    event_dir = os.path.join(HEARTBEAT_DIR, 'heartbeat_events')
    os.makedirs(event_dir, exist_ok=True)
    fname = f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source}.json"
    try:
        with open(os.path.join(event_dir, fname), 'w', encoding='utf-8') as f:
            json.dump(event, f, ensure_ascii=False)
    except Exception:
        pass


# ============================================================
# 模块级单例
# ============================================================

_heartbeat_instance: Optional[DataSourceHeartbeat] = None


def get_heartbeat() -> DataSourceHeartbeat:
    """获取全局 DataSourceHeartbeat 单例"""
    global _heartbeat_instance
    if _heartbeat_instance is None:
        _heartbeat_instance = DataSourceHeartbeat()
        _heartbeat_instance.on_state_change(_default_alarm_callback)
        # 自动连接告警系统：数据源状态变更时推送告警
        try:
            from scripts.alert_manager import get_alert_manager
            _am = get_alert_manager()
            def _alert_on_state_change(source: str, alive: bool, error: str):
                if not alive:
                    _am.alert_data_source(source, 'offline', error)
                else:
                    _am.alert_data_source(source, 'recovered', f'{source} 已恢复在线')
            _heartbeat_instance.on_state_change(_alert_on_state_change)
        except ImportError:
            pass  # alert_manager 未安装时不报警
    return _heartbeat_instance


def hb() -> DataSourceHeartbeat:
    """短别名"""
    return get_heartbeat()


# ============================================================
# CLI 入口
# ============================================================

def main():
    import sys
    beat = get_heartbeat()

    if len(sys.argv) < 2:
        print("Usage: python data_source_heartbeat.py [status|wait|check|history|start|stop]")
        return

    cmd = sys.argv[1]

    if cmd == 'status':
        status = beat.get_all_status()
        print("=" * 60)
        print("  Data Source Heartbeat Status")
        print("=" * 60)
        for src, info in status.items():
            alive = info.get('alive', False)
            latency = info.get('latency_ms', 0)
            failures = info.get('consecutive_failures', 0)
            error = info.get('error', '')
            symbol = 'ALIVE' if alive else 'DEAD'
            print(f"  [{symbol:5s}] {src:15s} latency={latency:>6.1f}ms failures={failures}")
            if error:
                print(f"          error: {error[:80]}")
        print("=" * 60)
        print(f"  Alive: {beat.get_alive_count()}/{beat.get_total_count()}")
        unready = beat.get_unready()
        if unready:
            print(f"  Unready: {', '.join(unready)}")
        print("=" * 60)

    elif cmd == 'wait':
        timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 60
        beat.check_all()  # 先做一次完整检查
        ready = beat.wait_ready(timeout=timeout)
        if ready:
            print(f"All required data sources ready (within {timeout}s)")
        else:
            unready = beat.get_unready()
            print(f"TIMEOUT after {timeout}s. Unready: {', '.join(unready)}")

    elif cmd == 'check':
        results = beat.check_all()
        print("Check results:")
        for src, alive in results.items():
            print(f"  {src}: {'ALIVE' if alive else 'DEAD'}")

    elif cmd == 'history':
        source = sys.argv[2] if len(sys.argv) > 2 else None
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        history = beat.get_history(source=source, limit=limit)
        print(json.dumps(history, indent=2, ensure_ascii=False))

    elif cmd == 'start':
        beat.start()
        print("Heartbeat daemon started in background")

    elif cmd == 'stop':
        beat.stop()
        print("Heartbeat daemon stopped")

    elif cmd == 'uptime':
        for src in ['tdx_local', 'tqsdk', 'eastmoney']:
            uptime = beat.get_uptime(src)
            alive = beat.is_alive(src)
            print(f"  {src:15s} uptime={uptime*100:.1f}% current={'ALIVE' if alive else 'DEAD'}")

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python data_source_heartbeat.py [status|wait|check|history|start|stop|uptime]")


if __name__ == '__main__':
    main()
