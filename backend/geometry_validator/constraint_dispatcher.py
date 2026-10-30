"""
constraint_dispatcher.py

Bộ phân phối constraint -> validator Python.
Các validator không sửa tọa độ và không cập nhật StateManager.

Coordinate format:
    {"A": [0, 0, 0], "B": [4, 0, 0], ...}

Constraint schema dùng trong file này:
    {"type": "perpendicular_lines", "line_1": ["A", "B"], "line_2": ["C", "D"]}
    {"type": "parallel_lines", "line_1": ["A", "B"], "line_2": ["C", "D"]}
    {"type": "right_triangle", "points": ["A", "B", "C"], "right_angle_at": "A"}
    {"type": "isosceles_triangle", "points": ["A", "B", "C"], "apex": "A"}
    {"type": "equilateral_triangle", "points": ["A", "B", "C"]}
    {"type": "equal_length", "segment_1": ["A", "B"], "segment_2": ["C", "D"]}
    {"type": "perpendicular_line_plane", "line": ["S", "A"], "plane": ["A", "B", "C"]}
    {"type": "point_on_line", "point": "K", "line": ["N", "P"]}
    {"type": "point_on_segment", "point": "K", "segment": ["N", "P"]}
    {"type": "midpoint", "point": "K", "segment": ["N", "P"]}
    {"type": "angle_between_planes", "plane_1": ["S", "B", "C"],
     "plane_2": ["A", "B", "C"], "angle_degrees": 60}
        (tùy chọn: "tolerance_degrees", mặc định 0.05)

Nếu validator hiện tại của bạn dùng tên trường khác, hãy chuẩn hóa ở đây
hoặc đổi schema đầu vào để khớp với code hiện có.
"""
from __future__ import annotations

from math import sqrt, isfinite, acos, degrees
from typing import Any, Callable


Vector = list[float]
Validator = Callable[[dict[str, Any], dict[str, Vector], float], dict[str, Any]]


def _result(status: str, constraint: dict, reason: str, **extra) -> dict:
    return {
        "status": status,
        "constraint_type": constraint.get("type"),
        "constraint": constraint,
        "reason": reason,
        **extra,
    }


def _point(name: str, coordinates: dict[str, Vector]) -> Vector:
    if name not in coordinates:
        raise KeyError(f"Không tìm thấy tọa độ điểm '{name}'.")
    p = coordinates[name]
    if not isinstance(p, (list, tuple)) or len(p) < 2:
        raise ValueError(f"Tọa độ điểm '{name}' phải là list có ít nhất 2 chiều.")
    values = [float(v) for v in p]
    if not all(isfinite(v) for v in values):
        raise ValueError(f"Tọa độ điểm '{name}' chứa giá trị không hữu hạn.")
    return values


def _same_dimension(*points: Vector) -> bool:
    return len({len(p) for p in points}) == 1


def _sub(a: Vector, b: Vector) -> Vector:
    return [x - y for x, y in zip(a, b)]


def _dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: Vector) -> float:
    return sqrt(_dot(a, a))


def _distance(a: Vector, b: Vector) -> float:
    return _norm(_sub(a, b))


def _cross3(a: Vector, b: Vector) -> Vector:
    if len(a) != 3 or len(b) != 3:
        raise ValueError("Phép tích có hướng trong validator này yêu cầu tọa độ 3D.")
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _relative_close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def _nonzero(v: Vector, tol: float) -> bool:
    return _norm(v) > tol


def check_perpendicular_lines(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    try:
        a, b = c["line_1"]
        d, e = c["line_2"]
        p1, p2, p3, p4 = (_point(n, xyz) for n in (a, b, d, e))
        if not _same_dimension(p1, p2, p3, p4):
            return _result("failed", c, "Các điểm không cùng số chiều.")
        u, v = _sub(p2, p1), _sub(p4, p3)
        if not _nonzero(u, tol) or not _nonzero(v, tol):
            return _result("failed", c, "Không xác định được đường thẳng từ hai điểm trùng nhau.")
        dot = _dot(u, v)
        ok = abs(dot) <= tol * max(1.0, _norm(u) * _norm(v))
        return _result("verified" if ok else "failed", c,
                       "Hai vector chỉ phương vuông góc." if ok else "Tích vô hướng hai vector chỉ phương khác 0.",
                       dot_product=dot)
    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))



