"""Text normalization helpers for TTS."""

from __future__ import annotations

import re
import unicodedata

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


def prepare_tts_text(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", str(text or ""))
    cleaned = cleaned.replace("\uFFFD", " ")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _ZERO_WIDTH_RE.sub("", cleaned)
    cleaned = _CONTROL_CHAR_RE.sub(" ", cleaned)

    cleaned = _CODE_BLOCK_RE.sub(" 代码示例 ", cleaned)
    cleaned = _INLINE_CODE_RE.sub(lambda m: f" {m.group(1)} ", cleaned)
    cleaned = _LINK_RE.sub(
        lambda m: f" {(m.group(1) or m.group(2) or '').strip()} ",
        cleaned,
    )
    cleaned = _URL_RE.sub(" 链接 ", cleaned)
    cleaned = _HTML_TAG_RE.sub(" ", cleaned)
    cleaned = _MARKDOWN_HEADER_RE.sub("", cleaned)
    cleaned = _MARKDOWN_LIST_RE.sub("", cleaned)
    cleaned = _MARKDOWN_QUOTE_RE.sub("", cleaned)

    cleaned = cleaned.replace("|", " ")
    cleaned = cleaned.replace("•", " ")
    cleaned = cleaned.replace("->", " ")
    cleaned = cleaned.replace("=>", " ")
    cleaned = cleaned.replace("::", " ")
    cleaned = re.sub(r"[*_~#`]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

