from flask import Flask

from routes.account import create_account_blueprint, hash_auth_password, verify_auth_password


class _DummyDb:
    def __init__(self):
        self.users = {
            "demo@example.com": {
                "id": 1,
                "email": "demo@example.com",
                "display_name": "Demo User",
                "password_hash": hash_auth_password("password123", salt_hex="0" * 32),
                "is_demo": True,
            }
        }

    def get_user_by_email(self, email):
        return self.users.get(email)

    def create_user(self, *, email, password_hash, display_name, is_demo=False):
        user = {
            "id": len(self.users) + 1,
            "email": email,
            "display_name": display_name,
            "password_hash": password_hash,
            "is_demo": is_demo,
        }
        self.users[email] = user
        return {"success": True, "user": user}

    def update_password(self, email, password_hash):
        if email not in self.users:
            return {"success": False, "error": "missing"}
        self.users[email]["password_hash"] = password_hash
        return {"success": True}

    def list_membership_orders(self, *args, **kwargs):
        return []


def _create_app(db=None):
    app = Flask(__name__)
    app.register_blueprint(create_account_blueprint(db_manager=db or _DummyDb()))
    return app


def test_auth_password_hash_roundtrip():
    stored = hash_auth_password("password123", salt_hex="1" * 32)

    assert verify_auth_password("password123", stored)
    assert not verify_auth_password("wrong-password", stored)


def test_account_blueprint_registers_expected_routes():
    app = _create_app()

    routes = {
        str(rule)
        for rule in app.url_map.iter_rules()
        if str(rule).startswith("/api/auth") or str(rule).startswith("/api/membership")
    }

    assert routes == {
        "/api/auth/change-password",
        "/api/auth/login",
        "/api/auth/register",
        "/api/membership/overview",
        "/api/membership/orders",
        "/api/membership/orders/pay",
    }


def test_auth_login_success_shape():
    client = _create_app().test_client()

    response = client.post(
        "/api/auth/login",
        json={"email": " Demo@Example.com ", "password": "password123"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["user"]["email"] == "demo@example.com"
    assert payload["user"]["name"] == "Demo User"


def test_membership_overview_requires_email():
    client = _create_app().test_client()

    response = client.get("/api/membership/overview")

    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "缺少用户邮箱"}

