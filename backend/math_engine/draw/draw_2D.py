import math
import re
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


from math_engine.draw.Common import (
        clean_vertex_names, common_fields, get_dict, is_real, make_edge, make_id,
        positive_number, require_dict, validate_point,
    )


_SAFE_EXPR = re.compile(r"^[0-9A-Za-z_+\-*/^().,\s]+$")
_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)


def draw_polygon_2d(input_data: dict, state: dict = None) -> dict[str, Any]:
    """
    Đa giác 2D.

    Input: vertices ["A","B","C","D"], coordinates {"A": [x, y], ...},
    role, style, coordinate_control, constraints.
    """
    input_data = require_dict(input_data)

    vertices = clean_vertex_names(input_data.get("vertices"))
    if len(vertices) < 3:
        raise ValueError("Đa giác phải có ít nhất 3 đỉnh.")

    raw = get_dict(input_data, "coordinates")
    coordinates = {}
    for v in vertices:
        if v not in raw:
            raise ValueError(f"Thiếu tọa độ đỉnh {v}.")
        coordinates[v] = validate_point(raw[v], v, dims=(2,))

    edges = [
        make_edge(v, vertices[(i + 1) % len(vertices)])
        for i, v in enumerate(vertices)
    ]

    return {
        "id": make_id("polygon"),
        "kind": "polygon",
        "dimension": "2d",
        "label": "".join(vertices),
        "vertices": vertices,
        "coordinates": coordinates,
        "edges": edges,
        **common_fields(input_data),
    }


def draw_function(input_data: dict, state: dict = None) -> dict[str, Any]:
    """
    Đồ thị hàm số y = f(x).

    Input: expression "x**2", x_range [-5, 5], num_points (mặc định 200),
    role, style, constraints.
    """
    input_data = require_dict(input_data)

    expression = input_data.get("expression")
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expression phải là chuỗi không rỗng.")
    # Chặn ký tự lạ / dunder trước khi đưa vào sympy (parse_expr dùng eval).
    if len(expression) > 200 or "__" in expression or not _SAFE_EXPR.match(expression):
        raise ValueError("Biểu thức hàm số chứa ký tự không được phép.")

    x = sp.Symbol("x")
    try:
        expr = parse_expr(
            expression,
            local_dict={"x": x},
            transformations=_TRANSFORMS,
        )
        if not expr.free_symbols.issubset({x}):
            raise ValueError("Hàm số chỉ được sử dụng biến x.")
        func = sp.lambdify(x, expr, modules=["math"])
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Biểu thức hàm số không hợp lệ: {exc}") from exc

    x_range = input_data.get("x_range", [-5.0, 5.0])
    if not isinstance(x_range, (list, tuple)) or len(x_range) != 2:
        raise ValueError("x_range phải có dạng [x_min, x_max].")
    if not all(is_real(v) for v in x_range):
        raise ValueError("Giới hạn x phải là số hữu hạn.")
    x_min, x_max = x_range
    if x_min >= x_max:
        raise ValueError("x_min phải nhỏ hơn x_max.")

    num_points = input_data.get("num_points", 200)
    if (
        isinstance(num_points, bool)
        or not isinstance(num_points, int)
        or not 2 <= num_points <= 5000
    ):
        raise ValueError("num_points phải nằm trong khoảng 2–5000.")

    points = []
    for i in range(num_points + 1):
        xv = x_min + (x_max - x_min) * i / num_points
        try:
            yv = float(func(xv))
        except (ValueError, OverflowError, ZeroDivisionError, TypeError):
            continue  # ngoài miền xác định / kết quả phức
        if math.isfinite(yv):
            points.append([xv, yv])

    if len(points) < 2:
        raise ValueError("Không đủ điểm hợp lệ để vẽ đồ thị.")

    return {
        "id": make_id("function"),
        "kind": "function",
        "dimension": "2d",
        "label": str(expr),
        "expression": expression,
        "points": points,
        **common_fields(input_data, style_default_color="#2563eb"),
    }

def _center_2d(input_data: dict, state: dict = None) -> list:
    """Lấy tọa độ tâm từ tọa độ trực tiếp hoặc tên điểm trong coordinates."""
    center = input_data.get("center")
    coordinates = get_dict(input_data, "coordinates")

    if center is None:
        center = coordinates.get("center", [0, 0])

    # Nếu center là tên điểm, ví dụ "O", tra tọa độ tương ứng
    elif isinstance(center, str):
        center = coordinates.get(center)

    return validate_point(center, "tâm", dims=(2,))

def draw_circle(input_data: dict, state: dict = None) -> dict:
    """
    Đường tròn.

    Input: center [x, y], radius, role, style, coordinate_control, constraints.
    """
    input_data = require_dict(input_data)

    center = _center_2d(input_data)
    radius = positive_number(input_data.get("radius"), "Bán kính")
    cx, cy = center

    n = 120
    points = [
        [
            round(cx + radius * math.cos(2 * math.pi * i / n), 6),
            round(cy + radius * math.sin(2 * math.pi * i / n), 6),
        ]
        for i in range(n + 1)  # lặp điểm đầu ở cuối để khép kín
    ]

    return {
        "id": make_id("circle"),
        "kind": "circle",
        "dimension": "2d",
        "label": "Đường tròn",
        "center": center,
        "radius": radius,
        "coordinates": {"center": center},
        "points": points,
        **common_fields(input_data),
    }


def draw_ellipse(input_data: dict, state: dict = None) -> dict:
    """
    Elip.

    Input: center [x, y], semi_major_axis, semi_minor_axis,
    rotation_angle (độ), role, style, coordinate_control, constraints.
    Nếu bán trục lớn < bán trục nhỏ thì tự hoán đổi và xoay thêm 90°.
    """
    input_data = require_dict(input_data)

    center = _center_2d(input_data)
    a = positive_number(input_data.get("semi_major_axis"), "semi_major_axis", default=5.0)
    b = positive_number(input_data.get("semi_minor_axis"), "semi_minor_axis", default=3.0)

    angle = input_data.get("rotation_angle", 0)
    if not is_real(angle):
        raise ValueError("rotation_angle phải là số hữu hạn.")
    angle = float(angle)

    if a < b:
        a, b = b, a
        angle += 90.0

    return {
        "id": make_id("ellipse"),
        "kind": "ellipse",
        "dimension": "2d",
        "label": "Elip",
        "center": center,
        "semi_major_axis": a,
        "semi_minor_axis": b,
        "rotation_angle": angle,
        "coordinates": {"center": center},
        **common_fields(input_data, style_default_color="#2563eb"),
    }


def draw_hyperbola(input_data: dict, state: dict = None) -> dict:
    """
    Hypebol.

    Input: a (bán trục thực), b (bán trục ảo), center [x, y] hoặc
    coordinates.center, orientation ("horizontal"|"vertical"),
    role, style, coordinate_control, constraints.
    """
    input_data = require_dict(input_data)

    a = positive_number(input_data.get("a"), "a", default=4)
    b = positive_number(input_data.get("b"), "b", default=3)
    center = _center_2d(input_data)

    orientation = input_data.get("orientation", "horizontal")
    if orientation not in ("horizontal", "vertical"):
        raise ValueError("orientation phải là 'horizontal' hoặc 'vertical'.")

    return {
        "id": make_id("hyperbola"),
        "kind": "hyperbola",
        "dimension": "2d",
        "label": "Hypebol",
        "center": center,
        "a": a,
        "b": b,
        "orientation": orientation,
        "coordinates": {"center": center},
        **common_fields(input_data, style_default_color="#2563eb"),
    }