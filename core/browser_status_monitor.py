#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
浏览器状态监控器 - 专门监控DevTools端口状态
"""

import time
import threading
import requests
from typing import Dict, Optional, Callable
from PyQt5.QtCore import QObject, pyqtSignal

from .logger import get_logger

class BrowserStatusMonitor(QObject):
    """专用浏览器状态监控器 - 独立线程监控DevTools端口"""
    
    # 信号定义
    browser_status_changed = pyqtSignal(str, bool)  # 账号名, 是否活跃
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        
        # 监控状态
        self.monitoring = False
        self.monitor_thread = None
        
        # 账号端口绑定 {账号名: 端口号}
        self.account_ports: Dict[str, int] = {}
        
        # 状态缓存 {账号名: 是否活跃}
        self.status_cache: Dict[str, bool] = {}
        
        # 待更新的状态变化 {账号名: 是否活跃}
        self.pending_updates: Dict[str, bool] = {}
        
        # 线程锁
        self.lock = threading.Lock()
        
        self.logger.info("🔧 浏览器状态监控器初始化完成")
    
    def bind_account_port(self, account_name: str, devtools_port: int):
        """绑定账号的专属DevTools端口"""
        with self.lock:
            old_port = self.account_ports.get(account_name)
            self.account_ports[account_name] = devtools_port
            
            if old_port != devtools_port:
                self.logger.info(f"🔗 绑定账号端口: {account_name} -> {devtools_port}")
                
                # 立即检测一次状态
                is_active = self._check_port_status(devtools_port)
                old_status = self.status_cache.get(account_name, False)
                self.status_cache[account_name] = is_active
                
                # 如果状态有变化，发送信号
                if old_status != is_active:
                    self.browser_status_changed.emit(account_name, is_active)
                    self.logger.info(f"🔄 端口绑定后状态: {account_name} -> {'活跃' if is_active else '未活跃'}")
    
    def unbind_account(self, account_name: str):
        """取消账号绑定"""
        with self.lock:
            if account_name in self.account_ports:
                del self.account_ports[account_name]
                self.logger.info(f"🗑️ 取消账号端口绑定: {account_name}")
            
            if account_name in self.status_cache:
                del self.status_cache[account_name]
    
    def get_account_status(self, account_name: str) -> bool:
        """获取账号当前状态"""
        with self.lock:
            return self.status_cache.get(account_name, False)
    
    def notify_status_change(self, account_name: str, is_active: bool):
        """立即通知状态变化 - 用于浏览器创建后的即时同步"""
        with self.lock:
            old_status = self.status_cache.get(account_name, False)
            self.status_cache[account_name] = is_active
        
        # 立即发送状态变化信号，不管是否有变化（用于强制同步）
        self.browser_status_changed.emit(account_name, is_active)
        status_text = "活跃" if is_active else "未活跃"
        self.logger.info(f"🚀 立即同步浏览器状态: {account_name} -> {status_text}")
    
    def start_monitoring(self):
        """启动监控线程"""
        if self.monitoring:
            self.logger.warning("浏览器状态监控已在运行")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("🚀 浏览器状态监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("⏹️ 浏览器状态监控已停止")
    
    def _monitor_loop(self):
        """监控主循环 - 优化版：快速响应并简化检查逻辑"""
        self.logger.info("🔍 浏览器状态监控循环开始 (快速响应版)")
        
        while self.monitoring:
            try:
                with self.lock:
                    accounts_to_check = list(self.account_ports.items())
                    self.pending_updates.clear()  # 清空待更新列表
                
                # 🔧 优化：每次检查所有账号，但缩短间隔
                if accounts_to_check:
                    self.logger.debug(f"🔍 检查 {len(accounts_to_check)} 个账号状态")
                    
                    # 检查所有账号状态
                    for account_name, devtools_port in accounts_to_check:
                        try:
                            # 检测端口状态
                            is_active = self._check_port_status(devtools_port)
                            
                            # 获取之前的状态
                            old_status = self.status_cache.get(account_name, False)
                            
                            # 更新缓存
                            with self.lock:
                                self.status_cache[account_name] = is_active
                            
                            # 如果状态有变化，添加到待更新列表
                            if old_status != is_active:
                                with self.lock:
                                    self.pending_updates[account_name] = is_active
                                status_text = "活跃" if is_active else "未活跃"
                                self.logger.info(f"🔄 浏览器状态变化: {account_name} -> {status_text} (端口: {devtools_port})")
                            else:
                                # DEBUG级别记录保持状态
                                status_text = "活跃" if is_active else "未活跃"
                                self.logger.debug(f"🔍 浏览器状态保持: {account_name} -> {status_text}")
                                
                        except Exception as e:
                            self.logger.error(f"检查账号 {account_name} 端口 {devtools_port} 时异常: {e}")
                    
                    # 批量发送状态变化信号
                    with self.lock:
                        if self.pending_updates:
                            for account_name, is_active in self.pending_updates.items():
                                self.browser_status_changed.emit(account_name, is_active)
                            self.logger.info(f"📊 批量更新 {len(self.pending_updates)} 个账号状态")
                
                # 🔧 优化：缩短检查间隔到10秒，快速响应浏览器关闭
                time.sleep(10)  # 从30秒改为10秒
                
            except Exception as e:
                self.logger.error(f"浏览器状态监控循环异常: {e}")
                time.sleep(5)  # 异常时快速重试
        
        self.logger.info("🔍 浏览器状态监控循环结束")
    
    def _check_port_status(self, port: int) -> bool:
        """检查DevTools端口状态 - 优化版：平衡速度和准确性"""
        try:
            # 🔧 优化：增加超时时间到2秒，减少误判但保持响应速度
            response = requests.get(f'http://127.0.0.1:{port}/json', timeout=2)
            
            # 只要能连接成功就认为活跃
            if response.status_code == 200:
                return True
            else:
                return False
                
        except requests.exceptions.ConnectionError:
            # 连接失败 = 未活跃
            return False
        except requests.exceptions.Timeout:
            # 超时 = 未活跃  
            return False
        except Exception as e:
            # 记录异常详情
            self.logger.debug(f"端口 {port} 检查异常: {type(e).__name__}: {e}")
            return False
    
    def force_check_all(self):
        """强制检查所有账号状态"""
        with self.lock:
            accounts_to_check = list(self.account_ports.items())
        
        self.logger.info("⚡ 强制检查所有账号浏览器状态")
        
        for account_name, devtools_port in accounts_to_check:
            is_active = self._check_port_status(devtools_port)
            
            with self.lock:
                old_status = self.status_cache.get(account_name, False)
                self.status_cache[account_name] = is_active
            
            # 强制发送状态信号，不管是否有变化
            self.browser_status_changed.emit(account_name, is_active)
            
            status_text = "活跃" if is_active else "未活跃"
            self.logger.info(f"  {account_name}: 端口{devtools_port} -> {status_text}")
    
    def get_monitoring_info(self) -> dict:
        """获取监控信息"""
        with self.lock:
            return {
                'monitoring': self.monitoring,
                'account_count': len(self.account_ports),
                'account_ports': dict(self.account_ports),
                'status_cache': dict(self.status_cache)
            }

# 全局实例
_browser_monitor = None

def get_browser_status_monitor() -> BrowserStatusMonitor:
    """获取全局浏览器状态监控器实例"""
    global _browser_monitor
    if _browser_monitor is None:
        _browser_monitor = BrowserStatusMonitor()
    return _browser_monitor 