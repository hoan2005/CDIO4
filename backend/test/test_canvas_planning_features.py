import unittest
import re
from unittest.mock import Mock, patch

from controller import xuly_chatbot
from controller.xuly_chatbot import _collect_state_points, _is_canvas_delete_request
from controller.execution_controller import ExecutionController
from math_engine.draw.draw_2D_3D import draw_angle, draw_equal_segments
from math_engine.draw.draw_3D import draw_polygon_3d
from orchestrator.orchestrator import (
    ALLOWED_OPERATIONS,
    Orchestrator,
    ensure_answer_task,
    validate_plan,
)
from orchestrator.prompt import ORCHESTRATOR_SYSTEM_PROMPT
from controller.final_answer_prompt import FINAL_ANSWER_SYSTEM_PROMPT
from state.state_manager import StateManager


class CanvasPlanningFeatureTests(unittest.TestCase):
    def test_3d_polygon_is_validated_and_keeps_vertex_order(self):
        polygon = draw_polygon_3d({
            "vertices": ["A", "B", "C"],
            "coordinates": {
                "A": [42, 0, 0],
                "B": [0, 21, 0],
                "C": [0, 0, 10.5],
            },
        })
        self.assertEqual(polygon["kind"], "polygon")
        self.assertEqual(polygon["dimension"], "3d")
        self.assertEqual(polygon["vertex_order"], ["A", "B", "C"])
        self.assertEqual(len(polygon["edges"]), 3)

    def test_3d_polygon_rejects_non_coplanar_vertices(self):
        with self.assertRaisesRegex(ValueError, "đồng phẳng"):
            draw_polygon_3d({
                "vertices": ["A", "B", "C", "D"],
                "coordinates": {
                    "A": [0, 0, 0],
                    "B": [1, 0, 0],
                    "C": [0, 1, 0],
                    "D": [0, 0, 1],
                },
            })

    def test_3d_polygon_points_are_available_to_follow_up_tasks(self):
        polygon = draw_polygon_3d({
            "vertices": ["A", "B", "C"],
            "coordinates": {
                "A": [1, 0, 0],
                "B": [0, 1, 0],
                "C": [0, 0, 1],
            },
        })
        points = _collect_state_points({
            "canvas_objects": {polygon["id"]: polygon},
        })
        self.assertEqual(points["A"], [1, 0, 0])
        self.assertEqual(points["B"], [0, 1, 0])
        self.assertEqual(points["C"], [0, 0, 1])

    def test_angle_and_equal_segment_markers_require_valid_geometry(self):
        angle = draw_angle({
            "points": ["B", "A", "C"],
            "coordinates": {"A": [0, 0], "B": [3, 0], "C": [0, 4]},
            "right_angle": True,
        })
        self.assertTrue(angle["right_angle"])
        self.assertAlmostEqual(angle["angle_degrees"], 90)

        with self.assertRaisesRegex(ValueError, "không tạo góc 90"):
            draw_angle({
                "points": ["B", "A", "C"],
                "coordinates": {"A": [0, 0], "B": [3, 0], "C": [1, 4]},
                "right_angle": True,
            })

        marks = draw_equal_segments({
            "segments": [["A", "B"], ["C", "D"]],
            "coordinates": {
                "A": [0, 0], "B": [3, 0], "C": [0, 2], "D": [3, 2],
            },
            "mark_count": 2,
        })
        self.assertEqual(marks["mark_count"], 2)
        with self.assertRaisesRegex(ValueError, "không có cùng độ dài"):
            draw_equal_segments({
                "segments": [["A", "B"], ["C", "D"]],
                "coordinates": {
                    "A": [0, 0], "B": [3, 0], "C": [0, 2], "D": [4, 2],
                },
            })

    def test_3d_perpendicular_to_plane_has_two_valid_right_angle_markers(self):
        coordinates = {
            "A": [0, 0, 0],
            "B": [3, 0, 0],
            "C": [0, 4, 0],
            "S": [0, 0, 5],
        }
        for points in (["S", "A", "B"], ["S", "A", "C"]):
            angle = draw_angle({
                "points": points,
                "coordinates": coordinates,
                "right_angle": True,
            })
            self.assertEqual(angle["dimension"], "3d")
            self.assertTrue(angle["right_angle"])
            self.assertAlmostEqual(angle["angle_degrees"], 90)

    def test_prompt_selects_3d_for_xyz_and_marks_line_plane_perpendicularity(self):
        self.assertIn("bắt buộc dùng operation 3D phù hợp", ORCHESTRATOR_SYSTEM_PROMPT)
        self.assertIn('["S","A","B"]', ORCHESTRATOR_SYSTEM_PROMPT)
        self.assertIn('["S","A","C"]', ORCHESTRATOR_SYSTEM_PROMPT)
        self.assertIn("right_angle=true", ORCHESTRATOR_SYSTEM_PROMPT)

    def test_new_draw_tasks_execute_and_update_canvas_state(self):
        manager = StateManager()
        state = manager.get_state("draw_markers_test")
        plan = {
            "tasks": [
                {
                    "id": "face",
                    "domain": "geometry",
                    "operation": "draw_polygon_3d",
                    "input": {
                        "vertices": ["A", "B", "C"],
                        "coordinates": {
                            "A": [0, 0, 0],
                            "B": [3, 0, 0],
                            "C": [0, 4, 0],
                        },
                    },
                },
                {
                    "id": "right-angle",
                    "domain": "geometry",
                    "operation": "draw_angle",
                    "input": {
                        "points": ["B", "A", "C"],
                        "coordinates": {
                            "A": [0, 0, 0],
                            "B": [3, 0, 0],
                            "C": [0, 4, 0],
                        },
                        "right_angle": True,
                    },
                },
                {
                    "id": "equal-edges",
                    "domain": "geometry",
                    "operation": "draw_equal_segments",
                    "input": {
                        "segments": [["A", "B"], ["C", "D"]],
                        "coordinates": {
                            "A": [0, 0, 0],
                            "B": [3, 0, 0],
                            "C": [0, 1, 0],
                            "D": [3, 1, 0],
                        },
                    },
                },
            ],
        }
        result = ExecutionController(manager).run(plan, state)
        self.assertTrue(result["success"], result)
        self.assertEqual(
            [obj["kind"] for obj in result["canvas"]["add"]],
            ["polygon", "angle", "equal_segments"],
        )
        self.assertEqual(len(manager.get_state("draw_markers_test")["canvas_objects"]), 3)

    def test_planner_contract_includes_answer_and_geometry_operations(self):
        self.assertTrue({
            "answer", "draw_polygon_3d", "draw_angle", "draw_equal_segments",
        }.issubset(ALLOWED_OPERATIONS))
        plan = validate_plan({
            "problem_type": "geometry",
            "tasks": [
                {"id": "answer", "domain": "other", "operation": "answer"},
                {"id": "draw", "domain": "geometry", "operation": "draw_polygon_3d"},
            ],
        })
        self.assertEqual([task["operation"] for task in plan["tasks"]], ["answer", "draw_polygon_3d"])
        self.assertIn('"operation": "answer"', ORCHESTRATOR_SYSTEM_PROMPT)
        self.assertIn('"operation": "draw_polygon_3d"', ORCHESTRATOR_SYSTEM_PROMPT)
        used_operations = re.findall(
            r'"operation"\s*:\s*"([^"]+)"',
            ORCHESTRATOR_SYSTEM_PROMPT,
        )
        self.assertTrue(set(used_operations).issubset(ALLOWED_OPERATIONS))

    def test_planner_adds_missing_answer_task_to_mixed_request(self):
        incomplete_plan = {
            "tasks": [
                {"id": "draw", "domain": "geometry", "operation": "draw_polygon_3d"},
            ],
        }
        completed = ensure_answer_task(
            incomplete_plan,
            "Tính T và vẽ tam giác mặt phẳng trong không gian.",
        )
        self.assertEqual(
            [task["operation"] for task in completed["tasks"]],
            ["draw_polygon_3d", "answer"],
        )
        self.assertEqual(len(incomplete_plan["tasks"]), 1)

        class FakeLLM:
            def generate_json(self, **_kwargs):
                return incomplete_plan

        generated = Orchestrator(FakeLLM()).create_plan(
            "Tính T và vẽ tam giác mặt phẳng trong không gian."
        )
        self.assertEqual(generated["tasks"][-1]["operation"], "answer")

    def test_intercept_plane_few_shot_coordinates_satisfy_the_given_data(self):
        a, b, c = 42.0, 21.0, 10.5
        x, y, z = 2.0, 4.0, 8.0
        self.assertAlmostEqual(a, 2 * b)
        self.assertAlmostEqual(a, 4 * c)
        self.assertAlmostEqual(b * c * x + a * c * y + a * b * z, a * b * c)
        self.assertAlmostEqual(a + b + c, 73.5)

    def test_probability_prompt_covers_dependent_draws_and_checks(self):
        self.assertIn("không hoàn lại", FINAL_ANSWER_SYSTEM_PROMPT)
        self.assertIn("chưa chứng minh độc lập", FINAL_ANSWER_SYSTEM_PROMPT)
        self.assertIn(r"\frac{3}{5}", FINAL_ANSWER_SYSTEM_PROMPT)

    def test_empty_canvas_delete_intent_is_distinguished_from_math(self):
        self.assertTrue(_is_canvas_delete_request("hãy xóa đối tượng trên canvas"))
        self.assertTrue(_is_canvas_delete_request("xóa tất cả hình"))
        self.assertFalse(_is_canvas_delete_request("rút gọn rồi xóa mẫu số"))
        self.assertFalse(_is_canvas_delete_request("tính xác suất"))

    def test_empty_canvas_delete_returns_message_without_requesting_a_plan(self):
        manager = Mock()
        manager.get_state.return_value = {"canvas_objects": {}}
        with patch.object(xuly_chatbot, "state_manager", manager), patch.object(
            xuly_chatbot, "create_plan"
        ) as create_plan:
            response = xuly_chatbot.xuly_thongtin(
                "hãy xóa đối tượng trên canvas", "empty_canvas_test"
            )
        self.assertIn("Canvas hiện đang trống", response["message"]["content"])
        self.assertEqual(response["canvas"], {"add": [], "update": [], "remove": []})
        manager.add_turn.assert_called_once()
        create_plan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