def check_parallel_lines(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    try:
        a, b = c["line_1"]
        p1, p2 = _point(a, xyz), _point(b, xyz)

        if not _same_dimension(p1, p2):
            return _result("failed", c, "Các điểm không cùng số chiều.")

        u = _sub(p2, p1)
        nu = _norm(u)

        if nu <= tol:
            return _result(
                "failed", c,
                "Không xác định được đường thẳng thứ nhất."
            )

        # Trường hợp 1: Hai đường thẳng được xác định bằng hai điểm.
        if "line_2" in c:
            d, e = c["line_2"]
            p3, p4 = _point(d, xyz), _point(e, xyz)

            if not _same_dimension(p1, p2, p3, p4):
                return _result(
                    "failed", c,
                    "Các điểm không cùng số chiều."
                )

            v = _sub(p4, p3)
            nv = _norm(v)

            if nv <= tol:
                return _result(
                    "failed", c,
                    "Không xác định được đường thẳng thứ hai."
                )

            if len(u) == 2:
                measure = abs(u[0] * v[1] - u[1] * v[0])
            elif len(u) == 3:
                measure = _norm(_cross3(u, v))
            else:
                scale = _dot(u, v) / _dot(u, u)
                residual = [
                    vv - scale * uu
                    for vv, uu in zip(v, u)
                ]
                measure = _norm(residual)

            ok = measure <= tol * max(1.0, nu * nv)

            return _result(
                "verified" if ok else "failed",
                c,
                "Hai đường có vector chỉ phương song song."
                if ok else "Hai vector chỉ phương không song song.",
                parallel_error=measure,
            )

        # Trường hợp 2: Đường thẳng song song với tiếp tuyến
        # tại tangent_at của đường tròn có tâm circle.
        if "tangent_at" in c and "circle" in c:
            tangent_point = c["tangent_at"]
            center_name = c["circle"]

            point_a = _point(tangent_point, xyz)
            center = _point(center_name, xyz)

            if not _same_dimension(p1, p2, point_a, center):
                return _result(
                    "failed", c,
                    "Các điểm không cùng số chiều."
                )

            radius_vec = _sub(point_a, center)
            nr = _norm(radius_vec)

            if nr <= tol:
                return _result(
                    "failed", c,
                    "Tâm đường tròn trùng với điểm tiếp xúc."
                )

            # Tiếp tuyến tại A vuông góc với OA.
            # PQ song song tiếp tuyến khi PQ vuông góc OA.
            dot = _dot(u, radius_vec)
            measure = abs(dot)
            ok = measure <= tol * max(1.0, nu * nr)

            return _result(
                "verified" if ok else "failed",
                c,
                "Đường thẳng song song với phương tiếp tuyến."
                if ok else "Đường thẳng không song song với phương tiếp tuyến.",
                dot_product=dot,
            )

        return _result(
            "failed", c,
            "parallel_lines cần line_2 hoặc "
            "cặp tangent_at và circle."
        )

    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))



