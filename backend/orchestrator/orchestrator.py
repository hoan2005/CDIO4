"""Orchestrator: convert a user request and current state into an execution plan."""

from copy import deepcopy
import re
import unicodedata
from typing import Any, Dict, List, Optional

from .llm_client import LLMClient, LLMClientError
from .prompt import ORCHESTRATOR_SYSTEM_PROMPT, build_orchestrator_user_prompt


ALLOWED_OPERATIONS = {
    "answer",
    "draw_point",
    "draw_line",
    "draw_function",
    "draw_cube",
    "draw_prism",
    "draw_pyramid",
    "draw_line_plane",
    "draw_polygon_2d",
    "draw_polygon_3d",
    "draw_angle",
    "draw_equal_segments",
    "draw_ellipse",
    "draw_hyperbola",
    "draw_circle",
    "draw_sphere",
    "draw_cone",
    "draw_plane",
    "update_object",
    "remove_object",
    "clarify"
}

ALLOWED_DIMENSIONS = {"2d", "3d", None}
ALLOWED_PROBLEM_TYPES = {
    "geometry", "algebra", "calculus", "probability", "other", "ambiguous"
}
CANVAS_OPERATIONS = ALLOWED_OPERATIONS - {"answer", "clarify"}
ANSWER_REQUEST_PATTERN = re.compile(
    r"\b(?:tính|giải|chứng minh|tìm|xác định|rút gọn|tính toán|"
    r"bao nhiêu|giá trị|answer|solve|calculate|compute|prove|find)\b",
    re.IGNORECASE,
)


class PlanValidationError(ValueError):
    """Raised when the generated plan does not follow the expected contract."""


def _reference_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFD", value.casefold())
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    normalized = re.sub(r"[^a-z0-9']+", " ", normalized)
    ignored = {
        "diem", "duong", "thang", "doan", "hinh", "tam", "giac",
        "mat", "phang", "doi", "tuong", "vua", "ve", "moi", "tao",
    }
    return " ".join(word for word in normalized.split() if word not in ignored)


def _resolve_object_reference(reference: Any, message: str, state: Dict[str, Any]) -> tuple[str | None, list[str]]:
    objects = state.get("canvas_objects") or {}
    if not isinstance(objects, dict) or not objects:
        return None, []

    ref = reference if isinstance(reference, str) else ""
    raw_context = unicodedata.normalize("NFD", f"{ref} {message}".casefold())
    raw_context = "".join(char for char in raw_context if unicodedata.category(char) != "Mn")
    recent_pattern = r"\b(vua ve|moi ve|vua tao|moi tao|hinh nay|duong nay|diem nay|doi tuong nay|no|do|ay|it|that|this|last|previous)\b"
    latest_reference = re.search(recent_pattern, raw_context)
    focus_id = state.get("focus_id")
    focus_object = objects.get(focus_id)
    expected_kind = (
        "point" if re.search(r"\bdiem\b", raw_context)
        else "line" if re.search(r"\bduong\b", raw_context)
        else None
    )
    focus_is_valid = (
        isinstance(focus_object, dict)
        and (expected_kind is None or focus_object.get("kind") == expected_kind)
    )

    if ref in objects:
        return ref, []

    key = _reference_key(ref)

    kind_filter = None
    raw_ref = unicodedata.normalize("NFD", ref.casefold())
    raw_ref = "".join(char for char in raw_ref if unicodedata.category(char) != "Mn")
    explicit_recent_reference = re.search(recent_pattern, raw_ref)
    if re.search(r"\bduong tron\b", raw_ref):
        kind_filter = {"circle"}
    elif re.search(r"\bdiem\b", raw_ref):
        kind_filter = {"point"}
    elif re.search(r"\bduong\b", raw_ref):
        kind_filter = {"line"}
    elif re.search(r"\bmat phang\b", raw_ref):
        kind_filter = {"plane"}
    elif re.search(r"\btam giac\b|\bda giac\b", raw_ref):
        kind_filter = {"polygon"}

    matches = []
    if key:
        for object_id, obj in objects.items():
            if not isinstance(obj, dict):
                continue
            if kind_filter and obj.get("kind") not in kind_filter:
                continue
            aliases = [object_id, obj.get("id"), obj.get("label"), obj.get("name")]
            point_names = obj.get("point_names")
            if isinstance(point_names, (list, tuple)):
                aliases.append("".join(str(name) for name in point_names))
            vertices = obj.get("vertex_order") or obj.get("vertices")
            if isinstance(vertices, (list, tuple)):
                aliases.append("".join(str(name) for name in vertices))
            elif isinstance(vertices, dict):
                aliases.append("".join(str(name) for name in vertices))
            if any(_reference_key(alias) == key for alias in aliases if alias is not None):
                matches.append(object_id)
        if len(matches) == 1:
            return matches[0], []

    if latest_reference and focus_is_valid and (not key or explicit_recent_reference):
        return focus_id, []
    return None, matches


