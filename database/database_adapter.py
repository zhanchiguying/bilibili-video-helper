#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库适配器 - 将SQLite数据包装成兼容的Account接口
提供渐进式迁移支持，保持与现有代码的兼容性
"""

import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from database.database_manager import db_manager


class DatabaseAccount:
    """数据库账号适配器 - 兼容现有Account类接口"""
    
    def __init__(self, username: str, db_data: Dict[str, Any] = None):
        self.username = username
        self._db_data = db_data or {}
        self._dirty_fields = set()  # 跟踪修改的字段
    
    @property
    def cookies(self) -> List[Dict[str, Any]]:
        """获取cookies"""
        cookies_str = self._db_data.get('cookies', '')
        if cookies_str:
            try:
                return json.loads(cookies_str)
            except:
                return []
        return []
    
    @cookies.setter
    def cookies(self, value: List[Dict[str, Any]]):
        """设置cookies"""
        self._db_data['cookies'] = json.dumps(value) if value else ''
        self._dirty_fields.add('cookies')
    
    @property
    def status(self) -> str:
        """获取账号状态"""
        return self._db_data.get('status', 'inactive')
    
    @status.setter
    def status(self, value: str):
        """设置账号状态"""
        self._db_data['status'] = value
        self._dirty_fields.add('status')
    
    @property
    def fingerprint(self) -> Dict[str, Any]:
        """获取浏览器指纹"""
        fingerprint_str = self._db_data.get('fingerprint', '')
        if fingerprint_str:
            try:
                return json.loads(fingerprint_str)
            except:
                return {}
        return {}
    
    @fingerprint.setter
    def fingerprint(self, value: Dict[str, Any]):
        """设置浏览器指纹"""
        self._db_data['fingerprint'] = json.dumps(value) if value else ''
        self._dirty_fields.add('fingerprint')
    
    @property
    def devtools_port(self) -> Optional[int]:
        """获取DevTools端口"""
        return self._db_data.get('devtools_port')
    
    @devtools_port.setter
    def devtools_port(self, value: Optional[int]):
        """设置DevTools端口"""
        self._db_data['devtools_port'] = value
        self._dirty_fields.add('devtools_port')
    
    @property
    def last_login(self) -> int:
        """获取最后登录时间"""
        return self._db_data.get('last_login', 0)
    
    @last_login.setter
    def last_login(self, value: int):
        """设置最后登录时间"""
        self._db_data['last_login'] = value
        self._dirty_fields.add('last_login')
    
    @property
    def notes(self) -> str:
        """获取备注"""
        return self._db_data.get('notes', '')
    
    @notes.setter
    def notes(self, value: str):
        """设置备注"""
        self._db_data['notes'] = value
        self._dirty_fields.add('notes')
    
    # 兼容性属性
    @property
    def browser_instance(self):
        """浏览器实例（兼容性属性）"""
        return getattr(self, '_browser_instance', None)
    
    @browser_instance.setter
    def browser_instance(self, value):
        """设置浏览器实例"""
        self._browser_instance = value
    
    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return self.status == 'active' and len(self.cookies) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（兼容现有代码）"""
        return {
            'cookies': self.cookies,
            'fingerprint': self.fingerprint,
            'status': self.status,
            'last_login': self.last_login,
            'notes': self.notes,
            'devtools_port': self.devtools_port
        }
    
    def save(self) -> bool:
        """保存修改到数据库"""
        if not self._dirty_fields:
            return True  # 没有修改，直接返回成功
        
        # 构建更新数据
        update_data = {'username': self.username}
        for field in self._dirty_fields:
            if field in self._db_data:
                update_data[field] = self._db_data[field]
        
        # 批量更新
        success = db_manager.batch_update_accounts([update_data]) > 0
        if success:
            self._dirty_fields.clear()
        
        return success


