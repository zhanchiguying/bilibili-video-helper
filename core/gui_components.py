#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI组件模块 - 从gui.py中抽离的可重用组件
减少主GUI文件的复杂度，提升代码可维护性
"""

import os
import time
from typing import List, Dict, Optional, Callable
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QTextCursor

from .thread_manager import get_thread_manager, BaseWorkerThread
from .ui_styles import UIStyles
from .ui_config import UIConfig

class StatusDisplayWidget(QWidget):
    """状态显示组件 - 统一的状态显示界面"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
    
    def update_status(self, message: str, progress: int = -1):
        """更新状态"""
        self.status_label.setText(message)
        
        if progress >= 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(progress)
        else:
            self.progress_bar.setVisible(False)
    
    def show_progress(self, message: str = "处理中..."):
        """显示进度条"""
        self.status_label.setText(message)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 无限滚动
    
    def hide_progress(self):
        """隐藏进度条"""
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)


class AccountTableWidget(QTableWidget):
    """账号表格组件 - 优化的账号管理表格"""
    
    account_selected = pyqtSignal(str)  # 账号选择信号
    
    def __init__(self):
        super().__init__()
        self.setup_table()
        self.account_data = {}
    
    def setup_table(self):
        """设置表格"""
        # 设置列
        headers = ["账号名", "登录状态", "浏览器状态", "最后登录"]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        
        # 应用样式
        self.setStyleSheet(UIStyles.table_style())
        
        # 设置选择模式
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # 设置列宽
        header = self.horizontalHeader()
        header.resizeSection(0, UIConfig.TABLE_COLUMN_WIDTHS['account_name'])
        header.resizeSection(1, UIConfig.TABLE_COLUMN_WIDTHS['login_status'])
        header.resizeSection(2, UIConfig.TABLE_COLUMN_WIDTHS['browser_status'])
        header.resizeSection(3, UIConfig.TABLE_COLUMN_WIDTHS['last_login'])
        
        # 连接信号
        self.itemSelectionChanged.connect(self.on_selection_changed)
    
    def update_accounts(self, accounts: Dict[str, Dict]):
        """更新账号数据"""
        self.account_data = accounts
        self.refresh_display()
    
    def refresh_display(self):
        """刷新显示"""
        self.setRowCount(len(self.account_data))
        
        for row, (username, account_info) in enumerate(self.account_data.items()):
            # 账号名
            self.setItem(row, 0, QTableWidgetItem(username))
            
            # 登录状态
            login_status = "已登录" if account_info.get('status') == 'active' else "未登录"
            login_item = QTableWidgetItem(login_status)
            if account_info.get('status') == 'active':
                login_item.setBackground(QColor(UIStyles.COLORS['success']))
            self.setItem(row, 1, login_item)
            
            # 浏览器状态
            browser_status = "活跃" if account_info.get('browser_active') else "未运行"
            browser_item = QTableWidgetItem(browser_status)
            if account_info.get('browser_active'):
                browser_item.setBackground(QColor(UIStyles.COLORS['info']))
            self.setItem(row, 2, browser_item)
            
            # 最后登录时间
            last_login = account_info.get('last_login', 0)
            if last_login:
                import datetime
                last_login_str = datetime.datetime.fromtimestamp(last_login).strftime('%Y-%m-%d %H:%M')
            else:
                last_login_str = "从未登录"
            self.setItem(row, 3, QTableWidgetItem(last_login_str))
    
    def on_selection_changed(self):
        """选择变化事件"""
        current_row = self.currentRow()
        if current_row >= 0:
            username_item = self.item(current_row, 0)
            if username_item:
                self.account_selected.emit(username_item.text())


class VideoListWidget(QListWidget):
    """视频列表组件 - 优化的视频文件列表"""
    
    video_selected = pyqtSignal(str)  # 视频选择信号
    
    def __init__(self):
        super().__init__()
        self.setup_list()
        self.video_files = []
    
    def setup_list(self):
        """设置列表"""
        self.setMaximumHeight(UIConfig.VIDEO_LIST_MAX_HEIGHT)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # 连接信号
        self.itemSelectionChanged.connect(self.on_selection_changed)
    
    def update_videos(self, video_files: List[str]):
        """更新视频列表"""
        self.video_files = video_files
        self.clear()
        
        for video_file in video_files:
            item = QListWidgetItem(video_file)
            
            # 添加文件信息到工具提示
            file_path = video_file if os.path.isabs(video_file) else os.path.abspath(video_file)
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                size_mb = file_size / (1024 * 1024)
                item.setToolTip(f"文件大小: {size_mb:.1f} MB\n路径: {file_path}")
            
            self.addItem(item)
    
    def get_selected_videos(self) -> List[str]:
        """获取选中的视频文件"""
        selected_items = self.selectedItems()
        return [item.text() for item in selected_items]
    
    def on_selection_changed(self):
        """选择变化事件"""
        selected_videos = self.get_selected_videos()
        if selected_videos:
            self.video_selected.emit(selected_videos[0])


