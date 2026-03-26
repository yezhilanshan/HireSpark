"""
日志系统 - 统一的日志记录和管理
"""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from utils.config_loader import config


class LoggerManager:
    """
    日志管理器 - 单例模式
    
    负责初始化和管理系统日志，支持文件轮转、多级别日志、模块化配置。
    """
    
    _instance = None
    _loggers = {}
    _initialized = False
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化日志管理器"""
        if not self._initialized:
            self.setup_logging()
            self._initialized = True
    
    def setup_logging(self):
        """设置日志系统"""
        try:
            # 获取日志配置
            log_config = config.get_logging_config()
            
            if not log_config.get('enabled', True):
                print("⚠ 日志系统已禁用")
                return
            
            # 创建日志目录
            if log_config.get('file', {}).get('enabled', True):
                log_file = log_config.get('file', {}).get('path', 'logs/system.log')
                log_dir = os.path.dirname(log_file)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                    print(f"✓ 创建日志目录: {log_dir}")
            
            print("✓ 日志系统初始化完成")
            
        except Exception as e:
            print(f"✗ 日志系统初始化失败: {e}")
    
    def get_logger(self, name: str = 'interview_system') -> logging.Logger:
        """
        获取日志记录器
        
        Args:
            name: 日志记录器名称（通常是模块名）
        
        Returns:
            配置好的 Logger 对象
        """
        # 如果已经创建过，直接返回
        if name in self._loggers:
            return self._loggers[name]
        
        # 创建新的 logger
        logger = logging.getLogger(name)
        
        # 获取配置
        log_config = config.get_logging_config()
        
        # 设置日志级别
        log_level_str = log_config.get('level', 'INFO')
        
        # 检查是否有模块特定的日志级别
        module_levels = log_config.get('modules', {})
        for module_name, level in module_levels.items():
            if module_name in name:
                log_level_str = level
                break
        
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        logger.setLevel(log_level)
        
        # 清除现有的处理器（避免重复）
        logger.handlers.clear()
        
        # 获取日志格式
        log_format = log_config.get('format', {}).get('standard',
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        formatter = logging.Formatter(log_format)
        
        # 控制台处理器
        if log_config.get('console_output', True):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG if config.get('system.debug') else log_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # 文件处理器（支持日志轮转）
        file_config = log_config.get('file', {})
        if file_config.get('enabled', True):
            log_file = file_config.get('path', 'logs/system.log')
            max_size = file_config.get('max_size', 10485760)  # 10MB
            backup_count = file_config.get('backup_count', 5)
            encoding = file_config.get('encoding', 'utf-8')
            
            try:
                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=max_size,
                    backupCount=backup_count,
                    encoding=encoding
                )
                file_handler.setLevel(logging.INFO)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                print(f"✗ 创建文件日志处理器失败: {e}")
        
        # 缓存 logger
        self._loggers[name] = logger
        
        return logger
    
    def set_level(self, name: str, level: str):
        """
        设置指定日志记录器的级别
        
        Args:
            name: 日志记录器名称
            level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        """
        if name in self._loggers:
            log_level = getattr(logging, level.upper(), logging.INFO)
            self._loggers[name].setLevel(log_level)
    
    def clear_handlers(self, name: str):
        """清除指定日志记录器的所有处理器"""
        if name in self._loggers:
            self._loggers[name].handlers.clear()
    
    def list_loggers(self):
        """列出所有已创建的日志记录器"""
        return list(self._loggers.keys())


# 创建全局日志管理器实例
_log_manager = LoggerManager()


def get_logger(name: str = 'interview_system') -> logging.Logger:
    """
    获取日志记录器（全局函数）
    
    Args:
        name: 日志记录器名称
    
    Returns:
        Logger 对象
    
    Example:
        >>> from utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("系统启动")
        >>> logger.warning("检测到异常")
        >>> logger.error("发生错误", exc_info=True)
    """
    return _log_manager.get_logger(name)


# 创建默认的系统日志记录器
logger = get_logger('interview_system')


class PerformanceLogger:
    """
    性能日志记录器 - 用于记录性能指标
    """
    
    def __init__(self, name: str = 'performance'):
        self.logger = get_logger(name)
        self.start_time = None
    
    def start(self, operation: str):
        """开始计时"""
        self.start_time = datetime.now()
        self.logger.debug(f"[开始] {operation}")
    
    def end(self, operation: str):
        """结束计时并记录"""
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            self.logger.info(f"[完成] {operation} - 耗时: {elapsed:.3f}秒")
            self.start_time = None
        else:
            self.logger.warning(f"[完成] {operation} - 未调用start()")
    
    def log_metric(self, metric_name: str, value: float, unit: str = ''):
        """记录性能指标"""
        self.logger.info(f"[指标] {metric_name}: {value:.2f} {unit}")


class AuditLogger:
    """
    审计日志记录器 - 用于记录重要操作
    """
    
    def __init__(self, name: str = 'audit'):
        self.logger = get_logger(name)
    
    def log_interview_start(self, interview_id: str):
        """记录面试开始"""
        self.logger.info(f"面试开始 | ID: {interview_id}")
    
    def log_interview_end(self, interview_id: str, duration: float, risk_level: str):
        """记录面试结束"""
        self.logger.info(
            f"面试结束 | ID: {interview_id} | "
            f"时长: {duration:.1f}秒 | 风险: {risk_level}"
        )
    
    def log_event(self, event_type: str, details: str):
        """记录事件"""
        self.logger.info(f"事件记录 | 类型: {event_type} | 详情: {details}")
    
    def log_database_operation(self, operation: str, success: bool, details: str = ''):
        """记录数据库操作"""
        status = "成功" if success else "失败"
        self.logger.info(f"数据库操作 | {operation} | {status} | {details}")
    
    def log_error(self, error_type: str, message: str):
        """记录错误"""
        self.logger.error(f"错误 | 类型: {error_type} | 消息: {message}")


# 创建预定义的日志记录器
performance_logger = PerformanceLogger()
audit_logger = AuditLogger()


def setup_module_logger(module_name: str) -> logging.Logger:
    """
    为模块设置日志记录器
    
    Args:
        module_name: 模块名称（通常使用 __name__）
    
    Returns:
        Logger 对象
    
    Example:
        >>> # 在模块顶部
        >>> from utils.logger import setup_module_logger
        >>> logger = setup_module_logger(__name__)
    """
    return get_logger(module_name)


def log_system_info():
    """记录系统信息"""
    import sys
    import platform
    
    logger.info("=" * 60)
    logger.info("系统信息")
    logger.info("=" * 60)
    logger.info(f"系统名称: {config.get('system.name')}")
    logger.info(f"版本: {config.get('system.version')}")
    logger.info(f"环境: {config.get('system.environment')}")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"平台: {platform.platform()}")
    logger.info("=" * 60)


def log_configuration():
    """记录关键配置"""
    logger.info("关键配置:")
    logger.info(f"  服务器: {config.get('server.host')}:{config.get('server.port')}")
    logger.info(f"  数据库: {config.get('database.path')}")
    logger.info(f"  日志级别: {config.get('logging.level')}")
    logger.info(f"  调试模式: {config.get('system.debug')}")


if __name__ == '__main__':
    # 测试日志系统
    print("=" * 60)
    print("日志系统测试")
    print("=" * 60)
    
    # 测试基本日志
    test_logger = get_logger('test_module')
    
    test_logger.debug("这是调试信息")
    test_logger.info("这是普通信息")
    test_logger.warning("这是警告信息")
    test_logger.error("这是错误信息")
    
    try:
        # 模拟错误
        raise ValueError("测试异常")
    except Exception as e:
        test_logger.error("捕获到异常", exc_info=True)
    
    # 测试性能日志
    print("\n" + "=" * 60)
    print("性能日志测试")
    print("=" * 60)
    
    perf_logger = PerformanceLogger()
    perf_logger.start("数据处理")
    import time
    time.sleep(0.1)
    perf_logger.end("数据处理")
    perf_logger.log_metric("FPS", 25.5, "fps")
    perf_logger.log_metric("CPU使用率", 45.2, "%")
    
    # 测试审计日志
    print("\n" + "=" * 60)
    print("审计日志测试")
    print("=" * 60)
    
    audit = AuditLogger()
    audit.log_interview_start("test_001")
    audit.log_event("gaze_deviation", "眼神向左偏离3秒")
    audit.log_database_operation("保存面试记录", True, "test_001")
    audit.log_interview_end("test_001", 300.5, "MEDIUM")
    
    # 测试系统信息
    print("\n" + "=" * 60)
    print("系统信息日志")
    print("=" * 60)
    log_system_info()
    log_configuration()
    
    print("\n" + "=" * 60)
    print("✓ 日志系统测试完成")
    print("=" * 60)
