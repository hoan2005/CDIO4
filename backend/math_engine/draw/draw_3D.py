import math


from math_engine.draw.Common import (
        HEX_COLOR_PATTERN, clean_vertex_names, common_fields, get_dict, make_edge, make_id,
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


def draw_polygon_3d(input_data: dict, state: dict = None) -> dict:
    """Đa giác phẳng 3D, dùng để biểu diễn tam giác/mặt phẳng hữu hạn."""
    input_data = require_dict(input_data)
    names = clean_vertex_names(input_data.get("vertices"))
    if len(names) < 3:
        raise ValueError("Đa giác 3D phải có ít nhất 3 đỉnh.")

    vertices = _vertex_coords(names, get_dict(input_data, "coordinates"))
    origin = vertices[names[0]]
    first = next(
        ([(vertices[name][i] - origin[i]) for i in range(3)]
         for name in names[1:] if vertices[name] != origin),
        None,
    )
    if first is None:
        raise ValueError("Đa giác 3D không được có các đỉnh trùng nhau.")
    normal = None
    for name in names[1:]:
        vector = [vertices[name][i] - origin[i] for i in range(3)]
        candidate = _cross(first, vector)
        if math.sqrt(sum(value * value for value in candidate)) > 1e-9:
            normal = candidate
            break
    if normal is None:
        raise ValueError("Các đỉnh đa giác 3D không được thẳng hàng.")

    normal_length = math.sqrt(sum(value * value for value in normal))
    for name in names[1:]:
        offset = [vertices[name][i] - origin[i] for i in range(3)]
        if abs(sum(normal[i] * offset[i] for i in range(3))) > 1e-7 * normal_length:
            raise ValueError("Các đỉnh đa giác 3D phải đồng phẳng.")

    edges = [make_edge(names[i], names[(i + 1) % len(names)]) for i in range(len(names))]
    style = get_dict(input_data, "style")
    fill_color = input_data.get("fill_color", style.get("fill_color"))
    if not isinstance(fill_color, str) or not HEX_COLOR_PATTERN.match(fill_color.strip()):
        fill_color = None
    return {
        "id": make_id("polygon3d"),
        "kind": "polygon",
        "dimension": "3d",
        "label": input_data.get("label", "".join(names)),
        "vertices": vertices,
        "vertex_order": names,
        "edges": edges,
        **({"fill_color": fill_color.strip()} if fill_color else {}),
        **common_fields(input_data),
    }


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

    return {
        "id": make_id("cube"),
        "kind": "cube",
        "dimension": "3d",
        "label": input_data.get("label") or "Hình lập phương",
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

    Input: center [x,y,z] và radius, hoặc coefficients [d,e,f,g]
    cho x²+y²+z²+dx+ey+fz+g=0.
    """
    input_data = require_dict(input_data)

    raw_center = input_data.get("center")
    coordinates = get_dict(input_data, "coordinates")
    center_name = raw_center.strip() if isinstance(raw_center, str) else None
    if "coefficients" in input_data:
        d, e, f, g = validate_point(input_data["coefficients"], "hệ số mặt cầu", dims=(4,))
        center = [-d / 2, -e / 2, -f / 2]
        radius_squared = sum(value * value for value in center) - g
        radius = math.sqrt(positive_number(radius_squared, "Bình phương bán kính"))
    elif isinstance(raw_center, str):
        center = coordinates.get(raw_center)
    elif raw_center is None:
        center_name = "O" if "O" in coordinates else None
        center = coordinates.get("O", [0, 0, 0])
    else:
        center = raw_center
    center = validate_point(center, "tâm", dims=(3,))
    if "coefficients" not in input_data:
        radius = positive_number(input_data.get("radius"), "Bán kính mặt cầu", default=3)

    return {
        "id": make_id("sphere"),
        "kind": "sphere",
        "dimension": "3d",
        "label": input_data.get("name", "Mặt cầu"),
        "center": center,
        **({"center_name": center_name} if center_name else {}),
        "radius": radius,
        "coordinates": {center_name: center} if center_name else (
            {} if "coefficients" in input_data else {"O": center}
        ),
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
    center = validate_point(coordinates.get("center", [0, 0, 0]), "center", dims=(3,))

    radius = positive_number(input_data.get("radius"), "Bán kính", default=3)
    if "apex" in coordinates:
        apex = validate_point(coordinates["apex"], "apex", dims=(3,))
        height = positive_number(math.dist(apex, center), "Chiều cao")
        if "height" in input_data:
            given_height = positive_number(input_data["height"], "Chiều cao")
            if not math.isclose(given_height, height, rel_tol=1e-6):
                raise ValueError("Chiều cao phải bằng khoảng cách từ tâm đáy đến đỉnh nón.")
    else:
        height = positive_number(input_data.get("height"), "Chiều cao", default=5)
        apex = validate_point([center[0], center[1], center[2] + height], "apex", dims=(3,))

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


def draw_cylinder(input_data: dict, state: dict = None) -> dict:
    """Hình trụ tròn xoay qua hai tâm đáy, mặc định trục song song Oz."""
    input_data = require_dict(input_data)
    base = validate_point(input_data.get("base_center", [0, 0, 0]), "tâm đáy dưới", dims=(3,))
    radius = positive_number(input_data.get("radius"), "Bán kính hình trụ")
    if "top_center" in input_data:
        top = validate_point(input_data["top_center"], "tâm đáy trên", dims=(3,))
        height = positive_number(math.dist(base, top), "Chiều cao")
        if "height" in input_data and not math.isclose(
            height, positive_number(input_data["height"], "Chiều cao"), rel_tol=1e-6
        ):
            raise ValueError("Chiều cao phải bằng khoảng cách giữa hai tâm đáy.")
    else:
        height = positive_number(input_data.get("height"), "Chiều cao", default=5)
        top = validate_point([base[0], base[1], base[2] + height], "tâm đáy trên", dims=(3,))
    return {
        "id": make_id("cylinder"), "kind": "cylinder", "dimension": "3d",
        "label": input_data.get("name") or "Hình trụ",
        "base_center": base, "top_center": top, "radius": radius, "height": height,
        **common_fields(input_data, style_default_color="#0f766e"),
    }
