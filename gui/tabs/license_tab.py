#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
许可证标签页 - 独立模块
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QPushButton, QLabel, QLineEdit, QTextEdit
)
from PyQt5.QtGui import QFont


class LicenseTab:
    """许可证标签页"""
    
    def __init__(self, main_window):
        """
        初始化许可证标签页
        
        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
    
    def create_widget(self) -> QWidget:
        """创建许可证标签页的UI"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 许可证状态区域
        layout.addWidget(self._create_status_area())
        
        # 硬件指纹区域
        layout.addWidget(self._create_hardware_area())
        
        # 许可证输入区域
        layout.addWidget(self._create_input_area())
        
        # 操作记录区域
        layout.addWidget(self._create_log_area())
        
        widget.setLayout(layout)
        return widget
    
    def _create_status_area(self) -> QGroupBox:
        """创建许可证状态区域"""
        status_group = QGroupBox("🔐 许可证状态")
        status_layout = QVBoxLayout()
        
        # 许可证状态标签
        if self.main_window.license_info and self.main_window.is_licensed:
            status_text = (f"✅ 许可证有效 | 剩余天数: {self.main_window.license_info['remaining_days']} 天 | "
                          f"过期时间: {self.main_window.license_info['expire_date']}")
            if self.main_window.license_info.get('user_info'):
                status_text += f" | 用户: {self.main_window.license_info['user_info']}"
            status_color = "color: green;"
        else:
            status_text = "⚠️ 试用模式 | 功能受限 | 请激活许可证获得完整功能"
            status_color = "color: orange;"
        
        self.main_window.license_status_label = QLabel(status_text)
        self.main_window.license_status_label.setStyleSheet(
            f"padding: 10px; font-weight: bold; {status_color}")
        status_layout.addWidget(self.main_window.license_status_label)
        
        # 如果是试用模式，显示限制说明
        if not self.main_window.is_licensed:
            trial_info = QLabel(self.main_window.get_trial_limitations_text())
            trial_info.setStyleSheet("""
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 15px;
                margin: 10px 0;
                color: #856404;
                font-size: 12px;
            """)
            trial_info.setWordWrap(True)
            status_layout.addWidget(trial_info)
        
        status_group.setLayout(status_layout)
        return status_group
    
    def _create_hardware_area(self) -> QGroupBox:
        """创建硬件指纹区域"""
        hardware_group = QGroupBox("💻 硬件指纹")
        hardware_layout = QVBoxLayout()
        
        # 硬件指纹显示
        hardware_fp = self.main_window.license_system.get_hardware_fingerprint()
        
        hardware_info_layout = QHBoxLayout()
        hardware_info_layout.addWidget(QLabel("当前硬件指纹:"))
        
        self.main_window.hardware_fp_edit = QLineEdit(hardware_fp)
        self.main_window.hardware_fp_edit.setReadOnly(True)
        self.main_window.hardware_fp_edit.setFont(QFont("Consolas", 10))
        hardware_info_layout.addWidget(self.main_window.hardware_fp_edit)
        
        copy_fp_btn = QPushButton("📋 复制")
        copy_fp_btn.clicked.connect(self.main_window.copy_hardware_fingerprint)
        hardware_info_layout.addWidget(copy_fp_btn)
        
        hardware_layout.addLayout(hardware_info_layout)
        
        # 说明文字
        hardware_note = QLabel("📝 请将硬件指纹发送给软件开发者以获取正式许可证")
        hardware_note.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
        hardware_layout.addWidget(hardware_note)
        
        hardware_group.setLayout(hardware_layout)
        return hardware_group
    
    def _create_input_area(self) -> QGroupBox:
        """创建许可证输入区域"""
        input_group = QGroupBox("📝 许可证激活")
        input_layout = QVBoxLayout()
        
        # 许可证输入框
        self.main_window.license_input = QTextEdit()
        self.main_window.license_input.setPlaceholderText("请在此处粘贴从开发者处获得的许可证内容...")
        self.main_window.license_input.setMaximumHeight(150)
        self.main_window.license_input.setFont(QFont("Consolas", 9))
        input_layout.addWidget(self.main_window.license_input)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        verify_btn = QPushButton("✅ 验证并激活许可证")
        verify_btn.setStyleSheet(self._get_button_style('success'))
        verify_btn.clicked.connect(self.main_window.verify_license)
        button_layout.addWidget(verify_btn)
        
        save_btn = QPushButton("💾 保存许可证")
        save_btn.setStyleSheet(self._get_button_style('primary'))
        save_btn.clicked.connect(self.main_window.save_license)
        button_layout.addWidget(save_btn)
        
        load_btn = QPushButton("📂 从文件加载")
        load_btn.clicked.connect(self.main_window.load_license_from_file)
        button_layout.addWidget(load_btn)
        
        button_layout.addStretch()
        input_layout.addLayout(button_layout)
        
        input_group.setLayout(input_layout)
        return input_group
    
    def _create_log_area(self) -> QGroupBox:
        """创建操作记录区域"""
        log_group = QGroupBox("📋 操作记录")
        log_layout = QVBoxLayout()
        
        self.main_window.license_log = QTextEdit()
        self.main_window.license_log.setMaximumHeight(150)
        self.main_window.license_log.setReadOnly(True)
        self.main_window.license_log.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.main_window.license_log)
        
        log_group.setLayout(log_layout)
        
        # 初始化日志信息
        self._initialize_log()
        
        return log_group
    
    def _initialize_log(self):
        """初始化日志信息"""
        if self.main_window.is_licensed:
            self.main_window.license_log_message("✅ 程序已授权，功能完整可用")
        else:
            hardware_fp = self.main_window.license_system.get_hardware_fingerprint()
            self.main_window.license_log_message("⚠️ 程序运行在试用模式，功能受限")
            self.main_window.license_log_message(f"💻 当前硬件指纹: {hardware_fp}")
            self.main_window.license_log_message("📧 请联系开发者获取正式许可证")
    
    def _get_button_style(self, style_type: str) -> str:
        """获取按钮样式"""
        styles = {
            'success': """
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
            """,
            'primary': """
                QPushButton {
                    background-color: #007bff;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #0056b3;
                }
            """
        }
        return styles.get(style_type, "") 