"""User notification settings and reminder routes."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from flask import Blueprint, jsonify, request


def _coerce_notification_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_notification_settings_payload(payload=None, user_id="default"):
    source = payload or {}
    return {
        "user_id": str(user_id or "default").strip().lower() or "default",
        "in_app_enabled": _coerce_notification_bool(source.get("in_app_enabled"), True),
        "inactivity_24h_enabled": _coerce_notification_bool(source.get("inactivity_24h_enabled"), True),
        "streak_enabled": _coerce_notification_bool(source.get("streak_enabled"), True),
        "weekly_plan_due_enabled": _coerce_notification_bool(source.get("weekly_plan_due_enabled"), True),
    }


def _parse_app_datetime(value):
    text = str(value or "").strip()
    if not text:
        return None
    for parser in (
        lambda item: datetime.fromisoformat(item.replace("Z", "+00:00")),
        lambda item: datetime.strptime(item, "%Y-%m-%d %H:%M:%S"),
        lambda item: datetime.strptime(item, "%Y-%m-%d"),
    ):
        try:
            return parser(text)
        except Exception:
            continue
    return None


def _build_current_week_range():
    safe_anchor = datetime.now()
    week_start = (safe_anchor - timedelta(days=safe_anchor.weekday())).date()
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _compute_training_streak_days(interviews):
    day_set = set()
    for item in interviews or []:
        timestamp = _parse_app_datetime(item.get("start_time") or item.get("created_at"))
        if timestamp is None:
            continue
        day_set.add(timestamp.date())

    if not day_set:
        return 0

    streak = 0
    cursor = datetime.now().date()
    while cursor in day_set:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


def _build_behavior_reminders_payload(db_manager: Any, user_id="default"):
    normalized_user_id = str(user_id or "default").strip().lower() or "default"
    settings = db_manager.get_notification_settings(normalized_user_id) if hasattr(db_manager, "get_notification_settings") else {
        "user_id": normalized_user_id,
        "in_app_enabled": True,
        "inactivity_24h_enabled": True,
        "streak_enabled": True,
        "weekly_plan_due_enabled": True,
    }

    interviews = db_manager.get_interviews(limit=180, offset=0) if hasattr(db_manager, "get_interviews") else []
    sorted_interviews = sorted(
        interviews or [],
        key=lambda item: _parse_app_datetime(item.get("start_time") or item.get("created_at")) or datetime.min,
        reverse=True,
    )
    last_training_dt = _parse_app_datetime(
        (sorted_interviews[0] or {}).get("start_time") or (sorted_interviews[0] or {}).get("created_at")
    ) if sorted_interviews else None

    now = datetime.now()
    current_streak_days = _compute_training_streak_days(sorted_interviews)
    hours_since_training = None
    if last_training_dt is not None:
        hours_since_training = round(max(0.0, (now - last_training_dt).total_seconds()) / 3600, 1)

    week_start, _ = _build_current_week_range()
    current_bundle = db_manager.get_training_plan_bundle(
        user_id=normalized_user_id,
        week_start_date=week_start.strftime("%Y-%m-%d"),
    ) if hasattr(db_manager, "get_training_plan_bundle") else {"plan": None, "tasks": []}
    current_plan = (current_bundle or {}).get("plan") or {}
    current_tasks = (current_bundle or {}).get("tasks") or []

    unfinished_statuses = {"planned", "training", "validation", "reflow"}
    pending_tasks = [
        item for item in current_tasks
        if str((item or {}).get("status") or "").strip().lower() in unfinished_statuses
    ]
    week_end_dt = _parse_app_datetime(current_plan.get("week_end_date"))
    days_until_week_end = None
    if week_end_dt is not None:
        days_until_week_end = (week_end_dt.date() - now.date()).days

    reminders = []
    if settings.get("in_app_enabled", True):
        if settings.get("inactivity_24h_enabled", True):
            if last_training_dt is None:
                reminders.append({
                    "id": "first-training",
                    "type": "inactivity_24h",
                    "tone": "warning",
                    "title": "今天还没有开始训练",
                    "message": "先完成一轮短练习，能更快把状态找回来，也能避免训练节奏断掉。",
                    "cta_label": "开始一场训练",
                    "cta_href": "/interview/setup",
                })
            elif (now - last_training_dt) >= timedelta(hours=24):
                reminders.append({
                    "id": "inactivity-24h",
                    "type": "inactivity_24h",
                    "tone": "warning",
                    "title": "你已经超过 24 小时没有训练",
                    "message": f'上一次训练时间是 {last_training_dt.strftime("%m-%d %H:%M")}，建议今天先完成一场 15 到 30 分钟的专项练习。',
                    "cta_label": "恢复训练",
                    "cta_href": "/interview/setup",
                })

        if settings.get("streak_enabled", True) and current_streak_days >= 3:
            reminders.append({
                "id": f"streak-{current_streak_days}",
                "type": "streak",
                "tone": "success",
                "title": f"你已连续训练 {current_streak_days} 天",
                "message": "现在最适合继续巩固同一类短板，把“偶尔答对”拉成“稳定答好”。",
                "cta_label": "继续保持",
                "cta_href": "/insights",
            })

        if settings.get("weekly_plan_due_enabled", True) and pending_tasks:
            if days_until_week_end is not None and days_until_week_end < 0:
                reminders.append({
                    "id": "weekly-plan-overdue",
                    "type": "weekly_plan_due",
                    "tone": "danger",
                    "title": "本周训练计划已到期，仍有任务未验收",
                    "message": f"还有 {len(pending_tasks)} 项任务未完成，建议先完成最高优先级任务，再决定是否回流到下周。",
                    "cta_label": "查看周计划",
                    "cta_href": "/insights",
                })
            elif days_until_week_end is not None and days_until_week_end <= 1:
                reminders.append({
                    "id": "weekly-plan-due-soon",
                    "type": "weekly_plan_due",
                    "tone": "info",
                    "title": "本周训练计划即将到期",
                    "message": f"还有 {len(pending_tasks)} 项任务待验收，建议优先处理本周最关键的一项。",
                    "cta_label": "去完成任务",
                    "cta_href": "/insights",
                })

    return {
        "settings": settings,
        "summary": {
            "last_training_at": last_training_dt.strftime("%Y-%m-%d %H:%M:%S") if last_training_dt else "",
            "hours_since_training": hours_since_training,
            "current_streak_days": current_streak_days,
            "weekly_plan_pending_count": len(pending_tasks),
            "weekly_plan_due_at": week_end_dt.strftime("%Y-%m-%d") if week_end_dt else "",
            "in_app_enabled": bool(settings.get("in_app_enabled", True)),
        },
        "reminders": reminders,
    }


def create_user_blueprint(*, db_manager: Any, logger: Any) -> Blueprint:
    bp = Blueprint("user", __name__)

    @bp.route("/api/user/notification-settings", methods=["GET"])
    def api_get_notification_settings():
        user_id = str(request.args.get("user_id", "default") or "default").strip().lower() or "default"
        settings = db_manager.get_notification_settings(user_id) if hasattr(db_manager, "get_notification_settings") else {}
        return jsonify({
            "success": True,
            "settings": settings,
        })

    @bp.route("/api/user/notification-settings", methods=["PUT"])
    def api_update_notification_settings():
        if not hasattr(db_manager, "upsert_notification_settings"):
            return jsonify({"success": False, "error": "notification settings unavailable"}), 503

        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id") or request.args.get("user_id", "default") or "default").strip().lower() or "default"
        normalized_payload = _normalize_notification_settings_payload(payload, user_id=user_id)
        result = db_manager.upsert_notification_settings(normalized_payload)
        if not result.get("success"):
            return jsonify({"success": False, "error": result.get("error") or "update notification settings failed"}), 500
        return jsonify({
            "success": True,
            "settings": result.get("settings") or normalized_payload,
        })

    @bp.route("/api/user/reminders", methods=["GET"])
    def api_user_reminders():
        try:
            user_id = str(request.args.get("user_id", "default") or "default").strip().lower() or "default"
            payload = _build_behavior_reminders_payload(db_manager, user_id=user_id)
            return jsonify({
                "success": True,
                **payload,
            })
        except Exception as e:
            logger.error(f"获取用户提醒失败: {e}", exc_info=True)
            return jsonify({"success": False, "error": "获取提醒失败，请稍后重试", "reminders": [], "summary": {}}), 500

    return bp

