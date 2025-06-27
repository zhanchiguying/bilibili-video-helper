#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试基础框架 - 提供通用测试工具和基础类
"""

import unittest
import time
import tempfile
import shutil
from typing import Any, Dict, Optional
from unittest.mock import Mock, patch


class BaseTestCase(unittest.TestCase):
    """测试基础类"""
    
    def setUp(self):
        """测试前准备"""
        self.start_time = time.time()
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """测试后清理"""
        # 清理临时目录
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # 记录测试时间
        duration = time.time() - self.start_time
        if duration > 5.0:  # 超过5秒的测试
            print(f"⚠️ 测试 {self._testMethodName} 耗时过长: {duration:.2f}秒")
    
    def assertBetween(self, value: float, min_val: float, max_val: float, msg: str = None):
        """断言值在指定范围内"""
        if not (min_val <= value <= max_val):
            msg = msg or f"{value} 不在范围 [{min_val}, {max_val}] 内"
            raise AssertionError(msg)
    
    def assertDictContainsSubset(self, subset: Dict, dictionary: Dict, msg: str = None):
        """断言字典包含子集"""
        for key, value in subset.items():
            if key not in dictionary:
                msg = msg or f"键 '{key}' 不存在于字典中"
                raise AssertionError(msg)
            if dictionary[key] != value:
                msg = msg or f"键 '{key}' 的值不匹配: 期望 {value}, 实际 {dictionary[key]}"
                raise AssertionError(msg)
    
    def create_mock_app(self) -> Mock:
        """创建模拟应用对象"""
        mock_app = Mock()
        mock_app.log_message = Mock()
        mock_app.core_app = Mock()
        return mock_app


class PerformanceTestCase(BaseTestCase):
    """性能测试基础类"""
    
    def setUp(self):
        super().setUp()
        self.performance_data = {}
    
    def measure_performance(self, func, *args, **kwargs):
        """测量函数性能"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        duration = end_time - start_time
        func_name = func.__name__ if hasattr(func, '__name__') else str(func)
        
        self.performance_data[func_name] = {
            'duration': duration,
            'timestamp': start_time,
            'result': result
        }
        
        return result, duration
    
    def assert_performance_under(self, func_name: str, max_duration: float):
        """断言性能在指定时间内"""
        if func_name not in self.performance_data:
            raise AssertionError(f"未找到函数 {func_name} 的性能数据")
        
        actual_duration = self.performance_data[func_name]['duration']
        if actual_duration > max_duration:
            raise AssertionError(
                f"函数 {func_name} 执行时间 {actual_duration:.3f}s 超过限制 {max_duration}s"
            )


class IntegrationTestCase(BaseTestCase):
    """集成测试基础类"""
    
    def setUp(self):
        super().setUp()
        self.setup_test_environment()
    
    def setup_test_environment(self):
        """设置测试环境"""
        # 创建测试配置
        self.test_config = {
            'test_mode': True,
            'log_level': 'DEBUG',
            'temp_dir': self.temp_dir
        }
    
    def cleanup_test_environment(self):
        """清理测试环境"""
        pass
    
    def tearDown(self):
        self.cleanup_test_environment()
        super().tearDown()


def skip_if_no_internet(func):
    """如果没有网络连接则跳过测试"""
    def wrapper(self):
        try:
            import requests
            requests.get('https://www.bilibili.com', timeout=5)
        except:
            self.skipTest("需要网络连接")
        return func(self)
    return wrapper


def skip_if_no_chrome(func):
    """如果没有Chrome浏览器则跳过测试"""
    def wrapper(self):
        try:
            from core.browser_detector import get_browser_detector
            detector = get_browser_detector()
            chrome_path = detector.get_best_chrome_path()
            if not chrome_path:
                raise Exception("Chrome not found")
        except:
            self.skipTest("需要Chrome浏览器")
        return func(self)
    return wrapper


class TestRunner:
    """自定义测试运行器"""
    
    def __init__(self, verbosity: int = 2):
        """
        初始化测试运行器
        
        Args:
            verbosity: 详细级别 (0=静默, 1=正常, 2=详细)
        """
        self.verbosity = verbosity
        self.results = {}
    
    def run_tests(self, test_modules: list = None) -> Dict[str, Any]:
        """
        运行测试
        
        Args:
            test_modules: 要运行的测试模块列表
            
        Returns:
            Dict[str, Any]: 测试结果
        """
        if test_modules is None:
            test_modules = self._discover_tests()
        
        suite = unittest.TestSuite()
        
        for module in test_modules:
            try:
                tests = unittest.defaultTestLoader.loadTestsFromModule(module)
                suite.addTests(tests)
            except Exception as e:
                print(f"⚠️ 加载测试模块 {module} 失败: {e}")
        
        # 运行测试
        runner = unittest.TextTestRunner(verbosity=self.verbosity)
        result = runner.run(suite)
        
        # 收集结果
        self.results = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'skipped': len(result.skipped),
            'success_rate': (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100 if result.testsRun > 0 else 0,
            'details': {
                'failures': result.failures,
                'errors': result.errors,
                'skipped': result.skipped
            }
        }
        
        return self.results
    
    def _discover_tests(self) -> list:
        """自动发现测试模块"""
        import os
        import importlib
        
        test_modules = []
        tests_dir = os.path.dirname(__file__)
        
        for filename in os.listdir(tests_dir):
            if filename.startswith('test_') and filename.endswith('.py'):
                module_name = f"tests.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    test_modules.append(module)
                except ImportError as e:
                    print(f"⚠️ 无法导入测试模块 {module_name}: {e}")
        
        return test_modules
    
    def print_summary(self):
        """打印测试摘要"""
        if not self.results:
            print("❌ 没有测试结果")
            return
        
        print("\n" + "="*50)
        print("📊 测试结果摘要")
        print("="*50)
        print(f"总测试数: {self.results['tests_run']}")
        print(f"成功: {self.results['tests_run'] - self.results['failures'] - self.results['errors']}")
        print(f"失败: {self.results['failures']}")
        print(f"错误: {self.results['errors']}")
        print(f"跳过: {self.results['skipped']}")
        print(f"成功率: {self.results['success_rate']:.1f}%")
        
        if self.results['success_rate'] >= 90:
            print("✅ 测试通过率良好")
        elif self.results['success_rate'] >= 70:
            print("⚠️ 测试通过率一般")
        else:
            print("❌ 测试通过率较低，需要关注")


if __name__ == '__main__':
    # 运行所有测试
    runner = TestRunner()
    results = runner.run_tests()
    runner.print_summary() 