"""
统一测试运行脚本 - 运行所有测试并生成报告
"""
import unittest
import sys
import os
from io import StringIO

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("面试防作弊监控系统 - 单元测试")
    print("=" * 70)
    print()
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 发现并添加所有测试
    start_dir = 'tests'
    suite.addTests(loader.discover(start_dir, pattern='test_*.py'))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 打印总结
    print()
    print("=" * 70)
    print("测试总结")
    print("=" * 70)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"跳过: {len(result.skipped)}")
    print("=" * 70)
    
    # 返回是否所有测试通过
    return result.wasSuccessful()


def run_specific_test(test_module):
    """运行特定的测试模块"""
    print(f"运行测试模块: {test_module}")
    print("=" * 70)
    
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(test_module)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    # 检查是否指定了特定测试
    if len(sys.argv) > 1:
        test_module = sys.argv[1]
        success = run_specific_test(test_module)
    else:
        success = run_all_tests()
    
    # 退出码
    sys.exit(0 if success else 1)
