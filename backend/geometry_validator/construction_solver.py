"""
ConstructionSolver: tính tọa độ các điểm phụ thuộc được khai báo bằng `constructions`.

Input mẫu:
{
    "coordinates": {
        "O": [0, 0],
        "D": [5, 0]
    },
    "constructions": {
        "B": {
            "construct": "tangent_point",
            "depends_on": ["O", "D"],
            "params": {"radius": 3, "which": "upper"}
        },
        "M": {
            "construct": "midpoint",
            "depends_on": ["A", "B"],
            "params": {}
        }
    }
}

Các phép dựng hiện hỗ trợ:
- midpoint: trung điểm của 2 điểm.
- point_on_line: P = A + t(B - A), params.t.
- perpendicular_foot: hình chiếu vuông góc của P lên đường thẳng AB.
  depends_on = ["P", "A", "B"].
- line_intersection: giao điểm của hai đường thẳng trong 2D.
  depends_on = ["A", "B", "C", "D"], hai đường AB và CD.
- tangent_point: tiếp điểm từ điểm ngoài D đến đường tròn tâm O, trong 2D.
  depends_on = ["O", "D"], params.radius và params.which = "upper"|"lower".

Lưu ý:
- Điểm do người dùng cung cấp được bảo vệ; điểm do LLM/state tạo ra có thể được tính lại nếu có construction.
- Phép dựng chưa đăng ký được trả về trong `needs_llm` để tầng điều phối quyết định gọi LLM/bổ sung hàm, không bị nhầm thành phép tính đã thành công.
- Solver không tự kiểm tra toàn bộ constraints; GeometryValidationController vẫn làm việc đó.
- Các tên điểm trong `depends_on` phải trùng key trong `coordinates` hoặc `constructions`.
"""

from __future__ import annotations

from math import sqrt, isfinite
from typing import Any, Callable, Dict, List, Mapping, Sequence, Tuple


Point = Tuple[float, ...]
Construction = Dict[str, Any]
Operation = Callable[[List[Point], Dict[str, Any]], Point]


class ConstructionError(ValueError):
    """Lỗi dữ liệu hoặc không thể thực hiện phép dựng hình học."""


