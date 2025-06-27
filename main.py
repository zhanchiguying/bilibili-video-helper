#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频带货助手 v2.0
主程序入口 - 简化架构，适合exe打包
"""

import sys
import os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core import BilibiliUploaderApp, Config, get_logger
    from gui import MainWindow
except ImportError as e:
    print(f"导入模块失败: {e}")
    sys.exit(1)

def check_dependencies():
    """检查关键依赖"""
    missing = []
    
    try:
        import selenium
        import PyQt5
        # from cryptography.fernet import Fernet  # 🎯 已移除加密功能
    except ImportError as e:
        missing.append(str(e))
    
    return missing

def main():
    """主函数"""
    print(f"启动 {Config.APP_NAME} v{Config.APP_VERSION}")
    
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        print("缺少依赖:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("请运行: pip install -r requirements.txt")
        return 1
    
    # 创建Qt应用
    app = QApplication(sys.argv)
    app.setApplicationName(Config.APP_NAME)
    app.setApplicationVersion(Config.APP_VERSION)
    app.setStyle('Fusion')
    
    try:
        # 启动GUI界面
        main_window = MainWindow()
        main_window.show()
        
        # 运行应用
        result = app.exec_()
        return result
        
    except Exception as e:
        QMessageBox.critical(None, "启动失败", f"程序启动失败:\n{str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 