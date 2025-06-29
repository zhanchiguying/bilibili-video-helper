#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高性能视频文件加载器 v1.0
支持增量扫描、智能缓存、后台加载
专为大量视频文件场景优化
"""

import os
import time
import hashlib
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from core.logger import get_logger

logger = get_logger()

@dataclass
class VideoFileInfo:
    """视频文件信息"""
    filename: str
    filepath: str
    size_bytes: int
    size_mb: float
    mtime: float  # 修改时间
    display_text: str

@dataclass 
class ScanResult:
    """扫描结果"""
    files: List[VideoFileInfo]
    total_files: int
    total_size_mb: float
    scan_time: float
    from_cache: bool = False

class VideoFileCache:
    """视频文件缓存管理器"""
    
    def __init__(self, cache_duration: int = 300):  # 5分钟缓存
        self.cache_duration = cache_duration
        self._cache: Dict[str, Tuple[ScanResult, float]] = {}
        self._dir_mtime_cache: Dict[str, float] = {}
        
    def get_cache_key(self, directory: str) -> str:
        """生成缓存键"""
        return hashlib.md5(directory.encode()).hexdigest()
        
    def is_cache_valid(self, directory: str) -> bool:
        """检查缓存是否有效"""
        cache_key = self.get_cache_key(directory)
        
        if cache_key not in self._cache:
            return False
            
        result, cache_time = self._cache[cache_key]
        
        # 检查时间是否过期
        if time.time() - cache_time > self.cache_duration:
            return False
            
        # 检查目录修改时间是否变化
        try:
            current_mtime = os.path.getmtime(directory)
            cached_mtime = self._dir_mtime_cache.get(directory, 0)
            return abs(current_mtime - cached_mtime) < 1.0  # 1秒容差
        except:
            return False
    
    def get_cached_result(self, directory: str) -> Optional[ScanResult]:
        """获取缓存结果"""
        if not self.is_cache_valid(directory):
            return None
            
        cache_key = self.get_cache_key(directory)
        result, _ = self._cache[cache_key]
        result.from_cache = True
        return result
    
    def cache_result(self, directory: str, result: ScanResult):
        """缓存扫描结果"""
        cache_key = self.get_cache_key(directory)
        current_time = time.time()
        
        try:
            dir_mtime = os.path.getmtime(directory)
            self._dir_mtime_cache[directory] = dir_mtime
        except:
            pass
            
        self._cache[cache_key] = (result, current_time)
        
        # 清理过期缓存
        self._cleanup_expired_cache()
    
    def _cleanup_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []
        
        for key, (_, cache_time) in self._cache.items():
            if current_time - cache_time > self.cache_duration:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            
    def clear_cache(self, directory: str = None):
        """清除缓存"""
        if directory:
            cache_key = self.get_cache_key(directory)
            self._cache.pop(cache_key, None)
            self._dir_mtime_cache.pop(directory, None)
        else:
            self._cache.clear()
            self._dir_mtime_cache.clear()

class AsyncVideoFileLoader(QObject):
    """异步视频文件加载器"""
    
    # 信号
    scan_started = pyqtSignal(str)  # directory
    scan_progress = pyqtSignal(int, int)  # current, total
    scan_completed = pyqtSignal(object)  # ScanResult
    scan_failed = pyqtSignal(str)  # error_message
    
    # 视频文件扩展名
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
    
    def __init__(self, max_workers: int = 4):
        super().__init__()
        self.max_workers = max_workers
        self.cache = VideoFileCache()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._current_scan_future = None
        self._is_scanning = False
        
    def scan_directory_async(self, directory: str, force_refresh: bool = False):
        """异步扫描目录"""
        if self._is_scanning:
            logger.info("正在扫描中，跳过新的扫描请求")
            return
            
        if not directory or not os.path.exists(directory):
            self.scan_failed.emit("目录不存在或无效")
            return
        
        # 检查缓存
        if not force_refresh:
            cached_result = self.cache.get_cached_result(directory)
            if cached_result:
                logger.info(f"使用缓存结果，文件数量: {cached_result.total_files}")
                self.scan_completed.emit(cached_result)
                return
        
        # 启动异步扫描
        self._is_scanning = True
        self.scan_started.emit(directory)
        
        self._current_scan_future = self._executor.submit(
            self._scan_directory_worker, directory
        )
        
        # 监控扫描完成
        def on_scan_done():
            try:
                if self._current_scan_future and not self._current_scan_future.cancelled():
                    result = self._current_scan_future.result()
                    self.cache.cache_result(directory, result)
                    self.scan_completed.emit(result)
            except Exception as e:
                error_msg = f"扫描失败: {e}"
                logger.error(error_msg)
                self.scan_failed.emit(error_msg)
            finally:
                self._is_scanning = False
                self._current_scan_future = None
        
        # 使用QTimer来在主线程中处理结果
        check_timer = QTimer()
        check_timer.setSingleShot(True)
        
        def check_completion():
            if self._current_scan_future and self._current_scan_future.done():
                on_scan_done()
            else:
                # 继续检查
                check_timer.start(100)
        
        check_timer.timeout.connect(check_completion)
        check_timer.start(100)
    
    def _scan_directory_worker(self, directory: str) -> ScanResult:
        """扫描目录的工作线程"""
        start_time = time.time()
        
        try:
            # 🚀 第一步：快速获取文件列表（只获取文件名）
            all_files = []
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    file_ext = Path(item).suffix.lower()
                    if file_ext in self.VIDEO_EXTENSIONS:
                        all_files.append((item, item_path))
            
            total_files = len(all_files)
            if total_files == 0:
                return ScanResult([], 0, 0.0, time.time() - start_time)
            
            # 🚀 第二步：并行获取文件大小（性能关键）
            video_files = []
            total_size = 0
            
            def get_file_info(file_item):
                filename, filepath = file_item
                try:
                    size_bytes = os.path.getsize(filepath)
                    size_mb = size_bytes / (1024 * 1024)
                    mtime = os.path.getmtime(filepath)
                    
                    display_text = f"{filename} ({size_mb:.1f}MB)"
                    return VideoFileInfo(
                        filename=filename,
                        filepath=filepath,
                        size_bytes=size_bytes,
                        size_mb=size_mb,
                        mtime=mtime,
                        display_text=display_text
                    )
                except Exception as e:
                    # 文件可能被删除或无法访问，返回基本信息
                    return VideoFileInfo(
                        filename=filename,
                        filepath=filepath,
                        size_bytes=0,
                        size_mb=0.0,
                        mtime=0.0,
                        display_text=filename
                    )
            
            # 🚀 并行处理文件信息获取
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(get_file_info, file_item): i 
                    for i, file_item in enumerate(all_files)
                }
                
                completed = 0
                for future in as_completed(future_to_file):
                    file_info = future.result()
                    video_files.append(file_info)
                    total_size += file_info.size_bytes
                    
                    completed += 1
                    # 发送进度信号（每10%或每50个文件发送一次）
                    if completed % max(1, total_files // 10) == 0 or completed % 50 == 0:
                        self.scan_progress.emit(completed, total_files)
            
            # 🚀 按文件名排序
            video_files.sort(key=lambda x: x.filename.lower())
            
            scan_time = time.time() - start_time
            total_size_mb = total_size / (1024 * 1024)
            
            logger.info(f"扫描完成: {total_files}个文件, {total_size_mb:.1f}MB, 耗时{scan_time:.2f}秒")
            
            return ScanResult(
                files=video_files,
                total_files=total_files,
                total_size_mb=total_size_mb,
                scan_time=scan_time
            )
            
        except Exception as e:
            logger.error(f"扫描目录失败: {e}")
            raise
    
    def cancel_current_scan(self):
        """取消当前扫描"""
        if self._current_scan_future and not self._current_scan_future.done():
            self._current_scan_future.cancel()
            self._is_scanning = False
            logger.info("扫描已取消")
    
    def clear_cache(self, directory: str = None):
        """清除缓存"""
        self.cache.clear_cache(directory)
        
    def is_scanning(self) -> bool:
        """是否正在扫描"""
        return self._is_scanning
        
    def __del__(self):
        """析构函数"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)

