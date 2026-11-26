"""Kiểm thử smoke cho schema gốc của dự án và solver số.
Chạy: python -m unittest -v test_coordinate_solver.py
"""
import math
import unittest
from unittest.mock import Mock

from geometry_validator.constraint_normalizer import ConstraintNormalizer
from geometry_validator.coordinate_solver_controller import CoordinateSolverController
from geometry_validator.constraint_dispatcher import ConstraintDispatcher
from geometry_validator.coordinate_repair import CoordinateRepair
from geometry_validator.geometry_solver_pipeline import GeometrySolverPipeline
from geometry_validator.geometry_validation_controller import GeometryValidationController

class TestConstraintSolver(unittest.TestCase):
    def test_parallel_lines_dispatcher_schema(self):
        coords={"A":[0,0],"B":[1,1],"C":[0,2],"D":[1,0]}
        cons=[{"type":"parallel_lines","line_1":["A","B"],"line_2":["C","D"]}]
        result=CoordinateSolverController(prefer_native=False).solve(coords,cons)
        self.assertTrue(result["success"],result)
        a,b,c,d=[result["coordinates"][k] for k in "ABCD"]
        cross=(b[0]-a[0])*(d[1]-c[1])-(b[1]-a[1])*(d[0]-c[0])
        self.assertAlmostEqual(cross,0.0,places=4)
        checked=ConstraintDispatcher().validate_many(cons,result["coordinates"])
        self.assertEqual(checked[0]["status"],"verified")

    def test_canonical_points_schema_remains_supported(self):
        coords={"A":[0,0],"B":[1,1],"C":[0,2],"D":[1,0]}
        cons=[{"type":"parallel_lines","points":["A","B","C","D"]}]
        result=CoordinateSolverController(prefer_native=False).solve(coords,cons)
        self.assertTrue(result["success"],result)

    def test_user_coordinate_is_hard_anchor(self):
        coords={"A":[0,0],"B":[3,0]}
        controls={"A":{"source":"user","fixed":False,"editable":True}}
        cons=[{"type":"segment_length","segment":["A","B"],"length":5}]
        result=CoordinateSolverController(prefer_native=False).solve(coords,cons,controls)
        self.assertTrue(result["success"],result)
        self.assertEqual(result["coordinates"]["A"],[0.0,0.0])
        self.assertAlmostEqual(math.dist(result["coordinates"]["A"],result["coordinates"]["B"]),5.0,places=4)

    def test_right_triangle_dispatcher_schema(self):
        coords={"A":[0,0],"B":[4,1],"C":[1,3]}
        cons=[{"type":"right_triangle","points":["A","B","C"],"right_angle_at":"A"}]
        result=CoordinateSolverController(prefer_native=False).solve(coords,cons)
        self.assertTrue(result["success"],result)
        checked=ConstraintDispatcher().validate_many(cons,result["coordinates"])
        self.assertEqual(checked[0]["status"],"verified")

    def test_segment_length_dispatcher_validator(self):
        result=ConstraintDispatcher().validate(
            {"type":"segment_length","segment":["A","B"],"length":5},
            {"A":[0,0],"B":[3,4]})
        self.assertEqual(result["status"],"verified")

    def test_validation_only_constraint_is_not_dropped(self):
        coords={"A":[0,0],"B":[3,4]}
        cons=[{"type":"ellipse_parameters","semi_major_axis":5,"semi_minor_axis":2}]
        normalized=ConstraintNormalizer().normalize(cons,coords)
        self.assertEqual(normalized["constraints"],[])
        self.assertEqual(len(normalized["validation_only_constraints"]),1)

    def test_bad_dimension_is_rejected(self):
        with self.assertRaises(ValueError):
            ConstraintNormalizer().normalize([], {"A":[0,0],"B":[0,0,0]})


