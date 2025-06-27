#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号数据适配器 - 统一处理dict和Account对象格式
消除代码重复，提供一致的访问接口
"""

from typing import Any, Dict, Optional, List


class AccountAdapter:
    """账号数据适配器 - 统一处理dict和Account对象格式"""
    
    def __init__(self, data: Dict[str, Any], manager, username: str):
        """
        初始化账号适配器
        
        Args:
            data: 原始账号数据(dict格式)
            manager: 账号管理器实例 
            username: 账号用户名
        """
        self._data = data
        self._manager = manager
        self.username = username
    
    @property
    def cookies(self) -> List[Dict[str, Any]]:
        """获取cookies"""
        return self._data.get('cookies', [])
    
    @cookies.setter
    def cookies(self, value: List[Dict[str, Any]]):
        """设置cookies"""
        self._data['cookies'] = value
    
    @property
    def status(self) -> str:
        """获取账号状态"""
        return self._data.get('status', 'inactive')
    
    @status.setter  
    def status(self, value: str):
        """设置账号状态"""
        self._data['status'] = value
    
    @property
    def last_login(self) -> int:
        """获取最后登录时间"""
        return self._data.get('last_login', 0)
    
    @last_login.setter
    def last_login(self, value: int):
        """设置最后登录时间"""
        self._data['last_login'] = value
    
    @property
    def fingerprint(self) -> Dict[str, Any]:
        """获取浏览器指纹"""
        return self._data.get('fingerprint', {})
    
    @fingerprint.setter
    def fingerprint(self, value: Dict[str, Any]):
        """设置浏览器指纹"""
        self._data['fingerprint'] = value
    
    @property
    def devtools_port(self) -> Optional[int]:
        """获取DevTools端口"""
        return self._data.get('devtools_port', None)
    
    @devtools_port.setter
    def devtools_port(self, value: Optional[int]):
        """设置DevTools端口"""
        self._data['devtools_port'] = value
    
    def __setattr__(self, name: str, value: Any):
        """动态属性设置"""
        if name in ['_data', '_manager', 'username']:
            super().__setattr__(name, value)
        elif name in ['browser_instance', '_browser_ready']:
            # 这些临时属性不保存到dict，仅存储在对象中
            super().__setattr__(name, value)
        else:
            # 其他属性保存到数据字典中
            if hasattr(self, '_data'):
                self._data[name] = value
            else:
                super().__setattr__(name, value)
    
    def __getattr__(self, name: str) -> Any:
        """动态属性获取"""
        if hasattr(self, '_data') and name in self._data:
            return self._data[name]
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return self._data.copy()
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"AccountAdapter(username={self.username}, status={self.status})"


def get_account_safely(raw_account: Any, manager, username: str):
    """
    安全获取账号对象 - 统一的访问接口
    
    Args:
        raw_account: 原始账号数据(可能是dict或Account对象)
        manager: 账号管理器实例
        username: 账号用户名
    
    Returns:
        统一的账号对象，支持所有必要的属性访问
    """
    if raw_account is None:
        return None
    
    if isinstance(raw_account, dict):
        # dict格式：使用适配器包装
        return AccountAdapter(raw_account, manager, username)
    else:
        # Account对象格式：直接返回
        return raw_account


def get_account_status_safely(account_data: Any) -> str:
    """
    安全获取账号状态 - 兼容所有格式
    
    Args:
        account_data: 账号数据(dict, Account对象, 或AccountAdapter)
    
    Returns:
        账号状态字符串
    """
    if not account_data:
        return 'inactive'
    
    if hasattr(account_data, '_data'):
        # AccountAdapter包装对象
        return account_data.status
    elif isinstance(account_data, dict):
        # 原始dict格式
        return account_data.get('status', 'inactive')
    else:
        # Account对象格式
        return getattr(account_data, 'status', 'inactive') 