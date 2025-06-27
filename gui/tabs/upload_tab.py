#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传标签页 - 独立模块
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, 
    QLabel, QLineEdit, QListWidget, QCheckBox, QComboBox,
    QProgressBar
)
from PyQt5.QtGui import QFont


class UploadTab:
    """上传标签页"""
    
    def __init__(self, main_window):
        """
        初始化上传标签页
        
        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
    
    def create_widget(self) -> QWidget:
        """创建上传标签页的UI"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 视频选择区域
        layout.addWidget(self._create_video_selection_area())
        
        # 上传设置区域
        layout.addWidget(self._create_upload_settings_area())
        
        # 控制区域
        layout.addWidget(self._create_control_area())
        
        widget.setLayout(layout)
        return widget
    
    def _create_video_selection_area(self) -> QGroupBox:
        """创建视频选择区域"""
        video_group = QGroupBox("📹 视频文件选择")
        video_layout = QVBoxLayout()
        
        # 目录选择
        dir_layout = QHBoxLayout()
        
        self.main_window.video_dir_edit = QLineEdit()
        self.main_window.video_dir_edit.setPlaceholderText("选择包含视频文件的目录")
        self.main_window.video_dir_edit.textChanged.connect(self.main_window.refresh_video_list)
        self.main_window.video_dir_edit.textChanged.connect(self.main_window.save_ui_settings)
        dir_layout.addWidget(self.main_window.video_dir_edit)
        
        select_dir_btn = QPushButton("📁 选择目录")
        select_dir_btn.clicked.connect(self.main_window.select_video_directory)
        dir_layout.addWidget(select_dir_btn)
        
        refresh_dir_btn = QPushButton("🔄 刷新")
        refresh_dir_btn.clicked.connect(self.main_window.refresh_video_list)
        dir_layout.addWidget(refresh_dir_btn)
        
        open_folder_btn = QPushButton("📂 打开文件夹")
        open_folder_btn.clicked.connect(self.main_window.open_video_folder)
        dir_layout.addWidget(open_folder_btn)
        
        video_layout.addLayout(dir_layout)
        
        # 文件统计信息
        self.main_window.video_stats_label = QLabel("📊 文件统计: 等待加载...")
        self.main_window.video_stats_label.setStyleSheet(
            "color: #666; font-size: 11px; padding: 2px 5px; margin: 0px;")
        self.main_window.video_stats_label.setMaximumHeight(20)
        video_layout.addWidget(self.main_window.video_stats_label)
        
        # 视频文件列表
        self.main_window.video_list = QListWidget()
        self.main_window.video_list.setMaximumHeight(400)
        self.main_window.video_list.setMinimumHeight(300)
        self.main_window.video_list.setAlternatingRowColors(True)
        self.main_window.video_list.itemClicked.connect(self.main_window.on_video_selected)
        video_layout.addWidget(self.main_window.video_list)
        
        # 自动刷新控制
        auto_refresh_layout = QHBoxLayout()
        self.main_window.auto_refresh_check = QCheckBox("自动刷新文件列表")
        self.main_window.auto_refresh_check.setChecked(True)
        self.main_window.auto_refresh_check.toggled.connect(self.main_window.toggle_auto_refresh)
        auto_refresh_layout.addWidget(self.main_window.auto_refresh_check)
        auto_refresh_layout.addStretch()
        video_layout.addLayout(auto_refresh_layout)
        
        video_group.setLayout(video_layout)
        return video_group
    
    def _create_upload_settings_area(self) -> QGroupBox:
        """创建上传设置区域"""
        settings_group = QGroupBox("⚙️ 上传设置")
        settings_layout = QVBoxLayout()
        
        # 账号选择
        account_layout = QHBoxLayout()
        account_layout.addWidget(QLabel("选择账号:"))
        self.main_window.account_combo = QComboBox()
        account_layout.addWidget(self.main_window.account_combo)
        account_layout.addStretch()
        settings_layout.addLayout(account_layout)
        
        settings_group.setLayout(settings_layout)
        return settings_group
    
    def _create_control_area(self) -> QGroupBox:
        """创建控制区域"""
        control_group = QGroupBox("🎬 浏览器上传控制")
        control_layout = QVBoxLayout()
        
        # 选中文件信息
        self.main_window.selected_file_label = QLabel("请选择要上传的视频文件")
        self.main_window.selected_file_label.setStyleSheet(
            "padding: 8px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;")
        self.main_window.selected_file_label.setWordWrap(True)
        control_layout.addWidget(self.main_window.selected_file_label)
        
        # 按钮区
        button_layout = QHBoxLayout()
        
        self.main_window.start_upload_btn = QPushButton("🚀 开始上传")
        self.main_window.start_upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.main_window.start_upload_btn.clicked.connect(self.main_window.start_browser_upload)
        button_layout.addWidget(self.main_window.start_upload_btn)
        
        self.main_window.pause_upload_btn = QPushButton("⏸️ 暂停")
        self.main_window.pause_upload_btn.setEnabled(False)
        self.main_window.pause_upload_btn.clicked.connect(self.main_window.pause_browser_upload)
        button_layout.addWidget(self.main_window.pause_upload_btn)
        
        self.main_window.stop_upload_btn = QPushButton("⏹️ 停止")
        self.main_window.stop_upload_btn.setEnabled(False)
        self.main_window.stop_upload_btn.clicked.connect(self.main_window.stop_browser_upload)
        button_layout.addWidget(self.main_window.stop_upload_btn)
        
        button_layout.addStretch()
        control_layout.addLayout(button_layout)
        
        # 进度显示
        self.main_window.upload_progress = QProgressBar()
        self.main_window.upload_progress.setVisible(False)
        control_layout.addWidget(self.main_window.upload_progress)
        
        # 状态标签
        self.main_window.upload_status_label = QLabel("✅ 准备就绪")
        self.main_window.upload_status_label.setStyleSheet("color: #28a745; font-weight: bold;")
        control_layout.addWidget(self.main_window.upload_status_label)
        
        control_group.setLayout(control_layout)
        return control_group 