"""
UI配置常量 - 性能优化版本
管理界面相关的常量，避免硬编码，提升性能
"""

from typing import Optional

class UIConfig:
    """UI配置类 - 优化版本"""
    
    # 窗口配置 - 优化宽度，让界面更紧凑
    WINDOW_WIDTH = 1080  # 从1200减少到1080，更适合显示
    WINDOW_HEIGHT = 800
    WINDOW_X = -1  # -1 表示自动居中
    WINDOW_Y = -1  # -1 表示自动居中
    
    # 组件尺寸
    VIDEO_LIST_MAX_HEIGHT = 200
    TABLE_COLUMN_WIDTHS = {
        'account_name': 120,
        'login_status': 120,
        'browser_status': 120,
        'last_login': 180  # 从150增加到180，确保最后登录时间完整显示
    }
    
    # 🚀 优化后的延时配置（大幅减少延迟）
    PAGE_LOAD_DELAY = 2  # 从5秒减少到2秒
    BUTTON_CLICK_DELAY = 0.5  # 从1秒减少到0.5秒
    STATUS_UPDATE_INTERVAL = 1  # 从2秒减少到1秒
    
    # 🎯 智能等待策略
    SMART_WAIT_CONFIG = {
        'fast_check': 0.2,      # 快速检查间隔
        'normal_check': 1,      # 普通检查间隔
        'slow_check': 3,        # 慢速检查间隔
        'max_fast_attempts': 10, # 快速检查最大次数
        'max_normal_attempts': 5, # 普通检查最大次数
    }
    
    # 超时配置（秒）- 优化
    BROWSER_CONNECT_TIMEOUT = 20  # 从30秒减少到20秒
    UPLOAD_TIMEOUT = 600  # 保持10分钟（上传需要足够时间）
    LOGIN_TIMEOUT = 30    # 从60秒减少到30秒
    
    # 🎯 新增：智能重试配置
    RETRY_CONFIG = {
        'max_retries': 3,
        'retry_delay': 1,
        'exponential_backoff': True
    }
    
    # 字体配置
    LOG_FONT_FAMILY = "Consolas"
    LOG_FONT_SIZE = 9
    
    # 状态消息
    STATUS_MESSAGES = {
        'ready': '准备就绪',
        'uploading': '上传中...',
        'success': '上传成功',
        'failed': '上传失败',
        'connecting': '连接中...',
        'waiting': '等待中...'
    }
    
    # 日志级别颜色
    LOG_COLORS = {
        'ERROR': 'red',
        'WARNING': 'orange', 
        'SUCCESS': 'green',
        'INFO': 'black'
    }
    
    # 支持的视频格式
    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
    
    # UI文本
    UI_TEXT = {
        'account_management': '账号管理',
        'browser_upload': '浏览器上传',
        'run_log': '运行日志',
        'add_account': '➕ 添加账号',
        'login_account': '🔑 登录账号',
        'remove_account': '🗑️ 删除账号',
        'detect_browser': '🔍 检测浏览器',
        'refresh_status': '🔄 刷新状态',
        'select_directory': '📁 选择目录',
        'start_upload': '🚀 开始浏览器上传',
        'pause_upload': '⏸️ 暂停',
        'stop_upload': '⏹️ 停止'
    } 


class SmartWaitManager:
    """智能等待管理器 - 替代固定sleep"""
    
    @staticmethod
    def smart_sleep(base_time: float, condition_check=None, max_time: Optional[float] = None):
        """
        智能睡眠：根据条件动态调整等待时间
        
        Args:
            base_time: 基础等待时间
            condition_check: 检查函数，返回True时停止等待
            max_time: 最大等待时间
        """
        import time
        
        if condition_check is None:
            # 如果没有条件检查，直接使用优化的基础时间
            optimized_time = base_time * 0.7  # 减少30%
            time.sleep(optimized_time)
            return
        
        max_time = max_time if max_time is not None else base_time * 2
        elapsed = 0
        check_interval = UIConfig.SMART_WAIT_CONFIG['fast_check']
        
        while elapsed < max_time:
            if condition_check():
                return  # 条件满足，立即返回
            
            time.sleep(check_interval)
            elapsed += check_interval
            
            # 动态调整检查间隔
            if elapsed > base_time:
                check_interval = UIConfig.SMART_WAIT_CONFIG['normal_check']
    
    @staticmethod
    def wait_for_element_optimized(driver, selector, timeout=10, condition="clickable"):
        """优化的元素等待"""
        from selenium.webdriver.support.wait import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        # 使用智能等待策略
        fast_timeout = min(3, timeout // 3)
        
        try:
            # 快速尝试
            if condition == "clickable":
                return WebDriverWait(driver, fast_timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
            elif condition == "present":
                return WebDriverWait(driver, fast_timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
        except:
            # 快速尝试失败，使用完整超时
            if condition == "clickable":
                return WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
            elif condition == "present":
                return WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                ) 