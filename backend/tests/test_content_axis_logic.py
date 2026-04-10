import unittest

try:
    from backend.utils.evaluation_service import EvaluationService
except ImportError:  # pragma: no cover
    from utils.evaluation_service import EvaluationService


class _NullDB:
    pass


class ContentAxisLogicTestCase(unittest.TestCase):
    def test_content_layer_uses_llm_anchor_plus_evidence_correction(self):
        service = EvaluationService(db_manager=_NullDB(), rag_service=None, llm_manager=None)
        try:
            layer1_result = {
                "key_points": {
                    "covered": [{"point": "提到了并发安全边界"}],
                    "missing": ["没有展开性能取舍"],
                    "coverage_ratio": 0.5,
                },
                "rubric_match": {"basic": 1.0, "good": 0.5, "excellent": 0.0},
                "signals": {"hit": ["提到了并发安全边界"], "red_flags": []},
            }
            layer2_result = {
                "overall_score_final": 80.0,
                "rubric_eval": {"confidence": 0.82},
                "final_dimension_scores": {
                    "technical_accuracy": {
                        "score": 90.0,
                        "reason": "concepts are mostly correct",
                        "evidence": {
                            "hit_rubric_points": ["提到了并发安全边界"],
                            "missed_rubric_points": ["没有展开性能取舍"],
                            "source_quotes": ["我会优先从线程安全和使用场景来区分"],
                            "deduction_rationale": "还缺少对性能差异的展开",
                        },
                    }
                },
            }
            text_layer = {"overall_score": 80.0, "confidence": 0.82}
            payload = {"answer": "我会优先从线程安全和使用场景来区分，然后再看性能取舍。"}

            content_layer = service._build_content_layer(
                layer1_result=layer1_result,
                layer2_result=layer2_result,
                text_layer=text_layer,
                payload=payload,
            )

            self.assertEqual(content_layer.get("status"), "ready")
            self.assertAlmostEqual(float(content_layer.get("overall_score") or 0.0), 82.55, places=2)
            correction = (content_layer.get("summary") or {}).get("evidence_correction") or {}
            self.assertEqual(correction.get("strategy"), "llm_anchor_plus_evidence_correction_v1")
            self.assertAlmostEqual(float(correction.get("llm_anchor_score") or 0.0), 80.0, places=2)
            self.assertAlmostEqual(float(correction.get("net_correction") or 0.0), 2.55, places=2)
            confidence_breakdown = content_layer.get("confidence_breakdown") or {}
            self.assertIn("data_confidence", confidence_breakdown)
            self.assertIn("model_confidence", confidence_breakdown)
            self.assertIn("rubric_confidence", confidence_breakdown)
            self.assertGreater(float(confidence_breakdown.get("overall_confidence") or 0.0), 0.0)
            evidence_service = content_layer.get("evidence_service") or {}
            self.assertEqual(evidence_service.get("source"), "text")
            self.assertEqual(evidence_service.get("status"), "ready")
            self.assertIn("features", evidence_service)
            self.assertIn("quotes", evidence_service)
        finally:
            service.shutdown()

    def test_speech_and_video_layers_expose_confidence_breakdown_and_fusion_keeps_it(self):
        service = EvaluationService(db_manager=_NullDB(), rag_service=None, llm_manager=None)
        try:
            service.build_speech_context = lambda payload: {
                "available": True,
                "speech_used": True,
                "quality_gate": {"passed": True, "reasons": []},
                "audio_duration_ms": 18000.0,
                "token_count": 48,
                "final_transcript_excerpt": "这是一次比较稳定的语音回答。",
                "expression_dimensions": {
                    "clarity_score": 82,
                    "fluency_score": 76,
                    "speech_rate_score": 71,
                    "pause_anomaly_score": 68,
                    "filler_frequency_score": 74,
                },
                "expression_score": 75.4,
            }
            speech_layer = service.evaluate_speech_layer({})
            self.assertIn("confidence_breakdown", speech_layer)
            self.assertGreater(float((speech_layer.get("confidence_breakdown") or {}).get("overall_confidence") or 0.0), 0.0)
            speech_evidence = speech_layer.get("evidence_service") or {}
            self.assertEqual(speech_evidence.get("source"), "speech")
            self.assertEqual(speech_evidence.get("status"), "ready")
            self.assertIn("quality_gate", speech_evidence)
            self.assertIn("features", speech_evidence)

            video_layer = service.evaluate_video_layer({
                "detection_state": {
                    "has_face": True,
                    "face_count": 1,
                    "off_screen_ratio": 0.12,
                    "rppg_reliable": True,
                    "hr": 82,
                    "risk_score": 18,
                    "flags": [],
                    "video_features": {
                        "expression_score": 78,
                        "engagement_signals": {
                            "head_movement": 54,
                            "facial_activity": 58,
                        },
                    },
                }
            })
            self.assertIn("confidence_breakdown", video_layer)
            self.assertGreater(float((video_layer.get("confidence_breakdown") or {}).get("overall_confidence") or 0.0), 0.0)
            video_evidence = video_layer.get("evidence_service") or {}
            self.assertEqual(video_evidence.get("source"), "video")
            self.assertEqual(video_evidence.get("status"), "ready")
            self.assertIn("features", video_evidence)
            self.assertIn("signals", video_evidence)

            content_layer = {
                "status": "ready",
                "overall_score": 80.0,
                "confidence": 0.81,
                "confidence_breakdown": {
                    "data_confidence": 0.8,
                    "model_confidence": 0.82,
                    "rubric_confidence": 0.79,
                    "overall_confidence": 0.81,
                },
                "dimension_scores": {"technical_accuracy": {"score": 80.0}},
            }
            fusion = service.fuse_layer_scores(
                content_layer=content_layer,
                delivery_layer=speech_layer,
                presence_layer=video_layer,
                integrity_layer={"status": "ready", "signals": [], "veto": False, "risk_level": "low", "risk_index": 12.0},
                round_type="technical",
            )
            self.assertIn("axis_confidence_breakdowns", fusion)
            self.assertIn("content", fusion["axis_confidence_breakdowns"])
            self.assertIn("delivery", fusion["axis_confidence_breakdowns"])
            self.assertIn("presence", fusion["axis_confidence_breakdowns"])
        finally:
            service.shutdown()


if __name__ == "__main__":
    unittest.main()
