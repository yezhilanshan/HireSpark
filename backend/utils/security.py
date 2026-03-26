"""
安全工具模块
提供输入验证、速率限制等安全功能
"""
import time
import re
from typing import Any, Dict, Optional, Callable
from functools import wraps
from threading import Lock


class ValidationError(Exception):
    """输入验证错误"""
    pass


def validate_string(value: Any, field_name: str, 
                   min_length: int = 0, 
                   max_length: int = 1000,
                   pattern: Optional[str] = None,
                   allow_empty: bool = False) -> str:
    """
    验证字符串输入
    
    参数:
        value: 要验证的值
        field_name: 字段名称
        min_length: 最小长度
        max_length: 最大长度
        pattern: 正则表达式模式
        allow_empty: 是否允许空字符串
        
    返回:
        验证后的字符串
        
    抛出:
        ValidationError: 验证失败
    """
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} 必须是字符串")
    
    if not value and not allow_empty:
        raise ValidationError(f"{field_name} 不能为空")
    
    if len(value) < min_length:
        raise ValidationError(f"{field_name} 长度不能小于 {min_length}")
    
    if len(value) > max_length:
        raise ValidationError(f"{field_name} 长度不能超过 {max_length}")
    
    if pattern and not re.match(pattern, value):
        raise ValidationError(f"{field_name} 格式不正确")
    
    return value


def validate_number(value: Any, field_name: str,
                   min_val: Optional[float] = None,
                   max_val: Optional[float] = None,
                   allow_float: bool = True) -> float:
    """
    验证数字输入
    
    参数:
        value: 要验证的值
        field_name: 字段名称
        min_val: 最小值
        max_val: 最大值
        allow_float: 是否允许浮点数
        
    返回:
        验证后的数字
        
    抛出:
        ValidationError: 验证失败
    """
    try:
        if allow_float:
            num_value = float(value)
        else:
            num_value = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} 必须是有效的数字")
    
    if min_val is not None and num_value < min_val:
        raise ValidationError(f"{field_name} 不能小于 {min_val}")
    
    if max_val is not None and num_value > max_val:
        raise ValidationError(f"{field_name} 不能大于 {max_val}")
    
    return num_value


