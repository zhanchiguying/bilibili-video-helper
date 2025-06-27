#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
浏览器检测器 - 智能检测和配置Chrome浏览器
"""

import os
import platform
import subprocess
import shutil
from typing import Optional, List, Tuple
from pathlib import Path
import glob

from .logger import get_logger

class BrowserDetector:
    """浏览器检测器"""
    
    def __init__(self):
        self.logger = get_logger()
        self.system = platform.system()
        self._chrome_path_cache = None  # 🎯 全局缓存Chrome路径
        self._chrome_source_cache = None  # 🎯 缓存Chrome来源信息
        self.logger.info(f"🔍 初始化浏览器检测器，当前系统: {self.system}")
    
    def quick_check_playwright(self) -> Tuple[Optional[str], str]:
        """
        快速检查ms-playwright浏览器（参考gui_main.py项目）
        如果找到就直接返回，跳过其他检查
        """
        # 🎯 优化：减少不必要的日志输出
        
        # 获取项目根目录
        try:
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(current_file))
        except:
            project_root = os.getcwd()
        
        # 检查可能的playwright浏览器路径（使用glob模式匹配）
        if self.system == "Windows":
            possible_patterns = [
                os.path.join(project_root, "ms-playwright", "chromium-*", "chrome-win", "chrome.exe"),
                os.path.join(os.getcwd(), "ms-playwright", "chromium-*", "chrome-win", "chrome.exe"),
            ]
            
            for pattern in possible_patterns:
                matches = glob.glob(pattern)
                for chrome_path in matches:
                    if os.path.exists(chrome_path) and os.path.isfile(chrome_path):
                        if os.access(chrome_path, os.X_OK) or self.system == "Windows":
                            # 🎯 优化：只在找到时输出简洁日志
                            return chrome_path, "项目内置ms-playwright浏览器"
        
        # 🎯 优化：移除"未找到"的日志，避免混乱
        return None, "快速检查未找到"
    
    def find_chrome_browser(self) -> Tuple[Optional[str], str]:
        """
        查找Chrome浏览器
        返回: (浏览器路径, 发现来源描述)
        """
        # 1. 优先检查项目内置的ms-playwright浏览器
        playwright_path, source = self.quick_check_playwright()
        if playwright_path:
            return playwright_path, source
        
        # 2. 检查系统安装的Chrome
        system_chrome_path = self._find_system_chrome()
        if system_chrome_path:
            return system_chrome_path, "系统安装的Chrome浏览器"
        
        # 3. 检查便携版Chrome
        portable_chrome_path = self._find_portable_chrome()
        if portable_chrome_path:
            return portable_chrome_path, "便携版Chrome浏览器"
        
        # 4. 检查其他可能位置
        other_chrome_path = self._find_other_chrome()
        if other_chrome_path:
            return other_chrome_path, "其他位置的Chrome浏览器"
        
        return None, "未找到任何Chrome浏览器"
    
    def _find_playwright_chrome(self) -> Optional[str]:
        """查找项目内置的playwright浏览器"""
        self.logger.info("🔍 正在查找项目内置的ms-playwright浏览器...")
        
        # 获取项目根目录
        try:
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(current_file))
        except:
            project_root = os.getcwd()
        
        # 检查可能的playwright浏览器路径
        possible_paths = []
        
        if self.system == "Windows":
            possible_paths = [
                os.path.join(project_root, "ms-playwright", "chromium-1169", "chrome-win", "chrome.exe"),
                os.path.join(project_root, "ms-playwright", "chromium", "chrome-win", "chrome.exe"),
                os.path.join(project_root, "ms-playwright", "chromium-1115", "chrome-win", "chrome.exe"),
                os.path.join(project_root, "ms-playwright", "chromium-1064", "chrome-win", "chrome.exe"),
                # 检查当前目录下的playwright
                os.path.join(os.getcwd(), "ms-playwright", "chromium-1169", "chrome-win", "chrome.exe"),
                os.path.join(os.getcwd(), "ms-playwright", "chromium", "chrome-win", "chrome.exe"),
            ]
        elif self.system == "Darwin":  # macOS
            possible_paths = [
                os.path.join(project_root, "ms-playwright", "chromium-1169", "chrome-mac", "Chromium.app", "Contents", "MacOS", "Chromium"),
                os.path.join(project_root, "ms-playwright", "chromium", "chrome-mac", "Chromium.app", "Contents", "MacOS", "Chromium"),
            ]
        elif self.system == "Linux":
            possible_paths = [
                os.path.join(project_root, "ms-playwright", "chromium-1169", "chrome-linux", "chrome"),
                os.path.join(project_root, "ms-playwright", "chromium", "chrome-linux", "chrome"),
            ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.path.isfile(path):
                # 验证文件可执行
                if os.access(path, os.X_OK) or self.system == "Windows":
                    self.logger.info(f"✅ 找到playwright浏览器: {path}")
                    return path
                else:
                    self.logger.warning(f"⚠️ 找到playwright浏览器但无执行权限: {path}")
            else:
                self.logger.debug(f"🔍 检查路径不存在: {path}")
        
        self.logger.info("❌ 未找到项目内置的playwright浏览器")
        return None
    
    def _find_system_chrome(self) -> Optional[str]:
        """查找系统安装的Chrome"""
        self.logger.info("🔍 正在查找系统安装的Chrome浏览器...")
        
        possible_paths = []
        
        if self.system == "Windows":
            # Windows常见安装路径
            possible_paths = [
                # 用户安装
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%USERPROFILE%\AppData\Local\Google\Chrome\Application\chrome.exe"),
                # 系统安装
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                # 其他可能位置
                r"C:\Users\Public\Desktop\Google Chrome.lnk",  # 快捷方式
            ]
            
            # 尝试通过注册表查找
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                    chrome_path = winreg.QueryValue(key, "")
                    if chrome_path and os.path.exists(chrome_path):
                        possible_paths.insert(0, chrome_path)
                        self.logger.info(f"📋 从注册表找到Chrome路径: {chrome_path}")
            except Exception as e:
                self.logger.debug(f"注册表查找失败: {e}")
            
        elif self.system == "Darwin":  # macOS
            possible_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            ]
            
        elif self.system == "Linux":
            # 先尝试which命令
            try:
                result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    chrome_path = result.stdout.strip()
                    if os.path.exists(chrome_path):
                        possible_paths.insert(0, chrome_path)
                        self.logger.info(f"📋 通过which找到Chrome: {chrome_path}")
            except:
                pass
            
            possible_paths.extend([
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/opt/google/chrome/chrome",
                "/snap/bin/chromium",
            ])
        
        # 检查路径
        for path in possible_paths:
            if os.path.exists(path) and os.path.isfile(path):
                if os.access(path, os.X_OK) or self.system == "Windows":
                    self.logger.info(f"✅ 找到系统Chrome: {path}")
                    return path
                else:
                    self.logger.warning(f"⚠️ 找到Chrome但无执行权限: {path}")
        
        self.logger.info("❌ 未找到系统安装的Chrome")
        return None
    
    def _find_portable_chrome(self) -> Optional[str]:
        """查找便携版Chrome"""
        self.logger.info("🔍 正在查找便携版Chrome...")
        
        if self.system != "Windows":
            return None
        
        # 检查常见的便携版Chrome位置
        possible_dirs = [
            "C:\\PortableApps\\GoogleChromePortable\\App\\Chrome-bin",
            "D:\\PortableApps\\GoogleChromePortable\\App\\Chrome-bin",
            "E:\\PortableApps\\GoogleChromePortable\\App\\Chrome-bin",
            os.path.join(os.getcwd(), "Chrome"),
            os.path.join(os.getcwd(), "chrome-win"),
            os.path.join(os.path.dirname(os.getcwd()), "Chrome"),
        ]
        
        for dir_path in possible_dirs:
            chrome_exe = os.path.join(dir_path, "chrome.exe")
            if os.path.exists(chrome_exe):
                self.logger.info(f"✅ 找到便携版Chrome: {chrome_exe}")
                return chrome_exe
        
        self.logger.info("❌ 未找到便携版Chrome")
        return None
    
    def _find_other_chrome(self) -> Optional[str]:
        """查找其他位置的Chrome"""
        self.logger.info("🔍 正在查找其他位置的Chrome...")
        
        # 检查PATH环境变量
        chrome_names = []
        if self.system == "Windows":
            chrome_names = ["chrome.exe", "google-chrome.exe"]
        else:
            chrome_names = ["google-chrome", "chromium", "chrome"]
        
        for name in chrome_names:
            chrome_path = shutil.which(name)
            if chrome_path and os.path.exists(chrome_path):
                self.logger.info(f"✅ 在PATH中找到Chrome: {chrome_path}")
                return chrome_path
        
        self.logger.info("❌ 在其他位置未找到Chrome")
        return None
    
    def get_chrome_version(self, chrome_path: str) -> Optional[str]:
        """获取Chrome版本"""
        try:
            # Windows环境下需要特别处理编码
            if self.system == "Windows":
                # 使用系统默认编码，避免中文环境下的编码问题
                result = subprocess.run(
                    [chrome_path, "--version"], 
                    capture_output=True, 
                    text=True, 
                    timeout=5,  # 减少超时时间到5秒
                    encoding='utf-8',
                    errors='ignore'  # 忽略编码错误
                )
            else:
                result = subprocess.run(
                    [chrome_path, "--version"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10,
                    encoding='utf-8',
                    errors='ignore'
                )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                if version:  # 确保版本信息不为空
                    self.logger.info(f"📋 Chrome版本: {version}")
                    return version
                else:
                    self.logger.warning("Chrome版本信息为空")
            else:
                self.logger.warning(f"Chrome版本命令返回码: {result.returncode}")
                
        except subprocess.TimeoutExpired:
            self.logger.warning("获取Chrome版本超时")
        except Exception as e:
            self.logger.warning(f"获取Chrome版本失败: {e}")
        
        return None
    
    def verify_chrome_executable(self, chrome_path: str) -> bool:
        """验证Chrome可执行文件"""
        try:
            if not os.path.exists(chrome_path):
                self.logger.error(f"Chrome路径不存在: {chrome_path}")
                return False
            
            if not os.path.isfile(chrome_path):
                self.logger.error(f"Chrome路径不是文件: {chrome_path}")
                return False
            
            # Windows不需要检查执行权限
            if self.system != "Windows" and not os.access(chrome_path, os.X_OK):
                self.logger.error(f"Chrome文件无执行权限: {chrome_path}")
                return False
            
            # 🎯 优化：跳过版本获取，直接验证文件可用性
            # 版本获取经常超时且不必要，只要文件存在且可执行就认为可用
            return True
                
        except Exception as e:
            self.logger.error(f"Chrome验证异常: {e}")
            return False
    
    def get_best_chrome_path(self) -> Optional[str]:
        """获取最佳的Chrome路径 - 缓存版：避免重复检测"""
        # 🎯 检查缓存，避免重复检测
        if self._chrome_path_cache is not None:
            self.logger.info(f"🔧 使用缓存的Chrome浏览器: {self._chrome_path_cache}")
            return self._chrome_path_cache
        
        self.logger.info("🔍 首次检测Chrome浏览器配置...")
        
        # 🎯 只在第一次调用时进行检测
        chrome_path, source = self.find_chrome_browser()
        
        if chrome_path:
            # 🎯 简化首次检测的日志输出
            self.logger.info(f"✅ 检测到Chrome浏览器: {source}")
            
            # 验证Chrome可用性
            if self.verify_chrome_executable(chrome_path):
                self.logger.info(f"🎉 Chrome浏览器验证通过，后续账号将自动使用缓存配置")
                # 🎯 缓存成功的结果
                self._chrome_path_cache = chrome_path
                self._chrome_source_cache = source
                return chrome_path
            else:
                self.logger.error(f"❌ Chrome浏览器验证失败")
                return None
        else:
            self.logger.error("❌ 未找到任何可用的Chrome浏览器")
            self._print_installation_guide()
            return None
    
    def _print_installation_guide(self):
        """打印Chrome安装指南"""
        self.logger.error("🛠️ Chrome浏览器安装指南:")
        
        if self.system == "Windows":
            self.logger.error("1. 下载Chrome: https://www.google.com/chrome/")
            self.logger.error("2. 或者使用内置浏览器：确保 ms-playwright 目录存在")
            self.logger.error("3. 或者安装便携版Chrome到程序目录")
        elif self.system == "Darwin":
            self.logger.error("1. 下载Chrome: https://www.google.com/chrome/")
            self.logger.error("2. 或使用 brew install --cask google-chrome")
        elif self.system == "Linux":
            self.logger.error("1. Ubuntu/Debian: sudo apt install google-chrome-stable")
            self.logger.error("2. CentOS/RHEL: sudo yum install google-chrome-stable")
            self.logger.error("3. 或下载: https://www.google.com/chrome/")
        
        self.logger.error("❗ 请安装Chrome后重新启动程序")

# 全局实例
_browser_detector = None

def get_browser_detector() -> BrowserDetector:
    """获取浏览器检测器单例"""
    global _browser_detector
    if _browser_detector is None:
        _browser_detector = BrowserDetector()
    return _browser_detector
