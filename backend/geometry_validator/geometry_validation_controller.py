"""Điều phối kiểm tra constraint, LLM fallback và sửa tọa độ ứng viên.

Luồng:
1. ConstraintDispatcher ưu tiên validator Python; constraint chưa hỗ trợ có thể được
   chuyển sang LLM theo cách triển khai của dispatcher.
2. Nếu có constraint thất bại, gọi CoordinateRepair.
3. Chuẩn hóa và kiểm tra tọa độ/control do repair đề xuất.
4. Hợp nhất ứng viên rồi kiểm tra lại TOÀN BỘ constraints.
5. Không ghi StateManager; caller chỉ commit khi success=True.

Lưu ý:
- llm_supported là kết quả đánh giá của LLM, không tương đương Python verified.
- Nếu planner bỏ sót constraint, controller không thể tự suy ra đầy đủ yêu cầu hình học.
"""

from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any

from geometry_validator.constraint_dispatcher import ConstraintDispatcher
from geometry_validator.coordinate_repair import CoordinateRepair


class GeometryValidationController:
    def __init__(
        self,
        dispatcher: ConstraintDispatcher | None = None,
        repairer: CoordinateRepair | None = None,
        max_repair_attempts: int = 3,
        *,
        allow_llm_supported: bool = True,
    ):
        self.dispatcher = dispatcher or ConstraintDispatcher()
        self.repairer = repairer or CoordinateRepair()
        self.max_repair_attempts = max(0, int(max_repair_attempts))
        self.allow_llm_supported = bool(allow_llm_supported)

    def validate_and_repair(
        self,
        coordinates: dict[str, list[float]],
        constraints: list[dict[str, Any]],
        coordinate_control: dict[str, dict[str, Any]] | None = None,
        *,
        error_summary: str | None = None,
        state_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Kiểm tra candidate và sửa tọa độ, không cập nhật StateManager."""

        input_error = self._validate_input(coordinates, constraints)
        if input_error:
            return self._failure(
                coordinates, [], coordinate_control or {}, input_error
            )

        # Chuẩn hóa tên điểm và ép tọa độ thành số ngay từ đầu.
        candidate = self._normalize_coordinates(coordinates)
        if isinstance(candidate, str):
            return self._failure(
                coordinates, [], coordinate_control or {}, candidate
            )

        controls, control_error = self._normalize_controls(
            coordinate_control or {}, known_points=set(candidate)
        )
        if control_error:
            return self._failure(
                coordinates, [], controls, control_error
            )

        original = deepcopy(candidate)
        constraints_working = deepcopy(constraints)
        repair_history: list[dict[str, Any]] = []

        if not constraints_working:
            return {
                "success": True,
                "coordinates": candidate,
                "constraints": [],
                "coordinate_control": controls,
                "results": [],
                "attempts": 0,
                "repair_history": [],
                "message": "Không có constraint cần kiểm tra.",
                "validation_level": "not_required",
            }

        for attempt in range(self.max_repair_attempts + 1):
            # Luôn kiểm tra toàn bộ constraints trên candidate hiện tại.
            try:
                results = self.dispatcher.validate_many(
                    constraints_working, candidate
                )
            except Exception as exc:
                return self._failure(
                    original,
                    [],
                    controls,
                    f"ConstraintDispatcher gặp lỗi: {exc}",
                    constraints=constraints_working,
                    attempts=attempt,
                    repair_history=repair_history,
                )

            if not isinstance(results, list):
                return self._failure(
                    original,
                    [],
                    controls,
                    "ConstraintDispatcher.validate_many phải trả về list.",
                    constraints=constraints_working,
                    attempts=attempt,
                    repair_history=repair_history,
                )

            failed = [
                r for r in results
                if isinstance(r, dict) and r.get("status") == "failed"
            ]
            unsupported = [
                r for r in results
                if isinstance(r, dict) and r.get("status") == "unsupported"
            ]
            uncertain = [
                r for r in results
                if isinstance(r, dict) and r.get("status") == "uncertain"
            ]
            llm_supported = [
                r for r in results
                if isinstance(r, dict) and r.get("status") == "llm_supported"
            ]
            invalid_results = [
                r for r in results if not isinstance(r, dict)
            ]

            if invalid_results:
                return self._failure(
                    original,
                    results,
                    controls,
                    "Validator trả về kết quả không đúng định dạng dict.",
                    constraints=constraints_working,
                    attempts=attempt,
                    repair_history=repair_history,
                )

            blocking = bool(failed or unsupported or uncertain)
            llm_is_allowed = self.allow_llm_supported or not llm_supported

            if not blocking and llm_is_allowed:
                has_llm = bool(llm_supported)
                return {
                    "success": True,
                    "coordinates": deepcopy(candidate),
                    "constraints": deepcopy(constraints_working),
                    "coordinate_control": deepcopy(controls),
                    "results": deepcopy(results),
                    "attempts": attempt,
                    "repair_history": deepcopy(repair_history),
                    "message": (
                        "Constraint đã được đánh giá; có constraint được LLM chấp nhận."
                        if has_llm
                        else "Tất cả constraint đã được Python xác minh."
                    ),
                    "validation_level": (
                        "mixed_llm" if has_llm else "python_verified"
                    ),
                }

            # Không sửa tọa độ chỉ vì constraint chưa được hỗ trợ hoặc chưa chắc chắn:
            # repair cần một constraint thất bại cụ thể để có mục tiêu sửa rõ ràng.
            # Nếu LLM-only bị cấm, cũng không tự động coi llm_supported là verified.
            if not failed:
                return self._failure(
                    original,
                    results,
                    controls,
                    self._summarize_blockers(
                        unsupported, uncertain, llm_supported,
                        allow_llm_supported=self.allow_llm_supported,
                    ),
                    constraints=constraints_working,
                    attempts=attempt,
                    repair_history=repair_history,
                    validation_level="incomplete",
                )

            if attempt >= self.max_repair_attempts:
                return self._failure(
                    original,
                    results,
                    controls,
                    "Đã đạt giới hạn sửa nhưng vẫn còn constraint thất bại.",
                    constraints=constraints_working,
                    attempts=attempt,
                    repair_history=repair_history,
                    validation_level="failed",
                )

            try:
                repair_result = self.repairer.repair(
                    coordinates=deepcopy(candidate),
                    failed_constraints=deepcopy(failed),
                    constraints=deepcopy(constraints_working),
                    coordinate_control=deepcopy(controls),
                    attempt=attempt + 1,
                    max_attempts=self.max_repair_attempts,
                    error_summary=(
                            "Kiểm tra tổng hợp tất cả constraints trong một request.\n"
    + self._summarize_failures(failed)
                    ),
                    state_context=deepcopy(state_context),
                )
            except Exception as exc:
                return self._failure(
                    original,
                    results,
                    controls,
                    f"CoordinateRepair gặp lỗi: {exc}",
                    constraints=constraints_working,
                    attempts=attempt + 1,
                    repair_history=repair_history,
                )

            repair_history.append({
                "attempt": attempt + 1,
                "failed_constraints": deepcopy(failed),
                "repair_result": deepcopy(repair_result),
            })

            if not isinstance(repair_result, dict) or not repair_result.get("success"):
                reason = (
                    repair_result.get("reason", "Không tạo được phương án sửa.")
                    if isinstance(repair_result, dict)
                    else "Repair provider trả về dữ liệu không hợp lệ."
                )
                return self._failure(
                    original,
                    results,
                    controls,
                    reason,
                    constraints=constraints_working,
                    attempts=attempt + 1,
                    repair_history=repair_history,
                )

            proposed_raw = repair_result.get("coordinates")
            if not isinstance(proposed_raw, dict) or not proposed_raw:
                return self._failure(
                    original,
                    results,
                    controls,
                    "Repair provider phải trả coordinates dạng dict không rỗng.",
                    constraints=constraints_working,
                    attempts=attempt + 1,
                    repair_history=repair_history,
                )

            proposed_coords, coord_error = self._normalize_proposed_coordinates(
                proposed_raw, candidate, controls
            )
            if coord_error:
                return self._failure(
                    original,
                    results,
                    controls,
                    coord_error,
                    constraints=constraints_working,
                    attempts=attempt + 1,
                    repair_history=repair_history,
                )

            # Chỉ cập nhật candidate sau khi toàn bộ đề xuất tọa độ hợp lệ.
            next_candidate = deepcopy(candidate)
            next_candidate.update(proposed_coords)

            control_update_raw = repair_result.get("coordinate_control")
            next_controls = deepcopy(controls)
            if control_update_raw is not None:
                if not isinstance(control_update_raw, dict):
                    return self._failure(
                        original,
                        results,
                        controls,
                        "coordinate_control từ repair phải là dict.",
                        constraints=constraints_working,
                        attempts=attempt + 1,
                        repair_history=repair_history,
                    )

                control_update, control_error = self._normalize_controls(
                    control_update_raw, known_points=set(candidate)
                )
                if control_error:
                    return self._failure(
                        original,
                        results,
                        controls,
                        control_error,
                        constraints=constraints_working,
                        attempts=attempt + 1,
                        repair_history=repair_history,
                    )

                lock_error = self._validate_control_update(
                    controls, control_update, set(candidate)
                )
                if lock_error:
                    return self._failure(
                        original,
                        results,
                        controls,
                        lock_error,
                        constraints=constraints_working,
                        attempts=attempt + 1,
                        repair_history=repair_history,
                    )
                next_controls.update(deepcopy(control_update))

            proposed_constraints = repair_result.get("constraints")
            next_constraints = constraints_working
            if proposed_constraints is not None:
                if not isinstance(proposed_constraints, list) or not all(
                    isinstance(item, dict) for item in proposed_constraints
                ):
                    return self._failure(
                        original,
                        results,
                        controls,
                        "constraints từ repair phải là list các dict.",
                        constraints=constraints_working,
                        attempts=attempt + 1,
                        repair_history=repair_history,
                    )
                next_constraints = self._merge_constraints(
                    constraints_working, proposed_constraints
                )

            candidate = next_candidate
            controls = next_controls
            constraints_working = next_constraints

        return self._failure(
            original,
            [],
            controls,
            "Validation kết thúc mà chưa đạt trạng thái hợp lệ.",
            constraints=constraints_working,
            attempts=self.max_repair_attempts,
            repair_history=repair_history,
        )

    @staticmethod
    def _normalize_point_name(name: Any) -> Any:
        """Chuẩn hóa point_A thành A; không sửa tên không phải chuỗi."""
        if isinstance(name, str) and name.startswith("point_"):
            return name[len("point_"):]
        return name

    @classmethod
    def _normalize_coordinates(
        cls, coordinates: dict[str, Any]
    ) -> dict[str, list[float]] | str:
        normalized: dict[str, list[float]] = {}
        for raw_name, values in coordinates.items():
            name = cls._normalize_point_name(raw_name)
            if not isinstance(name, str) or not name:
                return "Tên điểm phải là chuỗi không rỗng."
            if name in normalized:
                return f"Có nhiều khóa tọa độ cùng chuẩn hóa thành '{name}'."
            if not isinstance(values, (list, tuple)) or len(values) not in (2, 3):
                return f"Tọa độ '{raw_name}' phải có 2 hoặc 3 chiều."
            if any(isinstance(value, bool) for value in values):
                return f"Tọa độ '{raw_name}' không được chứa giá trị boolean."
            try:
                numeric = [float(value) for value in values]
            except (TypeError, ValueError):
                return f"Tọa độ '{raw_name}' chứa giá trị không phải số."
            if not all(isfinite(value) for value in numeric):
                return f"Tọa độ '{raw_name}' chứa NaN/Infinity."
            normalized[name] = numeric
        return normalized

    @classmethod
    def _normalize_controls(
        cls,
        raw_controls: dict[str, Any],
        *,
        known_points: set[str],
    ) -> tuple[dict[str, dict[str, Any]], str | None]:
        controls: dict[str, dict[str, Any]] = {}
        for raw_name, value in raw_controls.items():
            name = cls._normalize_point_name(raw_name)
            if name not in known_points:
                return controls, (
                    f"coordinate_control chứa điểm chưa tồn tại '{raw_name}'."
                )
            if not isinstance(value, dict):
                return controls, (
                    f"coordinate_control của '{raw_name}' phải là dict."
                )
            if "fixed" in value and not isinstance(value["fixed"], bool):
                return controls, f"coordinate_control.fixed của '{raw_name}' phải là boolean."
            if "editable" in value and not isinstance(value["editable"], bool):
                return controls, f"coordinate_control.editable của '{raw_name}' phải là boolean."
            if name in controls:
                return controls, (
                    f"Có nhiều control cùng chuẩn hóa thành '{name}'."
                )
            controls[name] = deepcopy(value)
        return controls, None

    @classmethod
    def _normalize_proposed_coordinates(
        cls,
        proposed: dict[str, Any],
        candidate: dict[str, list[float]],
        controls: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, list[float]], str | None]:
        normalized: dict[str, list[float]] = {}
        for raw_name, values in proposed.items():
            name = cls._normalize_point_name(raw_name)
            if name not in candidate:
                return {}, f"Repair provider đề xuất điểm chưa tồn tại '{raw_name}'."
            if name in normalized:
                return {}, (
                    f"Repair provider đề xuất trùng điểm '{name}' sau chuẩn hóa."
                )
            if cls._is_locked(controls.get(name, {})):
                return {}, (
                    f"Repair provider đề xuất thay đổi điểm bị khóa '{name}'."
                )
            if not isinstance(values, (list, tuple)) or len(values) != len(candidate[name]):
                return {}, (
                    f"Tọa độ '{name}' phải có đúng {len(candidate[name])} chiều."
                )
            if any(isinstance(value, bool) for value in values):
                return {}, f"Tọa độ '{name}' không được chứa giá trị boolean."
            try:
                numeric = [float(value) for value in values]
            except (TypeError, ValueError):
                return {}, f"Tọa độ '{name}' chứa giá trị không phải số."
            if not all(isfinite(value) for value in numeric):
                return {}, f"Tọa độ '{name}' chứa NaN/Infinity."
            normalized[name] = numeric
        return normalized, None

    @staticmethod
    def _validate_input(coordinates: Any, constraints: Any) -> str | None:
        if not isinstance(coordinates, dict):
            return "coordinates phải là dict dạng {tên_điểm: [x, y, z]}."
        if not coordinates:
            return "coordinates không được là dict rỗng."
        if not isinstance(constraints, list):
            return "constraints phải là list."
        for name, values in coordinates.items():
            if not isinstance(name, str) or not name:
                return "Tên điểm phải là chuỗi không rỗng."
            if not isinstance(values, (list, tuple)) or len(values) not in (2, 3):
                return f"Tọa độ '{name}' phải có 2 hoặc 3 chiều."
            if any(isinstance(value, bool) for value in values):
                return f"Tọa độ '{name}' không được chứa giá trị boolean."
            try:
                numeric = [float(value) for value in values]
            except (TypeError, ValueError):
                return f"Tọa độ '{name}' chứa giá trị không phải số."
            if not all(isfinite(value) for value in numeric):
                return f"Tọa độ '{name}' chứa NaN/Infinity."
        for index, constraint in enumerate(constraints):
            if not isinstance(constraint, dict):
                return f"Constraint tại vị trí {index} phải là dict."
            if not constraint.get("type"):
                return f"Constraint tại vị trí {index} thiếu trường 'type'."
        return None

    @staticmethod
    def _is_locked(control: dict[str, Any] | None) -> bool:
        control = control or {}
        source = str(control.get("origin_source", control.get("source", ""))).strip().lower()
        return (bool(control.get("fixed", False))
                or control.get("editable", True) is False
                or source == "user")

    @staticmethod
    def _failure(
        original: Any,
        results: list[dict[str, Any]],
        controls: dict[str, Any],
        message: str,
        *,
        constraints: list[dict[str, Any]] | None = None,
        attempts: int = 0,
        repair_history: list[dict[str, Any]] | None = None,
        validation_level: str = "failed",
    ) -> dict[str, Any]:
        return {
            "success": False,
            "coordinates": deepcopy(original) if isinstance(original, dict) else {},
            "constraints": deepcopy(constraints if constraints is not None else []),
            "coordinate_control": deepcopy(controls or {}),
            "results": deepcopy(results),
            "attempts": attempts,
            "repair_history": deepcopy(repair_history or []),
            "message": message,
            "validation_level": validation_level,
        }

    @staticmethod
    def _summarize_failures(failed: list[dict[str, Any]]) -> str:
        return "Các constraint thất bại: " + "; ".join(
            f"{item.get('constraint_type', item.get('type', 'unknown'))}: "
            f"{item.get('reason', 'không đạt')}"
            for item in failed
        )

    @staticmethod
    def _summarize_blockers(
        unsupported: list[dict[str, Any]],
        uncertain: list[dict[str, Any]],
        llm_supported: list[dict[str, Any]],
        *,
        allow_llm_supported: bool,
    ) -> str:
        messages = []
        if unsupported:
            messages.append(
                f"{len(unsupported)} constraint chưa được xác minh "
                "(không có validator phù hợp hoặc chưa có kết quả LLM hợp lệ)."
            )
        if uncertain:
            messages.append(
                f"{len(uncertain)} constraint có kết quả không chắc chắn."
            )
        if llm_supported and not allow_llm_supported:
            messages.append(
                f"{len(llm_supported)} constraint chỉ được LLM đánh giá; "
                "allow_llm_supported=False nên không được tự động chấp nhận."
            )
        return " ".join(messages) or "Không thể xác minh đầy đủ các constraint."

    @classmethod
    def _validate_control_update(
        cls,
        current: dict[str, dict[str, Any]],
        proposed: dict[str, dict[str, Any]],
        known_points: set[str],
    ) -> str | None:
        for name, new_control in proposed.items():
            if name not in known_points:
                return f"coordinate_control chứa điểm chưa tồn tại '{name}'."
            if not isinstance(new_control, dict):
                return f"coordinate_control của '{name}' phải là dict."
            old_locked = cls._is_locked(current.get(name, {}))
            new_locked = cls._is_locked(new_control)
            if old_locked and not new_locked:
                return (
                    f"Không được gỡ khóa chỉnh sửa của điểm '{name}' "
                    "trong quá trình repair."
                )
        return None

    @staticmethod
    def _merge_constraints(
        existing: list[dict[str, Any]],
        proposed: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Hợp nhất constraints; không âm thầm xóa constraint đã có."""
        import json

        merged = deepcopy(existing)
        positions: dict[str, int] = {}

        def key_for(item: dict[str, Any]) -> str:
            if item.get("id") is not None:
                return f"id:{item['id']}"
            return "body:" + json.dumps(
                item, sort_keys=True, ensure_ascii=False, default=str
            )

        for index, item in enumerate(merged):
            if isinstance(item, dict):
                positions[key_for(item)] = index

        for item in proposed:
            if not isinstance(item, dict):
                continue
            key = key_for(item)
            if key in positions:
                merged[positions[key]] = deepcopy(item)
            else:
                positions[key] = len(merged)
                merged.append(deepcopy(item))
        return merged
