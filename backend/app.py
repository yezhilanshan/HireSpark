"""
Flask 主服务 - Socket.IO 实时通信
AI 模拟面试与能力提升平台【改造进行中】
"""
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS # 跨域资源共享中间件
import base64
import hashlib
import time
import os
import json
import threading
import uuid
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
from utils.answer_session import AnswerSession, LONG_PAUSE_SECONDS, SHORT_PAUSE_SECONDS
from utils.session_orchestrator import SessionRegistry, StateOrchestrator
from utils.speech_normalizer import SpeechTextNormalizer
from utils.speech_metrics import compute_final_speech_metrics, aggregate_expression_metrics
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
    normalized = (text or '').strip()
    if not normalized:
        return True
    if len(normalized) < 2:
        return True
    fillers = {'啊', '嗯', '呃', '哦', '哎', '额', '唉', '哈', '噢', '嘛', '呗', '咯'}
    if normalized in fillers:
        return True
    noise_phrases = {'谢谢', '感谢', '好的', '好的呢', '然后', '还有', '那个', '这个', '就是'}
    return normalized in noise_phrases


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
    final_text = ' '.join(runtime.pending_asr_finals).strip()
    partial_text = ' '.join(runtime.pending_asr_partials).strip()
    runtime.pending_asr_partials.clear()
    runtime.pending_asr_finals.clear()
    if asr_generation and runtime.last_finalized_asr_generation == asr_generation:
        runtime.last_finalized_asr_generation = 0
        runtime.last_finalized_asr_speech_epoch = 0
    return str(final_text or partial_text).strip()


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


