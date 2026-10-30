"""Chọn solver theo số chiều, chuẩn hóa dữ liệu và trả kết quả có chẩn đoán.

Flow khuyến nghị:
  LLM plan -> ConstructionSolver (điểm dựng khai báo) -> Controller này
  -> GeometryValidationController (xác minh lại) -> StateManager/Canvas.

Controller này KHÔNG ghi StateManager và KHÔNG tự kết luận bài toán đúng chỉ vì solver
trả success. Bắt buộc chạy GeometryValidationController trên nghiệm trước khi commit.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Dict, Mapping, Sequence

try:  # package import
    from .constraint_normalizer import ConstraintNormalizer, ConstraintNormalizationError
    from .plane_gcs_adapter import PlaneGCSAdapter
    from .py_slvs_adapter import PySlvsAdapter
    from .scipy_constraint_adapter import ScipyConstraintAdapter
except ImportError:  # standalone/module-root import
    from constraint_normalizer import ConstraintNormalizer, ConstraintNormalizationError
    from plane_gcs_adapter import PlaneGCSAdapter
    from py_slvs_adapter import PySlvsAdapter
    from scipy_constraint_adapter import ScipyConstraintAdapter


class CoordinateSolverController:
    def __init__(self, normalizer=None, plane_2d=None, solver_3d=None, fallback=None,
                 prefer_native: bool = False, add_gauge_anchors: bool = True):
        self.normalizer = normalizer or ConstraintNormalizer()
        self.plane_2d = plane_2d or PlaneGCSAdapter()
        self.solver_3d = solver_3d or PySlvsAdapter()
        self.fallback = fallback or ScipyConstraintAdapter()
        self.prefer_native = bool(prefer_native)
        self.add_gauge_anchors = bool(add_gauge_anchors)

    def solve(self, coordinates: Mapping[str, Sequence[float]], constraints: Sequence[Mapping[str, Any]],
              coordinate_control: Mapping[str, Mapping[str, Any]] | None = None,
              dimension: int | None = None) -> Dict[str, Any]:
        try:
            normalized = self.normalizer.normalize(
                constraints=constraints, coordinates=coordinates,
                coordinate_control=coordinate_control, dimension=dimension)
        except ConstraintNormalizationError as exc:
            return {"success": False, "status": "normalization_error", "solver": None,
                    "coordinates": deepcopy(dict(coordinates or {})), "errors": [str(exc)], "attempts": []}
        if not normalized["success"]:
            return {"success": False, "status": "invalid_constraints", "solver": None,
                    "coordinates": normalized["coordinates"], "errors": normalized["errors"], "attempts": []}
        if not normalized["constraints"]:
            return {"success": True, "status": "no_solver_constraints", "solver": "none",
                    "coordinates": normalized["coordinates"], "errors": [], "attempts": [],
                    "validation_only_constraints": deepcopy(normalized.get("validation_only_constraints", [])),
                    "diagnostics": {"note": "Không có constraint phù hợp để giải tọa độ; giữ nguyên candidate và chuyển toàn bộ constraint gốc sang bước kiểm định."}}
        if self.add_gauge_anchors:
            normalized = self.normalizer.add_minimal_anchors(normalized)

        native = self.plane_2d if normalized["dimension"] == 2 else self.solver_3d
        attempts = []
        if self.prefer_native:
            native_result = native.solve(normalized)
            attempts.append(self._public_attempt(native_result))
            if native_result.get("success"):
                return self._finalize(native_result, normalized, attempts)
            # Only use the numerical fallback when the native binding is absent or
            # cannot represent this constraint set. Do not mask native solve failures.
            if native_result.get("status") not in {"dependency_missing", "unsupported_constraints", "api_mismatch"}:
                return self._failure_from(native_result, normalized, attempts)

        fallback_result = self.fallback.solve(normalized)
        attempts.append(self._public_attempt(fallback_result))
        if fallback_result.get("success"):
            return self._finalize(fallback_result, normalized, attempts)
        return self._failure_from(fallback_result, normalized, attempts)

    @staticmethod
    def _public_attempt(result: Mapping[str, Any]) -> Dict[str, Any]:
        return {k: deepcopy(v) for k, v in result.items() if k not in {"coordinates"}}

    @staticmethod
    def _finalize(result: Mapping[str, Any], normalized: Mapping[str, Any], attempts: list) -> Dict[str, Any]:
        solved = result.get("coordinates")
        if not isinstance(solved, Mapping):
            return {"success": False, "status": "invalid_solver_output", "solver": result.get("solver"),
                    "coordinates": normalized["coordinates"], "errors": ["Solver không trả coordinates dạng object."],
                    "attempts": attempts}
        # Validate shape and finiteness before handing coordinates to the next stage.
        clean: Dict[str, list] = {}
        try:
            for name in normalized["coordinates"]:
                point = solved[name]
                if not isinstance(point, (list, tuple)) or len(point) != normalized["dimension"]:
                    raise ValueError(f"Tọa độ nghiệm của {name!r} sai số chiều")
                vals = [float(x) for x in point]
                if any(not __import__("math").isfinite(x) for x in vals):
                    raise ValueError(f"Tọa độ nghiệm của {name!r} không hữu hạn")
                clean[name] = vals
            # Hard anchors must remain exact within numerical tolerance.
            for name, original in normalized.get("hard_anchors", {}).items():
                if any(abs(a-b) > 1e-7 for a, b in zip(clean[name], original)):
                    raise ValueError(f"Solver làm thay đổi điểm bị khóa {name!r}")
        except Exception as exc:
            return {"success": False, "status": "invalid_solver_output", "solver": result.get("solver"),
                    "coordinates": normalized["coordinates"], "errors": [str(exc)], "attempts": attempts}
        return {"success": True, "status": "solved", "solver": result.get("solver"),
                "coordinates": clean, "errors": [], "attempts": attempts,
                "diagnostics": deepcopy(result.get("diagnostics", {})),
                "validation_only_constraints": deepcopy(normalized.get("validation_only_constraints", [])),
                "max_residual": result.get("max_residual"),
                "normalization": {"dimension": normalized["dimension"],
                                  "hard_anchor_names": list(normalized.get("hard_anchors", {})),
                                  "gauge_anchor_names": list(normalized.get("gauge_anchors", {})),
                                  "constraint_count": len(normalized.get("constraints", []))}}

    @staticmethod
    def _failure_from(result: Mapping[str, Any], normalized: Mapping[str, Any], attempts: list) -> Dict[str, Any]:
        return {"success": False, "status": result.get("status", "solver_failed"),
                "solver": result.get("solver"), "coordinates": normalized["coordinates"],
                "errors": list(result.get("errors") or [result.get("message", "Không giải được hệ constraint.")]),
                "attempts": attempts, "diagnostics": deepcopy(result.get("diagnostics", {}))}
