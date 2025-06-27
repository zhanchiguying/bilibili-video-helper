#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础服务类 - 所有服务的父类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging


class BaseService(ABC):
    """
    基础服务类
    
    所有业务服务的基类，提供通用功能：
    - 日志记录
    - 错误处理
    - 事件通知
    """
    
    def __init__(self, main_window=None):
        """
        初始化基础服务
        
        Args:
            main_window: 主窗口实例，用于访问核心组件和UI更新
        """
        self.main_window = main_window
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialized = False
    
    @property
    def core_app(self):
        """获取核心应用实例"""
        return getattr(self.main_window, 'core_app', None) if self.main_window else None
    
    @property
    def license_system(self):
        """获取许可证系统实例"""
        return getattr(self.main_window, 'license_system', None) if self.main_window else None
    
    def log_message(self, message: str, level: str = "INFO"):
        """记录日志消息"""
        if self.main_window and hasattr(self.main_window, 'log_message'):
            self.main_window.log_message(message, level)
        else:
            # 后备日志记录
            getattr(self.logger, level.lower(), self.logger.info)(message)
    
    def handle_error(self, error: Exception, context: str = "") -> bool:
        """
        统一错误处理
        
        Args:
            error: 异常对象
            context: 错误上下文描述
            
        Returns:
            bool: 是否成功处理错误
        """
        error_msg = f"{context}: {str(error)}" if context else str(error)
        self.log_message(f"❌ {error_msg}", "ERROR")
        self.logger.exception(f"Service error in {self.__class__.__name__}: {error_msg}")
        return False
    
    def notify_success(self, message: str):
        """通知操作成功"""
        self.log_message(f"✅ {message}", "SUCCESS")
    
    def notify_warning(self, message: str):
        """通知警告信息"""
        self.log_message(f"⚠️ {message}", "WARNING")
    
    def initialize(self) -> bool:
        """
        初始化服务
        
        子类可以重写此方法进行特定初始化
        
        Returns:
            bool: 是否初始化成功
        """
        if self._initialized:
            return True
            
        try:
            self._do_initialize()
            self._initialized = True
            self.log_message(f"🔧 {self.__class__.__name__} 初始化成功", "INFO")
            return True
        except Exception as e:
            return self.handle_error(e, f"{self.__class__.__name__} 初始化失败")
    
    def _do_initialize(self):
        """
        具体的初始化逻辑
        
        子类可以重写此方法实现特定的初始化逻辑
        """
        pass
    
    def is_initialized(self) -> bool:
        """检查服务是否已初始化"""
        return self._initialized
    
    def cleanup(self):
        """
        清理资源
        
        子类可以重写此方法进行资源清理
        """
        self._initialized = False
        self.log_message(f"🧹 {self.__class__.__name__} 清理完成", "INFO") 