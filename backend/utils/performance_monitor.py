"""
性能监控系统 - 实时监控系统性能指标
"""
import time
import psutil
import threading
from collections import deque
from typing import Dict, Optional, Callable, Any
from datetime import datetime
from functools import wraps

from utils.config_loader import config
from utils.logger import get_logger

logger = get_logger(__name__)


class PerformanceMonitor:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化性能监控器"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # 配置
        self.enabled = config.get('performance.enable_monitoring', True)
        self.max_fps = config.get('performance.max_fps', 30)
        self.monitoring_interval = config.get('performance.monitoring_interval', 10)
        self.history_size = config.get('performance.history_size', 100)
        self.log_stats = config.get('performance.log_stats', False)
        
        # FPS 追踪
        self.frame_times = deque(maxlen=self.history_size)
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
        
        # 处理延迟追踪
        self.processing_times = deque(maxlen=self.history_size)
        self.avg_processing_time = 0.0
        
        # 系统资源监控
        self.cpu_percent = 0.0
        self.memory_percent = 0.0
        self.memory_used_mb = 0.0
        
        # 函数执行时间统计
        self.function_stats = {}
        
        # 监控线程
        self.monitoring_thread = None
        self.should_monitor = False
        
        # 性能历史
        self.performance_history = deque(maxlen=self.history_size)
        
        logger.info(f"性能监控器初始化 - 已{'启用' if self.enabled else '禁用'}")
    
    def start_monitoring(self):
        """启动后台监控线程"""
        if not self.enabled or self.should_monitor:
            return
        
        self.should_monitor = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info("性能监控线程已启动")
    
    def stop_monitoring(self):
        """停止后台监控"""
        self.should_monitor = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2.0)
        logger.info("性能监控线程已停止")
    
    def _monitoring_loop(self):
        """后台监控循环"""
        last_log_time = time.time()
        
        while self.should_monitor:
            try:
                # 更新系统资源
                self._update_system_resources()
                
                # 定期输出日志
                current_time = time.time()
                if current_time - last_log_time >= self.monitoring_interval:
                    self._log_performance_stats()
                    last_log_time = current_time
                
                time.sleep(1.0)  # 每秒更新一次
                
            except Exception as e:
                logger.error(f"性能监控异常: {e}", exc_info=True)
    
    def _update_system_resources(self):
        """更新系统资源使用情况"""
        try:
            # CPU 使用率（非阻塞）
            self.cpu_percent = psutil.cpu_percent(interval=0)
            
            # 内存使用
            memory = psutil.virtual_memory()
            self.memory_percent = memory.percent
            self.memory_used_mb = memory.used / (1024 * 1024)
            
        except Exception as e:
            logger.error(f"更新系统资源失败: {e}")
    
    def record_frame(self, processing_time: Optional[float] = None):
        """
        记录一帧的处理
        
        Args:
            processing_time: 帧处理耗时（秒），如果提供则记录
        """
        if not self.enabled:
            return
        
        current_time = time.time()
        self.frame_times.append(current_time)
        self.frame_count += 1
        
        # 记录处理时间
        if processing_time is not None:
            self.processing_times.append(processing_time)
            if self.processing_times:
                self.avg_processing_time = sum(self.processing_times) / len(self.processing_times)
        
        # 计算 FPS（使用滑动窗口）
        if len(self.frame_times) >= 2:
            time_span = self.frame_times[-1] - self.frame_times[0]
            if time_span > 0:
                self.current_fps = (len(self.frame_times) - 1) / time_span
    
    def get_fps(self) -> float:
        """获取当前 FPS"""
        return round(self.current_fps, 2)
    
    def get_avg_processing_time(self) -> float:
        """获取平均处理时间（毫秒）"""
        return round(self.avg_processing_time * 1000, 2)
    
    def get_system_stats(self) -> Dict[str, Any]:
        return {
            'cpu_percent': round(self.cpu_percent, 2),
            'memory_percent': round(self.memory_percent, 2),
            'memory_used_mb': round(self.memory_used_mb, 2),
            'fps': self.get_fps(),
            'avg_processing_time_ms': self.get_avg_processing_time(),
            'frame_count': self.frame_count,
            'timestamp': time.time()
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:

        summary = self.get_system_stats()
        
        # 添加函数统计
        if self.function_stats:
            summary['function_stats'] = {
                name: {
                    'avg_time_ms': round(stats['total_time'] / stats['count'] * 1000, 2),
                    'total_time_ms': round(stats['total_time'] * 1000, 2),
                    'count': stats['count'],
                    'min_time_ms': round(stats['min_time'] * 1000, 2),
                    'max_time_ms': round(stats['max_time'] * 1000, 2)
                }
                for name, stats in self.function_stats.items()
            }
        
        return summary
    
    def record_function_time(self, func_name: str, execution_time: float):

        if not self.enabled:
            return
        
        if func_name not in self.function_stats:
            self.function_stats[func_name] = {
                'count': 0,
                'total_time': 0.0,
                'min_time': float('inf'),
                'max_time': 0.0
            }
        
        stats = self.function_stats[func_name]
        stats['count'] += 1
        stats['total_time'] += execution_time
        stats['min_time'] = min(stats['min_time'], execution_time)
        stats['max_time'] = max(stats['max_time'], execution_time)
    
    def _log_performance_stats(self):
        """记录性能统计日志"""
        stats = self.get_system_stats()
        
        if self.log_stats:
            logger.info(
                f"性能统计 - "
                f"FPS: {stats['fps']}, "
                f"处理时间: {stats['avg_processing_time_ms']}ms, "
                f"CPU: {stats['cpu_percent']}%, "
                f"内存: {stats['memory_percent']}% ({stats['memory_used_mb']}MB)"
            )
        
        # 保存到历史
        self.performance_history.append({
            'timestamp': datetime.now().isoformat(),
            'stats': stats
        })
    
    def reset_stats(self):
        """重置所有统计数据"""
        self.frame_times.clear()
        self.processing_times.clear()
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
        self.avg_processing_time = 0.0
        self.function_stats.clear()
        logger.info("性能统计已重置")
    
    def get_bottlenecks(self, threshold_ms: float = 100.0) -> list:

        bottlenecks = []
        
        for func_name, stats in self.function_stats.items():
            avg_time_ms = (stats['total_time'] / stats['count']) * 1000
            if avg_time_ms > threshold_ms:
                bottlenecks.append({
                    'function': func_name,
                    'avg_time_ms': round(avg_time_ms, 2),
                    'count': stats['count']
                })
        
        # 按平均时间排序
        bottlenecks.sort(key=lambda x: x['avg_time_ms'], reverse=True)
        return bottlenecks


# 全局性能监控实例
performance_monitor = PerformanceMonitor()


def measure_time(func_name: Optional[str] = None):

    def decorator(func: Callable) -> Callable:
        name = func_name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not performance_monitor.enabled:
                return func(*args, **kwargs)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                execution_time = time.time() - start_time
                performance_monitor.record_function_time(name, execution_time)
        
        return wrapper
    return decorator


class PerformanceContext:

    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time and performance_monitor.enabled:
            execution_time = time.time() - self.start_time
            performance_monitor.record_function_time(self.operation_name, execution_time)


# 便捷函数
def start_monitoring():
    """启动性能监控"""
    performance_monitor.start_monitoring()


def stop_monitoring():
    """停止性能监控"""
    performance_monitor.stop_monitoring()


def get_stats() -> Dict[str, Any]:
    """获取性能统计"""
    return performance_monitor.get_system_stats()


def get_summary() -> Dict[str, Any]:
    """获取性能摘要"""
    return performance_monitor.get_performance_summary()


if __name__ == '__main__':
    # 测试代码
    print("="*60)
    print("性能监控系统测试")
    print("="*60)
    
    # 启动监控
    performance_monitor.start_monitoring()
    print("\n✓ 性能监控已启动")
    
    # 测试 FPS 记录
    print("\n测试 FPS 记录...")
    for i in range(30):
        time.sleep(0.033)  # 模拟 30 FPS
        performance_monitor.record_frame(0.025)
    
    print(f"✓ 当前 FPS: {performance_monitor.get_fps()}")
    print(f"✓ 平均处理时间: {performance_monitor.get_avg_processing_time()}ms")
    
    # 测试装饰器
    @measure_time()
    def slow_function():
        time.sleep(0.1)
        return "完成"
    
    @measure_time("fast_operation")
    def fast_function():
        time.sleep(0.01)
        return "完成"
    
    print("\n测试函数执行时间测量...")
    for _ in range(5):
        slow_function()
        fast_function()
    
    # 测试上下文管理器
    print("\n测试上下文管理器...")
    with PerformanceContext("custom_operation"):
        time.sleep(0.05)
    
    # 等待几秒让监控线程收集数据
    time.sleep(3)
    
    # 获取统计信息
    print("\n" + "="*60)
    print("性能统计摘要")
    print("="*60)
    summary = performance_monitor.get_performance_summary()
    
    print(f"FPS: {summary['fps']}")
    print(f"平均处理时间: {summary['avg_processing_time_ms']}ms")
    print(f"CPU 使用率: {summary['cpu_percent']}%")
    print(f"内存使用: {summary['memory_percent']}% ({summary['memory_used_mb']}MB)")
    print(f"已处理帧数: {summary['frame_count']}")
    
    if 'function_stats' in summary:
        print("\n函数执行统计:")
        for func_name, stats in summary['function_stats'].items():
            print(f"  {func_name}:")
            print(f"    平均: {stats['avg_time_ms']}ms")
            print(f"    最小: {stats['min_time_ms']}ms")
            print(f"    最大: {stats['max_time_ms']}ms")
            print(f"    调用次数: {stats['count']}")
    
    # 识别瓶颈
    bottlenecks = performance_monitor.get_bottlenecks(threshold_ms=50.0)
    if bottlenecks:
        print("\n性能瓶颈 (>50ms):")
        for bottleneck in bottlenecks:
            print(f"  {bottleneck['function']}: {bottleneck['avg_time_ms']}ms ({bottleneck['count']} 次调用)")
    
    # 停止监控
    performance_monitor.stop_monitoring()
    print("\n✓ 性能监控已停止")
    print("="*60)
