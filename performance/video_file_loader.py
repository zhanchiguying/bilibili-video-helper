#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高性能视频文件加载器 v1.0
支持增量扫描、智能缓存、后台加载、随机化
专为大量视频文件场景优化
"""

import os
import time
import hashlib
import threading
import random  # 🎯 新增：支持随机化
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QListWidgetItem
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

# 🎯 新增：视频随机化策略
class VideoRandomizer:
    """视频随机化管理器"""
    
    @staticmethod
    def shuffle_videos(video_files: List[str], strategy: str = "random") -> List[str]:
        """
        打乱视频顺序
        
        Args:
            video_files: 视频文件列表
            strategy: 随机化策略
                - "random": 完全随机
                - "group": 分组随机（每10个一组）
                - "partial": 部分随机（保留30%原顺序）
                - "none": 不随机
        
        Returns:
            打乱后的视频文件列表
        """
        if strategy == "none" or not video_files:
            return video_files.copy()
        
        result = video_files.copy()
        
        if strategy == "random":
            # 完全随机打乱
            random.shuffle(result)
            logger.info(f"🎲 完全随机化 {len(result)} 个视频")
            
        elif strategy == "group":
            # 分组随机：每10个为一组，组内随机，组间顺序保持
            group_size = 10
            for i in range(0, len(result), group_size):
                group = result[i:i+group_size]
                random.shuffle(group)
                result[i:i+group_size] = group
            logger.info(f"🎲 分组随机化 {len(result)} 个视频（每组{group_size}个）")
            
        elif strategy == "partial":
            # 部分随机：随机选择70%的视频进行位置交换
            indices = list(range(len(result)))
            swap_count = int(len(indices) * 0.7)
            swap_indices = random.sample(indices, swap_count)
            
            # 成对交换
            for i in range(0, len(swap_indices)-1, 2):
                idx1, idx2 = swap_indices[i], swap_indices[i+1]
                result[idx1], result[idx2] = result[idx2], result[idx1]
            logger.info(f"🎲 部分随机化 {len(result)} 个视频（交换{swap_count//2}对）")
        
        return result
    
    @staticmethod
    def get_randomization_info(original: List[str], shuffled: List[str]) -> str:
        """获取随机化统计信息"""
        if len(original) != len(shuffled):
            return "❌ 列表长度不匹配"
        
        unchanged_count = sum(1 for i, (o, s) in enumerate(zip(original, shuffled)) if o == s)
        changed_count = len(original) - unchanged_count
        change_rate = (changed_count / len(original)) * 100 if original else 0
        
        return f"📊 随机化统计: {changed_count}/{len(original)} 位置改变 ({change_rate:.1f}%)"

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
        
        # 使用更简单直接的方式处理异步结果
        def handle_result():
            try:
                if self._current_scan_future and self._current_scan_future.done():
                    if not self._current_scan_future.cancelled():
                        result = self._current_scan_future.result()
                        self.cache.cache_result(directory, result)
                        logger.info(f"扫描完成，发送结果信号: {result.total_files}个文件")
                        self.scan_completed.emit(result)
                    self._is_scanning = False
                    self._current_scan_future = None
                else:
                    # 继续检查
                    QTimer.singleShot(100, handle_result)
            except Exception as e:
                error_msg = f"扫描失败: {e}"
                logger.error(error_msg)
                self.scan_failed.emit(error_msg)
                self._is_scanning = False
                self._current_scan_future = None
        
        # 开始检查结果
        QTimer.singleShot(100, handle_result)
    
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
        logger.info(f"收到扫描完成信号: {result.total_files}个文件")
        
        self.all_files = result.files
        self.total_pages = (result.total_files + self.files_per_page - 1) // self.files_per_page
        
        logger.info(f"开始更新视频列表显示，总页数: {self.total_pages}")
        
        # 更新列表显示
        self._update_list_display()
        
        # 更新统计信息
        if self.stats_label:
            cache_text = " (缓存)" if result.from_cache else ""
            if self.total_pages > 1:
                stats_text = (
                    f"📊 第{self.current_page + 1}/{self.total_pages}页 | "
                    f"总计: {result.total_files}个文件 ({result.total_size_mb:.1f}MB){cache_text}"
                )
            else:
                stats_text = f"📊 文件统计: {result.total_files}个文件, {result.total_size_mb:.1f}MB{cache_text}"
            
            self.stats_label.setText(stats_text)
            logger.info(f"统计信息已更新: {stats_text}")
        
        logger.info(f"视频列表UI更新完成: {result.total_files}个文件")
        
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
        
        logger.info(f"更新视频列表显示: 第{self.current_page+1}页, {len(current_page_files)}个文件")
        
        # 更新UI
        self.video_list.blockSignals(True)
        self.video_list.clear()
        
        for i, file_info in enumerate(current_page_files):
            item = QListWidgetItem(file_info.display_text)
            item.setData(Qt.UserRole, file_info.filepath)
            self.video_list.addItem(item)
            if i < 3:  # 只打印前3个文件作为调试
                logger.info(f"  添加文件: {file_info.display_text}")
        
        self.video_list.blockSignals(False)
        logger.info(f"视频列表UI更新完成，共添加{len(current_page_files)}个条目")
        
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

# 🎯 新增：MD5缓存管理器
class VideoMD5Cache:
    """视频文件MD5缓存管理器 - 解决性能瓶颈"""
    
    def __init__(self, cache_duration: int = 3600):  # 1小时缓存
        self.cache_duration = cache_duration
        self._md5_cache: Dict[str, Tuple[str, float, float]] = {}  # {filepath: (md5, mtime, cache_time)}
        self._lock = threading.Lock()
        
    def get_file_md5(self, file_path: str) -> Optional[str]:
        """
        获取文件MD5，优先使用缓存
        
        Args:
            file_path: 文件路径
            
        Returns:
            MD5值或None
        """
        try:
            with self._lock:
                # 检查文件是否存在
                if not os.path.exists(file_path):
                    return None
                
                # 获取文件修改时间
                current_mtime = os.path.getmtime(file_path)
                current_time = time.time()
                
                # 检查缓存
                if file_path in self._md5_cache:
                    cached_md5, cached_mtime, cache_time = self._md5_cache[file_path]
                    
                    # 验证缓存有效性
                    if (abs(current_mtime - cached_mtime) < 1.0 and  # 文件未修改
                        current_time - cache_time < self.cache_duration):  # 缓存未过期
                        logger.debug(f"📊 MD5缓存命中: {os.path.basename(file_path)}")
                        return cached_md5
                
                # 缓存失效，重新计算MD5
                logger.info(f"🔢 计算MD5: {os.path.basename(file_path)}")
                md5_hash = self._calculate_md5(file_path)
                
                if md5_hash:
                    # 更新缓存
                    self._md5_cache[file_path] = (md5_hash, current_mtime, current_time)
                    
                    # 清理过期缓存
                    self._cleanup_expired_cache()
                
                return md5_hash
                
        except Exception as e:
            logger.error(f"获取MD5失败: {file_path} - {e}")
            return None
    
    def _calculate_md5(self, file_path: str) -> Optional[str]:
        """计算文件MD5值"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):  # 8KB chunks
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"计算MD5异常: {file_path} - {e}")
            return None
    
    def _cleanup_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []
        
        for file_path, (_, _, cache_time) in self._md5_cache.items():
            if current_time - cache_time > self.cache_duration:
                expired_keys.append(file_path)
        
        for key in expired_keys:
            del self._md5_cache[key]
        
        if expired_keys:
            logger.info(f"🧹 清理过期MD5缓存: {len(expired_keys)} 个条目")
    
    def clear_cache(self, file_path: str = None):
        """清除缓存"""
        with self._lock:
            if file_path:
                self._md5_cache.pop(file_path, None)
                logger.info(f"🧹 清除MD5缓存: {os.path.basename(file_path)}")
            else:
                cache_count = len(self._md5_cache)
                self._md5_cache.clear()
                logger.info(f"🧹 清除全部MD5缓存: {cache_count} 个条目")
    
    def get_cache_stats(self) -> str:
        """获取缓存统计信息"""
        with self._lock:
            cache_count = len(self._md5_cache)
            return f"📊 MD5缓存: {cache_count} 个文件"