def check_right_triangle(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    try:
        names = c["points"]
        if len(names) != 3:
            return _result("failed", c, "right_triangle cần đúng 3 điểm.")
        right = c["right_angle_at"]
        if right not in names:
            return _result("failed", c, "right_angle_at không nằm trong points.")
        others = [n for n in names if n != right]
        p, q, r = _point(right, xyz), _point(others[0], xyz), _point(others[1], xyz)
        if not _same_dimension(p, q, r):
            return _result("failed", c, "Các điểm không cùng số chiều.")
        u, v = _sub(q, p), _sub(r, p)
        if not _nonzero(u, tol) or not _nonzero(v, tol):
            return _result("failed", c, "Tam giác suy biến do có hai đỉnh trùng nhau.")
        dot = _dot(u, v)
        ok = abs(dot) <= tol * max(1.0, _norm(u) * _norm(v))
        if not ok:
            return _result("failed", c, f"Góc tại {right} không vuông.", dot_product=dot)
        # Reject collinear triangle / zero area.
        if len(p) == 2:
            area2 = abs(u[0] * v[1] - u[1] * v[0])
        elif len(p) == 3:
            area2 = _norm(_cross3(u, v))
        else:
            area2 = sqrt(max(0.0, _dot(u, u) * _dot(v, v) - dot * dot))
        if area2 <= tol:
            return _result("failed", c, "Tam giác suy biến.")
        return _result("verified", c, f"Tam giác vuông tại {right}.", dot_product=dot)
    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))


def check_isosceles_triangle(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    try:
        a, b, d = c["points"]
        apex = c.get("apex")
        if apex is None:
            return _result("uncertain", c, "Thiếu trường apex để xác định đỉnh cân.")
        if apex not in (a, b, d):
            return _result("failed", c, "apex không nằm trong points.")
        base = [n for n in (a, b, d) if n != apex]
        p_apex, p1, p2 = _point(apex, xyz), _point(base[0], xyz), _point(base[1], xyz)
        if not _same_dimension(p_apex, p1, p2):
            return _result("failed", c, "Các điểm không cùng số chiều.")
        l1, l2 = _distance(p_apex, p1), _distance(p_apex, p2)
        if min(l1, l2, _distance(p1, p2)) <= tol:
            return _result("failed", c, "Tam giác suy biến.")
        ok = _relative_close(l1, l2, tol)
        return _result("verified" if ok else "failed", c,
                       f"Hai cạnh bên tại {apex} {'bằng nhau' if ok else 'không bằng nhau'}.",
                       side_1=l1, side_2=l2)
    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))


def check_equilateral_triangle(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    try:
        a, b, d = c["points"]
        p, q, r = _point(a, xyz), _point(b, xyz), _point(d, xyz)
        if not _same_dimension(p, q, r):
            return _result("failed", c, "Các điểm không cùng số chiều.")
        lengths = [_distance(p, q), _distance(q, r), _distance(r, p)]
        if min(lengths) <= tol:
            return _result("failed", c, "Tam giác suy biến.")
        ok = all(_relative_close(lengths[0], x, tol) for x in lengths[1:])
        return _result("verified" if ok else "failed", c,
                       "Ba cạnh bằng nhau." if ok else "Ba cạnh không bằng nhau.",
                       side_lengths=lengths)
    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))


def check_equal_length(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    try:
        a, b = c["segment_1"]
        d, e = c["segment_2"]
        p1, p2, p3, p4 = (_point(n, xyz) for n in (a, b, d, e))
        if not _same_dimension(p1, p2, p3, p4):
            return _result("failed", c, "Các điểm không cùng số chiều.")
        l1, l2 = _distance(p1, p2), _distance(p3, p4)
        ok = _relative_close(l1, l2, tol)
        return _result("verified" if ok else "failed", c,
                       "Hai đoạn thẳng bằng nhau." if ok else "Hai đoạn thẳng không bằng nhau.",
                       length_1=l1, length_2=l2)
    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))


