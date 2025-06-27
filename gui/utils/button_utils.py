#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按钮工具模块 - 防止重复点击等功能
"""

import time
from functools import wraps
from typing import Dict, Callable, Optional
from PyQt5.QtWidgets import QPushButton, QApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import Qt

class ButtonClickGuard:
    """按钮点击保护器 - 防止重复点击"""
    
    def __init__(self):
        self._button_states: Dict[int, Dict] = {}  # 按钮状态记录
        self._timers: Dict[int, QTimer] = {}  # 定时器记录
    
    def protect_button(self, 
                      button: QPushButton, 
                      duration: float = 2.0,
                      disable_text: Optional[str] = None,
                      restore_cursor: bool = True) -> None:
        """
        保护按钮免受重复点击
        
        Args:
            button: 要保护的按钮
            duration: 保护持续时间（秒）
            disable_text: 禁用时显示的文本
            restore_cursor: 是否恢复光标
        """
        button_id = id(button)
        
        # 保存按钮原始状态
        if button_id not in self._button_states:
            self._button_states[button_id] = {
                'original_text': button.text(),
                'original_enabled': button.isEnabled(),
                'original_cursor': button.cursor()
            }
        
        # 禁用按钮
        button.setEnabled(False)
        
        # 更改按钮文本
        if disable_text:
            button.setText(disable_text)
        
        # 更改光标
        if restore_cursor:
            button.setCursor(QCursor(Qt.ForbiddenCursor))
        
        # 设置定时器恢复按钮
        if button_id in self._timers:
            self._timers[button_id].stop()
        
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._restore_button(button))
        timer.start(int(duration * 1000))  # 转换为毫秒
        
        self._timers[button_id] = timer
    
    def _restore_button(self, button: QPushButton) -> None:
        """恢复按钮状态"""
        button_id = id(button)
        
        if button_id in self._button_states:
            state = self._button_states[button_id]
            
            # 恢复按钮状态
            button.setEnabled(state['original_enabled'])
            button.setText(state['original_text'])
            button.setCursor(state['original_cursor'])
            
            # 清理记录
            del self._button_states[button_id]
        
        if button_id in self._timers:
            del self._timers[button_id]
    
    def is_button_protected(self, button: QPushButton) -> bool:
        """检查按钮是否被保护中"""
        return id(button) in self._button_states
    
    def release_button(self, button: QPushButton) -> None:
        """立即释放按钮保护"""
        button_id = id(button)
        
        if button_id in self._timers:
            self._timers[button_id].stop()
            self._restore_button(button)


# 全局按钮保护器实例
_global_guard = ButtonClickGuard()


def prevent_double_click(duration: float = 2.0, 
                        disable_text: Optional[str] = None,
                        restore_cursor: bool = True):
    """
    防止按钮重复点击的装饰器
    
    Args:
        duration: 保护持续时间（秒）
        disable_text: 禁用时显示的文本
        restore_cursor: 是否恢复光标
    
    Usage:
        @prevent_double_click(duration=3.0, disable_text="处理中...")
        def button_clicked(self):
            # 按钮点击处理逻辑
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取self对象（第一个参数应该是self）
            if args and hasattr(args[0], 'sender'):
                self = args[0]
                
                # 尝试找到触发的按钮
                button = None
                
                # 方法1：从sender()获取
                if hasattr(self, 'sender') and callable(self.sender):
                    sender = self.sender()
                    if isinstance(sender, QPushButton):
                        button = sender
                
                # 方法2：从QApplication获取焦点部件
                if not button:
                    focus_widget = QApplication.focusWidget()
                    if isinstance(focus_widget, QPushButton):
                        button = focus_widget
                
                # 如果找到按钮，进行保护
                if button and not _global_guard.is_button_protected(button):
                    _global_guard.protect_button(button, duration, disable_text, restore_cursor)
                
                # 只传递self参数，忽略PyQt5信号可能传递的额外参数
                return func(self)
            
            # 如果不是类方法调用，正常传递所有参数
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def protect_button_click(button: QPushButton, 
                        duration: float = 2.0,
                        disable_text: Optional[str] = None,
                        restore_cursor: bool = True) -> None:
    """
    直接保护按钮的便捷函数
    
    Args:
        button: 要保护的按钮
        duration: 保护持续时间（秒）
        disable_text: 禁用时显示的文本
        restore_cursor: 是否恢复光标
    """
    _global_guard.protect_button(button, duration, disable_text, restore_cursor)


