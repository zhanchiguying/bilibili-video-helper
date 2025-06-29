#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志标签页 - 独立模块
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QComboBox, 
    QCheckBox, QTextEdit
)
from PyQt5.QtGui import QFont

from core.config import UIConfig


class LogTab:
    """日志标签页"""
    
    def __init__(self, main_window):
        """
        初始化日志标签页
        
        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
    
    def create_widget(self) -> QWidget:
        """创建日志标签页的UI"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 日志控制区域
        layout.addLayout(self._create_log_controls())
        
        # 日志显示区域
        layout.addWidget(self._create_log_display())
        
        widget.setLayout(layout)
        return widget
    
    def _toggle_verbose_logging(self, enabled):
        """切换详细日志模式"""
        self.main_window._verbose_logging = enabled
        if enabled:
            self.main_window.log_message("✅ 详细日志模式已开启", "INFO")
        else:
            self.main_window.log_message("ℹ️ 详细日志模式已关闭，只显示重要信息", "INFO")
    
    def _create_log_controls(self) -> QHBoxLayout:
        """创建日志控制区域"""
        log_control = QHBoxLayout()
        
        # 日志过滤
        filter_combo = QComboBox()
        filter_combo.addItems(["全部", "信息", "警告", "错误"])
        filter_combo.currentTextChanged.connect(self.main_window.filter_logs)
        log_control.addWidget(QLabel("过滤:"))
        log_control.addWidget(filter_combo)
        
        # 搜索
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("搜索日志...")
        search_edit.textChanged.connect(self.main_window.search_logs)
        log_control.addWidget(QLabel("搜索:"))
        log_control.addWidget(search_edit)
        
        # 自动滚动
        auto_scroll_check = QCheckBox("自动滚动")
        auto_scroll_check.setChecked(True)
        auto_scroll_check.toggled.connect(self.main_window.toggle_auto_scroll)
        log_control.addWidget(auto_scroll_check)
        
        # 详细日志
        verbose_check = QCheckBox("详细日志")
        verbose_check.setChecked(False)
        verbose_check.toggled.connect(self._toggle_verbose_logging)
        log_control.addWidget(verbose_check)
        
        # 清空和保存
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self.main_window.clear_log)
        log_control.addWidget(clear_btn)
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.main_window.save_log)
        log_control.addWidget(save_btn)
        
        log_control.addStretch()
        return log_control
    
    def _create_log_display(self) -> QTextEdit:
        """创建日志显示区域"""
        self.main_window.log_text = QTextEdit()
        self.main_window.log_text.setReadOnly(True)
        self.main_window.log_text.setFont(QFont(UIConfig.LOG_FONT_FAMILY, UIConfig.LOG_FONT_SIZE))
        return self.main_window.log_text 