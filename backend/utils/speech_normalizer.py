"""
语音文本净化与口语化处理
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List


_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)|\[([^\]]+)\]\([^)]+\)")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MARKDOWN_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_MARKDOWN_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+", re.MULTILINE)
_MARKDOWN_QUOTE_RE = re.compile(r"^\s*>\s*", re.MULTILINE)
_MULTI_SPACE_RE = re.compile(r"\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])\s+")


class SpeechTextNormalizer:
    """在 LLM 输出和 TTS 之间做统一净化。"""

    def normalize(self, text: str) -> Dict[str, str]:
        display_text = self._normalize_display_text(text)
        spoken_text = self._normalize_spoken_text(display_text)

        if not spoken_text:
            spoken_text = "我换一种更清晰的说法。"
        if not display_text:
            display_text = spoken_text

        return {
            "display_text": display_text,
            "spoken_text": spoken_text,
        }

    def split_for_tts(self, text: str, max_chars: int = 80) -> List[str]:
        normalized = self._normalize_spoken_text(text)
        if not normalized:
            return []

        raw_parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(normalized) if part.strip()]
        chunks: List[str] = []

        for part in raw_parts or [normalized]:
            if len(part) <= max_chars:
                chunks.append(part)
                continue

            subparts = re.split(r"(?<=[，、,:：])\s*", part)
            buffer = ""
            for subpart in (item.strip() for item in subparts if item.strip()):
                candidate = f"{buffer}{subpart}".strip()
                if buffer and len(candidate) > max_chars:
                    chunks.append(buffer.strip())
                    buffer = subpart
                else:
                    buffer = candidate
            if buffer:
                chunks.append(buffer.strip())

        return [chunk for chunk in chunks if chunk]

    def _normalize_display_text(self, text: str) -> str:
        cleaned = self._basic_cleanup(text)
        cleaned = _CODE_BLOCK_RE.sub("\n[代码示例]\n", cleaned)
        cleaned = _INLINE_CODE_RE.sub(lambda m: m.group(1), cleaned)
        cleaned = _LINK_RE.sub(lambda m: (m.group(1) or m.group(2) or "").strip(), cleaned)
        cleaned = _URL_RE.sub("链接", cleaned)
        cleaned = _HTML_TAG_RE.sub(" ", cleaned)
        cleaned = _MARKDOWN_HEADER_RE.sub("", cleaned)
        cleaned = _MARKDOWN_LIST_RE.sub("", cleaned)
        cleaned = _MARKDOWN_QUOTE_RE.sub("", cleaned)
        cleaned = cleaned.replace("\n\n\n", "\n\n")
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        return cleaned.strip()

    def _normalize_spoken_text(self, text: str) -> str:
        cleaned = self._basic_cleanup(text)
        cleaned = _CODE_BLOCK_RE.sub(" 这里有一段代码示例。 ", cleaned)
        cleaned = _INLINE_CODE_RE.sub(lambda m: f" {m.group(1)} ", cleaned)
        cleaned = _LINK_RE.sub(lambda m: f" {(m.group(1) or m.group(2) or '').strip()} ", cleaned)
        cleaned = _URL_RE.sub(" 链接 ", cleaned)
        cleaned = _HTML_TAG_RE.sub(" ", cleaned)
        cleaned = _MARKDOWN_HEADER_RE.sub("", cleaned)
        cleaned = _MARKDOWN_LIST_RE.sub("", cleaned)
        cleaned = _MARKDOWN_QUOTE_RE.sub("", cleaned)
        cleaned = cleaned.replace("|", "，")
        cleaned = cleaned.replace("•", "，")
        cleaned = cleaned.replace("->", " 到 ")
        cleaned = cleaned.replace("=>", " 指向 ")
        cleaned = cleaned.replace("::", " ")
        cleaned = cleaned.replace("/", " 或 ")
        cleaned = re.sub(r"[*_~#`]+", " ", cleaned)
        cleaned = re.sub(r"\s*([,，;；:：])\s*", r"\1", cleaned)
        cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
        cleaned = cleaned.strip()
        return cleaned

    @staticmethod
    def _basic_cleanup(text: str) -> str:
        cleaned = unicodedata.normalize("NFKC", str(text or ""))
        cleaned = cleaned.replace("\uFFFD", " ")
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = _ZERO_WIDTH_RE.sub("", cleaned)
        cleaned = _CONTROL_CHAR_RE.sub(" ", cleaned)
        return cleaned
