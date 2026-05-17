from flask import Flask

from routes.knowledge_graph import create_knowledge_graph_blueprint


class _DummyLogger:
    def error(self, *args, **kwargs):
        pass


class _DummyKnowledgeGraphService:
    def health(self):
        return {"enabled": True}

    def build_user_graph(self, user_id="default"):
        return {
            "summary": {"user_id": user_id},
            "nodes": [],
            "edges": [],
        }

    def sync_user_graph(self, user_id="default"):
        return {"user_id": user_id, "synced": True}


def _create_app(service=None, import_error=None):
    app = Flask(__name__)
    app.register_blueprint(
        create_knowledge_graph_blueprint(
            knowledge_graph_service=service,
            knowledge_graph_import_error=import_error,
            logger=_DummyLogger(),
        )
    )
    return app


def test_knowledge_graph_unavailable_health_shape():
    client = _create_app(service=None, import_error="missing dependency").test_client()

    response = client.get("/api/knowledge-graph/health")

    assert response.status_code == 503
    assert response.get_json() == {
        "success": False,
        "enabled": False,
        "error": "knowledge graph service unavailable",
        "details": "missing dependency",
    }


def test_knowledge_graph_profile_normalizes_user_id():
    client = _create_app(service=_DummyKnowledgeGraphService()).test_client()

    response = client.get("/api/knowledge-graph/profile?user_id=%20Demo@Example.com%20")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "summary": {"user_id": "demo@example.com"},
        "nodes": [],
        "edges": [],
    }

