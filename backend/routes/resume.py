"""Resume upload, parsing, and optimization routes."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request


ALLOWED_RESUME_EXTENSIONS = (".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg")


def _update_resume_parsed_data(db_manager: Any, resume_id: int, parsed_result: dict) -> None:
    """Persist parsed resume fields in the legacy resumes table layout."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
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
            """,
            (
                json.dumps(parsed_result, ensure_ascii=False),
                json.dumps(parsed_result.get("projects", []), ensure_ascii=False),
                json.dumps(parsed_result.get("experiences", []), ensure_ascii=False),
                json.dumps(parsed_result.get("education", []), ensure_ascii=False),
                json.dumps(parsed_result.get("skills", []), ensure_ascii=False),
                resume_id,
            ),
        )
        conn.commit()


def create_resume_blueprint(
    *,
    db_manager: Any,
    resume_parser: Any,
    resume_optimizer_service: Any,
    resume_optimizer_import_error: str | None,
    logger: Any,
) -> Blueprint:
    bp = Blueprint("resume", __name__)

    @bp.route("/api/resume/upload", methods=["POST"])
    def upload_resume():
        """上传并解析简历"""
        try:
            if resume_parser is None:
                return jsonify({"success": False, "error": "简历解析器未初始化"}), 500

            if "file" not in request.files:
                return jsonify({"success": False, "error": "请选择要上传的文件"}), 400

            file = request.files.get("file")
            user_id = request.form.get("user_id", "default")

            if not file or file.filename == "":
                return jsonify({"success": False, "error": "未选择文件"}), 400

            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in ALLOWED_RESUME_EXTENSIONS:
                return jsonify({
                    "success": False,
                    "error": f'不支持的文件格式，请上传 {", ".join(ALLOWED_RESUME_EXTENSIONS)} 格式的文件',
                }), 400

            upload_dir = Path("uploads/resumes")
            upload_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}{file_ext}"
            file_path = upload_dir / unique_filename
            file.save(str(file_path))

            with open(file_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            duplicate_resume_id = None
            existing = db_manager.get_resumes(limit=1000)
            for resume in existing:
                if resume.get("file_hash") == file_hash:
                    duplicate_resume_id = resume.get("id")
                    logger.info(f"发现重复简历（将继续重新解析）：{file.filename}, 重复ID: {duplicate_resume_id}")
                    break

            resume_data = {
                "user_id": user_id,
                "file_name": file.filename,
                "file_path": str(file_path),
                "file_size": os.path.getsize(file_path),
                "file_hash": file_hash,
                "parsed_data": {},
                "status": "parsing",
            }

            save_result = db_manager.save_resume(resume_data)
            if not save_result.get("success"):
                return jsonify({"success": False, "error": save_result.get("error")}), 500

            resume_id = save_result["resume_id"]
            db_manager.update_resume_status(resume_id, "parsing")

            logger.info(f"开始解析简历：{file.filename}")
            parsed_result = resume_parser.parse_file(str(file_path))

            if parsed_result.get("error"):
                db_manager.update_resume_status(resume_id, "error", parsed_result.get("error"))
                return jsonify({"success": False, "error": parsed_result.get("error")}), 500

            _update_resume_parsed_data(db_manager, resume_id, parsed_result)

            logger.info(f"✓ 简历解析完成：{file.filename}")

            return jsonify({
                "success": True,
                "message": "简历上传并解析成功",
                "resume_id": resume_id,
                "data": parsed_result,
                "duplicate": duplicate_resume_id is not None,
                "duplicate_of": duplicate_resume_id,
            })

        except Exception as e:
            logger.error(f"上传简历失败：{e}", exc_info=True)
            try:
                if 'file_path' in locals() and file_path and file_path.exists():
                    file_path.unlink()
            except Exception:
                pass
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.route("/api/resume", methods=["GET"])
    def get_resume():
        """获取简历列表或详情"""
        try:
            resume_id = request.args.get("id", type=int)
            user_id = request.args.get("user_id", "default")
            limit = request.args.get("limit", 100, type=int)
            offset = request.args.get("offset", 0, type=int)

            if resume_id:
                resume = db_manager.get_resume(resume_id)
                if resume:
                    return jsonify({"success": True, "resume": resume})
                return jsonify({"success": False, "error": "简历不存在"}), 404

            resumes = db_manager.get_resumes(user_id=user_id, limit=limit, offset=offset)
            return jsonify({"success": True, "count": len(resumes), "resumes": resumes})

        except Exception as e:
            logger.error(f"获取简历失败：{e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.route("/api/resume/latest", methods=["GET"])
    def get_latest_resume():
        """获取最新的简历"""
        try:
            user_id = request.args.get("user_id", "default")
            resume = db_manager.get_latest_resume(user_id=user_id)

            if resume:
                return jsonify({"success": True, "resume": resume})
            return jsonify({"success": True, "resume": None, "message": "暂无简历"})

        except Exception as e:
            logger.error(f"获取最新简历失败：{e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.route("/api/resume/<int:resume_id>", methods=["DELETE"])
    def delete_resume(resume_id):
        """删除简历"""
        try:
            result = db_manager.delete_resume(resume_id)
            if result.get("success"):
                return jsonify(result)
            return jsonify(result), 500

        except Exception as e:
            logger.error(f"删除简历失败：{e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.route("/api/resume/parse", methods=["POST"])
    def reparse_resume():
        """重新解析简历"""
        try:
            data = request.get_json() or {}
            resume_id = data.get("resume_id")

            if not resume_id:
                return jsonify({"success": False, "error": "缺少 resume_id 参数"}), 400

            if resume_parser is None:
                return jsonify({"success": False, "error": "简历解析器未初始化"}), 500

            resume = db_manager.get_resume(resume_id)
            if not resume:
                return jsonify({"success": False, "error": "简历不存在"}), 404

            file_path = resume.get("file_path")
            if not isinstance(file_path, str) or not file_path.strip():
                return jsonify({"success": False, "error": "简历文件路径无效"}), 400

            if not os.path.exists(file_path):
                return jsonify({"success": False, "error": "简历文件不存在"}), 404

            logger.info(f"重新解析简历：{resume.get('file_name')}")
            parsed_result = resume_parser.parse_file(file_path)

            if parsed_result.get("error"):
                db_manager.update_resume_status(resume_id, "error", parsed_result.get("error"))
                return jsonify({"success": False, "error": parsed_result.get("error")}), 500

            _update_resume_parsed_data(db_manager, resume_id, parsed_result)

            logger.info(f"✓ 简历重新解析完成：{resume.get('file_name')}")

            return jsonify({
                "success": True,
                "message": "简历重新解析成功",
                "data": parsed_result,
            })

        except Exception as e:
            logger.error(f"重新解析简历失败：{e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.route("/api/resume/optimize", methods=["POST"])
    def optimize_resume():
        """基于目标岗位/JD 对当前简历做轻量优化，并返回前后对比。"""
        try:
            if resume_optimizer_service is None:
                return jsonify({
                    "success": False,
                    "error": resume_optimizer_import_error or "简历优化服务未初始化",
                }), 500

            data = request.get_json(silent=True) or {}
            user_id = str(data.get("user_id") or "default").strip() or "default"
            job_description = str(data.get("job_description") or "").strip()
            strategy = str(data.get("strategy") or "keywords").strip().lower()
            profile_form = data.get("profile_form") if isinstance(data.get("profile_form"), dict) else {}

            if strategy not in {"nudge", "keywords", "full"}:
                strategy = "keywords"

            if not job_description:
                return jsonify({
                    "success": False,
                    "error": "请先填写目标岗位描述（JD）后再开始优化。",
                }), 400

            latest_resume = db_manager.get_latest_resume(user_id=user_id)
            result = resume_optimizer_service.optimize(
                user_id=user_id,
                latest_resume=latest_resume,
                profile_form=profile_form,
                job_description=job_description,
                strategy=strategy,
            )
            return jsonify({"success": True, "result": result})
        except Exception as e:
            logger.error(f"简历优化失败：{e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.route("/api/resume/optimizations", methods=["GET"])
    def list_resume_optimizations():
        """获取简历优化历史。"""
        try:
            user_id = request.args.get("user_id", "default")
            limit = request.args.get("limit", 10, type=int)
            offset = request.args.get("offset", 0, type=int)
            history = db_manager.get_resume_optimizations(user_id=user_id, limit=limit, offset=offset)
            return jsonify({
                "success": True,
                "count": len(history),
                "optimizations": history,
            })
        except Exception as e:
            logger.error(f"获取简历优化历史失败：{e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.route("/api/resume/optimizations/<optimization_id>", methods=["GET"])
    def get_resume_optimization(optimization_id):
        """获取单条简历优化详情。"""
        try:
            user_id = request.args.get("user_id", "default")
            item = db_manager.get_resume_optimization(optimization_id, user_id=user_id)
            if not item:
                return jsonify({"success": False, "error": "简历优化记录不存在"}), 404
            return jsonify({"success": True, "optimization": item})
        except Exception as e:
            logger.error(f"获取简历优化详情失败：{e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    return bp

