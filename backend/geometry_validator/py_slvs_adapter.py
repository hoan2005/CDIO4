"""Adapter 3D cho binding py_slvs (SolveSpace).

Binding này là API mức thấp và có khác biệt giữa các bản build. Adapter fail-closed:
nếu API cần thiết không tồn tại hoặc constraint chưa được map thì trả lỗi, không tự bỏ qua.
"""
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
            import py_slvs
        except Exception as exc:
            return {"success": False, "status": "dependency_missing", "solver": self.name,
                    "errors": [f"Không import được py_slvs: {exc}. Cài/biên dịch binding SolveSpace phù hợp môi trường."]}

        System = getattr(py_slvs, "SolverSystem", None)
        Entity = getattr(py_slvs, "Entity", None)
        if System is None or Entity is None:
            return {"success": False, "status": "api_mismatch", "solver": self.name,
                    "errors": ["Module py_slvs không có SolverSystem/Entity theo API dự kiến; cần đối chiếu bản binding đã cài."]}

        coords = normalized.get("coordinates", {})
        hard = normalized.get("hard_anchors", {})
        constraints = normalized.get("constraints", [])
        try:
            system = System()
            pts = {name: system.add_point_3d(float(v[0]), float(v[1]), float(v[2])) for name, v in coords.items()}
            lines = {}
            def line(a, b):
                key = (a, b); rev = (b, a)
                if key in lines: return lines[key]
                if rev in lines: return lines[rev]
                result = system.add_line_3d(pts[a], pts[b]); lines[key] = result
                return result
            # Keep locked/user points at their supplied initial coordinates.
            for name in hard:
                system.dragged(pts[name], Entity.FREE_IN_3D)

            unsupported = []
            for c in constraints:
                typ, ps = c.get("type"), c.get("points", [])
                if typ == "coincident": system.coincident(pts[ps[0]], pts[ps[1]], Entity.FREE_IN_3D)
                elif typ == "distance": system.distance(pts[ps[0]], pts[ps[1]], float(c["value"]), Entity.FREE_IN_3D)
                elif typ == "parallel_lines": system.parallel(line(ps[0], ps[1]), line(ps[2], ps[3]), Entity.FREE_IN_3D)
                elif typ == "perpendicular_lines": system.perpendicular(line(ps[0], ps[1]), line(ps[2], ps[3]), Entity.FREE_IN_3D, False)
                elif typ == "equal_length": system.equal(line(ps[0], ps[1]), line(ps[2], ps[3]), Entity.FREE_IN_3D)
                elif typ == "midpoint": system.midpoint(pts[ps[0]], line(ps[1], ps[2]), Entity.FREE_IN_3D)
                elif typ == "point_on_line": system.coincident(pts[ps[0]], line(ps[1], ps[2]), Entity.FREE_IN_3D)
                elif typ == "collinear":
                    # 3D collinearity is point-on-line.
                    system.coincident(pts[ps[2]], line(ps[0], ps[1]), Entity.FREE_IN_3D)
                else: unsupported.append(typ)
            if unsupported:
                return {"success": False, "status": "unsupported_constraints", "solver": self.name,
                        "errors": [f"py_slvs adapter chưa map: {sorted(set(unsupported))}"]}
            raw_status = system.solve()
            # SolveSpace result enums vary by binding version; zero is commonly success.
            success = raw_status == 0
            solved = {}
            for name, entity in pts.items():
                params_handle = getattr(entity, "params", None)
                if params_handle is None:
                    raise RuntimeError("Entity không cung cấp params; không đọc được tọa độ nghiệm.")
                values = system.params(params_handle)
                if len(values) < 3:
                    raise RuntimeError(f"Không đủ tham số tọa độ cho điểm {name}: {values!r}")
                solved[name] = [float(values[0]), float(values[1]), float(values[2])]
            return {"success": bool(success), "status": "solved" if success else "native_solver_failed",
                    "solver": self.name, "coordinates": solved, "native_status": str(raw_status),
                    "errors": [] if success else [f"py_slvs.solve() trả status={raw_status}; cần xác minh enum của bản cài."]}
        except Exception as exc:
            return {"success": False, "status": "adapter_exception", "solver": self.name,
                    "errors": [f"Lỗi chuyển đổi constraint sang py_slvs: {exc}"]}
