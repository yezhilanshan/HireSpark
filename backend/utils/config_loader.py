"""
配置加载器 - 加载和管理系统配置
"""
import yaml
import os
from pathlib import Path
from typing import Any, Dict, Optional

# 尝试加载 .env，dotenv 是可选依赖
try:
    from dotenv import load_dotenv
    _has_dotenv = True
except ImportError:
    _has_dotenv = False
    load_dotenv = None  # type: ignore[assignment]

# 先加载 .env。优先项目根目录，其次兼容 backend 目录内的 .env。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

if _has_dotenv and load_dotenv:
    for dotenv_path in (PROJECT_ROOT / '.env', BACKEND_ROOT / '.env'):
        if dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path, override=False)


class ConfigLoader:
    """
    配置加载器 - 单例模式
    
    负责加载和管理系统配置文件，提供统一的配置访问接口。
    """
    
    _instance = None
    _config = None
    _config_file = None
    
    def __new__(cls):
        """单例模式 - 确保全局只有一个配置实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化配置加载器"""
        if self._config is None:
            self.load_config()
    
    def load_config(self, config_path: str = 'config.yaml'):
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径（默认为 config.yaml）
        
        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML 格式错误
        """
        # 检查文件是否存在
        if not os.path.exists(config_path):
            # 尝试在多个可能的位置查找配置文件
            possible_paths = [
                config_path,
                os.path.join('backend', config_path),
                os.path.join(os.path.dirname(__file__), config_path),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), config_path)
            ]
            
            config_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
            
            if config_path is None:
                raise FileNotFoundError(
                    f"配置文件不存在。尝试过以下路径: {possible_paths}"
                )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
                self._config_file = config_path
                print(f"[OK] 配置文件已加载: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {e}")
        except Exception as e:
            raise RuntimeError(f"加载配置文件失败: {e}")
    
    def reload(self):
        """重新加载配置文件"""
        if self._config_file:
            self.load_config(self._config_file)
        else:
            self.load_config()
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号分隔的路径）
        
        Args:
            key_path: 配置路径，如 'detection.gaze_deviation.score'
            default: 默认值（如果配置项不存在）
        
        Returns:
            配置值或默认值
        
        Example:
            >>> config.get('server.port', 5000)
            5000
            >>> config.get('detection.gaze_deviation.enabled')
            True
        """
        if self._config is None:
            self.load_config()
        
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict:
        """
        获取整个配置节
        
        Args:
            section: 节名称，如 'detection', 'server'
        
        Returns:
            配置节的字典，如果不存在返回空字典
        """
        return self.get(section, {})
    
    def set(self, key_path: str, value: Any):
        """
        设置配置值（仅在内存中，不保存到文件）
        
        Args:
            key_path: 配置路径
            value: 新值
        """
        if self._config is None:
            self.load_config()
        
        keys = key_path.split('.')
        config = self._config
        
        # 遍历到倒数第二个键
        for key in keys[:-1]:
            if key not in config or not isinstance(config[key], dict):
                config[key] = {}
            config = config[key]
        
        # 设置最后一个键的值
        config[keys[-1]] = value
    
    def get_all(self) -> Dict:
        """
        获取所有配置
        
        Returns:
            完整配置字典的副本
        """
        if self._config is None:
            self.load_config()
        
        return self._config.copy() if self._config else {}
    
    def exists(self, key_path: str) -> bool:
        """
        检查配置项是否存在
        
        Args:
            key_path: 配置路径
        
        Returns:
            True 如果存在，False 否则
        """
        return self.get(key_path) is not None
    
    def is_enabled(self, feature_path: str) -> bool:
        """
        检查功能是否启用（便捷方法）
        
        Args:
            feature_path: 功能配置路径
        
        Returns:
            True 如果启用，False 否则
        """
        enabled = self.get(f"{feature_path}.enabled", False)
        return bool(enabled)
    
    def get_logging_config(self) -> Dict:
        """
        获取日志配置
        
        Returns:
            日志配置字典
        """
        return self.get_section('logging')
    
    def get_database_config(self) -> Dict:
        """
        获取数据库配置
        
        Returns:
            数据库配置字典
        """
        return self.get_section('database')
    
    def get_detection_config(self) -> Dict:
        """
        获取检测配置
        
        Returns:
            检测配置字典
        """
        return self.get_section('detection')
    
    def get_server_config(self) -> Dict:
        """
        获取服务器配置
        
        Returns:
            服务器配置字典
        """
        return self.get_section('server')
    
    def save_config(self, output_path: Optional[str] = None):
        """
        保存配置到文件
        
        Args:
            output_path: 输出文件路径（默认覆盖原文件）
        """
        if self._config is None:
            raise RuntimeError("没有可保存的配置")
        
        output_path = output_path or self._config_file or 'config.yaml'
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    self._config,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False
                )
            print(f"[OK] 配置已保存到: {output_path}")
        except Exception as e:
            raise RuntimeError(f"保存配置文件失败: {e}")
    
    def validate_config(self) -> "tuple[bool, list]":
        """
        验证配置的完整性
        
        Returns:
            (is_valid, errors): 是否有效，错误列表
        """
        errors = []
        
        # 必需的配置项
        required_keys = [
            'system.name',
            'server.host',
            'server.port',
            'database.path',
            'logging.level'
        ]
        
        for key in required_keys:
            if not self.exists(key):
                errors.append(f"缺少必需配置项: {key}")
        
        # 验证数值范围
        port = self.get('server.port')
        if port and (not isinstance(port, int) or port < 1 or port > 65535):
            errors.append(f"server.port 无效: {port}（应为 1-65535）")
        
        # 验证日志级别
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        log_level = self.get('logging.level')
        if log_level and log_level not in valid_levels:
            errors.append(f"logging.level 无效: {log_level}（应为 {valid_levels}）")
        
        return (len(errors) == 0, errors)
    
    def print_config(self, section: Optional[str] = None):
        """
        打印配置（用于调试）
        
        Args:
            section: 可选，只打印指定节
        """
        if section:
            config_to_print = self.get_section(section)
            print(f"\n=== 配置节: {section} ===")
        else:
            config_to_print = self.get_all()
            print("\n=== 完整配置 ===")
        
        print(yaml.dump(
            config_to_print,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
        ))
    
    def __repr__(self):
        return f"<ConfigLoader: {self._config_file}>"


