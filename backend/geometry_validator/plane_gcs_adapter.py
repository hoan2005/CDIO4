"""Adapter 2D cho thư viện planegcs.

Cài đặt: pip install planegcs (Python 3.12+ theo bản PyPI hiện tại).
Chỉ chuyển các constraint có mapping rõ ràng; loại chưa hỗ trợ trả lỗi, không bị bỏ qua.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping


class PlaneGCSAdapter:
    name = "planegcs"

    def __init__(self, tolerance: float = 1e-7):
        self.tolerance = float(tolerance)

    def solve(self, normalized: Mapping[str, Any]) -> Dict[str, Any]:
        if normalized.get("dimension") != 2:
            return {"success": False, "status": "wrong_dimension", "solver": self.name,
                    "errors": ["PlaneGCSAdapter chỉ giải hình học 2D."]}
        if normalized.get("errors"):
            return {"success": False, "status": "invalid_constraints", "solver": self.name,
                    "errors": list(normalized["errors"])}
        try:
            from planegcs import Sketch, SolveStatus
        except Exception as exc:
            return {"success": False, "status": "dependency_missing", "solver": self.name,
                    "errors": [f"Không import được planegcs: {exc}. Cài bằng `pip install planegcs`."]}

        coords = normalized.get("coordinates", {})
        hard = normalized.get("hard_anchors", {})
        constraints = normalized.get("constraints", [])
        sketch = Sketch()
        points: Dict[str, Any] = {}
        lines: Dict[tuple[str, str], Any] = {}
        try:
            for name, xy in coords.items():
                if name in hard:
                    points[name] = sketch.add_fixed_point(float(xy[0]), float(xy[1]))
                else:
                    points[name] = sketch.add_point(float(xy[0]), float(xy[1]))

            def line(a: str, b: str):
                key = (a, b)
                rev = (b, a)
                if key in lines: return lines[key]
                if rev in lines: return lines[rev]
                if a not in points or b not in points:
                    raise ValueError(f"Không tìm thấy điểm tạo đường thẳng {a}-{b}")
                obj = sketch.add_line(points[a], points[b])
                lines[key] = obj
                return obj

            unsupported = []
            for c in constraints:
                typ, ps = c.get("type"), c.get("points", [])
                if typ == "parallel_lines": sketch.parallel(line(ps[0], ps[1]), line(ps[2], ps[3]))
                elif typ == "perpendicular_lines": sketch.perpendicular(line(ps[0], ps[1]), line(ps[2], ps[3]))
                elif typ == "distance": sketch.set_p2p_distance(points[ps[0]], points[ps[1]], float(c["value"]))
                elif typ == "point_on_line": sketch.point_on_object(points[ps[0]], line(ps[1], ps[2]))
                elif typ == "midpoint": sketch.midpoint(points[ps[0]], line(ps[1], ps[2]))
                elif typ == "collinear":
                    # Collinear can be represented as the third point on line AB.
                    sketch.point_on_object(points[ps[2]], line(ps[0], ps[1]))
                elif typ == "coincident": sketch.coincident(points[ps[0]], points[ps[1]])
                elif typ == "horizontal": sketch.horizontal(line(ps[0], ps[1]))
                elif typ == "vertical": sketch.vertical(line(ps[0], ps[1]))
                elif typ == "equal_length": sketch.equal_length(line(ps[0], ps[1]), line(ps[2], ps[3]))
                elif typ == "angle": sketch.set_angle(line(ps[0], ps[1]), line(ps[2], ps[3]), float(c["value"]))
                else: unsupported.append(typ)
            if unsupported:
                return {"success": False, "status": "unsupported_constraints", "solver": self.name,
                        "errors": [f"PlaneGCS adapter chưa hỗ trợ: {sorted(set(unsupported))}"]}
            status = sketch.solve()
            success = status == SolveStatus.Success
            solved = {name: [float(sketch.get_point(handle)[0]), float(sketch.get_point(handle)[1])]
                      for name, handle in points.items()}
            return {"success": bool(success), "status": "solved" if success else "native_solver_failed",
                    "solver": self.name, "coordinates": solved,
                    "native_status": str(status), "errors": [] if success else [f"PlaneGCS solve thất bại: {status}"]}
        except Exception as exc:
            return {"success": False, "status": "adapter_exception", "solver": self.name,
                    "errors": [f"Lỗi chuyển đổi constraint sang PlaneGCS: {exc}"]}
