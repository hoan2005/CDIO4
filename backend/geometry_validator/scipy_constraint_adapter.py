"""Generic numerical constraint adapter using scipy.optimize.least_squares.

This is a practical fallback while optional native bindings are installed. It supports
point-based constraints and keeps user/fixed coordinates locked. It is not a replacement
for a CAD-grade symbolic solver; it reports underconstraint/unsupported constraints.
"""
from __future__ import annotations
from math import cos, sin, radians, sqrt
from typing import Any, Dict, Mapping, Sequence


class ScipyConstraintAdapter:
    name = "scipy_least_squares"

    def __init__(self, tolerance: float = 1e-7, max_nfev: int = 5000):
        self.tolerance = float(tolerance)
        self.max_nfev = int(max_nfev)

    def solve(self, normalized: Mapping[str, Any]) -> Dict[str, Any]:
        try:
            import numpy as np
            from scipy.optimize import least_squares
        except Exception as exc:
            return {"success": False, "status": "dependency_missing", "solver": self.name,
                    "errors": [f"scipy/numpy không khả dụng: {exc}"]}
        coords = {k: list(v) for k, v in normalized.get("coordinates", {}).items()}
        dim = int(normalized.get("dimension", 2))
        constraints = list(normalized.get("constraints", []))
        hard = {k: list(v) for k, v in normalized.get("hard_anchors", {}).items()}
        gauge = normalized.get("gauge_anchors", {}) or {}
        errors = list(normalized.get("errors", []))
        if errors:
            return {"success": False, "status": "invalid_constraints", "solver": self.name, "errors": errors}
        if not coords:
            return {"success": False, "status": "no_points", "solver": self.name, "errors": ["Không có điểm để giải."]}

        names = list(coords)
        # Hard anchors are excluded from optimization variables.
        variable_names = [n for n in names if n not in hard]
        initial = np.array([coords[n][j] for n in variable_names for j in range(dim)], dtype=float)
        gauge_values = {k: list(v) for k, v in gauge.items()}
        def unpack(x):
            out = {k: np.array(v, dtype=float) for k, v in coords.items()}
            for n, v in hard.items(): out[n] = np.array(v, dtype=float)
            for i, n in enumerate(variable_names): out[n] = np.array(x[i*dim:(i+1)*dim], dtype=float)
            return out
        supported = {"parallel_lines", "perpendicular_lines", "distance", "point_on_line", "midpoint",
                     "collinear", "coincident", "horizontal", "vertical", "equal_length", "angle",
                     "perpendicular_line_plane", "angle_between_planes"}
        unsupported = sorted({c.get("type", "unknown") for c in constraints if c.get("type") not in supported})
        if unsupported:
            return {"success": False, "status": "unsupported_constraints", "solver": self.name,
                    "errors": [f"Constraint chưa được triển khai trong adapter số: {unsupported}"]}

        def residual(x):
            p = unpack(x)
            r = []
            for name, vals in gauge_values.items():
                if len(vals) == dim:
                    axes = list(range(dim))
                elif dim == 2 and len(vals) == 1:
                    axes = [1]
                elif dim == 3 and len(vals) == 2:
                    axes = [1, 2]
                elif dim == 3 and len(vals) == 1:
                    axes = [2]
                else:
                    raise ValueError(f"Gauge anchor không hợp lệ cho điểm {name!r}")
                for axis, target in zip(axes, vals):
                    r.append(float(p[name][axis] - target))
            for c in constraints:
                t, q = c["type"], c.get("points", [])
                try:
                    pts = [p[n] for n in q]
                    if t == "distance":
                        r.append(float(np.linalg.norm(pts[0]-pts[1])) - float(c["value"]))
                    elif t == "coincident":
                        r.extend(pts[0]-pts[1])
                    elif t == "midpoint":
                        r.extend(pts[0] - (pts[1]+pts[2])/2.0)
                    elif t == "point_on_line":
                        v = pts[2]-pts[1]; vv = float(v @ v)
                        if vv < self.tolerance**2: r.extend([1e3]*dim)
                        else:
                            t_param = float((pts[0]-pts[1]) @ v)/vv
                            proj = pts[1] + v * t_param
                            r.extend(pts[0]-proj)
                            if c.get("_source_type") == "point_on_segment":
                                r.append(min(0.0, t_param) + max(0.0, t_param-1.0))
                    elif t == "collinear":
                        u, v = pts[1]-pts[0], pts[2]-pts[0]
                        if dim == 2: r.append(float(u[0]*v[1]-u[1]*v[0]))
                        else: r.extend(np.cross(u, v))
                    elif t == "parallel_lines":
                        u, v = pts[1]-pts[0], pts[3]-pts[2]
                        if dim == 2: r.append(float(u[0]*v[1]-u[1]*v[0]))
                        else: r.extend(np.cross(u, v))
                    elif t == "perpendicular_lines":
                        u, v = pts[1]-pts[0], pts[3]-pts[2]
                        r.append(float(u @ v))
                    elif t == "equal_length":
                        r.append(float(np.linalg.norm(pts[1]-pts[0])-np.linalg.norm(pts[3]-pts[2])))
                    elif t == "horizontal": r.append(float(pts[1][1]-pts[0][1]))
                    elif t == "vertical": r.append(float(pts[1][0]-pts[0][0]))
                    elif t == "angle":
                        u, v = pts[1]-pts[0], pts[3]-pts[2]
                        den = float(np.linalg.norm(u)*np.linalg.norm(v))
                        if den < self.tolerance: r.append(1e3)
                        else:
                            cosang = max(-1.0, min(1.0, float((u@v)/den)))
                            r.append(cosang-cos(radians(float(c["value"]))))
                    elif t == "perpendicular_line_plane":
                        direction = pts[1]-pts[0]
                        normal = np.cross(pts[3]-pts[2], pts[4]-pts[2])
                        den = float(np.linalg.norm(direction)*np.linalg.norm(normal))
                        if den < self.tolerance: r.extend([1e3]*3)
                        else: r.extend(np.cross(direction, normal) / den)
                    elif t == "angle_between_planes":
                        n1 = np.cross(pts[1]-pts[0], pts[2]-pts[0])
                        n2 = np.cross(pts[4]-pts[3], pts[5]-pts[3])
                        den = float(np.linalg.norm(n1)*np.linalg.norm(n2))
                        if den < self.tolerance: r.append(1e3)
                        else:
                            cosine = abs(float(n1@n2)/den)
                            r.append(cosine-cos(radians(float(c["value"]))))
                except (KeyError, ValueError, TypeError, IndexError):
                    r.append(1e3)
            return np.asarray(r or [0.0], dtype=float)

        try:
            if len(initial) == 0:
                x = initial
                residuals = residual(x)
                result_success = bool(np.linalg.norm(residuals) <= self.tolerance)
                result_message = "Tất cả tọa độ đã khóa; chỉ kiểm tra độ thỏa mãn."
                nfev = 0
            else:
                result = least_squares(residual, initial, max_nfev=self.max_nfev,
                                       xtol=self.tolerance, ftol=self.tolerance, gtol=self.tolerance)
                x = result.x
                residuals = residual(x)
                result_success = bool(result.success and np.linalg.norm(residuals, ord=np.inf) <= max(self.tolerance*10, 1e-6))
                result_message = str(result.message)
                nfev = int(result.nfev)
            solved = unpack(x)
            out = {k: [float(vv) for vv in solved[k]] for k in names}
            max_residual = float(np.max(np.abs(residuals))) if residuals.size else 0.0
            status = "solved" if result_success else "constraint_residual_too_large"
            return {"success": result_success, "status": status, "solver": self.name,
                    "coordinates": out, "max_residual": max_residual,
                    "residual_count": int(residuals.size), "nfev": nfev,
                    "message": result_message,
                    "diagnostics": {"underconstrained_possible": len(variable_names)*dim > len(residuals),
                                    "variable_count": len(variable_names)*dim,
                                    "residual_count": int(residuals.size)},
                    "errors": [] if result_success else [f"Không thỏa constraints đủ chính xác (max residual={max_residual:.3g})."]}
        except Exception as exc:
            return {"success": False, "status": "solver_exception", "solver": self.name,
                    "errors": [f"Lỗi khi giải hệ constraint: {exc}"]}
