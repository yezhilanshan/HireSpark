import json

from utils.knowledge_graph_service import KnowledgeGraphService


class _DummyDb:
    def __init__(self, evaluations):
        self.evaluations = evaluations

    def get_latest_resume(self, user_id=None):
        return None

    def get_interviews(self, limit=100, offset=0, risk_level=None):
        return [
            {
                "interview_id": "interview-001",
                "start_time": "2026-05-16T10:00:00",
                "overall_score": 62,
                "risk_level": "LOW",
            }
        ]

    def get_interview_evaluations(self, interview_id):
        return self.evaluations

    def get_interview_dialogues(self, interview_id):
        return []

    def get_training_plan_bundle(self, user_id, week_start_date):
        return {"plan": None, "tasks": []}


def _build_service(evaluations):
    return KnowledgeGraphService(db_manager=_DummyDb(evaluations))


def test_build_user_graph_creates_capability_nodes_without_resume():
    service = _build_service([
        {
            "status": "ok",
            "round_type": "technical",
            "position": "前端工程师",
            "technical_accuracy_score": 82,
            "knowledge_depth_score": 54,
        }
    ])

    payload = service.build_user_graph(user_id="demo@example.com")
    nodes_by_id = {node["id"]: node for node in payload["nodes"]}
    edges_by_type = {edge["type"] for edge in payload["edges"]}

    assert nodes_by_id["capability:technical_accuracy"]["score"] == 82
    assert nodes_by_id["capability:knowledge_depth"]["status"] == "risk"
    assert nodes_by_id["weakness:knowledge_depth"]["score"] == 54
    assert "HAS_CAPABILITY" in edges_by_type
    assert "HAS_RISK" in edges_by_type
    assert payload["summary"]["graph_node_count"] == len(payload["nodes"])
    assert payload["summary"]["strength_count"] >= 1
    assert payload["summary"]["risk_count"] >= 1


def test_build_user_graph_reads_nested_dimension_score_payloads():
    service = _build_service([
        {
            "status": "ok",
            "round_type": "technical",
            "position": "算法工程师",
            "fusion_json": json.dumps({
                "dimension_scores": {
                    "technical_accuracy": {"score": 88.5},
                    "logic": {"score": 76},
                }
            }, ensure_ascii=False),
        }
    ])

    payload = service.build_user_graph(user_id="demo@example.com")
    nodes_by_id = {node["id"]: node for node in payload["nodes"]}

    assert nodes_by_id["capability:technical_accuracy"]["score"] == 88.5
    assert nodes_by_id["capability:logic"]["score"] == 76
    assert payload["summary"]["evaluations_analyzed"] == 1
