#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控与自动调优模块

功能：
1. 系统资源监控（CPU、内存、磁盘IO）
2. 自动调优并行线程数
3. 性能指标持久化记录
4. 健康检查与告警
5. 管道各环节耗时追踪

用法：
    from performance_monitor import PipelineMonitor
    monitor = PipelineMonitor()
    monitor.health_check()
    with monitor.stage("数据获取"):
        fetch_data()
"""

import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 性能日志目录
PERF_LOG_DIR = Path(__file__).parent.parent / "data" / "performance_logs"
PERF_LOG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SystemSnapshot:
    """系统资源快照"""
    timestamp: str
    cpu_percent: float
    memory_total_mb: float
    memory_used_mb: float
    memory_percent: float
    disk_read_mb: float
    disk_write_mb: float


@dataclass
class StageMetrics:
    """单个管道环节的性能指标"""
    name: str
    elapsed_sec: float
    mem_before_mb: float
    mem_after_mb: float
    mem_delta_mb: float
    cpu_avg_percent: float
    status: str = "ok"  # ok / warning / error
    notes: str = ""


@dataclass
class PipelineReport:
    """完整管道性能报告"""
    run_id: str
    start_time: str
    end_time: str
    total_elapsed_sec: float
    stages: List[StageMetrics] = field(default_factory=list)
    system_start: Optional[SystemSnapshot] = None
    system_end: Optional[SystemSnapshot] = None
    auto_tune_info: Dict = field(default_factory=dict)


class PipelineMonitor:
    """管道性能监控器 — 支持自动调优、健康检查、日志持久化"""

    def __init__(self, log_to_file: bool = True, auto_tune: bool = True):
        self._psutil = None
        self._log_to_file = log_to_file
        self._auto_tune = auto_tune
        self._stages: List[StageMetrics] = []
        self._run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._start_time = None
        self._system_start = None
        self._tune_info = {}

        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            logger.warning("psutil未安装，性能监控降级为基础模式")

    # ========== 系统资源 ==========

    def _snapshot(self) -> Optional[SystemSnapshot]:
        """获取系统资源快照"""
        if not self._psutil:
            return None
        vm = self._psutil.virtual_memory()
        try:
            disk = self._psutil.disk_io_counters()
            disk_r = disk.read_bytes / 1024 / 1024 if disk else 0
            disk_w = disk.write_bytes / 1024 / 1024 if disk else 0
        except Exception:
            disk_r = disk_w = 0

        return SystemSnapshot(
            timestamp=datetime.now().isoformat(),
            cpu_percent=self._psutil.cpu_percent(interval=0.5),
            memory_total_mb=vm.total / 1024 / 1024,
            memory_used_mb=vm.used / 1024 / 1024,
            memory_percent=vm.percent,
            disk_read_mb=disk_r,
            disk_write_mb=disk_w,
        )

    def _mem_mb(self) -> float:
        """当前进程内存（MB）"""
        if self._psutil:
            return self._psutil.Process().memory_info().rss / 1024 / 1024
        return 0.0

    def _cpu_percent(self) -> float:
        """当前进程CPU使用率"""
        if self._psutil:
            return self._psutil.Process().cpu_percent(interval=0)
        return 0.0

    # ========== 健康检查 ==========

    def health_check(self) -> Dict:
        """启动前健康检查，返回系统状态摘要"""
        snap = self._snapshot()
        if snap is None:
            return {"status": "degraded", "reason": "psutil不可用"}

        warnings = []
        # 内存检查：可用 < 1GB 时告警
        avail_mb = snap.memory_total_mb - snap.memory_used_mb
        if avail_mb < 1024:
            warnings.append(f"可用内存不足: {avail_mb:.0f}MB")

        # CPU检查：> 90% 时告警
        if snap.cpu_percent > 90:
            warnings.append(f"CPU负载过高: {snap.cpu_percent:.0f}%")

        status = "ok" if not warnings else "warning"
        result = {
            "status": status,
            "cpu_percent": snap.cpu_percent,
            "memory_total_mb": round(snap.memory_total_mb),
            "memory_used_mb": round(snap.memory_used_mb),
            "memory_avail_mb": round(avail_mb),
            "memory_percent": snap.memory_percent,
            "warnings": warnings,
        }
        if warnings:
            for w in warnings:
                logger.warning(f"⚠ 健康检查: {w}")
        else:
            logger.info(f"✅ 健康检查通过 (CPU: {snap.cpu_percent:.0f}%, 内存: {snap.memory_percent:.0f}%)")
        return result

    # ========== 自动调优 ==========

    def auto_tune_workers(self, task_type: str = "cpu") -> int:
        """根据系统负载自动调优并行线程数

        task_type:
            - "io":  IO密集型（数据获取），线程数 = CPU * 2，上限8
            - "cpu": CPU密集型（指标计算），线程数 = CPU，上限6
        """
        if not self._psutil:
            return 4  # 降级默认值

        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        mem = self._psutil.virtual_memory()

        if task_type == "io":
            # IO密集型：更多线程
            base = min(cpu_count * 2, 8)
        else:
            # CPU密集型：与核心数一致
            base = min(cpu_count, 6)

        # 根据内存压力降级
        if mem.percent > 85:
            base = max(2, base // 2)
            logger.warning(f"内存压力高({mem.percent:.0f}%)，降级线程数→{base}")
        elif mem.percent > 70:
            base = max(2, int(base * 0.75))

        # 根据CPU负载降级
        cpu_pct = self._psutil.cpu_percent(interval=0.5)
        if cpu_pct > 80:
            base = max(2, base // 2)
            logger.warning(f"CPU负载高({cpu_pct:.0f}%)，降级线程数→{base}")

        self._tune_info[task_type] = {
            "cpu_count": cpu_count,
            "mem_percent": mem.percent,
            "cpu_percent": cpu_pct,
            "workers": base,
        }
        logger.info(f"自动调优[{task_type}]: {base} 线程 (CPU={cpu_count}, 内存={mem.percent:.0f}%)")
        return base

    # ========== 管道环节追踪 ==========

    @contextmanager
    def stage(self, name: str):
        """上下文管理器：追踪单个管道环节的性能"""
        logger.info(f"▶ 开始: {name}")
        mem_before = self._mem_mb()
        cpu_samples = []
        start = time.time()

        # 后台CPU采样（简单版本）
        class CpuSampler:
            def __init__(self, monitor):
                self.monitor = monitor
                self.samples = []
            def sample(self):
                self.samples.append(self.monitor._cpu_percent())

        sampler = CpuSampler(self)
        try:
            yield sampler
            status = "ok"
            notes = ""
        except Exception as e:
            status = "error"
            notes = str(e)
            raise
        finally:
            elapsed = time.time() - start
            mem_after = self._mem_mb()
            cpu_avg = np.mean(sampler.samples) if sampler.samples else 0

            metric = StageMetrics(
                name=name,
                elapsed_sec=round(elapsed, 3),
                mem_before_mb=round(mem_before, 1),
                mem_after_mb=round(mem_after, 1),
                mem_delta_mb=round(mem_after - mem_before, 1),
                cpu_avg_percent=round(cpu_avg, 1),
                status=status,
                notes=notes,
            )
            self._stages.append(metric)

            icon = "✅" if status == "ok" else "❌"
            logger.info(f"{icon} 完成: {name} ({elapsed:.2f}s, 内存Δ: {mem_after - mem_before:+.1f}MB)")

    # ========== 报告生成 ==========

    def start_pipeline(self):
        """标记管道开始"""
        self._start_time = time.time()
        self._system_start = self._snapshot()

    def finish_pipeline(self) -> PipelineReport:
        """标记管道结束，生成报告"""
        total = time.time() - self._start_time if self._start_time else 0
        report = PipelineReport(
            run_id=self._run_id,
            start_time=datetime.fromtimestamp(self._start_time).isoformat() if self._start_time else "",
            end_time=datetime.now().isoformat(),
            total_elapsed_sec=round(total, 3),
            stages=self._stages,
            system_start=self._system_start,
            system_end=self._snapshot(),
            auto_tune_info=self._tune_info,
        )

        # 打印摘要
        self._print_summary(report)

        # 持久化
        if self._log_to_file:
            self._save_report(report)

        return report

    def _print_summary(self, report: PipelineReport):
        """打印性能摘要"""
        logger.info("\n" + "=" * 60)
        logger.info("管道性能摘要")
        logger.info("=" * 60)
        for s in report.stages:
            icon = "✅" if s.status == "ok" else "❌"
            logger.info(f"  {icon} {s.name}: {s.elapsed_sec:.2f}s (内存: {s.mem_before_mb:.0f}→{s.mem_after_mb:.0f}MB)")
        logger.info(f"  总耗时: {report.total_elapsed_sec:.2f}s")
        if report.system_end:
            logger.info(f"  系统内存: {report.system_end.memory_percent:.0f}%")
        if report.auto_tune_info:
            for k, v in report.auto_tune_info.items():
                logger.info(f"  调优[{k}]: {v.get('workers', '?')} 线程")
        logger.info("=" * 60)

    def _save_report(self, report: PipelineReport):
        """保存报告到JSON文件"""
        try:
            path = PERF_LOG_DIR / f"perf_{report.run_id}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(report), f, ensure_ascii=False, indent=2)
            logger.info(f"性能日志已保存: {path}")
        except Exception as e:
            logger.warning(f"性能日志保存失败: {e}")

    @staticmethod
    def get_recent_reports(limit: int = 10) -> List[Dict]:
        """获取最近N次性能报告摘要"""
        reports = []
        for p in sorted(PERF_LOG_DIR.glob("perf_*.json"), reverse=True)[:limit]:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                reports.append({
                    "run_id": data.get("run_id"),
                    "total_sec": data.get("total_elapsed_sec"),
                    "stages": len(data.get("stages", [])),
                    "end_time": data.get("end_time"),
                })
            except Exception:
                pass
        return reports


# ========== 独立运行：系统资源检查 ==========
if __name__ == "__main__":
    monitor = PipelineMonitor()
    health = monitor.health_check()
    print(json.dumps(health, indent=2, ensure_ascii=False))

    # 显示自动调优建议
    io_workers = monitor.auto_tune_workers("io")
    cpu_workers = monitor.auto_tune_workers("cpu")
    print(f"\n自动调优建议:")
    print(f"  IO密集型(数据获取): {io_workers} 线程")
    print(f"  CPU密集型(指标计算): {cpu_workers} 线程")

    # 显示最近报告
    recent = PipelineMonitor.get_recent_reports(5)
    if recent:
        print(f"\n最近 {len(recent)} 次运行:")
        for r in recent:
            print(f"  {r['run_id']}: {r['total_sec']:.1f}s ({r['stages']}个环节)")
