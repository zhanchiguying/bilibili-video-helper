#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号管理标签页 - 独立模块
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QGroupBox, 
    QPushButton, QLabel, QLineEdit, QSpinBox, QCheckBox,
    QTableWidget, QAbstractItemView
)
from PyQt5.QtCore import Qt

from core.ui_config import UIConfig
from core.ui_styles import UIStyles


class AccountTab:
    """账号管理标签页"""
    
    def __init__(self, main_window):
        """
        初始化账号标签页
        
        Args:
            main_window: 主窗口实例，用于访问主窗口的方法和属性
        """
        self.main_window = main_window
    
    def create_widget(self) -> QWidget:
        """创建账号管理标签页的UI"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 添加控制面板
        layout.addWidget(self._create_control_panel())
        
        # 添加账号表格区域
        layout.addWidget(self._create_table_area())
        
        # 添加统计信息栏
        layout.addWidget(self._create_stats_bar())
        
        widget.setLayout(layout)
        return widget
    
    def _create_control_panel(self) -> QFrame:
        """创建控制面板"""
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.StyledPanel)
        control_frame.setStyleSheet(UIStyles.get_frame_style())
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        control_layout.setContentsMargins(8, 8, 8, 8)
        
        # 账号操作区
        control_layout.addWidget(self._create_account_operations())
        
        # 批量上传控制区
        control_layout.addWidget(self._create_batch_upload_controls())
        
        control_layout.addStretch()
        control_frame.setLayout(control_layout)
        return control_frame
    
    def _create_account_operations(self) -> QGroupBox:
        """创建账号操作区"""
        account_group = QGroupBox("👤 账号操作")
        account_layout = QHBoxLayout()
        account_layout.setSpacing(10)
        account_layout.setContentsMargins(10, 10, 10, 10)
        
        # 添加账号按钮
        add_account_btn = QPushButton(UIConfig.UI_TEXT['add_account'])
        add_account_btn.setStyleSheet(UIStyles.get_button_style('success'))
        add_account_btn.clicked.connect(self.main_window.add_account)
        account_layout.addWidget(add_account_btn)
        
        # 登录账号按钮
        login_account_btn = QPushButton(UIConfig.UI_TEXT['login_account'])
        login_account_btn.setStyleSheet(UIStyles.get_button_style('primary'))
        login_account_btn.clicked.connect(self.main_window.login_account)
        account_layout.addWidget(login_account_btn)
        
        # 删除账号按钮
        remove_account_btn = QPushButton(UIConfig.UI_TEXT['remove_account'])
        remove_account_btn.setStyleSheet(UIStyles.get_button_style('danger'))
        remove_account_btn.clicked.connect(self.main_window.remove_account)
        account_layout.addWidget(remove_account_btn)
        
        # 浏览器诊断按钮
        diagnose_browser_btn = QPushButton("🔍 浏览器诊断")
        diagnose_browser_btn.setStyleSheet(UIStyles.get_button_style('warning'))
        diagnose_browser_btn.clicked.connect(self.main_window.diagnose_browser)
        account_layout.addWidget(diagnose_browser_btn)
        
        account_group.setLayout(account_layout)
        return account_group
    
    def _create_batch_upload_controls(self) -> QGroupBox:
        """创建批量上传控制区"""
        batch_group = QGroupBox("🚀 批量上传控制")
        batch_layout = QVBoxLayout()
        batch_layout.setSpacing(8)
        batch_layout.setContentsMargins(10, 10, 10, 10)
        
        # 第一行：数量设置
        batch_layout.addLayout(self._create_settings_row1())
        
        # 第二行：等待时间设置和操作按钮
        batch_layout.addLayout(self._create_settings_row2())
        
        batch_group.setLayout(batch_layout)
        return batch_group
    
    def _create_settings_row1(self) -> QHBoxLayout:
        """创建设置行1：浏览器数量和视频数量"""
        settings_row = QHBoxLayout()
        settings_row.setSpacing(10)
        
        # 同时多开浏览器数量
        settings_row.addWidget(QLabel("同时打开浏览器数量:"))
        self.main_window.concurrent_browsers_input = QLineEdit("2")
        self.main_window.concurrent_browsers_input.setMaximumWidth(80)
        self.main_window.concurrent_browsers_input.setPlaceholderText("数量")
        self.main_window.concurrent_browsers_input.textChanged.connect(
            self.main_window.save_ui_settings)
        settings_row.addWidget(self.main_window.concurrent_browsers_input)
        
        settings_row.addWidget(QLabel("每个账号上传视频数量:"))
        self.main_window.videos_per_account_input = QLineEdit("1")
        self.main_window.videos_per_account_input.setMaximumWidth(80)
        self.main_window.videos_per_account_input.setPlaceholderText("数量")
        self.main_window.videos_per_account_input.textChanged.connect(
            self.main_window.save_ui_settings)
        self.main_window.videos_per_account_input.textChanged.connect(
            self.main_window.on_videos_per_account_changed)
        settings_row.addWidget(self.main_window.videos_per_account_input)
        
        settings_row.addStretch()
        return settings_row
    
    def _create_settings_row2(self) -> QHBoxLayout:
        """创建设置行2：等待时间和操作按钮"""
        settings_row2 = QHBoxLayout()
        settings_row2.setSpacing(10)
        
        # 等待时间设置
        settings_row2.addWidget(QLabel("投稿成功等待:"))
        self.main_window.success_wait_time_spinbox = QSpinBox()
        self.main_window.success_wait_time_spinbox.setRange(0, 999)
        self.main_window.success_wait_time_spinbox.setSuffix(" 秒")
        self.main_window.success_wait_time_spinbox.setValue(2)
        self.main_window.success_wait_time_spinbox.setMaximumWidth(100)
        self.main_window.success_wait_time_spinbox.setStyleSheet("font-size: 12px;")
        self.main_window.success_wait_time_spinbox.setToolTip(
            "检测到投稿成功标识后的等待时间，用于确保页面状态稳定（0-999秒）")
        self.main_window.success_wait_time_spinbox.valueChanged.connect(
            self.main_window.on_success_wait_time_changed)
        settings_row2.addWidget(self.main_window.success_wait_time_spinbox)
        
        settings_row2.addStretch()
        
        # 操作按钮
        self.main_window.start_batch_upload_btn = QPushButton("🚀 一键开始")
        self.main_window.start_batch_upload_btn.setStyleSheet(
            UIStyles.get_button_style('success'))
        self.main_window.start_batch_upload_btn.clicked.connect(
            self.main_window.start_batch_upload)
        settings_row2.addWidget(self.main_window.start_batch_upload_btn)
        
        self.main_window.stop_batch_upload_btn = QPushButton("⏹️ 停止上传")
        self.main_window.stop_batch_upload_btn.setStyleSheet(
            UIStyles.get_button_style('danger'))
        self.main_window.stop_batch_upload_btn.setEnabled(False)
        self.main_window.stop_batch_upload_btn.clicked.connect(
            self.main_window.stop_batch_upload)
        settings_row2.addWidget(self.main_window.stop_batch_upload_btn)
        
        return settings_row2
    
    def _create_table_area(self) -> QFrame:
        """创建账号表格区域"""
        table_frame = QFrame()
        table_frame.setFrameStyle(QFrame.StyledPanel)
        table_layout = QVBoxLayout()
        table_layout.setSpacing(8)
        table_layout.setContentsMargins(8, 8, 8, 8)
        
        # 表格标题和全选控制
        title_row = QHBoxLayout()
        table_title = QLabel("👤 账号状态管理")
        table_title.setStyleSheet(UIStyles.get_title_style())
        title_row.addWidget(table_title)
        
        # 全选控制
        self.main_window.select_all_checkbox = QCheckBox("全选")
        self.main_window.select_all_checkbox.setChecked(False)
        self.main_window.select_all_checkbox.clicked.connect(
            self.main_window.toggle_select_all)
        title_row.addWidget(self.main_window.select_all_checkbox)
        
        title_row.addStretch()
        table_layout.addLayout(title_row)
        
        # 账号表格
        self.main_window.account_table = QTableWidget()
        self.main_window.account_table.setColumnCount(8)
        self.main_window.account_table.setHorizontalHeaderLabels([
            "选择", "账号名", "登录状态", "浏览器状态", "最后登录", "今日已发", "进度状态", "备注"
        ])
        
        # 设置表格样式
        self.main_window.account_table.setStyleSheet(UIStyles.get_table_style())
        self.main_window.account_table.setAlternatingRowColors(True)
        self.main_window.account_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # 设置列宽
        header = self.main_window.account_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.resizeSection(0, 60)  # 选择列
        header.resizeSection(1, UIConfig.TABLE_COLUMN_WIDTHS['account_name'])
        header.resizeSection(2, UIConfig.TABLE_COLUMN_WIDTHS['login_status'])
        header.resizeSection(3, UIConfig.TABLE_COLUMN_WIDTHS['browser_status'])
        header.resizeSection(4, UIConfig.TABLE_COLUMN_WIDTHS['last_login'])
        header.resizeSection(5, 80)  # 今日已发列
        header.resizeSection(6, 120)  # 进度状态列
        
        table_layout.addWidget(self.main_window.account_table)
        table_frame.setLayout(table_layout)
        return table_frame
    
    def _create_stats_bar(self) -> QFrame:
        """创建统计信息栏"""
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.StyledPanel)
        stats_frame.setStyleSheet(UIStyles.get_stats_frame_style())
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(8, 6, 8, 6)
        
        self.main_window.account_stats_label = QLabel("账号统计：等待加载...")
        self.main_window.account_stats_label.setStyleSheet(
            "font-weight: bold; color: #495057;")
        
        stats_layout.addWidget(self.main_window.account_stats_label)
        stats_layout.addStretch()
        stats_frame.setLayout(stats_layout)
        return stats_frame 