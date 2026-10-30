"""
coordinate_repair.py

Tạo tọa độ ứng viên mới sau khi validator phát hiện constraint thất bại.

Thiết kế:
- Không cập nhật StateManager.
- Không sửa điểm fixed=True hoặc editable=False.
- Mặc định gọi repair_provider (ví dụ hàm gọi lại Orchestrator/LLM).
- Nếu không có provider, trả thất bại rõ ràng thay vì tự đoán rằng đã sửa đúng.

repair_provider nhận một dict context và phải trả về một trong các dạng:
    {"success": True, "coordinates": {"S": [0, 0, 5]}, "coordinate_control": {...}, "constraints": [...]}
hoặc {"success": False, "reason": "..."}.

Trong kết quả coordinates, chỉ nên trả các điểm cần thay đổi. Tọa độ cuối cùng
vẫn phải được kiểm tra lại bởi GeometryValidationController.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Callable


RepairProvider = Callable[[dict[str, Any]], dict[str, Any]]


class CoordinateRepair:
    def __init__(self, repair_provider: RepairProvider | None = None):
        self.repair_provider = repair_provider

    @staticmethod
    def _is_locked(control: dict[str, Any] | None) -> bool:
        control = control or {}
        source = str(control.get("origin_source", control.get("source", ""))).strip().lower()
        return (bool(control.get("fixed", False))
                or control.get("editable", True) is False
                or source == "user")

    @staticmethod
    def _failed_constraints(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            item for item in results
            if item.get("status") == "failed"
        ]

    def repair(
        self,
        coordinates: dict[str, list[float]],
        failed_constraints: list[dict[str, Any]],
        constraints: list[dict[str, Any]],
        coordinate_control: dict[str, dict[str, Any]],
        attempt: int,
        max_attempts: int = 3,
        error_summary: str | None = None,
        state_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if attempt > max_attempts:
            return {
                "success": False,
                "reason": f"Đã vượt quá số lần sửa tối đa ({max_attempts})."
            }
        if not failed_constraints:
            return {
                "success": False,
                "reason": "Không có constraint thất bại để sửa."
            }
        if self.repair_provider is None:
            return {
                "success": False,
                "reason": (
                    "Chưa cấu hình repair_provider. Hãy truyền callback gọi lại "
                    "Orchestrator hoặc một bộ giải hình học Python."
                )
            }

        # Controls sometimes arrive as point_A while coordinates use A; normalize once
        # so locked/editable checks use the same keys as the aggregate coordinate pool.
        normalized_controls = {
            (name.removeprefix("point_") if isinstance(name, str) else name): control
            for name, control in (coordinate_control or {}).items()
            if isinstance(control, dict)
        }
        locked_points = [
            name for name, control in normalized_controls.items()
            if self._is_locked(control)
        ]
        editable_points = [
            name for name in coordinates
            if not self._is_locked(normalized_controls.get(name))
        ]

        # Lấy danh sách điểm liên quan từ failed constraints để hướng dẫn provider.
        related_points = self._extract_related_points(failed_constraints)
        related_editable = [name for name in related_points if name in editable_points]

        if not related_editable:
            return {
                "success": False,
                "reason": (
                    "Không có điểm nào liên quan đến constraint thất bại được phép sửa. "
                    "Không được tự ý thay đổi các điểm fixed hoặc non-editable."
                ),
                "locked_points": locked_points,
                "failed_constraints": deepcopy(failed_constraints),
            }

        context = {
            "mode": "repair",
            "attempt": attempt,
            "max_attempts": max_attempts,
            "current_coordinates": deepcopy(coordinates),
            "failed_constraints": deepcopy(failed_constraints),
            "constraints": deepcopy(constraints),
            "coordinate_control": deepcopy(normalized_controls),
            "locked_points": locked_points,
            "editable_points": editable_points,
            "related_points": related_points,
            "related_editable_points": related_editable,
            "error_summary": error_summary or "",
            "state_context": deepcopy(state_context or {}),
            "instructions": [
                "Chỉ trả tọa độ mới cho các điểm được phép sửa.",
                "Không thay đổi điểm fixed=true hoặc editable=false.",
                "Không thay đổi điểm có origin_source='user' hoặc source='user': đây là dữ kiện đầu vào chính xác, dù UI vẫn cho phép người dùng kéo điểm sau khi vẽ.",
                "Cố gắng thỏa mãn tất cả constraint thất bại và constraint liên quan.",
                "Không tuyên bố đã xác minh; controller sẽ kiểm tra lại.",
                "Không trả NaN, Infinity hoặc biểu thức thay cho số JSON.",
            ],
        }

        try:
            proposal = self.repair_provider(context)
        except Exception as exc:
            return {
                "success": False,
                "reason": f"repair_provider gặp lỗi: {type(exc).__name__}: {exc}"
            }

        if not isinstance(proposal, dict):
            return {
                "success": False,
                "reason": "repair_provider phải trả về dict."
            }
        if not proposal.get("success", False):
            return {
                "success": False,
                "reason": proposal.get("reason", "Provider không tìm được phương án sửa."),
                "provider_result": proposal,
            }

        new_coords = proposal.get("coordinates")
        if not isinstance(new_coords, dict) or not new_coords:
            return {
                "success": False,
                "reason": "Phương án sửa phải có dict coordinates không rỗng."
            }

        # Chặn provider thay đổi điểm bị khóa.
        for name in new_coords:
            control = normalized_controls.get(name)
            if self._is_locked(control):
                return {
                    "success": False,
                    "reason": f"Provider đề xuất sửa điểm bị khóa '{name}'.",
                    "locked_point": name,
                }
            if name not in coordinates:
                return {
                    "success": False,
                    "reason": f"Provider đề xuất sửa điểm chưa tồn tại '{name}'.",
                    "unknown_point": name,
                }

        # Validate shape / numeric finite values before handing candidate to controller.
        cleaned: dict[str, list[float]] = {}
        try:
            for name, values in new_coords.items():
                if not isinstance(values, (list, tuple)) or len(values) < 2:
                    raise ValueError(f"Tọa độ '{name}' phải là list có ít nhất 2 chiều.")
                numeric = [float(v) for v in values]
                if not all(isfinite(v) for v in numeric):
                    raise ValueError(f"Tọa độ '{name}' chứa NaN/Infinity.")
                if len(numeric) != len(coordinates[name]):
                    raise ValueError(
                        f"Tọa độ '{name}' có {len(numeric)} chiều, "
                        f"trong khi tọa độ hiện tại có {len(coordinates[name])} chiều."
                    )
                cleaned[name] = numeric
        except (TypeError, ValueError) as exc:
            return {"success": False, "reason": str(exc)}

        return {
            "success": True,
            "coordinates": cleaned,
            "coordinate_control": proposal.get("coordinate_control"),
            "constraints": proposal.get("constraints"),
            "notes": proposal.get("notes", []),
            "reason": proposal.get("reason", "Đã tạo phương án tọa độ ứng viên."),
        }

    @staticmethod
    def _extract_related_points(constraints: list[dict[str, Any]]) -> list[str]:
        found: list[str] = []

        def add(value: Any):
            if isinstance(value, str):
                value = value.removeprefix("point_")
                if value not in found:
                    found.append(value)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    add(item)

        fields = (
            "points", "line", "line_1", "line_2", "plane", "plane_1", "plane_2",
            "segment", "segment_1", "segment_2", "point", "right_angle_at", "apex",
            "tangent_at", "circle", "center", "center_point", "center_name",
            "point_on_circle", "point_on_circumference", "radius_point", "vertex"
        )
        for constraint in constraints:
            if not isinstance(constraint, dict):
                continue
            # Validation results wrap the original constraint under "constraint".
            # Unwrap it so points from failed Python/LLM checks are discoverable.
            source = constraint.get("constraint")
            if isinstance(source, dict):
                constraint = source
            for field in fields:
                if field in constraint:
                    add(constraint[field])
        return found
