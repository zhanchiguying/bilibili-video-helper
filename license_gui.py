#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频上传助手 - 许可证生成器GUI
提供图形界面的许可证生成和验证功能
"""

import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTextEdit,
    QSpinBox, QFileDialog, QMessageBox, QFrame, QGroupBox,
    QGridLayout, QProgressBar, QStatusBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

# 导入许可证系统
from core.license_system import LicenseSystem
# from core.button_utils import prevent_double_click  # 许可证生成器中未使用，注释掉避免导入错误


class LicenseWorker(QThread):
    """许可证操作的工作线程"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, operation, *args):
        super().__init__()
        self.operation = operation
        self.args = args
        self.license_system = LicenseSystem()
    
    def run(self):
        try:
            if self.operation == 'generate':
                if len(self.args) >= 3:
                    days, user_info, target_hardware = self.args
                    result = self.license_system.generate_license(days, user_info, target_hardware)
                else:
                    days, user_info = self.args
                    result = self.license_system.generate_license(days, user_info)
                self.finished.emit(result)
            elif self.operation == 'verify':
                license_text = self.args[0]
                result = self.license_system.verify_license(license_text)
                self.finished.emit(result)
            elif self.operation == 'hardware':
                hardware_fp = self.license_system.get_hardware_fingerprint()
                self.finished.emit({'hardware_fp': hardware_fp})
        except Exception as e:
            self.error.emit(str(e))


class LicenseGeneratorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.license_system = LicenseSystem()
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("B站视频上传助手 - 许可证生成器 v2.0")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建标题
        title_label = QLabel("B站视频上传助手 - 许可证管理系统")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # 生成许可证选项卡
        self.create_generate_tab(tab_widget)
        
        # 验证许可证选项卡
        self.create_verify_tab(tab_widget)
        
        # 硬件指纹选项卡
        self.create_hardware_tab(tab_widget)
        
        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # 获取硬件指纹
        QTimer.singleShot(100, self.refresh_hardware)
    
    def create_generate_tab(self, tab_widget):
        """创建生成许可证选项卡"""
        generate_tab = QWidget()
        tab_widget.addTab(generate_tab, "生成许可证")
        
        layout = QVBoxLayout(generate_tab)
        
        # 输入区域
        input_group = QGroupBox("许可证参数")
        input_layout = QGridLayout(input_group)
        
        # 有效天数
        input_layout.addWidget(QLabel("有效天数:"), 0, 0)
        self.days_spinbox = QSpinBox()
        self.days_spinbox.setRange(1, 36500)
        self.days_spinbox.setValue(30)
        input_layout.addWidget(self.days_spinbox, 0, 1)
        
        # 用户信息
        input_layout.addWidget(QLabel("用户信息:"), 1, 0)
        self.user_info_edit = QLineEdit()
        self.user_info_edit.setPlaceholderText("可选：用户名、公司名等")
        input_layout.addWidget(self.user_info_edit, 1, 1)
        
        # 硬件指纹
        input_layout.addWidget(QLabel("目标硬件指纹:"), 2, 0)
        self.target_hardware_edit = QLineEdit()
        self.target_hardware_edit.setPlaceholderText("留空则使用当前设备硬件指纹")
        input_layout.addWidget(self.target_hardware_edit, 2, 1)
        
        # 获取当前硬件指纹按钮
        get_hardware_btn = QPushButton("获取当前硬件指纹")
        get_hardware_btn.clicked.connect(self.get_current_hardware)
        input_layout.addWidget(get_hardware_btn, 2, 2)
        
        layout.addWidget(input_group)
        
        # 生成按钮
        generate_btn = QPushButton("生成许可证")
        generate_btn.clicked.connect(self.generate_license)
        layout.addWidget(generate_btn)
        
        # 结果显示
        self.license_content_edit = QTextEdit()
        self.license_content_edit.setReadOnly(True)
        layout.addWidget(self.license_content_edit)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.copy_license_btn = QPushButton("复制许可证")
        self.copy_license_btn.clicked.connect(self.copy_license)
        self.copy_license_btn.setEnabled(False)
        button_layout.addWidget(self.copy_license_btn)
        
        self.save_license_btn = QPushButton("保存到文件")
        self.save_license_btn.clicked.connect(self.save_license)
        self.save_license_btn.setEnabled(False)
        button_layout.addWidget(self.save_license_btn)
        
        layout.addLayout(button_layout)
    
    def create_verify_tab(self, tab_widget):
        """创建验证许可证选项卡"""
        verify_tab = QWidget()
        tab_widget.addTab(verify_tab, "验证许可证")
        
        layout = QVBoxLayout(verify_tab)
        
        # 输入区域
        layout.addWidget(QLabel("请输入许可证内容:"))
        self.verify_license_edit = QTextEdit()
        self.verify_license_edit.setMaximumHeight(150)
        layout.addWidget(self.verify_license_edit)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        load_file_btn = QPushButton("从文件加载")
        load_file_btn.clicked.connect(self.load_license_file)
        button_layout.addWidget(load_file_btn)
        
        verify_btn = QPushButton("验证许可证")
        verify_btn.clicked.connect(self.verify_license)
        button_layout.addWidget(verify_btn)
        
        layout.addLayout(button_layout)
        
        # 结果显示
        self.verify_result_label = QLabel()
        self.verify_result_label.setWordWrap(True)
        layout.addWidget(self.verify_result_label)
    
    def create_hardware_tab(self, tab_widget):
        """创建硬件指纹选项卡"""
        hardware_tab = QWidget()
        tab_widget.addTab(hardware_tab, "硬件指纹")
        
        layout = QVBoxLayout(hardware_tab)
        
        # 说明
        info_label = QLabel("硬件指纹用于绑定许可证到特定设备")
        layout.addWidget(info_label)
        
        # 硬件指纹显示
        self.hardware_display = QLineEdit()
        self.hardware_display.setReadOnly(True)
        layout.addWidget(self.hardware_display)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("刷新硬件指纹")
        refresh_btn.clicked.connect(self.refresh_hardware)
        button_layout.addWidget(refresh_btn)
        
        copy_btn = QPushButton("复制硬件指纹")
        copy_btn.clicked.connect(self.copy_hardware)
        button_layout.addWidget(copy_btn)
        
        layout.addLayout(button_layout)
    
    def get_current_hardware(self):
        """获取当前硬件指纹并填入输入框"""
        self.show_progress("正在获取硬件指纹...")
        self.worker = LicenseWorker('hardware')
        self.worker.finished.connect(self.on_hardware_ready)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    
    def on_hardware_ready(self, result):
        """硬件指纹获取完成"""
        self.hide_progress()
        hardware_fp = result['hardware_fp']
        self.target_hardware_edit.setText(hardware_fp)
        self.status_bar.showMessage(f"硬件指纹已获取: {hardware_fp}")
    
    def generate_license(self):
        """生成许可证"""
        days = self.days_spinbox.value()
        user_info = self.user_info_edit.text().strip()
        target_hardware = self.target_hardware_edit.text().strip()
        
        self.show_progress("正在生成许可证...")
        self.worker = LicenseWorker('generate', days, user_info, target_hardware)
        self.worker.finished.connect(self.on_license_generated)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    
    def on_license_generated(self, result):
        """许可证生成完成"""
        self.hide_progress()
        
        if result['success']:
            self.license_content_edit.setText(result['license'])
            self.generated_license = result['license']
            self.copy_license_btn.setEnabled(True)
            self.save_license_btn.setEnabled(True)
            self.status_bar.showMessage("许可证生成成功")
        else:
            QMessageBox.critical(self, "错误", f"生成失败: {result['error']}")
    
    def copy_license(self):
        """复制许可证"""
        if hasattr(self, 'generated_license'):
            clipboard = QApplication.clipboard()
            clipboard.setText(self.generated_license)
            QMessageBox.information(self, "成功", "许可证已复制到剪贴板！")
    
    def save_license(self):
        """保存许可证"""
        if hasattr(self, 'generated_license'):
            filename, _ = QFileDialog.getSaveFileName(
                self, "保存许可证", "license.key", "许可证文件 (*.key)"
            )
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(self.generated_license)
                    QMessageBox.information(self, "成功", f"许可证已保存到: {filename}")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def load_license_file(self):
        """加载许可证文件"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "加载许可证", "", "许可证文件 (*.key)"
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                self.verify_license_edit.setText(content)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载失败: {str(e)}")
    
    def verify_license(self):
        """验证许可证"""
        license_text = self.verify_license_edit.toPlainText().strip()
        if not license_text:
            QMessageBox.warning(self, "警告", "请输入许可证内容")
            return
        
        self.show_progress("正在验证许可证...")
        self.worker = LicenseWorker('verify', license_text)
        self.worker.finished.connect(self.on_license_verified)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    
    def on_license_verified(self, result):
        """许可证验证完成"""
        self.hide_progress()
        
        if result['valid']:
            text = f"✅ 许可证有效\n过期时间: {result['expire_date']}\n剩余天数: {result['remaining_days']}"
            self.verify_result_label.setText(text)
            self.verify_result_label.setStyleSheet("color: green;")
        else:
            text = f"❌ 许可证无效: {result['error']}"
            self.verify_result_label.setText(text)
            self.verify_result_label.setStyleSheet("color: red;")
    
    def refresh_hardware(self):
        """刷新硬件指纹"""
        self.show_progress("正在获取硬件指纹...")
        self.worker = LicenseWorker('hardware')
        self.worker.finished.connect(self.on_hardware_refreshed)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    
    def on_hardware_refreshed(self, result):
        """硬件指纹刷新完成"""
        self.hide_progress()
        self.hardware_display.setText(result['hardware_fp'])
    
    def copy_hardware(self):
        """复制硬件指纹"""
        hardware_fp = self.hardware_display.text()
        if hardware_fp:
            clipboard = QApplication.clipboard()
            clipboard.setText(hardware_fp)
            QMessageBox.information(self, "成功", "硬件指纹已复制！")
    
    def show_progress(self, message):
        """显示进度"""
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage(message)
    
    def hide_progress(self):
        """隐藏进度"""
        self.progress_bar.setVisible(False)
    
    def on_error(self, error_msg):
        """处理错误"""
        self.hide_progress()
        QMessageBox.critical(self, "错误", f"操作失败: {error_msg}")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = LicenseGeneratorGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 