# 全局MD5缓存实例
_global_md5_cache = VideoMD5Cache()

def get_global_md5_cache() -> VideoMD5Cache:
    """获取全局MD5缓存实例"""
    return _global_md5_cache 

# 🎯 核心解决方案：视频上传协调器
class VideoUploadCoordinator:
    """视频上传协调器 - 解决时序、重复上传、代码分散问题"""
    
    def __init__(self):
        self._upload_locks: Dict[str, threading.Lock] = {}  # 文件级别锁
        self._global_lock = threading.Lock()
        self.md5_cache = get_global_md5_cache()
    
    def safe_upload_video(self, video_path: str, account_name: str, uploader, 
                         browser, product_info: dict, upload_thread) -> Tuple[bool, str]:
        """
        安全的视频上传流程 - 解决所有已知问题
        
        Returns:
            (success, message)
        """
        filename = os.path.basename(video_path)
        
        # 🔒 步骤1：获取文件级别的锁，防止重复上传
        file_lock = self._get_file_lock(video_path)
        
        try:
            # 非阻塞获取锁，如果获取失败说明其他线程正在处理
            if not file_lock.acquire(blocking=False):
                return False, f"视频 {filename} 正在被其他账号处理"
            
            # 🔍 步骤2：在锁保护下再次检查视频状态
            md5_hash = self.md5_cache.get_file_md5(video_path)
            if not md5_hash:
                return False, f"无法计算文件MD5: {filename}"
            
            # 检查是否已上传（在锁保护下）
            try:
                from database.database_manager import db_manager
                if db_manager.is_video_uploaded(md5_hash):
                    return False, f"视频 {filename} 已被上传，跳过"
            except Exception as e:
                return False, f"检查上传状态失败: {e}"
            
            upload_thread.upload_status.emit(f"🔒 [{account_name}] 获得视频上传锁: {filename}")
            
            # 🚀 步骤3：执行上传（同步等待完成）
            upload_result = self._perform_synchronized_upload(
                video_path, account_name, uploader, browser, product_info, upload_thread
            )
            
            if upload_result['success']:
                # 📊 步骤4：原子性更新数据库和删除文件
                if self._atomic_complete_upload(video_path, account_name, upload_result['product_id'], upload_thread):
                    return True, f"视频 {filename} 上传并删除成功"
                else:
                    return False, f"视频 {filename} 上传成功但后处理失败"
            else:
                return False, f"视频 {filename} 上传失败: {upload_result['error']}"
        
        finally:
            # 🔓 释放文件锁
            try:
                file_lock.release()
                upload_thread.upload_status.emit(f"🔓 [{account_name}] 释放视频上传锁: {filename}")
            except:
                pass
    
    def _get_file_lock(self, video_path: str) -> threading.Lock:
        """获取文件级别的锁"""
        with self._global_lock:
            if video_path not in self._upload_locks:
                self._upload_locks[video_path] = threading.Lock()
            return self._upload_locks[video_path]
    
    def _perform_synchronized_upload(self, video_path: str, account_name: str, 
                                   uploader, browser, product_info: dict, 
                                   upload_thread) -> dict:
        """执行同步上传，等待完成"""
        import threading
        
        result = {'success': False, 'error': '', 'product_id': ''}
        upload_complete_event = threading.Event()
        
        # 同步回调函数
        def sync_success_callback():
            try:
                filename = os.path.basename(video_path)
                from core.bilibili_product_manager import get_product_manager
                product_manager = get_product_manager()
                product_id = product_manager.extract_product_id_from_filename(filename)
                
                result['success'] = True
                result['product_id'] = product_id
                upload_thread.upload_status.emit(f"✅ [{account_name}] 视频上传完成: {filename}")
                
                # 🔧 关键修复：在VideoUploadCoordinator的回调中返回True，避免uploader认为失败
                return True
                
            except Exception as e:
                result['error'] = f"回调处理异常: {e}"
                upload_thread.upload_status.emit(f"❌ [{account_name}] 回调异常: {e}")
                return False
            finally:
                upload_complete_event.set()
        
        try:
            # 🔧 关键修复：清除任何现有的回调，避免冲突
            old_callback = getattr(uploader, 'success_callback', None)
            if old_callback:
                upload_thread.upload_status.emit(f"🔧 [{account_name}] 发现现有回调，清除以避免重复调用")
            
            # 🔧 强制清除任何可能的回调
            uploader.success_callback = None
            upload_thread.upload_status.emit(f"🔧 [{account_name}] 回调已清除，设置VideoUploadCoordinator专用回调")
            
            # 设置同步回调
            uploader.success_callback = sync_success_callback
            
            # 1. 上传视频文件
            need_popup_handling = account_name not in getattr(upload_thread, 'account_popup_handled', {})
            if not uploader.upload_video(browser, video_path, account_name, need_popup_handling):
                result['error'] = "视频文件上传失败"
                return result
            
            # 标记弹窗已处理
            if need_popup_handling:
                if not hasattr(upload_thread, 'account_popup_handled'):
                    upload_thread.account_popup_handled = {}
                upload_thread.account_popup_handled[account_name] = True
            
            # 2. 填写视频信息
            filename = os.path.basename(video_path)
            filename_without_ext = filename.rsplit('.', 1)[0]
            if '----' in filename_without_ext:
                extracted_title = filename_without_ext.split('----', 1)[1]
            else:
                extracted_title = filename_without_ext
            
            upload_settings = {
                "title": extracted_title,
                "tags": ["带货", "推荐"],
                "description": f"优质商品推荐: {product_info.get('goodsName', '精选商品')}",
                "title_template": "{filename}"
            }
            
            if not uploader.fill_video_info(browser, filename, upload_settings, product_info):
                result['error'] = "填写视频信息失败"
                return result
            
            # 3. 添加商品
            if not uploader.add_product_to_video(browser, filename, product_info):
                result['error'] = "添加商品失败"
                return result
            
            # 4. 发布视频并等待完成
            if not uploader.publish_video(browser, account_name):
                result['error'] = "发布视频失败"
                return result
            
            # 🎯 关键：等待回调完成（最多等待30秒）
            if upload_complete_event.wait(timeout=30):
                if not result['success']:
                    result['error'] = result.get('error', '未知错误')
            else:
                result['error'] = "上传超时（30秒）"
            
            return result
            
        except Exception as e:
            result['error'] = f"上传过程异常: {e}"
            return result
        finally:
            # 🔧 强化清理回调，确保不影响后续使用
            try:
                uploader.success_callback = None
                upload_thread.upload_status.emit(f"🔧 [{account_name}] VideoUploadCoordinator回调已清理")
            except Exception as e:
                upload_thread.upload_status.emit(f"⚠️ [{account_name}] 清理回调时异常: {e}")
                pass
    
    def _atomic_complete_upload(self, video_path: str, account_name: str, 
                              product_id: str, upload_thread) -> bool:
        """原子性完成上传：更新数据库 + 删除文件"""
        try:
            # 🎯 步骤1：更新数据库
            success = upload_thread.mark_video_uploaded(video_path, account_name, product_id)
            if not success:
                upload_thread.upload_status.emit(f"❌ [{account_name}] 数据库更新失败")
                return False
            
            # 🎯 步骤2：删除文件
            if upload_thread.delete_video_file(video_path):
                upload_thread.upload_status.emit(f"🗑️ [{account_name}] 文件删除成功")
                
                # 🎯 步骤3：发送界面更新信号
                upload_thread.account_progress_updated.emit(account_name)
                return True
            else:
                upload_thread.upload_status.emit(f"⚠️ [{account_name}] 文件删除失败")
                return False
                
        except Exception as e:
            upload_thread.upload_status.emit(f"❌ [{account_name}] 完成上传时异常: {e}")
            return False
    
    def clear_completed_locks(self):
        """清理已完成的文件锁"""
        with self._global_lock:
            # 清理不存在文件的锁
            to_remove = []
            for video_path in self._upload_locks:
                if not os.path.exists(video_path):
                    to_remove.append(video_path)
            
            for path in to_remove:
                del self._upload_locks[path]
            
            if to_remove:
                logger.info(f"🧹 清理文件锁: {len(to_remove)} 个")

# 全局上传协调器实例
_global_upload_coordinator = VideoUploadCoordinator()

def get_global_upload_coordinator() -> VideoUploadCoordinator:
    """获取全局上传协调器实例"""
    return _global_upload_coordinator 