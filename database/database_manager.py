#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite数据库管理器 - B站视频助手数据库层
"""

import sqlite3
import json
import threading
import time
from typing import List, Dict, Optional, Tuple, Any
from contextlib import contextmanager
from datetime import datetime, timedelta
import logging

class DatabaseManager:
    """SQLite数据库管理器 - 单例模式"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str = "bilibili_helper.db"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = "bilibili_helper.db"):
        if self._initialized:
            return
        
        self.db_path = db_path
        self.connection_pool = {}
        self.pool_lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # 初始化数据库
        self._init_database()
        self._initialized = True
    
    def _init_database(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建账号表 - 增强版，添加指纹和DevTools端口字段
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'inactive',
                    cookies TEXT,
                    fingerprint TEXT,
                    devtools_port INTEGER,
                    last_login INTEGER,
                    notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建上传记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS uploaded_videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    md5_hash TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    account_username TEXT NOT NULL,
                    upload_date TEXT NOT NULL,
                    product_id TEXT,
                    deleted BOOLEAN DEFAULT 0,
                    file_size INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_username) REFERENCES accounts (username)
                )
            ''')
            
            # 创建设置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建浏览器状态缓存表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS browser_status_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_username TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT 0,
                    port INTEGER,
                    pid INTEGER,
                    last_check TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_username) REFERENCES accounts (username)
                )
            ''')
            
            # 创建高性能复合索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_accounts_username ON accounts (username)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_accounts_status_updated ON accounts (status, updated_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_uploaded_videos_md5 ON uploaded_videos (md5_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_uploaded_videos_account_date ON uploaded_videos (account_username, upload_date, deleted)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_uploaded_videos_date_deleted ON uploaded_videos (upload_date, deleted)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_settings_key ON settings (key)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_browser_cache_username ON browser_status_cache (account_username)')
            
            # 新增：为大数据量优化的统计视图
            cursor.execute('''
                CREATE VIEW IF NOT EXISTS account_progress_view AS
                SELECT 
                    a.username,
                    a.status,
                    COUNT(CASE WHEN uv.upload_date = date('now') AND uv.deleted = 0 THEN 1 END) as today_uploads,
                    COUNT(CASE WHEN uv.deleted = 0 THEN 1 END) as total_uploads,
                    MAX(uv.created_at) as last_upload_time
                FROM accounts a
                LEFT JOIN uploaded_videos uv ON a.username = uv.account_username
                GROUP BY a.username, a.status
            ''')
            
            conn.commit()
            self.logger.info("✅ 数据库初始化完成（增强版）")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（线程安全）"""
        thread_id = threading.get_ident()
        
        with self.pool_lock:
            if thread_id not in self.connection_pool:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row  # 使结果可以像字典一样访问
                # 优化设置
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                conn.execute("PRAGMA cache_size = 10000")
                conn.execute("PRAGMA temp_store = MEMORY")
                
                self.connection_pool[thread_id] = conn
        
        try:
            yield self.connection_pool[thread_id]
        except Exception as e:
            self.connection_pool[thread_id].rollback()
            raise e
    
    def close_all_connections(self):
        """关闭所有连接"""
        with self.pool_lock:
            for conn in self.connection_pool.values():
                conn.close()
            self.connection_pool.clear()
    
    # ================== 账号管理 ==================
    
    def add_account(self, username: str, status: str = 'inactive', 
                   cookies: str = '', notes: str = '') -> bool:
        """添加账号"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO accounts (username, status, cookies, notes)
                    VALUES (?, ?, ?, ?)
                ''', (username, status, cookies, notes))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            self.logger.warning(f"账号 {username} 已存在")
            return False
        except Exception as e:
            self.logger.error(f"添加账号失败: {e}")
            return False
    
    def get_account(self, username: str) -> Optional[Dict]:
        """获取单个账号信息"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM accounts WHERE username = ?', (username,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            self.logger.error(f"获取账号信息失败: {e}")
            return None
    
    def get_accounts_paginated(self, page: int = 1, page_size: int = 50, 
                              search: str = '', status_filter: str = '') -> Tuple[List[Dict], int]:
        """分页获取账号列表"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建WHERE条件
                where_conditions = []
                params = []
                
                if search:
                    where_conditions.append("username LIKE ?")
                    params.append(f"%{search}%")
                
                if status_filter:
                    where_conditions.append("status = ?")
                    params.append(status_filter)
                
                where_clause = " AND ".join(where_conditions)
                if where_clause:
                    where_clause = "WHERE " + where_clause
                
                # 获取总数
                count_query = f"SELECT COUNT(*) FROM accounts {where_clause}"
                cursor.execute(count_query, params)
                total_count = cursor.fetchone()[0]
                
                # 获取分页数据
                offset = (page - 1) * page_size
                data_query = f'''
                    SELECT * FROM accounts {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                '''
                cursor.execute(data_query, params + [page_size, offset])
                
                accounts = [dict(row) for row in cursor.fetchall()]
                return accounts, total_count
                
        except Exception as e:
            self.logger.error(f"分页获取账号失败: {e}")
            return [], 0
    
    def update_account_status(self, username: str, status: str, 
                             cookies: str = None, last_login: int = None) -> bool:
        """更新账号状态"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 动态构建更新字段
                update_fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
                params = [status]
                
                if cookies is not None:
                    update_fields.append("cookies = ?")
                    params.append(cookies)
                
                if last_login is not None:
                    update_fields.append("last_login = ?")
                    params.append(last_login)
                
                params.append(username)
                
                query = f"UPDATE accounts SET {', '.join(update_fields)} WHERE username = ?"
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            self.logger.error(f"更新账号状态失败: {e}")
            return False
    
    def delete_account(self, username: str) -> bool:
        """删除账号"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM accounts WHERE username = ?', (username,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"删除账号失败: {e}")
            return False
    
    # ================== 上传记录管理 ==================
    
    def add_uploaded_video(self, md5_hash: str, filename: str, account_username: str,
                          upload_date: str, product_id: str = '', file_size: int = 0) -> bool:
        """添加上传记录"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO uploaded_videos 
                    (md5_hash, filename, account_username, upload_date, product_id, file_size)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (md5_hash, filename, account_username, upload_date, product_id, file_size))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"添加上传记录失败: {e}")
            return False
    
    def get_account_today_uploads(self, username: str, date: str = None) -> List[Dict]:
        """获取账号今日上传记录"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM uploaded_videos 
                    WHERE account_username = ? AND upload_date = ?
                    ORDER BY created_at DESC
                ''', (username, date))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"获取今日上传记录失败: {e}")
            return []
    
    def get_account_progress(self, username: str, target_count: int = 1, 
                           date: str = None) -> Tuple[str, bool, int]:
        """获取账号进度信息"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM uploaded_videos 
                    WHERE account_username = ? AND upload_date = ? AND deleted = 0
                ''', (username, date))
                
                published_count = cursor.fetchone()[0]
                is_completed = published_count >= target_count
                
                status_text = f"{published_count}/{target_count}"
                if is_completed:
                    status_text += " 已完成"
                else:
                    status_text += " 进行中"
                
                return status_text, is_completed, published_count
                
        except Exception as e:
            self.logger.error(f"获取账号进度失败: {e}")
            return "获取失败", False, 0
    
    def mark_video_deleted(self, md5_hash: str) -> bool:
        """标记视频已删除"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE uploaded_videos SET deleted = 1 
                    WHERE md5_hash = ?
                ''', (md5_hash,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"标记视频删除失败: {e}")
            return False
    
    def is_video_uploaded(self, md5_hash: str) -> bool:
        """检查视频是否已上传"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM uploaded_videos 
                    WHERE md5_hash = ? AND deleted = 0
                ''', (md5_hash,))
                return cursor.fetchone()[0] > 0
        except Exception as e:
            self.logger.error(f"检查视频上传状态失败: {e}")
            return False
    
    # ================== 设置管理 ==================
    
    def get_setting(self, key: str, default_value: str = None) -> Optional[str]:
        """获取设置值"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
                row = cursor.fetchone()
                return row[0] if row else default_value
        except Exception as e:
            self.logger.error(f"获取设置失败: {e}")
            return default_value
    
    def set_setting(self, key: str, value: str, category: str = 'general') -> bool:
        """设置配置值"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value, category, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (key, value, category))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"设置配置失败: {e}")
            return False
    
    def get_all_settings(self, category: str = None) -> Dict[str, str]:
        """获取所有设置"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if category:
                    cursor.execute('SELECT key, value FROM settings WHERE category = ?', (category,))
                else:
                    cursor.execute('SELECT key, value FROM settings')
                return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            self.logger.error(f"获取所有设置失败: {e}")
            return {}
    
    # ================== 数据迁移 ==================
    
    def migrate_from_json(self, accounts_file: str = 'accounts.json', 
                         videos_file: str = 'uploaded_videos.json') -> bool:
        """从JSON文件迁移数据"""
        try:
            import os
            
            # 迁移账号数据
            if os.path.exists(accounts_file):
                with open(accounts_file, 'r', encoding='utf-8') as f:
                    accounts_data = json.load(f)
                    
                migrated_accounts = 0
                for username, account_info in accounts_data.items():
                    if isinstance(account_info, dict):
                        cookies_str = json.dumps(account_info.get('cookies', []))
                        if self.add_account(
                            username=username,
                            status=account_info.get('status', 'inactive'),
                            cookies=cookies_str,
                            notes=account_info.get('notes', '')
                        ):
                            migrated_accounts += 1
                
                self.logger.info(f"✅ 成功迁移 {migrated_accounts} 个账号")
            
            # 迁移上传记录
            if os.path.exists(videos_file):
                with open(videos_file, 'r', encoding='utf-8') as f:
                    videos_data = json.load(f)
                    uploaded_videos = videos_data.get('uploaded_videos', {})
                    
                migrated_videos = 0
                for md5_hash, video_info in uploaded_videos.items():
                    if isinstance(video_info, dict):
                        # 处理日期格式
                        upload_date = video_info.get('upload_date')
                        if not upload_date and video_info.get('upload_time'):
                            try:
                                upload_date = datetime.fromtimestamp(
                                    video_info['upload_time']
                                ).strftime("%Y-%m-%d")
                            except:
                                upload_date = datetime.now().strftime("%Y-%m-%d")
                        elif not upload_date:
                            upload_date = datetime.now().strftime("%Y-%m-%d")
                        
                        if self.add_uploaded_video(
                            md5_hash=md5_hash,
                            filename=video_info.get('filename', ''),
                            account_username=video_info.get('account', ''),
                            upload_date=upload_date,
                            product_id=video_info.get('product_id', ''),
                            file_size=video_info.get('file_size', 0)
                        ):
                            migrated_videos += 1
                            
                            # 处理删除标记
                            if video_info.get('deleted', False):
                                self.mark_video_deleted(md5_hash)
                
                self.logger.info(f"✅ 成功迁移 {migrated_videos} 条上传记录")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 数据迁移失败: {e}")
            return False
    
    # ================== 统计分析 ==================
    
    def get_account_statistics(self) -> Dict[str, Any]:
        """获取账号统计信息"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 基础统计
                cursor.execute('SELECT COUNT(*) FROM accounts')
                total_accounts = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM accounts WHERE status = 'active'")
                active_accounts = cursor.fetchone()[0]
                
                # 今日上传统计
                today = datetime.now().strftime("%Y-%m-%d")
                cursor.execute('''
                    SELECT COUNT(DISTINCT account_username) FROM uploaded_videos 
                    WHERE upload_date = ?
                ''', (today,))
                today_active_accounts = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(*) FROM uploaded_videos 
                    WHERE upload_date = ? AND deleted = 0
                ''', (today,))
                today_uploads = cursor.fetchone()[0]
                
                return {
                    'total_accounts': total_accounts,
                    'active_accounts': active_accounts,
                    'today_active_accounts': today_active_accounts,
                    'today_uploads': today_uploads,
                    'activity_rate': round(today_active_accounts / max(total_accounts, 1) * 100, 2)
                }
                
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def cleanup_old_records(self, days: int = 30) -> int:
        """清理旧记录"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM uploaded_videos 
                    WHERE upload_date < ? AND deleted = 1
                ''', (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"✅ 清理了 {deleted_count} 条旧记录")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"清理旧记录失败: {e}")
            return 0
    
    # ================== 新增：批量操作接口 ==================
    
    def batch_update_accounts(self, account_updates: List[Dict]) -> int:
        """
        批量更新账号信息
        
        Args:
            account_updates: 账号更新列表，格式：[{
                'username': 'xxx', 
                'status': 'active',
                'cookies': '...',
                'fingerprint': '...',
                'devtools_port': 8080
            }, ...]
            
        Returns:
            int: 成功更新的账号数量
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                updated_count = 0
                
                for update_data in account_updates:
                    username = update_data.get('username')
                    if not username:
                        continue
                    
                    # 动态构建更新字段
                    update_fields = ["updated_at = CURRENT_TIMESTAMP"]
                    params = []
                    
                    for field in ['status', 'cookies', 'fingerprint', 'devtools_port', 'last_login', 'notes']:
                        if field in update_data:
                            update_fields.append(f"{field} = ?")
                            params.append(update_data[field])
                    
                    params.append(username)
                    
                    query = f"UPDATE accounts SET {', '.join(update_fields)} WHERE username = ?"
                    cursor.execute(query, params)
                    
                    if cursor.rowcount > 0:
                        updated_count += 1
                
                conn.commit()
                self.logger.info(f"✅ 批量更新了 {updated_count} 个账号")
                return updated_count
                
        except Exception as e:
            self.logger.error(f"批量更新账号失败: {e}")
            return 0
    
    def batch_insert_videos(self, video_records: List[Dict]) -> int:
        """
        批量插入视频记录
        
        Args:
            video_records: 视频记录列表
            
        Returns:
            int: 成功插入的记录数量
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                insert_data = []
                for record in video_records:
                    insert_data.append((
                        record.get('md5_hash', ''),
                        record.get('filename', ''),
                        record.get('account_username', ''),
                        record.get('upload_date', datetime.now().strftime("%Y-%m-%d")),
                        record.get('product_id', ''),
                        record.get('file_size', 0)
                    ))
                
                cursor.executemany('''
                    INSERT INTO uploaded_videos 
                    (md5_hash, filename, account_username, upload_date, product_id, file_size)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', insert_data)
                
                conn.commit()
                inserted_count = cursor.rowcount
                self.logger.info(f"✅ 批量插入了 {inserted_count} 条视频记录")
                return inserted_count
                
        except Exception as e:
            self.logger.error(f"批量插入视频记录失败: {e}")
            return 0
    
    def get_all_accounts_cached(self, cache_seconds: int = 30) -> List[Dict]:
        """
        获取所有账号列表（带缓存）
        
        Args:
            cache_seconds: 缓存时间（秒）
            
        Returns:
            List[Dict]: 账号列表
        """
        cache_key = 'all_accounts'
        
        # 检查缓存
        if hasattr(self, '_cache') and cache_key in self._cache:
            cache_time, cached_data = self._cache[cache_key]
            if time.time() - cache_time < cache_seconds:
                return cached_data
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT username, status, cookies, fingerprint, devtools_port, 
                           last_login, notes, created_at, updated_at
                    FROM accounts 
                    ORDER BY created_at DESC
                ''')
                
                accounts = [dict(row) for row in cursor.fetchall()]
                
                # 更新缓存
                if not hasattr(self, '_cache'):
                    self._cache = {}
                self._cache[cache_key] = (time.time(), accounts)
                
                return accounts
                
        except Exception as e:
            self.logger.error(f"获取所有账号失败: {e}")
            return []
    
    def get_accounts_progress_batch(self, usernames: List[str], 
                                   target_count: int = 1, date: str = None) -> Dict[str, Tuple[str, bool, int]]:
        """
        批量获取多个账号的进度信息（高性能版）
        
        Args:
            usernames: 账号名列表
            target_count: 目标上传数量
            date: 指定日期，默认今天
            
        Returns:
            Dict[str, Tuple[str, bool, int]]: {账号名: (状态文本, 是否完成, 已发布数量)}
        """
        if not usernames:
            return {}
        
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 使用IN查询批量获取所有账号的进度
                placeholders = ','.join(['?' for _ in usernames])
                query = f'''
                    SELECT 
                        account_username,
                        COUNT(*) as upload_count
                    FROM uploaded_videos 
                    WHERE account_username IN ({placeholders}) 
                        AND upload_date = ? 
                        AND deleted = 0
                    GROUP BY account_username
                '''
                
                cursor.execute(query, usernames + [date])
                results = cursor.fetchall()
                
                # 构建结果字典
                progress_dict = {}
                upload_counts = {row[0]: row[1] for row in results}
                
                for username in usernames:
                    published_count = upload_counts.get(username, 0)
                    is_completed = published_count >= target_count
                    
                    status_text = f"{published_count}/{target_count}"
                    if is_completed:
                        status_text += " ✅ 已完成"
                    else:
                        status_text += " 🔄 进行中"
                    
                    progress_dict[username] = (status_text, is_completed, published_count)
                
                return progress_dict
                
        except Exception as e:
            self.logger.error(f"批量获取账号进度失败: {e}")
            return {username: ("获取失败", False, 0) for username in usernames}


# 全局数据库实例
db_manager = DatabaseManager() 