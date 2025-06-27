"""
B站视频上传助手 - 核心业务逻辑模块
处理账号管理、视频上传、商品验证等核心业务逻辑
"""

import os
import json
import time
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from .thread_manager import BaseWorkerThread, get_thread_manager
from .bilibili_product_manager import get_product_manager
from .ui_config import UIConfig


class BusinessLogicManager:
    """业务逻辑管理器"""
    
    def __init__(self, core_app):
        self.core_app = core_app
        self.product_manager = get_product_manager()
        self.thread_manager = get_thread_manager()
        self.uploaded_videos_cache = {}
        self._load_uploaded_videos()
    
    def _load_uploaded_videos(self):
        """加载已上传视频记录"""
        try:
            with open('uploaded_videos.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.uploaded_videos_cache = data.get('uploaded_videos', {})
        except (FileNotFoundError, json.JSONDecodeError):
            self.uploaded_videos_cache = {}
    
    def _save_uploaded_videos(self):
        """保存已上传视频记录"""
        try:
            data = {
                "uploaded_videos": self.uploaded_videos_cache,
                "description": "记录已上传视频的MD5值，防止重复上传",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
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
    
    def get_file_md5(self, file_path: str) -> Optional[str]:
        """计算文件MD5值"""
        if not os.path.exists(file_path):
            return None
            
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return None
    
    def is_video_uploaded(self, file_path: str) -> bool:
        """检查视频是否已上传"""
        md5_hash = self.get_file_md5(file_path)
        if not md5_hash:
            return False
        return md5_hash in self.uploaded_videos_cache
    
    def mark_video_uploaded(self, file_path: str, account: str, product_id: str):
        """标记视频已上传"""
        md5_hash = self.get_file_md5(file_path)
        if md5_hash:
            self.uploaded_videos_cache[md5_hash] = {
                "filename": os.path.basename(file_path),
                "upload_time": int(time.time()),
                "account": account,
                "product_id": product_id,
                "deleted": False
            }
            self._save_uploaded_videos()
    
    def validate_account(self, account_name: str) -> Tuple[bool, str, Any]:
        """验证账号状态"""
        account = self.core_app.account_manager.get_account(account_name)
        if not account:
            return False, "账号不存在", None
        
        if account.status != 'active':
            return False, "账号未激活，请先登录", None
        
        return True, "账号验证通过", account
    
    def validate_video_file(self, video_path: str) -> Tuple[bool, str]:
        """验证视频文件"""
        if not os.path.exists(video_path):
            return False, f"视频文件不存在: {video_path}"
        
        # 检查文件大小
        file_size = os.path.getsize(video_path)
        if file_size == 0:
            return False, "视频文件为空"
        
        # 检查文件扩展名
        valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
        _, ext = os.path.splitext(video_path)
        if ext.lower() not in valid_extensions:
            return False, f"不支持的视频格式: {ext}"
        
        return True, "视频文件验证通过"
    
    def validate_product(self, filename: str, account) -> Tuple[bool, str, Optional[Dict]]:
        """验证商品信息"""
        # 提取商品ID
        product_id = self.product_manager.extract_product_id_from_filename(filename)
        if not product_id:
            return False, "无法从文件名提取商品ID", None
        
        # 获取Cookie
        cookies = self.product_manager.get_cookies_from_account(account)
        if not cookies:
            return False, "无法获取账号Cookie，请重新登录", None
        
        # 验证商品
        jd_url = self.product_manager.build_jd_url(product_id)
        success, product_info = self.product_manager.distinguish_product(jd_url, cookies)
        
        if not success or not product_info:
            return False, f"商品验证失败 (ID: {product_id})，可能商品不在B站联盟库中", None
        
        return True, f"商品验证成功: {product_info.get('goodsName', '未知商品')}", product_info
    
    def filter_uploadable_videos(self, video_files: List[str]) -> Tuple[List[str], List[str]]:
        """过滤可上传的视频文件"""
        uploadable = []
        skipped = []
        
        for video_file in video_files:
            if self.is_video_uploaded(video_file):
                skipped.append(video_file)
            else:
                uploadable.append(video_file)
        
        return uploadable, skipped
    
    def calculate_upload_plan(self, accounts: List[str], videos: List[str], 
                            videos_per_account: int) -> Dict[str, List[str]]:
        """计算上传计划"""
        plan = {}
        video_index = 0
        
        for account in accounts:
            account_videos = []
            for _ in range(videos_per_account):
                if video_index < len(videos):
                    account_videos.append(videos[video_index])
                    video_index += 1
                else:
                    break
            plan[account] = account_videos
        
        return plan
    
    def get_upload_statistics(self) -> Dict[str, Any]:
        """获取上传统计信息"""
        total_uploads = len(self.uploaded_videos_cache)
        today_uploads = 0
        account_stats = {}
        
        current_time = int(time.time())
        one_day_ago = current_time - 86400  # 24小时前
        
        for md5_hash, info in self.uploaded_videos_cache.items():
            upload_time = info.get('upload_time', 0)
            account = info.get('account', 'unknown')
            
            # 统计今日上传
            if upload_time > one_day_ago:
                today_uploads += 1
            
            # 统计账号上传数
            if account not in account_stats:
                account_stats[account] = {'total': 0, 'today': 0}
            
            account_stats[account]['total'] += 1
            if upload_time > one_day_ago:
                account_stats[account]['today'] += 1
        
        return {
            'total_uploads': total_uploads,
            'today_uploads': today_uploads,
            'account_stats': account_stats,
            'last_update': current_time
        }


# 全局实例
_business_logic_manager = None

def get_business_logic_manager(core_app=None):
    """获取业务逻辑管理器单例"""
    global _business_logic_manager
    if _business_logic_manager is None and core_app:
        _business_logic_manager = BusinessLogicManager(core_app)
    return _business_logic_manager 