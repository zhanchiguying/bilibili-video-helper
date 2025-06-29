#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主应用模块 - 整合所有功能的核心应用
"""

import os
import sys
import json
import time
import atexit
import hashlib
import random
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
import threading

# PyQt5
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# WebDriver Manager (延迟导入避免启动时的浏览器检测)
try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.core.utils import ChromeType
    _WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    _WEBDRIVER_MANAGER_AVAILABLE = False

# 加密
# from cryptography.fernet import Fernet  # 🎯 已移除加密功能

# 其他依赖
try:
    from fake_useragent import UserAgent
except ImportError:
    UserAgent = None

import urllib3
from urllib3.util.retry import Retry
import requests.adapters

from .config import Config
from .logger import get_logger
from .fingerprint_validator import FingerprintValidator

# 方案5：Selenium超时配置优化
urllib3.disable_warnings()
# 设置urllib3的全局超时和重试配置
urllib3.util.connection.timeout = 2  # 连接超时2秒
default_retry = Retry(
    total=1,  # 最多重试1次
    connect=1,  # 连接重试1次
    read=1,   # 读取重试1次
    status=1, # 状态重试1次
    backoff_factor=0.1,  # 重试间隔0.1秒
    status_forcelist=[500, 502, 503, 504]
)

class Account:
    """账号类"""
    
    def __init__(self, username: str, data: Optional[Dict[str, Any]] = None):
        self.username = username
        data = data if data is not None else {}
        self.cookies = data.get('cookies', [])
        self.fingerprint = data.get('fingerprint', {})
        self.status = data.get('status', 'inactive')
        self.last_login = data.get('last_login', 0)
        self.notes = data.get('notes', '')
        self.devtools_port = data.get('devtools_port', None)  # DevTools端口信息
        self.browser_instance = None  # 保存当前的浏览器实例
        self._browser_ready = False  # 标记浏览器配置是否已就绪
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cookies': self.cookies,
            'fingerprint': self.fingerprint,
            'status': self.status,
            'last_login': self.last_login,
            'notes': self.notes,
            'devtools_port': getattr(self, 'devtools_port', None)  # 保存DevTools端口信息
        }
    
    def is_logged_in(self) -> bool:
        return len(self.cookies) > 0

class BrowserManager:
    """浏览器管理器"""
    
    def __init__(self, account_manager=None):
        self.drivers: List[webdriver.Chrome] = []
        self.logger = get_logger()
        self.account_ports = {}  # 账号端口映射
        self._chrome_path_cache = None  # 🎯 缓存Chrome路径，避免重复检测
        self._port_lock = threading.Lock()  # 🎯 新增：端口分配线程锁
        self._account_manager = account_manager  # 🎯 账号管理器引用，用于获取账号列表
        
        # 🎯 检查Chrome修复配置
        self._chrome_fix_config = self._load_chrome_fix_config()
        if self._chrome_fix_config.get('chrome_fix_applied'):
            self.logger.info("✅ 检测到Chrome修复配置已应用")
        
        # 初始化浏览器检测器
        from .browser_detector import get_browser_detector
        self.detector = get_browser_detector()
        atexit.register(self.cleanup_all)
        
        # 🔧 启动定期资源清理
        self.setup_periodic_cleanup()
    
    def _get_account_debug_port(self, account_name: str) -> int:
        """简化的端口分配策略 - 账号序号+基础端口"""
        with self._port_lock:  # 🎯 保持线程安全
            if account_name not in self.account_ports:
                # 🎯 简化策略：根据账号名分配固定端口
                if account_name == "__global_init__":
                    # 全局浏览器检测使用固定端口
                    port = 9301
                else:
                    # 账号浏览器使用序号分配
                    port = self._get_account_port_by_sequence(account_name)
                
                self.account_ports[account_name] = port
                self.logger.info(f"🎯 简化分配端口: {account_name} -> {port}")
            
            return self.account_ports[account_name]
    
    def _get_account_port_by_sequence(self, account_name: str) -> int:
        """根据账号在列表中的序号分配端口 - 直观易懂"""
        try:
            # 🎯 优化方案：使用账号管理器获取真正的账号列表序号
            if self._account_manager:
                all_accounts = self._account_manager.get_all_accounts()
                if account_name in all_accounts:
                    account_sequence = all_accounts.index(account_name) + 1  # 从1开始编号
                    port = 9310 + account_sequence  # 测试1->9311, 测试2->9312
                    self.logger.info(f"📋 账号 {account_name} 在列表中序号: {account_sequence}, 端口: {port}")
                    return port
                else:
                    self.logger.warning(f"⚠️ 账号 {account_name} 不在账号列表中")
            
            # 🎯 备用方案：基于账号名模式的智能识别
            account_mapping = {
                '1': 1, '测试1': 1, 'test1': 1,
                '2': 2, '测试2': 2, 'test2': 2, 
                '3': 3, '测试3': 3, 'test3': 3,
                '4': 4, '测试4': 4, 'test4': 4,
                '5': 5, '测试5': 5, 'test5': 5,
                '6': 6, '测试6': 6, 'test6': 6,
            }
            
            # 直接映射
            if account_name in account_mapping:
                account_sequence = account_mapping[account_name]
                port = 9310 + account_sequence
                self.logger.info(f"📋 账号 {account_name} 映射序号: {account_sequence}, 端口: {port}")
                return port
            
            # 从账号名提取数字
            import re
            numbers = re.findall(r'\d+', account_name)
            if numbers:
                account_sequence = int(numbers[0])
                # 限制在合理范围内
                if account_sequence > 50:
                    account_sequence = account_sequence % 50 + 1
                port = 9310 + account_sequence
                self.logger.info(f"📋 账号 {account_name} 提取序号: {account_sequence}, 端口: {port}")
                return port
            
            # 最后备用：使用简单哈希
            account_sequence = (hash(account_name) % 20) + 1  # 限制在20个端口内
            port = 9310 + account_sequence
            self.logger.info(f"📋 账号 {account_name} 哈希序号: {account_sequence}, 端口: {port}")
            return port
            
        except Exception as e:
            # 发生错误时使用备用端口
            self.logger.error(f"❌ 端口分配失败: {e}")
            return 9330  # 使用更高的备用端口避免冲突
    
    def _get_best_chrome_path(self) -> Optional[str]:
        """获取最佳的Chrome浏览器路径"""
        try:
            from .browser_detector import get_browser_detector
            browser_detector = get_browser_detector()
            return browser_detector.get_best_chrome_path()
        except Exception as e:
            self.logger.error(f"浏览器检测器初始化失败: {e}")
            # 回退到简单检测
            return self._fallback_chrome_detection()
    
    def _fallback_chrome_detection(self) -> Optional[str]:
        """备用Chrome检测方案"""
        import os
        import platform
        
        system = platform.system()
        self.logger.warning("使用备用Chrome检测方案...")
        
        if system == "Windows":
            possible_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
        elif system == "Darwin":
            possible_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ]
        else:  # Linux
            possible_paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/chromium",
            ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.logger.info(f"备用检测找到Chrome: {path}")
                return path
        
        self.logger.error("备用检测也未找到Chrome浏览器")
        return None
    
    def _load_chrome_fix_config(self) -> Dict[str, Any]:
        """加载Chrome修复配置"""
        try:
            # 获取配置文件路径
            if getattr(sys, 'frozen', False):
                # exe环境
                config_path = Path(sys.executable).parent / "chrome_startup_fix.json"
            else:
                # 开发环境
                config_path = Path(__file__).parent.parent / "chrome_startup_fix.json"
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.logger.info(f"✅ 加载Chrome修复配置: {config_path}")
                return config
            else:
                return {}
        except Exception as e:
            self.logger.warning(f"⚠️ 加载Chrome修复配置失败: {e}")
            return {}
    
    def create_driver(self, fingerprint: Optional[Dict] = None, headless: bool = False, use_user_profile: bool = False, account_name: Optional[str] = None, start_url: Optional[str] = None) -> webdriver.Chrome:
        """
        创建Chrome浏览器实例
        
        Args:
            fingerprint: 浏览器指纹配置
            headless: 是否无头模式
            use_user_profile: 是否使用用户配置文件
            account_name: 账号名称（用于端口分配）
            start_url: 启动时直接访问的URL（优化性能）
        """
        try:
            # 获取Chrome配置
            options = Options()
            
            # 应用基础Chrome选项
            for option in Config.CHROME_OPTIONS:
                options.add_argument(option)
            
            # 排除automation标识
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # 🎯 为账号分配专用调试端口
            if account_name:
                debug_port = self._get_account_debug_port(account_name)
                options.add_argument(f'--remote-debugging-port={debug_port}')
            
            # 应用浏览器指纹
            if fingerprint:
                options.add_argument(f'--user-agent={fingerprint.get("user_agent", "default")}')
                
                # 设置更多指纹参数
                if 'viewport' in fingerprint:
                    viewport = fingerprint['viewport']
                    # 🔧 修复：正确处理字符串格式的viewport
                    if isinstance(viewport, str):
                        # viewport格式如 "1920,1080"
                        width, height = viewport.split(',')
                        options.add_argument(f'--window-size={width},{height}')
                    elif isinstance(viewport, dict):
                        # viewport格式如 {"width": 1920, "height": 1080}
                        options.add_argument(f'--window-size={viewport["width"]},{viewport["height"]}')
                
                # 其他指纹参数...
            
            # 根据使用场景调整
            if headless:
                options.add_argument('--headless')
            
            # 🎯 记录启动URL，稍后访问（避免--app模式的限制）
            should_navigate_on_start = start_url is not None
            if start_url:
                self.logger.info(f"🚀 浏览器启动后将导航到: {start_url}")
            
            # 🎯 检测是否为exe打包环境
            is_exe_env = getattr(sys, 'frozen', False)
            if is_exe_env:
                self.logger.info("🔧 检测到exe打包环境，使用专用启动策略")
            
            # 尝试创建浏览器实例
            driver = None
            
            # 🎯 使用缓存的Chrome浏览器路径（避免重复检测）
            if self._chrome_path_cache is None:
                self._chrome_path_cache = self.detector.get_best_chrome_path()
                if self._chrome_path_cache:
                    self.logger.info(f"🎉 智能检测找到Chrome浏览器: {self._chrome_path_cache}")
                
            chrome_path = self._chrome_path_cache
            if chrome_path:
                # ✅ 使用缓存的Chrome浏览器路径
                self.logger.info(f"🔧 使用Chrome浏览器: {chrome_path}")
                options.binary_location = chrome_path
                
                # 🚀 借鉴gui_main.py思路：如果是ms-playwright，使用强制兼容模式
                if "ms-playwright" in chrome_path.lower():
                    self.logger.info("🎯 检测到ms-playwright浏览器，使用强制兼容模式...")
                    
                    # 添加强制兼容选项，忽略版本检查
                    options.add_argument('--disable-web-security')
                    options.add_argument('--disable-features=VizDisplayCompositor')
                    options.add_argument('--disable-extensions')
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    
                    # 🎯 exe环境特殊处理：绕过Selenium Manager验证
                    if is_exe_env:
                        self.logger.info("🚀 exe环境：使用无验证模式启动Chrome...")
                        
                        # 🔧 exe环境下的关键修复：设置超时和跳过验证
                        try:
                            # 添加更多exe兼容性选项
                            options.add_argument('--disable-gpu')
                            options.add_argument('--disable-software-rasterizer')
                            options.add_argument('--disable-background-timer-throttling')
                            options.add_argument('--disable-backgrounding-occluded-windows')
                            options.add_argument('--disable-renderer-backgrounding')
                            options.add_argument('--disable-features=TranslateUI')
                            options.add_argument('--disable-blink-features=AutomationControlled')
                            options.add_argument('--no-first-run')
                            options.add_argument('--disable-default-apps')
                            
                            # 🎯 关键修复：检查是否有Chrome修复配置
                            fix_config = self._chrome_fix_config
                            if fix_config.get('selenium_manager_disabled'):
                                self.logger.info("🔧 应用Chrome修复配置：禁用Selenium Manager")
                                # 设置环境变量禁用Selenium Manager
                                import os
                                os.environ['SE_AVOID_SELENIUM_MANAGER'] = '1'
                            
                            # 🎯 关键修复：创建自定义Service，避免Selenium Manager
                            from selenium.webdriver.chrome.service import Service
                            
                            # 检查是否有项目内置的ChromeDriver
                            exe_dir = Path(sys.executable).parent
                            builtin_driver = exe_dir / "drivers" / "chromedriver.exe"
                            
                            if builtin_driver.exists():
                                self.logger.info(f"🔧 exe模式：使用项目内置ChromeDriver: {builtin_driver}")
                                service = Service(str(builtin_driver))
                            else:
                                # 尝试使用系统默认ChromeDriver（通常在PATH中）
                                self.logger.info("🔧 exe模式：尝试系统ChromeDriver...")
                                service = Service()  # 不指定路径，让系统自动找
                            
                            # 设置服务超时
                            service.start_error_message = "ChromeDriver启动超时"
                            
                            self.logger.info("🔧 开始创建WebDriver实例（无验证模式）...")
                            driver = webdriver.Chrome(service=service, options=options)
                            self.logger.info("✅ exe环境Chrome启动成功！")
                            
                        except Exception as exe_chrome_error:
                            self.logger.warning(f"exe环境Chrome启动失败: {exe_chrome_error}")
                            
                            # 🔧 备用方案：尝试不指定service的方式
                            try:
                                self.logger.info("🔧 exe备用方案：直接创建Chrome实例...")
                                
                                # 临时设置环境变量，跳过Selenium Manager
                                import os
                                env_backup = os.environ.get('SE_AVOID_SELENIUM_MANAGER', '')
                                os.environ['SE_AVOID_SELENIUM_MANAGER'] = '1'
                                
                                try:
                                    driver = webdriver.Chrome(options=options)
                                    self.logger.info("✅ exe备用方案成功！")
                                finally:
                                    # 恢复环境变量
                                    if env_backup:
                                        os.environ['SE_AVOID_SELENIUM_MANAGER'] = env_backup
                                    else:
                                        os.environ.pop('SE_AVOID_SELENIUM_MANAGER', None)
                                        
                            except Exception as exe_backup_error:
                                self.logger.error(f"exe备用方案也失败: {exe_backup_error}")
                                raise exe_backup_error
                    else:
                        # 非exe环境，使用原来的逻辑
                        try:
                            self.logger.info("🚀 开发环境：直接使用系统ChromeDriver...")
                            
                            # 🔍 详细记录启动过程
                            self.logger.info("🔧 开始创建WebDriver实例...")
                            driver = webdriver.Chrome(options=options)
                            self.logger.info("🔧 WebDriver实例创建完成")
                            
                            # 🔍 测试基本功能
                            self.logger.info("🔧 测试浏览器基本功能...")
                            test_title = driver.title
                            self.logger.info(f"🔧 浏览器标题获取成功: {test_title}")
                            
                            test_url = driver.current_url  
                            self.logger.info(f"🔧 浏览器URL获取成功: {test_url}")
                            
                            self.logger.info("✅ ms-playwright + 系统ChromeDriver 组合成功！")
                        except Exception as ms_error:
                            self.logger.error(f"❌ ms-playwright模式失败: {ms_error}")
                            self.logger.error(f"❌ 错误类型: {type(ms_error).__name__}")
                            import traceback
                            self.logger.error(f"❌ 错误堆栈: {traceback.format_exc()}")
                            raise ms_error
                else:
                    # 非ms-playwright浏览器，使用标准策略
                    # 🎯 多重ChromeDriver策略，确保最大兼容性
                    driver = None
                    
                    # 策略1：优先使用项目内置ChromeDriver（最佳兼容性）
                    try:
                        import platform
                        if platform.system() == "Windows":
                            builtin_driver_path = "drivers/chromedriver.exe"
                        else:
                            builtin_driver_path = "drivers/chromedriver"
                        
                        if os.path.exists(builtin_driver_path):
                            self.logger.info("🎯 使用项目内置ChromeDriver（最佳兼容性）...")
                            service = Service(builtin_driver_path)
                            driver = webdriver.Chrome(service=service, options=options)
                            self.logger.info("✅ 内置ChromeDriver使用成功")
                        else:
                            raise Exception("内置ChromeDriver不存在")
                            
                    except Exception as builtin_error:
                        self.logger.warning(f"内置ChromeDriver失败: {builtin_error}")
                        
                        # 策略2：使用系统ChromeDriver
                        try:
                            self.logger.info("🔧 回退到系统ChromeDriver...")
                            driver = webdriver.Chrome(options=options)
                            self.logger.info("✅ 系统ChromeDriver使用成功")
                        except Exception as system_error:
                            self.logger.warning(f"系统ChromeDriver失败: {system_error}")
                            
                            # 策略3：仅在前两种都失败时才尝试自动下载
                            try:
                                self.logger.info("📥 最后尝试：下载兼容的ChromeDriver...")
                                
                                # 检查WebDriver Manager是否可用
                                if not _WEBDRIVER_MANAGER_AVAILABLE:
                                    raise Exception("webdriver_manager不可用")
                                
                                # 使用简化的ChromeDriverManager配置
                                chrome_driver_path = ChromeDriverManager().install()
                                
                                service = Service(chrome_driver_path)
                                driver = webdriver.Chrome(service=service, options=options)
                                self.logger.info("✅ ChromeDriver自动下载成功")
                                
                            except Exception as download_error:
                                self.logger.error(f"ChromeDriver自动下载也失败: {download_error}")
                                raise Exception(f"所有ChromeDriver方案都失败: 内置({builtin_error}) | 系统({system_error}) | 下载({download_error})")
            else:
                # 备用检测方案 - 也使用缓存避免重复检测
                self.logger.warning("智能检测未找到Chrome，使用备用方案")
                if self._chrome_path_cache is None:
                    chrome_path = self._fallback_chrome_detection()
                    if chrome_path:
                        self._chrome_path_cache = chrome_path
                        self.logger.info(f"🔧 备用检测找到Chrome浏览器: {chrome_path}")
                        options.binary_location = chrome_path
                    else:
                        self.logger.error("❌ 未找到可用的Chrome浏览器")
                        raise Exception("未找到Chrome浏览器，请安装Chrome或确保ms-playwright目录存在")
                else:
                    chrome_path = self._chrome_path_cache
                    self.logger.info(f"🔧 使用缓存的Chrome浏览器: {chrome_path}")
                    options.binary_location = chrome_path
                
                # 非ms-playwright浏览器，使用标准ChromeDriver策略
                # 🎯 多重ChromeDriver策略，确保最大兼容性
                driver = None
                
                # 策略1：优先使用项目内置ChromeDriver（最佳兼容性）
                try:
                    import platform
                    if platform.system() == "Windows":
                        builtin_driver_path = "drivers/chromedriver.exe"
                    else:
                        builtin_driver_path = "drivers/chromedriver"
                    
                    if os.path.exists(builtin_driver_path):
                        self.logger.info("🎯 使用项目内置ChromeDriver（最佳兼容性）...")
                        service = Service(builtin_driver_path)
                        driver = webdriver.Chrome(service=service, options=options)
                        self.logger.info("✅ 内置ChromeDriver使用成功")
                    else:
                        raise Exception("内置ChromeDriver不存在")
                        
                except Exception as builtin_error:
                    self.logger.warning(f"内置ChromeDriver失败: {builtin_error}")
                    
                    # 策略2：使用系统ChromeDriver
                    try:
                        self.logger.info("🔧 回退到系统ChromeDriver...")
                        driver = webdriver.Chrome(options=options)
                        self.logger.info("✅ 系统ChromeDriver使用成功")
                    except Exception as system_error:
                        self.logger.warning(f"系统ChromeDriver失败: {system_error}")
                        
                        # 策略3：仅在前两种都失败时才尝试自动下载
                        try:
                            self.logger.info("📥 最后尝试：下载兼容的ChromeDriver...")
                            
                            # 检查WebDriver Manager是否可用
                            if not _WEBDRIVER_MANAGER_AVAILABLE:
                                raise Exception("webdriver_manager不可用")
                            
                            # 使用简化的ChromeDriverManager配置
                            chrome_driver_path = ChromeDriverManager().install()
                            
                            service = Service(chrome_driver_path)
                            driver = webdriver.Chrome(service=service, options=options)
                            self.logger.info("✅ ChromeDriver自动下载成功")
                            
                        except Exception as download_error:
                            self.logger.error(f"ChromeDriver自动下载也失败: {download_error}")
                            raise Exception(f"所有ChromeDriver方案都失败: 内置({builtin_error}) | 系统({system_error}) | 下载({download_error})")
                
        except Exception as browser_error:
            self.logger.error(f"浏览器创建失败: {browser_error}")
            self.logger.error(f"浏览器创建错误类型: {type(browser_error).__name__}")
            import traceback
            self.logger.error(f"浏览器创建错误堆栈: {traceback.format_exc()}")
            
            # 最后的兜底尝试
            self.logger.warning("🔄 尝试最后的兜底方案...")
            try:
                # 为兜底方案使用简化配置
                self.logger.info("🔧 兜底方案：使用最基础的Chrome配置...")
                driver = webdriver.Chrome(options=options)
                self.logger.warning("⚠️ 兜底方案成功，但可能不稳定")
            except Exception as final_error:
                self.logger.error(f"兜底方案也失败: {final_error}")
                self.logger.error(f"兜底错误类型: {type(final_error).__name__}")
                self.logger.error(f"兜底错误堆栈: {traceback.format_exc()}")
                raise Exception(f"无法创建Chrome浏览器实例: {final_error}")
        
        # 超时配置
        driver.set_page_load_timeout(15)  # 15秒超时
        driver.implicitly_wait(3)  # 隐式等待3秒
        
        # 🎯 确保浏览器窗口可见并处理启动URL
        try:
            # 🎯 修复：增大窗口尺寸，确保B站上传页面的按钮都能正常显示
            driver.set_window_size(1280, 950)  # 增加高度到950，确保确定按钮可见
            driver.set_window_position(100, 50)
            self.logger.info("✅ 浏览器窗口已设置为合适大小 (1280x950)")
            
            # 使用JavaScript确保窗口获得焦点
            driver.execute_script("window.focus();")
            
            # 🎯 如果指定了启动URL，立即导航（优化版本）
            if should_navigate_on_start and start_url:
                try:
                    self.logger.info(f"🌐 正在导航到启动页面: {start_url}")
                    driver.get(start_url)
                    time.sleep(2)  # 短暂等待页面开始加载
                    self.logger.info("✅ 启动页面导航成功")
                except Exception as nav_error:
                    self.logger.warning(f"启动页面导航失败: {nav_error}")
            
            # 只设置窗口焦点，保持设定的窗口大小
            try:
                driver.execute_script("""
                    window.focus();
                    console.log('浏览器窗口已获得焦点');
                """)
                self.logger.info("✅ 浏览器窗口已获得焦点")
            except Exception as focus_error:
                self.logger.warning(f"窗口焦点设置失败（不影响使用）: {focus_error}")
                
        except Exception as window_error:
            self.logger.warning(f"窗口可见性设置失败（不影响功能）: {window_error}")
        
        # 🧪 验证浏览器实例是否正常工作
        try:
            self.logger.info("🧪 验证浏览器实例...")
            current_url = driver.current_url
            self.logger.info(f"✅ 浏览器验证成功，当前URL: {current_url}")
        except Exception as verify_error:
            self.logger.error(f"⚠️ 浏览器验证失败: {verify_error}")
            # 继续执行，不要因为验证失败而中断
        
        self.drivers.append(driver)
        return driver
    
    def close_driver(self, driver, account_name: str = None):
        """关闭浏览器并释放端口 - 线程安全版本"""
        try:
            if hasattr(driver, 'quit'):
                if driver in self.drivers:
                    self.drivers.remove(driver)
                driver.quit()
                
                # 🎯 线程安全的端口释放
                if account_name:
                    with self._port_lock:
                        if account_name in self.account_ports:
                            released_port = self.account_ports.pop(account_name)
                            self.logger.info(f"🎯 释放端口: {account_name} -> {released_port}")
                    
        except Exception as e:
            self.logger.error(f"关闭浏览器失败: {e}")
    
    def cleanup_all(self):
        """🔧 强化的资源清理机制 - 确保资源正确释放"""
        if self.drivers:
            self.logger.info(f"🔧 开始强化清理 {len(self.drivers)} 个浏览器实例")
            
            # 🔧 强化清理：更积极的资源释放策略
            for driver in self.drivers[:]:
                try:
                    if hasattr(driver, 'quit'):
                        driver.quit()
                        # 🔧 给浏览器更多时间清理资源
                        import time
                        time.sleep(0.5)
                        self.logger.debug("✅ 浏览器实例已清理")
                except Exception as e:
                    self.logger.warning(f"⚠️ 浏览器清理警告: {e}")
                    # 🔧 即使清理失败也要从列表中移除
                    pass
            
            # 清空列表
            self.drivers.clear()
            
            # 🔧 强制释放所有端口资源
            with self._port_lock:
                if self.account_ports:
                    self.logger.info(f"🔧 释放 {len(self.account_ports)} 个端口资源")
                    self.account_ports.clear()
            
            # 🔧 强制垃圾回收
            import gc
            gc.collect()
            
            self.logger.info("✅ 强化资源清理完成")
        else:
            self.logger.debug("🔧 无需清理浏览器实例")
    
    def setup_periodic_cleanup(self):
        """🔧 新增：设置定期资源清理（每30分钟）"""
        try:
            import threading
            import time
            
            def periodic_cleanup():
                while True:
                    time.sleep(30 * 60)  # 30分钟
                    self._periodic_resource_cleanup()
            
            cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
            cleanup_thread.start()
            
            self.logger.info("🔧 定期资源清理已启动 (30分钟间隔)")
            
        except Exception as e:
            self.logger.warning(f"⚠️ 定期资源清理启动失败: {e}")
    
    def _periodic_resource_cleanup(self):
        """🔧 新增：定期资源清理"""
        try:
            import gc
            import psutil
            
            # 检查内存使用率
            memory_percent = psutil.virtual_memory().percent
            
            if memory_percent > 80:
                self.logger.warning(f"⚠️ 内存使用率过高: {memory_percent}%，执行强制清理")
                
                # 强制垃圾回收
                gc.collect()
                
                # 检查是否有僵尸浏览器进程
                active_drivers = len(self.drivers)
                if active_drivers > 10:  # 如果浏览器实例过多
                    self.logger.warning(f"⚠️ 浏览器实例过多: {active_drivers}，执行清理")
                    self.cleanup_all()
                
                # 再次检查内存
                new_memory_percent = psutil.virtual_memory().percent
                self.logger.info(f"🔧 清理后内存使用率: {memory_percent}% -> {new_memory_percent}%")
            else:
                # 常规清理
                gc.collect()
                self.logger.debug(f"🔧 常规清理完成，内存使用率: {memory_percent}%")
                
        except Exception as e:
            self.logger.error(f"❌ 定期资源清理失败: {e}")

    def show_port_allocation_info(self):
        """显示端口分配信息 - 便于调试"""
        self.logger.info("🎯 端口分配策略说明:")
        self.logger.info("   📋 全局浏览器检测: 固定端口 9301")
        self.logger.info("   📋 账号浏览器: 9311 + 账号在列表中的序号")
        self.logger.info("   📋 示例: 测试1->9311, 测试2->9312, 测试3->9313")
        
        if self.account_ports:
            self.logger.info("🎯 当前端口分配:")
            for account, port in self.account_ports.items():
                if self._account_manager:
                    all_accounts = self._account_manager.get_all_accounts()
                    if account in all_accounts:
                        sequence = all_accounts.index(account) + 1
                        self.logger.info(f"   📋 {account} (序号{sequence}): {port}")
                    else:
                        self.logger.info(f"   📋 {account}: {port}")
                else:
                    self.logger.info(f"   📋 {account}: {port}")
        else:
            self.logger.info("🎯 当前无端口分配")

class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.logger = get_logger()
        self._ensure_files()
        # self.cipher = self._load_key()  # 🎯 禁用加密，改为明文存储
    
    def _ensure_files(self):
        """确保文件存在 - SQLite版本"""
        # 确保配置文件存在
        if not os.path.exists(Config.CONFIG_FILE):
            with open(Config.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)
        
        # 确保数据库存在（由DatabaseManager自动创建）
        try:
            from database.database_manager import db_manager
            # 数据库连接会自动创建表结构
            db_manager.get_all_accounts_cached()
        except Exception as e:
            self.logger.warning(f"数据库初始化检查失败: {e}")
        
        # 确保目录存在
        for dir_path in [Config.VIDEOS_DIR, Config.LOGS_DIR]:
            os.makedirs(dir_path, exist_ok=True)
    
    # def _load_key(self) -> Fernet:
    #     """加载或创建加密密钥 - 已移除"""
    #     # 🎯 不再使用加密功能
    #     pass
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置"""
        try:
            with open(Config.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置
                for key, value in Config.DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except:
            return Config.DEFAULT_CONFIG.copy()
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """保存配置 - 包含数据清理"""
        try:
            # 🎯 保存前清理数据，去除\n等异常字符
            from core.config import DataCleaner
            cleaned_config = DataCleaner.clean_config_data(config)
            
            # 记录清理效果
            if cleaned_config != config:
                self.logger.info("配置数据已清理，去除异常字符")
            
            with open(Config.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cleaned_config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            return False
    
    def load_accounts(self) -> Dict[str, Any]:
        """加载账号 - SQLite版本（已废弃JSON）"""
        # ❌ JSON模式已废弃，此方法已迁移到数据库
        self.logger.warning("load_accounts方法已废弃，账号数据已迁移到SQLite数据库")
        return {}
    
    def save_accounts(self, accounts: Dict[str, Any]) -> bool:
        """保存账号 - SQLite版本（已废弃JSON）"""
        # ❌ JSON模式已废弃，此方法已迁移到数据库
        self.logger.warning("save_accounts方法已废弃，账号数据已迁移到SQLite数据库")
        return True  # 返回True保持兼容性

class AccountManager:
    """账号管理器 - SQLite增强版"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.browser_manager = BrowserManager(self)  # 🎯 传入self引用
        self.logger = get_logger()
        self.fingerprint_validator = FingerprintValidator()
        
        # 🚀 SQLite模式：使用数据库适配器
        self.use_database = True  # 可配置，便于测试和回滚
        self.accounts: Dict[str, Account] = {}
        
        # 初始化数据库适配器
        try:
            from database.database_adapter import database_account_manager
            self.db_manager = database_account_manager
            self.db_manager.set_logger(self.logger)
            self.logger.info("🗄️ 数据库模式已启用")
        except Exception as e:
            self.logger.warning(f"数据库模式启用失败，回退到JSON模式: {e}")
            self.use_database = False
        
        self.load_accounts()
    
    def load_accounts(self):
        """加载账号 - 支持数据库和JSON两种模式"""
        if self.use_database and hasattr(self, 'db_manager'):
            try:
                # 🚀 数据库模式：从SQLite加载
                self.db_manager.load_accounts()
                all_usernames = self.db_manager.get_all_accounts()
                
                # 创建Account对象缓存（按需加载）
                self.accounts.clear()
                for username in all_usernames:
                    db_account = self.db_manager.get_account(username)
                    if db_account:
                        # 将DatabaseAccount包装成传统Account对象
                        account = Account(username, db_account.to_dict())
                        # 保持浏览器实例引用
                        if hasattr(db_account, '_browser_instance'):
                            account.browser_instance = db_account._browser_instance
                        self.accounts[username] = account
                
                self.logger.info(f"📊 从数据库加载了 {len(self.accounts)} 个账号")
                return
            except Exception as e:
                self.logger.error(f"数据库加载失败，回退到JSON模式: {e}")
                self.use_database = False
        
        # 🔄 JSON模式：传统加载方式
        data = self.config_manager.load_accounts()
        self.accounts.clear()
        for username, account_data in data.items():
            self.accounts[username] = Account(username, account_data)
        self.logger.info(f"📁 从JSON加载了 {len(self.accounts)} 个账号")
    
    def save_accounts(self) -> bool:
        """保存账号 - 支持数据库和JSON两种模式"""
        if self.use_database and hasattr(self, 'db_manager'):
            try:
                # 🚀 数据库模式：批量更新到SQLite
                account_updates = []
                for username, account in self.accounts.items():
                    account_data = account.to_dict()
                    
                    # 准备数据库更新格式
                    update_data = {
                        'username': username,
                        'status': account_data.get('status', 'inactive'),
                        'cookies': json.dumps(account_data.get('cookies', [])),
                        'fingerprint': json.dumps(account_data.get('fingerprint', {})),
                        'devtools_port': account_data.get('devtools_port'),
                        'last_login': account_data.get('last_login', 0),
                        'notes': account_data.get('notes', '')
                    }
                    account_updates.append(update_data)
                
                # 批量更新到数据库
                from database.database_manager import db_manager
                updated_count = db_manager.batch_update_accounts(account_updates)
                
                if updated_count > 0:
                    self.logger.info(f"✅ 数据库批量更新成功：{updated_count} 个账号")
                    return True
                else:
                    self.logger.warning("⚠️ 数据库批量更新：0个账号被更新")
                    return True  # 可能没有变化，也算成功
                    
            except Exception as e:
                self.logger.error(f"数据库保存失败，回退到JSON模式: {e}")
                self.use_database = False
        
        # 🔄 JSON模式：传统保存方式
        try:
            data = {}
            for username, account in self.accounts.items():
                account_data = account.to_dict()
                self.logger.debug(f"保存账号状态: {username} -> {account_data['status']}")
                data[username] = account_data
            
            success = self.config_manager.save_accounts(data)
            if success:
                self.logger.info(f"✅ JSON保存成功：{len(data)} 个账号")
            else:
                self.logger.error("❌ JSON保存失败")
            return success
        except Exception as e:
            self.logger.error(f"❌ JSON保存出错: {e}")
            return False
    
    def add_account(self, username: str) -> bool:
        """添加账号 - 支持数据库和JSON两种模式"""
        if username in self.accounts:
            return False
        
        # 数据库模式：直接添加到数据库
        if self.use_database and hasattr(self, 'db_manager'):
            try:
                success = self.db_manager.add_account(username)
                if success:
                    # 创建Account对象并添加到内存缓存
                    account = Account(username)
                    
                    # 生成初始指纹
                    initial_fingerprint = self._generate_fingerprint(username)
                    optimized_fingerprint = self.fingerprint_validator.optimize_fingerprint(username, initial_fingerprint)
                    account.fingerprint = optimized_fingerprint
                    
                    # 更新数据库中的指纹信息
                    from database.database_manager import db_manager
                    db_manager.batch_update_accounts([{
                        'username': username,
                        'fingerprint': json.dumps(optimized_fingerprint)
                    }])
                    
                    # 添加到内存缓存
                    self.accounts[username] = account
                    
                    # 显示指纹安全性评估
                    passed, results = self.fingerprint_validator.validate_fingerprint(username, optimized_fingerprint)
                    if passed:
                        self.logger.info(f"📊 账号 {username} 添加成功，指纹安全评分: {results['overall_score']}/100")
                    else:
                        self.logger.warning(f"⚠️ 账号 {username} 添加成功，但指纹风险较高，评分: {results['overall_score']}/100")
                    
                    return True
                return False
            except Exception as e:
                self.logger.error(f"数据库添加账号失败，回退到JSON模式: {e}")
                self.use_database = False
        
        # JSON模式：传统添加方式
        account = Account(username)
        
        # 生成初始指纹
        initial_fingerprint = self._generate_fingerprint(username)
        
        # 自动验证和优化指纹
        self.logger.info(f"为账号 {username} 自动验证和优化指纹...")
        optimized_fingerprint = self.fingerprint_validator.optimize_fingerprint(username, initial_fingerprint)
        
        account.fingerprint = optimized_fingerprint
        self.accounts[username] = account
        
        # 显示指纹安全性评估
        passed, results = self.fingerprint_validator.validate_fingerprint(username, optimized_fingerprint)
        if passed:
            self.logger.info(f"📁 账号 {username} 添加成功，指纹安全评分: {results['overall_score']}/100")
        else:
            self.logger.warning(f"⚠️ 账号 {username} 添加成功，但指纹风险较高，评分: {results['overall_score']}/100")
        
        return self.save_accounts()
    
    def remove_account(self, username: str) -> bool:
        """删除账号 - 支持数据库和JSON两种模式"""
        if username not in self.accounts:
            return False
        
        # 数据库模式：从数据库删除
        if self.use_database and hasattr(self, 'db_manager'):
            try:
                success = self.db_manager.remove_account(username)
                if success:
                    # 从内存缓存中删除
                    del self.accounts[username]
                    self.logger.info(f"📊 账号 {username} 已从数据库删除")
                    return True
                return False
            except Exception as e:
                self.logger.error(f"数据库删除账号失败，回退到JSON模式: {e}")
                self.use_database = False
        
        # JSON模式：传统删除方式
        del self.accounts[username]
        return self.save_accounts()
    
    def get_account(self, username: str) -> Optional[Account]:
        """获取账号 - 兼容dict和Account对象"""
        from .account_adapter import get_account_safely
        
        raw_account = self.accounts.get(username)
        return get_account_safely(raw_account, self, username)
    
    def get_all_accounts(self) -> List[str]:
        """获取所有账号名 - 支持数据库和JSON两种模式"""
        if self.use_database and hasattr(self, 'db_manager'):
            try:
                # 🚀 数据库模式：直接从数据库获取，性能更好
                return self.db_manager.get_all_accounts()
            except Exception as e:
                self.logger.error(f"数据库获取账号列表失败，回退到内存模式: {e}")
                self.use_database = False
        
        # 🔄 内存模式：从内存缓存获取
        return list(self.accounts.keys())
    
    def get_active_accounts(self) -> List[str]:
        """获取活跃账号 - 支持数据库和JSON两种模式"""
        if self.use_database and hasattr(self, 'db_manager'):
            try:
                # 🚀 数据库模式：直接从数据库获取，性能更好
                return self.db_manager.get_active_accounts()
            except Exception as e:
                self.logger.error(f"数据库获取活跃账号失败，回退到内存模式: {e}")
                self.use_database = False
        
        # 🔄 内存模式：遍历内存缓存
        from .account_adapter import get_account_status_safely
        
        result = []
        for username, account_data in self.accounts.items():
            if get_account_status_safely(account_data) == 'active':
                result.append(username)
        return result
    
    def get_accounts_progress_batch(self, usernames: List[str], target_count: int = 1) -> Dict[str, Tuple[str, bool, int]]:
        """批量获取账号进度 - 数据库优化版本"""
        if self.use_database and hasattr(self, 'db_manager'):
            try:
                # 🚀 数据库模式：使用高性能批量查询
                return self.db_manager.get_accounts_progress_batch(usernames, target_count)
            except Exception as e:
                self.logger.error(f"数据库批量获取进度失败: {e}")
                self.use_database = False
        
        # 🔄 回退到单个查询模式（兼容性）
        result = {}
        for username in usernames:
            try:
                # 这里可以集成现有的进度查询逻辑
                result[username] = ("0/1 🔄 进行中", False, 0)  # 简化版本
            except Exception as e:
                result[username] = ("获取失败", False, 0)
        
        return result
    
    def login_account(self, username: str) -> bool:
        """登录账号"""
        account = self.get_account(username)
        if not account:
            return False
        
        self.logger.info(f"开始登录账号: {username}")
        
        # 🚨 添加关键检查点
        self.logger.info(f"🚨 STEP 1: 登录方法开始执行")
        
        driver = None
        
        # 🚨 检查账号指纹是否存在
        self.logger.info(f"🚨 STEP 2: 检查账号指纹...")
        if hasattr(account, 'fingerprint') and account.fingerprint:
            self.logger.info(f"🚨 账号指纹存在: {len(str(account.fingerprint))} 字符")
        else:
            self.logger.error(f"🚨 账号指纹缺失！")
        
        self.logger.info(f"🚨 STEP 3: 准备进入try块...")
        
        try:
            # 🎯 使用固定指纹创建浏览器，直接启动到登录页面
            self.logger.info(f"🚨 STEP 4: 开始创建浏览器实例...")
            self.logger.info(f"🔧 正在为账号 {username} 创建浏览器实例...")
            
            try:
                # 🔧 获取Chrome路径用于诊断信息
                chrome_path = self.browser_manager._get_best_chrome_path()
                if chrome_path:
                    self.logger.info(f"🔧 使用Chrome浏览器: {chrome_path}")
                
                driver = self.browser_manager.create_driver(
                    fingerprint=account.fingerprint,
                    headless=False,  # 登录需要用户交互，不能无头模式
                    account_name=username,  # 传递账号名，分配专属端口
                    start_url="https://passport.bilibili.com/login"  # 🚀 直接启动到登录页面
                )
                
                # 🚨 强制日志：确认浏览器创建成功
                self.logger.info(f"✅ 浏览器实例创建成功: {username}")
                self.logger.info(f"🚨 DRIVER对象类型: {type(driver)}")
                
                # 🎯 立即保存浏览器实例和端口信息，并同步状态
                account.browser_instance = driver
                account._browser_ready = True
                
                # 提取DevTools端口信息
                devtools_port = self._extract_devtools_port(driver, username)
                if devtools_port:
                    old_port = getattr(account, 'devtools_port', None)
                    account.devtools_port = devtools_port
                    self.logger.info(f"🔗 绑定账号端口: {username} -> {devtools_port}")
                    
                    # 立即更新浏览器状态为活跃
                    try:
                        from core.browser_status_monitor import get_browser_status_monitor
                        browser_monitor = get_browser_status_monitor()
                        browser_monitor.bind_account_port(username, devtools_port)
                        
                        # 🎯 立即通知界面状态变化 - 这是用户期望的！
                        self.logger.info(f"🔄 端口绑定后状态: {username} -> 活跃")
                        browser_monitor.notify_status_change(username, True)
                        self.logger.info(f"🔗 已更新浏览器监控器绑定: {username} -> {devtools_port}")
                    except Exception as e:
                        self.logger.warning(f"更新浏览器监控器绑定失败: {e}")
                
                # 🔍 测试浏览器响应性
                try:
                    test_url = driver.current_url
                    self.logger.info(f"🚨 浏览器响应测试通过，当前URL: {test_url}")
                except Exception as response_error:
                    self.logger.error(f"🚨 浏览器响应测试失败: {response_error}")
                    raise Exception(f"浏览器创建后无法响应: {response_error}")
                
                # 🔍 详细的页面导航诊断
                self.logger.info(f"🔍 开始页面导航诊断...")
                try:
                    current_url = driver.current_url
                    page_title = driver.title
                    self.logger.info(f"📍 浏览器启动后当前URL: {current_url}")
                    self.logger.info(f"📋 浏览器启动后页面标题: {page_title}")
                    
                    # 检查是否已经在登录页面
                    if "passport.bilibili.com" in current_url and "login" in current_url:
                        self.logger.info(f"✅ 浏览器已直接启动到登录页面")
                    else:
                        self.logger.warning(f"⚠️ 浏览器未启动到登录页面，开始手动导航...")
                        
                        # 手动导航到登录页面
                        login_url = "https://passport.bilibili.com/login"
                        self.logger.info(f"🌐 手动导航到登录页面: {login_url}")
                        driver.get(login_url)
                        
                        # 等待页面加载
                        time.sleep(3)
                        
                        # 验证导航结果
                        new_url = driver.current_url
                        new_title = driver.title
                        self.logger.info(f"📍 手动导航后URL: {new_url}")
                        self.logger.info(f"📋 手动导航后标题: {new_title}")
                        
                        if "passport.bilibili.com" in new_url:
                            self.logger.info(f"✅ 手动导航到登录页面成功")
                        else:
                            self.logger.error(f"❌ 手动导航仍然失败，可能存在网络问题")
                            
                            # 尝试备用登录URL
                            backup_urls = [
                                "https://www.bilibili.com",
                                "https://space.bilibili.com",
                                "https://passport.bilibili.com"
                            ]
                            
                            for backup_url in backup_urls:
                                try:
                                    self.logger.info(f"🔄 尝试访问备用URL: {backup_url}")
                                    driver.get(backup_url)
                                    time.sleep(2)
                                    result_url = driver.current_url
                                    self.logger.info(f"📍 备用URL访问结果: {result_url}")
                                    
                                    if "bilibili.com" in result_url:
                                        self.logger.info(f"✅ 成功访问B站，网络连接正常")
                                        # 再次尝试登录页面
                                        driver.get("https://passport.bilibili.com/login")
                                        time.sleep(3)
                                        final_url = driver.current_url
                                        self.logger.info(f"📍 最终登录页面URL: {final_url}")
                                        break
                                except Exception as backup_error:
                                    self.logger.warning(f"备用URL访问失败: {backup_url} - {backup_error}")
                                    continue
                    
                    self.logger.info(f"🔍 页面导航诊断完成")
                    
                except Exception as nav_diag_error:
                    self.logger.error(f"❌ 页面导航诊断失败: {nav_diag_error}")
                    self.logger.error(f"   这可能表明浏览器实例不稳定或网络连接有问题")
                    
            except Exception as browser_error:
                self.logger.error(f"❌ 浏览器相关操作失败: {username}")
                self.logger.error(f"🚨 错误发生位置: {type(browser_error).__name__}")
                self.logger.error(f"🚨 错误详情: {browser_error}")
                import traceback
                self.logger.error(f"🚨 完整错误堆栈: {traceback.format_exc()}")
                
                # 判断是浏览器创建失败还是后续操作失败
                if 'driver' in locals() and driver:
                    self.logger.error(f"🚨 浏览器已创建但后续操作失败！")
                    try:
                        current_url = driver.current_url
                        self.logger.error(f"🚨 失败时浏览器URL: {current_url}")
                    except Exception as url_error:
                        self.logger.error(f"🚨 无法获取失败时浏览器URL: {url_error}")
                else:
                    self.logger.error(f"🚨 浏览器创建阶段就失败了！")
                
                # 记录浏览器创建失败的详细信息
                try:
                    chrome_path = self.browser_manager._get_best_chrome_path()
                    self.logger.error(f"   Chrome路径: {chrome_path}")
                    if chrome_path and os.path.exists(chrome_path):
                        self.logger.error(f"   Chrome文件存在: 是")
                        file_size = os.path.getsize(chrome_path) / (1024 * 1024)
                        self.logger.error(f"   Chrome文件大小: {file_size:.1f} MB")
                    else:
                        self.logger.error(f"   Chrome文件存在: 否")
                except Exception as path_error:
                    self.logger.error(f"   Chrome路径检查失败: {path_error}")
                
                raise Exception(f"浏览器操作失败: {browser_error}")
            
            # 🎯 浏览器应该已经导航到登录页面，验证加载状态
            self.logger.info(f"验证登录页面加载状态...")
            
            # 等待页面完全加载
            time.sleep(3)
            
            try:
                current_url = driver.current_url
                page_title = driver.title
                
                self.logger.info(f"✅ 登录页面已加载!")
                self.logger.info(f"📍 当前URL: {current_url}")
                self.logger.info(f"📋 页面标题: {page_title}")
                
                # 验证是否真的是登录页面
                if "login" not in current_url.lower() and "passport" not in current_url.lower():
                    self.logger.warning("⚠️ 页面可能未正确加载，尝试重新导航...")
                    driver.get("https://passport.bilibili.com/login")
                    time.sleep(3)
                    self.logger.info("✅ 重新导航到登录页面完成")
                
            except Exception as page_error:
                self.logger.error(f"页面验证失败: {page_error}")
                # 回退到传统导航方式
                try:
                    self.logger.info("🔄 使用传统导航方式...")
                    driver.get("https://passport.bilibili.com/login")
                    time.sleep(3)
                    self.logger.info("✅ 传统导航成功")
                except Exception as fallback_error:
                    self.logger.error(f"传统导航也失败: {fallback_error}")
                    raise Exception(f"无法访问登录页面: {fallback_error}")
            
            # 如果已有cookies，尝试恢复登录状态
            if account.cookies:
                self.logger.info(f"尝试恢复登录状态...")
                for cookie in account.cookies:
                    try:
                        driver.add_cookie(cookie)
                    except:
                        pass
                
                # 刷新页面检查登录状态
                driver.refresh()
                time.sleep(3)
                
                # 检查是否已登录
                if self._check_login_status(driver):
                    self.logger.info(f"账号 {username} 已登录，直接返回")
                    account.status = 'active'
                    account.last_login = int(time.time())
                    
                    # ✅ 重要修复：即使已登录也要更新浏览器实例和DevTools端口
                    account.browser_instance = driver
                    account._browser_ready = True
                    
                    # 🎯 关键：提取并更新DevTools端口信息
                    devtools_port = self._extract_devtools_port(driver, username)
                    if devtools_port:
                        old_port = getattr(account, 'devtools_port', None)
                        account.devtools_port = devtools_port
                        self.logger.info(f"🔗 更新DevTools端口: {username} {old_port} -> {devtools_port}")
                        
                        # 立即绑定到专用浏览器状态监控器
                        try:
                            from core.browser_status_monitor import get_browser_status_monitor
                            browser_monitor = get_browser_status_monitor()
                            browser_monitor.bind_account_port(username, devtools_port)
                            self.logger.info(f"🔗 已更新浏览器监控器绑定: {username} -> {devtools_port}")
                        except Exception as e:
                            self.logger.warning(f"更新浏览器监控器绑定失败: {e}")
                    else:
                        self.logger.warning(f"⚠️ 无法获取DevTools端口: {username}")
                    
                    self.save_accounts()
                    return True
            
            # 等待用户手动登录
            self.logger.info(f"等待用户登录...")
            
            # 设置最大等待时间（10分钟）
            max_wait_time = 600
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                try:
                    # 检查用户是否已完成登录
                    if self._check_login_status(driver):
                        self.logger.info(f"检测到登录成功")
                        
                        # 保存cookies
                        account.cookies = driver.get_cookies()
                        account.status = 'active'
                        account.last_login = int(time.time())
                        
                        # ✅ 关键修复：保存浏览器实例到账号对象
                        account.browser_instance = driver
                        account._browser_ready = True
                        
                        # 🎯 新增：保存浏览器的DevTools端口信息
                        devtools_port = self._extract_devtools_port(driver, username)
                        if devtools_port:
                            account.devtools_port = devtools_port
                            self.logger.info(f"🔗 保存DevTools端口: {username} -> {account.devtools_port}")
                            
                            # 立即绑定到专用浏览器状态监控器
                            try:
                                from core.browser_status_monitor import get_browser_status_monitor
                                browser_monitor = get_browser_status_monitor()
                                browser_monitor.bind_account_port(username, devtools_port)
                                self.logger.info(f"🔗 已绑定到浏览器监控器: {username} -> {devtools_port}")
                            except Exception as e:
                                self.logger.warning(f"绑定浏览器监控器失败: {e}")
                            
                        else:
                            self.logger.warning(f"⚠️ 无法获取DevTools端口: {username}")
                        
                        # 🎯 修复：保存账号信息时确保不影响其他账号
                        if self.save_accounts():
                            self.logger.info(f"✅ 账号 {username} 登录成功，状态已保存")
                            
                            # 🔍 验证保存结果
                            from .account_adapter import get_account_status_safely
                            
                            saved_account = self.get_account(username)
                            if saved_account:
                                account_status = get_account_status_safely(saved_account)
                                self.logger.info(f"🔍 调试：获取到的状态值: {account_status}, 类型: {type(account_status)}")
                                
                                if account_status == 'active':
                                    self.logger.info(f"✅ 验证：账号 {username} 状态正确保存为 active")
                                    return True
                                else:
                                    # 兼容问题：重新加载账号数据
                                    self.load_accounts()
                                    new_saved_account = self.get_account(username)
                                    if new_saved_account:
                                        new_status = get_account_status_safely(new_saved_account)
                                        if new_status == 'active':
                                            self.logger.info(f"✅ 验证（重新加载后）：账号 {username} 状态正确保存为 active")
                                            return True
                                    
                                    self.logger.error(f"❌ 验证失败：账号 {username} 状态为 {account_status} 而不是 active")
                                    return False
                            else:
                                self.logger.error(f"❌ 验证失败：无法获取账号 {username}")
                                return False
                        else:
                            self.logger.error(f"❌ 保存账号状态失败")
                            return False
                    
                    # 检查浏览器是否被关闭
                    try:
                        driver.current_url
                    except:
                        self.logger.info(f"浏览器被关闭，取消登录")
                        return False
                    
                    time.sleep(2)
                    
                except Exception as e:
                    self.logger.error(f"登录检查过程出错: {e}")
                    time.sleep(2)
            
            self.logger.warning(f"登录超时")
            return False
            
        except Exception as e:
            self.logger.error(f"登录过程详细错误: {e}")
            self.logger.error(f"错误类型: {type(e).__name__}")
            import traceback
            self.logger.error(f"完整错误堆栈: {traceback.format_exc()}")
            
            # 记录更详细的诊断信息
            self.logger.error(f"🔍 登录失败诊断信息:")
            self.logger.error(f"   - 账号: {username}")
            self.logger.error(f"   - 错误时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 检查浏览器状态
            if driver:
                try:
                    current_url = driver.current_url
                    page_title = driver.title
                    self.logger.error(f"   - 当前URL: {current_url}")
                    self.logger.error(f"   - 页面标题: {page_title}")
                except Exception as browser_error:
                    self.logger.error(f"   - 浏览器状态检查失败: {browser_error}")
            else:
                self.logger.error(f"   - 浏览器实例: 未创建")
            
            # 检查Chrome路径
            try:
                chrome_path = self.browser_manager._get_best_chrome_path()
                self.logger.error(f"   - Chrome路径: {chrome_path}")
            except Exception as chrome_error:
                self.logger.error(f"   - Chrome路径检查失败: {chrome_error}")
            
            # 确保登录失败时账号状态为inactive
            account.status = 'inactive'
            return False
        
        finally:
            # 登录完成后的浏览器处理
            if driver and account.status != 'active':
                # 只有登录失败时才关闭浏览器
                self.logger.info(f"❌ 账号 {username} 登录失败，关闭浏览器")
                try:
                    self.browser_manager.close_driver(driver)
                except:
                    pass
            elif driver and account.status == 'active':
                # 登录成功：保持浏览器开启，已保存实例到account.browser_instance
                self.logger.info(f"✅ 账号 {username} 登录成功，浏览器保持开启供监控系统使用")
    
    def _extract_devtools_port(self, driver, account_name: Optional[str] = None) -> Optional[int]:
        """从Chrome Driver中提取DevTools端口 - 极简版本"""
        # 🎯 简单的解决方案：如果有账号名，返回对应端口
        if account_name and hasattr(self, 'browser_manager'):
            return self.browser_manager._get_account_debug_port(account_name)
        return 9222
    
    def _check_login_status(self, driver) -> bool:
        """检查登录状态"""
        try:
            current_url = driver.current_url
            self.logger.debug(f"当前页面: {current_url}")
            
            # 如果还在登录页面，检查是否有登录成功的迹象
            if "passport.bilibili.com" in current_url:
                # 检查页面是否包含登录成功后的元素
                try:
                    # 检查是否有用户信息或跳转提示
                    driver.find_element("css selector", ".login-success")
                    return True
                except:
                    pass
                
                # 检查URL是否包含登录成功参数
                if "crossDomain" in current_url or "success" in current_url:
                    return True
                
                return False
            
            # 如果不在登录页面，尝试获取用户信息来确认登录状态
            try:
                # 执行JavaScript获取用户信息
                user_info = driver.execute_script("""
                    if (window.BilibiliLive && window.BilibiliLive.ANCHOR_UID) {
                        return window.BilibiliLive.ANCHOR_UID;
                    }
                    if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.isLogin) {
                        return window.__INITIAL_STATE__.isLogin;
                    }
                    if (window.DedeUserID && window.DedeUserID !== '0') {
                        return window.DedeUserID;
                    }
                    // 检查localStorage中的登录信息
                    try {
                        const userInfo = localStorage.getItem('userInfo');
                        if (userInfo && userInfo !== 'null') {
                            return JSON.parse(userInfo);
                        }
                    } catch(e) {}
                    
                    // 检查cookies中的登录信息
                    if (document.cookie.includes('DedeUserID')) {
                        return true;
                    }
                    
                    return false;
                """)
                
                if user_info and user_info != '0' and user_info != 0:
                    self.logger.info(f"检测到登录状态: {user_info}")
                    return True
                    
            except Exception as js_error:
                self.logger.debug(f"JavaScript检查失败: {js_error}")
            
            # 检查页面标题
            try:
                title = driver.title
                if "登录" not in title and "bilibili" in title.lower():
                    # 进一步检查是否有用户相关元素
                    try:
                        # 查找导航栏中的用户头像
                        driver.find_element("css selector", ".header-avatar-wrap, .bili-avatar, .user-avatar")
                        return True
                    except:
                        pass
            except:
                pass
            
            return False
            
        except Exception as e:
            self.logger.error(f"检查登录状态失败: {e}")
            return False
    
    def _generate_fingerprint(self, username: str) -> Dict[str, Any]:
        """生成浏览器指纹 - 确保同一账号永远使用相同指纹"""
        from .utils import generate_fixed_fingerprint
        
        fingerprint = generate_fixed_fingerprint(username)
        self.logger.info(f"为账号 {username} 生成固定指纹: {fingerprint['user_agent'][:50]}...")
        
        return fingerprint

    def is_browser_active(self, username: str) -> bool:
        """检查账号的浏览器是否活跃（简化版本，可以后续增强）"""
        from .account_adapter import get_account_status_safely
        
        # 这里可以添加更复杂的逻辑，比如检查浏览器最后活动时间
        # 目前简化为检查账号状态
        account = self.get_account(username)
        if not account:
            return False
        
        return get_account_status_safely(account) == 'active'
    
    def is_browser_active_simple(self, account_name: str) -> bool:
        """简化的浏览器状态检测 - 利用固定端口策略"""
        from .utils import check_port_available
        
        try:
            # 获取账号的固定端口
            port = self._get_account_debug_port(account_name)
            
            # 快速检查端口是否有浏览器在监听
            is_active = check_port_available(port, timeout=1.0)
            
            if is_active:
                self.logger.debug(f"🎯 账号 {account_name} 浏览器活跃 (端口 {port})")
            else:
                self.logger.debug(f"🎯 账号 {account_name} 浏览器未活跃 (端口 {port})")
            
            return is_active
                
        except Exception as e:
            self.logger.debug(f"🎯 账号 {account_name} 状态检测失败: {e}")
            return False

class BilibiliUploaderApp:
    """主应用类"""
    
    def __init__(self):
        self.logger = get_logger()
        self.config_manager = ConfigManager()
        self.account_manager = AccountManager(self.config_manager)
        
        # 添加browser_manager快捷访问
        self.browser_manager = self.account_manager.browser_manager
        
        self.logger.info(f"{Config.APP_NAME} v{Config.APP_VERSION} 初始化完成")
    
    def get_video_files(self, directory: str) -> List[str]:
        """获取视频文件列表"""
        video_files = []
        
        if not os.path.exists(directory):
            return video_files
        
        for file in os.listdir(directory):
            if any(file.lower().endswith(ext) for ext in Config.VIDEO_EXTENSIONS):
                video_files.append(os.path.join(directory, file))
        
        return sorted(video_files)
    
    def cleanup(self):
        """清理资源 - 极短超时版本"""
        self.account_manager.browser_manager.cleanup_all()
        self.logger.info("应用资源清理完成")
