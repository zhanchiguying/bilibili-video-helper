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
    # ACCOUNTS_FILE = "accounts.json"  # ❌ 已迁移到SQLite数据库
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
        },
        "ui_settings": {
            "concurrent_browsers": "2",
            "videos_per_account": "20",
            "video_directory": "",
            "account_selections": {},
            "success_wait_time": 2
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
        """保存配置文件 - 优化版本（包含数据清理）"""
        with self._lock:
            try:
                # 创建目录（如果不存在）
                config_dir = os.path.dirname(self.config_file)
                if config_dir and not os.path.exists(config_dir):
                    os.makedirs(config_dir)
                
                # 🎯 保存前清理数据，去除\n等异常字符
                cleaned_config = DataCleaner.clean_config_data(self.config)
                
                # 记录清理效果
                if cleaned_config != self.config:
                    self.logger.info("配置数据已清理，去除异常字符")
                    # 更新内存中的配置为清理后的版本
                    self.config = cleaned_config
                
                # 原子写入（先写临时文件再重命名）
                temp_file = f"{self.config_file}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(cleaned_config, f, ensure_ascii=False, indent=2)
                
                # 重命名为正式文件
                os.replace(temp_file, self.config_file)
                
                # 更新修改时间
                self._last_modified = os.path.getmtime(self.config_file)
                
                self.logger.debug("配置文件保存成功（已清理数据）")
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


# =============================================================================
# UI配置部分 - 从core/ui_config.py合并而来
# =============================================================================

class UIConfig:
    """UI配置类 - 优化版本"""
    
    # 窗口配置 - 优化宽度，让界面更紧凑
    WINDOW_WIDTH = 1080  # 从1200减少到1080，更适合显示
    WINDOW_HEIGHT = 800
    WINDOW_X = -1  # -1 表示自动居中
    WINDOW_Y = -1  # -1 表示自动居中
    
    # 组件尺寸
    VIDEO_LIST_MAX_HEIGHT = 200
    TABLE_COLUMN_WIDTHS = {
        'account_name': 120,
        'login_status': 120,
        'browser_status': 120,
        'last_login': 180  # 从150增加到180，确保最后登录时间完整显示
    }
    
    # 🚀 优化后的延时配置（大幅减少延迟）
    PAGE_LOAD_DELAY = 2  # 从5秒减少到2秒
    BUTTON_CLICK_DELAY = 0.5  # 从1秒减少到0.5秒
    STATUS_UPDATE_INTERVAL = 1  # 从2秒减少到1秒
    
    # 🎯 智能等待策略
    SMART_WAIT_CONFIG = {
        'fast_check': 0.2,      # 快速检查间隔
        'normal_check': 1,      # 普通检查间隔
        'slow_check': 3,        # 慢速检查间隔
        'max_fast_attempts': 10, # 快速检查最大次数
        'max_normal_attempts': 5, # 普通检查最大次数
    }
    
    # 超时配置（秒）- 优化
    BROWSER_CONNECT_TIMEOUT = 20  # 从30秒减少到20秒
    UPLOAD_TIMEOUT = 600  # 保持10分钟（上传需要足够时间）
    LOGIN_TIMEOUT = 30    # 从60秒减少到30秒
    
    # 🎯 新增：智能重试配置
    RETRY_CONFIG = {
        'max_retries': 3,
        'retry_delay': 1,
        'exponential_backoff': True
    }
    
    # 字体配置
    LOG_FONT_FAMILY = "Consolas"
    LOG_FONT_SIZE = 9
    
    # 状态消息
    STATUS_MESSAGES = {
        'ready': '准备就绪',
        'uploading': '上传中...',
        'success': '上传成功',
        'failed': '上传失败',
        'connecting': '连接中...',
        'waiting': '等待中...'
    }
    
    # 日志级别颜色
    LOG_COLORS = {
        'ERROR': 'red',
        'WARNING': 'orange', 
        'SUCCESS': 'green',
        'INFO': 'black'
    }
    
    # 支持的视频格式
    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
    
    # UI文本
    UI_TEXT = {
        'account_management': '账号管理',
        'browser_upload': '浏览器上传',
        'run_log': '运行日志',
        'add_account': '➕ 添加账号',
        'login_account': '🔑 登录账号',
        'remove_account': '🗑️ 删除账号',
        'detect_browser': '🔍 检测浏览器',
        'refresh_status': '🔄 刷新状态',
        'select_directory': '📁 选择目录',
        'start_upload': '🚀 开始浏览器上传',
        'pause_upload': '⏸️ 暂停',
        'stop_upload': '⏹️ 停止'
    } 


class SmartWaitManager:
    """智能等待管理器 - 替代固定sleep"""
    
    @staticmethod
    def smart_sleep(base_time: float, condition_check=None, max_time: Optional[float] = None):
        """
        智能睡眠：根据条件动态调整等待时间
        
        Args:
            base_time: 基础等待时间
            condition_check: 检查函数，返回True时停止等待
            max_time: 最大等待时间
        """
        import time
        
        if condition_check is None:
            # 如果没有条件检查，直接使用优化的基础时间
            optimized_time = base_time * 0.7  # 减少30%
            time.sleep(optimized_time)
            return
        
        max_time = max_time if max_time is not None else base_time * 2
        elapsed = 0
        check_interval = UIConfig.SMART_WAIT_CONFIG['fast_check']
        
        while elapsed < max_time:
            if condition_check():
                return  # 条件满足，立即返回
            
            time.sleep(check_interval)
            elapsed += check_interval
            
            # 动态调整检查间隔
            if elapsed > base_time:
                check_interval = UIConfig.SMART_WAIT_CONFIG['normal_check']
    
    @staticmethod
    def wait_for_element_optimized(driver, selector, timeout=10, condition="clickable"):
        """优化的元素等待"""
        from selenium.webdriver.support.wait import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        # 使用智能等待策略
        fast_timeout = min(3, timeout // 3)
        
        try:
            # 快速尝试
            if condition == "clickable":
                return WebDriverWait(driver, fast_timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
            elif condition == "present":
                return WebDriverWait(driver, fast_timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
        except:
            # 快速尝试失败，使用完整超时
            if condition == "clickable":
                return WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
            elif condition == "present":
                return WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )

class DataCleaner:
    """数据清理工具类"""
    
    @staticmethod
    def clean_string(value: str) -> str:
        """清理字符串，去除异常字符"""
        if not isinstance(value, str):
            return str(value)
        
        # 去除首尾空白字符和换行符
        cleaned = value.strip()
        
        # 去除字符串中的换行符、制表符等控制字符
        import re
        cleaned = re.sub(r'[\n\r\t\v\f]', '', cleaned)
        
        # 去除多余的空格
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned
    
    @staticmethod
    def clean_dict_keys(data: dict) -> dict:
        """清理字典的键名"""
        if not isinstance(data, dict):
            return data
        
        cleaned_dict = {}
        for key, value in data.items():
            # 清理键名
            if isinstance(key, str):
                clean_key = DataCleaner.clean_string(key)
            else:
                clean_key = key
            
            # 递归清理值
            if isinstance(value, dict):
                clean_value = DataCleaner.clean_dict_keys(value)
            elif isinstance(value, str):
                clean_value = DataCleaner.clean_string(value)
            elif isinstance(value, list):
                clean_value = DataCleaner.clean_list(value)
            else:
                clean_value = value
            
            cleaned_dict[clean_key] = clean_value
        
        return cleaned_dict
    
    @staticmethod
    def clean_list(data: list) -> list:
        """清理列表数据"""
        if not isinstance(data, list):
            return data
        
        cleaned_list = []
        for item in data:
            if isinstance(item, str):
                cleaned_list.append(DataCleaner.clean_string(item))
            elif isinstance(item, dict):
                cleaned_list.append(DataCleaner.clean_dict_keys(item))
            elif isinstance(item, list):
                cleaned_list.append(DataCleaner.clean_list(item))
            else:
                cleaned_list.append(item)
        
        return cleaned_list
    
    @staticmethod
    def clean_config_data(config: dict) -> dict:
        """清理完整的配置数据"""
        if not isinstance(config, dict):
            return {}
        
        # 深度清理所有数据
        cleaned_config = DataCleaner.clean_dict_keys(config)
        
        # 特殊处理account_selections
        if 'ui_settings' in cleaned_config and 'account_selections' in cleaned_config['ui_settings']:
            account_selections = cleaned_config['ui_settings']['account_selections']
            if isinstance(account_selections, dict):
                # 清理账号名称键名，去除换行符等异常字符
                cleaned_selections = {}
                for account_name, selected in account_selections.items():
                    clean_account_name = DataCleaner.clean_string(str(account_name))
                    # 只保留有效的账号名称（数字字符串）
                    if clean_account_name and clean_account_name.isdigit():
                        cleaned_selections[clean_account_name] = bool(selected)
                
                cleaned_config['ui_settings']['account_selections'] = cleaned_selections
        
        return cleaned_config