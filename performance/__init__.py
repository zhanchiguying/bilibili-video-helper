#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能优化模块 - 简化版本，避免null字节问题
"""

class DummyManager:
    """虚拟性能管理器 - 提供兼容接口但不执行实际操作"""
    
    def __init__(self, *args, **kwargs):
        pass
    
    def add_warning_callback(self, callback):
        pass
    
    def get_stats(self):
        return {}
    
    def get(self, key, default=None):
        """缓存获取方法 - 返回默认值"""
        return default
    
    def set(self, key, value, ttl=None):
        """缓存设置方法 - 支持ttl参数，什么都不做"""
        pass
    
    def cleanup(self):
        pass

# 导出所有性能管理器类
CacheManager = DummyManager
TaskQueue = DummyManager  
ResourcePool = DummyManager
MemoryManager = DummyManager

__all__ = ['CacheManager', 'TaskQueue', 'ResourcePool', 'MemoryManager']
