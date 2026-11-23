import unittest

from controller.xuly_chatbot import _validate_geometry_tasks
from math_engine.draw.draw_2D_3D import draw_angle


class SketchDrawingTests(unittest.TestCase):
    def test_relative_lengths_in_2d_and_3d(self):
        for extra in ([], [0]):
            for drawn_ab, valid in ((5, True), (1, False)):
                task = {"id": "abc", "operation": "draw_line", "input": {
                    "drawing_mode": "sketch", "points": ["A", "B"],
                    "coordinates": {"A": [0, 0] + extra, "B": [drawn_ab, 0] + extra, "C": [0, 3] + extra},
                    "constraints": [{"type": "segment_length", "segment": ["A", "B"], "length": 100},
                                    {"type": "segment_length", "segment": ["A", "C"], "length": 2}],
                }}
                result = _validate_geometry_tasks([task], {}, "test-sketch")
                self.assertEqual(result["ok"], valid, result)
                if valid:
                    self.assertEqual(task["input"]["coordinates"]["B"][0], 5)
                    self.assertEqual(task["input"]["sketch_measurements"][0]["value"], 100)

    def test_angle_label_and_angle_class(self):
        data = {"points": ["A", "B", "C"], "coordinates": {"A": [2, 0], "B": [0, 0], "C": [1, 1]},
                "angle_degrees": 60}
        self.assertEqual(draw_angle({**data, "drawing_mode": "sketch"})["angle_degrees"], 60)
        with self.assertRaises(ValueError):
            draw_angle({**data, "drawing_mode": "sketch", "angle_degrees": 120})
        with self.assertRaises(ValueError):
            draw_angle(data)
