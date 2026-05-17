"""Basic system, health, performance, and question-bank routes."""
from __future__ import annotations

import time
from typing import Any

from flask import Blueprint, jsonify, request


def create_system_blueprint(
    *,
    config: Any,
    logger: Any,
    performance_monitor: Any,
    db_manager: Any,
    llm_manager: Any,
    rag_service: Any,
    asr_manager: Any,
    assistant_service: Any,
    tts_manager: Any,
    tts_import_error: str | None,
) -> Blueprint:
    bp = Blueprint("system", __name__)

    @bp.route("/")
    def index():
        """主页路由"""
        logger.debug("收到主页请求")
        return jsonify({
            "message": "AI Interview Platform API",
            "version": config.get("system.version", "1.0.0"),
            "status": "running",
            "environment": config.get("system.environment", "development"),
        })

    @bp.route("/health")
    def health():
        """健康检查"""
        logger.debug("健康检查请求")
        perf_stats = performance_monitor.get_system_stats()
        return jsonify({
            "status": "healthy",
            "timestamp": time.time(),
            "performance": {
                "fps": perf_stats["fps"],
                "cpu_percent": perf_stats["cpu_percent"],
                "memory_percent": perf_stats["memory_percent"],
            },
            "services": {
                "llm": bool(llm_manager and getattr(llm_manager, "enabled", False)),
                "rag": bool(rag_service),
                "asr": bool(asr_manager and getattr(asr_manager, "enabled", False)),
                "assistant": bool(assistant_service and getattr(assistant_service, "enabled", False)),
                "tts": tts_manager.get_status() if tts_manager else {
                    "enabled": False,
                    "error": tts_import_error or "tts manager unavailable",
                },
            },
        })

    @bp.route("/api/performance")
    def get_performance():
        """获取性能统计"""
        logger.debug("性能统计请求")
        return jsonify({
            "success": True,
            "data": performance_monitor.get_performance_summary(),
        })

    @bp.route("/api/performance/bottlenecks")
    def get_bottlenecks():
        """获取性能瓶颈"""
        threshold = request.args.get("threshold", 100.0, type=float)
        return jsonify({
            "success": True,
            "data": performance_monitor.get_bottlenecks(threshold),
        })

    @bp.route("/api/question-bank")
    def get_question_bank():
        """读取数据库题库（interview_rounds.questions）"""
        try:
            round_type = str(request.args.get("round_type", "") or "").strip()
            position = str(request.args.get("position", "") or "").strip()
            difficulty = str(request.args.get("difficulty", "") or "").strip()
            keyword = str(request.args.get("keyword", "") or "").strip().lower()
            limit = request.args.get("limit", 500, type=int) or 500
            limit = max(1, min(limit, 2000))

            question_bank = db_manager.get_question_bank(
                round_type=round_type or None,
                position=position or None,
                difficulty=difficulty or None,
            )

            if keyword:
                question_bank = [
                    item for item in question_bank
                    if keyword in str(item.get("question", "")).lower()
                    or keyword in str(item.get("category", "")).lower()
                    or keyword in str(item.get("round_type", "")).lower()
                    or keyword in str(item.get("position", "")).lower()
                    or keyword in str(item.get("description", "")).lower()
                ]

            total = len(question_bank)
            truncated = question_bank[:limit]
            categories = sorted({
                str(item.get("category", "")).strip()
                for item in question_bank
                if str(item.get("category", "")).strip()
            })
            facets = db_manager.get_question_bank_facets()

            return jsonify({
                "success": True,
                "count": len(truncated),
                "total": total,
                "limit": limit,
                "question_bank": truncated,
                "categories": categories,
                "facets": facets,
                "message": "" if total > 0 else "question bank is empty",
            })

        except Exception as e:
            logger.error(f"获取题库失败：{e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": str(e),
                "question_bank": [],
                "categories": [],
                "facets": {
                    "round_types": [],
                    "positions": [],
                    "difficulties": [],
                },
            }), 500

    return bp
