"""
Flask 主服务 - Socket.IO 实时通信
AI 模拟面试与能力提升平台【改造进行中】
"""
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS # 跨域资源共享中间件
import time
import os
import json
import threading
from datetime import datetime
from pathlib import Path
from collections import Counter

# 导入自定义模块
from utils import DataManager, ReportGenerator
try:
    from utils.llm_manager import llm_manager
    llm_import_error = None
except Exception as e:
    llm_manager = None
    llm_import_error = str(e)
try:
    from utils.asr_manager import asr_manager
    asr_import_error = None
except Exception as e:
    asr_manager = None
    asr_import_error = str(e)
try:
    from utils.tts_manager import tts_manager
    tts_import_error = None
except Exception as e:
    tts_manager = None
    tts_import_error = str(e)
from utils.config_loader import config
from utils.logger import get_logger
from utils.performance_monitor import performance_monitor, measure_time
from utils.security import (
    RateLimiter,
    rate_limit,
    validate_string,
    ValidationError
)
from database import DatabaseManager

# 初始化日志
logger = get_logger(__name__)

# 初始化 Flask 应用
app = Flask(__name__)

# 获取或生成 SECRET_KEY
import secrets
SECRET_KEY = config.get('server.secret_key')
if not SECRET_KEY or SECRET_KEY == 'interview-anti-cheating-secret':
    SECRET_KEY = secrets.token_hex(32)
    logger.warning("未配置 SECRET_KEY，已生成随机密钥。生产环境请在 config.yaml 中设置安全的密钥！")
app.config['SECRET_KEY'] = SECRET_KEY

# 获取配置
FLASK_HOST = config.get('server.host', '0.0.0.0')# 监听地址
FLASK_PORT = config.get('server.port', 5000)# 监听端口
FLASK_DEBUG = config.get('system.debug', False)# 调试模式
CORS_ORIGINS = config.get('server.cors_origins', ['*'])# 跨域配置

CORS(app, origins=CORS_ORIGINS)

logger.info(f"Flask 应用初始化完成 - Host: {FLASK_HOST}, Port: {FLASK_PORT}, Debug: {FLASK_DEBUG}") # 日志输出

# 初始化 Socket.IO
socketio = SocketIO(
    app,
    cors_allowed_origins=CORS_ORIGINS,
    async_mode='threading', # 允许使用多线程模式，避免 eventlet/gevent 兼容问题
    max_http_buffer_size=config.get('server.max_buffer_size', 10485760)
)

logger.info("Socket.IO 初始化完成")

if llm_manager is None:
    logger.error(f"LLM 初始化失败，相关功能不可用：{llm_import_error}")
elif getattr(llm_manager, 'enabled', False):
    logger.info("LLM 模块初始化成功")
else:
    logger.warning("LLM 模块已加载，但当前未启用")

# 初始化工具类
logger.info("初始化工具模块...")
data_manager = DataManager()
report_generator = ReportGenerator()
db_manager = DatabaseManager()

# ASR 自动恢复状态（当前实现为单实例 ASR，按客户端缓存回调用于断线重启）
asr_client_callbacks = {}
asr_last_restart_attempt = {}
ASR_RESTART_COOLDOWN_SECONDS = 3

# ASR->LLM 防重入与冷却窗口，避免同一客户端在极短时间内重复触发追问
asr_llm_state_lock = threading.Lock()
asr_llm_processing_clients = set()
asr_llm_last_feedback_ts = {}
ASR_LLM_MIN_INTERVAL_SECONDS = 2.0

# ASR 分句聚合：避免一句话被切成多段后连续触发多次 LLM/TTS
asr_text_buffer_lock = threading.Lock()
asr_text_buffers = {}
asr_text_flush_timers = {}
ASR_TEXT_DEBOUNCE_SECONDS = 2.2


def _emit_tts_audio(client_id: str, text: str):
    """异步发送 TTS 音频到指定客户端。"""
    if not text or not text.strip():
        return
    if not tts_manager or not tts_manager.enabled:
        return

    import threading

    def tts_task():
        try:
            def send_audio_chunk(audio_data):
                import base64
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                socketio.emit('tts_audio', {
                    'audio': audio_base64
                }, to=client_id)

            # 网络抖动时做一次轻量重试，降低偶发无语音概率
            max_attempts = 2
            ok = False
            details = 'unknown tts error'

            for attempt in range(1, max_attempts + 1):
                ok = tts_manager.synthesize(text, callback=send_audio_chunk)  # type: ignore
                if ok:
                    break
                details = getattr(tts_manager, 'last_error', '') or 'unknown tts error'
                logger.warning(f"[TTS] 合成失败，第 {attempt}/{max_attempts} 次：{details}")
                if attempt < max_attempts:
                    time.sleep(0.35)

            if not ok:
                error_payload = {
                    'error': 'TTS synthesis failed',
                    'code': 'TTS_SYNTH_FAIL',
                    'details': details
                }
                logger.info(f"[TTS] 发送错误到前端 - payload: {error_payload}")
                socketio.emit('tts_error', error_payload, to=client_id)
        except Exception as e:
            logger.error(f"[TTS] 合成异常：{e}", exc_info=True)
            socketio.emit('tts_error', {
                'error': 'TTS synthesis exception',
                'code': 'TTS_EXCEPTION',
                'details': str(e)
            }, to=client_id)

    threading.Thread(target=tts_task, daemon=True).start()


def _flush_asr_text_buffer(client_id: str):
    """把聚合后的 ASR 文本提交给 LLM。"""
    text = ''
    with asr_text_buffer_lock:
        timer = asr_text_flush_timers.pop(client_id, None)
        if timer:
            timer.cancel()
        buffer_items = asr_text_buffers.pop(client_id, [])

    if buffer_items:
        text = ''.join(buffer_items).strip()

    if text:
        logger.info(f"[ASR] 聚合提交文本：'{text[:80]}...'")
        _process_asr_text_with_llm(client_id, text)


def _enqueue_asr_text_for_llm(client_id: str, text: str):
    """收集 ASR 分句，并在静默窗口后一次性提交。"""
    cleaned = (text or '').strip()
    if not cleaned:
        return

    with asr_text_buffer_lock:
        asr_text_buffers.setdefault(client_id, []).append(cleaned)

        old_timer = asr_text_flush_timers.get(client_id)
        if old_timer:
            old_timer.cancel()

        timer = threading.Timer(ASR_TEXT_DEBOUNCE_SECONDS, _flush_asr_text_buffer, args=(client_id,))
        timer.daemon = True
        asr_text_flush_timers[client_id] = timer
        timer.start()


