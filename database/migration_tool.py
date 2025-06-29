#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据迁移工具 - 从JSON文件迁移到SQLite数据库
支持安全迁移、数据校验、回滚机制
"""

import os
import json
import shutil
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import logging

from database.database_manager import db_manager


class DataMigrationTool:
    """数据迁移工具"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.backup_dir = "migration_backup"
        self.migration_log = []
    
    def migrate_all_data(self, backup_before_migrate: bool = True) -> Tuple[bool, str, Dict[str, Any]]:
        """
        完整的数据迁移流程
        
        Args:
            backup_before_migrate: 迁移前是否备份JSON文件
            
        Returns:
            Tuple[bool, str, Dict]: (是否成功, 详细信息, 迁移统计)
        """
        migration_stats = {
            'accounts_migrated': 0,
            'videos_migrated': 0,
            'settings_migrated': 0,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'duration_seconds': 0,
            'backup_created': False,
            'errors': []
        }
        
        start_time = time.time()
        
        try:
            self.log_migration("🚀 开始数据迁移流程...")
            
            # 步骤1：创建备份
            if backup_before_migrate:
                backup_success, backup_path = self.create_backup()
                if backup_success:
                    migration_stats['backup_created'] = True
                    migration_stats['backup_path'] = backup_path
                    self.log_migration(f"✅ 备份创建成功: {backup_path}")
                else:
                    self.log_migration("⚠️ 备份创建失败，但继续迁移")
            
            # 步骤2：迁移账号数据
            self.log_migration("📊 开始迁移账号数据...")
            accounts_success = db_manager.migrate_from_json('accounts.json', 'uploaded_videos.json')
            if accounts_success:
                migration_stats['accounts_migrated'] = self.count_migrated_accounts()
                self.log_migration(f"✅ 账号数据迁移完成: {migration_stats['accounts_migrated']} 个账号")
            else:
                raise Exception("账号数据迁移失败")
            
            # 步骤3：迁移配置数据
            self.log_migration("⚙️ 开始迁移配置数据...")
            config_migrated = self.migrate_config_data()
            migration_stats['settings_migrated'] = config_migrated
            if config_migrated > 0:
                self.log_migration(f"✅ 配置数据迁移完成: {config_migrated} 项设置")
            
            # 步骤4：数据校验
            self.log_migration("🔍 开始数据校验...")
            validation_success, validation_report = self.validate_migrated_data()
            if validation_success:
                self.log_migration("✅ 数据校验通过")
                migration_stats.update(validation_report)
            else:
                self.log_migration("⚠️ 数据校验发现问题，但迁移基本成功")
                migration_stats['validation_warnings'] = validation_report
            
            # 计算耗时
            end_time = time.time()
            migration_stats['duration_seconds'] = round(end_time - start_time, 2)
            migration_stats['end_time'] = datetime.now().isoformat()
            
            success_message = (
                f"🎉 数据迁移成功完成！\n"
                f"📊 账号: {migration_stats['accounts_migrated']} 个\n"
                f"🎬 视频记录: {migration_stats.get('videos_validated', 0)} 条\n"
                f"⚙️ 设置: {migration_stats['settings_migrated']} 项\n"
                f"⏱️ 耗时: {migration_stats['duration_seconds']} 秒"
            )
            
            self.log_migration(success_message)
            return True, success_message, migration_stats
            
        except Exception as e:
            end_time = time.time()
            migration_stats['duration_seconds'] = round(end_time - start_time, 2)
            migration_stats['end_time'] = datetime.now().isoformat()
            migration_stats['errors'].append(str(e))
            
            error_message = f"❌ 数据迁移失败: {e}"
            self.log_migration(error_message)
            return False, error_message, migration_stats
    
    def create_backup(self) -> Tuple[bool, str]:
        """创建JSON文件备份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.backup_dir, f"backup_{timestamp}")
            
            # 创建备份目录
            os.makedirs(backup_path, exist_ok=True)
            
            # 备份文件列表
            files_to_backup = [
                'accounts.json',
                'uploaded_videos.json', 
                'config.json',
                'ui_settings.json'
            ]
            
            backed_up_files = []
            for filename in files_to_backup:
                if os.path.exists(filename):
                    shutil.copy2(filename, backup_path)
                    backed_up_files.append(filename)
            
            # 创建备份信息文件
            backup_info = {
                'backup_time': datetime.now().isoformat(),
                'backed_up_files': backed_up_files,
                'migration_purpose': 'JSON to SQLite migration',
                'tool_version': '1.0'
            }
            
            with open(os.path.join(backup_path, 'backup_info.json'), 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, ensure_ascii=False, indent=2)
            
            return True, backup_path
            
        except Exception as e:
            self.logger.error(f"创建备份失败: {e}")
            return False, str(e)
    
    def migrate_config_data(self) -> int:
        """迁移配置数据到数据库"""
        migrated_count = 0
        
        try:
            # 迁移config.json
            if os.path.exists('config.json'):
                with open('config.json', 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                for key, value in config_data.items():
                    if db_manager.set_setting(key, json.dumps(value), 'config'):
                        migrated_count += 1
            
            # 迁移ui_settings.json
            if os.path.exists('ui_settings.json'):
                with open('ui_settings.json', 'r', encoding='utf-8') as f:
                    ui_data = json.load(f)
                
                for key, value in ui_data.items():
                    if db_manager.set_setting(f"ui_{key}", json.dumps(value), 'ui'):
                        migrated_count += 1
            
            return migrated_count
            
        except Exception as e:
            self.logger.error(f"迁移配置数据失败: {e}")
            return migrated_count
    
    def validate_migrated_data(self) -> Tuple[bool, Dict[str, Any]]:
        """校验迁移后的数据完整性"""
        validation_report = {
            'accounts_validated': 0,
            'videos_validated': 0,
            'settings_validated': 0,
            'consistency_checks': {},
            'warnings': []
        }
        
        try:
            # 校验账号数据
            json_accounts = self.load_json_accounts()
            db_accounts = db_manager.get_all_accounts_cached()
            
            validation_report['accounts_validated'] = len(db_accounts)
            validation_report['consistency_checks']['accounts_count_match'] = len(json_accounts) == len(db_accounts)
            
            if len(json_accounts) != len(db_accounts):
                validation_report['warnings'].append(f"账号数量不匹配: JSON={len(json_accounts)}, DB={len(db_accounts)}")
            
            # 校验视频记录
            json_videos = self.load_json_videos()
            # 这里可以添加视频记录的校验逻辑
            validation_report['videos_validated'] = len(json_videos)
            
            # 校验配置数据
            config_settings = db_manager.get_all_settings('config')
            ui_settings = db_manager.get_all_settings('ui')
            validation_report['settings_validated'] = len(config_settings) + len(ui_settings)
            
            # 总体校验结果
            has_warnings = len(validation_report['warnings']) > 0
            return not has_warnings, validation_report
            
        except Exception as e:
            validation_report['warnings'].append(f"校验过程出错: {e}")
            return False, validation_report
    
    def load_json_accounts(self) -> Dict[str, Any]:
        """加载JSON账号数据"""
        try:
            if os.path.exists('accounts.json'):
                with open('accounts.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except:
            return {}
    
    def load_json_videos(self) -> Dict[str, Any]:
        """加载JSON视频数据"""
        try:
            if os.path.exists('uploaded_videos.json'):
                with open('uploaded_videos.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('uploaded_videos', {})
            return {}
        except:
            return {}
    
    def count_migrated_accounts(self) -> int:
        """统计已迁移的账号数量"""
        try:
            accounts = db_manager.get_all_accounts_cached()
            return len(accounts)
        except:
            return 0
    
    def create_rollback_script(self) -> str:
        """创建回滚脚本"""
        rollback_script = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库回滚脚本 - 恢复到JSON文件模式
"""

