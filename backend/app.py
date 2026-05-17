"""
Flask 主服务 - Socket.IO 实时通信
AI 模拟面试与能力提升平台【改造进行中】
"""
import os

SOCKETIO_ASYNC_MODE = os.environ.get('SOCKETIO_ASYNC_MODE', 'gevent').strip() or 'gevent'
if SOCKETIO_ASYNC_MODE == 'gevent':
    from gevent import monkey
    monkey.patch_all()

from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_socketio import SocketIO, emit
from flask_cors import CORS # 跨域资源共享中间件
import base64
import hashlib
import time
import json
import threading
import uuid
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
from urllib.parse import urlparse

# 导入自定义模块
from utils import DataManager
from utils.config_loader import config
try:
    from utils.llm_manager import llm_manager
    llm_import_error = None
except Exception as e:
    llm_manager = None
    llm_import_error = str(e)
try:
    from rag.service import rag_service
    rag_import_error = None
except Exception as e:
    rag_service = None
    rag_import_error = str(e)
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
try:
    from utils.evaluation_service import EvaluationService
    evaluation_import_error = None
except Exception as e:
    EvaluationService = None
    evaluation_import_error = str(e)
try:
    from utils.assistant_service import assistant_service
    assistant_import_error = None
except Exception as e:
    assistant_service = None
    assistant_import_error = str(e)
try:
    from utils.knowledge_graph_service import KnowledgeGraphService
    knowledge_graph_import_error = None
except Exception as e:
    KnowledgeGraphService = None
    knowledge_graph_import_error = str(e)
try:
    from utils.resume_optimizer import ResumeOptimizer
    resume_optimizer_import_error = None
except Exception as e:
    ResumeOptimizer = None
    resume_optimizer_import_error = str(e)
from utils.logger import get_logger
from utils.performance_monitor import performance_monitor, measure_time
from utils.answer_session import (
    AnswerSession,
    LONG_PAUSE_SECONDS,
    SHORT_PAUSE_SECONDS,
    build_live_answer_text,
    merge_answer_text,
    stabilize_realtime_asr_text,
)
from utils.session_orchestrator import SessionRegistry, StateOrchestrator
from utils.speech_normalizer import SpeechTextNormalizer
from utils.speech_metrics import compute_final_speech_metrics, aggregate_expression_metrics
from utils.replay_service import ReplayService, ReplayTaskManager
from utils.behavior_analysis_service import BehaviorAnalysisService, BehaviorAnalysisTaskManager
from utils.video_upload_service import VideoUploadService
from utils.report_generator import ReportGenerator
from utils.round_aggregation import build_round_aggregation
from utils.security import (
    RateLimiter,
    rate_limit,
    validate_string,
    ValidationError
)
from database import DatabaseManager
from routes.account import (
    AUTH_DEFAULT_EMAIL,
    AUTH_DEFAULT_NAME,
    AUTH_DEFAULT_PASSWORD,
    create_account_blueprint,
    hash_auth_password,
)
from routes.knowledge_graph import create_knowledge_graph_blueprint
from routes.system import create_system_blueprint
from routes.user import create_user_blueprint

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


INSIGHTS_RECENT_LIMIT = 5
INSIGHTS_RECENT_SCAN_LIMIT = 30
INSIGHTS_REPORT_SCAN_LIMIT = 8
INSIGHTS_LOOKBACK_DAYS = 30
INSIGHTS_WEEKLY_DAYS = 7
INSIGHTS_PER_ROUND_LIMIT = 3
INSIGHTS_CACHE_TTL_SECONDS = 600
INSIGHTS_TRACKED_ROUNDS = ('technical', 'project', 'system_design', 'hr')
INSIGHTS_SUMMARY_CACHE = {}
INSIGHTS_AI_SUMMARY_ENABLED = str(os.environ.get("INSIGHTS_AI_SUMMARY_ENABLED", "true")).strip().lower() in {"1", "true", "yes", "on"}
INSIGHTS_AI_SUMMARY_TIMEOUT_SECONDS = 30
TRAINING_VALIDATION_QUESTION_COUNT = 3
TRAINING_STATUS_LABELS = {
    'planned': '计划中',
    'training': '训练中',
    'validation': '待验收',
    'reflow': '未达标待回流',
    'completed': '已达标',
    'rolled_over': '已回流到下周',
}
ASSISTANT_CITATION_MIN_SCORE = 0.5
ASSISTANT_RETRIEVAL_MIN_SIMILARITY = 0.2
ASSISTANT_CITATION_MAX_ITEMS = 4
ASSISTANT_RETRIEVAL_WORKERS = 2
ASSISTANT_HISTORY_QUERY_USER_TURNS = 2
ASSISTANT_MODEL_HISTORY_LIMIT = 6
ASSISTANT_FOLLOW_UP_MARKERS = (
    '继续', '展开', '细说', '再说', '再讲', '深入', '补充', '那', '那么', '这个', '这个问题',
    '上一题', '上一个', '它', '这块', '这一点', '刚才', '顺便', '那如果', '为什么', '然后呢',
)
ASSISTANT_POSITION_HINTS = {
    'frontend': ('react', 'vue', 'javascript', 'typescript', 'css', 'html', '浏览器', '前端', 'web前端', 'vite', 'webpack', 'next.js', 'nextjs'),
    'java_backend': ('java', 'spring', 'springboot', 'mybatis', 'redis', 'mysql', '后端', '后端开发', '微服务', 'jvm'),
    'test_engineer': ('测试', '软件测试', '测试工程师', 'qa', 'quality assurance', '接口自动化', 'ui自动化', 'jmeter', '测试用例', '缺陷', 'bug', '回归测试'),
    'agent_developer': ('agent', '智能体', 'mcp', 'react agent', 'tool call', 'function calling', 'langgraph', 'agent开发'),
    'algorithm': ('算法', '机器学习', '深度学习', '模型', '训练', '推理', 'embedding', '检索', '召回', '排序', '向量'),
    'product_manager': ('产品', '需求', 'prd', 'roadmap', '转化', '用户增长', '产品经理'),
    'devops': ('devops', 'docker', 'kubernetes', 'k8s', 'ci/cd', '运维', '部署'),
}


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, str(default))).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(default)


ASSISTANT_ASYNC_ENABLED = _env_bool("ASSISTANT_ASYNC_ENABLED", True)
ASSISTANT_TASK_MAX_WORKERS = max(
    1,
    min(
        8,
        _safe_int(os.environ.get("ASSISTANT_TASK_MAX_WORKERS", 2), 2),
    ),
)
ASSISTANT_TASK_RETENTION_SECONDS = max(
    120,
    min(
        7200,
        _safe_int(os.environ.get("ASSISTANT_TASK_RETENTION_SECONDS", 900), 900),
    ),
)
ASSISTANT_FAST_ACK_TEXT = str(
    os.environ.get("ASSISTANT_FAST_ACK_TEXT", "已接收，正在分析你的问题...")
).strip() or "已接收，正在分析你的问题..."


ASSISTANT_MIN_TOKENS = max(
    64,
    min(
        2048,
        _safe_int(os.environ.get("ASSISTANT_MIN_TOKENS", 256), 256),
    ),
)
ASSISTANT_MAX_TOKENS = max(
    ASSISTANT_MIN_TOKENS,
    min(
        4096,
        _safe_int(os.environ.get("ASSISTANT_MAX_TOKENS", 2048), 2048),
    ),
)
ASSISTANT_ADAPTIVE_BASE_TOKENS = max(
    ASSISTANT_MIN_TOKENS,
    min(
        ASSISTANT_MAX_TOKENS,
        _safe_int(os.environ.get("ASSISTANT_ADAPTIVE_BASE_TOKENS", 640), 640),
    ),
)
ASSISTANT_CONTINUATION_ENABLED = _env_bool("ASSISTANT_CONTINUATION_ENABLED", True)
ASSISTANT_CONTINUATION_MAX_TOKENS = max(
    ASSISTANT_MIN_TOKENS,
    min(
        ASSISTANT_MAX_TOKENS,
        _safe_int(os.environ.get("ASSISTANT_CONTINUATION_MAX_TOKENS", 768), 768),
    ),
)
ASSISTANT_STREAM_ENABLED = _env_bool("ASSISTANT_STREAM_ENABLED", True)
ASSISTANT_STREAM_CHUNK_CHARS = max(
    40,
    min(
        400,
        _safe_int(os.environ.get("ASSISTANT_STREAM_CHUNK_CHARS", 120), 120),
    ),
)
ASSISTANT_STREAM_CHUNK_DELAY_MS = max(
    0,
    min(
        300,
        _safe_int(os.environ.get("ASSISTANT_STREAM_CHUNK_DELAY_MS", 70), 70),
    ),
)
ASSISTANT_HISTORY_COMPRESS_MAX_CHARS = max(
    1200,
    min(
        12000,
        _safe_int(os.environ.get("ASSISTANT_HISTORY_COMPRESS_MAX_CHARS", 3200), 3200),
    ),
)
ASSISTANT_HISTORY_COMPRESS_KEEP_TURNS = max(
    2,
    min(
        12,
        _safe_int(os.environ.get("ASSISTANT_HISTORY_COMPRESS_KEEP_TURNS", 6), 6),
    ),
)

ASR_SPEECH_END_GRACE_MS = max(
    0,
    min(
        2000,
        _safe_int(config.get('interview.asr_speech_end_grace_ms', 420), 420),
    ),
)
ASR_SEGMENT_PREFER_FINAL_ONLY = _env_bool("ASR_SEGMENT_PREFER_FINAL_ONLY", True)
ASR_FINAL_USE_HINT_PROMPT = _env_bool("ASR_FINAL_USE_HINT_PROMPT", False)
ASR_DEBUG_STREAM_ENABLED = _env_bool("ASR_DEBUG_STREAM_ENABLED", True)
ASR_MIN_SEGMENT_UNITS = max(1, min(12, _safe_int(os.environ.get("ASR_MIN_SEGMENT_UNITS", 3), 3)))
ASR_PENDING_AUDIO_MAX_CHUNKS = max(4, min(240, _safe_int(os.environ.get("ASR_PENDING_AUDIO_MAX_CHUNKS", 80), 80)))
ASR_PENDING_AUDIO_MAX_BYTES = max(
    32000,
    min(4 * 1024 * 1024, _safe_int(os.environ.get("ASR_PENDING_AUDIO_MAX_BYTES", 512000), 512000)),
)
RUNTIME_RECONNECT_GRACE_SECONDS = max(
    5,
    min(
        300,
        _safe_int(os.environ.get("RUNTIME_RECONNECT_GRACE_SECONDS", 90), 90),
    ),
)
RUNTIME_COMMIT_DELAY_SECONDS = max(
    0.0,
    min(
        1.0,
        _safe_int(config.get('interview.commit_delay_ms', os.environ.get("RUNTIME_COMMIT_DELAY_MS", 120)), 120) / 1000.0,
    ),
)


def _parse_cors_origins():
    configured = config.get('server.cors_origins', ['*'])
    env_override = (
        os.environ.get('SOCKETIO_CORS_ALLOWED_ORIGINS')
        or os.environ.get('CORS_ALLOWED_ORIGINS')
        or ''
    ).strip()

    if env_override:
        if env_override == '*':
            return '*'
        configured = [item.strip() for item in env_override.split(',') if item.strip()]

    origins = []
    for item in configured if isinstance(configured, list) else [configured]:
        value = str(item or '').strip()
        if not value:
            continue
        if value == '*':
            return '*'
        origins.append(value.rstrip('/'))

    if FLASK_DEBUG:
        frontend_url = (
            os.environ.get('NEXT_PUBLIC_BACKEND_URL', '').strip()
            or os.environ.get('NEXT_PUBLIC_API_URL', '').strip()
        )
        if frontend_url:
            try:
                parsed = urlparse(frontend_url)
                if parsed.scheme and parsed.netloc:
                    backend_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip('/')
                    if backend_origin not in origins:
                        origins.append(backend_origin)
            except Exception:
                pass

    return origins or '*'


CORS_ORIGINS = _parse_cors_origins()# 跨域配置

CORS(app, origins=CORS_ORIGINS)

logger.info(f"Flask 应用初始化完成 - Host: {FLASK_HOST}, Port: {FLASK_PORT}, Debug: {FLASK_DEBUG}") # 日志输出

# 初始化 Socket.IO
socketio = SocketIO(
    app,
    cors_allowed_origins=CORS_ORIGINS,
    async_mode=SOCKETIO_ASYNC_MODE,
    max_http_buffer_size=config.get('server.max_buffer_size', 10485760)
)

logger.info(f"Socket.IO 初始化完成 - async_mode={socketio.async_mode}")

if llm_manager is None:
    logger.error(f"LLM 初始化失败，相关功能不可用：{llm_import_error}")
elif getattr(llm_manager, 'enabled', False):
    logger.info("LLM 模块初始化成功")
else:
    logger.warning("LLM 模块已加载，但当前未启用")

if rag_service is None:
    logger.error(f"RAG 初始化失败，相关功能不可用：{rag_import_error}")
elif getattr(rag_service, 'enabled', False):
    logger.info("RAG 模块初始化成功")
else:
    logger.info("RAG 模块未启用或未配置")

if assistant_service is None:
    logger.error(f"Assistant 初始化失败，相关功能不可用：{assistant_import_error}")
elif getattr(assistant_service, 'enabled', False):
    logger.info("Assistant 模块初始化成功")
else:
    logger.info("Assistant 模块未启用")

# 初始化工具类
logger.info("初始化工具模块...")
data_manager = DataManager()
configured_db_path = str(config.get('database.path', 'interview_system.db') or 'interview_system.db').strip()
resolved_db_path = Path(configured_db_path)
if not resolved_db_path.is_absolute():
    resolved_db_path = (Path(__file__).resolve().parent / resolved_db_path).resolve()
db_manager = DatabaseManager(str(resolved_db_path))
knowledge_graph_service = None
if KnowledgeGraphService is not None:
    try:
        knowledge_graph_service = KnowledgeGraphService(db_manager=db_manager, logger=logger)
    except Exception as e:
        knowledge_graph_service = None
        knowledge_graph_import_error = str(e)
resume_optimizer_service = None
if ResumeOptimizer is not None:
    try:
        resume_optimizer_service = ResumeOptimizer(
            db_manager=db_manager,
            llm_manager=llm_manager,
            logger=logger,
        )
    except Exception as e:
        resume_optimizer_service = None
        resume_optimizer_import_error = str(e)
try:
    seed_result = db_manager.ensure_user(
        email=AUTH_DEFAULT_EMAIL,
        password_hash=hash_auth_password(AUTH_DEFAULT_PASSWORD),
        display_name=AUTH_DEFAULT_NAME,
        is_demo=True,
    )
    if seed_result and seed_result.get('success'):
        if seed_result.get('created'):
            logger.info(f"[auth] created default demo account: {AUTH_DEFAULT_EMAIL}")
        else:
            logger.info(f"[auth] default demo account already exists: {AUTH_DEFAULT_EMAIL}")
    else:
        logger.warning(f"[auth] failed to seed default demo account: {seed_result}")
except Exception as exc:
    logger.error(f"[auth] exception while seeding default demo account: {exc}")
session_registry = SessionRegistry()
state_orchestrator = StateOrchestrator(session_registry)
speech_normalizer = SpeechTextNormalizer()
evaluation_service = (
    EvaluationService(
        db_manager=db_manager,
        rag_service=rag_service,
        llm_manager=llm_manager,
        logger=logger,
    )
    if EvaluationService is not None else None
)
if evaluation_service is None and evaluation_import_error:
    logger.error(f"评估服务初始化失败：{evaluation_import_error}")
elif evaluation_service is not None:
    logger.info("三层评价服务初始化成功")

    def _on_evaluation_completed(interview_id: str, turn_id: str, status: str) -> None:
        """评估完成时通知相关前端客户端刷新报告。"""
        try:
            socketio.emit('evaluation_completed', {
                'interview_id': interview_id,
                'turn_id': turn_id,
                'status': status,
                'timestamp': time.time(),
            })
        except Exception as exc:
            logger.warning(f"评估完成通知发送失败: {exc}")

    evaluation_service.register_completion_callback(_on_evaluation_completed)

video_upload_service = VideoUploadService(logger=logger)
report_generator = ReportGenerator()
replay_service = ReplayService(
    db_manager=db_manager,
    llm_manager=llm_manager,
    rag_service=rag_service,
    logger=logger,
)
replay_task_manager = ReplayTaskManager(
    replay_service=replay_service,
    max_workers=int(config.get('replay.max_workers', 2)),
    logger=logger,
)
behavior_analysis_service = BehaviorAnalysisService(
    db_manager=db_manager,
    logger=logger,
)
behavior_task_manager = BehaviorAnalysisTaskManager(
    service=behavior_analysis_service,
    max_workers=int(config.get('replay.behavior.max_workers', 1)),
    logger=logger,
)

SERVICE_PREWARM_CACHE_SECONDS = 300.0
_service_prewarm_lock = threading.RLock()
_service_prewarm_thread: threading.Thread | None = None
_service_prewarm_state = {
    "status": "idle",  # idle | running | completed | partial | failed
    "trigger": "",
    "last_started_at": 0.0,
    "last_finished_at": 0.0,
    "duration_ms": 0.0,
    "results": {},
}


def _snapshot_service_prewarm_state() -> dict:
    with _service_prewarm_lock:
        snapshot = dict(_service_prewarm_state)
        snapshot["running"] = bool(_service_prewarm_thread and _service_prewarm_thread.is_alive())
    snapshot["age_seconds"] = (
        round(max(0.0, time.time() - float(snapshot.get("last_finished_at") or 0.0)), 2)
        if snapshot.get("last_finished_at") else None
    )
    return snapshot


def _run_service_prewarm(trigger: str = "api") -> None:
    started_at = time.time()
    results: dict = {}
    any_failure = False

    # LLM 预热
    llm_started = time.time()
    llm_result = {
        "enabled": bool(llm_manager and getattr(llm_manager, "enabled", False)),
        "success": True,
        "latency_ms": 0.0,
        "skipped": False,
        "error": "",
    }
    try:
        if llm_result["enabled"]:
            if hasattr(llm_manager, "warmup"):
                llm_result = dict(llm_manager.warmup() or llm_result)
            else:
                llm_result["success"] = bool(getattr(llm_manager, "check_enabled", lambda: False)())
        else:
            llm_result["skipped"] = True
    except Exception as exc:
        llm_result["success"] = False
        llm_result["error"] = str(exc)[:240]
    llm_result["latency_ms"] = round((time.time() - llm_started) * 1000.0, 2)
    results["llm"] = llm_result
    if llm_result.get("enabled") and not llm_result.get("success"):
        any_failure = True

    # RAG 预热
    rag_started = time.time()
    rag_result = {
        "enabled": bool(rag_service and getattr(rag_service, "enabled", False)),
        "success": True,
        "latency_ms": 0.0,
        "skipped": False,
        "error": "",
        "ready": False,
    }
    try:
        if rag_result["enabled"]:
            rag_ready = bool(getattr(rag_service, "ensure_ready", lambda: False)())
            rag_result["ready"] = rag_ready
            rag_result["success"] = rag_ready
            if hasattr(rag_service, "status"):
                status_payload = rag_service.status() or {}
                rag_result["question_count"] = int(status_payload.get("question_count") or 0)
                rag_result["rubric_count"] = int(status_payload.get("rubric_count") or 0)
        else:
            rag_result["skipped"] = True
    except Exception as exc:
        rag_result["success"] = False
        rag_result["error"] = str(exc)[:240]
    rag_result["latency_ms"] = round((time.time() - rag_started) * 1000.0, 2)
    results["rag"] = rag_result
    if rag_result.get("enabled") and not rag_result.get("success"):
        any_failure = True

    # ASR 预热
    asr_started = time.time()
    asr_result = {
        "enabled": bool(asr_manager and getattr(asr_manager, "enabled", False)),
        "success": True,
        "latency_ms": 0.0,
        "skipped": False,
        "error": "",
    }
    prewarm_stream_id = f"asr_prewarm_{uuid.uuid4().hex[:10]}"
    try:
        if asr_result["enabled"]:
            started = bool(
                asr_manager.start_session(
                    prewarm_stream_id,
                    on_result=lambda _text: None,
                    on_partial=lambda _text: None,
                    on_error=lambda _error: None,
                )
            )
            asr_result["success"] = started
            if not started:
                asr_result["error"] = "start_session returned false"
        else:
            asr_result["skipped"] = True
    except Exception as exc:
        asr_result["success"] = False
        asr_result["error"] = str(exc)[:240]
    finally:
        try:
            if asr_manager is not None:
                asr_manager.stop_session(prewarm_stream_id)
        except Exception:
            pass
    asr_result["latency_ms"] = round((time.time() - asr_started) * 1000.0, 2)
    results["asr"] = asr_result
    if asr_result.get("enabled") and not asr_result.get("success"):
        any_failure = True

    # TTS 预热
    tts_started = time.time()
    tts_result = {
        "enabled": bool(tts_manager and getattr(tts_manager, "enabled", False)),
        "success": True,
        "latency_ms": 0.0,
        "skipped": False,
        "error": "",
        "provider": "",
    }
    try:
        if tts_result["enabled"]:
            status_payload = tts_manager.get_status() or {}
            remote_error = str(status_payload.get("remote_error") or "").strip()
            remote_status = status_payload.get("remote") if isinstance(status_payload.get("remote"), dict) else {}
            tts_result["provider"] = str(remote_status.get("active_provider") or "").strip()
            tts_result["success"] = not remote_error
            if remote_error:
                tts_result["error"] = remote_error[:240]
        else:
            tts_result["skipped"] = True
    except Exception as exc:
        tts_result["success"] = False
        tts_result["error"] = str(exc)[:240]
    tts_result["latency_ms"] = round((time.time() - tts_started) * 1000.0, 2)
    results["tts"] = tts_result
    if tts_result.get("enabled") and not tts_result.get("success"):
        any_failure = True

    duration_ms = round((time.time() - started_at) * 1000.0, 2)
    final_status = "failed" if all(
        item.get("enabled") and not item.get("success") for item in results.values()
    ) else ("partial" if any_failure else "completed")
    with _service_prewarm_lock:
        _service_prewarm_state["status"] = final_status
        _service_prewarm_state["trigger"] = trigger
        _service_prewarm_state["last_finished_at"] = time.time()
        _service_prewarm_state["duration_ms"] = duration_ms
        _service_prewarm_state["results"] = results
    logger.info(f"[prewarm] completed status={final_status} trigger={trigger} duration_ms={duration_ms}")


def _build_question_rag_context(
    position: str,
    difficulty: str = "medium",
    round_type: str = "technical",
    context: str = "",
    interview_state: dict | None = None
) -> tuple[str, dict | None]:
    """为生成问题构造 RAG 上下文。"""
    if rag_service is None or not getattr(rag_service, 'enabled', False):
        return "", None

    try:
        question_plan = None
        if interview_state:
            question_plan = rag_service.get_next_question(
                interview_state,
                context=context,
                top_k=getattr(rag_service, 'max_context_results', 2)
            )
            rag_context = rag_service.format_question_plan(question_plan)
            if rag_context:
                return rag_context, question_plan

        return rag_service.build_question_context(
            position=position,
            difficulty=difficulty,
            round_type=round_type,
            context=context
        ), question_plan
    except Exception as e:
        logger.warning(f"构建提问 RAG 上下文失败：{e}")
        return "", None


def _extract_question_id_from_plan(question_plan: dict | None) -> str:
    """从最近一次选题结果中提取原始 question_id。"""
    candidates = (question_plan or {}).get('candidate_questions', []) or []
    if not candidates:
        return ""
    return str(candidates[0].get('id', '')).strip()


def _extract_question_text_from_plan(question_plan: dict | None) -> str:
    """从 question_plan 中提取首个候选题文本，用于引导 LLM 基于 RAG 出题。"""
    candidates = (question_plan or {}).get('candidate_questions', []) or []
    if not candidates:
        return ""
    question_text = str(candidates[0].get('question', '')).strip()
    return question_text


def _extract_runtime_question_core(reply_text: str, fallback: str = "") -> str:
    """从面试官回复中提取用于后续分析/追问的纯题干。"""
    source = str(reply_text or "").strip()
    if not source:
        return str(fallback or "").strip()

    def trim_question_segment(candidate: str) -> str:
        normalized = str(candidate or "").strip()
        parts = [part.strip() for part in re.split(r"[，,；;。.!！]\s*", normalized) if part.strip()]
        if len(parts) >= 2 and parts[-1].endswith(("？", "?")):
            prefix = "".join(parts[:-1])
            if any(marker in prefix for marker in ("回答", "刚才", "不错", "概括", "完整", "补充", "遗漏", "欠缺", "换一个方向")):
                return parts[-1]
        return normalized

    if llm_manager is not None:
        parser = getattr(llm_manager, "_extract_primary_question", None)
        if callable(parser):
            try:
                parsed = trim_question_segment(str(parser(source) or "").strip())
                if parsed:
                    return parsed
            except Exception:
                pass

    lines = [line.strip() for line in source.splitlines() if line.strip()]
    question_segments = [
        trim_question_segment(
            re.sub(r"^(?:下一题|追问|问题|请回答|请你回答)\s*[:：]\s*", "", match.strip())
        )
        for match in re.findall(r"[^。！？!?\n；;]*[？?]", source)
        if match.strip()
    ]
    for candidate in reversed(question_segments):
        if len(candidate) >= 6:
            return candidate

    for line in reversed(lines):
        if len(line) >= 6 and line.endswith(("？", "?")):
            return line

    for part in re.split(r"(?<=[？?])\s*", source):
        candidate = str(part or "").strip()
        if len(candidate) >= 6 and ("？" in candidate or "?" in candidate):
            return candidate

    normalized_fallback = str(fallback or "").strip()
    return normalized_fallback or source


def _with_runtime_question(
    decision: dict | None,
    *,
    reply_text: str = "",
    fallback_question: str = "",
) -> dict:
    payload = dict(decision or {})
    runtime_question = str(
        payload.get("runtime_question")
        or payload.get("coach_next_question")
        or ""
    ).strip()
    if not runtime_question:
        runtime_question = _extract_runtime_question_core(reply_text, fallback=fallback_question)
    if runtime_question:
        payload["runtime_question"] = runtime_question
    return payload


def _downgrade_switch_decision(
    decision: dict | None,
    *,
    reason: str,
) -> dict:
    payload = dict(decision or {})
    payload["next_action"] = "ask_followup"
    payload["switch_fallback"] = True
    payload["switch_fallback_reason"] = str(reason or "switch_generation_failed")
    return payload


def _build_initial_interview_context(
    *,
    round_type: str,
    position: str,
    difficulty: str,
    training_mode: str = "",
) -> str:
    normalized_round = _normalize_round_type(round_type)
    normalized_mode = str(training_mode or "").strip().lower()
    hints: list[str] = []

    if normalized_mode == 'focused_training':
        hints.append("这是训练模式，请省略寒暄，直接进入最有针对性的训练题。")
    else:
        hints.append("这是更贴近真实面试场景的开场，请语气自然、像真人面试官，不要机械。")

    if normalized_round == 'project':
        hints.append("首题优先围绕候选人简历中的真实项目切入，聚焦个人职责、关键决策、技术深度和问题解决过程。")
        hints.append("避免每次都使用同一种泛化开场，优先选择能深挖项目细节和技术判断的场景题。")
    elif normalized_round == 'system_design':
        hints.append("首题优先选择与岗位和简历背景贴近的系统设计场景，关注核心模块、关键数据流、容量与权衡。")
        hints.append("避免总是使用完全相同的宽泛开场，优先给出更具体、更有业务感的系统设计问题。")
    elif normalized_round == 'technical':
        hints.append("首题先验证岗位关键基础能力，但不要只问过于教科书式的定义题。")
    elif normalized_round == 'hr':
        hints.append("开场更注重动机、经历和价值观表达，语气保持自然。")

    hints.append(f"目标岗位：{position}；目标难度：{difficulty}。")
    return "\n".join(hints)


def _compose_initial_interviewer_message(
    *,
    question_text: str,
    round_type: str,
    position: str,
    training_mode: str = "",
) -> str:
    normalized_mode = str(training_mode or "").strip().lower()
    normalized_round = _normalize_round_type(round_type)
    question = str(question_text or "").strip()
    if not question:
        if normalized_mode == 'focused_training':
            return "我们直接进入训练，请先回答这道题。"
        return "你好，我们先做一个简短的自我介绍，然后进入正式提问。"

    if normalized_mode == 'focused_training':
        return f"我们直接进入训练，先从这道题开始：\n\n{question}"

    round_name_map = {
        'technical': '技术面',
        'project': '项目面',
        'system_design': '系统设计面',
        'hr': '综合面',
    }
    opener = f"你好，我们现在开始这一轮{round_name_map.get(normalized_round, '面试')}。"
    if normalized_round in {'project', 'system_design'}:
        return (
            f"{opener} 你可以先用大约一分钟，结合和 {position} 相关的经历做个简短自我介绍。"
            f"介绍完后，我们先从这个问题切入：\n\n{question}"
        )
    if normalized_round == 'hr':
        return f"{opener} 你先做个简短自我介绍，我们再围绕这个问题展开：\n\n{question}"
    return f"{opener} 你先做个简短自我介绍，然后我们开始第一题：\n\n{question}"


def _build_intro_only_interviewer_message(*, round_type: str, position: str) -> str:
    normalized_round = _normalize_round_type(round_type)
    round_name_map = {
        'technical': '技术面',
        'project': '项目面',
        'system_design': '系统设计面',
        'hr': '综合面',
    }
    opener = f"你好，我们现在开始这一轮{round_name_map.get(normalized_round, '面试')}。"
    if normalized_round in {'project', 'system_design'}:
        return (
            f"{opener} 你可以先用大约一分钟，结合和 {position} 相关的经历，"
            "做一个简短的自我介绍。介绍完成后，我们再进入第一道正式问题。"
        )
    if normalized_round == 'hr':
        return f"{opener} 你先做一个简短的自我介绍，后面我们再围绕你的经历和动机继续展开。"
    return f"{opener} 你先做一个简短的自我介绍，后面我们再进入第一道正式问题。"


def _build_fallback_first_formal_question(*, round_type: str, position: str) -> str:
    normalized_round = _normalize_round_type(round_type)
    if normalized_round == 'project':
        return f"先从你和 {position} 最相关的一个项目讲起：这个项目的目标是什么，你负责了哪些核心部分？"
    if normalized_round == 'system_design':
        return "请你选一个与你目标岗位最相关的业务场景，先给出整体方案，再说明核心模块划分和关键权衡。"
    if normalized_round == 'hr':
        return "结合你刚才的介绍，说说你为什么会选择这个岗位方向，以及你最看重的一段经历是什么。"
    return f"结合你刚才的自我介绍，请先展开讲一个与你目标岗位 {position} 最相关的技术经历。"


def _normalize_interview_difficulty(value: str) -> str:
    normalized = str(value or '').strip().lower()
    return normalized if normalized in {'easy', 'medium', 'hard'} else ''


def _parse_auto_end_question_limit(value, default_value: int) -> int:
    try:
        normalized = int(value)
    except Exception:
        normalized = int(default_value)
    return max(1, min(normalized, 20))


def _parse_selected_question_payload(payload) -> dict | None:
    if not isinstance(payload, dict):
        return None

    question_text = str(payload.get('question') or payload.get('title') or '').strip()
    if not question_text:
        return None

    question_id = str(payload.get('id') or '').strip()
    if not question_id:
        question_id = f"manual_{hashlib.sha1(question_text.encode('utf-8')).hexdigest()[:12]}"

    round_type = _normalize_round_type(payload.get('round_type') or payload.get('round'))
    position = str(payload.get('position') or '').strip().lower()
    difficulty = _normalize_interview_difficulty(payload.get('difficulty'))
    category = str(payload.get('category') or '').strip()

    return {
        'id': question_id,
        'question': question_text,
        'round_type': round_type,
        'position': position,
        'difficulty': difficulty,
        'category': category,
    }


def _build_forced_question_plan(
    question_id: str,
    question_text: str,
    round_type: str,
    position: str,
    difficulty: str,
    category: str = "",
) -> dict:
    return {
        'candidate_questions': [
            {
                'id': str(question_id or '').strip() or "manual_selected_question",
                'question': str(question_text or '').strip(),
                'round_type': str(round_type or '').strip(),
                'position': str(position or '').strip(),
                'difficulty': str(difficulty or '').strip(),
                'category': str(category or '').strip(),
                'source': 'manual_selected_question',
            }
        ],
        'question': str(question_text or '').strip(),
        'source': 'manual_selected_question',
    }


def _build_answer_rag_context(
    position: str,
    round_type: str,
    current_question: str,
    user_answer: str = "",
    interview_state: dict | None = None,
    question_plan: dict | None = None,
) -> tuple[str, dict | None]:
    """为追问/纠偏构造 RAG 上下文。"""
    if rag_service is None or not getattr(rag_service, 'enabled', False):
        return "", None

    try:
        analysis_result = None
        question_id = _extract_question_id_from_plan(question_plan)
        if question_id or str(current_question or "").strip():
            analysis_result = rag_service.analyze_answer(
                question_id=question_id or None,
                candidate_answer=user_answer,
                session_state=interview_state,
                current_question=current_question,
                position=position,
                round_type=round_type
            )

        context_parts = []
        if analysis_result:
            analysis_context = rag_service.format_analysis_result(analysis_result)
            if analysis_context:
                context_parts.append(analysis_context)

        reference_context = rag_service.build_answer_context(
            position=position,
            current_question=current_question,
            user_answer=user_answer,
            round_type=round_type
        )
        if reference_context:
            context_parts.append(reference_context)

        return "\n\n".join(part for part in context_parts if part), analysis_result
    except Exception as e:
        logger.warning(f"构建回答 RAG 上下文失败：{e}")
        return "", None


def _merge_text_blocks(*parts: str) -> str:
    return "\n\n".join(str(part).strip() for part in parts if str(part).strip())


def _get_last_interviewer_question(chat_history):
    if not chat_history:
        return ''
    for item in reversed(chat_history):
        if isinstance(item, dict) and item.get('role') == 'interviewer':
            return item.get('content', '')
    return ''


def _is_noise_text(text: str) -> bool:
    normalized = ' '.join(str(text or '').strip().split())
    if not normalized:
        return True

    stripped = normalized.strip('，。！？,.!?、~…-— ')
    if not stripped:
        return True

    fillers = {
        '啊', '嗯', '呃', '哦', '哎', '额', '唉', '哈', '噢', '欸', '嘛', '呗', '咯', '诶', '喔',
    }
    weak_phrases = {
        '谢谢', '感谢', '好的', '好的呢', '然后', '还有', '那个', '这个', '就是', '然后呢',
        '嗯嗯', '啊啊', '呃呃',
    }
    short_valid_answers = {
        '对', '是', '有', '会', '能', '行', '好', '嗯', '可以', '知道', '记得', '不是', '不会',
        '有的', '会的', '能的', '行的',
    }

    if stripped in fillers:
        return True

    if stripped in weak_phrases:
        return True

    if len(set(stripped)) == 1 and stripped[0] in fillers and len(stripped) <= 4:
        return True

    if len(stripped) == 1 and stripped not in short_valid_answers:
        return True

    if len(stripped) <= 3 and stripped in short_valid_answers:
        return False

    return False


def _current_question_id(runtime) -> str:
    question_id = _extract_question_id_from_plan(runtime.last_question_plan)
    return question_id or runtime.turn_id or f"question_{runtime.turn_index or 0}"


def _cancel_answer_finalize_timer(runtime) -> None:
    timer = getattr(runtime, 'pending_answer_finalize_timer', None)
    if timer:
        timer.cancel()
        runtime.pending_answer_finalize_timer = None


def _reset_answer_session(runtime) -> None:
    _cancel_answer_finalize_timer(runtime)
    runtime.current_answer_session = None


def _ensure_answer_session(runtime) -> AnswerSession:
    current = runtime.current_answer_session
    if current and current.turn_id == runtime.turn_id and current.status != 'finalized':
        return current

    answer_session = AnswerSession(
        question_id=_current_question_id(runtime),
        turn_id=runtime.turn_id,
        last_speech_epoch=runtime.speech_epoch,
    )
    runtime.current_answer_session = answer_session
    return answer_session


def _emit_answer_session_update(runtime, source: str = "") -> None:
    answer_session = runtime.current_answer_session
    if not answer_session:
        return

    payload = answer_session.to_payload()
    payload.update({
        'session_id': runtime.session_id,
        'interrupt_epoch': runtime.interrupt_epoch,
        'source': source,
        'short_pause_ms': int(runtime.short_pause_threshold_seconds * 1000),
        'long_pause_ms': int(runtime.long_pause_threshold_seconds * 1000),
        'timestamp': time.time(),
    })
    socketio.emit('answer_session_update', payload, to=runtime.client_id)


def _emit_realtime_speech_metrics(
    runtime,
    answer_session: AnswerSession,
    *,
    is_speaking: bool,
    text_snapshot: str = "",
    source: str = "",
) -> None:
    metrics = answer_session.update_realtime_speech_metrics(
        is_speaking=is_speaking,
        text_snapshot=text_snapshot,
        segment_index=max(1, len(answer_session.segments) + (1 if is_speaking else 0)),
    )
    socketio.emit('speech_metrics_realtime', {
        'session_id': runtime.session_id,
        'turn_id': runtime.turn_id,
        'answer_session_id': answer_session.answer_session_id,
        'interrupt_epoch': runtime.interrupt_epoch,
        'source': source,
        'timestamp': time.time(),
        **metrics,
    }, to=runtime.client_id)


def _consume_runtime_segment_text(runtime, asr_generation: int = 0) -> str:
    _final_text, _partial_text, merged_text = _build_pending_asr_text(runtime)
    runtime.pending_asr_partials.clear()
    runtime.pending_asr_finals.clear()
    if asr_generation and runtime.last_finalized_asr_generation == asr_generation:
        runtime.last_finalized_asr_generation = 0
        runtime.last_finalized_asr_speech_epoch = 0
    return merged_text


def _pending_asr_audio_lock(runtime):
    lock = getattr(runtime, 'pending_asr_audio_lock', None)
    if lock is None:
        lock = threading.RLock()
        setattr(runtime, 'pending_asr_audio_lock', lock)
    return lock


def _reset_pending_asr_audio(runtime) -> None:
    lock = _pending_asr_audio_lock(runtime)
    with lock:
        runtime.pending_asr_audio_chunks.clear()
        runtime.pending_asr_audio_bytes = 0


def _enqueue_pending_asr_audio(runtime, audio_data: bytes) -> bool:
    if not audio_data:
        return False

    lock = _pending_asr_audio_lock(runtime)
    with lock:
        queued = runtime.pending_asr_audio_chunks
        queued.append(audio_data)
        runtime.pending_asr_audio_bytes += len(audio_data)

        while len(queued) > ASR_PENDING_AUDIO_MAX_CHUNKS:
            dropped = queued.pop(0)
            runtime.pending_asr_audio_bytes = max(0, runtime.pending_asr_audio_bytes - len(dropped))

        while runtime.pending_asr_audio_bytes > ASR_PENDING_AUDIO_MAX_BYTES and queued:
            dropped = queued.pop(0)
            runtime.pending_asr_audio_bytes = max(0, runtime.pending_asr_audio_bytes - len(dropped))

        return bool(queued)


def _flush_pending_asr_audio(runtime, asr_generation: int = 0) -> int:
    if asr_manager is None:
        return 0

    lock = _pending_asr_audio_lock(runtime)
    with lock:
        if asr_generation and runtime.active_asr_generation != asr_generation:
            return 0
        if not runtime.active_asr_stream_id or not asr_manager.is_available(runtime.active_asr_stream_id):
            return 0

        flushed = 0
        while runtime.pending_asr_audio_chunks:
            if asr_generation and runtime.active_asr_generation != asr_generation:
                break
            stream_id = runtime.active_asr_stream_id
            if not stream_id or not asr_manager.is_available(stream_id):
                break

            chunk = runtime.pending_asr_audio_chunks[0]
            try:
                queued_ok = bool(asr_manager.send_audio(stream_id, chunk))
            except Exception:
                queued_ok = False
            if not queued_ok:
                break

            runtime.pending_asr_audio_chunks.pop(0)
            runtime.pending_asr_audio_bytes = max(0, runtime.pending_asr_audio_bytes - len(chunk))
            flushed += 1

        return flushed


def _merge_asr_fragments(fragments: list[str]) -> str:
    def _sanitize_fragment(value: str) -> str:
        text = ' '.join(str(value or '').strip().split())
        if not text:
            return ''
        return text.strip()

    merged = ""
    for fragment in fragments or []:
        chunk = _sanitize_fragment(fragment)
        if not chunk:
            continue
        if not merged:
            merged = chunk
            continue
        if chunk.startswith(merged) or merged in chunk:
            merged = chunk
            continue
        if merged.startswith(chunk):
            continue
        merged = merge_answer_text(merged, chunk)
    return str(merged).strip()


def _build_pending_asr_text(runtime) -> tuple[str, str, str]:
    final_text = _merge_asr_fragments(runtime.pending_asr_finals)
    partial_text = _merge_asr_fragments(runtime.pending_asr_partials)
    merged_text = build_live_answer_text(final_text, partial_text)
    return final_text, partial_text, str(merged_text or "").strip()


def _extract_technical_terms(*texts: str, limit: int = 20) -> list[str]:
    # 抽取英文术语/缩写/CamelCase，增强 ASR 文件复写对技术词的保留能力。
    pattern = re.compile(r"[A-Za-z][A-Za-z0-9_+.#/\-]{1,40}")
    seen: set[str] = set()
    terms: list[str] = []
    for text in texts:
        for match in pattern.findall(str(text or "")):
            token = str(match).strip()
            if len(token) < 2:
                continue
            lower = token.lower()
            if lower in seen:
                continue
            seen.add(lower)
            terms.append(token)
            if len(terms) >= limit:
                return terms
    return terms


def _persist_answer_audio(runtime, answer_session: AnswerSession) -> str:
    if not answer_session.audio_chunks:
        return ""

    output_dir = Path(__file__).resolve().parent / 'uploads' / 'answer_sessions'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{runtime.session_id}_{answer_session.answer_session_id}.wav"

    try:
        import wave

        with wave.open(str(output_path), 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b''.join(answer_session.audio_chunks))
    except Exception as exc:
        logger.warning(f"[ASR] 导出整题音频失败: {exc}")
        return ""

    return str(output_path)


def _estimate_answer_audio_duration_ms(answer_session: AnswerSession, audio_path: str = "") -> float:
    try:
        if audio_path and os.path.isfile(audio_path):
            import wave
            with wave.open(audio_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate() or 16000
                return max(0.0, (frames / float(sample_rate)) * 1000.0)
    except Exception as exc:
        logger.debug(f"[ASR] 读取音频时长失败，回退字节估算: {exc}")
    return max(0.0, (float(answer_session.audio_bytes) / 2.0 / 16000.0) * 1000.0)


def _count_text_units(text: str) -> int:
    content = str(text or "").strip()
    if not content:
        return 0
    return len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", content))


def _pick_segment_text(final_text: str, partial_text: str, merged_pending_text: str) -> str:
    final_text = str(final_text or "").strip()
    partial_text = str(partial_text or "").strip()
    merged_pending_text = str(merged_pending_text or "").strip()

    if not ASR_SEGMENT_PREFER_FINAL_ONLY:
        return merged_pending_text or final_text or partial_text

    if not final_text:
        return merged_pending_text or partial_text
    if not merged_pending_text:
        return final_text

    final_units = _count_text_units(final_text)
    merged_units = _count_text_units(merged_pending_text)
    if merged_units >= max(6, int(final_units * 1.25)):
        return merged_pending_text
    return final_text


def _is_low_information_asr_segment(text: str) -> bool:
    normalized = re.sub(r"[\s，。！？!?；;,.、~～…]+", "", str(text or "").strip().lower())
    if not normalized:
        return True
    units = _count_text_units(normalized)
    if units >= ASR_MIN_SEGMENT_UNITS:
        return False
    filler_only = {
        "嗯", "啊", "哦", "噢", "呃", "额", "诶", "哎", "唉",
        "好", "好的", "对", "是", "不是", "这个", "那个", "就是", "然后",
        "谢谢", "不好意思",
    }
    if normalized in filler_only:
        return True
    return units <= 1


def _text_token_overlap_ratio(text_a: str, text_b: str) -> float:
    tokens_a = set(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", str(text_a or "").lower()))
    tokens_b = set(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", str(text_b or "").lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    if union <= 0:
        return 0.0
    return float(intersection) / float(union)


def _reconcile_final_answer_text(draft_text: str, rewritten_text: str) -> tuple[str, str]:
    draft = str(draft_text or "").strip()
    rewritten = str(rewritten_text or "").strip()

    if not rewritten:
        return draft, 'fallback_empty_rewrite'
    if not draft:
        return rewritten, 'asr_final_rewrite_only'
    if rewritten == draft:
        return rewritten, 'asr_final_exact'
    if draft in rewritten:
        return rewritten, 'asr_final_superset'
    if rewritten in draft:
        return draft, 'draft_contains_rewrite'

    draft_units = _count_text_units(draft)
    rewritten_units = _count_text_units(rewritten)
    if draft_units >= 8 and rewritten_units <= max(4, int(draft_units * 0.55)):
        return draft, 'fallback_short_rewrite'

    overlap_ratio = _text_token_overlap_ratio(draft, rewritten)
    if draft_units >= 8 and rewritten_units >= 8 and overlap_ratio < 0.25:
        if rewritten_units >= max(8, int(draft_units * 0.85)):
            return rewritten, 'asr_final_rewrite_low_overlap_preferred'
        return draft, 'fallback_low_overlap_draft'

    if rewritten_units >= max(4, int(draft_units * 0.55)):
        return rewritten, 'asr_final_rewrite_preferred'
    return draft, 'fallback_draft_preferred'


def _rewrite_answer_text(runtime, answer_session: AnswerSession, audio_path: str = "") -> dict:
    if not audio_path or asr_manager is None or not hasattr(asr_manager, 'transcribe_file'):
        return {'text': answer_session.merged_text_draft, 'word_timestamps': [], 'confidence': None, 'mode': 'fallback_no_file'}

    prompt_parts = []
    if ASR_FINAL_USE_HINT_PROMPT:
        runtime_question = str(
            getattr(runtime, 'current_question_core', '')
            or getattr(runtime, 'current_question', '')
            or ''
        ).strip()
        prompt_parts = [
            "这是一次中文技术面试回答的音频转写，请尽量准确保留技术术语、英文缩写、数字和项目名称。",
            "只输出转写后的正文，不要补充解释，不要改写成总结。",
        ]
        if runtime_question:
            prompt_parts.append(f"当前题目：{runtime_question}")
        technical_terms = _extract_technical_terms(runtime_question, answer_session.merged_text_draft)
        if technical_terms:
            prompt_parts.append(
                "术语词表（若音频中出现，请优先按下列写法输出，保持大小写）："
                + "、".join(technical_terms)
            )

    rewrite_payload = {}
    if hasattr(asr_manager, 'transcribe_file_with_meta'):
        rewrite_payload = asr_manager.transcribe_file_with_meta(
            audio_path=audio_path,
            prompt="\n".join(part for part in prompt_parts if part) if prompt_parts else "",
        ) or {}
    else:
        rewrite_text = asr_manager.transcribe_file(
            audio_path=audio_path,
            prompt="\n".join(part for part in prompt_parts if part) if prompt_parts else "",
        )
        rewrite_payload = {'text': rewrite_text}

    rewritten_text = str(rewrite_payload.get('text') or '').strip()
    if rewritten_text:
        return {
            'text': rewritten_text,
            'word_timestamps': rewrite_payload.get('word_timestamps') or [],
            'confidence': rewrite_payload.get('confidence'),
            'mode': 'asr_final',
        }

    _log_runtime_event(
        runtime,
        'answer_session_rewrite_fallback',
        level='warning',
        answer_session_id=answer_session.answer_session_id,
        details=getattr(asr_manager, 'last_transcribe_error', '')[:200],
    )
    return {
        'text': answer_session.merged_text_draft,
        'word_timestamps': rewrite_payload.get('word_timestamps') or [],
        'confidence': rewrite_payload.get('confidence'),
        'mode': 'fallback_empty_rewrite',
    }


def _build_answer_session_final_metrics(runtime, answer_session: AnswerSession, audio_path: str, final_text: str):
    align_result = {}
    word_timestamps = []
    if asr_manager is not None and hasattr(asr_manager, 'align_transcript'):
        try:
            align_result = asr_manager.align_transcript(
                audio_path=audio_path,
                transcript=final_text,
                language=getattr(asr_manager, 'final_language', ''),
            ) or {}
            word_timestamps = align_result.get('word_timestamps') or []
        except Exception as exc:
            logger.warning(f"[ASR] 强制对齐失败，使用空时间戳回退: {exc}")
            word_timestamps = []

    audio_duration_ms = _estimate_answer_audio_duration_ms(answer_session, audio_path=audio_path)
    speech_metrics_final, pause_events, filler_events = compute_final_speech_metrics(
        transcript=final_text,
        draft_text=answer_session.merged_text_draft,
        word_timestamps=word_timestamps,
        audio_duration_ms=audio_duration_ms,
    )
    speech_metrics_final.update({
        'align_mode': str(align_result.get('mode') or 'unknown'),
        'align_confidence': align_result.get('confidence'),
    })
    answer_session.mark_final_metrics(
        final_transcript=final_text,
        word_timestamps=word_timestamps,
        pause_events=pause_events,
        filler_events=filler_events,
        speech_metrics_final=speech_metrics_final,
    )


def _finalize_answer_session(runtime, reason: str = "long_pause") -> None:
    current = session_registry.get(runtime.client_id)
    if not current or current.session_id != runtime.session_id or current.ended:
        return

    answer_session = current.current_answer_session
    if not answer_session or answer_session.turn_id != current.turn_id or answer_session.committed:
        return

    if answer_session.current_partial:
        answer_session.finalize_segment(answer_session.current_partial)

    final_candidate = (answer_session.merged_text_draft or answer_session.live_text).strip()
    if not final_candidate:
        _reset_answer_session(current)
        return

    _set_runtime_asr_lock(current, True, reason or 'answer_finalized')
    answer_session.mark_status('finalizing')
    _log_runtime_event(
        current,
        'answer_session_finalizing',
        source=reason,
        answer_session_id=answer_session.answer_session_id,
        segment_count=len(answer_session.segments),
    )
    _emit_orchestrator_state(current)
    _emit_answer_session_update(current, source=f'{reason}_finalizing')

    audio_path = _persist_answer_audio(current, answer_session)
    rewrite_payload = _rewrite_answer_text(current, answer_session, audio_path=audio_path)
    final_text, final_text_mode = _reconcile_final_answer_text(
        answer_session.merged_text_draft,
        rewrite_payload.get('text') or '',
    )
    final_text = final_text or final_candidate
    _log_runtime_event(
        current,
        'answer_session_final_text_selected',
        level='debug',
        answer_session_id=answer_session.answer_session_id,
        final_text_mode=final_text_mode,
        rewrite_mode=str(rewrite_payload.get('mode') or ''),
        draft_units=_count_text_units(answer_session.merged_text_draft),
        rewrite_units=_count_text_units(str(rewrite_payload.get('text') or '')),
        final_units=_count_text_units(final_text),
    )
    answer_session.mark_final(final_text, reason=reason, exported_audio_path=audio_path)
    _build_answer_session_final_metrics(current, answer_session, audio_path=audio_path, final_text=final_text)
    _emit_realtime_speech_metrics(
        current,
        answer_session,
        is_speaking=False,
        text_snapshot=final_text,
        source=f'{reason}_finalized',
    )
    _emit_answer_session_update(current, source=f'{reason}_finalized')

    answer_session.committed = True
    _emit_answer_session_update(current, source=f'{reason}_commit')
    _process_runtime_commit(
        current,
        answer_session.final_text or answer_session.merged_text_draft,
        answer_session.turn_id,
        source='answer_session',
    )


def _schedule_answer_session_finalize(
    runtime,
    reason: str = "long_pause",
    asr_generation: int = 0,
    speech_epoch: int = 0,
) -> None:
    current = session_registry.get(runtime.client_id)
    if not current or current.session_id != runtime.session_id or current.ended:
        return

    answer_session = current.current_answer_session
    if not answer_session or answer_session.turn_id != current.turn_id or answer_session.committed:
        return

    expected_speech_epoch = speech_epoch or getattr(answer_session, 'last_speech_epoch', 0)
    expected_asr_generation = asr_generation or getattr(answer_session, 'last_asr_generation', 0)

    if expected_speech_epoch and getattr(answer_session, 'last_speech_epoch', 0) != expected_speech_epoch:
        _log_runtime_event(
            current,
            'answer_session_finalize_dropped',
            level='debug',
            source=reason,
            answer_session_id=answer_session.answer_session_id,
            expected_speech_epoch=expected_speech_epoch,
            current_speech_epoch=getattr(answer_session, 'last_speech_epoch', 0),
            reason_detail='answer_session_epoch_changed_before_schedule',
        )
        return

    if expected_asr_generation and getattr(answer_session, 'last_asr_generation', 0) != expected_asr_generation:
        _log_runtime_event(
            current,
            'answer_session_finalize_dropped',
            level='debug',
            source=reason,
            answer_session_id=answer_session.answer_session_id,
            expected_asr_generation=expected_asr_generation,
            current_asr_generation=getattr(answer_session, 'last_asr_generation', 0),
            reason_detail='asr_generation_changed_before_schedule',
        )
        return

    _cancel_answer_finalize_timer(current)

    answer_session_id = answer_session.answer_session_id

    def finalize_task():
        live_runtime = session_registry.get(runtime.client_id)
        if not live_runtime or live_runtime.session_id != runtime.session_id or live_runtime.ended:
            return
        live_runtime.pending_answer_finalize_timer = None
        live_answer_session = live_runtime.current_answer_session
        if not live_answer_session or live_answer_session.answer_session_id != answer_session_id:
            return
        if getattr(live_runtime, 'active_asr_generation', 0) or getattr(live_runtime, 'active_client_speech_epoch', 0):
            _log_runtime_event(
                live_runtime,
                'answer_session_finalize_retry',
                level='debug',
                source=reason,
                answer_session_id=answer_session_id,
                active_asr_generation=getattr(live_runtime, 'active_asr_generation', 0) or '',
                active_client_speech_epoch=getattr(live_runtime, 'active_client_speech_epoch', 0) or '',
                reason_detail='speech_active',
            )
            retry_timer = threading.Timer(0.5, finalize_task)
            retry_timer.daemon = True
            live_runtime.pending_answer_finalize_timer = retry_timer
            retry_timer.start()
            return
        if expected_speech_epoch and getattr(live_answer_session, 'last_speech_epoch', 0) != expected_speech_epoch:
            _log_runtime_event(
                live_runtime,
                'answer_session_finalize_dropped',
                level='debug',
                source=reason,
                answer_session_id=answer_session_id,
                expected_speech_epoch=expected_speech_epoch,
                current_speech_epoch=getattr(live_answer_session, 'last_speech_epoch', 0),
                reason_detail='answer_session_epoch_changed',
            )
            return
        if expected_asr_generation and getattr(live_answer_session, 'last_asr_generation', 0) != expected_asr_generation:
            _log_runtime_event(
                live_runtime,
                'answer_session_finalize_dropped',
                level='debug',
                source=reason,
                answer_session_id=answer_session_id,
                expected_asr_generation=expected_asr_generation,
                current_asr_generation=getattr(live_answer_session, 'last_asr_generation', 0),
                reason_detail='answer_session_generation_changed',
            )
            return
        _finalize_answer_session(live_runtime, reason=reason)

    timer = threading.Timer(current.long_pause_threshold_seconds, finalize_task)
    timer.daemon = True
    current.pending_answer_finalize_timer = timer
    timer.start()
    _log_runtime_event(
        current,
        'answer_session_finalize_scheduled',
        source=reason,
        answer_session_id=answer_session.answer_session_id,
        speech_epoch=expected_speech_epoch or '',
        asr_generation=expected_asr_generation or '',
        after_seconds=current.long_pause_threshold_seconds,
    )


def _finalize_answer_segment(
    runtime,
    asr_generation: int,
    speech_epoch: int = 0,
    reason: str = "speech_end",
) -> str:
    current = session_registry.get(runtime.client_id)
    if not current or current.session_id != runtime.session_id or current.ended:
        return ""

    answer_session = current.current_answer_session
    if not answer_session or answer_session.turn_id != current.turn_id:
        return ""

    final_text, partial_text, merged_pending_text = _build_pending_asr_text(current)
    segment_text = _pick_segment_text(final_text, partial_text, merged_pending_text)
    current.pending_asr_partials.clear()
    current.pending_asr_finals.clear()
    if asr_generation and current.last_finalized_asr_generation == asr_generation:
        current.last_finalized_asr_generation = 0
        current.last_finalized_asr_speech_epoch = 0
    segment_added = False
    if segment_text:
        if _is_low_information_asr_segment(segment_text):
            _log_runtime_event(
                current,
                'answer_segment_ignored',
                level='debug',
                source=reason,
                answer_session_id=answer_session.answer_session_id,
                segment_preview=segment_text[:160],
                reason_detail='low_information_asr_segment',
            )
        else:
            answer_session.finalize_segment(segment_text)
            segment_added = True
    if segment_added and speech_epoch and speech_epoch >= getattr(answer_session, 'last_speech_epoch', 0):
        answer_session.last_speech_epoch = speech_epoch
    if segment_added and asr_generation and asr_generation >= getattr(answer_session, 'last_asr_generation', 0):
        answer_session.last_asr_generation = asr_generation

    answer_session.mark_status('paused_short')
    _emit_realtime_speech_metrics(
        current,
        answer_session,
        is_speaking=False,
        text_snapshot=answer_session.live_text or answer_session.merged_text_draft,
        source=reason,
    )
    _log_runtime_event(
        current,
        'answer_segment_finalized',
        source=reason,
        answer_session_id=answer_session.answer_session_id,
        segment_preview=segment_text[:160],
        segment_count=len(answer_session.segments),
    )
    _emit_answer_session_update(current, source=reason)
    return segment_text


def _generate_policy_response(
    user_answer: str,
    current_question: str,
    position: str,
    round_type: str,
    chat_history: list | None = None,
    difficulty: str = "medium",
    interview_state: dict | None = None,
    question_plan: dict | None = None,
    locked_question: str = "",
    training_mode: str = "",
) -> tuple[str, dict | None, dict | None, dict | None, dict | None]:
    """根据结构化分析和 FollowupPolicy 生成追问或切题结果。"""
    rag_context, analysis_result = _build_answer_rag_context(
        position=position,
        round_type=round_type,
        current_question=current_question,
        user_answer=user_answer,
        interview_state=interview_state,
        question_plan=question_plan
    )

    next_state = interview_state
    followup_decision = None
    question_id = _extract_question_id_from_plan(question_plan)

    if rag_service is not None and getattr(rag_service, 'enabled', False) and analysis_result:
        next_state = rag_service.update_interview_state_from_analysis(
            interview_state,
            analysis_result
        )
        followup_decision = rag_service.decide_followup(
            question_id=question_id,
            analysis_result=analysis_result,
            session_state=next_state
        )

    decision_context = ""
    if followup_decision and rag_service is not None and getattr(rag_service, 'enabled', False):
        decision_context = rag_service.format_followup_decision(followup_decision)

    normalized_training_mode = str(training_mode or '').strip().lower()
    fixed_question = str(locked_question or '').strip()
    if normalized_training_mode == 'coach_drill':
        coach_decision = dict(followup_decision or {})
        coach_state = next_state
        next_question_plan = question_plan
        coach_reference_question = fixed_question or current_question
        coach_decision_context = decision_context
        coach_question_context_parts = [rag_context, coach_decision_context]
        next_question_text = ""

        if fixed_question:
            coach_decision['next_action'] = 'ask_followup'
            coach_decision['forced_question_mode'] = True
            coach_decision['locked_question'] = fixed_question
            coach_question_context_parts.append(
                "【固定题目模式】请继续围绕这道题深入追问，优先补齐候选人刚才没有展开的关键点。"
            )
        elif (
            str(coach_decision.get('next_action', 'ask_followup')).strip() in {'switch_question', 'raise_difficulty'}
            and rag_service is not None
            and getattr(rag_service, 'enabled', False)
        ):
            target_difficulty = str(
                coach_decision.get('difficulty_target') or difficulty or 'medium'
            ).strip() or 'medium'
            planning_state = dict(next_state or {})
            planning_state['target_difficulty'] = target_difficulty
            next_question_plan = rag_service.get_next_question(
                planning_state,
                top_k=getattr(rag_service, 'max_context_results', 2)
            )
            next_question_context = rag_service.format_question_plan(next_question_plan)
            coach_reference_question = _extract_question_text_from_plan(next_question_plan)
            if coach_reference_question:
                next_question_text = llm_manager.generate_round_question(
                    round_type=round_type,
                    position=position,
                    difficulty=target_difficulty,
                    rag_context=_merge_text_blocks(coach_decision_context, next_question_context),
                    reference_question=coach_reference_question,
                )
            if next_question_text and next_question_plan:
                coach_state = rag_service.mark_question_asked(planning_state, next_question_plan)
                coach_question_context_parts.append(next_question_context)
            else:
                coach_decision = _downgrade_switch_decision(
                    coach_decision,
                    reason='coach_switch_generation_failed',
                )
                next_question_plan = question_plan
                coach_state = next_state
                coach_reference_question = current_question
                if rag_service is not None and getattr(rag_service, 'enabled', False):
                    coach_decision_context = rag_service.format_followup_decision(coach_decision)
                coach_question_context_parts = [rag_context, coach_decision_context]

        if not next_question_text:
            next_question_text = llm_manager.generate_round_question(
                round_type=round_type,
                position=position,
                difficulty=difficulty,
                context=(
                    f"上一题：{current_question}\n"
                    "请继续围绕刚才回答中还不够完整的部分，提出一个更聚焦、更具体的下一问。"
                ),
                rag_context=_merge_text_blocks(*coach_question_context_parts),
                reference_question=coach_reference_question,
            )

        coach_payload = llm_manager.generate_coach_followup(
            user_answer=user_answer,
            current_question=current_question,
            next_question=next_question_text or coach_reference_question,
            position=position,
            round_type=round_type,
            analysis_result=analysis_result,
            followup_decision=coach_decision,
            rag_context=_merge_text_blocks(*coach_question_context_parts),
        )
        coach_display_text = _format_coach_mode_reply(coach_payload)
        coach_spoken_text = str(coach_payload.get('spoken_summary') or '').strip()
        coach_next_question = str(
            coach_payload.get('next_question') or next_question_text or coach_reference_question
        ).strip()
        coach_decision.update({
            'coach_mode': True,
            'coach_display_text': coach_display_text,
            'coach_spoken_text': coach_spoken_text,
            'coach_next_question': coach_next_question,
            'coach_reference_outline': coach_payload.get('reference_outline') or [],
            'coach_improvement_tip': coach_payload.get('improvement_tip') or '',
        })
        coach_decision = _with_runtime_question(
            coach_decision,
            reply_text=coach_next_question or coach_display_text,
            fallback_question=coach_reference_question or current_question,
        )
        return coach_display_text or coach_next_question, analysis_result, coach_decision, coach_state, next_question_plan

    if fixed_question:
        fixed_decision = dict(followup_decision or {})
        fixed_decision['next_action'] = 'ask_followup'
        fixed_decision['forced_question_mode'] = True
        fixed_decision['locked_question'] = fixed_question
        fixed_context = (
            "【固定题目模式】本轮必须围绕以下题目继续追问，不得切换到新题：\n"
            f"{fixed_question}\n"
            "请先给出简短反馈，再提出一个更深入且紧扣该题的追问。"
        )
        feedback = llm_manager.process_answer_with_round(
            user_answer=user_answer,
            current_question=fixed_question,
            position=position,
            round_type=round_type,
            chat_history=chat_history,
            rag_context=_merge_text_blocks(rag_context, decision_context, fixed_context)
        )
        fixed_decision = _with_runtime_question(
            fixed_decision,
            reply_text=feedback,
            fallback_question=fixed_question,
        )
        return feedback, analysis_result, fixed_decision, next_state, question_plan

    next_action = str((followup_decision or {}).get('next_action', 'ask_followup')).strip()
    if (
        next_action in {'switch_question', 'raise_difficulty'}
        and rag_service is not None
        and getattr(rag_service, 'enabled', False)
    ):
        planning_state = dict(next_state or {})
        target_difficulty = str(
            (followup_decision or {}).get('difficulty_target') or difficulty or 'medium'
        ).strip() or 'medium'
        planning_state['target_difficulty'] = target_difficulty

        next_question_plan = rag_service.get_next_question(
            planning_state,
            top_k=getattr(rag_service, 'max_context_results', 2)
        )
        next_question_context = rag_service.format_question_plan(next_question_plan)
        reference_question = _extract_question_text_from_plan(next_question_plan)
        next_question = ""
        if reference_question:
            next_question = llm_manager.generate_round_question(
                round_type=round_type,
                position=position,
                difficulty=target_difficulty,
                rag_context=_merge_text_blocks(decision_context, next_question_context),
                reference_question=reference_question,
            )
        if next_question and next_question_plan:
            transition_text = llm_manager.generate_natural_transition(
                previous_question=current_question,
                user_answer=user_answer,
                next_question=next_question,
                transition_type=next_action,
                position=position,
                round_type=round_type,
                chat_history=chat_history,
            )
            final_state = planning_state
            final_state = rag_service.mark_question_asked(planning_state, next_question_plan)
            switched_decision = _with_runtime_question(
                followup_decision,
                reply_text=next_question,
                fallback_question=next_question,
            )
            return (
                transition_text,
                analysis_result,
                switched_decision,
                final_state,
                next_question_plan,
            )
        followup_decision = _downgrade_switch_decision(
            followup_decision,
            reason='switch_generation_failed',
        )
        if rag_service is not None and getattr(rag_service, 'enabled', False):
            decision_context = rag_service.format_followup_decision(followup_decision)
        next_action = str((followup_decision or {}).get('next_action', 'ask_followup')).strip()

    if next_action == 'ask_followup' and followup_decision:
        targeted_followup_question = str(followup_decision.get('followup_question') or '').strip()
        if targeted_followup_question:
            followup_style = str(followup_decision.get('followup_style') or 'detail_probe').strip() or 'detail_probe'
            followup_text = llm_manager.generate_targeted_followup_question(
                current_question=current_question,
                user_answer=user_answer,
                position=position,
                round_type=round_type,
                followup_style=followup_style,
                followup_hint=targeted_followup_question,
                rag_context=_merge_text_blocks(rag_context, decision_context),
            )
            followup_decision = _with_runtime_question(
                followup_decision,
                reply_text=followup_text,
                fallback_question=targeted_followup_question or current_question,
            )
            return followup_text, analysis_result, followup_decision, next_state, question_plan

    feedback = llm_manager.process_answer_with_round(
        user_answer=user_answer,
        current_question=current_question,
        position=position,
        round_type=round_type,
        chat_history=chat_history,
        rag_context=_merge_text_blocks(rag_context, decision_context)
    )
    followup_decision = _with_runtime_question(
        followup_decision,
        reply_text=feedback,
        fallback_question=current_question,
    )
    return feedback, analysis_result, followup_decision, next_state, question_plan


def _emit_pipeline_error(client_id: str, session_id: str, code: str, error: str, details: str = ""):
    logger.error(
        "[pipeline_error] client_id=%r session_id=%r code=%r error=%r details=%r",
        client_id,
        session_id,
        code,
        error,
        details,
    )
    socketio.emit('pipeline_error', {
        'session_id': session_id,
        'code': code,
        'error': error,
        'details': details,
        'timestamp': time.time()
    }, to=client_id)


def _emit_orchestrator_state(runtime):
    socketio.emit(
        'orchestrator_state',
        {
            **state_orchestrator.build_public_state(runtime),
            'timestamp': time.time()
        },
        to=runtime.client_id
    )


def _set_runtime_asr_status(runtime, available: bool, code: str = "", details: str = ""):
    runtime.asr_available = available
    runtime.asr_error_code = str(code or "").strip()
    runtime.asr_error = str(details or "").strip()


def _set_runtime_asr_lock(runtime, locked: bool, reason: str = ""):
    runtime.asr_locked = bool(locked)
    runtime.asr_lock_reason = str(reason or "").strip() if locked else ""


def _disable_runtime_asr(runtime, code: str, error: str, details: str = "", asr_generation: int | None = None):
    current = session_registry.get(runtime.client_id)
    if not current or current.session_id != runtime.session_id or current.ended:
        return

    if asr_generation is not None and current.active_asr_generation != asr_generation:
        return

    normalized_details = str(details or "").strip()
    if (
        not current.asr_available
        and current.asr_error_code == code
        and current.asr_error == normalized_details
    ):
        return

    if current.pending_commit_timer:
        current.pending_commit_timer.cancel()
        current.pending_commit_timer = None
    _cancel_answer_finalize_timer(current)
    current.pending_asr_partials.clear()
    current.pending_asr_finals.clear()
    _reset_pending_asr_audio(current)
    current.active_asr_generation = 0
    current.active_asr_speech_epoch = 0
    current.active_client_speech_epoch = 0
    current.finalizing_asr_generation = 0
    current.last_finalized_asr_generation = 0
    current.last_finalized_asr_speech_epoch = 0
    _set_runtime_asr_status(current, False, code, normalized_details or error)

    if asr_manager and current.active_asr_stream_id:
        try:
            asr_manager.stop_session(current.active_asr_stream_id)
        except Exception as stop_error:
            logger.warning(f"[ASR] 停止异常流失败: {stop_error}")

    _log_runtime_event(
        current,
        'asr_disabled',
        level='warning',
        asr_generation=asr_generation or '',
        code=code,
        details=(normalized_details or error)[:200],
    )
    _emit_orchestrator_state(current)
    _emit_pipeline_error(current.client_id, current.session_id, code, error, normalized_details)


def _get_runtime(client_id: str, expected_session_id: str = ""):
    runtime = session_registry.get(client_id)
    if not runtime:
        return None
    if expected_session_id and runtime.session_id != expected_session_id:
        return None
    return runtime


def _current_runtime_matches(
    client_id: str,
    session_id: str,
    job_id: str = "",
    interrupt_epoch: int | None = None,
    asr_generation: int | None = None,
    allow_finalizing_asr: bool = False,
    allow_finalized_asr: bool = False,
) -> bool:
    runtime = session_registry.get(client_id)
    if not runtime or runtime.session_id != session_id or runtime.ended:
        return False
    if interrupt_epoch is not None and runtime.interrupt_epoch != interrupt_epoch:
        return False
    if job_id and runtime.active_tts_job_id != job_id and runtime.active_llm_job_id != job_id:
        return False
    if asr_generation is not None:
        valid_generation = runtime.active_asr_generation == asr_generation
        if allow_finalizing_asr and runtime.finalizing_asr_generation == asr_generation:
            valid_generation = True
        if allow_finalized_asr and runtime.last_finalized_asr_generation == asr_generation:
            valid_generation = True
        if not valid_generation:
            return False
    return True


def _runtime_log_fields(runtime, **fields):
    payload = {
        'client_id': runtime.client_id,
        'session_id': runtime.session_id,
        'turn_id': runtime.turn_id,
        'mode': runtime.mode,
        'interrupt_epoch': runtime.interrupt_epoch,
    }
    payload.update({key: value for key, value in fields.items() if value not in (None, '')})
    return payload


def _emit_asr_debug_event(runtime, event: str, level: str = "info", **fields) -> None:
    if not ASR_DEBUG_STREAM_ENABLED:
        return
    if not runtime or not getattr(runtime, "client_id", ""):
        return

    payload = _runtime_log_fields(
        runtime,
        event=str(event or "").strip(),
        level=str(level or "info").strip() or "info",
        timestamp=time.time(),
        **fields,
    )

    clip_fields = {
        "details",
        "partial_preview",
        "final_preview",
        "segment_preview",
        "answer_preview",
        "text_snapshot",
        "question_preview",
    }
    for field in clip_fields:
        value = payload.get(field)
        if isinstance(value, str):
            normalized = " ".join(value.split())
            payload[field] = (normalized[:280] + "...") if len(normalized) > 280 else normalized

    try:
        socketio.emit("asr_debug", payload, to=runtime.client_id)
    except Exception as exc:
        logger.debug(f"[runtime] asr_debug emit failed: {exc}")


def _log_runtime_event(runtime, event: str, level: str = 'info', **fields):
    payload = _runtime_log_fields(runtime, event=event, **fields)
    log_fn = getattr(logger, level, logger.info)
    details = ' '.join(f"{key}={payload[key]!r}" for key in sorted(payload))
    log_fn(f"[runtime] {details}")

    normalized_event = str(event or "").strip().lower()
    should_emit_debug = (
        normalized_event.startswith("asr_")
        or normalized_event.startswith("speech_")
        or normalized_event.startswith("answer_session_")
        or normalized_event in {
            "utterance_commit_request",
            "commit_scheduled",
            "commit_dropped",
            "commit_ignored",
            "commit_accepted",
        }
    )
    if should_emit_debug:
        _emit_asr_debug_event(runtime, normalized_event, level=level, **fields)


def _print_asr_console(runtime, phase: str, text: str, asr_generation: int):
    content = str(text or '').strip()
    if not content:
        return
    print(
        f"[ASR_CONSOLE] phase={phase} session_id={runtime.session_id} "
        f"turn_id={runtime.turn_id} stream_id={runtime.active_asr_stream_id} "
        f"gen={asr_generation} text={content}",
        flush=True,
    )


def _estimate_spoken_duration_ms(text: str) -> float:
    content = str(text or '').strip()
    if not content:
        return 1200.0
    token_count = len([ch for ch in content if ch.strip()])
    return max(1200.0, float(token_count) * 260.0)


def _track_question_timeline(runtime, turn_id: str, question_text: str) -> None:
    if not runtime or not runtime.started_at:
        return
    now = time.time()
    runtime.current_question_started_at = now
    runtime.current_question_estimated_end_at = now + (_estimate_spoken_duration_ms(question_text) / 1000.0)
    runtime.current_answer_started_at = None

    if not hasattr(db_manager, 'save_or_update_turn_timeline'):
        return
    question_start_ms = max(0.0, (runtime.current_question_started_at - runtime.started_at) * 1000.0)
    question_end_ms = max(question_start_ms, (runtime.current_question_estimated_end_at - runtime.started_at) * 1000.0)
    db_manager.save_or_update_turn_timeline({
        'interview_id': runtime.interview_id,
        'turn_id': str(turn_id or runtime.turn_id or '').strip(),
        'question_start_ms': round(question_start_ms, 2),
        'question_end_ms': round(question_end_ms, 2),
        'source': 'runtime',
    })


def _track_answer_timeline(runtime, turn_id: str) -> None:
    if not runtime or not runtime.started_at or not hasattr(db_manager, 'save_or_update_turn_timeline'):
        return
    now = time.time()
    answer_start_at = runtime.current_answer_started_at or now
    answer_end_at = now
    question_end_at = runtime.current_question_estimated_end_at or runtime.current_question_started_at or answer_start_at
    latency_ms = max(0.0, (answer_start_at - question_end_at) * 1000.0)
    db_manager.save_or_update_turn_timeline({
        'interview_id': runtime.interview_id,
        'turn_id': str(turn_id or runtime.turn_id or '').strip(),
        'answer_start_ms': round(max(0.0, (answer_start_at - runtime.started_at) * 1000.0), 2),
        'answer_end_ms': round(max(0.0, (answer_end_at - runtime.started_at) * 1000.0), 2),
        'latency_ms': round(latency_ms, 2),
        'source': 'runtime',
    })


def _timestamp_to_epoch_seconds(raw_timestamp, runtime) -> float:
    try:
        value = float(raw_timestamp or 0.0)
    except Exception:
        value = 0.0
    if value > 1_000_000_000_000:
        return value / 1000.0
    if value > 1_000_000_000:
        return value
    if runtime and runtime.started_at:
        if value > 10_000:
            return float(runtime.started_at) + value / 1000.0
        if value > 0:
            return float(runtime.started_at) + value
    return value or time.time()


def _build_turn_detection_state(runtime, turn_id: str) -> dict:
    fallback = dict(getattr(runtime, 'pending_detection_state', {}) or {})
    timeline = []
    if runtime and runtime.data_manager:
        timeline = list((runtime.data_manager.get_interview_data() or {}).get('timeline') or [])

    answer_end_at = time.time()
    answer_start_at = (
        getattr(runtime, 'current_answer_started_at', None)
        or getattr(runtime, 'current_question_estimated_end_at', None)
        or getattr(runtime, 'current_question_started_at', None)
        or 0.0
    )
    detection_rows = []
    for item in timeline:
        if not isinstance(item, dict) or str(item.get('type') or '').strip() != 'detection_state':
            continue
        ts_epoch = _timestamp_to_epoch_seconds(item.get('timestamp'), runtime)
        if answer_start_at and (ts_epoch < float(answer_start_at) - 0.5 or ts_epoch > answer_end_at + 0.5):
            continue
        detection_rows.append(item)

    if not detection_rows:
        recent_rows = [
            item for item in timeline
            if isinstance(item, dict) and str(item.get('type') or '').strip() == 'detection_state'
        ][-40:]
        detection_rows = recent_rows

    if not detection_rows:
        return fallback

    def _norm_percent(value):
        parsed = _safe_float(value, 0.0)
        return parsed * 100.0 if parsed <= 1.0 else parsed

    risk_values = [_norm_percent(item.get('risk_score', item.get('probability', 0.0))) for item in detection_rows]
    offscreen_values = [_norm_percent(item.get('off_screen_ratio', 0.0)) for item in detection_rows]
    face_counts = [_safe_int(item.get('face_count'), 1) for item in detection_rows]
    hr_values = [
        _safe_float(item.get('hr'), None)
        for item in detection_rows
        if _safe_float(item.get('hr'), None) is not None
    ]
    flags = sorted({
        str(flag).strip()
        for item in detection_rows
        for flag in (item.get('flags') or [])
        if str(flag).strip()
    })
    latest = dict(detection_rows[-1] or {})
    latest_insights = latest.get('camera_insights') if isinstance(latest.get('camera_insights'), dict) else {}
    return {
        **fallback,
        'turn_id': str(turn_id or getattr(runtime, 'turn_id', '') or '').strip(),
        'sample_count': len(detection_rows),
        'risk_score': round(max(risk_values + [0.0]), 2),
        'risk_score_avg': round(_safe_avg(risk_values), 2) if risk_values else 0.0,
        'off_screen_ratio': round(_safe_avg(offscreen_values), 2) if offscreen_values else 0.0,
        'off_screen_ratio_max': round(max(offscreen_values + [0.0]), 2),
        'has_face': all(bool(item.get('has_face', True)) for item in detection_rows),
        'face_count': max(face_counts + [1]),
        'flags': flags,
        'hr': round(_safe_avg(hr_values), 2) if hr_values else latest.get('hr'),
        'rppg_reliable': any(bool(item.get('rppg_reliable', False)) for item in detection_rows),
        'camera_insights': latest_insights,
        'video_features': latest.get('video_features') if isinstance(latest.get('video_features'), dict) else {},
    }


def _maybe_enqueue_replay_generation(interview_id: str, force: bool = False) -> None:
    normalized_id = str(interview_id or '').strip()
    if not normalized_id:
        return
    try:
        replay_task_manager.enqueue(normalized_id, force=force)
    except Exception as exc:
        logger.warning(f"投递复盘任务失败：{exc}")


def _maybe_enqueue_behavior_analysis(interview_id: str, force: bool = False) -> None:
    normalized_id = str(interview_id or '').strip()
    if not normalized_id:
        return
    if not bool(config.get('replay.behavior.auto_trigger', True)):
        return
    try:
        behavior_task_manager.enqueue(normalized_id, force=force)
    except Exception as exc:
        logger.warning(f"投递行为分析任务失败：{exc}")


def _derive_detection_events_and_stats(report_data: dict) -> tuple[list[dict], dict]:
    timeline = (report_data or {}).get('timeline') or []
    events: list[dict] = []
    total_deviations = 0
    total_mouth_open = 0
    total_multi_person = 0
    offscreen_values: list[float] = []
    hr_values: list[float] = []
    rppg_reliable_frames = 0
    rppg_frames = 0

    for item in timeline:
        if not isinstance(item, dict):
            continue
        if str(item.get('type') or '').strip() != 'detection_state':
            continue
        timestamp = float(item.get('timestamp') or 0.0)
        risk_score = float(item.get('probability') or item.get('risk_score') or 0.0)
        score = int(max(0.0, min(100.0, risk_score * 100.0 if risk_score <= 1.0 else risk_score)))
        has_face = bool(item.get('has_face', True))
        face_count = int(item.get('face_count', 1) or 1)
        raw_off_screen_ratio = float(item.get('off_screen_ratio') or 0.0)
        off_screen_ratio = raw_off_screen_ratio * 100.0 if raw_off_screen_ratio <= 1.0 else raw_off_screen_ratio
        flags = [str(flag).strip().lower() for flag in (item.get('flags') or []) if str(flag).strip()]
        camera_insights = item.get('camera_insights') if isinstance(item.get('camera_insights'), dict) else {}
        blendshapes = camera_insights.get('blendshapes') if isinstance(camera_insights.get('blendshapes'), dict) else {}
        head_pose = camera_insights.get('head_pose') if isinstance(camera_insights.get('head_pose'), dict) else {}
        try:
            hr_raw = item.get('hr')
            hr_value = float(hr_raw) if hr_raw is not None else None
        except Exception:
            hr_value = None
        rppg_reliable = bool(item.get('rppg_reliable', False))

        jaw_open_avg = float(blendshapes.get('jaw_open_avg') or 0.0)
        mouth_status = str(item.get('mouth_status') or '').strip().lower()
        abs_pitch = abs(float(head_pose.get('pitch') or item.get('pitch') or 0.0))
        abs_yaw = abs(float(head_pose.get('yaw') or item.get('yaw') or 0.0))
        abs_roll = abs(float(head_pose.get('roll') or item.get('roll') or 0.0))
        pose_unstable = abs_yaw >= 28.0 or abs_pitch >= 20.0 or abs_roll >= 20.0 or ('pose_unstable' in flags)
        offscreen_values.append(off_screen_ratio)
        if isinstance(hr_value, (int, float)):
            hr_values.append(float(hr_value))
            rppg_frames += 1
            if rppg_reliable:
                rppg_reliable_frames += 1

        if face_count > 1 or 'multi_person' in flags:
            total_multi_person += 1
            events.append({
                'type': 'multi_person',
                'timestamp': timestamp,
                'score': score,
                'description': '检测到多张人脸或环境人员波动',
                'face_count': face_count,
                'flags': flags,
                'off_screen_ratio': off_screen_ratio,
            })

        if (jaw_open_avg >= 0.2 and mouth_status == 'open') or ('mouth_open' in flags):
            total_mouth_open += 1
            events.append({
                'type': 'mouth_open',
                'timestamp': timestamp,
                'score': score,
                'description': '检测到明显口型张开行为',
                'jaw_open_avg': jaw_open_avg,
                'mouth_status': mouth_status,
                'flags': flags,
            })

        if pose_unstable:
            events.append({
                'type': 'posture_shift',
                'timestamp': timestamp,
                'score': score,
                'description': '头部姿态偏移较大，存在频繁转头/低头迹象',
                'pitch': abs_pitch,
                'yaw': abs_yaw,
                'roll': abs_roll,
                'flags': flags,
            })

        if (not has_face) or off_screen_ratio >= 30.0 or ('no_face_long' in flags):
            total_deviations += 1
            events.append({
                'type': 'gaze_deviation',
                'timestamp': timestamp,
                'score': score,
                'description': '出现离屏/离镜头行为',
                'has_face': has_face,
                'face_count': face_count,
                'flags': flags,
                'off_screen_ratio': off_screen_ratio,
                'gaze_drift_count': int(item.get('gaze_drift_count') or 0),
            })

    avg_off_screen_ratio = (sum(offscreen_values) / len(offscreen_values)) if offscreen_values else 0.0
    avg_heart_rate = (sum(hr_values) / len(hr_values)) if hr_values else None
    rppg_reliable_ratio = ((rppg_reliable_frames / rppg_frames) * 100.0) if rppg_frames else None
    stats = {
        'total_deviations': int(total_deviations),
        'total_mouth_open': int(total_mouth_open),
        'total_multi_person': int(total_multi_person),
        'off_screen_ratio': round(avg_off_screen_ratio, 4),
        'frames_processed': int((report_data or {}).get('summary', {}).get('frames_processed', 0) or len(timeline)),
        'avg_heart_rate': round(avg_heart_rate, 2) if isinstance(avg_heart_rate, (int, float)) else None,
        'rppg_reliable_ratio': round(rppg_reliable_ratio, 2) if isinstance(rppg_reliable_ratio, (int, float)) else None,
        'heart_rate_samples': int(len(hr_values)),
    }
    return events, stats


def _normalize_risk_probability(value) -> float:
    try:
        risk = float(value or 0.0)
    except Exception:
        risk = 0.0
    if risk <= 1.0:
        risk *= 100.0
    return round(max(0.0, min(100.0, risk)), 2)


def _risk_level_from_probability(value: float) -> str:
    risk = _normalize_risk_probability(value)
    if risk >= 75.0:
        return 'HIGH'
    if risk >= 40.0:
        return 'MEDIUM'
    return 'LOW'


def _interrupt_runtime(runtime, reason: str):
    payload = state_orchestrator.start_speech(runtime)
    _log_runtime_event(runtime, 'interrupt', reason=reason, interrupted_job_id=payload.get('job_id', ''))
    if payload:
        socketio.emit('tts_stop', {
            **payload,
            'reason': reason,
            'timestamp': time.time()
        }, to=runtime.client_id)
    _emit_orchestrator_state(runtime)


def _record_runtime_dialogue(
    runtime,
    question: str,
    answer: str,
    feedback: str,
    analysis_result=None,
    followup_decision=None,
    turn_id: str = "",
    question_id: str = "",
):
    normalized_turn_id = str(turn_id or runtime.turn_id or '').strip() or f"turn_{runtime.turn_index}"
    resolved_question_id = _resolve_evaluation_question_id(runtime, question, question_id)
    if runtime.data_manager:
        runtime.data_manager.add_frame_data({
            'type': 'interview_dialogue',
            'question': question,
            'user_answer': answer,
            'llm_feedback': feedback,
            'rag_analysis': analysis_result,
            'followup_decision': followup_decision,
            'timestamp': time.time()
        })

    db_manager.save_interview_dialogue({
        'interview_id': runtime.interview_id,
        'turn_id': normalized_turn_id,
        'round_type': runtime.round_type,
        'question': question,
        'answer': answer,
        'llm_feedback': feedback
    })

    answer_session = runtime.current_answer_session
    if answer_session and hasattr(db_manager, 'save_or_update_speech_evaluation'):
        try:
            db_manager.save_or_update_speech_evaluation({
                'interview_id': runtime.interview_id,
                'turn_id': normalized_turn_id,
                'answer_session_id': answer_session.answer_session_id,
                'round_type': runtime.round_type,
                'final_transcript': answer_session.final_transcript or answer_session.final_text or answer,
                'word_timestamps_json': json.dumps(answer_session.word_timestamps or [], ensure_ascii=False),
                'pause_events_json': json.dumps(answer_session.pause_events or [], ensure_ascii=False),
                'filler_events_json': json.dumps(answer_session.filler_events or [], ensure_ascii=False),
                'speech_metrics_final_json': json.dumps(answer_session.speech_metrics_final or {}, ensure_ascii=False),
                'realtime_metrics_json': json.dumps(answer_session.realtime_speech_metrics or {}, ensure_ascii=False),
            })
        except Exception as exc:
            logger.warning(f"保存语音表达评估失败：{exc}")

    _track_answer_timeline(runtime, normalized_turn_id)

    if evaluation_service is not None:
        try:
            enqueue_result = evaluation_service.enqueue_evaluation(
                interview_id=runtime.interview_id,
                turn_id=normalized_turn_id,
                question_id=resolved_question_id,
                user_id=runtime.user_id,
                round_type=runtime.round_type,
                position=runtime.position,
                question=question,
                answer=answer,
                detection_state=_build_turn_detection_state(runtime, normalized_turn_id),
            )
            if not enqueue_result.get('success'):
                _log_runtime_event(
                    runtime,
                    'evaluation_enqueue_failed',
                    level='warning',
                    error=enqueue_result.get('error', ''),
                    message=enqueue_result.get('message', ''),
                )
        except Exception as e:
            logger.warning(f"投递三层评估任务失败：{e}")


def _normalize_question_for_match(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").strip().lower().replace("？", "?"))


def _resolve_evaluation_question_id(runtime, question: str, explicit_question_id: str = "") -> str:
    question_id = str(explicit_question_id or "").strip() or _extract_question_id_from_plan(runtime.last_question_plan)
    if not question_id:
        return ""

    planned_question = _extract_question_text_from_plan(runtime.last_question_plan)
    forced_question = str(getattr(runtime, 'forced_question_text', '') or '').strip()
    current = _normalize_question_for_match(question)
    candidates = [
        _normalize_question_for_match(planned_question),
        _normalize_question_for_match(forced_question),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if current == candidate or current in candidate or candidate in current:
            return question_id

    # 普通追问或教练生成问题不强制沿用上一道主问题 ID，让 RAG 按当前题面检索 rubric。
    return ""


def _format_coach_mode_reply(coach_payload: dict) -> str:
    """将教练式反馈组织成稳定可读的文本结构。"""
    if not isinstance(coach_payload, dict):
        return ""

    summary_feedback = str(coach_payload.get('summary_feedback') or '').strip()
    improvement_tip = str(coach_payload.get('improvement_tip') or '').strip()
    next_question = str(coach_payload.get('next_question') or '').strip()
    reference_outline = [
        str(item).strip()
        for item in (coach_payload.get('reference_outline') or [])
        if str(item).strip()
    ][:5]

    sections = []
    if summary_feedback:
        sections.append(f"本轮点评\n{summary_feedback}")
    if improvement_tip:
        sections.append(f"优先改进\n{improvement_tip}")
    if reference_outline:
        outline_text = "\n".join(
            f"{index}. {item}"
            for index, item in enumerate(reference_outline, start=1)
        )
        sections.append(f"参考回答骨架\n{outline_text}")
    if next_question:
        sections.append(f"下一问\n{next_question}")
    return "\n\n".join(section for section in sections if section.strip())


AUTO_END_MIN_QUESTIONS = 3
AUTO_END_MAX_QUESTIONS = 8
AUTO_END_RECENT_WINDOW = 2
AUTO_END_HIGH_SCORE = 85.0
AUTO_END_LOW_SCORE = 45.0
AUTO_END_SCORE_WAIT_SECONDS = 3.0
AUTO_END_SCORE_POLL_SECONDS = 0.2

EVALUATION_STATUS_PRIORITY = {
    'ok': 5,
    'partial_ok': 4,
    'running': 3,
    'pending': 2,
    'queued': 1,
    'skipped': 0,
    'failed': 0,
    'unknown': 0,
}

FINAL_SCORE_DIRECT_FUSION_WEIGHT = 0.35
FINAL_SCORE_STABLE_WEIGHT = 0.65


def _extract_turn_sequence(turn_id: str) -> int:
    normalized_turn_id = str(turn_id or '').strip()
    match = re.match(r'^turn_(\d+)', normalized_turn_id)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except Exception:
        return 0


def _extract_fusion_score_from_evaluation(row) -> float | None:
    if not isinstance(row, dict):
        return None
    fusion = row.get('fusion') if isinstance(row.get('fusion'), dict) else {}
    layer2 = row.get('layer2') if isinstance(row.get('layer2'), dict) else {}
    candidates = (
        fusion.get('overall_score'),
        row.get('overall_score'),
        layer2.get('overall_score_final'),
        layer2.get('overall_score'),
    )
    for candidate in candidates:
        if isinstance(candidate, (int, float)):
            return round(float(candidate), 2)
        try:
            if candidate is not None and str(candidate).strip() != '':
                return round(float(candidate), 2)
        except Exception:
            continue
    return None


def _evaluation_row_priority(row) -> tuple[int, int, int, int]:
    status = str((row or {}).get('status') or '').strip().lower()
    has_score = _extract_fusion_score_from_evaluation(row) is not None
    return (
        int(EVALUATION_STATUS_PRIORITY.get(status or 'unknown', 0)),
        int(has_score),
        _evaluation_row_updated_epoch(row),
        _safe_int((row or {}).get('id'), 0),
    )



def _evaluation_row_updated_epoch(row) -> int:
    value = str((row or {}).get('updated_at') or (row or {}).get('created_at') or '').strip()
    if not value:
        return 0
    normalized = value.replace('T', ' ').replace('Z', '').split('.')[0]
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return int(datetime.strptime(normalized[:19] if fmt.endswith('%S') else normalized[:10], fmt).timestamp())
        except Exception:
            continue
    try:
        return int(datetime.fromisoformat(normalized).timestamp())
    except Exception:
        return 0


def _dedupe_evaluation_rows_by_turn(rows):
    """同一 turn 只保留最可信且最新的一条评估记录。"""
    deduped = {}
    for index, row in enumerate(rows or []):
        turn_id = str((row or {}).get('turn_id') or '').strip()
        dedupe_key = turn_id or str((row or {}).get('eval_task_key') or f'row_{index}')
        existing = deduped.get(dedupe_key)
        if existing is None or _evaluation_row_priority(row) > _evaluation_row_priority(existing):
            deduped[dedupe_key] = row
    return list(deduped.values())


def _collect_scored_turns(interview_id: str):
    if not interview_id or not hasattr(db_manager, 'get_interview_evaluations'):
        return []

    raw_rows = db_manager.get_interview_evaluations(interview_id=interview_id) or []
    decoded_rows = _decode_evaluation_rows(raw_rows)
    best_rows_by_turn = {}
    for row in decoded_rows:
        turn_id = str((row or {}).get('turn_id') or '').strip()
        if not turn_id:
            continue
        existing = best_rows_by_turn.get(turn_id)
        if existing is None or _evaluation_row_priority(row) >= _evaluation_row_priority(existing):
            best_rows_by_turn[turn_id] = row

    scored_turns = []
    for turn_id, row in best_rows_by_turn.items():
        fusion_score = _extract_fusion_score_from_evaluation(row)
        if fusion_score is None:
            continue
        scored_turns.append({
            'turn_id': turn_id,
            'turn_sequence': _extract_turn_sequence(turn_id),
            'fusion_score': fusion_score,
            'status': str((row or {}).get('status') or '').strip().lower(),
        })

    scored_turns.sort(key=lambda item: (int(item.get('turn_sequence') or 0), str(item.get('turn_id') or '')))
    return scored_turns


def _wait_for_turn_fusion_score(
    interview_id: str,
    turn_id: str,
    timeout_seconds: float = AUTO_END_SCORE_WAIT_SECONDS,
    poll_interval: float = AUTO_END_SCORE_POLL_SECONDS,
) -> float | None:
    normalized_interview_id = str(interview_id or '').strip()
    normalized_turn_id = str(turn_id or '').strip()
    if not normalized_interview_id or not normalized_turn_id or not hasattr(db_manager, 'get_turn_scorecard'):
        return None

    deadline = time.time() + max(float(timeout_seconds or 0.0), 0.0)
    while time.time() <= deadline:
        raw_scorecard = db_manager.get_turn_scorecard(normalized_interview_id, normalized_turn_id) or {}
        scorecard = _normalize_turn_scorecard(raw_scorecard)
        evaluation = scorecard.get('evaluation') if isinstance(scorecard.get('evaluation'), dict) else {}
        fusion_score = _extract_fusion_score_from_evaluation(evaluation)
        if fusion_score is not None:
            return fusion_score
        time.sleep(max(float(poll_interval or 0.0), 0.05))
    return None


def _should_auto_end_interview(runtime, current_turn_id: str):
    interaction_question_count = int(getattr(runtime, 'formal_question_count', 0) or 0)
    topic_question_count = int(getattr(runtime, 'topic_question_count', 0) or 0)
    if topic_question_count <= 0:
        topic_question_count = interaction_question_count
    question_count = topic_question_count
    current_turn_sequence = _extract_turn_sequence(current_turn_id)
    min_questions = _parse_auto_end_question_limit(
        getattr(runtime, 'auto_end_min_questions', AUTO_END_MIN_QUESTIONS),
        AUTO_END_MIN_QUESTIONS,
    )
    max_questions = _parse_auto_end_question_limit(
        getattr(runtime, 'auto_end_max_questions', AUTO_END_MAX_QUESTIONS),
        AUTO_END_MAX_QUESTIONS,
    )
    if max_questions < min_questions:
        max_questions = min_questions

    decision = {
        'question_count': question_count,
        'topic_question_count': topic_question_count,
        'interaction_question_count': interaction_question_count,
        'recent_scores': [],
        'recent_average': None,
        'reason': '',
        'current_turn_score': None,
        'min_questions': min_questions,
        'max_questions': max_questions,
    }

    if question_count < min_questions:
        decision['reason'] = 'below_min_questions'
        return False, decision

    if question_count >= max_questions:
        decision['reason'] = 'max_questions_reached'
        return True, decision

    current_turn_score = _wait_for_turn_fusion_score(runtime.interview_id, current_turn_id)
    if current_turn_score is not None:
        decision['current_turn_score'] = current_turn_score

    scored_turns = _collect_scored_turns(runtime.interview_id)
    latest_scored_turn_sequence = int(scored_turns[-1].get('turn_sequence') or 0) if scored_turns else 0
    if current_turn_sequence > 0 and latest_scored_turn_sequence < current_turn_sequence:
        decision['reason'] = 'current_turn_score_pending'
        return False, decision

    recent_scores = [
        float(item.get('fusion_score'))
        for item in scored_turns[-AUTO_END_RECENT_WINDOW:]
        if isinstance(item.get('fusion_score'), (int, float))
    ]
    decision['recent_scores'] = recent_scores

    if len(recent_scores) < AUTO_END_RECENT_WINDOW:
        decision['reason'] = 'insufficient_scored_turns'
        return False, decision

    recent_average = round(sum(recent_scores) / len(recent_scores), 2)
    decision['recent_average'] = recent_average
    if recent_average >= AUTO_END_HIGH_SCORE:
        decision['reason'] = 'high_score_threshold_reached'
        return True, decision
    if recent_average <= AUTO_END_LOW_SCORE:
        decision['reason'] = 'low_score_threshold_reached'
        return True, decision

    decision['reason'] = 'continue_interview'
    return False, decision


def _maybe_emit_session_notice(runtime):
    if runtime.mode != 'listening':
        return
    if runtime.active_tts_job_id or runtime.active_llm_job_id:
        return
    if not runtime.notice_queue:
        return

    notice_text = runtime.notice_queue.pop(0)
    normalized = speech_normalizer.normalize(notice_text)
    answer_session = getattr(runtime, 'current_answer_session', None)
    answer_status = str(getattr(answer_session, 'status', '') or '').strip()
    answer_text_in_progress = bool(
        str(getattr(answer_session, 'live_text', '') or '').strip()
        or str(getattr(answer_session, 'merged_text_draft', '') or '').strip()
        or str(getattr(answer_session, 'current_partial', '') or '').strip()
    )
    answer_in_progress = bool(
        runtime.active_asr_generation
        or runtime.finalizing_asr_generation
        or (
            answer_session
            and not getattr(answer_session, 'committed', False)
            and (answer_status in {'recording', 'paused_short', 'finalizing'} or answer_text_in_progress)
        )
    )
    spoken_text = '' if answer_in_progress else normalized['spoken_text']
    _log_runtime_event(
        runtime,
        'session_notice',
        source='detection_state',
        display_text=normalized['display_text'][:120],
        spoken_text=spoken_text[:120],
        notice_audio_suppressed=answer_in_progress,
    )
    socketio.emit('session_control_notice', {
        'session_id': runtime.session_id,
        'turn_id': runtime.turn_id,
        'job_id': '',
        'display_text': normalized['display_text'],
        'spoken_text': '',
        'speak_now': False,
        'interrupt_epoch': runtime.interrupt_epoch,
        'timestamp': time.time()
    }, to=runtime.client_id)


def _start_runtime_tts(runtime, spoken_text: str, turn_id: str, source: str = 'reply'):
    text = str(spoken_text or '').strip()
    if not text:
        state_orchestrator.begin_listening(runtime)
        _emit_orchestrator_state(runtime)
        _maybe_emit_session_notice(runtime)
        return

    if not tts_manager or not getattr(tts_manager, 'enabled', False):
        state_orchestrator.begin_listening(runtime)
        _emit_orchestrator_state(runtime)
        return

    sentences = speech_normalizer.split_for_tts(text)
    if not sentences:
        state_orchestrator.begin_listening(runtime)
        _emit_orchestrator_state(runtime)
        return

    tts_job_id = runtime.new_job('tts')
    interrupt_epoch = runtime.interrupt_epoch
    state_orchestrator.begin_speaking(runtime, tts_job_id)
    _log_runtime_event(
        runtime,
        'tts_start',
        job_id=tts_job_id,
        source=source,
        sentence_count=len(sentences),
        spoken_preview=text[:160],
    )
    _emit_orchestrator_state(runtime)

    def tts_task():
        try:
            for index, sentence in enumerate(sentences):
                current = session_registry.get(runtime.client_id)
                if not current or current.session_id != runtime.session_id:
                    return
                if current.active_tts_job_id != tts_job_id or current.interrupt_epoch != interrupt_epoch:
                    return

                emitted = {'ok': False}

                def send_audio_chunk(audio_data, text_chunk=sentence, chunk_index=index):
                    if not _current_runtime_matches(runtime.client_id, runtime.session_id, tts_job_id, interrupt_epoch):
                        return
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    emitted['ok'] = True
                    _log_runtime_event(
                        runtime,
                        'tts_chunk',
                        level='debug',
                        job_id=tts_job_id,
                        chunk_index=chunk_index,
                        source=source,
                        chunk_preview=str(text_chunk)[:120],
                    )
                    socketio.emit('tts_chunk', {
                        'session_id': runtime.session_id,
                        'turn_id': turn_id,
                        'job_id': tts_job_id,
                        'chunk_index': chunk_index,
                        'text': text_chunk,
                        'audio': audio_base64,
                        'mime_type': getattr(tts_manager, 'last_content_type', 'audio/mpeg'),
                        'provider': getattr(tts_manager, 'last_provider', ''),
                        'interrupt_epoch': interrupt_epoch,
                        'source': source,
                        'timestamp': time.time()
                    }, to=runtime.client_id)

                ok = tts_manager.synthesize(
                    sentence,
                    callback=send_audio_chunk,
                    interview_id=runtime.interview_id,
                    session_id=runtime.session_id,
                )
                if not _current_runtime_matches(runtime.client_id, runtime.session_id, tts_job_id, interrupt_epoch):
                    return
                if not ok or not emitted['ok']:
                    _emit_pipeline_error(
                        runtime.client_id,
                        runtime.session_id,
                        'TTS_SYNTH_FAIL',
                        'TTS synthesis failed',
                        getattr(tts_manager, 'last_error', '') or 'unknown tts error'
                    )
                    break
        except Exception as e:
            logger.error(f"[TTS] 新会话链路异常：{e}", exc_info=True)
            _emit_pipeline_error(runtime.client_id, runtime.session_id, 'TTS_EXCEPTION', 'TTS synthesis exception', str(e))
        finally:
            current = session_registry.get(runtime.client_id)
            if current and current.session_id == runtime.session_id:
                if state_orchestrator.finish_speaking(current, tts_job_id):
                    _log_runtime_event(current, 'tts_finish', job_id=tts_job_id, source=source)
                    socketio.emit('tts_done', {
                        'session_id': current.session_id,
                        'turn_id': turn_id,
                        'job_id': tts_job_id,
                        'interrupt_epoch': interrupt_epoch,
                        'source': source,
                        'timestamp': time.time(),
                    }, to=current.client_id)
                    _emit_orchestrator_state(current)
                    _maybe_emit_session_notice(current)

    threading.Thread(target=tts_task, daemon=True).start()


def _start_runtime_asr(runtime, reason: str = "speech_start") -> bool:
    if asr_manager is None:
        _disable_runtime_asr(runtime, 'ASR_NOT_READY', 'ASR is not initialized on server', asr_import_error or '')
        return False

    stream_id = runtime.active_asr_stream_id or runtime.session_id
    runtime.active_asr_stream_id = stream_id
    with runtime.asr_start_lock:
        current = session_registry.get(runtime.client_id)
        if not current or current.session_id != runtime.session_id or current.ended:
            return False

        if current.active_asr_generation:
            _log_runtime_event(
                current,
                'asr_start_skip',
                stream_id=stream_id,
                asr_generation=current.active_asr_generation,
                reason='already_running_or_starting',
            )
            return True

        current.asr_generation_counter += 1
        asr_generation = current.asr_generation_counter
        current.active_asr_generation = asr_generation
        current.active_asr_speech_epoch = current.speech_epoch
        current.finalizing_asr_generation = 0
        current.last_finalized_asr_generation = 0
        current.last_finalized_asr_speech_epoch = 0

        def on_partial(text: str):
            if not _current_runtime_matches(
                runtime.client_id,
                runtime.session_id,
                asr_generation=asr_generation,
            ):
                return
            live_runtime = session_registry.get(runtime.client_id)
            if not live_runtime:
                return
            if live_runtime.asr_locked:
                _log_runtime_event(
                    live_runtime,
                    'asr_partial_dropped',
                    level='debug',
                    stream_id=live_runtime.active_asr_stream_id,
                    asr_generation=asr_generation,
                    reason='asr_locked',
                    lock_reason=live_runtime.asr_lock_reason,
                )
                return
            partial_text = stabilize_realtime_asr_text(text)
            if not partial_text:
                return
            previous_partial = _merge_asr_fragments(live_runtime.pending_asr_partials)
            previous_final = _merge_asr_fragments(live_runtime.pending_asr_finals)
            # partial 只保留最新快照，避免 revision 抖动导致重复累积。
            live_runtime.pending_asr_partials = [partial_text]
            _final_text, _partial_text, new_segment_preview = _build_pending_asr_text(live_runtime)
            answer_session = _ensure_answer_session(live_runtime)
            answer_session.mark_status('recording')
            answer_session.update_partial(new_segment_preview)
            _emit_realtime_speech_metrics(
                live_runtime,
                answer_session,
                is_speaking=True,
                text_snapshot=new_segment_preview or partial_text,
                source='asr_partial',
            )
            _print_asr_console(live_runtime, 'partial', partial_text, asr_generation)
            _log_runtime_event(
                live_runtime,
                'asr_partial',
                level='debug',
                stream_id=live_runtime.active_asr_stream_id,
                asr_generation=asr_generation,
                partial_preview=partial_text[:120],
            )
            _log_runtime_event(
                live_runtime,
                'asr_partial_trace',
                level='info',
                stream_id=live_runtime.active_asr_stream_id,
                asr_generation=asr_generation,
                details=(
                    f"prev_partial_units={_count_text_units(previous_partial)} "
                    f"prev_final_units={_count_text_units(previous_final)} "
                    f"incoming_units={_count_text_units(partial_text)} "
                    f"preview_units={_count_text_units(new_segment_preview)}"
                ),
                partial_preview=partial_text[:160],
                final_preview=previous_final[:160],
                text_snapshot=new_segment_preview[:200],
            )
            _emit_answer_session_update(live_runtime, source='asr_partial')
            socketio.emit('asr_partial', {
                'session_id': live_runtime.session_id,
                'turn_id': live_runtime.turn_id,
                'stream_id': live_runtime.active_asr_stream_id,
                'speech_epoch': live_runtime.active_asr_speech_epoch or live_runtime.speech_epoch,
                'asr_generation': asr_generation,
                'text': partial_text,
                'full_text': new_segment_preview,
                'interrupt_epoch': live_runtime.interrupt_epoch,
                'timestamp': time.time()
            }, to=live_runtime.client_id)

        def on_final(text: str):
            if not _current_runtime_matches(
                runtime.client_id,
                runtime.session_id,
                asr_generation=asr_generation,
                allow_finalizing_asr=True,
                allow_finalized_asr=True,
            ):
                return
            live_runtime = session_registry.get(runtime.client_id)
            if not live_runtime:
                return
            if live_runtime.asr_locked:
                _log_runtime_event(
                    live_runtime,
                    'asr_final_dropped',
                    level='debug',
                    stream_id=live_runtime.active_asr_stream_id,
                    asr_generation=asr_generation,
                    reason='asr_locked',
                    lock_reason=live_runtime.asr_lock_reason,
                )
                return
            final_text = stabilize_realtime_asr_text(text)
            if not final_text:
                return
            previous_partial = _merge_asr_fragments(live_runtime.pending_asr_partials)
            previous_final = live_runtime.pending_asr_finals[0] if live_runtime.pending_asr_finals else ""
            # 直接使用已合并的文本与新 final 合并，避免重复合并
            merged_final = merge_answer_text(previous_final, final_text) if previous_final else final_text
            live_runtime.pending_asr_finals = [merged_final]
            live_runtime.pending_asr_partials.clear()
            _merged_final, _merged_partial, new_segment_preview = _build_pending_asr_text(live_runtime)
            answer_session = _ensure_answer_session(live_runtime)
            answer_session.mark_status('recording')
            answer_session.update_partial(new_segment_preview)
            _emit_realtime_speech_metrics(
                live_runtime,
                answer_session,
                is_speaking=True,
                text_snapshot=new_segment_preview or merged_final,
                source='asr_final',
            )
            _print_asr_console(live_runtime, 'final', final_text, asr_generation)
            _log_runtime_event(
                live_runtime,
                'asr_final',
                stream_id=live_runtime.active_asr_stream_id,
                asr_generation=asr_generation,
                final_preview=final_text[:160],
                final_count=len(live_runtime.pending_asr_finals),
            )
            _log_runtime_event(
                live_runtime,
                'asr_final_trace',
                level='info',
                stream_id=live_runtime.active_asr_stream_id,
                asr_generation=asr_generation,
                details=(
                    f"prev_final_units={_count_text_units(previous_final)} "
                    f"prev_partial_units={_count_text_units(previous_partial)} "
                    f"incoming_units={_count_text_units(final_text)} "
                    f"merged_final_units={_count_text_units(merged_final)} "
                    f"preview_units={_count_text_units(new_segment_preview)}"
                ),
                partial_preview=previous_partial[:160],
                final_preview=final_text[:160],
                text_snapshot=new_segment_preview[:200],
            )
            _emit_answer_session_update(live_runtime, source='asr_sentence_final')
            socketio.emit('asr_final', {
                'session_id': live_runtime.session_id,
                'turn_id': live_runtime.turn_id,
                'stream_id': live_runtime.active_asr_stream_id,
                'speech_epoch': live_runtime.active_asr_speech_epoch or live_runtime.speech_epoch,
                'asr_generation': asr_generation,
                'text': final_text,
                'full_text': merged_final,
                'preview_text': new_segment_preview,
                'interrupt_epoch': live_runtime.interrupt_epoch,
                'timestamp': time.time()
            }, to=live_runtime.client_id)

        def on_error(error: str):
            if not _current_runtime_matches(
                runtime.client_id,
                runtime.session_id,
                asr_generation=asr_generation,
            ):
                return
            live_runtime = session_registry.get(runtime.client_id)
            if not live_runtime:
                return
            _log_runtime_event(
                live_runtime,
                'asr_error',
                level='error',
                stream_id=stream_id,
                asr_generation=asr_generation,
                details=error[:200],
            )
            _disable_runtime_asr(
                live_runtime,
                'ASR_STREAM_ERROR',
                'ASR stream error',
                error,
                asr_generation=asr_generation,
            )

        started = asr_manager.start_session(
            stream_id,
            on_result=on_final,
            on_partial=on_partial,
            on_error=on_error
        )
        if started:
            flushed = _flush_pending_asr_audio(current, asr_generation=asr_generation)
            _set_runtime_asr_status(current, True)
            _log_runtime_event(
                current,
                'asr_start',
                stream_id=stream_id,
                asr_generation=asr_generation,
                speech_epoch=current.active_asr_speech_epoch,
                reason=reason,
                pending_audio_flushed=flushed,
            )
            return True

        _disable_runtime_asr(
            current,
            'ASR_START_FAILED',
            'ASR failed to start',
            f'stream_id={stream_id}',
            asr_generation=asr_generation,
        )
        return False


def _finalize_runtime_asr(runtime, reason: str = "speech_end") -> tuple[int, int]:
    if asr_manager is None or not runtime.active_asr_stream_id:
        return 0, 0

    with runtime.asr_start_lock:
        current = session_registry.get(runtime.client_id)
        if not current or current.session_id != runtime.session_id or current.ended:
            return 0, 0

        asr_generation = current.active_asr_generation
        if not asr_generation:
            return current.last_finalized_asr_generation, current.last_finalized_asr_speech_epoch

        speech_epoch = current.active_asr_speech_epoch
        pending_audio_flushed = _flush_pending_asr_audio(current, asr_generation=asr_generation)

        current.finalizing_asr_generation = asr_generation
        current.active_asr_generation = 0
        current.active_asr_speech_epoch = 0

        try:
            if asr_manager.is_available(current.active_asr_stream_id):
                asr_manager.stop_session(current.active_asr_stream_id)
            _log_runtime_event(
                current,
                'asr_finalize',
                stream_id=current.active_asr_stream_id,
                asr_generation=asr_generation,
                speech_epoch=speech_epoch,
                reason=reason,
                pending_audio_flushed=pending_audio_flushed,
            )
            grace_ms = ASR_SPEECH_END_GRACE_MS if reason == 'speech_end' else 0
            if grace_ms > 0:
                time.sleep(grace_ms / 1000.0)
        except Exception as e:
            logger.warning(f"[ASR] 结束识别流失败 - stream={current.active_asr_stream_id}: {e}")
        finally:
            _reset_pending_asr_audio(current)
            current.finalizing_asr_generation = 0
            current.last_finalized_asr_generation = asr_generation
            current.last_finalized_asr_speech_epoch = speech_epoch

        return asr_generation, speech_epoch


def _schedule_runtime_commit(
    runtime,
    turn_id: str,
    source: str,
    text_override: str = "",
    asr_generation: int = 0,
):
    timer = runtime.pending_commit_timer
    if timer:
        timer.cancel()

    def commit_task():
        current = session_registry.get(runtime.client_id)
        if not current or current.session_id != runtime.session_id or current.ended:
            return
        current.pending_commit_timer = None
        if asr_generation and current.last_finalized_asr_generation != asr_generation:
            _log_runtime_event(
                current,
                'commit_dropped',
                level='debug',
                source=source,
                dropped_turn_id=turn_id,
                asr_generation=asr_generation,
                reason='stale_asr_generation',
            )
            return
        final_text, partial_text, merged_pending_text = _build_pending_asr_text(current)
        stream_active = bool(
            asr_manager
            and current.active_asr_stream_id
            and current.active_asr_generation == asr_generation
            and asr_manager.is_available(current.active_asr_stream_id)
        )
        if text_override:
            answer_text = str(text_override).strip()
        elif final_text:
            answer_text = final_text if ASR_SEGMENT_PREFER_FINAL_ONLY else (merged_pending_text or final_text)
        elif asr_generation and not stream_active:
            answer_text = partial_text
        else:
            answer_text = ''
        current.pending_asr_partials.clear()
        current.pending_asr_finals.clear()
        if asr_generation and current.last_finalized_asr_generation == asr_generation:
            current.last_finalized_asr_generation = 0
        if answer_text:
            _process_runtime_commit(current, answer_text, turn_id, source)

    runtime.pending_commit_timer = threading.Timer(RUNTIME_COMMIT_DELAY_SECONDS, commit_task)
    runtime.pending_commit_timer.daemon = True
    runtime.pending_commit_timer.start()
    _log_runtime_event(
        runtime,
        'commit_scheduled',
        source=source,
        scheduled_turn_id=turn_id,
        text_override=bool(text_override),
        asr_generation=asr_generation or '',
    )


def _process_runtime_commit(runtime, answer_text: str, turn_id: str, source: str):
    if llm_manager is None:
        _emit_pipeline_error(runtime.client_id, runtime.session_id, 'LLM_NOT_READY', 'LLM is not initialized on server', llm_import_error or '')
        return

    normalized_answer = str(answer_text or '').strip()
    if not normalized_answer or _is_noise_text(normalized_answer):
        _log_runtime_event(runtime, 'commit_ignored', source=source, ignored_turn_id=turn_id, answer_preview=normalized_answer[:120])
        return

    text_hash = hashlib.sha1(normalized_answer.encode('utf-8')).hexdigest()
    now = time.time()
    if not state_orchestrator.can_commit(runtime, turn_id, text_hash, now):
        _log_runtime_event(runtime, 'commit_dropped', source=source, dropped_turn_id=turn_id, answer_preview=normalized_answer[:160])
        return

    current_question = (
        str(getattr(runtime, 'current_question_core', '') or '').strip()
        or str(runtime.current_question or '').strip()
        or _get_last_interviewer_question(runtime.chat_history)
    )
    if not current_question:
        _emit_pipeline_error(runtime.client_id, runtime.session_id, 'QUESTION_MISSING', 'Current question is missing')
        return

    state_orchestrator.mark_committed(runtime, text_hash, now)
    llm_job_id = runtime.new_job('llm')
    interrupt_epoch = runtime.interrupt_epoch
    state_orchestrator.begin_thinking(runtime, llm_job_id)
    _log_runtime_event(
        runtime,
        'commit_accepted',
        source=source,
        job_id=llm_job_id,
        accepted_turn_id=turn_id,
        answer_preview=normalized_answer[:160],
    )
    _emit_orchestrator_state(runtime)
    is_intro_commit = (
        str(getattr(runtime, 'current_question_kind', '')).strip().lower() == 'intro'
        and bool(str(getattr(runtime, 'pending_formal_question', '')).strip())
    )

    def llm_task():
        try:
            if is_intro_commit:
                current = session_registry.get(runtime.client_id)
                if not current or current.session_id != runtime.session_id or current.ended:
                    return
                if current.active_llm_job_id != llm_job_id or current.interrupt_epoch != interrupt_epoch:
                    return

                state_orchestrator.finish_thinking(current, llm_job_id)
                queued_formal_question = str(current.pending_formal_question or '').strip()
                if not queued_formal_question:
                    state_orchestrator.begin_listening(current)
                    _emit_orchestrator_state(current)
                    _emit_pipeline_error(current.client_id, current.session_id, 'QUESTION_MISSING', 'Formal question is missing after intro')
                    return

                current.chat_history.append({
                    'role': 'candidate',
                    'content': normalized_answer,
                    'kind': 'intro',
                })
                _reset_answer_session(current)

                normalized_reply = speech_normalizer.normalize(queued_formal_question)
                next_turn_id = current.next_turn()
                _set_runtime_asr_lock(current, False)
                current.current_question_kind = 'formal'
                current.current_question_core = _extract_runtime_question_core(
                    normalized_reply['display_text'],
                    fallback=queued_formal_question,
                )
                current.current_question = current.current_question_core
                current.formal_question_count += 1
                current.topic_question_count += 1
                current.last_question_plan = current.pending_formal_question_plan
                current.pending_formal_question = ""
                current.pending_formal_question_plan = None
                current.last_answer_analysis = None
                _track_question_timeline(current, next_turn_id, normalized_reply['spoken_text'] or normalized_reply['display_text'])
                current.chat_history.append({
                    'role': 'interviewer',
                    'content': normalized_reply['display_text'],
                })

                _log_runtime_event(
                    current,
                    'intro_turn_completed',
                    job_id=llm_job_id,
                    next_turn_id=next_turn_id,
                    intro_preview=normalized_answer[:120],
                    display_preview=normalized_reply['display_text'][:160],
                )
                socketio.emit('dialog_reply', {
                    'session_id': current.session_id,
                    'turn_id': next_turn_id,
                    'job_id': llm_job_id,
                    'display_text': normalized_reply['display_text'],
                    'spoken_text': normalized_reply['spoken_text'],
                    'analysis': None,
                    'followup_decision': {
                        'next_action': 'start_formal_question',
                        'intro_only': True,
                    },
                    'interrupt_epoch': current.interrupt_epoch,
                    'source': source,
                    'timestamp': time.time()
                }, to=current.client_id)

                _start_runtime_tts(current, normalized_reply['spoken_text'], next_turn_id, source='reply')
                return

            feedback, analysis_result, followup_decision, next_state, next_question_plan = _generate_policy_response(
                user_answer=normalized_answer,
                current_question=current_question,
                position=runtime.position,
                round_type=runtime.round_type,
                chat_history=runtime.chat_history,
                difficulty=runtime.difficulty,
                interview_state=runtime.interview_state,
                question_plan=runtime.last_question_plan,
                locked_question=runtime.forced_question_text,
                training_mode=runtime.training_mode,
            )

            current = session_registry.get(runtime.client_id)
            if not current or current.session_id != runtime.session_id or current.ended:
                return
            if current.active_llm_job_id != llm_job_id or current.interrupt_epoch != interrupt_epoch:
                return

            state_orchestrator.finish_thinking(current, llm_job_id)

            if not feedback:
                state_orchestrator.begin_listening(current)
                _emit_orchestrator_state(current)
                _emit_pipeline_error(current.client_id, current.session_id, 'LLM_ERROR', 'Failed to process answer')
                return

            _log_runtime_event(
                current,
                'llm_reply_ready',
                job_id=llm_job_id,
                reply_preview=str(feedback)[:200],
                next_action=str((followup_decision or {}).get('next_action', 'ask_followup')),
            )
            _record_runtime_dialogue(
                current,
                current_question,
                normalized_answer,
                feedback,
                analysis_result,
                followup_decision,
                turn_id=current.turn_id,
                question_id=_extract_question_id_from_plan(current.last_question_plan),
            )

            current.chat_history.append({
                'role': 'candidate',
                'content': normalized_answer
            })
            _reset_answer_session(current)

            should_auto_end, auto_end_decision = _should_auto_end_interview(current, turn_id)
            if should_auto_end:
                current.last_answer_analysis = analysis_result
                _set_runtime_asr_lock(current, True, reason='auto_end_pending')
                state_orchestrator.begin_listening(current)
                _log_runtime_event(
                    current,
                    'interview_auto_end_pending',
                    reason=str(auto_end_decision.get('reason') or '').strip(),
                    question_count=auto_end_decision.get('question_count', 0),
                    recent_average=auto_end_decision.get('recent_average', ''),
                    recent_scores=', '.join(
                        str(round(float(score), 2))
                        for score in (auto_end_decision.get('recent_scores') or [])
                        if isinstance(score, (int, float))
                    ),
                    current_turn_score=auto_end_decision.get('current_turn_score', ''),
                )
                _emit_orchestrator_state(current)
                socketio.emit('interview_should_end', {
                    'session_id': current.session_id,
                    'turn_id': turn_id,
                    'interview_id': current.interview_id,
                    'reason': auto_end_decision.get('reason', ''),
                    'question_count': auto_end_decision.get('question_count', 0),
                    'recent_average': auto_end_decision.get('recent_average'),
                    'recent_scores': auto_end_decision.get('recent_scores') or [],
                    'message': '当前面试已达到收束条件，正在结束本轮面试。',
                    'timestamp': time.time(),
                }, to=current.client_id)
                return

            next_action = str((followup_decision or {}).get('next_action', 'ask_followup')).strip()
            current.interview_state = next_state
            if next_action in {'switch_question', 'raise_difficulty'} and next_question_plan:
                current.last_question_plan = next_question_plan
                current.last_answer_analysis = None
                if next_action == 'raise_difficulty':
                    current.difficulty = (followup_decision or {}).get('difficulty_target', current.difficulty)
            else:
                current.last_answer_analysis = analysis_result

            raw_display_text = str((followup_decision or {}).get('coach_display_text') or feedback or '').strip()
            raw_spoken_text = str((followup_decision or {}).get('coach_spoken_text') or raw_display_text).strip()
            normalized_reply = {
                'display_text': speech_normalizer.normalize(raw_display_text).get('display_text', raw_display_text),
                'spoken_text': speech_normalizer.normalize(raw_spoken_text).get('spoken_text', raw_spoken_text),
            }
            next_turn_id = current.next_turn()
            _set_runtime_asr_lock(current, False)
            next_runtime_question = str(
                (followup_decision or {}).get('runtime_question')
                or (followup_decision or {}).get('coach_next_question')
                or ''
            ).strip()
            if not next_runtime_question:
                next_runtime_question = _extract_runtime_question_core(
                    normalized_reply['display_text'],
                    fallback=current.current_question,
                )
            current.current_question_kind = 'formal'
            current.current_question_core = next_runtime_question
            current.current_question = next_runtime_question
            current.formal_question_count += 1
            if next_action in {'switch_question', 'raise_difficulty'} and next_question_plan:
                current.topic_question_count += 1
            _track_question_timeline(
                current,
                next_turn_id,
                normalized_reply['spoken_text'] or normalized_reply['display_text'],
            )
            current.chat_history.append({
                'role': 'interviewer',
                'content': normalized_reply['display_text']
            })

            _log_runtime_event(
                current,
                'dialog_reply_emit',
                job_id=llm_job_id,
                next_turn_id=next_turn_id,
                display_preview=normalized_reply['display_text'][:160],
                spoken_preview=normalized_reply['spoken_text'][:160],
            )
            socketio.emit('dialog_reply', {
                'session_id': current.session_id,
                'turn_id': next_turn_id,
                'job_id': llm_job_id,
                'display_text': normalized_reply['display_text'],
                'spoken_text': normalized_reply['spoken_text'],
                'analysis': analysis_result,
                'followup_decision': followup_decision,
                'interrupt_epoch': current.interrupt_epoch,
                'source': source,
                'timestamp': time.time()
            }, to=current.client_id)

            _start_runtime_tts(current, normalized_reply['spoken_text'], next_turn_id, source='reply')
        except Exception as e:
            logger.error(f"[LLM] 新会话链路处理失败：{e}", exc_info=True)
            current = session_registry.get(runtime.client_id)
            if current and current.session_id == runtime.session_id:
                state_orchestrator.finish_thinking(current, llm_job_id)
                state_orchestrator.begin_listening(current)
                _emit_orchestrator_state(current)
            _emit_pipeline_error(runtime.client_id, runtime.session_id, 'LLM_EXCEPTION', 'LLM processing exception', str(e))

    threading.Thread(target=llm_task, daemon=True).start()


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

# 初始化速率限制器
answer_rate_limiter = RateLimiter(max_calls=5, time_window=1.0)    # 回答提交：5 次/秒
interview_rate_limiter = RateLimiter(max_calls=2, time_window=10.0) # 面试操作：2 次/10 秒
assistant_rate_limiter = RateLimiter(max_calls=20, time_window=60.0) # 助手问答：20 次/60 秒

logger.info("速率限制器初始化完成")


_assistant_task_lock = threading.RLock()
_assistant_task_executor = ThreadPoolExecutor(
    max_workers=ASSISTANT_TASK_MAX_WORKERS,
    thread_name_prefix="assistant_slow_path",
)
_assistant_tasks: dict[str, dict] = {}


def _assistant_client_key() -> str:
    forwarded_for = str(request.headers.get('X-Forwarded-For', '') or '').split(',')[0].strip()
    if forwarded_for:
        return forwarded_for
    remote_addr = str(getattr(request, 'remote_addr', '') or '').strip()
    if remote_addr:
        return remote_addr
    return 'assistant_unknown_client'


def _assistant_user_id(payload: dict | None = None) -> str:
    payload = payload or {}
    candidates = [
        request.headers.get('X-职跃星辰-User', ''),
        request.args.get('user_id', ''),
        payload.get('user_id', ''),
        payload.get('email', ''),
    ]
    for candidate in candidates:
        value = str(candidate or '').strip().lower()
        if value:
            return value[:120]
    return 'default'


def _assistant_trim_text(value: str, limit: int = 120) -> str:
    text = re.sub(r'\s+', ' ', str(value or '').strip())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _assistant_build_title(text: str) -> str:
    normalized = _assistant_trim_text(text, limit=36)
    return normalized or '新对话'


def _assistant_prune_tasks_locked(now_ts: float | None = None) -> None:
    current = float(now_ts or time.time())
    expired_ids: list[str] = []
    for task_id, task in _assistant_tasks.items():
        status = str(task.get('status') or 'queued').strip().lower()
        updated_at = float(task.get('updated_at_ts') or task.get('created_at_ts') or current)
        if status in {'completed', 'failed'} and (current - updated_at) > ASSISTANT_TASK_RETENTION_SECONDS:
            expired_ids.append(task_id)

    for task_id in expired_ids:
        _assistant_tasks.pop(task_id, None)


def _assistant_task_response(task: dict) -> dict:
    return {
        'task_id': str(task.get('task_id') or ''),
        'conversation_id': str(task.get('conversation_id') or ''),
        'user_id': str(task.get('user_id') or ''),
        'status': str(task.get('status') or 'queued'),
        'created_at': str(task.get('created_at') or ''),
        'updated_at': str(task.get('updated_at') or ''),
        'queued_at': str(task.get('queued_at') or ''),
        'started_at': str(task.get('started_at') or ''),
        'finished_at': str(task.get('finished_at') or ''),
        'provider': str(task.get('provider') or ''),
        'model': str(task.get('model') or ''),
        'latency_ms': float(task.get('latency_ms') or 0.0),
        'error': task.get('error') if isinstance(task.get('error'), dict) else None,
        'stream_text': str(task.get('stream_text') or ''),
        'stream_version': int(task.get('stream_version') or 0),
        'stream_done': bool(task.get('stream_done')),
    }


def _assistant_sse_pack(event_name: str, payload: dict) -> str:
    safe_name = str(event_name or 'message').strip() or 'message'
    data_text = json.dumps(payload or {}, ensure_ascii=False)
    return f"event: {safe_name}\ndata: {data_text}\n\n"


def _assistant_create_task(
    *,
    conversation_id: str,
    user_id: str,
    message: str,
    history_messages: list[dict],
    system_prompt: str,
    temperature: float,
    max_tokens: int | None,
) -> dict:
    now_ts = time.time()
    now_text = datetime.now().isoformat(timespec='seconds')
    task_id = f"ast_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    task_payload = {
        'task_id': task_id,
        'conversation_id': str(conversation_id or '').strip(),
        'user_id': str(user_id or '').strip().lower() or 'default',
        'status': 'queued',
        'created_at': now_text,
        'updated_at': now_text,
        'queued_at': now_text,
        'started_at': '',
        'finished_at': '',
        'created_at_ts': now_ts,
        'updated_at_ts': now_ts,
        'provider': '',
        'model': '',
        'latency_ms': 0.0,
        'error': None,
        'assistant_message': None,
        'stream_text': '',
        'stream_version': 0,
        'stream_done': False,
        'stream_error': None,
        'request': {
            'message': str(message or ''),
            'history_messages': history_messages or [],
            'system_prompt': str(system_prompt or ''),
            'temperature': float(temperature),
            'max_tokens': int(max_tokens) if max_tokens is not None else None,
        },
    }
    with _assistant_task_lock:
        _assistant_prune_tasks_locked(now_ts)
        _assistant_tasks[task_id] = task_payload
    return task_payload


def _assistant_update_task(task_id: str, **updates) -> None:
    now_ts = time.time()
    now_text = datetime.now().isoformat(timespec='seconds')
    with _assistant_task_lock:
        task = _assistant_tasks.get(task_id)
        if not task:
            return
        task.update(updates)
        task['updated_at'] = now_text
        task['updated_at_ts'] = now_ts


def _assistant_update_task_stream(
    task_id: str,
    *,
    stream_text: str | None = None,
    status: str | None = None,
    done: bool | None = None,
    error: dict | None = None,
) -> None:
    now_ts = time.time()
    now_text = datetime.now().isoformat(timespec='seconds')
    with _assistant_task_lock:
        task = _assistant_tasks.get(task_id)
        if not task:
            return

        changed = False
        if stream_text is not None:
            next_text = str(stream_text)
            if str(task.get('stream_text') or '') != next_text:
                task['stream_text'] = next_text
                changed = True
        if status is not None and str(task.get('status') or '') != str(status):
            task['status'] = str(status)
            changed = True
        if done is not None and bool(task.get('stream_done')) != bool(done):
            task['stream_done'] = bool(done)
            changed = True
        if error is not None:
            task['stream_error'] = error
            changed = True

        if changed:
            task['stream_version'] = int(task.get('stream_version') or 0) + 1
        task['updated_at'] = now_text
        task['updated_at_ts'] = now_ts


def _assistant_get_task(task_id: str, user_id: str) -> dict | None:
    normalized_task_id = str(task_id or '').strip()
    normalized_user_id = str(user_id or '').strip().lower() or 'default'
    if not normalized_task_id:
        return None
    with _assistant_task_lock:
        _assistant_prune_tasks_locked()
        task = _assistant_tasks.get(normalized_task_id)
        if not task:
            return None
        if str(task.get('user_id') or '').strip().lower() != normalized_user_id:
            return None
        return dict(task)


def _assistant_run_task(task_id: str, *, user_id: str) -> None:
    task = _assistant_get_task(task_id, user_id=user_id)
    if not task:
        return

    now_text = datetime.now().isoformat(timespec='seconds')
    _assistant_update_task(task_id, status='running', started_at=now_text)
    _assistant_update_task_stream(
        task_id,
        stream_text=str(ASSISTANT_FAST_ACK_TEXT or '已接收，正在分析你的问题...'),
        status='running',
        done=False,
        error=None,
    )
    started_at = time.perf_counter()

    try:
        request_payload = task.get('request') if isinstance(task.get('request'), dict) else {}
        message = str(request_payload.get('message') or '').strip()
        history_messages = request_payload.get('history_messages') if isinstance(request_payload.get('history_messages'), list) else []
        system_prompt = str(request_payload.get('system_prompt') or '')
        temperature = float(request_payload.get('temperature') or 0.25)
        max_tokens = _assistant_parse_max_tokens(request_payload.get('max_tokens'))

        result = _assistant_generate_reply(
            user_message=message,
            history_messages=history_messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not result.get('success'):
            error_code = str(result.get('error', 'assistant error') or 'assistant error')
            error_message = str(result.get('message', '') or '')
            _assistant_update_task(
                task_id,
                status='failed',
                finished_at=datetime.now().isoformat(timespec='seconds'),
                error={
                    'code': error_code,
                    'message': error_message,
                },
                latency_ms=float(result.get('latency_ms') or 0.0),
                provider=str(result.get('provider') or ''),
                model=str(result.get('model') or ''),
            )
            _assistant_update_task_stream(
                task_id,
                status='failed',
                done=True,
                error={
                    'code': error_code,
                    'message': error_message,
                },
            )
            return

        reply_content = str(result.get('reply', '') or '')
        if ASSISTANT_STREAM_ENABLED:
            chunks = _assistant_split_stream_chunks(reply_content)
            merged = ''
            for idx, chunk in enumerate(chunks):
                merged += chunk
                _assistant_update_task_stream(
                    task_id,
                    stream_text=merged,
                    status='streaming',
                    done=False,
                    error=None,
                )
                if idx < len(chunks) - 1 and ASSISTANT_STREAM_CHUNK_DELAY_MS > 0:
                    time.sleep(ASSISTANT_STREAM_CHUNK_DELAY_MS / 1000.0)
            _assistant_update_task_stream(
                task_id,
                stream_text=reply_content,
                status='streaming',
                done=True,
                error=None,
            )

        assistant_message_row = db_manager.append_assistant_message(
            task.get('conversation_id'),
            role='assistant',
            content=reply_content,
            citations=result.get('citations', []),
            answer_mode=result.get('answer_mode'),
            retrieval_meta=result.get('retrieval_meta', {}),
        )
        if not assistant_message_row:
            _assistant_update_task(
                task_id,
                status='failed',
                finished_at=datetime.now().isoformat(timespec='seconds'),
                error={
                    'code': 'PERSIST_ERROR',
                    'message': 'failed to persist assistant message',
                },
                latency_ms=float(result.get('latency_ms') or 0.0),
                provider=str(result.get('provider') or ''),
                model=str(result.get('model') or ''),
            )
            _assistant_update_task_stream(
                task_id,
                status='failed',
                done=True,
                error={
                    'code': 'PERSIST_ERROR',
                    'message': 'failed to persist assistant message',
                },
            )
            return

        _assistant_update_task(
            task_id,
            status='completed',
            finished_at=datetime.now().isoformat(timespec='seconds'),
            assistant_message=assistant_message_row,
            error=None,
            latency_ms=float(result.get('latency_ms') or round((time.perf_counter() - started_at) * 1000.0, 2)),
            provider=str(result.get('provider') or ''),
            model=str(result.get('model') or ''),
        )
        _assistant_update_task_stream(
            task_id,
            stream_text=reply_content,
            status='completed',
            done=True,
            error=None,
        )
    except Exception as exc:
        logger.error(f"[assistant] async task failed: task_id={task_id}, error={exc}", exc_info=True)
        _assistant_update_task(
            task_id,
            status='failed',
            finished_at=datetime.now().isoformat(timespec='seconds'),
            error={
                'code': 'INTERNAL_ERROR',
                'message': str(exc),
            },
            latency_ms=round((time.perf_counter() - started_at) * 1000.0, 2),
        )
        _assistant_update_task_stream(
            task_id,
            status='failed',
            done=True,
            error={
                'code': 'INTERNAL_ERROR',
                'message': str(exc),
            },
        )


def _assistant_model_history(messages: list[dict], limit: int = ASSISTANT_MODEL_HISTORY_LIMIT) -> list[dict]:
    normalized = []
    for item in messages[-max(1, limit):]:
        if not isinstance(item, dict):
            continue
        role = str(item.get('role', '') or '').strip().lower()
        content = str(item.get('content', '') or '').strip()
        if role not in {'user', 'assistant', 'system'} or not content:
            continue
        normalized.append({
            'role': role,
            'content': content[:4000],
        })
    return normalized


def _assistant_parse_max_tokens(raw_value) -> int | None:
    if raw_value is None:
        return None
    try:
        parsed = int(raw_value)
    except Exception:
        return None
    return max(ASSISTANT_MIN_TOKENS, min(ASSISTANT_MAX_TOKENS, parsed))


def _assistant_adaptive_max_tokens(
    *,
    requested_max_tokens: int | None,
    user_message: str,
    history_messages: list[dict],
    rag_context: str,
) -> int:
    if requested_max_tokens is not None:
        return max(ASSISTANT_MIN_TOKENS, min(ASSISTANT_MAX_TOKENS, int(requested_max_tokens)))

    default_tokens = int(getattr(assistant_service, 'default_max_tokens', ASSISTANT_ADAPTIVE_BASE_TOKENS) or ASSISTANT_ADAPTIVE_BASE_TOKENS)
    target = max(ASSISTANT_MIN_TOKENS, min(ASSISTANT_MAX_TOKENS, default_tokens))

    question_len = len(str(user_message or ''))
    history_len = sum(len(str((item or {}).get('content', '') or '')) for item in (history_messages or []) if isinstance(item, dict))
    rag_len = len(str(rag_context or ''))

    if question_len > 120:
        target += 96
    if question_len > 240:
        target += 96
    if history_len > 1800:
        target += 128
    if history_len > 3600:
        target += 128
    if rag_len > 1800:
        target += 128

    return max(ASSISTANT_MIN_TOKENS, min(ASSISTANT_MAX_TOKENS, int(target)))


def _assistant_extract_key_facts(text: str, *, max_items: int = 3) -> list[str]:
    normalized = str(text or '').replace('\r\n', '\n').replace('\r', '\n')
    if not normalized.strip():
        return []
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    pieces = re.split(r'[。！？；;\n]+', normalized)
    facts: list[str] = []
    for piece in pieces:
        value = str(piece or '').strip()
        if len(value) < 10:
            continue
        facts.append(value[:120])
        if len(facts) >= max_items:
            break
    return facts


def _assistant_compress_history(messages: list[dict]) -> tuple[list[dict], dict]:
    normalized: list[dict] = []
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get('role') or '').strip().lower()
        content = str(item.get('content') or '').strip()
        if role not in {'user', 'assistant', 'system'} or not content:
            continue
        normalized.append({'role': role, 'content': content[:4000]})

    total_chars = sum(len(str(item.get('content') or '')) for item in normalized)
    keep_turns = max(1, ASSISTANT_HISTORY_COMPRESS_KEEP_TURNS)
    keep_messages = keep_turns * 2

    if len(normalized) <= keep_messages and total_chars <= ASSISTANT_HISTORY_COMPRESS_MAX_CHARS:
        return normalized, {
            'history_compressed': False,
            'history_original_count': len(normalized),
            'history_final_count': len(normalized),
            'history_original_chars': total_chars,
            'history_summary_chars': 0,
        }

    recent = normalized[-keep_messages:] if keep_messages > 0 else []
    older = normalized[:-keep_messages] if keep_messages > 0 else normalized

    summary_lines: list[str] = []
    for item in older[-12:]:
        role = '用户' if item.get('role') == 'user' else ('助手' if item.get('role') == 'assistant' else '系统')
        facts = _assistant_extract_key_facts(str(item.get('content') or ''), max_items=2)
        if not facts:
            continue
        summary_lines.append(f"- {role}: {'；'.join(facts)}")

    summary_text = ''
    if summary_lines:
        summary_text = (
            "历史对话摘要（已压缩，仅保留关键事实）：\n"
            + "\n".join(summary_lines[:12])
        )[:1200]

    compact: list[dict] = []
    if summary_text:
        compact.append({'role': 'system', 'content': summary_text})
    compact.extend(recent)

    return compact, {
        'history_compressed': True,
        'history_original_count': len(normalized),
        'history_final_count': len(compact),
        'history_original_chars': total_chars,
        'history_summary_chars': len(summary_text),
    }


def _assistant_split_stream_chunks(text: str) -> list[str]:
    content = str(text or '')
    if not content.strip():
        return []
    sentences = [segment.strip() for segment in re.split(r'(?<=[。！？!?])', content) if segment.strip()]
    if not sentences:
        sentences = [content.strip()]

    first_chunk = ''.join(sentences[:2]).strip()
    remaining = ''.join(sentences[2:]).strip()
    chunks: list[str] = []
    if first_chunk:
        chunks.append(first_chunk)
    if remaining:
        step = max(40, ASSISTANT_STREAM_CHUNK_CHARS)
        for index in range(0, len(remaining), step):
            chunks.append(remaining[index:index + step])
    if not chunks:
        chunks = [content.strip()]
    return chunks


def _assistant_detect_position_hint(user_message: str) -> str | None:
    normalized = str(user_message or '').strip().lower()
    if not normalized:
        return None

    compact = normalized.replace(' ', '')
    for position, keywords in ASSISTANT_POSITION_HINTS.items():
        for keyword in keywords:
            token = str(keyword or '').strip().lower()
            if not token:
                continue
            if token in normalized or token.replace(' ', '') in compact:
                return position
    return None


def _assistant_should_attach_history(user_message: str, history_messages: list[dict] | None = None) -> bool:
    history_messages = history_messages or []
    if not history_messages:
        return False

    normalized = str(user_message or '').strip().lower()
    if not normalized:
        return False

    if len(normalized) <= 18:
        return True

    if any(marker in normalized for marker in ASSISTANT_FOLLOW_UP_MARKERS):
        return True

    # Standalone questions with clear technical nouns should prefer the current query only.
    if _assistant_detect_position_hint(normalized):
        return False

    return False


def _assistant_normalize_citation(item: dict, min_score: float = ASSISTANT_CITATION_MIN_SCORE) -> dict | None:
    if not isinstance(item, dict):
        return None

    metadata = item.get('metadata') or {}
    document = str(item.get('document', '') or '').strip()
    answer_summary = str(metadata.get('answer_summary', '') or '').strip()
    answer = str(metadata.get('answer', '') or '').strip()
    retrieval_text = str(metadata.get('retrieval_text', '') or '').strip()
    snippet = answer_summary or answer or retrieval_text or document
    snippet = _assistant_trim_text(snippet, limit=180)
    if not snippet:
        return None

    title = (
        str(metadata.get('question', '') or '').strip()
        or str(item.get('question', '') or '').strip()
        or str(metadata.get('subcategory', '') or '').strip()
        or str(metadata.get('category', '') or '').strip()
        or '知识库片段'
    )
    source = (
        str(metadata.get('source', '') or '').strip()
        or str(metadata.get('source_id', '') or '').strip()
        or str(metadata.get('position', '') or '').strip()
        or '本地知识库'
    )
    score = item.get('similarity', item.get('rerank_score'))
    try:
        score = round(float(score), 4) if score is not None else None
    except Exception:
        score = None

    if score is not None and score < min_score:
        return None

    return {
        'title': _assistant_trim_text(title, limit=80) or '知识库片段',
        'source': _assistant_trim_text(source, limit=80) or '本地知识库',
        'snippet': snippet,
        'score': score,
        'source_type': str(metadata.get('source_type', '') or metadata.get('view_type', '') or '').strip(),
    }


def _assistant_collect_rag_context(user_message: str, history_messages: list[dict] | None = None) -> tuple[str, list[dict], dict, str]:
    rag_status = rag_service.status() if rag_service is not None else {}
    if rag_service is None or not bool(getattr(rag_service, 'enabled', False)):
        return '', [], {
            'rag_enabled': False,
            'rag_ready': False,
            'question_hits': 0,
            'rubric_hits': 0,
            'citation_count': 0,
        }, 'model_fallback'

    history_messages = history_messages or []
    query = user_message.strip()
    position_hint = _assistant_detect_position_hint(query)
    history_attached = False
    if _assistant_should_attach_history(query, history_messages):
        recent_user_context = ' '.join(
            str(item.get('content', '') or '').strip()
            for item in history_messages[-max(1, ASSISTANT_HISTORY_QUERY_USER_TURNS * 2):]
            if str(item.get('role', '') or '').strip().lower() == 'user'
        ).strip()
        if recent_user_context:
            recent_user_context = _assistant_trim_text(recent_user_context, limit=240)
            query = f"{recent_user_context}\n{query}".strip()
            history_attached = True

    def _retrieve_questions():
        return rag_service.retrieve_questions(
            query,
            top_k=2,
            min_similarity=ASSISTANT_RETRIEVAL_MIN_SIMILARITY,
            position=position_hint,
        )

    def _retrieve_rubrics():
        return rag_service.retrieve_rubrics(
            query,
            top_k=2,
            min_similarity=ASSISTANT_RETRIEVAL_MIN_SIMILARITY,
            position=position_hint,
        )

    question_hits = []
    rubric_hits = []
    retrieval_started_at = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=ASSISTANT_RETRIEVAL_WORKERS) as executor:
            question_future = executor.submit(_retrieve_questions)
            rubric_future = executor.submit(_retrieve_rubrics)
            question_hits = question_future.result()
            rubric_hits = rubric_future.result()
    except Exception:
        question_hits = _retrieve_questions()
        rubric_hits = _retrieve_rubrics()
    retrieval_latency_ms = round((time.perf_counter() - retrieval_started_at) * 1000.0, 2)

    merged_hits = [*question_hits, *rubric_hits]
    merged_hits.sort(
        key=lambda item: (
            float(item.get('rerank_score', 0.0) or 0.0),
            float(item.get('similarity', 0.0) or 0.0),
        ),
        reverse=True,
    )

    context_citations: list[dict] = []
    citations: list[dict] = []
    seen_context = set()
    seen_display = set()
    for raw_item in merged_hits:
        context_citation = _assistant_normalize_citation(
            raw_item,
            min_score=ASSISTANT_RETRIEVAL_MIN_SIMILARITY,
        )
        if context_citation:
            context_key = (
                context_citation.get('title', ''),
                context_citation.get('source', ''),
                context_citation.get('snippet', ''),
            )
            if context_key not in seen_context and len(context_citations) < ASSISTANT_CITATION_MAX_ITEMS:
                seen_context.add(context_key)
                context_citations.append(context_citation)

        citation = _assistant_normalize_citation(raw_item)
        if citation:
            display_key = (
                citation.get('title', ''),
                citation.get('source', ''),
                citation.get('snippet', ''),
            )
            if display_key not in seen_display and len(citations) < ASSISTANT_CITATION_MAX_ITEMS:
                seen_display.add(display_key)
                citations.append(citation)

        if len(context_citations) >= ASSISTANT_CITATION_MAX_ITEMS and len(citations) >= ASSISTANT_CITATION_MAX_ITEMS:
            break

    rag_context = ''
    if context_citations:
        parts = []
        for index, citation in enumerate(context_citations, start=1):
            part_lines = [
                f"{index}. 标题：{citation.get('title', '')}",
                f"来源：{citation.get('source', '')}",
                f"内容：{citation.get('snippet', '')}",
            ]
            if citation.get('source_type'):
                part_lines.append(f"类型：{citation.get('source_type')}")
            parts.append('\n'.join(part_lines))
        rag_context = '\n\n'.join(parts)

    answer_mode = 'model_fallback'
    if context_citations:
        answer_mode = 'rag_grounded' if len(citations) >= 1 else 'rag_plus_model'

    retrieval_meta = {
        'rag_enabled': True,
        'rag_ready': bool(rag_status.get('dual_index_ready') or rag_status.get('count')),
        'knowledge_count': int(rag_status.get('count') or 0),
        'question_hits': len(question_hits),
        'rubric_hits': len(rubric_hits),
        'grounding_count': len(context_citations),
        'citation_count': len(citations),
        'retrieval_latency_ms': retrieval_latency_ms,
        'retrieval_min_similarity': ASSISTANT_RETRIEVAL_MIN_SIMILARITY,
        'citation_min_score': ASSISTANT_CITATION_MIN_SCORE,
        'position_hint': position_hint or '',
        'history_attached': history_attached,
    }
    return rag_context, citations, retrieval_meta, answer_mode


def _assistant_base_system_prompt(extra_prompt: str = '') -> str:
    base_prompt = (
        "你是 职跃星辰 的 AI 问答助手，主要帮助用户完成求职准备、项目表达梳理、岗位理解、"
        "面试复盘、简历优化与训练建议总结。\n"
        "回答风格要求：中文优先，简洁清晰，尽量给出可执行建议。\n"
        "如果知识库证据充足，优先依据知识库回答；如果证据不足，要明确说明哪些内容属于一般经验补充。"
    )
    addition = str(extra_prompt or '').strip()
    if addition:
        return f"{base_prompt}\n\n补充要求：\n{addition}"
    return base_prompt


def _assistant_generate_reply(
    *,
    user_message: str,
    history_messages: list[dict] | None = None,
    system_prompt: str = '',
    temperature: float = 0.25,
    max_tokens: int | None = None,
) -> dict:
    history_messages = history_messages or []
    compressed_history, compression_meta = _assistant_compress_history(history_messages)
    rag_context, citations, retrieval_meta, answer_mode = _assistant_collect_rag_context(
        user_message,
        history_messages=history_messages,
    )
    effective_max_tokens = _assistant_adaptive_max_tokens(
        requested_max_tokens=max_tokens,
        user_message=user_message,
        history_messages=compressed_history,
        rag_context=rag_context,
    )
    result = assistant_service.chat(
        user_message=user_message,
        messages=compressed_history,
        system_prompt=_assistant_base_system_prompt(system_prompt),
        rag_context=rag_context,
        temperature=temperature,
        max_tokens=effective_max_tokens,
    )
    result['citations'] = citations
    retrieval_meta = dict(retrieval_meta or {})
    retrieval_meta.update(compression_meta)
    retrieval_meta['effective_max_tokens'] = int(effective_max_tokens)
    result['retrieval_meta'] = retrieval_meta
    result['answer_mode'] = answer_mode
    return result


# ==================== 基础路由 ====================

app.register_blueprint(create_system_blueprint(
    config=config,
    logger=logger,
    performance_monitor=performance_monitor,
    db_manager=db_manager,
    llm_manager=llm_manager,
    rag_service=rag_service,
    asr_manager=asr_manager,
    assistant_service=assistant_service,
    tts_manager=tts_manager,
    tts_import_error=tts_import_error,
))


@app.route('/api/prewarm', methods=['GET', 'POST'])
def api_prewarm():
    """后台预热 LLM/RAG/ASR/TTS，减少首次进入面试的冷启动等待。"""
    payload = request.get_json(silent=True) or {}
    source = str(payload.get('source') or request.args.get('source') or 'api').strip() or 'api'
    force_raw = payload.get('force', request.args.get('force', '0'))
    wait_raw = payload.get('wait', request.args.get('wait', '0'))
    wait_timeout_raw = payload.get('wait_timeout', request.args.get('wait_timeout', 2.5))

    force = str(force_raw).strip().lower() in {'1', 'true', 'yes', 'on'}
    wait = str(wait_raw).strip().lower() in {'1', 'true', 'yes', 'on'}
    try:
        wait_timeout = max(0.0, min(float(wait_timeout_raw), 8.0))
    except Exception:
        wait_timeout = 2.5

    global _service_prewarm_thread
    now = time.time()
    with _service_prewarm_lock:
        running = bool(_service_prewarm_thread and _service_prewarm_thread.is_alive())
        last_finished_at = float(_service_prewarm_state.get('last_finished_at') or 0.0)
        cached_recent = bool(
            last_finished_at > 0.0
            and (now - last_finished_at) < SERVICE_PREWARM_CACHE_SECONDS
            and _service_prewarm_state.get('status') in {'completed', 'partial'}
        )

        if not running and (force or not cached_recent):
            _service_prewarm_state['status'] = 'running'
            _service_prewarm_state['trigger'] = source
            _service_prewarm_state['last_started_at'] = now
            _service_prewarm_state['results'] = {}
            _service_prewarm_state['duration_ms'] = 0.0
            _service_prewarm_thread = threading.Thread(
                target=_run_service_prewarm,
                args=(source,),
                daemon=True,
            )
            _service_prewarm_thread.start()
            running = True

        worker = _service_prewarm_thread

    if wait and worker and worker.is_alive():
        worker.join(timeout=wait_timeout)

    return jsonify({
        'success': True,
        'data': _snapshot_service_prewarm_state(),
    })


# ==================== 账号与会员接口 ====================

app.register_blueprint(create_account_blueprint(db_manager=db_manager))


# ==================== 用户提醒接口 ====================

app.register_blueprint(create_user_blueprint(
    db_manager=db_manager,
    logger=logger,
))


# ==================== 知识图谱接口 ====================

app.register_blueprint(create_knowledge_graph_blueprint(
    knowledge_graph_service=knowledge_graph_service,
    knowledge_graph_import_error=knowledge_graph_import_error,
    logger=logger,
))

@app.route('/api/assistant/health')
def api_assistant_health():
    """检查全局助手可用状态。"""
    if assistant_service is None:
        return jsonify({
            'success': False,
            'error': 'assistant service unavailable',
            'details': assistant_import_error or '',
        }), 503

    status_payload = assistant_service.health()
    rag_payload = rag_service.status() if rag_service is not None else {
        'enabled': False,
        'dual_index_ready': False,
        'count': 0,
        'question_count': 0,
        'rubric_count': 0,
    }
    success = bool(status_payload.get('success'))
    return jsonify({
        'success': success,
        'data': {
            **status_payload,
            'rag': rag_payload,
            'async_mode': {
                'enabled': bool(ASSISTANT_ASYNC_ENABLED),
                'task_max_workers': int(ASSISTANT_TASK_MAX_WORKERS),
                'task_retention_seconds': int(ASSISTANT_TASK_RETENTION_SECONDS),
            },
        },
    }), (200 if success else 503)

@app.route('/api/assistant/conversations', methods=['GET'])
def api_assistant_conversations():
    user_id = _assistant_user_id()
    limit = max(1, min(request.args.get('limit', 50, type=int) or 50, 200))
    conversations = db_manager.list_assistant_conversations(user_id=user_id, limit=limit)
    return jsonify({
        'success': True,
        'conversations': conversations,
        'count': len(conversations),
        'user_id': user_id,
    })


@app.route('/api/assistant/conversations', methods=['POST'])
def api_create_assistant_conversation():
    payload = request.get_json(silent=True) or {}
    user_id = _assistant_user_id(payload)
    raw_title = str(payload.get('title', '') or '').strip()
    title = _assistant_build_title(raw_title or '新对话')
    conversation = db_manager.create_assistant_conversation(user_id=user_id, title=title)
    if not conversation:
        return jsonify({
            'success': False,
            'error': 'failed to create conversation',
        }), 500

    return jsonify({
        'success': True,
        'conversation': conversation,
    }), 201


@app.route('/api/assistant/conversations/<conversation_id>', methods=['GET'])
def api_get_assistant_conversation(conversation_id):
    user_id = _assistant_user_id()
    conversation = db_manager.get_assistant_conversation(conversation_id, user_id=user_id)
    if not conversation:
        return jsonify({
            'success': False,
            'error': 'conversation not found',
        }), 404

    messages = db_manager.get_assistant_messages(conversation_id, user_id=user_id, limit=500)
    return jsonify({
        'success': True,
        'conversation': conversation,
        'messages': messages,
    })


@app.route('/api/assistant/conversations/<conversation_id>', methods=['DELETE'])
def api_delete_assistant_conversation(conversation_id):
    payload = request.get_json(silent=True) or {}
    user_id = _assistant_user_id(payload)

    deleted = db_manager.delete_assistant_conversation(
        conversation_id,
        user_id=user_id,
    )
    if not deleted:
        return jsonify({
            'success': False,
            'error': 'conversation not found',
        }), 404

    return jsonify({
        'success': True,
        'conversation_id': str(conversation_id or '').strip(),
        'user_id': user_id,
    })


@app.route('/api/assistant/conversations/<conversation_id>/messages', methods=['POST'])
def api_post_assistant_message(conversation_id):
    if assistant_service is None:
        return jsonify({
            'success': False,
            'error': 'assistant service unavailable',
            'details': assistant_import_error or '',
        }), 503

    if not bool(getattr(assistant_service, 'enabled', False)):
        return jsonify({
            'success': False,
            'error': 'assistant disabled',
        }), 503

    client_key = _assistant_client_key()
    if not assistant_rate_limiter.is_allowed(client_key):
        return jsonify({
            'success': False,
            'error': 'rate limit exceeded',
            'retry_after_seconds': int(assistant_rate_limiter.time_window),
        }), 429

    payload = request.get_json(silent=True) or {}
    user_id = _assistant_user_id(payload)
    conversation = db_manager.get_assistant_conversation(conversation_id, user_id=user_id)
    if not conversation:
        return jsonify({
            'success': False,
            'error': 'conversation not found',
        }), 404

    raw_message = str(payload.get('message', '') or '')
    raw_system_prompt = str(payload.get('system_prompt', '') or '')
    raw_temperature = payload.get('temperature', 0.25)
    raw_max_tokens = payload.get('max_tokens')

    try:
        message = validate_string(
            raw_message,
            'message',
            min_length=1,
            max_length=4000,
            allow_empty=False,
        ).strip()

        system_prompt = ''
        if raw_system_prompt.strip():
            system_prompt = validate_string(
                raw_system_prompt,
                'system_prompt',
                min_length=0,
                max_length=4000,
                allow_empty=True,
            ).strip()

        try:
            temperature = float(raw_temperature)
        except Exception:
            temperature = 0.25
        temperature = max(0.0, min(1.2, temperature))

        max_tokens = _assistant_parse_max_tokens(raw_max_tokens)

        existing_messages = db_manager.get_assistant_messages(conversation_id, user_id=user_id, limit=20)
        history_messages = _assistant_model_history(existing_messages, limit=ASSISTANT_MODEL_HISTORY_LIMIT)

        user_message_row = db_manager.append_assistant_message(
            conversation_id,
            role='user',
            content=message,
            retrieval_meta={'source': 'user_input'},
        )
        if not user_message_row:
            return jsonify({
                'success': False,
                'error': 'failed to persist user message',
            }), 500

        if int(conversation.get('message_count') or 0) == 0:
            db_manager.update_assistant_conversation(
                conversation_id,
                title=_assistant_build_title(message),
            )

        if ASSISTANT_ASYNC_ENABLED:
            task = _assistant_create_task(
                conversation_id=conversation_id,
                user_id=user_id,
                message=message,
                history_messages=history_messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            try:
                _assistant_task_executor.submit(
                    _assistant_run_task,
                    task['task_id'],
                    user_id=user_id,
                )
            except Exception as schedule_exc:
                logger.error(f"[assistant] failed to schedule async task: {schedule_exc}", exc_info=True)
                _assistant_update_task(
                    task['task_id'],
                    status='failed',
                    finished_at=datetime.now().isoformat(timespec='seconds'),
                    error={
                        'code': 'SCHEDULE_ERROR',
                        'message': str(schedule_exc),
                    },
                )
                return jsonify({
                    'success': False,
                    'error': 'failed to schedule assistant task',
                    'details': str(schedule_exc),
                }), 500

            latest_conversation = db_manager.get_assistant_conversation(conversation_id, user_id=user_id)
            return jsonify({
                'success': True,
                'async': True,
                'conversation': latest_conversation,
                'user_message': user_message_row,
                'task': _assistant_task_response(task),
                'placeholder': {
                    'content': ASSISTANT_FAST_ACK_TEXT,
                },
            }), 202

        result = _assistant_generate_reply(
            user_message=message,
            history_messages=history_messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not result.get('success'):
            error_code = str(result.get('error', 'assistant error') or 'assistant error')
            error_message = str(result.get('message', '') or '')
            status_code = 502
            lowered_message = error_message.lower()
            if error_code == 'ASSISTANT_EXCEPTION' and ('timed out' in lowered_message or 'timeout' in lowered_message):
                status_code = 504
            elif error_code == 'ASSISTANT_NOT_READY':
                status_code = 503
            return jsonify({
                'success': False,
                'error': error_code,
                'message': error_message,
                'latency_ms': result.get('latency_ms', 0.0),
                'citations': result.get('citations', []),
                'retrieval_meta': result.get('retrieval_meta', {}),
                'answer_mode': result.get('answer_mode', 'model_fallback'),
            }), status_code

        assistant_message_row = db_manager.append_assistant_message(
            conversation_id,
            role='assistant',
            content=str(result.get('reply', '') or ''),
            citations=result.get('citations', []),
            answer_mode=result.get('answer_mode'),
            retrieval_meta=result.get('retrieval_meta', {}),
        )
        if not assistant_message_row:
            return jsonify({
                'success': False,
                'error': 'failed to persist assistant message',
            }), 500

        latest_conversation = db_manager.get_assistant_conversation(conversation_id, user_id=user_id)
        return jsonify({
            'success': True,
            'async': False,
            'conversation': latest_conversation,
            'user_message': user_message_row,
            'assistant_message': assistant_message_row,
            'reply': assistant_message_row.get('content', ''),
            'citations': assistant_message_row.get('citations', []),
            'retrieval_meta': assistant_message_row.get('retrieval_meta', {}),
            'answer_mode': assistant_message_row.get('answer_mode', 'model_fallback'),
            'provider': result.get('provider', ''),
            'model': result.get('model', ''),
            'latency_ms': result.get('latency_ms', 0.0),
            'done_reason': result.get('done_reason', ''),
            'usage': {
                'prompt_eval_count': int(result.get('prompt_eval_count') or 0),
                'eval_count': int(result.get('eval_count') or 0),
            },
        })
    except ValidationError as exc:
        return jsonify({
            'success': False,
            'error': str(exc),
        }), 400
    except Exception as exc:
        logger.error(f"assistant message error: {exc}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'internal server error',
            'details': str(exc),
        }), 500


@app.route('/api/assistant/tasks/<task_id>', methods=['GET'])
def api_get_assistant_task(task_id):
    user_id = _assistant_user_id()
    task = _assistant_get_task(task_id, user_id=user_id)
    if not task:
        return jsonify({
            'success': False,
            'error': 'task not found',
        }), 404

    response_payload = {
        'success': True,
        'task': _assistant_task_response(task),
        'assistant_message': task.get('assistant_message') if task.get('status') == 'completed' else None,
        'async': True,
    }
    if task.get('status') == 'completed':
        conversation = db_manager.get_assistant_conversation(task.get('conversation_id'), user_id=user_id)
        response_payload['conversation'] = conversation
    return jsonify(response_payload)


@app.route('/api/assistant/tasks/<task_id>/stream', methods=['GET'])
def api_stream_assistant_task(task_id):
    user_id = _assistant_user_id()

    def _event_stream():
        last_version = -1
        idle_rounds = 0
        max_idle_rounds = 240  # ~120s with 0.5s cadence
        while idle_rounds < max_idle_rounds:
            task = _assistant_get_task(task_id, user_id=user_id)
            if not task:
                yield _assistant_sse_pack('error', {
                    'success': False,
                    'error': 'task not found',
                })
                return

            stream_version = int(task.get('stream_version') or 0)
            status = str(task.get('status') or '').lower()
            done = status in {'completed', 'failed'}

            if stream_version != last_version:
                payload = {
                    'success': True,
                    'task': _assistant_task_response(task),
                    'assistant_message': task.get('assistant_message') if status == 'completed' else None,
                    'async': True,
                    'done': done,
                }
                if status == 'completed':
                    payload['conversation'] = db_manager.get_assistant_conversation(
                        task.get('conversation_id'),
                        user_id=user_id,
                    )
                yield _assistant_sse_pack('assistant_stream', payload)
                last_version = stream_version
                idle_rounds = 0
            else:
                idle_rounds += 1

            if done:
                yield _assistant_sse_pack('done', {'success': True, 'task_id': task_id})
                return

            time.sleep(0.5)

        yield _assistant_sse_pack('timeout', {
            'success': False,
            'error': 'stream timeout',
            'task_id': task_id,
        })

    response = Response(stream_with_context(_event_stream()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@app.route('/api/assistant/chat', methods=['POST'])
def api_assistant_chat():
    """全局助手对话（仅非面试场景调用）。"""
    if assistant_service is None:
        return jsonify({
            'success': False,
            'error': 'assistant service unavailable',
            'details': assistant_import_error or '',
        }), 503

    if not bool(getattr(assistant_service, 'enabled', False)):
        return jsonify({
            'success': False,
            'error': 'assistant disabled',
        }), 503

    client_key = _assistant_client_key()
    if not assistant_rate_limiter.is_allowed(client_key):
        return jsonify({
            'success': False,
            'error': 'rate limit exceeded',
            'retry_after_seconds': int(assistant_rate_limiter.time_window),
        }), 429

    payload = request.get_json(silent=True) or {}
    raw_message = str(payload.get('message', '') or '')
    raw_messages = payload.get('messages', [])
    raw_system_prompt = str(payload.get('system_prompt', '') or '')
    raw_temperature = payload.get('temperature', 0.3)
    raw_max_tokens = payload.get('max_tokens')

    try:
        message = validate_string(
            raw_message,
            'message',
            min_length=1,
            max_length=4000,
            allow_empty=False,
        ).strip()

        system_prompt = ''
        if raw_system_prompt.strip():
            system_prompt = validate_string(
                raw_system_prompt,
                'system_prompt',
                min_length=0,
                max_length=4000,
                allow_empty=True,
            ).strip()

        if not isinstance(raw_messages, list):
            raise ValidationError('messages 必须是数组')

        messages = []
        for item in raw_messages[-20:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get('role', '') or '').strip().lower()
            content = str(item.get('content', '') or '').strip()
            if role not in {'user', 'assistant', 'system'}:
                continue
            if not content:
                continue
            messages.append({
                'role': role,
                'content': content[:4000],
            })

        try:
            temperature = float(raw_temperature)
        except Exception:
            temperature = 0.3
        temperature = max(0.0, min(1.2, temperature))

        max_tokens = _assistant_parse_max_tokens(raw_max_tokens)

        result = _assistant_generate_reply(
            user_message=message,
            history_messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not result.get('success'):
            error_code = str(result.get('error', 'assistant error') or 'assistant error')
            error_message = str(result.get('message', '') or '')
            status_code = 502
            lowered_message = error_message.lower()
            if error_code == 'ASSISTANT_EXCEPTION' and ('timed out' in lowered_message or 'timeout' in lowered_message):
                status_code = 504
            elif error_code == 'ASSISTANT_NOT_READY':
                status_code = 503
            elif error_code.startswith('OLLAMA_HTTP_') or error_code.startswith('OPENROUTER_HTTP_'):
                try:
                    upstream = int(error_code.split('_')[-1].strip())
                    if upstream in {401, 403, 429}:
                        status_code = upstream
                    elif 400 <= upstream < 600:
                        status_code = 502
                except Exception:
                    status_code = 502

            logger.warning(
                f"[assistant] chat failed: code={error_code}, status={status_code}, message={error_message[:200]}"
            )
            return jsonify({
                'success': False,
                'error': error_code,
                'message': error_message,
                'latency_ms': result.get('latency_ms', 0.0),
            }), status_code

        return jsonify({
            'success': True,
            'reply': result.get('reply', ''),
            'citations': result.get('citations', []),
            'retrieval_meta': result.get('retrieval_meta', {}),
            'answer_mode': result.get('answer_mode', 'model_fallback'),
            'provider': result.get('provider', ''),
            'model': result.get('model', ''),
            'latency_ms': result.get('latency_ms', 0.0),
            'done_reason': result.get('done_reason', ''),
            'usage': {
                'prompt_eval_count': int(result.get('prompt_eval_count') or 0),
                'eval_count': int(result.get('eval_count') or 0),
            },
        })
    except ValidationError as exc:
        return jsonify({
            'success': False,
            'error': str(exc),
        }), 400
    except Exception as exc:
        logger.error(f"assistant chat error: {exc}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'internal server error',
            'details': str(exc),
        }), 500


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
    runtime = session_registry.get(client_id)
    if runtime:
        runtime.disconnected_at = time.time()

        def cleanup_if_not_resumed():
            current = session_registry.get(client_id)
            if (
                not current
                or current.session_id != runtime.session_id
                or current.client_id != client_id
                or not current.disconnected_at
                or time.time() - current.disconnected_at < RUNTIME_RECONNECT_GRACE_SECONDS
            ):
                return

            removed = session_registry.remove(client_id)
            if removed:
                removed.ended = True
                if removed.pending_commit_timer:
                    removed.pending_commit_timer.cancel()
                _cancel_answer_finalize_timer(removed)
                _reset_pending_asr_audio(removed)
                if asr_manager and removed.active_asr_stream_id:
                    asr_manager.stop_session(removed.active_asr_stream_id)
                _log_runtime_event(removed, 'disconnect_cleanup', reconnect_grace_seconds=RUNTIME_RECONNECT_GRACE_SECONDS)

        runtime.disconnect_cleanup_timer = threading.Timer(RUNTIME_RECONNECT_GRACE_SECONDS, cleanup_if_not_resumed)
        runtime.disconnect_cleanup_timer.daemon = True
        runtime.disconnect_cleanup_timer.start()
        _log_runtime_event(runtime, 'disconnect_grace_started', reconnect_grace_seconds=RUNTIME_RECONNECT_GRACE_SECONDS)
    logger.info(f"客户端已断开 - ID: {client_id}")


@socketio.on('session_resume')
def handle_session_resume(data=None):
    """客户端 Socket.IO 重连后按稳定 session_id 恢复运行时。"""
    client_id = request.sid
    session_id = str((data or {}).get('session_id', '')).strip()
    if not session_id:
        emit('session_resume_failed', {
            'session_id': '',
            'code': 'MISSING_SESSION_ID',
            'message': 'session_id is required for resume',
        })
        return

    runtime = session_registry.rebind_client(session_id, client_id)
    if not runtime or runtime.ended:
        emit('session_resume_failed', {
            'session_id': session_id,
            'code': 'SESSION_NOT_FOUND',
            'message': 'Session cannot be resumed',
        })
        return

    _log_runtime_event(runtime, 'session_resumed', client_id=client_id)
    _emit_orchestrator_state(runtime)
    emit('session_resumed', {
        'session_id': runtime.session_id,
        'interview_id': runtime.interview_id,
        'turn_id': runtime.turn_id,
        'mode': runtime.mode,
        'current_question': runtime.current_question_core or runtime.current_question,
        'current_question_kind': runtime.current_question_kind,
        'formal_question_count': runtime.formal_question_count,
        'topic_question_count': runtime.topic_question_count,
        'interrupt_epoch': runtime.interrupt_epoch,
        'timestamp': time.time(),
    })


@socketio.on('session_start')
@rate_limit(interview_rate_limiter)
def handle_session_start(data=None):
    client_id = request.sid

    try:
        existing = session_registry.remove(client_id)
        if existing:
            existing.ended = True
            if existing.pending_commit_timer:
                existing.pending_commit_timer.cancel()
            _cancel_answer_finalize_timer(existing)
            _reset_pending_asr_audio(existing)
            if asr_manager and existing.active_asr_stream_id:
                asr_manager.stop_session(existing.active_asr_stream_id)

        selected_question = _parse_selected_question_payload((data or {}).get('selected_question'))

        round_type = data.get('round_type', data.get('round', 'technical')) if data else 'technical'
        position = data.get('position', 'java_backend') if data else 'java_backend'
        difficulty = data.get('difficulty', 'medium') if data else 'medium'

        if selected_question:
            if selected_question.get('round_type'):
                round_type = selected_question.get('round_type')
            if selected_question.get('position'):
                position = selected_question.get('position')
            if selected_question.get('difficulty'):
                difficulty = selected_question.get('difficulty')
        user_id = data.get('user_id', 'default') if data else 'default'
        training_mode = str(data.get('training_mode', '')).strip() if data else ''
        session_id = str(data.get('session_id', '')).strip() if data else ''
        if not session_id:
            session_id = uuid.uuid4().hex

        runtime = session_registry.create(
            client_id=client_id,
            session_id=session_id,
            user_id=user_id,
            round_type=round_type,
            position=position,
            difficulty=difficulty,
            training_mode=training_mode,
        )
        target_session_id = runtime.session_id

        def runtime_stale() -> bool:
            live_runtime = session_registry.get(client_id)
            return bool(
                not live_runtime
                or live_runtime.session_id != target_session_id
                or live_runtime.ended
            )

        runtime.started_at = time.time()
        runtime.active_asr_stream_id = f"asr_{session_id}"
        runtime.short_pause_threshold_seconds = SHORT_PAUSE_SECONDS
        runtime.long_pause_threshold_seconds = LONG_PAUSE_SECONDS
        runtime.auto_end_min_questions = _parse_auto_end_question_limit(
            (data or {}).get('auto_end_min_questions', AUTO_END_MIN_QUESTIONS),
            AUTO_END_MIN_QUESTIONS,
        )
        runtime.auto_end_max_questions = _parse_auto_end_question_limit(
            (data or {}).get('auto_end_max_questions', AUTO_END_MAX_QUESTIONS),
            AUTO_END_MAX_QUESTIONS,
        )
        if runtime.auto_end_max_questions < runtime.auto_end_min_questions:
            runtime.auto_end_max_questions = runtime.auto_end_min_questions
        runtime.forced_question_id = ''
        runtime.forced_question_text = ''
        runtime.forced_question_meta = {}
        if selected_question:
            runtime.forced_question_id = str(selected_question.get('id') or '').strip()
            runtime.forced_question_text = str(selected_question.get('question') or '').strip()
            runtime.forced_question_meta = {
                'category': str(selected_question.get('category') or '').strip(),
                'source': 'manual_selected_question',
            }
        # 先创建会话主记录，确保后续结构化评估入库不会触发外键失败
        try:
            db_manager.save_interview({
                'interview_id': runtime.interview_id,
                'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': None,
                'duration': 0,
                'max_probability': None,
                'avg_probability': None,
                'risk_level': 'LOW',
                'events_count': 0,
                'report_path': ''
            })
        except Exception as e:
            logger.warning(f"会话主记录预创建失败：{e}")
        _log_runtime_event(
            runtime,
            'session_start',
            requested_round_type=round_type,
            requested_position=position,
            requested_difficulty=difficulty,
            training_mode=training_mode,
            forced_question_mode=bool(runtime.forced_question_text),
            forced_question_id=runtime.forced_question_id,
            forced_question_preview=(runtime.forced_question_text or '')[:120],
        )

        if runtime.data_manager:
            runtime.data_manager.reset()
            runtime.data_manager.start_interview()

        if llm_manager:
            resume_data = llm_manager.load_resume_data(user_id)
            runtime.resume_data = resume_data
            llm_manager.set_interview_round(round_type, resume_data)

        if rag_service is not None and getattr(rag_service, 'enabled', False):
            runtime.interview_state = rag_service.create_interview_state(
                role=position,
                round_type=round_type,
                difficulty=difficulty,
                session_id=session_id
            )
            if runtime.resume_data:
                runtime.interview_state = rag_service.attach_resume_to_state(
                    runtime.interview_state,
                    runtime.resume_data
                )

        if runtime_stale():
            _log_runtime_event(
                runtime,
                'session_start_aborted',
                level='debug',
                reason='runtime_replaced_before_initial_question',
            )
            return

        _emit_orchestrator_state(runtime)

        # 不在 session_start 阶段持有真实流式 ASR 连接。流式识别连接长时间空转后
        # 容易把第一段正式音频放进一个陈旧解码上下文；正式流在 speech_start 时创建。

        initial_question = runtime.forced_question_text or ""
        initial_question_context = _build_initial_interview_context(
            round_type=round_type,
            position=position,
            difficulty=difficulty,
            training_mode=runtime.training_mode,
        )
        if llm_manager:
            if runtime.forced_question_text:
                runtime.last_question_plan = _build_forced_question_plan(
                    question_id=runtime.forced_question_id,
                    question_text=runtime.forced_question_text,
                    round_type=round_type,
                    position=position,
                    difficulty=difficulty,
                    category=(runtime.forced_question_meta or {}).get('category', ''),
                )
                runtime.last_answer_analysis = None
            else:
                rag_context, question_plan = _build_question_rag_context(
                    position=position,
                    difficulty=difficulty,
                    round_type=round_type,
                    context=initial_question_context,
                    interview_state=runtime.interview_state
                )
                runtime.last_question_plan = question_plan
                reference_question = _extract_question_text_from_plan(question_plan)
                initial_question = llm_manager.generate_round_question(
                    round_type=round_type,
                    position=position,
                    difficulty=difficulty,
                    context=initial_question_context,
                    rag_context=rag_context,
                    reference_question=reference_question,
                )
                if question_plan and rag_service is not None and getattr(rag_service, 'enabled', False):
                    runtime.interview_state = rag_service.mark_question_asked(
                        runtime.interview_state,
                        question_plan
                    )
                    runtime.last_answer_analysis = None

        if runtime_stale():
            _log_runtime_event(
                runtime,
                'session_start_aborted',
                level='debug',
                reason='runtime_replaced_after_initial_question',
            )
            return

        runtime = session_registry.get(client_id) or runtime
        should_use_intro_turn = (
            str(runtime.training_mode or '').strip().lower() == 'realistic_mock'
            and not str(runtime.forced_question_text or '').strip()
        )
        queued_formal_question = str(initial_question or '').strip()
        if should_use_intro_turn and not queued_formal_question:
            queued_formal_question = _build_fallback_first_formal_question(
                round_type=round_type,
                position=position,
            )
        if should_use_intro_turn:
            runtime.pending_formal_question = queued_formal_question
            runtime.pending_formal_question_plan = runtime.last_question_plan
            initial_question = _build_intro_only_interviewer_message(
                round_type=round_type,
                position=position,
            )
        elif not queued_formal_question:
            initial_question = "请先做一个简短自我介绍，然后我们进入正式提问。"
        else:
            initial_question = _compose_initial_interviewer_message(
                question_text=queued_formal_question,
                round_type=round_type,
                position=position,
                training_mode=runtime.training_mode,
            )

        normalized_question = speech_normalizer.normalize(initial_question)
        runtime.next_turn()
        _set_runtime_asr_lock(runtime, False)
        runtime.current_question_kind = 'intro' if should_use_intro_turn else 'formal'
        runtime.current_question = normalized_question['display_text']
        if runtime.current_question_kind == 'formal':
            runtime.current_question_core = str(queued_formal_question or '').strip() or _extract_runtime_question_core(
                normalized_question['display_text'],
                fallback=normalized_question['display_text'],
            )
            runtime.current_question = runtime.current_question_core
        else:
            runtime.current_question_core = normalized_question['display_text']
        if runtime.current_question_kind == 'formal':
            runtime.formal_question_count += 1
            runtime.topic_question_count += 1
        _track_question_timeline(runtime, runtime.turn_id, normalized_question['spoken_text'] or normalized_question['display_text'])
        runtime.chat_history.append({
            'role': 'interviewer',
            'content': normalized_question['display_text']
        })

        _log_runtime_event(
            runtime,
            'dialog_reply_emit',
            job_id='session_start',
            next_turn_id=runtime.turn_id,
            display_preview=normalized_question['display_text'][:160],
            spoken_preview=normalized_question['spoken_text'][:160],
        )
        socketio.emit('dialog_reply', {
            'session_id': runtime.session_id,
            'turn_id': runtime.turn_id,
            'job_id': 'session_start',
            'display_text': normalized_question['display_text'],
            'spoken_text': normalized_question['spoken_text'],
            'analysis': None,
            'followup_decision': None,
            'interrupt_epoch': runtime.interrupt_epoch,
            'source': 'session_start',
            'timestamp': time.time()
        }, to=client_id)

        if runtime_stale():
            _log_runtime_event(
                runtime,
                'session_start_aborted',
                level='debug',
                reason='runtime_replaced_before_tts_start',
            )
            return

        _start_runtime_tts(runtime, normalized_question['spoken_text'], runtime.turn_id, source='session_start')
        logger.info(f"✓ 新会话已启动 - session_id={runtime.session_id}, client_id={client_id}")
    except Exception as e:
        logger.error(f"启动新会话错误：{e}", exc_info=True)
        _emit_pipeline_error(client_id, '', 'SESSION_START_ERROR', 'Failed to start session', str(e))

def _finalize_video_upload_async(upload_id: str, interview_id: str):
    try:
        finalize_payload = video_upload_service.finalize_upload(
            upload_id=upload_id,
            interview_id=interview_id,
        )
        if finalize_payload.get('success'):
            db_manager.save_or_update_interview_asset({
                'interview_id': interview_id,
                'upload_id': upload_id,
                'storage_key': Path(finalize_payload.get('final_path', '')).name,
                'video_url': '',
                'local_path': finalize_payload.get('final_path', ''),
                'duration_ms': finalize_payload.get('duration_ms', 0),
                'codec': finalize_payload.get('codec', ''),
                'status': finalize_payload.get('status', 'uploaded'),
                'metadata_json': json.dumps({
                    'raw_path': finalize_payload.get('raw_path', ''),
                }, ensure_ascii=False),
            })
            return

        error = str(finalize_payload.get('error', '')).strip()
        if error != 'upload_not_found':
            logger.warning("Video finalize fallback failed for upload_id=%s: %s", upload_id, error)
    except Exception as exc:
        logger.warning("Video finalize fallback crashed for upload_id=%s: %s", upload_id, exc, exc_info=True)


@socketio.on('session_end')
@rate_limit(interview_rate_limiter)
def handle_session_end(data=None):
    client_id = request.sid
    runtime = _get_runtime(client_id, str((data or {}).get('session_id', '')).strip())
    if not runtime:
        return

    try:
        _log_runtime_event(runtime, 'session_end_requested')
        upload_id = str((data or {}).get('video_upload_id', '')).strip()
        if upload_id:
            socketio.start_background_task(
                _finalize_video_upload_async,
                upload_id,
                runtime.interview_id,
            )
            finalize_payload = {'success': False}
            if False:
                db_manager.save_or_update_interview_asset({
                    'interview_id': runtime.interview_id,
                    'upload_id': upload_id,
                    'storage_key': Path(finalize_payload.get('final_path', '')).name,
                    'video_url': '',
                    'local_path': finalize_payload.get('final_path', ''),
                    'duration_ms': finalize_payload.get('duration_ms', 0),
                    'codec': finalize_payload.get('codec', ''),
                    'status': finalize_payload.get('status', 'uploaded'),
                    'metadata_json': json.dumps({
                        'raw_path': finalize_payload.get('raw_path', ''),
                    }, ensure_ascii=False),
                })
            else:
                logger.warning(f"会话结束时自动 finalize 视频失败：{finalize_payload.get('error', '')}")

        runtime.ended = True
        if runtime.pending_commit_timer:
            runtime.pending_commit_timer.cancel()
            runtime.pending_commit_timer = None
        _cancel_answer_finalize_timer(runtime)
        _reset_pending_asr_audio(runtime)
        if asr_manager and runtime.active_asr_stream_id:
            asr_manager.stop_session(runtime.active_asr_stream_id)

        if runtime.data_manager:
            runtime.data_manager.end_interview()
            report_data = runtime.data_manager.export_for_report()
        else:
            report_data = {}

        report_path = ""
        if report_data:
            try:
                report_path = report_generator.generate_report(report_data)
            except Exception as exc:
                report_path = ""
                logger.warning(f"检测报告落盘失败，报告页将只能展示摘要统计：{exc}")
            derived_events, derived_stats = _derive_detection_events_and_stats(report_data)
            risk_stats = report_data.get('statistics') if isinstance(report_data.get('statistics'), dict) else {}
            max_probability = _normalize_risk_probability(risk_stats.get('max_probability'))
            avg_probability = _normalize_risk_probability(risk_stats.get('avg_probability'))
            risk_level = _risk_level_from_probability(max_probability)
            db_manager.save_interview({
                'interview_id': runtime.interview_id,
                'start_time': report_data.get('summary', {}).get('start_time'),
                'end_time': report_data.get('summary', {}).get('end_time'),
                'duration': report_data.get('summary', {}).get('duration', 0),
                'max_probability': max_probability,
                'avg_probability': avg_probability,
                'risk_level': risk_level,
                'events_count': len(derived_events),
                'report_path': report_path
            })
            if derived_events:
                db_manager.save_events(runtime.interview_id, derived_events)
            if derived_stats:
                db_manager.save_statistics(runtime.interview_id, derived_stats)

        state_orchestrator.begin_listening(runtime)
        runtime.mode = 'ended'
        _log_runtime_event(runtime, 'session_end_completed', report_path=report_path)
        _maybe_enqueue_replay_generation(runtime.interview_id, force=False)
        _maybe_enqueue_behavior_analysis(runtime.interview_id, force=False)
        _emit_orchestrator_state(runtime)
        emit('interview_ended', {
            'message': 'Interview session ended',
            'report_path': report_path,
            'session_id': runtime.session_id,
            'interview_id': runtime.interview_id,
            'timestamp': time.time(),
            'success': True
        })
    except Exception as e:
        logger.error(f"结束新会话错误：{e}", exc_info=True)
        _emit_pipeline_error(client_id, runtime.session_id, 'SESSION_END_ERROR', 'Failed to end session', str(e))
    finally:
        session_registry.remove(client_id)


@socketio.on('speech_start')
def handle_speech_start(data=None):
    client_id = request.sid
    runtime = _get_runtime(client_id, str((data or {}).get('session_id', '')).strip())
    if not runtime:
        return

    if runtime.asr_locked:
        _log_runtime_event(
            runtime,
            'speech_start_ignored',
            level='debug',
            requested_turn_id=str((data or {}).get('turn_id', '')).strip(),
            reason='asr_locked',
            lock_reason=runtime.asr_lock_reason,
        )
        return

    raw_client_speech_epoch = (data or {}).get('speech_epoch', 0)
    try:
        client_speech_epoch = int(raw_client_speech_epoch or 0)
    except Exception:
        client_speech_epoch = 0

    if client_speech_epoch > 0:
        if client_speech_epoch <= int(getattr(runtime, 'client_speech_epoch', 0) or 0):
            _log_runtime_event(
                runtime,
                'speech_start_ignored',
                level='debug',
                requested_turn_id=str((data or {}).get('turn_id', '')).strip(),
                client_speech_epoch=client_speech_epoch,
                latest_client_speech_epoch=runtime.client_speech_epoch,
                reason='stale_or_duplicate_client_speech_epoch',
            )
            return
        runtime.client_speech_epoch = client_speech_epoch
        runtime.active_client_speech_epoch = client_speech_epoch

    if runtime.active_asr_generation:
        _log_runtime_event(
            runtime,
            'speech_start_ignored',
            level='debug',
            requested_turn_id=str((data or {}).get('turn_id', '')).strip(),
            speech_epoch=runtime.speech_epoch,
            asr_generation=runtime.active_asr_generation,
            reason='asr_generation_active',
        )
        return

    runtime.speech_epoch += 1
    if runtime.current_answer_started_at is None:
        runtime.current_answer_started_at = time.time()
    _log_runtime_event(
        runtime,
        'speech_start',
        requested_turn_id=str((data or {}).get('turn_id', '')).strip(),
        speech_epoch=runtime.speech_epoch,
        client_speech_epoch=client_speech_epoch or '',
    )
    _interrupt_runtime(runtime, 'speech_start')
    _reset_pending_asr_audio(runtime)
    answer_session = _ensure_answer_session(runtime)
    answer_session.mark_status('recording')
    _emit_realtime_speech_metrics(
        runtime,
        answer_session,
        is_speaking=True,
        text_snapshot=answer_session.live_text or answer_session.merged_text_draft,
        source='speech_start',
    )
    _emit_answer_session_update(runtime, source='speech_start')
    _start_runtime_asr(runtime, reason='speech_start')


@socketio.on('manual_interrupt')
def handle_manual_interrupt(data=None):
    client_id = request.sid
    runtime = _get_runtime(client_id, str((data or {}).get('session_id', '')).strip())
    if not runtime:
        return

    _log_runtime_event(runtime, 'manual_interrupt')
    _interrupt_runtime(runtime, 'manual_interrupt')


@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    client_id = request.sid
    runtime = _get_runtime(client_id, str((data or {}).get('session_id', '')).strip())
    if not runtime or asr_manager is None:
        return

    try:
        if not data or 'audio' not in data:
            return

        if runtime.asr_locked:
            return

        if not runtime.asr_available:
            return

        if (
            not runtime.active_asr_generation
            or not runtime.active_asr_stream_id
        ):
            return

        audio_base64 = data.get('audio', '')
        if audio_base64:
            audio_data = base64.b64decode(audio_base64)
            answer_session = runtime.current_answer_session
            if answer_session and answer_session.turn_id == runtime.turn_id and answer_session.status != 'finalized':
                answer_session.add_audio_chunk(audio_data)

            if asr_manager.is_available(runtime.active_asr_stream_id):
                _flush_pending_asr_audio(runtime, asr_generation=runtime.active_asr_generation)
                if not asr_manager.send_audio(runtime.active_asr_stream_id, audio_data):
                    _enqueue_pending_asr_audio(runtime, audio_data)
            else:
                _enqueue_pending_asr_audio(runtime, audio_data)
    except Exception as e:
        logger.error(f"处理 audio_chunk 错误：{e}", exc_info=True)
        _emit_pipeline_error(client_id, runtime.session_id, 'AUDIO_CHUNK_ERROR', 'Failed to process audio chunk', str(e))


@socketio.on('speech_end')
def handle_speech_end(data=None):
    client_id = request.sid
    runtime = _get_runtime(client_id, str((data or {}).get('session_id', '')).strip())
    if not runtime:
        return

    raw_client_speech_epoch = (data or {}).get('speech_epoch', 0)
    try:
        client_speech_epoch = int(raw_client_speech_epoch or 0)
    except Exception:
        client_speech_epoch = 0

    active_client_speech_epoch = int(getattr(runtime, 'active_client_speech_epoch', 0) or 0)
    if (
        client_speech_epoch > 0
        and active_client_speech_epoch > 0
        and client_speech_epoch != active_client_speech_epoch
    ):
        _log_runtime_event(
            runtime,
            'speech_end_ignored',
            level='debug',
            requested_turn_id=str((data or {}).get('turn_id', '')).strip(),
            client_speech_epoch=client_speech_epoch,
            active_client_speech_epoch=active_client_speech_epoch,
            reason='stale_client_speech_epoch',
        )
        return

    asr_generation, speech_epoch = _finalize_runtime_asr(runtime, reason='speech_end')
    if client_speech_epoch > 0 and active_client_speech_epoch == client_speech_epoch:
        runtime.active_client_speech_epoch = 0
    _finalize_answer_segment(
        runtime,
        asr_generation=asr_generation,
        speech_epoch=speech_epoch,
        reason='speech_end',
    )
    _schedule_answer_session_finalize(
        runtime,
        reason='long_pause',
        asr_generation=asr_generation,
        speech_epoch=speech_epoch,
    )
    state_orchestrator.begin_listening(runtime)
    _log_runtime_event(
        runtime,
        'speech_end',
        requested_turn_id=str((data or {}).get('turn_id', '')).strip(),
        asr_generation=asr_generation or '',
        speech_epoch=speech_epoch or '',
        client_speech_epoch=client_speech_epoch or '',
    )
    _emit_orchestrator_state(runtime)


@socketio.on('utterance_commit')
def handle_utterance_commit(data=None):
    client_id = request.sid
    runtime = _get_runtime(client_id, str((data or {}).get('session_id', '')).strip())
    if not runtime:
        return

    turn_id = str((data or {}).get('turn_id', '')).strip() or runtime.turn_id
    text_override = str((data or {}).get('text', '')).strip()
    source = str((data or {}).get('source', 'asr')).strip() or 'asr'

    if source == 'asr' and not text_override:
        _cancel_answer_finalize_timer(runtime)
        _finalize_answer_session(runtime, reason='utterance_commit')
        return

    if source == 'manual':
        _cancel_answer_finalize_timer(runtime)
        manual_asr_generation = 0
        if runtime.active_asr_generation:
            manual_asr_generation, _ = _finalize_runtime_asr(runtime, reason='manual_submit')
            _consume_runtime_segment_text(runtime, asr_generation=manual_asr_generation)
        _set_runtime_asr_lock(runtime, True, 'manual_submit')
        answer_session = runtime.current_answer_session
        if answer_session and answer_session.turn_id == turn_id and not answer_session.committed:
            final_text = (text_override or answer_session.merged_text_draft or answer_session.live_text).strip()
            audio_path = _persist_answer_audio(runtime, answer_session)
            answer_session.mark_final(final_text, reason='manual_submit', exported_audio_path=audio_path)
            try:
                _build_answer_session_final_metrics(
                    runtime,
                    answer_session,
                    audio_path=audio_path,
                    final_text=answer_session.final_text or final_text,
                )
            except Exception as exc:
                logger.warning(f"手动提交语音指标计算失败：{exc}")
            _emit_realtime_speech_metrics(
                runtime,
                answer_session,
                is_speaking=False,
                text_snapshot=answer_session.final_text or final_text,
                source='manual_submit',
            )
            answer_session.committed = True
            _emit_answer_session_update(runtime, source='manual_commit')
        _emit_orchestrator_state(runtime)

    asr_generation = runtime.last_finalized_asr_generation if source == 'asr' and not text_override else 0
    _log_runtime_event(
        runtime,
        'utterance_commit_request',
        source=source,
        requested_turn_id=turn_id,
        has_text=bool(text_override),
        asr_generation=asr_generation or '',
    )
    _schedule_runtime_commit(
        runtime,
        turn_id,
        source,
        text_override=text_override,
        asr_generation=asr_generation,
    )


@socketio.on('detection_state')
def handle_detection_state(data=None):
    client_id = request.sid
    runtime = _get_runtime(client_id, str((data or {}).get('session_id', '')).strip())
    if not runtime:
        return

    payload = dict(data or {})
    _log_runtime_event(
        runtime,
        'detection_state',
        level='debug',
        risk_level=payload.get('risk_level'),
        risk_score=payload.get('risk_score'),
        flags=','.join(payload.get('flags', []) or []),
    )
    notice_text = state_orchestrator.update_detection_state(runtime, payload)
    if runtime.data_manager:
        camera_insights = payload.get('camera_insights') if isinstance(payload.get('camera_insights'), dict) else {}
        runtime.data_manager.add_frame_data({
            'type': 'detection_state',
            'probability': float(payload.get('risk_score', 0) or 0),
            'risk_score': float(payload.get('risk_score', 0) or 0),
            'risk_level': payload.get('risk_level', 'LOW'),
            'has_face': payload.get('has_face', True),
            'face_count': payload.get('face_count', 1),
            'off_screen_ratio': payload.get('off_screen_ratio', 0),
            'flags': payload.get('flags', []),
            # 兼容前端毫秒时间戳，缺失时回退服务端时间（秒）。
            'timestamp': payload.get('ts') or time.time(),
            'hr': payload.get('hr'),
            'rppg_reliable': bool(payload.get('rppg_reliable', False)),
            # 关键镜头指标：用于报告端聚合 3D 关键点/表情系数/头姿/虹膜追踪。
            'camera_insights': camera_insights,
            'landmark_count': payload.get('landmark_count', 0),
            'blendshape_count': payload.get('blendshape_count', 0),
            'gaze_drift_count': payload.get('gaze_drift_count', 0),
            'pitch': payload.get('pitch', 0),
            'yaw': payload.get('yaw', 0),
            'roll': payload.get('roll', 0),
            'speech_expressiveness': payload.get('speech_expressiveness', 0),
        })

    _emit_orchestrator_state(runtime)

    if notice_text:
        _maybe_emit_session_notice(runtime)


@socketio.on('llm_generate_question')
@rate_limit(interview_rate_limiter)
def handle_llm_generate_question(data):
    client_id = request.sid

    try:
        if llm_manager is None:
            emit('error', {
                'error': 'LLM is not initialized on server',
                'code': 'LLM_NOT_READY',
                'details': llm_import_error
            })
            return

        runtime = _get_runtime(client_id, str((data or {}).get('session_id', '')).strip())
        if not runtime:
            emit('error', {
                'error': 'Session runtime not found',
                'code': 'SESSION_NOT_FOUND'
            })
            return

        position = str((data or {}).get('position', runtime.position)).strip() or runtime.position
        difficulty = str((data or {}).get('difficulty', runtime.difficulty)).strip() or runtime.difficulty
        context = str((data or {}).get('context', '')).strip()
        round_type = runtime.round_type
        rag_context, question_plan = _build_question_rag_context(
            position=position,
            difficulty=difficulty,
            round_type=round_type,
            context=context,
            interview_state=runtime.interview_state
        )
        runtime.last_question_plan = question_plan
        reference_question = _extract_question_text_from_plan(question_plan)

        _log_runtime_event(runtime, 'llm_generate_question', position=position, difficulty=difficulty)

        emit('llm_generating', {
            'message': '正在生成问题...',
            'status': 'generating'
        })

        question = llm_manager.generate_interview_question(
            position=position,
            difficulty=difficulty,
            context=context,
            rag_context=rag_context,
            reference_question=reference_question,
        )

        if question:
            if question_plan and rag_service is not None and getattr(rag_service, 'enabled', False):
                runtime.interview_state = rag_service.mark_question_asked(
                    runtime.interview_state,
                    question_plan
                )
                runtime.last_answer_analysis = None
            if runtime.data_manager:
                runtime.data_manager.add_frame_data({
                    'type': 'interview_question',
                    'question': question,
                    'position': position,
                    'difficulty': difficulty,
                    'timestamp': time.time()
                })

            emit('llm_question', {
                'success': True,
                'session_id': runtime.session_id,
                'question': question,
                'position': position,
                'difficulty': difficulty,
                'timestamp': time.time()
            })

            _log_runtime_event(runtime, 'llm_question_emitted', question_preview=question[:160], position=position, difficulty=difficulty)
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


def _decode_speech_rows(raw_rows):
    decoded = []
    for row in raw_rows or []:
        item = dict(row)
        for key in ('word_timestamps_json', 'pause_events_json', 'filler_events_json', 'speech_metrics_final_json', 'realtime_metrics_json'):
            raw_value = item.get(key)
            if not raw_value:
                item[key.replace('_json', '')] = [] if key != 'speech_metrics_final_json' else {}
                continue
            try:
                parsed = json.loads(raw_value)
            except Exception:
                parsed = [] if key != 'speech_metrics_final_json' else {}
            item[key.replace('_json', '')] = parsed
        decoded.append(item)
    return decoded


def _decode_evaluation_rows(raw_rows):
    decoded = []
    for row in raw_rows or []:
        item = dict(row)
        for key in ('layer1_json', 'layer2_json', 'text_layer_json', 'speech_layer_json', 'video_layer_json', 'fusion_json', 'scoring_snapshot_json'):
            raw_value = item.get(key)
            if not raw_value:
                item[key.replace('_json', '')] = {}
                continue
            try:
                item[key.replace('_json', '')] = json.loads(raw_value)
            except Exception:
                item[key.replace('_json', '')] = {}
        decoded.append(item)
    return decoded


def _filter_evaluation_rows_by_dialogues(decoded_rows, dialogues):
    """按当前会话 turn_id 过滤评估记录；若完全不匹配则回退到原始记录。"""
    rows = list(decoded_rows or [])
    if not rows:
        return rows

    valid_turn_ids = {
        str(item.get('turn_id') or '').strip()
        for item in (dialogues or [])
        if str(item.get('turn_id') or '').strip()
    }
    if not valid_turn_ids:
        return rows

    matched_rows = [
        row for row in rows
        if str(row.get('turn_id') or '').strip() in valid_turn_ids
    ]
    # 兼容历史数据：例如 backfill 生成 legacy_dialogue_xxx，不与 turn_id 对齐。
    return matched_rows if matched_rows else rows


def _decode_evaluation_traces(raw_rows):
    decoded = []
    for row in raw_rows or []:
        item = dict(row)
        raw_payload = item.get('payload_json')
        if raw_payload:
            try:
                item['payload'] = json.loads(raw_payload)
            except Exception:
                item['payload'] = {}
        else:
            item['payload'] = {}
        decoded.append(item)
    return decoded


def _normalize_turn_scorecard(scorecard):
    payload = dict(scorecard or {})

    evaluation = payload.get('evaluation')
    if evaluation:
        decoded = _decode_evaluation_rows([evaluation])
        payload['evaluation'] = decoded[0] if decoded else dict(evaluation)

    speech = payload.get('speech_evaluation')
    if speech:
        decoded = _decode_speech_rows([speech])
        payload['speech_evaluation'] = decoded[0] if decoded else dict(speech)

    payload['traces'] = _decode_evaluation_traces(payload.get('traces') or [])
    return payload


def _score_to_level(score: float) -> str:
    score = float(score or 0.0)
    if score >= 85:
        return 'excellent'
    if score >= 70:
        return 'good'
    if score >= 55:
        return 'developing'
    return 'basic'


def _safe_avg(values):
    valid = [float(v) for v in values if isinstance(v, (int, float))]
    return (sum(valid) / len(valid)) if valid else 0.0


def _build_final_score_snapshot(structured_snapshot, evaluation_v2):
    """将直接融合分和稳定化分合成为报告最终展示分。"""
    fusion_score = _safe_float(((evaluation_v2 or {}).get('fusion') or {}).get('overall_score'), None)
    round_aggregation = (structured_snapshot or {}).get('round_aggregation') if isinstance((structured_snapshot or {}).get('round_aggregation'), dict) else {}
    stability = (round_aggregation or {}).get('interview_stability') if isinstance((round_aggregation or {}).get('interview_stability'), dict) else {}
    stable_score = _safe_float((stability or {}).get('overall_score_stable'), None)
    structured_score = _safe_float((structured_snapshot or {}).get('overall_score'), None)

    if fusion_score is not None and stable_score is not None:
        overall_score = round(
            float(fusion_score) * FINAL_SCORE_DIRECT_FUSION_WEIGHT
            + float(stable_score) * FINAL_SCORE_STABLE_WEIGHT,
            1,
        )
        source = 'stable_fusion_blend'
    elif stable_score is not None:
        overall_score = round(float(stable_score), 1)
        source = 'round_stability'
    elif fusion_score is not None:
        overall_score = round(float(fusion_score), 1)
        source = 'direct_fusion'
    elif structured_score is not None:
        overall_score = round(float(structured_score), 1)
        source = 'structured_content'
    else:
        overall_score = None
        source = 'pending'

    return {
        'overall_score': overall_score,
        'source': source,
        'formula': (
            f'final = {FINAL_SCORE_STABLE_WEIGHT:.2f} * round_aggregation.interview_stability.overall_score_stable '
            f'+ {FINAL_SCORE_DIRECT_FUSION_WEIGHT:.2f} * evaluation_v2.fusion.overall_score'
        ),
        'components': {
            'fusion_overall_score': fusion_score,
            'stable_overall_score': stable_score,
            'structured_overall_score': structured_score,
        },
        'weights': {
            'stable': FINAL_SCORE_STABLE_WEIGHT,
            'fusion': FINAL_SCORE_DIRECT_FUSION_WEIGHT,
        },
    }


def _build_round_aggregation_snapshot(interview_id: str, decoded_rows=None, dialogues=None):
    rows = list(decoded_rows or [])
    if not rows:
        return {
            'status': 'empty',
            'status_message': 'no round aggregation data',
            'round_profiles': [],
            'interview_stability': {
                'overall_score_raw': None,
                'overall_score_stable': None,
                'round_count': 0,
                'avg_consistency_score': None,
                'outlier_turn_count': 0,
                'dominant_round_type': None,
            },
            'calibration_version': 'cross_turn_calibrator_v1',
            'stabilizer_version': 'round_stabilizer_v1',
        }

    question_lookup = {
        str(item.get('turn_id') or '').strip(): str(item.get('question') or '').strip()
        for item in (dialogues or [])
        if str(item.get('turn_id') or '').strip()
    }
    round_types = {
        str(row.get('round_type') or 'unknown').strip() or 'unknown'
        for row in rows
    }
    baseline_rows_by_round = {}
    if hasattr(db_manager, 'get_recent_interview_evaluations_by_round'):
        for round_type in round_types:
            raw_baseline_rows = db_manager.get_recent_interview_evaluations_by_round(
                round_type=round_type,
                exclude_interview_id=interview_id,
                limit=300,
            ) or []
            baseline_rows_by_round[round_type] = _decode_evaluation_rows(raw_baseline_rows)

    return build_round_aggregation(
        current_rows=rows,
        baseline_rows_by_round=baseline_rows_by_round,
        question_lookup=question_lookup,
    )


def _safe_float(value, default=0.0):
    try:
        if value is None:
            if default is None:
                return None
            return float(default)
        return float(value)
    except Exception:
        if default is None:
            return None
        return float(default)


def _dimension_label_map():
    return {
        'technical_accuracy': '技术准确性',
        'knowledge_depth': '知识深度',
        'completeness': '回答完整度',
        'logic': '逻辑严谨性',
        'job_match': '岗位匹配度',
        'authenticity': '项目真实性',
        'ownership': '项目 ownership',
        'technical_depth': '项目技术深度',
        'reflection': '复盘反思',
        'architecture_reasoning': '架构推理',
        'tradeoff_awareness': '权衡意识',
        'scalability': '扩展性设计',
        'clarity': '表达清晰度',
        'relevance': '回答相关性',
        'self_awareness': '自我认知',
        'communication': '沟通表现',
    }


def _filter_content_dimensions_by_round(round_type, dimension_map):
    normalized_round = str(round_type or '').strip().lower()
    if not isinstance(dimension_map, dict):
        return {}

    filtered = {}
    for dim_key, dim_payload in dimension_map.items():
        if not isinstance(dim_payload, dict):
            continue

        normalized_key = str(dim_key or '').strip().lower()
        if normalized_round == 'system_design' and normalized_key == 'clarity':
            # 系统设计轮次不再将 clarity 归入内容轴，避免和表达轴重复并造成结构性偏低。
            continue

        filtered[dim_key] = dim_payload

    return filtered


def _compact_text(value, limit=120):
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if len(text) <= limit:
        return text
    clipped = text[:max(0, int(limit) - 1)].rstrip()
    return f'{clipped}…'


def _classify_reason_tags(dim_key: str, reason_text: str):
    dim = str(dim_key or '').strip().lower()
    reason = str(reason_text or '').strip()
    merged = f"{dim} {reason}"
    merged_lower = merged.lower()

    tags = set()
    dim_to_tag = {
        'technical_accuracy': '技术',
        'knowledge_depth': '技术',
        'job_match': '技术',
        'authenticity': '技术',
        'ownership': '技术',
        'technical_depth': '技术',
        'architecture_reasoning': '技术',
        'tradeoff_awareness': '技术',
        'scalability': '技术',
        'clarity': '表达',
        'relevance': '表达',
        'communication': '表达',
        'logic': '结构',
        'completeness': '结构',
        'reflection': '结构',
        'self_awareness': '结构',
    }
    if dim in dim_to_tag:
        tags.add(dim_to_tag[dim])

    tech_keywords = [
        '技术', '算法', '架构', '原理', '准确', '深度', '实现', '扩展', 'tradeoff', 'scalability',
        'technical', 'knowledge', 'authenticity', 'ownership', 'job match',
    ]
    expression_keywords = [
        '表达', '沟通', '清晰', '语速', '停顿', '口头词', '流畅', 'clarity', 'communication',
        'speech', 'fluency', 'filler', 'pause', 'relevance',
    ]
    structure_keywords = [
        '结构', '逻辑', '完整', '条理', '结论', '框架', '组织', 'completeness', 'logic',
        'structure', 'reasoning', 'reflection', 'self-awareness',
    ]

    if any(keyword in merged for keyword in tech_keywords if any('\u4e00' <= ch <= '\u9fff' for ch in keyword)) or any(keyword in merged_lower for keyword in tech_keywords if not any('\u4e00' <= ch <= '\u9fff' for ch in keyword)):
        tags.add('技术')
    if any(keyword in merged for keyword in expression_keywords if any('\u4e00' <= ch <= '\u9fff' for ch in keyword)) or any(keyword in merged_lower for keyword in expression_keywords if not any('\u4e00' <= ch <= '\u9fff' for ch in keyword)):
        tags.add('表达')
    if any(keyword in merged for keyword in structure_keywords if any('\u4e00' <= ch <= '\u9fff' for ch in keyword)) or any(keyword in merged_lower for keyword in structure_keywords if not any('\u4e00' <= ch <= '\u9fff' for ch in keyword)):
        tags.add('结构')

    if not tags:
        tags.add('结构')
    return [tag for tag in ('技术', '表达', '结构') if tag in tags]


def _content_token_count(text: str) -> int:
    content = str(text or '').strip()
    if not content:
        return 0
    return len(re.findall(r'[A-Za-z0-9_]+|[\u4e00-\u9fff]', content))


def _question_echo_ratio(question: str, answer: str) -> float:
    question_tokens = set(re.findall(r'[A-Za-z0-9_]+|[\u4e00-\u9fff]', str(question or '').lower()))
    answer_tokens = set(re.findall(r'[A-Za-z0-9_]+|[\u4e00-\u9fff]', str(answer or '').lower()))
    if not question_tokens or not answer_tokens:
        return 0.0
    return len(question_tokens & answer_tokens) / max(1, len(answer_tokens))


def _iter_dimension_evidence_items(final_dims):
    for dim_payload in (final_dims or {}).values():
        if not isinstance(dim_payload, dict):
            continue
        evidence = dim_payload.get('evidence') if isinstance(dim_payload.get('evidence'), dict) else {}
        yield dim_payload, evidence


def _detect_content_sample_quality(question: str, answer: str, layer1, final_dims):
    """区分真实低分回答和误收环境音/未作答样本，避免把后者画成能力画像。"""
    answer_text = str(answer or '').strip()
    layer1 = layer1 if isinstance(layer1, dict) else {}
    final_dims = final_dims if isinstance(final_dims, dict) else {}

    scores = []
    hit_count = 0
    no_content_reason_count = 0
    for dim_payload, evidence in _iter_dimension_evidence_items(final_dims):
        score = (dim_payload or {}).get('score')
        if isinstance(score, (int, float)):
            scores.append(float(score))
        hit_count += len(evidence.get('hit_rubric_points') or [])
        reason_text = f"{dim_payload.get('reason') or ''} {evidence.get('deduction_rationale') or ''}"
        if any(marker in reason_text for marker in ('没有提供', '没有提到', '没有回答', '未提供', '未提及', '未能提供', '完全没有', '无任何', '缺乏实质')):
            no_content_reason_count += 1

    key_points = layer1.get('key_points') if isinstance(layer1.get('key_points'), dict) else {}
    covered_points = key_points.get('covered') or []
    coverage_ratio = _safe_float(key_points.get('coverage_ratio'), 0.0)
    signals = layer1.get('signals') if isinstance(layer1.get('signals'), dict) else {}
    hit_count += len(signals.get('hit') or [])

    avg_score = _safe_avg(scores) if scores else 0.0
    token_count = _content_token_count(answer_text)
    echo_ratio = _question_echo_ratio(question, answer_text)
    answer_lower = answer_text.lower()
    non_answer_patterns = [
        '不知道',
        '不确定',
        '没听清',
        '没准备好',
        '还没开始',
        '等一等',
        '让我看一下',
        '啥问题',
        '咋突然开始面试',
        '请你现在回答我的问题',
        'hello',
        '哈喽',
    ]
    # Only flag as non-answer if the pattern dominates the answer (short text or pattern at start)
    has_non_answer_marker = False
    for pattern in non_answer_patterns:
        if pattern in answer_text or pattern in answer_lower:
            if token_count <= 12 or answer_text.startswith(pattern) or answer_lower.startswith(pattern):
                has_non_answer_marker = True
                break
    has_positive_content_signal = bool(covered_points or coverage_ratio >= 0.1 or (hit_count > 0 and avg_score > 5.0))
    no_content_reason_threshold = max(2, int(len(final_dims or {}) * 0.5))
    has_no_content_reason = bool(no_content_reason_count >= no_content_reason_threshold)

    reasons = []
    if token_count < 8:
        reasons.append('answer_too_short')
    if has_non_answer_marker:
        reasons.append('non_answer_marker')
    if echo_ratio >= 0.68 and token_count <= 36:
        reasons.append('mostly_repeats_question')
    if avg_score <= 5.0 and coverage_ratio <= 0.05 and not has_positive_content_signal:
        reasons.append('zero_content_match')
    if has_no_content_reason:
        reasons.append('no_content_reason')

    ineffective = (
        avg_score <= 5.0
        and coverage_ratio <= 0.05
        and not has_positive_content_signal
        and (
            has_non_answer_marker
            or token_count < 8
            or (echo_ratio >= 0.68 and token_count <= 36)
            or has_no_content_reason
        )
    )

    return {
        'effective': not ineffective,
        'reasons': reasons,
        'avg_score': round(float(avg_score), 1),
        'coverage_ratio': round(float(coverage_ratio), 4),
        'token_count': int(token_count),
        'question_echo_ratio': round(float(echo_ratio), 4),
    }


def _is_fallback_scored_evaluation(row, layer2) -> bool:
    """识别启发式回退评分，避免把它当作可追溯语义依据。"""
    status = str((row or {}).get('status') or '').strip().lower()
    error_code = str((row or {}).get('error_code') or '').strip().upper()
    error_message = str((row or {}).get('error_message') or '').strip()
    layer2 = layer2 if isinstance(layer2, dict) else {}
    mode = str(layer2.get('evaluation_mode') or '').strip().lower()
    note = str(layer2.get('evaluation_note') or '').strip().lower()
    rubric_reason = str(((layer2.get('rubric_eval') or {}) if isinstance(layer2.get('rubric_eval'), dict) else {}).get('reason') or '').strip()
    dim_reasons = [
        str((payload or {}).get('reason') or '').strip()
        for payload in ((layer2.get('final_dimension_scores') or layer2.get('dimension_scores') or {}) if isinstance(layer2.get('final_dimension_scores') or layer2.get('dimension_scores'), dict) else {}).values()
        if isinstance(payload, dict)
    ]
    fallback_reason_count = sum(1 for reason in dim_reasons if '回退评分' in reason or '文本长度与结构' in reason)
    return bool(
        mode.startswith('heuristic')
        or 'fallback' in mode
        or 'fallback' in note
        or (status == 'partial_ok' and error_code.startswith('LAYER2'))
        or ('Expecting' in error_message and 'delimiter' in error_message)
        or '回退评分' in rubric_reason
        or (dim_reasons and fallback_reason_count >= max(1, int(len(dim_reasons) * 0.6)))
    )


def _normalize_event_offset_seconds(timestamp_value, started_at):
    """将事件时间标准化为“会话内偏移秒”；若无法判断则回退原值。"""
    raw_seconds = float(timestamp_value or 0.0)
    if raw_seconds <= 0:
        return 0.0
    # 大于该阈值通常是 Unix 时间戳（秒）。
    if raw_seconds > 1_000_000 and started_at is not None:
        try:
            session_start_epoch = float(started_at.timestamp())
            return max(0.0, raw_seconds - session_start_epoch)
        except Exception:
            return raw_seconds
    return raw_seconds


def _load_detection_timeline_from_report(report_file_path: Path):
    if not report_file_path or not report_file_path.exists():
        return []
    try:
        with open(report_file_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
    except Exception as exc:
        logger.warning(f'读取报告时间轴失败: {report_file_path} | {exc}')
        return []

    timeline = payload.get('timeline') if isinstance(payload, dict) else []
    if not isinstance(timeline, list):
        return []

    return [
        item for item in timeline
        if isinstance(item, dict) and str(item.get('type') or '').strip() == 'detection_state'
    ]


def _build_camera_insights_snapshot_from_timeline(timeline):
    rows = [item for item in (timeline or []) if isinstance(item, dict)]
    if not rows:
        return {
            'sample_count': 0,
            'landmarks_3d': {},
            'blendshapes': {},
            'head_pose': {},
            'iris_tracking': {},
            'physiology': {},
        }

    landmark_counts = []
    mouth_open_ratios = []
    micro_variances = []
    face_distance_z = []

    blink_rates = []
    brow_inner_up = []
    smile_avg = []
    jaw_open_avg = []
    speech_expressiveness = []
    blendshape_count_values = []
    blendshape_averages_acc = {}

    abs_pitch_values = []
    abs_yaw_values = []
    abs_roll_values = []
    high_pose_frames = 0

    gaze_offsets = []
    gaze_focus_scores = []
    max_gaze_drift_count = 0
    last_gaze_drift = 0
    drift_jumps = 0

    gaze_focus_trend_full = []
    first_ts_sec = None
    low_focus_frames = 0
    min_focus_score = 100.0

    close_frames = 0
    far_frames = 0
    hr_values = []
    hr_out_of_range_frames = 0
    rppg_frames = 0
    rppg_reliable_frames = 0

    for item in rows:
        camera_insights = item.get('camera_insights') if isinstance(item.get('camera_insights'), dict) else {}
        landmarks = camera_insights.get('landmarks_3d') if isinstance(camera_insights.get('landmarks_3d'), dict) else {}
        blendshapes = camera_insights.get('blendshapes') if isinstance(camera_insights.get('blendshapes'), dict) else {}
        head_pose = camera_insights.get('head_pose') if isinstance(camera_insights.get('head_pose'), dict) else {}
        iris = camera_insights.get('iris_tracking') if isinstance(camera_insights.get('iris_tracking'), dict) else {}
        hr_raw = item.get('hr')
        try:
            hr_value = float(hr_raw) if hr_raw is not None else None
        except Exception:
            hr_value = None
        rppg_reliable = bool(item.get('rppg_reliable', False))

        landmark_count = int(_safe_float(landmarks.get('landmark_count'), _safe_float(item.get('landmark_count'), 0)))
        if landmark_count > 0:
            landmark_counts.append(landmark_count)

        mouth_ratio = landmarks.get('mouth_open_ratio')
        if not isinstance(mouth_ratio, (int, float)):
            mouth_ratio = item.get('mouth_open_ratio')
        if isinstance(mouth_ratio, (int, float)):
            mouth_open_ratios.append(float(mouth_ratio))

        micro_var = landmarks.get('micro_movement_variance')
        if not isinstance(micro_var, (int, float)):
            micro_var = item.get('micro_movement_variance')
        if isinstance(micro_var, (int, float)):
            micro_variances.append(float(micro_var))

        z_value = landmarks.get('face_distance_z')
        if not isinstance(z_value, (int, float)):
            z_value = item.get('face_distance_z')
        if isinstance(z_value, (int, float)):
            z = float(z_value)
            face_distance_z.append(z)
            if z < -0.12:
                close_frames += 1
            elif z > -0.02:
                far_frames += 1

        blend_count = int(_safe_float(blendshapes.get('available_count'), _safe_float(item.get('blendshape_count'), 0)))
        if blend_count > 0:
            blendshape_count_values.append(blend_count)

        blink_rate = blendshapes.get('blink_rate_per_min')
        if not isinstance(blink_rate, (int, float)):
            blink_rate = item.get('blink_rate_per_min')
        if isinstance(blink_rate, (int, float)):
            blink_rates.append(float(blink_rate))

        brow_value = blendshapes.get('brow_inner_up_avg')
        if not isinstance(brow_value, (int, float)):
            brow_value = item.get('brow_inner_up_avg')
        if isinstance(brow_value, (int, float)):
            brow_inner_up.append(float(brow_value))

        smile_value = blendshapes.get('smile_avg')
        if not isinstance(smile_value, (int, float)):
            smile_value = item.get('smile_avg')
        if isinstance(smile_value, (int, float)):
            smile_avg.append(float(smile_value))

        jaw_value = blendshapes.get('jaw_open_avg')
        if not isinstance(jaw_value, (int, float)):
            jaw_value = item.get('jaw_open_avg')
        if isinstance(jaw_value, (int, float)):
            jaw_open_avg.append(float(jaw_value))

        speech_value = blendshapes.get('speech_expressiveness')
        if not isinstance(speech_value, (int, float)):
            speech_value = item.get('speech_expressiveness')
        if isinstance(speech_value, (int, float)):
            speech_expressiveness.append(float(speech_value))

        blend_avg_map = blendshapes.get('averages') if isinstance(blendshapes.get('averages'), dict) else {}
        if not blend_avg_map:
            blend_avg_map = blendshapes.get('key_current') if isinstance(blendshapes.get('key_current'), dict) else {}
        for key, value in blend_avg_map.items():
            if not isinstance(value, (int, float)):
                continue
            blendshape_averages_acc.setdefault(str(key), []).append(float(value))

        pitch = abs(_safe_float(head_pose.get('pitch'), _safe_float(item.get('pitch'), 0.0)))
        yaw = abs(_safe_float(head_pose.get('yaw'), _safe_float(item.get('yaw'), 0.0)))
        roll = abs(_safe_float(head_pose.get('roll'), _safe_float(item.get('roll'), 0.0)))
        if pitch or yaw or roll:
            abs_pitch_values.append(pitch)
            abs_yaw_values.append(yaw)
            abs_roll_values.append(roll)
            if yaw >= 28 or pitch >= 20 or roll >= 20:
                high_pose_frames += 1

        gaze_offset_mag = iris.get('gaze_offset_magnitude')
        if not isinstance(gaze_offset_mag, (int, float)):
            gaze_offset_mag = item.get('gaze_offset_magnitude')
        if isinstance(gaze_offset_mag, (int, float)):
            gaze_offsets.append(float(gaze_offset_mag))

        if isinstance(hr_value, (int, float)):
            hr_values.append(float(hr_value))
            rppg_frames += 1
            if rppg_reliable:
                rppg_reliable_frames += 1
            if hr_value < 50 or hr_value > 120:
                hr_out_of_range_frames += 1

        gaze_focus = iris.get('gaze_focus_score')
        if not isinstance(gaze_focus, (int, float)):
            gaze_focus = item.get('gaze_focus_score')
        if isinstance(gaze_focus, (int, float)):
            gaze_focus_scores.append(float(gaze_focus))

        raw_off_screen = _safe_float(item.get('off_screen_ratio'), 0.0)
        off_screen_percent = raw_off_screen * 100.0 if raw_off_screen <= 1.0 else raw_off_screen

        gaze_focus_value = float(gaze_focus) if isinstance(gaze_focus, (int, float)) else max(0.0, 100.0 - off_screen_percent)
        gaze_focus_value = max(0.0, min(100.0, gaze_focus_value))
        if gaze_focus_value < 60.0:
            low_focus_frames += 1
        min_focus_score = min(min_focus_score, gaze_focus_value)

        raw_ts = _safe_float(item.get('timestamp'), 0.0)
        if raw_ts > 0:
            ts_sec = raw_ts / 1000.0 if raw_ts > 1_000_000_000_000 else raw_ts
            if first_ts_sec is None:
                first_ts_sec = ts_sec
            sec_offset = max(0.0, ts_sec - first_ts_sec)
        else:
            # detection_state 默认约 250ms 一帧，缺时间戳时按采样序号估算。
            sec_offset = len(gaze_focus_trend_full) * 0.25

        raw_risk_score = _safe_float(item.get('risk_score'), _safe_float(item.get('probability'), 0.0))
        risk_percent = raw_risk_score * 100.0 if raw_risk_score <= 1.0 else raw_risk_score
        risk_percent = max(0.0, min(100.0, risk_percent))

        gaze_focus_trend_full.append({
            'second': round(sec_offset, 1),
            'focus_score': round(gaze_focus_value, 2),
            'off_screen_ratio': round(max(0.0, min(100.0, off_screen_percent)), 2),
            'risk_score': round(risk_percent, 2),
        })

        drift_count = int(_safe_float(iris.get('drift_count'), _safe_float(item.get('gaze_drift_count'), 0)))
        max_gaze_drift_count = max(max_gaze_drift_count, drift_count)
        if drift_count > last_gaze_drift:
            drift_jumps += (drift_count - last_gaze_drift)
        last_gaze_drift = drift_count

    sample_count = len(rows)
    blendshape_averages = {
        key: round(_safe_avg(values), 4)
        for key, values in blendshape_averages_acc.items()
        if values
    }

    landmarks_snapshot = {
        'avg_landmark_count': round(_safe_avg(landmark_counts), 2) if landmark_counts else 0.0,
        'max_landmark_count': max(landmark_counts) if landmark_counts else 0,
        'avg_mouth_open_ratio': round(_safe_avg(mouth_open_ratios), 4) if mouth_open_ratios else 0.0,
        'avg_micro_movement_variance': round(_safe_avg(micro_variances), 6) if micro_variances else 0.0,
        'avg_face_distance_z': round(_safe_avg(face_distance_z), 6) if face_distance_z else 0.0,
        'close_ratio': round((close_frames / sample_count) * 100.0, 2) if sample_count else 0.0,
        'far_ratio': round((far_frames / sample_count) * 100.0, 2) if sample_count else 0.0,
    }

    blendshape_snapshot = {
        'tracked_count_max': max(blendshape_count_values) if blendshape_count_values else 0,
        'avg_blink_rate_per_min': round(_safe_avg(blink_rates), 2) if blink_rates else 0.0,
        'avg_brow_inner_up': round(_safe_avg(brow_inner_up), 4) if brow_inner_up else 0.0,
        'avg_smile': round(_safe_avg(smile_avg), 4) if smile_avg else 0.0,
        'avg_jaw_open': round(_safe_avg(jaw_open_avg), 4) if jaw_open_avg else 0.0,
        'avg_speech_expressiveness': round(_safe_avg(speech_expressiveness), 2) if speech_expressiveness else 0.0,
        'blendshape_averages': blendshape_averages,
    }

    head_pose_snapshot = {
        'avg_abs_pitch': round(_safe_avg(abs_pitch_values), 2) if abs_pitch_values else 0.0,
        'avg_abs_yaw': round(_safe_avg(abs_yaw_values), 2) if abs_yaw_values else 0.0,
        'avg_abs_roll': round(_safe_avg(abs_roll_values), 2) if abs_roll_values else 0.0,
        'high_pose_ratio': round((high_pose_frames / sample_count) * 100.0, 2) if sample_count else 0.0,
    }

    iris_snapshot = {
        'avg_gaze_offset_magnitude': round(_safe_avg(gaze_offsets), 4) if gaze_offsets else 0.0,
        'avg_gaze_focus_score': round(_safe_avg(gaze_focus_scores), 2) if gaze_focus_scores else 0.0,
        'max_drift_count': int(max_gaze_drift_count),
        'drift_jumps': int(drift_jumps),
    }

    # 下采样，避免报告载荷过大（保留首尾点）。
    gaze_focus_trend = gaze_focus_trend_full
    max_points = 180
    if len(gaze_focus_trend_full) > max_points:
        stride = max(1, len(gaze_focus_trend_full) // max_points)
        gaze_focus_trend = [gaze_focus_trend_full[i] for i in range(0, len(gaze_focus_trend_full), stride)]
        if gaze_focus_trend[-1].get('second') != gaze_focus_trend_full[-1].get('second'):
            gaze_focus_trend.append(gaze_focus_trend_full[-1])

    gaze_focus_summary = {
        'avg_focus_score': round(_safe_avg([item.get('focus_score') for item in gaze_focus_trend_full]), 2) if gaze_focus_trend_full else 0.0,
        'low_focus_ratio': round((low_focus_frames / sample_count) * 100.0, 2) if sample_count else 0.0,
        'min_focus_score': round(min_focus_score if gaze_focus_trend_full else 0.0, 2),
    }
    physiology_summary = {
        'avg_heart_rate': round(_safe_avg(hr_values), 2) if hr_values else None,
        'min_heart_rate': round(min(hr_values), 2) if hr_values else None,
        'max_heart_rate': round(max(hr_values), 2) if hr_values else None,
        'heart_rate_samples': int(len(hr_values)),
        'rppg_reliable_ratio': round((rppg_reliable_frames / rppg_frames) * 100.0, 2) if rppg_frames else None,
        'hr_out_of_range_ratio': round((hr_out_of_range_frames / len(hr_values)) * 100.0, 2) if hr_values else None,
    }

    return {
        'sample_count': sample_count,
        'landmarks_3d': landmarks_snapshot,
        'blendshapes': blendshape_snapshot,
        'head_pose': head_pose_snapshot,
        'iris_tracking': iris_snapshot,
        'physiology': physiology_summary,
        'gaze_focus_summary': gaze_focus_summary,
        'gaze_focus_trend': gaze_focus_trend,
    }


def _build_content_performance_snapshot(interview_id: str, dialogues=None):
    total_questions = len(dialogues or [])
    if not hasattr(db_manager, 'get_interview_evaluations'):
        return {
            'status': 'unavailable',
            'status_message': '评估能力未启用，无法生成内容表现依据。',
            'question_evidence': [],
            'weak_dimensions': [],
            'scoring_basis': {
                'overall_formula': 'session_overall_score = mean(question.overall_score_final)',
                'question_formula': 'question.overall_score_final = mean(final_dimension_scores)',
                'sample_size': 0,
            },
        }

    raw_rows = db_manager.get_interview_evaluations(interview_id=interview_id) or []
    decoded_rows = _decode_evaluation_rows(raw_rows)
    decoded_rows = _filter_evaluation_rows_by_dialogues(decoded_rows, dialogues)

    scored_rows = [
        row for row in _dedupe_evaluation_rows_by_turn(decoded_rows)
        if str((row or {}).get('status') or '').strip().lower() in {'ok', 'partial_ok'}
    ]
    if not scored_rows:
        pending_message = '结构化评分处理中，请稍后刷新。' if total_questions > 0 else '暂无可追溯评分样本。'
        return {
            'status': 'processing' if total_questions > 0 else 'empty',
            'status_message': pending_message,
            'question_evidence': [],
            'weak_dimensions': [],
            'scoring_basis': {
                'overall_formula': 'session_overall_score = mean(question.overall_score_final)',
                'question_formula': 'question.overall_score_final = mean(final_dimension_scores)',
                'sample_size': 0,
            },
        }

    dialogue_by_turn = {
        str(item.get('turn_id') or '').strip(): item
        for item in (dialogues or [])
        if str(item.get('turn_id') or '').strip()
    }
    dim_labels = _dimension_label_map()
    dim_scores = {}
    dim_reasons = {}
    question_evidence = []
    excluded_questions = []
    fallback_sample_count = 0

    for row in scored_rows:
        layer1 = row.get('layer1') or {}
        layer2 = row.get('layer2') or {}
        turn_id = str(row.get('turn_id') or '').strip()
        dialogue_ref = dialogue_by_turn.get(turn_id) or {}

        question = str(row.get('question') or dialogue_ref.get('question') or '').strip()
        answer = str(row.get('answer') or dialogue_ref.get('answer') or '').strip()
        round_type = str(row.get('round_type') or dialogue_ref.get('round_type') or 'unknown').strip() or 'unknown'
        overall_score = (
            layer2.get('overall_score_final')
            or row.get('overall_score')
            or layer2.get('overall_score')
            or 0.0
        )

        final_dims = _filter_content_dimensions_by_round(
            round_type,
            layer2.get('final_dimension_scores') or layer2.get('dimension_scores') or {},
        )
        if _is_fallback_scored_evaluation(row, layer2):
            fallback_sample_count += 1
            excluded_questions.append({
                'turn_id': turn_id,
                'round_type': round_type,
                'question_excerpt': _compact_text(question, limit=100),
                'answer_excerpt': _compact_text(answer, limit=180),
                'overall_score': round(float(overall_score or 0.0), 1),
                'exclude_reasons': ['fallback_scoring'],
                'error_code': str(row.get('error_code') or '').strip(),
                'error_message': _compact_text(row.get('error_message') or '', limit=140),
                'trace_source': f"interview_evaluations/{str(row.get('evaluation_version') or 'v1').strip() or 'v1'}",
            })
            continue

        sample_quality = _detect_content_sample_quality(
            question=question,
            answer=answer,
            layer1=layer1,
            final_dims=final_dims,
        )
        if not sample_quality.get('effective'):
            excluded_questions.append({
                'turn_id': turn_id,
                'round_type': round_type,
                'question_excerpt': _compact_text(question, limit=100),
                'answer_excerpt': _compact_text(answer, limit=180),
                'overall_score': round(float(overall_score or 0.0), 1),
                'exclude_reasons': sample_quality.get('reasons') or [],
                'coverage_ratio': sample_quality.get('coverage_ratio'),
                'token_count': sample_quality.get('token_count'),
                'trace_source': f"interview_evaluations/{str(row.get('evaluation_version') or 'v1').strip() or 'v1'}",
            })
            continue

        weak_dims = []
        content_dimension_scores = []
        for dim_key, dim_payload in (final_dims or {}).items():
            score = float((dim_payload or {}).get('score') or 0.0)
            reason = str((dim_payload or {}).get('reason') or '').strip()
            reason_tags = _classify_reason_tags(dim_key, reason)
            dim_scores.setdefault(dim_key, []).append(score)
            content_dimension_scores.append(score)
            if reason:
                dim_reasons.setdefault(dim_key, []).append(reason)
            weak_dims.append({
                'key': dim_key,
                'label': dim_labels.get(dim_key, dim_key),
                'score': round(score, 1),
                'reason': reason,
                'reason_tags': reason_tags,
            })

        effective_overall_score = _safe_avg(content_dimension_scores) if content_dimension_scores else float(overall_score or 0.0)

        weak_dims_sorted = sorted(weak_dims, key=lambda item: float(item.get('score') or 0.0))[:2]
        key_points = layer1.get('key_points') or {}
        missing_points = [
            str(item).strip()
            for item in (key_points.get('missing') or [])
            if str(item).strip()
        ]
        signals = layer1.get('signals') or {}
        red_flags = [
            str(item).strip()
            for item in (signals.get('red_flags') or [])
            if str(item).strip()
        ]
        evidence_tags = (missing_points[:3] + red_flags[:3])[:6]

        question_evidence.append({
            'turn_id': turn_id,
            'round_type': round_type,
            'question_excerpt': _compact_text(question, limit=100),
            'answer_excerpt': _compact_text(answer, limit=180),
            'overall_score': round(float(effective_overall_score or 0.0), 1),
            'weak_dimensions': weak_dims_sorted,
            'reason_tags': sorted({
                tag
                for dim_item in weak_dims_sorted
                for tag in (dim_item.get('reason_tags') or [])
            }, key=lambda item: ('技术', '表达', '结构').index(item) if item in {'技术', '表达', '结构'} else 99),
            'evidence_tags': evidence_tags,
            'trace_source': f"interview_evaluations/{str(row.get('evaluation_version') or 'v1').strip() or 'v1'}",
        })

    weak_dimensions = []
    for dim_key, values in sorted(dim_scores.items(), key=lambda item: _safe_avg(item[1])):
        reasons = []
        reason_tags = set()
        for reason in dim_reasons.get(dim_key, []):
            if reason and reason not in reasons:
                reasons.append(reason)
            for tag in _classify_reason_tags(dim_key, reason):
                reason_tags.add(tag)
        weak_dimensions.append({
            'key': dim_key,
            'label': dim_labels.get(dim_key, dim_key),
            'avg_score': round(_safe_avg(values), 1),
            'sample_count': len(values),
            'reasons': reasons[:2],
            'reason_tags': [
                tag for tag in ('技术', '表达', '结构')
                if tag in reason_tags
            ],
        })

    if not question_evidence:
        status = 'no_effective_answer' if excluded_questions else 'processing'
        status_message = (
            '已检索到评分记录，但本场没有可用于内容能力画像的有效回答；疑似误收环境音、题干复述或未作答。'
            if excluded_questions
            else ('结构化评分处理中，请稍后刷新。' if total_questions > 0 else '暂无可追溯评分样本。')
        )
        return {
            'status': status,
            'status_message': status_message,
            'question_evidence': [],
            'weak_dimensions': [],
            'excluded_questions': excluded_questions[:6],
            'effective_sample_size': 0,
            'excluded_sample_count': len(excluded_questions),
            'scoring_basis': {
                'overall_formula': 'session_overall_score = mean(question.overall_score_final)',
                'question_formula': 'question.overall_score_final = mean(final_dimension_scores)',
                'sample_size': 0,
                'total_scored_samples': len(scored_rows),
                'excluded_sample_count': len(excluded_questions),
                'fallback_sample_count': fallback_sample_count,
            },
        }

    return {
        'status': 'ready',
        'status_message': (
            f'已基于单题结构化评估生成内容表现依据；已排除 {len(excluded_questions)} 个无有效回答样本。'
            if excluded_questions
            else '已基于单题结构化评估生成内容表现依据。'
        ),
        'question_evidence': sorted(
            question_evidence,
            key=lambda item: float(item.get('overall_score') or 0.0)
        )[:6],
        'weak_dimensions': weak_dimensions[:6],
        'excluded_questions': excluded_questions[:6],
        'effective_sample_size': len(question_evidence),
        'excluded_sample_count': len(excluded_questions),
        'fallback_sample_count': fallback_sample_count,
        'scoring_basis': {
            'overall_formula': 'session_overall_score = mean(question.overall_score_final)',
            'question_formula': 'question.overall_score_final = mean(final_dimension_scores)',
            'sample_size': len(question_evidence),
            'total_scored_samples': len(scored_rows),
            'excluded_sample_count': len(excluded_questions),
            'fallback_sample_count': fallback_sample_count,
        },
    }


def _build_speech_performance_snapshot(interview_id: str):
    if not hasattr(db_manager, 'get_speech_evaluations'):
        return {
            'status': 'unavailable',
            'status_message': '语音评估能力未启用。',
            'dimensions': [],
            'summary': {},
            'evidence_samples': [],
            'diagnosis': [],
        }

    raw_rows = db_manager.get_speech_evaluations(interview_id=interview_id) or []
    decoded_rows = _decode_speech_rows(raw_rows)
    if not decoded_rows:
        return {
            'status': 'empty',
            'status_message': '暂无语音评估样本。',
            'dimensions': [],
            'summary': {},
            'evidence_samples': [],
            'diagnosis': [],
        }

    speech_summary = aggregate_expression_metrics(decoded_rows)
    dimension_labels = {
        'speech_rate_score': '语速节奏',
        'pause_anomaly_score': '停顿稳定性',
        'filler_frequency_score': '口头词控制',
        'fluency_score': '流畅度',
        'clarity_score': '清晰度',
    }

    dimensions = []
    for key, value in (speech_summary.get('dimensions') or {}).items():
        dimensions.append({
            'key': key,
            'label': dimension_labels.get(key, key),
            'score': round(float(value or 0.0), 1),
        })
    dimensions.sort(key=lambda item: float(item.get('score') or 0.0))

    evidence_samples = []
    for row in decoded_rows:
        metrics = row.get('speech_metrics_final') or {}
        pause_data = (metrics or {}).get('pause') or {}
        filler_data = (metrics or {}).get('fillers') or {}
        transcript = str(row.get('final_transcript') or '').strip()
        sample = {
            'turn_id': str(row.get('turn_id') or '').strip(),
            'transcript_excerpt': _compact_text(transcript, limit=120),
            'speech_rate_wpm': round(float((metrics or {}).get('speech_rate_wpm') or 0.0), 1),
            'fillers_per_100_words': round(float((filler_data or {}).get('per_100_words') or 0.0), 2),
            'pause_anomaly_ratio': round(float((pause_data or {}).get('anomaly_ratio') or 0.0), 4),
            'long_pause_count': int((pause_data or {}).get('long_count') or 0),
            'token_count': int((metrics or {}).get('token_count') or 0),
        }
        sample['_issue_score'] = (
            abs(sample['speech_rate_wpm'] - 165.0) * 0.06
            + sample['fillers_per_100_words'] * 2.2
            + sample['pause_anomaly_ratio'] * 100.0
            + sample['long_pause_count'] * 1.8
        )
        evidence_samples.append(sample)

    evidence_samples.sort(key=lambda item: float(item.get('_issue_score') or 0.0), reverse=True)
    trimmed_samples = []
    for item in evidence_samples[:5]:
        copied = dict(item)
        copied.pop('_issue_score', None)
        trimmed_samples.append(copied)

    summary = speech_summary.get('summary') or {}
    avg_speech_rate = float(summary.get('avg_speech_rate_wpm') or 0.0)
    avg_fillers = float(summary.get('avg_fillers_per_100_words') or 0.0)
    raw_pause_ratio = summary.get('avg_pause_anomaly_ratio')
    avg_pause_ratio = float(raw_pause_ratio) if isinstance(raw_pause_ratio, (int, float)) else None
    pause_reliable_samples = int(summary.get('pause_metric_reliable_samples') or 0)
    quality_warnings = [
        str(item).strip()
        for item in (summary.get('quality_warnings') or [])
        if str(item).strip()
    ]
    diagnosis = []
    if avg_speech_rate > 0 and avg_speech_rate < 110:
        diagnosis.append('整体语速偏慢，建议先给结论再展开，以减少停顿。')
    elif avg_speech_rate > 230:
        diagnosis.append('整体语速偏快，建议在关键结论处放慢节奏。')
    if avg_fillers > 6.0:
        diagnosis.append('口头词偏多，建议回答前先用 1 句话组织主线。')
    if avg_pause_ratio is not None and avg_pause_ratio > 0.45:
        diagnosis.append('异常停顿比例较高，建议按“结论-依据-结果”模板回答。')
    if pause_reliable_samples <= 0 and quality_warnings:
        diagnosis.append('当前停顿数据置信度不足，建议结合语音回放人工确认停顿问题。')
    if not diagnosis:
        diagnosis.append('语音表达整体稳定，可持续保持当前节奏。')

    return {
        'status': 'ready',
        'status_message': '语音指标已完成聚合。',
        'dimensions': dimensions,
        'summary': summary,
        'evidence_samples': trimmed_samples,
        'diagnosis': diagnosis,
    }


def _build_camera_performance_snapshot(statistics, event_type_counter, top_events, max_probability: float, camera_insights=None):
    stats = statistics or {}
    deep = camera_insights or {}
    total_deviations = int(stats.get('total_deviations') or 0)
    total_mouth_open = int(stats.get('total_mouth_open') or 0)
    total_multi_person = int(stats.get('total_multi_person') or 0)
    off_screen_ratio = float(stats.get('off_screen_ratio') or 0.0)

    head_pose = deep.get('head_pose') if isinstance(deep.get('head_pose'), dict) else {}
    iris_tracking = deep.get('iris_tracking') if isinstance(deep.get('iris_tracking'), dict) else {}
    blendshapes = deep.get('blendshapes') if isinstance(deep.get('blendshapes'), dict) else {}
    landmarks = deep.get('landmarks_3d') if isinstance(deep.get('landmarks_3d'), dict) else {}
    physiology = deep.get('physiology') if isinstance(deep.get('physiology'), dict) else {}

    avg_gaze_focus = _safe_float(iris_tracking.get('avg_gaze_focus_score'), 0.0)
    high_pose_ratio = _safe_float(head_pose.get('high_pose_ratio'), 0.0)
    avg_blink_rate = _safe_float(blendshapes.get('avg_blink_rate_per_min'), 0.0)
    avg_jaw_open = _safe_float(blendshapes.get('avg_jaw_open'), 0.0)
    avg_heart_rate = _safe_float(physiology.get('avg_heart_rate'), 0.0)
    rppg_reliable_ratio = _safe_float(physiology.get('rppg_reliable_ratio'), 0.0)
    hr_out_of_range_ratio = _safe_float(physiology.get('hr_out_of_range_ratio'), 0.0)
    heart_rate_samples = int(_safe_float(physiology.get('heart_rate_samples'), 0.0))

    focus_score = max(0.0, min(100.0, 100.0 - off_screen_ratio * 2.6 - max(0, total_deviations - 2) * 1.4))
    if avg_gaze_focus > 0:
        focus_score = (focus_score * 0.55) + (avg_gaze_focus * 0.45)

    compliance_score = max(0.0, min(100.0, 100.0 - total_mouth_open * 2.2 - total_multi_person * 40.0))
    if high_pose_ratio > 0:
        compliance_score -= min(24.0, high_pose_ratio * 0.26)
    if avg_blink_rate > 45:
        compliance_score -= min(8.0, (avg_blink_rate - 45.0) * 0.25)
    if avg_jaw_open > 0.25:
        compliance_score -= min(8.0, (avg_jaw_open - 0.25) * 30.0)
    compliance_score = max(0.0, min(100.0, compliance_score))

    anti_cheat_score = max(0.0, min(100.0, 100.0 - float(max_probability or 0.0)))
    overall_score = round((focus_score + compliance_score + anti_cheat_score) / 3.0, 1)

    notes = []
    if total_multi_person > 0:
        notes.append('检测到多人同框，属于高风险违规行为。')
    if off_screen_ratio >= 20:
        notes.append(f'屏幕外注视占比 {off_screen_ratio:.1f}%，注意力稳定性不足。')
    elif off_screen_ratio >= 10:
        notes.append(f'屏幕外注视占比 {off_screen_ratio:.1f}%，建议减少视线偏离。')
    if total_mouth_open >= 4:
        notes.append(f'检测到 {total_mouth_open} 次异常口型，建议确认环境无干扰。')
    if total_deviations >= 6:
        notes.append(f'累计 {total_deviations} 次偏移事件，建议固定坐姿并保持正对镜头。')
    if high_pose_ratio >= 25:
        notes.append(f'头部姿态异常帧占比 {high_pose_ratio:.1f}%，建议回答时减少频繁转头/低头。')
    if avg_blink_rate >= 45:
        notes.append(f'眨眼频率约 {avg_blink_rate:.1f} 次/分钟，存在明显紧张迹象。')
    drift_jumps = int(_safe_float(iris_tracking.get('drift_jumps'), 0.0))
    if drift_jumps >= 8:
        notes.append(f'虹膜漂移累计 {drift_jumps} 次，核心题回答时眼神稳定性不足。')
    if heart_rate_samples > 0:
        if rppg_reliable_ratio >= 60:
            notes.append(f'平均心率约 {avg_heart_rate:.1f} bpm，生理信号可用率 {rppg_reliable_ratio:.1f}%。')
        else:
            notes.append(f'平均心率约 {avg_heart_rate:.1f} bpm，但生理信号可用率仅 {rppg_reliable_ratio:.1f}%，建议保证光线与正脸稳定。')
        if hr_out_of_range_ratio >= 40:
            notes.append(f'心率偏离常见区间帧占比 {hr_out_of_range_ratio:.1f}%，可结合呼吸节奏与表达节奏做稳定训练。')
    else:
        notes.append('当前会话未采集到稳定心率信号，建议保持正脸、光线均匀并减少快速位移。')
    avg_landmark_count = _safe_float(landmarks.get('avg_landmark_count'), 0.0)
    tracked_count_max = int(_safe_float(blendshapes.get('tracked_count_max'), 0.0))
    if avg_landmark_count < 468 or tracked_count_max < 40:
        notes.append('面部关键点或表情系数采样不足，建议保证光线均匀并保持正脸。')
    if not notes:
        notes.append('镜头前行为总体稳定，未见明显异常模式。')

    return {
        'status': 'ready',
        'status_message': '镜头行为指标已完成聚合（含 3D 关键点/表情系数/头姿/虹膜追踪）。',
        'overall_score': overall_score,
        'focus_score': round(max(0.0, min(100.0, focus_score)), 1),
        'compliance_score': round(compliance_score, 1),
        'anti_cheat_score': round(anti_cheat_score, 1),
        'statistics': {
            'total_deviations': total_deviations,
            'total_mouth_open': total_mouth_open,
            'total_multi_person': total_multi_person,
            'off_screen_ratio': round(off_screen_ratio, 2),
            'avg_heart_rate': round(avg_heart_rate, 2) if heart_rate_samples > 0 else None,
            'rppg_reliable_ratio': round(rppg_reliable_ratio, 2) if heart_rate_samples > 0 else None,
            'heart_rate_samples': heart_rate_samples,
        },
        'camera_insights': deep,
        'event_type_breakdown': [
            {'event_type': key, 'count': int(count)}
            for key, count in sorted(event_type_counter.items(), key=lambda item: item[1], reverse=True)
        ],
        'top_risk_events': top_events[:6],
        'notes': notes,
    }


def _build_legacy_score_breakdown_from_dimensions(dimension_items, speech_dimensions=None):
    score_map = {item.get('key'): float(item.get('score', 0.0) or 0.0) for item in (dimension_items or [])}
    speech_map = {
        str(key or '').strip(): _safe_float(value)
        for key, value in ((speech_dimensions or {}) if isinstance(speech_dimensions, dict) else {}).items()
    }

    def _pick_score(*keys):
        for key in keys:
            if key in score_map:
                return round(float(score_map.get(key, 0.0) or 0.0), 1)
        return 0.0

    expression_clarity = _pick_score('clarity', 'communication', 'expression_clarity')
    if expression_clarity <= 0.0 and speech_map:
        speech_fallback = (
            speech_map.get('clarity_score')
            if isinstance(speech_map.get('clarity_score'), (int, float))
            else speech_map.get('fluency_score')
        )
        if isinstance(speech_fallback, (int, float)):
            expression_clarity = round(max(0.0, min(100.0, float(speech_fallback))), 1)

    return {
        'technical_correctness': _pick_score('technical_accuracy', 'technical_correctness'),
        'knowledge_depth': _pick_score('knowledge_depth'),
        'logical_rigor': _pick_score('logic', 'logical_rigor'),
        'expression_clarity': expression_clarity,
        'job_match': _pick_score('job_match'),
        'adaptability': _pick_score('reflection', 'tradeoff_awareness', 'adaptability'),
    }


def _build_growth_report_v2(dialogues, evaluation_rows=None, speech_rows=None):
    speech_summary = aggregate_expression_metrics(speech_rows or [])
    decoded_evaluations = _dedupe_evaluation_rows_by_turn(_decode_evaluation_rows(evaluation_rows or []))
    decoded_evaluations = [
        row for row in decoded_evaluations
        if not _is_fallback_scored_evaluation(row, (row or {}).get('layer2') or {})
    ]
    rounds = [str(d.get('round_type') or 'unknown') for d in dialogues]
    round_counter = Counter(rounds)
    started_at = _parse_db_datetime(dialogues[0].get('created_at')) if dialogues else None
    ended_at = _parse_db_datetime(dialogues[-1].get('created_at')) if dialogues else None
    duration_seconds = int((ended_at - started_at).total_seconds()) if started_at and ended_at else 0
    dominant_round = round_counter.most_common(1)[0][0] if round_counter else 'technical'

    score_transparency = {}

    if decoded_evaluations:
        dimension_labels = {
            'technical_accuracy': '技术准确性',
            'knowledge_depth': '知识深度',
            'completeness': '回答完整度',
            'logic': '逻辑严谨性',
            'job_match': '岗位匹配度',
            'authenticity': '项目真实性',
            'ownership': '项目 ownership',
            'technical_depth': '项目技术深度',
            'reflection': '复盘反思',
            'architecture_reasoning': '架构推理',
            'tradeoff_awareness': '权衡意识',
            'scalability': '扩展性设计',
            'clarity': '表达清晰度',
            'relevance': '回答相关性',
            'self_awareness': '自我认知',
            'communication': '沟通表现',
        }

        aggregated_dimension_scores = {}
        dimension_samples = {}
        round_score_values = {}
        strengths = []
        weaknesses = []
        next_actions = []
        question_reviews = []
        overall_components = []
        missing_point_counter = Counter()
        red_flag_counter = Counter()
        speech_used_count = 0
        speech_expression_values = []
        speech_adjustment_values = []

        for row in decoded_evaluations:
            layer1 = row.get('layer1') or {}
            layer2 = row.get('layer2') or {}
            text_base_dim_scores = (layer2.get('text_base_dimension_scores') or {})
            round_type = str(row.get('round_type') or 'technical')
            dim_scores = _filter_content_dimensions_by_round(
                round_type,
                layer2.get('final_dimension_scores') or layer2.get('dimension_scores') or {},
            )
            speech_adjustments = (layer2.get('speech_adjustments') or {})
            summary = (layer2.get('summary') or {})
            turn_id = str(row.get('turn_id') or '').strip()
            fusion = row.get('fusion') or {}
            _candidate_score = (
                fusion.get('overall_score')
                if fusion.get('overall_score') is not None
                else row.get('overall_score')
                if row.get('overall_score') is not None
                else layer2.get('overall_score_final')
                if layer2.get('overall_score_final') is not None
                else layer2.get('overall_score')
                if layer2.get('overall_score') is not None
                else 0.0
            )
            overall_score = float(_candidate_score)
            round_score_values.setdefault(round_type, []).append(overall_score)
            speech_used = bool(layer2.get('speech_used'))
            speech_expression_score = (
                round(float(layer2.get('speech_expression_score') or 0.0), 1)
                if layer2.get('speech_expression_score') is not None else None
            )
            if speech_used:
                speech_used_count += 1
            if speech_expression_score is not None:
                speech_expression_values.append(float(speech_expression_score))

            layer1_key_points = layer1.get('key_points') or {}
            covered_points = layer1_key_points.get('covered') or []
            missing_points = [
                str(item).strip()
                for item in (layer1_key_points.get('missing') or [])
                if str(item).strip()
            ]
            for point in missing_points:
                missing_point_counter[point] += 1

            layer1_signals = layer1.get('signals') or {}
            hit_signals = [
                str(item).strip()
                for item in (layer1_signals.get('hit') or [])
                if str(item).strip()
            ]
            red_flags = [
                str(item).strip()
                for item in (layer1_signals.get('red_flags') or [])
                if str(item).strip()
            ]
            for flag in red_flags:
                red_flag_counter[flag] += 1

            normalized_dims = []
            for dim_key, dim_payload in dim_scores.items():
                score = float((dim_payload or {}).get('score') or 0.0)
                text_base_score = float(((text_base_dim_scores.get(dim_key) or {}).get('score')) or score)
                speech_adjustment = speech_adjustments.get(dim_key, score - text_base_score)
                aggregated_dimension_scores.setdefault(dim_key, []).append(score)
                reason = str((dim_payload or {}).get('reason') or '').strip()
                normalized_dim = {
                    'key': dim_key,
                    'label': dimension_labels.get(dim_key, dim_key),
                    'score': round(score, 1),
                    'final_score': round(score, 1),
                    'text_base_score': round(text_base_score, 1),
                    'speech_adjustment': round(float(speech_adjustment or 0.0), 1),
                    'speech_used': speech_used,
                    'reason': reason,
                }
                normalized_dims.append(normalized_dim)
                dimension_samples.setdefault(dim_key, []).append({
                    'turn_id': turn_id,
                    'question': str(row.get('question') or ''),
                    'score': float(score),
                    'text_base_score': float(text_base_score),
                    'speech_adjustment': float(speech_adjustment or 0.0),
                    'reason': reason,
                })
                if speech_used:
                    speech_adjustment_values.append(abs(float(speech_adjustment or 0.0)))

            weakest_dimensions = sorted(
                [
                    {
                        'key': item.get('key'),
                        'label': item.get('label'),
                        'score': float(item.get('final_score') or item.get('score') or 0.0),
                    }
                    for item in normalized_dims
                ],
                key=lambda item: item['score']
            )[:2]

            strengths.extend([str(x).strip() for x in (summary.get('strengths') or []) if str(x).strip()])
            weaknesses.extend([str(x).strip() for x in (summary.get('weaknesses') or []) if str(x).strip()])
            next_actions.extend([str(x).strip() for x in (summary.get('next_actions') or []) if str(x).strip()])

            overall_components.append({
                'turn_id': turn_id,
                'round_type': round_type,
                'question': str(row.get('question') or ''),
                'overall_score_final': round(overall_score, 1),
                'status': str(row.get('status') or ''),
                'weight': 1.0,
            })

            question_reviews.append({
                'turn_id': turn_id,
                'question_id': row.get('question_id', ''),
                'round_type': round_type,
                'question': row.get('question', ''),
                'answer': row.get('answer', ''),
                'rubric_level': row.get('rubric_level', ''),
                'overall_score': round(overall_score, 1),
                'overall_score_base': round(float(layer2.get('overall_score_base') or overall_score), 1),
                'overall_score_final': round(float(layer2.get('overall_score_final') or overall_score), 1),
                'confidence': round(float(row.get('confidence') or 0.0), 4),
                'status': row.get('status', ''),
                'speech_used': speech_used,
                'speech_fusion_version': layer2.get('speech_fusion_version', ''),
                'speech_expression_score': speech_expression_score,
                'dimensions': normalized_dims,
                'evidence': {
                    'key_point_coverage_ratio': round(float(layer1_key_points.get('coverage_ratio') or 0.0), 4),
                    'covered_key_points': len(covered_points),
                    'total_key_points': len(covered_points) + len(missing_points),
                    'missing_key_points': missing_points[:5],
                    'hit_signals': hit_signals[:5],
                    'red_flags': red_flags[:4],
                    'rubric_match': layer1.get('rubric_match') or {},
                },
                'score_transparency': {
                    'formula': 'overall_score_final = mean(final_dimension_scores)',
                    'overall_score_base': round(float(layer2.get('overall_score_base') or overall_score), 1),
                    'overall_score_final': round(float(layer2.get('overall_score_final') or overall_score), 1),
                    'weakest_dimensions': weakest_dimensions,
                },
                'summary': {
                    'strengths': [str(x) for x in (summary.get('strengths') or [])][:3],
                    'weaknesses': [str(x) for x in (summary.get('weaknesses') or [])][:3],
                    'next_actions': [str(x) for x in (summary.get('next_actions') or [])][:3],
                }
            })

        overall_score = round(_safe_avg([
            (row.get('layer2') or {}).get('overall_score_final')
            or row.get('overall_score')
            or (row.get('layer2') or {}).get('overall_score')
            for row in decoded_evaluations
        ]), 1)
        dimension_items = [
            {
                'key': dim_key,
                'label': dimension_labels.get(dim_key, dim_key),
                'score': round(_safe_avg(values), 1),
                'source': 'evaluation_service'
            }
            for dim_key, values in sorted(aggregated_dimension_scores.items())
        ]

        dimension_aggregation = []
        for dim_key, values in sorted(aggregated_dimension_scores.items()):
            samples = sorted(
                dimension_samples.get(dim_key, []),
                key=lambda item: float(item.get('score') or 0.0)
            )
            dimension_aggregation.append({
                'key': dim_key,
                'label': dimension_labels.get(dim_key, dim_key),
                'avg_score': round(_safe_avg(values), 1),
                'avg_text_base_score': round(_safe_avg([item.get('text_base_score') for item in samples]), 1),
                'avg_speech_adjustment': round(_safe_avg([item.get('speech_adjustment') for item in samples]), 2),
                'sample_count': len(samples),
                'lowest_questions': [
                    {
                        'turn_id': item.get('turn_id', ''),
                        'question': str(item.get('question') or ''),
                        'score': round(float(item.get('score') or 0.0), 1),
                        'reason': str(item.get('reason') or ''),
                    }
                    for item in samples[:2]
                ],
            })

        score_breakdown = _build_legacy_score_breakdown_from_dimensions(
            dimension_items,
            speech_dimensions=speech_summary.get('dimensions') if isinstance(speech_summary, dict) else {},
        )

        round_breakdown = [
            {
                'round_type': round_type,
                'count': len(values),
                'avg_score': round(_safe_avg(values), 1),
            }
            for round_type, values in sorted(round_score_values.items())
        ]

        coaching = {
            'strengths': list(dict.fromkeys(strengths))[:6],
            'weaknesses': list(dict.fromkeys(weaknesses))[:6],
            'next_actions': list(dict.fromkeys(next_actions))[:6],
        }
        score_transparency = {
            'mode': 'structured_evaluation',
            'overall_formula': 'session_overall_score = mean(question.overall_score_final)',
            'question_formula': 'question.overall_score_final = mean(final_dimension_scores)',
            'overall_components': overall_components,
            'dimension_aggregation': sorted(dimension_aggregation, key=lambda item: float(item.get('avg_score') or 0.0)),
            'gap_signals': {
                'missing_key_points': [
                    {'point': point, 'count': int(count)}
                    for point, count in missing_point_counter.most_common(8)
                ],
                'red_flags': [
                    {'signal': signal, 'count': int(count)}
                    for signal, count in red_flag_counter.most_common(8)
                ],
            },
            'speech_fusion_summary': {
                'speech_used_questions': speech_used_count,
                'total_questions': len(question_reviews),
                'avg_expression_score': round(_safe_avg(speech_expression_values), 1) if speech_expression_values else None,
                'avg_abs_dimension_adjustment': round(_safe_avg(speech_adjustment_values), 2) if speech_adjustment_values else 0.0,
            },
        }
        report_mode = 'structured_evaluation'
        has_structured = True
    else:
        overall_score = None
        dimension_items = []
        score_breakdown = {
            'technical_correctness': 0.0,
            'knowledge_depth': 0.0,
            'logical_rigor': 0.0,
            'expression_clarity': 0.0,
            'job_match': 0.0,
            'adaptability': 0.0,
        }
        round_breakdown = [
            {
                'round_type': round_type,
                'count': count,
                'avg_score': 0.0,
            }
            for round_type, count in sorted(round_counter.items())
        ]
        question_reviews = [
            {
                'turn_id': item.get('turn_id') or item.get('id', ''),
                'question_id': '',
                'round_type': item.get('round_type', 'unknown'),
                'question': item.get('question', ''),
                'answer': item.get('answer', ''),
                'rubric_level': '',
                'overall_score': None,
                'confidence': 0.0,
                'status': 'pending_structured_evaluation',
                'dimensions': [],
                'summary': {
                    'strengths': [],
                    'weaknesses': [],
                    'next_actions': [],
                }
            }
            for item in dialogues[-6:]
        ]
        coaching = {
            'strengths': [],
            'weaknesses': [],
            'next_actions': [
                '当前会话暂无结构化评分结果，请稍后刷新报告。',
                '确认评估服务已启用（RAG + LLM）并完成异步落库。',
                '若长期无分数，请检查 interview_evaluations 表中的任务状态。'
            ],
        }
        score_transparency = {
            'mode': 'structured_evaluation_only',
            'overall_formula': 'session_overall_score = mean(question.overall_score_final)',
            'limitations': '未检索到可用结构化评估记录，本次未进行启发式兜底评分。',
        }
        report_mode = 'structured_pending'
        has_structured = False

    expression_detail = {
        'available': bool(speech_summary.get('available')),
        'dimensions': speech_summary.get('dimensions', {}),
        'summary': speech_summary.get('summary', {}),
    }

    followup_chain = []
    for item in dialogues[-6:]:
        followup_chain.append({
            'round': item.get('round_type', 'unknown'),
            'question': item.get('question', ''),
            'answer': item.get('answer', ''),
            'feedback': item.get('llm_feedback', '')
        })

    report = {
        'schema_version': 'growth_report_v2',
        'meta': {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'interview_id': str(dialogues[0].get('interview_id') or '').strip() if dialogues else '',
            'report_mode': report_mode,
            'has_structured_evaluations': has_structured,
            'transparency_version': 'score_transparency_v1',
            'dialogue_count': len(dialogues),
            'evaluation_count': len(decoded_evaluations),
        },
        'summary': {
            'overall_score': overall_score,
            'level': _score_to_level(overall_score) if overall_score is not None else None,
            'interview_count': len(dialogues),
            'started_at': dialogues[0].get('created_at') if dialogues else '',
            'ended_at': dialogues[-1].get('created_at') if dialogues else '',
            'duration_seconds': max(0, duration_seconds),
            'dominant_round': dominant_round,
        },
        'dimensions': dimension_items,
        'round_breakdown': round_breakdown,
        'expression': expression_detail,
        'coaching': coaching,
        'score_transparency': score_transparency,
        'question_reviews': question_reviews,
        # legacy fields kept for current frontend compatibility
        'score_breakdown': score_breakdown,
        'expression_detail': expression_detail,
        'strengths': coaching['strengths'],
        'weaknesses': coaching['weaknesses'],
        'improvement_plan': [
            {
                'focus': action,
                'action': action,
                'target': ''
            }
            for action in coaching['next_actions'][:3]
        ],
        'followup_chain': followup_chain,
    }
    return report


def _build_growth_report(dialogues, speech_rows=None):
    evaluation_rows = []
    try:
        interview_id = str(dialogues[0].get('interview_id') or '').strip() if dialogues else ''
        if interview_id and hasattr(db_manager, 'get_interview_evaluations'):
            raw_rows = db_manager.get_interview_evaluations(interview_id=interview_id) or []
            evaluation_rows = [
                row for row in raw_rows
                if str((row or {}).get('status') or '').strip().lower() in {'ok', 'partial_ok'}
            ]
    except Exception:
        evaluation_rows = []
    return _build_growth_report_v2(dialogues, evaluation_rows=evaluation_rows, speech_rows=speech_rows)


def _build_structured_snapshot(interview_id: str, dialogues=None):
    """构建即时报告用的结构化评分快照。"""
    total_questions = len(dialogues or [])
    if not hasattr(db_manager, 'get_interview_evaluations'):
        return {
            'status': 'unavailable',
            'status_message': '评估能力未启用',
            'total_questions': total_questions,
            'evaluated_questions': 0,
            'overall_score': None,
            'level': None,
            'round_breakdown': [],
            'dimension_scores': [],
            'status_counts': {},
        }

    raw_rows = db_manager.get_interview_evaluations(interview_id=interview_id) or []
    decoded_rows = _decode_evaluation_rows(raw_rows)
    decoded_rows = _filter_evaluation_rows_by_dialogues(decoded_rows, dialogues)

    decoded_rows = _dedupe_evaluation_rows_by_turn(decoded_rows)
    fallback_scored_count = sum(
        1
        for row in decoded_rows
        if _is_fallback_scored_evaluation(row, (row or {}).get('layer2') or {})
    )

    if not decoded_rows:
        pending_message = '结构化评分处理中，请稍后刷新。' if total_questions > 0 else '暂无可评分题目。'
        return {
            'status': 'processing' if total_questions > 0 else 'empty',
            'status_message': pending_message,
            'total_questions': total_questions,
            'evaluated_questions': 0,
            'overall_score': None,
            'level': None,
            'round_breakdown': [],
            'round_aggregation': _build_round_aggregation_snapshot(interview_id, decoded_rows=[], dialogues=dialogues),
            'dimension_scores': [],
            'status_counts': {},
        }

    status_counts = Counter()
    round_scores = {}
    all_scores = []
    dim_scores = {}
    scored_turns = set()

    dimension_labels = {
        'technical_accuracy': '技术准确性',
        'knowledge_depth': '知识深度',
        'completeness': '回答完整度',
        'logic': '逻辑严谨性',
        'job_match': '岗位匹配度',
        'authenticity': '项目真实性',
        'ownership': '项目 ownership',
        'technical_depth': '项目技术深度',
        'reflection': '复盘反思',
        'architecture_reasoning': '架构推理',
        'tradeoff_awareness': '权衡意识',
        'scalability': '扩展性设计',
        'clarity': '表达清晰度',
        'relevance': '回答相关性',
        'self_awareness': '自我认知',
        'communication': '沟通表现',
    }

    valid_score_status = {'ok', 'partial_ok'}

    for row in decoded_rows:
        status = str(row.get('status') or 'unknown').strip().lower() or 'unknown'
        status_counts[status] += 1
        turn_id = str(row.get('turn_id') or '').strip()
        round_type = str(row.get('round_type') or 'technical').strip() or 'technical'

        layer2 = row.get('layer2') or {}
        if _is_fallback_scored_evaluation(row, layer2):
            continue
        score_value = (
            layer2.get('overall_score_final')
            or row.get('overall_score')
            or layer2.get('overall_score')
        )

        if status in valid_score_status and isinstance(score_value, (int, float)):
            score = _clamp_score(score_value)
            all_scores.append(score)
            round_scores.setdefault(round_type, []).append(score)
            if turn_id:
                scored_turns.add(turn_id)

        dim_map = _filter_content_dimensions_by_round(
            round_type,
            layer2.get('final_dimension_scores') or layer2.get('dimension_scores') or {},
        )
        for dim_key, dim_payload in (dim_map or {}).items():
            dim_score = (dim_payload or {}).get('score')
            if isinstance(dim_score, (int, float)):
                dim_scores.setdefault(dim_key, []).append(float(dim_score))

    evaluated_questions = len(scored_turns) if scored_turns else len(all_scores)
    has_pending_status = any(status in {'queued', 'pending', 'running'} for status in status_counts)
    if evaluated_questions > 0:
        status = 'ready'
        status_message = '结构化评分已就绪。'
        if total_questions > evaluated_questions or has_pending_status:
            status = 'partial'
            status_message = '部分题目评分已完成，剩余题目仍在处理中。'
    else:
        status = 'processing' if total_questions > 0 else 'empty'
        status_message = '结构化评分处理中，请稍后刷新。' if total_questions > 0 else '暂无可评分题目。'
        if fallback_scored_count > 0 and not has_pending_status:
            status = 'fallback_only'
            status_message = '本场仅有回退评分样本，未纳入结构化能力画像。'
        if status_counts.get('skipped', 0) > 0 and status_counts.get('ok', 0) == 0 and status_counts.get('partial_ok', 0) == 0:
            status = 'failed'
            status_message = '未匹配到可用评分标准，暂无法生成结构化评分。'
        if status_counts.get('failed', 0) > 0 and not has_pending_status:
            status = 'failed'
            status_message = '结构化评分执行失败，请稍后重试。'

    dimension_items = [
        {
            'key': key,
            'label': dimension_labels.get(key, key),
            'score': round(_safe_avg(values), 1),
        }
        for key, values in sorted(dim_scores.items())
    ]
    round_breakdown = [
        {
            'round_type': round_type,
            'count': len(values),
            'avg_score': round(_safe_avg(values), 1),
        }
        for round_type, values in sorted(round_scores.items())
    ]

    overall_score = round(_safe_avg(all_scores), 1) if all_scores else None
    round_aggregation_rows = [
        row for row in decoded_rows
        if not _is_fallback_scored_evaluation(row, (row or {}).get('layer2') or {})
    ]
    round_aggregation = _build_round_aggregation_snapshot(interview_id, decoded_rows=round_aggregation_rows, dialogues=dialogues)
    return {
        'status': status,
        'status_message': status_message,
        'total_questions': total_questions,
        'evaluated_questions': int(evaluated_questions),
        'overall_score': overall_score,
        'level': _score_to_level(overall_score) if overall_score is not None else None,
        'round_breakdown': round_breakdown,
        'round_aggregation': round_aggregation,
        'dimension_scores': dimension_items,
        'status_counts': dict(status_counts),
        'fallback_scored_count': int(fallback_scored_count),
    }


def _build_evaluation_v2_snapshot(interview_id: str, dialogues=None):
    total_questions = len(dialogues or [])
    if not hasattr(db_manager, 'get_interview_evaluations'):
        return {
            'status': 'unavailable',
            'status_message': '评估能力未启用',
            'layers': {},
            'fusion': {},
            'total_questions': total_questions,
            'evaluated_questions': 0,
            'questions': [],
        }

    raw_rows = db_manager.get_interview_evaluations(interview_id=interview_id) or []
    decoded_rows = _decode_evaluation_rows(raw_rows)
    decoded_rows = _filter_evaluation_rows_by_dialogues(decoded_rows, dialogues)

    if not decoded_rows:
        pending_message = '结构化评分处理中，请稍后刷新。' if total_questions > 0 else '暂无可评分题目。'
        return {
            'status': 'processing' if total_questions > 0 else 'empty',
            'status_message': pending_message,
            'layers': {},
            'fusion': {},
            'total_questions': total_questions,
            'evaluated_questions': 0,
            'questions': [],
        }

    decoded_rows = _dedupe_evaluation_rows_by_turn(decoded_rows)
    fallback_scored_count = sum(
        1
        for row in decoded_rows
        if _is_fallback_scored_evaluation(row, (row or {}).get('layer2') or {})
    )

    valid_score_status = {'ok', 'partial_ok'}
    layer_scores = {'text': [], 'speech': [], 'video': []}
    layer_confidence_parts = {
        'text': {'data_confidence': [], 'model_confidence': [], 'rubric_confidence': [], 'overall_confidence': []},
        'speech': {'data_confidence': [], 'model_confidence': [], 'rubric_confidence': [], 'overall_confidence': []},
        'video': {'data_confidence': [], 'model_confidence': [], 'rubric_confidence': [], 'overall_confidence': []},
    }
    fusion_scores = []
    fusion_confidences = []
    fusion_axis_confidence_parts = {
        'content': {'data_confidence': [], 'model_confidence': [], 'rubric_confidence': [], 'overall_confidence': []},
        'delivery': {'data_confidence': [], 'model_confidence': [], 'rubric_confidence': [], 'overall_confidence': []},
        'presence': {'data_confidence': [], 'model_confidence': [], 'rubric_confidence': [], 'overall_confidence': []},
    }
    questions = []
    scored_turns = set()
    base_weights = {'text': 0.5, 'speech': 0.25, 'video': 0.25}
    fusion_formula = 'W_effective_i = (W_base_i * C_i) / sum(W_base_j * C_j)'
    shortboard_applied_count = 0
    integrity_flagged_count = 0
    status_counts = Counter()

    for row in decoded_rows:
        row_status = str(row.get('status') or 'unknown').strip().lower() or 'unknown'
        status_counts[row_status] += 1
        if row_status not in valid_score_status:
            continue

        turn_id = str(row.get('turn_id') or '').strip()
        if _is_fallback_scored_evaluation(row, row.get('layer2') or {}):
            continue
        if turn_id:
            scored_turns.add(turn_id)

        text_layer = row.get('text_layer') or {}
        speech_layer = row.get('speech_layer') or {}
        video_layer = row.get('video_layer') or {}
        fusion = row.get('fusion') or {}

        if not text_layer:
            layer2 = row.get('layer2') or {}
            _text_score = layer2.get('overall_score_final')
            if _text_score is None:
                _text_score = layer2.get('overall_score')
            text_layer = {
                'overall_score': _text_score
            }

        for layer_name, layer_data in (('text', text_layer), ('speech', speech_layer), ('video', video_layer)):
            score = (layer_data or {}).get('overall_score')
            if isinstance(score, (int, float)):
                layer_scores[layer_name].append(float(score))
            confidence_breakdown = (layer_data or {}).get('confidence_breakdown') if isinstance((layer_data or {}).get('confidence_breakdown'), dict) else {}
            for confidence_key in ('data_confidence', 'model_confidence', 'rubric_confidence', 'overall_confidence'):
                confidence_value = confidence_breakdown.get(confidence_key)
                if isinstance(confidence_value, (int, float)):
                    layer_confidence_parts[layer_name][confidence_key].append(float(confidence_value))

        if isinstance((fusion or {}).get('base_weights'), dict):
            raw_weights = fusion.get('base_weights') or {}
            if 'text' in raw_weights or 'speech' in raw_weights or 'video' in raw_weights:
                base_weights = {
                    'text': float(raw_weights.get('text') or base_weights['text']),
                    'speech': float(raw_weights.get('speech') or base_weights['speech']),
                    'video': float(raw_weights.get('video') or base_weights['video']),
                }
            elif 'content' in raw_weights or 'delivery' in raw_weights or 'presence' in raw_weights:
                base_weights = {
                    'text': float(raw_weights.get('content') or base_weights['text']),
                    'speech': float(raw_weights.get('delivery') or base_weights['speech']),
                    'video': float(raw_weights.get('presence') or base_weights['video']),
                }

        formula = str((fusion or {}).get('formula') or '').strip()
        if formula:
            fusion_formula = formula

        shortboard_payload = (fusion or {}).get('shortboard_penalty') if isinstance((fusion or {}).get('shortboard_penalty'), dict) else {}
        shortboard_applied = bool((shortboard_payload or {}).get('applied'))
        if shortboard_applied:
            shortboard_applied_count += 1

        integrity_payload = (fusion or {}).get('integrity') if isinstance((fusion or {}).get('integrity'), dict) else {}
        integrity_veto = bool((integrity_payload or {}).get('veto'))
        if integrity_veto:
            integrity_flagged_count += 1

        fusion_score = (fusion or {}).get('overall_score')
        if fusion_score is None:
            fusion_score = row.get('overall_score')
        if isinstance(fusion_score, (int, float)):
            fusion_scores.append(float(fusion_score))

        fusion_confidence = (fusion or {}).get('overall_confidence')
        if isinstance(fusion_confidence, (int, float)):
            fusion_confidences.append(float(fusion_confidence))

        axis_confidence_breakdowns = (fusion or {}).get('axis_confidence_breakdowns') if isinstance((fusion or {}).get('axis_confidence_breakdowns'), dict) else {}
        for axis_name, axis_breakdown in axis_confidence_breakdowns.items():
            normalized_axis_name = str(axis_name or '').strip().lower()
            if normalized_axis_name not in fusion_axis_confidence_parts or not isinstance(axis_breakdown, dict):
                continue
            for confidence_key in ('data_confidence', 'model_confidence', 'rubric_confidence', 'overall_confidence'):
                confidence_value = axis_breakdown.get(confidence_key)
                if isinstance(confidence_value, (int, float)):
                    fusion_axis_confidence_parts[normalized_axis_name][confidence_key].append(float(confidence_value))

        questions.append({
            'turn_id': turn_id,
            'round_type': str(row.get('round_type') or 'unknown').strip() or 'unknown',
            'text_score': (text_layer or {}).get('overall_score'),
            'speech_score': (speech_layer or {}).get('overall_score'),
            'video_score': (video_layer or {}).get('overall_score'),
            'fusion_score': fusion_score,
            'shortboard_applied': shortboard_applied,
            'integrity_veto': integrity_veto,
            'status': row_status,
        })

    evaluated_questions = len(scored_turns) if scored_turns else len(fusion_scores)
    has_pending_status = any(key in {'queued', 'pending', 'running'} for key in status_counts.keys())

    if evaluated_questions > 0:
        status = 'ready'
        status_message = '三层解耦评分已就绪。'
        if total_questions > evaluated_questions or has_pending_status:
            status = 'partial'
            status_message = '部分题目三层评分已完成，剩余题目仍在处理中。'
    else:
        status = 'processing' if total_questions > 0 else 'empty'
        status_message = '三层评分处理中，请稍后刷新。' if total_questions > 0 else '暂无可评分题目。'
        if fallback_scored_count > 0 and not has_pending_status:
            status = 'fallback_only'
            status_message = '本场仅有回退评分样本，未纳入三层融合画像。'

    def _aggregate_confidence_breakdown(parts):
        aggregated = {}
        sample_size = 0
        for confidence_key in ('data_confidence', 'model_confidence', 'rubric_confidence', 'overall_confidence'):
            values = list(parts.get(confidence_key) or [])
            if values:
                aggregated[confidence_key] = round(_safe_avg(values), 3)
                sample_size = max(sample_size, len(values))
            else:
                aggregated[confidence_key] = None
        aggregated['sample_size'] = int(sample_size)
        return aggregated

    layers = {
        'text': {
            'overall_score': round(_safe_avg(layer_scores['text']), 1) if layer_scores['text'] else None,
            'sample_size': len(layer_scores['text']),
            'confidence_breakdown': _aggregate_confidence_breakdown(layer_confidence_parts['text']),
        },
        'speech': {
            'overall_score': round(_safe_avg(layer_scores['speech']), 1) if layer_scores['speech'] else None,
            'sample_size': len(layer_scores['speech']),
            'confidence_breakdown': _aggregate_confidence_breakdown(layer_confidence_parts['speech']),
        },
        'video': {
            'overall_score': round(_safe_avg(layer_scores['video']), 1) if layer_scores['video'] else None,
            'sample_size': len(layer_scores['video']),
            'confidence_breakdown': _aggregate_confidence_breakdown(layer_confidence_parts['video']),
        },
    }
    missing_layers = [name for name, payload in layers.items() if payload.get('overall_score') is None]

    return {
        'status': status,
        'status_message': status_message,
        'total_questions': total_questions,
        'evaluated_questions': int(evaluated_questions),
        'layers': layers,
        'fusion': {
            'overall_score': round(_safe_avg(fusion_scores), 1) if fusion_scores else None,
            'overall_confidence': round(_safe_avg(fusion_confidences), 3) if fusion_confidences else None,
            'base_weights': base_weights,
            'missing_layers': missing_layers,
            'formula': fusion_formula,
            'shortboard_applied_count': shortboard_applied_count,
            'integrity_flagged_count': integrity_flagged_count,
            'axis_confidence_breakdowns': {
                'content': _aggregate_confidence_breakdown(fusion_axis_confidence_parts['content']),
                'delivery': _aggregate_confidence_breakdown(fusion_axis_confidence_parts['delivery']),
                'presence': _aggregate_confidence_breakdown(fusion_axis_confidence_parts['presence']),
            },
        },
        'questions': questions[:8],
        'status_counts': dict(status_counts),
        'fallback_scored_count': int(fallback_scored_count),
    }


def _build_immediate_report_payload(interview_id: str):
    """按 interview_id 生成即时报告聚合数据（不含复盘数据）。"""
    normalized_id = str(interview_id or '').strip()
    if not normalized_id:
        return None, 'invalid interview id'

    interview = db_manager.get_interview_by_id(normalized_id)
    if not interview:
        return None, 'interview not found'

    statistics = db_manager.get_statistics_by_interview(normalized_id) if hasattr(db_manager, 'get_statistics_by_interview') else None
    dialogues = db_manager.get_interview_dialogues(normalized_id) if hasattr(db_manager, 'get_interview_dialogues') else []
    events = db_manager.get_events(normalized_id) if hasattr(db_manager, 'get_events') else []
    started_at = _parse_db_datetime(interview.get('start_time'))
    ended_at = _parse_db_datetime(interview.get('end_time'))
    report_path = str(interview.get('report_path') or '').strip()
    report_file_path = Path(report_path) if report_path else None
    detection_timeline = _load_detection_timeline_from_report(report_file_path)
    camera_insights = _build_camera_insights_snapshot_from_timeline(detection_timeline)

    sorted_events = sorted(
        events or [],
        key=lambda item: float(item.get('score') or 0.0),
        reverse=True,
    )
    event_type_counter = Counter(str(item.get('event_type') or 'unknown') for item in (events or []))
    top_events = [
        {
            'event_type': str(item.get('event_type') or 'unknown'),
            'score': float(item.get('score') or 0.0),
            'description': str(item.get('description') or ''),
            'timestamp': _normalize_event_offset_seconds(item.get('timestamp'), started_at),
        }
        for item in sorted_events[:8]
    ]

    structured_snapshot = _build_structured_snapshot(normalized_id, dialogues=dialogues)
    evaluation_v2 = _build_evaluation_v2_snapshot(normalized_id, dialogues=dialogues)
    final_score = _build_final_score_snapshot(structured_snapshot, evaluation_v2)
    content_performance = _build_content_performance_snapshot(normalized_id, dialogues=dialogues)
    speech_performance = _build_speech_performance_snapshot(normalized_id)
    camera_performance = _build_camera_performance_snapshot(
        statistics=statistics,
        event_type_counter=event_type_counter,
        top_events=top_events,
        max_probability=float(interview.get('max_probability') or 0.0),
        camera_insights=camera_insights,
    )
    if started_at and ended_at:
        duration_seconds = int(max(0, (ended_at - started_at).total_seconds()))
    else:
        duration_seconds = int(interview.get('duration') or 0)

    stored_max_probability = _normalize_risk_probability(interview.get('max_probability'))
    stored_avg_probability = _normalize_risk_probability(interview.get('avg_probability'))
    fallback_event_peak = max([float(item.get('score') or 0.0) for item in sorted_events] + [0.0])
    max_probability = max(stored_max_probability, _normalize_risk_probability(fallback_event_peak))
    avg_probability = stored_avg_probability
    risk_level = str(interview.get('risk_level') or '').strip().upper() or _risk_level_from_probability(max_probability)
    if risk_level not in {'LOW', 'MEDIUM', 'HIGH'}:
        risk_level = _risk_level_from_probability(max_probability)

    payload = {
        'interview_id': normalized_id,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            'start_time': interview.get('start_time'),
            'end_time': interview.get('end_time'),
            'duration_seconds': duration_seconds,
            'dialogue_count': len(dialogues or []),
        },
        'anti_cheat': {
            'risk_level': risk_level,
            'max_probability': max_probability,
            'avg_probability': avg_probability,
            'events_count': int(interview.get('events_count') or len(events or [])),
            'event_type_breakdown': [
                {'event_type': key, 'count': int(count)}
                for key, count in sorted(event_type_counter.items(), key=lambda item: item[1], reverse=True)
            ],
            'top_risk_events': top_events,
            'statistics': {
                'total_deviations': int((statistics or {}).get('total_deviations') or 0),
                'total_mouth_open': int((statistics or {}).get('total_mouth_open') or 0),
                'total_multi_person': int((statistics or {}).get('total_multi_person') or 0),
                'off_screen_ratio': float((statistics or {}).get('off_screen_ratio') or 0.0),
                'frames_processed': int((statistics or {}).get('frames_processed') or 0),
                'avg_heart_rate': float((statistics or {}).get('avg_heart_rate')) if isinstance((statistics or {}).get('avg_heart_rate'), (int, float)) else None,
                'rppg_reliable_ratio': float((statistics or {}).get('rppg_reliable_ratio')) if isinstance((statistics or {}).get('rppg_reliable_ratio'), (int, float)) else None,
            },
        },
        'final_score': final_score,
        'structured_evaluation': structured_snapshot,
        'evaluation_v2': evaluation_v2,
        'content_performance': content_performance,
        'speech_performance': speech_performance,
        'camera_performance': camera_performance,
        'next_steps': {
            'review_url': f'/review?interviewId={normalized_id}',
            'replay_url': f'/replay?interviewId={normalized_id}',
        },
    }
    return payload, ''


def _normalize_round_type(value):
    normalized = str(value or '').strip().lower()
    return normalized if normalized in INSIGHTS_TRACKED_ROUNDS else ''


def _round_label_for_insights(round_type):
    normalized = _normalize_round_type(round_type)
    if normalized == 'technical':
        return '技术面'
    if normalized == 'project':
        return '项目面'
    if normalized == 'system_design':
        return '系统设计面'
    if normalized == 'hr':
        return 'HR 综合面'
    return '未标记'


def _canonical_training_position(position):
    raw = str(position or '').strip()
    normalized = raw.lower()
    if not normalized:
        return 'java_backend'

    if normalized in {'java_backend', 'frontend', 'test_engineer', 'agent_developer', 'product_manager', 'algorithm', 'devops'}:
        return normalized

    if (
        normalized in {'backend', 'backend_engineer', 'java', 'java后端', '后端开发工程师', 'java后端工程师'}
        or ('backend' in normalized and 'front' not in normalized)
        or ('后端' in raw)
    ):
        return 'java_backend'

    if normalized in {'frontend_engineer', 'web_frontend', 'web_frontend_engineer', 'qianduan'} or ('frontend' in normalized) or ('前端' in raw):
        return 'frontend'

    if normalized in {'software_test', 'software_test_engineer', 'qa', 'qa_engineer', 'test_engineer'} or ('测试' in raw):
        return 'test_engineer'

    if normalized in {'agent开发', 'agent开发工程师', 'data_engineer'} or ('agent' in normalized) or ('智能体' in raw) or ('数据工程' in raw):
        return 'agent_developer'

    if normalized in {'product_manager', 'pm'} or ('product' in normalized and 'manager' in normalized) or ('产品' in raw):
        return 'product_manager'

    if normalized in {'algorithm_engineer', 'algorithm'} or ('algorithm' in normalized) or ('算法' in raw):
        return 'algorithm'

    return normalized


def _build_training_task_id(plan_id: str, round_type: str, priority: int, from_task_id: str = '') -> str:
    seed = f"{str(plan_id or '').strip()}|{str(round_type or '').strip().lower()}|{int(priority or 0)}|{str(from_task_id or '').strip()}"
    digest = hashlib.md5(seed.encode('utf-8')).hexdigest()[:24]
    return f"task_{digest}"


def _training_status_rank(status: str) -> int:
    mapping = {
        'completed': 7,
        'validation': 6,
        'training': 5,
        'reflow': 4,
        'planned': 3,
        'rolled_over': 2,
    }
    return mapping.get(str(status or '').strip().lower(), 1)


def _dedupe_training_tasks(task_rows):
    deduped = {}
    for item in (task_rows or []):
        task = dict(item or {})
        round_type = _normalize_round_type(task.get('round_type')) or str(task.get('round_type') or '').strip().lower()
        priority = int(task.get('priority') or 0)
        from_task_id = str(task.get('from_task_id') or '').strip()
        key = (round_type, priority, from_task_id)

        current = deduped.get(key)
        if not current:
            deduped[key] = task
            continue

        current_status_rank = _training_status_rank(current.get('status'))
        next_status_rank = _training_status_rank(task.get('status'))
        if next_status_rank > current_status_rank:
            deduped[key] = task
            continue

        if next_status_rank == current_status_rank:
            current_updated = _parse_db_datetime(current.get('updated_at') or current.get('created_at')) or datetime.min
            next_updated = _parse_db_datetime(task.get('updated_at') or task.get('created_at')) or datetime.min
            if next_updated > current_updated:
                deduped[key] = task

    return sorted(
        list(deduped.values()),
        key=lambda row: (
            int((row or {}).get('priority') or 0),
            _parse_db_datetime((row or {}).get('created_at') or '') or datetime.min,
            str((row or {}).get('task_id') or ''),
        ),
    )


def _position_label_for_insights(position):
    normalized = str(position or '').strip().lower()
    if not normalized:
        return '当前目标岗位'
    if normalized in {'test_engineer', 'software_test', 'software_test_engineer', 'qa', 'qa_engineer', '测试工程师', '软件测试工程师'}:
        return '软件测试工程师'
    if normalized in {'agent_developer', 'agent开发', 'agent开发工程师', 'data_engineer', '数据工程师'}:
        return 'Agent开发工程师'
    if normalized in {'frontend', 'frontend_engineer', 'web_frontend', 'web_frontend_engineer'}:
        return '前端开发工程师'
    if normalized in {'product_manager', 'pm'}:
        return '产品经理'
    if normalized in {'algorithm_engineer', 'algorithm'}:
        return '算法工程师'
    if normalized in {'backend', 'backend_engineer', 'java_backend'}:
        return '后端开发工程师'
    return str(position).strip()


def _parse_week_anchor(raw_value):
    text = str(raw_value or '').strip()
    if not text:
        return datetime.now()
    try:
        return datetime.strptime(text, '%Y-%m-%d')
    except Exception:
        return datetime.now()


def _build_week_range(anchor: datetime):
    safe_anchor = anchor or datetime.now()
    week_start = (safe_anchor - timedelta(days=safe_anchor.weekday())).date()
    week_end = (week_start + timedelta(days=6))
    return week_start, week_end


def _training_status_label(status: str) -> str:
    normalized = str(status or '').strip().lower()
    return TRAINING_STATUS_LABELS.get(normalized, '未知状态')


def _normalize_training_task_row(row):
    task = dict(row or {})
    task_status = str(task.get('status') or 'planned').strip().lower() or 'planned'
    task_round = _normalize_round_type(task.get('round_type'))
    task_position = _canonical_training_position(task.get('position'))
    task_payload = {
        **task,
        'task_id': str(task.get('task_id') or '').strip(),
        'round_type': task_round,
        'round_label': _round_label_for_insights(task_round),
        'position': task_position,
        'position_label': _position_label_for_insights(task_position),
        'difficulty': _normalize_interview_difficulty(task.get('difficulty')) or 'medium',
        'status': task_status,
        'status_label': _training_status_label(task_status),
        'goal_score': float(task.get('goal_score') or 75),
        'last_score': float(task.get('last_score')) if isinstance(task.get('last_score'), (int, float)) else None,
    }
    return task_payload


def _build_training_stage_summary(tasks):
    counters = {
        'planned': 0,
        'training': 0,
        'validation': 0,
        'reflow': 0,
        'completed': 0,
    }
    for item in tasks or []:
        status = str((item or {}).get('status') or '').strip().lower()
        if status in counters:
            counters[status] += 1
    counters['total'] = len(tasks or [])
    return counters


def _pick_training_round_sequence(insights_payload):
    default_rounds = list(INSIGHTS_TRACKED_ROUNDS)
    profile = (insights_payload or {}).get('cross_round_profile') if isinstance((insights_payload or {}).get('cross_round_profile'), dict) else {}
    coverage = profile.get('round_coverage') if isinstance(profile.get('round_coverage'), list) else []
    if not coverage:
        return default_rounds

    sortable = []
    for item in coverage:
        round_type = _normalize_round_type(item.get('round_type'))
        if not round_type:
            continue
        count = int(item.get('count') or 0)
        status = str(item.get('status') or '').strip().lower()
        sortable.append((0 if status == 'insufficient' else 1, count, round_type))

    sortable.sort(key=lambda x: (x[0], x[1]))
    ordered = [item[2] for item in sortable]
    for round_type in default_rounds:
        if round_type not in ordered:
            ordered.append(round_type)
    return ordered[:len(default_rounds)]


def _build_training_seed_tasks(plan_id: str, user_id: str, target_position: str, insights_payload):
    round_sequence = _pick_training_round_sequence(insights_payload)
    ai_summary = (insights_payload or {}).get('ai_summary') if isinstance((insights_payload or {}).get('ai_summary'), dict) else {}
    primary_gap = ai_summary.get('primary_gap') if isinstance(ai_summary.get('primary_gap'), dict) else {}
    focus_label = str(primary_gap.get('title') or '').strip() or '核心短板修正'
    normalized_position = _canonical_training_position(target_position)
    tasks = []
    for index, round_type in enumerate(round_sequence):
        round_label = _round_label_for_insights(round_type)
        priority = index + 1
        tasks.append({
            'task_id': _build_training_task_id(plan_id=plan_id, round_type=round_type, priority=priority),
            'plan_id': plan_id,
            'user_id': user_id,
            'title': f"{round_label}专项训练",
            'round_type': round_type,
            'position': normalized_position,
            'difficulty': 'medium',
            'focus_key': str(round_type or ''),
            'focus_label': focus_label,
            'goal_score': 75,
            'status': 'planned',
            'priority': priority,
            'from_task_id': '',
            'due_at': '',
        })
    return tasks


def _serialize_training_plan_payload(plan_row, task_rows):
    normalized_plan = dict(plan_row or {})
    target_position = _canonical_training_position(normalized_plan.get('target_position'))
    deduped_tasks = _dedupe_training_tasks(task_rows)
    normalized_tasks = [_normalize_training_task_row(item) for item in deduped_tasks]
    return {
        'plan': {
            **normalized_plan,
            'target_position': target_position,
            'target_position_label': _position_label_for_insights(target_position),
            'status_label': _training_status_label(str(normalized_plan.get('status') or '').strip().lower() or 'active'),
        },
        'tasks': normalized_tasks,
        'stage_summary': _build_training_stage_summary(normalized_tasks),
    }


def _extract_dimension_score_for_insights(dimension_items, target_key):
    target = str(target_key or '').strip().lower()
    for item in (dimension_items or []):
        key = str((item or {}).get('key') or '').strip().lower()
        score = (item or {}).get('score')
        if key == target and isinstance(score, (int, float)):
            return float(score)
    return None


def _extract_primary_round_profile_for_insights(report_payload):
    profiles = (
        (((report_payload or {}).get('structured_evaluation') or {}).get('round_aggregation') or {}).get('round_profiles')
        or []
    )
    if not profiles:
        return None
    return sorted(
        profiles,
        key=lambda item: int((item or {}).get('turn_count_used') or 0),
        reverse=True,
    )[0]


def _infer_interview_round_for_insights(interview_id):
    normalized_id = str(interview_id or '').strip()
    if not normalized_id:
        return ''

    counter = Counter()
    if hasattr(db_manager, 'get_interview_dialogues'):
        for row in (db_manager.get_interview_dialogues(normalized_id) or []):
            round_type = _normalize_round_type((row or {}).get('round_type'))
            if round_type:
                counter[round_type] += 1

    if not counter and hasattr(db_manager, 'get_interview_evaluations'):
        for row in (db_manager.get_interview_evaluations(normalized_id) or []):
            round_type = _normalize_round_type((row or {}).get('round_type'))
            if round_type:
                counter[round_type] += 1

    return counter.most_common(1)[0][0] if counter else ''


def _infer_interview_position_for_insights(interview_id):
    normalized_id = str(interview_id or '').strip()
    if not normalized_id or not hasattr(db_manager, 'get_interview_evaluations'):
        return ''

    counter = Counter()
    rows = db_manager.get_interview_evaluations(normalized_id) or []
    for row in rows:
        status = str((row or {}).get('status') or '').strip().lower()
        position = str((row or {}).get('position') or '').strip()
        if status in {'ok', 'partial_ok'} and position:
            counter[position] += 1

    if not counter:
        for row in rows:
            position = str((row or {}).get('position') or '').strip()
            if position:
                counter[position] += 1

    return counter.most_common(1)[0][0] if counter else ''


def _build_insight_item_from_payload(interview_row, report_payload=None):
    report_payload = report_payload or {}
    interview_id = str((interview_row or {}).get('interview_id') or '').strip()
    position = _infer_interview_position_for_insights(interview_id)
    structured = (report_payload.get('structured_evaluation') or {}) if isinstance(report_payload, dict) else {}
    round_aggregation = (structured.get('round_aggregation') or {}) if isinstance(structured, dict) else {}
    interview_stability = (round_aggregation.get('interview_stability') or {}) if isinstance(round_aggregation, dict) else {}
    profile = _extract_primary_round_profile_for_insights(report_payload)
    round_type = _normalize_round_type(
        (interview_row or {}).get('dominant_round')
        or (profile or {}).get('round_type')
        or _infer_interview_round_for_insights(interview_id)
    )

    final_score_payload = (report_payload.get('final_score') or {}) if isinstance(report_payload, dict) else {}
    score = final_score_payload.get('overall_score')
    if not isinstance(score, (int, float)):
        score = interview_stability.get('overall_score_stable')
    if not isinstance(score, (int, float)):
        evaluation_v2 = (report_payload.get('evaluation_v2') or {}) if isinstance(report_payload, dict) else {}
        fusion = (evaluation_v2.get('fusion') or {}) if isinstance(evaluation_v2, dict) else {}
        score = fusion.get('overall_score')
    if not isinstance(score, (int, float)):
        score = structured.get('overall_score')
    if not isinstance(score, (int, float)):
        row_score = (interview_row or {}).get('overall_score')
        if isinstance(row_score, (int, float)):
            score = row_score
    score = float(score) if isinstance(score, (int, float)) else None

    risk_probability = (((report_payload.get('anti_cheat') or {}) if isinstance(report_payload, dict) else {}).get('max_probability'))
    risk_score = None
    if isinstance(risk_probability, (int, float)):
        risk_value = float(risk_probability)
        risk_score = max(0.0, min(100.0, risk_value if risk_value > 1.0 else risk_value * 100.0))
    if not isinstance(risk_score, (int, float)):
        row_risk_probability = (interview_row or {}).get('max_probability')
        if isinstance(row_risk_probability, (int, float)):
            row_risk = float(row_risk_probability)
            risk_score = max(0.0, min(100.0, row_risk if row_risk > 1.0 else row_risk * 100.0))

    stability_score = interview_stability.get('avg_consistency_score')
    if not isinstance(stability_score, (int, float)):
        stability_score = (profile or {}).get('round_consistency_score')
    stability_score = float(stability_score) if isinstance(stability_score, (int, float)) else None

    content_score = (profile or {}).get('round_content_score')
    delivery_score = (profile or {}).get('round_delivery_score')
    presence_score = (profile or {}).get('round_presence_score')
    content_score = float(content_score) if isinstance(content_score, (int, float)) else None
    delivery_score = float(delivery_score) if isinstance(delivery_score, (int, float)) else None
    presence_score = float(presence_score) if isinstance(presence_score, (int, float)) else None

    structured_dimensions = structured.get('dimension_scores') if isinstance(structured, dict) else []
    job_match_score = _extract_dimension_score_for_insights(structured_dimensions, 'job_match')

    content_performance = (report_payload.get('content_performance') or {}) if isinstance(report_payload, dict) else {}
    speech_performance = (report_payload.get('speech_performance') or {}) if isinstance(report_payload, dict) else {}
    camera_performance = (report_payload.get('camera_performance') or {}) if isinstance(report_payload, dict) else {}
    question_evidence = (content_performance.get('question_evidence') or []) if isinstance(content_performance, dict) else []
    speech_status_message = str((speech_performance.get('status_message') or '')) if isinstance(speech_performance, dict) else ''
    camera_status_message = str((camera_performance.get('status_message') or '')) if isinstance(camera_performance, dict) else ''
    low_axis_labels = []
    for axis_key, axis_label, axis_score in (
        ('content', '内容轴', content_score),
        ('delivery', '表达轴', delivery_score),
        ('presence', '镜头轴', presence_score),
    ):
        if isinstance(axis_score, (int, float)) and float(axis_score) < 70:
            low_axis_labels.append(axis_label)

    return {
        'interview_id': interview_id,
        'created_at': (interview_row or {}).get('created_at') or (interview_row or {}).get('start_time') or '',
        'duration_seconds': int((interview_row or {}).get('duration') or ((report_payload.get('summary') or {}) if isinstance(report_payload, dict) else {}).get('duration_seconds') or 0),
        'round_type': round_type,
        'round_label': _round_label_for_insights(round_type),
        'position': position,
        'position_label': _position_label_for_insights(position),
        'score': score,
        'risk_score': risk_score,
        'stability_score': stability_score,
        'content_score': content_score,
        'delivery_score': delivery_score,
        'presence_score': presence_score,
        'job_match_score': job_match_score,
        'content_weak_dimensions': [
            str((item or {}).get('label') or '').strip()
            for item in ((content_performance.get('weak_dimensions') or [])[:3] if isinstance(content_performance, dict) else [])
            if str((item or {}).get('label') or '').strip()
        ],
        'speech_diagnosis': [
            str(item).strip()
            for item in ((speech_performance.get('diagnosis') or [])[:3] if isinstance(speech_performance, dict) else [])
            if str(item).strip()
        ],
        'camera_notes': [
            str(item).strip()
            for item in ((camera_performance.get('notes') or [])[:3] if isinstance(camera_performance, dict) else [])
            if str(item).strip()
        ],
        'content_status_message': str((content_performance.get('status_message') or '')) if isinstance(content_performance, dict) else '',
        'speech_status_message': speech_status_message.strip(),
        'camera_status_message': camera_status_message.strip(),
        'question_examples': [
            {
                'question': str((item or {}).get('question_excerpt') or '').strip(),
                'round_type': str((item or {}).get('round_type') or '').strip(),
                'overall_score': float((item or {}).get('overall_score') or 0.0) if isinstance((item or {}).get('overall_score'), (int, float)) else None,
            }
            for item in question_evidence[:2]
            if str((item or {}).get('question_excerpt') or '').strip()
        ],
        'low_axes': low_axis_labels,
        'report_url': f"/report?interviewId={interview_id}",
    }


def _build_insights_signature(interviews):
    payload = [
        {
            'interview_id': str((item or {}).get('interview_id') or '').strip(),
            'created_at': str((item or {}).get('created_at') or (item or {}).get('start_time') or ''),
            'duration': int((item or {}).get('duration') or 0),
        }
        for item in (interviews or [])
    ]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def _insights_avg_or_none(values):
    valid = [float(value) for value in (values or []) if isinstance(value, (int, float))]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 1)


def _insights_has_metric_signal(item):
    return any(
        isinstance((item or {}).get(key), (int, float))
        for key in ('score', 'stability_score', 'risk_score')
    )


def _select_recent_metric_items(items, limit=INSIGHTS_RECENT_LIMIT):
    ordered_desc = sorted(
        [item for item in (items or []) if str((item or {}).get('interview_id') or '').strip()],
        key=lambda item: _parse_db_datetime((item or {}).get('created_at')) or datetime.min,
        reverse=True,
    )
    if not ordered_desc:
        return []

    selected = []
    seen_ids = set()

    def append_item(candidate):
        interview_id = str((candidate or {}).get('interview_id') or '').strip()
        if not interview_id or interview_id in seen_ids:
            return
        seen_ids.add(interview_id)
        selected.append(candidate)

    for candidate in ordered_desc:
        if isinstance((candidate or {}).get('score'), (int, float)):
            append_item(candidate)
        if len(selected) >= int(limit):
            break

    if len(selected) < int(limit):
        for candidate in ordered_desc:
            if _insights_has_metric_signal(candidate):
                append_item(candidate)
            if len(selected) >= int(limit):
                break

    if not selected:
        selected = ordered_desc[: int(limit)]

    return sorted(
        selected[: int(limit)],
        key=lambda item: _parse_db_datetime((item or {}).get('created_at')) or datetime.min,
    )


def _build_insights_recent_metrics(items):
    ordered = sorted(
        [item for item in (items or []) if str(item.get('interview_id') or '').strip()],
        key=lambda item: _parse_db_datetime(item.get('created_at')) or datetime.min
    )
    average_score = _insights_avg_or_none([item.get('score') for item in ordered]) if ordered else None
    average_stability = _insights_avg_or_none([item.get('stability_score') for item in ordered]) if ordered else None
    average_risk = _insights_avg_or_none([item.get('risk_score') for item in ordered]) if ordered else None
    delta_from_previous = None
    if len(ordered) >= 2:
        latest = ordered[-1].get('score')
        previous = ordered[-2].get('score')
        if isinstance(latest, (int, float)) and isinstance(previous, (int, float)):
            delta_from_previous = round(float(latest) - float(previous), 1)

    return {
        'items': ordered,
        'averages': {
            'score': average_score,
            'stability': average_stability,
            'risk': average_risk,
        },
        'axis_averages': {
            'content': _insights_avg_or_none([item.get('content_score') for item in ordered]) if ordered else None,
            'delivery': _insights_avg_or_none([item.get('delivery_score') for item in ordered]) if ordered else None,
            'presence': _insights_avg_or_none([item.get('presence_score') for item in ordered]) if ordered else None,
        },
        'delta_from_previous': delta_from_previous,
    }


def _build_insights_weekly_distribution(interviews):
    threshold = datetime.now() - timedelta(days=INSIGHTS_WEEKLY_DAYS)
    counter = Counter()
    for item in (interviews or []):
        created_at = _parse_db_datetime((item or {}).get('created_at') or (item or {}).get('start_time'))
        if not created_at or created_at < threshold:
            continue
        round_type = _normalize_round_type((item or {}).get('dominant_round'))
        if not round_type:
            round_type = _infer_interview_round_for_insights((item or {}).get('interview_id'))
        if not round_type:
            continue
        counter[_round_label_for_insights(round_type)] += 1

    return [
        {'name': label, 'value': int(count)}
        for label, count in counter.items()
    ]


def _build_cross_round_sample_candidates(interviews):
    threshold = datetime.now() - timedelta(days=INSIGHTS_LOOKBACK_DAYS)
    by_round = {round_type: [] for round_type in INSIGHTS_TRACKED_ROUNDS}

    for item in (interviews or []):
        created_at = _parse_db_datetime((item or {}).get('created_at') or (item or {}).get('start_time'))
        if not created_at or created_at < threshold:
            continue
        round_type = _normalize_round_type((item or {}).get('dominant_round'))
        if not round_type:
            round_type = _infer_interview_round_for_insights((item or {}).get('interview_id'))
            item['dominant_round'] = round_type
        if not round_type or len(by_round[round_type]) >= INSIGHTS_PER_ROUND_LIMIT:
            continue
        by_round[round_type].append(item)

    return by_round


def _build_insights_fit_breakdown(sample_items, fit_score):
    scenario_values = [
        item.get('content_score')
        for item in (sample_items or [])
        if item.get('round_type') in {'project', 'system_design'}
    ]
    if not scenario_values:
        scenario_values = [item.get('content_score') for item in (sample_items or [])]

    communication_values = [
        item.get('delivery_score')
        for item in (sample_items or [])
    ]
    hr_scores = [item.get('score') for item in (sample_items or []) if item.get('round_type') == 'hr']
    if hr_scores:
        communication_values.extend(hr_scores)

    return [
        {
            'key': 'core_skill',
            'label': '岗位核心技能匹配',
            'score': round(_safe_avg([item.get('job_match_score') for item in (sample_items or [])]), 1) if sample_items else fit_score,
        },
        {
            'key': 'scenario',
            'label': '业务/场景理解匹配',
            'score': round(_safe_avg(scenario_values), 1) if scenario_values else fit_score,
        },
        {
            'key': 'communication',
            'label': '表达与协作匹配',
            'score': round(_safe_avg(communication_values), 1) if communication_values else fit_score,
        },
    ]


def _build_insights_primary_gap_candidate(sample_items):
    if not sample_items:
        return {
            'title': '综合短板待补充',
            'reason': '近期样本不足，暂时还无法识别稳定重复出现的问题模式。',
            'description': '近期样本量还不够，暂时不适合过早下结论。更建议先补齐不同轮次的有效面试，再观察是否存在真正重复出现的短板。',
            'summary': '目前可用样本仍偏少，建议再补充不同轮次的有效面试后再看综合诊断。',
            'manifestations': [],
            'impact': '现阶段更适合先补齐样本，再判断真正的主短板。',
            'focus': '先补齐技术面、项目面和 HR 面的有效样本，再做下一轮综合对比。',
            'impacted_rounds': [],
            'evidence': [],
            'score': 0.0,
        }

    theme_defs = {
        'scenario': {
            'title': '岗位场景迁移不够强',
            'reason': '回答经常停留在通用知识或标准答案层面，和目标岗位的真实业务场景连接还不够稳。',
            'impact': '这会直接拉低岗位匹配度判断，让回答看起来“基本正确”，但不够像真实能上手的候选人。',
            'focus': '下一轮回答里要主动补上业务背景、技术取舍和真实落地场景，而不是只停留在概念解释。',
        },
        'structure': {
            'title': '回答结构感不够稳定',
            'reason': '近期多轮样本里，问题拆解、主次排序和结尾收束反复出现波动，导致信息密度不稳。',
            'impact': '这会让面试官难以快速判断你的思路质量，也会削弱已经掌握内容的说服力。',
            'focus': '优先练“先结论、后拆解、再补例子”的三段式回答，把每道题压缩成更稳定的表达框架。',
        },
        'depth': {
            'title': '问题深挖层次还不够',
            'reason': '近期报告里多次出现关键概念没有展开到底、方案依据不够完整的情况。',
            'impact': '这会让技术面和项目面更容易停留在“知道名词”，但还没有形成可验证的深入理解。',
            'focus': '复盘时重点补“为什么这样设计、还有什么替代方案、代价是什么”这三类深挖追问。',
        },
        'stability': {
            'title': '临场稳定性仍有波动',
            'reason': '风险、镜头状态和响应节奏在近期样本里有反复，说明发挥质量还没有完全稳定下来。',
            'impact': '当稳定性下滑时，即使答案方向正确，也会削弱表达完成度和面试整体观感。',
            'focus': '下一阶段训练时要把限时回答和录像复盘结合起来，优先把节奏、停顿和镜头状态拉稳。',
        },
    }
    keyword_map = {
        'depth': ('深度', '原理', '底层', '技术', '设计', '架构', '完整度', '取舍', '展开'),
        'structure': ('结构', '逻辑', '拆解', '表达', '总结', '收束', '主线', '条理', '完整'),
        'scenario': ('场景', '业务', '岗位', '落地', '实践', '项目', '案例'),
        'stability': ('紧张', '停顿', '镜头', '姿态', '视线', '状态', '稳定', '卡顿', '节奏'),
    }
    theme_scores = {key: [] for key in theme_defs}
    theme_rounds = {key: Counter() for key in theme_defs}
    theme_signals = {key: Counter() for key in theme_defs}
    theme_questions = {key: [] for key in theme_defs}

    for item in sample_items:
        round_type = _normalize_round_type(item.get('round_type'))
        weak_dims = [str(label or '').strip() for label in (item.get('content_weak_dimensions') or []) if str(label or '').strip()]
        speech_notes = [str(label or '').strip() for label in (item.get('speech_diagnosis') or []) if str(label or '').strip()]
        camera_notes = [str(label or '').strip() for label in (item.get('camera_notes') or []) if str(label or '').strip()]
        question_examples = [str(label or '').strip() for label in (item.get('question_examples') or []) if str(label or '').strip()]
        merged_notes = weak_dims + speech_notes + camera_notes

        if isinstance(item.get('job_match_score'), (int, float)):
            theme_scores['scenario'].append(float(item.get('job_match_score')))
        if isinstance(item.get('delivery_score'), (int, float)):
            theme_scores['structure'].append(float(item.get('delivery_score')))
        if isinstance(item.get('content_score'), (int, float)):
            theme_scores['depth'].append(float(item.get('content_score')))
        stability_candidates = [
            value for value in (
                item.get('stability_score'),
                item.get('presence_score'),
                (100.0 - float(item.get('risk_score'))) if isinstance(item.get('risk_score'), (int, float)) else None,
            ) if isinstance(value, (int, float))
        ]
        if stability_candidates:
            theme_scores['stability'].append(_safe_avg(stability_candidates))

        for note in merged_notes:
            matched_theme = None
            lowered = note.lower()
            for theme_key, keywords in keyword_map.items():
                if any(keyword.lower() in lowered for keyword in keywords):
                    matched_theme = theme_key
                    break
            if matched_theme:
                theme_signals[matched_theme][note] += 1

        if round_type:
            low_axes = [str(axis or '').strip() for axis in (item.get('low_axes') or []) if str(axis or '').strip()]
            if '岗位匹配度' in low_axes or (isinstance(item.get('job_match_score'), (int, float)) and float(item.get('job_match_score')) < 65):
                theme_rounds['scenario'][round_type] += 1
            if '表达轴' in low_axes or (isinstance(item.get('delivery_score'), (int, float)) and float(item.get('delivery_score')) < 65):
                theme_rounds['structure'][round_type] += 1
            if '内容轴' in low_axes or (isinstance(item.get('content_score'), (int, float)) and float(item.get('content_score')) < 65):
                theme_rounds['depth'][round_type] += 1
            if '镜头轴' in low_axes or (isinstance(item.get('stability_score'), (int, float)) and float(item.get('stability_score')) < 65):
                theme_rounds['stability'][round_type] += 1

        for theme_key in theme_defs:
            if question_examples:
                theme_questions[theme_key].extend(question_examples[:1])

    ranked = []
    for theme_key, definition in theme_defs.items():
        avg_score = _safe_avg(theme_scores[theme_key]) if theme_scores[theme_key] else 0.0
        signal_bonus = min(12.0, float(sum(theme_signals[theme_key].values())) * 2.5)
        round_bonus = min(10.0, float(sum(theme_rounds[theme_key].values())) * 1.5)
        severity = 100.0 - float(avg_score) + signal_bonus + round_bonus
        ranked.append({
            'key': theme_key,
            'score': round(float(avg_score), 1),
            'severity': severity,
            **definition,
        })

    top = sorted(ranked, key=lambda item: float(item.get('severity') or 0.0), reverse=True)[0]
    top_key = str(top.get('key') or '').strip()
    impacted_rounds = [
        _round_label_for_insights(round_type)
        for round_type, _ in theme_rounds[top_key].most_common(3)
    ]

    evidence = [label for label, _ in theme_signals[top_key].most_common(3)]
    if not evidence:
        evidence = [
            str(item).strip()
            for item in (theme_questions.get(top_key) or [])
            if str(item).strip()
        ][:3]

    manifestations = []
    for label, _ in theme_signals[top_key].most_common(2):
        manifestations.append(f'近期多场报告反复提到“{label}”这一类问题。')
    for question in (theme_questions.get(top_key) or [])[:2]:
        if len(manifestations) >= 4:
            break
        manifestations.append(f'在题目“{question[:28]}{"..." if len(question) > 28 else ""}”中，这类问题也有重复出现。')

    if not manifestations:
        manifestations.append('近期四轮样本里，这一问题在不同类型面试中都出现了重复信号。')

    if impacted_rounds:
        summary = f'{top["title"]}不是单场偶发问题，而是在{"/".join(impacted_rounds[:3])}里都能看到相似信号。'
    else:
        summary = f'{top["title"]}已经在近期样本中形成重复出现的问题模式。'
    description_parts = [
        summary,
        str(top.get('reason') or '').strip(),
    ]
    if impacted_rounds:
        description_parts.append(f'这类问题目前主要出现在{"/".join(impacted_rounds[:3])}。')
    if evidence:
        description_parts.append(f'最近报告里反复出现的信号包括：{"；".join(evidence[:2])}。')
    description_parts.append(str(top.get('focus') or '').strip())
    description = ''.join(part for part in description_parts if part)

    return {
        'title': str(top.get('title') or '综合短板待补充'),
        'reason': str(top.get('reason') or ''),
        'description': description,
        'summary': summary,
        'manifestations': manifestations[:4],
        'impact': str(top.get('impact') or ''),
        'focus': str(top.get('focus') or ''),
        'score': round(float(top.get('score') or 0.0), 1),
        'impacted_rounds': impacted_rounds,
        'evidence': [str(item).strip() for item in evidence if str(item).strip()][:3],
    }


def _build_insights_profile_summary_fallback(radar_dimensions):
    dimension_map = {
        str((item or {}).get('key') or '').strip(): float((item or {}).get('score') or 0.0)
        for item in (radar_dimensions or [])
        if str((item or {}).get('key') or '').strip()
    }
    content_score = dimension_map.get('content_depth', 0.0)
    delivery_score = dimension_map.get('expression_maturity', 0.0)
    stability_score = dimension_map.get('stability_state', 0.0)
    fit_score = dimension_map.get('job_fit', 0.0)

    strongest_key = max(dimension_map.items(), key=lambda item: item[1])[0] if dimension_map else ''
    weakest_key = min(dimension_map.items(), key=lambda item: item[1])[0] if dimension_map else ''
    strongest_label = {
        'content_depth': '知识回答型',
        'expression_maturity': '表达组织型',
        'stability_state': '发挥稳定型',
        'job_fit': '岗位贴合型',
    }.get(strongest_key, '综合型')
    weakest_hint = {
        'content_depth': '内容深度仍需补强',
        'expression_maturity': '表达组织仍偏弱',
        'stability_state': '临场稳定性仍有波动',
        'job_fit': '岗位场景贴合度仍需提高',
    }.get(weakest_key, '仍需继续补齐短板')

    if fit_score >= content_score and fit_score >= delivery_score and fit_score >= stability_score:
        return f'你当前更接近{strongest_label}候选人，岗位理解已经形成主线，但{weakest_hint}。'
    return f'你当前更接近{strongest_label}候选人，近期综合样本显示{weakest_hint}。'


def _build_insights_fit_summary_fallback(position_label, fit_score, fit_breakdown):
    breakdown_sorted = sorted(
        [item for item in (fit_breakdown or []) if isinstance(item.get('score'), (int, float))],
        key=lambda item: float(item.get('score') or 0.0)
    )
    blocker = breakdown_sorted[0]['label'] if breakdown_sorted else '岗位贴合度'
    if isinstance(fit_score, (int, float)) and fit_score >= 75:
        summary = f'当前已具备较强的{position_label}岗位匹配度，整体胜任画像比较完整。'
    elif isinstance(fit_score, (int, float)) and fit_score >= 60:
        summary = f'当前对{position_label}已有较稳定的匹配基础，但还没有形成明显优势。'
    else:
        summary = f'当前与{position_label}的岗位匹配仍在建立阶段，核心能力证据还不够扎实。'
    return {
        'summary': summary,
        'blocker': f'当前主要限制项集中在{blocker}。'
    }


def _build_insights_growth_advice_fallback(primary_gap_candidate, weakest_round_label, position_label):
    gap_title = str((primary_gap_candidate or {}).get('title') or '关键短板').strip()
    gap_reason = str((primary_gap_candidate or {}).get('reason') or '').strip()
    return [
        {
            'title': '下周最该补的一项能力',
            'advice': f'优先围绕“{gap_title}”做专项训练，先把这一项从短板变成稳定项。{gap_reason}'.strip(),
        },
        {
            'title': '最值得加练的一类面试',
            'advice': f'下一阶段优先增加{weakest_round_label}的练习频次，用更接近{position_label}真实场景的问题去训练。'.strip(),
        },
        {
            'title': '下一次复盘最该关注的观察点',
            'advice': f'复盘时重点看这次回答有没有真正体现岗位场景、结构收束和关键点展开，而不只是回答“基本正确”。',
        },
    ]


def _pick_recommended_review_for_insights(sample_items, fit_breakdown):
    if not sample_items:
        return None

    fit_avg = _safe_avg([item.get('job_match_score') for item in sample_items])
    stability_avg = _safe_avg([item.get('stability_score') for item in sample_items])

    def _priority(item):
        score = float(item.get('score') or 0.0) if isinstance(item.get('score'), (int, float)) else 0.0
        job_fit = float(item.get('job_match_score') or 0.0) if isinstance(item.get('job_match_score'), (int, float)) else 0.0
        stability = float(item.get('stability_score') or 0.0) if isinstance(item.get('stability_score'), (int, float)) else 0.0
        risk = float(item.get('risk_score') or 0.0) if isinstance(item.get('risk_score'), (int, float)) else 0.0
        created_at = _parse_db_datetime(item.get('created_at')) or datetime.min
        return (score, job_fit, stability, -risk, -created_at.timestamp())

    target = sorted(sample_items, key=_priority)[0]
    reasons = []
    if isinstance(target.get('job_match_score'), (int, float)) and isinstance(fit_avg, (int, float)) and target['job_match_score'] < fit_avg:
        reasons.append('这场岗位贴合度明显低于你的近期综合水平')
    if isinstance(target.get('content_score'), (int, float)):
        round_peers = [item.get('content_score') for item in sample_items if item.get('round_type') == target.get('round_type')]
        round_avg = _safe_avg(round_peers)
        if isinstance(round_avg, (int, float)) and target['content_score'] < round_avg:
            reasons.append(f"这场{target.get('round_label') or '面试'}的内容组织低于你的同类轮次均值")
    if isinstance(target.get('stability_score'), (int, float)) and isinstance(stability_avg, (int, float)) and target['stability_score'] < stability_avg:
        reasons.append('这场临场稳定性也低于你的近期平均值')
    if not reasons:
        reasons.append('这场综合表现最能代表你当前最值得优先修正的问题')

    return {
        'interview_id': target.get('interview_id'),
        'round_label': target.get('round_label') or '面试',
        'created_at': target.get('created_at') or '',
        'score': target.get('score'),
        'reason': '；'.join(reasons[:2]),
        'report_url': target.get('report_url') or '',
    }


def _generate_insights_ai_summary(payload):
    if not INSIGHTS_AI_SUMMARY_ENABLED:
        raise RuntimeError("AI summary generation is disabled")
    if llm_manager is None or not getattr(llm_manager, 'enabled', False):
        raise RuntimeError("AI summary model is unavailable")

    target_model = str(
        os.environ.get('LLM_MODEL', '').strip()
        or config.get('assistant.qwen.fallback_text_model', '')
        or config.get('llm.model', 'qwen-max')
    ).strip() or 'qwen-max'

    system_prompt = (
        '你是面试训练平台的总结分析助手。'
        '请严格输出 JSON，不要输出 Markdown，不要解释你的推理。'
        '语言必须是自然、克制、专业的中文。'
    )
    user_prompt = (
        '请基于下面的结构化聚合数据，输出一个 JSON 对象，字段必须完全匹配：\n'
        '{\n'
        '  "profile_summary": "一句话综合画像",\n'
        '  "fit_summary": {"summary": "岗位匹配总结", "blocker": "限制项一句话"},\n'
        '  "primary_gap": {\n'
        '    "title": "主短板标题",\n'
        '    "description": "一段 2 到 4 句的完整短板描述，要像教练复盘总结，串起问题模式、影响和下一步方向",\n'
        '    "reason": "主短板说明",\n'
        '    "summary": "一句话判断这为什么是当前主短板",\n'
        '    "manifestations": ["典型表现1", "典型表现2"],\n'
        '    "impact": "它如何拖累岗位匹配或整体表现",\n'
        '    "focus": "下一步最该优先改什么",\n'
        '    "impacted_rounds": ["技术面"],\n'
        '    "evidence": ["证据1", "证据2"]\n'
        '  },\n'
        '  "growth_advice": [\n'
        '    {"title": "下周最该补的一项能力", "advice": "建议内容"},\n'
        '    {"title": "最值得加练的一类面试", "advice": "建议内容"},\n'
        '    {"title": "下一次复盘时最该关注的观察点", "advice": "建议内容"}\n'
        '  ]\n'
        '}\n'
        '要求：\n'
        '1. 必须基于输入证据，不要编造未出现的数据。\n'
        '2. 每段建议都要可执行，不要说空话。\n'
        '3. impacted_rounds 最多 3 项。\n'
        '4. evidence 最多 3 项。\n'
        '5. manifestations 最多 4 项，每项都要写成用户能感知到的具体表现，不要只写抽象名词。\n'
        '6. description 必须是一段自然中文，避免模板感，不要拆成列表。\n'
        '7. focus 必须是一个明确训练方向，不能写成泛泛鼓励。\n'
        '8. title 不要总是“知识深度不足”这类宽泛标签，优先归纳为更贴近行为的问题模式。\n'
        '9. 不要重复页面顶部已经表达过的“最强项”式结论。\n'
        f'输入数据：\n{json.dumps(payload, ensure_ascii=False, indent=2)}'
    )

    result = llm_manager.generate_structured_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=target_model,
        temperature=0.2,
        max_tokens=1200,
        timeout=INSIGHTS_AI_SUMMARY_TIMEOUT_SECONDS,
    )
    if not result.get('success'):
        raise RuntimeError(str(result.get('error') or 'AI summary generation failed'))
    data = result.get('data')
    if not isinstance(data, dict):
        raise RuntimeError("AI summary response is invalid")
    return data


def _build_insights_summary_payload():
    interviews = db_manager.get_interviews(limit=120, offset=0) or []
    interviews = sorted(
        interviews,
        key=lambda item: _parse_db_datetime((item or {}).get('created_at') or (item or {}).get('start_time')) or datetime.min,
        reverse=True,
    )

    signature = _build_insights_signature(interviews)
    cached = INSIGHTS_SUMMARY_CACHE.get(signature)
    if cached:
        cached_at = float(cached.get('cached_at') or 0.0)
        if time.time() - cached_at <= INSIGHTS_CACHE_TTL_SECONDS:
            return cached.get('payload')

    recent_scan_rows = interviews[:max(INSIGHTS_RECENT_LIMIT, INSIGHTS_RECENT_SCAN_LIMIT)]
    sample_candidates_by_round = _build_cross_round_sample_candidates(interviews)
    selected_rows = {
        str((item or {}).get('interview_id') or '').strip(): item
        for item in recent_scan_rows[:INSIGHTS_REPORT_SCAN_LIMIT]
    }
    for round_items in sample_candidates_by_round.values():
        for item in round_items:
            selected_rows[str((item or {}).get('interview_id') or '').strip()] = item

    report_payloads = {}
    enriched_items = {}
    for interview_id, interview_row in selected_rows.items():
        payload, _ = _build_immediate_report_payload(interview_id)
        report_payloads[interview_id] = payload or {}
        enriched_items[interview_id] = _build_insight_item_from_payload(interview_row, payload)

    recent_scan_items = [
        enriched_items.get(str((item or {}).get('interview_id') or '').strip()) or _build_insight_item_from_payload(item, None)
        for item in recent_scan_rows
    ]
    recent_items = _select_recent_metric_items(recent_scan_items, INSIGHTS_RECENT_LIMIT)
    weekly_distribution = _build_insights_weekly_distribution(interviews)

    sample_items = []
    for round_type in INSIGHTS_TRACKED_ROUNDS:
        for item in sample_candidates_by_round.get(round_type, []):
            enriched = enriched_items.get(str((item or {}).get('interview_id') or '').strip())
            if enriched:
                sample_items.append(enriched)

    target_position = Counter(
        str(item.get('position') or '').strip()
        for item in sample_items
        if str(item.get('position') or '').strip()
    ).most_common(1)
    target_position_value = target_position[0][0] if target_position else ''
    target_position_label = _position_label_for_insights(target_position_value)

    radar_dimensions = [
        {
            'key': 'content_depth',
            'label': '内容深度',
            'score': round(_safe_avg([item.get('content_score') for item in sample_items]), 1) if sample_items else 0.0,
        },
        {
            'key': 'expression_maturity',
            'label': '表达成熟度',
            'score': round(_safe_avg([item.get('delivery_score') for item in sample_items]), 1) if sample_items else 0.0,
        },
        {
            'key': 'stability_state',
            'label': '状态稳定性',
            'score': round(_safe_avg([
                _safe_avg([
                    item.get('stability_score'),
                    item.get('presence_score'),
                    (100.0 - float(item.get('risk_score'))) if isinstance(item.get('risk_score'), (int, float)) else None,
                ])
                for item in sample_items
            ]), 1) if sample_items else 0.0,
        },
        {
            'key': 'job_fit',
            'label': '岗位贴合度',
            'score': round(_safe_avg([item.get('job_match_score') for item in sample_items]), 1) if sample_items else 0.0,
        },
    ]

    fit_score = next((float(item.get('score') or 0.0) for item in radar_dimensions if item.get('key') == 'job_fit'), 0.0)
    fit_breakdown = _build_insights_fit_breakdown(sample_items, fit_score)
    primary_gap_candidate = _build_insights_primary_gap_candidate(sample_items)

    round_coverage = []
    round_score_map = {}
    for round_type in INSIGHTS_TRACKED_ROUNDS:
        values = [item.get('score') for item in sample_items if item.get('round_type') == round_type]
        round_score_map[round_type] = round(_safe_avg(values), 1) if values else None
        round_coverage.append({
            'round_type': round_type,
            'label': _round_label_for_insights(round_type),
            'count': len(values),
            'status': 'ready' if values else 'insufficient',
            'avg_score': round_score_map[round_type],
        })

    weakest_round_type = ''
    weakest_round_score = None
    for round_type, score in round_score_map.items():
        if not isinstance(score, (int, float)):
            continue
        if weakest_round_score is None or float(score) < float(weakest_round_score):
            weakest_round_type = round_type
            weakest_round_score = score
    weakest_round_label = _round_label_for_insights(weakest_round_type) if weakest_round_type else '技术面'

    ai_seed_payload = {
        'target_position': {
            'key': target_position_value,
            'label': target_position_label,
        },
        'sample_count': len(sample_items),
        'round_coverage': round_coverage,
        'recent_metrics': _build_insights_recent_metrics(recent_items),
        'radar_dimensions': radar_dimensions,
        'fit_score': fit_score,
        'fit_breakdown': fit_breakdown,
        'primary_gap_candidate': primary_gap_candidate,
        'recommended_review': _pick_recommended_review_for_insights(sample_items, fit_breakdown),
        'sample_evidence': [
            {
                'round_label': item.get('round_label') or '面试',
                'score': item.get('score'),
                'job_match_score': item.get('job_match_score'),
                'content_score': item.get('content_score'),
                'delivery_score': item.get('delivery_score'),
                'presence_score': item.get('presence_score'),
                'stability_score': item.get('stability_score'),
                'risk_score': item.get('risk_score'),
                'low_axes': item.get('low_axes') or [],
                'content_weak_dimensions': item.get('content_weak_dimensions') or [],
                'speech_diagnosis': item.get('speech_diagnosis') or [],
                'camera_notes': item.get('camera_notes') or [],
                'question_examples': item.get('question_examples') or [],
            }
            for item in sample_items[:8]
        ],
    }
    ai_summary = _generate_insights_ai_summary(ai_seed_payload)
    fit_fallback = _build_insights_fit_summary_fallback(target_position_label, fit_score, fit_breakdown)
    growth_fallback = _build_insights_growth_advice_fallback(primary_gap_candidate, weakest_round_label, target_position_label)
    ai_primary_gap = ai_summary.get('primary_gap') if isinstance(ai_summary.get('primary_gap'), dict) else {}
    merged_primary_gap = {
        **(primary_gap_candidate or {}),
        **ai_primary_gap,
    }

    final_payload = {
        'success': True,
        'recent_metrics': _build_insights_recent_metrics(recent_items),
        'weekly_distribution': weekly_distribution,
        'cross_round_profile': {
            'sample_count': len(sample_items),
            'covered_round_count': len([item for item in round_coverage if item.get('count')]),
            'target_position': target_position_value,
            'target_position_label': target_position_label,
            'round_coverage': round_coverage,
            'radar_dimensions': radar_dimensions,
            'fit_score': fit_score,
            'fit_breakdown': fit_breakdown,
            'primary_gap_candidate': primary_gap_candidate,
            'recommended_review': _pick_recommended_review_for_insights(sample_items, fit_breakdown),
        },
        'ai_summary': {
            'profile_summary': str(ai_summary.get('profile_summary') or _build_insights_profile_summary_fallback(radar_dimensions)),
            'fit_summary': (
                ai_summary.get('fit_summary')
                if isinstance(ai_summary.get('fit_summary'), dict)
                else fit_fallback
            ),
            'primary_gap': merged_primary_gap,
            'growth_advice': (
                ai_summary.get('growth_advice')
                if isinstance(ai_summary.get('growth_advice'), list) and ai_summary.get('growth_advice')
                else growth_fallback
            ),
        },
        'ai_summary_meta': {
            'status': 'generated',
            'required': True,
            'timeout_seconds': INSIGHTS_AI_SUMMARY_TIMEOUT_SECONDS,
        },
    }

    INSIGHTS_SUMMARY_CACHE.clear()
    INSIGHTS_SUMMARY_CACHE[signature] = {
        'cached_at': time.time(),
        'payload': final_payload,
    }
    return final_payload


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


def _load_speech_rows_for_dialogues(dialogues):
    """按对话时间窗加载并解码语音评估明细。"""
    if not dialogues or not hasattr(db_manager, 'get_speech_evaluations'):
        return []

    interview_id = str(dialogues[0].get('interview_id') or '').strip()
    if not interview_id:
        return []

    start_time = dialogues[0].get('created_at')
    end_time = dialogues[-1].get('created_at')
    raw_speech_rows = db_manager.get_speech_evaluations(
        interview_id=interview_id,
        start_time=start_time,
        end_time=end_time,
    )
    return _decode_speech_rows(raw_speech_rows)


@app.route('/api/growth-report/latest')
def get_latest_growth_report():
    """Return latest interview report plus historical trend data."""
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

        empty_history = {
            'session_count': 0,
            'average_score': 0.0,
            'best_score': 0.0,
            'latest_score': 0.0,
            'delta_from_previous': None,
            'trend': [],
            'sessions': [],
        }

        if not rows:
            return jsonify({
                'success': True,
                'report': None,
                'latest_report': None,
                'trend': [],
                'history': empty_history,
                'message': 'no interview dialogue data',
            })

        sessions_desc = _split_recent_sessions(rows)
        if not sessions_desc:
            return jsonify({
                'success': True,
                'report': None,
                'latest_report': None,
                'trend': [],
                'history': empty_history,
                'message': 'no analyzable sessions',
            })

        latest_session = list(reversed(sessions_desc[0]))

        latest_report = _build_growth_report(
            latest_session,
            speech_rows=_load_speech_rows_for_dialogues(latest_session),
        )

        trend = []
        history_reports = []
        sessions_for_trend = list(reversed(sessions_desc))
        for idx, session_desc in enumerate(sessions_for_trend, start=1):
            session = list(reversed(session_desc))
            session_report = _build_growth_report(
                session,
                speech_rows=_load_speech_rows_for_dialogues(session),
            )
            interview_id = str(session[0].get('interview_id') or '').strip() if session else ''
            started_at = session[0].get('created_at') if session else ''
            ended_at = session[-1].get('created_at') if session else ''
            label = f'Session {idx}'
            history_reports.append({
                'session_index': idx,
                'label': label,
                'interview_id': interview_id,
                'started_at': started_at,
                'ended_at': ended_at,
                'summary': session_report.get('summary', {}),
                'dimensions': session_report.get('dimensions', []),
                'meta': session_report.get('meta', {}),
            })
            trend.append({
                'label': label,
                'interview_id': interview_id,
                'started_at': started_at,
                'overall_score': session_report.get('summary', {}).get('overall_score', 0.0),
            })

        trend_scores = [float(item.get('overall_score') or 0.0) for item in trend]
        latest_score = float(latest_report.get('summary', {}).get('overall_score') or 0.0)
        previous_score = float(trend[-2].get('overall_score') or 0.0) if len(trend) >= 2 else None
        delta_from_previous = round(latest_score - previous_score, 1) if previous_score is not None else None
        best_score = round(max(trend_scores), 1) if trend_scores else round(latest_score, 1)
        average_score = round(sum(trend_scores) / len(trend_scores), 1) if trend_scores else round(latest_score, 1)

        history = {
            'session_count': len(history_reports),
            'average_score': average_score,
            'best_score': best_score,
            'latest_score': round(latest_score, 1),
            'delta_from_previous': delta_from_previous,
            'trend': trend,
            'sessions': history_reports[-8:],
        }

        return jsonify({
            'success': True,
            'report': latest_report,
            'latest_report': latest_report,
            'trend': trend,
            'history': history,
        })

    except Exception as e:
        logger.error(f'????????: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/growth-report/interview/<interview_id>')
def get_growth_report_by_interview(interview_id):
    """按 interview_id 返回单场复盘。"""
    try:
        normalized_id = str(interview_id or '').strip()
        if not normalized_id:
            return jsonify({
                'success': False,
                'error': 'invalid interview id'
            }), 400

        dialogues = db_manager.get_interview_dialogues(normalized_id) if hasattr(db_manager, 'get_interview_dialogues') else []
        if not dialogues:
            return jsonify({
                'success': False,
                'error': 'interview dialogue not found'
            }), 404

        dialogues_sorted = sorted(
            dialogues,
            key=lambda item: _parse_db_datetime(item.get('created_at')) or datetime.min
        )

        report = _build_growth_report(
            dialogues_sorted,
            speech_rows=_load_speech_rows_for_dialogues(dialogues_sorted),
        )

        started_at = dialogues_sorted[0].get('created_at') if dialogues_sorted else ''
        ended_at = dialogues_sorted[-1].get('created_at') if dialogues_sorted else ''
        overall_score = float(report.get('summary', {}).get('overall_score') or 0.0)
        trend = [{
            'label': 'Session 1',
            'interview_id': normalized_id,
            'started_at': started_at,
            'overall_score': overall_score,
        }]
        history = {
            'session_count': 1,
            'average_score': round(overall_score, 1),
            'best_score': round(overall_score, 1),
            'latest_score': round(overall_score, 1),
            'delta_from_previous': None,
            'trend': trend,
            'sessions': [{
                'session_index': 1,
                'label': 'Session 1',
                'interview_id': normalized_id,
                'started_at': started_at,
                'ended_at': ended_at,
                'summary': report.get('summary', {}),
                'dimensions': report.get('dimensions', []),
                'meta': report.get('meta', {}),
            }],
        }

        return jsonify({
            'success': True,
            'report': report,
            'latest_report': report,
            'trend': trend,
            'history': history,
        })

    except Exception as e:
        logger.error(f'获取单场成长报告错误: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/report/interview/<interview_id>')
def get_immediate_report_by_interview(interview_id):
    """按 interview_id 获取即时报告（与复盘数据分离）。"""
    try:
        payload, error = _build_immediate_report_payload(interview_id)
        if not payload:
            status_code = 400 if error == 'invalid interview id' else 404
            return jsonify({'success': False, 'error': error}), status_code
        return jsonify({'success': True, 'report': payload})
    except Exception as e:
        logger.error(f'获取即时报告失败: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/report/latest')
def get_latest_immediate_report():
    """获取最近一场面试的即时报告（与复盘分离）。"""
    try:
        latest_id = ''
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT interview_id
                FROM interviews
                WHERE
                    (COALESCE(TRIM(end_time), '') != '')
                    OR (COALESCE(duration, 0) > 0)
                ORDER BY datetime(COALESCE(end_time, created_at)) DESC, id DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            latest_id = str(row['interview_id']).strip() if row and row['interview_id'] else ''

        if not latest_id:
            return jsonify({'success': False, 'error': 'no interview found'}), 404

        payload, error = _build_immediate_report_payload(latest_id)
        if not payload:
            status_code = 400 if error == 'invalid interview id' else 404
            return jsonify({'success': False, 'error': error}), status_code
        return jsonify({'success': True, 'report': payload})
    except Exception as e:
        logger.error(f'获取最近即时报告失败: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/evaluation/trace/<interview_id>/<turn_id>')
def get_evaluation_trace(interview_id, turn_id):
    """按 interview_id + turn_id 返回评分审计链路。"""
    try:
        normalized_interview_id = str(interview_id or '').strip()
        normalized_turn_id = str(turn_id or '').strip()
        if not normalized_interview_id or not normalized_turn_id:
            return jsonify({'success': False, 'error': 'invalid interview_id or turn_id'}), 400

        if not hasattr(db_manager, 'get_turn_scorecard'):
            return jsonify({'success': False, 'error': 'evaluation scorecard API unavailable'}), 503

        raw_scorecard = db_manager.get_turn_scorecard(normalized_interview_id, normalized_turn_id) or {}
        scorecard = _normalize_turn_scorecard(raw_scorecard)
        evaluation = scorecard.get('evaluation') or {}
        if not evaluation:
            return jsonify({'success': False, 'error': 'scorecard not found'}), 404

        return jsonify({
            'success': True,
            'interview_id': normalized_interview_id,
            'turn_id': normalized_turn_id,
            'scorecard': scorecard,
            'snapshot': (evaluation.get('scoring_snapshot') if isinstance(evaluation.get('scoring_snapshot'), dict) else {}),
            'trace': scorecard.get('traces') or [],
        })
    except Exception as e:
        logger.error(f'获取评分审计链路失败: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/evaluation/scorecard/<interview_id>/<turn_id>')
def get_evaluation_scorecard(interview_id, turn_id):
    """按 interview_id + turn_id 返回标准单题评分卡。"""
    try:
        normalized_interview_id = str(interview_id or '').strip()
        normalized_turn_id = str(turn_id or '').strip()
        if not normalized_interview_id or not normalized_turn_id:
            return jsonify({'success': False, 'error': 'invalid interview_id or turn_id'}), 400

        if not hasattr(db_manager, 'get_turn_scorecard'):
            return jsonify({'success': False, 'error': 'evaluation scorecard API unavailable'}), 503

        raw_scorecard = db_manager.get_turn_scorecard(normalized_interview_id, normalized_turn_id) or {}
        scorecard = _normalize_turn_scorecard(raw_scorecard)
        if not (scorecard.get('evaluation') or {}):
            return jsonify({'success': False, 'error': 'scorecard not found'}), 404

        return jsonify({
            'success': True,
            'interview_id': normalized_interview_id,
            'turn_id': normalized_turn_id,
            'scorecard': scorecard,
        })
    except Exception as e:
        logger.error(f'获取单题评分卡失败: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/interview/video/init', methods=['POST'])
def api_video_init():
    """初始化视频分片上传会话。"""
    try:
        payload = request.get_json(silent=True) or {}
        session_id = str(payload.get('session_id', '')).strip()
        interview_id = str(payload.get('interview_id', '')).strip() or (f"interview_{session_id}" if session_id else '')
        if not interview_id:
            return jsonify({'success': False, 'error': 'missing interview_id'}), 400

        result = video_upload_service.init_upload(
            session_id=session_id,
            interview_id=interview_id,
            mime_type=str(payload.get('mime_type', 'video/webm')).strip(),
            codec=str(payload.get('codec', '')).strip(),
        )
        return jsonify({
            'success': True,
            **result,
        })
    except Exception as e:
        logger.error(f"初始化视频上传失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/interview/video/chunk', methods=['POST'])
def api_video_chunk():
    """接收视频分片。支持 multipart file 或 base64 字段。"""
    try:
        payload = request.get_json(silent=True) or {}
        upload_id = str(request.form.get('upload_id', '') or payload.get('upload_id', '')).strip()
        part_no_raw = request.form.get('part_no', '') or payload.get('part_no', 0)
        try:
            part_no = int(part_no_raw)
        except Exception:
            part_no = 0

        chunk_data = b''
        if 'chunk' in request.files:
            file_obj = request.files['chunk']
            chunk_data = file_obj.read() or b''
        else:
            chunk_base64 = str(payload.get('chunk_base64', '')).strip()
            if chunk_base64:
                chunk_data = base64.b64decode(chunk_base64)

        result = video_upload_service.save_chunk(upload_id=upload_id, part_no=part_no, chunk_data=chunk_data)
        if not result.get('success'):
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error(f"上传视频分片失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/interview/video/finalize', methods=['POST'])
def api_video_finalize():
    """合并分片并写入视频资产。"""
    try:
        payload = request.get_json(silent=True) or {}
        upload_id = str(payload.get('upload_id', '')).strip()
        interview_id = str(payload.get('interview_id', '')).strip()
        if not upload_id:
            return jsonify({'success': False, 'error': 'missing upload_id'}), 400

        result = video_upload_service.finalize_upload(upload_id=upload_id, interview_id=interview_id)
        if not result.get('success'):
            return jsonify(result), 400

        db_result = db_manager.save_or_update_interview_asset({
            'interview_id': result.get('interview_id', ''),
            'upload_id': upload_id,
            'storage_key': Path(result.get('final_path', '')).name,
            'video_url': '',
            'local_path': result.get('final_path', ''),
            'duration_ms': result.get('duration_ms', 0),
            'codec': result.get('codec', ''),
            'status': result.get('status', 'uploaded'),
            'metadata_json': json.dumps({
                'raw_path': result.get('raw_path', ''),
            }, ensure_ascii=False),
        })

        return jsonify({
            'success': True,
            'interview_id': result.get('interview_id', ''),
            'asset_id': db_result.get('id', 0),
            'status': result.get('status', 'uploaded'),
            'duration_ms': result.get('duration_ms', 0),
        })
    except Exception as e:
        logger.error(f"视频 finalize 失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/interview/video/<interview_id>/play-url')
def api_video_play_url(interview_id):
    """返回播放地址（本地回放签名 URL）。"""
    try:
        interview_id = str(interview_id or '').strip()
        if not interview_id:
            return jsonify({'success': False, 'error': 'invalid interview_id'}), 400

        asset = db_manager.get_interview_asset(interview_id) if hasattr(db_manager, 'get_interview_asset') else None
        if not asset:
            return jsonify({'success': False, 'error': 'video asset not found'}), 404

        expires_in = request.args.get('expires_in', 3600, type=int) or 3600
        sig_payload = video_upload_service.sign_local_playback(interview_id, expires_in=expires_in)
        play_url = f"/api/interview/video/raw/{interview_id}?expires={sig_payload['expires']}&sig={sig_payload['sig']}"

        return jsonify({
            'success': True,
            'play_url': play_url,
            'expires_in': int(expires_in),
            'duration_ms': float(asset.get('duration_ms') or 0.0),
            'status': asset.get('status', ''),
            'codec': asset.get('codec', ''),
        })
    except Exception as e:
        logger.error(f"获取视频播放地址失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


def _resolve_local_video_path(raw_path: str) -> Path | None:
    normalized = str(raw_path or '').strip()
    if not normalized:
        return None

    raw = Path(normalized)
    candidates = [raw] if raw.is_absolute() else [Path.cwd() / raw]
    app_root = Path(__file__).resolve().parent
    project_root = app_root.parent
    allowed_roots = {app_root.resolve(), project_root.resolve(), Path.cwd().resolve()}
    candidates.extend([app_root / raw, project_root / raw])

    parts = raw.parts
    if parts and str(parts[0]).lower() == 'backend':
        stripped = Path(*parts[1:]) if len(parts) > 1 else Path()
        candidates.extend([app_root / stripped, project_root / stripped])

    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if not resolved.exists() or not resolved.is_file():
            continue
        if not any(str(resolved).startswith(str(root)) for root in allowed_roots):
            continue
        return resolved
    return None


@app.route('/api/interview/video/raw/<interview_id>')
def api_video_raw(interview_id):
    """本地视频回放（签名鉴权）。"""
    try:
        interview_id = str(interview_id or '').strip()
        expires = request.args.get('expires', '', type=str)
        sig = request.args.get('sig', '', type=str)
        if not video_upload_service.verify_local_playback(interview_id, expires=expires, sig=sig):
            return jsonify({'success': False, 'error': 'invalid signature'}), 403

        asset = db_manager.get_interview_asset(interview_id) if hasattr(db_manager, 'get_interview_asset') else None
        if not asset:
            return jsonify({'success': False, 'error': 'video asset not found'}), 404
        local_path = _resolve_local_video_path(str(asset.get('local_path', '')).strip())
        if not local_path:
            return jsonify({'success': False, 'error': 'video file missing'}), 404

        response = send_file(
            str(local_path),
            mimetype='video/mp4' if str(local_path).lower().endswith('.mp4') else 'video/webm',
            conditional=True,
        )
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'private, max-age=0, must-revalidate'
        return response
    except Exception as e:
        logger.error(f"本地视频回放失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/review/generate/<interview_id>', methods=['POST'])
def api_generate_replay(interview_id):
    """异步触发复盘生成任务。"""
    try:
        normalized_id = str(interview_id or '').strip()
        if not normalized_id:
            return jsonify({'success': False, 'error': 'invalid interview_id'}), 400
        payload = request.get_json(silent=True) or {}
        force = bool(payload.get('force', False))
        result = replay_task_manager.enqueue(normalized_id, force=force)
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"触发复盘任务失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/review/tasks/<task_id>')
def api_get_review_task(task_id):
    """查询复盘任务状态。"""
    try:
        task = replay_task_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'task not found'}), 404
        return jsonify({'success': True, 'task': task})
    except Exception as e:
        logger.error(f"查询复盘任务状态失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/review/behavior-analyze/<interview_id>', methods=['POST'])
def api_behavior_analyze(interview_id):
    """异步触发二期行为分析（emotion/posture/gaze）。"""
    try:
        normalized_id = str(interview_id or '').strip()
        if not normalized_id:
            return jsonify({'success': False, 'error': 'invalid interview_id'}), 400
        payload = request.get_json(silent=True) or {}
        force = bool(payload.get('force', False))
        result = behavior_task_manager.enqueue(normalized_id, force=force)
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"触发行为分析任务失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/review/behavior-tasks/<task_id>')
def api_behavior_task(task_id):
    """查询行为分析任务状态。"""
    try:
        task = behavior_task_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'task not found'}), 404
        return jsonify({'success': True, 'task': task})
    except Exception as e:
        logger.error(f"查询行为分析任务状态失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/replay/<interview_id>')
def api_get_replay(interview_id):
    """聚合复盘接口：视频 + 锚点 + A/B/C/D。"""
    try:
        normalized_id = str(interview_id or '').strip()
        if not normalized_id:
            return jsonify({'success': False, 'error': 'invalid interview_id'}), 400

        # 若当前无产物，先即时生成一版，保证首个调用有返回。
        preview_payload = replay_service.build_replay_payload(normalized_id)
        if not (preview_payload.get('transcript_anchor_list') or preview_payload.get('tags')):
            replay_service.generate_replay(normalized_id, force=False)
            preview_payload = replay_service.build_replay_payload(normalized_id)

        video_meta = {'available': False}
        asset = db_manager.get_interview_asset(normalized_id) if hasattr(db_manager, 'get_interview_asset') else None
        if asset:
            sig_payload = video_upload_service.sign_local_playback(normalized_id, expires_in=3600)
            play_url = f"/api/interview/video/raw/{normalized_id}?expires={sig_payload['expires']}&sig={sig_payload['sig']}"
            video_meta = {
                'available': True,
                'play_url': play_url,
                'duration_ms': float(asset.get('duration_ms') or 0.0),
                'status': asset.get('status', ''),
                'codec': asset.get('codec', ''),
            }
            tag_types = {
                str(item.get('tag_type') or '').strip().lower()
                for item in (preview_payload.get('tags') or [])
                if isinstance(item, dict)
            }
            if not ({'emotion', 'posture', 'gaze'} & tag_types):
                _maybe_enqueue_behavior_analysis(normalized_id, force=False)

        return jsonify({
            **preview_payload,
            'video': video_meta,
        })
    except Exception as e:
        logger.error(f"获取复盘聚合数据失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

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


@app.route('/api/insights/summary')
def get_insights_summary():
    """返回最近面试总览聚合数据。"""
    try:
        payload = _build_insights_summary_payload()
        return jsonify(payload)
    except Exception as e:
        logger.error(f"获取 insights summary 错误: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'recent_metrics': {'items': [], 'averages': {}, 'axis_averages': {}, 'delta_from_previous': None},
            'weekly_distribution': [],
            'cross_round_profile': {
                'sample_count': 0,
                'covered_round_count': 0,
                'target_position': '',
                'target_position_label': '当前目标岗位',
                'round_coverage': [],
                'radar_dimensions': [],
                'fit_score': 0.0,
                'fit_breakdown': [],
                'primary_gap_candidate': {},
                'recommended_review': None,
            },
            'ai_summary': {
                'profile_summary': '',
                'fit_summary': {'summary': '', 'blocker': ''},
                'primary_gap': {},
                'growth_advice': [],
            },
        }), 500


@app.route('/api/training/weekly-plan')
def get_training_weekly_plan():
    """获取或自动生成本周训练计划。"""
    try:
        if not hasattr(db_manager, 'get_training_plan_bundle'):
            return jsonify({'success': False, 'error': 'training api unavailable'}), 503

        user_id = str(request.args.get('user_id', 'default') or 'default').strip() or 'default'
        anchor = _parse_week_anchor(request.args.get('week_start_date', ''))
        week_start, week_end = _build_week_range(anchor)
        week_start_text = week_start.strftime('%Y-%m-%d')
        week_end_text = week_end.strftime('%Y-%m-%d')

        bundle = db_manager.get_training_plan_bundle(user_id=user_id, week_start_date=week_start_text)
        plan = (bundle or {}).get('plan')
        tasks = (bundle or {}).get('tasks') or []

        insights_payload = {}
        if not plan or not tasks:
            try:
                insights_payload = _build_insights_summary_payload() or {}
            except Exception:
                insights_payload = {}

        if not plan:
            profile = insights_payload.get('cross_round_profile') if isinstance(insights_payload.get('cross_round_profile'), dict) else {}
            target_position = _canonical_training_position(profile.get('target_position'))
            plan_result = db_manager.upsert_training_week_plan({
                'plan_id': f"plan_{uuid.uuid4().hex}",
                'user_id': user_id,
                'week_start_date': week_start_text,
                'week_end_date': week_end_text,
                'target_position': target_position,
                'status': 'active',
                'source_summary_json': json.dumps({
                    'target_position': target_position,
                    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }, ensure_ascii=False),
            })
            if not plan_result.get('success'):
                return jsonify({'success': False, 'error': plan_result.get('error') or 'create weekly plan failed'}), 500
            plan = plan_result.get('plan') or {}

        if not tasks:
            target_position = _canonical_training_position((plan or {}).get('target_position'))
            generated_tasks = _build_training_seed_tasks(
                plan_id=str((plan or {}).get('plan_id') or '').strip(),
                user_id=user_id,
                target_position=target_position,
                insights_payload=insights_payload,
            )
            insert_result = db_manager.insert_training_tasks(generated_tasks)
            if not insert_result.get('success'):
                return jsonify({'success': False, 'error': insert_result.get('error') or 'create training tasks failed'}), 500
            bundle = db_manager.get_training_plan_bundle(user_id=user_id, week_start_date=week_start_text)
            plan = (bundle or {}).get('plan') or plan
            tasks = (bundle or {}).get('tasks') or []

        payload = _serialize_training_plan_payload(plan, tasks)
        return jsonify({
            'success': True,
            'week_start_date': week_start_text,
            'week_end_date': week_end_text,
            **payload,
        })
    except Exception as e:
        logger.error(f"获取训练周计划失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/training/tasks/<task_id>/start-training', methods=['POST'])
def start_training_task(task_id):
    """将任务置为训练中，并返回题库过滤参数。"""
    try:
        if not hasattr(db_manager, 'get_training_task'):
            return jsonify({'success': False, 'error': 'training api unavailable'}), 503

        normalized_task_id = str(task_id or '').strip()
        task = db_manager.get_training_task(normalized_task_id)
        if not task:
            return jsonify({'success': False, 'error': 'task not found'}), 404

        update_result = db_manager.update_training_task_status(
            normalized_task_id,
            status='training',
            set_training_started=True,
        )
        if not update_result.get('success'):
            return jsonify({'success': False, 'error': update_result.get('error') or 'update task failed'}), 500

        refreshed = db_manager.get_training_task(normalized_task_id) or task
        normalized_task = _normalize_training_task_row(refreshed)
        db_manager.create_training_task_attempt({
            'attempt_id': f"attempt_{uuid.uuid4().hex}",
            'task_id': normalized_task_id,
            'user_id': str(normalized_task.get('user_id') or 'default').strip() or 'default',
            'attempt_type': 'training_start',
            'interview_id': '',
            'score': None,
            'passed': None,
            'notes': 'start training',
        })

        round_type = str(normalized_task.get('round_type') or 'technical').strip()
        position = _canonical_training_position(normalized_task.get('position'))
        difficulty = str(normalized_task.get('difficulty') or 'medium').strip()
        strict_bank = db_manager.get_question_bank(
            round_type=round_type or None,
            position=position or None,
            difficulty=difficulty or None,
        )
        has_strict_questions = bool(strict_bank)
        fallback_filter = None
        if not has_strict_questions:
            fallback_bank = db_manager.get_question_bank(
                round_type=None,
                position=position or None,
                difficulty=difficulty or None,
            )
            if fallback_bank:
                fallback_filter = {
                    'round_type': '',
                    'position': position,
                    'difficulty': difficulty,
                }

        navigate_url = (
            f"/dashboard/questions?round_type={round_type}&position={position}"
            f"&difficulty={difficulty}&training_task_id={normalized_task_id}"
        )
        if fallback_filter:
            navigate_url = (
                f"/dashboard/questions?position={position}&difficulty={difficulty}"
                f"&training_task_id={normalized_task_id}"
            )

        return jsonify({
            'success': True,
            'task': normalized_task,
            'question_filter': {
                'round_type': round_type,
                'position': position,
                'difficulty': difficulty,
                'focus_label': str(normalized_task.get('focus_label') or '').strip(),
            },
            'fallback_filter': fallback_filter,
            'navigate_url': navigate_url,
        })
    except Exception as e:
        logger.error(f"开启训练任务失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/training/tasks/<task_id>/start-validation', methods=['POST'])
def start_validation_task(task_id):
    """将任务置为待验收，并返回 3 题短测配置。"""
    try:
        if not hasattr(db_manager, 'get_training_task'):
            return jsonify({'success': False, 'error': 'training api unavailable'}), 503

        normalized_task_id = str(task_id or '').strip()
        task = db_manager.get_training_task(normalized_task_id)
        if not task:
            return jsonify({'success': False, 'error': 'task not found'}), 404

        update_result = db_manager.update_training_task_status(
            normalized_task_id,
            status='validation',
            set_validation_started=True,
        )
        if not update_result.get('success'):
            return jsonify({'success': False, 'error': update_result.get('error') or 'update task failed'}), 500

        refreshed = db_manager.get_training_task(normalized_task_id) or task
        normalized_task = _normalize_training_task_row(refreshed)

        question_bank = db_manager.get_question_bank(
            round_type=normalized_task.get('round_type') or None,
            position=normalized_task.get('position') or None,
            difficulty=normalized_task.get('difficulty') or None,
        )
        fallback_applied = False
        if not question_bank:
            question_bank = db_manager.get_question_bank(
                round_type=None,
                position=normalized_task.get('position') or None,
                difficulty=normalized_task.get('difficulty') or None,
            )
            fallback_applied = bool(question_bank)
        preview_questions = [
            {
                'id': str(item.get('id') or '').strip(),
                'question': str(item.get('question') or '').strip(),
                'category': str(item.get('category') or '').strip(),
            }
            for item in (question_bank or [])[:TRAINING_VALIDATION_QUESTION_COUNT]
            if str(item.get('question') or '').strip()
        ]

        db_manager.create_training_task_attempt({
            'attempt_id': f"attempt_{uuid.uuid4().hex}",
            'task_id': normalized_task_id,
            'user_id': str(normalized_task.get('user_id') or 'default').strip() or 'default',
            'attempt_type': 'validation_start',
            'interview_id': '',
            'score': None,
            'passed': None,
            'notes': 'start validation',
        })

        return jsonify({
            'success': True,
            'task': normalized_task,
            'fallback_applied': fallback_applied,
            'validation_questions_preview': preview_questions,
            'interview_config': {
                'round': str(normalized_task.get('round_type') or 'technical').strip() or 'technical',
                'position': _canonical_training_position(normalized_task.get('position')),
                'difficulty': str(normalized_task.get('difficulty') or 'medium').strip() or 'medium',
                'trainingTaskId': normalized_task_id,
                'trainingMode': 'coach_drill',
                'auto_end_min_questions': TRAINING_VALIDATION_QUESTION_COUNT,
                'auto_end_max_questions': TRAINING_VALIDATION_QUESTION_COUNT,
            },
            'navigate_url': '/interview',
        })
    except Exception as e:
        logger.error(f"开启验收任务失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/training/tasks/<task_id>/mark-result', methods=['POST'])
def mark_training_task_result(task_id):
    """记录任务验收结果（达标/未达标）。"""
    try:
        if not hasattr(db_manager, 'get_training_task'):
            return jsonify({'success': False, 'error': 'training api unavailable'}), 503

        payload = request.get_json(silent=True) or {}
        normalized_task_id = str(task_id or '').strip()
        task = db_manager.get_training_task(normalized_task_id)
        if not task:
            return jsonify({'success': False, 'error': 'task not found'}), 404

        raw_passed = payload.get('passed')
        if isinstance(raw_passed, bool):
            passed = raw_passed
        else:
            passed = str(raw_passed or '').strip().lower() in {'1', 'true', 'yes', 'pass', 'passed'}

        score_value = payload.get('score')
        score = None
        if isinstance(score_value, (int, float)):
            score = float(score_value)
        else:
            try:
                if str(score_value or '').strip() != '':
                    score = float(score_value)
            except Exception:
                score = None

        interview_id = str(payload.get('interview_id') or '').strip()
        notes = str(payload.get('notes') or '').strip()
        status = 'completed' if passed else 'reflow'

        update_result = db_manager.update_training_task_status(
            normalized_task_id,
            status=status,
            last_score=score,
            last_interview_id=interview_id,
        )
        if not update_result.get('success'):
            return jsonify({'success': False, 'error': update_result.get('error') or 'update task failed'}), 500

        user_id = str(task.get('user_id') or 'default').strip() or 'default'
        db_manager.create_training_task_attempt({
            'attempt_id': f"attempt_{uuid.uuid4().hex}",
            'task_id': normalized_task_id,
            'user_id': user_id,
            'attempt_type': 'validation_result',
            'interview_id': interview_id,
            'score': score,
            'passed': 1 if passed else 0,
            'notes': notes,
        })
        db_manager.create_training_task_validation({
            'validation_id': f"validation_{uuid.uuid4().hex}",
            'task_id': normalized_task_id,
            'user_id': user_id,
            'validation_interview_id': interview_id,
            'score': score,
            'passed': 1 if passed else 0,
            'decision': 'pass' if passed else 'reflow',
        })

        refreshed = db_manager.get_training_task(normalized_task_id) or task
        return jsonify({
            'success': True,
            'task': _normalize_training_task_row(refreshed),
        })
    except Exception as e:
        logger.error(f"记录训练任务结果失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/training/tasks/reflow', methods=['POST'])
def reflow_training_tasks():
    """将未达标任务回流到下周计划。"""
    try:
        if not hasattr(db_manager, 'get_training_plan_bundle'):
            return jsonify({'success': False, 'error': 'training api unavailable'}), 503

        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get('user_id') or 'default').strip() or 'default'
        source_anchor = _parse_week_anchor(payload.get('week_start_date', ''))
        source_week_start, source_week_end = _build_week_range(source_anchor)
        source_start_text = source_week_start.strftime('%Y-%m-%d')

        source_bundle = db_manager.get_training_plan_bundle(user_id=user_id, week_start_date=source_start_text)
        source_plan = (source_bundle or {}).get('plan')
        source_tasks = (source_bundle or {}).get('tasks') or []
        if not source_plan:
            return jsonify({'success': False, 'error': 'source weekly plan not found'}), 404

        reflow_candidates = [
            item for item in source_tasks
            if str((item or {}).get('status') or '').strip().lower() == 'reflow'
        ]
        if not reflow_candidates:
            return jsonify({
                'success': True,
                'created_count': 0,
                'message': '当前周无待回流任务',
            })

        next_week_anchor = datetime.combine(source_week_start, datetime.min.time()) + timedelta(days=7)
        next_week_start, next_week_end = _build_week_range(next_week_anchor)
        next_start_text = next_week_start.strftime('%Y-%m-%d')
        next_end_text = next_week_end.strftime('%Y-%m-%d')

        next_bundle = db_manager.get_training_plan_bundle(user_id=user_id, week_start_date=next_start_text)
        next_plan = (next_bundle or {}).get('plan')
        next_tasks = (next_bundle or {}).get('tasks') or []

        if not next_plan:
            target_position = _canonical_training_position((source_plan or {}).get('target_position'))
            create_next_plan_result = db_manager.upsert_training_week_plan({
                'plan_id': f"plan_{uuid.uuid4().hex}",
                'user_id': user_id,
                'week_start_date': next_start_text,
                'week_end_date': next_end_text,
                'target_position': target_position,
                'status': 'active',
                'source_summary_json': json.dumps({
                    'generated_by': 'reflow',
                    'from_week': source_start_text,
                }, ensure_ascii=False),
            })
            if not create_next_plan_result.get('success'):
                return jsonify({'success': False, 'error': create_next_plan_result.get('error') or 'create next weekly plan failed'}), 500
            next_plan = create_next_plan_result.get('plan') or {}
            next_tasks = []

        existing_from_task_ids = {
            str(item.get('from_task_id') or '').strip()
            for item in next_tasks
            if str(item.get('from_task_id') or '').strip()
        }

        prepared_tasks = []
        for index, item in enumerate(reflow_candidates, start=1):
            source_task_id = str(item.get('task_id') or '').strip()
            if source_task_id in existing_from_task_ids:
                continue
            round_type = _normalize_round_type(item.get('round_type')) or 'technical'
            priority = int(item.get('priority') or index)
            prepared_tasks.append({
                'task_id': _build_training_task_id(
                    plan_id=str((next_plan or {}).get('plan_id') or '').strip(),
                    round_type=round_type,
                    priority=priority,
                    from_task_id=source_task_id,
                ),
                'plan_id': str((next_plan or {}).get('plan_id') or '').strip(),
                'user_id': user_id,
                'title': f"{str(item.get('title') or '回流任务').strip()}（回流）",
                'round_type': round_type,
                'position': _canonical_training_position(item.get('position') or (next_plan or {}).get('target_position')),
                'difficulty': _normalize_interview_difficulty(item.get('difficulty')) or 'medium',
                'focus_key': str(item.get('focus_key') or '').strip(),
                'focus_label': str(item.get('focus_label') or '').strip() or '回流复训',
                'goal_score': float(item.get('goal_score') or 75),
                'status': 'planned',
                'priority': priority,
                'from_task_id': source_task_id,
                'due_at': '',
            })

        insert_result = db_manager.insert_training_tasks(prepared_tasks)
        if not insert_result.get('success'):
            return jsonify({'success': False, 'error': insert_result.get('error') or 'insert reflow tasks failed'}), 500

        for item in reflow_candidates:
            source_task_id = str(item.get('task_id') or '').strip()
            if not source_task_id:
                continue
            if any(str(task.get('from_task_id') or '').strip() == source_task_id for task in prepared_tasks):
                db_manager.update_training_task_status(source_task_id, status='rolled_over')

        refreshed_next_bundle = db_manager.get_training_plan_bundle(user_id=user_id, week_start_date=next_start_text)
        payload_result = _serialize_training_plan_payload(
            (refreshed_next_bundle or {}).get('plan'),
            (refreshed_next_bundle or {}).get('tasks') or [],
        )

        return jsonify({
            'success': True,
            'created_count': int(insert_result.get('count') or 0),
            'source_week': {
                'week_start_date': source_start_text,
                'week_end_date': source_week_end.strftime('%Y-%m-%d'),
            },
            'next_week': {
                'week_start_date': next_start_text,
                'week_end_date': next_end_text,
            },
            **payload_result,
        })
    except Exception as e:
        logger.error(f"执行训练任务回流失败：{e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/interviews')
def get_interviews_from_db():
    """从数据库获取面试记录列表"""
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        interviews = db_manager.get_interviews(limit=limit, offset=offset)
        interview_ids = [
            str(item.get('interview_id') or '').strip()
            for item in interviews
            if str(item.get('interview_id') or '').strip()
        ]
        score_map = (
            db_manager.get_interview_structured_score_map(interview_ids)
            if hasattr(db_manager, 'get_interview_structured_score_map')
            else {}
        )
        for item in interviews:
            interview_id = str(item.get('interview_id') or '').strip()
            if not interview_id:
                item['overall_score'] = None
                item['scored_turns'] = 0
                item['score_source'] = 'not_available'
                item['structured_status'] = 'empty'
                item['dominant_round'] = ''
                continue

            # 列表接口走批量评分摘要，避免每一行同步构建完整报告快照。
            dialogues = db_manager.get_interview_dialogues(interview_id) if hasattr(db_manager, 'get_interview_dialogues') else []
            score_info = dict(score_map.get(interview_id) or {})
            round_counter = Counter(
                str(row.get('round_type') or '').strip().lower()
                for row in dialogues
                if str(row.get('round_type') or '').strip()
            )
            dominant_round = round_counter.most_common(1)[0][0] if round_counter else ''
            item['dominant_round'] = dominant_round
            evaluated_questions = int(score_info.get('scored_turns') or 0)
            display_score = score_info.get('overall_score')

            if isinstance(display_score, (int, float)):
                item['overall_score'] = float(display_score)
                item['scored_turns'] = evaluated_questions
                item['score_source'] = score_info.get('score_source') or 'structured_evaluation'
                item['structured_status'] = 'ready'
            else:
                item['overall_score'] = None
                item['scored_turns'] = evaluated_questions
                item['score_source'] = 'not_available'
                item['structured_status'] = 'processing' if dialogues else 'empty'
            item['final_score'] = {
                'overall_score': item['overall_score'],
                'source': item['score_source'],
                'components': {
                    'structured_overall_score': item['overall_score'],
                },
            }

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

from routes.resume import create_resume_blueprint

app.register_blueprint(create_resume_blueprint(
    db_manager=db_manager,
    resume_parser=resume_parser,
    resume_optimizer_service=resume_optimizer_service,
    resume_optimizer_import_error=resume_optimizer_import_error,
    logger=logger,
))


# ==================== 应用启动 ====================

if __name__ == '__main__':
    try:
        logger.info("=" * 60)
        logger.info("启动 AI 模拟面试平台")
        logger.info("=" * 60)

        run_options = {
            'host': FLASK_HOST,
            'port': FLASK_PORT,
            'debug': FLASK_DEBUG,
            'use_reloader': False,
        }
        if socketio.async_mode == 'threading':
            run_options['allow_unsafe_werkzeug'] = True

        socketio.run(app, **run_options)
    except Exception as e:
        logger.error(f"应用启动失败：{e}", exc_info=True)
        raise
