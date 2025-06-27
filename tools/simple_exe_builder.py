#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXE构建器 - 创建纯净的独立EXE文件
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def build_main_exe():
    """构建主程序EXE"""
    print("🚀 开始构建主程序EXE...")
    
    # 项目根目录
    project_dir = Path(__file__).parent.parent
    temp_dir = project_dir / "build_temp"
    
    # 清理临时目录
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()
    
    try:
        # 使用系统Python
        system_python = r"D:\Program Files (x86)\python\python.exe"
        
        # 构建命令 - 只使用必要的参数
        cmd = [
            system_python, "-m", "PyInstaller",
            "--onefile",                    # 单文件模式
            "--windowed",                   # 无控制台窗口
            "--name=B站视频助手",           # EXE名称
            "--distpath=" + str(project_dir / "dist"),  # 输出目录
            "--workpath=" + str(temp_dir),  # 工作目录
            "--specpath=" + str(temp_dir),  # spec文件目录
            
            # 🎯 修复：不强制添加配置文件，让程序运行时自动创建
            # "--add-data=config.json;.",
            # "--add-data=accounts.json;.",
            # "--add-data=uploaded_videos.json;.",
            
            # 添加图标
            "--icon=" + str(project_dir / "icons" / "icon_32x32.png"),
            
            # 🎯 关键修复：添加图标文件到EXE包中，程序运行时需要
            "--add-data=" + str(project_dir / "icons") + ";icons",
            
            # 隐藏导入模块
            "--hidden-import=PyQt5.QtCore",
            "--hidden-import=PyQt5.QtGui", 
            "--hidden-import=PyQt5.QtWidgets",
            "--hidden-import=PyQt5.QtNetwork",
            "--hidden-import=selenium",
            "--hidden-import=selenium.webdriver",
            "--hidden-import=selenium.webdriver.chrome",
            "--hidden-import=selenium.webdriver.chrome.service",
            "--hidden-import=selenium.webdriver.common.by",
            "--hidden-import=selenium.webdriver.support.wait",
            "--hidden-import=selenium.webdriver.support.expected_conditions",
            "--hidden-import=cryptography",
            "--hidden-import=fake_useragent",
            "--hidden-import=webdriver_manager",
            "--hidden-import=webdriver_manager.chrome",
            
            # 项目模块
            "--hidden-import=core",
            "--hidden-import=core.app",
            "--hidden-import=core.config",
            "--hidden-import=core.logger",
            "--hidden-import=core.bilibili_video_uploader",
            "--hidden-import=core.bilibili_product_manager",
            "--hidden-import=core.browser_detector",
            "--hidden-import=core.fingerprint_validator",
            "--hidden-import=core.license_system",
            "--hidden-import=services",
            "--hidden-import=services.account_service",
            "--hidden-import=services.upload_service",
            "--hidden-import=services.license_service",
            "--hidden-import=services.file_service",
            "--hidden-import=services.settings_service",
            "--hidden-import=gui",
            "--hidden-import=gui.main_window",
            "--hidden-import=gui.tabs",
            "--hidden-import=gui.tabs.account_tab",
            "--hidden-import=gui.tabs.upload_tab",
            "--hidden-import=gui.tabs.license_tab",
            "--hidden-import=gui.tabs.log_tab",
            "--hidden-import=performance",
            "--hidden-import=performance.cache_manager",
            "--hidden-import=performance.task_queue",
            
            # 清理和确认选项
            "--clean",
            "--noconfirm",
            
            # 主入口文件
            str(project_dir / "main.py")
        ]
        
        print("📦 使用PyInstaller构建...")
        print(f"命令: {' '.join(cmd[:5])}...")
        
        # 运行构建
        result = subprocess.run(cmd, cwd=str(project_dir))
        
        if result.returncode == 0:
            exe_file = project_dir / "dist" / "B站视频助手.exe"
            if exe_file.exists():
                exe_size = exe_file.stat().st_size / (1024 * 1024)
                print(f"✅ 主程序构建成功！EXE大小: {exe_size:.1f} MB")
                return True
        
        print("❌ 主程序构建失败")
        return False
        
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

