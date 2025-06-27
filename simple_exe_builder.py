#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的EXE构建器 - 使用系统Python避免路径问题
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def build_simple_exe():
    """构建简化的EXE"""
    print("开始构建EXE...")
    
    # 创建英文路径的临时目录
    temp_dir = Path("C:/temp_bili_build")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()
    
    try:
        # 复制必要文件
        current_dir = Path(__file__).parent
        
        # 完整复制core目录（确保所有文件都复制）
        print("复制core目录...")
        shutil.copytree(current_dir / "core", temp_dir / "core")
        
        # 复制主要Python文件
        main_files = ["main.py", "gui.py"]
        for file_name in main_files:
            src_file = current_dir / file_name
            if src_file.exists():
                shutil.copy2(src_file, temp_dir)
                print(f"复制文件: {file_name}")
            else:
                print(f"文件不存在，跳过: {file_name}")
        
        # 复制配置文件
        config_files = ["config.json", "accounts.json", "uploaded_videos.json"]
        for file_name in config_files:
            src_file = current_dir / file_name
            if src_file.exists():
                shutil.copy2(src_file, temp_dir)
            else:
                # 创建空配置文件
                with open(temp_dir / file_name, 'w', encoding='utf-8') as f:
                    if file_name.endswith('.json'):
                        f.write('{}')
        
        # 不复制ms-playwright到临时目录（将通过独立方式提供）
        print("跳过ms-playwright复制（将作为独立文件包提供）")
        
        # 复制匹配版本的ChromeDriver
        drivers_dir = temp_dir / "drivers"
        drivers_dir.mkdir(exist_ok=True)
        if (current_dir / "drivers" / "chromedriver.exe").exists():
            shutil.copy2(current_dir / "drivers" / "chromedriver.exe", drivers_dir / "chromedriver.exe")
            print("✅ 已复制匹配版本的ChromeDriver (139.0.7246.0)")
        
        # 复制图标文件
        icons_dir = temp_dir / "icons"
        if (current_dir / "icons").exists():
            shutil.copytree(current_dir / "icons", icons_dir)
            print("✅ 已复制程序图标文件")
        else:
            print("⚠️ 图标文件夹不存在，跳过图标复制")
        
        # 创建目录
        (temp_dir / "videos").mkdir()
        (temp_dir / "logs").mkdir()
        
        # 切换到临时目录
        os.chdir(temp_dir)
        
        # 使用系统Python
        system_python = r"D:\Program Files (x86)\python\python.exe"
        
        # 构建命令 - 添加更多隐藏导入
        cmd = [
            system_python, "-m", "PyInstaller",
            "--onefile",
            "--windowed",
            "--name=BilibiliUploader",
            "--add-data=core;core",
            "--add-data=config.json;.",
            "--add-data=accounts.json;.",
            "--add-data=uploaded_videos.json;.",
        ]
        
        # 添加图标（如果存在）
        icon_file = temp_dir / "icons" / "app_icon.ico"
        if icon_file.exists():
            cmd.append(f"--icon={icon_file}")
            print(f"✅ 已添加程序图标: {icon_file}")
        else:
            print("⚠️ 未找到图标文件，使用默认图标")
        
        # 添加图标文件夹到数据
        if (temp_dir / "icons").exists():
            cmd.append("--add-data=icons;icons")
        
        # 继续添加其他参数
        additional_args = [
            "--hidden-import=PyQt5.QtCore",
            "--hidden-import=PyQt5.QtGui",
            "--hidden-import=PyQt5.QtWidgets",
            "--hidden-import=PyQt5.QtNetwork",
            "--hidden-import=selenium",
            "--hidden-import=selenium.webdriver",
            "--hidden-import=selenium.webdriver.chrome",
            "--hidden-import=selenium.webdriver.chrome.options",
            "--hidden-import=selenium.webdriver.chrome.service",
            "--hidden-import=selenium.webdriver.common.by",
            "--hidden-import=selenium.webdriver.support.wait",
            "--hidden-import=selenium.webdriver.support.expected_conditions",
            "--hidden-import=cryptography",
            # "--hidden-import=cryptography.fernet",  # 🎯 已移除加密功能
            "--hidden-import=fake_useragent",
            "--hidden-import=webdriver_manager",
            "--hidden-import=webdriver_manager.chrome",
            "--hidden-import=core.app",
            "--hidden-import=core.config",
            "--hidden-import=core.logger",
            "--hidden-import=core.bilibili_video_uploader",
            "--hidden-import=core.bilibili_product_manager",
            "--hidden-import=core.browser_detector",
            "--hidden-import=core.fingerprint_validator",
            "--hidden-import=core.license_system",
            "--clean",
            "--noconfirm",
            "main.py"
        ]
        
        # 合并所有命令参数
        cmd.extend(additional_args)
        
        print("使用系统Python构建...")
        print(f"命令: {' '.join(cmd[:5])}...")
        
        # 运行构建
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        result = subprocess.run(cmd, env=env, cwd=str(temp_dir))
        
        if result.returncode == 0:
            # 复制结果到原目录
            exe_file = temp_dir / "dist" / "BilibiliUploader.exe"
            if exe_file.exists():
                target_dir = current_dir / "B站视频带货助手_完整EXE版"
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                target_dir.mkdir()
                
                shutil.copy2(exe_file, target_dir / "B站视频带货助手.exe")
                (target_dir / "videos").mkdir()
                (target_dir / "logs").mkdir()
                
                # 复制ms-playwright作为独立目录
                if (current_dir / "ms-playwright").exists():
                    print("复制ms-playwright到EXE版目录...")
                    shutil.copytree(current_dir / "ms-playwright", target_dir / "ms-playwright")
                    print("✅ ms-playwright已作为独立文件夹复制")
                
                # 复制upgrade_ms_playwright.py工具
                if (current_dir / "upgrade_ms_playwright.py").exists():
                    shutil.copy2(current_dir / "upgrade_ms_playwright.py", target_dir)
                    print("✅ 已复制浏览器升级工具")
                
                # Chrome修复工具已移除，程序内置自动修复机制
                
                # 复制示例视频
                if (current_dir / "videos").exists():
                    for video in list((current_dir / "videos").glob("*.mp4"))[:2]:
                        try:
                            shutil.copy2(video, target_dir / "videos")
                        except:
                            pass
                
                # 创建启动脚本（移除emoji字符）
                start_bat = '''@echo off
chcp 65001 >nul
title B站视频带货助手 v2.0
color 0A

echo.
echo =========================================
echo    B站视频带货助手 v2.0 完整EXE版
echo =========================================
echo.

:: 检查浏览器文件夹
if not exist "ms-playwright\\chromium-139" (
    echo [警告] 未找到浏览器文件夹
    echo.
    echo 解决方案：
    echo 1. 运行 upgrade_ms_playwright.py 自动下载
    echo 2. 或在程序中使用浏览器诊断功能
    echo.
    echo 继续启动程序...
    timeout /t 3 >nul
)

echo [信息] 启动程序...
echo 首次运行可能需要2-3分钟初始化
echo.

start "" "B站视频带货助手.exe"

echo [成功] 程序已启动
echo.
echo 提示：
echo - 独立浏览器文件夹，不占用EXE体积
echo - 如被杀毒软件拦截请添加信任
echo - 如果登录失败，使用浏览器诊断功能
echo - 如有问题请联系技术支持
echo.
timeout /t 3 >nul
'''
                with open(target_dir / "启动程序.bat", 'w', encoding='utf-8') as f:
                    f.write(start_bat)
                
                # 创建使用说明
                readme = '''# B站视频带货助手 v2.0 完整EXE版

## 快速开始
1. 双击"启动程序.bat"启动程序
2. 或直接双击"B站视频带货助手.exe"
3. 首次运行需要2-3分钟初始化
4. 在"账号管理"页面添加B站账号

## 浏览器配置
- 包含独立的ms-playwright浏览器文件夹
- 内置智能Chrome启动修复系统
- 可使用程序内的"🔍 浏览器诊断"功能检查状态

## Chrome启动问题解决
如果程序启动时遇到浏览器问题：
1. 使用程序内置的智能修复机制
2. 点击"🔍 浏览器诊断"按钮检查状态
3. 程序会自动配置最佳的Chrome启动方式

## 特色功能
- 完全免安装，开箱即用
- 智能Chrome启动修复
- 独立浏览器文件夹，不占用EXE体积
- 无需安装Python或其他依赖
- 支持批量视频上传
- 包含许可证生成器

## 使用方法
1. 将视频文件放入videos文件夹
2. 文件命名格式：商品ID----商品名称.mp4
3. 在软件中选择账号和视频开始上传

## 故障排除
1. Chrome启动问题：程序内置自动修复机制
2. 登录失败：点击"🔍 浏览器诊断"按钮
3. 浏览器文件缺失：运行"upgrade_ms_playwright.py"
4. 网络连接异常：尝试切换到手机热点

## 启动方式说明
- 启动程序.bat：标准启动方式
- 直接运行exe：适合高级用户
- 程序内置智能Chrome修复机制

## 系统要求
- Windows 10/11（64位）
- 至少4GB可用内存
- 网络连接

版本：v2.0.0 完整EXE版（内置智能修复）
'''
                with open(target_dir / "使用说明.txt", 'w', encoding='utf-8') as f:
                    f.write(readme)
                
                # 计算文件大小
                exe_size = exe_file.stat().st_size / (1024 * 1024)
                print(f"成功！EXE文件大小: {exe_size:.1f} MB")
                print(f"完整包位置: {target_dir}")
                return True
        
        print("构建失败")
        return False
        
    finally:
        # 清理
        try:
            os.chdir(Path(__file__).parent)
            shutil.rmtree(temp_dir)
        except:
            pass