class OptimizedVideoListManager:
    """优化的视频列表管理器"""
    
    def __init__(self, video_list_widget, stats_label=None):
        self.video_list = video_list_widget
        self.stats_label = stats_label
        self.loader = AsyncVideoFileLoader()
        
        # 分页参数
        self.files_per_page = 200
        self.current_page = 0
        self.total_pages = 0
        self.all_files: List[VideoFileInfo] = []
        
        # 连接信号
        self.loader.scan_started.connect(self._on_scan_started)
        self.loader.scan_progress.connect(self._on_scan_progress) 
        self.loader.scan_completed.connect(self._on_scan_completed)
        self.loader.scan_failed.connect(self._on_scan_failed)
        
    def refresh_directory(self, directory: str, force_refresh: bool = False):
        """刷新目录"""
        self.current_page = 0
        self.loader.scan_directory_async(directory, force_refresh)
        
    def _on_scan_started(self, directory: str):
        """扫描开始"""
        if self.stats_label:
            self.stats_label.setText("📊 正在扫描文件...")
            
    def _on_scan_progress(self, current: int, total: int):
        """扫描进度"""
        if self.stats_label:
            progress = int(current / total * 100) if total > 0 else 0
            self.stats_label.setText(f"📊 扫描进度: {current}/{total} ({progress}%)")
            
    def _on_scan_completed(self, result: ScanResult):
        """扫描完成"""
        self.all_files = result.files
        self.total_pages = (result.total_files + self.files_per_page - 1) // self.files_per_page
        
        # 更新列表显示
        self._update_list_display()
        
        # 更新统计信息
        if self.stats_label:
            cache_text = " (缓存)" if result.from_cache else ""
            if self.total_pages > 1:
                self.stats_label.setText(
                    f"📊 第{self.current_page + 1}/{self.total_pages}页 | "
                    f"总计: {result.total_files}个文件 ({result.total_size_mb:.1f}MB){cache_text}"
                )
            else:
                self.stats_label.setText(
                    f"📊 文件统计: {result.total_files}个文件, {result.total_size_mb:.1f}MB{cache_text}"
                )
        
        logger.info(f"视频列表更新完成: {result.total_files}个文件")
        
    def _on_scan_failed(self, error_message: str):
        """扫描失败"""
        if self.stats_label:
            self.stats_label.setText(f"📊 扫描失败: {error_message}")
        logger.error(f"视频文件扫描失败: {error_message}")
        
    def _update_list_display(self):
        """更新列表显示"""
        # 计算当前页的文件范围
        start_idx = self.current_page * self.files_per_page
        end_idx = min(start_idx + self.files_per_page, len(self.all_files))
        current_page_files = self.all_files[start_idx:end_idx]
        
        # 更新UI
        self.video_list.blockSignals(True)
        self.video_list.clear()
        
        for file_info in current_page_files:
            from PyQt5.QtWidgets import QListWidgetItem
            from PyQt5.QtCore import Qt
            
            item = QListWidgetItem(file_info.display_text)
            item.setData(Qt.UserRole, file_info.filepath)
            self.video_list.addItem(item)
        
        self.video_list.blockSignals(False)
        
    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_list_display()
            return True
        return False
        
    def prev_page(self):
        """上一页"""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_list_display()
            return True
        return False
        
    def get_current_files(self) -> List[VideoFileInfo]:
        """获取当前页文件"""
        start_idx = self.current_page * self.files_per_page
        end_idx = min(start_idx + self.files_per_page, len(self.all_files))
        return self.all_files[start_idx:end_idx]
        
    def get_all_files(self) -> List[VideoFileInfo]:
        """获取所有文件"""
        return self.all_files.copy()
        
    def clear_cache(self, directory: str = None):
        """清除缓存"""
        self.loader.clear_cache(directory)
        
    def is_loading(self) -> bool:
        """是否正在加载"""
        return self.loader.is_scanning() 