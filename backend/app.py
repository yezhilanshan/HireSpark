"""
Flask 主服务 - Socket.IO 实时通信
AI 模拟面试与能力提升平台【改造进行中】
"""
from flask import Flask, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS # 跨域资源共享中间件
import base64
import hashlib
import time
import os
import json
import threading
import uuid
import re
from datetime import datetime
from pathlib import Path
from collections import Counter
from urllib.parse import urlparse

# 导入自定义模块
from utils import DataManager, ReportGenerator
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
ASR_PENDING_AUDIO_MAX_CHUNKS = max(4, min(240, _safe_int(os.environ.get("ASR_PENDING_AUDIO_MAX_CHUNKS", 80), 80)))
ASR_PENDING_AUDIO_MAX_BYTES = max(
    32000,
    min(4 * 1024 * 1024, _safe_int(os.environ.get("ASR_PENDING_AUDIO_MAX_BYTES", 512000), 512000)),
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
        frontend_url = os.environ.get('NEXT_PUBLIC_BACKEND_URL', '').strip()
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

if rag_service is None:
    logger.error(f"RAG 初始化失败，相关功能不可用：{rag_import_error}")
elif getattr(rag_service, 'enabled', False):
    logger.info("RAG 模块初始化成功")
else:
    logger.info("RAG 模块未启用或未配置")

# 初始化工具类
logger.info("初始化工具模块...")
data_manager = DataManager()
report_generator = ReportGenerator()
db_manager = DatabaseManager()
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

video_upload_service = VideoUploadService(logger=logger)
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
        if question_id:
            analysis_result = rag_service.analyze_answer(
                question_id=question_id,
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
    if draft_units >= 8 and rewritten_units <= max(4, int(draft_units * 0.62)):
        merged = merge_answer_text(draft, rewritten)
        if merged and _count_text_units(merged) >= int(draft_units * 0.9):
            return merged, 'merge_guard_short_rewrite'
        return draft, 'fallback_short_rewrite'

    overlap_ratio = _text_token_overlap_ratio(draft, rewritten)
    if draft_units >= 8 and rewritten_units >= 8 and overlap_ratio < 0.35:
        if rewritten_units >= max(8, int(draft_units * 0.92)):
            return rewritten, 'asr_final_rewrite_low_overlap_preferred'
        return draft, 'fallback_low_overlap_draft'

    merged = merge_answer_text(draft, rewritten)
    if merged and _count_text_units(merged) >= max(draft_units, rewritten_units):
        return merged, 'merge_rewrite_and_draft'
    if rewritten_units >= draft_units:
        return rewritten, 'asr_final_rewrite_preferred'
    return draft, 'fallback_draft_preferred'


def _rewrite_answer_text(runtime, answer_session: AnswerSession, audio_path: str = "") -> dict:
    if not audio_path or asr_manager is None or not hasattr(asr_manager, 'transcribe_file'):
        return {'text': answer_session.merged_text_draft, 'word_timestamps': [], 'confidence': None, 'mode': 'fallback_no_file'}

    prompt_parts = []
    if ASR_FINAL_USE_HINT_PROMPT:
        prompt_parts = [
            "这是一次中文技术面试回答的音频转写，请尽量准确保留技术术语、英文缩写、数字和项目名称。",
            "只输出转写后的正文，不要补充解释，不要改写成总结。",
        ]
        if runtime.current_question:
            prompt_parts.append(f"当前题目：{runtime.current_question}")
        technical_terms = _extract_technical_terms(runtime.current_question, answer_session.merged_text_draft)
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

    if expected_speech_epoch and current.speech_epoch != expected_speech_epoch:
        _log_runtime_event(
            current,
            'answer_session_finalize_dropped',
            level='debug',
            source=reason,
            answer_session_id=answer_session.answer_session_id,
            expected_speech_epoch=expected_speech_epoch,
            current_speech_epoch=current.speech_epoch,
            reason_detail='speech_epoch_advanced_before_schedule',
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
        if expected_speech_epoch and live_runtime.speech_epoch != expected_speech_epoch:
            _log_runtime_event(
                live_runtime,
                'answer_session_finalize_dropped',
                level='debug',
                source=reason,
                answer_session_id=answer_session_id,
                expected_speech_epoch=expected_speech_epoch,
                current_speech_epoch=live_runtime.speech_epoch,
                reason_detail='speech_epoch_advanced',
            )
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
    if segment_text:
        answer_session.finalize_segment(segment_text)
    if speech_epoch and speech_epoch >= getattr(answer_session, 'last_speech_epoch', 0):
        answer_session.last_speech_epoch = speech_epoch
    if asr_generation and asr_generation >= getattr(answer_session, 'last_asr_generation', 0):
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
        next_question = llm_manager.generate_round_question(
            round_type=round_type,
            position=position,
            difficulty=target_difficulty,
            rag_context=_merge_text_blocks(decision_context, next_question_context)
        )
        if next_question:
            intro = "这个点先到这里，我们换一个方向。" if next_action == 'switch_question' else "这部分回答得比较扎实，我们提升一点难度。"
            final_state = planning_state
            if next_question_plan:
                final_state = rag_service.mark_question_asked(planning_state, next_question_plan)
            return (
                f"{intro}\n\n{next_question}",
                analysis_result,
                followup_decision,
                final_state,
                next_question_plan,
            )

    feedback = llm_manager.process_answer_with_round(
        user_answer=user_answer,
        current_question=current_question,
        position=position,
        round_type=round_type,
        chat_history=chat_history,
        rag_context=_merge_text_blocks(rag_context, decision_context)
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
        off_screen_ratio = float(item.get('off_screen_ratio') or 0.0)
        flags = [str(flag).strip().lower() for flag in (item.get('flags') or []) if str(flag).strip()]
        offscreen_values.append(off_screen_ratio)

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
            })

    avg_off_screen_ratio = (sum(offscreen_values) / len(offscreen_values)) if offscreen_values else 0.0
    stats = {
        'total_deviations': int(total_deviations),
        'total_mouth_open': int(total_mouth_open),
        'total_multi_person': int(total_multi_person),
        'off_screen_ratio': round(avg_off_screen_ratio, 4),
        'frames_processed': int((report_data or {}).get('summary', {}).get('frames_processed', 0) or len(timeline)),
    }
    return events, stats


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
                question_id=str(question_id or "").strip() or _extract_question_id_from_plan(runtime.last_question_plan),
                user_id=runtime.user_id,
                round_type=runtime.round_type,
                position=runtime.position,
                question=question,
                answer=answer,
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
            _final_text, _partial_text, preview_text = _build_pending_asr_text(live_runtime)
            answer_session = _ensure_answer_session(live_runtime)
            answer_session.mark_status('recording')
            answer_session.update_partial(preview_text)
            _emit_realtime_speech_metrics(
                live_runtime,
                answer_session,
                is_speaking=True,
                text_snapshot=preview_text or partial_text,
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
                    f"preview_units={_count_text_units(preview_text)}"
                ),
                partial_preview=partial_text[:160],
                final_preview=previous_final[:160],
                text_snapshot=preview_text[:200],
            )
            _emit_answer_session_update(live_runtime, source='asr_partial')
            socketio.emit('asr_partial', {
                'session_id': live_runtime.session_id,
                'turn_id': live_runtime.turn_id,
                'stream_id': live_runtime.active_asr_stream_id,
                'speech_epoch': live_runtime.active_asr_speech_epoch or live_runtime.speech_epoch,
                'asr_generation': asr_generation,
                'text': partial_text,
                'full_text': preview_text,
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
            previous_final = _merge_asr_fragments(live_runtime.pending_asr_finals)
            merged_final = _merge_asr_fragments(live_runtime.pending_asr_finals)
            merged_final = merge_answer_text(merged_final, final_text) if merged_final else final_text
            live_runtime.pending_asr_finals = [merged_final]
            live_runtime.pending_asr_partials.clear()
            _merged_final, _merged_partial, preview_text = _build_pending_asr_text(live_runtime)
            answer_session = _ensure_answer_session(live_runtime)
            answer_session.mark_status('recording')
            answer_session.update_partial(preview_text)
            _emit_realtime_speech_metrics(
                live_runtime,
                answer_session,
                is_speaking=True,
                text_snapshot=preview_text or merged_final,
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
                    f"preview_units={_count_text_units(preview_text)}"
                ),
                partial_preview=previous_partial[:160],
                final_preview=final_text[:160],
                text_snapshot=preview_text[:200],
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
                'preview_text': preview_text,
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

    runtime.pending_commit_timer = threading.Timer(0.45, commit_task)
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

    current_question = runtime.current_question or _get_last_interviewer_question(runtime.chat_history)
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

    def llm_task():
        try:
            feedback, analysis_result, followup_decision, next_state, next_question_plan = _generate_policy_response(
                user_answer=normalized_answer,
                current_question=current_question,
                position=runtime.position,
                round_type=runtime.round_type,
                chat_history=runtime.chat_history,
                difficulty=runtime.difficulty,
                interview_state=runtime.interview_state,
                question_plan=runtime.last_question_plan
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

            next_action = str((followup_decision or {}).get('next_action', 'ask_followup')).strip()
            current.interview_state = next_state
            if next_action in {'switch_question', 'raise_difficulty'} and next_question_plan:
                current.last_question_plan = next_question_plan
                current.last_answer_analysis = None
                if next_action == 'raise_difficulty':
                    current.difficulty = (followup_decision or {}).get('difficulty_target', current.difficulty)
            else:
                current.last_answer_analysis = analysis_result

            normalized_reply = speech_normalizer.normalize(feedback)
            next_turn_id = current.next_turn()
            _set_runtime_asr_lock(current, False)
            current.current_question = normalized_reply['display_text']
            _track_question_timeline(current, next_turn_id, normalized_reply['spoken_text'] or normalized_reply['display_text'])
            current.chat_history.append({
                'role': 'interviewer',
                'content': current.current_question
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
        },
        'services': {
            'llm': bool(llm_manager and getattr(llm_manager, 'enabled', False)),
            'rag': bool(rag_service),
            'asr': bool(asr_manager and getattr(asr_manager, 'enabled', False)),
            'tts': tts_manager.get_status() if tts_manager else {
                'enabled': False,
                'error': tts_import_error or 'tts manager unavailable'
            }
        }
    })


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


@app.route('/api/question-bank')
def get_question_bank():
    """读取数据库题库（interview_rounds.questions）"""
    try:
        round_type = str(request.args.get('round_type', '') or '').strip()
        position = str(request.args.get('position', '') or '').strip()
        difficulty = str(request.args.get('difficulty', '') or '').strip()
        keyword = str(request.args.get('keyword', '') or '').strip().lower()
        limit = request.args.get('limit', 500, type=int) or 500
        limit = max(1, min(limit, 2000))

        question_bank = db_manager.get_question_bank(
            round_type=round_type or None,
            position=position or None,
            difficulty=difficulty or None,
        )

        if keyword:
            question_bank = [
                item for item in question_bank
                if keyword in str(item.get('question', '')).lower()
                or keyword in str(item.get('category', '')).lower()
                or keyword in str(item.get('round_type', '')).lower()
                or keyword in str(item.get('position', '')).lower()
                or keyword in str(item.get('description', '')).lower()
            ]

        total = len(question_bank)
        truncated = question_bank[:limit]
        categories = sorted({
            str(item.get('category', '')).strip()
            for item in question_bank
            if str(item.get('category', '')).strip()
        })
        facets = db_manager.get_question_bank_facets()

        return jsonify({
            'success': True,
            'count': len(truncated),
            'total': total,
            'limit': limit,
            'question_bank': truncated,
            'categories': categories,
            'facets': facets,
            'message': '' if total > 0 else 'question bank is empty',
        })

    except Exception as e:
        logger.error(f"获取题库失败：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'question_bank': [],
            'categories': [],
            'facets': {
                'round_types': [],
                'positions': [],
                'difficulties': [],
            }
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
    runtime = session_registry.remove(client_id)
    if runtime:
        runtime.ended = True
        if runtime.pending_commit_timer:
            runtime.pending_commit_timer.cancel()
        _cancel_answer_finalize_timer(runtime)
        _reset_pending_asr_audio(runtime)
        if asr_manager and runtime.active_asr_stream_id:
            asr_manager.stop_session(runtime.active_asr_stream_id)
        _log_runtime_event(runtime, 'disconnect_cleanup')
    logger.info(f"客户端已断开 - ID: {client_id}")


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

        round_type = data.get('round_type', data.get('round', 'technical')) if data else 'technical'
        position = data.get('position', 'java_backend') if data else 'java_backend'
        difficulty = data.get('difficulty', 'medium') if data else 'medium'
        user_id = data.get('user_id', 'default') if data else 'default'
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

        initial_question = ""
        if llm_manager:
            rag_context, question_plan = _build_question_rag_context(
                position=position,
                difficulty=difficulty,
                round_type=round_type,
                interview_state=runtime.interview_state
            )
            runtime.last_question_plan = question_plan
            initial_question = llm_manager.generate_round_question(
                round_type=round_type,
                position=position,
                difficulty=difficulty,
                rag_context=rag_context
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

        normalized_question = speech_normalizer.normalize(initial_question)
        runtime.next_turn()
        _set_runtime_asr_lock(runtime, False)
        runtime.current_question = normalized_question['display_text']
        _track_question_timeline(runtime, runtime.turn_id, normalized_question['spoken_text'] or normalized_question['display_text'])
        runtime.chat_history.append({
            'role': 'interviewer',
            'content': runtime.current_question
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
            finalize_payload = video_upload_service.finalize_upload(
                upload_id=upload_id,
                interview_id=runtime.interview_id,
            )
            if finalize_payload.get('success'):
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

        report_path = report_generator.generate_report(report_data) if report_data else ""
        if report_data:
            derived_events, derived_stats = _derive_detection_events_and_stats(report_data)
            db_manager.save_interview({
                'interview_id': runtime.interview_id,
                'start_time': report_data.get('summary', {}).get('start_time'),
                'end_time': report_data.get('summary', {}).get('end_time'),
                'duration': report_data.get('summary', {}).get('duration', 0),
                'risk_level': report_data.get('summary', {}).get('risk_level', 'LOW'),
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
    _cancel_answer_finalize_timer(runtime)
    _reset_pending_asr_audio(runtime)
    answer_session = _ensure_answer_session(runtime)
    answer_session.last_speech_epoch = runtime.speech_epoch
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
            answer_session.mark_final(text_override or answer_session.merged_text_draft, reason='manual_submit')
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
        runtime.data_manager.add_frame_data({
            'type': 'detection_state',
            'probability': float(payload.get('risk_score', 0) or 0),
            'risk_level': payload.get('risk_level', 'LOW'),
            'has_face': payload.get('has_face', True),
            'face_count': payload.get('face_count', 1),
            'off_screen_ratio': payload.get('off_screen_ratio', 0),
            'flags': payload.get('flags', []),
            'timestamp': time.time()
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

        _log_runtime_event(runtime, 'llm_generate_question', position=position, difficulty=difficulty)

        emit('llm_generating', {
            'message': '正在生成问题...',
            'status': 'generating'
        })

        question = llm_manager.generate_interview_question(
            position=position,
            difficulty=difficulty,
            context=context,
            rag_context=rag_context
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
        for key in ('layer1_json', 'layer2_json'):
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


def _build_legacy_score_breakdown_from_dimensions(dimension_items):
    score_map = {item.get('key'): float(item.get('score', 0.0) or 0.0) for item in (dimension_items or [])}

    def _pick_score(*keys):
        for key in keys:
            if key in score_map:
                return round(float(score_map.get(key, 0.0) or 0.0), 1)
        return 0.0

    return {
        'technical_correctness': _pick_score('technical_accuracy', 'technical_correctness'),
        'knowledge_depth': _pick_score('knowledge_depth'),
        'logical_rigor': _pick_score('logic', 'logical_rigor'),
        'expression_clarity': _pick_score('clarity', 'communication', 'expression_clarity'),
        'job_match': _pick_score('job_match'),
        'adaptability': _pick_score('reflection', 'tradeoff_awareness', 'adaptability'),
    }


def _build_growth_report_v2(dialogues, evaluation_rows=None, speech_rows=None):
    speech_summary = aggregate_expression_metrics(speech_rows or [])
    decoded_evaluations = _decode_evaluation_rows(evaluation_rows or [])
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
            dim_scores = (layer2.get('final_dimension_scores') or layer2.get('dimension_scores') or {})
            speech_adjustments = (layer2.get('speech_adjustments') or {})
            summary = (layer2.get('summary') or {})
            round_type = str(row.get('round_type') or 'technical')
            turn_id = str(row.get('turn_id') or '').strip()
            overall_score = float(
                layer2.get('overall_score_final')
                or row.get('overall_score')
                or layer2.get('overall_score')
                or 0.0
            )
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

        score_breakdown = _build_legacy_score_breakdown_from_dimensions(dimension_items)

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
        overall_score = 0.0
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
                'turn_id': item.get('id', ''),
                'question_id': '',
                'round_type': item.get('round_type', 'unknown'),
                'question': item.get('question', ''),
                'answer': item.get('answer', ''),
                'rubric_level': '',
                'overall_score': 0.0,
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
            'level': _score_to_level(overall_score),
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

    valid_turn_ids = {
        str(item.get('turn_id') or '').strip()
        for item in (dialogues or [])
        if str(item.get('turn_id') or '').strip()
    }
    if valid_turn_ids:
        decoded_rows = [
            row for row in decoded_rows
            if str(row.get('turn_id') or '').strip() in valid_turn_ids
        ]

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

        layer2 = row.get('layer2') or {}
        score_value = (
            layer2.get('overall_score_final')
            or row.get('overall_score')
            or layer2.get('overall_score')
        )

        if status in valid_score_status and isinstance(score_value, (int, float)):
            score = _clamp_score(score_value)
            all_scores.append(score)
            round_type = str(row.get('round_type') or 'technical').strip() or 'technical'
            round_scores.setdefault(round_type, []).append(score)
            if turn_id:
                scored_turns.add(turn_id)

        dim_map = layer2.get('final_dimension_scores') or layer2.get('dimension_scores') or {}
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
    return {
        'status': status,
        'status_message': status_message,
        'total_questions': total_questions,
        'evaluated_questions': int(evaluated_questions),
        'overall_score': overall_score,
        'level': _score_to_level(overall_score) if overall_score is not None else None,
        'round_breakdown': round_breakdown,
        'dimension_scores': dimension_items,
        'status_counts': dict(status_counts),
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

    report_path = str(interview.get('report_path') or '').strip()
    report_file_path = Path(report_path)
    if report_path and not report_file_path.is_absolute():
        report_file_path = Path(report_path)
    report_exists = bool(report_path and report_file_path.exists())
    report_size = int(report_file_path.stat().st_size) if report_exists else 0

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
            'timestamp': float(item.get('timestamp') or 0.0),
        }
        for item in sorted_events[:8]
    ]

    structured_snapshot = _build_structured_snapshot(normalized_id, dialogues=dialogues)
    started_at = _parse_db_datetime(interview.get('start_time'))
    ended_at = _parse_db_datetime(interview.get('end_time'))
    if started_at and ended_at:
        duration_seconds = int(max(0, (ended_at - started_at).total_seconds()))
    else:
        duration_seconds = int(interview.get('duration') or 0)

    payload = {
        'interview_id': normalized_id,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            'start_time': interview.get('start_time'),
            'end_time': interview.get('end_time'),
            'duration_seconds': duration_seconds,
            'dialogue_count': len(dialogues or []),
        },
        'pdf_report': {
            'path': report_path,
            'exists': report_exists,
            'size_bytes': report_size,
        },
        'anti_cheat': {
            'risk_level': str(interview.get('risk_level') or 'LOW'),
            'max_probability': float(interview.get('max_probability') or 0.0),
            'avg_probability': float(interview.get('avg_probability') or 0.0),
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
            },
        },
        'structured_evaluation': structured_snapshot,
        'next_steps': {
            'review_url': f'/review?interviewId={normalized_id}',
            'replay_url': f'/replay?interviewId={normalized_id}',
        },
    }
    return payload, ''


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
                    OR (COALESCE(TRIM(report_path), '') != '')
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
        local_path = str(asset.get('local_path', '')).strip()
        if not local_path or not Path(local_path).exists():
            return jsonify({'success': False, 'error': 'video file missing'}), 404

        return send_file(
            local_path,
            mimetype='video/mp4' if local_path.lower().endswith('.mp4') else 'video/webm',
            conditional=True,
        )
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


@app.route('/api/interviews')
def get_interviews_from_db():
    """从数据库获取面试记录列表"""
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        interviews = db_manager.get_interviews(limit=limit, offset=offset)
        interview_ids = [
            str(item.get('interview_id') or '').strip()
            for item in (interviews or [])
            if str(item.get('interview_id') or '').strip()
        ]
        structured_score_map = {}
        if interview_ids and hasattr(db_manager, 'get_interview_structured_score_map'):
            structured_score_map = db_manager.get_interview_structured_score_map(interview_ids)

        for item in interviews:
            interview_id = str(item.get('interview_id') or '').strip()
            score_payload = structured_score_map.get(interview_id)
            if score_payload:
                item['overall_score'] = float(score_payload.get('overall_score') or 0.0)
                item['scored_turns'] = int(score_payload.get('scored_turns') or 0)
                item['score_source'] = 'structured_evaluation'
            else:
                item['overall_score'] = None
                item['scored_turns'] = 0
                item['score_source'] = 'not_available'

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