class DatabaseAccountManager:
    """数据库账号管理器 - 替代现有AccountManager"""
    
    def __init__(self):
        self.logger = None  # 将在初始化时设置
        self._account_cache = {}  # 账号缓存
        self._cache_timestamp = 0
    
    def set_logger(self, logger):
        """设置日志记录器"""
        self.logger = logger
    
    def load_accounts(self):
        """加载账号 - 从数据库加载"""
        try:
            # 清空缓存，强制重新加载
            self._account_cache.clear()
            self._cache_timestamp = 0
            
            if self.logger:
                self.logger.info("📂 开始从数据库加载账号...")
            
            # 从数据库获取所有账号
            accounts_data = db_manager.get_all_accounts_cached(cache_seconds=60)
            
            if self.logger:
                self.logger.info(f"✅ 从数据库加载了 {len(accounts_data)} 个账号")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ 从数据库加载账号失败: {e}")
    
    def get_all_accounts(self) -> List[str]:
        """获取所有账号名"""
        try:
            accounts_data = db_manager.get_all_accounts_cached()
            return [account['username'] for account in accounts_data]
        except Exception as e:
            if self.logger:
                self.logger.error(f"获取所有账号失败: {e}")
            return []
    
    def get_active_accounts(self) -> List[str]:
        """获取活跃账号"""
        try:
            accounts_data = db_manager.get_all_accounts_cached()
            return [account['username'] for account in accounts_data 
                   if account.get('status') == 'active']
        except Exception as e:
            if self.logger:
                self.logger.error(f"获取活跃账号失败: {e}")
            return []
    
    def get_account(self, username: str) -> Optional[DatabaseAccount]:
        """获取账号对象"""
        try:
            # 检查缓存
            cache_key = f"account_{username}"
            current_time = time.time()
            
            if (cache_key in self._account_cache and 
                current_time - self._cache_timestamp < 30):
                return self._account_cache[cache_key]
            
            # 从数据库获取
            account_data = db_manager.get_account(username)
            if account_data:
                account = DatabaseAccount(username, account_data)
                
                # 更新缓存
                self._account_cache[cache_key] = account
                self._cache_timestamp = current_time
                
                return account
            
            return None
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"获取账号 {username} 失败: {e}")
            return None
    
    def add_account(self, username: str) -> bool:
        """添加账号"""
        try:
            success = db_manager.add_account(username)
            if success:
                # 清除相关缓存
                self._clear_cache()
                if self.logger:
                    self.logger.info(f"✅ 账号 {username} 已添加到数据库")
            return success
        except Exception as e:
            if self.logger:
                self.logger.error(f"添加账号 {username} 失败: {e}")
            return False
    
    def remove_account(self, username: str) -> bool:
        """删除账号"""
        try:
            success = db_manager.delete_account(username)
            if success:
                # 清除相关缓存
                self._clear_cache()
                if self.logger:
                    self.logger.info(f"✅ 账号 {username} 已从数据库删除")
            return success
        except Exception as e:
            if self.logger:
                self.logger.error(f"删除账号 {username} 失败: {e}")
            return False
    
    def save_accounts(self) -> bool:
        """保存账号 - 数据库模式下无需手动保存"""
        # 在数据库模式下，每个账号的修改都会自动保存
        # 这里主要是为了兼容现有代码
        try:
            if self.logger:
                self.logger.debug("✅ 账号数据已同步到数据库")
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"保存账号状态失败: {e}")
            return False
    
    def get_accounts_progress_batch(self, usernames: List[str], target_count: int = 1) -> Dict[str, Tuple[str, bool, int]]:
        """批量获取账号进度（高性能版本）"""
        try:
            return db_manager.get_accounts_progress_batch(usernames, target_count)
        except Exception as e:
            if self.logger:
                self.logger.error(f"批量获取账号进度失败: {e}")
            return {username: ("获取失败", False, 0) for username in usernames}
    
    def _clear_cache(self):
        """清除缓存"""
        self._account_cache.clear()
        self._cache_timestamp = 0


class DatabaseVideoManager:
    """数据库视频记录管理器"""
    
    def __init__(self):
        self.logger = None
    
    def set_logger(self, logger):
        """设置日志记录器"""
        self.logger = logger
    
    def add_uploaded_video(self, md5_hash: str, filename: str, account_username: str,
                          product_id: str = '', file_size: int = 0) -> bool:
        """添加上传记录"""
        try:
            upload_date = datetime.now().strftime("%Y-%m-%d")
            return db_manager.add_uploaded_video(
                md5_hash=md5_hash,
                filename=filename,
                account_username=account_username,
                upload_date=upload_date,
                product_id=product_id,
                file_size=file_size
            )
        except Exception as e:
            if self.logger:
                self.logger.error(f"添加上传记录失败: {e}")
            return False
    
    def is_video_uploaded(self, md5_hash: str) -> bool:
        """检查视频是否已上传"""
        try:
            return db_manager.is_video_uploaded(md5_hash)
        except Exception as e:
            if self.logger:
                self.logger.error(f"检查视频上传状态失败: {e}")
            return False
    
    def mark_video_deleted(self, md5_hash: str) -> bool:
        """标记视频已删除"""
        try:
            return db_manager.mark_video_deleted(md5_hash)
        except Exception as e:
            if self.logger:
                self.logger.error(f"标记视频删除失败: {e}")
            return False
    
    def get_account_progress(self, username: str, target_count: int = 1) -> Tuple[str, bool, int]:
        """获取账号进度"""
        try:
            return db_manager.get_account_progress(username, target_count)
        except Exception as e:
            if self.logger:
                self.logger.error(f"获取账号进度失败: {e}")
            return ("获取失败", False, 0)


# 全局实例
database_account_manager = DatabaseAccountManager()
database_video_manager = DatabaseVideoManager() 