def check_perpendicular_line_plane(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    try:
        line_a, line_b = c["line"]
        plane_names = c["plane"]
        if len(plane_names) < 3:
            return _result("failed", c, "Mặt phẳng cần ít nhất 3 điểm.")
        a, b = _point(line_a, xyz), _point(line_b, xyz)
        plane_pts = [_point(n, xyz) for n in plane_names]
        if not _same_dimension(a, b, *plane_pts):
            return _result("failed", c, "Các điểm không cùng số chiều.")
        direction = _sub(b, a)
        if not _nonzero(direction, tol):
            return _result("failed", c, "Đường thẳng không xác định.")
        # A line is perpendicular to a plane iff its direction is parallel
        # to a plane normal. Build a normal from two independent plane vectors.
        origin = plane_pts[0]
        normal = None
        for i in range(1, len(plane_pts)):
            for j in range(i + 1, len(plane_pts)):
                u = _sub(plane_pts[i], origin)
                v = _sub(plane_pts[j], origin)
                if len(origin) == 3:
                    candidate = _cross3(u, v)
                    if _norm(candidate) > tol:
                        normal = candidate
                        break
                elif len(origin) == 2:
                    # In 2D, a line cannot be perpendicular to a 2D plane in the usual 3D sense.
                    return _result("unsupported", c, "perpendicular_line_plane yêu cầu tọa độ 3D.")
            if normal is not None:
                break
        if normal is None:
            return _result("failed", c, "Không xác định được mặt phẳng: các điểm đáy có thể thẳng hàng.")
        cross = _cross3(direction, normal)
        err = _norm(cross)
        ok = err <= tol * max(1.0, _norm(direction) * _norm(normal))
        return _result("verified" if ok else "failed", c,
                       "Đường thẳng vuông góc với mặt phẳng." if ok else "Vector chỉ phương đường thẳng không song song vector pháp tuyến.",
                       error=err)
    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))


def check_point_on_line(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    try:
        p_name = c["point"]
        a_name, b_name = c["line"]
        p, a, b = _point(p_name, xyz), _point(a_name, xyz), _point(b_name, xyz)
        if not _same_dimension(p, a, b):
            return _result("failed", c, "Các điểm không cùng số chiều.")
        u, v = _sub(b, a), _sub(p, a)
        denom = _dot(u, u)
        if denom <= tol * tol:
            return _result("failed", c, "Đường thẳng không xác định.")
        t = _dot(v, u) / denom
        residual = [vv - t * uu for vv, uu in zip(v, u)]
        err = _norm(residual)
        ok = err <= tol * max(1.0, _norm(v), _norm(u))
        return _result("verified" if ok else "failed", c,
                       "Điểm thuộc đường thẳng." if ok else "Điểm không thuộc đường thẳng.",
                       parameter=t, error=err)
    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))


def check_point_on_segment(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    result = check_point_on_line(
        {"type": "point_on_line", "point": c["point"], "line": c["segment"]},
        xyz, tol
    )
    if result["status"] != "verified":
        result["constraint"] = c
        result["constraint_type"] = c.get("type")
        return result
    t = result.get("parameter", 0.0)
    ok = -tol <= t <= 1.0 + tol
    return _result("verified" if ok else "failed", c,
                   "Điểm thuộc đoạn thẳng." if ok else "Điểm nằm ngoài đoạn thẳng.",
                   parameter=t)


def check_midpoint(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    try:
        k = _point(c["point"], xyz)
        a_name, b_name = c["segment"]
        a, b = _point(a_name, xyz), _point(b_name, xyz)
        if not _same_dimension(k, a, b):
            return _result("failed", c, "Các điểm không cùng số chiều.")
        expected = [(x + y) / 2 for x, y in zip(a, b)]
        err = _distance(k, expected)
        scale = max(1.0, _norm(a), _norm(b), _norm(k))
        ok = err <= tol * scale
        return _result("verified" if ok else "failed", c,
                       "Điểm là trung điểm." if ok else "Điểm không phải trung điểm.",
                       error=err)
    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))


def _plane_normal(names: list[str], xyz: dict[str, Vector], tol: float) -> Vector:
    """Pháp tuyến (chưa chuẩn hóa) của mặt phẳng qua các điểm đã cho (cần 3D)."""
    if not isinstance(names, (list, tuple)) or len(names) < 3:
        raise ValueError("Mặt phẳng cần ít nhất 3 điểm.")
    pts = [_point(n, xyz) for n in names]
    if not _same_dimension(*pts) or len(pts[0]) != 3:
        raise ValueError("angle_between_planes yêu cầu tọa độ 3D và cùng số chiều.")
    origin = pts[0]
    for i in range(1, len(pts)):
        for j in range(i + 1, len(pts)):
            n = _cross3(_sub(pts[i], origin), _sub(pts[j], origin))
            if _norm(n) > tol:
                return n
    raise ValueError(f"Các điểm {list(names)} thẳng hàng hoặc trùng nhau, không xác định được mặt phẳng.")


