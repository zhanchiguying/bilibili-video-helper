#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能分析器 - 监控和分析程序性能
提供实时性能监控、瓶颈识别、优化建议等功能
"""

import time
import threading
import functools
import sys
import gc
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import contextmanager

from .logger import get_logger

@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    start_time: float
    end_time: float = 0.0
    duration: float = 0.0
    memory_before: int = 0
    memory_after: int = 0
    memory_delta: int = 0
    call_count: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self, end_time: float, memory_after: int = 0):
        """完成性能记录"""
        self.end_time = end_time
        self.duration = end_time - self.start_time
        self.memory_after = memory_after
        self.memory_delta = memory_after - self.memory_before

@dataclass
class FunctionStats:
    """函数统计信息"""
    function_name: str
    total_calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    last_call_time: float = 0.0
    memory_usage: List[int] = field(default_factory=list)
    recent_calls: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def add_call(self, duration: float, memory_delta: int = 0):
        """添加调用记录"""
        self.total_calls += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.avg_time = self.total_time / self.total_calls
        self.last_call_time = time.time()
        
        if memory_delta != 0:
            self.memory_usage.append(memory_delta)
        
        self.recent_calls.append({
            'timestamp': self.last_call_time,
            'duration': duration,
            'memory_delta': memory_delta
        })

class PerformanceProfiler:
    """性能分析器"""
    
    def __init__(self, max_records: int = 10000):
        self.max_records = max_records
        self.metrics: deque = deque(maxlen=max_records)
        self.function_stats: Dict[str, FunctionStats] = {}
        self.active_metrics: Dict[str, PerformanceMetric] = {}
        self.enabled = True
        self.lock = threading.RLock()
        self.logger = get_logger()
        
        # 性能阈值配置
        self.slow_function_threshold = 1.0  # 1秒
        self.high_memory_threshold = 10 * 1024 * 1024  # 10MB
        
        # 警告回调
        self.warning_callbacks: List[Callable] = []
    
    def add_warning_callback(self, callback: Callable):
        """添加性能警告回调"""
        self.warning_callbacks.append(callback)
    
    def _trigger_warning(self, warning_type: str, message: str, data: Dict = None):
        """触发性能警告"""
        for callback in self.warning_callbacks:
            try:
                callback(warning_type, message, data or {})
            except Exception as e:
                self.logger.error(f"性能警告回调异常: {e}")
    
    def start_metric(self, name: str, metadata: Dict = None) -> str:
        """开始性能测量"""
        if not self.enabled:
            return name
        
        metric_id = f"{name}_{id(threading.current_thread())}_{time.time()}"
        
        with self.lock:
            metric = PerformanceMetric(
                name=name,
                start_time=time.time(),
                memory_before=self._get_memory_usage(),
                metadata=metadata or {}
            )
            self.active_metrics[metric_id] = metric
        
        return metric_id
    
    def end_metric(self, metric_id: str):
        """结束性能测量"""
        if not self.enabled or metric_id not in self.active_metrics:
            return
        
        end_time = time.time()
        memory_after = self._get_memory_usage()
        
        with self.lock:
            metric = self.active_metrics.pop(metric_id)
            metric.finish(end_time, memory_after)
            
            # 添加到记录中
            self.metrics.append(metric)
            
            # 更新函数统计
            self._update_function_stats(metric)
            
            # 检查性能警告
            self._check_performance_warnings(metric)
    
    def _update_function_stats(self, metric: PerformanceMetric):
        """更新函数统计"""
        func_name = metric.name
        if func_name not in self.function_stats:
            self.function_stats[func_name] = FunctionStats(func_name)
        
        self.function_stats[func_name].add_call(metric.duration, metric.memory_delta)
    
    def _check_performance_warnings(self, metric: PerformanceMetric):
        """检查性能警告"""
        # 检查慢函数
        if metric.duration > self.slow_function_threshold:
            self._trigger_warning(
                "slow_function",
                f"函数 {metric.name} 执行时间过长: {metric.duration:.2f}秒",
                {"function": metric.name, "duration": metric.duration}
            )
        
        # 检查高内存使用
        if metric.memory_delta > self.high_memory_threshold:
            self._trigger_warning(
                "high_memory",
                f"函数 {metric.name} 内存使用过高: {metric.memory_delta / 1024 / 1024:.1f}MB",
                {"function": metric.name, "memory_delta": metric.memory_delta}
            )
    
    @contextmanager
    def measure(self, name: str, metadata: Dict = None):
        """性能测量上下文管理器"""
        metric_id = self.start_metric(name, metadata)
        try:
            yield
        finally:
            self.end_metric(metric_id)
    
    def profile_function(self, func_name: str = None, include_memory: bool = True):
        """函数性能分析装饰器"""
        def decorator(func):
            name = func_name or f"{func.__module__}.{func.__name__}"
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)
                
                with self.measure(name, {"args_count": len(args), "kwargs_count": len(kwargs)}):
                    return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def get_function_stats(self, top_n: int = 10) -> List[FunctionStats]:
        """获取函数统计信息"""
        with self.lock:
            # 按平均执行时间排序
            sorted_stats = sorted(
                self.function_stats.values(),
                key=lambda x: x.avg_time,
                reverse=True
            )
            return sorted_stats[:top_n]
    
    def get_slow_functions(self, threshold: float = None) -> List[FunctionStats]:
        """获取慢函数列表"""
        threshold = threshold or self.slow_function_threshold
        with self.lock:
            return [
                stats for stats in self.function_stats.values()
                if stats.avg_time > threshold
            ]
    
    def get_memory_intensive_functions(self, threshold: int = None) -> List[FunctionStats]:
        """获取内存密集函数列表"""
        threshold = threshold or self.high_memory_threshold
        with self.lock:
            return [
                stats for stats in self.function_stats.values()
                if stats.memory_usage and max(stats.memory_usage) > threshold
            ]
    
    def get_recent_metrics(self, count: int = 100) -> List[PerformanceMetric]:
        """获取最近的性能指标"""
        with self.lock:
            return list(self.metrics)[-count:]
    
    def _get_memory_usage(self) -> int:
        """获取当前内存使用量"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            return 0
    
    def generate_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        with self.lock:
            total_metrics = len(self.metrics)
            if total_metrics == 0:
                return {"error": "没有性能数据"}
            
            # 统计总体信息
            total_time = sum(m.duration for m in self.metrics)
            avg_time = total_time / total_metrics
            
            # 获取慢函数
            slow_functions = self.get_slow_functions()
            
            # 获取内存密集函数
            memory_intensive = self.get_memory_intensive_functions()
            
            # 最近的性能趋势
            recent_metrics = self.get_recent_metrics(100)
            recent_avg_time = sum(m.duration for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0
            
            return {
                "summary": {
                    "total_measurements": total_metrics,
                    "total_time": total_time,
                    "average_time": avg_time,
                    "recent_average_time": recent_avg_time,
                    "unique_functions": len(self.function_stats)
                },
                "slow_functions": [
                    {
                        "name": f.function_name,
                        "avg_time": f.avg_time,
                        "total_calls": f.total_calls,
                        "max_time": f.max_time
                    } for f in slow_functions[:10]
                ],
                "memory_intensive_functions": [
                    {
                        "name": f.function_name,
                        "max_memory": max(f.memory_usage) if f.memory_usage else 0,
                        "avg_memory": sum(f.memory_usage) / len(f.memory_usage) if f.memory_usage else 0,
                        "total_calls": f.total_calls
                    } for f in memory_intensive[:10]
                ],
                "recommendations": self._generate_recommendations()
            }
    
    def _generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 检查慢函数
        slow_functions = self.get_slow_functions()
        if slow_functions:
            recommendations.append(f"发现 {len(slow_functions)} 个慢函数，建议进行优化")
        
        # 检查内存使用
        memory_intensive = self.get_memory_intensive_functions()
        if memory_intensive:
            recommendations.append(f"发现 {len(memory_intensive)} 个内存密集函数，建议优化内存使用")
        
        # 检查GC频率
        gc_count = gc.get_count()
        if gc_count[0] > 1000:
            recommendations.append("垃圾回收频繁，建议检查对象创建和销毁")
        
        # 检查线程数量
        active_threads = threading.active_count()
        if active_threads > 20:
            recommendations.append(f"活跃线程数较多 ({active_threads})，建议检查线程管理")
        
        return recommendations
    
    def clear_stats(self):
        """清空统计数据"""
        with self.lock:
            self.metrics.clear()
            self.function_stats.clear()
            self.active_metrics.clear()
    
    def enable(self):
        """启用性能分析"""
        self.enabled = True
    
    def disable(self):
        """禁用性能分析"""
        self.enabled = False


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, check_interval: float = 5.0):
        self.check_interval = check_interval
        self.monitoring = False
        self.monitor_thread = None
        self.logger = get_logger()
        
        # 监控数据
        self.cpu_history = deque(maxlen=100)
        self.memory_history = deque(maxlen=100)
        self.thread_history = deque(maxlen=100)
        
        # 阈值
        self.cpu_threshold = 80.0  # 80%
        self.memory_threshold = 80.0  # 80%
        self.thread_threshold = 50
        
        # 警告回调
        self.warning_callbacks: List[Callable] = []
    
    def add_warning_callback(self, callback: Callable):
        """添加系统警告回调"""
        self.warning_callbacks.append(callback)
    
    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("系统监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        self.logger.info("系统监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                self._collect_system_metrics()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"系统监控异常: {e}")
                time.sleep(self.check_interval)
    
    def _collect_system_metrics(self):
        """收集系统指标"""
        timestamp = time.time()
        
        try:
            import psutil
            
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_history.append((timestamp, cpu_percent))
            
            # 内存使用率
            memory = psutil.virtual_memory()
            self.memory_history.append((timestamp, memory.percent))
            
            # 线程数
            thread_count = threading.active_count()
            self.thread_history.append((timestamp, thread_count))
            
            # 检查阈值
            self._check_thresholds(cpu_percent, memory.percent, thread_count)
            
        except ImportError:
            # psutil不可用，使用基础监控
            thread_count = threading.active_count()
            self.thread_history.append((timestamp, thread_count))
            
            if thread_count > self.thread_threshold:
                self._trigger_warning("high_threads", f"线程数过多: {thread_count}")
    
    def _check_thresholds(self, cpu_percent: float, memory_percent: float, thread_count: int):
        """检查阈值"""
        if cpu_percent > self.cpu_threshold:
            self._trigger_warning("high_cpu", f"CPU使用率过高: {cpu_percent:.1f}%")
        
        if memory_percent > self.memory_threshold:
            self._trigger_warning("high_memory", f"内存使用率过高: {memory_percent:.1f}%")
        
        if thread_count > self.thread_threshold:
            self._trigger_warning("high_threads", f"线程数过多: {thread_count}")
    
    def _trigger_warning(self, warning_type: str, message: str):
        """触发警告"""
        for callback in self.warning_callbacks:
            try:
                callback(warning_type, message)
            except Exception as e:
                self.logger.error(f"系统警告回调异常: {e}")
    
    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前统计信息"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('.')
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available": memory.available,
                "disk_percent": (disk.used / disk.total) * 100,
                "disk_free": disk.free,
                "thread_count": threading.active_count(),
                "process_count": len(psutil.pids())
            }
        except ImportError:
            return {
                "thread_count": threading.active_count(),
                "gc_count": gc.get_count()
            }


# 全局性能分析器实例
_global_profiler = None
_global_monitor = None

def get_profiler() -> PerformanceProfiler:
    """获取全局性能分析器"""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler()
    return _global_profiler

def get_monitor() -> SystemMonitor:
    """获取全局系统监控器"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = SystemMonitor()
    return _global_monitor

def profile(func_name: str = None):
    """性能分析装饰器"""
    return get_profiler().profile_function(func_name)

@contextmanager
def measure_performance(name: str, metadata: Dict = None):
    """性能测量上下文管理器"""
    with get_profiler().measure(name, metadata):
        yield 