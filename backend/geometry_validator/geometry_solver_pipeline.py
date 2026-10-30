"""Pipeline ghép CoordinateSolverController với GeometryValidationController.

Module này không sửa StateManager/Canvas. Caller chỉ commit kết quả khi success=True.
Không tự gọi ConstructionSolver vì điểm dựng phải được xử lý trước pipeline này.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping, Sequence
try:
    from .coordinate_solver_controller import CoordinateSolverController
except ImportError:
    from coordinate_solver_controller import CoordinateSolverController


class GeometrySolverPipeline:
    def __init__(self, coordinate_solver: CoordinateSolverController,
                 geometry_validation_controller: Any):
        if coordinate_solver is None or geometry_validation_controller is None:
            raise ValueError("Cần coordinate_solver và geometry_validation_controller")
        self.coordinate_solver = coordinate_solver
        self.geometry_validation_controller = geometry_validation_controller

    def solve_and_validate(self, coordinates: Mapping[str, Sequence[float]],
                           constraints: Sequence[Mapping[str, Any]],
                           coordinate_control: Mapping[str, Mapping[str, Any]] | None = None,
                           state_context: Mapping[str, Any] | None = None,
                           error_summary: str = "Kiểm tra toàn bộ ràng buộc hình học.") -> dict:
        solved = self.coordinate_solver.solve(
            coordinates=coordinates,
            constraints=constraints,
            coordinate_control=coordinate_control,
        )
        if not solved.get("success"):
            return {"success": False, "stage": "coordinate_solver", "coordinates": deepcopy(dict(coordinates)),
                    "solver_result": solved, "validation_result": None,
                    "message": "; ".join(solved.get("errors") or ["Coordinate solver thất bại."])}

        # Re-validate solver output; numerical convergence is not proof of correctness.
        validated = self.geometry_validation_controller.validate_and_repair(
            coordinates=solved["coordinates"],
            constraints=list(constraints),
            coordinate_control=dict(coordinate_control or {}),
            error_summary=error_summary,
            state_context=dict(state_context or {}),
        )
        if not validated.get("success"):
            return {"success": False, "stage": "geometry_validation", "coordinates": solved["coordinates"],
                    "solver_result": solved, "validation_result": validated,
                    "message": validated.get("message", "Nghiệm chưa vượt qua kiểm định hình học.")}
        return {"success": True, "stage": "validated", "coordinates": validated.get("coordinates") or solved["coordinates"],
                "coordinate_control": validated.get("coordinate_control") or dict(coordinate_control or {}),
                "solver_result": solved, "validation_result": validated,
                "message": validated.get("message", "Đã giải và kiểm định các ràng buộc.")}
