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
from core.config import Config, UIConfig
from gui.ui_styles import UIStyles
from core.bilibili_video_uploader import BilibiliVideoUploader
from core.license_system import LicenseSystem
from gui.utils.button_utils import prevent_double_click, protect_button_click

# 在导入部分添加 Services 模块的导入
from services.account_service import AccountService

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
    account_progress_updated = pyqtSignal(str)  # 🎯 新增：账号进度更新信号
    
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
        
    def mark_video_uploaded(self, file_path, account, product_id):
        """标记视频已上传 - 数据库版本，增强错误处理"""
        import hashlib
        import os
        from datetime import datetime
        
        try:
            # 🔍 步骤1：验证文件存在性
            if not os.path.exists(file_path):
                self.upload_status.emit(f"❌ [{self.account_name}] 文件不存在: {os.path.basename(file_path)}")
                return False
            
            # 🔍 步骤2：计算文件MD5（增强错误处理）
            self.upload_status.emit(f"🔍 [{self.account_name}] 开始计算MD5: {os.path.basename(file_path)}")
            hash_md5 = hashlib.md5()
            try:
                file_size = os.path.getsize(file_path)
                self.upload_status.emit(f"📊 [{self.account_name}] 文件大小: {file_size} 字节")
                
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
                
                md5_hash = hash_md5.hexdigest()
                self.upload_status.emit(f"✅ [{self.account_name}] MD5计算完成: {md5_hash[:8]}...")
                
            except PermissionError:
                self.upload_status.emit(f"❌ [{self.account_name}] 文件权限错误，无法读取: {os.path.basename(file_path)}")
                return False
            except IOError as e:
                self.upload_status.emit(f"❌ [{self.account_name}] 文件读取错误: {os.path.basename(file_path)} - {e}")
                return False
            except Exception as e:
                self.upload_status.emit(f"❌ [{self.account_name}] MD5计算异常: {os.path.basename(file_path)} - {e}")
                return False
        
            # 🔍 步骤3：数据库记录（增强错误处理和重试机制）
            try:
                self.upload_status.emit(f"📊 开始数据库记录: 账号={account}, 商品ID={product_id}")
                
                # 导入数据库管理器
                from database.database_manager import db_manager
                
                # 检查数据库连接
                self.upload_status.emit(f"🔍 检查数据库连接...")
                try:
                    # 测试数据库连接
                    with db_manager.get_connection() as test_conn:
                        test_cursor = test_conn.cursor()
                        test_cursor.execute("SELECT 1")
                        test_result = test_cursor.fetchone()
                        if test_result:
                            self.upload_status.emit(f"✅ 数据库连接正常")
                        else:
                            self.upload_status.emit(f"❌ 数据库连接测试失败")
                            return False
                except Exception as conn_e:
                    self.upload_status.emit(f"❌ 数据库连接失败: {conn_e}")
                    return False
                
                # 尝试添加记录（最多重试3次）
                for attempt in range(3):
                    self.upload_status.emit(f"🔄 数据库记录尝试 {attempt + 1}/3")
                    
                    success = db_manager.add_uploaded_video(
                        md5_hash=md5_hash,
                        filename=os.path.basename(file_path),
                        account_username=account,
                        upload_date=datetime.now().strftime("%Y-%m-%d"),
                        product_id=product_id,
                        file_size=file_size
                    )
                    
                    if success:
                        self.upload_status.emit(f"✅ 数据库记录成功: {os.path.basename(file_path)}")
                        return True
                    else:
                        self.upload_status.emit(f"⚠️ 数据库记录失败，尝试 {attempt + 1}/3")
                        if attempt < 2:  # 不是最后一次尝试
                            import time
                            time.sleep(1)  # 等待1秒后重试
                
                # 所有重试都失败
                self.upload_status.emit(f"❌ 数据库记录失败: 所有重试都失败")
                
                # 🔍 尝试手动检查是否已记录
                try:
                    if db_manager.is_video_uploaded(md5_hash):
                        self.upload_status.emit(f"🔍 检查发现视频已在数据库中，可能是重复记录")
                        return True
                    else:
                        self.upload_status.emit(f"🔍 确认视频未在数据库中")
                except Exception as check_e:
                    self.upload_status.emit(f"⚠️ 无法检查视频状态: {check_e}")
                
                return False
                
            except ImportError:
                self.upload_status.emit(f"❌ 无法导入数据库管理器")
                return False
            except Exception as db_e:
                import traceback
                error_trace = traceback.format_exc()
                self.upload_status.emit(f"❌ 数据库操作异常: {db_e}")
                self.upload_status.emit(f"❌ 异常详情: {error_trace}")
                return False
                
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.upload_status.emit(f"❌ mark_video_uploaded 总体异常: {e}")
            self.upload_status.emit(f"❌ 异常详情: {error_trace}")
            return False
        
    def run(self):
        try:
            # 步骤1: 验证账号和浏览器
            self.upload_status.emit(f"[{self.account_name}] 验证账号状态...")
            self.upload_progress.emit(10)
            
            account = self.core_app.account_manager.get_account(self.account_name)
            if not account:
                self.upload_finished.emit(False, "账号不存在")
                return
            
            # 兼容dict和Account对象格式
            if hasattr(account, '_data'):
                # TempAccount包装对象
                account_status = account.status
            elif isinstance(account, dict):
                # 原始dict格式
                account_status = account.get('status', 'inactive')
            else:
                # Account对象格式
                account_status = account.status
            
            if account_status != 'active':
                self.upload_finished.emit(False, "账号未激活，请先登录")
                return
                
            if self.is_stopped:
                return
                
            # 步骤2: 验证视频文件
            self.upload_status.emit(f"[{self.account_name}] 验证视频文件...")
            self.upload_progress.emit(20)
            
            video_path = os.path.join(self.video_directory, self.video_filename)
            if not os.path.exists(video_path):
                self.upload_finished.emit(False, f"视频文件不存在: {video_path}")
                return
                
            # 步骤3: 验证商品ID
            self.upload_status.emit(f"[{self.account_name}] 验证商品信息...")
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
                
            self.upload_status.emit(f"[{self.account_name}] 商品验证成功: {product_info.get('goodsName', '未知商品')}")
            self.upload_progress.emit(40)
            
            if self.is_stopped:
                return
                
            # 步骤4: 启动浏览器并访问创作中心
            self.upload_status.emit(f"[{self.account_name}] 启动浏览器...")
            self.upload_progress.emit(50)
            
            # 获取浏览器实例
            if hasattr(account, 'browser_instance') and account.browser_instance:
                driver = account.browser_instance
            else:
                self.upload_finished.emit(False, "账号浏览器实例不存在，请重新登录")
                return
                
            # 访问创作中心
            self.upload_status.emit(f"[{self.account_name}] 访问B站创作中心...")
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
            self.upload_status.emit(f"[{self.account_name}] 开始真实上传视频文件...")
            from core.bilibili_video_uploader import create_uploader
            uploader = create_uploader(self.upload_status.emit, self.core_app.config_manager)
            
            # 真实上传视频文件
            self.upload_status.emit(f"📤 [{self.account_name}] 上传视频文件...")
            success = uploader.upload_video(driver, video_path, self.account_name)
            if not success:
                self.upload_finished.emit(False, "视频上传失败")
                return
                
            self.upload_progress.emit(80)
            
            # 步骤6: 使用独立上传器填写视频信息
            self.upload_status.emit(f"[{self.account_name}] 填写视频信息...")
            success = uploader.fill_video_info(driver, self.video_filename, self.upload_settings, product_info, self.account_name)
            if not success:
                self.upload_finished.emit(False, "填写视频信息失败")
                return
                
            self.upload_progress.emit(85)
            
            # 步骤7: 使用独立上传器添加商品
            self.upload_status.emit(f"[{self.account_name}] 添加带货商品...")
            success = uploader.add_product_to_video(driver, self.video_filename, product_info, self.account_name)
            if not success:
                self.upload_finished.emit(False, "添加商品失败")
                return
                
            self.upload_progress.emit(95)
            
            # 🎯 优化：设置投稿成功回调，在投稿成功后立即更新数据库和界面
            def success_callback():
                """投稿成功后的回调：立即更新数据库和界面"""
                try:
                    self.upload_status.emit(f"🎯 开始成功回调：视频={os.path.basename(video_path)}, 账号={self.account_name}, 商品ID={product_id}")
                    
                    # 立即更新数据库
                    db_success = self.mark_video_uploaded(video_path, self.account_name, product_id)
                    self.upload_status.emit(f"📊 数据库更新结果: {db_success}")
                    
                    if db_success:
                        # 立即发送界面更新信号
                        self.account_progress_updated.emit(self.account_name)
                        self.upload_status.emit(f"✅ 成功回调完成：已发送界面更新信号")
                        return True
                    else:
                        self.upload_status.emit(f"❌ 数据库记录失败，检查mark_video_uploaded方法")
                        return False
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    self.upload_status.emit(f"❌ 成功回调异常: {e}")
                    self.upload_status.emit(f"❌ 异常详情:\n{error_trace}")
                    return False
            
            # 设置回调
            uploader.success_callback = success_callback
            
            # 步骤8: 使用独立上传器发布视频（成功时会自动调用回调更新数据库和界面）
            self.upload_status.emit(f"[{self.account_name}] 发布视频...")
            success = uploader.publish_video(driver, self.account_name)
            
            # 🎯 重要：清除回调避免影响其他使用
            uploader.success_callback = None
            
            if not success:
                self.upload_finished.emit(False, "发布视频失败")
                return
                
            # 🎯 优化：发布成功，数据库更新和界面刷新已在回调中完成
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
        # 🎯 修复：不保存固定值，而是保存获取最新值的方法
        self._initial_videos_per_account = videos_per_account  # 保留初始值作为后备
        self.main_window = None  # 稍后设置
        self.is_stopped = False
        
        # 🎯 初始化共享上传器
        try:
            from core.bilibili_video_uploader import BilibiliVideoUploader
            self.shared_uploader = BilibiliVideoUploader(self.upload_status.emit, self.core_app.config_manager)
            # 🔧 关键修复：确保没有遗留的回调
            self.shared_uploader.success_callback = None
        except ImportError:
            # 后备方案：使用工厂函数
            try:
                from core.bilibili_video_uploader import create_uploader
                self.shared_uploader = create_uploader(self.upload_status.emit, self.core_app.config_manager)
                # 🔧 关键修复：确保没有遗留的回调
                if self.shared_uploader:
                    self.shared_uploader.success_callback = None
            except ImportError:
                self.shared_uploader = None
        
        # 🎯 创建账号弹窗处理记录（每个账号只处理一次）
        self.account_popup_handled = {}
        
        # 🎯 账号服务注入点
        self.account_service = None
        
        # 加载已上传视频记录
        self.uploaded_videos_md5 = self.load_uploaded_videos()

    def load_uploaded_videos(self):
        """从文件加载已上传的视频MD5列表 - 兼容性保留"""
        try:
            # 这里主要为了兼容性，实际使用数据库
            return set()
        except Exception:
            return set()
    
    def save_uploaded_videos(self):
        """保存已上传视频记录 - 兼容性保留"""
        try:
            # 这里主要为了兼容性，实际使用数据库
            pass
        except Exception:
            pass

    def get_current_videos_per_account(self):
        """🎯 实时获取当前的每账号视频数量设置"""
        try:
            # 从主窗口获取最新的设置值
            if (self.main_window and 
                hasattr(self.main_window, 'videos_per_account_input') and 
                self.main_window.videos_per_account_input):
                current_value = int(self.main_window.videos_per_account_input.text())
                self.upload_status.emit(f"🎯 实时获取目标数量: {current_value}")
                return current_value
            else:
                # 后备方案：使用初始值
                self.upload_status.emit(f"⚠️ 无法获取实时设置，使用初始值: {self._initial_videos_per_account}")
                return self._initial_videos_per_account
        except (ValueError, AttributeError) as e:
            # 如果获取失败，使用初始值
            self.upload_status.emit(f"⚠️ 获取实时设置失败: {e}，使用初始值: {self._initial_videos_per_account}")
            return self._initial_videos_per_account

    @property
    def videos_per_account(self):
        """🎯 动态属性：每次访问都获取最新值"""
        return self.get_current_videos_per_account()
    
    def load_uploaded_videos(self):
        """加载已上传视频MD5记录 - SQLite增强版"""
        try:
            # 🚀 优先使用数据库模式
            from database.database_manager import db_manager
            
            # 加载所有视频记录到内存，兼容现有代码结构
            uploaded_videos = {}
            
            # 获取所有上传记录（这里可以优化为按需加载）
            # 但为了兼容现有的MD5检查逻辑，暂时全量加载
            # 数据库模式：直接查询数据库获取上传记录
            
            self.upload_status.emit("📊 从数据库加载上传记录...")
            return uploaded_videos  # 暂时返回空字典，依赖数据库查询
            
        except Exception as e:
            # ❌ JSON模式已废弃，直接返回空字典
            self.upload_status.emit(f"❌ 数据库加载失败: {e}")
            return {}
    
    def save_uploaded_videos(self):
        """保存已上传视频MD5记录 - 数据库版本（已废弃JSON）"""
        # ❌ JSON模式已废弃，此方法仅保留兼容性，实际数据已保存到数据库
        pass
    
    def get_file_md5(self, file_path):
        """获取文件MD5值 - 使用缓存优化"""
        from performance.video_file_loader import get_global_md5_cache
        return get_global_md5_cache().get_file_md5(file_path)
    
    def is_video_uploaded(self, file_path):
        """检查视频是否已上传 - SQLite增强版"""
        md5_hash = self.get_file_md5(file_path)
        if not md5_hash:
            return False
        
        try:
            # 🚀 优先使用数据库查询
            from database.database_manager import db_manager
            return db_manager.is_video_uploaded(md5_hash)
        except Exception as e:
            # 回退到内存模式
            return md5_hash in self.uploaded_videos_md5
    
    def mark_video_uploaded(self, file_path, account, product_id):
        """标记视频已上传 - SQLite增强版，添加详细调试"""
        try:
            self.upload_status.emit(f"🔍 [{account}] 开始标记视频上传: {os.path.basename(file_path)}")
            
            # 步骤1：验证文件存在性
            if not os.path.exists(file_path):
                self.upload_status.emit(f"❌ [{account}] 文件不存在: {os.path.basename(file_path)}")
                return False
            
            # 步骤2：计算MD5
            md5_hash = self.get_file_md5(file_path)
            if not md5_hash:
                self.upload_status.emit(f"❌ [{account}] 无法计算文件MD5: {os.path.basename(file_path)}")
                return False
            
            self.upload_status.emit(f"✅ [{account}] MD5计算完成: {md5_hash[:8]}...")
            
            from datetime import datetime
            
            # 步骤3：数据库记录（增强版）
            try:
                # 导入并测试数据库连接
                from database.database_manager import db_manager
                self.upload_status.emit(f"🔍 [{account}] 检查数据库连接...")
                
                # 测试连接
                try:
                    with db_manager.get_connection() as test_conn:
                        test_cursor = test_conn.cursor()
                        test_cursor.execute("SELECT 1")
                        if test_cursor.fetchone():
                            self.upload_status.emit(f"✅ [{account}] 数据库连接正常")
                        else:
                            self.upload_status.emit(f"❌ [{account}] 数据库连接测试失败")
                            return False
                except Exception as conn_e:
                    self.upload_status.emit(f"❌ [{account}] 数据库连接失败: {conn_e}")
                    return False
                
                # 重试机制添加记录
                for attempt in range(3):
                    self.upload_status.emit(f"🔄 [{account}] 数据库记录尝试 {attempt + 1}/3")
                    
                    try:
                        file_size = os.path.getsize(file_path)
                        success = db_manager.add_uploaded_video(
                            md5_hash=md5_hash,
                            filename=os.path.basename(file_path),
                            account_username=account,
                            upload_date=datetime.now().strftime("%Y-%m-%d"),
                            product_id=product_id,
                            file_size=file_size
                        )
                        
                        if success:
                            self.upload_status.emit(f"✅ [{account}] 数据库记录成功: {os.path.basename(file_path)}")
                            # 🎯 关键修复：只有数据库记录成功才清除进度缓存
                            self._clear_progress_cache()
                            return True
                        else:
                            self.upload_status.emit(f"⚠️ [{account}] 数据库记录失败，尝试 {attempt + 1}/3")
                            if attempt < 2:  # 不是最后一次尝试
                                import time
                                time.sleep(1)  # 等待1秒后重试
                    except Exception as record_e:
                        self.upload_status.emit(f"⚠️ [{account}] 记录异常: {record_e}")
                        if attempt < 2:
                            import time
                            time.sleep(1)
                
                # 所有重试都失败，尝试检查是否已存在
                self.upload_status.emit(f"❌ [{account}] 数据库记录失败: 所有重试都失败")
                
                try:
                    if db_manager.is_video_uploaded(md5_hash):
                        self.upload_status.emit(f"🔍 [{account}] 检查发现视频已在数据库中，可能是重复记录")
                        self._clear_progress_cache()
                        return True
                    else:
                        self.upload_status.emit(f"🔍 [{account}] 确认视频未在数据库中")
                except Exception as check_e:
                    self.upload_status.emit(f"⚠️ [{account}] 无法检查视频状态: {check_e}")
                
                return False
                
            except ImportError:
                self.upload_status.emit(f"❌ [{account}] 无法导入数据库管理器")
                return False
            except Exception as db_e:
                import traceback
                error_trace = traceback.format_exc()
                self.upload_status.emit(f"❌ [{account}] 数据库操作异常: {db_e}")
                self.upload_status.emit(f"❌ [{account}] 异常详情: {error_trace}")
                return False
        
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.upload_status.emit(f"❌ [{account}] mark_video_uploaded 总体异常: {e}")
            self.upload_status.emit(f"❌ [{account}] 异常详情: {error_trace}")
            return False

    def _clear_progress_cache(self):
        """清除进度缓存 - 确保数据一致性"""
        try:
            # 清除UI层缓存
            if hasattr(self, '_progress_cache'):
                self._progress_cache.clear()
                self._progress_cache_time.clear()
            
            # 清除service层缓存
            if hasattr(self, 'account_service') and self.account_service:
                from services.account_service import AccountService
                AccountService.clear_progress_cache()
                
        except Exception as e:
            self.log_message(f"⚠️ 清除进度缓存失败: {e}", "WARNING")

    def delete_video_file(self, file_path):
        """删除视频文件 - 数据库版本"""
        try:
            # 🎯 先计算MD5，再删除文件
            md5_hash = self.get_file_md5(file_path)
            
            # 删除文件
            os.remove(file_path)
            
            # 🚀 更新数据库记录为已删除
            if md5_hash:
                try:
                    from database.database_manager import db_manager
                    db_manager.mark_video_deleted(md5_hash)
                    self.upload_status.emit(f"📊 数据库标记删除: {os.path.basename(file_path)}")
                except Exception as e:
                    self.upload_status.emit(f"⚠️ 数据库标记删除失败: {e}")
                
                # 🎯 关键修复：文件删除后清除进度缓存
                self._clear_progress_cache()
            
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
        """批量上传主逻辑 - 安全并发版本"""
        try:
            # 🎯 步骤0：内存监控
            import psutil
            initial_memory = 0
            try:
                process = psutil.Process()
                initial_memory = process.memory_info().rss / 1024 / 1024
                self.upload_status.emit(f"📊 初始内存使用: {initial_memory:.1f}MB")
            except:
                pass
            
            # 🎯 步骤1：验证账号并过滤已完成的账号
            valid_accounts = []
            completed_accounts = []
            
            for account in self.selected_accounts:
                account_obj = self.core_app.account_manager.get_account(account)
                if not account_obj:
                    self.upload_status.emit(f"⚠️ 账号 {account} 无效，跳过")
                    continue
                
                # 🔧 关键修复：检查账号投稿进度
                try:
                    from database.database_manager import db_manager
                    status_text, is_completed, published_count = db_manager.get_account_progress(account, self.videos_per_account)
                    
                    if is_completed:
                        completed_accounts.append(account)
                        self.upload_status.emit(f"✅ 账号 {account} 已完成目标 ({published_count}/{self.videos_per_account})，跳过")
                        continue
                    elif published_count >= self.videos_per_account:
                        completed_accounts.append(account)
                        self.upload_status.emit(f"✅ 账号 {account} 已超过目标 ({published_count}/{self.videos_per_account})，跳过")
                        continue
                    else:
                        valid_accounts.append(account)
                        self.upload_status.emit(f"📋 账号 {account} 需要继续上传 ({published_count}/{self.videos_per_account})")
                        
                except Exception as e:
                    # 如果检查进度失败，默认认为需要上传
                    valid_accounts.append(account)
                    self.upload_status.emit(f"⚠️ 账号 {account} 进度检查失败: {e}，默认加入上传队列")
            
            # 报告统计结果
            if completed_accounts:
                self.upload_status.emit(f"📊 已完成账号: {len(completed_accounts)} 个 ({', '.join(completed_accounts)})")
            
            if not valid_accounts:
                if completed_accounts:
                    self.upload_finished.emit(True, f"所有账号都已完成目标！已完成: {len(completed_accounts)} 个账号")
                else:
                    self.upload_finished.emit(False, "没有有效的账号可以上传")
                return
            
            self.upload_status.emit(f"🚀 需要上传的账号: {len(valid_accounts)} 个 ({', '.join(valid_accounts)})")
            
            # 🔧 步骤1.5：清理缓存和锁，确保检查基于最新状态
            try:
                from performance.video_file_loader import get_global_md5_cache, get_global_upload_coordinator
                
                md5_cache = get_global_md5_cache()
                upload_coordinator = get_global_upload_coordinator()
                
                # 清理过期的MD5缓存和文件锁
                md5_cache._cleanup_expired_cache()
                upload_coordinator.clear_completed_locks()
                
                self.upload_status.emit("🧹 已清理缓存和锁，确保状态检查准确")
            except Exception as e:
                self.upload_status.emit(f"⚠️ 清理缓存失败: {e}")
            
            # 🎯 步骤2：准备视频文件
            from core.bilibili_product_manager import get_product_manager
            product_manager = get_product_manager()
            
            all_video_files = []
            skipped_count = 0
            for video_file in self.video_files:
                video_path = os.path.join(self.video_dir, video_file)
                if not os.path.exists(video_path):
                    self.upload_status.emit(f"⚠️ 文件不存在，跳过: {video_file}")
                    skipped_count += 1
                elif self.is_video_uploaded(video_path):
                    self.upload_status.emit(f"⏭️ 已上传，跳过: {video_file}")
                    skipped_count += 1
                else:
                    all_video_files.append(video_path)
            
            if skipped_count > 0:
                self.upload_status.emit(f"📊 初始过滤：跳过 {skipped_count} 个已处理视频，剩余 {len(all_video_files)} 个")
            
            if not all_video_files:
                self.upload_finished.emit(False, "没有可上传的视频文件（所有视频都已处理）")
                return
            
            # 🎯 步骤3：随机化视频列表并预估需求
            import random
            random.shuffle(all_video_files)
            
            # 🔧 关键修复：基于需要上传的账号计算视频需求，而不是总账号数
            # 先预估每个账号的需求（实际分配时会更精确）
            estimated_videos_needed = len(valid_accounts) * self.videos_per_account
            available_videos = all_video_files[:estimated_videos_needed] if len(all_video_files) >= estimated_videos_needed else all_video_files
            
            self.upload_status.emit(f"📊 准备上传: {len(available_videos)} 个视频文件")
            self.upload_status.emit(f"🎯 预估目标: 每个账号最多 {self.videos_per_account} 个视频，待处理账号 {len(valid_accounts)} 个")
            self.upload_status.emit(f"🌐 并发浏览器数量: {self.concurrent_browsers}")
            
            # 🎯 步骤4：为每个账号预分配视频队列（关键：避免竞争且考虑现有进度）
            account_video_queues = {}
            video_index = 0
            
            self.upload_status.emit("📊 检查账号投稿进度...")
            
            for account in valid_accounts:
                # 🔧 关键修复：检查账号当前投稿进度
                try:
                    from database.database_manager import db_manager
                    status_text, is_completed, published_count = db_manager.get_account_progress(account, self.videos_per_account)
                    
                    if is_completed:
                        # 账号已完成目标，跳过分配
                        account_video_queues[account] = []
                        self.upload_status.emit(f"✅ [{account}] 已完成目标 ({published_count}/{self.videos_per_account})，跳过")
                        continue
                    
                    # 计算还需要上传的数量
                    remaining_needed = self.videos_per_account - published_count
                    if remaining_needed <= 0:
                        account_video_queues[account] = []
                        self.upload_status.emit(f"✅ [{account}] 无需额外上传 ({published_count}/{self.videos_per_account})")
                        continue
                    
                    # 为账号分配剩余需要的视频数量
                    account_video_queues[account] = []
                    for i in range(remaining_needed):
                        if video_index < len(available_videos):
                            account_video_queues[account].append(available_videos[video_index])
                            video_index += 1
                        else:
                            break
                    
                    self.upload_status.emit(f"📋 [{account}] 预分配 {len(account_video_queues[account])} 个视频 (已有:{published_count}, 目标:{self.videos_per_account})")
                    
                except Exception as e:
                    # 如果检查进度失败，按原逻辑分配
                    self.upload_status.emit(f"⚠️ [{account}] 进度检查失败: {e}，按原逻辑分配")
                    account_video_queues[account] = []
                    for i in range(self.videos_per_account):
                        if video_index < len(available_videos):
                            account_video_queues[account].append(available_videos[video_index])
                            video_index += 1
                        else:
                            break
                    
                    self.upload_status.emit(f"📋 [{account}] 预分配 {len(account_video_queues[account])} 个视频 (未检查进度)")
            
            # 🔧 检查是否有账号需要执行任务
            accounts_with_tasks = [account for account, videos in account_video_queues.items() if videos]
            if not accounts_with_tasks:
                self.upload_status.emit("✅ 所有账号都已完成目标或无需上传，批量上传结束")
                self.upload_finished.emit(True, "所有账号都已完成目标！")
                return
            
            self.upload_status.emit(f"🎯 实际需要执行的账号: {len(accounts_with_tasks)} 个 ({', '.join(accounts_with_tasks)})")
            
            # 🎯 步骤5：并发执行账号任务
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading
            
            # 线程安全的进度计数器
            progress_lock = threading.Lock()
            total_processed = 0
            total_successful = 0
            
            def process_account(account):
                """处理单个账号的上传任务"""
                nonlocal total_processed, total_successful
                
                try:
                    self.upload_status.emit(f"🎯 [{account}] 开始并发任务")
                    
                    # 启动账号的浏览器
                    account_obj = self.core_app.account_manager.get_account(account)
                    browser = self.ensure_browser_ready(account, account_obj)
                    if not browser:
                        self.upload_status.emit(f"❌ [{account}] 浏览器启动失败，跳过")
                        return 0, 0
                    
                    self.upload_status.emit(f"✅ [{account}] 浏览器就绪，开始上传")
                    self.browser_status_changed.emit(account, True)
                    
                    account_uploaded = 0
                    account_processed = 0
                    account_videos = account_video_queues.get(account, [])
                    
                    # 处理分配给这个账号的视频
                    for video_path in account_videos:
                        if self.is_stopped:
                            break
                        
                        filename = os.path.basename(video_path)
                        account_processed += 1
                        
                        self.upload_status.emit(f"📹 [{account}] 第{account_processed}个视频: {filename}")
                        
                        try:
                            # 🔧 关键修复1：动态检查账号是否已达到目标数量
                            try:
                                from database.database_manager import db_manager
                                _, is_completed, current_count = db_manager.get_account_progress(account, self.videos_per_account)
                                if is_completed:
                                    self.upload_status.emit(f"🎉 [{account}] 已达到目标数量 ({current_count}/{self.videos_per_account})，停止上传")
                                    break
                                elif current_count >= self.videos_per_account:
                                    self.upload_status.emit(f"🎉 [{account}] 已超过目标数量 ({current_count}/{self.videos_per_account})，停止上传")
                                    break
                            except Exception as check_error:
                                self.upload_status.emit(f"⚠️ [{account}] 动态进度检查失败: {check_error}")
                            
                            # 🔧 关键修复2：动态检查视频是否已被其他账号上传
                            if self.is_video_uploaded(video_path):
                                self.upload_status.emit(f"⏭️ [{account}] 视频 {filename} 已被其他账号上传，跳过")
                                with progress_lock:
                                    total_processed += 1
                                continue
                            
                            # 验证商品ID
                            product_id = product_manager.extract_product_id_from_filename(filename)
                            if not product_id:
                                self.upload_status.emit(f"❌ [{account}] {filename} 无商品ID，删除继续")
                                if self.delete_video_file(video_path):
                                    with progress_lock:
                                        total_processed += 1
                                continue
                            
                            # 验证商品信息
                            cookies = product_manager.get_cookies_from_account(account_obj)
                            if not cookies:
                                self.upload_status.emit(f"❌ [{account}] 无法获取Cookie，跳过")
                                continue
                            
                            jd_url = product_manager.build_jd_url(product_id)
                            success, product_info = product_manager.distinguish_product(jd_url, cookies)
                            
                            if not success or not product_info:
                                self.upload_status.emit(f"❌ [{account}] 商品{product_id}不在库中，删除{filename}")
                                if self.delete_video_file(video_path):
                                    with progress_lock:
                                        total_processed += 1
                                continue
                            
                            # 🎯 执行上传（使用协调器确保原子性）
                            self.upload_status.emit(f"🚀 [{account}] 开始上传: {filename}")
                            
                            from performance.video_file_loader import get_global_upload_coordinator
                            coordinator = get_global_upload_coordinator()
                            
                            upload_success, upload_message = coordinator.safe_upload_video(
                                video_path, account, self.shared_uploader, browser, product_info, self
                            )
                            
                            if upload_success:
                                account_uploaded += 1
                                with progress_lock:
                                    total_successful += 1
                                    total_processed += 1
                                
                                self.upload_status.emit(f"✅ [{account}] 第{account_uploaded}个成功: {upload_message}")
                                self.upload_status.emit(f"📊 [{account}] 进度: {account_uploaded}/{len(account_videos)}")
                                
                                # 投稿成功后的延时
                                if account_uploaded < len(account_videos):
                                    try:
                                        config = self.core_app.config_manager.load_config()
                                        wait_time = config.get('ui_settings', {}).get('success_wait_time', 2)
                                        wait_time = max(1, min(999, int(wait_time)))
                                        
                                        self.upload_status.emit(f"⏳ [{account}] 投稿成功，等待 {wait_time} 秒后继续...")
                                        for i in range(wait_time):
                                            if self.is_stopped:
                                                break
                                            time.sleep(1)
                                    except:
                                        time.sleep(2)
                            else:
                                self.upload_status.emit(f"⚠️ [{account}] 上传失败: {upload_message}")
                                with progress_lock:
                                    total_processed += 1
                            
                            # 定期刷新浏览器
                            refresh_interval = self.core_app.config_manager.load_config().get('ui_settings', {}).get('browser_refresh_interval', 5)
                            if account_processed % refresh_interval == 0:
                                try:
                                    self.upload_status.emit(f"🔄 [{account}] 刷新浏览器状态...")
                                    browser.get("https://member.bilibili.com/platform/upload/video/frame")
                                    time.sleep(2)
                                except Exception as refresh_error:
                                    self.upload_status.emit(f"⚠️ [{account}] 刷新浏览器失败: {refresh_error}")
                            
                            # 更新总体进度
                            with progress_lock:
                                progress = int((total_processed / len(available_videos)) * 100)
                                self.upload_progress.emit(progress)
                        
                        except Exception as e:
                            self.upload_status.emit(f"❌ [{account}] 处理视频 {filename} 时异常: {e}")
                            with progress_lock:
                                total_processed += 1
                            continue
                    
                    # 🔧 智能任务完成判断 - 包含最终进度验证
                    try:
                        from database.database_manager import db_manager
                        _, final_is_completed, final_count = db_manager.get_account_progress(account, self.videos_per_account)
                        
                        if final_is_completed or final_count >= self.videos_per_account:
                            self.upload_status.emit(f"🎉 [{account}] 目标达成！数据库显示: {final_count}/{self.videos_per_account}")
                        elif account_uploaded >= self.videos_per_account:
                            self.upload_status.emit(f"🎉 [{account}] 本轮目标达成！本轮上传: {account_uploaded}/{self.videos_per_account}")
                        elif account_processed >= len(account_videos):
                            self.upload_status.emit(f"🏁 [{account}] 队列完成！本轮成功: {account_uploaded}/{len(account_videos)}（目标:{self.videos_per_account}，总计:{final_count}）")
                        else:
                            self.upload_status.emit(f"🛑 [{account}] 任务中断！本轮成功: {account_uploaded}/{len(account_videos)}（总计:{final_count}）")
                    except Exception as final_check_error:
                        # 后备判断逻辑
                        if account_uploaded >= self.videos_per_account:
                            self.upload_status.emit(f"🎉 [{account}] 目标达成！成功上传: {account_uploaded}/{self.videos_per_account}")
                        elif account_processed >= len(account_videos):
                            self.upload_status.emit(f"🏁 [{account}] 队列完成！成功上传: {account_uploaded}/{len(account_videos)}（目标:{self.videos_per_account}）")
                        else:
                            self.upload_status.emit(f"🛑 [{account}] 任务中断！成功上传: {account_uploaded}/{len(account_videos)}")
                    
                    # 关闭浏览器
                    try:
                        self.core_app.browser_manager.close_driver(browser, account)
                        account_obj.browser_instance = None
                        self.browser_status_changed.emit(account, False)
                        self.upload_status.emit(f"🔒 [{account}] 浏览器已关闭")
                    except Exception as e:
                        self.upload_status.emit(f"⚠️ [{account}] 关闭浏览器失败: {e}")
                    
                    return account_processed, account_uploaded
                
                except Exception as e:
                    self.upload_status.emit(f"❌ [{account}] 账号处理异常: {e}")
                    # 确保浏览器关闭
                    try:
                        if 'browser' in locals() and browser:
                            self.core_app.browser_manager.close_driver(browser, account)
                            account_obj.browser_instance = None
                            self.browser_status_changed.emit(account, False)
                    except:
                        pass
                    return 0, 0
            
            # 🎯 使用ThreadPoolExecutor进行并发执行
            self.upload_status.emit(f"🚀 开始 {self.concurrent_browsers} 个并发任务...")
            self.upload_status.emit(f"🔍 调试信息: 有效账号={len(valid_accounts)}, 并发数={self.concurrent_browsers}, 实际并发数={min(len(valid_accounts), self.concurrent_browsers)}")
            
            with ThreadPoolExecutor(max_workers=self.concurrent_browsers, thread_name_prefix="BatchUpload") as executor:
                # 提交所有账号任务
                future_to_account = {executor.submit(process_account, account): account for account in valid_accounts}
                
                # 等待所有任务完成
                for future in as_completed(future_to_account):
                    account = future_to_account[future]
                    try:
                        processed, uploaded = future.result()
                        self.upload_status.emit(f"📋 [{account}] 任务完成统计: 处理{processed}个，成功{uploaded}个")
                    except Exception as e:
                        self.upload_status.emit(f"❌ [{account}] 任务执行异常: {e}")
            
            # 🎯 输出最终统计
            try:
                if initial_memory > 0:
                    final_memory = process.memory_info().rss / 1024 / 1024
                    memory_used = final_memory - initial_memory
                    self.upload_status.emit(f"📊 最终内存使用: {final_memory:.1f}MB (增加: {memory_used:+.1f}MB)")
            except:
                pass
            
            message = f"✅ 并发批量上传完成！总处理 {total_processed} 个视频，成功 {total_successful} 个"
            self.upload_finished.emit(True, message)
            
        except Exception as e:
            import traceback
            error_msg = f"并发批量上传异常: {str(e)}"
            detailed_error = f"异常详情:\n{traceback.format_exc()}"
            
            self.upload_status.emit(f"❌ {error_msg}")
            self.upload_status.emit(f"🔍 {detailed_error}")
            self.upload_finished.emit(False, error_msg)
                
        finally:
            # 🎯 确保清理所有浏览器实例
            try:
                self.upload_status.emit("🧹 正在清理并发上传资源...")
                
                # 清理所有可能的浏览器实例
                for account in self.selected_accounts:
                    try:
                        account_obj = self.core_app.account_manager.get_account(account)
                        if account_obj and hasattr(account_obj, 'browser_instance') and account_obj.browser_instance:
                            self.core_app.browser_manager.close_driver(account_obj.browser_instance, account)
                            account_obj.browser_instance = None
                            self.browser_status_changed.emit(account, False)
                            self.upload_status.emit(f"🔒 清理时关闭 {account} 的浏览器")
                    except:
                        pass
                
                import gc
                gc.collect()
                self.upload_status.emit("✅ 并发批量上传资源清理完成")
                
            except Exception as cleanup_error:
                self.upload_status.emit(f"⚠️ 清理资源时出错: {cleanup_error}")

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
        """🎯 安全停止许可证检查线程"""
        try:
            self.running = False
            # 🎯 修复：不立即调用quit()，先等待线程自然结束
            if self.isRunning():
                # 等待线程完成当前任务
                if not self.wait(3000):  # 等待3秒
                    # 如果3秒后还没结束，强制终止
                    self.terminate()
                    self.wait(1000)  # 再等1秒确保终止
        except Exception as e:
            # 静默处理停止过程中的异常
            pass


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
        
        # 🎯 启动浏览器状态监控器
        try:
            self.browser_monitor.start_monitoring()  # 启动核心监控器
            self.setup_browser_status_timer()  # 设置GUI状态缓存
            self.log_message("🔧 浏览器状态监控已启动", "INFO")
        except Exception as e:
            self.log_message(f"⚠️ 浏览器状态监控启动失败: {e}", "WARNING")
        
        self.load_data()
        
        # 🎯 初始化日志过滤器
        self._current_account_filter = "全部账号"  # 默认显示全部账号

        # 原有的性能优化补丁已清理，性能问题应通过重构解决
        
        # 🎯 启动日志缓冲区定时刷新，确保日志及时显示
        self._setup_log_flush_timer()

        self.log_message(f"{Config.APP_NAME} v{Config.APP_VERSION} 启动完成")
    
    def _initialize_services(self):
        """初始化服务层"""
        try:
            # 🔧 简化启动日志，只记录关键信息
            
            # 🚀 初始化性能优化组件
            self._initialize_performance_components()
            
            from services import (
                AccountService, UploadService, LicenseService, 
                FileService, SettingsService
            )
            
            # 初始化各个服务，每个都有独立的错误处理
            self._init_account_service(AccountService)
            self._init_upload_service(UploadService)
            self._init_license_service(LicenseService)
            self._init_file_service(FileService)
            self._init_settings_service(SettingsService)
            
            self.log_message("✅ 服务层初始化完成", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 服务层初始化失败: {e}", "ERROR")
            # 提供后备的空服务，防止AttributeError
            self._create_fallback_services()
    
    def _init_account_service(self, AccountService):
        """初始化账号服务"""
        try:
            self.account_service = AccountService(self)
            if not self.account_service.initialize():
                self.log_message("❌ 账号服务初始化失败", "ERROR")
        except Exception as e:
            self.log_message(f"❌ 账号服务初始化错误: {e}", "ERROR")
            self.account_service = None
    
    def _init_upload_service(self, UploadService):
        """初始化上传服务"""
        try:
            self.upload_service = UploadService(self)
            if not self.upload_service.initialize():
                self.log_message("❌ 上传服务初始化失败", "ERROR")
        except Exception as e:
            self.log_message(f"❌ 上传服务初始化错误: {e}", "ERROR")
            self.upload_service = None
    
    def _init_license_service(self, LicenseService):
        """初始化许可证服务"""
        try:
            self.license_service = LicenseService(self)
            if not self.license_service.initialize():
                self.log_message("❌ 许可证服务初始化失败", "ERROR")
        except Exception as e:
            self.log_message(f"❌ 许可证服务初始化错误: {e}", "ERROR")
            self.license_service = None
    
    def _init_file_service(self, FileService):
        """初始化文件服务"""
        try:
            self.file_service = FileService(self)
            if not self.file_service.initialize():
                self.log_message("❌ 文件服务初始化失败", "ERROR")
        except Exception as e:
            self.log_message(f"❌ 文件服务初始化错误: {e}", "ERROR")
            self.file_service = None
    
    def _init_settings_service(self, SettingsService):
        """初始化设置服务"""
        try:
            self.settings_service = SettingsService(self)
            if not self.settings_service.initialize():
                self.log_message("❌ 设置服务初始化失败", "ERROR")
        except Exception as e:
            self.log_message(f"❌ 设置服务初始化错误: {e}", "ERROR")
            self.settings_service = None
    
    def _create_fallback_services(self):
        """创建后备服务，防止AttributeError"""
        class FallbackService:
            def __getattr__(self, name):
                def fallback_method(*args, **kwargs):
                    print(f"⚠️ 服务未初始化，调用 {name} 被忽略")
                    return False
                return fallback_method
        
        if not hasattr(self, 'account_service') or self.account_service is None:
            self.account_service = FallbackService()
        if not hasattr(self, 'upload_service') or self.upload_service is None:
            self.upload_service = FallbackService()
        if not hasattr(self, 'license_service') or self.license_service is None:
            self.license_service = FallbackService()
        if not hasattr(self, 'file_service') or self.file_service is None:
            self.file_service = FallbackService()
        if not hasattr(self, 'settings_service') or self.settings_service is None:
            self.settings_service = FallbackService()
    
    def _initialize_performance_components(self):
        """初始化性能优化组件"""
        try:
            from performance import CacheManager, TaskQueue, MemoryManager, ResourcePool
            
            # 初始化缓存管理器
            self.cache_manager = CacheManager(max_size=500, default_ttl=600)
            
            # 初始化任务队列
            self.task_queue = TaskQueue(max_workers=3)
            
            # 初始化内存管理器
            self.memory_manager = MemoryManager(gc_threshold=200.0, auto_gc_interval=600)
            
            # 添加内存警告回调
            def memory_warning_callback(message):
                self.log_message(f"⚠️ 内存警告: {message}", "WARNING")
            
            if hasattr(self.memory_manager, 'add_warning_callback'):
                self.memory_manager.add_warning_callback(memory_warning_callback)
            
            # 只在全部成功时记录一条日志
            self.log_message("✅ 性能组件初始化完成", "SUCCESS")
            
        except ImportError as e:
            self.log_message(f"⚠️ 性能组件不可用: {e}", "WARNING")
            # 创建后备的空组件
            self.cache_manager = None
            self.task_queue = None
            self.memory_manager = None
        except Exception as e:
            self.log_message(f"❌ 性能组件初始化失败: {e}", "ERROR")
            self.cache_manager = None
            self.task_queue = None
            self.memory_manager = None
    
    def _init_optimized_video_loader(self):
        """🚀 初始化高性能视频文件加载器"""
        try:
            from performance.video_file_loader import OptimizedVideoListManager
            
            # 确保视频列表组件存在
            if hasattr(self, 'video_list') and hasattr(self, 'video_stats_label'):
                self.video_loader_manager = OptimizedVideoListManager(
                    self.video_list, 
                    self.video_stats_label
                )
                self.log_message("🚀 高性能视频文件加载器已初始化", "SUCCESS")
            else:
                self.video_loader_manager = None
                self.log_message("⚠️ 视频组件未就绪，跳过加载器初始化", "WARNING")
                
        except ImportError as e:
            self.log_message(f"⚠️ 视频文件加载器不可用: {e}", "WARNING")
            self.video_loader_manager = None
        except Exception as e:
            self.log_message(f"❌ 视频文件加载器初始化失败: {e}", "ERROR")
            self.video_loader_manager = None
    
    def set_window_icon(self):
        """设置窗口图标"""
        try:
            # 🎯 修复：在EXE环境中，优先使用PNG图标
            icon_paths = [
                "icons/icon_32x32.png",        # 32x32 PNG图标
                "icons/icon_48x48.png",        # 48x48 PNG图标  
                "icons/icon_64x64.png",        # 64x64 PNG图标
                "icons/app_icon.ico",          # ICO文件（如果存在）
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
            
            # 🎯 如果在EXE环境中找不到外部图标文件，尝试从资源中获取
            try:
                # 在PyInstaller打包的EXE中，资源文件可能在不同位置
                import sys
                if getattr(sys, 'frozen', False):
                    # 在EXE环境中，尝试从临时目录查找
                    if hasattr(sys, '_MEIPASS'):
                        base_path = sys._MEIPASS
                        icon_paths = [
                            os.path.join(base_path, "icons", "icon_32x32.png"),
                            os.path.join(base_path, "icons", "icon_48x48.png"),
                        ]
                        
                        for icon_path in icon_paths:
                            if os.path.exists(icon_path):
                                icon = QIcon(icon_path)
                                if not icon.isNull():
                                    self.setWindowIcon(icon)
                                    self.log_message(f"✅ 从资源加载图标: {icon_path}", "INFO")
                                    return
            except:
                pass
            
            # 如果所有尝试都失败，使用应用程序默认图标
            self.log_message("⚠️ 未找到图标文件，使用默认图标", "WARNING")
            
        except Exception as e:
            self.log_message(f"⚠️ 设置图标时出错: {e}", "WARNING")
    
    def create_account_tab(self):
        """创建账号管理标签页 - 使用模块化组件"""
        from gui.tabs.account_tab import AccountTab
        
        account_tab = AccountTab(self)
        return account_tab.create_widget()
    
    def create_license_tab(self):
        """创建许可证标签页 - 使用模块化组件"""
        from gui.tabs.license_tab import LicenseTab
        
        license_tab = LicenseTab(self)
        return license_tab.create_widget()
    
    def create_upload_tab(self):
        """创建上传标签页 - 使用模块化组件"""
        from gui.tabs.upload_tab import UploadTab
        
        upload_tab = UploadTab(self)
        return upload_tab.create_widget()

    def create_log_tab(self):
        """创建日志标签页 - 使用模块化组件"""
        from gui.tabs.log_tab import LogTab
        
        self.log_tab_instance = LogTab(self)
        widget = self.log_tab_instance.create_widget()
        
        # 🎯 创建完成后立即更新账号列表
        if hasattr(self, 'core_app'):
            try:
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(100, self.log_tab_instance.update_account_list)
            except:
                pass
        
        return widget
    
    def setup_browser_status_timer(self):
        """🔧 优化版浏览器状态监控 - 禁用GUI重复检查，统一使用核心监控器"""
        try:
            # 🔧 优化：移除GUI层面的重复检查，避免双重HTTP请求
            # 核心监控器 (browser_status_monitor.py) 已经每30秒检查一次所有账号
            # GUI层面的额外检查是不必要的，会造成资源浪费
            
            # 初始化缓存（保持兼容性）
            if not hasattr(self, '_browser_status_cache'):
                self._browser_status_cache = {}
            
            self.log_message("🔧 浏览器状态监控已优化 (使用核心监控器，避免重复检查)", "INFO")
            
        except Exception as e:
            self.log_message(f"⚠️ 浏览器状态监控设置失败: {e}", "WARNING")
    
    def update_browser_status_async(self):
        """🎯 增强版：使用异步任务队列优化浏览器状态检测"""
        try:
            # 获取当前账号列表
            accounts = []
            for row in range(self.account_table.rowCount()):
                username_item = self.account_table.item(row, 1)
                if username_item:
                    accounts.append(username_item.text())
            
            if not accounts:
                return
            
            # 🚀 使用异步任务队列处理耗时的浏览器状态检测
            if hasattr(self, 'task_queue') and self.task_queue:
                # 性能优化：限制每次检查的账号数量
                max_check_count = min(3, len(accounts))
                
                # 轮询检查：使用计数器确保所有账号都能被检查到
                if not hasattr(self, '_browser_check_counter'):
                    self._browser_check_counter = 0
                
                start_index = self._browser_check_counter % len(accounts)
                accounts_to_check = []
                
                for i in range(max_check_count):
                    index = (start_index + i) % len(accounts)
                    accounts_to_check.append(accounts[index])
                
                # 更新计数器
                self._browser_check_counter = (self._browser_check_counter + max_check_count) % len(accounts)
                
                # 🚀 提交异步任务检测浏览器状态
                for username in accounts_to_check:
                    def check_browser_task(user):
                        try:
                            return user, self.is_browser_active(user)
                        except:
                            return user, False
                    
                    def on_check_complete(result):
                        if result:
                            username, is_active = result
                            self.on_browser_status_checked(username, is_active)
                    
                    # 🎯 修复：检查task_queue是否真正可用（不是DummyManager）
                    if (hasattr(self, 'task_queue') and self.task_queue and 
                        hasattr(self.task_queue, 'submit') and callable(self.task_queue.submit)):
                        self.task_queue.submit(
                            check_browser_task, username,
                            callback=on_check_complete,
                            name=f"browser_check_{username}"
                        )
                    else:
                        # 直接执行任务（后备方案）
                        result = check_browser_task(username)
                        on_check_complete(result)
            else:
                # 后备方案：同步处理
                self._update_browser_status_sync()
            
        except Exception as e:
            # 静默处理错误
            pass
    
    def _update_browser_status_sync(self):
        """同步版本的浏览器状态更新（后备方案）"""
        try:
            accounts = []
            for row in range(self.account_table.rowCount()):
                username_item = self.account_table.item(row, 1)
                if username_item:
                    accounts.append(username_item.text())
            
            if not accounts:
                return
            
            max_check_count = min(3, len(accounts))
            
            if not hasattr(self, '_browser_check_counter'):
                self._browser_check_counter = 0
            
            start_index = self._browser_check_counter % len(accounts)
            accounts_to_check = []
            
            for i in range(max_check_count):
                index = (start_index + i) % len(accounts)
                accounts_to_check.append(accounts[index])
            
            self._browser_check_counter = (self._browser_check_counter + max_check_count) % len(accounts)
            
            for username in accounts_to_check:
                try:
                    is_active = self.is_browser_active(username)
                    self.on_browser_status_checked(username, is_active)
                except Exception as e:
                    # 🔧 改进：记录异常详情而不是静默忽略
                    self.log_message(f"⚠️ 检查账号 {username} 浏览器状态失败: {type(e).__name__}: {e}", "WARNING")
                    self.on_browser_status_checked(username, False)
            
        except Exception as e:
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
                
                # 只有距离上次日志超过300秒才记录，减少状态变化日志
                if current_time - last_log > 300:
                    self.log_message(f"🔄 {username} -> {new_status}", "DEBUG")  # 改为DEBUG级别
                    self._last_status_log[username] = current_time
                    
        except Exception as e:
            # 静默处理错误
            pass

    def load_data(self):
        """🎯 简化版数据加载 - 减少线程和定时器使用"""
        # 🆕 首先初始化服务层
        self._initialize_services()
        
        # 🚀 初始化高性能视频文件加载器
        self._init_optimized_video_loader()
        
        self.load_ui_settings()  # 🎯 修复：先加载设置，包括账号选择状态
        self.refresh_accounts()  # 然后刷新账号，应用加载的选择状态
        self.refresh_video_list()  # 然后刷新视频列表
        self.refresh_account_combo()
        
        # 🎯 账号进度已在refresh_accounts中自动加载，无需额外刷新
        
        # 🎯 临时禁用文件监控，避免定时器问题
        # QTimer.singleShot(2000, self.setup_file_monitor)  # 暂时注释掉
    
    def log_message(self, message: str, level: str = "INFO", account: str = None):
        """🎯 安全的日志消息添加 - 修复闪退问题，支持账号标识"""
        try:
            # 🎯 修复1：线程安全检查
            from PyQt5.QtCore import QThread, QTimer
            if QThread.currentThread() != self.thread():
                # 如果不在主线程，使用QTimer延迟到主线程执行
                QTimer.singleShot(0, lambda: self._safe_log_message(message, level, account))
                return
            
            self._safe_log_message(message, level, account)
            
        except Exception as e:
            # 🎯 静默处理日志异常，防止无限递归
            print(f"日志记录异常: {e}")
    
    def _safe_log_message(self, message: str, level: str = "INFO", account: str = None):
        """🎯 安全的日志消息处理 - 主线程执行，优化日志过滤，支持账号标识"""
        try:
            if not hasattr(self, 'log_text') or not self.log_text:
                return
            
            # 🎯 新增：日志级别过滤，减少不必要的输出
            if not self._should_log(message, level):
                return
            
            # 🎯 从消息中自动提取账号信息
            if account is None:
                account = self._extract_account_from_message(message)
            
            # 🎯 修复2：HTML转义，防止注入攻击和解析异常
            import html
            safe_message = html.escape(str(message))
            
            # 🎯 修复3：限制单条日志长度，防止超长日志导致崩溃
            if len(safe_message) > 500:  # 进一步减少到500字符
                safe_message = safe_message[:497] + "..."
            
            # 🎯 修复4：初始化日志计数和缓冲区
            if not hasattr(self, '_log_count'):
                self._log_count = 0
            if not hasattr(self, '_log_buffer'):
                self._log_buffer = []
            if not hasattr(self, '_original_log_buffer'):
                self._original_log_buffer = []  # 保存所有原始日志用于账号过滤
            
            # 🎯 修复5：使用缓冲区批量更新，减少DOM操作
            timestamp = time.strftime("%H:%M:%S")
            
            # 简化颜色处理
            color_map = {
                "ERROR": "#dc3545",
                "WARNING": "#ffc107", 
                "SUCCESS": "#28a745",
                "INFO": "#17a2b8"
            }
            color = color_map.get(level, "#17a2b8")
            
            # 🎯 修复6：简化HTML格式，减少解析开销，添加账号标识
            if account:
                log_entry = f'[{timestamp}] [{account}] {safe_message}'
            else:
                log_entry = f'[{timestamp}] {safe_message}'
            
            # 🎯 新增：保存到原始日志缓冲区（用于账号过滤）
            self._original_log_buffer.append((log_entry, color, account))
            
            # 🎯 应用当前的账号过滤
            current_filter = getattr(self, '_current_account_filter', '全部账号')
            if current_filter == "全部账号" or account == current_filter or account is None:
                self._log_buffer.append((log_entry, color))
            
            # 🎯 修复7：批量清理日志，防止内存溢出
            if self._log_count > 200:  # 进一步降低到200条
                try:
                    self.log_text.clear()
                    self._log_count = 0
                    self._log_buffer.clear()
                    # 同时清理原始缓冲区
                    self._original_log_buffer = self._original_log_buffer[-50:]  # 只保留最近50条
                    self.log_text.append("--- 日志已清理 ---")
                except:
                    pass
            
            # 🎯 修复8：批量更新UI，每10条或缓冲区满时更新
            if len(self._log_buffer) >= 10 or self._log_count % 50 == 0:
                self._flush_log_buffer()
            
        except Exception as e:
            # 🎯 静默处理异常，防止日志功能影响主程序
            try:
                print(f"安全日志记录异常: {e}")
            except:
                pass
    
    def _extract_account_from_message(self, message: str) -> str:
        """从日志消息中提取账号信息"""
        try:
            import re
            # 匹配 [账号名] 格式
            match = re.search(r'\[([^\]]+)\]', message)
            if match:
                potential_account = match.group(1)
                # 验证是否是有效的账号名（手机号格式）
                if re.match(r'^\d{11}$', potential_account):
                    return potential_account
            return None
        except:
            return None
    
    def _should_log(self, message: str, level: str) -> bool:
        """🎯 平衡版日志过滤器 - 保留重要信息，过滤技术细节"""
        # 🎯 检查是否开启详细日志模式
        verbose_mode = getattr(self, '_verbose_logging', False)
        if verbose_mode:
            return True  # 详细模式下显示所有日志
        
        # 🚫 只过滤技术细节，保留用户关心的流程信息
        technical_filters = [
            # 过于详细的技术步骤
            "导航到", "智能等待", "尝试方法", "方法1成功", "JavaScript成功",
            "✅ 找到", "✅ 已点击", "✅ 已输入", "✅ 已选中", "✅ 已选择",
            "确定按钮已就绪", "确定窗口已消失", "iframe", "在当前iframe",
            "滚动到页面", "按钮消失", "按钮仍在", "使用配置的",
            
            # 系统状态细节
            "📋 账号选择状态", "💾 保存", "📂 已更新", "🔍 检查账号",
            "-> 活跃", "-> 未活跃", "浏览器状态", "🔄 状态刷新",
            
            # 性能调试信息
            "🔧", "🎯", "💻", "🌐", "👤", "🚀 启动异步", "扫描进度",
            "高性能", "缓存", "性能组件", "视频文件加载器", "异步更新"
        ]
        
        # 🚫 过滤DEBUG级别的消息
        if level == "DEBUG":
            return False
        
        # 🚫 过滤技术细节
        for filter_keyword in technical_filters:
            if filter_keyword in message:
                return False
        
        # 🚫 过滤重复的状态消息
        if hasattr(self, '_last_logged_messages'):
            if message in self._last_logged_messages:
                return False
        else:
            self._last_logged_messages = set()
        
        # 记录最近的消息，防止重复（最多记录50条）
        if len(self._last_logged_messages) > 50:
            self._last_logged_messages.clear()
        self._last_logged_messages.add(message)
        
        # ✅ 保留用户关心的重要信息
        important_keywords = [
            # 投稿流程关键步骤
            "🚀 开始投稿", "视频上传完成", "📝 提取标题", "标题填写成功", 
            "话题选择成功", "商品添加流程", "🎉 视频投稿成功", "投稿失败",
            
            # 文件操作
            "🗑️ 文件已删除", "📊 数据库记录", "📊 数据库标记",
            
            # 账号操作
            "登录成功", "登录失败", "添加账号", "删除账号", "进度显示已更新",
            
            # 批量上传
            "开始批量上传", "批量上传", "上传完成", "上传失败", "第.*个视频",
            
            # 程序状态
            "程序启动", "启动完成", "构建", "初始化", "诊断",
            
            # 重要图标
            "✅", "❌", "⚠️", "🚀", "🎉", "🗑️", "📝", "📊"
        ]
        
        # 💯 显示错误、警告和重要操作
        if level in ["ERROR", "WARNING", "SUCCESS"]:
            return True
        
        # 💯 显示包含重要关键词的信息
        for keyword in important_keywords:
            if keyword in message:
                return True
        
        # 💯 显示简短的INFO信息
        if level == "INFO" and len(message) < 80:
            return True
        
        # 过滤其他冗长的技术细节
        return False
    
    def _flush_log_buffer(self):
        """🎯 刷新日志缓冲区 - 批量更新UI"""
        try:
            if not hasattr(self, '_log_buffer') or not self._log_buffer:
                return
            
            if not hasattr(self, 'log_text') or not self.log_text:
                return
            
            # 🎯 批量构建HTML内容
            html_content = ""
            for log_entry, color in self._log_buffer:
                html_content += f'<div style="color: {color}; margin: 1px 0;">{log_entry}</div>'
            
            # 🎯 一次性添加到文本框
            if html_content:
                try:
                    self.log_text.append(html_content)
                    self._log_count += len(self._log_buffer)
                except:
                    # 如果HTML添加失败，使用纯文本方式
                    plain_content = "\n".join([entry for entry, _ in self._log_buffer])
                    self.log_text.append(plain_content)
                    self._log_count += len(self._log_buffer)
            
            # 清空缓冲区
            self._log_buffer.clear()
            
            # 🎯 修复9：安全的自动滚动
            try:
                if hasattr(self, 'auto_scroll') and getattr(self, 'auto_scroll', True):
                    # 使用更安全的滚动方式
                    scrollbar = self.log_text.verticalScrollBar()
                    if scrollbar:
                        scrollbar.setValue(scrollbar.maximum())
            except:
                # 滚动失败时静默处理
                pass
                
        except Exception as e:
            try:
                print(f"刷新日志缓冲区异常: {e}")
            except:
                pass
    
    def _setup_log_flush_timer(self):
        """🎯 设置日志缓冲区定时刷新机制"""
        try:
            from PyQt5.QtCore import QTimer
            # 创建定时器，每2秒自动刷新一次日志缓冲区
            if not hasattr(self, '_log_flush_timer'):
                self._log_flush_timer = QTimer()
                self._log_flush_timer.timeout.connect(self._flush_log_buffer)
                self._log_flush_timer.start(2000)  # 每2秒刷新一次
        except Exception as e:
            print(f"设置日志刷新定时器失败: {e}")
    
    @prevent_double_click(duration=3.0, disable_text="添加中...")
    def add_account(self):
        """添加账号 - 使用服务层"""
        username, ok = QInputDialog.getText(self, "添加账号", "请输入账号名:")
        if ok and username:
            if self.account_service.add_account(username):
                # 🚀 失效账号缓存，确保界面更新
                if hasattr(self, '_invalidate_account_cache'):
                    self._invalidate_account_cache()
                # 🚀 强制延迟刷新，确保界面立即显示新账号
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(100, self.refresh_accounts)
                QTimer.singleShot(500, self.refresh_accounts)  # 双重保险确保刷新
    
    @prevent_double_click(duration=5.0, disable_text="登录中...")
    def login_account(self):
        """登录账号 - 使用服务层"""
        selected_rows = self.account_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "提示", "请选择要登录的账号")
            return
        
        row = selected_rows[0].row()
        username = self.account_table.item(row, 1).text()
        
        # 使用服务层启动登录
        self.account_service.start_login(username)
    
    def on_login_success(self, username):
        """登录成功处理"""
        self.log_message(f"账号 {username} 登录成功", "SUCCESS")
        self.refresh_accounts()
    
    def on_login_failed(self, username, error):
        """登录失败处理"""
        self.log_message(f"账号 {username} 登录失败: {error}", "ERROR")
        self.refresh_accounts()
    
    def remove_account(self):
        """删除账号 - 使用服务层"""
        selected_rows = self.account_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "提示", "请选择要删除的账号")
            return
        
        row = selected_rows[0].row()
        username = self.account_table.item(row, 1).text()
        
        reply = QMessageBox.question(self, "确认删除", f"确定要删除账号 {username} 吗？")
        if reply == QMessageBox.Yes:
            if self.account_service.remove_account(username):
                # 🚀 失效账号缓存，确保界面更新
                if hasattr(self, '_invalidate_account_cache'):
                    self._invalidate_account_cache()
                # 🚀 强制延迟刷新，确保界面立即更新
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(100, self.refresh_accounts)
                QTimer.singleShot(500, self.refresh_accounts)  # 双重保险确保刷新
    

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
                        # 兼容dict和Account对象格式
                        if hasattr(account, '_data'):
                            # TempAccount包装对象
                            account_status = account.status
                        elif isinstance(account, dict):
                            # 原始dict格式
                            account_status = account.get('status', 'inactive')
                        else:
                            # Account对象格式
                            account_status = account.status
                        
                        status = "✅ 活跃" if account_status == 'active' else "❌ 未登录"
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
        """刷新账号列表 - 性能优化版：防抖动+快速更新"""
        try:
            # 🎯 性能优化：防抖动机制 - 避免短时间内重复刷新
            current_time = time.time()
            if not hasattr(self, '_last_refresh_time'):
                self._last_refresh_time = 0
            
            # 如果距离上次刷新不到0.5秒，启用防抖动
            if current_time - self._last_refresh_time < 0.5:
                if not hasattr(self, '_refresh_debounce_timer'):
                    self._refresh_debounce_timer = QTimer()
                    self._refresh_debounce_timer.setSingleShot(True)
                    self._refresh_debounce_timer.timeout.connect(self._do_refresh_accounts)
                
                # 重置定时器，延迟500ms执行
                self._refresh_debounce_timer.start(500)
                return
            
            self._last_refresh_time = current_time
            self._do_refresh_accounts()
            
        except Exception as e:
            self.log_message(f"❌ 刷新账号列表失败: {str(e)}", "ERROR")
    
    def _do_refresh_accounts(self):
        """实际执行账号刷新"""
        try:
            accounts = self.core_app.account_manager.get_all_accounts()
            
            if not hasattr(self, 'account_table'):
                return
            
            # 🎯 性能优化：减少日志输出，只在账号数量变化时记录
            if len(accounts) > 0:
                if not hasattr(self, '_last_account_count') or self._last_account_count != len(accounts):
                    self.log_message(f"📋 账号列表已更新 ({len(accounts)} 个)", "INFO")
                    self._last_account_count = len(accounts)
            
            # 🎯 性能优化：暂时断开信号，避免频繁触发
            self.account_table.blockSignals(True)
            
            self.account_table.setRowCount(len(accounts))
            
            for row, username in enumerate(accounts):
                account = self.core_app.account_manager.get_account(username)
                if not account:
                    continue
                
                # 选择框 - 直接使用保存的选择状态
                checkbox = QCheckBox()
                # 🎯 增强：使用保存的选择状态，新账号默认不选中
                is_selected = False
                if hasattr(self, '_account_selections') and username in self._account_selections:
                    saved_state = self._account_selections[username]
                    if isinstance(saved_state, bool):
                        is_selected = saved_state
                        # 🎯 调试：记录应用的选择状态（仅在有变化时）
                        if not hasattr(self, '_logged_selection_restore'):
                            self._logged_selection_restore = set()
                        if username not in self._logged_selection_restore:
                            self.log_message(f"📋 恢复账号选择状态: {username} = {is_selected}", "DEBUG")
                            self._logged_selection_restore.add(username)
                
                checkbox.setChecked(is_selected)
                checkbox.stateChanged.connect(self.on_account_selection_changed)
                self.account_table.setCellWidget(row, 0, checkbox)
                
                # 账号名
                self.account_table.setItem(row, 1, QTableWidgetItem(username))
                
                # 🎯 修复：登录状态 - 使用更稳定的状态判断逻辑，减少耗时检查
                # 兼容dict和Account对象格式
                if hasattr(account, '_data'):
                    # TempAccount包装对象
                    account_status = account.status
                    account_cookies = account.cookies
                elif isinstance(account, dict):
                    # 原始dict格式
                    account_status = account.get('status', 'inactive')
                    account_cookies = account.get('cookies', [])
                else:
                    # Account对象格式
                    account_status = account.status
                    account_cookies = getattr(account, 'cookies', [])
                
                is_really_logged_in = (account_status == 'active' and 
                                       account_cookies and 
                                       len(account_cookies) > 0)
                
                status_text = "已登录" if is_really_logged_in else "未登录"
                status_item = QTableWidgetItem(status_text)
                
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
                
                # 🎯 性能优化：进度信息延迟加载，避免阻塞
                try:
                    # 🎯 修复：安全获取target_count，避免控件未创建的问题
                    target_count = 1
                    if (hasattr(self, 'videos_per_account_input') and 
                        self.videos_per_account_input and
                        self.videos_per_account_input.text().strip()):
                        try:
                            target_count = max(1, int(self.videos_per_account_input.text().strip()))
                        except (ValueError, AttributeError):
                            target_count = 1
                    
                    # 🎯 简化进度获取，减少文件I/O，增加异常处理
                    if hasattr(self, 'account_service') and self.account_service:
                        try:
                            status, completed, published = self.account_service.get_account_progress(username, target_count)
                        except Exception as e:
                            self.log_message(f"⚠️ 获取账号 {username} 进度失败: {e}", "WARNING")
                            status, completed, published = f"0/{target_count}", False, 0
                    else:
                        status, completed, published = f"0/{target_count}", False, 0
                    
                    # 今日已发列 - 🎯 修复：确保只显示纯数字
                    published_count = published if isinstance(published, int) else 0
                    today_published_item = QTableWidgetItem(str(published_count))
                    today_published_item.setTextAlignment(Qt.AlignCenter)
                    if completed:
                        today_published_item.setBackground(QColor(144, 238, 144))
                    else:
                        today_published_item.setBackground(QColor(255, 255, 200))
                    self.account_table.setItem(row, 5, today_published_item)
                    
                    # 进度状态列
                    progress_item = QTableWidgetItem(status)
                    progress_item.setTextAlignment(Qt.AlignCenter)
                    if completed:
                        progress_item.setBackground(QColor(144, 238, 144))
                        progress_item.setForeground(QColor(0, 100, 0))
                    else:
                        progress_item.setBackground(QColor(255, 255, 200))
                        progress_item.setForeground(QColor(100, 100, 0))
                    self.account_table.setItem(row, 6, progress_item)
                    
                except Exception as e:
                    # 如果获取进度失败，显示默认值
                    self.account_table.setItem(row, 5, QTableWidgetItem("0"))  # 今日已发：纯数字
                    self.account_table.setItem(row, 6, QTableWidgetItem("获取中..."))  # 进度状态
                
                # 备注
                notes = getattr(account, 'notes', "")
                self.account_table.setItem(row, 7, QTableWidgetItem(notes))
            
            # 🎯 性能优化：重新启用信号
            self.account_table.blockSignals(False)
            
            # 🎯 性能优化：显示统计信息
            try:
                target_count = int(self.videos_per_account_input.text()) if hasattr(self, 'videos_per_account_input') else 1
                self._update_account_stats_with_progress(target_count)
            except Exception as e:
                self.log_message(f"⚠️ 更新账号统计失败: {e}", "WARNING")
                total_accounts = len(accounts)
                active_accounts = 0
                for a in accounts:
                    account = self.core_app.account_manager.get_account(a)
                    if account:
                        # 兼容dict和Account对象格式
                        if hasattr(account, '_data'):
                            # TempAccount包装对象
                            account_status = account.status
                        elif isinstance(account, dict):
                            # 原始dict格式
                            account_status = account.get('status', 'inactive')
                        else:
                            # Account对象格式
                            account_status = account.status
                        
                        if account_status == 'active':
                            active_accounts += 1
                stats_text = f"账号统计：总数 {total_accounts}，活跃 {active_accounts}"
                if hasattr(self, 'account_stats_label'):
                    self.account_stats_label.setText(stats_text)
            
            # 🎯 刷新全选框状态
            if hasattr(self, 'on_account_selection_changed'):
                self.on_account_selection_changed()
            
            # 🎯 刷新完成后更新日志过滤器的账号列表
            if hasattr(self, 'log_tab_instance'):
                try:
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(100, self.log_tab_instance.update_account_list)
                except:
                    pass
            
        except Exception as e:
            self.log_message(f"❌ 账号刷新执行失败: {str(e)}", "ERROR")
    
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
            # 🚀 清除之前目录的缓存
            if hasattr(self, 'video_loader_manager') and self.video_loader_manager:
                self.video_loader_manager.clear_cache()
                
            self.video_dir_edit.setText(directory)
            self.refresh_video_list(force_refresh=True)  # 强制刷新新目录
    
    def refresh_video_list(self, force_refresh: bool = False):
        """🚀 高性能视频列表刷新 - 异步加载，智能缓存"""
        if not hasattr(self, 'video_list'):
            return
            
        directory = self.video_dir_edit.text() if hasattr(self, 'video_dir_edit') else ""
        if not directory or not os.path.exists(directory):
            if hasattr(self, 'video_stats_label'):
                self.video_stats_label.setText("📊 文件统计: 请选择有效目录")
            return
        
        # 🚀 使用高性能加载器
        if hasattr(self, 'video_loader_manager') and self.video_loader_manager:
            try:
                self.video_loader_manager.refresh_directory(directory, force_refresh)
                self.log_message(f"🚀 启动异步视频扫描: {directory}", "INFO")
                return
            except Exception as e:
                self.log_message(f"⚠️ 高性能加载器失败，回退到传统方式: {e}", "WARNING")
        
        # 🔧 后备方案：传统同步方式（保持兼容性）
        try:
            # 显示加载状态
            if hasattr(self, 'video_stats_label'):
                self.video_stats_label.setText("📊 正在扫描文件...")
            
            # 获取所有视频文件
            all_video_files = self.get_video_files(directory)
            total_files = len(all_video_files)
            
            # 分页参数
            max_files_per_page = 200
            current_page = getattr(self, '_current_video_page', 0)
            
            # 分页处理
            start_index = current_page * max_files_per_page
            end_index = min(start_index + max_files_per_page, total_files)
            current_page_files = all_video_files[start_index:end_index]
            
            # 更新UI
            self.video_list.blockSignals(True)
            self.video_list.clear()
            
            page_total_size = 0
            for file_path in current_page_files:
                filename = os.path.basename(file_path)
                try:
                    file_size = os.path.getsize(file_path)
                    page_total_size += file_size
                    size_mb = file_size / (1024 * 1024)
                    display_text = f"{filename} ({size_mb:.1f}MB)"
                except:
                    display_text = filename
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, file_path)
                self.video_list.addItem(item)
            
            self.video_list.blockSignals(False)
            
            # 更新统计信息
            if hasattr(self, 'video_stats_label'):
                page_size_mb = page_total_size / (1024 * 1024) if page_total_size > 0 else 0
                total_pages = (total_files + max_files_per_page - 1) // max_files_per_page if total_files > 0 else 1
                
                if total_pages > 1:
                    stats_text = f"📊 第{current_page + 1}/{total_pages}页 | 当前页: {len(current_page_files)} 个文件 ({page_size_mb:.1f}MB) | 总计: {total_files} 个文件"
                else:
                    stats_text = f"📊 文件统计: {total_files} 个文件, 总大小 {page_size_mb:.1f}MB"
                self.video_stats_label.setText(stats_text)
            
            # 更新分页按钮
            self._update_video_pagination_buttons(current_page, total_pages)
                
        except Exception as e:
            if hasattr(self, 'video_stats_label'):
                self.video_stats_label.setText("📊 文件扫描失败")
            self.log_message(f"❌ 视频文件扫描失败: {e}", "ERROR")
    
    def _apply_cached_video_list(self, cache_data):
        """应用缓存的视频列表数据"""
        try:
            # 暂时断开信号
            self.video_list.blockSignals(True)
            self.video_list.clear()
            
            # 添加缓存的条目
            for display_text, file_path in cache_data['display_items']:
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, file_path)
                self.video_list.addItem(item)
            
            # 重新启用信号
            self.video_list.blockSignals(False)
            
            # 更新统计信息
            if hasattr(self, 'video_stats_label'):
                total_size_mb = cache_data['total_size'] / (1024 * 1024) if cache_data['total_size'] > 0 else 0
                stats_text = f"📊 文件统计: {cache_data['file_count']} 个文件, 总大小 {total_size_mb:.1f}MB (缓存)"
                self.video_stats_label.setText(stats_text)
                
        except Exception as e:
            self.log_message(f"❌ 应用缓存视频列表失败: {e}", "ERROR")
            # fallback到正常扫描
            self.refresh_video_list()
    
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
        """设置文件监控 - 🔧 优化版：延长间隔减少资源消耗"""
        # 🔧 优化：延长检查间隔，减少文件系统调用
        if not hasattr(self, 'file_monitor_timer'):
            from PyQt5.QtCore import QTimer
            self.file_monitor_timer = QTimer()
            self.file_monitor_timer.timeout.connect(self.check_file_changes)
            
        if hasattr(self, 'auto_refresh_check') and self.auto_refresh_check.isChecked():
            self.file_monitor_timer.start(60000)  # 🔧 从10秒延长到60秒
    
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
        self.upload_thread.account_progress_updated.connect(self.on_account_progress_updated)  # 🎯 新增：连接进度更新信号
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
        """🎯 安全清空日志"""
        try:
            if hasattr(self, 'log_text') and self.log_text:
                self.log_text.clear()
                # 重置计数器和缓冲区
                self._log_count = 0
                if hasattr(self, '_log_buffer'):
                    self._log_buffer.clear()
                # 直接添加清空消息，避免递归调用log_message
                self.log_text.append('<div style="color: #28a745; margin: 2px 0;">--- 日志已手动清空 ---</div>')
        except Exception as e:
            print(f"清空日志异常: {e}")
    
    def save_log(self):
        """🎯 安全保存日志"""
        try:
            if not hasattr(self, 'log_text') or not self.log_text:
                return
            
            # 先刷新缓冲区，确保所有日志都显示
            if hasattr(self, '_flush_log_buffer'):
                self._flush_log_buffer()
            
            from PyQt5.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(self, "保存日志", "log.txt", "Text Files (*.txt)")
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(self.log_text.toPlainText())
                    # 直接添加成功消息，避免递归调用
                    self.log_text.append(f'<div style="color: #28a745; margin: 2px 0;">[{time.strftime("%H:%M:%S")}] 日志已保存到: {filename}</div>')
                except Exception as e:
                    self.log_text.append(f'<div style="color: #dc3545; margin: 2px 0;">[{time.strftime("%H:%M:%S")}] 保存日志失败: {e}</div>')
        except Exception as e:
            print(f"保存日志异常: {e}")
    
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
        """快速检查DevTools端口 - 优化版：减少超时时间"""
        try:
            import requests
            devtools_url = f"http://127.0.0.1:{port}/json"
            # 🎯 关键优化：减少超时时间从1秒到0.3秒，避免主线程长时间阻塞
            response = requests.get(devtools_url, timeout=0.3)
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
        
        # 🎯 只在状态真正改变时刷新界面，不记录状态变化日志
        if old_status != status_text:
            # 简化：移除状态变化日志，减少输出
            
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
                
                # 🎯 关键修复：保存每个账号的选择状态（确保数据类型正确）
                if username and isinstance(username, str):
                    self._account_selections[username] = bool(is_checked)
                    current_status[username] = bool(is_checked)
                
                if is_checked:
                    selected_count += 1
        
        # 🎯 调试信息：显示当前选择状态（只在有选中账号时显示）
        if selected_count > 0:
            selected_accounts = [acc for acc, checked in current_status.items() if checked]
            self.log_message(f"📋 已选择 {selected_count} 个账号: {selected_accounts}", "DEBUG")
        
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
                        # 有Cookie就认为登录有效，强制设置为active状态 - 兼容dict和Account对象格式
                        if hasattr(account, '_data'):
                            # TempAccount包装对象
                            account.status = 'active'
                        elif isinstance(account, dict):
                            # 原始dict格式
                            account['status'] = 'active'
                        else:
                            # Account对象格式
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
            # 🎯 关键修复：设置主窗口引用，让线程能获取实时设置
            self.batch_upload_thread.main_window = self
            # 🎯 修复：直接传递account_service给线程
            self.batch_upload_thread.account_service = self.account_service
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
        """批量上传状态，支持账号提取"""
        # 🎯 从状态消息中提取账号信息
        account = self._extract_account_from_message(status)
        self.log_message(f"📝 {status}", "INFO", account)
    
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

    def on_account_progress_updated(self, account_name):
        """处理账号进度更新信号 - 修复：投稿成功后更新详细统计"""
        try:
            # 🎯 修复：获取当前的目标视频数量
            try:
                target_videos_per_account = int(self.videos_per_account_input.text()) if hasattr(self, 'videos_per_account_input') else 1
            except (ValueError, AttributeError):
                target_videos_per_account = 1
            
            # 刷新账号列表以更新进度显示
            self.refresh_accounts()
            
            # 🎯 关键修复：投稿成功后立即更新详细的统计信息
            self._update_account_stats_with_progress(target_videos_per_account)
            
            self.log_message(f"📊 投稿成功后已更新进度和统计信息: {account_name}", "INFO")
            
        except Exception as e:
            self.log_message(f"❌ 更新账号进度显示失败: {e}", "ERROR")
    
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
            
            # 🎯 增强：加载账号选择状态
            saved_selections = ui_settings.get('account_selections', {})
            if saved_selections and isinstance(saved_selections, dict):
                # 🎯 修复：确保选择状态是有效的布尔值
                cleaned_selections = {}
                for account, selected in saved_selections.items():
                    if isinstance(account, str) and isinstance(selected, bool):
                        cleaned_selections[account] = selected
                
                self._account_selections = cleaned_selections
                if cleaned_selections:
                    self.log_message(f"📋 已加载账号选择状态: {len(cleaned_selections)} 个账号", "INFO")
                else:
                    self.log_message("📋 选择状态数据无效，使用默认设置", "INFO")
                    self._account_selections = {}
            else:
                self._account_selections = {}
                self.log_message("📋 未找到保存的账号选择状态，使用默认设置", "INFO")
            
            # 🎯 新增：加载投稿成功等待时间设置
            success_wait_time = ui_settings.get('success_wait_time', 2)  # 默认2秒
            if hasattr(self, 'success_wait_time_spinbox'):
                self.success_wait_time_spinbox.setValue(int(success_wait_time))
                self.log_message(f"⏱️ 已加载投稿成功等待时间: {success_wait_time}秒", "INFO")
            
            # 🎯 新增：加载视频随机化策略设置到UI
            if hasattr(self, 'randomize_strategy_combo'):
                try:
                    from gui.tabs.upload_tab import UploadTab
                    # 为了访问UploadTab的方法，我们需要创建一个临时实例
                    # 但是我们可以直接在这里实现加载逻辑
                    current_strategy = ui_settings.get('randomize_strategy', 'random')
                    
                    # 映射策略值到UI显示文本
                    strategy_mapping = {
                        'random': 'random - 完全随机（推荐）',
                        'group': 'group - 分组随机（每10个一组）',
                        'partial': 'partial - 部分随机（70%改变）',
                        'none': 'none - 不随机（按文件名顺序）'
                    }
                    
                    display_text = strategy_mapping.get(current_strategy, 'random - 完全随机（推荐）')
                    
                    # 设置下拉框选中项（阻止信号触发，避免重复保存）
                    self.randomize_strategy_combo.blockSignals(True)
                    index = self.randomize_strategy_combo.findText(display_text)
                    if index >= 0:
                        self.randomize_strategy_combo.setCurrentIndex(index)
                    self.randomize_strategy_combo.blockSignals(False)
                    
                    # 更新说明标签
                    if hasattr(self, 'randomize_info_label'):
                        strategy_info = {
                            'random': '💡 完全随机可有效降低平台检测风险',
                            'group': '💡 分组随机适合有序列要求的场景',
                            'partial': '💡 部分随机平衡随机性和连续性',
                            'none': '💡 不随机将按文件名顺序上传'
                        }
                        self.randomize_info_label.setText(strategy_info.get(current_strategy, '💡 策略已加载'))
                    
                    self.log_message(f"🎲 已加载视频随机化策略: {current_strategy}", "INFO")
                    
                except Exception as e:
                    self.log_message(f"⚠️ 加载随机化策略设置失败: {e}", "WARNING")
            
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
            
            # 🎯 新增：保存账号选择状态（清理后）
            if hasattr(self, '_account_selections'):
                # 清理账号选择状态中的异常字符
                from core.config import DataCleaner
                cleaned_selections = DataCleaner.clean_dict_keys(self._account_selections)
                config['ui_settings']['account_selections'] = cleaned_selections
                
                # 如果清理后有变化，更新内存中的数据
                if cleaned_selections != self._account_selections:
                    self._account_selections = cleaned_selections
                    self.log_message("🧹 账号选择状态已清理异常字符", "INFO")
                
                self.log_message(f"💾 保存账号选择状态: {len(cleaned_selections)}个账号", "DEBUG")
            
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
        """验证许可证 - 使用服务层"""
        try:
            license_text = self.license_input.toPlainText().strip()
            if not license_text:
                QMessageBox.warning(self, "输入错误", "请先输入许可证内容")
                return
            
            # 使用服务层验证许可证
            is_valid, message = self.license_service.verify_license(license_text)
            
            if is_valid:
                # 更新许可证信息和授权状态（保持原有逻辑）
                result = self.license_system.verify_license(license_text)
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
                
            else:
                self.license_log_message(f"❌ 许可证验证失败: {message}")
                QMessageBox.critical(self, "验证失败", f"许可证验证失败:\n\n{message}")
                
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
        """🎯 安全关闭事件 - 修复强制退出导致的意外终止问题"""
        # 🔍 检测是否为意外关闭
        is_unexpected_close = False
        if hasattr(self, 'batch_upload_thread') and self.batch_upload_thread and self.batch_upload_thread.isRunning():
            is_unexpected_close = True
            self.log_message("⚠️ 检测到批量上传进行中的意外关闭事件！", "WARNING")
        
        self.log_message("🔄 程序正在安全关闭...", "INFO")
        
        try:
            # 🎯 第一步：停止所有活动
            self._stop_all_activities()
            
            # 🎯 第二步：保存配置（增加超时保护）
            try:
                self._safe_save_config()
            except Exception as e:
                self.log_message(f"⚠️ 保存配置失败: {e}", "WARNING")
            
            # 🎯 第三步：关闭浏览器（增加超时保护）
            try:
                self._safe_close_browsers()
            except Exception as e:
                self.log_message(f"⚠️ 关闭浏览器失败: {e}", "WARNING")
            
            # 🎯 第四步：清理线程和资源
            try:
                self._cleanup_threads()
            except Exception as e:
                self.log_message(f"⚠️ 清理线程失败: {e}", "WARNING")
            
            self.log_message("✅ 程序安全关闭完成", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 关闭过程出错: {e}", "ERROR")
            # 🎯 即使出错也不强制退出，让Qt正常处理
        
        finally:
            # 🎯 修复：使用正常的Qt退出机制，不强制杀死进程
            if is_unexpected_close:
                # 如果是意外关闭，询问用户是否确认
                from PyQt5.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self, 
                    "确认退出", 
                    "检测到程序可能意外退出。\n\n是否确认关闭程序？\n\n点击「Yes」正常退出\n点击「No」取消关闭",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    event.ignore()  # 取消关闭
                    self.log_message("🔄 用户取消关闭，程序继续运行", "INFO")
                    return
            
            # 🎯 使用安全的退出方式
            event.accept()
            QApplication.processEvents()
            
            # 🎯 移除强制退出，改为正常退出
            # os._exit(0)  # ❌ 删除这行强制退出代码
            
            # 🎯 使用正常的应用退出
            if QApplication.instance():
                QApplication.instance().quit()
    
    def _safe_save_config(self):
        """安全保存配置（带超时保护）"""
        try:
            import threading
            import time
            
            config_saved = threading.Event()
            save_error = None
            
            def save_config_task():
                nonlocal save_error
                try:
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
                    config_saved.set()
                except Exception as e:
                    save_error = e
                    config_saved.set()
            
            # 启动保存任务
            save_thread = threading.Thread(target=save_config_task)
            save_thread.daemon = True
            save_thread.start()
            
            # 等待保存完成或超时（3秒）
            if config_saved.wait(timeout=3):
                if save_error:
                    raise save_error
                self.log_message("✅ 配置已安全保存", "INFO")
            else:
                self.log_message("⚠️ 配置保存超时，跳过", "WARNING")
                
        except Exception as e:
            self.log_message(f"❌ 安全保存配置失败: {e}", "ERROR")
    
    def _safe_close_browsers(self):
        """安全关闭浏览器（带超时保护）"""
        try:
            import threading
            import time
            
            def close_browser_task(account_name):
                try:
                    account = self.core_app.account_manager.get_account(account_name)
                    if hasattr(account, 'browser_instance') and account.browser_instance:
                        account.browser_instance.quit()
                        account.browser_instance = None
                        return f"✅ {account_name}"
                    return f"⏭️ {account_name} (无需关闭)"
                except Exception as e:
                    return f"❌ {account_name}: {e}"
            
            # 并行关闭所有浏览器（最多等待5秒）
            accounts = self.core_app.account_manager.get_all_accounts()
            if accounts:
                close_threads = []
                results = []
                
                for account_name in accounts[:10]:  # 最多处理10个账号
                    thread = threading.Thread(
                        target=lambda an=account_name: results.append(close_browser_task(an))
                    )
                    thread.daemon = True
                    thread.start()
                    close_threads.append(thread)
                
                # 等待所有线程完成或超时
                start_time = time.time()
                for thread in close_threads:
                    remaining_time = max(0, 5 - (time.time() - start_time))
                    thread.join(timeout=remaining_time)
                
                # 输出结果
                for result in results:
                    self.log_message(f"🔒 关闭浏览器: {result}", "INFO")
                    
        except Exception as e:
            self.log_message(f"❌ 安全关闭浏览器失败: {e}", "ERROR")
    
    def _cleanup_threads(self):
        """清理所有线程和资源"""
        try:
            # 清理上传线程
            thread_names = [
                'batch_upload_thread', 'upload_thread', 'login_thread',
                'license_worker', 'file_worker', 'periodic_checker'
            ]
            
            for thread_name in thread_names:
                if hasattr(self, thread_name):
                    thread = getattr(self, thread_name)
                    if thread and hasattr(thread, 'isRunning') and thread.isRunning():
                        if hasattr(thread, 'stop'):
                            thread.stop()
                        if hasattr(thread, 'quit'):
                            thread.quit()
                        
                        # 等待线程结束（最多1秒）
                        if hasattr(thread, 'wait'):
                            thread.wait(1000)  # 1秒超时
                        
                        self.log_message(f"🧹 清理线程: {thread_name}", "INFO")
            
            # 清理性能组件
            if hasattr(self, 'memory_manager') and self.memory_manager:
                try:
                    self.memory_manager.cleanup()
                except:
                    pass
            
            if hasattr(self, 'task_queue') and self.task_queue:
                try:
                    self.task_queue.shutdown()
                except:
                    pass
                    
        except Exception as e:
            self.log_message(f"❌ 清理线程失败: {e}", "ERROR")
    
    def _stop_all_activities(self):
        """停止所有定时器和线程活动"""
        try:
            # 🎯 优先停止浏览器状态监控器
            if hasattr(self, 'browser_monitor'):
                try:
                    self.browser_monitor.stop_monitoring()
                    self.log_message("✅ 浏览器状态监控器已停止")
                except Exception as e:
                    self.log_message(f"⚠️ 停止状态监控器失败: {e}", "WARNING")
            
            # 停止定时器
            timers = [
                'browser_status_timer', 'file_monitor_timer', 
                '_video_refresh_timer', '_file_refresh_timer',
                '_file_delete_refresh_timer', 'security_timer',
                '_log_flush_timer'  # 🎯 新增：停止日志刷新定时器
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

    def on_videos_per_account_changed(self):
        """处理每账号视频数量变化"""
        try:
            # 获取新的视频数量设置
            if hasattr(self, 'videos_per_account_input'):
                try:
                    videos_per_account = int(self.videos_per_account_input.text())
                    # 🎯 立即更新账号统计信息，使用新的目标数量
                    self._async_update_account_stats(videos_per_account)
                    self.log_message(f"📊 每账号视频数量已更新为: {videos_per_account}", "INFO")
                except ValueError:
                    # 如果输入的不是有效数字，使用默认值1
                    self.log_message("⚠️ 输入的视频数量无效，使用默认值1", "WARNING")
                    self._async_update_account_stats(1)
        except Exception as e:
            self.log_message(f"❌ 处理视频数量变化失败: {e}", "ERROR")

    def _async_update_account_stats(self, target_videos_per_account):
        """异步更新账号统计信息 - 修复进度状态显示"""
        try:
            # 获取所有账号
            accounts = self.core_app.account_manager.get_all_accounts()
            if not accounts:
                return
            
            # 更新界面中的账号进度信息
            for row in range(self.account_table.rowCount()):
                try:
                    username_item = self.account_table.item(row, 1)  # 用户名列
                    if not username_item:
                        continue
                    
                    username = username_item.text()
                    account = self.core_app.account_manager.get_account(username)
                    if not account:
                        continue
                    
                    # 获取该账号的上传进度 - 🎯 修复：使用与原始方法相同的数据源
                    try:
                        if hasattr(self, 'account_service') and self.account_service:
                            progress_text, is_completed, uploaded_count = self.account_service.get_account_progress(username, target_videos_per_account)
                        else:
                            progress_text, is_completed, uploaded_count = self.core_app.database_manager.get_account_progress(
                                username, target_videos_per_account
                            )
                        
                        # 🎯 修复：正确设置今日已发列（第5列）和进度状态列（第6列）
                        from PyQt5.QtWidgets import QTableWidgetItem
                        from PyQt5.QtCore import Qt
                        from PyQt5.QtGui import QColor
                        
                        # 第5列：今日已发 - 显示纯数字
                        if self.account_table.columnCount() > 5:
                            today_item = self.account_table.item(row, 5)
                            if today_item:
                                today_item.setText(str(uploaded_count))
                            else:
                                today_item = QTableWidgetItem(str(uploaded_count))
                                today_item.setTextAlignment(Qt.AlignCenter)
                                if is_completed:
                                    today_item.setBackground(QColor(144, 238, 144))
                                else:
                                    today_item.setBackground(QColor(255, 255, 200))
                                self.account_table.setItem(row, 5, today_item)
                        
                        # 第6列：进度状态 - 显示分数格式加状态文字
                        if self.account_table.columnCount() > 6:
                            progress_item = self.account_table.item(row, 6)
                            if progress_item:
                                progress_item.setText(progress_text)
                            else:
                                progress_item = QTableWidgetItem(progress_text)
                                progress_item.setTextAlignment(Qt.AlignCenter)
                                if is_completed:
                                    progress_item.setBackground(QColor(144, 238, 144))
                                    progress_item.setForeground(QColor(0, 100, 0))
                                else:
                                    progress_item.setBackground(QColor(255, 255, 200))
                                    progress_item.setForeground(QColor(100, 100, 0))
                                self.account_table.setItem(row, 6, progress_item)
                                
                    except Exception as e:
                        # 🎯 修复：只在真正获取失败时设置默认值，并记录错误
                        self.log_message(f"⚠️ 获取账号 {username} 进度失败: {e}", "DEBUG")
                        from PyQt5.QtWidgets import QTableWidgetItem
                        if self.account_table.columnCount() > 5:
                            today_item = QTableWidgetItem("0")  # 今日已发：纯数字
                            self.account_table.setItem(row, 5, today_item)
                        if self.account_table.columnCount() > 6:
                            progress_item = QTableWidgetItem(f"0/{target_videos_per_account} 进行中")  # 进度状态：带状态文字
                            self.account_table.setItem(row, 6, progress_item)
                    
                except Exception as e:
                    continue
            
            # 🎯 关键修复：调用详细统计信息更新，而不是简单统计
            self._update_account_stats_with_progress(target_videos_per_account)
            
            self.log_message(f"📊 账号统计已更新，目标数量: {target_videos_per_account}", "INFO")
            
        except Exception as e:
            self.log_message(f"❌ 更新账号统计失败: {e}", "ERROR")

    def _update_account_stats_with_progress(self, target_videos_per_account):
        """更新带有进度信息的账号统计"""
        try:
            # 获取所有账号
            accounts = self.core_app.account_manager.get_all_accounts()
            if not accounts:
                if hasattr(self, 'account_stats_label'):
                    self.account_stats_label.setText("账号统计：无账号")
                return
            
            # 统计变量
            total_accounts = len(accounts)
            active_accounts = 0
            completed_accounts = 0
            in_progress_accounts = 0
            total_uploaded_today = 0
            
            # 逐个分析账号
            for username in accounts:
                account = self.core_app.account_manager.get_account(username)
                if not account:
                    continue
                
                # 检查账号是否活跃（已登录）
                # 兼容dict和Account对象格式
                if hasattr(account, '_data'):
                    # TempAccount包装对象
                    account_status = account.status
                    account_cookies = account.cookies
                elif isinstance(account, dict):
                    # 原始dict格式
                    account_status = account.get('status', 'inactive')
                    account_cookies = account.get('cookies', [])
                else:
                    # Account对象格式
                    account_status = account.status
                    account_cookies = getattr(account, 'cookies', [])
                
                is_logged_in = (account_status == 'active' and 
                               account_cookies and 
                               len(account_cookies) > 0)
                
                if is_logged_in:
                    active_accounts += 1
                
                # 获取投稿进度
                try:
                    if hasattr(self, 'account_service') and self.account_service:
                        status, completed, published = self.account_service.get_account_progress(username, target_videos_per_account)
                        total_uploaded_today += published
                        
                        if completed:
                            completed_accounts += 1
                        elif published > 0:
                            in_progress_accounts += 1
                    else:
                        # 如果没有account_service，直接查询数据库
                        from database.database_manager import db_manager
                        status, completed, published = db_manager.get_account_progress(username, target_videos_per_account)
                        total_uploaded_today += published
                        
                        if completed:
                            completed_accounts += 1
                        elif published > 0:
                            in_progress_accounts += 1
                            
                except Exception as e:
                    self.log_message(f"⚠️ 获取账号 {username} 进度失败: {e}", "DEBUG")
                    continue
            
            # 计算剩余待处理账号
            pending_accounts = total_accounts - completed_accounts - in_progress_accounts
            
            # 生成统计文本
            stats_parts = []
            stats_parts.append(f"总数 {total_accounts}")
            stats_parts.append(f"已登录 {active_accounts}")
            stats_parts.append(f"已完成 {completed_accounts}")
            
            if in_progress_accounts > 0:
                stats_parts.append(f"进行中 {in_progress_accounts}")
            
            if pending_accounts > 0:
                stats_parts.append(f"待处理 {pending_accounts}")
                
            stats_parts.append(f"今日总发布 {total_uploaded_today}")
            
            stats_text = f"账号统计：{' | '.join(stats_parts)}"
            
            # 更新显示
            if hasattr(self, 'account_stats_label'):
                self.account_stats_label.setText(stats_text)
                
            self.log_message(f"📊 账号统计已更新: {stats_text}", "DEBUG")
            
        except Exception as e:
            self.log_message(f"❌ 更新账号统计失败: {e}", "ERROR")
            # 回退到简单统计
            try:
                accounts = self.core_app.account_manager.get_all_accounts()
                simple_stats = f"账号统计：总数 {len(accounts)} (统计功能异常)"
                if hasattr(self, 'account_stats_label'):
                    self.account_stats_label.setText(simple_stats)
            except:
                pass


