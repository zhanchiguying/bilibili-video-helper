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
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.setup_logging()
        self.logger = logging.getLogger("BilibiliUploader")
    
    def setup_logging(self):
        """设置日志系统"""
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
        
        # 文件处理器
        log_file = os.path.join(Config.LOGS_DIR, f"{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # GUI处理器
        if self._signal_emitter is None:
            self._signal_emitter = LogSignalEmitter()
        
        gui_handler = GuiLogHandler(self._signal_emitter)
        gui_handler.setLevel(logging.INFO)
        gui_handler.setFormatter(logging.Formatter('%(message)s'))
        
        # 配置根logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 添加处理器
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(gui_handler)
    
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
        """调试日志"""
        self.logger.debug(message)

# 全局日志实例
_logger = None

def get_logger() -> Logger:
    """获取全局日志实例"""
    global _logger
    if _logger is None:
        _logger = Logger()
    return _logger 