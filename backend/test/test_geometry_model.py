import unittest
from unittest.mock import patch

from controller.execution_controller import ExecutionController
import controller.xuly_chatbot as chatbot
from controller.xuly_chatbot import _validate_geometry_tasks
from geometry_validator.construction_solver import ConstructionSolver
from geometry_validator.geometry_model import build_geometry_model
from orchestrator.orchestrator import resolve_plan_references
from orchestrator.prompt import ORCHESTRATOR_SYSTEM_PROMPT
from state.state_manager import StateManager


class ConstructionSolverTests(unittest.TestCase):
    def setUp(self):
        self.solver = ConstructionSolver()

    def construct(self, points, construction):
        result = self.solver.solve({
            "coordinates": points,
            "constructions": {"X": construction},
        })
        self.assertTrue(result["success"], result)
        return result["computed_points"]["X"]

    def test_midpoint_and_perpendicular_foot_work_in_2d_and_3d(self):
        self.assertEqual(
            self.construct(
                {"A": [0, 0], "B": [4, 2]},
                {"construct": "midpoint", "depends_on": ["A", "B"]},
            ),
            [2.0, 1.0],
        )
        self.assertEqual(
            self.construct(
                {"A": [0, 0, 0], "B": [4, 2, 6]},
                {"construct": "midpoint", "depends_on": ["A", "B"]},
            ),
            [2.0, 1.0, 3.0],
        )
        self.assertEqual(
            self.construct(
                {"P": [2, 3], "A": [0, 0], "B": [4, 0]},
                {"construct": "perpendicular_foot", "depends_on": ["P", "A", "B"]},
            ),
            [2.0, 0.0],
        )
        self.assertEqual(
            self.construct(
                {"P": [2, 3, 5], "A": [0, 0, 0], "B": [4, 0, 0]},
                {"construct": "perpendicular_foot", "depends_on": ["P", "A", "B"]},
            ),
            [2.0, 0.0, 0.0],
        )

    def test_plane_projection_parallel_perpendicular_and_bisector_support_both_dimensions(self):
        self.assertEqual(
            self.construct(
                {"P": [1, 2, 5], "A": [0, 0, 0], "B": [1, 0, 0], "C": [0, 1, 0]},
                {"construct": "plane_perpendicular_foot", "depends_on": ["P", "A", "B", "C"]},
            ),
            [1.0, 2.0, 0.0],
        )
        self.assertEqual(
            self.construct(
                {"A": [0, 0], "B": [2, 0], "P": [1, 1]},
                {"construct": "parallel_point", "depends_on": ["A", "B", "P"], "params": {"length": 2}},
            ),
            [3.0, 1.0],
        )
        self.assertEqual(
            self.construct(
                {"A": [0, 0, 0], "B": [2, 0, 0], "P": [0, 1, 0]},
                {"construct": "parallel_point", "depends_on": ["A", "B", "P"], "params": {"length": 2}},
            ),
            [2.0, 1.0, 0.0],
        )
        self.assertEqual(
            self.construct(
                {"A": [0, 0], "B": [2, 0], "P": [0, 0]},
                {"construct": "perpendicular_point", "depends_on": ["A", "B", "P"]},
            ),
            [0.0, 1.0],
        )
        self.assertEqual(
            self.construct(
                {"A": [0, 0, 0], "B": [1, 0, 0], "P": [0, 0, 0], "R": [0, 1, 0]},
                {"construct": "perpendicular_point", "depends_on": ["A", "B", "P", "R"]},
            ),
            [0.0, 0.0, 1.0],
        )
        self.assertAlmostEqual(
            self.construct(
                {"A": [1, 0], "B": [0, 0], "C": [0, 1]},
                {"construct": "angle_bisector", "depends_on": ["A", "B", "C"]},
            )[0],
            2**-0.5,
        )
        bisector_3d = self.construct(
            {"A": [1, 0, 0], "B": [0, 0, 0], "C": [0, 1, 0]},
            {"construct": "angle_bisector", "depends_on": ["A", "B", "C"]},
        )
        self.assertAlmostEqual(bisector_3d[0], 2**-0.5)
        self.assertAlmostEqual(bisector_3d[1], 2**-0.5)

    def test_3d_tangent_requires_circle_plane_and_constructs_real_contact(self):
        result = self.solver.solve({
            "coordinates": {"O": [0, 0, 0], "D": [5, 0, 0]},
            "constructions": {
                "T": {
                    "construct": "tangent_point",
                    "depends_on": ["O", "D"],
                    "params": {"radius": 3, "plane_normal": [0, 0, 1], "which": "first"},
                },
            },
        })
        self.assertTrue(result["success"], result)
        x, y, z = result["computed_points"]["T"]
        self.assertAlmostEqual(x * x + y * y, 9)
        self.assertAlmostEqual((x - 5) * x + y * y, 0)
        self.assertEqual(z, 0)

        missing_plane = self.solver.solve({
            "coordinates": {"O": [0, 0, 0], "D": [5, 0, 0]},
            "constructions": {
                "T": {
                    "construct": "tangent_point",
                    "depends_on": ["O", "D"],
                    "params": {"radius": 3},
                },
            },
        })
        self.assertFalse(missing_plane["success"])
        self.assertIn("plane_normal", " ".join(missing_plane["errors"]))

    def test_3d_perpendicular_without_reference_fails_instead_of_guessing(self):
        result = self.solver.solve({
            "coordinates": {"A": [0, 0, 0], "B": [1, 0, 0], "P": [0, 0, 0]},
            "constructions": {
                "Q": {"construct": "perpendicular_point", "depends_on": ["A", "B", "P"]},
            },
        })
        self.assertFalse(result["success"])
        self.assertIn("điểm tham chiếu", " ".join(result["errors"]))


