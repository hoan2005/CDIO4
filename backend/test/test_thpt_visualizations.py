import math
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from controller import xuly_chatbot
from main import app
from math_engine.draw.draw_2D import draw_function, draw_histogram
from math_engine.draw.draw_2D_3D import draw_line, draw_plane
from math_engine.draw.draw_3D import draw_cone, draw_cylinder, draw_sphere
from math_engine.draw.function_graph import draw_area_between


class GraphTests(unittest.TestCase):
    def test_rational_branches_and_asymptotes(self):
        graph = draw_function({"expression": "(x^2+1)/(x-0.37)", "show_asymptotes": True})
        left, right = graph["segments"]
        self.assertLess(left[-1][0], 0.37)
        self.assertGreater(right[0][0], 0.37)
        vertical, oblique = graph["guides"]
        self.assertAlmostEqual(vertical["x"], 0.37)
        self.assertEqual(oblique, {"slope": 1, "intercept": 0.37})

    def test_cancelled_denominator_is_a_hole(self):
        graph = draw_function({"expression": "(x^2-1)/(x-1)", "show_asymptotes": True})
        self.assertEqual(len(graph["segments"]), 2)
        self.assertEqual(graph["guides"], [])
        self.assertEqual(graph["markers"], [{"position": [1, 2], "label": "Điểm khuyết", "open": True}])

    def test_elementary_function_domains(self):
        graph = draw_function({"expression": "tan(x)", "x_range": [-2, 2]})
        self.assertEqual(len(graph["segments"]), 3)
        root = draw_function({"expression": "sqrt(x-3)"})
        self.assertEqual(root["segments"][0][0], [3, 0])
        log = draw_function({"expression": "log(2x, 3)", "x_range": [-1, 2]})
        self.assertGreater(log["segments"][0][0][0], 0)
        exponential = draw_function({"expression": "e^(-x^2)", "x_range": [-1, 1]})
        self.assertAlmostEqual(exponential["segments"][0][-1][1], math.exp(-1))

    def test_extrema_and_tangent(self):
        graph = draw_function({"expression": "x^3 - 3x + 1", "show_extrema": True, "tangent_at": 0})
        self.assertEqual(graph["guides"], [{"slope": -3, "intercept": 1, "role": "tangent"}])
        self.assertEqual({tuple(marker["position"]) for marker in graph["markers"]},
                         {(-1, 3), (1, -1), (0, 1)})
        with self.assertRaises(ValueError):
            draw_function({"expression": "abs(x)", "tangent_at": 0})
        with self.assertRaises(ValueError):
            draw_function({"expression": "1/(x-1)", "tangent_at": 1})

    def test_area_splits_where_top_curve_changes(self):
        area = draw_area_between({"expression": "x^2", "other_expression": "x", "x_range": [-1, 2]})
        self.assertEqual([(band[0][0], band[-1][0]) for band in area["bands"]], [(-1, 0), (0, 1), (1, 2)])
        with self.assertRaisesRegex(ValueError, "khoảng liên tục"):
            draw_area_between({"expression": "1/(x-0.37)", "x_range": [-1, 2]})


class GeometryAndStatisticsTests(unittest.TestCase):
    def test_plane_normal_and_parametric_line(self):
        plane = draw_plane({"coefficients": [2, -1, 3, -6]})
        origin = plane["coordinates"]["origin"]
        normal = plane["coordinates"]["normal"]
        self.assertAlmostEqual(2 * origin[0] - origin[1] + 3 * origin[2], 6)
        self.assertAlmostEqual(math.hypot(*normal), 1)
        line = draw_line({"origin": [1, 0, 3], "direction": [2, -1, 1], "name": "d"})
        self.assertEqual(line["extent"], "infinite")
        self.assertEqual(line["points"][0], [1, 0, 3])
        end = line["points"][1]
        self.assertAlmostEqual(end[0] - 1, -2 * end[1])
        self.assertAlmostEqual(end[2] - 3, -end[1])
        with self.assertRaises(ValueError):
            draw_plane({"coefficients": [0, 0, 0, 1]})
        with self.assertRaises(ValueError):
            draw_line({"origin": [0, 0, 0], "direction": [0, 0, 0]})

    def test_solids_keep_exact_dimensions(self):
        sphere = draw_sphere({"coefficients": [-2, 4, -6, -2]})
        self.assertEqual(sphere["center"], [1, -2, 3])
        self.assertEqual(sphere["radius"], 4)
        cylinder = draw_cylinder({"radius": 2, "base_center": [1, 2, 3], "top_center": [4, 6, 3]})
        self.assertEqual(cylinder["height"], 5)
        cone = draw_cone({"height": 3, "coordinates": {"center": [1, 2, 3]}})
        self.assertEqual(cone["coordinates"]["apex"], [1, 2, 6])
        with self.assertRaises(ValueError):
            draw_cylinder({"radius": 2, "height": 4, "top_center": [0, 0, 5]})

    def test_histogram_uses_density_for_unequal_widths(self):
        result = draw_histogram({"groups": [[30, 50, 6], [10, 20, 4], [20, 30, 7]]})
        self.assertEqual([bar["height"] for bar in result["bars"]], [.4, .7, .3])
        equal = draw_histogram({"groups": [[0, 5, 1], [5, 10, 8]]})
        self.assertEqual([bar["height"] for bar in equal["bars"]], [1, 8])
        with self.assertRaises(ValueError):
            draw_histogram({"groups": [[1, 5, 9], [4, 6, 1]]})

    def test_chat_executes_visualization_plan_and_persists_objects(self):
        operations = [
            ("calculus", "draw_function", {"expression": "x^2", "tangent_at": 1}, "function"),
            ("calculus", "draw_area_between", {"expression": "x^2", "x_range": [0, 2]}, "area_between"),
            ("geometry", "draw_plane", {"coefficients": [1, 0, 1, -2]}, "plane"),
            ("geometry", "draw_cylinder", {"height": 5, "radius": 2}, "cylinder"),
            ("statistics", "draw_histogram", {"groups": [[10, 20, 4], [20, 30, 7]]}, "histogram"),
        ]
        plan = {"tasks": [
            {"id": f"task_{index}", "domain": domain, "operation": operation, "input": data}
            for index, (domain, operation, data, _) in enumerate(operations)
        ]}
        question = "Vẽ tiếp tuyến, tô miền diện tích, vẽ mặt phẳng, hình trụ và biểu đồ ghép nhóm."
        conversation_id = str(uuid4())
        self.addCleanup(xuly_chatbot.state_manager.delete_conversation, conversation_id)
        with patch.object(xuly_chatbot.llm_client, "generate_json", return_value=plan), patch.object(
            xuly_chatbot, "_generate_text", return_value="Đã vẽ theo yêu cầu."
        ), patch("builtins.print"), TestClient(app) as client:
            response = client.post("/chat", json={"message": question, "conversation_id": conversation_id})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"], body.get("errors"))
        self.assertEqual([obj["kind"] for obj in body["canvas"]["add"]], [entry[3] for entry in operations])
        stored = xuly_chatbot.state_manager.get_state(conversation_id)["canvas_objects"]
        self.assertEqual(len(stored), len(operations))


if __name__ == "__main__":
    unittest.main()