def _get_last_interviewer_question(chat_history):
    """从历史中取最近一条面试官提问"""
    if not chat_history:
        return ''
    for item in reversed(chat_history):
        if isinstance(item, dict) and item.get('role') == 'interviewer':
            return item.get('content', '')
    return ''


def _is_noise_text(text: str) -> bool:
    """过滤明显无意义的口头语，避免频繁触发 LLM"""
    normalized = (text or '').strip()
    if not normalized:
        return True
    # 语气词集合
    fillers = {'啊', '嗯', '呃', '哦', '哎', '额', '唉', '哈', '噢', '嘛', '呗', '咯'}
    if normalized in fillers:
        return True
    # 单字直接过滤
    if len(normalized) < 3:
        return True
    # 常见无意义短语
    noise_phrases = {'谢谢', '感谢', '好的', '好的呢', '然后', '还有', '那个', '这个', '就是', '还有谁', '都是谁'}
    if normalized in noise_phrases:
        return True
    return False


def _process_asr_text_with_llm(client_id: str, text: str):
    """ASR 识别结果后端兜底直连 LLM，避免前端事件丢失导致流程中断"""
    logger.info(f"[ASR->LLM] _process_asr_text_with_llm 被调用！client_id={client_id}, text='{text[:50]}...'")

    if llm_manager is None:
        logger.warning("[ASR->LLM] llm_manager 为 None，跳过")
        return

    if not interview_active:
        logger.warning(f"[ASR->LLM] 面试未激活 (interview_active={interview_active})，跳过")
        return

    if _is_noise_text(text):
        logger.warning(f"[ASR->LLM] 过滤噪声文本：'{text}'")
        return

    now = time.time()
    with asr_llm_state_lock:
        if client_id in asr_llm_processing_clients:
            logger.warning(f"[ASR->LLM] 客户端正在处理中，忽略本次识别：'{text[:30]}'")
            return

        last_feedback_ts = asr_llm_last_feedback_ts.get(client_id, 0)
        if now - last_feedback_ts < ASR_LLM_MIN_INTERVAL_SECONDS:
            logger.warning(
                f"[ASR->LLM] 命中冷却窗口({ASR_LLM_MIN_INTERVAL_SECONDS}s)，忽略本次识别：'{text[:30]}'"
            )
            return

        asr_llm_processing_clients.add(client_id)

    try:
        chat_history = current_interview_session.get('chat_history', [])
        current_question = _get_last_interviewer_question(chat_history)
        if not current_question:
            logger.warning("[ASR->LLM] 当前问题为空，跳过本次触发")
            return

        round_type = current_interview_session.get('round_type', 'technical')
        position = current_interview_session.get('position', 'unknown')

        logger.info(f"[ASR->LLM] ★★★ 开始调用 LLM - 问题：'{current_question[:30]}...'")
        feedback = llm_manager.process_answer_with_round(
            user_answer=text,
            current_question=current_question,
            position=position,
            round_type=round_type,
            chat_history=chat_history
        )
        logger.info(f"[ASR->LLM] LLM 返回结果：'{feedback[:50] if feedback else 'None'}...'")

        if not feedback:
            socketio.emit('error', {
                'error': 'Failed to process answer',
                'code': 'LLM_ERROR'
            }, to=client_id)
            return

        # 只是使用列表记录到内存中，速度快，不涉及复杂查询，暂不存数据库
        data_manager.add_frame_data({
            'type': 'interview_dialogue',
            'question': current_question,
            'user_answer': text,
            'llm_feedback': feedback,
            'timestamp': time.time()
        })
        
        # 正式环境建议改为异步入库，避免数据库操作影响响应速度
        db_manager.save_interview_dialogue({
            'interview_id': f"interview_{int(time.time())}",
            'round_type': round_type,
            'question': current_question,
            'answer': text,
            'llm_feedback': feedback
        })

        current_interview_session['chat_history'].append({
            'role': 'candidate',
            'content': text
        })
        current_interview_session['chat_history'].append({
            'role': 'interviewer',
            'content': feedback
        })

        socketio.emit('llm_answer', {
            'success': True,
            'feedback': feedback,
            'round': round_type,
            'timestamp': time.time()
        }, to=client_id)

        _emit_tts_audio(client_id, feedback)

        with asr_llm_state_lock:
            asr_llm_last_feedback_ts[client_id] = time.time()

        logger.info(f"[ASR->LLM] ✓ 已生成追问 - 轮次：{round_type}")

    except Exception as e:
        logger.error(f"[ASR->LLM] 处理失败：{e}", exc_info=True)
        socketio.emit('error', {
            'error': 'Internal server error',
            'code': 'SERVER_ERROR',
            'details': str(e)
        }, to=client_id)
    finally:
        with asr_llm_state_lock:
            asr_llm_processing_clients.discard(client_id)

# 初始化简历解析器
try:
    from utils.resume_parser import resume_parser
    if getattr(resume_parser, 'enabled', False):
        logger.info("简历解析器初始化成功")
    else:
        logger.warning("简历解析器已加载，但当前未启用")
except Exception as e:
    resume_parser = None
    logger.error(f"简历解析器初始化失败：{e}")

# 初始化 ASR 管理器
if asr_manager is None:
    logger.error(f"ASR 初始化失败，相关功能不可用：{asr_import_error}")
elif getattr(asr_manager, 'enabled', False):
    logger.info("ASR 模块初始化成功")
else:
    logger.warning("ASR 模块已加载，但当前未启用")

# 初始化 TTS 管理器
if tts_manager is None:
    logger.error(f"TTS 初始化失败，相关功能不可用：{tts_import_error}")
elif getattr(tts_manager, 'enabled', False):
    logger.info("TTS 模块初始化成功")
else:
    logger.warning("TTS 模块已加载，但当前未启用")

logger.info("工具模块初始化完成")

# 启动性能监控
if config.get('performance.enable_monitoring', True):
    performance_monitor.start_monitoring()
    logger.info("性能监控已启动")

# 全局状态
interview_active = False
current_interview_session = {
    'round_type': 'technical', # 面试轮次
    'position': 'java_backend', # 岗位
    'difficulty': 'medium', # 难度
    'resume_data': None, # 简历数据
    'chat_history': [], # 对话历史
    'started_at': None # 开始时间
}

