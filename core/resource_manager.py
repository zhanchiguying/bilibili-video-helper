#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资源管理器 - 统一管理系统资源，避免内存泄漏
优化内存使用、文件句柄、浏览器实例等资源的生命周期管理
"""

import gc
import os
import sys
import time
import threading
import weakref
from typing import Dict, List, Set, Optional, Any
from contextlib import contextmanager
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .logger import get_logger

@dataclass
class ResourceInfo:
    """资源信息"""
    resource_id: str
    resource_type: str
    created_at: float
    last_accessed: float
    size_bytes: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ResourceTracker:
    """资源跟踪器"""
    
    def __init__(self):
        self._resources: Dict[str, ResourceInfo] = {}
        self._lock = threading.RLock()
        self.logger = get_logger()
    
    def register_resource(self, resource_id: str, resource_type: str, 
                         size_bytes: int = 0, **metadata) -> bool:
        """注册资源"""
        with self._lock:
            current_time = time.time()
            resource_info = ResourceInfo(
                resource_id=resource_id,
                resource_type=resource_type,
                created_at=current_time,
                last_accessed=current_time,
                size_bytes=size_bytes,
                metadata=metadata
            )
            self._resources[resource_id] = resource_info
            self.logger.debug(f"注册资源: {resource_type}:{resource_id}")
            return True
    
    def unregister_resource(self, resource_id: str) -> bool:
        """注销资源"""
        with self._lock:
            if resource_id in self._resources:
                resource_info = self._resources.pop(resource_id)
                self.logger.debug(f"注销资源: {resource_info.resource_type}:{resource_id}")
                return True
            return False
    
    def update_access_time(self, resource_id: str):
        """更新访问时间"""
        with self._lock:
            if resource_id in self._resources:
                self._resources[resource_id].last_accessed = time.time()
    
    def get_resource_info(self, resource_id: str) -> Optional[ResourceInfo]:
        """获取资源信息"""
        with self._lock:
            return self._resources.get(resource_id)
    
    def get_resources_by_type(self, resource_type: str) -> List[ResourceInfo]:
        """按类型获取资源"""
        with self._lock:
            return [info for info in self._resources.values() 
                   if info.resource_type == resource_type]
    
    def get_idle_resources(self, max_idle_time: float = 300) -> List[ResourceInfo]:
        """获取空闲资源"""
        current_time = time.time()
        with self._lock:
            return [info for info in self._resources.values()
                   if current_time - info.last_accessed > max_idle_time]
    
    def get_total_memory_usage(self) -> int:
        """获取总内存使用量"""
        with self._lock:
            return sum(info.size_bytes for info in self._resources.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取资源统计"""
        with self._lock:
            stats = {
                'total_resources': len(self._resources),
                'total_memory_bytes': self.get_total_memory_usage(),
                'by_type': {}
            }
            
            for info in self._resources.values():
                resource_type = info.resource_type
                if resource_type not in stats['by_type']:
                    stats['by_type'][resource_type] = {
                        'count': 0,
                        'memory_bytes': 0
                    }
                stats['by_type'][resource_type]['count'] += 1
                stats['by_type'][resource_type]['memory_bytes'] += info.size_bytes
            
            return stats


