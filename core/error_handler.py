"""
错误处理管理器
统一处理应用程序中的异常和错误
"""

import logging
import traceback
from typing import Optional, Callable
from functools import wraps

class ErrorHandler:
    """错误处理管理器"""
    
    def __init__(self, logger_name: str = "BilibiliUploader"):
        self.logger = logging.getLogger(logger_name)
        self.status_callback: Optional[Callable] = None
    
    def set_status_callback(self, callback: Callable):
        """设置状态回调函数"""
        self.status_callback = callback
    
    def handle_exception(self, e: Exception, context: str = "", emit_status: bool = True) -> str:
        """
        统一处理异常
        :param e: 异常对象
        :param context: 异常上下文
        :param emit_status: 是否发送状态消息
        :return: 格式化的错误消息
        """
        error_type = type(e).__name__
        error_msg = str(e)
        
        # 格式化错误消息
        if context:
            formatted_msg = f"{context}: {error_type} - {error_msg}"
        else:
            formatted_msg = f"{error_type}: {error_msg}"
        
        # 记录到日志
        self.logger.error(formatted_msg)
        self.logger.debug(f"Traceback: {traceback.format_exc()}")
        
        # 发送状态消息
        if emit_status and self.status_callback:
            self.status_callback(f"❌ {formatted_msg}")
        
        return formatted_msg
    
    def safe_execute(self, func: Callable, *args, default=None, context: str = "", **kwargs):
        """
        安全执行函数，自动处理异常
        :param func: 要执行的函数
        :param args: 函数参数
        :param default: 发生异常时返回的默认值
        :param context: 执行上下文
        :param kwargs: 函数关键字参数
        :return: 函数结果或默认值
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.handle_exception(e, context)
            return default
    
    def retry_on_failure(self, max_retries: int = 3, delay: float = 1.0):
        """
        装饰器：失败时重试
        :param max_retries: 最大重试次数
        :param delay: 重试间隔（秒）
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_retries:
                            if self.status_callback:
                                self.status_callback(f"⚠️ 第{attempt + 1}次尝试失败，{delay}秒后重试...")
                            import time
                            time.sleep(delay)
                        else:
                            self.handle_exception(e, f"函数 {func.__name__} 重试{max_retries}次后仍失败")
                
                return None
            return wrapper
        return decorator


def with_error_handling(context: str = "", emit_status: bool = True):
    """
    装饰器：为函数添加错误处理
    :param context: 错误上下文
    :param emit_status: 是否发送状态消息
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                # 如果对象有error_handler属性，使用它
                if hasattr(self, 'error_handler'):
                    self.error_handler.handle_exception(e, context or f"执行 {func.__name__}", emit_status)
                else:
                    # 否则简单打印错误
                    error_msg = f"{context or func.__name__}执行失败: {str(e)}"
                    print(error_msg)
                    # 如果有upload_status.emit方法，使用它
                    if hasattr(self, 'upload_status') and emit_status:
                        self.upload_status.emit(f"❌ {error_msg}")
                return None
        return wrapper
    return decorator


# 全局错误处理器实例
_global_error_handler = ErrorHandler()

def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    return _global_error_handler 