def resolve_plan_references(
    plan: Dict[str, Any],
    user_message: str,
    state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Resolve unambiguous update/delete targets; never guess between canvas objects."""
    state = state or {}
    updated = deepcopy(plan)
    unresolved = []
    for task in updated.get("tasks", []):
        if task.get("operation") not in {"update_object", "remove_object"}:
            continue
        task_input = task.setdefault("input", {})
        reference = (
            task.get("object_id")
            or task_input.get("object_id")
            or task_input.get("target_id")
            or task_input.get("target_ref")
            or updated.get("target_ref")
        )
        resolved, candidates = _resolve_object_reference(reference, user_message, state)
        if resolved:
            task["object_id"] = resolved
            task_input["object_id"] = resolved
        else:
            unresolved.append((reference, candidates))

    if unresolved:
        labels = []
        objects = state.get("canvas_objects") or {}
        for object_id, obj in objects.items():
            if isinstance(obj, dict):
                labels.append(f"{obj.get('label', obj.get('kind', 'đối tượng'))} ({object_id})")
        choices = ", ".join(labels[:8]) or "canvas hiện đang trống"
        updated["ambiguous"] = True
        updated["notes"] = [
            f"Mình chưa xác định chắc chắn đối tượng cần thao tác. Bạn muốn chọn đối tượng nào? Hiện có: {choices}."
        ]
        updated["tasks"] = [{
            "id": "clarify_target",
            "domain": "other",
            "operation": "clarify",
            "depends_on": [],
            "input": {},
        }]
    return updated


def ensure_answer_task(plan: Dict[str, Any], user_message: str) -> Dict[str, Any]:
    """Keep an explicit answer task when a visual request also asks for a solution."""
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        return plan
    has_canvas_task = any(
        isinstance(task, dict) and task.get("operation") in CANVAS_OPERATIONS
        for task in tasks
    )
    has_answer_task = any(
        isinstance(task, dict) and task.get("operation") == "answer"
        for task in tasks
    )
    if not has_canvas_task or has_answer_task or not ANSWER_REQUEST_PATTERN.search(user_message):
        return plan

    updated = dict(plan)
    updated_tasks = list(tasks)
    task_ids = {
        task.get("id") for task in updated_tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    task_id = "answer_required"
    suffix = 2
    while task_id in task_ids:
        task_id = f"answer_required_{suffix}"
        suffix += 1
    updated_tasks.append({
        "id": task_id,
        "domain": "other",
        "operation": "answer",
        "depends_on": [],
        "input": {"question": user_message},
    })
    updated["tasks"] = updated_tasks
    return updated


def validate_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize the LLM plan before it reaches the execution controller.
    This validates the plan structure, not the mathematical correctness of constraints.
    """
    if not isinstance(plan, dict):
        raise PlanValidationError("Plan phải là một dictionary/JSON object.")

    problem_type = plan.get("problem_type", "other")
    if problem_type not in ALLOWED_PROBLEM_TYPES:
        problem_type = "other"

    dimension = plan.get("visual_dimension")
    if dimension not in ALLOWED_DIMENSIONS:
        dimension = None

    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise PlanValidationError("Plan phải có danh sách tasks không rỗng.")

    normalized_tasks: List[Dict[str, Any]] = []
    seen_ids = set()

    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise PlanValidationError(f"Task thứ {index} phải là object.")

        task_id = task.get("id") or f"task_{index}"
        if not isinstance(task_id, str) or not task_id.strip():
            raise PlanValidationError(f"ID task thứ {index} không hợp lệ.")
        if task_id in seen_ids:
            raise PlanValidationError(f"Task ID bị trùng: {task_id}")
        seen_ids.add(task_id)

        operation = task.get("operation")
        if operation not in ALLOWED_OPERATIONS:
            raise PlanValidationError(
                f"Operation '{operation}' chưa được hỗ trợ. "
                f"Các operation hợp lệ: {sorted(ALLOWED_OPERATIONS)}"
            )

        depends_on = task.get("depends_on", [])
        if not isinstance(depends_on, list) or not all(
            isinstance(item, str) for item in depends_on
        ):
            raise PlanValidationError(
                f"depends_on của {task_id} phải là danh sách string."
            )

        task_input = task.get("input", {})
        if not isinstance(task_input, dict):
            raise PlanValidationError(f"input của {task_id} phải là object.")

        normalized_tasks.append({
            "id": task_id,
            "domain": task.get("domain", "other"),
            "operation": operation,
            "depends_on": depends_on,
            "input": task_input,
        })

    valid_ids = {task["id"] for task in normalized_tasks}
    for task in normalized_tasks:
        missing = set(task["depends_on"]) - valid_ids
        if missing:
            raise PlanValidationError(
                f"{task['id']} phụ thuộc vào task không tồn tại: {sorted(missing)}"
            )
        if task["id"] in task["depends_on"]:
            raise PlanValidationError(f"{task['id']} không thể phụ thuộc vào chính nó.")

    # Keep the normalized schema stable for the downstream controller.
    result = {
        "problem_type": problem_type,
        "domains": plan.get("domains", []),
        "needs_visual": bool(plan.get("needs_visual", False)),
        "visual_dimension": dimension,
        "needs_symbolic_compute": bool(plan.get("needs_symbolic_compute", False)),
        "needs_object_reference": bool(plan.get("needs_object_reference", False)),
        "target_ref": plan.get("target_ref"),
        "ambiguous": bool(plan.get("ambiguous", problem_type == "ambiguous")),
        "tasks": normalized_tasks,
        "notes": plan.get("notes", []),
    }
    if not isinstance(result["domains"], list):
        result["domains"] = []
    if not isinstance(result["notes"], list):
        result["notes"] = []

    return result


class Orchestrator:
    """Creates a plan; it does not execute drawing or math operations."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def create_plan(
        self,
        user_message: str,
        state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(user_message, str) or not user_message.strip():
            raise ValueError("user_message không được để trống.")

        state = state or {}
        prompt = build_orchestrator_user_prompt(
            user_message=user_message.strip(),
            summary=state.get("summary", ""),
            recent_turns=state.get("recent_turns", []),
            canvas_objects=state.get("canvas_objects", {}),
            geometry_model=state.get("geometry_model", {}),
        )

        raw_plan = self.llm_client.generate_json(
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.2,
        )
        if isinstance(raw_plan, dict):
            raw_plan = ensure_answer_task(raw_plan, user_message)
        return resolve_plan_references(
            validate_plan(raw_plan),
            user_message,
            state,
        )


def create_plan(
    user_message: str,
    state: Optional[Dict[str, Any]] = None,
    llm_client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    """Convenience function for use by a FastAPI route or a LangGraph node."""
    return Orchestrator(llm_client=llm_client).create_plan(
        user_message=user_message,
        state=deepcopy(state or {}),
    )
