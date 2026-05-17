"""Knowledge graph HTTP routes."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request


def create_knowledge_graph_blueprint(
    *,
    knowledge_graph_service: Any,
    knowledge_graph_import_error: str | None,
    logger: Any,
) -> Blueprint:
    bp = Blueprint("knowledge_graph", __name__)

    @bp.route("/api/knowledge-graph/health", methods=["GET"])
    def api_knowledge_graph_health():
        if knowledge_graph_service is None:
            return jsonify({
                "success": False,
                "enabled": False,
                "error": "knowledge graph service unavailable",
                "details": knowledge_graph_import_error or "",
            }), 503

        return jsonify({
            "success": True,
            "data": knowledge_graph_service.health(),
        })

    @bp.route("/api/knowledge-graph/profile", methods=["GET"])
    def api_knowledge_graph_profile():
        if knowledge_graph_service is None:
            return jsonify({
                "success": False,
                "error": "knowledge graph service unavailable",
                "details": knowledge_graph_import_error or "",
            }), 503

        try:
            user_id = str(request.args.get("user_id", "default") or "default").strip().lower() or "default"
            payload = knowledge_graph_service.build_user_graph(user_id=user_id)
            return jsonify({
                "success": True,
                **payload,
            })
        except Exception as e:
            logger.error(f"生成知识图谱失败: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": str(e),
                "summary": {},
                "nodes": [],
                "edges": [],
            }), 500

    @bp.route("/api/knowledge-graph/sync", methods=["POST"])
    def api_knowledge_graph_sync():
        if knowledge_graph_service is None:
            return jsonify({
                "success": False,
                "error": "knowledge graph service unavailable",
                "details": knowledge_graph_import_error or "",
            }), 503

        try:
            payload = request.get_json(silent=True) or {}
            user_id = str(
                payload.get("user_id") or request.args.get("user_id", "default") or "default"
            ).strip().lower() or "default"
            result = knowledge_graph_service.sync_user_graph(user_id=user_id)
            return jsonify({
                "success": True,
                "data": result,
            })
        except Exception as e:
            logger.error(f"同步知识图谱到 Neo4j 失败: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": str(e),
            }), 500

    return bp

