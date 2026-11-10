"""Opt-in Gemini evaluation for Vietnamese geometry-construction paraphrases."""
import os
import unittest

from orchestrator.llm_client import LLMClient
from orchestrator.orchestrator import create_plan


CASES = (
    {
        "utterance": "Cho A(0,0), B(4,0). Hãy dựng M là trung điểm của AB.",
        "construct": "midpoint",
        "points": ["A", "B"],
        "dimension": "2d",
    },
    {
        "utterance": "A(0,0), B(4,0). Lấy M nằm chính giữa hai điểm A và B rồi vẽ M.",
        "construct": "midpoint",
        "points": ["A", "B"],
        "dimension": "2d",
    },
    {
        "utterance": "Trong mặt phẳng, P(2,3), A(0,0), B(4,0). Dựng chân đường vuông góc H từ P xuống AB.",
        "construct": "perpendicular_foot",
        "points": ["P", "A", "B"],
        "dimension": "2d",
    },
    {
        "utterance": "Trong Oxyz, P(1,2,5), A(0,0,0), B(1,0,0), C(0,1,0). Tìm hình chiếu vuông góc H của P lên (ABC).",
        "construct": "plane_perpendicular_foot",
        "points": ["P", "A", "B", "C"],
        "dimension": "3d",
    },
    {
        "utterance": "Trong không gian Oxyz, A(0,0,0), B(1,0,0), P(0,0,0), R(0,1,0). Qua P dựng đường vuông góc AB nằm trong mặt phẳng xác định bởi AB và PR.",
        "construct": "perpendicular_point",
        "points": ["A", "B", "P", "R"],
        "dimension": "3d",
    },
    {
        "utterance": "Trong Oxyz, dựng giao điểm của đường AB với CD: A(0,0,0), B(1,1,1), C(0,1,0), D(1,0,1).",
        "construct": "line_intersection",
        "points": ["A", "B", "C", "D"],
        "dimension": "3d",
    },
)


@unittest.skipUnless(
    os.getenv("RUN_GEOMETRY_LLM_EVAL") == "1",
    "Set RUN_GEOMETRY_LLM_EVAL=1 to run the Gemini-backed language evaluation.",
)
class GeometryLanguageEvalTests(unittest.TestCase):
    def test_vietnamese_paraphrases_select_expected_construction(self):
        client = LLMClient()
        for case in CASES:
            with self.subTest(utterance=case["utterance"]):
                plan = create_plan(
                    case["utterance"],
                    {"canvas_objects": {}, "geometry_model": {}},
                    client,
                )
                self.assertEqual(plan["visual_dimension"], case["dimension"])
                constructions = [
                    spec
                    for task in plan["tasks"]
                    for spec in (task.get("input", {}).get("constructions") or {}).values()
                    if isinstance(spec, dict)
                ]
                self.assertTrue(
                    any(
                        spec.get("construct") == case["construct"]
                        and spec.get("depends_on") == case["points"]
                        for spec in constructions
                    ),
                    plan,
                )


if __name__ == "__main__":
    unittest.main()
