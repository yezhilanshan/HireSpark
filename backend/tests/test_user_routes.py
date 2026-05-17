from flask import Flask

from routes.user import create_user_blueprint


class _DummyDb:
    def __init__(self):
        self.settings = {
            "demo": {
                "user_id": "demo",
                "in_app_enabled": True,
                "inactivity_24h_enabled": True,
                "streak_enabled": True,
                "weekly_plan_due_enabled": True,
            }
        }

    def get_notification_settings(self, user_id="default"):
        return self.settings.get(user_id, {
            "user_id": user_id,
            "in_app_enabled": True,
            "inactivity_24h_enabled": True,
            "streak_enabled": True,
            "weekly_plan_due_enabled": True,
        })

    def upsert_notification_settings(self, payload):
        self.settings[payload["user_id"]] = payload
        return {"success": True, "settings": payload}

    def get_interviews(self, *args, **kwargs):
        return []

    def get_training_plan_bundle(self, *args, **kwargs):
        return {"plan": None, "tasks": []}


class _DummyLogger:
    def error(self, *args, **kwargs):
        pass


def _create_app(db=None):
    app = Flask(__name__)
    app.register_blueprint(create_user_blueprint(db_manager=db or _DummyDb(), logger=_DummyLogger()))
    return app


def test_get_notification_settings_normalizes_user_id():
    response = _create_app().test_client().get("/api/user/notification-settings?user_id=%20DEMO%20")

    assert response.status_code == 200
    assert response.get_json()["settings"]["user_id"] == "demo"


def test_update_notification_settings_coerces_bools():
    response = _create_app().test_client().put(
        "/api/user/notification-settings",
        json={
            "user_id": "Demo",
            "in_app_enabled": "false",
            "inactivity_24h_enabled": "1",
            "streak_enabled": 0,
            "weekly_plan_due_enabled": True,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["settings"] == {
        "user_id": "demo",
        "in_app_enabled": False,
        "inactivity_24h_enabled": True,
        "streak_enabled": False,
        "weekly_plan_due_enabled": True,
    }


def test_user_reminders_first_training_shape():
    response = _create_app().test_client().get("/api/user/reminders?user_id=demo")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["summary"]["last_training_at"] == ""
    assert payload["summary"]["weekly_plan_pending_count"] == 0
    assert payload["reminders"][0]["id"] == "first-training"

