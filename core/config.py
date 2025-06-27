#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置模块 - 管理应用配置和常量
"""

class Config:
    """应用配置常量"""
    
    # 应用信息
    APP_NAME = "B站带货助手"
    APP_VERSION = "2.0.0"
    
    # 文件路径
    CONFIG_FILE = "config.json"
    ACCOUNTS_FILE = "accounts.json"
    # KEY_FILE = "key.key"  # 🎯 已移除加密功能，不再需要密钥文件
    VIDEOS_DIR = "videos"
    LOGS_DIR = "logs"
    
    # 网络设置
    TIMEOUT = 30
    UPLOAD_TIMEOUT = 1800
    MAX_RETRIES = 3
    
    # B站URL
    BILIBILI_HOME = "https://www.bilibili.com"
    BILIBILI_LOGIN = "https://passport.bilibili.com/login"
    
    # 浏览器设置 - 优化窗口显示（用户要求不要最大化）
    CHROME_OPTIONS = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", 
        "--no-sandbox",
        "--disable-web-security",
        # 确保窗口可见的选项（移除--start-maximized，改用程序设置合适大小）
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-background-networking",
        "--force-first-run-ui",
        # 禁用GPU加速可能导致的显示问题，但保留基本渲染能力
        "--disable-gpu-sandbox",
        "--disable-software-rasterizer"
    ]
    
    # 支持的视频格式
    VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
    
    # UI配置
    WINDOW_SIZE = (1280, 950)
    UI_COLORS = {
        'active': '#90EE90',     # 浅绿色
        'inactive': '#FFB6C1',   # 浅红色 
        'warning': '#FFFFE0',    # 浅黄色
        'success': '#4CAF50',    # 绿色
        'danger': '#f44336'      # 红色
    }
    
    # 默认配置
    DEFAULT_CONFIG = {
        "video_directory": VIDEOS_DIR,
        "upload_settings": {
            "title_template": "{filename}",
            "description": "精彩视频内容，欢迎观看！",
            "tags": ["带货", "推荐", "好物"],
            "category": "生活",
            "success_wait_time": 2  # 🎯 新增：投稿成功后等待时间（秒）
        },
        "browser_settings": {
            "headless": False,
            "window_size": "1920,1080"
        }
    }


import json
import os
import time
import threading
from typing import Dict, Any, Optional, Callable
from .logger import get_logger

class ConfigManager:
    """配置管理器 - 性能优化版本"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or Config.CONFIG_FILE
        self.config = {}
        self._config_cache = {}
        self._last_modified = 0
        self._lock = threading.RLock()
        self._change_callbacks = []
        self.logger = get_logger()
        
        # 初始加载配置
        self._load_config()
        
        # 启动文件监控
        self._start_file_monitor()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件 - 优化版本"""
        with self._lock:
            try:
                # 检查文件修改时间
                if os.path.exists(self.config_file):
                    current_modified = os.path.getmtime(self.config_file)
                    
                    # 如果文件未修改且已有缓存，直接返回缓存
                    if (self._last_modified == current_modified and 
                        self._config_cache):
                        return self._config_cache
                    
                    # 加载文件
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    # 合并默认配置
                    merged_config = Config.DEFAULT_CONFIG.copy()
                    self._deep_update(merged_config, config)
                    
                    # 更新缓存
                    self._config_cache = merged_config
                    self._last_modified = current_modified
                    self.config = merged_config
                    
                    self.logger.debug(f"配置文件加载成功: {self.config_file}")
                    return merged_config
                else:
                    # 文件不存在，使用默认配置
                    default_config = Config.DEFAULT_CONFIG.copy()
                    self._config_cache = default_config
                    self.config = default_config
                    self.logger.info("使用默认配置")
                    return default_config
                    
            except Exception as e:
                self.logger.error(f"加载配置文件失败: {e}")
                # 返回默认配置
                default_config = Config.DEFAULT_CONFIG.copy()
                self._config_cache = default_config
                self.config = default_config
                return default_config
    
    def _deep_update(self, base_dict: dict, update_dict: dict):
        """深度更新字典"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def _start_file_monitor(self):
        """启动文件监控线程"""
        def monitor_file():
            while True:
                try:
                    time.sleep(5)  # 每5秒检查一次
                    if os.path.exists(self.config_file):
                        current_modified = os.path.getmtime(self.config_file)
                        if current_modified != self._last_modified:
                            self.logger.info("检测到配置文件变化，重新加载")
                            old_config = self.config.copy()
                            self._load_config()
                            
                            # 触发变更回调
                            self._notify_config_change(old_config, self.config)
                
                except Exception as e:
                    self.logger.error(f"文件监控异常: {e}")
                    time.sleep(10)  # 出错后等待更长时间
        
        monitor_thread = threading.Thread(target=monitor_file, daemon=True)
        monitor_thread.start()
    
    def save_config(self) -> bool:
        """保存配置文件 - 优化版本"""
        with self._lock:
            try:
                # 创建目录（如果不存在）
                config_dir = os.path.dirname(self.config_file)
                if config_dir and not os.path.exists(config_dir):
                    os.makedirs(config_dir)
                
                # 原子写入（先写临时文件再重命名）
                temp_file = f"{self.config_file}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=2)
                
                # 重命名为正式文件
                os.replace(temp_file, self.config_file)
                
                # 更新修改时间
                self._last_modified = os.path.getmtime(self.config_file)
                
                self.logger.debug("配置文件保存成功")
                return True
                
            except Exception as e:
                self.logger.error(f"保存配置文件失败: {e}")
                # 清理临时文件
                temp_file = f"{self.config_file}.tmp"
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                return False
    
    def get(self, key: str, default=None):
        """获取配置项 - 支持嵌套键"""
        with self._lock:
            if '.' in key:
                # 支持嵌套键，如 "upload_settings.title_template"
                keys = key.split('.')
                value = self.config
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return default
                return value
            else:
                return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """设置配置项 - 支持嵌套键"""
        with self._lock:
            old_config = self.config.copy()
            
            if '.' in key:
                # 支持嵌套键设置
                keys = key.split('.')
                current = self.config
                for k in keys[:-1]:
                    if k not in current or not isinstance(current[k], dict):
                        current[k] = {}
                    current = current[k]
                current[keys[-1]] = value
            else:
                self.config[key] = value
            
            if self.save_config():
                # 触发变更回调
                self._notify_config_change(old_config, self.config)
                return True
            else:
                # 保存失败，恢复旧配置
                self.config = old_config
                return False
    
    def update(self, updates: Dict[str, Any]) -> bool:
        """批量更新配置 - 优化版本"""
        with self._lock:
            old_config = self.config.copy()
            
            # 应用更新
            self._deep_update(self.config, updates)
            
            if self.save_config():
                # 触发变更回调
                self._notify_config_change(old_config, self.config)
                return True
            else:
                # 保存失败，恢复旧配置
                self.config = old_config
                return False
    
    def add_change_callback(self, callback: Callable[[dict, dict], None]):
        """添加配置变更回调"""
        self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: Callable[[dict, dict], None]):
        """移除配置变更回调"""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    def _notify_config_change(self, old_config: dict, new_config: dict):
        """通知配置变更"""
        for callback in self._change_callbacks:
            try:
                callback(old_config, new_config)
            except Exception as e:
                self.logger.error(f"配置变更回调异常: {e}")
    
    def reload_config(self) -> bool:
        """强制重新加载配置"""
        with self._lock:
            try:
                old_config = self.config.copy()
                self._last_modified = 0  # 强制重新加载
                self._load_config()
                self._notify_config_change(old_config, self.config)
                return True
            except Exception as e:
                self.logger.error(f"重新加载配置失败: {e}")
                return False
    
    def reset_to_default(self) -> bool:
        """重置为默认配置"""
        with self._lock:
            old_config = self.config.copy()
            self.config = Config.DEFAULT_CONFIG.copy()
            
            if self.save_config():
                self._notify_config_change(old_config, self.config)
                return True
            else:
                # 保存失败，恢复旧配置
                self.config = old_config
                return False
    
    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置"""
        with self._lock:
            return self.config.copy()
    
    def export_config(self, export_file: str) -> bool:
        """导出配置到指定文件"""
        try:
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"导出配置失败: {e}")
            return False
    
    def import_config(self, import_file: str) -> bool:
        """从指定文件导入配置"""
        try:
            with open(import_file, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            
            return self.update(imported_config)
        except Exception as e:
            self.logger.error(f"导入配置失败: {e}")
            return False 