class BrowserResourceManager:
    """浏览器资源管理器"""
    
    def __init__(self):
        self.active_browsers: Dict[str, Any] = {}  # account_name -> driver instance
        self.browser_processes: Set[int] = set()
        self.max_browsers = 5
        self.idle_timeout = 300  # 5分钟空闲超时
        self.logger = get_logger()
        self._lock = threading.RLock()
        
        # 启动清理任务
        self._cleanup_timer = threading.Timer(60, self._periodic_cleanup)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()
    
    def register_browser(self, account_name: str, driver, process_id: int = None):
        """注册浏览器实例"""
        with self._lock:
            self.active_browsers[account_name] = {
                'driver': driver,
                'created_at': time.time(),
                'last_used': time.time(),
                'process_id': process_id
            }
            
            if process_id:
                self.browser_processes.add(process_id)
            
            self.logger.info(f"注册浏览器实例: {account_name} (PID: {process_id})")
            
            # 检查是否超过最大数量
            if len(self.active_browsers) > self.max_browsers:
                self._cleanup_idle_browsers()
    
    def unregister_browser(self, account_name: str):
        """注销浏览器实例"""
        with self._lock:
            if account_name in self.active_browsers:
                browser_info = self.active_browsers.pop(account_name)
                process_id = browser_info.get('process_id')
                
                if process_id:
                    self.browser_processes.discard(process_id)
                
                self.logger.info(f"注销浏览器实例: {account_name}")
                
                # 清理驱动实例
                try:
                    driver = browser_info['driver']
                    if hasattr(driver, 'quit'):
                        driver.quit()
                except Exception as e:
                    self.logger.error(f"关闭浏览器失败: {e}")
    
    def update_browser_usage(self, account_name: str):
        """更新浏览器使用时间"""
        with self._lock:
            if account_name in self.active_browsers:
                self.active_browsers[account_name]['last_used'] = time.time()
    
    def get_browser(self, account_name: str):
        """获取浏览器实例"""
        with self._lock:
            if account_name in self.active_browsers:
                self.update_browser_usage(account_name)
                return self.active_browsers[account_name]['driver']
            return None
    
    def _cleanup_idle_browsers(self):
        """清理空闲浏览器"""
        current_time = time.time()
        idle_accounts = []
        
        with self._lock:
            for account_name, browser_info in self.active_browsers.items():
                if current_time - browser_info['last_used'] > self.idle_timeout:
                    idle_accounts.append(account_name)
        
        for account_name in idle_accounts:
            self.logger.info(f"清理空闲浏览器: {account_name}")
            self.unregister_browser(account_name)
    
    def _periodic_cleanup(self):
        """定期清理任务"""
        try:
            self._cleanup_idle_browsers()
            self._cleanup_orphaned_processes()
        except Exception as e:
            self.logger.error(f"定期清理失败: {e}")
        finally:
            # 重新设置定时器
            self._cleanup_timer = threading.Timer(60, self._periodic_cleanup)
            self._cleanup_timer.daemon = True
            self._cleanup_timer.start()
    
    def _cleanup_orphaned_processes(self):
        """清理孤儿进程"""
        try:
            import psutil
            orphaned_processes = []
            
            for pid in list(self.browser_processes):
                try:
                    if not psutil.pid_exists(pid):
                        orphaned_processes.append(pid)
                except:
                    orphaned_processes.append(pid)
            
            for pid in orphaned_processes:
                self.browser_processes.discard(pid)
                self.logger.debug(f"移除孤儿进程记录: {pid}")
        
        except ImportError:
            pass  # psutil不可用
        except Exception as e:
            self.logger.error(f"清理孤儿进程失败: {e}")
    
    def cleanup_all(self):
        """清理所有浏览器"""
        with self._lock:
            account_names = list(self.active_browsers.keys())
            for account_name in account_names:
                self.unregister_browser(account_name)
            
            # 停止定时器
            if hasattr(self, '_cleanup_timer'):
                self._cleanup_timer.cancel()


