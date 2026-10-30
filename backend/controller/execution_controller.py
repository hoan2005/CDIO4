
from copy import deepcopy
from typing import Any, Callable

from math_engine.draw import draw_3D,draw_2D_3D,draw_2D


class ExecutionController:
    """
    Điều phối thực thi kế hoạch do Orchestrator sinh ra.

    Nhiệm vụ:
    - Kiểm tra plan.
    - Sắp xếp task theo dependency.
    - Gọi Drawing Engine / Math Engine.
    - Cập nhật State thông qua StateManager.
    - Trả về canvas.add / update / remove.
    """

    def __init__(self, state_manager, drawing_handlers=None, math_handlers=None):
        self.state_manager = state_manager
        # Không dùng mutable default; cho phép inject handlers để test và mở rộng.
        self.drawing_handlers = drawing_handlers if drawing_handlers is not None else {
            "draw_cube": draw_3D.draw_cube,
            "draw_pyramid": draw_3D.draw_pyramid,
            "draw_line": draw_2D_3D.draw_line,
            "draw_point": draw_2D_3D.draw_point,
            "draw_polygon_2d": draw_2D.draw_polygon_2d,
            "draw_ellipse": draw_2D.draw_ellipse,
            "draw_circle": draw_2D.draw_circle,
            "draw_prism": draw_3D.draw_prism,
            "draw_sphere": draw_3D.draw_sphere,
            "draw_cone": draw_3D.draw_cone,
            "draw_plane": draw_2D_3D.draw_plane,
            "draw_hyperbola": draw_2D.draw_hyperbola,
            "draw_function": draw_2D.draw_function,
            "draw_line_plane": draw_2D_3D.draw_plane,
        }
        # Bugfix: math_handlers phải là tham số riêng, không được lấy drawing_handlers.
        self.math_handlers = math_handlers if math_handlers is not None else {}

    # ==================================================
    # 1. KIỂM TRA KẾ HOẠCH
    # ==================================================

    def validate_plan(self, plan: dict) -> None:
        if not isinstance(plan, dict):
            raise ValueError("Plan phải là dictionary.")

        tasks = plan.get("tasks")

        if not isinstance(tasks, list):
            raise ValueError("Plan phải có danh sách tasks.")

        task_ids = set()

        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Mỗi task phải là dictionary.")

            required_fields = [
                "id",
                "domain",
                "operation",
                "input",
            ]

            for field in required_fields:
                if field not in task:
                    raise ValueError(
                        f"Task thiếu trường {field}: {task}"
                    )

            task_id = task["id"]

            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("Task id không hợp lệ.")

            if task_id in task_ids:
                raise ValueError(
                    f"Task id bị trùng: {task_id}"
                )

            if not isinstance(task["input"], dict):
                raise ValueError(
                    f"Input của {task_id} phải là dictionary."
                )

            dependencies = task.get("depends_on", [])

            if not isinstance(dependencies, list):
                raise ValueError(
                    f"depends_on của {task_id} phải là list."
                )

            task_ids.add(task_id)

        # Kiểm tra dependency phải tham chiếu đến task tồn tại.
        for task in tasks:
            for dependency in task.get("depends_on", []):
                if dependency not in task_ids:
                    raise ValueError(
                        f"Task {task['id']} phụ thuộc vào "
                        f"task không tồn tại: {dependency}"
                    )

                if dependency == task["id"]:
                    raise ValueError(
                        f"Task không thể phụ thuộc chính nó: "
                        f"{dependency}"
                    )

    # ==================================================
    # 2. SẮP XẾP TASK THEO DEPENDENCY
    # ==================================================

    def sort_tasks(self, tasks: list) -> list:
        """
        Topological sort:
        task phụ thuộc task nào thì phải chạy sau task đó.
        """

        if not isinstance(tasks, list):
            raise ValueError("tasks phải là list.")
        task_map = {task["id"]: task for task in tasks}
        if len(task_map) != len(tasks):
            raise ValueError("Task id bị trùng.")

        completed = set()
        ordered = []

        while len(ordered) < len(tasks):
            found_task = False

            for task in tasks:
                task_id = task["id"]

                if task_id in completed:
                    continue

                dependencies = task.get("depends_on", [])

                if all(dep in completed for dep in dependencies):
                    ordered.append(task)
                    completed.add(task_id)
                    found_task = True

            if not found_task:
                raise ValueError(
                    "Dependency bị vòng lặp hoặc không thể sắp xếp."
                )

        return ordered

    # ==================================================
    # 3. CHỌN HÀM XỬ LÝ
    # ==================================================

    def execute_task(self, task: dict, state: dict) -> Any:
        operation = task["operation"]
        domain = task["domain"]
        task_input = task["input"]

        # UPDATE_OBJECT: cập nhật object hiện có, không gọi handler vẽ mới.
        # Tọa độ đã được validate/repair ở bước xử lý request trước khi run().
        if operation == "update_object":
            target_id = (
                task.get("object_id")
                or task_input.get("object_id")
                or task_input.get("target_id")
                or task_input.get("target_ref")
            )
            if not target_id:
                raise ValueError(
                    "update_object yêu cầu object_id, target_id hoặc target_ref."
                )

            current = (state.get("canvas_objects") or {}).get(target_id)
            if not isinstance(current, dict):
                raise ValueError(f"Không tìm thấy object để update: {target_id}")

            updated = deepcopy(current)
            # Tách metadata khỏi patch hiển thị, nhưng vẫn tiếp nhận metadata mới.
            incoming_controls = task_input.get("coordinate_control")
            if incoming_controls is not None and not isinstance(incoming_controls, dict):
                raise ValueError("coordinate_control của update_object phải là dict.")
            metadata_fields = {
                "object_id", "target_id", "target_ref",
                "coordinate_control", "constraints", "constructions",
            }
            patch = {
                key: deepcopy(value)
                for key, value in task_input.items()
                if key not in metadata_fields
            }

            # Hợp nhất tọa độ để các điểm không được yêu cầu sửa vẫn được giữ lại.
            if isinstance(patch.get("coordinates"), dict):
                old_coordinates = updated.get("coordinates")
                if not isinstance(old_coordinates, dict):
                    old_coordinates = {}
                merged_coordinates = {
                    **deepcopy(old_coordinates),
                    **deepcopy(patch["coordinates"]),
                }
                updated["coordinates"] = merged_coordinates
                patch.pop("coordinates", None)

                # Đồng bộ mảng points theo point_names (schema line/segment).
                # Nếu không cập nhật mảng này, Canvas có thể vẫn render tọa độ cũ.
                point_names = updated.get("point_names")
                old_points = updated.get("points")
                if (isinstance(point_names, (list, tuple))
                        and isinstance(old_points, list)
                        and len(point_names) == len(old_points)):
                    updated_points = deepcopy(old_points)
                    for index, point_name in enumerate(point_names):
                        if point_name in merged_coordinates:
                            updated_points[index] = list(merged_coordinates[point_name])
                    updated["points"] = updated_points

            updated.update(patch)

            # coordinate_control là map theo tên điểm; merge để không mất metadata cũ.
            if isinstance(incoming_controls, dict):
                old_controls = updated.get("coordinate_control")
                if not isinstance(old_controls, dict):
                    old_controls = {}
                merged_controls = deepcopy(old_controls)
                for point_name, control in incoming_controls.items():
                    if isinstance(control, dict) and isinstance(merged_controls.get(point_name), dict):
                        merged_controls[point_name] = {
                            **merged_controls[point_name], **deepcopy(control)
                        }
                    else:
                        merged_controls[point_name] = deepcopy(control)
                updated["coordinate_control"] = merged_controls

            # ID là định danh ổn định: không cho LLM đổi ID object.
            updated["id"] = target_id

            # Object điểm thường lưu vị trí ở `position`, trong khi validator
            # chuẩn hóa tọa độ thành `coordinates` theo tên điểm. Đồng bộ cả hai.
            if updated.get("kind") == "point":
                point_name = updated.get("label")
                if not point_name and target_id.startswith("point_"):
                    point_name = target_id[len("point_"):]
                coordinates = updated.get("coordinates") or {}
                if point_name in coordinates:
                    updated["position"] = list(coordinates[point_name])

            return {
                "operation": "update_object",
                "result": {"objects": [updated]},
            }

        # Xử lý xóa đối tượng.
        if operation == "remove_object":
            target_id = task.get("object_id")

            if not target_id:
                target_id = task_input.get("object_id")

            if not target_id:
                raise ValueError(
                    "remove_object yêu cầu target_id."
                )

            return {
                "operation": "remove_object",
                "target_id": target_id,
            }

        # Chọn nhóm hàm theo domain.
        if domain == "geometry":
            handlers = self.drawing_handlers
        elif domain in {
            "algebra",
            "calculus",
            "probability",
            "statistics",
            "linear_algebra",
            "discrete_math",
            "numerical_math",
        }:
            handlers = self.math_handlers
        else:
            raise ValueError(
                f"Domain chưa được hỗ trợ: {domain}"
            )

        handler = handlers.get(operation)

        if handler is None:
            raise ValueError(
                f"Chưa đăng ký handler cho operation: {operation}"
            )

        # Handler được đăng ký phải nhận input và state.
        result = handler(task_input, state)

        if result is None:
            raise ValueError(
                f"Handler {operation} trả về None."
            )

        if not isinstance(result, dict):
            raise ValueError(
                f"Handler {operation} phải trả về dictionary."
            )

        return {
            "operation": operation,
            "result": result,
        }

    # ==================================================
    # 4. KIỂM TRA VÀ GHI KẾT QUẢ VÀO STATE
    # ==================================================

    def commit_result(
        self,
        task: dict,
        execution_result: dict,
        state: dict,
        canvas_changes: dict,
    ) -> dict:
        """
        StateManager là nơi chịu trách nhiệm kiểm tra
        và thực hiện add / update / remove trên State.
        """

        operation = execution_result["operation"]

        # ---------- REMOVE ----------
        if operation == "remove_object":
            target_id = execution_result["target_id"]

            if target_id not in (state.get("canvas_objects") or {}):
                raise ValueError(
                    f"Không tìm thấy đối tượng: {target_id}"
                )

            # Hợp đồng API giả định:
            # remove_object(state, object_id) -> object đã xóa
            removed = self.state_manager.remove_object(
                state.get("conversation_id"), target_id
            )

            (state.get("canvas_objects") or {}).pop(target_id, None)
            canvas_changes["remove"].append(target_id)

            return {
                "task_id": task["id"],
                "status": "success",
                "operation": operation,
                "result": removed,
            }

        result = execution_result["result"]

        # Quy ước: hàm vẽ trả về object hoặc danh sách objects.
        # Ví dụ: {"id": "point_A", "kind": "point", ...}
        objects = result.get("objects")

        if objects is None:
            objects = [result]

        if not isinstance(objects, list) or not objects:
            raise ValueError(
                "Kết quả vẽ phải chứa object hoặc danh sách objects."
            )

        committed_objects = []

        for obj in objects:
            if not isinstance(obj, dict):
                raise ValueError("Canvas object phải là dictionary.")

            object_id = obj.get("id")

            if not isinstance(object_id, str) or not object_id:
                raise ValueError(
                    "Canvas object phải có id hợp lệ."
                )

            # UPDATE: đối tượng phải tồn tại.
            if operation == "update_object":
                if object_id not in (state.get("canvas_objects") or {}):
                    raise ValueError(
                        f"Không tìm thấy object để update: {object_id}"
                    )

                # Hợp đồng API giả định:
                # update_object(state, id, patch) -> object mới
                # coordinate_control trong snapshot được đánh chỉ mục theo tên điểm;
                # không truyền cả dictionary này vào control của riêng object.
                self.state_manager.update_object(
                    state.get("conversation_id"),
                    object_id,
                    obj,
                    obj.get("coordinate_control"),
                )

                state.setdefault("canvas_objects", {})[object_id] = deepcopy(obj)
                canvas_changes["update"].append(deepcopy(obj))
                committed_objects.append(deepcopy(obj))

            # ADD: không ghi đè ID đang tồn tại.
            else:
                if object_id in state["canvas_objects"]:
                    raise ValueError(
                        f"ID đã tồn tại: {object_id}"
                    )

                # Hợp đồng API giả định:
                # add_object(state, object) -> object đã thêm
                # Chỉ truyền control của object đang thêm, không truyền map toàn cục.
                self.state_manager.add_object(
                    state.get("conversation_id"), obj, obj.get("coordinate_control")
                )
                state.setdefault("canvas_objects", {})[object_id] = deepcopy(obj)
                canvas_changes["add"].append(deepcopy(obj))
                committed_objects.append(deepcopy(obj))

        return {
            "task_id": task["id"],
            "status": "success",
            "operation": operation,
            "result": committed_objects,
        }

    # ==================================================
    # 5. HÀM ĐIỀU PHỐI CHÍNH
    # ==================================================

    def run(self, plan: dict, state: dict) -> dict:
        """
        Hàm entry point được gọi sau Orchestrator.
        """

        state.setdefault("canvas_objects", {})
        canvas_changes = {
            "add": [],
            "update": [],
            "remove": [],
        }

        task_results = []
        errors = []

        # Bước 1: kiểm tra toàn bộ plan và metadata validation trước khi thực thi.
        # xuly_chatbot gắn _validation sau khi kiểm tra tổng hợp toàn request.
        # Nếu metadata cho biết có constraint chưa đạt, tuyệt đối không vẽ task nào.
        try:
            self.validate_plan(plan)
            ordered_tasks = self.sort_tasks(plan["tasks"])
            for task in ordered_tasks:
                validation_items = task.get("_validation", [])
                if not isinstance(validation_items, list):
                    raise ValueError(f"_validation của task {task['id']} phải là list.")
                for item in validation_items:
                    if not isinstance(item, dict):
                        raise ValueError(f"_validation của task {task['id']} chứa phần tử không hợp lệ.")
                    if item.get("status") not in {"verified", "llm_supported"}:
                        raise ValueError(
                            f"Task {task['id']} có constraint chưa được xác minh: "
                            f"{item.get('status', 'unknown')}"
                        )
        except (ValueError, TypeError, KeyError) as exc:
            return {
                "success": False,
                "results": [],
                "canvas": canvas_changes,
                "errors": [str(exc)],
                "state_revision": state.get("revision", 0),
            }

        # Theo dõi task đã thành công/thất bại.
        status = {}

        # Bước 2: thực thi lần lượt.
        for task in ordered_tasks:
            task_id = task["id"]
            dependencies = task.get("depends_on", [])

            # Không chạy task nếu dependency thất bại.
            failed_dependencies = [
                dep for dep in dependencies
                if status.get(dep) != "success"
            ]

            if failed_dependencies:
                status[task_id] = "skipped"

                task_results.append({
                    "task_id": task_id,
                    "status": "skipped",
                    "reason": (
                        "Dependency thất bại: "
                        + ", ".join(failed_dependencies)
                    ),
                })
                continue

            try:
                execution_result = self.execute_task(task, state)

                task_result = self.commit_result(
                    task,
                    execution_result,
                    state,
                    canvas_changes,
                )

                status[task_id] = "success"
                task_results.append(task_result)

            except Exception as exc:
                status[task_id] = "failed"

                errors.append({
                    "task_id": task_id,
                    "error": str(exc),
                })

                task_results.append({
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(exc),
                })

        # Snapshot truyền vào run() là bản deepcopy; đọc lại revision thực tế
        # sau commit để trả về đúng trạng thái đã lưu.
        final_state = self.state_manager.get_state(state.get("conversation_id"))
        state.clear()
        state.update(deepcopy(final_state))

        return {
            "success": all(
                item["status"] == "success"
                for item in task_results
            ),
            "results": task_results,
            "canvas": canvas_changes,
            "errors": errors,
            "state_revision": final_state.get("revision", 0),
        }
