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
    
    def _filter_logs_by_account(self, selected_account):
        """按账号过滤日志"""
        try:
            # 设置当前账号过滤器
            self.main_window._current_account_filter = selected_account
            
            # 重新应用日志过滤
            self._apply_account_filter()
            
            if selected_account == "全部账号":
                self.main_window.log_message("🔍 显示全部账号的日志", "INFO")
            else:
                self.main_window.log_message(f"🔍 只显示账号 [{selected_account}] 的日志", "INFO")
                
        except Exception as e:
            print(f"账号过滤失败: {e}")
    
    def _apply_account_filter(self):
        """应用账号过滤"""
        try:
            if not hasattr(self.main_window, '_original_log_buffer'):
                return
            
            selected_account = getattr(self.main_window, '_current_account_filter', '全部账号')
            
            if selected_account == "全部账号":
                # 显示所有日志
                filtered_logs = self.main_window._original_log_buffer
            else:
                # 过滤指定账号的日志
                filtered_logs = []
                for log_entry, color, account in self.main_window._original_log_buffer:
                    if account == selected_account or account is None:
                        filtered_logs.append((log_entry, color, account))
            
            # 重新构建日志显示
            if hasattr(self.main_window, 'log_text'):
                self.main_window.log_text.clear()
                
                html_content = ""
                for log_entry, color, account in filtered_logs:
                    html_content += f'<div style="color: {color}; margin: 1px 0;">{log_entry}</div>'
                
                if html_content:
                    self.main_window.log_text.append(html_content)
                    
                # 滚动到底部
                scrollbar = self.main_window.log_text.verticalScrollBar()
                if scrollbar:
                    scrollbar.setValue(scrollbar.maximum())
        
        except Exception as e:
            print(f"应用账号过滤失败: {e}")
    
    def update_account_list(self):
        """更新账号列表"""
        try:
            if not hasattr(self.main_window, 'account_filter_combo'):
                return
                
            current_selection = self.main_window.account_filter_combo.currentText()
            
            # 获取当前所有账号
            accounts = ["全部账号"]
            if hasattr(self.main_window, 'core_app') and self.main_window.core_app:
                account_names = self.main_window.core_app.account_manager.get_all_accounts()
                accounts.extend(account_names)
            
            # 更新下拉框
            self.main_window.account_filter_combo.blockSignals(True)
            self.main_window.account_filter_combo.clear()
            self.main_window.account_filter_combo.addItems(accounts)
            
            # 恢复之前的选择
            index = self.main_window.account_filter_combo.findText(current_selection)
            if index >= 0:
                self.main_window.account_filter_combo.setCurrentIndex(index)
            else:
                self.main_window.account_filter_combo.setCurrentIndex(0)  # 默认选择"全部账号"
                
            self.main_window.account_filter_combo.blockSignals(False)
            
        except Exception as e:
            print(f"更新账号列表失败: {e}")
    
    def _create_log_controls(self) -> QHBoxLayout:
        """创建日志控制区域"""
        log_control = QHBoxLayout()
        
        # 账号过滤
        self.main_window.account_filter_combo = QComboBox()
        self.main_window.account_filter_combo.addItems(["全部账号"])
        self.main_window.account_filter_combo.setMinimumWidth(120)
        self.main_window.account_filter_combo.currentTextChanged.connect(self._filter_logs_by_account)
        log_control.addWidget(QLabel("🔍 账号:"))
        log_control.addWidget(self.main_window.account_filter_combo)
        
        # 日志级别过滤
        filter_combo = QComboBox()
        filter_combo.addItems(["全部", "信息", "警告", "错误"])
        filter_combo.currentTextChanged.connect(self.main_window.filter_logs)
        log_control.addWidget(QLabel("级别:"))
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