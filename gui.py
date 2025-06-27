#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频带货助手 - GUI界面（简化版本）
"""

import sys
import os
import time
import json
import re
# 统一使用线程管理器，移除直接导入
from functools import wraps
from typing import Optional

# PyQt5 明确导入
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QFrame, QGroupBox, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QLineEdit, QComboBox, QListWidget, QProgressBar, QTextEdit,
    QCheckBox, QAbstractItemView, QHeaderView, QInputDialog, QMessageBox,
    QFileDialog, QSpinBox, QSplashScreen, QListWidgetItem
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QObject
from PyQt5.QtGui import QFont, QColor, QTextCursor, QIcon, QPixmap

# 应用模块
from core.app import BilibiliUploaderApp as BilibiliApp
from core.config import Config
from core.ui_styles import UIStyles
from core.ui_config import UIConfig
from core.bilibili_video_uploader import BilibiliVideoUploader
from core.license_system import LicenseSystem
from core.button_utils import prevent_double_click, protect_button_click

class LoginThread(QThread):
    """登录线程"""
    login_success = pyqtSignal(str)
    login_failed = pyqtSignal(str, str)
    
    def __init__(self, account_manager, username):
        super().__init__()
        self.account_manager = account_manager
        self.username = username
    
    def run(self):
        try:
            success = self.account_manager.login_account(self.username)
            if success:
                self.login_success.emit(self.username)
            else:
                self.login_failed.emit(self.username, "登录失败")
        except Exception as e:
            self.login_failed.emit(self.username, str(e))


class BrowserUploadThread(QThread):
    """浏览器上传线程"""
    upload_progress = pyqtSignal(int)
    upload_status = pyqtSignal(str)
    upload_finished = pyqtSignal(bool, str)
    
    def __init__(self, core_app, account_name, video_filename, video_directory, upload_settings):
        super().__init__()
        self.core_app = core_app
        self.account_name = account_name
        self.video_filename = video_filename
        self.video_directory = video_directory
        self.upload_settings = upload_settings
        self.is_paused = False
        self.is_stopped = False
        self.dialog_handled = False  # 标记弹窗是否已处理
        
    def pause(self):
        self.is_paused = True
        
    def resume(self):
        self.is_paused = False
        
    def stop(self):
        self.is_stopped = True
        
    def run(self):
        try:
            # 步骤1: 验证账号和浏览器
            self.upload_status.emit("验证账号状态...")
            self.upload_progress.emit(10)
            
            account = self.core_app.account_manager.get_account(self.account_name)
            if not account or account.status != 'active':
                self.upload_finished.emit(False, "账号未激活，请先登录")
                return
                
            if self.is_stopped:
                return
                
            # 步骤2: 验证视频文件
            self.upload_status.emit("验证视频文件...")
            self.upload_progress.emit(20)
            
            video_path = os.path.join(self.video_directory, self.video_filename)
            if not os.path.exists(video_path):
                self.upload_finished.emit(False, f"视频文件不存在: {video_path}")
                return
                
            # 步骤3: 验证商品ID
            self.upload_status.emit("验证商品信息...")
            self.upload_progress.emit(30)
            
            # 使用商品管理器验证商品
            from core.bilibili_product_manager import get_product_manager
            product_manager = get_product_manager()
            
            # 提取商品ID
            product_id = product_manager.extract_product_id_from_filename(self.video_filename)
            if not product_id:
                self.upload_finished.emit(False, "无法从文件名提取商品ID，请确保文件名包含商品ID")
                return
                
            # 验证商品
            cookies = product_manager.get_cookies_from_account(account)
            if not cookies:
                self.upload_finished.emit(False, "无法获取账号Cookie，请重新登录")
                return
                
            jd_url = product_manager.build_jd_url(product_id)
            success, product_info = product_manager.distinguish_product(jd_url, cookies)
            
            if not success or not product_info:
                self.upload_finished.emit(False, f"商品验证失败 (ID: {product_id})，可能商品不在B站联盟库中")
                return
                
            self.upload_status.emit(f"商品验证成功: {product_info.get('goodsName', '未知商品')}")
            self.upload_progress.emit(40)
            
            if self.is_stopped:
                return
                
            # 步骤4: 启动浏览器并访问创作中心
            self.upload_status.emit("启动浏览器...")
            self.upload_progress.emit(50)
            
            # 获取浏览器实例
            if hasattr(account, 'browser_instance') and account.browser_instance:
                driver = account.browser_instance
            else:
                self.upload_finished.emit(False, "账号浏览器实例不存在，请重新登录")
                return
                
            # 访问创作中心
            self.upload_status.emit("访问B站创作中心...")
            try:
                driver.get("https://member.bilibili.com/platform/upload/video/frame")
                time.sleep(UIConfig.PAGE_LOAD_DELAY)  # 给页面更多加载时间
                
            except Exception as e:
                self.upload_finished.emit(False, f"访问创作中心失败: {e}")
                return
                
            self.upload_progress.emit(60)
            
            if self.is_stopped:
                return
                
            # 步骤5: 使用独立上传器进行真实上传视频
            self.upload_status.emit("开始真实上传视频文件...")
            from core.bilibili_video_uploader import create_uploader
            uploader = create_uploader(self.upload_status.emit, self.core_app.config_manager)
            
            # 真实上传视频文件
            self.upload_status.emit(f"📤 [{self.account_name}] 上传视频文件...")
            success = uploader.upload_video(driver, video_path)
            if not success:
                self.upload_finished.emit(False, "视频上传失败")
                return
                
            self.upload_progress.emit(80)
            
            # 步骤6: 使用独立上传器填写视频信息
            self.upload_status.emit("填写视频信息...")
            success = uploader.fill_video_info(driver, self.video_filename, self.upload_settings, product_info)
            if not success:
                self.upload_finished.emit(False, "填写视频信息失败")
                return
                
            self.upload_progress.emit(85)
            
            # 步骤7: 使用独立上传器添加商品
            self.upload_status.emit("添加带货商品...")
            success = uploader.add_product_to_video(driver, self.video_filename, product_info)
            if not success:
                self.upload_finished.emit(False, "添加商品失败")
                return
                
            self.upload_progress.emit(95)
            
            # 步骤8: 使用独立上传器发布视频
            self.upload_status.emit("发布视频...")
            success = uploader.publish_video(driver, self.account_name)
            if not success:
                self.upload_finished.emit(False, "发布视频失败")
                return
                
            self.upload_progress.emit(100)
            self.upload_finished.emit(True, f"视频上传成功! 商品: {product_info.get('goodsName', '未知商品')}")
            
        except Exception as e:
            self.upload_finished.emit(False, f"上传过程异常: {str(e)}")
    

    # 注意：fill_video_info, add_product_to_video, publish_video 方法已移至 core/bilibili_video_uploader.py


class BatchUploadThread(QThread):
    """批量上传线程"""
    upload_progress = pyqtSignal(int)
    upload_status = pyqtSignal(str)
    upload_finished = pyqtSignal(bool, str)
    browser_status_changed = pyqtSignal(str, bool)  # 账号名, 是否活跃
    file_deleted = pyqtSignal(str)  # 🎯 新增：文件删除信号，通知刷新文件列表
    account_progress_updated = pyqtSignal(str)  # 🎯 新增：账号进度更新信号，通知刷新进度显示
    
    def __init__(self, core_app, selected_accounts, video_files, video_dir, concurrent_browsers, videos_per_account):
        super().__init__()
        self.core_app = core_app
        self.selected_accounts = selected_accounts
        self.video_files = video_files
        self.video_dir = video_dir
        self.concurrent_browsers = concurrent_browsers
        self.videos_per_account = videos_per_account
        self.is_stopped = False
        self.uploaded_videos_md5 = self.load_uploaded_videos()
        
        # 🎯 修复：创建共享的上传器实例（但弹窗标志位与账号绑定）
        from core.bilibili_video_uploader import create_uploader
        self.shared_uploader = create_uploader(self.upload_status.emit, self.core_app.config_manager)
        
        # 🎯 弹窗处理标志位与账号绑定（浏览器重启时重置）
        self.account_popup_handled = {}  # {账号名: 是否已处理弹窗}
        
    def load_uploaded_videos(self):
        """加载已上传视频MD5记录"""
        try:
            with open('uploaded_videos.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('uploaded_videos', {})
        except:
            return {}
    
    def save_uploaded_videos(self):
        """保存已上传视频MD5记录"""
        try:
            data = {
                "uploaded_videos": self.uploaded_videos_md5,
                "description": "记录已上传视频的MD5值，防止重复上传导致封号",
                "created_at": "2025-01-25",
                "format": {
                    "video_md5": {
                        "filename": "原始文件名",
                        "upload_time": "上传时间戳",
                        "account": "上传账号",
                        "product_id": "商品ID",
                        "deleted": "是否已删除"
                    }
                }
            }
            with open('uploaded_videos.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存上传记录失败: {e}")
    
    def get_file_md5(self, file_path):
        """计算文件MD5值"""
        import hashlib
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return None
    
    def is_video_uploaded(self, file_path):
        """检查视频是否已上传"""
        md5_hash = self.get_file_md5(file_path)
        if not md5_hash:
            return False
        return md5_hash in self.uploaded_videos_md5
    
    def mark_video_uploaded(self, file_path, account, product_id):
        """标记视频已上传"""
        md5_hash = self.get_file_md5(file_path)
        if md5_hash:
            self.uploaded_videos_md5[md5_hash] = {
                "filename": os.path.basename(file_path),
                "upload_time": int(time.time()),
                "account": account,
                "product_id": product_id,
                "deleted": False
            }
            self.save_uploaded_videos()
    
    def delete_video_file(self, file_path):
        """删除视频文件 - 修复MD5记录更新"""
        try:
            # 🎯 先计算MD5，再删除文件
            md5_hash = self.get_file_md5(file_path)
            
            # 删除文件
            os.remove(file_path)
            
            # 更新MD5记录
            if md5_hash and md5_hash in self.uploaded_videos_md5:
                self.uploaded_videos_md5[md5_hash]["deleted"] = True
                self.save_uploaded_videos()
            
            # 🎯 文件删除后发出信号，通知刷新文件列表
            self.file_deleted.emit(file_path)
            return True
        except Exception as e:
            print(f"删除文件失败: {e}")
            return False
    
    def stop(self):
        """停止上传"""
        self.is_stopped = True
    
    def run(self):
        """执行批量上传 - 动态浏览器池管理"""
        try:
            from core.bilibili_product_manager import get_product_manager
            from queue import Queue
            
            product_manager = get_product_manager()
            
            self.upload_status.emit("🚀 开始批量上传流程...")
            
            # 🎯 第一步：全局浏览器初始化
            self.upload_status.emit("🔍 进行全局浏览器初始化...")
            initialization_success = self._perform_global_browser_initialization()
            
            if not initialization_success:
                self.upload_finished.emit(False, "全局浏览器初始化失败，无法继续批量上传")
                return
            
            self.upload_status.emit("✅ 全局浏览器初始化完成，开始账号浏览器创建...")
            
            # 获取所有未上传的视频文件
            available_videos = []
            for video_file in self.video_files:
                filename = os.path.basename(video_file)
                is_uploaded = self.is_video_uploaded(video_file)
                if not is_uploaded:
                    available_videos.append(video_file)
                    self.upload_status.emit(f"📹 待上传: {filename}")
                else:
                    self.upload_status.emit(f"⏭️ 已上传跳过: {filename}")
            
            if not available_videos:
                self.upload_finished.emit(False, "没有可上传的新视频")
                return
            
            self.upload_status.emit(f"📹 找到 {len(available_videos)} 个待上传视频")
            
            # 创建视频队列
            video_queue = Queue()
            for video in available_videos:
                video_queue.put(video)
            
            # 统计变量
            total_videos = len(available_videos)
            processed_videos = 0
            successful_uploads = 0
            deleted_videos = 0
            
            # 🎯 新增：预检查账号完成状态，过滤掉已完成的账号
            from core.account_manager import account_manager
            valid_accounts = []
            completed_accounts = []
            
            self.upload_status.emit("🔍 检查账号完成状态...")
            for account in self.selected_accounts:
                try:
                    status, completed, published = account_manager.get_account_progress(account, self.videos_per_account)
                    if completed:
                        completed_accounts.append(account)
                        self.upload_status.emit(f"⏭️ [{account}] 已完成目标 ({status})，跳过")
                    else:
                        valid_accounts.append(account)
                        self.upload_status.emit(f"📋 [{account}] 需要继续: {status}")
                except Exception as e:
                    # 如果检查失败，仍然加入队列，让后续处理决定
                    valid_accounts.append(account)
                    self.upload_status.emit(f"⚠️ [{account}] 状态检查失败: {e}，将继续处理")
            
            if not valid_accounts:
                self.upload_finished.emit(True, f"所有账号都已完成目标！已完成: {len(completed_accounts)} 个")
                return
            
            self.upload_status.emit(f"✅ 有效账号: {len(valid_accounts)} 个，已完成: {len(completed_accounts)} 个")
            
            # 账号队列和浏览器池管理（只处理有效账号）
            account_queue = Queue()
            for account in valid_accounts:
                account_queue.put(account)
            
            active_browsers = {}  # {account: browser}
            # 使用简单的标志位避免复杂线程同步
            browser_active_accounts = set()
            
            def process_single_account(account):
                """处理单个账号的所有视频"""
                nonlocal processed_videos, successful_uploads, deleted_videos
                
                browser = None
                try:
                    # 🎯 新增：处理前再次检查账号完成状态
                    try:
                        status, completed, published = account_manager.get_account_progress(account, self.videos_per_account)
                        if completed:
                            self.upload_status.emit(f"⏭️ [{account}] 处理前检查发现已完成目标 ({status})，跳过")
                            return
                        else:
                            self.upload_status.emit(f"📋 [{account}] 开始处理，当前进度: {status}")
                    except Exception as e:
                        self.upload_status.emit(f"⚠️ [{account}] 状态检查失败: {e}，继续处理")
                    
                    # 启动浏览器
                    account_obj = self.core_app.account_manager.get_account(account)
                    if not account_obj:
                        self.upload_status.emit(f"❌ 账号 {account} 不存在，跳过")
                        return
                    
                    browser = self.ensure_browser_ready(account, account_obj)
                    if not browser:
                        self.upload_status.emit(f"❌ 账号 {account} 浏览器启动失败，跳过")
                        # 🎯 浏览器启动失败时发送状态变化信号
                        self.browser_status_changed.emit(account, False)
                        return
                    
                    # 加入活跃浏览器池
                    active_browsers[account] = browser
                    browser_active_accounts.add(account)
                    self.upload_status.emit(f"✅ 账号 {account} 浏览器就绪 (当前活跃: {len(active_browsers)}/{self.concurrent_browsers})")
                    
                    # 通知主界面刷新状态
                    self.browser_status_changed.emit(account, True)
                    
                    uploaded_count = 0
                    
                    # 🎯 修复：允许每个账号上传多个视频（用户需求：30个视频循环上传）
                    videos_processed_by_account = 0
                    while videos_processed_by_account < self.videos_per_account and not video_queue.empty():
                        if self.is_stopped:
                            break
                        
                        # 🎯 新增：每个视频处理前检查账号是否已达目标
                        try:
                            status, completed, published = account_manager.get_account_progress(account, self.videos_per_account)
                            if completed:
                                self.upload_status.emit(f"⏭️ [{account}] 视频处理前检查发现已完成目标 ({status})，停止处理")
                                break
                        except Exception as e:
                            self.upload_status.emit(f"⚠️ [{account}] 视频前状态检查失败: {e}")
                        
                        
                        try:
                            video_path = video_queue.get_nowait()
                        except:
                            break  # 队列为空
                        
                        filename = os.path.basename(video_path)
                        processed_videos += 1
                        videos_processed_by_account += 1
                        
                        self.upload_status.emit(f"📹 [{account}] 第{videos_processed_by_account}个视频: {filename} ({processed_videos}/{total_videos})")
                        
                        # 实时验证商品
                        product_id = product_manager.extract_product_id_from_filename(filename)
                        if not product_id:
                            self.upload_status.emit(f"❌ [{account}] {filename} 无商品ID，删除")
                            if self.delete_video_file(video_path):
                                deleted_videos += 1
                            continue
                        
                        # 验证商品是否在B站联盟库中
                        cookies = product_manager.get_cookies_from_account(account_obj)
                        if not cookies:
                            self.upload_status.emit(f"❌ [{account}] 无法获取Cookie")
                            continue
                        
                        jd_url = product_manager.build_jd_url(product_id)
                        success, product_info = product_manager.distinguish_product(jd_url, cookies)
                        
                        if not success or not product_info:
                            self.upload_status.emit(f"❌ [{account}] 商品{product_id}不在库中，删除{filename}")
                            if self.delete_video_file(video_path):
                                deleted_videos += 1
                            continue
                        
                        # 商品验证通过，开始上传
                        self.upload_status.emit(f"🚀 [{account}] 上传第{videos_processed_by_account}个视频: {filename}")
                        
                        # 调用实际上传逻辑
                        upload_success = self.perform_actual_upload(account_obj, browser, video_path, product_info)
                        
                        if upload_success:
                            successful_uploads += 1
                            uploaded_count += 1
                            self.mark_video_uploaded(video_path, account, product_id)
                            # 删除视频文件并更新计数器
                            if self.delete_video_file(video_path):
                                deleted_videos += 1
                            self.upload_status.emit(f"✅ [{account}] 第{videos_processed_by_account}个视频成功: {filename}")
                            
                            # 🎯 新增：检查账号是否已完成当日目标
                            try:
                                from core.account_manager import account_manager
                                status, completed, published = account_manager.get_account_progress(account, self.videos_per_account)
                                if completed:
                                    self.upload_status.emit(f"🎉 [{account}] 已完成当日目标 ({published}/{self.videos_per_account})，停止继续上传")
                                    break  # 跳出视频循环，该账号完成任务
                                else:
                                    self.upload_status.emit(f"📊 [{account}] 当前进度: {status}")
                            except Exception as e:
                                self.upload_status.emit(f"⚠️ [{account}] 检查完成状态失败: {e}")
                        else:
                            self.upload_status.emit(f"❌ [{account}] 第{videos_processed_by_account}个视频失败: {filename}")
                        
                        # 更新进度
                        progress = int((processed_videos / total_videos) * 100)
                        self.upload_progress.emit(progress)
                        
                        # 🎯 修复：不立即退出，继续处理下一个视频
                        # 每个视频完成后短暂休息，让界面更新
                        time.sleep(1)
                        
                        # 🎯 每5个视频后重新导航到上传页面，保持浏览器状态
                        if videos_processed_by_account % 5 == 0:
                            try:
                                self.upload_status.emit(f"🔄 [{account}] 第{videos_processed_by_account}个视频完成，刷新浏览器状态...")
                                browser.get("https://member.bilibili.com/platform/upload/video/frame")
                                time.sleep(2)
                            except Exception as refresh_error:
                                self.upload_status.emit(f"⚠️ [{account}] 刷新浏览器失败: {refresh_error}")
                        
                        # 继续下一个视频的循环
                    
                    self.upload_status.emit(f"🏁 [{account}] 完成上传 {uploaded_count} 个视频")
                    
                finally:
                    # 🎯 优化：关闭浏览器并释放端口
                    if browser:
                        try:
                            if account in active_browsers:
                                del active_browsers[account]
                            browser_active_accounts.discard(account)
                            self.upload_status.emit(f"🔒 关闭账号 {account} 的浏览器 (当前活跃: {len(active_browsers)}/{self.concurrent_browsers})")
                            
                            # 使用BrowserManager的方法来正确关闭浏览器并释放端口
                            self.core_app.browser_manager.close_driver(browser, account)
                            
                            # 清除账号对象中的浏览器实例引用
                            account_obj = self.core_app.account_manager.get_account(account)
                            if account_obj:
                                account_obj.browser_instance = None
                            
                            # 通知主界面刷新状态
                            self.browser_status_changed.emit(account, False)
                                
                        except Exception as e:
                            self.upload_status.emit(f"⚠️ 关闭浏览器失败: {account} - {e}")
            
            # 使用统一的线程管理器
            
            # 创建结果队列来接收完成的任务
            from queue import Queue
            completion_queue = Queue()
            
            def account_wrapper(account):
                """包装函数，处理完成后通知"""
                try:
                    process_single_account(account)
                    completion_queue.put(('completed', account, None))
                except Exception as e:
                    completion_queue.put(('error', account, str(e)))
            
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.concurrent_browsers) as executor:
                active_futures = {}  # {account: future}
                
                # 启动初始的浏览器（使用有效账号数量）
                for _ in range(min(self.concurrent_browsers, len(valid_accounts))):
                    if account_queue.empty():
                        break
                    account = account_queue.get()
                    future = executor.submit(account_wrapper, account)
                    active_futures[account] = future
                    self.upload_status.emit(f"🚀 启动账号: {account} (活跃: {len(active_futures)}/{self.concurrent_browsers})")
                
                # 监控完成状态并动态添加新任务
                while active_futures or not account_queue.empty():
                    if self.is_stopped:
                        break
                    
                    try:
                        # 等待任务完成
                        status, completed_account, error = completion_queue.get(timeout=1)
                        
                        # 移除已完成的任务
                        if completed_account in active_futures:
                            del active_futures[completed_account]
                        
                        if status == 'completed':
                            self.upload_status.emit(f"✅ 账号 {completed_account} 处理完成")
                        else:
                            self.upload_status.emit(f"❌ 账号 {completed_account} 处理失败: {error}")
                        
                        # 如果还有账号需要处理，启动新的浏览器
                        if not account_queue.empty():
                            account = account_queue.get()
                            future = executor.submit(account_wrapper, account)
                            active_futures[account] = future
                            self.upload_status.emit(f"🔄 启动下一个账号: {account} (活跃: {len(active_futures)}/{self.concurrent_browsers})")
                    
                    except Exception:  # Queue.Empty异常
                        # 超时，继续等待
                        continue
            
            # 输出最终结果
            message = f"批量上传完成: 处理 {processed_videos} 个视频, 成功 {successful_uploads} 个, 删除 {deleted_videos} 个"
            self.upload_finished.emit(True, message)
            
        except Exception as e:
            self.upload_finished.emit(False, f"批量上传异常: {str(e)}")
    
    def perform_actual_upload(self, account_obj, browser, video_path, product_info):
        """执行实际上传逻辑"""
        try:
            # 🎯 修复：使用共享的上传器实例，保持弹窗标志位
            uploader = self.shared_uploader
            
            # 1. 真实上传视频文件（传递账号信息用于弹窗标志位）
            account_name = account_obj.username if hasattr(account_obj, 'username') else 'unknown'
            
            # 检查是否需要处理弹窗（与账号绑定）
            need_popup_handling = account_name not in self.account_popup_handled
            
            if not uploader.upload_video(browser, video_path, account_name, need_popup_handling):
                return False
            
            # 标记该账号已处理过弹窗
            if need_popup_handling:
                self.account_popup_handled[account_name] = True
            
            # 2. 填写视频信息
            filename = os.path.basename(video_path)
            
            # 🎯 修复：正确提取标题，从文件名中去除商品ID部分
            filename_without_ext = filename.rsplit('.', 1)[0]  # 去掉扩展名
            if '----' in filename_without_ext:
                # 文件名格式：商品ID----标题.mp4
                extracted_title = filename_without_ext.split('----', 1)[1]
                self.upload_status.emit(f"📝 提取标题: {extracted_title}")
            else:
                # 如果没有----分隔符，直接使用文件名（去掉扩展名）
                extracted_title = filename_without_ext
                self.upload_status.emit(f"📝 使用完整文件名作为标题: {extracted_title}")
            
            upload_settings = {
                "title": extracted_title,  # 🎯 使用正确提取的标题
                "tags": ["带货", "推荐"],
                "description": f"优质商品推荐: {product_info.get('goodsName', '精选商品')}",
                "title_template": "{filename}"  # 保持与uploader的兼容性
            }
            if not uploader.fill_video_info(browser, filename, upload_settings, product_info):
                return False
            
            # 3. 添加商品
            if not uploader.add_product_to_video(browser, filename, product_info):
                return False
            
            # 4. 发布视频
            if not uploader.publish_video(browser, account_name):
                return False
            
            # 🎯 新增：投稿成功后发出账号进度更新信号
            self.account_progress_updated.emit(account_name)
                
            return True
            
        except Exception as e:
            self.upload_status.emit(f"上传异常: {str(e)}")
            return False

    def ensure_browser_ready(self, account_name, account_obj):
        """确保浏览器就绪 - 修复版：正确的初始化流程"""
        try:
            # 检查是否有现有浏览器实例
            if hasattr(account_obj, 'browser_instance') and account_obj.browser_instance:
                try:
                    # 检查浏览器是否还活着
                    current_url = account_obj.browser_instance.current_url
                    self.upload_status.emit(f"🔄 [{account_name}] 复用现有浏览器")
                    
                    # 🎯 确保在正确页面：如果不在上传页面，重新走完整流程
                    if "member.bilibili.com" not in current_url or "upload" not in current_url:
                        self.upload_status.emit(f"🔄 [{account_name}] 重新初始化浏览器流程...")
                        # 先回到主页恢复登录状态
                        account_obj.browser_instance.get("https://www.bilibili.com")
                        time.sleep(2)
                        
                        # 恢复cookie
                        if hasattr(account_obj, 'cookies') and account_obj.cookies:
                            self._restore_cookies(account_obj.browser_instance, account_obj.cookies, account_name)
                        
                        # 导航到上传页面
                        self.upload_status.emit(f"🌐 [{account_name}] 导航到上传页面...")
                        account_obj.browser_instance.get("https://member.bilibili.com/platform/upload/video/frame")
                        time.sleep(3)
                    
                    return account_obj.browser_instance
                except:
                    # 浏览器已死，清除引用
                    account_obj.browser_instance = None
            
            # 🎯 正确流程：启动新浏览器
            self.upload_status.emit(f"🚀 [{account_name}] 初始化浏览器...")
            
            # 获取账号指纹
            fingerprint = None
            if account_obj and hasattr(account_obj, 'fingerprint'):
                fingerprint = account_obj.fingerprint
            
            # 🎯 步骤1：创建浏览器，先启动到主页（不是上传页面）
            browser = self.core_app.browser_manager.create_driver(
                fingerprint=fingerprint,
                headless=False,
                account_name=account_name,
                start_url="https://www.bilibili.com"  # 🚀 先启动到主页
            )
            
            if not browser:
                self.upload_status.emit(f"❌ [{account_name}] 浏览器创建失败")
                return None
            
            # 保存浏览器实例到账号对象
            account_obj.browser_instance = browser
            self.upload_status.emit(f"✅ [{account_name}] 浏览器初始化完成")
            
            # 🎯 步骤2：恢复cookie确保登录状态
            if hasattr(account_obj, 'cookies') and account_obj.cookies:
                if self._restore_cookies(browser, account_obj.cookies, account_name):
                    self.upload_status.emit(f"✅ [{account_name}] 登录状态已恢复")
                else:
                    self.upload_status.emit(f"⚠️ [{account_name}] 登录状态恢复失败，但继续流程")
            else:
                self.upload_status.emit(f"⚠️ [{account_name}] 没有保存的登录信息")
            
            # 🎯 步骤3：导航到上传页面
            self.upload_status.emit(f"🌐 [{account_name}] 导航到上传页面...")
            try:
                browser.get("https://member.bilibili.com/platform/upload/video/frame")
                time.sleep(3)  # 等待页面加载
                
                # 验证是否成功到达上传页面
                current_url = browser.current_url
                if "member.bilibili.com" in current_url and "upload" in current_url:
                    self.upload_status.emit(f"✅ [{account_name}] 已到达上传页面")
                else:
                    self.upload_status.emit(f"⚠️ [{account_name}] 当前URL: {current_url}")
                    
            except Exception as nav_error:
                self.upload_status.emit(f"⚠️ [{account_name}] 导航到上传页面失败: {nav_error}")
            
            return browser
            
        except Exception as e:
            self.upload_status.emit(f"❌ [{account_name}] 浏览器准备失败: {str(e)}")
            # 🎯 浏览器准备失败时发送状态变化信号
            self.browser_status_changed.emit(account_name, False)
            return None
    
    def _restore_cookies(self, browser, cookies, account_name):
        """恢复cookies的独立方法"""
        try:
            self.upload_status.emit(f"🔑 [{account_name}] 恢复登录状态...")
            
            # 清除现有cookies
            browser.delete_all_cookies()
            
            # 添加保存的cookies
            cookie_count = 0
            for cookie in cookies:
                try:
                    browser.add_cookie(cookie)
                    cookie_count += 1
                except Exception as e:
                    # 单个cookie恢复失败不影响整体
                    continue
            
            if cookie_count > 0:
                # 刷新页面使cookies生效
                browser.refresh()
                time.sleep(3)
                self.upload_status.emit(f"✅ [{account_name}] 已恢复{cookie_count}个cookie")
                return True
            else:
                self.upload_status.emit(f"⚠️ [{account_name}] 没有有效的cookie可恢复")
                return False
                
        except Exception as e:
            self.upload_status.emit(f"⚠️ [{account_name}] 恢复cookie失败: {e}")
            return False

    def _perform_global_browser_initialization(self):
        """执行全局浏览器初始化 - 先弹出空白浏览器检测环境，然后关闭"""
        initialization_browser = None
        try:
            self.upload_status.emit("🔧 启动初始化浏览器...")
            
            # 🎯 创建初始化浏览器（不指定起始URL，会是data:,空白页）
            initialization_browser = self.core_app.browser_manager.create_driver(
                fingerprint=None,
                headless=False,
                account_name="__global_init__",  # 特殊的初始化标识
                start_url=None  # 不指定URL，保持data:,空白页
            )
            
            if not initialization_browser:
                self.upload_status.emit("❌ 初始化浏览器创建失败")
                return False
            
            self.upload_status.emit("✅ 初始化浏览器已启动 (data:, 空白页)")
            
            # 🎯 进行基本功能测试
            self.upload_status.emit("🧪 测试浏览器基本功能...")
            
            try:
                # 测试基本功能
                current_url = initialization_browser.current_url
                page_title = initialization_browser.title
                
                # 测试导航功能
                initialization_browser.get("https://www.bilibili.com")
                time.sleep(3)
                
                # 验证导航成功
                final_url = initialization_browser.current_url
                if "bilibili.com" in final_url:
                    self.upload_status.emit("✅ 浏览器导航功能正常")
                else:
                    self.upload_status.emit(f"⚠️ 浏览器导航异常，URL: {final_url}")
                
                # 测试JavaScript执行
                js_result = initialization_browser.execute_script("return 'JS_OK';")
                if js_result == "JS_OK":
                    self.upload_status.emit("✅ JavaScript执行功能正常")
                else:
                    self.upload_status.emit("⚠️ JavaScript执行功能异常")
                
            except Exception as test_error:
                self.upload_status.emit(f"⚠️ 浏览器功能测试失败: {test_error}")
                # 继续流程，不因为测试失败而中断
            
            # 🎯 等待用户观察（可选）
            self.upload_status.emit("⏳ 初始化完成，准备关闭初始化浏览器...")
            time.sleep(2)  # 短暂等待让用户看到初始化过程
            
            return True
            
        except Exception as e:
            self.upload_status.emit(f"❌ 全局浏览器初始化失败: {e}")
            return False
            
        finally:
            # 🎯 关键：确保初始化浏览器被正确关闭
            if initialization_browser:
                try:
                    self.upload_status.emit("🔒 关闭初始化浏览器...")
                    self.core_app.browser_manager.close_driver(initialization_browser, "__global_init__")
                    self.upload_status.emit("✅ 初始化浏览器已关闭")
                except Exception as close_error:
                    self.upload_status.emit(f"⚠️ 关闭初始化浏览器失败: {close_error}")

    def check_login_status(self, browser, account_obj=None):
        """检查登录状态 - 优化版本，支持恢复cookies"""
        try:
            # 访问B站主页
            browser.get("https://www.bilibili.com")
            time.sleep(2)
            
            # 如果有账号信息，尝试恢复cookies
            if account_obj and hasattr(account_obj, 'cookies') and account_obj.cookies:
                try:
                    # 清除现有cookies
                    browser.delete_all_cookies()
                    
                    # 恢复保存的cookies
                    for cookie in account_obj.cookies:
                        try:
                            browser.add_cookie(cookie)
                        except Exception as e:
                            # 单个cookie恢复失败不影响整体
                            continue
                    
                    # 刷新页面使cookies生效
                    browser.refresh()
                    time.sleep(3)
                    
                except Exception as e:
                    print(f"恢复cookies失败: {e}")
            
            # 检查是否有登录标识
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.wait import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                # 检查多个可能的登录元素
                login_selectors = [
                    ".header-avatar-wrap",  # 头像容器
                    ".bili-avatar",         # 头像元素
                    ".user-con",            # 用户信息容器
                    ".user-name",           # 用户名
                    ".nav-user-info"        # 导航用户信息
                ]
                
                for selector in login_selectors:
                    try:
                        WebDriverWait(browser, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        return True
                    except:
                        continue
                
                # 都没找到，可能没登录
                return False
                
            except Exception as e:
                print(f"登录状态检查异常: {e}")
                return False
                
        except Exception as e:
            print(f"检查登录状态失败: {e}")
            return False

    def simulate_upload(self, account, video_path, product_info):
        """模拟上传过程（用于测试）"""
        filename = os.path.basename(video_path)
        self.upload_status.emit(f"🎯 [{account}] 模拟上传: {filename}")
        time.sleep(2)  # 模拟耗时
        return True


class LicenseWorker(QThread):
    """许可证检查工作线程"""
    license_checked = pyqtSignal(bool, str, str)  # is_valid, license_info, error_msg
    
    def __init__(self, license_system, license_file_path):
        super().__init__()
        self.license_system = license_system
        self.license_file_path = license_file_path
        
    def run(self):
        try:
            if os.path.exists(self.license_file_path):
                with open(self.license_file_path, 'r', encoding='utf-8') as f:
                    license_content = f.read().strip()
                    
                result = self.license_system.verify_license(license_content)
                if result['valid']:
                    # 构造许可证信息字符串
                    info = {
                        'remaining_days': result['remaining_days'],
                        'expire_date': result['expire_date'],
                        'user_info': result.get('user_info', ''),
                        'hardware_fp': result['hardware_fp']
                    }
                    self.license_checked.emit(True, str(info), "")
                else:
                    self.license_checked.emit(False, "", f"许可证验证失败: {result['error']}")
            else:
                self.license_checked.emit(False, "", "未找到许可证文件")
        except Exception as e:
            self.license_checked.emit(False, "", f"许可证检查出错: {str(e)}")

class FileOperationWorker(QThread):
    """文件操作工作线程"""
    operation_completed = pyqtSignal(bool, str)  # success, message/data
    
    def __init__(self, operation_type, *args):
        super().__init__()
        self.operation_type = operation_type
        self.args = args
        
    def run(self):
        try:
            if self.operation_type == "save_config":
                config, config_file = self.args
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                self.operation_completed.emit(True, "配置保存成功")
                
            elif self.operation_type == "load_config":
                config_file = self.args[0]
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    self.operation_completed.emit(True, json.dumps(config))
                else:
                    self.operation_completed.emit(False, "配置文件不存在")
                    
        except Exception as e:
            self.operation_completed.emit(False, f"文件操作失败: {str(e)}")

class PeriodicCheckWorker(QThread):
    """定期安全检查工作线程"""
    check_completed = pyqtSignal(bool, str)  # is_valid, message
    
    def __init__(self, license_system, license_file_path):
        super().__init__()
        self.license_system = license_system
        self.license_file_path = license_file_path
        self.running = True
        
    def run(self):
        check_interval = 5 * 60  # 5分钟间隔
        elapsed_time = 0
        
        while self.running:
            try:
                # 使用短时间睡眠，每1秒检查一次是否需要停止
                self.msleep(1000)  # 1秒
                elapsed_time += 1
                
                if not self.running:
                    break
                    
                # 只有到达检查间隔时才执行许可证检查
                if elapsed_time >= check_interval:
                    elapsed_time = 0  # 重置计时器
                    
                    # 检查许可证文件是否存在
                    if not os.path.exists(self.license_file_path):
                        self.check_completed.emit(False, "许可证文件丢失")
                        continue
                        
                    # 验证许可证
                    try:
                        with open(self.license_file_path, 'r', encoding='utf-8') as f:
                            license_content = f.read().strip()
                        
                        result = self.license_system.verify_license(license_content)
                        if not result['valid']:
                            self.check_completed.emit(False, f"许可证失效: {result['error']}")
                        else:
                            self.check_completed.emit(True, "许可证正常")
                            
                    except Exception as e:
                        self.check_completed.emit(False, f"许可证验证出错: {str(e)}")
                    
            except Exception as e:
                self.check_completed.emit(False, f"安全检查出错: {str(e)}")
                
    def stop(self):
        self.running = False
        self.quit()
        self.wait()


class MainWindow(QMainWindow):
    """主窗口 - 简化版本"""
    
    def __init__(self):
        super().__init__()
        self.core_app = BilibiliApp()
        
        # 许可证系统
        from core.license_system import LicenseSystem
        self.license_system = LicenseSystem()
        self.license_info = None
        self.is_licensed = False  # 授权状态
        self._security_token = None  # 安全令牌
        self._last_check_time = 0  # 上次检查时间
        
        # 线程支持
        self.license_worker = None
        self.file_worker = None
        self.periodic_checker = None
        
        # 🎯 启动时许可证检查，重新启用
        self.check_license_on_startup_async()  # 重新启用许可证检查
        
        # 🎯 临时禁用定期安全检查线程，防止程序崩溃
        # self.setup_security_timer_async()  # 暂时注释掉
        
        self.setWindowTitle("B站带货助手 v2.0 - 硬件绑定版")
        
        # 🎯 设置程序图标
        self.set_window_icon()
        
        # 🎯 窗口居中显示
        if UIConfig.WINDOW_X == -1 or UIConfig.WINDOW_Y == -1:
            # 计算屏幕中央位置
            from PyQt5.QtWidgets import QDesktopWidget
            desktop = QDesktopWidget()
            screen_rect = desktop.screenGeometry()
            screen_center_x = screen_rect.width() // 2
            screen_center_y = screen_rect.height() // 2
            
            # 计算窗口左上角位置（让窗口中心对齐屏幕中心）
            window_x = screen_center_x - UIConfig.WINDOW_WIDTH // 2
            window_y = screen_center_y - UIConfig.WINDOW_HEIGHT // 2
            
            self.setGeometry(window_x, window_y, UIConfig.WINDOW_WIDTH, UIConfig.WINDOW_HEIGHT)
        else:
            # 使用配置的固定位置
            self.setGeometry(UIConfig.WINDOW_X, UIConfig.WINDOW_Y, UIConfig.WINDOW_WIDTH, UIConfig.WINDOW_HEIGHT)
        
        # 创建中心部件和标签页
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        
        # 添加标签页
        self.tab_widget.addTab(self.create_account_tab(), UIConfig.UI_TEXT['account_management'])
        self.tab_widget.addTab(self.create_license_tab(), "🔐 许可证管理")
        self.tab_widget.addTab(self.create_upload_tab(), UIConfig.UI_TEXT['browser_upload'])
        self.tab_widget.addTab(self.create_log_tab(), UIConfig.UI_TEXT['run_log'])
        
        layout.addWidget(self.tab_widget)
        
        # 创建状态栏
        self.statusBar().showMessage("程序已启动")
        
        # 创建专用浏览器状态监控器
        from core.browser_status_monitor import get_browser_status_monitor
        self.browser_monitor = get_browser_status_monitor()
        
        # 连接浏览器状态监控器信号
        self.browser_monitor.browser_status_changed.connect(self.on_browser_status_changed)
        
        # 🎯 启用浏览器状态监控，使用安全的定时器机制
        try:
            self.setup_browser_status_timer()  # 启用状态监控
            self.log_message("🔄 浏览器状态同步已启用", "INFO")
        except Exception as e:
            self.log_message(f"⚠️ 浏览器状态监控启动失败: {e}", "WARNING")
        
        self.load_data()

        self.log_message(f"{Config.APP_NAME} v{Config.APP_VERSION} 启动完成")
    
    def set_window_icon(self):
        """设置窗口图标"""
        try:
            # 优先使用ICO文件（Windows标准）
            icon_paths = [
                "icons/app_icon.ico",          # 项目目录下的图标
                "icons/icon_48x48.png",        # PNG备用图标
                "icons/icon_32x32.png",        # 更小的PNG图标
            ]
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    try:
                        icon = QIcon(icon_path)
                        if not icon.isNull():  # 检查图标是否有效
                            self.setWindowIcon(icon)
                            self.log_message(f"✅ 已设置程序图标: {icon_path}", "INFO")
                            return
                    except Exception as e:
                        self.log_message(f"⚠️ 加载图标失败 {icon_path}: {e}", "WARNING")
                        continue
            
            # 如果没有找到图标文件，使用默认图标
            self.log_message("⚠️ 未找到图标文件，使用默认图标", "WARNING")
            
        except Exception as e:
            self.log_message(f"⚠️ 设置图标时出错: {e}", "WARNING")
    
    def create_account_tab(self):
        """创建账号管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)  # 🎯 减少整体间距
        layout.setContentsMargins(8, 8, 8, 8)  # 🎯 减少边距
        
        # === 账号操作控制面板 ===
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.StyledPanel)
        control_frame.setStyleSheet(UIStyles.get_frame_style())
        control_layout = QHBoxLayout()
        
        # 账号操作区
        account_group = QGroupBox("👤 账号操作")
        account_layout = QHBoxLayout()
        account_layout.setSpacing(10)  # 🎯 设置统一间距
        account_layout.setContentsMargins(10, 10, 10, 10)  # 🎯 减少内边距
        
        add_account_btn = QPushButton(UIConfig.UI_TEXT['add_account'])
        add_account_btn.setStyleSheet(UIStyles.get_button_style('success'))
        add_account_btn.clicked.connect(self.add_account)
        
        login_account_btn = QPushButton(UIConfig.UI_TEXT['login_account'])
        login_account_btn.setStyleSheet(UIStyles.get_button_style('primary'))
        login_account_btn.clicked.connect(self.login_account)
        
        remove_account_btn = QPushButton(UIConfig.UI_TEXT['remove_account'])
        remove_account_btn.setStyleSheet(UIStyles.get_button_style('danger'))
        remove_account_btn.clicked.connect(self.remove_account)
        
        # 浏览器诊断按钮
        diagnose_browser_btn = QPushButton("🔍 浏览器诊断")
        diagnose_browser_btn.setStyleSheet(UIStyles.get_button_style('warning'))
        diagnose_browser_btn.clicked.connect(self.diagnose_browser)
        
        account_layout.addWidget(add_account_btn)
        account_layout.addWidget(login_account_btn)
        account_layout.addWidget(remove_account_btn)
        account_layout.addWidget(diagnose_browser_btn)
        account_group.setLayout(account_layout)
        
        # 批量上传控制区
        batch_group = QGroupBox("🚀 批量上传控制")
        batch_layout = QVBoxLayout()
        batch_layout.setSpacing(8)  # 🎯 减少行间距，让布局更紧凑
        batch_layout.setContentsMargins(10, 10, 10, 10)  # 🎯 减少内边距
        
        # 设置行
        settings_row = QHBoxLayout()
        settings_row.setSpacing(10)  # 🎯 设置元素间距
        
        # 同时多开浏览器数量
        settings_row.addWidget(QLabel("同时打开浏览器数量:"))
        self.concurrent_browsers_input = QLineEdit("2")
        self.concurrent_browsers_input.setMaximumWidth(80)
        self.concurrent_browsers_input.setPlaceholderText("数量")
        self.concurrent_browsers_input.textChanged.connect(self.save_ui_settings)
        settings_row.addWidget(self.concurrent_browsers_input)
        
        settings_row.addWidget(QLabel("每个账号上传视频数量:"))
        self.videos_per_account_input = QLineEdit("1")
        self.videos_per_account_input.setMaximumWidth(80)
        self.videos_per_account_input.setPlaceholderText("数量")
        self.videos_per_account_input.textChanged.connect(self.save_ui_settings)
        # 🎯 新增：数量改变时实时更新账号进度显示
        self.videos_per_account_input.textChanged.connect(self.on_videos_per_account_changed)
        settings_row.addWidget(self.videos_per_account_input)
        
        settings_row.addStretch()
        batch_layout.addLayout(settings_row)
        
        # 🎯 新增：第二行 - 等待时间设置 + 操作按钮
        settings_row2 = QHBoxLayout()
        settings_row2.setSpacing(10)  # 🎯 设置元素间距
        
        # 等待时间设置
        settings_row2.addWidget(QLabel("投稿成功等待:"))
        self.success_wait_time_spinbox = QSpinBox()
        self.success_wait_time_spinbox.setRange(0, 999)  # 0-999秒，支持3位数
        self.success_wait_time_spinbox.setSuffix(" 秒")
        self.success_wait_time_spinbox.setValue(2)  # 默认2秒
        self.success_wait_time_spinbox.setMaximumWidth(100)  # 增加宽度以支持3位数
        self.success_wait_time_spinbox.setStyleSheet("font-size: 12px;")
        self.success_wait_time_spinbox.setToolTip("检测到投稿成功标识后的等待时间，用于确保页面状态稳定（0-999秒）")
        self.success_wait_time_spinbox.valueChanged.connect(self.on_success_wait_time_changed)
        settings_row2.addWidget(self.success_wait_time_spinbox)
        
        # 🎯 添加弹性间距，让按钮右对齐与上面的按钮位置保持一致
        settings_row2.addStretch()
        
        # 操作按钮
        self.start_batch_upload_btn = QPushButton("🚀 一键开始")
        self.start_batch_upload_btn.setStyleSheet(UIStyles.get_button_style('success'))
        self.start_batch_upload_btn.clicked.connect(self.start_batch_upload)
        settings_row2.addWidget(self.start_batch_upload_btn)
        
        self.stop_batch_upload_btn = QPushButton("⏹️ 停止上传")
        self.stop_batch_upload_btn.setStyleSheet(UIStyles.get_button_style('danger'))
        self.stop_batch_upload_btn.setEnabled(False)
        self.stop_batch_upload_btn.clicked.connect(self.stop_batch_upload)
        settings_row2.addWidget(self.stop_batch_upload_btn)
        
        batch_layout.addLayout(settings_row2)
        
        batch_group.setLayout(batch_layout)
        
        # 添加到控制布局
        control_layout.setSpacing(10)  # 🎯 减少组之间的间距，让布局更紧凑
        control_layout.setContentsMargins(8, 8, 8, 8)  # 🎯 减少外边距
        control_layout.addWidget(account_group)
        control_layout.addWidget(batch_group)
        control_layout.addStretch()
        control_frame.setLayout(control_layout)
        layout.addWidget(control_frame)
        
        # === 账号状态表格 ===
        table_frame = QFrame()
        table_frame.setFrameStyle(QFrame.StyledPanel)
        table_layout = QVBoxLayout()
        table_layout.setSpacing(8)  # 🎯 减少表格区域间距
        table_layout.setContentsMargins(8, 8, 8, 8)  # 🎯 减少内边距
        
        # 表格标题和全选控制
        title_row = QHBoxLayout()
        table_title = QLabel("👤 账号状态管理")
        table_title.setStyleSheet(UIStyles.get_title_style())
        title_row.addWidget(table_title)
        
        # 全选控制
        self.select_all_checkbox = QCheckBox("全选")
        self.select_all_checkbox.setChecked(False)  # 🎯 修改：默认不选中，会根据保存的状态调整
        self.select_all_checkbox.clicked.connect(self.toggle_select_all)
        title_row.addWidget(self.select_all_checkbox)
        
        title_row.addStretch()
        table_layout.addLayout(title_row)
        
        # 账号表格
        self.account_table = QTableWidget()
        self.account_table.setColumnCount(8)
        self.account_table.setHorizontalHeaderLabels([
            "选择", "账号名", "登录状态", "浏览器状态", "最后登录", "今日已发", "进度状态", "备注"
        ])
        
        # 设置表格样式
        self.account_table.setStyleSheet(UIStyles.get_table_style())
        
        self.account_table.setAlternatingRowColors(True)
        self.account_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # 设置列宽
        header = self.account_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.resizeSection(0, 60)  # 选择列
        header.resizeSection(1, UIConfig.TABLE_COLUMN_WIDTHS['account_name'])
        header.resizeSection(2, UIConfig.TABLE_COLUMN_WIDTHS['login_status'])
        header.resizeSection(3, UIConfig.TABLE_COLUMN_WIDTHS['browser_status'])
        header.resizeSection(4, UIConfig.TABLE_COLUMN_WIDTHS['last_login'])
        header.resizeSection(5, 80)  # 今日已发列
        header.resizeSection(6, 120)  # 进度状态列
        
        table_layout.addWidget(self.account_table)
        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)
        
        # === 统计信息栏 ===
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.StyledPanel)
        stats_frame.setStyleSheet(UIStyles.get_stats_frame_style())
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(8, 6, 8, 6)  # 🎯 减少统计栏边距
        
        self.account_stats_label = QLabel("账号统计：等待加载...")
        self.account_stats_label.setStyleSheet("font-weight: bold; color: #495057;")
        
        stats_layout.addWidget(self.account_stats_label)
        stats_layout.addStretch()
        stats_frame.setLayout(stats_layout)
        layout.addWidget(stats_frame)
        
        widget.setLayout(layout)
        return widget
    
    def create_license_tab(self):
        """创建许可证管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # === 许可证状态区域 ===
        status_group = QGroupBox("🔐 许可证状态")
        status_layout = QVBoxLayout()
        
        # 许可证状态标签
        if self.license_info and self.is_licensed:
            status_text = f"✅ 许可证有效 | 剩余天数: {self.license_info['remaining_days']} 天 | 过期时间: {self.license_info['expire_date']}"
            if self.license_info.get('user_info'):
                status_text += f" | 用户: {self.license_info['user_info']}"
            status_color = "color: green;"
        else:
            status_text = "⚠️ 试用模式 | 功能受限 | 请激活许可证获得完整功能"
            status_color = "color: orange;"
        
        self.license_status_label = QLabel(status_text)
        self.license_status_label.setStyleSheet(f"padding: 10px; font-weight: bold; {status_color}")
        status_layout.addWidget(self.license_status_label)
        
        # 如果是试用模式，显示限制说明
        if not self.is_licensed:
            trial_info = QLabel(self.get_trial_limitations_text())
            trial_info.setStyleSheet("""
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 15px;
                margin: 10px 0;
                color: #856404;
                font-size: 12px;
            """)
            trial_info.setWordWrap(True)
            status_layout.addWidget(trial_info)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # === 硬件指纹区域 ===
        hardware_group = QGroupBox("💻 硬件指纹")
        hardware_layout = QVBoxLayout()
        
        # 硬件指纹显示
        hardware_fp = self.license_system.get_hardware_fingerprint()
        
        hardware_info_layout = QHBoxLayout()
        hardware_info_layout.addWidget(QLabel("当前硬件指纹:"))
        
        self.hardware_fp_edit = QLineEdit(hardware_fp)
        self.hardware_fp_edit.setReadOnly(True)
        self.hardware_fp_edit.setFont(QFont("Consolas", 10))
        hardware_info_layout.addWidget(self.hardware_fp_edit)
        
        copy_fp_btn = QPushButton("📋 复制")
        copy_fp_btn.clicked.connect(self.copy_hardware_fingerprint)
        hardware_info_layout.addWidget(copy_fp_btn)
        
        hardware_layout.addLayout(hardware_info_layout)
        
        # 说明文字
        hardware_note = QLabel("📝 请将硬件指纹发送给软件开发者以获取正式许可证")
        hardware_note.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
        hardware_layout.addWidget(hardware_note)
        
        hardware_group.setLayout(hardware_layout)
        layout.addWidget(hardware_group)
        
        # === 许可证输入区域 ===
        input_group = QGroupBox("📝 许可证激活")
        input_layout = QVBoxLayout()
        
        # 许可证输入框
        self.license_input = QTextEdit()
        self.license_input.setPlaceholderText("请在此处粘贴从开发者处获得的许可证内容...")
        self.license_input.setMaximumHeight(150)
        self.license_input.setFont(QFont("Consolas", 9))
        input_layout.addWidget(self.license_input)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        verify_btn = QPushButton("✅ 验证并激活许可证")
        verify_btn.setStyleSheet(UIStyles.get_button_style('success'))
        verify_btn.clicked.connect(self.verify_license)
        button_layout.addWidget(verify_btn)
        
        save_btn = QPushButton("💾 保存许可证")
        save_btn.setStyleSheet(UIStyles.get_button_style('primary'))
        save_btn.clicked.connect(self.save_license)
        button_layout.addWidget(save_btn)
        
        load_btn = QPushButton("📂 从文件加载")
        load_btn.clicked.connect(self.load_license_from_file)
        button_layout.addWidget(load_btn)
        
        button_layout.addStretch()
        input_layout.addLayout(button_layout)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # === 操作记录区域 ===
        log_group = QGroupBox("📋 操作记录")
        log_layout = QVBoxLayout()
        
        self.license_log = QTextEdit()
        self.license_log.setMaximumHeight(150)
        self.license_log.setReadOnly(True)
        self.license_log.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.license_log)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # 初始化日志信息
        if self.is_licensed:
            self.license_log_message("✅ 程序已授权，功能完整可用")
        else:
            self.license_log_message("⚠️ 程序运行在试用模式，功能受限")
            self.license_log_message(f"💻 当前硬件指纹: {hardware_fp}")
            self.license_log_message("📧 请联系开发者获取正式许可证")
        
        widget.setLayout(layout)
        return widget
    
    def create_upload_tab(self):
        """创建浏览器上传标签页 - 方案二：保留原布局+核心改进"""
        widget = QWidget()
        layout = QVBoxLayout()  # 恢复原来的垂直布局
        
        # === 视频选择区域 ===
        video_group = QGroupBox("📹 视频文件选择")
        video_layout = QVBoxLayout()
        
        # 目录选择
        dir_layout = QHBoxLayout()
        self.video_dir_edit = QLineEdit()
        self.video_dir_edit.setPlaceholderText("选择包含视频文件的目录")
        self.video_dir_edit.textChanged.connect(self.refresh_video_list)  # 实时刷新
        self.video_dir_edit.textChanged.connect(self.save_ui_settings)
        dir_layout.addWidget(self.video_dir_edit)
        
        select_dir_btn = QPushButton("📁 选择目录")
        select_dir_btn.clicked.connect(self.select_video_directory)
        dir_layout.addWidget(select_dir_btn)
        
        refresh_dir_btn = QPushButton("🔄 刷新")
        refresh_dir_btn.clicked.connect(self.refresh_video_list)
        dir_layout.addWidget(refresh_dir_btn)
        
        # 添加打开文件夹按钮
        open_folder_btn = QPushButton("📂 打开文件夹")
        open_folder_btn.clicked.connect(self.open_video_folder)
        dir_layout.addWidget(open_folder_btn)
        
        video_layout.addLayout(dir_layout)
        
        # 文件统计信息（紧凑版）
        self.video_stats_label = QLabel("📊 文件统计: 等待加载...")
        self.video_stats_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px 5px; margin: 0px;")
        self.video_stats_label.setMaximumHeight(20)  # 限制统计信息高度
        video_layout.addWidget(self.video_stats_label)
        
        # 🎯 用户反馈：不需要加载更多按钮，移除该功能
        
        # 视频文件列表（增加高度，更好利用空间）
        self.video_list = QListWidget()
        self.video_list.setMaximumHeight(400)  # 增加高度到400px
        self.video_list.setMinimumHeight(300)  # 设置最小高度
        self.video_list.setAlternatingRowColors(True)
        self.video_list.itemClicked.connect(self.on_video_selected)
        video_layout.addWidget(self.video_list)
        
        # 简单的自动刷新控制
        auto_refresh_layout = QHBoxLayout()
        self.auto_refresh_check = QCheckBox("自动刷新文件列表")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.toggled.connect(self.toggle_auto_refresh)
        auto_refresh_layout.addWidget(self.auto_refresh_check)
        auto_refresh_layout.addStretch()
        video_layout.addLayout(auto_refresh_layout)
        
        video_group.setLayout(video_layout)
        layout.addWidget(video_group)
        
        # === 上传设置区域 ===
        settings_group = QGroupBox("⚙️ 上传设置")
        settings_layout = QVBoxLayout()
        
        # 账号选择
        account_layout = QHBoxLayout()
        account_layout.addWidget(QLabel("选择账号:"))
        self.account_combo = QComboBox()
        account_layout.addWidget(self.account_combo)
        account_layout.addStretch()
        settings_layout.addLayout(account_layout)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # === 控制区域 ===
        control_group = QGroupBox("🎬 浏览器上传控制")
        control_layout = QVBoxLayout()
        
        # 选中文件信息（简化版）
        self.selected_file_label = QLabel("请选择要上传的视频文件")
        self.selected_file_label.setStyleSheet("padding: 8px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;")
        self.selected_file_label.setWordWrap(True)
        control_layout.addWidget(self.selected_file_label)
        
        # 按钮区
        button_layout = QHBoxLayout()
        
        self.start_upload_btn = QPushButton("🚀 开始上传")
        self.start_upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.start_upload_btn.clicked.connect(self.start_browser_upload)
        
        self.pause_upload_btn = QPushButton("⏸️ 暂停")
        self.pause_upload_btn.setEnabled(False)
        self.pause_upload_btn.clicked.connect(self.pause_browser_upload)
        
        self.stop_upload_btn = QPushButton("⏹️ 停止")
        self.stop_upload_btn.setEnabled(False)
        self.stop_upload_btn.clicked.connect(self.stop_browser_upload)
        
        button_layout.addWidget(self.start_upload_btn)
        button_layout.addWidget(self.pause_upload_btn)
        button_layout.addWidget(self.stop_upload_btn)
        button_layout.addStretch()
        
        control_layout.addLayout(button_layout)
        
        # 进度显示
        self.upload_progress = QProgressBar()
        self.upload_progress.setVisible(False)
        control_layout.addWidget(self.upload_progress)
        
        # 状态标签
        self.upload_status_label = QLabel("✅ 准备就绪")
        self.upload_status_label.setStyleSheet("color: #28a745; font-weight: bold;")
        control_layout.addWidget(self.upload_status_label)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        widget.setLayout(layout)
        return widget

    def create_log_tab(self):
        """创建日志标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 日志控制
        log_control = QHBoxLayout()
        
        # 日志过滤
        filter_combo = QComboBox()
        filter_combo.addItems(["全部", "信息", "警告", "错误"])
        filter_combo.currentTextChanged.connect(self.filter_logs)
        log_control.addWidget(QLabel("过滤:"))
        log_control.addWidget(filter_combo)
        
        # 搜索
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("搜索日志...")
        search_edit.textChanged.connect(self.search_logs)
        log_control.addWidget(QLabel("搜索:"))
        log_control.addWidget(search_edit)
        
        # 自动滚动
        auto_scroll_check = QCheckBox("自动滚动")
        auto_scroll_check.setChecked(True)
        auto_scroll_check.toggled.connect(self.toggle_auto_scroll)
        log_control.addWidget(auto_scroll_check)
        
        # 清空和保存
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self.clear_log)
        log_control.addWidget(clear_btn)
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_log)
        log_control.addWidget(save_btn)
        
        log_control.addStretch()
        layout.addLayout(log_control)
        
        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont(UIConfig.LOG_FONT_FAMILY, UIConfig.LOG_FONT_SIZE))
        layout.addWidget(self.log_text)
        
        widget.setLayout(layout)
        return widget
    
    def setup_browser_status_timer(self):
        """🎯 简化版浏览器状态监控 - 防止线程问题"""
        try:
            from PyQt5.QtCore import QTimer
            
            # 🎯 延长检查间隔到60秒，减少资源消耗和线程冲突
            self.browser_status_timer = QTimer()
            self.browser_status_timer.timeout.connect(self.update_browser_status_async)
            self.browser_status_timer.start(60000)  # 改为每60秒检查一次
            
            # 初始化缓存
            if not hasattr(self, '_browser_status_cache'):
                self._browser_status_cache = {}
            
            self.log_message("🔄 浏览器状态监控已启动 (60秒间隔)", "INFO")
            
        except Exception as e:
            self.log_message(f"⚠️ 浏览器状态监控启动失败: {e}", "WARNING")
    
    def update_browser_status_async(self):
        """🎯 增强版：真实检测浏览器状态，准确反映关闭状态"""
        try:
            # 获取当前账号列表
            accounts = []
            for row in range(self.account_table.rowCount()):
                username_item = self.account_table.item(row, 1)
                if username_item:
                    accounts.append(username_item.text())
            
            if not accounts:
                return
            
            # 🎯 真实检测浏览器状态
            for username in accounts:
                try:
                    is_active = self.is_browser_active(username)
                    self.on_browser_status_checked(username, is_active)
                except:
                    self.on_browser_status_checked(username, False)
            
        except Exception as e:
            # 静默处理错误
            pass
    
    def on_browser_status_checked(self, username: str, is_active: bool):
        """处理后台线程返回的浏览器状态结果"""
        try:
            # 🎯 性能优化：更新缓存
            if not hasattr(self, '_browser_status_cache'):
                self._browser_status_cache = {}
            
            old_status = self._browser_status_cache.get(username, "未活跃")
            new_status = "活跃" if is_active else "未活跃"
            
            # 更新缓存
            self._browser_status_cache[username] = new_status
            
            # 🎯 性能优化：只在状态真正变化时更新UI
            if old_status != new_status:
                # 找到对应的表格行并更新
                for row in range(self.account_table.rowCount()):
                    username_item = self.account_table.item(row, 1)
                    if username_item and username_item.text() == username:
                        browser_item = self.account_table.item(row, 3)
                        if browser_item:
                            browser_item.setText(new_status)
                            
                            if is_active:
                                browser_item.setBackground(QColor(144, 238, 144))
                            else:
                                browser_item.setBackground(QColor(255, 182, 193))
                        break
                
                # 🎯 性能优化：减少日志输出
                if not hasattr(self, '_last_status_log'):
                    self._last_status_log = {}
                
                current_time = time.time()
                last_log = self._last_status_log.get(username, 0)
                
                # 只有距离上次日志超过120秒才记录
                if current_time - last_log > 120:
                    self.log_message(f"🔄 {username} -> {new_status}", "INFO")
                    self._last_status_log[username] = current_time
                    
        except Exception as e:
            # 静默处理错误
            pass

    def load_data(self):
        """🎯 简化版数据加载 - 减少线程和定时器使用"""
        self.load_ui_settings()  # 🎯 修复：先加载设置，包括账号选择状态
        self.refresh_accounts()  # 然后刷新账号，应用加载的选择状态
        self.refresh_video_list()  # 然后刷新视频列表
        self.refresh_account_combo()
        
        # 🎯 账号进度已在refresh_accounts中自动加载，无需额外刷新
        
        # 🎯 临时禁用文件监控，避免定时器问题
        # QTimer.singleShot(2000, self.setup_file_monitor)  # 暂时注释掉
    
    def log_message(self, message: str, level: str = "INFO"):
        """添加日志消息 - 性能优化版"""
        if not hasattr(self, 'log_text'):
            return
            
        # 🎯 性能优化：限制日志条数，防止内存无限增长
        if not hasattr(self, '_log_count'):
            self._log_count = 0
        
        # 🎯 性能优化：批量清理日志
        if self._log_count > 500:  # 限制500条日志
            self.log_text.clear()
            self._log_count = 0
            self.log_text.append('<span style="color: #666;">--- 日志已清理 ---</span><br>')
        
        # 🎯 性能优化：简化日志格式，减少HTML处理
        timestamp = time.strftime("%H:%M:%S")
        
        # 简化颜色处理
        color_map = {
            "ERROR": "#dc3545",
            "WARNING": "#ffc107", 
            "SUCCESS": "#28a745",
            "INFO": "#17a2b8"
        }
        color = color_map.get(level, "#17a2b8")
        
        # 🎯 性能优化：使用更简单的格式
        formatted_message = f'<span style="color: {color};">[{timestamp}] {message}</span><br>'
        
        # 🎯 性能优化：减少UI更新频率
        self.log_text.append(formatted_message)
        self._log_count += 1
        
        # 🎯 性能优化：只在必要时滚动
        if self._log_count % 5 == 0:  # 每5条日志才滚动一次
            if hasattr(self, 'auto_scroll') and getattr(self, 'auto_scroll', True):
                self.log_text.moveCursor(QTextCursor.End)
    
    @prevent_double_click(duration=3.0, disable_text="添加中...")
    def add_account(self):
        """添加账号"""
        username, ok = QInputDialog.getText(self, "添加账号", "请输入账号名:")
        if ok and username:
            if self.core_app.account_manager.add_account(username):
                self.log_message(f"账号 {username} 添加成功", "SUCCESS")
                self.refresh_accounts()
            else:
                self.log_message(f"账号 {username} 添加失败", "ERROR")
    
    @prevent_double_click(duration=5.0, disable_text="登录中...")
    def login_account(self):
        """登录账号"""
        selected_rows = self.account_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "提示", "请选择要登录的账号")
            return
        
        row = selected_rows[0].row()
        username = self.account_table.item(row, 1).text()
        
        # 创建登录线程
        self.login_thread = LoginThread(self.core_app.account_manager, username)
        self.login_thread.login_success.connect(self.on_login_success)
        self.login_thread.login_failed.connect(self.on_login_failed)
        self.login_thread.start()
        
        self.log_message(f"开始登录账号: {username}")
    
    def on_login_success(self, username):
        """登录成功处理"""
        self.log_message(f"账号 {username} 登录成功", "SUCCESS")
        self.refresh_accounts()
    
    def on_login_failed(self, username, error):
        """登录失败处理"""
        self.log_message(f"账号 {username} 登录失败: {error}", "ERROR")
        self.refresh_accounts()
    
    def remove_account(self):
        """删除账号"""
        selected_rows = self.account_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "提示", "请选择要删除的账号")
            return
        
        row = selected_rows[0].row()
        username = self.account_table.item(row, 1).text()
        
        reply = QMessageBox.question(self, "确认删除", f"确定要删除账号 {username} 吗？")
        if reply == QMessageBox.Yes:
            self.core_app.account_manager.remove_account(username)
            self.log_message(f"账号 {username} 已删除", "SUCCESS")
            self.refresh_accounts()
    

    @prevent_double_click(duration=5.0, disable_text="诊断中...")
    def diagnose_browser(self):
        """浏览器诊断功能 - 内置于EXE程序中"""
        try:
            self.log_message("🔍 开始浏览器诊断...", "INFO")
            
            # 创建诊断信息对话框
            dialog = QMessageBox(self)
            dialog.setWindowTitle("🔍 浏览器诊断报告")
            dialog.setIcon(QMessageBox.Information)
            
            # 诊断结果收集
            diagnosis_results = []
            all_passed = True
            
            # 1. 检查ms-playwright目录
            self.log_message("📁 检查ms-playwright目录...", "INFO")
            playwright_status = self._check_playwright_directory()
            diagnosis_results.append(f"📁 ms-playwright目录: {playwright_status['status']}")
            if playwright_status['details']:
                for detail in playwright_status['details']:
                    diagnosis_results.append(f"   {detail}")
            if not playwright_status['success']:
                all_passed = False
            
            # 2. 检查Chrome浏览器
            self.log_message("🔧 检查Chrome浏览器...", "INFO")
            chrome_status = self._check_chrome_browser()
            diagnosis_results.append(f"🔧 Chrome浏览器: {chrome_status['status']}")
            if chrome_status['details']:
                for detail in chrome_status['details']:
                    diagnosis_results.append(f"   {detail}")
            if not chrome_status['success']:
                all_passed = False
            
            # 3. 检查网络连接
            self.log_message("🌐 检查网络连接...", "INFO")
            network_status = self._check_network_connection()
            diagnosis_results.append(f"🌐 网络连接: {network_status['status']}")
            if network_status['details']:
                for detail in network_status['details']:
                    diagnosis_results.append(f"   {detail}")
            if not network_status['success']:
                all_passed = False
            
            # 4. 检查账号状态
            self.log_message("👤 检查账号状态...", "INFO")
            account_status = self._check_account_status()
            diagnosis_results.append(f"👤 账号状态: {account_status['status']}")
            if account_status['details']:
                for detail in account_status['details']:
                    diagnosis_results.append(f"   {detail}")
            if not account_status['success']:
                all_passed = False
            
            # 生成报告
            status_icon = "✅" if all_passed else "❌"
            overall_status = "所有检查通过" if all_passed else "发现问题"
            
            report_header = f"{status_icon} 诊断完成: {overall_status}\n\n"
            report_body = "\n".join(diagnosis_results)
            
            # 添加解决建议
            if not all_passed:
                report_body += "\n\n💡 解决建议:\n"
                if not playwright_status['success']:
                    report_body += "• 运行 upgrade_ms_playwright.py 重新下载浏览器\n"
                if not chrome_status['success']:
                    report_body += "• 以管理员身份运行程序\n• 确保有足够磁盘空间\n"
                if not network_status['success']:
                    # 检查是否是B站412错误
                    network_details_str = "\n".join(network_status.get('details', []))
                    if "412" in network_details_str:
                        report_body += "🚨 发现B站反爬虫拦截问题：\n"
                        report_body += "• 立即尝试：切换到手机热点网络测试\n"
                        report_body += "• 如果手机热点可用，说明当前网络被B站限制\n"
                        report_body += "• 等待2-24小时后重试\n"
                        report_body += "• 考虑使用不同的网络环境\n"
                    else:
                        report_body += "• 检查网络连接\n• 暂时关闭防火墙测试\n"
                report_body += "• 联系技术支持并提供此诊断报告"
            
            full_report = report_header + report_body
            
            # 显示诊断报告
            dialog.setText("浏览器诊断已完成，点击 'Show Details' 查看详细报告")
            dialog.setDetailedText(full_report)
            dialog.exec_()
            
            # 记录到日志
            self.log_message(f"🔍 诊断完成: {overall_status}", "SUCCESS" if all_passed else "ERROR")
            for line in diagnosis_results:
                self.log_message(line, "INFO")
                
        except Exception as e:
            self.log_message(f"❌ 浏览器诊断失败: {e}", "ERROR")
            QMessageBox.critical(self, "诊断失败", f"浏览器诊断过程中发生错误:\n{e}")
    
    def _check_playwright_directory(self):
        """检查ms-playwright目录"""
        try:
            playwright_dirs = []
            chrome_files = []
            
            # 搜索ms-playwright目录
            for root, dirs, files in os.walk('.'):
                if 'ms-playwright' in root:
                    playwright_dirs.append(root)
                    # 查找Chrome文件
                    for file in files:
                        if file.lower() == 'chrome.exe':
                            chrome_path = os.path.join(root, file)
                            size_mb = os.path.getsize(chrome_path) / (1024 * 1024)
                            chrome_files.append({
                                'path': chrome_path,
                                'size_mb': round(size_mb, 1),
                                'exists': os.path.exists(chrome_path)
                            })
            
            if playwright_dirs and chrome_files:
                details = []
                details.append(f"找到目录: {len(playwright_dirs)} 个")
                details.append(f"找到Chrome文件: {len(chrome_files)} 个")
                for chrome_info in chrome_files[:3]:  # 只显示前3个
                    details.append(f"Chrome: {chrome_info['path']} ({chrome_info['size_mb']} MB)")
                
                return {
                    'success': True,
                    'status': '✅ 正常',
                    'details': details
                }
            else:
                return {
                    'success': False,
                    'status': '❌ 缺失',
                    'details': ['ms-playwright目录或Chrome文件不存在']
                }
                
        except Exception as e:
            return {
                'success': False,
                'status': '❌ 检查失败',
                'details': [f'检查错误: {e}']
            }
    
    def _check_chrome_browser(self):
        """检查Chrome浏览器"""
        try:
            from core.browser_detector import get_browser_detector
            detector = get_browser_detector()
            
            chrome_path = detector.get_best_chrome_path()
            
            if chrome_path:
                details = []
                details.append(f"路径: {chrome_path}")
                
                # 检查文件大小
                if os.path.exists(chrome_path):
                    size_mb = os.path.getsize(chrome_path) / (1024 * 1024)
                    details.append(f"大小: {size_mb:.1f} MB")
                    
                    # 尝试获取版本
                    try:
                        version = detector.get_chrome_version(chrome_path)
                        if version:
                            details.append(f"版本: {version}")
                    except:
                        details.append("版本: 获取失败")
                
                return {
                    'success': True,
                    'status': '✅ 可用',
                    'details': details
                }
            else:
                return {
                    'success': False,
                    'status': '❌ 未找到',
                    'details': ['无法检测到可用的Chrome浏览器']
                }
                
        except Exception as e:
            return {
                'success': False,
                'status': '❌ 检查失败',
                'details': [f'检查错误: {e}']
            }
    
    def _check_network_connection(self):
        """检查网络连接"""
        try:
            import requests
            
            # 使用真实浏览器User-Agent避免412错误
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            test_urls = [
                ("百度", "https://www.baidu.com"),
                ("B站", "https://www.bilibili.com"),
                ("B站登录", "https://passport.bilibili.com/login")
            ]
            
            details = []
            all_success = True
            critical_failure = False
            
            for name, url in test_urls:
                try:
                    start_time = time.time()
                    response = requests.get(url, headers=headers, timeout=10)
                    response_time = time.time() - start_time
                    
                    if response.status_code == 200:
                        details.append(f"{name}: ✅ 正常 ({response_time:.2f}秒)")
                    elif response.status_code == 412:
                        details.append(f"{name}: ⚠️ 状态码412 (可能被反爬虫拦截)")
                        if "bilibili" in url:
                            critical_failure = True
                            details.append(f"  ❗ 这是登录失败的主要原因！")
                    else:
                        details.append(f"{name}: ⚠️ 状态码 {response.status_code}")
                        all_success = False
                        
                except Exception as e:
                    details.append(f"{name}: ❌ 失败 ({e})")
                    all_success = False
                    if "bilibili" in url:
                        critical_failure = True
            
            # 特别检查：如果B站连接有问题，给出具体建议
            if critical_failure:
                details.append("🔍 B站连接问题分析:")
                details.append("  • 412状态码表示请求被B站反爬虫系统拦截")
                details.append("  • 这会导致浏览器无法正常访问B站登录页面")
                details.append("  • 建议解决方案:")
                details.append("    1. 更换网络环境(如切换到手机热点)")
                details.append("    2. 使用VPN或代理")
                details.append("    3. 等待一段时间后重试")
                details.append("    4. 联系网络管理员检查防火墙设置")
            
            return {
                'success': all_success and not critical_failure,
                'status': '✅ 正常' if (all_success and not critical_failure) else '❌ B站连接异常',
                'details': details
            }
                
        except Exception as e:
            return {
                'success': False,
                'status': '❌ 检查失败',
                'details': [f'检查错误: {e}']
            }
    
    def _check_account_status(self):
        """检查账号状态"""
        try:
            all_accounts = self.core_app.account_manager.get_all_accounts()
            active_accounts = self.core_app.account_manager.get_active_accounts()
            
            details = []
            details.append(f"总账号数: {len(all_accounts)}")
            details.append(f"活跃账号数: {len(active_accounts)}")
            
            if all_accounts:
                details.append("账号列表:")
                for username in all_accounts[:5]:  # 只显示前5个
                    account = self.core_app.account_manager.get_account(username)
                    if account:
                        status = "✅ 活跃" if account.status == 'active' else "❌ 未登录"
                        details.append(f"  {username}: {status}")
            
            success = len(all_accounts) > 0
            status_text = '✅ 正常' if success else '❌ 无账号'
            
            return {
                'success': success,
                'status': status_text,
                'details': details
            }
                
        except Exception as e:
            return {
                'success': False,
                'status': '❌ 检查失败',
                'details': [f'检查错误: {e}']
            }
    
    def refresh_accounts(self):
        """刷新账号列表 - 修复版：防止状态错误重置"""
        try:
            # 🎯 关键修复：在刷新前记录当前所有账号的状态
            current_statuses = {}
            all_accounts = self.core_app.account_manager.get_all_accounts()
            for username in all_accounts:
                account = self.core_app.account_manager.get_account(username)
                if account:
                    current_statuses[username] = {
                        'status': account.status,
                        'cookies_count': len(account.cookies) if hasattr(account, 'cookies') else 0,
                        'last_login': getattr(account, 'last_login', 0)
                    }
            
            self.log_message(f"🔍 刷新前状态快照: {[(k, v['status']) for k, v in current_statuses.items()]}", "DEBUG")
            
            accounts = self.core_app.account_manager.get_all_accounts()
            
            if not hasattr(self, 'account_table'):
                return
            
            # 🎯 性能优化：减少日志输出
            if len(accounts) > 0:
                self.log_message(f"📋 刷新账号列表 ({len(accounts)} 个)", "INFO")
            
            # 🎯 性能优化：暂时断开信号，避免频繁触发
            self.account_table.blockSignals(True)
            
            self.account_table.setRowCount(len(accounts))
            
            for row, username in enumerate(accounts):
                account = self.core_app.account_manager.get_account(username)
                if not account:
                    continue
                
                # 选择框 - 直接使用保存的选择状态
                checkbox = QCheckBox()
                # 🎯 修复：直接使用_account_selections中的状态，新账号默认不选中
                is_selected = False
                if hasattr(self, '_account_selections') and username in self._account_selections:
                    is_selected = self._account_selections[username]
                    self.log_message(f"🔍 恢复账号 {username} 选择状态: {is_selected}", "DEBUG")
                
                checkbox.setChecked(is_selected)
                checkbox.stateChanged.connect(self.on_account_selection_changed)
                self.account_table.setCellWidget(row, 0, checkbox)
                
                # 账号名
                self.account_table.setItem(row, 1, QTableWidgetItem(username))
                
                # 🎯 修复：登录状态 - 使用更稳定的状态判断逻辑
                # 只有当账号状态明确为active且有有效cookies时才显示已登录
                is_really_logged_in = (account.status == 'active' and 
                                       hasattr(account, 'cookies') and 
                                       len(account.cookies) > 0 and
                                       account.is_logged_in())
                
                status_text = "已登录" if is_really_logged_in else "未登录"
                status_item = QTableWidgetItem(status_text)
                
                # 🔍 调试日志：记录状态判断过程
                self.log_message(f"🔍 账号 {username} 状态检查: status={account.status}, cookies={len(account.cookies) if hasattr(account, 'cookies') else 0}, 最终状态={status_text}", "DEBUG")
                
                if is_really_logged_in:
                    status_item.setBackground(QColor(144, 238, 144))  # 浅绿色
                else:
                    status_item.setBackground(QColor(255, 182, 193))  # 浅红色
                self.account_table.setItem(row, 2, status_item)
                
                # 🎯 性能优化：浏览器状态使用缓存，避免实时检查
                browser_status = self._get_cached_browser_status(username)
                browser_item = QTableWidgetItem(browser_status)
                if browser_status == "活跃":
                    browser_item.setBackground(QColor(144, 238, 144))
                else:
                    browser_item.setBackground(QColor(255, 182, 193))
                self.account_table.setItem(row, 3, browser_item)
                
                # 最后登录
                if hasattr(account, 'last_login') and account.last_login:
                    last_login = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(account.last_login))
                else:
                    last_login = "从未登录"
                self.account_table.setItem(row, 4, QTableWidgetItem(last_login))
                
                # 🎯 获取目标数量（从界面设置获取）
                target_count = 1  # 默认值，如果界面有设置就使用界面值
                if hasattr(self, 'videos_per_account_input'):
                    try:
                        target_count = int(self.videos_per_account_input.text())
                    except:
                        target_count = 1
                
                # 🎯 新增：今日已发数量
                from core.account_manager import account_manager
                try:
                    status, completed, published = account_manager.get_account_progress(username, target_count)
                    
                    # 今日已发列
                    today_published_item = QTableWidgetItem(str(published))
                    today_published_item.setTextAlignment(Qt.AlignCenter)
                    if completed:
                        today_published_item.setBackground(QColor(144, 238, 144))  # 已完成：绿色
                    else:
                        today_published_item.setBackground(QColor(255, 255, 200))  # 进行中：淡黄色
                    self.account_table.setItem(row, 5, today_published_item)
                    
                    # 进度状态列
                    progress_item = QTableWidgetItem(status)
                    progress_item.setTextAlignment(Qt.AlignCenter)
                    if completed:
                        progress_item.setBackground(QColor(144, 238, 144))  # 已完成：绿色
                        progress_item.setForeground(QColor(0, 100, 0))     # 深绿色字体
                    else:
                        progress_item.setBackground(QColor(255, 255, 200))  # 进行中：淡黄色
                        progress_item.setForeground(QColor(100, 100, 0))   # 深黄色字体
                    self.account_table.setItem(row, 6, progress_item)
                    
                except Exception as e:
                    # 如果获取进度失败，显示默认值
                    self.account_table.setItem(row, 5, QTableWidgetItem("0"))
                    self.account_table.setItem(row, 6, QTableWidgetItem("0/0 错误"))
                
                # 备注（列索引改为7）
                notes = getattr(account, 'notes', "")
                self.account_table.setItem(row, 7, QTableWidgetItem(notes))
            
            # 🎯 性能优化：重新启用信号
            self.account_table.blockSignals(False)
            
            # 🎯 性能优化：显示带进度的统计信息
            try:
                target_count = int(self.videos_per_account_input.text()) if hasattr(self, 'videos_per_account_input') else 1
                self._update_account_stats_with_progress(target_count)
            except:
                # 如果进度统计失败，回退到基本统计
                total_accounts = len(accounts)
                active_accounts = len([a for a in accounts if self.core_app.account_manager.get_account(a).status == 'active'])
                stats_text = f"账号统计：总数 {total_accounts}，活跃 {active_accounts}"
                self.account_stats_label.setText(stats_text)
            
            # 🔍 验证刷新后的状态是否发生了意外变化
            if 'current_statuses' in locals():
                unexpected_changes = []
                for username in accounts:
                    account = self.core_app.account_manager.get_account(username)
                    if account and username in current_statuses:
                        old_status = current_statuses[username]['status']
                        new_status = account.status
                        if old_status != new_status and old_status == 'active':
                            unexpected_changes.append(f"{username}: {old_status} -> {new_status}")
                
                if unexpected_changes:
                    self.log_message(f"⚠️ 检测到意外的状态变化: {unexpected_changes}", "WARNING")
                    self.log_message("🔧 这可能是导致其他账号显示未登录的原因", "WARNING")
            
            # 🎯 新增：刷新全选框状态，避免状态不一致
            self.on_account_selection_changed()
            
        except Exception as e:
            self.log_message(f"❌ 刷新账号列表失败: {str(e)}", "ERROR")
    
    def _get_cached_browser_status(self, username: str) -> str:
        """获取缓存的浏览器状态，避免实时检查造成卡顿"""
        if not hasattr(self, '_browser_status_cache'):
            self._browser_status_cache = {}
        
        # 🎯 修复：如果缓存中没有状态，先进行一次快速检查
        if username not in self._browser_status_cache:
            # 🎯 使用简化的端口检测方法
            try:
                is_active = self.core_app.browser_manager.is_browser_active_simple(username)
                self._browser_status_cache[username] = "活跃" if is_active else "未活跃"
            except:
                # 如果新方法失败，回退到原方法
                is_active = self.is_browser_active(username)
                self._browser_status_cache[username] = "活跃" if is_active else "未活跃"
        
        return self._browser_status_cache.get(username, "未活跃")
    
    def refresh_account_combo(self):
        """刷新账号下拉框"""
        if hasattr(self, 'account_combo'):
            self.account_combo.clear()
            accounts = self.core_app.account_manager.get_active_accounts()
            for account in accounts:
                self.account_combo.addItem(account)
    
    def select_video_directory(self):
        """选择视频目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择视频目录", ".")
        if directory:
            self.video_dir_edit.setText(directory)
            self.refresh_video_list()
    
    def refresh_video_list(self):
        """🎯 临时禁用线程版本 - 直接在主线程处理，防止崩溃"""
        if not hasattr(self, 'video_list'):
            return
            
        directory = self.video_dir_edit.text() if hasattr(self, 'video_dir_edit') else ""
        if not directory or not os.path.exists(directory):
            if hasattr(self, 'video_stats_label'):
                self.video_stats_label.setText("📊 文件统计: 请选择有效目录")
            return
        
        # 🎯 直接在主线程处理，避免线程问题
        try:
            if hasattr(self, 'video_stats_label'):
                self.video_stats_label.setText("📊 正在扫描文件...")
            
            # 获取视频文件
            video_files = self.get_video_files(directory)
            
            # 暂时断开信号
            self.video_list.blockSignals(True)
            self.video_list.clear()
            
            total_size = 0
            for file_path in video_files:
                filename = os.path.basename(file_path)
                try:
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    size_mb = file_size / (1024 * 1024)
                    display_text = f"{filename} ({size_mb:.1f}MB)"
                except:
                    display_text = filename
                    
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, file_path)
                self.video_list.addItem(item)
            
            # 重新启用信号
            self.video_list.blockSignals(False)
            
            # 更新统计信息
            if hasattr(self, 'video_stats_label'):
                total_size_mb = total_size / (1024 * 1024) if total_size > 0 else 0
                stats_text = f"📊 文件统计: {len(video_files)} 个文件, 总大小 {total_size_mb:.1f}MB"
                self.video_stats_label.setText(stats_text)
                
        except Exception as e:
            if hasattr(self, 'video_stats_label'):
                self.video_stats_label.setText("📊 文件扫描失败")
            self.log_message(f"❌ 视频文件扫描失败: {e}", "ERROR")
    
    def _refresh_video_list_async(self, directory):
        """刷新视频文件列表 - 修复版：同步处理避免线程问题"""
        try:
            # 🎯 修复：改为同步处理，避免线程管理问题
            video_files = self.get_video_files(directory)
            
            # 处理所有文件
            file_info_list = []
            total_size = 0
            
            for file_path in video_files:
                filename = os.path.basename(file_path)
                try:
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    size_mb = file_size / (1024 * 1024)
                    display_text = f"{filename} ({size_mb:.1f}MB)"
                except:
                    display_text = filename
                    
                file_info_list.append((display_text, file_path))
            
            # 直接调用结果处理
            total_files = len(video_files)
            self.on_video_files_scanned(file_info_list, total_size, total_files, total_files)
            
        except Exception as e:
            # 静默处理错误，显示空结果
            self.on_video_files_scanned([], 0, 0, 0)
    
    def on_video_files_scanned(self, file_info_list, total_size, file_count, total_files):
        """处理视频文件扫描结果 - 显示全部文件"""
        try:
            # 🎯 性能优化：暂时断开信号
            self.video_list.blockSignals(True)
            self.video_list.clear()
            
            # 批量添加所有文件
            for display_text, file_path in file_info_list:
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, file_path)
                self.video_list.addItem(item)
            
            # 重新启用信号
            self.video_list.blockSignals(False)
            
            # 更新统计信息
            if hasattr(self, 'video_stats_label'):
                total_size_mb = total_size / (1024 * 1024) if total_size > 0 else 0
                stats_text = f"📊 文件统计: {total_files} 个文件, 总大小 {total_size_mb:.1f}MB"
                self.video_stats_label.setText(stats_text)
                
        except Exception as e:
            # 静默处理错误
            pass
    
    # 🎯 用户反馈：移除加载更多功能，已删除相关方法
    
    def _update_pagination_buttons(self, page_info):
        """更新分页控制按钮状态"""
        current_page = page_info['current_page']
        total_pages = page_info['total_pages']
        
        # 如果分页按钮不存在，创建它们
        if not hasattr(self, 'prev_page_btn'):
            self._create_pagination_buttons()
        
        # 更新按钮状态
        if hasattr(self, 'prev_page_btn'):
            self.prev_page_btn.setEnabled(current_page > 0)
        
        if hasattr(self, 'next_page_btn'):
            self.next_page_btn.setEnabled(current_page < total_pages - 1)
        
        # 显示/隐藏分页控件
        show_pagination = total_pages > 1
        if hasattr(self, 'pagination_widget'):
            self.pagination_widget.setVisible(show_pagination)
    
    def _create_pagination_buttons(self):
        """创建分页控制按钮"""
        try:
            # 如果在视频文件列表的父容器中找到位置添加分页控件
            if hasattr(self, 'video_list') and self.video_list.parent():
                from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
                
                # 创建分页控件容器
                self.pagination_widget = QWidget()
                pagination_layout = QHBoxLayout()
                
                # 上一页按钮
                self.prev_page_btn = QPushButton("◀ 上一页")
                self.prev_page_btn.clicked.connect(self._prev_page)
                pagination_layout.addWidget(self.prev_page_btn)
                
                # 页码信息
                self.page_info_label = QLabel("第 1/1 页")
                pagination_layout.addWidget(self.page_info_label)
                
                # 下一页按钮
                self.next_page_btn = QPushButton("下一页 ▶")
                self.next_page_btn.clicked.connect(self._next_page)
                pagination_layout.addWidget(self.next_page_btn)
                
                pagination_layout.addStretch()
                self.pagination_widget.setLayout(pagination_layout)
                
                # 将分页控件添加到视频文件列表下方
                parent_layout = self.video_list.parent().layout()
                if parent_layout:
                    # 找到video_list的位置，在其后插入分页控件
                    for i in range(parent_layout.count()):
                        if parent_layout.itemAt(i).widget() == self.video_list:
                            parent_layout.insertWidget(i + 1, self.pagination_widget)
                            break
                
                # 初始状态隐藏
                self.pagination_widget.setVisible(False)
                
        except Exception as e:
            # 静默处理错误
            pass
    
    def _prev_page(self):
        """上一页"""
        if not hasattr(self, '_video_current_page'):
            self._video_current_page = 0
        
        if self._video_current_page > 0:
            self._video_current_page -= 1
            self.refresh_video_list()
    
    def _next_page(self):
        """下一页"""
        if not hasattr(self, '_video_current_page'):
            self._video_current_page = 0
        
        self._video_current_page += 1
        self.refresh_video_list()
    
    def on_video_selected(self, item):
        """视频文件选中回调"""
        if not item:
            return
            
        file_path = item.data(Qt.UserRole)
        filename = os.path.basename(file_path)
        
        # 更新选中文件信息
        if hasattr(self, 'selected_file_label'):
            try:
                file_size = os.path.getsize(file_path)
                size_mb = file_size / (1024 * 1024)
                
                file_info = (
                    f"📁 已选择: {filename}\n"
                    f"📏 大小: {size_mb:.1f}MB\n"
                    f"📂 路径: {file_path}"
                )
                self.selected_file_label.setText(file_info)
                self.selected_file_label.setStyleSheet(
                    "padding: 10px; "
                    "background-color: #e8f5e8; "
                    "border: 1px solid #28a745; "
                    "border-radius: 4px; "
                    "color: #155724;"
                )
            except Exception as e:
                self.selected_file_label.setText(f"📁 已选择: {filename}\n❌ 文件信息获取失败")
    
    def open_video_folder(self):
        """打开视频文件夹"""
        # 获取当前设置的视频目录
        directory = ""
        if hasattr(self, 'video_dir_edit') and self.video_dir_edit.text():
            directory = self.video_dir_edit.text().strip()
        
        # 如果没有设置目录，提示用户先选择
        if not directory:
            QMessageBox.information(
                self, 
                "提示", 
                "📁 请先点击「选择目录」按钮选择视频文件夹。\n\n"
                "选择后，此按钮将打开您选定的文件夹。"
            )
            self.log_message("ℹ️ 用户需要先选择视频目录", "INFO")
            return
        
        # 检查目录是否存在
        if not os.path.exists(directory):
            QMessageBox.warning(
                self, 
                "目录不存在", 
                f"所选目录不存在或已被删除：\n{directory}\n\n"
                "请重新选择一个有效的视频目录。"
            )
            self.log_message(f"❌ 目录不存在: {directory}", "ERROR")
            return
        
        # 打开文件夹
        try:
            import subprocess
            import platform
            
            system = platform.system()
            if system == "Windows":
                # Windows：使用explorer打开文件夹
                subprocess.run(['explorer', os.path.normpath(directory)])
            elif system == "Darwin":  # macOS
                subprocess.run(['open', directory])
            else:  # Linux
                subprocess.run(['xdg-open', directory])
                
            self.log_message(f"📂 已打开文件夹: {directory}", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 打开文件夹失败: {e}", "ERROR")
            QMessageBox.critical(
                self, 
                "打开失败", 
                f"无法打开文件夹：\n{directory}\n\n"
                f"错误信息：{e}\n\n"
                "请手动打开文件管理器浏览该目录。"
            )
    
    def toggle_auto_refresh(self, enabled):
        """切换自动刷新"""
        if enabled:
            self.setup_file_monitor()
            self.log_message("✅ 自动刷新已启用", "INFO")
        else:
            self.stop_file_monitor()
            self.log_message("⏸️ 自动刷新已禁用", "INFO")
    
    def setup_file_monitor(self):
        """设置文件监控"""
        # 简单的定时器方案，每3秒检查一次
        if not hasattr(self, 'file_monitor_timer'):
            from PyQt5.QtCore import QTimer
            self.file_monitor_timer = QTimer()
            self.file_monitor_timer.timeout.connect(self.check_file_changes)
            
        if hasattr(self, 'auto_refresh_check') and self.auto_refresh_check.isChecked():
            self.file_monitor_timer.start(10000)  # 10秒间隔（优化性能）
    
    def stop_file_monitor(self):
        """停止文件监控"""
        if hasattr(self, 'file_monitor_timer'):
            self.file_monitor_timer.stop()
    
    def check_file_changes(self):
        """检查文件变化"""
        if not hasattr(self, 'video_dir_edit') or not hasattr(self, 'auto_refresh_check'):
            return
            
        if not self.auto_refresh_check.isChecked():
            return
            
        directory = self.video_dir_edit.text()
        if not directory or not os.path.exists(directory):
            return
            
        # 获取当前文件列表
        current_files = set(self.get_video_files(directory))
        
        # 比较文件列表
        if not hasattr(self, '_last_file_list'):
            self._last_file_list = current_files
            return
            
        if current_files != self._last_file_list:
            # 延迟刷新，避免频繁更新
            if hasattr(self, '_file_refresh_timer'):
                self._file_refresh_timer.stop()
            
            self._file_refresh_timer = QTimer()
            self._file_refresh_timer.setSingleShot(True)
            self._file_refresh_timer.timeout.connect(lambda: self._delayed_video_refresh(current_files))
            self._file_refresh_timer.start(500)  # 500ms延迟
    
    def _delayed_video_refresh(self, current_files):
        """延迟执行的视频列表刷新"""
        self._last_file_list = current_files
        self.refresh_video_list()
        # 减少日志频率 - 只记录重要的文件变化
        if not hasattr(self, '_last_file_log_time'):
            self._last_file_log_time = 0
        
        current_time = time.time()
        if current_time - self._last_file_log_time > 60:  # 1分钟内最多记录一次
            self.log_message("🔄 检测到文件变化，已自动刷新列表", "INFO")
            self._last_file_log_time = current_time
    
    def get_video_files(self, directory: str):
        """获取目录中的视频文件"""
        video_files = []
        if os.path.exists(directory):
            from core.config import Config
            for file in os.listdir(directory):
                if any(file.lower().endswith(ext) for ext in Config.VIDEO_EXTENSIONS):
                    video_files.append(os.path.join(directory, file))
        return video_files
    
    @prevent_double_click(duration=3.0, disable_text="启动中...")
    def start_browser_upload(self):
        """开始浏览器上传"""
        # 许可证检查
        if not self.is_licensed:
            QMessageBox.warning(
                self, 
                "试用版限制", 
                "🔒 试用版功能受限\n\n"
                "单个视频上传功能在试用版中可用，但功能受限。\n"
                "如需完整功能，请在许可证管理页面激活正式许可证。"
            )
        
        if not hasattr(self, 'account_combo') or self.account_combo.currentText() == "":
            QMessageBox.warning(self, "警告", "请先选择一个账号")
            return
        
        if not hasattr(self, 'video_list') or self.video_list.count() == 0:
            QMessageBox.warning(self, "警告", "请先选择视频文件")
            return
        
        # 获取选中的视频文件
        current_item = self.video_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请选择要上传的视频文件")
            return
        
        # 从新界面获取文件路径
        video_file_path = current_item.data(Qt.UserRole)
        video_filename = os.path.basename(video_file_path)
        account_name = self.account_combo.currentText()
        
        mode_text = "🔓 正式版" if self.is_licensed else "🔒 试用版"
        self.log_message(f"🚀 开始浏览器上传 ({mode_text}): {video_filename} (账号: {account_name})", "INFO")
        
        # 更新UI状态
        self.start_upload_btn.setEnabled(False)
        self.pause_upload_btn.setEnabled(True)
        self.stop_upload_btn.setEnabled(True)
        self.upload_progress.setVisible(True)
        self.upload_status_label.setText("正在准备上传...")
        self.upload_status_label.setStyleSheet("color: #007bff; font-weight: bold;")
        
        # 🎯 修复：正确提取标题，确保与批量上传一致
        filename_without_ext = video_filename.rsplit('.', 1)[0]  # 去掉扩展名
        if '----' in filename_without_ext:
            # 文件名格式：商品ID----标题.mp4
            extracted_title = filename_without_ext.split('----', 1)[1]
            self.log_message(f"📝 提取标题: {extracted_title}")
        else:
            # 如果没有----分隔符，直接使用文件名（去掉扩展名）
            extracted_title = filename_without_ext
            self.log_message(f"📝 使用完整文件名作为标题: {extracted_title}")
        
        # 创建上传线程
        self.upload_thread = BrowserUploadThread(
            self.core_app,
            account_name,
            video_filename,
            self.video_dir_edit.text(),
            {
                'title': extracted_title,  # 🎯 使用正确提取的标题
                'title_template': '{filename}',  # 保持兼容性
                'tags': ["带货", "推荐"],
                'description': "优质商品推荐"
            }
        )
        
        self.upload_thread.upload_progress.connect(self.on_upload_progress)
        self.upload_thread.upload_status.connect(self.on_upload_status)
        self.upload_thread.upload_finished.connect(self.on_upload_finished)
        self.upload_thread.start()
    
    def pause_browser_upload(self):
        """暂停浏览器上传"""
        if hasattr(self, 'upload_thread'):
            self.upload_thread.pause()
        self.log_message("⏸️ 上传已暂停", "WARNING")
    
    def stop_browser_upload(self):
        """停止浏览器上传"""
        if hasattr(self, 'upload_thread'):
            self.upload_thread.stop()
        self.reset_upload_ui()
        self.log_message("⏹️ 上传已停止", "WARNING")
    
    def on_upload_progress(self, progress):
        """上传进度更新"""
        if hasattr(self, 'upload_progress'):
            self.upload_progress.setValue(progress)
    
    def on_upload_status(self, status):
        """上传状态更新"""
        if hasattr(self, 'upload_status_label'):
            self.upload_status_label.setText(status)
        
        # 更新主日志
        self.log_message(f"📝 {status}", "INFO")
    
    def on_upload_finished(self, success, message):
        """上传完成"""
        self.reset_upload_ui()
        if success:
            self.log_message(f"✅ 上传成功: {message}", "SUCCESS")
            QMessageBox.information(self, "上传成功", message)
        else:
            self.log_message(f"❌ 上传失败: {message}", "ERROR")
            QMessageBox.critical(self, "上传失败", message)
    
    def reset_upload_ui(self):
        """重置上传UI状态"""
        if hasattr(self, 'start_upload_btn'):
            self.start_upload_btn.setEnabled(True)
        if hasattr(self, 'pause_upload_btn'):
            self.pause_upload_btn.setEnabled(False)
        if hasattr(self, 'stop_upload_btn'):
            self.stop_upload_btn.setEnabled(False)
        if hasattr(self, 'upload_progress'):
            self.upload_progress.setVisible(False)
            self.upload_progress.setValue(0)
        if hasattr(self, 'upload_status_label'):
            self.upload_status_label.setText("✅ 准备就绪")
            self.upload_status_label.setStyleSheet("color: #28a745; font-weight: bold; padding: 5px;")
        
        # 重置选中文件信息
        if hasattr(self, 'selected_file_label'):
            self.selected_file_label.setText("请选择要上传的视频文件")
            self.selected_file_label.setStyleSheet("padding: 8px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;")

    def filter_logs(self, filter_type):
        """过滤日志"""
        pass
    
    def search_logs(self, search_text):
        """搜索日志"""
        pass
    
    def toggle_auto_scroll(self, enabled):
        """切换自动滚动"""
        self.auto_scroll = enabled
    
    def clear_log(self):
        """清空日志"""
        if hasattr(self, 'log_text'):
            self.log_text.clear()
    
    def save_log(self):
        """保存日志"""
        if hasattr(self, 'log_text'):
            filename, _ = QFileDialog.getSaveFileName(self, "保存日志", "log.txt", "Text Files (*.txt)")
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                self.log_message(f"日志已保存到: {filename}", "SUCCESS")
    
    def force_detect_browser_status(self):
        """强制检测浏览器状态"""
        self.log_message("🔍 开始强制检测浏览器状态...", "INFO")
        
        for username in self.core_app.account_manager.get_all_accounts():
            account = self.core_app.account_manager.get_account(username)
            
            # 检测浏览器实例
            has_instance = hasattr(account, 'browser_instance') and account.browser_instance is not None
            
            # 尝试获取浏览器信息
            browser_info = "无实例"
            if has_instance:
                try:
                    current_url = account.browser_instance.current_url
                    title = account.browser_instance.title
                    browser_info = f"URL: {current_url[:50]}..., 标题: {title[:30]}..."
                except:
                    browser_info = "实例失效"
            
            # 执行状态检测
            browser_active = self.is_browser_active(username)
            
            self.log_message(f"👤 {username}: {'✅活跃' if browser_active else '❌未活跃'} | {browser_info}", 
                           "SUCCESS" if browser_active else "WARNING")
        
        self.log_message("🔍 强制检测完成", "SUCCESS")
        self.refresh_accounts()
    
    def force_refresh_all_status(self):
        """强制刷新所有状态"""
        self.log_message("⚡ 强制刷新所有状态...", "INFO")
        self.refresh_accounts()
        QTimer.singleShot(2000, self._on_status_refresh_completed)
    
    def _on_status_refresh_completed(self):
        """状态刷新完成回调"""
        self.log_message("✅ 状态刷新完成", "SUCCESS")
    
    def is_browser_active(self, username: str) -> bool:
        """检查浏览器是否活跃 - 修复版：不影响账号登录状态"""
        try:
            account = self.core_app.account_manager.get_account(username)
            if not account:
                return False
            
            # 🎯 第一优先级：检查浏览器实例是否可用
            if hasattr(account, 'browser_instance') and account.browser_instance:
                try:
                    # 测试浏览器实例是否仍然有效
                    current_url = account.browser_instance.current_url
                    page_title = account.browser_instance.title
                    
                    if current_url and page_title is not None:
                        return True
                    else:
                        # 🎯 关键修复：浏览器实例无效时，只清理浏览器相关属性，不修改登录状态
                        account.browser_instance = None
                        # account.status = 'inactive'  # ❌ 删除这行！浏览器不活跃≠账号未登录
                        return False
                        
                except Exception as browser_error:
                    # 🎯 关键修复：浏览器已关闭或无响应时，只清理浏览器相关属性，不修改登录状态
                    account.browser_instance = None
                    # account.status = 'inactive'  # ❌ 删除这行！浏览器不活跃≠账号未登录
                    return False
            
            # 🎯 第二优先级：检查DevTools端口（更准确的检测）
            if hasattr(account, 'devtools_port') and account.devtools_port:
                port_active = self._quick_port_check(account.devtools_port)
                if port_active:
                    return True
                else:
                    # 🎯 关键修复：端口不活跃时，不修改账号登录状态
                    # account.status = 'inactive'  # ❌ 删除这行！端口不活跃≠账号未登录
                    return False
            
            # 🎯 第三优先级：检查进程是否存在（新增）
            if hasattr(account, 'browser_pid') and account.browser_pid:
                if self._check_process_exists(account.browser_pid):
                    return True
                else:
                    # 🎯 关键修复：进程不存在时，只清理进程相关属性，不修改登录状态
                    account.browser_pid = None
                    # account.status = 'inactive'  # ❌ 删除这行！进程不存在≠账号未登录
                    return False
            
            # 🎯 最后：如果没有任何有效检测方式，返回False（但不修改登录状态）
            return False
            
        except Exception as e:
            return False
    
    def _check_process_exists(self, pid: int) -> bool:
        """检查进程是否存在"""
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            # 如果没有psutil，使用系统命令
            try:
                import subprocess
                import platform
                
                if platform.system() == "Windows":
                    result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                          capture_output=True, text=True, timeout=2)
                    return str(pid) in result.stdout
                else:
                    result = subprocess.run(['ps', '-p', str(pid)], 
                                          capture_output=True, timeout=2)
                    return result.returncode == 0
            except:
                return False
        except:
            return False
    
    def _quick_port_check(self, port: int) -> bool:
        """快速检查DevTools端口"""
        try:
            import requests
            devtools_url = f"http://127.0.0.1:{port}/json"
            response = requests.get(devtools_url, timeout=1)
            return response.status_code == 200
        except:
            return False
    
    def on_browser_status_changed(self, account_name: str, is_active: bool):
        """处理浏览器状态变化信号 - 立即同步状态"""
        status_text = "活跃" if is_active else "未活跃"
        
        # 🎯 立即更新缓存状态
        if not hasattr(self, '_browser_status_cache'):
            self._browser_status_cache = {}
        
        old_status = self._browser_status_cache.get(account_name, "未活跃")
        self._browser_status_cache[account_name] = status_text
        
        # 🎯 只在状态真正改变时记录日志和刷新界面
        if old_status != status_text:
            self.log_message(f"🔧 浏览器状态变化: {account_name} -> {status_text}")
            
            # 🎯 立即更新界面，无需延迟
            try:
                # 直接更新账号表格中的浏览器状态列
                for row in range(self.account_table.rowCount()):
                    username_item = self.account_table.item(row, 1)
                    if username_item and username_item.text() == account_name:
                        browser_item = self.account_table.item(row, 3)
                        if browser_item:
                            browser_item.setText(status_text)
                            # 更新颜色
                            if status_text == "活跃":
                                browser_item.setBackground(QColor(144, 238, 144))  # 浅绿色
                            else:
                                browser_item.setBackground(QColor(255, 182, 193))  # 浅红色
                                
                                # 🎯 新增：浏览器变为未活跃时，清理账号对象中的浏览器实例
                                account = self.core_app.account_manager.get_account(account_name)
                                if account and hasattr(account, 'browser_instance'):
                                    account.browser_instance = None
                        break
            except Exception as e:
                # 如果直接更新失败，使用完整刷新作为备用
                self.log_message(f"⚠️ 界面状态更新失败，使用完整刷新: {e}", "WARNING")
                self.refresh_accounts()
    
    def toggle_select_all(self):
        """切换全选/取消全选"""
        is_checked = self.select_all_checkbox.isChecked()
        for row in range(self.account_table.rowCount()):
            checkbox = self.account_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(is_checked)
        
        # 🎯 新增：保存全选状态
        self.save_ui_settings()
        
        self.log_message(f"{'全选' if is_checked else '取消全选'}所有账号")
    
    def on_account_selection_changed(self):
        """账号选择状态改变"""
        # 💡 保存当前选择状态到内存
        if not hasattr(self, '_account_selections'):
            self._account_selections = {}
        
        selected_count = 0
        total_count = self.account_table.rowCount()
        current_status = {}  # 记录当前状态用于调试
        
        for row in range(total_count):
            checkbox = self.account_table.cellWidget(row, 0)
            username_item = self.account_table.item(row, 1)
            
            if checkbox and username_item:
                username = username_item.text()
                is_checked = checkbox.isChecked()
                
                # 🎯 关键修复：保存每个账号的选择状态
                self._account_selections[username] = is_checked
                current_status[username] = is_checked
                
                if is_checked:
                    selected_count += 1
        
        # 🎯 调试信息：显示当前选择状态
        self.log_message(f"📋 账号选择状态变更: {current_status}", "DEBUG")
        
        # 🎯 新增：保存选择状态到配置文件
        self.save_ui_settings()
        
        # 更新全选框状态
        if hasattr(self, 'select_all_checkbox'):
            if selected_count == total_count and total_count > 0:
                self.select_all_checkbox.setChecked(True)
            elif selected_count == 0:
                self.select_all_checkbox.setChecked(False)
            else:
                self.select_all_checkbox.setTristate(True)
                self.select_all_checkbox.setCheckState(Qt.PartiallyChecked)
    
    def get_selected_accounts(self):
        """获取选中的账号列表"""
        selected_accounts = []
        for row in range(self.account_table.rowCount()):
            checkbox = self.account_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                username = self.account_table.item(row, 1).text()
                selected_accounts.append(username)
        return selected_accounts
    
    @prevent_double_click(duration=3.0, disable_text="启动中...")
    def start_batch_upload(self):
        """开始批量上传 - 优化版本，避免UI阻塞"""
        self.log_message("🚀 点击了一键开始按钮，正在检查参数...")
        
        # 🎯 快速的基础检查（不耗时）
        selected_accounts = self.get_selected_accounts()
        if not selected_accounts:
            QMessageBox.warning(self, "警告", "请至少选择一个账号")
            self.log_message("❌ 没有选中的账号")
            return
        
        # 📋 输出选中的账号信息
        self.log_message(f"📋 用户选中的账号: {selected_accounts}")
        
        # 检查视频目录
        video_dir = ""
        if hasattr(self, 'video_dir_edit'):
            video_dir = self.video_dir_edit.text()
        
        if not video_dir or not os.path.exists(video_dir):
            QMessageBox.warning(self, "警告", "请先选择视频目录")
            self.log_message(f"❌ 视频目录无效: {video_dir}")
            return
        
        # 快速检查视频文件
        video_files = self.get_video_files(video_dir)
        if not video_files:
            QMessageBox.warning(self, "警告", "视频目录中没有找到视频文件")
            self.log_message(f"❌ 视频目录 {video_dir} 中没有视频文件")
            return
        
        # 检查设置参数
        try:
            if self.is_licensed:
                concurrent_browsers = int(self.concurrent_browsers_input.text())
                videos_per_account = int(self.videos_per_account_input.text())
            else:
                concurrent_browsers = 1
                videos_per_account = 1
        except ValueError as e:
            QMessageBox.warning(self, "警告", "请输入有效的数字")
            self.log_message(f"❌ 参数错误: {e}")
            return
        
        # 检查许可证状态
        if not self.is_licensed:
            if len(selected_accounts) > 1:
                QMessageBox.warning(
                    self, 
                    "试用版限制", 
                    "试用版仅支持单个账号上传。\n\n"
                    f"当前选中 {len(selected_accounts)} 个账号，请只选择1个账号。\n\n"
                    "如需多账号批量上传，请激活正式许可证。"
                )
                return
            
            QMessageBox.information(
                self,
                "试用版模式",
                "🔒 当前为试用版模式\n\n"
                "限制条件：\n"
                "• 单个账号上传\n"
                "• 单个浏览器运行\n"
                "• 单个视频上传\n\n"
                "如需完整功能，请在许可证管理页面激活正式许可证。"
            )
        
        # 🎯 关键优化：将耗时的账号状态检查移到后台线程
        self.log_message("📋 开始后台检查账号状态，界面保持响应...")
        
        # 立即更新UI状态，显示正在处理
        self.start_batch_upload_btn.setText("🔄 检查中...")
        self.start_batch_upload_btn.setEnabled(False)
        QApplication.processEvents()  # 立即更新UI
        
        # 🎯 使用QTimer延迟执行耗时操作，保持UI响应
        # 保存参数到实例变量
        self._batch_upload_params = (selected_accounts, video_files, video_dir, concurrent_browsers, videos_per_account)
        QTimer.singleShot(100, self._start_batch_upload_delayed)
    
    def _start_batch_upload_delayed(self):
        """延迟启动批量上传的回调方法"""
        if hasattr(self, '_batch_upload_params'):
            selected_accounts, video_files, video_dir, concurrent_browsers, videos_per_account = self._batch_upload_params
            self._perform_batch_upload_async(selected_accounts, video_files, video_dir, concurrent_browsers, videos_per_account)
            delattr(self, '_batch_upload_params')  # 清理临时参数
    
    def _perform_batch_upload_async(self, selected_accounts, video_files, video_dir, 
                                   concurrent_browsers, videos_per_account):
        """异步执行批量上传的耗时检查 - 在后台执行"""
        try:
            self.log_message("🚀 开始批量上传流程...")
            
            # 🎯 修复：更智能的账号状态检查
            valid_accounts = []
            for account_name in selected_accounts:
                account = self.core_app.account_manager.get_account(account_name)
                if account:
                    # 🔍 实时检查账号状态，而不是依赖缓存
                    has_cookies = hasattr(account, 'cookies') and account.cookies
                    has_browser = hasattr(account, 'browser_instance') and account.browser_instance
                    
                                         # 🎯 乐观策略：一旦有登录凭据就认为可用，不频繁检查状态
                    if has_cookies:
                        # 有Cookie就认为登录有效，强制设置为active状态
                        account.status = 'active'
                        valid_accounts.append((account_name, account))
                        self.log_message(f"✅ 账号 {account_name} 有登录凭据，视为有效账号", "SUCCESS")
                    else:
                        self.log_message(f"❌ 账号 {account_name} 无登录凭据，请先登录", "WARNING")
                else:
                    self.log_message(f"❌ 账号 {account_name} 不存在，跳过", "WARNING")
            
            if not valid_accounts:
                QMessageBox.warning(self, "账号状态错误", 
                    "所选账号均未登录或状态无效！\\n\\n"
                    "请先登录账号后再进行批量上传。")
                return
            
            self.log_message(f"📊 有效账号数量: {len(valid_accounts)}", "INFO")
            
            # 启动批量上传
            self._start_batch_upload_execution(valid_accounts, video_files, video_dir, 
                                             concurrent_browsers, videos_per_account)
                                            
        except Exception as e:
            self.log_message(f"❌ 批量上传初始化失败: {str(e)}", "ERROR")
            import traceback
            self.log_message(f"错误详情: {traceback.format_exc()}", "ERROR")
    
    def _start_batch_upload_execution(self, valid_accounts, video_files, video_dir, 
                                     concurrent_browsers, videos_per_account):
        """启动批量上传执行 - 处理UI状态和线程启动"""
        try:
            # 提取账号名称列表（保持兼容性）
            selected_accounts = [account_name for account_name, _ in valid_accounts]
            
            # 输出详细信息
            mode_text = "🔓 正式版" if self.is_licensed else "🔒 试用版"
            self.log_message(f"🚀 批量上传参数确认 ({mode_text}):")
            self.log_message(f"   📋 选中账号: {len(selected_accounts)} 个 - {selected_accounts}")
            self.log_message(f"   📁 视频目录: {video_dir}")
            self.log_message(f"   📹 视频文件: {len(video_files)} 个")
            self.log_message(f"   🌐 并发浏览器: {concurrent_browsers} 个")
            self.log_message(f"   🎬 每账号视频: {videos_per_account} 个")
            
            # 显示视频文件示例
            for i, video_file in enumerate(video_files[:3]):
                filename = os.path.basename(video_file)
                self.log_message(f"   📹 视频{i+1}: {filename}")
            if len(video_files) > 3:
                self.log_message(f"   📹 ...还有 {len(video_files)-3} 个视频文件")
            
            # 更新UI状态
            self.start_batch_upload_btn.setText("🚀 一键开始")
            self.start_batch_upload_btn.setEnabled(False)
            self.stop_batch_upload_btn.setEnabled(True)
            
            # 启动批量上传线程
            self.log_message("🚀 正在启动批量上传线程...")
            self.batch_upload_thread = BatchUploadThread(
                self.core_app,
                selected_accounts,
                video_files,
                video_dir,
                concurrent_browsers,
                videos_per_account
            )
            self.batch_upload_thread.upload_progress.connect(self.on_batch_upload_progress)
            self.batch_upload_thread.upload_status.connect(self.on_batch_upload_status)
            self.batch_upload_thread.upload_finished.connect(self.on_batch_upload_finished)
            self.batch_upload_thread.browser_status_changed.connect(self.on_browser_status_changed)
            # 🎯 连接文件删除信号，自动刷新文件列表
            self.batch_upload_thread.file_deleted.connect(self.on_file_deleted)
            # 🎯 连接账号进度更新信号，自动刷新进度显示
            self.batch_upload_thread.account_progress_updated.connect(self.on_account_progress_updated)
            self.batch_upload_thread.start()
            self.log_message("✅ 批量上传线程已启动")
            
        except Exception as e:
            # 恢复按钮状态
            self.start_batch_upload_btn.setText("🚀 一键开始")
            self.start_batch_upload_btn.setEnabled(True)
            self.log_message(f"❌ 启动批量上传线程失败: {e}", "ERROR")
            QMessageBox.critical(self, "启动失败", f"批量上传启动失败：\n{e}")
    
    def stop_batch_upload(self):
        """停止批量上传"""
        if hasattr(self, 'batch_upload_thread'):
            self.batch_upload_thread.stop()
        self.start_batch_upload_btn.setEnabled(True)
        self.stop_batch_upload_btn.setEnabled(False)
        self.log_message("⏹️ 批量上传已停止", "WARNING")
    
    def on_batch_upload_progress(self, progress):
        """批量上传进度"""
        self.log_message(f"📊 批量上传进度: {progress}%")
    
    def on_batch_upload_status(self, status):
        """批量上传状态"""
        self.log_message(f"📝 {status}")
    
    def on_batch_upload_finished(self, success, message):
        """批量上传完成"""
        self.start_batch_upload_btn.setEnabled(True)
        self.stop_batch_upload_btn.setEnabled(False)
        if success:
            self.log_message(f"✅ 批量上传完成: {message}", "SUCCESS")
        else:
            self.log_message(f"❌ 批量上传失败: {message}", "ERROR")
    
    def on_file_deleted(self, file_path):
        """🎯 处理文件删除事件 - 自动刷新文件列表"""
        try:
            filename = os.path.basename(file_path)
            self.log_message(f"🗑️ 文件已删除: {filename}", "INFO")
            
            # 🎯 延迟刷新文件列表，避免频繁刷新
            if not hasattr(self, '_file_delete_refresh_timer'):
                from PyQt5.QtCore import QTimer
                self._file_delete_refresh_timer = QTimer()
                self._file_delete_refresh_timer.setSingleShot(True)
                self._file_delete_refresh_timer.timeout.connect(self.refresh_video_list)
            
            self._file_delete_refresh_timer.start(1000)  # 1秒后刷新
            
        except Exception as e:
            # 静默处理错误
            pass
    
    def load_ui_settings(self):
        """加载界面设置"""
        try:
            config = self.core_app.config_manager.load_config()
            ui_settings = config.get('ui_settings', {})
            
            # 加载浏览器数量设置
            concurrent_browsers = ui_settings.get('concurrent_browsers', '2')
            if hasattr(self, 'concurrent_browsers_input'):
                self.concurrent_browsers_input.setText(str(concurrent_browsers))
            
            # 加载每账号视频数量设置
            videos_per_account = ui_settings.get('videos_per_account', '1')
            if hasattr(self, 'videos_per_account_input'):
                self.videos_per_account_input.setText(str(videos_per_account))
            
            # 加载视频目录设置
            video_directory = ui_settings.get('video_directory', '')
            if hasattr(self, 'video_dir_edit') and video_directory:
                self.video_dir_edit.setText(video_directory)
                self.refresh_video_list()  # 自动加载视频列表
            
            # 🎯 新增：加载账号选择状态
            saved_selections = ui_settings.get('account_selections', {})
            if saved_selections:
                self._account_selections = saved_selections
                self.log_message(f"📋 已加载账号选择状态: {saved_selections}", "INFO")
            else:
                self._account_selections = {}
                self.log_message("📋 未找到保存的账号选择状态，使用默认设置", "INFO")
            
            # 🎯 新增：加载投稿成功等待时间设置
            success_wait_time = ui_settings.get('success_wait_time', 2)  # 默认2秒
            if hasattr(self, 'success_wait_time_spinbox'):
                self.success_wait_time_spinbox.setValue(int(success_wait_time))
                self.log_message(f"⏱️ 已加载投稿成功等待时间: {success_wait_time}秒", "INFO")
            
            self.log_message("📋 界面设置已加载", "INFO")
            
        except Exception as e:
            self.log_message(f"⚠️ 加载界面设置失败: {e}", "WARNING")
    
    def on_success_wait_time_changed(self, value):
        """处理投稿成功等待时间变化"""
        try:
            self.save_ui_settings()  # 自动保存设置
            self.log_message(f"⏱️ 投稿成功等待时间已更新为: {value}秒", "INFO")
        except Exception as e:
            self.log_message(f"⚠️ 保存投稿成功等待时间失败: {e}", "WARNING")
    
    def save_ui_settings(self):
        """保存界面设置 - 性能优化版"""
        # 🎯 性能优化：延迟保存，避免频繁文件IO
        if not hasattr(self, '_save_settings_timer'):
            from PyQt5.QtCore import QTimer
            self._save_settings_timer = QTimer()
            self._save_settings_timer.setSingleShot(True)
            self._save_settings_timer.timeout.connect(self._do_save_ui_settings)
        
        # 延迟2秒保存，如果在此期间再次调用，会重置定时器
        self._save_settings_timer.start(2000)
    
    def _do_save_ui_settings(self):
        """实际执行保存操作 - 修复版：同步保存避免线程问题"""
        try:
            # 🎯 修复：改为同步保存，避免线程管理问题
            config = self.core_app.config_manager.load_config()
            if 'ui_settings' not in config:
                config['ui_settings'] = {}
            
            # 保存设置
            if hasattr(self, 'concurrent_browsers_input'):
                config['ui_settings']['concurrent_browsers'] = self.concurrent_browsers_input.text()
            
            if hasattr(self, 'videos_per_account_input'):
                config['ui_settings']['videos_per_account'] = self.videos_per_account_input.text()
            
            if hasattr(self, 'video_dir_edit'):
                config['ui_settings']['video_directory'] = self.video_dir_edit.text()
            
            # 🎯 新增：保存账号选择状态
            if hasattr(self, '_account_selections'):
                config['ui_settings']['account_selections'] = self._account_selections
                self.log_message(f"💾 保存账号选择状态: {self._account_selections}", "DEBUG")
            
            # 🎯 新增：保存投稿成功等待时间设置
            if hasattr(self, 'success_wait_time_spinbox'):
                config['ui_settings']['success_wait_time'] = self.success_wait_time_spinbox.value()
                self.log_message(f"💾 保存投稿成功等待时间: {self.success_wait_time_spinbox.value()}秒", "DEBUG")
            
            self.core_app.config_manager.save_config(config)
            
        except Exception as e:
            pass  # 静默处理错误，避免影响UI
    
    def copy_hardware_fingerprint(self):
        """复制硬件指纹到剪贴板"""
        try:
            hardware_fp = self.hardware_fp_edit.text()
            clipboard = QApplication.clipboard()
            clipboard.setText(hardware_fp)
            
            self.license_log_message("✅ 硬件指纹已复制到剪贴板")
            self.log_message("硬件指纹已复制到剪贴板", "INFO")
            
        except Exception as e:
            self.license_log_message(f"❌ 复制失败: {str(e)}")
            self.log_message(f"复制硬件指纹失败: {str(e)}", "ERROR")
    
    @prevent_double_click(duration=3.0, disable_text="验证中...")
    def verify_license(self):
        """验证许可证"""
        try:
            license_text = self.license_input.toPlainText().strip()
            if not license_text:
                QMessageBox.warning(self, "输入错误", "请先输入许可证内容")
                return
            
            result = self.license_system.verify_license(license_text)
            
            if result['valid']:
                # 更新许可证信息和授权状态
                self.license_info = result
                self.is_licensed = True
                
                self.license_log_message("✅ 许可证验证成功!")
                self.license_log_message(f"   过期时间: {result['expire_date']}")
                self.license_log_message(f"   剩余天数: {result['remaining_days']}")
                if result.get('user_info'):
                    self.license_log_message(f"   用户信息: {result['user_info']}")
                
                # 更新状态显示
                self.update_license_status()
                
                # 重新创建许可证标签页以更新界面显示
                self.refresh_license_tab()
                
                QMessageBox.information(self, "验证成功", 
                    f"🎉 许可证验证成功！程序已激活完整功能。\n\n"
                    f"过期时间: {result['expire_date']}\n"
                    f"剩余天数: {result['remaining_days']} 天\n\n"
                    "现在您可以使用所有功能，包括多账号批量上传。")
                
                self.log_message("许可证验证成功，程序已激活", "SUCCESS")
                
            else:
                self.license_log_message(f"❌ 许可证验证失败: {result['error']}")
                if 'current_hardware' in result:
                    self.license_log_message(f"   当前硬件指纹: {result['current_hardware']}")
                    self.license_log_message(f"   许可证硬件指纹: {result['license_hardware']}")
                
                QMessageBox.critical(self, "验证失败", f"许可证验证失败:\n\n{result['error']}")
                self.log_message(f"许可证验证失败: {result['error']}", "ERROR")
                
        except Exception as e:
            error_msg = f"验证许可证时发生错误: {str(e)}"
            self.license_log_message(f"❌ {error_msg}")
            QMessageBox.critical(self, "验证错误", error_msg)
            self.log_message(error_msg, "ERROR")
    
    def refresh_license_tab(self):
        """刷新许可证标签页显示"""
        try:
            # 获取许可证标签页的索引
            license_tab_index = 1  # 许可证管理是第二个标签页
            
            # 重新创建许可证标签页
            new_license_tab = self.create_license_tab()
            
            # 保存当前选中的标签页
            current_index = self.tab_widget.currentIndex()
            
            # 移除旧的许可证标签页并添加新的
            self.tab_widget.removeTab(license_tab_index)
            self.tab_widget.insertTab(license_tab_index, new_license_tab, "🔐 许可证管理")
            
            # 恢复之前选中的标签页
            self.tab_widget.setCurrentIndex(current_index)
            
        except Exception as e:
            self.log_message(f"刷新许可证标签页失败: {str(e)}", "ERROR")
    
    def save_license(self):
        """保存许可证到文件"""
        try:
            license_text = self.license_input.toPlainText().strip()
            if not license_text:
                QMessageBox.warning(self, "输入错误", "请先输入许可证内容")
                return
            
            # 先验证许可证
            result = self.license_system.verify_license(license_text)
            if not result['valid']:
                QMessageBox.critical(self, "保存失败", f"许可证无效，无法保存:\n\n{result['error']}")
                return
            
            # 保存到文件
            if self.license_system.save_license_to_file(license_text, "license.key"):
                self.license_info = result
                self.license_log_message("✅ 许可证已保存到 license.key 文件")
                self.update_license_status()
                QMessageBox.information(self, "保存成功", "许可证已成功保存到 license.key 文件")
                self.log_message("许可证已保存", "SUCCESS")
            else:
                self.license_log_message("❌ 保存许可证失败")
                QMessageBox.critical(self, "保存失败", "无法保存许可证文件")
                
        except Exception as e:
            error_msg = f"保存许可证时发生错误: {str(e)}"
            self.license_log_message(f"❌ {error_msg}")
            QMessageBox.critical(self, "保存错误", error_msg)
            self.log_message(error_msg, "ERROR")
    
    def load_license_from_file(self):
        """从文件加载许可证"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "选择许可证文件", 
                "", 
                "许可证文件 (*.key);;文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    license_content = f.read().strip()
                
                self.license_input.setPlainText(license_content)
                self.license_log_message(f"✅ 已从文件加载许可证: {os.path.basename(file_path)}")
                self.log_message(f"已加载许可证文件: {file_path}", "INFO")
                
        except Exception as e:
            error_msg = f"加载许可证文件失败: {str(e)}"
            self.license_log_message(f"❌ {error_msg}")
            QMessageBox.critical(self, "加载失败", error_msg)
            self.log_message(error_msg, "ERROR")
    
    def update_license_status(self):
        """更新许可证状态显示"""
        try:
            if hasattr(self, 'license_status_label'):
                if self.license_info and self.is_licensed:
                    status_text = f"✅ 许可证有效 | 剩余天数: {self.license_info['remaining_days']} 天 | 过期时间: {self.license_info['expire_date']}"
                    if self.license_info.get('user_info'):
                        status_text += f" | 用户: {self.license_info['user_info']}"
                    
                    self.license_status_label.setText(status_text)
                    self.license_status_label.setStyleSheet("padding: 10px; font-weight: bold; color: green;")
                else:
                    self.license_status_label.setText("⚠️ 试用模式 | 功能受限 | 请激活许可证获得完整功能")
                    self.license_status_label.setStyleSheet("padding: 10px; font-weight: bold; color: orange;")
            
            # 更新窗口标题
            if self.is_licensed:
                self.setWindowTitle("B站带货助手 v2.0 - 硬件绑定版 [已激活]")
            else:
                self.setWindowTitle("B站带货助手 v2.0 - 硬件绑定版 [试用模式]")
                
        except Exception as e:
            self.log_message(f"更新许可证状态失败: {str(e)}", "ERROR")
    
    def license_log_message(self, message):
        """添加许可证日志消息"""
        try:
            if hasattr(self, 'license_log'):
                timestamp = time.strftime("%H:%M:%S")
                formatted_message = f"[{timestamp}] {message}"
                self.license_log.append(formatted_message)
                
                # 自动滚动到底部
                cursor = self.license_log.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.license_log.setTextCursor(cursor)
        except:
            pass
    
    def closeEvent(self, event):
        """🎯 强力关闭事件 - 防止残留进程和卡死"""
        self.log_message("🔄 正在强力关闭程序...", "INFO")
        
        try:
            # 🎯 第一步：立即停止所有活动（最快）
            self._stop_all_activities()
            
            # 🎯 第二步：快速保存配置（同步，1秒超时）
            self._quick_save_config()
            
            # 🎯 第三步：强制关闭所有浏览器（并行，1秒超时）
            self._force_close_browsers()
            
            # 🎯 第四步：强制终止残留进程
            self._force_kill_remaining_processes()
            
            self.log_message("✅ 程序强力关闭完成", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 关闭过程出错: {e}", "ERROR")
        
        finally:
            # 🎯 无论如何都立即退出
            event.accept()
            QApplication.processEvents()
            
            # 🎯 最终强制退出
            import os
            os._exit(0)  # 强制退出，不等待任何清理
    
    def _stop_all_activities(self):
        """停止所有定时器和线程活动"""
        try:
            # 停止定时器
            timers = [
                'browser_status_timer', 'file_monitor_timer', 
                '_video_refresh_timer', '_file_refresh_timer',
                '_file_delete_refresh_timer', 'security_timer'
            ]
            
            for timer_name in timers:
                if hasattr(self, timer_name):
                    timer = getattr(self, timer_name)
                    if timer and hasattr(timer, 'stop'):
                        timer.stop()
            
            # 停止上传线程
            threads_to_stop = [
                'batch_upload_thread', 'upload_thread', 'login_thread',
                'license_worker', 'file_worker', 'periodic_checker'
            ]
            
            for thread_name in threads_to_stop:
                if hasattr(self, thread_name):
                    thread = getattr(self, thread_name)
                    if thread and hasattr(thread, 'stop'):
                        thread.stop()
                    if thread and hasattr(thread, 'terminate'):
                        thread.terminate()
        except:
            pass
    
    def _quick_save_config(self):
        """快速保存配置（1秒超时）"""
        try:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("保存配置超时")
            
            # 设置1秒超时（仅Unix系统）
            try:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(1)
                
                config = self.core_app.config_manager.load_config()
                if 'ui_settings' not in config:
                    config['ui_settings'] = {}
                
                if hasattr(self, 'concurrent_browsers_input'):
                    config['ui_settings']['concurrent_browsers'] = self.concurrent_browsers_input.text()
                if hasattr(self, 'videos_per_account_input'):
                    config['ui_settings']['videos_per_account'] = self.videos_per_account_input.text()
                if hasattr(self, 'video_dir_edit'):
                    config['ui_settings']['video_directory'] = self.video_dir_edit.text()
                
                self.core_app.config_manager.save_config(config)
                signal.alarm(0)  # 取消超时
                
            except (AttributeError, TimeoutError):
                # Windows系统或超时，直接跳过
                pass
                
        except:
            pass
    
    def _force_close_browsers(self):
        """强制关闭所有浏览器（并行）"""
        try:
            import threading
            import time
            
            def close_browser(account_name):
                try:
                    account = self.core_app.account_manager.get_account(account_name)
                    if hasattr(account, 'browser_instance') and account.browser_instance:
                        account.browser_instance.quit()
                except:
                    pass
            
            # 并行关闭所有浏览器
            threads = []
            for account_name in self.core_app.account_manager.get_all_accounts():
                thread = threading.Thread(target=close_browser, args=(account_name,))
                thread.daemon = True
                thread.start()
                threads.append(thread)
            
            # 等待最多1秒
            start_time = time.time()
            for thread in threads:
                remaining_time = max(0, 1 - (time.time() - start_time))
                thread.join(timeout=remaining_time)
                
        except:
            pass
    
    def _force_kill_remaining_processes(self):
        """精确清理ms-playwright相关的残留进程"""
        try:
            import psutil
            
            playwright_processes = []
            
            # 🎯 第一步：收集所有ms-playwright相关的进程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'ppid']):
                try:
                    if not proc.info['cmdline']:
                        continue
                    
                    cmdline = ' '.join(proc.info['cmdline'])
                    
                    # 只处理包含ms-playwright路径的进程
                    if 'ms-playwright' in cmdline.lower():
                        playwright_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline,
                            'proc': proc
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # 🎯 第二步：终止ms-playwright相关进程
            for proc_info in playwright_processes:
                try:
                    proc = proc_info['proc']
                    self.log_message(f"🧹 清理ms-playwright进程: {proc_info['name']} (PID: {proc_info['pid']})", "INFO")
                    
                    # 优雅终止
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)  # 等待2秒
                    except psutil.TimeoutExpired:
                        # 强制杀死
                        proc.kill()
                        proc.wait(timeout=1)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                except Exception as e:
                    self.log_message(f"⚠️ 清理进程失败: {e}", "WARNING")
            
            # 🎯 第三步：清理与ms-playwright进程相关的孤儿conhost进程
            try:
                playwright_pids = {p['pid'] for p in playwright_processes}
                
                for proc in psutil.process_iter(['pid', 'name', 'ppid']):
                    try:
                        if (proc.info['name'] and 'conhost.exe' in proc.info['name'].lower() and 
                            proc.info['ppid'] in playwright_pids):
                            
                            self.log_message(f"🧹 清理关联的conhost进程 (PID: {proc.info['pid']})", "INFO")
                            proc.terminate()
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                        
            except Exception:
                pass
            
            if playwright_processes:
                self.log_message(f"✅ 已清理 {len(playwright_processes)} 个ms-playwright相关进程", "SUCCESS")
            else:
                self.log_message("ℹ️ 未发现需要清理的ms-playwright进程", "INFO")
                
        except ImportError:
            # 如果没有psutil，跳过强制清理
            self.log_message("⚠️ 缺少psutil库，跳过进程清理", "WARNING")
        except Exception as e:
            self.log_message(f"❌ 进程清理失败: {e}", "ERROR")

    def check_license_on_startup_async(self):
        """异步启动时许可证检查"""
        license_file_path = os.path.join(os.getcwd(), "license.key")
        
        # 创建并启动许可证检查线程
        self.license_worker = LicenseWorker(self.license_system, license_file_path)
        self.license_worker.license_checked.connect(self.on_license_checked)
        self.license_worker.start()

    def on_license_checked(self, is_valid, license_info, error_msg):
        """许可证检查完成回调"""
        if is_valid:
            # 解析许可证信息
            try:
                # license_info现在是字典的字符串表示，需要使用eval来解析
                # 但为了安全，先尝试用ast.literal_eval
                import ast
                self.license_info = ast.literal_eval(license_info)
                self.is_licensed = True
                title = "B站带货助手 v2.0 [已激活]"
                self.log_message("✅ 许可证验证成功，程序已激活")
            except:
                # 如果解析失败，使用默认信息
                self.license_info = {"remaining_days": "未知", "expire_date": "未知"}
                self.is_licensed = True
                title = "B站带货助手 v2.0 [已激活]"
                self.log_message("✅ 许可证验证成功")
        else:
            # 未授权，进入试用模式
            self.license_info = None
            self.is_licensed = False
            title = "B站带货助手 v2.0 [试用模式]"
            if error_msg:
                self.log_message(f"⚠️ {error_msg}，进入试用模式")
            else:
                self.log_message("⚠️ 未找到有效许可证，进入试用模式")
        
        # 更新窗口标题
        self.setWindowTitle(title)
        
        # 如果许可证检查完成后界面已创建，刷新许可证标签页
        if hasattr(self, 'tab_widget'):
            try:
                self.refresh_license_tab()
            except:
                pass
            
    def setup_security_timer_async(self):
        """异步设置安全检查定时器"""
        license_file_path = os.path.join(os.getcwd(), "license.key")
        
        # 创建并启动定期检查线程
        self.periodic_checker = PeriodicCheckWorker(self.license_system, license_file_path)
        self.periodic_checker.check_completed.connect(self.on_periodic_check_completed)
        self.periodic_checker.start()

    def on_periodic_check_completed(self, is_valid, message):
        """定期安全检查完成回调"""
        if not is_valid:
            self.log_message(f"🚨 安全检查失败: {message}")
            # 如果许可证失效，可以选择强制退出或进入试用模式
            if "许可证失效" in message or "许可证文件丢失" in message:
                self.license_info = None
                self.is_licensed = False
                self.setWindowTitle("B站带货助手 v2.0 [试用模式]")
                self.log_message("⚠️ 许可证失效，已切换到试用模式")
                # 可选：刷新界面
                try:
                    self.refresh_license_tab()
                except:
                    pass
        # 成功的检查不需要特别处理，避免日志过多

    def save_ui_settings_async(self):
        """异步保存UI设置"""
        try:
            config = {
                "video_directory": self.video_dir_edit.text(),
                "concurrent_browsers": self.concurrent_browsers_input.text(),
                "videos_per_account": self.videos_per_account_input.text()
            }
            
            config_file = "config.json"
            
            # 如果有正在运行的文件操作线程，等待完成
            if self.file_worker and self.file_worker.isRunning():
                self.file_worker.quit()
                self.file_worker.wait()
            
            # 创建并启动文件保存线程
            self.file_worker = FileOperationWorker("save_config", config, config_file)
            self.file_worker.operation_completed.connect(self.on_config_save_completed)
            self.file_worker.start()
            
        except Exception as e:
            print(f"异步保存配置失败: {e}")

    def on_config_save_completed(self, success, message):
        """配置保存完成回调"""
        if not success:
            print(f"配置保存失败: {message}")
        # 成功时不需要特别处理，避免过多提示

    def load_ui_settings_async(self):
        """异步加载UI设置"""
        try:
            config_file = "config.json"
            
            # 创建并启动文件加载线程
            load_worker = FileOperationWorker("load_config", config_file)
            load_worker.operation_completed.connect(self.on_config_load_completed)
            load_worker.start()
            
        except Exception as e:
            print(f"异步加载配置失败: {e}")

    def on_config_load_completed(self, success, data):
        """配置加载完成回调"""
        if success:
            try:
                import json
                config = json.loads(data)
                
                # 应用配置到界面
                if "video_directory" in config:
                    self.video_dir_edit.setText(config["video_directory"])
                    # 异步刷新视频列表
                    self.refresh_video_list()
                
                if "concurrent_browsers" in config:
                    self.concurrent_browsers_input.setText(config["concurrent_browsers"])
                
                if "videos_per_account" in config:
                    self.videos_per_account_input.setText(config["videos_per_account"])
                    
            except Exception as e:
                print(f"应用配置失败: {e}")

    def check_license_before_operation_async(self, operation_name="操作", callback=None):
        """异步操作前许可证检查"""
        if self.is_licensed:
            # 已授权，直接执行回调
            if callback:
                callback(True)
            return True
        
        # 未授权，检查试用版限制
        self.log_message(f"⚠️ {operation_name}需要完整许可证，当前为试用模式")
        
        # 试用版可以继续，但有功能限制
        if callback:
            callback(False)  # 传递试用模式状态
        return False

    def get_trial_limitations_text(self):
        """获取试用版限制说明"""
        return """
🔒 试用版功能限制：

• 单次上传视频数量限制为 1 个
• 同时打开浏览器数量限制为 1 个
• 批量上传功能受限
• 无法保存上传配置

💡 获取完整版许可证：
1. 复制当前硬件指纹
2. 联系开发者获取许可证
3. 在许可证管理页面激活
"""



    def on_account_progress_updated(self, account_name):
        """🎯 处理账号进度更新事件 - 自动刷新指定账号的进度显示"""
        try:
            self.log_message(f"📊 账号 {account_name} 发布进度已更新，刷新显示", "INFO")
            
            # 获取目标数量
            target_count = 1
            if hasattr(self, 'videos_per_account_input'):
                try:
                    target_count = int(self.videos_per_account_input.text())
                except:
                    target_count = 1
            
            from core.account_manager import account_manager
            
            # 查找对应的表格行并更新进度
            for row in range(self.account_table.rowCount()):
                username_item = self.account_table.item(row, 1)
                if username_item and username_item.text() == account_name:
                    try:
                        # 获取最新进度
                        status, completed, published = account_manager.get_account_progress(account_name, target_count)
                        
                        # 更新今日已发列（第5列）
                        today_published_item = self.account_table.item(row, 5)
                        if today_published_item:
                            today_published_item.setText(str(published))
                            if completed:
                                today_published_item.setBackground(QColor(144, 238, 144))  # 已完成：绿色
                            else:
                                today_published_item.setBackground(QColor(255, 255, 200))  # 进行中：淡黄色
                        
                        # 更新进度状态列（第6列）
                        progress_item = self.account_table.item(row, 6)
                        if progress_item:
                            progress_item.setText(status)
                            if completed:
                                progress_item.setBackground(QColor(144, 238, 144))  # 已完成：绿色
                                progress_item.setForeground(QColor(0, 100, 0))     # 深绿色字体
                            else:
                                progress_item.setBackground(QColor(255, 255, 200))  # 进行中：淡黄色
                                progress_item.setForeground(QColor(100, 100, 0))   # 深黄色字体
                        
                        self.log_message(f"✅ 账号 {account_name} 进度显示已更新: {status}", "SUCCESS")
                        
                        # 🎯 新增：同时更新账号统计信息
                        try:
                            self._update_account_stats_with_progress(target_count)
                        except:
                            pass  # 忽略统计更新失败
                        
                        break
                        
                    except Exception as e:
                        # 如果获取进度失败，显示错误状态
                        today_published_item = self.account_table.item(row, 5)
                        if today_published_item:
                            today_published_item.setText("错误")
                            today_published_item.setBackground(QColor(255, 182, 193))  # 错误：红色
                        
                        progress_item = self.account_table.item(row, 6)
                        if progress_item:
                            progress_item.setText("获取失败")
                            progress_item.setBackground(QColor(255, 182, 193))  # 错误：红色
                            progress_item.setForeground(QColor(100, 0, 0))     # 深红色字体
                        
                        self.log_message(f"❌ 更新账号 {account_name} 进度显示失败: {e}", "ERROR")
                        break
            
        except Exception as e:
            self.log_message(f"❌ 处理账号进度更新事件失败: {str(e)}", "ERROR")

    def on_videos_per_account_changed(self):
        """🎯 处理每账号视频数量变化事件 - 实时更新所有账号的进度显示"""
        try:
            # 获取新的目标数量
            try:
                new_target = int(self.videos_per_account_input.text())
                if new_target <= 0:
                    return  # 无效数量，不更新
            except (ValueError, AttributeError):
                return  # 无效输入，不更新
            
            # 如果账号表格不存在，直接返回
            if not hasattr(self, 'account_table') or not self.account_table:
                return
            
            from core.account_manager import account_manager
            
            # 遍历表格中的所有账号并更新进度
            updated_count = 0
            for row in range(self.account_table.rowCount()):
                username_item = self.account_table.item(row, 1)
                if username_item:
                    username = username_item.text()
                    
                    try:
                        # 🎯 使用新的目标数量重新计算进度
                        status, completed, published = account_manager.get_account_progress(username, new_target)
                        
                        # 更新今日已发列（第5列） - 这个数量不变
                        today_published_item = self.account_table.item(row, 5)
                        if today_published_item:
                            today_published_item.setText(str(published))
                            # 根据新目标判断完成状态并设置背景色
                            if completed:
                                today_published_item.setBackground(QColor(144, 238, 144))  # 已完成：绿色
                            else:
                                today_published_item.setBackground(QColor(255, 255, 200))  # 进行中：淡黄色
                        
                        # 🎯 更新进度状态列（第6列） - 这个会根据新目标显示不同的状态
                        progress_item = self.account_table.item(row, 6)
                        if progress_item:
                            progress_item.setText(status)  # 新的状态字符串，如 "5/10 进行中"
                            if completed:
                                progress_item.setBackground(QColor(144, 238, 144))  # 已完成：绿色
                                progress_item.setForeground(QColor(0, 100, 0))     # 深绿色字体
                            else:
                                progress_item.setBackground(QColor(255, 255, 200))  # 进行中：淡黄色
                                progress_item.setForeground(QColor(100, 100, 0))   # 深黄色字体
                        
                        updated_count += 1
                        
                    except Exception as e:
                        # 如果获取进度失败，显示错误状态
                        today_published_item = self.account_table.item(row, 5)
                        if today_published_item:
                            today_published_item.setText("错误")
                            today_published_item.setBackground(QColor(255, 182, 193))  # 错误：红色
                        
                        progress_item = self.account_table.item(row, 6)
                        if progress_item:
                            progress_item.setText("获取失败")
                            progress_item.setBackground(QColor(255, 182, 193))  # 错误：红色
                            progress_item.setForeground(QColor(100, 0, 0))     # 深红色字体
            
            if updated_count > 0:
                self.log_message(f"📊 目标数量已更新为 {new_target}，已刷新 {updated_count} 个账号的进度显示", "INFO")
                
                # 🎯 新增：同时更新账号统计信息，显示完成状态
                self._update_account_stats_with_progress(new_target)
            
        except Exception as e:
            self.log_message(f"❌ 更新账号进度显示失败: {str(e)}", "ERROR")

    def _update_account_stats_with_progress(self, target_count):
        """🎯 更新带有进度信息的账号统计显示"""
        try:
            if not hasattr(self, 'account_stats_label') or not hasattr(self, 'account_table'):
                return
            
            from core.account_manager import account_manager
            
            total_accounts = 0
            active_accounts = 0
            completed_accounts = 0
            in_progress_accounts = 0
            
            # 遍历账号表格统计信息
            for row in range(self.account_table.rowCount()):
                username_item = self.account_table.item(row, 1)
                login_status_item = self.account_table.item(row, 2)
                
                if username_item:
                    total_accounts += 1
                    username = username_item.text()
                    
                    # 统计活跃账号（登录状态为"已登录"）
                    if login_status_item and "已登录" in login_status_item.text():
                        active_accounts += 1
                    
                    # 统计完成状态
                    try:
                        status, completed, published = account_manager.get_account_progress(username, target_count)
                        if completed:
                            completed_accounts += 1
                        elif published > 0:
                            in_progress_accounts += 1
                    except:
                        pass  # 忽略获取进度失败的情况
            
            # 构建统计信息文本
            stats_text = (
                f"账号统计：总数 {total_accounts}，活跃 {active_accounts} | "
                f"进度：已完成 {completed_accounts}，进行中 {in_progress_accounts}，"
                f"未开始 {total_accounts - completed_accounts - in_progress_accounts}"
            )
            
            self.account_stats_label.setText(stats_text)
            
        except Exception as e:
            # 如果更新失败，回退到基本统计
            try:
                accounts = self.core_app.account_manager.get_all_accounts()
                total_accounts = len(accounts)
                active_accounts = len([a for a in accounts if self.core_app.account_manager.get_account(a).status == 'active'])
                stats_text = f"账号统计：总数 {total_accounts}，活跃 {active_accounts}"
                self.account_stats_label.setText(stats_text)
            except:
                pass




if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())