#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号发布计数管理模块
负责追踪每个账号的每日发布数量，自动重置计数
"""

import json
import os
from datetime import datetime

class AccountManager:
    """账号发布计数管理器"""
    
    def __init__(self, accounts_file="accounts.json"):
        self.accounts_file = accounts_file
    
    def _load_accounts(self):
        """加载账号数据"""
        try:
            if os.path.exists(self.accounts_file):
                with open(self.accounts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"加载账号数据失败: {e}")
            return {}
    
    def _save_accounts(self, accounts):
        """保存账号数据"""
        try:
            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                json.dump(accounts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存账号数据失败: {e}")
            return False
    
    def _ensure_publish_fields(self, account_data):
        """确保账号数据包含发布追踪字段"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 初始化字段
        if 'today_published' not in account_data:
            account_data['today_published'] = 0
        
        if 'last_publish_date' not in account_data:
            account_data['last_publish_date'] = today
        
        if 'total_published' not in account_data:
            account_data['total_published'] = 0
        
        # 检查是否需要重置（新的一天）
        if account_data.get('last_publish_date') != today:
            account_data['today_published'] = 0
            account_data['last_publish_date'] = today
        
        return account_data
    
    def update_publish_count(self, account_name):
        """视频发布成功后更新计数"""
        accounts = self._load_accounts()
        
        if account_name not in accounts:
            print(f"账号 {account_name} 不存在")
            return False
        
        # 确保有发布追踪字段
        account = self._ensure_publish_fields(accounts[account_name])
        
        # 更新计数
        account['today_published'] += 1
        account['total_published'] += 1
        account['last_publish_date'] = datetime.now().strftime("%Y-%m-%d")
        
        # 保存数据
        success = self._save_accounts(accounts)
        if success:
            print(f"✅ 账号 {account_name} 发布计数已更新: {account['today_published']}")
        else:
            print(f"❌ 账号 {account_name} 发布计数更新失败")
        
        return success
    
    def get_account_progress(self, account_name, target_count):
        """获取账号发布进度"""
        accounts = self._load_accounts()
        
        if account_name not in accounts:
            return "账号不存在", False, 0
        
        # 确保有发布追踪字段
        account = self._ensure_publish_fields(accounts[account_name])
        
        # 需要保存一次以确保日期重置生效
        self._save_accounts(accounts)
        
        published = account['today_published']
        completed = published >= target_count
        
        if completed:
            status = f"{published}/{target_count} 已完成"
        else:
            status = f"{published}/{target_count} 进行中"
        
        return status, completed, published
    
    def should_skip_account(self, account_name, target_count):
        """判断账号是否应该跳过（已完成今日目标）"""
        _, completed, published = self.get_account_progress(account_name, target_count)
        
        if completed:
            return True, f"已完成今日目标 ({published}/{target_count})"
        else:
            return False, f"继续执行 ({published}/{target_count})"
    
    def get_all_accounts_progress(self, target_count):
        """获取所有账号的发布进度"""
        accounts = self._load_accounts()
        progress_list = []
        
        for account_name in accounts.keys():
            status, completed, published = self.get_account_progress(account_name, target_count)
            progress_list.append({
                'account_name': account_name,
                'published': published,
                'target': target_count,
                'status': status,
                'completed': completed
            })
        
        return progress_list
    
    def reset_all_daily_counts(self):
        """手动重置所有账号的每日计数（调试用）"""
        accounts = self._load_accounts()
        today = datetime.now().strftime("%Y-%m-%d")
        
        for account_name, account_data in accounts.items():
            account_data['today_published'] = 0
            account_data['last_publish_date'] = today
        
        success = self._save_accounts(accounts)
        if success:
            print(f"✅ 已重置所有账号的每日计数")
        
        return success

# 创建全局实例
account_manager = AccountManager() 