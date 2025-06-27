#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件管理服务 - 文件相关业务逻辑
"""

import os
from typing import List, Tuple
from .base_service import BaseService


class FileService(BaseService):
    """文件管理服务"""
    
    def save_log(self, log_content: str, filename: str = None) -> bool:
        """
        保存日志到文件
        
        Args:
            log_content: 日志内容
            filename: 文件名（可选）
            
        Returns:
            bool: 是否保存成功
        """
        if not log_content:
            self.notify_warning("日志内容为空")
            return False
        
        try:
            if not filename:
                import time
                filename = f"log_{int(time.time())}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(log_content)
            
            self.notify_success(f"日志已保存到: {filename}")
            return True
            
        except Exception as e:
            return self.handle_error(e, "保存日志时发生错误")
    
    def scan_video_files(self, directory: str) -> Tuple[List[str], int, int]:
        """
        扫描视频文件
        
        Args:
            directory: 目录路径
            
        Returns:
            Tuple[List[str], int, int]: (文件列表, 总大小MB, 文件数量)
        """
        try:
            if not os.path.exists(directory):
                return [], 0, 0
            
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
            video_files = []
            total_size = 0
            
            for filename in os.listdir(directory):
                if any(filename.lower().endswith(ext) for ext in video_extensions):
                    video_files.append(filename)
                    file_path = os.path.join(directory, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                    except OSError:
                        pass
            
            total_size_mb = total_size // (1024 * 1024)
            return sorted(video_files), total_size_mb, len(video_files)
            
        except Exception as e:
            self.handle_error(e, f"扫描视频文件时发生错误: {directory}")
            return [], 0, 0
    
    def validate_directory(self, directory: str) -> bool:
        """
        验证目录是否有效
        
        Args:
            directory: 目录路径
            
        Returns:
            bool: 是否有效
        """
        if not directory:
            return False
        
        try:
            return os.path.exists(directory) and os.path.isdir(directory)
        except Exception as e:
            self.handle_error(e, f"验证目录时发生错误: {directory}")
            return False
    
    def get_file_info(self, file_path: str) -> dict:
        """
        获取文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            dict: 文件信息
        """
        try:
            if not os.path.exists(file_path):
                return {}
            
            stat = os.stat(file_path)
            return {
                'name': os.path.basename(file_path),
                'size': stat.st_size,
                'size_mb': stat.st_size // (1024 * 1024),
                'modified': stat.st_mtime,
                'created': stat.st_ctime
            }
            
        except Exception as e:
            self.handle_error(e, f"获取文件信息时发生错误: {file_path}")
            return {} 