class FileResourceManager:
    """文件资源管理器"""
    
    def __init__(self):
        self.open_files: Dict[str, Any] = {}
        self.temp_files: Set[str] = set()
        self.cache_files: Dict[str, float] = {}  # path -> created_time
        self.max_cache_age = 3600  # 1小时
        self.logger = get_logger()
        self._lock = threading.RLock()
    
    @contextmanager
    def managed_file(self, file_path: str, mode: str = 'r', **kwargs):
        """托管文件上下文管理器"""
        file_obj = None
        try:
            file_obj = open(file_path, mode, **kwargs)
            file_id = f"{file_path}:{id(file_obj)}"
            
            with self._lock:
                self.open_files[file_id] = {
                    'file_obj': file_obj,
                    'path': file_path,
                    'mode': mode,
                    'opened_at': time.time()
                }
            
            yield file_obj
        
        finally:
            if file_obj:
                try:
                    file_obj.close()
                except:
                    pass
                
                file_id = f"{file_path}:{id(file_obj)}"
                with self._lock:
                    self.open_files.pop(file_id, None)
    
    def register_temp_file(self, file_path: str):
        """注册临时文件"""
        with self._lock:
            self.temp_files.add(file_path)
            self.logger.debug(f"注册临时文件: {file_path}")
    
    def register_cache_file(self, file_path: str):
        """注册缓存文件"""
        with self._lock:
            self.cache_files[file_path] = time.time()
            self.logger.debug(f"注册缓存文件: {file_path}")
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        cleaned_count = 0
        
        with self._lock:
            temp_files = list(self.temp_files)
        
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    cleaned_count += 1
                
                with self._lock:
                    self.temp_files.discard(file_path)
            
            except Exception as e:
                self.logger.warning(f"清理临时文件失败 {file_path}: {e}")
        
        self.logger.info(f"清理了 {cleaned_count} 个临时文件")
        return cleaned_count
    
    def cleanup_cache_files(self):
        """清理过期缓存文件"""
        current_time = time.time()
        cleaned_count = 0
        
        with self._lock:
            expired_files = [
                path for path, created_time in self.cache_files.items()
                if current_time - created_time > self.max_cache_age
            ]
        
        for file_path in expired_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    cleaned_count += 1
                
                with self._lock:
                    self.cache_files.pop(file_path, None)
            
            except Exception as e:
                self.logger.warning(f"清理缓存文件失败 {file_path}: {e}")
        
        self.logger.info(f"清理了 {cleaned_count} 个过期缓存文件")
        return cleaned_count
    
    def get_open_files_count(self) -> int:
        """获取打开文件数量"""
        with self._lock:
            return len(self.open_files)


