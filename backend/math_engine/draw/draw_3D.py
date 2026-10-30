import math
from math import dist


from math_engine.draw.Common import (
        clean_vertex_names, common_fields, get_dict, make_edge, make_id,
        positive_number, require_dict, validate_point,
    )



def _vertex_coords(names: list, coordinates: dict) -> dict:
    """Kiểm tra và chuẩn hóa tọa độ 3D cho danh sách đỉnh."""
    result = {}
    for name in names:
        if name not in coordinates:
            raise ValueError(f"Thiếu tọa độ đỉnh {name}.")
        result[name] = validate_point(coordinates[name], f"đỉnh {name}", dims=(3,))
    return result


def _cross(u, v):
    return [
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    ]


def _sub(p, q):
    return [p[i] - q[i] for i in range(3)]


def draw_cube(input_data: dict, state: dict = None) -> dict:
    """
    Hình lập phương (8 đỉnh phân biệt).

    Input: vertices [8 tên], coordinates {tên: [x, y, z]}, role, style, ...
    """
    input_data = require_dict(input_data)

    names = clean_vertex_names(input_data.get("vertices"))
    if len(names) != 8:
        raise ValueError("Hình lập phương phải có 8 đỉnh phân biệt.")

    vertices = _vertex_coords(names, get_dict(input_data, "coordinates"))

    if "A" in vertices and "B" in vertices:
        side_label = f"{dist(vertices['A'], vertices['B']):g}"
    else:
        side_label = "chưa xác định"

    return {
        "id": make_id("cube"),
        "kind": "cube",
        "dimension": "3d",
        "label": f"Hình lập phương cạnh {side_label}",
        "vertices": vertices,
        **common_fields(input_data),
    }


def draw_pyramid(input_data: dict, state: dict = None) -> dict:
    """
    Hình chóp (đỉnh chóp là đỉnh duy nhất nằm ngoài base_order).

    Input: vertices ["S","A","B","C"], base_order ["A","B","C"],
    coordinates, label (tùy chọn), role, style, ...
    """
    input_data = require_dict(input_data)

    names = clean_vertex_names(input_data.get("vertices"))
    base_order = input_data.get("base_order")

    if len(names) < 4:
        raise ValueError("Hình chóp cần ít nhất 4 đỉnh.")
    if not isinstance(base_order, list) or len(base_order) < 3:
        raise ValueError("base_order phải có ít nhất 3 đỉnh.")
    if len(set(base_order)) != len(base_order):
        raise ValueError("base_order không được chứa đỉnh trùng.")
    if not set(base_order).issubset(names):
        raise ValueError("Đỉnh đáy phải thuộc danh sách vertices.")

    apex_candidates = [n for n in names if n not in base_order]
    if len(apex_candidates) != 1:
        raise ValueError("Hình chóp phải có đúng một đỉnh nằm ngoài đáy.")
    apex_name = apex_candidates[0]

    vertices = _vertex_coords(names, get_dict(input_data, "coordinates"))

    # 3 đỉnh đầu của đáy không thẳng hàng
    A, B, C = (vertices[base_order[i]] for i in range(3))
    normal = _cross(_sub(B, A), _sub(C, A))
    if math.sqrt(sum(v * v for v in normal)) < 1e-9:
        raise ValueError("Ba đỉnh đầu tiên của đáy thẳng hàng.")

    # đỉnh chóp không nằm trên mặt phẳng đáy
    AS = _sub(vertices[apex_name], A)
    if abs(sum(normal[i] * AS[i] for i in range(3))) < 1e-9:
        raise ValueError(f"Đỉnh chóp {apex_name} nằm trên mặt phẳng đáy.")

    n = len(base_order)
    edges = [make_edge(base_order[i], base_order[(i + 1) % n], "base") for i in range(n)]
    edges += [make_edge(apex_name, v, "lateral") for v in base_order]

    faces = [list(base_order)]
    faces += [[apex_name, base_order[i], base_order[(i + 1) % n]] for i in range(n)]

    return {
        "id": make_id("pyramid"),
        "kind": "pyramid",
        "dimension": "3d",
        "label": input_data.get("label", f"Hình chóp {apex_name}"),
        "vertices": vertices,
        "base_order": list(base_order),
        "apex_name": apex_name,
        "edges": edges,
        "faces": faces,
        **common_fields(input_data),
    }