class LogDisplayWidget(QTextEdit):
    """日志显示组件 - 优化的日志查看器"""
    
    def __init__(self):
        super().__init__()
        self.setup_log_display()
        self.auto_scroll = True
        self.log_buffer = []
        self.max_lines = 1000  # 限制最大行数
    
    def setup_log_display(self):
        """设置日志显示"""
        self.setReadOnly(True)
        self.setFont(QFont(UIConfig.LOG_FONT_FAMILY, UIConfig.LOG_FONT_SIZE))
        self.setStyleSheet(UIStyles.log_style())
    
    def append_log(self, message: str, level: str = "INFO"):
        """添加日志"""
        # 格式化消息
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] [{level}] {message}"
        
        # 添加到缓冲区
        self.log_buffer.append(formatted_message)
        
        # 限制缓冲区大小
        if len(self.log_buffer) > self.max_lines:
            self.log_buffer = self.log_buffer[-self.max_lines:]
        
        # 显示消息
        color = UIConfig.LOG_COLORS.get(level, UIConfig.LOG_COLORS['INFO'])
        html_message = f'<span style="color: {color}">{formatted_message}</span>'
        
        self.append(html_message)
        
        # 自动滚动
        if self.auto_scroll:
            self.scroll_to_bottom()
    
    def scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_logs(self):
        """清空日志"""
        self.clear()
        self.log_buffer.clear()
    
    def toggle_auto_scroll(self, enabled: bool):
        """切换自动滚动"""
        self.auto_scroll = enabled
    
    def search_logs(self, text: str):
        """搜索日志"""
        if not text:
            return
        
        cursor = self.document().find(text, self.textCursor())
        if cursor.isNull():
            # 从头开始搜索
            cursor = self.document().find(text)
        
        if not cursor.isNull():
            self.setTextCursor(cursor)


class BrowserStatusIndicator(QLabel):
    """浏览器状态指示器"""
    
    def __init__(self):
        super().__init__()
        self.setup_indicator()
    
    def setup_indicator(self):
        """设置指示器"""
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(20, 20)
        self.setStyleSheet("""
            QLabel {
                border-radius: 10px;
                border: 2px solid #ccc;
            }
        """)
        self.set_status(False)
    
    def set_status(self, active: bool):
        """设置状态"""
        if active:
            self.setStyleSheet("""
                QLabel {
                    background-color: #4CAF50;
                    border-radius: 10px;
                    border: 2px solid #45a049;
                }
            """)
            self.setToolTip("浏览器运行中")
        else:
            self.setStyleSheet("""
                QLabel {
                    background-color: #f44336;
                    border-radius: 10px;
                    border: 2px solid #da190b;
                }
            """)
            self.setToolTip("浏览器未运行")


class ProgressDialog(QDialog):
    """进度对话框 - 统一的进度显示"""
    
    def __init__(self, title: str = "处理中", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 150)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 状态标签
        self.status_label = QLabel("初始化...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # 取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)
    
    def update_progress(self, value: int, status: str = ""):
        """更新进度"""
        self.progress_bar.setValue(value)
        if status:
            self.status_label.setText(status)
    
    def set_indeterminate(self, status: str = "处理中..."):
        """设置为不确定进度"""
        self.progress_bar.setRange(0, 0)
        self.status_label.setText(status)


class QuickActionWidget(QWidget):
    """快速操作组件"""
    
    action_triggered = pyqtSignal(str)  # 操作触发信号
    
    def __init__(self):
        super().__init__()
        self.setup_actions()
    
    def setup_actions(self):
        """设置快速操作"""
        layout = QHBoxLayout(self)
        
        actions = [
            ("刷新状态", "refresh"),
            ("停止所有", "stop_all"),
            ("清理缓存", "cleanup"),
            ("查看日志", "view_logs")
        ]
        
        for text, action_id in actions:
            button = QPushButton(text)
            button.setStyleSheet(UIStyles.button_style("secondary", "small"))
            button.clicked.connect(lambda checked, aid=action_id: self.action_triggered.emit(aid))
            layout.addWidget(button)


class TaskManagerWidget(QWidget):
    """任务管理组件 - 显示当前运行的任务"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.thread_manager = get_thread_manager()
        
        # 定时器更新任务状态
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_task_status)
        self.update_timer.start(2000)  # 每2秒更新一次
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("活跃任务")
        title_label.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(title_label)
        
        # 任务列表
        self.task_list = QListWidget()
        self.task_list.setMaximumHeight(100)
        layout.addWidget(self.task_list)
        
        # 任务计数
        self.task_count_label = QLabel("0 个活跃任务")
        layout.addWidget(self.task_count_label)
    
    def update_task_status(self):
        """更新任务状态"""
        active_count = self.thread_manager.get_active_thread_count()
        self.task_count_label.setText(f"{active_count} 个活跃任务")
        
        # 这里可以添加更详细的任务信息显示
        # 由于ThreadManager没有提供获取具体任务信息的接口，暂时只显示数量


# 工具函数
def create_labeled_input(label_text: str, input_widget: QWidget) -> QWidget:
    """创建带标签的输入组件"""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    
    label = QLabel(label_text)
    label.setMinimumWidth(80)
    layout.addWidget(label)
    layout.addWidget(input_widget)
    
    return container


def create_button_group(buttons: List[tuple], style: str = "primary") -> QWidget:
    """创建按钮组"""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    
    for text, callback in buttons:
        button = QPushButton(text)
        button.setStyleSheet(UIStyles.button_style(style))
        if callback:
            button.clicked.connect(callback)
        layout.addWidget(button)
    
    return container


def show_error_dialog(parent, title: str, message: str):
    """显示错误对话框"""
    QMessageBox.critical(parent, title, message)


def show_info_dialog(parent, title: str, message: str):
    """显示信息对话框"""
    QMessageBox.information(parent, title, message)


def show_question_dialog(parent, title: str, message: str) -> bool:
    """显示询问对话框"""
    reply = QMessageBox.question(parent, title, message, 
                                QMessageBox.Yes | QMessageBox.No)
    return reply == QMessageBox.Yes 