def build_license_exe():
    """构建许可证生成器EXE"""
    print("\n🔐 开始构建许可证生成器EXE...")
    
    project_dir = Path(__file__).parent.parent
    temp_dir = project_dir / "build_temp_license"
    
    # 清理临时目录
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()
    
    try:
        # 复制许可证生成器文件
        shutil.copy2(project_dir / "tools" / "license_gui.py", temp_dir / "main.py")
        
        # 复制核心文件到临时目录
        core_dir = temp_dir / "core"
        core_dir.mkdir()
        
        core_files = ["license_system.py", "fingerprint_validator.py", "config.py", "logger.py"]
        for file_name in core_files:
            src_file = project_dir / "core" / file_name
            if src_file.exists():
                shutil.copy2(src_file, core_dir)
        
        # 创建简化的__init__.py
        with open(core_dir / "__init__.py", 'w', encoding='utf-8') as f:
            f.write('''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心模块包（许可证生成器专用）
"""

from .license_system import LicenseSystem
from .config import Config  
from .logger import get_logger
from .fingerprint_validator import FingerprintValidator

__all__ = ['LicenseSystem', 'Config', 'get_logger', 'FingerprintValidator']
''')
        
        # 复制图标
        if (project_dir / "icons").exists():
            shutil.copytree(project_dir / "icons", temp_dir / "icons")
        
        # 使用系统Python构建
        system_python = r"D:\Program Files (x86)\python\python.exe"
        
        cmd = [
            system_python, "-m", "PyInstaller",
            "--onefile",
            "--windowed",
            "--name=B站许可证生成器",
            "--distpath=" + str(project_dir / "dist"),
            "--workpath=" + str(temp_dir / "work"),
            "--specpath=" + str(temp_dir),
            "--icon=" + str(project_dir / "icons" / "icon_32x32.png"),
            "--add-data=icons;icons",
            "--hidden-import=PyQt5.QtCore",
            "--hidden-import=PyQt5.QtGui",
            "--hidden-import=PyQt5.QtWidgets",
            "--hidden-import=cryptography",
            "--hidden-import=core.license_system",
            "--hidden-import=core.config",
            "--hidden-import=core.logger",
            "--hidden-import=core.fingerprint_validator",
            "--clean",
            "--noconfirm",
            "main.py"
        ]
        
        print("📦 构建许可证生成器...")
        result = subprocess.run(cmd, cwd=str(temp_dir))
        
        if result.returncode == 0:
            exe_file = project_dir / "dist" / "B站许可证生成器.exe"
            if exe_file.exists():
                exe_size = exe_file.stat().st_size / (1024 * 1024)
                print(f"✅ 许可证生成器构建成功！EXE大小: {exe_size:.1f} MB")
                return True
        
        print("❌ 许可证生成器构建失败")
        return False
        
    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