# 创建全局配置实例
config = ConfigLoader()


# 便捷函数
def get_config(key_path: str, default: Any = None) -> Any:
    """
    获取配置值（全局函数）
    
    Args:
        key_path: 配置路径
        default: 默认值
    
    Returns:
        配置值
    """
    return config.get(key_path, default)


def is_debug_mode() -> bool:
    """检查是否为调试模式"""
    return config.get('system.debug', False)


def is_development() -> bool:
    """检查是否为开发环境"""
    return config.get('system.environment') == 'development'


def is_production() -> bool:
    """检查是否为生产环境"""
    return config.get('system.environment') == 'production'


if __name__ == '__main__':
    # 测试配置加载器
    print("=" * 60)
    print("配置加载器测试")
    print("=" * 60)
    
    try:
        # 加载配置
        cfg = ConfigLoader()
        
        # 验证配置
        is_valid, errors = cfg.validate_config()
        if is_valid:
            print("[OK] 配置验证通过")
        else:
            print("[ERROR] 配置验证失败:")
            for error in errors:
                print(f"  - {error}")
        
        # 测试获取配置
        print(f"\n系统名称: {cfg.get('system.name')}")
        print(f"服务器端口: {cfg.get('server.port')}")
        print(f"日志级别: {cfg.get('logging.level')}")
        print(f"眼神偏离分数: {cfg.get('detection.gaze_deviation.score')}")
        print(f"数据库路径: {cfg.get('database.path')}")
        
        # 测试功能开关
        print(f"\n真人验证: {'启用' if cfg.is_enabled('features.liveness_check') else '禁用'}")
        print(f"音频检测: {'启用' if cfg.is_enabled('features.audio_detection') else '禁用'}")
        
        # 测试环境检查
        print(f"\n调试模式: {is_debug_mode()}")
        print(f"开发环境: {is_development()}")
        print(f"生产环境: {is_production()}")
        
        # 打印部分配置
        print("\n" + "=" * 60)
        cfg.print_config('detection')
        
        print("=" * 60)
        print("[OK] 配置加载器测试完成")
        
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