class GeometryModelTests(unittest.TestCase):
    def test_model_indexes_points_constructions_and_reverse_dependencies(self):
        model = build_geometry_model({
            "point_A": {"id": "point_A", "kind": "point", "label": "A", "position": [0, 0]},
            "point_M": {
                "id": "point_M",
                "kind": "point",
                "label": "M",
                "position": [1, 0],
                "constructions": {
                    "M": {"construct": "midpoint", "depends_on": ["A", "B"]},
                },
            },
        })
        self.assertEqual(model["points"]["A"]["coordinates"], [0, 0])
        self.assertEqual(model["dependents"]["A"], ["M"])
        self.assertEqual(model["objects"]["point_M"]["point_names"], ["M"])

    def test_connect_canvas_points_persists_2d_and_3d_lines(self):
        manager = StateManager()
        conversation_id = "connect-existing-points"
        manager.add_object(conversation_id, {
            "id": "point_A", "kind": "point", "dimension": "2d",
            "label": "A", "position": [0, 0],
        })
        manager.add_object(conversation_id, {
            "id": "point_B", "kind": "point", "dimension": "2d",
            "label": "B", "position": [3, 4],
        })
        manager.add_object(conversation_id, {
            "id": "cube-1", "kind": "cube", "dimension": "3d",
            "vertices": {"C": [0, 0, 0], "D": [0, 2, 0]},
        })

        with patch.object(chatbot, "state_manager", manager):
            line_2d = chatbot.connect_canvas_points(conversation_id, "A", "B")
            line_3d = chatbot.connect_canvas_points(conversation_id, "C", "D")

        self.assertEqual(line_2d["dimension"], "2d")
        self.assertEqual(line_2d["point_names"], ["A", "B"])
        self.assertEqual(line_2d["points"], [[0.0, 0.0], [3.0, 4.0]])
        self.assertEqual(line_3d["dimension"], "3d")
        self.assertEqual(line_3d["point_names"], ["C", "D"])
        self.assertEqual(line_3d["points"], [[0.0, 0.0, 0.0], [0.0, 2.0, 0.0]])
        objects = manager.get_state(conversation_id)["canvas_objects"]
        self.assertIn(line_2d["id"], objects)
        self.assertIn(line_3d["id"], objects)

    def test_moving_a_point_recomputes_dependent_points_and_linked_objects(self):
        manager = StateManager()
        conversation_id = "dependent-update"
        manager.add_object(conversation_id, {
            "id": "point_A", "kind": "point", "dimension": "2d", "label": "A", "position": [0, 0],
        })
        manager.add_object(conversation_id, {
            "id": "point_B", "kind": "point", "dimension": "2d", "label": "B", "position": [2, 0],
        })
        manager.add_object(conversation_id, {
            "id": "point_M", "kind": "point", "dimension": "2d", "label": "M", "position": [1, 0],
            "constructions": {"M": {"construct": "midpoint", "depends_on": ["A", "B"]}},
        })
        manager.add_object(conversation_id, {
            "id": "line_AM", "kind": "line", "dimension": "2d",
            "point_names": ["A", "M"], "points": [[0, 0], [1, 0]],
        })

        result = ExecutionController(manager).run({
            "tasks": [{
                "id": "move-a",
                "domain": "geometry",
                "operation": "update_object",
                "object_id": "point_A",
                "input": {"coordinates": {"A": [0, 2]}},
            }],
        }, manager.get_state(conversation_id))
        self.assertTrue(result["success"], result)
        current = manager.get_state(conversation_id)["canvas_objects"]
        self.assertEqual(current["point_M"]["position"], [1.0, 1.0])
        self.assertEqual(current["line_AM"]["points"], [[0, 2], [1.0, 1.0]])
        self.assertEqual(
            {obj["id"] for obj in result["canvas"]["update"]},
            {"point_A", "point_M", "line_AM"},
        )

    def test_validated_construction_metadata_is_retained_for_future_recomputation(self):
        task = {
            "id": "draw-midpoint",
            "domain": "geometry",
            "operation": "draw_point",
            "input": {
                "name": "M",
                "coordinates": {"A": [0, 0], "B": [2, 0], "M": [1, 0]},
                "constructions": {
                    "M": {"construct": "midpoint", "depends_on": ["A", "B"]},
                },
            },
        }
        validation = _validate_geometry_tasks(
            [task],
            {"canvas_objects": {}, "coordinate_control": {}, "geometry_model": {}},
            "persist-construction",
        )
        self.assertTrue(validation["ok"], validation)
        self.assertEqual(
            task["_construction_specs"]["M"]["construct"],
            "midpoint",
        )
        self.assertEqual(task["input"]["constructions"], {})
        manager = StateManager()
        result = ExecutionController(manager).run(
            {"tasks": [task]},
            manager.get_state("persisted-construction"),
        )
        self.assertTrue(result["success"], result)
        stored = manager.get_state("persisted-construction")
        self.assertEqual(
            stored["canvas_objects"]["point_M"]["constructions"]["M"]["construct"],
            "midpoint",
        )
        self.assertEqual(stored["geometry_model"]["dependents"]["A"], ["M"])

    def test_removing_a_source_point_cascades_constructed_dependents(self):
        manager = StateManager()
        conversation_id = "dependent-remove"
        for name, position in (("A", [0, 0]), ("B", [2, 0])):
            manager.add_object(conversation_id, {
                "id": f"point_{name}", "kind": "point", "dimension": "2d",
                "label": name, "position": position,
            })
        manager.add_object(conversation_id, {
            "id": "point_M", "kind": "point", "dimension": "2d", "label": "M", "position": [1, 0],
            "constructions": {"M": {"construct": "midpoint", "depends_on": ["A", "B"]}},
        })

        result = ExecutionController(manager).run({
            "tasks": [{
                "id": "remove-a",
                "domain": "geometry",
                "operation": "remove_object",
                "input": {"object_id": "point_A"},
            }],
        }, manager.get_state(conversation_id))
        self.assertTrue(result["success"], result)
        self.assertEqual(set(result["canvas"]["remove"]), {"point_A", "point_M"})
        self.assertNotIn("point_M", manager.get_state(conversation_id)["canvas_objects"])


class ObjectReferenceTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "focus_id": "line_CD",
            "canvas_objects": {
                "line_AB": {"id": "line_AB", "kind": "line", "label": "Đường thẳng AB", "point_names": ["A", "B"]},
                "line_CD": {"id": "line_CD", "kind": "line", "label": "Đường thẳng CD", "point_names": ["C", "D"]},
            },
        }

    def test_explicit_vietnamese_reference_resolves_to_existing_object_id(self):
        for utterance, target_ref in (
            ("Xóa đường AB", "đường AB"),
            ("Xóa đường thẳng AB", "đường thẳng AB"),
            ("Bỏ AB khỏi hình", "AB"),
        ):
            with self.subTest(utterance=utterance):
                plan = resolve_plan_references({
                    "ambiguous": False,
                    "tasks": [{
                        "id": "remove",
                        "domain": "geometry",
                        "operation": "remove_object",
                        "input": {"target_ref": target_ref},
                    }],
                }, utterance, self.state)
                self.assertFalse(plan["ambiguous"])
                self.assertEqual(plan["tasks"][0]["object_id"], "line_AB")

    def test_recent_object_reference_uses_focus_and_missing_target_asks(self):
        latest = resolve_plan_references({
            "ambiguous": False,
            "tasks": [{
                "id": "remove",
                "domain": "geometry",
                "operation": "remove_object",
                "input": {},
            }],
        }, "Xóa đường vừa vẽ", self.state)
        self.assertEqual(latest["tasks"][0]["object_id"], "line_CD")

        missing = resolve_plan_references({
            "ambiguous": False,
            "tasks": [{
                "id": "remove",
                "domain": "geometry",
                "operation": "remove_object",
                "input": {"target_ref": "đường không tồn tại"},
            }],
        }, "Xóa đường không tồn tại", self.state)
        self.assertTrue(missing["ambiguous"])
        self.assertEqual(missing["tasks"][0]["operation"], "clarify")
        self.assertIn("chưa xác định chắc chắn", missing["notes"][0])

    def test_ambiguous_matching_labels_are_not_resolved_by_focus(self):
        duplicate_state = {
            **self.state,
            "canvas_objects": {
                **self.state["canvas_objects"],
                "line_AB_copy": {
                    "id": "line_AB_copy",
                    "kind": "line",
                    "label": "Đường thẳng AB",
                    "point_names": ["A", "B"],
                },
            },
        }
        plan = resolve_plan_references({
            "ambiguous": False,
            "tasks": [{
                "id": "remove",
                "domain": "geometry",
                "operation": "remove_object",
                "input": {"target_ref": "đường AB"},
            }],
        }, "Xóa đường AB, không phải đường vừa vẽ", duplicate_state)
        self.assertTrue(plan["ambiguous"])
        self.assertEqual(plan["tasks"][0]["operation"], "clarify")


