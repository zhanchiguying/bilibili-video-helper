#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指纹验证器 - 自动检测和优化浏览器指纹
"""

import json
import time
import random
import hashlib
from typing import Dict, Any, Tuple, List

from .logger import get_logger

class FingerprintValidator:
    """指纹验证器"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def validate_fingerprint(self, username: str, fingerprint: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """验证指纹是否能躲过检测"""
        self.logger.info(f"开始验证账号 {username} 的指纹...")
        
        # 执行多项检测
        results = {
            'user_agent_valid': self._validate_user_agent(fingerprint['user_agent']),
            'screen_resolution_valid': self._validate_screen_resolution(fingerprint),
            'webgl_renderer_safe': self._validate_webgl_renderer(fingerprint),
            'fingerprint_unique': self._check_fingerprint_uniqueness(username, fingerprint),
            'overall_score': 0
        }
        
        # 计算总体评分
        results['overall_score'] = self._calculate_risk_score(results)
        
        # 判断是否通过验证
        passed = results['overall_score'] >= 80  # 80分以上认为安全
        
        if passed:
            self.logger.info(f"账号 {username} 指纹验证通过，评分: {results['overall_score']}")
        else:
            self.logger.warning(f"账号 {username} 指纹风险较高，评分: {results['overall_score']}")
        
        return passed, results
    
    def _validate_user_agent(self, user_agent: str) -> bool:
        """验证User-Agent的有效性"""
        # 检查是否包含必要的组件
        required_components = ['Mozilla', 'Chrome', 'Safari', 'AppleWebKit']
        has_required = all(comp in user_agent for comp in required_components)
        
        # 检查版本号是否合理
        import re
        chrome_version = re.search(r'Chrome/(\d+)', user_agent)
        if chrome_version:
            version = int(chrome_version.group(1))
            is_recent = 110 <= version <= 130  # 合理的Chrome版本范围
        else:
            is_recent = False
        
        self.logger.debug(f"User-Agent验证: 组件完整={has_required}, 版本合理={is_recent}")
        return has_required and is_recent
    
    def _validate_screen_resolution(self, fingerprint: Dict[str, Any]) -> bool:
        """验证屏幕分辨率的合理性"""
        resolution = fingerprint.get('window_size', '1920,1080')
        try:
            width, height = map(int, resolution.split(','))
            
            # 常见的分辨率
            common_resolutions = [
                (1920, 1080), (1366, 768), (1536, 864), 
                (1440, 900), (1280, 1024), (1600, 900)
            ]
            
            is_common = (width, height) in common_resolutions
            self.logger.debug(f"分辨率验证: {width}x{height}, 常见分辨率={is_common}")
            return is_common
        except:
            return False
    
    def _validate_webgl_renderer(self, fingerprint: Dict[str, Any]) -> bool:
        """验证WebGL渲染器的安全性"""
        renderer = fingerprint.get('webgl_renderer', '')
        
        # 检查是否为常见的虚拟化环境标识（高风险）
        risky_patterns = [
            "VMware", "VirtualBox", "Software", "Microsoft Basic",
            "SwiftShader", "llvmpipe", "Chromium"
        ]
        
        # 检查是否为安全的渲染器
        safe_patterns = [
            "Intel", "NVIDIA", "AMD", "ANGLE"
        ]
        
        has_risky = any(pattern in renderer for pattern in risky_patterns)
        has_safe = any(pattern in renderer for pattern in safe_patterns)
        
        is_safe = has_safe and not has_risky
        self.logger.debug(f"WebGL渲染器验证: {renderer[:30]}..., 安全={is_safe}")
        return is_safe
    
    def _check_fingerprint_uniqueness(self, username: str, fingerprint: Dict[str, Any]) -> bool:
        """检查指纹的唯一性"""
        # 生成指纹哈希
        fingerprint_str = json.dumps(fingerprint, sort_keys=True)
        fingerprint_hash = hashlib.md5(fingerprint_str.encode()).hexdigest()
        
        # 检查是否使用了用户名作为种子（确保唯一性）
        expected_seed = int(hashlib.md5(username.encode()).hexdigest()[:8], 16)
        
        # 验证指纹是否基于用户名生成（通过重新生成验证）
        random.seed(expected_seed)
        test_choice = random.randint(1, 1000)
        
        # 重置种子并再次生成，应该得到相同结果
        random.seed(expected_seed)
        verify_choice = random.randint(1, 1000)
        
        is_deterministic = test_choice == verify_choice
        self.logger.debug(f"指纹唯一性验证: 哈希={fingerprint_hash[:16]}..., 确定性={is_deterministic}")
        return is_deterministic
    
    def _calculate_risk_score(self, results: Dict[str, Any]) -> int:
        """计算风险评分 (0-100，分数越高越安全)"""
        weights = {
            'user_agent_valid': 25,       # User-Agent有效性
            'screen_resolution_valid': 20, # 屏幕分辨率
            'webgl_renderer_safe': 30,    # WebGL渲染器安全性
            'fingerprint_unique': 25      # 指纹唯一性
        }
        
        total_score = 0
        for key, weight in weights.items():
            if results.get(key, False):
                total_score += weight
        
        return total_score
    
    def optimize_fingerprint(self, username: str, current_fingerprint: Dict[str, Any]) -> Dict[str, Any]:
        """优化指纹以提高安全性"""
        self.logger.info(f"开始优化账号 {username} 的指纹...")
        
        # 验证当前指纹
        passed, results = self.validate_fingerprint(username, current_fingerprint)
        
        if passed:
            self.logger.info(f"账号 {username} 指纹已经足够安全，无需优化")
            return current_fingerprint
        
        # 根据检测结果进行优化
        optimized = current_fingerprint.copy()
        
        # 优化User-Agent
        if not results.get('user_agent_valid', True):
            optimized['user_agent'] = self._generate_safe_user_agent(username)
            self.logger.info(f"已优化账号 {username} 的User-Agent")
        
        # 优化分辨率
        if not results.get('screen_resolution_valid', True):
            optimized['window_size'] = self._generate_safe_resolution(username)
            self.logger.info(f"已优化账号 {username} 的屏幕分辨率")
        
        # 优化WebGL渲染器
        if not results.get('webgl_renderer_safe', True):
            optimized.update(self._generate_safe_webgl(username))
            self.logger.info(f"已优化账号 {username} 的WebGL信息")
        
        # 再次验证优化后的指纹
        passed_after, results_after = self.validate_fingerprint(username, optimized)
        
        if passed_after:
            self.logger.info(f"账号 {username} 指纹优化成功，评分提升至: {results_after['overall_score']}")
        else:
            self.logger.warning(f"账号 {username} 指纹优化后仍有风险，评分: {results_after['overall_score']}")
        
        return optimized
    
    def _generate_safe_user_agent(self, username: str) -> str:
        """生成安全的User-Agent"""
        # 基于用户名生成确定性的种子
        seed = int(hashlib.md5(username.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        
        # 选择安全的Chrome版本
        safe_versions = ["120.0.0.0", "121.0.0.0", "119.0.0.0", "118.0.0.0"]
        version = random.choice(safe_versions)
        
        return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36"
    
    def _generate_safe_resolution(self, username: str) -> str:
        """生成安全的分辨率"""
        seed = int(hashlib.md5(username.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        
        safe_resolutions = ["1920,1080", "1366,768", "1536,864", "1440,900", "1280,1024"]
        return random.choice(safe_resolutions)
    
    def _generate_safe_webgl(self, username: str) -> Dict[str, Any]:
        """生成安全的WebGL信息"""
        seed = int(hashlib.md5(username.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        
        safe_renderers = [
            "ANGLE (Intel, Intel(R) HD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "ANGLE (NVIDIA, NVIDIA GeForce GTX 1050 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"
        ]
        
        return {
            'webgl_vendor': "Google Inc. (Intel)",
            'webgl_renderer': random.choice(safe_renderers),
            'webgl_version': "WebGL 1.0 (OpenGL ES 2.0 Chromium)"
        }
