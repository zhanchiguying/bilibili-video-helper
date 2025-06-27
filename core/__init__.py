#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频带货助手 - 核心模块包
"""

from .app import BilibiliUploaderApp
from .config import Config
from .logger import get_logger
from .fingerprint_validator import FingerprintValidator
from .browser_detector import get_browser_detector

__version__ = "2.0.0"
__all__ = ['BilibiliUploaderApp', 'Config', 'get_logger', 'FingerprintValidator', 'get_browser_detector'] 