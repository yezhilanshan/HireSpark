"""
全局 AI 助理服务（非面试链路）
支持 provider:
- qwen / dashscope（阿里百炼）
- openrouter
- ollama（兼容回退）
"""
import os
import re
import time
from typing import Any, Dict, List, Optional

import dashscope
import requests
from dashscope import Generation

from utils.config_loader import config
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_ASSISTANT_QWEN_MODEL = "qwen-plus"


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, str(default))).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _safe_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    raw = str(value or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _resolve_dashscope_api_key(config_value: Optional[str] = None) -> Optional[str]:
    env_key = (
        os.environ.get("ASSISTANT_DASHSCOPE_API_KEY")
        or os.environ.get("ASSISTANT_BAILIAN_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("BAILIAN_API_KEY")
    )
    if env_key:
        return str(env_key).strip()

    if isinstance(config_value, str):
        value = config_value.strip()
        if value and not (value.startswith("${") and value.endswith("}")):
            return value

    return None


def _safe_field(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return getattr(obj, key)
    except Exception:
        return default


def _safe_text_content(value: Any) -> str:
    """兼容 OpenAI/OpenRouter 不同响应结构，提取可读文本。"""

    def _extract(raw: Any, depth: int = 0) -> str:
        if depth > 6:
            return ""
        if isinstance(raw, str):
            return raw.strip()
        if isinstance(raw, list):
            parts: List[str] = []
            for item in raw:
                text = _extract(item, depth + 1)
                if text:
                    parts.append(text)
            return "\n".join(parts).strip()
        if isinstance(raw, dict):
            parts: List[str] = []
            for key in ("content", "text", "output_text", "value", "summary", "refusal"):
                if key in raw:
                    text = _extract(raw.get(key), depth + 1)
                    if text:
                        parts.append(text)
            if parts:
                return "\n".join(parts).strip()
            for value in raw.values():
                text = _extract(value, depth + 1)
                if text:
                    parts.append(text)
            return "\n".join(parts).strip()
        return ""

    return _extract(value)


def _extract_openrouter_reply(data: Any) -> str:
    """从 OpenRouter 响应中尽量稳健提取主回复文本。"""
    if not isinstance(data, dict):
        return ""

    candidates: List[Any] = []

    choices = data.get("choices")
    if isinstance(choices, list):
        for choice in choices[:3]:
            if not isinstance(choice, dict):
                continue
            message_payload = choice.get("message")
            if isinstance(message_payload, dict):
                candidates.append(message_payload.get("content"))
                candidates.append(message_payload.get("text"))
                candidates.append(message_payload.get("output_text"))
                candidates.append(message_payload.get("refusal"))
            candidates.append(choice.get("text"))
            candidates.append(choice.get("content"))
            candidates.append(choice.get("output_text"))

    candidates.append(data.get("output_text"))
    candidates.append(data.get("content"))
    candidates.append(data.get("response"))

    for candidate in candidates:
        text = _safe_text_content(candidate)
        if text:
            return text
    return ""


def _to_plain_natural_text(text: str) -> str:
    """将常见 Markdown 输出规整为自然语言纯文本。"""
    content = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not content.strip():
        return ""

    # 去掉常见 Markdown 语法符号（保留正文）
    content = content.replace("```", "")
    content = content.replace("**", "")
    content = content.replace("__", "")
    content = content.replace("`", "")

    normalized_lines: List[str] = []
    for raw_line in content.split("\n"):
        line = raw_line.strip()
        if not line:
            normalized_lines.append("")
            continue

        # 标题、引用、列表、编号列表
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = re.sub(r"^\s*>\s*", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = re.sub(r"^\s*\d+[.)]\s+", "", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        normalized_lines.append(line)

    # 合并多余空行，保留自然分段
    compact_lines: List[str] = []
    prev_blank = False
    for line in normalized_lines:
        is_blank = (line == "")
        if is_blank and prev_blank:
            continue
        compact_lines.append(line)
        prev_blank = is_blank

    return "\n".join(compact_lines).strip()


def _sanitize_user_visible_reply(text: str) -> str:
    content = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not content:
        return ""
    content = re.sub(r"(?i)<br\s*/?>", "\n", content)
    content = re.sub(r"[（(]\s*(?:见|参见|详见)\s*[^()（）\n]{0,140}[)）]", "", content)
    content = re.sub(
        r"(?:见|参见|详见)\s*knowledge\/[^\s，。；;、)]{1,80}",
        "",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def _sanitize_user_visible_reply_v2(text: str) -> str:
    content = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not content:
        return ""
    # Keep markdown table cells stable: avoid inserting hard newlines inside cells.
    content = re.sub(r"(?i)<br\s*/?>", "；", content)
    content = re.sub(
        r"[\uFF08(]\s*(?:\u89c1|\u53c2\u89c1|\u8be6\u89c1)\s*[^()\uFF08\uFF09\n]{0,140}[)\uFF09]",
        "",
        content,
    )
    content = re.sub(
        r"(?:\u89c1|\u53c2\u89c1|\u8be6\u89c1)\s*knowledge\/[^\s\uFF0C\u3002\uFF1B;\u3001)]{1,80}",
        "",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(r"\s*；\s*；+", "；", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


class AssistantService:
    """面向业务页面的通用助手服务，不参与面试实时问答链路。"""

    def __init__(self):
        self.enabled = _env_bool("ASSISTANT_ENABLED", bool(config.get("assistant.enabled", True)))
        self.provider = (
            str(os.environ.get("ASSISTANT_PROVIDER", "")).strip().lower()
            or str(config.get("assistant.provider", "qwen")).strip().lower()
            or "qwen"
        )
        self.model = (
            str(os.environ.get("ASSISTANT_MODEL", "")).strip()
            or str(config.get("assistant.model", "qvq-max-2025-03-25")).strip()
            or "qvq-max-2025-03-25"
        )
        self.dashscope_api_key = _resolve_dashscope_api_key(
            config.get("assistant.qwen.api_key", config.get("llm.api_key"))
        )
        self.timeout = float(config.get("assistant.timeout", 45) or 45)
        self.max_history = int(config.get("assistant.max_history", 6) or 6)
        self.max_context_chars = int(config.get("assistant.max_context_chars", 1200) or 1200)
        self.default_max_tokens = int(config.get("assistant.default_max_tokens", 512) or 512)
        self.default_temperature = float(config.get("assistant.default_temperature", 0.3) or 0.3)

        if self.provider in {"qwen", "dashscope", "aliyun"} and self.model.startswith("qvq-"):
            fallback_model = (
                str(os.environ.get("ASSISTANT_QWEN_TEXT_MODEL", "")).strip()
                or str(config.get("assistant.qwen.fallback_text_model", DEFAULT_ASSISTANT_QWEN_MODEL)).strip()
                or DEFAULT_ASSISTANT_QWEN_MODEL
            )
            logger.warning(
                "Assistant 文本助手当前不兼容视觉推理模型 %s，已自动回退到 %s",
                self.model,
                fallback_model,
            )
            self.model = fallback_model

        if self.dashscope_api_key:
            dashscope.api_key = self.dashscope_api_key
            Generation.api_key = self.dashscope_api_key

        # OpenRouter 配置
        self.openrouter_base_url = (
            str(os.environ.get("ASSISTANT_OPENROUTER_BASE_URL", "")).strip()
            or str(os.environ.get("OPENROUTER_BASE_URL", "")).strip()
            or str(config.get("assistant.openrouter.base_url", "https://openrouter.ai/api/v1")).strip()
            or "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.openrouter_api_key = (
            str(os.environ.get("OPENROUTER_API_KEY", "")).strip()
            or str(os.environ.get("ASSISTANT_OPENROUTER_API_KEY", "")).strip()
            or str(config.get("assistant.openrouter.api_key", "")).strip()
        )
        self.openrouter_site_url = (
            str(os.environ.get("OPENROUTER_SITE_URL", "")).strip()
            or str(config.get("assistant.openrouter.site_url", "")).strip()
        )
        self.openrouter_app_name = (
            str(os.environ.get("OPENROUTER_APP_NAME", "")).strip()
            or str(config.get("assistant.openrouter.app_name", "tianshuzhimian")).strip()
            or "tianshuzhimian"
        )

        # Ollama 配置（保留兼容）
        self.ollama_base_url = (
            str(os.environ.get("ASSISTANT_OLLAMA_BASE_URL", "")).strip()
            or str(os.environ.get("OLLAMA_BASE_URL", "")).strip()
            or str(config.get("assistant.ollama.base_url", "http://127.0.0.1:11434")).strip()
            or "http://127.0.0.1:11434"
        ).rstrip("/")
        self.ollama_num_ctx = int(config.get("assistant.ollama.num_ctx", 1536) or 1536)
        self.ollama_think = _safe_bool(
            os.environ.get("ASSISTANT_OLLAMA_THINK", config.get("assistant.ollama.think", False)),
            False,
        )
        self.ollama_keep_alive = (
            str(os.environ.get("ASSISTANT_OLLAMA_KEEP_ALIVE", "")).strip()
            or str(config.get("assistant.ollama.keep_alive", "2m")).strip()
            or "2m"
        )

        raw_num_gpu = os.environ.get("ASSISTANT_OLLAMA_NUM_GPU", "")
        if raw_num_gpu == "":
            raw_num_gpu = config.get("assistant.ollama.num_gpu", None)
        try:
            self.ollama_num_gpu = None if raw_num_gpu is None or str(raw_num_gpu).strip() == "" else int(raw_num_gpu)
        except Exception:
            self.ollama_num_gpu = None

        self.default_system_prompt = str(
            config.get(
                "assistant.default_system_prompt",
                (
                    "你是一个专业、简洁、可信的中文求职助手。"
                    "重点帮助用户准备技术面试、梳理项目表达、优化简历表述，并提供可执行建议。"
                    "回答请直奔主题，先给结论，再给关键理由。"
                    "输出必须是自然中文纯文本，不要使用 Markdown、标题、编号列表、项目符号、代码块。"
                ),
            )
            or ""
        ).strip()
        self.force_plain_text = _safe_bool(
            os.environ.get("ASSISTANT_FORCE_PLAIN_TEXT", config.get("assistant.force_plain_text", True)),
            True,
        )

        if not self.enabled:
            logger.info("Assistant 服务已禁用")
        else:
            logger.info(
                (
                    "Assistant 服务初始化完成 - "
                    f"provider={self.provider}, model={self.model}, timeout={self.timeout}s, "
                    f"openrouter_base={self.openrouter_base_url}, ollama_base={self.ollama_base_url}, "
                    f"dashscope_ready={bool(self.dashscope_api_key)}"
                )
            )

    def check_enabled(self) -> bool:
        if not self.enabled:
            return False
        if self.provider in {"qwen", "dashscope", "aliyun"}:
            return bool(self.dashscope_api_key)
        if self.provider == "openrouter":
            return bool(self.openrouter_api_key)
        if self.provider == "ollama":
            return True
        return False

    @staticmethod
    def _normalize_role(role: Any) -> str:
        raw = str(role or "").strip().lower()
        if raw in {"assistant", "system", "user"}:
            return raw
        if raw in {"candidate", "human"}:
            return "user"
        if raw in {"interviewer", "ai"}:
            return "assistant"
        return "user"

    def _sanitize_messages(self, messages: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
        if not isinstance(messages, list):
            return []

        normalized: List[Dict[str, str]] = []
        for item in messages[-max(1, self.max_history):]:
            if not isinstance(item, dict):
                continue
            role = self._normalize_role(item.get("role"))
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            normalized.append(
                {
                    "role": role,
                    "content": content[: max(200, self.max_context_chars)],
                }
            )
        return normalized

    def _openrouter_headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-Title": self.openrouter_app_name,
        }
        if self.openrouter_site_url:
            headers["HTTP-Referer"] = self.openrouter_site_url
        return headers

    def health(self) -> Dict[str, Any]:
        """检查助手服务可用性。"""
        payload: Dict[str, Any] = {
            "enabled": bool(self.enabled),
            "provider": self.provider,
            "model": self.model,
            "success": False,
            "latency_ms": 0.0,
            "error": "",
            "model_available": False,
        }

        if self.provider in {"qwen", "dashscope", "aliyun"}:
            payload["api_key_configured"] = bool(self.dashscope_api_key)
            if not self.dashscope_api_key:
                payload["error"] = "DASHSCOPE_API_KEY missing"
                return payload

            started_at = time.time()
            try:
                response = Generation.call(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a health checker. Reply with OK only."},
                        {"role": "user", "content": "ping"},
                    ],
                    top_p=0.1,
                    top_k=10,
                    temperature=0.0,
                    max_tokens=8,
                    timeout=min(float(self.timeout or 30), 15.0),
                )
                payload["latency_ms"] = round((time.time() - started_at) * 1000.0, 2)
                if getattr(response, "status_code", None) != 200:
                    payload["error"] = str(
                        getattr(response, "message", "") or getattr(response, "code", "") or "unknown_error"
                    )
                    return payload

                payload["success"] = True
                payload["model_available"] = True
                payload["reply_preview"] = str(getattr(getattr(response, "output", None), "text", "") or "").strip()[:48]
                return payload
            except Exception as exc:
                payload["latency_ms"] = round((time.time() - started_at) * 1000.0, 2)
                payload["error"] = str(exc)[:300]
                return payload

        if self.provider == "openrouter":
            payload["base_url"] = self.openrouter_base_url
            payload["api_key_configured"] = bool(self.openrouter_api_key)
            if not self.openrouter_api_key:
                payload["error"] = "OPENROUTER_API_KEY missing"
                return payload

            started_at = time.time()
            try:
                response = requests.get(
                    f"{self.openrouter_base_url}/models",
                    headers=self._openrouter_headers(),
                    timeout=min(self.timeout, 15),
                )
                payload["latency_ms"] = round((time.time() - started_at) * 1000.0, 2)
                if response.status_code != 200:
                    payload["error"] = f"openrouter_http_{response.status_code}"
                    payload["details"] = response.text[:400]
                    return payload

                data = response.json() if response.content else {}
                models = data.get("data") if isinstance(data, dict) else None
                model_ids: List[str] = []
                if isinstance(models, list):
                    for item in models:
                        if isinstance(item, dict):
                            model_id = str(item.get("id") or "").strip()
                            if model_id:
                                model_ids.append(model_id)
                payload["available_models_preview"] = model_ids[:60]
                payload["model_available"] = self.model in model_ids
                payload["success"] = True
                return payload
            except Exception as exc:
                payload["latency_ms"] = round((time.time() - started_at) * 1000.0, 2)
                payload["error"] = str(exc)[:300]
                return payload

        if self.provider == "ollama":
            payload["base_url"] = self.ollama_base_url
            payload["think"] = self.ollama_think
            payload["num_ctx"] = self.ollama_num_ctx
            started_at = time.time()
            try:
                response = requests.get(
                    f"{self.ollama_base_url}/api/tags",
                    timeout=min(self.timeout, 8),
                )
                payload["latency_ms"] = round((time.time() - started_at) * 1000.0, 2)
                if response.status_code != 200:
                    payload["error"] = f"ollama_http_{response.status_code}"
                    return payload

                data = response.json() if response.content else {}
                models = data.get("models") if isinstance(data, dict) else None
                model_names: List[str] = []
                if isinstance(models, list):
                    for item in models:
                        if isinstance(item, dict):
                            name = str(item.get("name") or "").strip()
                            if name:
                                model_names.append(name)
                payload["available_models_preview"] = model_names[:60]
                payload["model_available"] = any(
                    name == self.model or name.startswith(f"{self.model}:")
                    for name in model_names
                )
                payload["success"] = True
                return payload
            except Exception as exc:
                payload["latency_ms"] = round((time.time() - started_at) * 1000.0, 2)
                payload["error"] = str(exc)[:300]
                return payload

        payload["error"] = f"unsupported provider: {self.provider}"
        return payload

    def _chat_qwen(
        self,
        *,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        started_at = time.time()
        try:
            response = Generation.call(
                model=self.model,
                messages=messages,
                top_p=0.8,
                top_k=40,
                temperature=round(max(0.0, min(1.2, float(temperature))), 3),
                max_tokens=int(max(64, min(4096, int(max_tokens)))),
                timeout=self.timeout,
            )
            latency_ms = round((time.time() - started_at) * 1000.0, 2)
            if _safe_field(response, "status_code") != 200:
                return {
                    "success": False,
                    "error": str(_safe_field(response, "code", "") or "QWEN_API_ERROR"),
                    "message": str(_safe_field(response, "message", "") or "assistant request failed"),
                    "latency_ms": latency_ms,
                }

            output_payload = _safe_field(response, "output")
            reply_text = str(_safe_field(output_payload, "text", "") or "").strip()
            if self.force_plain_text:
                reply_text = _to_plain_natural_text(reply_text)
            if not reply_text:
                return {
                    "success": False,
                    "error": "EMPTY_REPLY",
                    "message": "assistant returned empty reply",
                    "latency_ms": latency_ms,
                }

            usage = _safe_field(response, "usage")
            return {
                "success": True,
                "provider": "qwen",
                "model": str(_safe_field(response, "model", "") or self.model),
                "reply": reply_text,
                "latency_ms": latency_ms,
                "done_reason": str(_safe_field(output_payload, "finish_reason", "") or ""),
                "prompt_eval_count": int(_safe_field(usage, "input_tokens", 0) or 0),
                "eval_count": int(_safe_field(usage, "output_tokens", 0) or 0),
            }
        except Exception as exc:
            return {
                "success": False,
                "error": "ASSISTANT_EXCEPTION",
                "message": repr(exc)[:500],
                "latency_ms": round((time.time() - started_at) * 1000.0, 2),
            }

    def _chat_openrouter(
        self,
        *,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        started_at = time.time()
        base_payload = {
            "model": self.model,
            "temperature": round(max(0.0, min(1.2, float(temperature))), 3),
            "max_tokens": int(max(64, min(4096, int(max_tokens)))),
        }

        attempts: List[List[Dict[str, str]]] = [messages]
        retry_messages = [dict(item) for item in messages]
        if retry_messages and retry_messages[-1].get("role") == "user":
            retry_messages[-1]["content"] = (
                f"{retry_messages[-1].get('content', '')}\n\n"
                "请直接给出非空中文回答，不要输出思考过程，不要使用 Markdown。"
            )[:4000]
        attempts.append(retry_messages)

        last_error: Dict[str, Any] = {}
        for idx, request_messages in enumerate(attempts):
            try:
                response = requests.post(
                    f"{self.openrouter_base_url}/chat/completions",
                    headers=self._openrouter_headers(),
                    json={
                        **base_payload,
                        "messages": request_messages,
                    },
                    timeout=self.timeout,
                )
            except Exception as exc:
                last_error = {
                    "success": False,
                    "error": "ASSISTANT_EXCEPTION",
                    "message": str(exc)[:500],
                }
                continue

            if response.status_code != 200:
                last_error = {
                    "success": False,
                    "error": f"OPENROUTER_HTTP_{response.status_code}",
                    "message": response.text[:500],
                }
                continue

            data = response.json() if response.content else {}
            choices = data.get("choices") if isinstance(data, dict) else None
            if not isinstance(choices, list) or not choices:
                last_error = {
                    "success": False,
                    "error": "OPENROUTER_EMPTY_CHOICES",
                    "message": "openrouter returned empty choices",
                }
                continue

            first = choices[0] if isinstance(choices[0], dict) else {}
            reply_text = _extract_openrouter_reply(data)
            if self.force_plain_text:
                reply_text = _to_plain_natural_text(reply_text)
            if not reply_text:
                last_error = {
                    "success": False,
                    "error": "EMPTY_REPLY",
                    "message": "assistant returned empty reply",
                    "done_reason": str(first.get("finish_reason") or ""),
                    "attempt": idx + 1,
                }
                continue

            usage = data.get("usage") if isinstance(data, dict) else {}
            if not isinstance(usage, dict):
                usage = {}

            return {
                "success": True,
                "provider": "openrouter",
                "model": str(data.get("model") or self.model),
                "reply": reply_text,
                "latency_ms": round((time.time() - started_at) * 1000.0, 2),
                "done_reason": str(first.get("finish_reason") or ""),
                "prompt_eval_count": int(usage.get("prompt_tokens") or 0),
                "eval_count": int(usage.get("completion_tokens") or 0),
            }

        return {
            "success": False,
            "error": str(last_error.get("error") or "ASSISTANT_EXCEPTION"),
            "message": str(last_error.get("message") or "assistant request failed"),
            "latency_ms": round((time.time() - started_at) * 1000.0, 2),
        }

    def _chat_ollama(
        self,
        *,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        options: Dict[str, Any] = {
            "temperature": round(max(0.0, min(1.2, float(temperature))), 3),
            "num_predict": int(max(64, min(2048, int(max_tokens)))),
            "num_ctx": int(max(1024, min(8192, int(self.ollama_num_ctx)))),
        }
        if self.ollama_num_gpu is not None:
            options["num_gpu"] = int(max(0, min(999, int(self.ollama_num_gpu))))

        started_at = time.time()
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "think": bool(self.ollama_think),
                    "keep_alive": self.ollama_keep_alive,
                    "options": options,
                },
                timeout=self.timeout,
            )
            latency_ms = round((time.time() - started_at) * 1000.0, 2)
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"OLLAMA_HTTP_{response.status_code}",
                    "message": response.text[:500],
                    "latency_ms": latency_ms,
                }

            data = response.json() if response.content else {}
            message_payload = data.get("message") if isinstance(data, dict) else {}
            reply_text = ""
            if isinstance(message_payload, dict):
                reply_text = str(message_payload.get("content") or "").strip()
            if self.force_plain_text:
                reply_text = _to_plain_natural_text(reply_text)

            if not reply_text:
                return {
                    "success": False,
                    "error": "EMPTY_REPLY",
                    "message": "assistant returned empty reply",
                    "latency_ms": latency_ms,
                }

            return {
                "success": True,
                "provider": "ollama",
                "model": str(data.get("model") or self.model),
                "reply": reply_text,
                "latency_ms": latency_ms,
                "done_reason": str(data.get("done_reason") or ""),
                "prompt_eval_count": int(data.get("prompt_eval_count") or 0),
                "eval_count": int(data.get("eval_count") or 0),
            }
        except Exception as exc:
            return {
                "success": False,
                "error": "ASSISTANT_EXCEPTION",
                "message": str(exc)[:500],
                "latency_ms": round((time.time() - started_at) * 1000.0, 2),
            }

    def chat(
        self,
        *,
        user_message: str,
        messages: Optional[List[Dict[str, Any]]] = None,
        system_prompt: str = "",
        rag_context: str = "",
        temperature: float = 0.3,
        max_tokens: int = 640,
    ) -> Dict[str, Any]:
        """统一对话入口。"""
        if not self.check_enabled():
            reason = "assistant disabled or provider unsupported"
            if self.provider in {"qwen", "dashscope", "aliyun"} and not self.dashscope_api_key:
                reason = "DASHSCOPE_API_KEY missing"
            if self.provider == "openrouter" and not self.openrouter_api_key:
                reason = "OPENROUTER_API_KEY missing"
            return {
                "success": False,
                "error": "ASSISTANT_NOT_READY",
                "message": reason,
            }

        final_user_message = str(user_message or "").strip()
        if not final_user_message:
            return {
                "success": False,
                "error": "EMPTY_MESSAGE",
                "message": "user message is empty",
            }

        final_system_prompt = str(system_prompt or "").strip() or self.default_system_prompt
        final_rag_context = str(rag_context or "").strip()
        if final_rag_context:
            final_system_prompt = "\n\n".join(
                part for part in [
                    final_system_prompt,
                    (
                        "回答要求：\n"
                        "1. 优先依据下方“知识库检索证据”回答，并尽量引用其中的事实与表述。\n"
                        "2. 如果知识库证据不足，可以补充通用经验，但必须明确说明“以下为一般经验补充”。\n"
                        "3. 不要把未命中的事实伪装成知识库结论。\n"
                        "4. 输出中文，尽量简洁、可执行、适合求职准备场景。"
                    ),
                    f"知识库检索证据：\n{final_rag_context}",
                ] if part
            )
        history = self._sanitize_messages(messages)
        composed: List[Dict[str, str]] = []
        if final_system_prompt:
            composed.append({"role": "system", "content": final_system_prompt[:4000]})
        composed.extend(history)
        composed.append({"role": "user", "content": final_user_message[:4000]})

        safe_temperature = round(max(0.0, min(1.2, float(temperature))), 3)
        safe_max_tokens = int(max(64, min(4096, int(max_tokens or self.default_max_tokens))))

        if self.provider in {"qwen", "dashscope", "aliyun"}:
            result = self._chat_qwen(
                messages=composed,
                temperature=safe_temperature,
                max_tokens=safe_max_tokens,
            )
        elif self.provider == "openrouter":
            result = self._chat_openrouter(
                messages=composed,
                temperature=safe_temperature,
                max_tokens=safe_max_tokens,
            )
        elif self.provider == "ollama":
            result = self._chat_ollama(
                messages=composed,
                temperature=safe_temperature,
                max_tokens=safe_max_tokens,
            )
        else:
            result = {
                "success": False,
                "error": "UNSUPPORTED_PROVIDER",
                "message": f"unsupported provider: {self.provider}",
            }

        if not result.get("success"):
            logger.warning(
                (
                    "[assistant] chat failed - "
                    f"provider={self.provider}, model={self.model}, "
                    f"code={result.get('error', '')}, msg={str(result.get('message', ''))[:180]}"
                )
            )
            return result

        result["reply"] = _sanitize_user_visible_reply_v2(str(result.get("reply", "") or ""))
        return result


assistant_service = AssistantService()