def draw_prism(input_data: dict, state: dict = None) -> dict:
    """
    Lăng trụ. Đỉnh mặt trên là các đỉnh không thuộc base_order, theo thứ tự
    tương ứng với base_order (A→A', B→B', ...).

    Input: vertices ["A","B","C","A'","B'","C'"], base_order ["A","B","C"],
    coordinates, role, style, ...
    """
    input_data = require_dict(input_data)

    names = clean_vertex_names(input_data.get("vertices"))
    base_order = input_data.get("base_order")

    if not isinstance(base_order, list) or len(base_order) < 3:
        raise ValueError("Đáy lăng trụ phải có ít nhất 3 đỉnh.")
    if len(set(base_order)) != len(base_order):
        raise ValueError("base_order không được chứa đỉnh trùng.")
    if not set(base_order).issubset(names):
        raise ValueError("Đỉnh đáy phải thuộc danh sách vertices.")

    top_vertices = [n for n in names if n not in base_order]
    if len(top_vertices) != len(base_order):
        raise ValueError("Số đỉnh mặt trên phải bằng số đỉnh đáy.")

    vertices = _vertex_coords(names, get_dict(input_data, "coordinates"))

    n = len(base_order)
    edges = [make_edge(base_order[i], base_order[(i + 1) % n], "base") for i in range(n)]
    edges += [make_edge(base_order[i], top_vertices[i], "lateral") for i in range(n)]
    edges += [make_edge(top_vertices[i], top_vertices[(i + 1) % n], "top") for i in range(n)]

    faces = [list(base_order), list(top_vertices)]
    faces += [
        [base_order[i], base_order[(i + 1) % n], top_vertices[(i + 1) % n], top_vertices[i]]
        for i in range(n)
    ]

    return {
        "id": make_id("prism"),
        "kind": "prism",
        "dimension": "3d",
        "label": input_data.get("label", "Lăng trụ"),
        "vertices": vertices,            # dict tên -> [x, y, z], giống cube/pyramid
        "coordinates": vertices,         # giữ để tương thích frontend cũ
        "base_order": list(base_order),
        "top_order": top_vertices,
        "edges": edges,
        "faces": faces,
        **common_fields(input_data),
    }


def draw_sphere(input_data: dict, state: dict = None) -> dict:
    """
    Mặt cầu.

    Input: center [x, y, z], radius, role, style, coordinate_control, constraints.
    """
    input_data = require_dict(input_data)

    center = input_data.get("center")
    if center is None:
        center = get_dict(input_data, "coordinates").get("O", [0, 0, 0])
    center = validate_point(center, "tâm", dims=(3,))
    radius = positive_number(input_data.get("radius"), "Bán kính mặt cầu", default=3)

    return {
        "id": make_id("sphere"),
        "kind": "sphere",
        "dimension": "3d",
        "label": input_data.get("name", "Mặt cầu"),
        "center": center,
        "radius": radius,
        "coordinates": {"O": center},
        **common_fields(input_data, style_default_color="#2563eb"),
    }


def draw_cone(input_data: dict, state: dict = None) -> dict:
    """
    Hình nón.

    Input: coordinates {"apex": [x,y,z], "center": [x,y,z]}, radius, height,
    role, style, coordinate_control, constraints.
    """
    input_data = require_dict(input_data)

    coordinates = get_dict(input_data, "coordinates")
    apex = validate_point(coordinates.get("apex", [0, 0, 5]), "apex", dims=(3,))
    center = validate_point(coordinates.get("center", [0, 0, 0]), "center", dims=(3,))

    radius = positive_number(input_data.get("radius"), "Bán kính", default=3)
    height = positive_number(input_data.get("height"), "Chiều cao", default=5)

    return {
        "id": make_id("cone"),
        "kind": "cone",
        "dimension": "3d",
        "label": input_data.get("name", "Hình nón"),
        "coordinates": {"apex": apex, "center": center},
        "radius": radius,
        "height": height,
        **common_fields(input_data, style_default_color="#2563eb"),
    }