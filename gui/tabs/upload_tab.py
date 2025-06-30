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
        
        # 视频随机化策略选择
        randomize_layout = QHBoxLayout()
        randomize_layout.addWidget(QLabel("🎲 视频随机化策略:"))
        
        self.main_window.randomize_strategy_combo = QComboBox()
        self.main_window.randomize_strategy_combo.addItems([
            "random - 完全随机（推荐）",
            "group - 分组随机（每10个一组）", 
            "partial - 部分随机（70%改变）",
            "none - 不随机（按文件名顺序）"
        ])
        self.main_window.randomize_strategy_combo.setToolTip(
            "选择视频上传的随机化策略：\n"
            "• 完全随机：最大化随机性，降低平台检测风险\n"
            "• 分组随机：每10个视频一组，组内随机\n" 
            "• 部分随机：70%位置改变，30%保持原顺序\n"
            "• 不随机：按原始文件名顺序上传"
        )
        self.main_window.randomize_strategy_combo.currentTextChanged.connect(self._on_randomize_strategy_changed)
        randomize_layout.addWidget(self.main_window.randomize_strategy_combo)
        
        # 添加策略说明标签
        self.main_window.randomize_info_label = QLabel("💡 完全随机可有效降低平台检测风险")
        self.main_window.randomize_info_label.setStyleSheet(
            "color: #6c757d; font-size: 11px; font-style: italic; padding: 2px;"
        )
        randomize_layout.addWidget(self.main_window.randomize_info_label)
        randomize_layout.addStretch()
        settings_layout.addLayout(randomize_layout)
        
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
    
    def _on_randomize_strategy_changed(self, text):
        """随机化策略改变时的处理"""
        try:
            # 从UI文本中提取策略值
            strategy_value = text.split(' - ')[0]  # 提取 "random", "group", "partial", "none"
            
            # 更新配置
            config = self.main_window.core_app.config_manager.load_config()
            if 'ui_settings' not in config:
                config['ui_settings'] = {}
            config['ui_settings']['randomize_strategy'] = strategy_value
            
            # 保存配置
            self.main_window.core_app.config_manager.save_config(config)
            
            # 更新说明标签
            strategy_info = {
                'random': '💡 完全随机可有效降低平台检测风险',
                'group': '💡 分组随机适合有序列要求的场景',
                'partial': '💡 部分随机平衡随机性和连续性',
                'none': '💡 不随机将按文件名顺序上传'
            }
            self.main_window.randomize_info_label.setText(strategy_info.get(strategy_value, '💡 策略已更新'))
            
            # 在日志中记录变更
            self.main_window.log_message(f"🎲 视频随机化策略已更改为: {strategy_value}", "INFO")
            
        except Exception as e:
            self.main_window.log_message(f"❌ 保存随机化策略失败: {e}", "ERROR")
    
    def load_randomize_strategy_from_config(self):
        """从配置文件加载随机化策略设置到UI"""
        try:
            config = self.main_window.core_app.config_manager.load_config()
            current_strategy = config.get('ui_settings', {}).get('randomize_strategy', 'random')
            
            # 映射策略值到UI显示文本
            strategy_mapping = {
                'random': 'random - 完全随机（推荐）',
                'group': 'group - 分组随机（每10个一组）',
                'partial': 'partial - 部分随机（70%改变）',
                'none': 'none - 不随机（按文件名顺序）'
            }
            
            display_text = strategy_mapping.get(current_strategy, 'random - 完全随机（推荐）')
            
            # 设置下拉框选中项（不触发信号，避免重复保存）
            combo = self.main_window.randomize_strategy_combo
            combo.blockSignals(True)
            index = combo.findText(display_text)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)
            
            # 更新说明标签
            strategy_info = {
                'random': '💡 完全随机可有效降低平台检测风险',
                'group': '💡 分组随机适合有序列要求的场景',
                'partial': '💡 部分随机平衡随机性和连续性',
                'none': '💡 不随机将按文件名顺序上传'
            }
            self.main_window.randomize_info_label.setText(strategy_info.get(current_strategy, '💡 策略已加载'))
            
        except Exception as e:
            self.main_window.log_message(f"❌ 加载随机化策略配置失败: {e}", "WARNING")