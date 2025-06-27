#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用工具函数 - 减少代码重复，提高可维护性
"""

import time
import hashlib
import random
import os
import socket
from typing import Dict, Any, Optional, List
from functools import wraps


def format_timestamp(timestamp: int = None) -> str:
    """
    格式化时间戳
    
    Args:
        timestamp: Unix时间戳，如果为None则使用当前时间
    
    Returns:
        格式化的时间字符串
    """
    if timestamp is None:
        timestamp = int(time.time())
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


def get_file_size_mb(file_path: str) -> float:
    """
    获取文件大小(MB)
    
    Args:
        file_path: 文件路径
    
    Returns:
        文件大小(MB)，文件不存在时返回0
    """
    try:
        if os.path.exists(file_path):
            return os.path.getsize(file_path) / (1024 * 1024)
    except Exception:
        pass
    return 0.0


def check_port_available(port: int, timeout: float = 1.0) -> bool:
    """
    检查端口是否可用
    
    Args:
        port: 端口号
        timeout: 超时时间(秒)
    
    Returns:
        True表示端口被占用，False表示端口可用
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex(('localhost', port))
            return result == 0  # 0表示连接成功（端口被占用）
    except Exception:
        return False


def generate_fixed_fingerprint(username: str) -> Dict[str, Any]:
    """
    为指定用户名生成固定的浏览器指纹
    
    Args:
        username: 用户名
    
    Returns:
        浏览器指纹字典
    """
    # 使用用户名作为种子，确保可重现性
    seed = int(hashlib.md5(username.encode()).hexdigest()[:8], 16)
    random.seed(seed)
    
    # 预定义选项池
    window_sizes = ["1920,1080", "1680,1050", "1536,864", "1440,900", "1366,768", "1280,800"]
    languages = [
        "zh-CN,zh;q=0.9,en;q=0.8",
        "zh-CN,zh;q=0.8,zh-TW;q=0.7,en;q=0.5"
    ]
    
    # 为确保稳定性，使用固定的Chrome版本User-Agent池
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ]
    
    # 基于种子选择固定的指纹组合
    fingerprint = {
        'user_agent': random.choice(user_agents),
        'window_size': random.choice(window_sizes),
        'language': random.choice(languages),
        'timezone': 'Asia/Shanghai',
        
        # 添加更多指纹特征以提高唯一性
        'viewport': random.choice(window_sizes),
        'screen_resolution': random.choice(["1920x1080", "1366x768", "1536x864"]),
        'color_depth': random.choice([24, 32]),
        'platform': "Win32",
        'webgl_vendor': "Google Inc. (Intel)",
        'webgl_renderer': random.choice([
            "ANGLE (Intel, Intel(R) HD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"
        ])
    }
    
    return fingerprint


def safe_get_attr(obj: Any, attr_name: str, default: Any = None) -> Any:
    """
    安全获取对象属性
    
    Args:
        obj: 对象
        attr_name: 属性名
        default: 默认值
    
    Returns:
        属性值或默认值
    """
    try:
        return getattr(obj, attr_name, default)
    except Exception:
        return default


def safe_dict_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    安全获取字典值
    
    Args:
        data: 字典
        key: 键名
        default: 默认值
    
    Returns:
        字典值或默认值
    """
    try:
        if isinstance(data, dict):
            return data.get(key, default)
    except Exception:
        pass
    return default


def cleanup_temp_files(directory: str, pattern: str = "*.tmp") -> int:
    """
    清理临时文件
    
    Args:
        directory: 目录路径
        pattern: 文件匹配模式
    
    Returns:
        清理的文件数量
    """
    import glob
    
    try:
        temp_files = glob.glob(os.path.join(directory, pattern))
        count = 0
        for file_path in temp_files:
            try:
                os.remove(file_path)
                count += 1
            except Exception:
                continue
        return count
    except Exception:
        return 0


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0):
    """
    失败重试装饰器
    
    Args:
        max_attempts: 最大尝试次数
        delay: 重试间隔(秒)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


def log_performance(logger, operation_name: str):
    """
    性能记录装饰器
    
    Args:
        logger: 日志记录器
        operation_name: 操作名称
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"✅ {operation_name} 完成，耗时: {duration:.2f}秒")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"❌ {operation_name} 失败，耗时: {duration:.2f}秒, 错误: {e}")
                raise
        return wrapper
    return decorator


class SimpleCache:
    """简单的内存缓存"""
    
    def __init__(self, timeout: int = 300):
        """
        初始化缓存
        
        Args:
            timeout: 缓存超时时间(秒)
        """
        self._cache = {}
        self._timestamps = {}
        self._timeout = timeout
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        if key in self._cache:
            # 检查是否过期
            if time.time() - self._timestamps[key] < self._timeout:
                return self._cache[key]
            else:
                # 过期，清除
                self.remove(key)
        return default
    
    def set(self, key: str, value: Any):
        """设置缓存值"""
        self._cache[key] = value
        self._timestamps[key] = time.time()
    
    def remove(self, key: str):
        """删除缓存项"""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._timestamps.clear()
    
    def size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)


def validate_video_file(file_path: str) -> bool:
    """
    验证视频文件是否有效
    
    Args:
        file_path: 视频文件路径
    
    Returns:
        True表示文件有效
    """
    if not os.path.exists(file_path):
        return False
    
    # 检查文件大小
    if os.path.getsize(file_path) < 1024:  # 小于1KB认为无效
        return False
    
    # 检查文件扩展名
    valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']
    _, ext = os.path.splitext(file_path.lower())
    return ext in valid_extensions


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 文件大小(字节)
    
    Returns:
        格式化的文件大小字符串
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB" 