def _rewrite_answer_text(runtime, answer_session: AnswerSession, audio_path: str = "") -> dict:
    if not audio_path or asr_manager is None or not hasattr(asr_manager, 'transcribe_file'):
        return {'text': answer_session.merged_text_draft, 'word_timestamps': [], 'confidence': None, 'mode': 'fallback_no_file'}

    prompt_parts = [
        "这是一次中文技术面试回答的音频转写，请尽量准确保留技术术语、英文缩写、数字和项目名称。",
        "只输出转写后的正文，不要补充解释，不要改写成总结。",
    ]
    if runtime.current_question:
        prompt_parts.append(f"当前题目：{runtime.current_question}")
    if answer_session.merged_text_draft:
        prompt_parts.append(f"实时草稿：{answer_session.merged_text_draft}")

    rewrite_payload = {}
    if hasattr(asr_manager, 'transcribe_file_with_meta'):
        rewrite_payload = asr_manager.transcribe_file_with_meta(
            audio_path=audio_path,
            prompt="\n".join(part for part in prompt_parts if part),
        ) or {}
    else:
        rewrite_text = asr_manager.transcribe_file(
            audio_path=audio_path,
            prompt="\n".join(part for part in prompt_parts if part),
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
    final_text = str(rewrite_payload.get('text') or '').strip() or final_candidate
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

    segment_text = _consume_runtime_segment_text(current, asr_generation=asr_generation)
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
    current.active_asr_generation = 0
    current.active_asr_speech_epoch = 0
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


def _log_runtime_event(runtime, event: str, level: str = 'info', **fields):
    payload = _runtime_log_fields(runtime, event=event, **fields)
    log_fn = getattr(logger, level, logger.info)
    details = ' '.join(f"{key}={payload[key]!r}" for key in sorted(payload))
    log_fn(f"[runtime] {details}")


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
        'round_type': runtime.round_type,
        'question': question,
        'answer': answer,
        'llm_feedback': feedback
    })

    answer_session = runtime.current_answer_session
    if answer_session and hasattr(db_manager, 'save_or_update_speech_evaluation'):
        normalized_turn_id = str(turn_id or runtime.turn_id or '').strip() or f"turn_{runtime.turn_index}"
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

    if evaluation_service is not None:
        try:
            enqueue_result = evaluation_service.enqueue_evaluation(
                interview_id=runtime.interview_id,
                turn_id=str(turn_id or runtime.turn_id or "").strip() or f"turn_{runtime.turn_index}",
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
    _log_runtime_event(
        runtime,
        'session_notice',
        source='detection_state',
        display_text=normalized['display_text'][:120],
        spoken_text=normalized['spoken_text'][:120],
    )
    socketio.emit('session_control_notice', {
        'session_id': runtime.session_id,
        'turn_id': runtime.turn_id,
        'job_id': '',
        'display_text': normalized['display_text'],
        'spoken_text': normalized['spoken_text'],
        'interrupt_epoch': runtime.interrupt_epoch,
        'timestamp': time.time()
    }, to=runtime.client_id)
    _start_runtime_tts(runtime, normalized['spoken_text'], runtime.turn_id, source='session_control')


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

                ok = tts_manager.synthesize(sentence, callback=send_audio_chunk)
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
            live_runtime.pending_asr_partials = [text]
            answer_session = _ensure_answer_session(live_runtime)
            preview_text = ' '.join(live_runtime.pending_asr_finals + [text]).strip()
            answer_session.mark_status('recording')
            answer_session.update_partial(preview_text)
            _emit_realtime_speech_metrics(
                live_runtime,
                answer_session,
                is_speaking=True,
                text_snapshot=preview_text or text,
                source='asr_partial',
            )
            _print_asr_console(live_runtime, 'partial', text, asr_generation)
            _log_runtime_event(
                live_runtime,
                'asr_partial',
                level='debug',
                stream_id=live_runtime.active_asr_stream_id,
                asr_generation=asr_generation,
                partial_preview=text[:120],
            )
            _emit_answer_session_update(live_runtime, source='asr_partial')
            socketio.emit('asr_partial', {
                'session_id': live_runtime.session_id,
                'turn_id': live_runtime.turn_id,
                'stream_id': live_runtime.active_asr_stream_id,
                'text': text,
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
            if not live_runtime.pending_asr_finals or live_runtime.pending_asr_finals[-1] != text:
                live_runtime.pending_asr_finals.append(text)
            answer_session = _ensure_answer_session(live_runtime)
            answer_session.mark_status('recording')
            answer_session.update_partial(' '.join(live_runtime.pending_asr_finals).strip())
            _emit_realtime_speech_metrics(
                live_runtime,
                answer_session,
                is_speaking=True,
                text_snapshot=' '.join(live_runtime.pending_asr_finals).strip(),
                source='asr_final',
            )
            _print_asr_console(live_runtime, 'final', text, asr_generation)
            _log_runtime_event(
                live_runtime,
                'asr_final',
                stream_id=live_runtime.active_asr_stream_id,
                asr_generation=asr_generation,
                final_preview=text[:160],
                final_count=len(live_runtime.pending_asr_finals),
            )
            _emit_answer_session_update(live_runtime, source='asr_sentence_final')
            socketio.emit('asr_final', {
                'session_id': live_runtime.session_id,
                'turn_id': live_runtime.turn_id,
                'stream_id': live_runtime.active_asr_stream_id,
                'text': text,
                'full_text': ' '.join(live_runtime.pending_asr_finals).strip(),
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
            _set_runtime_asr_status(current, True)
            _log_runtime_event(
                current,
                'asr_start',
                stream_id=stream_id,
                asr_generation=asr_generation,
                speech_epoch=current.active_asr_speech_epoch,
                reason=reason,
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
            )
        except Exception as e:
            logger.warning(f"[ASR] 结束识别流失败 - stream={current.active_asr_stream_id}: {e}")
        finally:
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
        final_text = ' '.join(current.pending_asr_finals).strip()
        partial_text = ' '.join(current.pending_asr_partials).strip()
        stream_active = bool(
            asr_manager
            and current.active_asr_stream_id
            and current.active_asr_generation == asr_generation
            and asr_manager.is_available(current.active_asr_stream_id)
        )
        answer_text = str(
            text_override
            or final_text
            or (partial_text if asr_generation and not stream_active else '')
        ).strip()
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
    runtime = session_registry.remove(client_id)
    if runtime:
        runtime.ended = True
        if runtime.pending_commit_timer:
            runtime.pending_commit_timer.cancel()
        _cancel_answer_finalize_timer(runtime)
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
            if existing.pending_commit_timer:
                existing.pending_commit_timer.cancel()
            _cancel_answer_finalize_timer(existing)
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
        runtime.started_at = time.time()
        runtime.active_asr_stream_id = f"asr_{session_id}"
        runtime.short_pause_threshold_seconds = SHORT_PAUSE_SECONDS
        runtime.long_pause_threshold_seconds = LONG_PAUSE_SECONDS
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

        normalized_question = speech_normalizer.normalize(initial_question)
        runtime.next_turn()
        _set_runtime_asr_lock(runtime, False)
        runtime.current_question = normalized_question['display_text']
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
        runtime.ended = True
        if runtime.pending_commit_timer:
            runtime.pending_commit_timer.cancel()
            runtime.pending_commit_timer = None
        _cancel_answer_finalize_timer(runtime)
        if asr_manager and runtime.active_asr_stream_id:
            asr_manager.stop_session(runtime.active_asr_stream_id)

        if runtime.data_manager:
            runtime.data_manager.end_interview()
            report_data = runtime.data_manager.export_for_report()
        else:
            report_data = {}

        report_path = report_generator.generate_report(report_data) if report_data else ""
        if report_data:
            db_manager.save_interview({
                'interview_id': runtime.interview_id,
                'start_time': report_data.get('summary', {}).get('start_time'),
                'end_time': report_data.get('summary', {}).get('end_time'),
                'duration': report_data.get('summary', {}).get('duration', 0),
                'report_path': report_path
            })

        state_orchestrator.begin_listening(runtime)
        runtime.mode = 'ended'
        _log_runtime_event(runtime, 'session_end_completed', report_path=report_path)
        _emit_orchestrator_state(runtime)
        emit('interview_ended', {
            'message': 'Interview session ended',
            'report_path': report_path,
            'session_id': runtime.session_id,
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

    if (
        asr_manager is not None
        and runtime.active_asr_generation
    ):
        _log_runtime_event(
            runtime,
            'speech_start_ignored',
            level='debug',
            requested_turn_id=str((data or {}).get('turn_id', '')).strip(),
            asr_generation=runtime.active_asr_generation,
            reason='asr_already_running_or_starting',
        )
        return

    runtime.speech_epoch += 1
    _log_runtime_event(
        runtime,
        'speech_start',
        requested_turn_id=str((data or {}).get('turn_id', '')).strip(),
        speech_epoch=runtime.speech_epoch,
    )
    _interrupt_runtime(runtime, 'speech_start')
    _cancel_answer_finalize_timer(runtime)
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
            or not asr_manager.is_available(runtime.active_asr_stream_id)
        ):
            return

        audio_base64 = data.get('audio', '')
        if audio_base64:
            audio_data = base64.b64decode(audio_base64)
            answer_session = runtime.current_answer_session
            if answer_session and answer_session.turn_id == runtime.turn_id and answer_session.status != 'finalized':
                answer_session.add_audio_chunk(audio_data)
            asr_manager.send_audio(runtime.active_asr_stream_id, audio_data)
    except Exception as e:
        logger.error(f"处理 audio_chunk 错误：{e}", exc_info=True)
        _emit_pipeline_error(client_id, runtime.session_id, 'AUDIO_CHUNK_ERROR', 'Failed to process audio chunk', str(e))


@socketio.on('speech_end')
def handle_speech_end(data=None):
    client_id = request.sid
    runtime = _get_runtime(client_id, str((data or {}).get('session_id', '')).strip())
    if not runtime:
        return

    asr_generation, speech_epoch = _finalize_runtime_asr(runtime, reason='speech_end')
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


@socketio.on('llm_evaluate_answer')
@rate_limit(answer_rate_limiter)
def handle_llm_evaluate_answer(data):
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

        user_answer = str((data or {}).get('user_answer', '')).strip()
        if not user_answer:
            emit('error', {
                'error': 'Missing required fields',
                'code': 'MISSING_FIELD'
            })
            return
        question = str((data or {}).get('question', runtime.current_question)).strip() or runtime.current_question
        position = str((data or {}).get('position', runtime.position)).strip() or runtime.position
        round_type = runtime.round_type
        question_id = str(data.get('question_id', '')).strip() or _extract_question_id_from_plan(
            runtime.last_question_plan
        )

        _log_runtime_event(runtime, 'llm_evaluate_answer', question_preview=question[:120], answer_preview=user_answer[:120])

        emit('llm_evaluating', {
            'message': '正在评估回答质量...',
            'status': 'evaluating'
        })

        evaluation = llm_manager.evaluate_answer(
            user_answer=user_answer,
            question=question,
            position=position
        )
        analysis_result = None
        followup_decision = None
        if rag_service is not None and getattr(rag_service, 'enabled', False):
            analysis_result = rag_service.analyze_answer(
                question_id=question_id,
                candidate_answer=user_answer,
                session_state=runtime.interview_state,
                current_question=question,
                position=position,
                round_type=round_type
            )
            runtime.last_answer_analysis = analysis_result
            runtime.interview_state = rag_service.update_interview_state_from_analysis(
                runtime.interview_state,
                analysis_result
            )
            followup_decision = rag_service.decide_followup(
                question_id=question_id,
                analysis_result=analysis_result,
                session_state=runtime.interview_state
            )
            evaluation = {
                **(evaluation or {}),
                'rag_analysis': analysis_result,
                'followup_decision': followup_decision
            }

        if runtime.data_manager:
            runtime.data_manager.add_frame_data({
                'type': 'answer_evaluation',
                'question': question,
                'answer': user_answer,
                'evaluation': evaluation,
                'rag_analysis': analysis_result,
                'followup_decision': followup_decision,
                'timestamp': time.time()
            })

        emit('llm_evaluation', {
            'success': True,
            'session_id': runtime.session_id,
            'evaluation': evaluation,
            'analysis': analysis_result,
            'followup_decision': followup_decision,
            'timestamp': time.time()
        })

        _log_runtime_event(runtime, 'llm_evaluation_emitted', question_preview=question[:120], answer_preview=user_answer[:120])

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


def _calc_dimension_scores(dialogues, speech_summary=None):
    """基于问答过程做启发式多维评分，并融合语音表达指标。"""
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

    speech_dims = (speech_summary or {}).get('dimensions') or {}
    if speech_dims:
        clarity_from_speech = float(speech_dims.get('clarity_score', expression_clarity))
        fluency_from_speech = float(speech_dims.get('fluency_score', adaptability))
        expression_clarity = _clamp_score(expression_clarity * 0.35 + clarity_from_speech * 0.65)
        adaptability = _clamp_score(adaptability * 0.65 + fluency_from_speech * 0.35)

    return {
        'technical_correctness': round(technical_correctness, 1),
        'knowledge_depth': round(knowledge_depth, 1),
        'logical_rigor': round(logical_rigor, 1),
        'expression_clarity': round(expression_clarity, 1),
        'job_match': round(job_match, 1),
        'adaptability': round(adaptability, 1)
    }


def _build_growth_report(dialogues, speech_rows=None):
    speech_summary = aggregate_expression_metrics(speech_rows or [])
    scores = _calc_dimension_scores(dialogues, speech_summary=speech_summary)
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

    expression_detail = {
        'available': bool(speech_summary.get('available')),
        'dimensions': speech_summary.get('dimensions', {}),
        'summary': speech_summary.get('summary', {}),
    }

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
        'expression_detail': expression_detail,
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

        def _load_session_speech_rows(session_rows):
            if not session_rows or not hasattr(db_manager, 'get_speech_evaluations'):
                return []
            interview_id = str(session_rows[0].get('interview_id') or '').strip()
            if not interview_id:
                return []
            start_time = session_rows[0].get('created_at')
            end_time = session_rows[-1].get('created_at')
            raw_speech_rows = db_manager.get_speech_evaluations(
                interview_id=interview_id,
                start_time=start_time,
                end_time=end_time,
            )
            return _decode_speech_rows(raw_speech_rows)

        report = _build_growth_report(
            latest_session,
            speech_rows=_load_session_speech_rows(latest_session),
        )

        trend = []
        sessions_for_trend = list(reversed(sessions_desc))
        for idx, session_desc in enumerate(sessions_for_trend, start=1):
            session = list(reversed(session_desc))
            session_report = _build_growth_report(
                session,
                speech_rows=_load_session_speech_rows(session),
            )
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
