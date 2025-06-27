#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号管理服务 - 账号相关业务逻辑
"""

from typing import List, Dict, Optional, Tuple
from PyQt5.QtCore import QThread, pyqtSignal

from .base_service import BaseService


class LoginThread(QThread):
    """登录线程 - 从gui.py移动过来"""
    login_success = pyqtSignal(str)
    login_failed = pyqtSignal(str, str)
    
    def __init__(self, account_manager, username):
        super().__init__()
        self.account_manager = account_manager
        self.username = username
    
    def run(self):
        try:
            if self.account_manager.login_account(self.username):
                self.login_success.emit(self.username)
            else:
                self.login_failed.emit(self.username, "登录失败")
        except Exception as e:
            self.login_failed.emit(self.username, str(e))


class AccountService(BaseService):
    """账号管理服务"""
    
    def _do_initialize(self):
        """初始化账号服务"""
        self.login_thread = None
    
    def add_account(self, username: str) -> bool:
        """
        添加账号
        
        Args:
            username: 账号名
            
        Returns:
            bool: 是否添加成功
        """
        if not username or not username.strip():
            self.notify_warning("账号名不能为空")
            return False
        
        username = username.strip()
        
        try:
            if self.core_app and self.core_app.account_manager:
                if self.core_app.account_manager.add_account(username):
                    self.notify_success(f"账号 {username} 添加成功")
                    return True
                else:
                    self.log_message(f"账号 {username} 添加失败", "ERROR")
                    return False
            else:
                self.log_message("核心应用未初始化", "ERROR")
                return False
                
        except Exception as e:
            return self.handle_error(e, f"添加账号 {username} 时发生错误")
    
    def remove_account(self, username: str) -> bool:
        """
        删除账号
        
        Args:
            username: 账号名
            
        Returns:
            bool: 是否删除成功
        """
        if not username:
            self.notify_warning("账号名不能为空")
            return False
        
        try:
            if self.core_app and self.core_app.account_manager:
                result = self.core_app.account_manager.remove_account(username)
                if result:
                    self.notify_success(f"账号 {username} 已删除")
                else:
                    self.log_message(f"账号 {username} 删除失败", "ERROR")
                return result
            else:
                self.log_message("核心应用未初始化", "ERROR")
                return False
                
        except Exception as e:
            return self.handle_error(e, f"删除账号 {username} 时发生错误")
    
    def start_login(self, username: str) -> bool:
        """
        开始登录账号（异步）
        
        Args:
            username: 账号名
            
        Returns:
            bool: 是否成功启动登录流程
        """
        if not username:
            self.notify_warning("账号名不能为空")
            return False
        
        if self.login_thread and self.login_thread.isRunning():
            self.notify_warning("已有登录任务正在进行中")
            return False
        
        try:
            if self.core_app and self.core_app.account_manager:
                self.login_thread = LoginThread(self.core_app.account_manager, username)
                
                # 连接信号到主窗口的处理方法
                if self.main_window:
                    self.login_thread.login_success.connect(self.main_window.on_login_success)
                    self.login_thread.login_failed.connect(self.main_window.on_login_failed)
                
                self.login_thread.start()
                self.log_message(f"开始登录账号: {username}", "INFO")
                return True
            else:
                self.log_message("核心应用未初始化", "ERROR")
                return False
                
        except Exception as e:
            return self.handle_error(e, f"启动登录流程时发生错误")
    
    def get_all_accounts(self) -> List[str]:
        """
        获取所有账号列表
        
        Returns:
            List[str]: 账号名列表
        """
        try:
            if self.core_app and self.core_app.account_manager:
                return self.core_app.account_manager.get_all_accounts()
            else:
                self.log_message("核心应用未初始化", "ERROR")
                return []
                
        except Exception as e:
            self.handle_error(e, "获取账号列表时发生错误")
            return []
    
    def get_active_accounts(self) -> List[str]:
        """
        获取活跃账号列表
        
        Returns:
            List[str]: 活跃账号名列表
        """
        try:
            if self.core_app and self.core_app.account_manager:
                return self.core_app.account_manager.get_active_accounts()
            else:
                return []
                
        except Exception as e:
            self.handle_error(e, "获取活跃账号列表时发生错误")
            return []
    
    def get_account(self, username: str):
        """
        获取账号信息
        
        Args:
            username: 账号名
            
        Returns:
            账号对象或None
        """
        try:
            if self.core_app and self.core_app.account_manager:
                return self.core_app.account_manager.get_account(username)
            else:
                return None
                
        except Exception as e:
            self.handle_error(e, f"获取账号 {username} 信息时发生错误")
            return None
    
    def get_account_status(self, username: str) -> Tuple[str, bool]:
        """
        获取账号状态
        
        Args:
            username: 账号名
            
        Returns:
            Tuple[str, bool]: (状态文本, 是否已登录)
        """
        try:
            account = self.get_account(username)
            if not account:
                return "账号不存在", False
            
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
            
            status_text = "已登录" if is_logged_in else "未登录"
            return status_text, is_logged_in
            
        except Exception as e:
            self.handle_error(e, f"获取账号 {username} 状态时发生错误")
            return "状态未知", False
    
    def get_account_progress(self, username: str, target_count: int = 1) -> Tuple[str, bool, int]:
        """
        获取账号上传进度
        
        Args:
            username: 账号名
            target_count: 目标上传数量
            
        Returns:
            Tuple[str, bool, int]: (进度状态, 是否完成, 已发布数量)
        """
        try:
            # 🎯 简化的进度检查逻辑 - 直接使用日期字符串比较
            import json
            import os
            from datetime import datetime
            
            # 获取今日日期
            today = datetime.now().strftime("%Y-%m-%d")
            published_count = 0
            debug_info = []
            
            # 从上传记录中统计今日该账号的发布数量
            try:
                if os.path.exists('uploaded_videos.json'):
                    # 🎯 强制重新读取文件，避免缓存问题
                    import time
                    time.sleep(0.1)  # 短暂延迟确保文件写入完成
                    with open('uploaded_videos.json', 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        uploaded_videos = data.get('uploaded_videos', {})
                        
                        for md5_hash, video_info in uploaded_videos.items():
                            if video_info.get('account') == username:
                                # 🎯 优先使用新的upload_date字段，兼容旧的upload_time字段
                                upload_date = video_info.get('upload_date')
                                if not upload_date:
                                    # 兼容旧格式：从upload_time转换
                                    upload_time = video_info.get('upload_time', 0)
                                    if upload_time > 0:
                                        try:
                                            upload_date = datetime.fromtimestamp(upload_time).strftime("%Y-%m-%d")
                                        except (ValueError, OSError, OverflowError):
                                            upload_date = None
                                
                                deleted = video_info.get('deleted', False)
                                filename = video_info.get('filename', 'unknown')
                                
                                # 检查是否是今日上传
                                if upload_date == today:
                                    # 🎯 修正逻辑：今日投稿记录都计入进度，不管文件是否删除
                                    published_count += 1
                                    if deleted:
                                        debug_info.append(f"✅ 计入(文件已删): {filename}")
                                    else:
                                        debug_info.append(f"✅ 计入(文件保留): {filename}")
                                elif upload_date:
                                    debug_info.append(f"📅 其他日期({upload_date}): {filename}")
                                else:
                                    debug_info.append(f"⚠️ 日期无效: {filename}")
                        
                        # 🎯 调试信息输出（可选）
                        if debug_info:
                            self.log_message(f"📊 [{username}] 进度分析:\n" + "\n".join(debug_info[:5]), "DEBUG")
                        
            except Exception as e:
                self.log_message(f"读取上传记录失败: {e}", "WARNING")
            
            # 判断是否完成目标
            is_completed = published_count >= target_count
            
            # 生成状态文本
            if is_completed:
                status_text = f"{published_count}/{target_count} 已完成"
            else:
                status_text = f"{published_count}/{target_count} 进行中"
            
            # 🎯 添加详细日志
            self.log_message(f"📊 账号 {username} 进度查询: {status_text}, 目标: {target_count}, 实际: {published_count}, 完成: {is_completed}", "DEBUG")
                
            return status_text, is_completed, published_count
            
        except Exception as e:
            return self.handle_error(e, f"获取账号 {username} 进度时发生错误", ("获取失败", False, 0))
    
    def cleanup(self):
        """清理资源"""
        if self.login_thread and self.login_thread.isRunning():
            self.login_thread.quit()
            self.login_thread.wait()
        super().cleanup() 