class ConstructionSolver:
    """Tính tọa độ các điểm được mô tả trong trường `constructions`."""

    def __init__(self, tolerance: float = 1e-9) -> None:
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not isfinite(float(tolerance)) or tolerance <= 0:
            raise ValueError("tolerance phải là số hữu hạn lớn hơn 0.")
        self.tolerance = float(tolerance)
        self._operations: Dict[str, Operation] = {
            "midpoint": self._midpoint,
            "point_on_line": self._point_on_line,
            "perpendicular_foot": self._perpendicular_foot,
            "line_intersection": self._line_intersection,
            # Tương thích các prompt/plan cũ từng đặt tên phép dựng là "intersection".
            "intersection": self._line_intersection,
            "tangent_point": self._tangent_point,
        }

    def register(self, name: str, operation: Operation) -> None:
        """Đăng ký phép dựng mới; operation nhận (dependency_points, params)."""
        if not name or not callable(operation):
            raise ValueError("name phải là chuỗi không rỗng và operation phải callable.")
        self._operations[name] = operation

    @staticmethod
    def _point_source(
        name: str,
        spec: Mapping[str, Any],
        coordinate_control: Mapping[str, Any],
    ) -> str | None:
        """Lấy nguồn gốc điểm; origin_source được ưu tiên hơn source hiện tại."""
        control = coordinate_control.get(name, {})
        if not isinstance(control, Mapping):
            control = {}
        candidates = (
            spec.get("origin_source"),
            control.get("origin_source"),
            control.get("source"),
            spec.get("source"),
        )
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return None

    @staticmethod
    def _object_point_names(
        object_ref: str,
        canvas_objects: Mapping[str, Any] | Sequence[Any],
    ) -> List[str]:
        """Tìm các tên điểm cấu thành một object Canvas (thường là đường thẳng).

        Hỗ trợ object được định danh bằng dict key, id, name, label hoặc object_name.
        Chỉ trả về tên điểm; tọa độ vẫn phải có trong coordinates.
        """
        if isinstance(canvas_objects, Mapping):
            iterable = list(canvas_objects.items())
        elif isinstance(canvas_objects, Sequence) and not isinstance(canvas_objects, (str, bytes)):
            iterable = [(None, item) for item in canvas_objects]
        else:
            return []

        for object_key, obj in iterable:
            if not isinstance(obj, Mapping):
                continue
            identifiers = {
                str(value) for value in (
                    object_key, obj.get("id"), obj.get("object_id"),
                    obj.get("name"), obj.get("label"), obj.get("object_name"),
                    obj.get("line_name"),
                ) if value is not None
            }
            if object_ref not in identifiers:
                continue

            names = obj.get("point_names") or obj.get("vertex_names") or obj.get("vertices_names")
            if isinstance(names, (list, tuple)) and all(isinstance(v, str) and v.strip() for v in names):
                return [v.strip() for v in names]

            point_values = obj.get("points")
            if isinstance(point_values, (list, tuple)) and point_values and all(
                isinstance(v, str) and v.strip() for v in point_values
            ):
                return [v.strip() for v in point_values]

            coordinates = obj.get("coordinates")
            if isinstance(coordinates, Mapping):
                return [str(name) for name in coordinates.keys()]

            endpoints = obj.get("endpoints")
            if isinstance(endpoints, (list, tuple)) and all(isinstance(v, str) for v in endpoints):
                return list(endpoints)

        return []

    @classmethod
    def _expand_dependency(
        cls,
        dependency: str,
        coordinates: Mapping[str, Any],
        constructions: Mapping[str, Any],
        canvas_objects: Mapping[str, Any] | Sequence[Any],
    ) -> List[str]:
        """Đổi tham chiếu object đường thẳng thành tên các điểm đầu mút.

        Tên điểm thật trong coordinates/constructions luôn được ưu tiên.
        Ví dụ "AB" được mở rộng thành ["A", "B"] khi A và B là các điểm đã biết;
        hoặc tra trong canvas_objects nếu object có point_names=["A", "B"].
        """
        if dependency in coordinates or dependency in constructions:
            return [dependency]

        object_names = cls._object_point_names(dependency, canvas_objects)
        if object_names:
            return object_names

        # Backward compatibility: một số prompt cũ dùng tên đoạn/đường "AB"
        # thay vì liệt kê hai đầu mút. Chỉ tách khi cả A và B đã là tên điểm hợp lệ.
        if len(dependency) == 2:
            a, b = dependency[0], dependency[1]
            if a in coordinates and b in coordinates:
                return [a, b]

        return [dependency]

    def solve(self, task_input: Mapping[str, Any]) -> Dict[str, Any]:
        """Giải constructions và phân biệt điểm người dùng nhập với điểm suy ra.

        Input hỗ trợ:
        {
          "coordinates": {"A": [0, 0]},
          "coordinate_control": {
            "A": {"source": "user", "origin_source": "user"},
            "M": {"source": "state", "origin_source": "llm"}
          },
          "constructions": {
            "M": {"construct": "midpoint", "depends_on": ["A", "B"],
                  "params": {}, "source": "llm"}
          },
          "canvas_objects": {}
        }

        Quy tắc nguồn gốc:
        - user: không tự ghi đè tọa độ đã có.
        - llm/state: nếu có construction thì tính lại từ các điểm phụ thuộc.
        - không xác định nguồn + tọa độ đã có: bảo toàn an toàn, không tự ghi đè.
        - chưa đăng ký phép dựng: đưa vào `needs_llm`, không tuyên bố thành công.
        """
        raw_coordinates = task_input.get("coordinates") or {}
        raw_constructions = task_input.get("constructions") or {}
        raw_control = task_input.get("coordinate_control") or {}
        raw_canvas_objects = task_input.get("canvas_objects") or task_input.get("objects") or {}

        if not isinstance(raw_coordinates, Mapping):
            return self._failure({}, {}, ["'coordinates' phải là object/dict."])
        if not isinstance(raw_constructions, Mapping):
            return self._failure(dict(raw_coordinates), {}, ["'constructions' phải là object/dict."])
        if not isinstance(raw_control, Mapping):
            return self._failure(dict(raw_coordinates), {}, ["'coordinate_control' phải là object/dict."])
        if not isinstance(raw_canvas_objects, (Mapping, list, tuple)):
            return self._failure(dict(raw_coordinates), {}, ["'canvas_objects' phải là object/dict hoặc list."])

        coordinates: Dict[str, List[float]] = {}
        try:
            for name, values in raw_coordinates.items():
                coordinates[str(name)] = self._normalize_point(values, str(name))
        except ConstructionError as exc:
            return self._failure({}, {}, [str(exc)])

        constructions: Dict[str, Construction] = {}
        for name, spec in raw_constructions.items():
            if not isinstance(name, str) or not name.strip():
                return self._failure(coordinates, {}, ["Tên điểm trong constructions phải là chuỗi không rỗng."])
            if not isinstance(spec, Mapping):
                return self._failure(coordinates, {}, [f"Construction của điểm {name!r} phải là object."])
            constructions[str(name)] = dict(spec)

        coordinate_control = {str(k): v for k, v in raw_control.items()}
        computed: Dict[str, List[float]] = {}
        errors: List[str] = []
        needs_llm: List[Dict[str, Any]] = []
        skipped_existing: List[str] = []

        # Điểm mới luôn được dựng. Điểm đã tồn tại chỉ được tính lại khi nguồn
        # xác định là llm/state; điểm user hoặc không rõ nguồn được bảo toàn.
        pending: Dict[str, Construction] = {}
        for name, spec in constructions.items():
            if name not in coordinates:
                pending[name] = spec
                continue
            source = self._point_source(name, spec, coordinate_control)
            if source == "user":
                skipped_existing.append(name)
            elif source in {"llm", "state", "model", "assistant"}:
                pending[name] = spec
            else:
                skipped_existing.append(name)

        while pending:
            progressed = False

            for name in list(pending.keys()):
                spec = pending[name]
                op_name = spec.get("construct")
                dependencies = spec.get("depends_on", [])
                params = spec.get("params") or {}

                if not isinstance(op_name, str) or not op_name:
                    errors.append(f"Điểm {name!r}: thiếu tên phép dựng 'construct'.")
                    del pending[name]
                    progressed = True
                    continue
                if not isinstance(dependencies, list) or not all(
                    isinstance(dep, str) and dep.strip() for dep in dependencies
                ):
                    errors.append(f"Điểm {name!r}: 'depends_on' phải là danh sách tên điểm.")
                    del pending[name]
                    progressed = True
                    continue
                if not isinstance(params, Mapping):
                    errors.append(f"Điểm {name!r}: 'params' phải là object/dict.")
                    del pending[name]
                    progressed = True
                    continue
                if name in dependencies:
                    errors.append(f"Điểm {name!r}: không thể phụ thuộc trực tiếp vào chính nó.")
                    del pending[name]
                    progressed = True
                    continue
                canonical_op_name = {"intersection": "line_intersection"}.get(op_name, op_name)
                if canonical_op_name not in self._operations:
                    # Không tự đoán phép toán. Gửi thông tin có cấu trúc lên tầng
                    # Orchestrator để gọi LLM hoặc yêu cầu đăng ký implementation.
                    needs_llm.append({
                        "point": name,
                        "construct": op_name,
                        "depends_on": list(dependencies),
                        "reason": f"Phép dựng {op_name!r} chưa được đăng ký trong ConstructionSolver.",
                    })
                    # Nếu đây là điểm LLM/state cần tính lại, loại tọa độ cũ khỏi
                    # tập tọa độ hợp lệ để điểm phụ thuộc không dùng nhầm giá trị stale.
                    if self._point_source(name, spec, coordinate_control) in {"llm", "state", "model", "assistant"}:
                        coordinates.pop(name, None)
                    del pending[name]
                    progressed = True
                    continue
                # dependencies trong construction là tên điểm. Để tương thích dữ liệu
                # cũ, nếu LLM đưa tên đường/object (AB, CD, d), mở rộng thành các
                # điểm đầu mút dựa trên object Canvas hoặc quy ước tên AB.
                expanded_dependencies: List[str] = []
                for dependency in dependencies:
                    expanded_dependencies.extend(
                        self._expand_dependency(
                            dependency, coordinates, constructions, raw_canvas_objects
                        )
                    )

                missing_dependencies = [dep for dep in expanded_dependencies if dep not in coordinates]
                if missing_dependencies:
                    unresolved_by_llm = [
                        dep for dep in missing_dependencies
                        if any(item.get("point") == dep for item in needs_llm)
                    ]
                    if unresolved_by_llm:
                        needs_llm.append({
                            "point": name,
                            "construct": op_name,
                            "depends_on": list(expanded_dependencies),
                            "params": dict(params),
                            "reason": f"Chưa thể tính vì điểm phụ thuộc {unresolved_by_llm} cần được xử lý trước.",
                        })
                        del pending[name]
                        progressed = True
                        continue
                    # Chờ điểm phụ thuộc được tính ở vòng lặp sau.
                    continue

                try:
                    points = [tuple(coordinates[dep]) for dep in expanded_dependencies]
                    result = self._operations[canonical_op_name](points, dict(params))
                    normalized = self._normalize_point(result, name)
                    if points and any(len(p) != len(normalized) for p in points):
                        raise ConstructionError(
                            f"Điểm {name!r}: số chiều kết quả không khớp với điểm đầu vào."
                        )
                    coordinates[name] = normalized
                    computed[name] = normalized
                except (ConstructionError, TypeError, ValueError, KeyError, ZeroDivisionError) as exc:
                    errors.append(f"Điểm {name!r} ({op_name}): {exc}")
                del pending[name]
                progressed = True

            if not progressed:
                unresolved = []
                for name, spec in pending.items():
                    deps = spec.get("depends_on", [])
                    expanded = []
                    for dependency in deps if isinstance(deps, list) else []:
                        expanded.extend(self._expand_dependency(
                            dependency, coordinates, constructions, raw_canvas_objects
                        ))
                    missing = [d for d in expanded if d not in coordinates]
                    unresolved.append(f"{name!r} thiếu/chờ điểm {missing}")
                errors.append(
                    "Không thể giải tiếp constructions; có thể thiếu điểm đầu vào "
                    "hoặc vòng phụ thuộc. " + "; ".join(unresolved)
                )
                break

        # success chỉ true khi không còn lỗi và không có construction cần LLM.
        success = not errors and not needs_llm
        return {
            "success": success,
            "status": "success" if success else ("needs_llm" if needs_llm else "failed"),
            "coordinates": coordinates,
            "computed_points": computed,
            "errors": errors,
            "needs_llm": needs_llm,
            "skipped_existing_points": skipped_existing,
        }

    def _normalize_point(self, values: Any, name: str) -> List[float]:
        if not isinstance(values, (list, tuple)) or len(values) not in (2, 3):
            raise ConstructionError(
                f"Tọa độ điểm {name!r} phải là list/tuple gồm 2 hoặc 3 số."
            )
        point: List[float] = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConstructionError(f"Tọa độ điểm {name!r} chứa giá trị không phải số.")
            number = float(value)
            if not isfinite(number):
                raise ConstructionError(f"Tọa độ điểm {name!r} phải là số hữu hạn.")
            point.append(number)
        return point

    @staticmethod
    def _same_dimension(points: Sequence[Point]) -> int:
        if not points:
            raise ConstructionError("Phép dựng cần ít nhất một điểm đầu vào.")
        dimension = len(points[0])
        if any(len(p) != dimension for p in points):
            raise ConstructionError("Các điểm đầu vào không cùng số chiều.")
        return dimension

    @staticmethod
    def _midpoint(points: List[Point], params: Dict[str, Any]) -> Point:
        if len(points) != 2:
            raise ConstructionError("midpoint cần đúng 2 điểm: A, B.")
        ConstructionSolver._same_dimension(points)
        a, b = points
        return tuple((x + y) / 2.0 for x, y in zip(a, b))

    @staticmethod
    def _point_on_line(points: List[Point], params: Dict[str, Any]) -> Point:
        if len(points) != 2:
            raise ConstructionError("point_on_line cần đúng 2 điểm: A, B.")
        ConstructionSolver._same_dimension(points)
        if "t" not in params:
            raise ConstructionError("point_on_line yêu cầu params.t.")
        t = float(params["t"])
        if not isfinite(t):
            raise ConstructionError("params.t phải là số hữu hạn.")
        a, b = points
        return tuple(x + t * (y - x) for x, y in zip(a, b))

    def _perpendicular_foot(self, points: List[Point], params: Dict[str, Any]) -> Point:
        if len(points) != 3:
            raise ConstructionError("perpendicular_foot cần [P, A, B].")
        self._same_dimension(points)
        p, a, b = points
        ab = tuple(y - x for x, y in zip(a, b))
        ap = tuple(y - x for x, y in zip(a, p))
        denom = sum(v * v for v in ab)
        if denom <= self.tolerance:
            raise ConstructionError("Không thể chiếu lên đường thẳng vì A và B trùng nhau.")
        t = sum(x * y for x, y in zip(ap, ab)) / denom
        return tuple(x + t * v for x, v in zip(a, ab))

    def _line_intersection(self, points: List[Point], params: Dict[str, Any]) -> Point:
        if len(points) != 4:
            raise ConstructionError("line_intersection cần [A, B, C, D] cho hai đường AB và CD.")
        if self._same_dimension(points) != 2:
            raise ConstructionError("line_intersection hiện chỉ hỗ trợ hình học 2D.")
        (x1, y1), (x2, y2), (x3, y3), (x4, y4) = points
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) <= self.tolerance:
            raise ConstructionError("Hai đường thẳng song song hoặc trùng nhau, không có giao điểm duy nhất.")
        det1 = x1 * y2 - y1 * x2
        det2 = x3 * y4 - y3 * x4
        x = (det1 * (x3 - x4) - (x1 - x2) * det2) / den
        y = (det1 * (y3 - y4) - (y1 - y2) * det2) / den
        return (x, y)

    def _tangent_point(self, points: List[Point], params: Dict[str, Any]) -> Point:
        if len(points) != 2:
            raise ConstructionError("tangent_point cần [O, D]: tâm đường tròn và điểm ngoài.")
        if self._same_dimension(points) != 2:
            raise ConstructionError("tangent_point hiện chỉ hỗ trợ hình học 2D.")
        o, d = points
        if "radius" not in params:
            raise ConstructionError("tangent_point yêu cầu params.radius.")
        radius = float(params["radius"])
        if not isfinite(radius) or radius <= 0:
            raise ConstructionError("params.radius phải là số hữu hạn lớn hơn 0.")

        ox, oy = o
        dx, dy = d[0] - ox, d[1] - oy
        distance_sq = dx * dx + dy * dy
        radius_sq = radius * radius

        if distance_sq <= radius_sq + self.tolerance:
            raise ConstructionError("D phải nằm ngoài đường tròn để có hai tiếp tuyến thực phân biệt.")

        # Hai tiếp điểm: O + (r²/d²)v ± (r*sqrt(d²-r²)/d²)*perp(v)
        factor = radius_sq / distance_sq
        side = radius * sqrt(max(0.0, distance_sq - radius_sq)) / distance_sq
        base_x, base_y = ox + factor * dx, oy + factor * dy
        offset_x, offset_y = -side * dy, side * dx

        candidates = [
            (base_x + offset_x, base_y + offset_y),
            (base_x - offset_x, base_y - offset_y),
        ]
        which = str(params.get("which", "upper")).lower()
        if which == "upper":
            return max(candidates, key=lambda p: p[1])
        if which == "lower":
            return min(candidates, key=lambda p: p[1])
        if which in ("left", "right"):
            if which == "left":
                return min(candidates, key=lambda p: p[0])
            return max(candidates, key=lambda p: p[0])
        if which in ("0", "first", "plus"):
            return candidates[0]
        if which in ("1", "second", "minus"):
            return candidates[1]
        raise ConstructionError(
            "params.which phải là upper/lower/left/right/first/second."
        )

    @staticmethod
    def _failure(
        coordinates: Dict[str, Any],
        computed: Dict[str, Any],
        errors: List[str],
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "status": "failed",
            "coordinates": coordinates,
            "computed_points": computed,
            "errors": errors,
            "needs_llm": [],
            "skipped_existing_points": [],
        }


if __name__ == "__main__":
    # Ví dụ nhanh: đường tròn tâm O=(0,0), bán kính 3, D=(5,0).
    solver = ConstructionSolver()
    result = solver.solve({
        "coordinates": {"O": [0, 0], "D": [5, 0]},
        "constructions": {
            "B": {
                "construct": "tangent_point",
                "depends_on": ["O", "D"],
                "params": {"radius": 3, "which": "upper"},
            },
            "C": {
                "construct": "tangent_point",
                "depends_on": ["O", "D"],
                "params": {"radius": 3, "which": "lower"},
            },
        },
    })
    print(result)
