"""Adapter 2D cho thư viện planegcs.

Cài đặt: pip install planegcs (Python 3.12+ theo bản PyPI hiện tại).
Chỉ chuyển các constraint có mapping rõ ràng; loại chưa hỗ trợ trả lỗi, không bị bỏ qua.
"""
from __future__ import annotations
from math import atan2, pi, radians
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

        try:
            sketch = Sketch()
            coords = normalized["coordinates"]
            anchors = {**normalized.get("gauge_anchors", {}), **normalized["hard_anchors"]}
            points: Dict[str, Any] = {}
            lines: Dict[tuple[str, str], Any] = {}
            for name, xy in coords.items():
                fixed = anchors.get(name, [])
                params = [sketch.add_param(value, fixed=axis >= 2 - len(fixed))
                          for axis, value in enumerate(xy)]
                points[name] = sketch.add_point_from_params(*params)

            def line(a: str, b: str):
                key = (a, b)
                if key not in lines:
                    lines[key] = sketch.add_line(points[a], points[b])
                return lines[key]

            def constrain_midpoint(point, a, b):
                axis = line(a, b)
                sketch.point_on_line(point, axis)
                sketch.point_on_perp_bisector(point, axis)

            unsupported = []
            for c in normalized["constraints"]:
                typ, ps = c.get("type"), c.get("points", [])
                if typ == "parallel_lines": sketch.parallel(line(ps[0], ps[1]), line(ps[2], ps[3]))
                elif typ == "perpendicular_lines": sketch.perpendicular(line(ps[0], ps[1]), line(ps[2], ps[3]))
                elif typ == "distance" and c["value"] != 0:
                    sketch.set_p2p_distance(points[ps[0]], points[ps[1]], c["value"])
                elif typ == "point_on_line" and c.get("_source_type") != "point_on_segment":
                    sketch.point_on_line(points[ps[0]], line(ps[1], ps[2]))
                elif typ == "midpoint":
                    constrain_midpoint(points[ps[0]], ps[1], ps[2])
                elif typ == "collinear":
                    sketch.point_on_line(points[ps[2]], line(ps[0], ps[1]))
                elif typ == "coincident" or typ == "distance":
                    sketch.coincident(points[ps[0]], points[ps[1]])
                elif typ == "horizontal": sketch.horizontal(line(ps[0], ps[1]))
                elif typ == "vertical": sketch.vertical(line(ps[0], ps[1]))
                elif typ == "equal_length": sketch.equal_length(line(ps[0], ps[1]), line(ps[2], ps[3]))
                elif typ == "angle":
                    a, b, c0, d = (coords[name] for name in ps)
                    first = atan2(b[1] - a[1], b[0] - a[0])
                    second = atan2(d[1] - c0[1], d[0] - c0[0])
                    signed = (second - first + pi) % (2 * pi) - pi
                    angle = radians(c["value"]) * (-1 if signed < 0 else 1)
                    sketch.set_l2l_angle(line(ps[0], ps[1]), line(ps[2], ps[3]), angle)
                elif typ == "parallelogram":
                    a, b, c0, d = ps
                    midpoint = sketch.add_point(*[(x + y) / 2 for x, y in zip(coords[a], coords[c0])])
                    constrain_midpoint(midpoint, a, c0)
                    constrain_midpoint(midpoint, b, d)
                else:
                    unsupported.append(c.get("_source_type") or typ)
            if unsupported:
                return {"success": False, "status": "unsupported_constraints", "solver": self.name,
                        "errors": [f"PlaneGCS adapter chưa hỗ trợ: {sorted(set(unsupported))}"]}
            status = sketch.solve()
            success = status == SolveStatus.Success
            solved = {name: list(sketch.get_point(handle)) for name, handle in points.items()} if success else {}
            return {"success": bool(success), "status": "solved" if success else "native_solver_failed",
                    "solver": self.name, "coordinates": solved,
                    "native_status": str(status), "errors": [] if success else [f"PlaneGCS solve thất bại: {status}"]}
        except Exception as exc:
            status = "api_mismatch" if isinstance(exc, (AttributeError, TypeError)) else "adapter_exception"
            return {"success": False, "status": status, "solver": self.name,
                    "errors": [f"Lỗi chuyển đổi constraint sang PlaneGCS: {exc}"]}