def create_exe_package():
    """创建完整的EXE包目录"""
    print("\n📦 创建EXE包...")
    
    project_dir = Path(__file__).parent.parent
    dist_dir = project_dir / "dist"
    package_dir = project_dir / "B站视频带货助手_EXE版"
    
    # 清理旧包
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()
    
    # 复制EXE文件
    for exe_name in ["B站视频助手.exe", "B站许可证生成器.exe"]:
        exe_file = dist_dir / exe_name
        if exe_file.exists():
            shutil.copy2(exe_file, package_dir)
            print(f"✅ 复制 {exe_name}")
    
    # 创建必要目录
    (package_dir / "videos").mkdir()
    (package_dir / "logs").mkdir()
    
    # 复制ms-playwright浏览器
    if (project_dir / "ms-playwright").exists():
        shutil.copytree(project_dir / "ms-playwright", package_dir / "ms-playwright")
        print("✅ 复制ms-playwright浏览器")
    
    # 复制ChromeDriver
    if (project_dir / "drivers").exists():
        shutil.copytree(project_dir / "drivers", package_dir / "drivers")
        print("✅ 复制ChromeDriver")
    
    # 创建启动脚本
    start_bat = '''@echo off
chcp 65001 >nul
title B站视频助手 v2.0
color 0A

echo.
echo ========================================
echo   B站视频助手 v2.0 纯净EXE版
echo ========================================
echo.

if not exist "B站视频助手.exe" (
    echo [错误] 找不到主程序文件
    pause
    exit /b 1
)

echo [信息] 启动程序...
echo 首次运行可能需要初始化
echo.

start "" "B站视频助手.exe"

echo [成功] 程序已启动
timeout /t 2 >nul
'''
    
    with open(package_dir / "启动程序.bat", 'w', encoding='utf-8') as f:
        f.write(start_bat)
    
    # 创建许可证生成器启动脚本
    license_bat = '''@echo off
chcp 65001 >nul
title B站许可证生成器
color 0B

echo.
echo ========================================
echo   B站许可证生成器 v2.0
echo ========================================
echo.

if not exist "B站许可证生成器.exe" (
    echo [错误] 找不到许可证生成器文件
    pause
    exit /b 1
)

echo [信息] 启动许可证生成器...
start "" "B站许可证生成器.exe"

echo [成功] 许可证生成器已启动
timeout /t 2 >nul
'''
    
    with open(package_dir / "启动许可证生成器.bat", 'w', encoding='utf-8') as f:
        f.write(license_bat)
    
    # 创建使用说明
    readme = '''# B站视频助手 v2.0 纯净EXE版

## 快速开始
1. 双击"启动程序.bat"启动程序
2. 或直接双击"B站视频助手.exe"
3. 在"账号管理"页面添加B站账号
4. 将视频文件放入videos文件夹开始上传

## 版本特点
- ✅ 纯净EXE文件，无需安装Python
- ✅ 独立浏览器环境，不影响系统浏览器
- ✅ 完整功能，支持批量上传和账号管理
- ✅ 包含许可证生成器工具

## 文件结构
├── B站视频助手.exe        # 主程序
├── B站许可证生成器.exe    # 许可证工具
├── ms-playwright/        # 浏览器环境
├── drivers/             # ChromeDriver
├── videos/              # 视频文件夹
└── logs/                # 日志文件夹

## 系统要求
- Windows 10/11（64位）
- 至少4GB可用内存
- 网络连接

## 文件命名规范
视频文件命名格式：商品ID----商品名称.mp4
例如：12345678----测试商品.mp4

## 故障排除
1. 如遇到启动问题，请检查Windows Defender设置
2. 确保网络连接正常
3. 首次运行需要较长初始化时间

版本：v2.0.0 纯净EXE版
构建日期：''' + str(__import__('datetime').datetime.now().strftime('%Y-%m-%d'))
    
    with open(package_dir / "使用说明.txt", 'w', encoding='utf-8') as f:
        f.write(readme)
    
    print(f"✅ EXE包创建完成: {package_dir}")

if __name__ == "__main__":
    print("🚀 B站视频助手 EXE构建器")
    print("=" * 50)
    
    # 构建主程序
    main_success = build_main_exe()
    
    # 构建许可证生成器
    license_success = build_license_exe()
    
    if main_success and license_success:
        # 创建完整包
        create_exe_package()
        
        print("\n" + "=" * 50)
        print("🎉 构建完成！")
        print("✅ 主程序EXE构建成功")
        print("✅ 许可证生成器EXE构建成功")
        print("✅ 完整EXE包已准备就绪")
        print("\n特点：")
        print("- 纯净EXE文件，无源码泄露")
        print("- 独立运行，无需Python环境")
        print("- 包含完整浏览器和驱动")
        print("=" * 50)
    else:
        print("\n❌ 构建失败!")
        print(f"主程序: {'成功' if main_success else '失败'}")
        print(f"许可证生成器: {'成功' if license_success else '失败'}")
    
    # 清理dist目录
    try:
        dist_dir = Path(__file__).parent.parent / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
            print("🧹 临时文件已清理")
    except:
        pass 