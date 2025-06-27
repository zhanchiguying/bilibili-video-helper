#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI样式模块 - 性能优化版本
集中管理所有界面样式，避免重复定义，提升加载速度
"""

class UIStyles:
    """UI样式管理器 - 优化版本"""
    
    # 🎨 基础颜色配置
    COLORS = {
        'primary': '#0078d4',
        'secondary': '#6c757d',
        'success': '#28a745',
        'danger': '#dc3545',
        'warning': '#ffc107',
        'info': '#17a2b8',
        'light': '#f8f9fa',
        'dark': '#343a40',
        'white': '#ffffff',
        'border': '#dee2e6',
        'hover': '#e9ecef',
        'focus': '#007bff',
        'disabled': '#6c757d'
    }
    
    # 🚀 缓存样式字符串，避免重复计算
    _STYLE_CACHE = {}
    
    @classmethod
    def get_cached_style(cls, style_key: str, style_func, *args, **kwargs):
        """获取缓存的样式，避免重复计算"""
        cache_key = f"{style_key}_{hash(str(args) + str(kwargs))}"
        if cache_key not in cls._STYLE_CACHE:
            cls._STYLE_CACHE[cache_key] = style_func(*args, **kwargs)
        return cls._STYLE_CACHE[cache_key]
    
    @classmethod
    def button_style(cls, style_type="primary", size="normal"):
        """优化的按钮样式生成器"""
        return cls.get_cached_style(f"button_{style_type}_{size}", cls._create_button_style, style_type, size)
    
    @classmethod
    def _create_button_style(cls, style_type="primary", size="normal"):
        """创建按钮样式"""
        # 基础样式
        base_style = """
            QPushButton {
                border-radius: 6px;
                font-weight: 500;
                border: 1px solid transparent;
                text-align: center;
            }
        """
        
        # 尺寸样式
        size_styles = {
            "small": "padding: 4px 8px; font-size: 12px;",
            "normal": "padding: 8px 16px; font-size: 14px;",
            "large": "padding: 12px 24px; font-size: 16px;"
        }
        
        # 颜色样式
        color_map = {
            'primary': (cls.COLORS['primary'], cls.COLORS['white']),
            'success': (cls.COLORS['success'], cls.COLORS['white']),
            'danger': (cls.COLORS['danger'], cls.COLORS['white']),
            'warning': (cls.COLORS['warning'], cls.COLORS['dark']),
            'info': (cls.COLORS['info'], cls.COLORS['white']),
            'secondary': (cls.COLORS['secondary'], cls.COLORS['white']),
            'light': (cls.COLORS['light'], cls.COLORS['dark'])
        }
        
        bg_color, text_color = color_map.get(style_type, color_map['primary'])
        
        return f"""
            {base_style}
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border-color: {bg_color};
                {size_styles.get(size, size_styles['normal'])}
            }}
            QPushButton:hover {{
                background-color: {cls._darken_color(bg_color)};
                border-color: {cls._darken_color(bg_color)};
            }}
            QPushButton:pressed {{
                background-color: {cls._darken_color(bg_color, 0.2)};
            }}
            QPushButton:disabled {{
                background-color: {cls.COLORS['disabled']};
                border-color: {cls.COLORS['disabled']};
                color: {cls.COLORS['white']};
            }}
        """
    
    @classmethod
    def table_style(cls):
        """优化的表格样式"""
        return cls.get_cached_style("table_main", cls._create_table_style)
    
    @classmethod
    def _create_table_style(cls):
        """创建表格样式"""
        return f"""
            QTableWidget {{
                background-color: {cls.COLORS['white']};
                border: 1px solid {cls.COLORS['border']};
                border-radius: 4px;
                gridline-color: {cls.COLORS['border']};
                selection-background-color: {cls.COLORS['primary']};
                selection-color: {cls.COLORS['white']};
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {cls.COLORS['border']};
            }}
            QTableWidget::item:selected {{
                background-color: {cls.COLORS['primary']};
                color: {cls.COLORS['white']};
            }}
            QTableWidget::item:hover {{
                background-color: {cls.COLORS['hover']};
            }}
            QHeaderView::section {{
                background-color: {cls.COLORS['light']};
                padding: 10px;
                border: 1px solid {cls.COLORS['border']};
                font-weight: 600;
            }}
        """
    
    @classmethod
    def input_style(cls):
        """优化的输入框样式"""
        return cls.get_cached_style("input_main", cls._create_input_style)
    
    @classmethod
    def _create_input_style(cls):
        """创建输入框样式"""
        return f"""
            QLineEdit, QTextEdit, QComboBox {{
                border: 1px solid {cls.COLORS['border']};
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 14px;
                background-color: {cls.COLORS['white']};
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border-color: {cls.COLORS['focus']};
                outline: 0;
                box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
            }}
            QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{
                background-color: {cls.COLORS['light']};
                color: {cls.COLORS['disabled']};
            }}
        """
    
    @classmethod
    def progress_style(cls):
        """优化的进度条样式"""
        return cls.get_cached_style("progress_main", cls._create_progress_style)
    
    @classmethod
    def _create_progress_style(cls):
        """创建进度条样式"""
        return f"""
            QProgressBar {{
                border: 1px solid {cls.COLORS['border']};
                border-radius: 4px;
                text-align: center;
                font-weight: bold;
                background-color: {cls.COLORS['light']};
            }}
            QProgressBar::chunk {{
                background-color: {cls.COLORS['success']};
                border-radius: 3px;
            }}
        """
    
    @classmethod
    def log_style(cls):
        """优化的日志显示样式"""
        return cls.get_cached_style("log_main", cls._create_log_style)
    
    @classmethod
    def _create_log_style(cls):
        """创建日志样式"""
        return f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid {cls.COLORS['border']};
                border-radius: 4px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 12px;
                padding: 8px;
            }}
        """
    
    @classmethod
    def tab_style(cls):
        """优化的选项卡样式"""
        return cls.get_cached_style("tab_main", cls._create_tab_style)
    
    @classmethod
    def _create_tab_style(cls):
        """创建选项卡样式"""
        return f"""
            QTabWidget::pane {{
                border: 1px solid {cls.COLORS['border']};
                border-radius: 4px;
                background-color: {cls.COLORS['white']};
            }}
            QTabBar::tab {{
                background-color: {cls.COLORS['light']};
                border: 1px solid {cls.COLORS['border']};
                border-bottom: none;
                border-radius: 4px 4px 0 0;
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {cls.COLORS['white']};
                border-bottom: 1px solid {cls.COLORS['white']};
            }}
            QTabBar::tab:hover {{
                background-color: {cls.COLORS['hover']};
            }}
        """
    
    @classmethod
    def group_box_style(cls):
        """优化的分组框样式"""
        return cls.get_cached_style("groupbox_main", cls._create_group_box_style)
    
    @classmethod
    def _create_group_box_style(cls):
        """创建分组框样式"""
        return f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {cls.COLORS['border']};
                border-radius: 4px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: {cls.COLORS['white']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {cls.COLORS['dark']};
            }}
        """
    
    @classmethod
    def main_window_style(cls):
        """主窗口样式"""
        return cls.get_cached_style("main_window", cls._create_main_window_style)
    
    @classmethod
    def _create_main_window_style(cls):
        """创建主窗口样式"""
        return f"""
            QMainWindow {{
                background-color: {cls.COLORS['light']};
            }}
            QWidget {{
                background-color: {cls.COLORS['white']};
            }}
            QFrame {{
                border: 1px solid {cls.COLORS['border']};
                border-radius: 4px;
            }}
        """
    
    @staticmethod
    def _darken_color(color: str, factor: float = 0.1) -> str:
        """使颜色变暗"""
        if color.startswith('#'):
            hex_color = color[1:]
            # 简化的颜色变暗算法
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            r = max(0, int(r * (1 - factor)))
            g = max(0, int(g * (1 - factor)))
            b = max(0, int(b * (1 - factor)))
            
            return f"#{r:02x}{g:02x}{b:02x}"
        return color
    
    @classmethod
    def apply_global_style(cls, app):
        """应用全局样式 - 一次性设置所有样式"""
        combined_style = f"""
            {cls.main_window_style()}
            {cls.button_style()}
            {cls.table_style()}
            {cls.input_style()}
            {cls.progress_style()}
            {cls.tab_style()}
            {cls.group_box_style()}
        """
        app.setStyleSheet(combined_style)
    
    @classmethod
    def get_frame_style(cls):
        """获取框架样式"""
        return cls.get_cached_style("frame_main", cls._create_frame_style)
    
    @classmethod
    def _create_frame_style(cls):
        """创建框架样式"""
        return f"""
            QFrame {{
                background-color: {cls.COLORS['white']};
                border: 1px solid {cls.COLORS['border']};
                border-radius: 4px;
                padding: 10px;
            }}
        """
    
    @classmethod
    def get_stats_frame_style(cls):
        """获取统计框架样式"""
        return cls.get_cached_style("stats_frame", cls._create_stats_frame_style)
    
    @classmethod
    def _create_stats_frame_style(cls):
        """创建统计框架样式"""
        return f"""
            QFrame {{
                background-color: {cls.COLORS['light']};
                border: 1px solid {cls.COLORS['border']};
                border-radius: 4px;
                padding: 8px;
                margin: 2px;
            }}
        """
    
    @classmethod
    def get_title_style(cls):
        """获取标题样式"""
        return cls.get_cached_style("title_main", cls._create_title_style)
    
    @classmethod
    def _create_title_style(cls):
        """创建标题样式"""
        return f"""
            QLabel {{
                font-size: 16px;
                font-weight: bold;
                color: {cls.COLORS['dark']};
                padding: 5px;
            }}
        """
    
    @classmethod
    def get_button_style(cls, style_type="primary", size="normal"):
        """获取按钮样式 - 保持兼容性"""
        return cls.button_style(style_type, size)
    
    @classmethod
    def get_table_style(cls):
        """获取表格样式 - 保持兼容性"""
        return cls.table_style()
    
    @classmethod
    def clear_cache(cls):
        """清除样式缓存"""
        cls._STYLE_CACHE.clear() 