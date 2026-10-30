"""Kiểm thử smoke cho schema gốc của dự án và solver số.
Chạy: python -m unittest -v test_coordinate_solver.py
"""
import math
import unittest
from geometry_validator.constraint_normalizer import ConstraintNormalizer
from geometry_validator.coordinate_solver_controller import CoordinateSolverController
from geometry_validator.constraint_dispatcher import ConstraintDispatcher

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

if __name__=="__main__": unittest.main()
