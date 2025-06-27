#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI模块 - 界面组件包
"""

from .tabs import *

# 🎯 直接从main_window模块导入MainWindow类
try:
    from .main_window import MainWindow
    __all__ = ['MainWindow']
except ImportError as e:
    print(f"无法导入MainWindow: {e}")
    # 提供一个占位符以防导入失败
    class MainWindow:
        def __init__(self):
            raise ImportError(f"MainWindow导入失败: {e}")
    __all__ = ['MainWindow'] 