"""Adapter 3D cho API SWIG của py_slvs (SolveSpace)."""
from __future__ import annotations

from typing import Any, Dict, Mapping


class PySlvsAdapter:
    name = "py_slvs"

    def __init__(self, tolerance: float = 1e-6):
        self.tolerance = float(tolerance)

    def solve(self, normalized: Mapping[str, Any]) -> Dict[str, Any]:
        if normalized.get("dimension") != 3:
            return {"success": False, "status": "wrong_dimension", "solver": self.name,
                    "errors": ["PySlvsAdapter chỉ giải hình học 3D."]}
        if normalized.get("errors"):
            return {"success": False, "status": "invalid_constraints", "solver": self.name,
                    "errors": list(normalized["errors"])}
        try:
            from py_slvs import slvs
        except Exception as exc:
            return {"success": False, "status": "dependency_missing", "solver": self.name,
                    "errors": [f"Không import được py_slvs: {exc}"]}

        coords = normalized["coordinates"]
        anchors = {**normalized.get("gauge_anchors", {}), **normalized["hard_anchors"]}
        fixed_group, solve_group = 1, 2
        try:
            system = slvs.System()
            free_3d = slvs.SLVS_FREE_IN_3D
            params = {}
            points = {}
            lines = {}

            def add_point(values, fixed_count=0):
                handles = [
                    system.addParamV(value, group=fixed_group if axis >= 3 - fixed_count else solve_group)
                    for axis, value in enumerate(values)
                ]
                group = fixed_group if fixed_count == 3 else solve_group
                return system.addPoint3d(*handles, group=group), handles

            for name, values in coords.items():
                points[name], params[name] = add_point(values, len(anchors.get(name, [])))

            def line(a, b):
                key = (a, b)
                if key not in lines:
                    lines[key] = system.addLineSegment(points[a], points[b], group=solve_group)
                return lines[key]

            def constrain(method, *args):
                method(*args, wrkpln=free_3d, group=solve_group)

            unsupported = []
            for constraint in normalized["constraints"]:
                typ, ps = constraint["type"], constraint["points"]
                if typ == "distance" and constraint["value"] != 0:
                    constrain(system.addPointsDistance, constraint["value"], points[ps[0]], points[ps[1]])
                elif typ in {"coincident", "distance"}:
                    constrain(system.addPointsCoincident, points[ps[0]], points[ps[1]])
                elif typ == "parallel_lines":
                    constrain(system.addParallel, line(*ps[:2]), line(*ps[2:]))
                elif typ == "perpendicular_lines":
                    constrain(system.addPerpendicular, line(*ps[:2]), line(*ps[2:]))
                elif typ == "equal_length":
                    constrain(system.addEqualLength, line(*ps[:2]), line(*ps[2:]))
                elif typ == "midpoint":
                    constrain(system.addMidPoint, points[ps[0]], line(*ps[1:]))
                elif typ == "point_on_line" and constraint.get("_source_type") != "point_on_segment":
                    constrain(system.addPointOnLine, points[ps[0]], line(*ps[1:]))
                elif typ == "collinear":
                    constrain(system.addPointOnLine, points[ps[2]], line(*ps[:2]))
                elif typ == "angle":
                    constrain(system.addAngle, constraint["value"], False, line(*ps[:2]), line(*ps[2:]))
                elif typ == "parallelogram":
                    a, b, c, d = ps
                    center, _ = add_point([(x + y) / 2 for x, y in zip(coords[a], coords[c])])
                    constrain(system.addMidPoint, center, line(a, c))
                    constrain(system.addMidPoint, center, line(b, d))
                else:
                    unsupported.append(constraint.get("_source_type") or typ)
            if unsupported:
                return {"success": False, "status": "unsupported_constraints", "solver": self.name,
                        "errors": [f"py_slvs adapter chưa hỗ trợ: {sorted(set(unsupported))}"]}

            raw_status = system.solve(group=solve_group)
            # SolveSpace's SLVS_RESULT_OKAY is 0 and is not exported by this binding.
            if raw_status != 0:
                # SLVS_RESULT_TOO_MANY_UNKNOWNS is a SolveSpace capacity limit.
                status = "native_capacity_exceeded" if raw_status == 3 else "native_solver_failed"
                return {"success": False, "status": status, "solver": self.name,
                        "native_status": str(raw_status), "errors": [f"py_slvs.solve() trả status={raw_status}."]}
            solved = {name: [system.getParam(handle).val for handle in handles]
                      for name, handles in params.items()}
            return {"success": True, "status": "solved", "solver": self.name,
                    "coordinates": solved, "native_status": str(raw_status), "errors": []}
        except Exception as exc:
            status = "api_mismatch" if isinstance(exc, (AttributeError, TypeError)) else "adapter_exception"
            return {"success": False, "status": status, "solver": self.name,
                    "errors": [f"Lỗi chuyển đổi constraint sang py_slvs: {exc}"]}
