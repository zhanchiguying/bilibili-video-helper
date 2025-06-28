#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频带货助手 v2.0
主程序入口 - 简化架构，适合exe打包
"""

import sys
import os
import logging
import traceback
import signal
import atexit
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QTimer

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 🔧 新增：全局异常监控
def setup_global_exception_monitoring():
    """设置全局异常监控，确保能捕获所有退出原因"""
    
    # 创建专门的异常日志文件
    exception_log_path = Path("logs") / "exceptions.log"
    exception_log_path.parent.mkdir(exist_ok=True)
    
    # 设置异常日志记录器
    exception_logger = logging.getLogger('global_exceptions')
    exception_logger.setLevel(logging.ERROR)
    
    # 创建异常日志处理器
    exception_handler = logging.FileHandler(exception_log_path, encoding='utf-8')
    exception_formatter = logging.Formatter(
        '%(asctime)s - CRITICAL - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    exception_handler.setFormatter(exception_formatter)
    exception_logger.addHandler(exception_handler)
    
    def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
        """处理未捕获的异常"""
        if issubclass(exc_type, KeyboardInterrupt):
            exception_logger.error("程序被用户中断 (Ctrl+C)")
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # 记录详细的异常信息
        exception_logger.error("🚨 程序发生未捕获异常，即将退出:")
        exception_logger.error(f"异常类型: {exc_type.__name__}")
        exception_logger.error(f"异常信息: {exc_value}")
        exception_logger.error("完整堆栈:")
        
        # 记录完整的异常堆栈
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        for line in tb_lines:
            exception_logger.error(line.rstrip())
        
        exception_logger.error("=" * 80)
        
        # 继续使用默认的异常处理
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    def handle_signal(signum, frame):
        """处理系统信号"""
        signal_names = {
            signal.SIGTERM: "SIGTERM (程序被终止)",
            signal.SIGINT: "SIGINT (Ctrl+C中断)",
        }
        
        if hasattr(signal, 'SIGBREAK'):  # Windows特有
            signal_names[signal.SIGBREAK] = "SIGBREAK (Ctrl+Break中断)"
        
        signal_name = signal_names.get(signum, f"信号 {signum}")
        exception_logger.error(f"🚨 程序收到系统信号: {signal_name}")
        exception_logger.error("=" * 80)
    
    def log_normal_exit():
        """记录正常退出"""
        exception_logger.error("✅ 程序正常退出")
    
    # 设置全局异常处理器
    sys.excepthook = handle_unhandled_exception
    
    # 设置信号处理器
    try:
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, handle_signal)
    except Exception:
        pass  # 某些环境可能不支持信号处理
    
    # 注册正常退出处理
    atexit.register(log_normal_exit)
    
    return exception_logger

def is_frozen():
    """检测是否在PyInstaller打包的EXE环境中运行"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

try:
    from core.app import BilibiliUploaderApp
    from core.config import Config  
    from core.logger import get_logger
    
    # 🎯 简化导入：直接从gui模块导入MainWindow
    from gui import MainWindow

except ImportError as e:
    print(f"导入模块失败: {e}")
    import traceback
    traceback.print_exc()
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
    # 🔧 首先设置全局异常监控
    try:
        exception_logger = setup_global_exception_monitoring()
        exception_logger.error("🚀 B站视频助手启动，异常监控已激活")
    except Exception as e:
        print(f"异常监控设置失败: {e}")
        exception_logger = None
    
    print(f"启动 {Config.APP_NAME} v{Config.APP_VERSION}")
    
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        print("缺少依赖:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("请运行: pip install -r requirements.txt")
        if exception_logger:
            exception_logger.error(f"❌ 依赖检查失败: {missing_deps}")
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
        
        if exception_logger:
            exception_logger.error("✅ 主窗口已显示，进入事件循环")
        
        # 🔧 添加定期存活检查
        if exception_logger:
            def heartbeat():
                exception_logger.error("💓 程序存活检查")
            
            heartbeat_timer = QTimer()
            heartbeat_timer.timeout.connect(heartbeat)
            heartbeat_timer.start(5 * 60 * 1000)  # 每5分钟一次心跳
        
        # 运行应用
        result = app.exec_()
        
        if exception_logger:
            exception_logger.error(f"🏁 事件循环结束，退出码: {result}")
        
        return result
        
    except Exception as e:
        error_msg = f"程序启动失败: {str(e)}"
        print(error_msg)
        
        if exception_logger:
            exception_logger.error(f"❌ {error_msg}")
            exception_logger.error("启动异常堆栈:")
            exception_logger.error(traceback.format_exc())
        
        QMessageBox.critical(None, "启动失败", error_msg)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 