class TestSolverPipeline(unittest.TestCase):
    def setUp(self):
        self.coordinates = {"A": [0, 0], "B": [3, 0], "C": [0, 2], "D": [2, 2]}
        self.constraints = [
            {"type": "segment_length", "segment": ["A", "B"], "length": 5},
            {"type": "segment_length", "segment": ["C", "D"], "length": 2},
        ]
        self.solution = {**self.coordinates, "B": [5, 0]}

    def pipeline(self, native, fallback, repair_provider=None):
        return GeometrySolverPipeline(
            CoordinateSolverController(plane_2d=native, fallback=fallback),
            GeometryValidationController(repairer=CoordinateRepair(repair_provider)),
        )

    def test_native_solves_distance_in_both_dimensions(self):
        for dimension, module, solver_name in (
            (2, "planegcs", "planegcs"), (3, "py_slvs.slvs", "py_slvs"),
        ):
            with self.subTest(dimension=dimension):
                try:
                    __import__(module)
                except ImportError:
                    self.skipTest(f"{module} is unavailable")
                coordinates = {
                    "A": [0] * dimension,
                    "B": [3] + [0] * (dimension - 1),
                }
                result = GeometrySolverPipeline(
                    CoordinateSolverController(), GeometryValidationController()
                ).solve_and_validate(
                    coordinates, self.constraints[:1], {"point_A": {"source": "user"}},
                )
                self.assertTrue(result["success"], result)
                self.assertEqual(result["solver_result"]["solver"], solver_name)
                self.assertEqual(result["coordinates"]["A"], coordinates["A"])
                self.assertAlmostEqual(math.dist(*result["coordinates"].values()), 5)

    def test_scipy_exception_then_rejected_solution_reselects_anchors(self):
        native = Mock()
        native.solve.return_value = {"success": False, "status": "dependency_missing"}
        fallback = Mock()
        fallback.name = "scipy"
        fallback.solve.side_effect = [
            RuntimeError("least_squares failed"),
            {"success": True, "solver": "scipy", "coordinates": self.coordinates},
            {"success": True, "solver": "scipy", "coordinates": self.solution},
        ]
        repair = Mock()
        result = self.pipeline(native, fallback, repair).solve_and_validate(
            self.coordinates, self.constraints,
        )
        self.assertTrue(result["success"], result)
        attempts = result["solver_result"]["solve_attempts"]
        self.assertEqual([a["status"] for a in attempts], ["solver_exception", "solved", "solved"])
        self.assertEqual([a["normalization"]["gauge_anchor_names"] for a in attempts],
                         [["A", "B"], ["B", "C"], ["C", "D"]])
        repair.assert_not_called()

    def test_repair_runs_after_three_anchor_retries_and_keeps_user_point(self):
        native = Mock()
        native.solve.return_value = {"success": False, "status": "unsupported_constraints"}
        fallback = Mock()
        fallback.solve.return_value = {
            "success": False, "status": "constraint_residual_too_large",
            "errors": ["residual too high"],
        }
        controls = {"point_A": {"source": "user"}}

        def repair(context):
            self.assertEqual(fallback.solve.call_count, 4)
            self.assertEqual(context["locked_points"], ["A"])
            self.assertIn("residual too high", context["error_summary"])
            return {"success": True, "coordinates": {"B": [5, 0]}}

        repair_provider = Mock(side_effect=repair)
        result = self.pipeline(native, fallback, repair_provider).solve_and_validate(
            self.coordinates, self.constraints, controls,
        )
        self.assertTrue(result["success"], result)
        self.assertEqual(result["coordinates"], self.solution)
        attempts = result["solver_result"]["solve_attempts"]
        self.assertEqual([a["normalization"]["gauge_anchor_names"] for a in attempts],
                         [[], ["B"], ["C"], ["D"]])
        repair_provider.assert_called_once()

    def test_native_solver_failure_reselects_anchors_without_scipy(self):
        native = Mock()
        native.solve.side_effect = [
            {"success": False, "status": "native_solver_failed"},
            {"success": True, "solver": "planegcs", "coordinates": self.solution},
        ]
        fallback = Mock()
        result = self.pipeline(native, fallback).solve_and_validate(self.coordinates, self.constraints)
        self.assertTrue(result["success"], result)
        self.assertEqual(native.solve.call_count, 2)
        fallback.solve.assert_not_called()

    def test_llm_constraint_check_waits_until_after_anchor_retries(self):
        native = Mock()
        native.solve.return_value = {"success": True, "solver": "planegcs", "coordinates": self.solution}

        def check(context):
            self.assertEqual(native.solve.call_count, 4)
            return {"status": "satisfied"}

        checker = Mock(side_effect=check)
        pipeline = GeometrySolverPipeline(
            CoordinateSolverController(plane_2d=native),
            GeometryValidationController(dispatcher=ConstraintDispatcher(llm_checker=checker)),
        )
        constraints = [*self.constraints, {"type": "custom_geometry", "points": ["A", "B"]}]
        result = pipeline.solve_and_validate(self.coordinates, constraints)
        self.assertTrue(result["success"], result)
        checker.assert_called_once()


if __name__=="__main__": unittest.main()
