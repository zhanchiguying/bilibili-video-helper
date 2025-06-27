#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一线程管理器 - 解决线程管理混乱和重复定义问题
集中管理所有后台任务线程，提供统一的接口和生命周期管理
"""

import time
import threading
from typing import Dict, List, Optional, Callable, Any
from PyQt5.QtCore import QThread, pyqtSignal, QObject, QMutex, QWaitCondition
from abc import ABC, abstractmethod

class ThreadPool:
    """线程池管理器"""
    
    def __init__(self, max_threads: int = 5):
        self.max_threads = max_threads
        self.active_threads: Dict[str, 'BaseWorkerThread'] = {}
        self.mutex = QMutex()
        self._shutdown = False
    
    def submit_task(self, task_id: str, thread: 'BaseWorkerThread') -> bool:
        """提交任务到线程池"""
        self.mutex.lock()
        try:
            if self._shutdown:
                return False
                
            if len(self.active_threads) >= self.max_threads:
                return False
                
            if task_id in self.active_threads:
                # 停止已存在的同名任务
                self.active_threads[task_id].stop()
                self.active_threads[task_id].wait(1000)
            
            self.active_threads[task_id] = thread
            thread.finished.connect(lambda: self._on_thread_finished(task_id))
            thread.start()
            return True
        finally:
            self.mutex.unlock()
    
    def _on_thread_finished(self, task_id: str):
        """线程完成回调"""
        self.mutex.lock()
        try:
            if task_id in self.active_threads:
                del self.active_threads[task_id]
        finally:
            self.mutex.unlock()
    
    def stop_task(self, task_id: str) -> bool:
        """停止指定任务"""
        self.mutex.lock()
        try:
            if task_id in self.active_threads:
                self.active_threads[task_id].stop()
                return True
            return False
        finally:
            self.mutex.unlock()
    
    def stop_all(self):
        """停止所有任务"""
        self.mutex.lock()
        try:
            self._shutdown = True
            for thread in self.active_threads.values():
                thread.stop()
            
            # 等待所有线程结束
            for thread in self.active_threads.values():
                thread.wait(2000)
            
            self.active_threads.clear()
        finally:
            self.mutex.unlock()
    
    def get_active_count(self) -> int:
        """获取活跃线程数量"""
        self.mutex.lock()
        try:
            return len(self.active_threads)
        finally:
            self.mutex.unlock()


class BaseWorkerThread(QThread, ABC):
    """基础工作线程 - 所有业务线程的基类"""
    
    # 通用信号
    status_updated = pyqtSignal(str)  # 状态更新
    progress_updated = pyqtSignal(int)  # 进度更新
    task_completed = pyqtSignal(bool, str)  # 任务完成 (成功, 消息)
    error_occurred = pyqtSignal(str)  # 错误发生
    
    def __init__(self, task_name: str = ""):
        super().__init__()
        self.task_name = task_name
        self._stop_requested = False
        self._pause_requested = False
        self._wait_condition = QWaitCondition()
        self._mutex = QMutex()
    
    def stop(self):
        """请求停止线程"""
        self._stop_requested = True
        self._wake_up()
    
    def pause(self):
        """暂停线程"""
        self._pause_requested = True
    
    def resume(self):
        """恢复线程"""
        self._pause_requested = False
        self._wake_up()
    
    def _wake_up(self):
        """唤醒等待的线程"""
        self._mutex.lock()
        self._wait_condition.wakeAll()
        self._mutex.unlock()
    
    def _check_pause_and_stop(self):
        """检查暂停和停止状态"""
        if self._stop_requested:
            return True
        
        if self._pause_requested:
            self._mutex.lock()
            self._wait_condition.wait(self._mutex)
            self._mutex.unlock()
        
        return self._stop_requested
    
    def emit_status(self, message: str):
        """发送状态消息"""
        self.status_updated.emit(f"[{self.task_name}] {message}")
    
    def emit_progress(self, progress: int):
        """发送进度更新"""
        self.progress_updated.emit(progress)
    
    def emit_error(self, error: str):
        """发送错误消息"""
        self.error_occurred.emit(f"[{self.task_name}] 错误: {error}")
    
    def run(self):
        """线程主执行方法"""
        try:
            self.emit_status("任务开始")
            result = self.execute_task()
            
            if not self._stop_requested:
                self.task_completed.emit(result, "任务完成")
                self.emit_status("任务完成")
        
        except Exception as e:
            self.emit_error(str(e))
            self.task_completed.emit(False, f"任务失败: {e}")
        
        finally:
            self.emit_status("线程结束")
    
    @abstractmethod
    def execute_task(self) -> bool:
        """执行具体任务 - 子类必须实现"""
        pass


class LoginWorkerThread(BaseWorkerThread):
    """登录工作线程"""
    
    def __init__(self, account_manager, username: str):
        super().__init__(f"登录-{username}")
        self.account_manager = account_manager
        self.username = username
    
    def execute_task(self) -> bool:
        """执行登录任务"""
        self.emit_status(f"开始登录账号: {self.username}")
        
        try:
            success = self.account_manager.login_account(self.username)
            if success:
                self.emit_status(f"账号 {self.username} 登录成功")
                return True
            else:
                self.emit_error(f"账号 {self.username} 登录失败")
                return False
        
        except Exception as e:
            self.emit_error(f"登录过程异常: {e}")
            return False


class VideoUploadWorkerThread(BaseWorkerThread):
    """视频上传工作线程"""
    
    def __init__(self, core_app, account_name: str, video_filename: str, 
                 video_directory: str, upload_settings: dict):
        super().__init__(f"上传-{account_name}")
        self.core_app = core_app
        self.account_name = account_name
        self.video_filename = video_filename
        self.video_directory = video_directory
        self.upload_settings = upload_settings
    
    def execute_task(self) -> bool:
        """执行视频上传任务"""
        # 这里会调用原有的上传逻辑，但是通过统一的接口
        self.emit_status("准备上传环境...")
        self.emit_progress(10)
        
        if self._check_pause_and_stop():
            return False
        
        # 验证账号
        account = self.core_app.account_manager.get_account(self.account_name)
        if not account or account.status != 'active':
            self.emit_error("账号未激活")
            return False
        
        self.emit_progress(30)
        
        if self._check_pause_and_stop():
            return False
        
        # 这里可以调用具体的上传逻辑
        # 为了简化，这里模拟上传过程
        import time
        for i in range(50, 100, 10):
            if self._check_pause_and_stop():
                return False
            
            self.emit_progress(i)
            self.emit_status(f"上传进度: {i}%")
            time.sleep(0.5)  # 模拟上传时间
        
        self.emit_progress(100)
        return True


class BatchUploadWorkerThread(BaseWorkerThread):
    """批量上传工作线程"""
    
    def __init__(self, core_app, selected_accounts: List[str], video_files: List[str],
                 video_dir: str, concurrent_browsers: int, videos_per_account: int):
        super().__init__("批量上传")
        self.core_app = core_app
        self.selected_accounts = selected_accounts
        self.video_files = video_files
        self.video_dir = video_dir
        self.concurrent_browsers = concurrent_browsers
        self.videos_per_account = videos_per_account
    
    def execute_task(self) -> bool:
        """执行批量上传任务"""
        total_tasks = len(self.selected_accounts) * self.videos_per_account
        completed_tasks = 0
        
        self.emit_status(f"开始批量上传，总任务数: {total_tasks}")
        
        # 这里实现批量上传逻辑
        for account in self.selected_accounts:
            if self._check_pause_and_stop():
                return False
            
            self.emit_status(f"处理账号: {account}")
            
            for i in range(self.videos_per_account):
                if self._check_pause_and_stop():
                    return False
                
                if i < len(self.video_files):
                    video_file = self.video_files[i]
                    self.emit_status(f"上传视频: {video_file}")
                    
                    # 模拟单个视频上传
                    time.sleep(1)
                    
                    completed_tasks += 1
                    progress = int((completed_tasks / total_tasks) * 100)
                    self.emit_progress(progress)
        
        return True


class LicenseWorkerThread(BaseWorkerThread):
    """许可证验证工作线程"""
    
    def __init__(self, license_system, license_content: str):
        super().__init__("许可证验证")
        self.license_system = license_system
        self.license_content = license_content
    
    def execute_task(self) -> bool:
        """执行许可证验证任务"""
        self.emit_status("开始验证许可证...")
        
        try:
            result = self.license_system.verify_license(self.license_content)
            
            if result.get('valid', False):
                self.emit_status("许可证验证通过")
                return True
            else:
                self.emit_error(result.get('error', '未知错误'))
                return False
        
        except Exception as e:
            self.emit_error(f"验证过程异常: {e}")
            return False


class FileOperationWorkerThread(BaseWorkerThread):
    """文件操作工作线程"""
    
    def __init__(self, operation: str, **kwargs):
        super().__init__(f"文件操作-{operation}")
        self.operation = operation
        self.kwargs = kwargs
    
    def execute_task(self) -> bool:
        """执行文件操作任务"""
        self.emit_status(f"开始文件操作: {self.operation}")
        
        try:
            if self.operation == "scan_videos":
                return self._scan_videos()
            elif self.operation == "cleanup_temp":
                return self._cleanup_temp()
            # 可以添加更多文件操作类型
            else:
                self.emit_error(f"未知的文件操作类型: {self.operation}")
                return False
            
        except Exception as e:
            self.emit_error(f"文件操作异常: {e}")
            return False
    
    def _scan_videos(self) -> bool:
        """扫描视频文件"""
        directory = self.kwargs.get('directory', '')
        if not directory:
            return False
        
        import os
        from core.config import Config
        
        video_files = []
        try:
            for file in os.listdir(directory):
                if self._check_pause_and_stop():
                    return False
                
                if any(file.lower().endswith(ext) for ext in Config.VIDEO_EXTENSIONS):
                    video_files.append(file)
                    self.emit_status(f"发现视频: {file}")
        
        except Exception as e:
            self.emit_error(f"扫描目录失败: {e}")
            return False
        
        self.emit_status(f"扫描完成，共发现 {len(video_files)} 个视频文件")
        return True
    
    def _cleanup_temp(self) -> bool:
        """清理临时文件"""
        # 实现临时文件清理逻辑
        import os
        import tempfile
        
        temp_dir = tempfile.gettempdir()
        cleaned_files = 0
        
        try:
            for root, dirs, files in os.walk(temp_dir):
                if self._check_pause_and_stop():
                    return False
                
                for file in files:
                    if file.startswith('bilibili_temp_'):
                        try:
                            os.remove(os.path.join(root, file))
                            cleaned_files += 1
                            self.emit_status(f"已清理: {file}")
                        except:
                            continue
        
        except Exception as e:
            self.emit_error(f"清理过程异常: {e}")
            return False
        
        self.emit_status(f"清理完成，共清理 {cleaned_files} 个临时文件")
        return True


# 全局线程池实例
_global_thread_pool = None

def get_thread_pool() -> ThreadPool:
    """获取全局线程池实例"""
    global _global_thread_pool
    if _global_thread_pool is None:
        _global_thread_pool = ThreadPool(max_threads=8)
    return _global_thread_pool

def shutdown_thread_pool():
    """关闭全局线程池"""
    global _global_thread_pool
    if _global_thread_pool:
        _global_thread_pool.stop_all()
        _global_thread_pool = None


class ThreadManager:
    """线程管理器 - 提供高级线程管理接口"""
    
    def __init__(self):
        self.thread_pool = get_thread_pool()
    
    def start_login_task(self, account_manager, username: str) -> bool:
        """启动登录任务"""
        task_id = f"login_{username}"
        thread = LoginWorkerThread(account_manager, username)
        return self.thread_pool.submit_task(task_id, thread)
    
    def start_upload_task(self, core_app, account_name: str, video_filename: str,
                         video_directory: str, upload_settings: dict) -> bool:
        """启动上传任务"""
        task_id = f"upload_{account_name}"
        thread = VideoUploadWorkerThread(core_app, account_name, video_filename,
                                       video_directory, upload_settings)
        return self.thread_pool.submit_task(task_id, thread)
    
    def start_batch_upload_task(self, core_app, selected_accounts: List[str],
                              video_files: List[str], video_dir: str,
                              concurrent_browsers: int, videos_per_account: int) -> bool:
        """启动批量上传任务"""
        task_id = "batch_upload"
        thread = BatchUploadWorkerThread(core_app, selected_accounts, video_files,
                                       video_dir, concurrent_browsers, videos_per_account)
        return self.thread_pool.submit_task(task_id, thread)
    
    def start_license_verification(self, license_system, license_content: str) -> bool:
        """启动许可证验证任务"""
        task_id = "license_verification"
        thread = LicenseWorkerThread(license_system, license_content)
        return self.thread_pool.submit_task(task_id, thread)
    
    def start_file_operation(self, operation: str, **kwargs) -> bool:
        """启动文件操作任务"""
        task_id = f"file_op_{operation}"
        thread = FileOperationWorkerThread(operation, **kwargs)
        return self.thread_pool.submit_task(task_id, thread)
    
    def stop_task(self, task_id: str) -> bool:
        """停止指定任务"""
        return self.thread_pool.stop_task(task_id)
    
    def stop_all_tasks(self):
        """停止所有任务"""
        self.thread_pool.stop_all()
    
    def get_active_thread_count(self) -> int:
        """获取活跃线程数量"""
        return self.thread_pool.get_active_count()


# 全局线程管理器实例
_global_thread_manager = None

def get_thread_manager() -> ThreadManager:
    """获取全局线程管理器实例"""
    global _global_thread_manager
    if _global_thread_manager is None:
        _global_thread_manager = ThreadManager()
    return _global_thread_manager 