def check_angle_between_planes(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    """Góc nhị diện nhọn (0..90 độ) giữa hai mặt phẳng so với angle_degrees."""
    try:
        n1 = _plane_normal(c["plane_1"], xyz, tol)
        n2 = _plane_normal(c["plane_2"], xyz, tol)
        cos_t = abs(_dot(n1, n2)) / (_norm(n1) * _norm(n2))
        angle = degrees(acos(min(1.0, cos_t)))
        expected = float(c["angle_degrees"])
        # Sai số theo độ, cho phép tọa độ bị làm tròn (vd 3.464 thay vì 2*sqrt(3)).
        angle_tol = float(c.get("tolerance_degrees", 0.05))
        ok = abs(angle - expected) <= angle_tol
        return _result("verified" if ok else "failed", c,
                       f"Góc giữa hai mặt phẳng ≈ {angle:.4f}°." if ok
                       else f"Góc thực tế ≈ {angle:.4f}°, khác giá trị yêu cầu {expected}°.",
                       angle_degrees=angle, expected_degrees=expected)
    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))


def check_circle_radius(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    """Kiểm tra bán kính đường tròn mà không bắt buộc phải có điểm phụ.

    Schema hỗ trợ:
      {"type": "circle_radius", "radius": 3}
      {"type": "circle_radius", "center": "O", "radius": 3}
      {"type": "circle_radius", "center": "O", "point": "A", "radius": 3}

    Nếu có point trên đường tròn và center, kiểm tra khoảng cách center-point
    có bằng radius hay không. Nếu chỉ có radius, kiểm tra radius hợp lệ.
    """
    try:
        raw_radius = c.get("radius", c.get("r"))
        center_name = c.get("center", c.get("center_point", c.get("center_name")))
        point_name = c.get(
            "point_on_circle",
            c.get("point_on_circumference", c.get("point"))
        )

        center = _point(center_name, xyz) if isinstance(center_name, str) else None
        point = _point(point_name, xyz) if isinstance(point_name, str) else None

        if raw_radius is None:
            # Nếu có đủ tâm và điểm thuộc đường tròn, có thể suy ra bán kính.
            if center is None or point is None:
                return _result(
                    "uncertain", c,
                    "Thiếu bán kính; cần radius hoặc cả tâm và điểm trên đường tròn."
                )
            if not _same_dimension(center, point):
                return _result("failed", c, "Tâm và điểm trên đường tròn không cùng số chiều.")
            computed_radius = _distance(center, point)
            if not isfinite(computed_radius) or computed_radius <= tol:
                return _result("failed", c, "Bán kính suy ra phải hữu hạn và lớn hơn 0.")
            return _result(
                "verified", c, "Bán kính được xác định từ khoảng cách tâm đến điểm.",
                radius=computed_radius
            )

        try:
            radius = float(raw_radius)
        except (TypeError, ValueError):
            return _result("failed", c, "Bán kính phải là số.")

        if not isfinite(radius) or radius <= 0:
            return _result("failed", c, "Bán kính phải là số hữu hạn lớn hơn 0.")

        # Tâm và điểm trên đường tròn là tùy chọn khi radius đã được cung cấp.
        if center is None and point is None:
            return _result("verified", c, "Bán kính là số hữu hạn lớn hơn 0.", radius=radius)

        if center is None or point is None:
            return _result(
                "uncertain", c,
                "Có khai báo điểm/tâm nhưng thiếu thành phần còn lại để đối chiếu bán kính.",
                radius=radius
            )

        if not _same_dimension(center, point):
            return _result("failed", c, "Tâm và điểm trên đường tròn không cùng số chiều.")

        actual_radius = _distance(center, point)
        ok = abs(actual_radius - radius) <= tol * max(1.0, actual_radius, radius)
        return _result(
            "verified" if ok else "failed", c,
            "Khoảng cách từ tâm đến điểm khớp bán kính."
            if ok else f"Khoảng cách thực tế {actual_radius:g} khác bán kính {radius:g}.",
            radius=radius, actual_radius=actual_radius
        )
    except (KeyError, ValueError, TypeError) as e:
        return _result("failed", c, str(e))




def check_segment_length(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    """Kiểm tra độ dài một đoạn thẳng theo schema segment + length/value."""
    try:
        names = c.get("segment", c.get("points"))
        if not isinstance(names, (list, tuple)) or len(names) != 2:
            return _result("failed", c, "segment_length cần segment gồm đúng 2 điểm.")
        a, b = (_point(name, xyz) for name in names)
        if not _same_dimension(a, b):
            return _result("failed", c, "Hai đầu mút không cùng số chiều.")
        raw = c.get("length", c.get("value", c.get("distance")))
        if isinstance(raw, bool):
            return _result("failed", c, "Độ dài phải là số hữu hạn không âm.")
        expected = float(raw)
        if not isfinite(expected) or expected < 0:
            return _result("failed", c, "Độ dài phải là số hữu hạn không âm.")
        actual = _distance(a, b)
        ok = abs(actual - expected) <= tol * max(1.0, actual, expected)
        return _result("verified" if ok else "failed", c,
                       "Độ dài đoạn thẳng đúng." if ok else f"Độ dài thực tế {actual:g}, yêu cầu {expected:g}.",
                       actual_length=actual, expected_length=expected)
    except (KeyError, ValueError, TypeError) as exc:
        return _result("failed", c, str(exc))

def check_ellipse_parameters(c: dict, xyz: dict[str, Vector], tol: float) -> dict:
    """
    Kiểm tra tham số elip và chuẩn hóa theo cùng quy tắc draw_ellipse:
    - Bán trục phải hữu hạn và > 0.
    - Nếu semi_major_axis < semi_minor_axis thì hoán đổi hai trục,
      đồng thời cộng 90 độ vào rotation_angle.
    - Góc xoay phải hữu hạn.

    Schema:
      {"type": "ellipse_parameters", "semi_major_axis": 5,
       "semi_minor_axis": 3, "rotation_angle": 30}

    Không yêu cầu điểm nằm trên elip vì các tham số đã đủ để định nghĩa elip.
    """
    try:
        raw_a = c.get("semi_major_axis", c.get("a"))
        raw_b = c.get("semi_minor_axis", c.get("b"))
        raw_angle = c.get("rotation_angle", 0.0)

        def finite_number(value, field: str) -> float:
            if isinstance(value, bool):
                raise ValueError(f"{field} phải là số hữu hạn.")
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{field} phải là số hữu hạn.")
            if not isfinite(number):
                raise ValueError(f"{field} phải là số hữu hạn.")
            return number

        a = finite_number(raw_a, "semi_major_axis")
        b = finite_number(raw_b, "semi_minor_axis")
        angle = finite_number(raw_angle, "rotation_angle")

        if a <= 0:
            return _result("failed", c, "semi_major_axis phải lớn hơn 0.")
        if b <= 0:
            return _result("failed", c, "semi_minor_axis phải lớn hơn 0.")

        normalized = False
        if a < b:
            a, b = b, a
            angle += 90.0
            normalized = True

        # Tránh góc bị vô hạn sau phép cộng (đầu vào hữu hạn nhưng cực lớn).
        if not isfinite(angle):
            return _result("failed", c, "rotation_angle sau chuẩn hóa không hữu hạn.")

        return _result(
            "verified", c,
            "Tham số elip hợp lệ; đã chuẩn hóa hai bán trục." if normalized
            else "Tham số elip hợp lệ.",
            semi_major_axis=a,
            semi_minor_axis=b,
            rotation_angle=angle,
            normalized=normalized,
        )
    except (ValueError, TypeError) as exc:
        return _result("failed", c, str(exc))


class ConstraintDispatcher:
    """Chọn validator Python; nếu chưa có thì chuyển sang LLM checker.

    llm_checker là callback do ứng dụng cung cấp, nhận context dict và trả về dict.
    Hợp đồng khuyến nghị của callback:
        {"status": "satisfied" | "not_satisfied" | "uncertain",
         "reason": "...", "confidence": 0.0..1.0}

    Cũng hỗ trợ dạng {"satisfied": true/false, "reason": "..."}.
    LLM không được giả mạo kết quả Python: kết quả được đánh dấu method='llm'.
    """

    def __init__(
        self,
        tolerance: float = 1e-6,
        llm_checker: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ):
        if tolerance <= 0:
            raise ValueError("tolerance phải lớn hơn 0.")
        self.tolerance = float(tolerance)
        self.llm_checker = llm_checker
        self.validators: dict[str, Validator] = {
            "perpendicular_lines": check_perpendicular_lines,
            "parallel_lines": check_parallel_lines,
            "right_triangle": check_right_triangle,
            "isosceles_triangle": check_isosceles_triangle,
            "equilateral_triangle": check_equilateral_triangle,
            "equal_length": check_equal_length,
            "segment_length": check_segment_length,
            "perpendicular_line_plane": check_perpendicular_line_plane,
            "point_on_line": check_point_on_line,
            "point_on_segment": check_point_on_segment,
            "midpoint": check_midpoint,
            "angle_between_planes": check_angle_between_planes,
            "circle_radius": check_circle_radius,
            "ellipse_parameters": check_ellipse_parameters,
            "ellipse_axes": check_ellipse_parameters,
        }

    def register(self, constraint_type: str, validator: Validator) -> None:
        """Đăng ký validator Python mới."""
        if not constraint_type or not callable(validator):
            raise ValueError("constraint_type và validator hợp lệ là bắt buộc.")
        self.validators[constraint_type] = validator

    def set_llm_checker(
        self, checker: Callable[[dict[str, Any]], dict[str, Any]] | None
    ) -> None:
        """Gắn/thay callback kiểm tra constraint bằng LLM."""
        if checker is not None and not callable(checker):
            raise ValueError("llm_checker phải là callable hoặc None.")
        self.llm_checker = checker

    @staticmethod
    def _required_point_names(constraint: dict[str, Any]) -> set[str]:
        """Return point identifiers required by supported constraint schemas."""
        fields = (
            "points", "line", "line_1", "line_2", "plane", "plane_1", "plane_2",
            "segment", "segment_1", "segment_2", "point", "right_angle_at", "apex",
            "tangent_at", "circle", "center", "center_point", "center_name",
            "point_on_circle", "point_on_circumference", "radius_point", "vertex",
        )
        names: set[str] = set()
        def add(value: Any) -> None:
            if isinstance(value, str):
                names.add(value.removeprefix("point_"))
            elif isinstance(value, (list, tuple)):
                for part in value:
                    add(part)
        for field in fields:
            if field in constraint:
                add(constraint[field])
        return names

    def validate(self, constraint: dict[str, Any], coordinates: dict[str, Vector]) -> dict[str, Any]:
        if not isinstance(constraint, dict):
            return {
                "status": "failed", "method": "input",
                "constraint_type": None, "constraint": constraint,
                "reason": "Constraint phải là dict.",
            }

        constraint_type = constraint.get("type")
        validator = self.validators.get(constraint_type)
        if validator is not None:
            required = self._required_point_names(constraint)
            missing = sorted(name for name in required if name not in coordinates)
            if missing:
                return {
                    "status": "uncertain", "method": "python_input",
                    "constraint_type": constraint_type, "constraint": constraint,
                    "reason": "Thiếu tọa độ điểm cần thiết: " + ", ".join(missing),
                    "missing_points": missing,
                }
        if validator is None:
            # Fallback CHỈ khi không có Python validator cho loại constraint.
            return self._validate_with_llm(constraint, coordinates)

        try:
            result = validator(constraint, coordinates, self.tolerance)
            if not isinstance(result, dict) or result.get("status") not in {
                "verified", "failed", "unsupported", "uncertain"
            }:
                return {
                    "status": "uncertain", "method": "python",
                    "constraint_type": constraint_type, "constraint": constraint,
                    "reason": "Validator Python trả về kết quả không đúng schema.",
                }
            result.setdefault("method", "python")
            return result
        except Exception as exc:
            # Lỗi bên trong validator không có nghĩa là constraint sai; không fallback
            # sang LLM vì loại constraint này đã có validator Python.
            return {
                "status": "uncertain", "method": "python",
                "constraint_type": constraint_type, "constraint": constraint,
                "reason": f"Lỗi validator Python: {type(exc).__name__}: {exc}",
            }

    def _validate_with_llm(
        self, constraint: dict[str, Any], coordinates: dict[str, Vector]
    ) -> dict[str, Any]:
        base = {
            "constraint_type": constraint.get("type"),
            "constraint": constraint,
            "method": "llm",
        }
        if self.llm_checker is None:
            return {
                **base, "status": "unsupported",
                "reason": f"Chưa có Python validator cho '{constraint.get('type')}' và chưa cấu hình llm_checker.",
            }

        context = {
            "task": "evaluate_geometry_constraint",
            "constraint": constraint,
            "coordinates": coordinates,
            "instructions": [
                "Đánh giá xem tọa độ đã cho có thỏa mãn đúng constraint hay không.",
                "Không tự thay đổi tọa độ.",
                "Không đoán khi thiếu điểm, thiếu định nghĩa hoặc không đủ thông tin.",
                "Trả status là satisfied, not_satisfied hoặc uncertain.",
                "Nêu ngắn gọn lý do và confidence từ 0 đến 1 nếu có thể.",
            ],
        }
        try:
            answer = self.llm_checker(context)
        except Exception as exc:
            return {
                **base, "status": "uncertain",
                "reason": f"LLM checker gặp lỗi: {type(exc).__name__}: {exc}",
            }

        if not isinstance(answer, dict):
            return {**base, "status": "uncertain", "reason": "LLM checker phải trả về dict."}

        raw_status = str(answer.get("status", "")).strip().lower()
        if raw_status not in {"satisfied", "not_satisfied", "uncertain"}:
            if isinstance(answer.get("satisfied"), bool):
                raw_status = "satisfied" if answer["satisfied"] else "not_satisfied"
            elif isinstance(answer.get("success"), bool) and answer.get("success"):
                raw_status = "satisfied" if answer.get("is_satisfied") is True else "uncertain"
            else:
                raw_status = "uncertain"

        # Keep LLM's positive verdict distinct from a deterministic Python verification.
        mapped_status = {
            "satisfied": "llm_supported",
            "not_satisfied": "failed",
            "uncertain": "uncertain",
        }[raw_status]
        result = {
            **base,
            "status": mapped_status,
            "reason": str(answer.get("reason") or answer.get("explanation") or "LLM không cung cấp lý do."),
            "llm_status": raw_status,
        }
        confidence = answer.get("confidence")
        if isinstance(confidence, (int, float)) and 0 <= confidence <= 1:
            result["confidence"] = float(confidence)
        return result

    def validate_many(
        self, constraints: list[dict[str, Any]], coordinates: dict[str, Vector]
    ) -> list[dict[str, Any]]:
        if not isinstance(constraints, list):
            return [{
                "status": "failed", "method": "input", "constraint_type": None,
                "constraint": constraints, "reason": "constraints phải là list.",
            }]
        normalized: dict[str, Vector] = {}
        for name, values in coordinates.items():
            point_name = name.removeprefix("point_") if isinstance(name, str) else name
            if point_name in normalized and list(normalized[point_name]) != list(values):
                return [{
                    "status": "uncertain", "method": "python_input", "constraint_type": None,
                    "constraint": None,
                    "reason": f"Tọa độ mâu thuẫn giữa alias của điểm '{point_name}'.",
                }]
            normalized[point_name] = values
        return [self.validate(c, normalized) for c in constraints]