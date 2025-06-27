#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设置管理服务 - 设置相关业务逻辑
"""

import json
import os
from typing import Dict, Any, Optional
from .base_service import BaseService


class SettingsService(BaseService):
    """设置管理服务"""
    
    def _do_initialize(self):
        """初始化设置服务"""
        self.settings_file = "ui_settings.json"
        self._settings_cache = {}
    
    def load_settings(self) -> Dict[str, Any]:
        """
        加载UI设置
        
        Returns:
            Dict[str, Any]: 设置字典
        """
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self._settings_cache = settings
                    self.log_message(f"UI设置已加载: {len(settings)} 项", "INFO")
                    return settings
            else:
                self.log_message("设置文件不存在，使用默认设置", "INFO")
                return {}
                
        except Exception as e:
            self.handle_error(e, "加载UI设置时发生错误")
            return {}
    
    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """
        保存UI设置
        
        Args:
            settings: 设置字典
            
        Returns:
            bool: 是否保存成功
        """
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            self._settings_cache = settings.copy()
            self.log_message(f"UI设置已保存: {len(settings)} 项", "INFO")
            return True
            
        except Exception as e:
            return self.handle_error(e, "保存UI设置时发生错误")
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        获取单个设置
        
        Args:
            key: 设置键
            default: 默认值
            
        Returns:
            Any: 设置值
        """
        try:
            if key in self._settings_cache:
                return self._settings_cache[key]
            
            # 如果缓存中没有，尝试从文件加载
            settings = self.load_settings()
            return settings.get(key, default)
            
        except Exception as e:
            self.handle_error(e, f"获取设置 {key} 时发生错误")
            return default
    
    def set_setting(self, key: str, value: Any) -> bool:
        """
        设置单个设置
        
        Args:
            key: 设置键
            value: 设置值
            
        Returns:
            bool: 是否设置成功
        """
        try:
            # 更新缓存
            self._settings_cache[key] = value
            
            # 保存到文件
            return self.save_settings(self._settings_cache)
            
        except Exception as e:
            return self.handle_error(e, f"设置 {key} 时发生错误")
    
    def get_window_geometry(self) -> Optional[Dict[str, int]]:
        """
        获取窗口几何信息
        
        Returns:
            Optional[Dict[str, int]]: 窗口几何信息
        """
        return self.get_setting("window_geometry")
    
    def save_window_geometry(self, x: int, y: int, width: int, height: int) -> bool:
        """
        保存窗口几何信息
        
        Args:
            x: X坐标
            y: Y坐标
            width: 宽度
            height: 高度
            
        Returns:
            bool: 是否保存成功
        """
        return self.set_setting("window_geometry", {
            "x": x,
            "y": y,
            "width": width,
            "height": height
        })
    
    def get_account_selections(self) -> Dict[str, bool]:
        """
        获取账号选择状态
        
        Returns:
            Dict[str, bool]: 账号选择状态
        """
        return self.get_setting("account_selections", {})
    
    def save_account_selections(self, selections: Dict[str, bool]) -> bool:
        """
        保存账号选择状态
        
        Args:
            selections: 账号选择状态
            
        Returns:
            bool: 是否保存成功
        """
        return self.set_setting("account_selections", selections)
    
    def get_video_directory(self) -> str:
        """
        获取视频目录
        
        Returns:
            str: 视频目录路径
        """
        return self.get_setting("video_directory", "")
    
    def save_video_directory(self, directory: str) -> bool:
        """
        保存视频目录
        
        Args:
            directory: 目录路径
            
        Returns:
            bool: 是否保存成功
        """
        return self.set_setting("video_directory", directory)
    
    def get_upload_settings(self) -> Dict[str, Any]:
        """
        获取上传设置
        
        Returns:
            Dict[str, Any]: 上传设置
        """
        return self.get_setting("upload_settings", {
            "concurrent_browsers": 3,
            "videos_per_account": 5,
            "success_wait_time": 10
        })
    
    def save_upload_settings(self, settings: Dict[str, Any]) -> bool:
        """
        保存上传设置
        
        Args:
            settings: 上传设置
            
        Returns:
            bool: 是否保存成功
        """
        return self.set_setting("upload_settings", settings) 