def build_license_exe():
    """构建许可证生成器EXE"""
    print("\n开始构建许可证生成器EXE...")
    
    temp_dir = Path("C:/temp_license_build")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()
    
    try:
        current_dir = Path(__file__).parent
        
        # 复制许可证生成器文件（使用现有的license_gui.py）
        shutil.copy2(current_dir / "license_gui.py", temp_dir / "main.py")
        
        # 创建独立的core目录，只包含许可证相关文件
        core_dir = temp_dir / "core"
        core_dir.mkdir()
        
        # 只复制许可证生成器需要的核心文件
        core_files = [
            "license_system.py", 
            "fingerprint_validator.py", 
            "config.py", 
            "logger.py",
            "button_utils.py"  # 添加button_utils以防将来需要
        ]
        
        for file_name in core_files:
            src_file = current_dir / "core" / file_name
            if src_file.exists():
                shutil.copy2(src_file, core_dir)
                print(f"复制核心文件: {file_name}")
        
        # 创建许可证生成器专用的__init__.py（不导入app模块）
        license_init_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站许可证生成器 - 核心模块包（简化版）
"""

from .license_system import LicenseSystem
from .config import Config  
from .logger import get_logger
from .fingerprint_validator import FingerprintValidator

__version__ = "2.0.0"
__all__ = ['LicenseSystem', 'Config', 'get_logger', 'FingerprintValidator']
'''
        
        with open(core_dir / "__init__.py", 'w', encoding='utf-8') as f:
            f.write(license_init_content)
        print("创建许可证专用__init__.py")
        
        os.chdir(temp_dir)
        
        # 复制图标文件到许可证生成器目录
        if (current_dir / "icons").exists():
            shutil.copytree(current_dir / "icons", temp_dir / "icons")
            print("✅ 已复制图标文件到许可证生成器")
        
        # 使用系统Python构建许可证生成器
        system_python = r"D:\Program Files (x86)\python\python.exe"
        
        cmd = [
            system_python, "-m", "PyInstaller",
            "--onefile",
            "--windowed",
            "--name=BilibiliLicenseGenerator",
            "--add-data=core;core",
        ]
        
        # 添加图标（如果存在）
        icon_file = temp_dir / "icons" / "app_icon.ico"
        if icon_file.exists():
            cmd.append(f"--icon={icon_file}")
            cmd.append("--add-data=icons;icons")
            print(f"✅ 许可证生成器已添加图标: {icon_file}")
        
        # 添加其他参数
        additional_license_args = [
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
        
        cmd.extend(additional_license_args)
        
        print("构建许可证生成器...")
        result = subprocess.run(cmd, cwd=str(temp_dir))
        
        if result.returncode == 0:
            exe_file = temp_dir / "dist" / "BilibiliLicenseGenerator.exe"
            if exe_file.exists():
                target_dir = current_dir / "B站视频带货助手_完整EXE版"
                if target_dir.exists():
                    shutil.copy2(exe_file, target_dir / "B站许可证生成器.exe")
                    
                    # 创建许可证生成器启动脚本
                    license_bat = '''@echo off
chcp 65001 >nul
title B站许可证生成器
color 0B

echo.
echo =========================================
echo    B站许可证生成器 v2.0
echo =========================================
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
                    with open(target_dir / "启动许可证生成器.bat", 'w', encoding='utf-8') as f:
                        f.write(license_bat)
                    
                    print("许可证生成器EXE创建成功")
                    return True
        
        print("许可证生成器构建失败")
        return False
        
    finally:
        try:
            os.chdir(Path(__file__).parent)
            shutil.rmtree(temp_dir)
        except:
            pass

if __name__ == "__main__":
    # 构建主程序
    main_success = build_simple_exe()
    
    # 构建许可证生成器
    license_success = build_license_exe()
    
    print("\n" + "="*50)
    print("构建完成:")
    print(f"主程序: {'成功' if main_success else '失败'}")
    print(f"许可证生成器: {'成功' if license_success else '失败'}")
    
    if main_success:
        print("\n完整EXE版本已准备就绪!")
        print("包含内容:")
        print("- B站视频带货助手.exe (主程序)")
        if license_success:
            print("- B站许可证生成器.exe (许可证工具)")
        print("- 内置ms-playwright浏览器")
        print("- 完整使用说明")
    print("="*50) 