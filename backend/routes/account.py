"""Authentication and membership routes."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from flask import Blueprint, jsonify, request


AUTH_DEFAULT_EMAIL = str(os.environ.get("AUTH_LOGIN_EMAIL", "admin@zhiyuexingchen.cn") or "").strip().lower() or "admin@zhiyuexingchen.cn"
AUTH_DEFAULT_PASSWORD = str(os.environ.get("AUTH_LOGIN_PASSWORD", "职跃星辰123") or "").strip() or "职跃星辰123"
AUTH_DEFAULT_NAME = str(os.environ.get("AUTH_LOGIN_NAME", "职跃星辰 管理员") or "").strip() or "职跃星辰 管理员"
AUTH_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


class _HttpRateLimiter:
    """Simple IP-based rate limiter for Flask HTTP routes."""

    def __init__(self, max_calls: int = 10, time_window: float = 60.0):
        self.max_calls = max_calls
        self.time_window = time_window
        self._lock = threading.Lock()
        self._calls: dict[str, list[float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        with self._lock:
            now = time.time()
            calls = self._calls.get(client_id, [])
            calls = [t for t in calls if now - t < self.time_window]
            if len(calls) >= self.max_calls:
                self._calls[client_id] = calls
                return False
            calls.append(now)
            self._calls[client_id] = calls
            return True

    def check_and_reject(self) -> Any | None:
        client_id = request.remote_addr or "unknown"
        if not self.is_allowed(client_id):
            return jsonify({"success": False, "error": "请求过于频繁，请稍后再试"}), 429
        return None


_auth_rate_limiter = _HttpRateLimiter(max_calls=15, time_window=60.0)
_change_password_rate_limiter = _HttpRateLimiter(max_calls=5, time_window=60.0)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


AUTH_PASSWORD_PBKDF2_ITERATIONS = max(
    60000,
    min(
        600000,
        _safe_int(os.environ.get("AUTH_PASSWORD_PBKDF2_ITERATIONS", 180000), 180000),
    ),
)


def normalize_auth_email(raw_email: str) -> str:
    return str(raw_email or "").strip().lower()


def normalize_auth_name(raw_name: str) -> str:
    return str(raw_name or "").strip()


def hash_auth_password(password: str, salt_hex: str | None = None) -> str:
    normalized_password = str(password or "")
    if not salt_hex:
        salt_hex = os.urandom(16).hex()
    try:
        salt_bytes = bytes.fromhex(str(salt_hex))
    except Exception:
        salt_hex = os.urandom(16).hex()
        salt_bytes = bytes.fromhex(salt_hex)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        normalized_password.encode("utf-8"),
        salt_bytes,
        AUTH_PASSWORD_PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${AUTH_PASSWORD_PBKDF2_ITERATIONS}${salt_hex}${digest.hex()}"


def verify_auth_password(password: str, stored_hash: str) -> bool:
    normalized_hash = str(stored_hash or "").strip()
    normalized_password = str(password or "")
    if not normalized_hash:
        return False

    parts = normalized_hash.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        import logging
        logging.getLogger(__name__).warning("password hash is not pbkdf2_sha256 format, falling back to plain comparison — consider migrating legacy hashes")
        return hmac.compare_digest(normalized_hash, normalized_password)

    try:
        iterations = int(parts[1])
        salt_hex = parts[2]
        expected_digest = parts[3]
        test_digest = hashlib.pbkdf2_hmac(
            "sha256",
            normalized_password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        ).hex()
        return hmac.compare_digest(expected_digest, test_digest)
    except Exception:
        return False


MEMBERSHIP_TEAM_DISCOUNT = 0.8
MEMBERSHIP_PLAN_CATALOG = {
    "single": {
        "id": "single",
        "title": "按次订阅",
        "description": "适合偶尔练习、临近面试冲刺时按需使用。",
        "unit_label": "/次",
        "base_price": 5,
        "detail": "单次开通即可使用，适合先试用产品能力或补一场专项训练。",
        "highlight": "灵活体验",
        "quota_total": 1,
        "duration_days": None,
    },
    "monthly": {
        "id": "monthly",
        "title": "按月订阅",
        "description": "适合持续打磨表达、节奏和岗位匹配度。",
        "unit_label": "/月",
        "base_price": 40,
        "detail": "按月更适合稳定训练节奏，方便在求职周期内持续复盘和跟踪。",
        "highlight": "热门选择",
        "quota_total": 0,
        "duration_days": 30,
    },
    "yearly": {
        "id": "yearly",
        "title": "按年订阅",
        "description": "适合长期提升与系统训练，综合性价比更高。",
        "unit_label": "/年",
        "base_price": 400,
        "detail": "年付包含每年 200 次使用额度，适合长期备战或全年训练规划。",
        "highlight": "年度最省",
        "quota_total": 200,
        "duration_days": 365,
    },
}


def _normalize_membership_mode(value) -> str:
    normalized = str(value or "").strip().lower()
    return "team" if normalized == "team" else "personal"


def _normalize_membership_plan_id(value) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in MEMBERSHIP_PLAN_CATALOG else ""


def _serialize_membership_catalog():
    return {
        "team_discount": MEMBERSHIP_TEAM_DISCOUNT,
        "modes": [
            {"id": "personal", "label": "个人版", "min_team_size": 1},
            {"id": "team", "label": "团队版", "min_team_size": 2},
        ],
        "plans": list(MEMBERSHIP_PLAN_CATALOG.values()),
    }


def _calculate_membership_selection(mode, plan_id, team_size):
    normalized_mode = _normalize_membership_mode(mode)
    normalized_plan_id = _normalize_membership_plan_id(plan_id)
    if not normalized_plan_id:
        raise ValueError("无效的订阅方案")

    try:
        normalized_team_size = int(team_size or 1)
    except Exception:
        normalized_team_size = 1

    if normalized_mode == "team":
        normalized_team_size = max(2, min(normalized_team_size, 50))
        discount = MEMBERSHIP_TEAM_DISCOUNT
    else:
        normalized_team_size = 1
        discount = 1.0

    plan = MEMBERSHIP_PLAN_CATALOG[normalized_plan_id]
    base_price = float(plan.get("base_price") or 0)
    unit_price = round(base_price * discount, 2)
    total_price = round(unit_price * normalized_team_size, 2)
    base_quota = int(plan.get("quota_total") or 0)
    quota_total = base_quota * normalized_team_size if base_quota > 0 else 0
    expires_at = None
    duration_days = plan.get("duration_days")
    if duration_days:
        expires_at = (datetime.utcnow() + timedelta(days=int(duration_days))).isoformat(timespec="seconds")

    return {
        "membership_mode": normalized_mode,
        "plan_id": normalized_plan_id,
        "team_size": normalized_team_size,
        "plan": plan,
        "unit_price": unit_price,
        "total_price": total_price,
        "quota_total": quota_total,
        "quota_used": 0,
        "expires_at": expires_at,
    }


def _serialize_membership_snapshot(user):
    if not user:
        return {
            "status": "inactive",
            "mode": "personal",
            "plan_id": None,
            "plan_title": None,
            "team_size": 1,
            "auto_renew": False,
            "started_at": None,
            "expires_at": None,
            "usage": {"total": 0, "used": 0, "remaining": 0},
        }

    status = str(user.get("membership_status") or "inactive").strip() or "inactive"
    plan_id = _normalize_membership_plan_id(user.get("membership_plan_id"))
    plan = MEMBERSHIP_PLAN_CATALOG.get(plan_id) if plan_id else None
    quota_total = max(0, int(user.get("membership_cycle_quota") or 0))
    quota_used = max(0, int(user.get("membership_cycle_used") or 0))
    return {
        "status": status,
        "mode": _normalize_membership_mode(user.get("membership_mode")),
        "plan_id": plan_id or None,
        "plan_title": plan.get("title") if plan else None,
        "team_size": max(1, int(user.get("membership_team_size") or 1)),
        "auto_renew": bool(user.get("membership_auto_renew")),
        "started_at": user.get("membership_started_at"),
        "expires_at": user.get("membership_expires_at"),
        "usage": {
            "total": quota_total,
            "used": quota_used,
            "remaining": max(0, quota_total - quota_used),
        },
    }


def _serialize_membership_order(order):
    if not order:
        return None
    plan = MEMBERSHIP_PLAN_CATALOG.get(str(order.get("plan_id") or "").strip())
    return {
        "order_id": order.get("order_id"),
        "membership_mode": order.get("membership_mode"),
        "plan_id": order.get("plan_id"),
        "plan_title": plan.get("title") if plan else None,
        "team_size": int(order.get("team_size") or 1),
        "unit_price": float(order.get("unit_price") or 0),
        "total_price": float(order.get("total_price") or 0),
        "status": str(order.get("status") or "pending").strip() or "pending",
        "quota_total": int(order.get("quota_total") or 0),
        "quota_used": int(order.get("quota_used") or 0),
        "created_at": order.get("created_at"),
        "updated_at": order.get("updated_at"),
    }


def create_account_blueprint(*, db_manager: Any) -> Blueprint:
    bp = Blueprint("account", __name__)

    @bp.route("/api/membership/overview", methods=["GET"])
    def api_membership_overview():
        user_email = normalize_auth_email(request.args.get("user_email", ""))
        if not user_email:
            return jsonify({"success": False, "error": "缺少用户邮箱"}), 400

        user = db_manager.get_user_by_email(user_email)
        if not user:
            return jsonify({"success": False, "error": "用户不存在"}), 404

        orders = db_manager.list_membership_orders(user_email=user_email, limit=6)
        return jsonify({
            "success": True,
            "catalog": _serialize_membership_catalog(),
            "current_membership": _serialize_membership_snapshot(user),
            "recent_orders": [_serialize_membership_order(order) for order in orders],
        })

    @bp.route("/api/membership/orders", methods=["POST"])
    def api_membership_create_order():
        payload = request.get_json(silent=True) or {}
        user_email = normalize_auth_email(payload.get("user_email", ""))
        membership_mode = _normalize_membership_mode(payload.get("membership_mode"))
        plan_id = _normalize_membership_plan_id(payload.get("plan_id"))
        team_size = payload.get("team_size", 1)

        if not user_email:
            return jsonify({"success": False, "error": "缺少用户邮箱"}), 400

        user = db_manager.get_user_by_email(user_email)
        if not user:
            return jsonify({"success": False, "error": "用户不存在"}), 404
        if not plan_id:
            return jsonify({"success": False, "error": "请选择有效的订阅方案"}), 400

        try:
            summary = _calculate_membership_selection(membership_mode, plan_id, team_size)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        order_id = f"mem_{uuid.uuid4().hex[:12]}"
        created = db_manager.create_membership_order({
            "order_id": order_id,
            "user_email": user_email,
            "membership_mode": summary["membership_mode"],
            "plan_id": summary["plan_id"],
            "team_size": summary["team_size"],
            "unit_price": summary["unit_price"],
            "total_price": summary["total_price"],
            "quota_total": summary["quota_total"],
            "quota_used": summary["quota_used"],
            "status": "pending",
        })
        if not created.get("success"):
            return jsonify({"success": False, "error": str(created.get("error") or "创建订单失败")}), 500

        return jsonify({
            "success": True,
            "order": _serialize_membership_order(created.get("order")),
        }), 201

    @bp.route("/api/membership/orders/pay", methods=["POST"])
    def api_membership_pay_order():
        # NOTE: Demo/MVP mode — activates membership without real payment gateway verification.
        # In production, this must go through a payment provider webhook callback.
        payload = request.get_json(silent=True) or {}
        user_email = normalize_auth_email(payload.get("user_email", ""))
        order_id = str(payload.get("order_id", "") or "").strip()

        if not user_email or not order_id:
            return jsonify({"success": False, "error": "缺少支付参数"}), 400

        user = db_manager.get_user_by_email(user_email)
        if not user:
            return jsonify({"success": False, "error": "用户不存在"}), 404

        order = db_manager.get_membership_order(order_id=order_id, user_email=user_email)
        if not order:
            return jsonify({"success": False, "error": "订单不存在"}), 404

        if str(order.get("status") or "").strip() == "paid":
            return jsonify({
                "success": True,
                "order": _serialize_membership_order(order),
                "current_membership": _serialize_membership_snapshot(user),
            })

        try:
            summary = _calculate_membership_selection(
                order.get("membership_mode"),
                order.get("plan_id"),
                order.get("team_size"),
            )
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        started_at = datetime.utcnow().isoformat(timespec="seconds")
        updated_user = db_manager.update_user_membership(user_email, {
            "membership_status": "active",
            "membership_mode": summary["membership_mode"],
            "membership_plan_id": summary["plan_id"],
            "membership_team_size": summary["team_size"],
            "membership_cycle_quota": summary["quota_total"],
            "membership_cycle_used": 0,
            "membership_auto_renew": summary["plan_id"] in {"monthly", "yearly"},
            "membership_started_at": started_at,
            "membership_expires_at": summary["expires_at"],
        })
        if not updated_user.get("success"):
            return jsonify({"success": False, "error": str(updated_user.get("error") or "开通会员失败")}), 500

        order_update = db_manager.update_membership_order_status(order_id, "paid", quota_used=0)
        if not order_update.get("success"):
            return jsonify({"success": False, "error": str(order_update.get("error") or "更新订单状态失败")}), 500

        latest_user = db_manager.get_user_by_email(user_email)
        latest_order = db_manager.get_membership_order(order_id=order_id, user_email=user_email)
        return jsonify({
            "success": True,
            "order": _serialize_membership_order(latest_order),
            "current_membership": _serialize_membership_snapshot(latest_user),
            "message": "会员已开通",
        })

    @bp.route("/api/auth/register", methods=["POST"])
    def api_auth_register():
        payload = request.get_json(silent=True) or {}

        email = normalize_auth_email(payload.get("email", ""))
        password = str(payload.get("password", "") or "")
        display_name = normalize_auth_name(payload.get("name", ""))

        if not email or not AUTH_EMAIL_PATTERN.match(email):
            return jsonify({"success": False, "error": "请输入有效邮箱地址。"}), 400
        if len(password) < 8:
            return jsonify({"success": False, "error": "密码长度至少为 8 位。"}), 400
        if len(password) > 128:
            return jsonify({"success": False, "error": "密码长度不能超过 128 位。"}), 400
        if len(display_name) < 2:
            return jsonify({"success": False, "error": "昵称至少需要 2 个字符。"}), 400
        if len(display_name) > 40:
            return jsonify({"success": False, "error": "昵称长度不能超过 40 个字符。"}), 400

        existing = db_manager.get_user_by_email(email)
        if existing:
            return jsonify({"success": False, "error": "该邮箱已注册，请直接登录。"}), 409

        created = db_manager.create_user(
            email=email,
            password_hash=hash_auth_password(password),
            display_name=display_name,
            is_demo=False,
        )
        if not created or not created.get("success"):
            return jsonify({
                "success": False,
                "error": str((created or {}).get("error") or "注册失败，请稍后重试。"),
            }), 500

        user = created.get("user") or {}
        return jsonify({
            "success": True,
            "user": {
                "id": user.get("id"),
                "email": user.get("email"),
                "name": user.get("display_name") or display_name,
            },
        }), 201

    @bp.route("/api/auth/login", methods=["POST"])
    def api_auth_login():
        rejected = _auth_rate_limiter.check_and_reject()
        if rejected is not None:
            return rejected

        payload = request.get_json(silent=True) or {}
        email = normalize_auth_email(payload.get("email", ""))
        password = str(payload.get("password", "") or "")

        if not email or not password:
            return jsonify({"success": False, "error": "请输入完整的邮箱和密码。"}), 400

        user = db_manager.get_user_by_email(email)
        if not user:
            return jsonify({"success": False, "error": "邮箱或密码错误。"}), 401

        stored_hash = str(user.get("password_hash") or "")
        if not verify_auth_password(password, stored_hash):
            return jsonify({"success": False, "error": "邮箱或密码错误。"}), 401

        return jsonify({
            "success": True,
            "user": {
                "id": user.get("id"),
                "email": user.get("email"),
                "name": user.get("display_name") or AUTH_DEFAULT_NAME,
                "is_demo": bool(user.get("is_demo")),
            },
        })

    @bp.route("/api/auth/change-password", methods=["POST"])
    def api_auth_change_password():
        rejected = _change_password_rate_limiter.check_and_reject()
        if rejected is not None:
            return rejected

        payload = request.get_json(silent=True) or {}
        email = normalize_auth_email(payload.get("email", ""))
        current_password = str(payload.get("current_password", "") or "")
        new_password = str(payload.get("new_password", "") or "")

        if not email or not current_password or not new_password:
            return jsonify({"success": False, "error": "请完整填写邮箱、当前密码和新密码。"}), 400

        user = db_manager.get_user_by_email(email)
        if not user:
            return jsonify({"success": False, "error": "用户不存在。"}), 404

        stored_hash = str(user.get("password_hash") or "")
        if not verify_auth_password(current_password, stored_hash):
            return jsonify({"success": False, "error": "当前密码错误。"}), 401

        if len(new_password) < 8:
            return jsonify({"success": False, "error": "新密码长度至少为 8 位。"}), 400
        if len(new_password) > 128:
            return jsonify({"success": False, "error": "新密码长度不能超过 128 位。"}), 400
        if new_password == current_password:
            return jsonify({"success": False, "error": "新密码不能与当前密码相同。"}), 400

        new_hash = hash_auth_password(new_password)
        result = db_manager.update_password(email, new_hash)
        if not result.get("success"):
            return jsonify({"success": False, "error": str(result.get("error") or "密码修改失败，请稍后重试。")}), 500

        return jsonify({"success": True, "message": "密码修改成功。"})

    return bp

