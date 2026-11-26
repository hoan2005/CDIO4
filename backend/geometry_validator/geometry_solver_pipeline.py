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
    MAX_ANCHOR_RETRIES = 3

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
        candidate = deepcopy(dict(coordinates))
        controls = dict(coordinate_control or {})
        validation_args = {
            "constraints": list(constraints),
            "coordinate_control": controls,
            "state_context": dict(state_context or {}),
        }
        solve_attempts = []
        validated = None
        best_failure_count = float("inf")
        for anchor_attempt in range(self.MAX_ANCHOR_RETRIES + 1):
            solved = self.coordinate_solver.solve(
                coordinates=coordinates,
                constraints=constraints,
                coordinate_control=coordinate_control,
                anchor_attempt=anchor_attempt,
            )
            report = {key: value for key, value in solved.items() if key != "coordinates"}
            solve_attempts.append(report)
            if solved["status"] in {"normalization_error", "invalid_constraints"}:
                return {"success": False, "stage": "coordinate_solver", "coordinates": candidate,
                        "solver_result": solved, "validation_result": None,
                        "message": "; ".join(solved["errors"])}
            if solved["success"]:
                validated = self.geometry_validation_controller.validate_and_repair(
                    coordinates=solved["coordinates"], **validation_args, allow_llm=False,
                )
                report["validation_message"] = validated["message"]
                failure_count = sum(
                    item["status"] in {"failed", "uncertain"} for item in validated["results"]
                )
                if failure_count <= best_failure_count:
                    candidate = solved["coordinates"]
                    best_failure_count = failure_count
                if validated["success"]:
                    break
            if not solved.get("can_retry_anchors"):
                break

        if validated is None or not validated["success"]:
            errors = solved.get("errors") or []
            validated = self.geometry_validation_controller.validate_and_repair(
                coordinates=candidate, **validation_args,
                error_summary="\n".join([error_summary, *errors]),
            )

        success = validated["success"]
        return {
            "success": success,
            "stage": "validated" if success else "geometry_validation",
            "coordinates": validated["coordinates"],
            "coordinate_control": validated.get("coordinate_control") or controls,
            "solver_result": {**solved, "solve_attempts": solve_attempts},
            "validation_result": validated,
            "message": validated["message"],
        }
