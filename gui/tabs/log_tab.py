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

from core.ui_config import UIConfig


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