class MemoryManager:
    """内存管理器"""
    
    def __init__(self):
        self.logger = get_logger()
        self._weak_refs: Set[weakref.ref] = set()
        self._large_objects: Dict[str, Any] = {}
        self.gc_threshold = 100 * 1024 * 1024  # 100MB
    
    def register_large_object(self, obj_id: str, obj: Any, size_hint: int = 0):
        """注册大对象"""
        self._large_objects[obj_id] = {
            'object': obj,
            'size_hint': size_hint,
            'created_at': time.time()
        }
        self.logger.debug(f"注册大对象: {obj_id} ({size_hint} bytes)")
        
        # 检查是否需要垃圾回收
        if self.get_estimated_memory_usage() > self.gc_threshold:
            self.force_garbage_collection()
    
    def unregister_large_object(self, obj_id: str):
        """注销大对象"""
        if obj_id in self._large_objects:
            self._large_objects.pop(obj_id)
            self.logger.debug(f"注销大对象: {obj_id}")
    
    def get_estimated_memory_usage(self) -> int:
        """获取估计内存使用量"""
        return sum(info['size_hint'] for info in self._large_objects.values())
    
    def force_garbage_collection(self):
        """强制垃圾回收"""
        before_count = len(gc.get_objects())
        collected = gc.collect()
        after_count = len(gc.get_objects())
        
        self.logger.info(f"强制垃圾回收: 回收{collected}个对象, 对象数量 {before_count} -> {after_count}")
        return collected
    
    def cleanup_weak_refs(self):
        """清理失效的弱引用"""
        valid_refs = set()
        for ref in self._weak_refs:
            if ref() is not None:
                valid_refs.add(ref)
        
        cleaned_count = len(self._weak_refs) - len(valid_refs)
        self._weak_refs = valid_refs
        
        if cleaned_count > 0:
            self.logger.debug(f"清理了 {cleaned_count} 个失效弱引用")
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """获取内存统计"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                'rss': memory_info.rss,
                'vms': memory_info.vms,
                'percent': process.memory_percent(),
                'large_objects': len(self._large_objects),
                'estimated_large_usage': self.get_estimated_memory_usage(),
                'gc_objects': len(gc.get_objects()),
                'weak_refs': len(self._weak_refs)
            }
        except ImportError:
            return {
                'large_objects': len(self._large_objects),
                'estimated_large_usage': self.get_estimated_memory_usage(),
                'gc_objects': len(gc.get_objects()),
                'weak_refs': len(self._weak_refs)
            }


class ResourceManager:
    """主资源管理器"""
    
    def __init__(self):
        self.logger = get_logger()
        self.tracker = ResourceTracker()
        self.browser_manager = BrowserResourceManager()
        self.file_manager = FileResourceManager()
        self.memory_manager = MemoryManager()
        self._shutdown = False
        
        # 启动定期清理任务
        self._start_periodic_cleanup()
    
    def _start_periodic_cleanup(self):
        """启动定期清理任务"""
        def cleanup_task():
            while not self._shutdown:
                try:
                    self.periodic_cleanup()
                    time.sleep(300)  # 5分钟清理一次
                except Exception as e:
                    self.logger.error(f"定期清理任务异常: {e}")
                    time.sleep(60)  # 出错后1分钟重试
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
    
    def periodic_cleanup(self):
        """定期清理"""
        self.logger.debug("开始定期资源清理")
        
        # 清理临时文件
        temp_cleaned = self.file_manager.cleanup_temp_files()
        
        # 清理缓存文件
        cache_cleaned = self.file_manager.cleanup_cache_files()
        
        # 内存清理
        self.memory_manager.cleanup_weak_refs()
        gc_collected = self.memory_manager.force_garbage_collection()
        
        self.logger.info(f"定期清理完成: 临时文件{temp_cleaned}, 缓存文件{cache_cleaned}, GC回收{gc_collected}")
    
    def emergency_cleanup(self):
        """紧急清理 - 在内存不足时调用"""
        self.logger.warning("执行紧急资源清理")
        
        # 立即清理所有可清理的资源
        self.file_manager.cleanup_temp_files()
        self.file_manager.cleanup_cache_files()
        self.memory_manager.force_garbage_collection()
        
        # 清理空闲浏览器
        self.browser_manager._cleanup_idle_browsers()
        
        self.logger.info("紧急清理完成")
    
    def get_resource_usage_report(self) -> Dict[str, Any]:
        """获取资源使用报告"""
        return {
            'timestamp': time.time(),
            'tracker_stats': self.tracker.get_statistics(),
            'browser_count': len(self.browser_manager.active_browsers),
            'open_files': self.file_manager.get_open_files_count(),
            'temp_files': len(self.file_manager.temp_files),
            'cache_files': len(self.file_manager.cache_files),
            'memory_stats': self.memory_manager.get_memory_statistics()
        }
    
    def shutdown(self):
        """关闭资源管理器"""
        self.logger.info("关闭资源管理器")
        self._shutdown = True
        
        # 清理所有资源
        self.browser_manager.cleanup_all()
        self.file_manager.cleanup_temp_files()
        self.memory_manager.force_garbage_collection()


# 全局资源管理器实例
_global_resource_manager = None

def get_resource_manager() -> ResourceManager:
    """获取全局资源管理器"""
    global _global_resource_manager
    if _global_resource_manager is None:
        _global_resource_manager = ResourceManager()
    return _global_resource_manager

def shutdown_resource_manager():
    """关闭全局资源管理器"""
    global _global_resource_manager
    if _global_resource_manager:
        _global_resource_manager.shutdown()
        _global_resource_manager = None 