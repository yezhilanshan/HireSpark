"""
安全功能测试
测试输入验证和速率限制功能
"""
import unittest
import time
from utils.security import (
    RateLimiter,
    TokenBucket,
    validate_string,
    validate_number,
    validate_base64_image,
    sanitize_filename,
    ValidationError
)


class TestInputValidation(unittest.TestCase):
    """输入验证测试"""
    
    def test_validate_string_success(self):
        """测试字符串验证 - 成功情况"""
        result = validate_string("test_user", "username", min_length=1, max_length=20)
        self.assertEqual(result, "test_user")
    
    def test_validate_string_too_short(self):
        """测试字符串验证 - 太短"""
        with self.assertRaises(ValidationError) as context:
            validate_string("a", "username", min_length=3)
        self.assertIn("长度不能小于", str(context.exception))
    
    def test_validate_string_too_long(self):
        """测试字符串验证 - 太长"""
        with self.assertRaises(ValidationError) as context:
            validate_string("a" * 100, "username", max_length=20)
        self.assertIn("长度不能超过", str(context.exception))
    
    def test_validate_string_empty_not_allowed(self):
        """测试字符串验证 - 不允许空字符串"""
        with self.assertRaises(ValidationError) as context:
            validate_string("", "username", allow_empty=False)
        self.assertIn("不能为空", str(context.exception))
    
    def test_validate_string_pattern(self):
        """测试字符串验证 - 正则表达式"""
        # 只允许字母和数字
        result = validate_string("user123", "username", pattern=r'^[a-zA-Z0-9]+$')
        self.assertEqual(result, "user123")
        
        # 包含特殊字符应该失败
        with self.assertRaises(ValidationError) as context:
            validate_string("user@123", "username", pattern=r'^[a-zA-Z0-9]+$')
        self.assertIn("格式不正确", str(context.exception))
    
    def test_validate_number_success(self):
        """测试数字验证 - 成功情况"""
        result = validate_number(42, "age")
        self.assertEqual(result, 42.0)
        
        result_int = validate_number(42, "age", allow_float=False)
        self.assertEqual(result_int, 42)
    
    def test_validate_number_range(self):
        """测试数字验证 - 范围检查"""
        result = validate_number(25, "age", min_val=18, max_val=100)
        self.assertEqual(result, 25.0)
        
        # 太小
        with self.assertRaises(ValidationError) as context:
            validate_number(10, "age", min_val=18)
        self.assertIn("不能小于", str(context.exception))
        
        # 太大
        with self.assertRaises(ValidationError) as context:
            validate_number(150, "age", max_val=100)
        self.assertIn("不能大于", str(context.exception))
    
    def test_validate_number_invalid_type(self):
        """测试数字验证 - 无效类型"""
        with self.assertRaises(ValidationError) as context:
            validate_number("not_a_number", "value")
        self.assertIn("必须是有效的数字", str(context.exception))
    
    def test_validate_base64_image_success(self):
        """测试 Base64 图片验证 - 成功情况"""
        # 有效的 base64 字符串
        valid_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        result = validate_base64_image(valid_b64, "image")
        self.assertEqual(result, valid_b64)
    
    def test_validate_base64_with_data_url(self):
        """测试 Base64 图片验证 - 包含 data URL scheme"""
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        result = validate_base64_image(data_url, "image")
        # 应该返回原始数据
        self.assertEqual(result, data_url)
    
    def test_validate_base64_invalid_format(self):
        """测试 Base64 图片验证 - 无效格式"""
        with self.assertRaises(ValidationError) as context:
            validate_base64_image("not-valid-base64!@#", "image")
        self.assertIn("不是有效的 Base64 格式", str(context.exception))
    
    def test_sanitize_filename(self):
        """测试文件名清理"""
        # 移除特殊字符
        result = sanitize_filename("test@file#name!.txt")
        self.assertEqual(result, "testfilename.txt")
        
        # 移除路径分隔符
        result = sanitize_filename("../../../etc/passwd")
        self.assertEqual(result, "etcpasswd")
        
        # 长文件名截断
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        self.assertLessEqual(len(result), 200)
        self.assertTrue(result.endswith(".txt"))