class UpdatingConstraintTests(unittest.TestCase):
    def test_update_replaces_only_the_saved_constraint_for_its_object(self):
        names = ["A", "B", "C", "D", "A'", "B'", "C'", "D'"]
        coordinates = {
            "A": [0, 0, 0], "B": [5, 0, 0], "C": [5, 5, 0], "D": [0, 5, 0],
            "A'": [0, 0, 5], "B'": [5, 0, 5], "C'": [5, 5, 5], "D'": [0, 5, 5],
        }
        old_coordinates = {
            "A": [0, 0, 0], "B": [3, 0, 0], "C": [3, 3, 0], "D": [0, 3, 0],
            "A'": [0, 0, 3], "B'": [3, 0, 3], "C'": [3, 3, 3], "D'": [0, 3, 3],
        }
        cube_constraint = {"type": "cube", "points": names}
        new_length_constraint = {
            "type": "segment_length", "segment": ["A", "B"], "length": 5,
        }
        other_object_constraint = {
            "type": "segment_length", "segment": ["A", "C"], "length": 5 * 2 ** 0.5,
        }
        captured = {}

        class PipelineStub:
            def solve_and_validate(self, **kwargs):
                captured.update(kwargs)
                solver_result = chatbot.coordinate_solver.solve(
                    kwargs["coordinates"],
                    kwargs["constraints"],
                    kwargs["coordinate_control"],
                )
                if not solver_result["success"]:
                    return {
                        "success": False,
                        "stage": "coordinate_solver",
                        "message": "; ".join(solver_result["errors"]),
                        "solver_result": solver_result,
                    }
                results = [
                    {"constraint": constraint, "status": "verified", "method": "python"}
                    for constraint in kwargs["constraints"]
                ]
                return {
                    "success": True,
                    "coordinates": solver_result["coordinates"],
                    "coordinate_control": kwargs["coordinate_control"],
                    "solver_result": solver_result,
                    "validation_result": {
                        "coordinates": solver_result["coordinates"],
                        "coordinate_control": kwargs["coordinate_control"],
                        "results": results,
                        "message": "validated",
                    },
                }

        state = {
            "canvas_objects": {
                "cube-1": {
                    "id": "cube-1", "kind": "cube", "vertices": old_coordinates,
                },
            },
            "coordinate_control": {
                name: {"source": "state", "fixed": False, "editable": True}
                for name in names
            },
            "geometry_model": {"dependents": {}},
            "constraints": {
                "cube-shape": {
                    **cube_constraint, "object_ids": ["cube-1"], "status": "verified",
                },
                "cube-edge": {
                    "type": "segment_length", "segment": ["A", "B"], "length": 3,
                    "object_ids": ["cube-1"], "status": "verified",
                },
                "other-object-edge": {
                    **other_object_constraint,
                    "object_ids": ["another-cube"], "status": "verified",
                },
            },
        }
        task = {
            "id": "update-cube",
            "operation": "update_object",
            "object_id": "cube-1",
            "input": {
                "object_id": "cube-1",
                "coordinates": coordinates,
                "constraints": [cube_constraint, new_length_constraint],
                "coordinate_control": {
                    f"point_{name}": {
                        "source": "state", "fixed": False, "editable": True,
                    }
                    for name in names
                },
            },
        }

        with patch.object(chatbot, "geometry_solver_pipeline", PipelineStub()):
            result = _validate_geometry_tasks([task], state, "update-cube")

        self.assertTrue(result["ok"], result)
        edge_constraints = [
            constraint for constraint in captured["constraints"]
            if constraint.get("type") == "segment_length"
        ]
        self.assertIn(new_length_constraint, edge_constraints)
        preserved_other_constraint = next(
            constraint for constraint in edge_constraints
            if constraint["segment"] == ["A", "C"]
        )
        self.assertAlmostEqual(
            preserved_other_constraint["length"], other_object_constraint["length"],
        )
        replaced_state_constraint = next(
            item for item in task["_state_validation"]
            if item["constraint_id"] == "cube-edge"
        )
        self.assertEqual(replaced_state_constraint["constraint"], new_length_constraint)

        class StateManagerStub:
            def __init__(self):
                self.constraints = {}

            def get_state(self, _conversation_id):
                return {"revision": 1}

            def set_constraint(self, _conversation_id, constraint_id, constraint):
                self.constraints[constraint_id] = constraint

            def set_coordinate_control(self, *_args):
                pass

        manager = StateManagerStub()
        with patch.object(chatbot, "state_manager", manager):
            chatbot._persist_validation(
                "update-cube",
                [task],
                [{
                    "task_id": "update-cube",
                    "status": "success",
                    "result": [{"id": "cube-1"}],
                }],
            )
        self.assertEqual(manager.constraints["cube-edge"]["length"], 5)
        self.assertNotIn("update-cube_c0", manager.constraints)

    def test_construction_prompt_covers_2d_3d_and_missing_data_policy(self):
        for construction in (
            "midpoint",
            "perpendicular_foot",
            "plane_perpendicular_foot",
            "line_intersection",
            "parallel_point",
            "perpendicular_point",
            "angle_bisector",
            "tangent_point",
        ):
            self.assertIn(construction, ORCHESTRATOR_SYSTEM_PROMPT)
        self.assertIn("dùng `clarify`", ORCHESTRATOR_SYSTEM_PROMPT)
        self.assertIn("geometry_model", ORCHESTRATOR_SYSTEM_PROMPT)

    def test_missing_3d_perpendicular_orientation_is_reported_as_clarification(self):
        validation = _validate_geometry_tasks(
            [{
                "id": "construct-perpendicular",
                "operation": "draw_line",
                "input": {
                    "points": ["P", "Q"],
                    "coordinates": {
                        "A": [0, 0, 0],
                        "B": [1, 0, 0],
                        "P": [0, 0, 0],
                    },
                    "constructions": {
                        "Q": {
                            "construct": "perpendicular_point",
                            "depends_on": ["A", "B", "P"],
                        },
                    },
                },
            }],
            {"canvas_objects": {}, "coordinate_control": {}, "geometry_model": {}},
            "missing-3d-reference",
        )
        self.assertFalse(validation["ok"])
        self.assertTrue(validation["needs_clarification"])
        self.assertIn("bổ sung dữ kiện", validation["message"])


if __name__ == "__main__":
    unittest.main()