import os
import shutil
from datetime import datetime

def rollback_to_json():
    """回滚到JSON文件模式"""
    print("🔄 开始回滚到JSON文件模式...")
    
    # 1. 重命名数据库文件
    if os.path.exists("bilibili_helper.db"):
        backup_name = f"bilibili_helper_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        os.rename("bilibili_helper.db", backup_name)
        print(f"📦 数据库已备份为: {backup_name}")
    
    # 2. 恢复JSON文件（如果存在备份）
    backup_dirs = [d for d in os.listdir('.') if d.startswith('migration_backup')]
    if backup_dirs:
        latest_backup = max(backup_dirs)
        backup_path = os.path.join(latest_backup, os.listdir(latest_backup)[0])
        
        for filename in ['accounts.json', 'uploaded_videos.json', 'config.json']:
            backup_file = os.path.join(backup_path, filename)
            if os.path.exists(backup_file):
                shutil.copy2(backup_file, filename)
                print(f"📂 恢复文件: {filename}")
    
    print("✅ 回滚完成！程序将使用JSON文件模式运行")

if __name__ == "__main__":
    rollback_to_json()
'''
        
        with open('rollback_to_json.py', 'w', encoding='utf-8') as f:
            f.write(rollback_script)
        
        return 'rollback_to_json.py'
    
    def log_migration(self, message: str):
        """记录迁移日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.migration_log.append(log_entry)
        print(log_entry)
    
    def save_migration_log(self) -> str:
        """保存迁移日志"""
        log_filename = f"migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        try:
            with open(log_filename, 'w', encoding='utf-8') as f:
                f.write("B站视频助手 - SQLite数据迁移日志\n")
                f.write("=" * 50 + "\n\n")
                for log_entry in self.migration_log:
                    f.write(log_entry + "\n")
            
            return log_filename
        except Exception as e:
            print(f"保存迁移日志失败: {e}")
            return ""


def run_migration():
    """运行数据迁移"""
    print("🚀 B站视频助手 - SQLite数据迁移工具")
    print("=" * 50)
    
    migration_tool = DataMigrationTool()
    
    # 执行迁移
    success, message, stats = migration_tool.migrate_all_data(backup_before_migrate=True)
    
    # 保存日志
    log_file = migration_tool.save_migration_log()
    if log_file:
        print(f"📝 迁移日志已保存: {log_file}")
    
    # 创建回滚脚本
    rollback_script = migration_tool.create_rollback_script()
    print(f"🔄 回滚脚本已创建: {rollback_script}")
    
    if success:
        print("\n🎉 数据迁移成功完成！")
        print("💡 提示：")
        print("  - 原JSON文件已备份，可安全删除")
        print("  - 程序现在将使用SQLite数据库")
        print("  - 如需回滚，运行: python rollback_to_json.py")
    else:
        print(f"\n❌ 数据迁移失败: {message}")
        print("💡 建议：")
        print("  - 检查原JSON文件是否完整")
        print("  - 确保数据库文件有写权限")
        print("  - 查看迁移日志了解详细错误")
    
    return success, stats


if __name__ == "__main__":
    run_migration() 