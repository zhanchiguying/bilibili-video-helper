#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化测试运行器 - 一键运行所有测试并生成报告
"""

import os
import sys
import time
import argparse
from typing import Dict, Any

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from tests.test_base import TestRunner
except ImportError:
    print("❌ 无法导入测试模块，请检查测试环境")
    sys.exit(1)


class AutomatedTestRunner:
    """自动化测试运行器"""
    
    def __init__(self):
        """初始化测试运行器"""
        self.test_runner = TestRunner(verbosity=2)
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("🧪 开始运行自动化测试...")
        print("=" * 60)
        
        self.start_time = time.time()
        
        # 运行测试
        self.results = self.test_runner.run_tests()
        
        self.end_time = time.time()
        
        return self.results
    
    def run_specific_tests(self, test_patterns: list) -> Dict[str, Any]:
        """运行特定的测试"""
        print(f"🧪 运行特定测试: {test_patterns}")
        print("=" * 60)
        
        self.start_time = time.time()
        
        # 这里可以添加过滤逻辑来运行特定测试
        self.results = self.test_runner.run_tests()
        
        self.end_time = time.time()
        
        return self.results
    
    def generate_report(self) -> str:
        """生成测试报告"""
        if not self.results:
            return "❌ 没有测试结果可生成报告"
        
        duration = self.end_time - self.start_time if self.start_time and self.end_time else 0
        
        report = []
        report.append("📊 测试报告")
        report.append("=" * 60)
        report.append(f"🕒 测试开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.start_time))}")
        report.append(f"⏱️ 测试持续时间: {duration:.2f} 秒")
        report.append("")
        
        # 基本统计
        report.append("📈 统计摘要:")
        report.append(f"  总测试数: {self.results['tests_run']}")
        report.append(f"  成功: {self.results['tests_run'] - self.results['failures'] - self.results['errors']}")
        report.append(f"  失败: {self.results['failures']}")
        report.append(f"  错误: {self.results['errors']}")
        report.append(f"  跳过: {self.results['skipped']}")
        report.append(f"  成功率: {self.results['success_rate']:.1f}%")
        report.append("")
        
        # 结果评估
        if self.results['success_rate'] >= 95:
            report.append("✅ 测试结果: 优秀")
        elif self.results['success_rate'] >= 85:
            report.append("✅ 测试结果: 良好")
        elif self.results['success_rate'] >= 70:
            report.append("⚠️ 测试结果: 一般")
        else:
            report.append("❌ 测试结果: 需要关注")
        
        # 失败详情
        if self.results['failures'] > 0:
            report.append("")
            report.append("❌ 失败的测试:")
            for i, (test, traceback) in enumerate(self.results['details']['failures'], 1):
                report.append(f"  {i}. {test}")
                # 只显示简短的错误信息
                lines = traceback.split('\n')
                for line in lines[-3:]:
                    if line.strip():
                        report.append(f"     {line.strip()}")
        
        # 错误详情
        if self.results['errors'] > 0:
            report.append("")
            report.append("💥 错误的测试:")
            for i, (test, traceback) in enumerate(self.results['details']['errors'], 1):
                report.append(f"  {i}. {test}")
                # 只显示简短的错误信息
                lines = traceback.split('\n')
                for line in lines[-3:]:
                    if line.strip():
                        report.append(f"     {line.strip()}")
        
        # 跳过的测试
        if self.results['skipped'] > 0:
            report.append("")
            report.append("⏭️ 跳过的测试:")
            for i, (test, reason) in enumerate(self.results['details']['skipped'], 1):
                report.append(f"  {i}. {test} - {reason}")
        
        # 性能分析
        report.append("")
        report.append("⚡ 性能分析:")
        avg_time_per_test = duration / self.results['tests_run'] if self.results['tests_run'] > 0 else 0
        report.append(f"  平均每个测试时间: {avg_time_per_test:.3f} 秒")
        
        if avg_time_per_test > 5.0:
            report.append("  ⚠️ 部分测试可能运行较慢")
        elif avg_time_per_test < 0.1:
            report.append("  ✅ 测试运行速度良好")
        
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def save_report(self, filename: str = None) -> str:
        """保存测试报告到文件"""
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"test_report_{timestamp}.txt"
        
        report_content = self.generate_report()
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_content)
            return f"✅ 测试报告已保存到: {filename}"
        except Exception as e:
            return f"❌ 保存报告失败: {e}"
    
    def check_environment(self) -> Dict[str, bool]:
        """检查测试环境"""
        print("🔍 检查测试环境...")
        
        checks = {}
        
        # 检查必要的模块
        try:
            import unittest
            checks['unittest'] = True
        except ImportError:
            checks['unittest'] = False
        
        try:
            from unittest.mock import Mock
            checks['unittest.mock'] = True
        except ImportError:
            checks['unittest.mock'] = False
        
        try:
            import tempfile
            checks['tempfile'] = True
        except ImportError:
            checks['tempfile'] = False
        
        # 检查项目模块
        try:
            from services import AccountService
            checks['services'] = True
        except ImportError:
            checks['services'] = False
        
        try:
            from performance import CacheManager
            checks['performance'] = True
        except ImportError:
            checks['performance'] = False
        
        # 检查可选模块
        try:
            import psutil
            checks['psutil'] = True
        except ImportError:
            checks['psutil'] = False
        
        try:
            import requests
            checks['requests'] = True
        except ImportError:
            checks['requests'] = False
        
        # 打印检查结果
        for module, available in checks.items():
            status = "✅" if available else "❌"
            print(f"  {status} {module}")
        
        return checks


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="自动化测试运行器")
    parser.add_argument('--check-env', action='store_true', help="检查测试环境")
    parser.add_argument('--save-report', action='store_true', help="保存测试报告到文件")
    parser.add_argument('--report-file', type=str, help="指定报告文件名")
    parser.add_argument('--tests', nargs='*', help="运行特定的测试")
    
    args = parser.parse_args()
    
    runner = AutomatedTestRunner()
    
    # 检查环境
    if args.check_env:
        env_checks = runner.check_environment()
        failed_checks = [module for module, available in env_checks.items() if not available]
        
        if failed_checks:
            print(f"\n⚠️ 缺少模块: {', '.join(failed_checks)}")
            print("部分测试可能会被跳过")
        else:
            print("\n✅ 测试环境检查通过")
        
        if not args.tests and not args.save_report:
            return
    
    # 运行测试
    try:
        if args.tests:
            results = runner.run_specific_tests(args.tests)
        else:
            results = runner.run_all_tests()
        
        # 显示报告
        print("\n" + runner.generate_report())
        
        # 保存报告
        if args.save_report:
            save_result = runner.save_report(args.report_file)
            print(f"\n{save_result}")
        
        # 返回适当的退出码
        if results['failures'] > 0 or results['errors'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 运行测试时发生错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main() 