class TestRateLimiter(unittest.TestCase):
    """速率限制器测试"""
    
    def test_rate_limiter_basic(self):
        """测试速率限制 - 基本功能"""
        limiter = RateLimiter(max_calls=3, time_window=1.0)
        
        # 前3次调用应该被允许
        self.assertTrue(limiter.is_allowed("client1"))
        self.assertTrue(limiter.is_allowed("client1"))
        self.assertTrue(limiter.is_allowed("client1"))
        
        # 第4次调用应该被拒绝
        self.assertFalse(limiter.is_allowed("client1"))
    
    def test_rate_limiter_different_clients(self):
        """测试速率限制 - 不同客户端"""
        limiter = RateLimiter(max_calls=2, time_window=1.0)
        
        # 客户端1
        self.assertTrue(limiter.is_allowed("client1"))
        self.assertTrue(limiter.is_allowed("client1"))
        self.assertFalse(limiter.is_allowed("client1"))
        
        # 客户端2应该有独立的限制
        self.assertTrue(limiter.is_allowed("client2"))
        self.assertTrue(limiter.is_allowed("client2"))
        self.assertFalse(limiter.is_allowed("client2"))
    
    def test_rate_limiter_time_window(self):
        """测试速率限制 - 时间窗口"""
        limiter = RateLimiter(max_calls=2, time_window=0.1)
        
        # 使用完配额
        self.assertTrue(limiter.is_allowed("client1"))
        self.assertTrue(limiter.is_allowed("client1"))
        self.assertFalse(limiter.is_allowed("client1"))
        
        # 等待时间窗口过期
        time.sleep(0.15)
        
        # 应该可以再次调用
        self.assertTrue(limiter.is_allowed("client1"))
    
    def test_rate_limiter_get_remaining(self):
        """测试速率限制 - 获取剩余次数"""
        limiter = RateLimiter(max_calls=5, time_window=1.0)
        
        # 初始剩余次数
        self.assertEqual(limiter.get_remaining("client1"), 5)
        
        # 使用一次后
        limiter.is_allowed("client1")
        self.assertEqual(limiter.get_remaining("client1"), 4)
        
        # 使用两次后
        limiter.is_allowed("client1")
        self.assertEqual(limiter.get_remaining("client1"), 3)
    
    def test_rate_limiter_reset(self):
        """测试速率限制 - 重置"""
        limiter = RateLimiter(max_calls=2, time_window=1.0)
        
        # 使用完配额
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        self.assertFalse(limiter.is_allowed("client1"))
        
        # 重置
        limiter.reset("client1")
        
        # 应该可以再次调用
        self.assertTrue(limiter.is_allowed("client1"))


class TestTokenBucket(unittest.TestCase):
    """令牌桶测试"""
    
    def test_token_bucket_basic(self):
        """测试令牌桶 - 基本功能"""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        
        # 初始应该有满桶的令牌
        for _ in range(5):
            self.assertTrue(bucket.consume("client1"))
        
        # 令牌耗尽
        self.assertFalse(bucket.consume("client1"))
    
    def test_token_bucket_refill(self):
        """测试令牌桶 - 令牌填充"""
        # 每秒填充10个令牌
        bucket = TokenBucket(capacity=10, refill_rate=10.0)
        
        # 消耗所有令牌
        for _ in range(10):
            bucket.consume("client1")
        
        # 应该没有令牌了
        self.assertFalse(bucket.consume("client1"))
        
        # 等待0.5秒，应该填充5个令牌
        time.sleep(0.5)
        
        # 应该可以消耗约5个令牌（允许一些误差）
        successful = 0
        for _ in range(10):
            if bucket.consume("client1", tokens=1):
                successful += 1
        
        self.assertGreaterEqual(successful, 4)  # 至少4个（允许误差）
        self.assertLessEqual(successful, 6)     # 最多6个（允许误差）
    
    def test_token_bucket_different_clients(self):
        """测试令牌桶 - 不同客户端"""
        bucket = TokenBucket(capacity=3, refill_rate=1.0)
        
        # 客户端1消耗令牌
        self.assertTrue(bucket.consume("client1"))
        self.assertTrue(bucket.consume("client1"))
        
        # 客户端2应该有独立的桶
        self.assertTrue(bucket.consume("client2"))
        self.assertTrue(bucket.consume("client2"))
        self.assertTrue(bucket.consume("client2"))


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestInputValidation))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRateLimiter))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestTokenBucket))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回测试结果
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
