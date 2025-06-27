#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
许可证管理服务 - 许可证相关业务逻辑
"""

from typing import Tuple, Optional
from .base_service import BaseService


class LicenseService(BaseService):
    """许可证管理服务"""
    
    def verify_license(self, license_content: str) -> Tuple[bool, str]:
        """
        验证许可证
        
        Args:
            license_content: 许可证内容
            
        Returns:
            Tuple[bool, str]: (是否有效, 消息)
        """
        if not license_content or not license_content.strip():
            return False, "许可证内容不能为空"
        
        try:
            if self.license_system:
                result = self.license_system.verify_license(license_content.strip())
                if result.get('valid', False):
                    self.notify_success("许可证验证成功")
                    return True, "许可证验证成功"
                else:
                    error_msg = result.get('error', '许可证无效')
                    self.log_message(f"许可证验证失败: {error_msg}", "ERROR")
                    return False, error_msg
            else:
                return False, "许可证系统未初始化"
                
        except Exception as e:
            return self.handle_error(e, "验证许可证时发生错误"), str(e)
    
    def save_license(self, license_content: str, filename: str = "license.key") -> bool:
        """
        保存许可证到文件
        
        Args:
            license_content: 许可证内容
            filename: 文件名
            
        Returns:
            bool: 是否保存成功
        """
        if not license_content or not license_content.strip():
            self.notify_warning("许可证内容不能为空")
            return False
        
        try:
            if self.license_system:
                self.license_system.save_license_to_file(license_content.strip(), filename)
                self.notify_success(f"许可证已保存到 {filename}")
                return True
            else:
                self.log_message("许可证系统未初始化", "ERROR")
                return False
                
        except Exception as e:
            return self.handle_error(e, "保存许可证时发生错误")
    
    def load_license(self, filename: str = "license.key") -> Tuple[bool, str]:
        """
        从文件加载许可证
        
        Args:
            filename: 文件名
            
        Returns:
            Tuple[bool, str]: (是否成功, 许可证内容或错误信息)
        """
        try:
            if self.license_system:
                license_content = self.license_system.load_license_from_file(filename)
                if license_content:
                    self.notify_success(f"许可证已从 {filename} 加载")
                    return True, license_content
                else:
                    return False, "许可证文件不存在或为空"
            else:
                return False, "许可证系统未初始化"
                
        except Exception as e:
            self.handle_error(e, "加载许可证时发生错误")
            return False, str(e)
    
    def get_hardware_fingerprint(self) -> str:
        """
        获取硬件指纹
        
        Returns:
            str: 硬件指纹
        """
        try:
            if self.license_system:
                return self.license_system.get_hardware_fingerprint()
            else:
                return "许可证系统未初始化"
                
        except Exception as e:
            self.handle_error(e, "获取硬件指纹时发生错误")
            return "获取失败" 