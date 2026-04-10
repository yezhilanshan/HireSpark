import unittest

try:
    from backend.utils.round_aggregation import build_round_aggregation
except ImportError:  # pragma: no cover
    from utils.round_aggregation import build_round_aggregation


def make_row(
    *,
    interview_id="interview-a",
    turn_id="turn-1",
    round_type="technical",
    status="ok",
    confidence=1.0,
    score=70.0,
    content=68.0,
    delivery=72.0,
    presence=74.0,
    evaluation_mode=None,
    error_code=None,
    evaluation_note=None,
    veto=False,
):
    layer2 = {}
    if evaluation_mode is not None:
        layer2["evaluation_mode"] = evaluation_mode
    if evaluation_note is not None:
        layer2["evaluation_note"] = evaluation_note

    row = {
        "interview_id": interview_id,
        "turn_id": turn_id,
        "round_type": round_type,
        "status": status,
        "confidence": confidence,
        "question": f"Question for {turn_id}",
        "fusion": {
            "overall_score": score,
            "axis_scores": {
                "content": content,
                "delivery": delivery,
                "presence": presence,
            },
            "integrity": {"veto": veto},
        },
        "layer2": layer2,
    }
    if error_code is not None:
        row["error_code"] = error_code
    return row


class RoundAggregationTestCase(unittest.TestCase):
    def test_mixed_status_rows_compute_expected_raw_and_stable_scores(self):
        rows = [
            make_row(turn_id="turn-1", status="ok", confidence=1.0, score=80),
            make_row(
                turn_id="turn-2",
                status="partial_ok",
                confidence=0.8,
                score=60,
                evaluation_mode="layer2_without_layer1_rubric",
            ),
            make_row(
                turn_id="turn-3",
                status="partial_ok",
                confidence=0.6,
                score=20,
                error_code="LAYER2_FALLBACK",
            ),
            make_row(turn_id="turn-4", status="failed", confidence=1.0, score=90),
        ]

        result = build_round_aggregation(rows)
        profile = result["round_profiles"][0]

        self.assertEqual(profile["turn_count_total"], 4)
        self.assertEqual(profile["turn_count_used"], 3)
        self.assertEqual(profile["turn_count_excluded"], 1)
        self.assertEqual(profile["status_mix"]["full_ok"], 1)
        self.assertEqual(profile["status_mix"]["partial_ok"], 1)
        self.assertEqual(profile["status_mix"]["fallback_only"], 1)
        self.assertEqual(profile["status_mix"]["excluded"], 1)
        self.assertAlmostEqual(profile["round_score_raw"], 66.41, places=2)
        self.assertAlmostEqual(profile["round_score_stable"], 67.69, places=2)
        self.assertEqual(profile["excluded_turns"][0]["turn_id"], "turn-4")

    def test_outlier_suppression_applies_for_gt18_and_gt25_deviation(self):
        rows = [
            make_row(turn_id="turn-a", score=50, content=50, delivery=50, presence=50),
            make_row(turn_id="turn-b", score=70, content=70, delivery=70, presence=70),
            make_row(turn_id="turn-c", score=100, content=100, delivery=100, presence=100),
        ]

        result = build_round_aggregation(rows)
        profile = result["round_profiles"][0]

        self.assertAlmostEqual(profile["round_score_raw"], 73.33, places=2)
        self.assertAlmostEqual(profile["round_score_stable"], 69.05, places=2)
        self.assertEqual(len(profile["outlier_turns"]), 2)
        suppression_factors = sorted(turn["suppression_factor"] for turn in profile["outlier_turns"])
        self.assertEqual(suppression_factors, [0.4, 0.7])

    def test_single_turn_round_gets_full_consistency_score(self):
        rows = [make_row(turn_id="solo", score=66, content=64, delivery=68, presence=70)]

        result = build_round_aggregation(rows)
        profile = result["round_profiles"][0]

        self.assertEqual(profile["round_consistency_score"], 100.0)
        self.assertEqual(result["interview_stability"]["avg_consistency_score"], 100.0)

    def test_axis_scores_use_stable_weights(self):
        rows = [
            make_row(turn_id="turn-a", score=50, content=10, delivery=20, presence=30),
            make_row(turn_id="turn-b", score=70, content=40, delivery=50, presence=60),
            make_row(turn_id="turn-c", score=100, content=100, delivery=100, presence=100),
        ]

        result = build_round_aggregation(rows)
        profile = result["round_profiles"][0]

        self.assertAlmostEqual(profile["round_content_score"], 41.43, places=2)
        self.assertAlmostEqual(profile["round_delivery_score"], 49.52, places=2)
        self.assertAlmostEqual(profile["round_presence_score"], 57.62, places=2)

    def test_relative_position_maps_to_expected_bands(self):
        current_rows = [
            make_row(interview_id="current", turn_id="turn-1", score=84),
            make_row(interview_id="current", turn_id="turn-2", score=86),
        ]
        high_baseline = [
            make_row(interview_id="base-1", turn_id="base-1", score=60),
            make_row(interview_id="base-2", turn_id="base-2", score=62),
        ]
        result_high = build_round_aggregation(
            current_rows=current_rows,
            baseline_rows_by_round={"technical": high_baseline},
        )
        profile_high = result_high["round_profiles"][0]
        self.assertEqual(profile_high["relative_band"], "above_baseline")
        self.assertAlmostEqual(profile_high["relative_position"], 24.0, places=2)

        low_rows = [
            make_row(interview_id="current", turn_id="turn-1", score=40),
            make_row(interview_id="current", turn_id="turn-2", score=42),
        ]
        result_low = build_round_aggregation(
            current_rows=low_rows,
            baseline_rows_by_round={"technical": high_baseline},
        )
        profile_low = result_low["round_profiles"][0]
        self.assertEqual(profile_low["relative_band"], "below_baseline")

        near_rows = [
            make_row(interview_id="current", turn_id="turn-1", score=61),
            make_row(interview_id="current", turn_id="turn-2", score=63),
        ]
        result_near = build_round_aggregation(
            current_rows=near_rows,
            baseline_rows_by_round={"technical": high_baseline},
        )
        profile_near = result_near["round_profiles"][0]
        self.assertEqual(profile_near["relative_band"], "near_baseline")

    def test_missing_baseline_returns_null_calibration_fields(self):
        rows = [make_row(turn_id="turn-1", score=72)]

        result = build_round_aggregation(rows, baseline_rows_by_round={})
        profile = result["round_profiles"][0]

        self.assertIsNone(profile["baseline_avg_score"])
        self.assertIsNone(profile["relative_position"])
        self.assertIsNone(profile["relative_band"])
        self.assertEqual(profile["baseline_sample_size"], 0)


if __name__ == "__main__":
    unittest.main()