# 初始化速率限制器
answer_rate_limiter = RateLimiter(max_calls=5, time_window=1.0)    # 回答提交：5 次/秒
interview_rate_limiter = RateLimiter(max_calls=2, time_window=10.0) # 面试操作：2 次/10 秒

logger.info("速率限制器初始化完成")


# ==================== 基础路由 ====================

@app.route('/')
def index():
    """主页路由"""
    logger.debug("收到主页请求")
    return jsonify({
        'message': 'AI Interview Platform API',
        'version': config.get('system.version', '1.0.0'),
        'status': 'running',
        'environment': config.get('system.environment', 'development')
    })


@app.route('/health')
def health():
    """健康检查"""
    logger.debug("健康检查请求")
    perf_stats = performance_monitor.get_system_stats()
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'performance': {
            'fps': perf_stats['fps'],
            'cpu_percent': perf_stats['cpu_percent'],
            'memory_percent': perf_stats['memory_percent']
        }
    })


@app.route('/api/performance')
def get_performance():
    """获取性能统计"""
    logger.debug("性能统计请求")
    return jsonify({
        'success': True,
        'data': performance_monitor.get_performance_summary()
    })


@app.route('/api/performance/bottlenecks')
def get_bottlenecks():
    """获取性能瓶颈"""
    threshold_ms = request.args.get('threshold', 100.0, type=float)
    bottlenecks = performance_monitor.get_bottlenecks(threshold_ms)
    return jsonify({
        'success': True,
        'data': bottlenecks
    })


# ==================== Socket.IO 事件 ====================

