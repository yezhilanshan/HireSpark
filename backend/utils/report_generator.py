"""
轻量报告生成器。

说明：
- 旧版本的 ReportGenerator 文件缺失会导致 app.py 在启动阶段崩溃。
- 这里提供一个无额外依赖的实现，至少保证服务可启动、报告可落盘。
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime, time as datetime_time
from pathlib import Path
from typing import Any, Dict

from .config_loader import config
from .logger import get_logger


logger = get_logger(__name__)


class ReportGenerator:
    """生成结构化 JSON 报告并返回文件路径。"""

    def __init__(self) -> None:
        output_dir = str(config.get("report.output_dir", "reports") or "reports").strip() or "reports"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ReportGenerator 初始化完成，输出目录: {self.output_dir.resolve()}")

    def _build_payload(self, report_data: Dict[str, Any], created_at: datetime) -> Dict[str, Any]:
        payload: Dict[str, Any] = copy.deepcopy(report_data or {})
        payload.setdefault("created_at", created_at.strftime("%Y-%m-%d %H:%M:%S"))
        payload.setdefault("schema_version", "report_json_v1")
        return payload

    @staticmethod
    def _json_default(value: Any):
        """将常见的非 JSON 原生类型转成可序列化值。"""
        if isinstance(value, datetime):
            return value.isoformat(sep=" ", timespec="seconds")
        if isinstance(value, (date, datetime_time)):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, set):
            return list(value)
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        # 兼容 numpy / torch 等标量类型（有 item() 方法）
        item = getattr(value, "item", None)
        if callable(item):
            try:
                return item()
            except Exception:
                pass

        return str(value)

    def generate_report(self, report_data: Dict[str, Any]) -> str:
        """生成 JSON 报告，返回绝对路径字符串。"""
        now = datetime.now()
        file_name = f"interview_report_{now.strftime('%Y%m%d_%H%M%S')}.json"
        file_path = self.output_dir / file_name
        tmp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")

        payload = self._build_payload(report_data, now)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2,
                default=self._json_default,
            )
        tmp_path.replace(file_path)

        resolved = str(file_path.resolve())
        logger.info(f"报告已生成: {resolved}")
        return resolved
