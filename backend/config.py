"""
配置文件 - 所有检测阈值和系统参数
"""

# ================== 眼神追踪阈值 ==================
# 头部姿态角度阈值（度）
YAW_THRESHOLD = 25              # 左右转头角度阈值
PITCH_UP_THRESHOLD = 15         # 抬头角度阈值
PITCH_DOWN_THRESHOLD = -20      # 低头角度阈值

# 位置偏移阈值（相对于画面中心的比例）
OFFSET_THRESHOLD_X = 0.25       # 水平方向偏移阈值（25%画面宽度）
OFFSET_THRESHOLD_Y = 0.25       # 垂直方向偏移阈值（25%画面高度）

# 眼神偏离持续时间阈值（秒）
GAZE_DEVIATION_DURATION = 3     # 连续偏离多少秒触发警告

# ================== 嘴部检测阈值 ==================
# MAR（Mouth Aspect Ratio）阈值
MOUTH_OPEN_THRESHOLD = 0.5      # 嘴部开合比例阈值
MOUTH_OPEN_DURATION = 2         # 异常张嘴持续时间阈值（秒）

# ================== 真人检测阈值 ==================
# EAR（Eye Aspect Ratio）阈值
EYE_BLINK_THRESHOLD = 0.25      # 眼睛闭合阈值
EYE_BLINK_FRAMES = 2            # 连续多少帧认为是眨眼

# 嘴部张开阈值（真人验证）
LIVENESS_MOUTH_THRESHOLD = 0.5  # 真人验证时的张嘴阈值

# ================== 作弊评分 ==================
# 各类异常行为的扣分
GAZE_DEVIATION_SCORE = 30       # 眼神严重偏离扣分
MULTI_PERSON_SCORE = 50         # 检测到多人扣分
MOUTH_OPEN_SCORE = 20           # 异常说话扣分
OFF_SCREEN_TIME_SCORE = 25      # 屏幕外注视时间占比扣分

# 作弊概率计算参数
SIGMOID_OFFSET = 50             # Sigmoid函数偏移量
SIGMOID_SCALE = 10              # Sigmoid函数缩放系数

# ================== 风险等级阈值 ==================
LOW_RISK_THRESHOLD = 30         # 低风险阈值（0-30%）
MEDIUM_RISK_THRESHOLD = 60      # 中风险阈值（30-60%）
# 60%以上为高风险

# ================== MediaPipe 配置 ==================
# 人脸检测参数
MIN_DETECTION_CONFIDENCE = 0.5  # 最小检测置信度
MIN_TRACKING_CONFIDENCE = 0.5   # 最小追踪置信度
MAX_NUM_FACES = 2               # 最大检测人脸数量

# ================== 视频处理参数 ==================
VIDEO_WIDTH = 640               # 视频宽度
VIDEO_HEIGHT = 480              # 视频高度
VIDEO_FPS = 20                  # 目标帧率

# ================== Socket.IO 配置 ==================
SOCKETIO_ASYNC_MODE = 'threading'  # Socket.IO异步模式
SOCKETIO_CORS_ALLOWED_ORIGINS = '*'  # CORS跨域设置

# ================== 服务器配置 ==================
FLASK_HOST = '127.0.0.1'        # Flask服务器地址
FLASK_PORT = 5000               # Flask服务器端口
FLASK_DEBUG = True              # 调试模式

# ================== 报告配置 ==================
REPORT_OUTPUT_DIR = 'reports'   # PDF报告输出目录
REPORT_FONT_SIZE = 12           # 报告字体大小

# ================== 数据缓冲区大小 ==================
DATA_BUFFER_SIZE = 10           # 数据平滑缓冲区大小（用于平滑角度数据）

# ================== 时间窗口 ==================
TIME_WINDOW_SIZE = 60           # 时间窗口大小（秒），用于计算屏幕外注视占比