@socketio.on('connect')
def handle_connect():
    """客户端连接事件"""
    client_id = request.sid
    logger.info(f"客户端已连接 - ID: {client_id}")
    emit('connection_response', {
        'message': 'Connected to server',
        'status': 'success',
        'client_id': client_id
    })


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开事件"""
    client_id = request.sid
    with asr_llm_state_lock:
        asr_llm_processing_clients.discard(client_id)
        asr_llm_last_feedback_ts.pop(client_id, None)
    with asr_text_buffer_lock:
        timer = asr_text_flush_timers.pop(client_id, None)
        if timer:
            timer.cancel()
        asr_text_buffers.pop(client_id, None)
    logger.info(f"客户端已断开 - ID: {client_id}")


@socketio.on('start_interview')
@rate_limit(interview_rate_limiter)
def handle_start_interview(data=None):
    """启动面试会话

    参数:
        data: {
            'position': 'java_backend' | 'frontend',
            'difficulty': 'easy' | 'medium' | 'hard',
            'round': 'technical' | 'project' | 'system_design' | 'hr',
            'user_id': str
        }
    """
    global interview_active, current_interview_session
    client_id = request.sid

    try:
        round_type = data.get('round', 'technical') if data else 'technical'
        position = data.get('position', 'java_backend') if data else 'java_backend'
        difficulty = data.get('difficulty', 'medium') if data else 'medium'
        user_id = data.get('user_id', 'default') if data else 'default'

        logger.info(f"启动面试会话 - 岗位：{position}, 轮次：{round_type}, 难度：{difficulty}")

        # 激活面试状态
        interview_active = True

        # 重置状态
        data_manager.reset()
        current_interview_session = {
            'round_type': round_type,
            'position': position,
            'difficulty': difficulty,
            'resume_data': None,
            'chat_history': [],
            'started_at': time.time()
        }

        # 加载简历数据并设置 LLM 上下文
        if llm_manager:
            resume_data = llm_manager.load_resume_data(user_id)
            if resume_data:
                current_interview_session['resume_data'] = resume_data
                llm_manager.set_interview_round(round_type, resume_data)
                logger.info(f"已加载候选人简历数据")
            else:
                llm_manager.set_interview_round(round_type)
                logger.info("未找到候选人简历，使用通用面试模式")

        # 开始记录
        data_manager.start_interview()

        # 生成初始问题
        initial_question = ""
        if llm_manager:
            initial_question = llm_manager.generate_round_question(
                round_type=round_type,
                position=position,
                difficulty=difficulty
            )
            # 更新 chat_history
            current_interview_session['chat_history'].append({
                'role': 'interviewer',
                'content': initial_question
            })

        emit('interview_started', {
            'message': 'Interview session started',
            'timestamp': time.time(),
            'success': True,
            'round': round_type,
            'position': position,
            'difficulty': difficulty,
            'question': initial_question
        })

        # 首问同样发送语音，避免只有文字无声音
        _emit_tts_audio(client_id, initial_question)

        logger.info(f"✓ 面试会话已启动 - 轮次：{round_type}")

    except Exception as e:
        logger.error(f"启动面试错误：{e}", exc_info=True)
        emit('error', {
            'error': 'Failed to start interview',
            'code': 'START_ERROR',
            'details': str(e)
        })


@socketio.on('submit_answer')
@rate_limit(answer_rate_limiter)
def handle_submit_answer(data):
    """处理学生的答案提交

    参数:
        data: {
            'question_id': 'xxx',
            'question': '问题内容',
            'answer': '学生回答',
            'input_type': 'text' | 'voice'
        }
    """
    client_id = request.sid

    try:
        logger.debug(f"收到答案提交 - 客户端：{client_id}")

        # 输入验证
        if not data or not isinstance(data, dict):
            logger.warning("答案提交 - 无效的数据格式")
            emit('error', {
                'error': 'Invalid data format',
                'code': 'INVALID_DATA'
            })
            return

        if 'answer' not in data:
            emit('error', {
                'error': 'Missing answer field',
                'code': 'MISSING_FIELD'
            })
            return

        # 检查面试状态
        if not interview_active:
            emit('error', {
                'error': 'Interview session not active',
                'code': 'SESSION_INACTIVE'
            })
            return

        # 保存回答
        data_manager.add_frame_data({
            'type': 'answer',
            'question_id': data.get('question_id'),
            'answer': data.get('answer'),
            'input_type': data.get('input_type', 'text'),
            'timestamp': time.time()
        })

        # 发送确认
        emit('answer_received', {
            'success': True,
            'message': 'Answer received and recorded',
            'timestamp': time.time()
        })

        logger.debug(f"✓ 答案已保存")

    except Exception as e:
        logger.error(f"处理答案错误：{e}", exc_info=True)
        emit('error', {
            'error': 'Internal server error',
            'code': 'SERVER_ERROR'
        })


@socketio.on('end_interview')
@rate_limit(interview_rate_limiter)
def handle_end_interview(data=None):
    """结束面试并生成报告"""
    global interview_active
    client_id = request.sid

    try:
        logger.info("结束面试会话")
        interview_active = False
        asr_client_callbacks.pop(client_id, None)
        asr_last_restart_attempt.pop(client_id, None)
        with asr_llm_state_lock:
            asr_llm_processing_clients.discard(client_id)
            asr_llm_last_feedback_ts.pop(client_id, None)
        with asr_text_buffer_lock:
            timer = asr_text_flush_timers.pop(client_id, None)
            if timer:
                timer.cancel()
            asr_text_buffers.pop(client_id, None)
        if asr_manager and asr_manager.is_available():
            asr_manager.stop()

        # 结束记录
        data_manager.end_interview()

        # 获取面试数据
        report_data = data_manager.export_for_report()

        # 生成报告 (暂时)
        report_path = report_generator.generate_report(report_data)

        # 保存到数据库
        try:
            interview_record = {
                'interview_id': report_data.get('interview_id', f"interview_{int(time.time())}"),
                'start_time': report_data.get('start_time'),
                'end_time': report_data.get('end_time'),
                'duration': report_data.get('duration', 0),
                'report_path': report_path
            }

            db_result = db_manager.save_interview(interview_record)

            if db_result.get('success'):
                logger.info("✓ 面试记录已保存到数据库")
            else:
                logger.error(f"✗ 数据库保存失败：{db_result.get('error')}")

        except Exception as db_error:
            logger.error(f"✗ 数据库操作出错：{db_error}", exc_info=True)

        emit('interview_ended', {
            'message': 'Interview session ended',
            'report_path': report_path,
            'timestamp': time.time(),
            'success': True
        })

        logger.info("✓ 面试会话已结束")

    except Exception as e:
        logger.error(f"结束面试错误：{e}", exc_info=True)
        emit('error', {
            'error': 'Failed to end interview',
            'code': 'END_ERROR'
        })


# ==================== LLM 事件处理 ====================

# ==================== ASR 事件处理 ====================

@socketio.on('start_asr')
def handle_start_asr(data=None):
    """启动 ASR 语音识别"""
    client_id = request.sid

    try:
        if asr_manager is None:
            emit('asr_error', {
                'error': 'ASR is not initialized on server',
                'code': 'ASR_NOT_READY',
                'details': asr_import_error
            })
            return

        def on_recognition_result(text: str):
            """识别结果回调"""
            logger.info(f"[ASR 回调] on_recognition_result 被调用！text='{text}'")
            logger.info(f"[ASR 回调] 准备发送 asr_result 到前端")
            # 发送识别结果到客户端
            socketio.emit('asr_result', {
                'success': True,
                'text': text,
                'timestamp': time.time()
            }, to=client_id)
            logger.info(f"[ASR 回调] 已发送 asr_result，准备进入聚合队列")
            _enqueue_asr_text_for_llm(client_id, text)
            logger.info(f"[ASR 回调] 已加入聚合队列")

        # 缓存回调，供超时后自动恢复使用
        asr_client_callbacks[client_id] = on_recognition_result

        # 避免重复 start 导致状态不一致，先停再起
        if asr_manager.is_available():
            asr_manager.stop()

        # 启动 ASR
        success = asr_manager.start(on_recognition_result)

        if success:
            emit('asr_started', {
                'success': True,
                'message': 'ASR 已启动',
                'timestamp': time.time()
            })
            logger.info(f"✓ ASR 已启动 - 客户端：{client_id}")
        else:
            emit('asr_error', {
                'error': 'Failed to start ASR',
                'code': 'ASR_START_ERROR'
            })

    except Exception as e:
        logger.error(f"启动 ASR 错误：{e}", exc_info=True)
        emit('asr_error', {
            'error': 'Internal server error',
            'code': 'SERVER_ERROR',
            'details': str(e)
        })


@socketio.on('audio_stream')
def handle_audio_stream(data):
    """接收音频流并送入 ASR 处理

    参数:
        data: {
            'audio': base64 编码的 PCM 音频数据 (16kHz, 16bit, 单声道)
        }
    """
    client_id = request.sid

    try:
        if asr_manager is None:
            logger.warning(f"[ASR] ASR 未初始化")
            return

        if not asr_manager.is_available():
            # ASR 常见在云端超时后掉线，这里在新音频到达时自动尝试恢复
            callback = asr_client_callbacks.get(client_id)
            now = time.time()
            last_attempt = asr_last_restart_attempt.get(client_id, 0)
            can_retry = (now - last_attempt) >= ASR_RESTART_COOLDOWN_SECONDS

            if callback and can_retry:
                asr_last_restart_attempt[client_id] = now
                logger.warning(f"[ASR] 检测到服务不可用，尝试自动恢复 - 客户端：{client_id}")
                restart_ok = asr_manager.start(callback)
                if restart_ok:
                    socketio.emit('asr_started', {
                        'success': True,
                        'message': 'ASR 已自动恢复',
                        'timestamp': time.time()
                    }, to=client_id)
                else:
                    socketio.emit('asr_error', {
                        'error': 'ASR auto-restart failed',
                        'code': 'ASR_RECOVERY_FAILED',
                        'timestamp': time.time()
                    }, to=client_id)
            return

        # 如果 Socket SID 已变化但 ASR 仍在跑旧回调，重绑到当前客户端
        if client_id not in asr_client_callbacks:
            logger.warning(f"[ASR] 检测到客户端 SID 变化，重绑回调 - 客户端：{client_id}")

            def on_recognition_result(text: str):
                logger.info(f"[ASR] 识别结果：{text}")
                socketio.emit('asr_result', {
                    'success': True,
                    'text': text,
                    'timestamp': time.time()
                }, to=client_id)
                _enqueue_asr_text_for_llm(client_id, text)

            asr_client_callbacks[client_id] = on_recognition_result
            asr_manager.stop()
            rebind_ok = asr_manager.start(on_recognition_result)
            if rebind_ok:
                socketio.emit('asr_started', {
                    'success': True,
                    'message': 'ASR 回调已重绑定',
                    'timestamp': time.time()
                }, to=client_id)
            else:
                socketio.emit('asr_error', {
                    'error': 'ASR callback rebind failed',
                    'code': 'ASR_REBIND_FAILED',
                    'timestamp': time.time()
                }, to=client_id)
                return

        if not data or 'audio' not in data:
            logger.warning(f"[ASR] 数据格式错误：{data}")
            return

        import base64
        audio_base64 = data.get('audio', '')

        if audio_base64:
            # 解码音频数据
            audio_data = base64.b64decode(audio_base64)
            # 送入 ASR 处理
            asr_manager.send_audio(audio_data)
            logger.debug(f"[ASR] 已发送音频到队列：{len(audio_data)} 字节")

    except Exception as e:
        logger.error(f"处理音频流错误：{e}", exc_info=True)


@socketio.on('stop_asr')
def handle_stop_asr(data=None):
    """停止 ASR 语音识别"""
    client_id = request.sid

    try:
        asr_client_callbacks.pop(client_id, None)
        asr_last_restart_attempt.pop(client_id, None)
        if asr_manager:
            asr_manager.stop()
            logger.info(f"✓ ASR 已停止 - 客户端：{client_id}")
    except Exception as e:
        logger.error(f"停止 ASR 错误：{e}", exc_info=True)


@socketio.on('llm_process_answer')
@rate_limit(answer_rate_limiter)
def handle_llm_process_answer(data):
    """处理用户回答，生成追问

    参数:
        data: {
            'user_answer': '用户的回答文本',
            'current_question': '当前问题',
            'position': '职位名称',
            'chat_history': []  # 可选，对话历史
        }
    """
    client_id = request.sid

    try:
        if llm_manager is None:
            emit('error', {
                'error': 'LLM is not initialized on server',
                'code': 'LLM_NOT_READY',
                'details': llm_import_error
            })
            return

        if not data or 'user_answer' not in data:
            logger.warning("llm_process_answer - 缺少必要参数")
            emit('error', {
                'error': 'Missing required fields: user_answer',
                'code': 'MISSING_FIELD'
            })
            return

        logger.info(f"处理用户回答 - 客户端：{client_id}")

        user_answer = data.get('user_answer', '').strip()
        current_question = data.get('current_question', '')
        position = data.get('position', 'unknown')
        chat_history = data.get('chat_history', [])

        # 使用当前面试轮次
        round_type = current_interview_session.get('round_type', 'technical')

        # 发送正在处理的消息
        emit('llm_processing', {
            'message': '正在分析你的回答...',
            'status': 'processing'
        })

        # 调用 LLM 处理回答（使用轮次专用方法）
        feedback = llm_manager.process_answer_with_round(
            user_answer=user_answer,
            current_question=current_question,
            position=position,
            round_type=round_type,
            chat_history=chat_history
        )

        if feedback:
            # 保存对话历史
            data_manager.add_frame_data({
                'type': 'interview_dialogue',
                'question': current_question,
                'user_answer': user_answer,
                'llm_feedback': feedback,
                'timestamp': time.time()
            })

            # 保存对话到数据库
            db_manager.save_interview_dialogue({
                'interview_id': f"interview_{int(time.time())}",
                'round_type': round_type,
                'question': current_question,
                'answer': user_answer,
                'llm_feedback': feedback
            })

            # 更新 chat_history
            current_interview_session['chat_history'].append({
                'role': 'candidate',
                'content': user_answer
            })
            current_interview_session['chat_history'].append({
                'role': 'interviewer',
                'content': feedback
            })

            # 返回追问和反馈
            emit('llm_answer', {
                'success': True,
                'feedback': feedback,
                'round': round_type,
                'timestamp': time.time()
            })

            _emit_tts_audio(client_id, feedback)

            logger.info(f"✓ 已生成追问 - 轮次：{round_type}")
        else:
            emit('error', {
                'error': 'Failed to process answer',
                'code': 'LLM_ERROR'
            })

    except Exception as e:
        logger.error(f"处理回答错误：{e}", exc_info=True)
        emit('error', {
            'error': 'Internal server error',
            'code': 'SERVER_ERROR',
            'details': str(e)
        })


@socketio.on('llm_generate_question')
@rate_limit(interview_rate_limiter)
def handle_llm_generate_question(data):
    """生成面试问题

    参数:
        data: {
            'position': '职位名称',
            'difficulty': 'easy' | 'medium' | 'hard',
            'context': '上下文信息（可选）'
        }
    """
    client_id = request.sid

    try:
        if llm_manager is None:
            emit('error', {
                'error': 'LLM is not initialized on server',
                'code': 'LLM_NOT_READY',
                'details': llm_import_error
            })
            return

        if not data or 'position' not in data:
            logger.warning("llm_generate_question - 缺少职位信息")
            emit('error', {
                'error': 'Missing required field: position',
                'code': 'MISSING_FIELD'
            })
            return

        position = data.get('position', '')
        difficulty = data.get('difficulty', 'medium')
        context = data.get('context', '')

        logger.info(f"生成面试问题 - 职位：{position}, 难度：{difficulty}")

        # 发送正在生成的消息
        emit('llm_generating', {
            'message': '正在生成问题...',
            'status': 'generating'
        })

        # 调用 LLM 生成问题
        question = llm_manager.generate_interview_question(
            position=position,
            difficulty=difficulty,
            context=context
        )

        if question:
            # 保存问题
            data_manager.add_frame_data({
                'type': 'interview_question',
                'question': question,
                'position': position,
                'difficulty': difficulty,
                'timestamp': time.time()
            })

            # 返回生成的问题
            emit('llm_question', {
                'success': True,
                'question': question,
                'position': position,
                'difficulty': difficulty,
                'timestamp': time.time()
            })

            logger.info(f"✓ 已生成问题")
        else:
            emit('error', {
                'error': 'Failed to generate question',
                'code': 'LLM_ERROR'
            })

    except Exception as e:
        logger.error(f"生成问题错误：{e}", exc_info=True)
        emit('error', {
            'error': 'Internal server error',
            'code': 'SERVER_ERROR',
            'details': str(e)
        })


@socketio.on('llm_evaluate_answer')
@rate_limit(answer_rate_limiter)
def handle_llm_evaluate_answer(data):
    """评估用户回答质量

    参数:
        data: {
            'user_answer': '用户回答',
            'question': '问题内容',
            'position': '职位名称'
        }
    """
    client_id = request.sid

    try:
        if llm_manager is None:
            emit('error', {
                'error': 'LLM is not initialized on server',
                'code': 'LLM_NOT_READY',
                'details': llm_import_error
            })
            return

        if not data or 'user_answer' not in data:
            emit('error', {
                'error': 'Missing required fields',
                'code': 'MISSING_FIELD'
            })
            return

        user_answer = data.get('user_answer', '').strip()
        question = data.get('question', '')
        position = data.get('position', 'unknown')

        logger.info(f"评估用户回答 - 职位：{position}")

        # 发送正在评估的消息
        emit('llm_evaluating', {
            'message': '正在评估回答质量...',
            'status': 'evaluating'
        })

        # 调用 LLM 评估回答
        evaluation = llm_manager.evaluate_answer(
            user_answer=user_answer,
            question=question,
            position=position
        )

        # 保存评估结果
        data_manager.add_frame_data({
            'type': 'answer_evaluation',
            'question': question,
            'answer': user_answer,
            'evaluation': evaluation,
            'timestamp': time.time()
        })

        # 返回评估结果
        emit('llm_evaluation', {
            'success': True,
            'evaluation': evaluation,
            'timestamp': time.time()
        })

        logger.info(f"✓ 已完成评估")

    except Exception as e:
        logger.error(f"评估回答错误：{e}", exc_info=True)
        emit('error', {
            'error': 'Internal server error',
            'code': 'SERVER_ERROR',
            'details': str(e)
        })


@socketio.on('get_performance')
def handle_get_performance(data=None):
    """获取实时性能统计"""
    try:
        perf_summary = performance_monitor.get_performance_summary()
        emit('performance_stats', perf_summary)
    except Exception as e:
        logger.error(f"获取性能统计错误：{e}", exc_info=True)
        emit('error', {'error': str(e)})


# ==================== 报告相关接口 ====================

def _parse_db_datetime(value):
    """解析 SQLite 时间字符串。"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # sqlite 默认格式：YYYY-MM-DD HH:MM:SS
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def _clamp_score(value):
    return max(0.0, min(100.0, float(value)))


