"""
utils 包初始化文件
"""
VideoProcessor = None
DataManager = None
ReportGenerator = None
LLMManager = None
llm_manager = None

# 可选依赖：当环境中缺少 cv2 等库时，避免在导入 utils 包时直接失败。
try:
	from .video_processor import VideoProcessor
except Exception:
	VideoProcessor = None

try:
	from .data_manager import DataManager
except Exception:
	DataManager = None

try:
	from .report_generator import ReportGenerator
except Exception:
	ReportGenerator = None

try:
	from .llm_manager import LLMManager, llm_manager
except Exception:
	LLMManager = None
	llm_manager = None

__all__ = ['VideoProcessor', 'DataManager', 'ReportGenerator', 'LLMManager', 'llm_manager']
