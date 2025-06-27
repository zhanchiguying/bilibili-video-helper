#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传管理服务 - 上传相关业务逻辑
"""

import os
from typing import List, Dict, Optional, Tuple

from .base_service import BaseService


class UploadService(BaseService):
    """上传管理服务"""
    
    def _do_initialize(self):
        """初始化上传服务"""
        pass
    
    def validate_single_upload(self, account_name: str, video_filename: str, video_directory: str) -> Tuple[bool, str]:
        """
        验证单个上传
        
        Args:
            account_name: 账号名
            video_filename: 视频文件名
            video_directory: 视频目录
            
        Returns:
            Tuple[bool, str]: (是否验证成功, 错误信息)
        """
        try:
            # 验证账号
            if not account_name or not account_name.strip():
                return False, "请选择账号"
            
            # 验证视频文件
            if not video_filename or not video_filename.strip():
                return False, "请选择视频文件"
            
            video_path = os.path.join(video_directory, video_filename)
            if not os.path.exists(video_path):
                return False, f"视频文件不存在: {video_path}"
            
            # 检查文件大小
            file_size = os.path.getsize(video_path)
            if file_size == 0:
                return False, "视频文件为空"
            
            # 检查文件扩展名
            valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
            file_ext = os.path.splitext(video_filename)[1].lower()
            if file_ext not in valid_extensions:
                return False, f"不支持的视频格式: {file_ext}"
            
            return True, ""
            
        except Exception as e:
            return self.handle_error(e, "验证单个上传时发生错误", (False, str(e)))
    
    def validate_batch_upload(self, account_names: List[str], video_files: List[str], video_directory: str) -> Tuple[bool, str]:
        """
        验证批量上传
        
        Args:
            account_names: 账号名列表
            video_files: 视频文件列表
            video_directory: 视频目录
            
        Returns:
            Tuple[bool, str]: (是否验证成功, 错误信息)
        """
        try:
            # 验证账号
            if not account_names:
                return False, "请至少选择一个账号"
            
            # 验证视频文件
            if not video_files:
                return False, "没有找到视频文件"
            
            # 检查每个视频文件
            for video_file in video_files:
                video_path = os.path.join(video_directory, os.path.basename(video_file))
                if not os.path.exists(video_path):
                    return False, f"视频文件不存在: {video_path}"
            
            return True, ""
            
        except Exception as e:
            return self.handle_error(e, "验证批量上传时发生错误", (False, str(e)))
    
    def start_single_upload(self, account_name: str, video_filename: str, video_directory: str, upload_settings: Dict) -> bool:
        """
        开始单个上传
        
        Args:
            account_name: 账号名
            video_filename: 视频文件名
            video_directory: 视频目录
            upload_settings: 上传设置
            
        Returns:
            bool: 是否成功启动
        """
        try:
            # 验证上传
            is_valid, error_msg = self.validate_single_upload(account_name, video_filename, video_directory)
            if not is_valid:
                self.notify_warning(error_msg)
                return False
            
            # 这里应该启动实际的上传线程
            # 由于这是服务层，实际的线程管理由UI层处理
            self.log_message(f"准备开始单个上传: {account_name} -> {video_filename}", "INFO")
            return True
            
        except Exception as e:
            return self.handle_error(e, f"启动单个上传时发生错误")
    
    def get_video_files(self, directory: str) -> List[str]:
        """
        获取视频文件列表
        
        Args:
            directory: 目录路径
            
        Returns:
            List[str]: 视频文件路径列表
        """
        try:
            if not directory or not os.path.exists(directory):
                return []
            
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
            video_files = []
            
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext in video_extensions:
                        video_files.append(file_path)
            
            return sorted(video_files)
            
        except Exception as e:
            self.handle_error(e, f"获取视频文件列表时发生错误")
            return []
    
    def get_upload_statistics(self, directory: str) -> Dict:
        """
        获取上传统计信息
        
        Args:
            directory: 目录路径
            
        Returns:
            Dict: 统计信息
        """
        try:
            video_files = self.get_video_files(directory)
            total_size = 0
            
            for video_file in video_files:
                try:
                    total_size += os.path.getsize(video_file)
                except:
                    continue
            
            return {
                'total_files': len(video_files),
                'total_size': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'files': video_files
            }
            
        except Exception as e:
            self.handle_error(e, f"获取上传统计信息时发生错误")
            return {'total_files': 0, 'total_size': 0, 'total_size_mb': 0, 'files': []}
    
    def cleanup(self):
        """清理资源"""
        super().cleanup() 