def _calc_dimension_scores(dialogues):
    """基于问答过程做启发式多维评分。"""
    if not dialogues:
        return {
            'technical_correctness': 60.0,
            'knowledge_depth': 60.0,
            'logical_rigor': 60.0,
            'expression_clarity': 60.0,
            'job_match': 60.0,
            'adaptability': 60.0
        }

    answers = [str(d.get('answer') or '').strip() for d in dialogues]
    feedbacks = [str(d.get('llm_feedback') or '').strip() for d in dialogues]
    answer_lengths = [len(a) for a in answers if a]
    avg_answer_len = (sum(answer_lengths) / len(answer_lengths)) if answer_lengths else 0

    bad_markers = ['不完整', '偏离', '混淆', '误输入', '再来一次', '不清楚', '截断', '不准确']
    good_markers = ['很好', '不错', '准确', '清晰', '正确', '完整', '深入', '有条理']

    bad_hits = sum(sum(1 for m in bad_markers if m in fb) for fb in feedbacks)
    good_hits = sum(sum(1 for m in good_markers if m in fb) for fb in feedbacks)

    logic_words = ['首先', '其次', '然后', '最后', '因为', '所以', '例如', '总结']
    logic_hits = sum(sum(1 for w in logic_words if w in a) for a in answers)

    job_keywords = ['java', 'spring', 'redis', 'mysql', '并发', '线程', 'jvm', '前端', 'react', 'vue']
    match_hits = sum(sum(1 for k in job_keywords if k.lower() in a.lower()) for a in answers)

    first_half = feedbacks[:max(1, len(feedbacks)//2)]
    second_half = feedbacks[max(1, len(feedbacks)//2):]
    first_bad = sum(sum(1 for m in bad_markers if m in fb) for fb in first_half)
    second_bad = sum(sum(1 for m in bad_markers if m in fb) for fb in second_half)

    technical_correctness = _clamp_score(74 + good_hits * 3.5 - bad_hits * 4.5)
    knowledge_depth = _clamp_score(58 + min(28, avg_answer_len / 9) + good_hits * 1.2 - bad_hits * 1.4)
    logical_rigor = _clamp_score(60 + logic_hits * 2.8 - bad_hits * 1.2)
    expression_clarity = _clamp_score(62 + min(18, avg_answer_len / 12) + logic_hits * 1.2 - bad_hits * 1.3)
    job_match = _clamp_score(56 + min(30, match_hits * 2.6) + good_hits * 0.8)
    adaptability = _clamp_score(62 + (6 if second_bad <= first_bad else -6) - max(0, bad_hits - good_hits) * 0.6)

    return {
        'technical_correctness': round(technical_correctness, 1),
        'knowledge_depth': round(knowledge_depth, 1),
        'logical_rigor': round(logical_rigor, 1),
        'expression_clarity': round(expression_clarity, 1),
        'job_match': round(job_match, 1),
        'adaptability': round(adaptability, 1)
    }


def _build_growth_report(dialogues):
    scores = _calc_dimension_scores(dialogues)
    overall = round(
        scores['technical_correctness'] * 0.30
        + scores['knowledge_depth'] * 0.15
        + scores['logical_rigor'] * 0.15
        + scores['expression_clarity'] * 0.15
        + scores['job_match'] * 0.15
        + scores['adaptability'] * 0.10,
        1
    )

    answers = [str(d.get('answer') or '').strip() for d in dialogues]
    feedbacks = [str(d.get('llm_feedback') or '').strip() for d in dialogues]
    rounds = [str(d.get('round_type') or 'unknown') for d in dialogues]
    round_counter = Counter(rounds)

    strengths = []
    weaknesses = []

    if scores['technical_correctness'] >= 75:
        strengths.append('技术回答整体正确，关键概念覆盖较完整。')
    if scores['logical_rigor'] >= 75:
        strengths.append('回答结构较清晰，具备较好的论证顺序。')
    if scores['job_match'] >= 72:
        strengths.append('回答与目标岗位技术栈关联度较高。')
    if scores['adaptability'] >= 70:
        strengths.append('面对追问时能够持续作答，临场应变较稳定。')

    if scores['knowledge_depth'] < 65:
        weaknesses.append('知识点解释偏表层，深挖时细节支撑不足。')
    if scores['expression_clarity'] < 65:
        weaknesses.append('表达存在停顿与重复，建议优化回答结构。')
    if scores['job_match'] < 65:
        weaknesses.append('岗位关键词覆盖不足，回答与岗位场景结合不够。')
    if scores['adaptability'] < 65:
        weaknesses.append('连续追问下稳定性一般，建议进行高压追问训练。')

    if not strengths:
        strengths.append('完成了多轮问答，具备持续输出和沟通基础。')
    if not weaknesses:
        weaknesses.append('整体表现较均衡，下一步可重点冲刺高频深挖题。')

    improvement_plan = [
        {
            'focus': '技术正确性与知识深度',
            'action': '围绕本次追问点做二次复盘，每题补充“原理+场景+权衡”。',
            'target': '下一次技术正确性提升至 80+'
        },
        {
            'focus': '逻辑表达',
            'action': '采用“结论先行 + 3点展开 + 小结”的口头模板进行训练。',
            'target': '将表达清晰度提升到 75+'
        },
        {
            'focus': '岗位匹配',
            'action': '回答中主动加入岗位高频关键词（如并发、缓存、事务、性能优化等）。',
            'target': '岗位匹配度提升到 75+'
        }
    ]

    followup_chain = []
    for item in dialogues[-6:]:
        followup_chain.append({
            'round': item.get('round_type', 'unknown'),
            'question': item.get('question', ''),
            'answer': item.get('answer', ''),
            'feedback': item.get('llm_feedback', '')
        })

    started_at = _parse_db_datetime(dialogues[0].get('created_at')) if dialogues else None
    ended_at = _parse_db_datetime(dialogues[-1].get('created_at')) if dialogues else None
    duration_seconds = int((ended_at - started_at).total_seconds()) if started_at and ended_at else 0

    return {
        'summary': {
            'overall_score': overall,
            'interview_count': len(dialogues),
            'started_at': dialogues[0].get('created_at') if dialogues else '',
            'ended_at': dialogues[-1].get('created_at') if dialogues else '',
            'duration_seconds': max(0, duration_seconds),
            'dominant_round': round_counter.most_common(1)[0][0] if round_counter else 'technical'
        },
        'score_breakdown': scores,
        'strengths': strengths,
        'weaknesses': weaknesses,
        'improvement_plan': improvement_plan,
        'followup_chain': followup_chain
    }


def _split_recent_sessions(rows):
    """按时间间隔切分近几次面试会话（用于成长趋势）。"""
    sessions = []
    current = []
    prev_time = None

    for row in rows:
        row_time = _parse_db_datetime(row.get('created_at'))
        if not row_time:
            continue

        if prev_time is None:
            current = [row]
        else:
            gap = (prev_time - row_time).total_seconds()
            if gap > 180:
                sessions.append(current)
                current = [row]
            else:
                current.append(row)

        prev_time = row_time

        if len(sessions) >= 5:
            break

    if current and len(sessions) < 5:
        sessions.append(current)

    return sessions


@app.route('/api/growth-report/latest')
def get_latest_growth_report():
    """基于面试过程对话生成成长报告。"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, interview_id, round_type, question, answer, llm_feedback, created_at
                FROM interview_dialogues
                ORDER BY datetime(created_at) DESC
                LIMIT 120
            ''')
            rows = [dict(row) for row in cursor.fetchall()]

        if not rows:
            return jsonify({
                'success': True,
                'report': None,
                'trend': [],
                'message': '暂无面试过程数据'
            })

        sessions_desc = _split_recent_sessions(rows)
        if not sessions_desc:
            return jsonify({
                'success': True,
                'report': None,
                'trend': [],
                'message': '暂无可分析会话'
            })

        latest_session_desc = sessions_desc[0]
        latest_session = list(reversed(latest_session_desc))
        report = _build_growth_report(latest_session)

        trend = []
        sessions_for_trend = list(reversed(sessions_desc))
        for idx, session_desc in enumerate(sessions_for_trend, start=1):
            session = list(reversed(session_desc))
            session_report = _build_growth_report(session)
            trend.append({
                'label': f'第{idx}次',
                'overall_score': session_report['summary']['overall_score']
            })

        return jsonify({
            'success': True,
            'report': report,
            'trend': trend
        })

    except Exception as e:
        logger.error(f"生成成长报告失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/reports')
def get_reports():
    """获取所有报告列表"""
    try:
        reports_dir = Path('reports')
        if not reports_dir.exists():
            return jsonify({'reports': []})

        reports = []
        for json_file in reports_dir.glob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)
                    reports.append(report)
            except Exception as e:
                logger.warning(f"无法读取报告 {json_file.name}: {e}")

        # 按日期降序排列
        reports.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return jsonify({
            'success': True,
            'count': len(reports),
            'reports': reports
        })

    except Exception as e:
        logger.error(f"获取报告列表错误：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/interviews')
def get_interviews_from_db():
    """从数据库获取面试记录列表"""
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        interviews = db_manager.get_interviews(limit=limit, offset=offset)

        return jsonify({
            'success': True,
            'interviews': interviews,
            'count': len(interviews)
        })

    except Exception as e:
        logger.error(f"获取面试记录错误：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'interviews': []
        }), 500


@app.route('/api/interviews/<interview_id>')
def get_interview_detail(interview_id):
    """获取面试详细信息"""
    try:
        interview = db_manager.get_interview_by_id(interview_id)

        if not interview:
            return jsonify({
                'success': False,
                'error': 'Interview not found'
            }), 404

        return jsonify({
            'success': True,
            'interview': interview
        })

    except Exception as e:
        logger.error(f"获取面试详情错误：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 简历相关接口 ====================

@app.route('/api/resume/upload', methods=['POST'])
def upload_resume():
    """上传并解析简历"""
    try:
        if resume_parser is None:
            return jsonify({
                'success': False,
                'error': '简历解析器未初始化'
            }), 500

        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': '请选择要上传的文件'
            }), 400

        file = request.files.get('file')
        user_id = request.form.get('user_id', 'default')

        if not file or file.filename == '':
            return jsonify({
                'success': False,
                'error': '未选择文件'
            }), 400

        # 检查文件类型
        allowed_extensions = ['.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg']
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return jsonify({
                'success': False,
                'error': f'不支持的文件格式，请上传 {", ".join(allowed_extensions)} 格式的文件'
            }), 400

        # 创建上传目录
        upload_dir = Path('uploads/resumes')
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        import uuid
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = upload_dir / unique_filename

        # 保存文件
        file.save(str(file_path))

        # 计算文件哈希（用于去重）
        import hashlib
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()

        # 检查是否已存在相同简历（仅标记，不拦截：每次上传都重新识别）
        duplicate_resume_id = None
        existing = db_manager.get_resumes(limit=1000)
        for resume in existing:
            if resume.get('file_hash') == file_hash:
                duplicate_resume_id = resume.get('id')
                logger.info(f"发现重复简历（将继续重新解析）：{file.filename}, 重复ID: {duplicate_resume_id}")
                break

        # 保存到数据库（状态为解析中）
        resume_data = {
            'user_id': user_id,
            'file_name': file.filename,
            'file_path': str(file_path),
            'file_size': os.path.getsize(file_path),
            'file_hash': file_hash,
            'parsed_data': {},
            'status': 'parsing'
        }

        save_result = db_manager.save_resume(resume_data)
        if not save_result.get('success'):
            return jsonify({
                'success': False,
                'error': save_result.get('error')
            }), 500

        resume_id = save_result['resume_id']

        # 标记为解析中（便于前端状态展示）
        db_manager.update_resume_status(resume_id, 'parsing')

        # 解析简历
        logger.info(f"开始解析简历：{file.filename}")
        parsed_result = resume_parser.parse_file(str(file_path))

        if parsed_result.get('error'):
            # 解析失败
            db_manager.update_resume_status(resume_id, 'error', parsed_result.get('error'))
            return jsonify({
                'success': False,
                'error': parsed_result.get('error')
            }), 500

        # 更新简历数据
        resume_data['parsed_data'] = parsed_result
        db_manager.update_resume_status(resume_id, 'parsed')

        # 重新保存解析后的数据
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE resumes
                SET parsed_data = ?,
                    projects = ?,
                    experiences = ?,
                    education = ?,
                    skills = ?,
                    status = 'parsed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                json.dumps(parsed_result, ensure_ascii=False),
                json.dumps(parsed_result.get('projects', []), ensure_ascii=False),
                json.dumps(parsed_result.get('experiences', []), ensure_ascii=False),
                json.dumps(parsed_result.get('education', []), ensure_ascii=False),
                json.dumps(parsed_result.get('skills', []), ensure_ascii=False),
                resume_id
            ))
            conn.commit()

        logger.info(f"✓ 简历解析完成：{file.filename}")

        return jsonify({
            'success': True,
            'message': '简历上传并解析成功',
            'resume_id': resume_id,
            'data': parsed_result,
            'duplicate': duplicate_resume_id is not None,
            'duplicate_of': duplicate_resume_id
        })

    except Exception as e:
        logger.error(f"上传简历失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/resume', methods=['GET'])
def get_resume():
    """获取简历列表或详情"""
    try:
        resume_id = request.args.get('id', type=int)
        user_id = request.args.get('user_id', 'default')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        if resume_id:
            # 获取指定简历详情
            resume = db_manager.get_resume(resume_id)
            if resume:
                return jsonify({
                    'success': True,
                    'resume': resume
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '简历不存在'
                }), 404
        else:
            # 获取简历列表
            resumes = db_manager.get_resumes(user_id=user_id, limit=limit, offset=offset)
            return jsonify({
                'success': True,
                'count': len(resumes),
                'resumes': resumes
            })

    except Exception as e:
        logger.error(f"获取简历失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/resume/latest', methods=['GET'])
def get_latest_resume():
    """获取最新的简历"""
    try:
        user_id = request.args.get('user_id', 'default')
        resume = db_manager.get_latest_resume(user_id=user_id)

        if resume:
            return jsonify({
                'success': True,
                'resume': resume
            })
        else:
            return jsonify({
                'success': True,
                'resume': None,
                'message': '暂无简历'
            })

    except Exception as e:
        logger.error(f"获取最新简历失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/resume/<int:resume_id>', methods=['DELETE'])
def delete_resume(resume_id):
    """删除简历"""
    try:
        result = db_manager.delete_resume(resume_id)
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"删除简历失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/resume/parse', methods=['POST'])
def reparse_resume():
    """重新解析简历"""
    try:
        data = request.get_json()
        resume_id = data.get('resume_id')

        if not resume_id:
            return jsonify({
                'success': False,
                'error': '缺少 resume_id 参数'
            }), 400

        if resume_parser is None:
            return jsonify({
                'success': False,
                'error': '简历解析器未初始化'
            }), 500

        # 获取简历信息
        resume = db_manager.get_resume(resume_id)
        if not resume:
            return jsonify({
                'success': False,
                'error': '简历不存在'
            }), 404

        file_path = resume.get('file_path')
        if not isinstance(file_path, str) or not file_path.strip():
            return jsonify({
                'success': False,
                'error': '简历文件路径无效'
            }), 400

        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': '简历文件不存在'
            }), 404

        # 重新解析
        logger.info(f"重新解析简历：{resume.get('file_name')}")
        parsed_result = resume_parser.parse_file(file_path)

        if parsed_result.get('error'):
            db_manager.update_resume_status(resume_id, 'error', parsed_result.get('error'))
            return jsonify({
                'success': False,
                'error': parsed_result.get('error')
            }), 500

        # 更新解析结果
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE resumes
                SET parsed_data = ?,
                    projects = ?,
                    experiences = ?,
                    education = ?,
                    skills = ?,
                    status = 'parsed',
                    error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                json.dumps(parsed_result, ensure_ascii=False),
                json.dumps(parsed_result.get('projects', []), ensure_ascii=False),
                json.dumps(parsed_result.get('experiences', []), ensure_ascii=False),
                json.dumps(parsed_result.get('education', []), ensure_ascii=False),
                json.dumps(parsed_result.get('skills', []), ensure_ascii=False),
                resume_id
            ))
            conn.commit()

        logger.info(f"✓ 简历重新解析完成：{resume.get('file_name')}")

        return jsonify({
            'success': True,
            'message': '简历重新解析成功',
            'data': parsed_result
        })

    except Exception as e:
        logger.error(f"重新解析简历失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 应用启动 ====================

if __name__ == '__main__':
    try:
        logger.info("=" * 60)
        logger.info("启动 AI 模拟面试平台")
        logger.info("=" * 60)

        socketio.run(
            app,
            host=FLASK_HOST,
            port=FLASK_PORT,
            debug=FLASK_DEBUG,
            allow_unsafe_werkzeug=True
        )
    except Exception as e:
        logger.error(f"应用启动失败：{e}", exc_info=True)
        raise
