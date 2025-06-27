#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试模块 - 自动化测试框架
"""

import os
import sys

# 将项目根目录添加到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

__version__ = "1.0.0" 