import math
from typing import Any

from math_engine.draw.Common import (
    clean_vertex_names, common_fields, get_dict, get_list, make_edge, make_id,
    positive_number, require_dict, validate_point,
)
from math_engine.draw.function_graph import draw_function


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

    raw_center = input_data.get("center")
    center_name = raw_center.strip() if isinstance(raw_center, str) else None
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
        **({"center_name": center_name} if center_name else {}),
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


def draw_histogram(input_data: dict, state: dict = None) -> dict:
    """Biểu đồ tần số cho mẫu số liệu ghép nhóm."""
    input_data = require_dict(input_data)
    raw_groups = get_list(input_data, "groups")
    if not 1 <= len(raw_groups) <= 40:
        raise ValueError("Biểu đồ cần từ 1 đến 40 nhóm.")
    groups = []
    for raw in raw_groups:
        lo, hi, frequency = validate_point(raw, "nhóm [cận dưới, cận trên, tần số]", dims=(3,))
        if hi <= lo or not math.isfinite(hi - lo) or frequency < 0 or not frequency.is_integer():
            raise ValueError("Cận nhóm phải tăng và tần số phải là số nguyên không âm.")
        groups.append((lo, hi, int(frequency)))
    groups.sort()
    if any(left[1] > right[0] for left, right in zip(groups, groups[1:])):
        raise ValueError("Các khoảng ghép nhóm không được chồng lên nhau.")
    if not any(group[2] for group in groups):
        raise ValueError("Cần ít nhất một nhóm có tần số dương.")

    first_width = groups[0][1] - groups[0][0]
    density = any(not math.isclose(hi - lo, first_width, rel_tol=1e-9) for lo, hi, _ in groups)
    bars = []
    for lo, hi, frequency in groups:
        height = frequency / (hi - lo) if density else float(frequency)
        if not math.isfinite(height):
            raise ValueError("Chiều cao cột vượt phạm vi vẽ.")
        bars.append({"lower": lo, "upper": hi, "frequency": frequency, "height": height})
    return {
        "id": make_id("histogram"), "kind": "histogram", "dimension": "2d",
        "label": input_data.get("name") or ("Mật độ tần số" if density else "Biểu đồ tần số"),
        "y_label": "Mật độ tần số" if density else "Tần số",
        "bars": bars,
        **common_fields(input_data, style_default_color="#2563eb"),
    }
