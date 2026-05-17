from flask import Flask

from routes.resume import create_resume_blueprint


class _DummyDb:
    def get_resumes(self, *args, **kwargs):
        return []

    def get_resume(self, *args, **kwargs):
        return None

    def get_latest_resume(self, *args, **kwargs):
        return None

    def delete_resume(self, *args, **kwargs):
        return {"success": True}

    def get_resume_optimizations(self, *args, **kwargs):
        return []

    def get_resume_optimization(self, *args, **kwargs):
        return None


class _DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def _create_app():
    app = Flask(__name__)
    app.register_blueprint(
        create_resume_blueprint(
            db_manager=_DummyDb(),
            resume_parser=None,
            resume_optimizer_service=None,
            resume_optimizer_import_error=None,
            logger=_DummyLogger(),
        )
    )
    return app


def test_resume_blueprint_registers_expected_routes():
    app = _create_app()

    routes = {
        str(rule)
        for rule in app.url_map.iter_rules()
        if str(rule).startswith("/api/resume")
    }

    assert routes == {
        "/api/resume",
        "/api/resume/<int:resume_id>",
        "/api/resume/latest",
        "/api/resume/optimizations",
        "/api/resume/optimizations/<optimization_id>",
        "/api/resume/optimize",
        "/api/resume/parse",
        "/api/resume/upload",
    }


def test_latest_resume_empty_response_shape():
    client = _create_app().test_client()

    response = client.get("/api/resume/latest")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "resume": None,
        "message": "暂无简历",
    }

