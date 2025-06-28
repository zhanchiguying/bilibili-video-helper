#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志模块 - 简化的日志系统
"""

import os
import logging
from datetime import datetime
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal
from .config import Config

class GuiLogHandler(logging.Handler):
    """GUI日志处理器"""
    
    def __init__(self, signal_emitter):
        super().__init__()
        self.signal_emitter = signal_emitter
    
    def emit(self, record):
        try:
            msg = self.format(record)
            self.signal_emitter.log_signal.emit(msg)
        except:
            pass

class LogSignalEmitter(QObject):
    """日志信号发射器"""
    log_signal = pyqtSignal(str)

class Logger:
    """统一的日志管理器"""
    
    _instance = None
    _signal_emitter = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            # 🔧 修复：在创建实例时就设置基本属性
            cls._instance.logger = logging.getLogger("BilibiliUploader")
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.setup_logging()
    
    def setup_logging(self):
        """设置日志系统 - 优化版：减少日志产生量"""
        # 创建日志目录
        os.makedirs(Config.LOGS_DIR, exist_ok=True)
        
        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # 🔧 优化：使用轮转文件处理器，防止单文件过大
        log_file = os.path.join(Config.LOGS_DIR, f"{datetime.now().strftime('%Y%m%d')}.log")
        try:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=50*1024*1024,  # 50MB轮转
                backupCount=3, 
                encoding='utf-8'
            )
            file_handler.setLevel(logging.WARNING)  # 🔧 文件只记录WARNING及以上
        except ImportError:
            # 如果没有RotatingFileHandler，回退到普通FileHandler
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.WARNING)  # 🔧 文件只记录WARNING及以上
        
        file_handler.setFormatter(formatter)
        
        # GUI处理器
        if self._signal_emitter is None:
            self._signal_emitter = LogSignalEmitter()
        
        gui_handler = GuiLogHandler(self._signal_emitter)
        gui_handler.setLevel(logging.INFO)
        gui_handler.setFormatter(logging.Formatter('%(message)s'))
        
        # 🔧 优化：配置根logger级别为INFO（生产环境）
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)  # 从DEBUG改为INFO
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 添加处理器
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(gui_handler)
        
        # 🔧 新增：禁用第三方库的详细日志，防止日志爆炸
        self._configure_third_party_logging()
    
    def _configure_third_party_logging(self):
        """配置第三方库日志级别，防止日志爆炸"""
        # 禁用requests库的详细日志
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('requests.packages.urllib3').setLevel(logging.WARNING)
        
        # 禁用urllib3的详细日志
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
        
        # 禁用selenium的详细日志
        logging.getLogger('selenium').setLevel(logging.WARNING)
        logging.getLogger('selenium.webdriver').setLevel(logging.WARNING)
        logging.getLogger('selenium.webdriver.remote').setLevel(logging.WARNING)
        
        # 禁用其他可能产生大量日志的库
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        logging.getLogger('websockets').setLevel(logging.WARNING)
        
        # 记录配置完成
        self.info("🔧 第三方库日志级别已优化，减少日志产生量")
    
    @property
    def signal_emitter(self):
        """获取信号发射器"""
        return self._signal_emitter
    
    def info(self, message: str):
        """信息日志"""
        self.logger.info(message)
    
    def error(self, message: str):
        """错误日志"""
        self.logger.error(message)
    
    def warning(self, message: str):
        """警告日志"""
        self.logger.warning(message)
    
    def debug(self, message: str):
        """调试日志 - 优化：只在必要时记录"""
        # 🔧 优化：DEBUG信息只在开发模式下记录
        if os.getenv('BILIBILI_DEBUG', '').lower() in ('1', 'true', 'yes'):
            self.logger.debug(message)

# 全局日志实例
_logger = None

def get_logger() -> Logger:
    """获取全局日志实例"""
    global _logger
    if _logger is None:
        _logger = Logger()
    return _logger 