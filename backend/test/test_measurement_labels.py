import unittest

from controller.execution_controller import ExecutionController


class MeasurementLabelTests(unittest.TestCase):
    def test_add_and_relabel_without_resizing(self):
        engine = ExecutionController(None)
        coords = {"A": [0, 0], "B": [3, 0], "C": [1, 2]}
        angle = {"kind": "angle", "points": ["A", "B", "C"], "text": "α"}
        side = {"kind": "length", "points": ["A", "B"], "text": "5 cm"}
        task = {"id": "shape", "domain": "geometry", "operation": "draw_polygon_2d",
                "input": {"vertices": list(coords), "coordinates": coords,
                          "measurement_labels": [angle, side]}}
        obj = engine.execute_task(task, {})["result"]
        state = {"canvas_objects": {obj["id"]: obj}}
        new_side = {**side, "points": ["B", "A"], "text": "9"}
        update = {"id": "label", "domain": "geometry", "operation": "update_object",
                  "input": {"object_id": obj["id"], "measurement_labels": [new_side]}}
        updated = engine.execute_task(update, state)["result"]["objects"][0]
        self.assertEqual(updated["coordinates"], coords)
        self.assertEqual(updated["measurement_labels"], [angle, new_side])
        update["input"]["measurement_labels"] = [{**side, "points": ["A", "D"]}]
        with self.assertRaises(ValueError):
            engine.execute_task(update, state)
