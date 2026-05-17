from flask import Flask

from routes.system import create_system_blueprint


class _DummyConfig:
    def get(self, key, default=None):
        values = {
            "system.version": "test-version",
            "system.environment": "test",
        }
        return values.get(key, default)


class _DummyLogger:
    def debug(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _DummyPerformanceMonitor:
    def get_system_stats(self):
        return {
            "fps": 30,
            "cpu_percent": 12.5,
            "memory_percent": 45.0,
        }

    def get_performance_summary(self):
        return {"fps": 30, "frame_count": 10}

    def get_bottlenecks(self, threshold):
        return [{"function": "slow", "threshold": threshold}]


class _DummyDb:
    def get_question_bank(self, **kwargs):
        return [
            {
                "question": "介绍一个推荐系统项目",
                "category": "项目经历",
                "round_type": "project",
                "position": "algorithm",
                "description": "推荐系统",
            },
            {
                "question": "讲讲 Java GC",
                "category": "JVM",
                "round_type": "technical",
                "position": "java_backend",
                "description": "垃圾回收",
            },
        ]

    def get_question_bank_facets(self):
        return {
            "round_types": ["project", "technical"],
            "positions": ["algorithm", "java_backend"],
            "difficulties": [],
        }


class _EnabledService:
    enabled = True


class _DummyTts:
    def get_status(self):
        return {"enabled": True}


def _create_app():
    app = Flask(__name__)
    app.register_blueprint(
        create_system_blueprint(
            config=_DummyConfig(),
            logger=_DummyLogger(),
            performance_monitor=_DummyPerformanceMonitor(),
            db_manager=_DummyDb(),
            llm_manager=_EnabledService(),
            rag_service=object(),
            asr_manager=_EnabledService(),
            assistant_service=_EnabledService(),
            tts_manager=_DummyTts(),
            tts_import_error=None,
        )
    )
    return app


def test_index_response_shape():
    response = _create_app().test_client().get("/")

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "AI Interview Platform API",
        "version": "test-version",
        "status": "running",
        "environment": "test",
    }


def test_health_includes_service_statuses():
    response = _create_app().test_client().get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "healthy"
    assert payload["performance"] == {
        "fps": 30,
        "cpu_percent": 12.5,
        "memory_percent": 45.0,
    }
    assert payload["services"]["llm"] is True
    assert payload["services"]["rag"] is True
    assert payload["services"]["tts"] == {"enabled": True}


def test_performance_routes_keep_original_wrappers():
    client = _create_app().test_client()

    assert client.get("/api/performance").get_json() == {
        "success": True,
        "data": {"fps": 30, "frame_count": 10},
    }
    assert client.get("/api/performance/bottlenecks?threshold=150").get_json() == {
        "success": True,
        "data": [{"function": "slow", "threshold": 150.0}],
    }


def test_question_bank_keyword_and_limit():
    response = _create_app().test_client().get("/api/question-bank?keyword=推荐&limit=1")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["total"] == 1
    assert payload["question_bank"][0]["question"] == "介绍一个推荐系统项目"
    assert payload["categories"] == ["项目经历"]

