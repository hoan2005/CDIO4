
# backend/state/state_manager.py

from copy import deepcopy
from threading import RLock
from typing import Any, Dict, List, Optional


class StateManager:
    """
    Quản lý State riêng cho từng conversation.

    - canvas_objects: các đối tượng hiện có trên Canvas.
    - coordinate_control: thông tin tọa độ cố định / được phép thay đổi.
    - constraints: trạng thái kiểm tra các ràng buộc hình học.
    - tasks: danh sách task của lượt xử lý hiện tại.
    """

    def __init__(self):
        self._states: Dict[str, dict] = {}
        self._lock = RLock()

    # ==================================================
    # 1. TẠO STATE
    # ==================================================

    def create_initial_state(self, conversation_id: str ="") -> dict:
        return {
            "conversation_id": conversation_id,
            "summary": "",
            "recent_turns": [],
            "canvas_objects": {},
            "coordinate_control": {},
            "constraints": {},
            "tasks": [],
            "focus_id": None,
            "revision": 0,
        }

    def get_state(self, conversation_id: str) -> dict:
        """
        Lấy bản sao State để đọc dữ liệu.
        Không trả trực tiếp dictionary nội bộ để tránh bị sửa ngoài ý muốn.
        """
        if not conversation_id:
            raise ValueError("conversation_id không được để trống")

        with self._lock:
            if conversation_id not in self._states:
                self._states[conversation_id] = (
                    self.create_initial_state(conversation_id)
                )

            return deepcopy(self._states[conversation_id])

    def _get_internal_state(self, conversation_id: str) -> dict:
        """Chỉ gọi bên trong StateManager."""
        if conversation_id not in self._states:
            self._states[conversation_id] = (
                self.create_initial_state(conversation_id)
            )

        return self._states[conversation_id]

    def _increase_revision(self, state: dict) -> None:
        state["revision"] += 1

    # ==================================================
    # 2. QUẢN LÝ CANVAS OBJECTS
    # ==================================================

    @staticmethod
    def _merge_nested_dict(current: Optional[dict], incoming: Optional[dict]) -> dict:
        """Merge dict metadata without discarding keys already stored."""
        result = deepcopy(current) if isinstance(current, dict) else {}
        if isinstance(incoming, dict):
            for key, value in incoming.items():
                if isinstance(value, dict) and isinstance(result.get(key), dict):
                    result[key] = {**result[key], **deepcopy(value)}
                else:
                    result[key] = deepcopy(value)
        return result

    @staticmethod
    def _extract_object_control(obj: dict, coordinate_control: Optional[dict]) -> dict:
        """Return per-point controls for this object, never a global control map."""
        embedded = obj.get("coordinate_control")
        supplied = coordinate_control
        if isinstance(embedded, dict) and isinstance(supplied, dict):
            return StateManager._merge_nested_dict(embedded, supplied)
        if isinstance(supplied, dict):
            return deepcopy(supplied)
        if isinstance(embedded, dict):
            return deepcopy(embedded)
        return {}

    def add_object(
        self,
        conversation_id: str,
        obj: dict,
        coordinate_control: Optional[dict] = None,
    ) -> None:
        """Thêm object và đồng bộ metadata coordinate_control theo tên điểm.

        `coordinate_control` ở đây là map theo tên điểm, ví dụ
        {"A": {"source": "llm", "fixed": False, "editable": True}},
        không phải map toàn cục dạng {object_id: {...}}.
        """
        if not isinstance(obj, dict):
            raise TypeError("obj phải là dictionary")

        object_id = obj.get("id")
        if not isinstance(object_id, str) or not object_id.strip():
            raise ValueError("Object phải có id hợp lệ")
        if not conversation_id:
            raise ValueError("conversation_id không được để trống")

        with self._lock:
            state = self._get_internal_state(conversation_id)
            if object_id in state["canvas_objects"]:
                raise ValueError(f"Object '{object_id}' đã tồn tại")

            stored = deepcopy(obj)
            controls = self._extract_object_control(stored, coordinate_control)
            if controls:
                stored["coordinate_control"] = deepcopy(controls)
                state["coordinate_control"].update(deepcopy(controls))

            state["canvas_objects"][object_id] = stored
            self._increase_revision(state)

    def update_object(
        self,
        conversation_id: str,
        object_id: str,
        updates: dict,
        coordinate_control: Optional[dict] = None,
    ) -> None:
        """Cập nhật object; merge các map tọa độ/control thay vì ghi đè mất dữ liệu."""
        if not isinstance(updates, dict):
            raise TypeError("updates phải là dictionary")
        if "id" in updates and updates["id"] != object_id:
            raise ValueError("Không được thay đổi id của object")
        if not conversation_id:
            raise ValueError("conversation_id không được để trống")

        with self._lock:
            state = self._get_internal_state(conversation_id)
            current = state["canvas_objects"].get(object_id)
            if current is None:
                raise KeyError(f"Không tìm thấy object '{object_id}'")

            patch = deepcopy(updates)
            incoming_controls = coordinate_control
            if incoming_controls is None:
                incoming_controls = patch.get("coordinate_control")

            # Nested maps cần merge để update một vài điểm không làm mất điểm khác.
            for field in ("coordinates", "coordinate_control"):
                if isinstance(patch.get(field), dict):
                    patch[field] = self._merge_nested_dict(current.get(field), patch[field])

            current.update(patch)
            controls = self._extract_object_control(current, incoming_controls)
            if controls:
                current["coordinate_control"] = deepcopy(controls)
                state["coordinate_control"].update(deepcopy(controls))

            self._increase_revision(state)
            self._invalidate_constraints(state, {object_id})

    def remove_object(
        self,
        conversation_id: str,
        object_id: str,
    ) -> dict:
        """
        Xóa object khỏi State và trả về object đã xóa.
        """
        with self._lock:
            state = self._get_internal_state(conversation_id)

            if object_id not in state["canvas_objects"]:
                raise KeyError(f"Không tìm thấy object '{object_id}'")

            removed = state["canvas_objects"].pop(object_id)

            # Dọn control theo tên điểm thuộc object vừa xóa, nhưng giữ lại
            # control nếu điểm đó vẫn còn được object khác sử dụng.
            removed_names = set()
            point_names = removed.get("point_names")
            if isinstance(point_names, (list, tuple)):
                removed_names.update(str(name) for name in point_names)
            coordinates = removed.get("coordinates")
            if isinstance(coordinates, dict):
                removed_names.update(str(name) for name in coordinates)
            if removed.get("kind") == "point" and removed.get("label"):
                removed_names.add(str(removed["label"]))
            embedded_controls = removed.get("coordinate_control")
            if isinstance(embedded_controls, dict):
                removed_names.update(str(name) for name in embedded_controls)

            still_used = set()
            for other in state["canvas_objects"].values():
                names = other.get("point_names")
                if isinstance(names, (list, tuple)):
                    still_used.update(str(name) for name in names)
                coords = other.get("coordinates")
                if isinstance(coords, dict):
                    still_used.update(str(name) for name in coords)
                if other.get("kind") == "point" and other.get("label"):
                    still_used.add(str(other["label"]))
                controls = other.get("coordinate_control")
                if isinstance(controls, dict):
                    still_used.update(str(name) for name in controls)

            for point_name in removed_names - still_used:
                state["coordinate_control"].pop(point_name, None)
            state["coordinate_control"].pop(object_id, None)

            # Các constraint tham chiếu đến object đã xóa không còn
            # được coi là đã xác minh trên hình hiện tại.
            self._invalidate_constraints(state, {object_id})

            if state["focus_id"] == object_id:
                state["focus_id"] = None

            self._increase_revision(state)

            return deepcopy(removed)

    def get_object(
        self,
        conversation_id: str,
        object_id: str,
    ) -> Optional[dict]:
        state = self.get_state(conversation_id)
        obj = state["canvas_objects"].get(object_id)
        return deepcopy(obj) if obj is not None else None

    # ==================================================
    # 3. QUẢN LÝ TỌA ĐỘ
    # ==================================================

    
    def set_coordinate_control(
        self,
        conversation_id: str,
        object_id: str,
        control: dict,
    ) -> None:
        """Lưu metadata quyền điều khiển cho một điểm.

        Tham số `object_id` được giữ tên cũ để tương thích API, nhưng trong
        pipeline hình học giá trị này thường là tên điểm (A, B, C...), không
        phải id của Canvas object. Vì vậy không ép buộc nó phải tồn tại trong
        canvas_objects.
        """
        if not conversation_id:
            raise ValueError("conversation_id không được để trống")
        if not isinstance(object_id, str) or not object_id.strip():
            raise ValueError("Tên điểm/object không hợp lệ")
        if not isinstance(control, dict):
            raise TypeError("control phải là dict")

        with self._lock:
            state = self._get_internal_state(conversation_id)
            state["coordinate_control"][object_id] = self._merge_nested_dict(
                state["coordinate_control"].get(object_id), control
            )

            # Đồng bộ metadata nhúng trong những object có chứa điểm này.
            for obj in state["canvas_objects"].values():
                names = set()
                point_names = obj.get("point_names")
                if isinstance(point_names, (list, tuple)):
                    names.update(str(name) for name in point_names)
                coordinates = obj.get("coordinates")
                if isinstance(coordinates, dict):
                    names.update(str(name) for name in coordinates)
                label = obj.get("label")
                if label:
                    names.add(str(label))
                if object_id in names:
                    obj_controls = obj.setdefault("coordinate_control", {})
                    obj_controls[object_id] = self._merge_nested_dict(
                        obj_controls.get(object_id), control
                    )

            self._increase_revision(state)

    # ==================================================
    # 4. QUẢN LÝ CONSTRAINTS
    # ==================================================

    def set_constraint(
        self,
        conversation_id: str,
        constraint_id: str,
        constraint: dict,
    ) -> None:
        """
        Ví dụ:
        {
            "type": "perpendicular_lines",
            "object_ids": ["line_AB", "line_SC"],
            "status": "pending",
            "method": None,
            "checked_revision": None
        }
        """
        if not constraint_id:
            raise ValueError("constraint_id không được để trống")

        with self._lock:
            state = self._get_internal_state(conversation_id)

            item = deepcopy(constraint)
            item.setdefault("status", "pending")
            item.setdefault("method", None)
            item.setdefault("checked_revision", None)

            state["constraints"][constraint_id] = item

            self._increase_revision(state)

    def update_constraint(
        self,
        conversation_id: str,
        constraint_id: str,
        updates: dict,
    ) -> None:
        with self._lock:
            state = self._get_internal_state(conversation_id)

            if constraint_id not in state["constraints"]:
                raise KeyError(
                    f"Không tìm thấy constraint '{constraint_id}'"
                )

            state["constraints"][constraint_id].update(
                deepcopy(updates)
            )

            self._increase_revision(state)

    def _invalidate_constraints(
        self,
        state: dict,
        changed_object_ids: set,
    ) -> None:
        """
        Đánh dấu pending những constraint liên quan đến object thay đổi.

        Quy ước: mỗi constraint có trường object_ids là danh sách ID
        của những object mà constraint phụ thuộc vào.
        """
        for constraint in state["constraints"].values():
            related_ids = set(constraint.get("object_ids", []))

            if related_ids.intersection(changed_object_ids):
                constraint["status"] = "pending"
                constraint["method"] = None
                constraint["checked_revision"] = None

    # ==================================================
    # 5. QUẢN LÝ TASKS THEO TỪNG LƯỢT
    # ==================================================

    def start_turn(self, conversation_id: str) -> None:
        """Bắt đầu lượt xử lý mới, xóa danh sách task của lượt trước."""
        with self._lock:
            state = self._get_internal_state(conversation_id)
            state["tasks"] = []
            self._increase_revision(state)

    def set_tasks(
        self,
        conversation_id: str,
        tasks: List[dict],
    ) -> None:
        with self._lock:
            state = self._get_internal_state(conversation_id)
            state["tasks"] = deepcopy(tasks)
            self._increase_revision(state)

    def update_task(
        self,
        conversation_id: str,
        task_id: str,
        updates: dict,
    ) -> None:
        with self._lock:
            state = self._get_internal_state(conversation_id)

            for task in state["tasks"]:
                if task.get("id") == task_id:
                    task.update(deepcopy(updates))
                    self._increase_revision(state)
                    return

            raise KeyError(f"Không tìm thấy task '{task_id}'")

    # ==================================================
    # 6. FOCUS OBJECT
    # ==================================================

    def set_focus(
        self,
        conversation_id: str,
        object_id: Optional[str],
    ) -> None:
        with self._lock:
            state = self._get_internal_state(conversation_id)

            if (
                object_id is not None
                and object_id not in state["canvas_objects"]
            ):
                raise KeyError(f"Không tìm thấy object '{object_id}'")

            state["focus_id"] = object_id
            self._increase_revision(state)

    # ==================================================
    # 7. LỊCH SỬ HỘI THOẠI
    # ==================================================

    def add_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        with self._lock:
            state = self._get_internal_state(conversation_id)

            state["recent_turns"].append({
                "user": user_message,
                "assistant": assistant_message,
            })

            # Giữ một số lượt gần nhất để State không tăng vô hạn.
            state["recent_turns"] = state["recent_turns"][-10:]

            self._increase_revision(state)

    def update_summary(
        self,
        conversation_id: str,
        summary: str,
    ) -> None:
        with self._lock:
            state = self._get_internal_state(conversation_id)
            state["summary"] = summary
            self._increase_revision(state)

    # ==================================================
    # 8. XÓA STATE CỦA MỘT CONVERSATION
    # ==================================================

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._lock:
            if conversation_id in self._states:
                del self._states[conversation_id]
                return True

            return False


# Dùng chung một StateManager trong backend.
# state_manager = StateManager()