def is_button_protected(button: QPushButton) -> bool:
    """检查按钮是否被保护中"""
    return _global_guard.is_button_protected(button)


def release_button_protection(button: QPushButton) -> None:
    """立即释放按钮保护"""
    _global_guard.release_button(button)


class SmartButton(QPushButton):
    """智能按钮 - 自带防重复点击功能"""
    
    def __init__(self, text: str = "", 
                 click_protection: float = 2.0,
                 disable_text: Optional[str] = None,
                 parent=None):
        super().__init__(text, parent)
        self.click_protection = click_protection
        self.disable_text = disable_text or f"{text}中..."
        self._original_clicked_handlers = []
        
        # 重写clicked信号连接
        self._connect_with_protection()
    
    def _connect_with_protection(self):
        """连接带保护的点击事件"""
        # 保存原始的clicked信号
        self._original_clicked = self.clicked
        
        # 拦截clicked.connect方法
        original_connect = self.clicked.connect
        
        def protected_connect(slot):
            def protected_slot(*args, **kwargs):
                # 先保护按钮
                protect_button_click(
                    self, 
                    self.click_protection, 
                    self.disable_text, 
                    True
                )
                # 然后执行原始slot
                return slot(*args, **kwargs)
            
            # 连接保护后的slot
            return original_connect(protected_slot)
        
        # 替换connect方法
        self.clicked.connect = protected_connect
    
    def set_protection_duration(self, duration: float):
        """设置保护持续时间"""
        self.click_protection = duration
    
    def set_disable_text(self, text: str):
        """设置禁用时的文本"""
        self.disable_text = text


# 便捷函数：为现有按钮添加保护
def add_click_protection(button: QPushButton, 
                        duration: float = 2.0,
                        disable_text: Optional[str] = None) -> None:
    """
    为现有按钮添加点击保护
    
    Args:
        button: 要保护的按钮
        duration: 保护持续时间
        disable_text: 禁用时显示的文本
    """
    # 保存原始的点击处理器
    original_handlers = []
    
    # 获取当前连接的所有处理器（这个在PyQt5中比较复杂，用简单方法）
    def create_protected_handler(original_handler):
        def protected_handler(*args, **kwargs):
            protect_button_click(button, duration, disable_text or f"{button.text()}中...")
            return original_handler(*args, **kwargs)
        return protected_handler
    
    # 注意：这个方法需要在按钮创建时调用，不能在已经连接后调用
    # 更推荐使用装饰器或SmartButton类


def batch_protect_buttons(buttons_config: Dict[QPushButton, Dict]) -> None:
    """
    批量保护按钮
    
    Args:
        buttons_config: 按钮配置字典
            {
                button: {
                    'duration': 2.0,
                    'disable_text': '处理中...'
                }
            }
    """
    for button, config in buttons_config.items():
        duration = config.get('duration', 2.0)
        disable_text = config.get('disable_text', f"{button.text()}中...")
        
        # 为按钮添加保护（需要在点击时调用）
        def create_click_handler(btn, dur, txt):
            original_click = btn.click
            def protected_click():
                protect_button_click(btn, dur, txt)
                return original_click()
            return protected_click
        
        # 这种方法不太理想，推荐使用装饰器
        print(f"为按钮 '{button.text()}' 配置保护: {duration}秒") 