def validate_base64_image(data: str, field_name: str = "图片数据",
                         max_size: int = 10 * 1024 * 1024) -> str:
    """
    验证 Base64 编码的图片数据
    
    参数:
        data: Base64 数据
        field_name: 字段名称
        max_size: 最大大小（字节）
        
    返回:
        验证后的数据
        
    抛出:
        ValidationError: 验证失败
    """
    if not isinstance(data, str):
        raise ValidationError(f"{field_name} 必须是字符串")
    
    # 检查是否包含 data URL scheme
    if data.startswith('data:image/'):
        # 提取实际的 base64 数据
        try:
            header, b64_data = data.split(',', 1)
        except ValueError:
            raise ValidationError(f"{field_name} 格式不正确")
    else:
        b64_data = data
    
    # 验证 base64 格式
    if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', b64_data):
        raise ValidationError(f"{field_name} 不是有效的 Base64 格式")
    
    # 检查大小
    data_size = len(b64_data.encode('utf-8'))
    if data_size > max_size:
        raise ValidationError(f"{field_name} 超过最大大小限制 ({max_size} 字节)")
    
    return data


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除不安全字符
    
    参数:
        filename: 原始文件名
        
    返回:
        清理后的文件名
    """
    # 首先移除路径遍历模式（.. 和 路径分隔符）
    safe_name = filename.replace('..', '').replace('/', '').replace('\\', '')
    
    # 然后移除其他特殊字符（保留单词字符、空格、点号、连字符）
    safe_name = re.sub(r'[^\w\s.-]', '', safe_name)
    
    # 移除多余的点号（保留扩展名的点号）
    safe_name = re.sub(r'\.{2,}', '', safe_name)
    
    # 限制长度
    if len(safe_name) > 200:
        name_parts = safe_name.rsplit('.', 1)
        if len(name_parts) == 2:
            safe_name = name_parts[0][:195] + '.' + name_parts[1]
        else:
            safe_name = safe_name[:200]
    return safe_name


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_calls: int, time_window: float):
        """
        初始化速率限制器
        
        参数:
            max_calls: 时间窗口内最大调用次数
            time_window: 时间窗口（秒）
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: Dict[str, list] = {}
        self.lock = Lock()
    
    def is_allowed(self, client_id: str) -> bool:
        """
        检查客户端是否允许访问
        
        参数:
            client_id: 客户端标识符
            
        返回:
            是否允许访问
        """
        with self.lock:
            current_time = time.time()
            
            # 初始化客户端记录
            if client_id not in self.calls:
                self.calls[client_id] = []
            
            # 移除过期的调用记录
            self.calls[client_id] = [
                call_time for call_time in self.calls[client_id]
                if current_time - call_time < self.time_window
            ]
            
            # 检查是否超过限制
            if len(self.calls[client_id]) >= self.max_calls:
                return False
            
            # 记录本次调用
            self.calls[client_id].append(current_time)
            return True
    
    def get_remaining(self, client_id: str) -> int:
        """
        获取剩余可用次数
        
        参数:
            client_id: 客户端标识符
            
        返回:
            剩余次数
        """
        with self.lock:
            current_time = time.time()
            
            if client_id not in self.calls:
                return self.max_calls
            
            # 移除过期记录
            self.calls[client_id] = [
                call_time for call_time in self.calls[client_id]
                if current_time - call_time < self.time_window
            ]
            
            return max(0, self.max_calls - len(self.calls[client_id]))
    
    def reset(self, client_id: str):
        """
        重置客户端的速率限制
        
        参数:
            client_id: 客户端标识符
        """
        with self.lock:
            if client_id in self.calls:
                del self.calls[client_id]


def rate_limit(limiter: RateLimiter):
    """
    速率限制装饰器（用于 Socket.IO 处理器）
    
    参数:
        limiter: RateLimiter 实例
        
    使用示例:
        frame_limiter = RateLimiter(max_calls=20, time_window=1.0)
        
        @socketio.on('process_frame')
        @rate_limit(frame_limiter)
        def handle_frame(data):
            # 处理逻辑
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request
            
            # 获取客户端 ID（使用 session ID）
            client_id = request.sid
            
            # 检查速率限制
            if not limiter.is_allowed(client_id):
                from flask_socketio import emit
                emit('error', {
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'message': '请求过于频繁，请稍后再试'
                })
                return
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class TokenBucket:
    """
    令牌桶算法实现（更平滑的速率限制）
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        初始化令牌桶
        
        参数:
            capacity: 桶容量（最大令牌数）
            refill_rate: 令牌填充速率（令牌/秒）
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets: Dict[str, Dict[str, float]] = {}
        self.lock = Lock()
    
    def consume(self, client_id: str, tokens: int = 1) -> bool:
        """
        消耗令牌
        
        参数:
            client_id: 客户端标识符
            tokens: 要消耗的令牌数
            
        返回:
            是否成功消耗令牌
        """
        with self.lock:
            current_time = time.time()
            
            # 初始化桶
            if client_id not in self.buckets:
                self.buckets[client_id] = {
                    'tokens': float(self.capacity),
                    'last_refill': current_time
                }
            
            bucket = self.buckets[client_id]
            
            # 计算应该填充的令牌数
            time_passed = current_time - bucket['last_refill']
            new_tokens = time_passed * self.refill_rate
            
            # 填充令牌（不超过容量）
            bucket['tokens'] = min(self.capacity, bucket['tokens'] + new_tokens)
            bucket['last_refill'] = current_time
            
            # 尝试消耗令牌
            if bucket['tokens'] >= tokens:
                bucket['tokens'] -= tokens
                return True
            
            return False
