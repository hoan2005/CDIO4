from math_engine.draw.Common import (
        clean_vertex_names, common_fields, get_dict, make_edge, make_id,
        positive_number, require_dict, validate_point,
    )


def draw_line(input_data: dict, state: dict = None) -> dict:
    """
    Đường thẳng đi qua 2 điểm (2D hoặc 3D, tự suy ra từ số tọa độ).

    Input:
    {
        "points": ["A", "B"],
        "coordinates": {"A": [0, 0, 0], "B": [4, 0, 0]},
        "style": {"color": "#64748b", "line_style": "solid"},
        "coordinate_control": {}, "constraints": []
    }
    """
    input_data = require_dict(input_data)

    names = input_data.get("points")
    if not isinstance(names, list) or len(names) != 2:
        raise ValueError("Đường thẳng phải được xác định bởi đúng 2 điểm.")

    a_name, b_name = names
    if a_name == b_name:
        raise ValueError("Hai điểm xác định đường thẳng phải khác tên nhau.")

    coordinates = get_dict(input_data, "coordinates")
    if a_name not in coordinates or b_name not in coordinates:
        raise ValueError(f"Thiếu tọa độ của điểm {a_name} hoặc {b_name}.")

    a = validate_point(coordinates[a_name], a_name)
    b = validate_point(coordinates[b_name], b_name)

    if len(a) != len(b):
        raise ValueError(
            f"Hai điểm phải cùng số chiều: {a_name} có {len(a)}D, {b_name} có {len(b)}D."
        )
    if a == b:
        raise ValueError(
            f"Hai điểm {a_name} và {b_name} trùng tọa độ, không thể xác định đường thẳng."
        )

    return {
        "id": make_id("line"),
        "kind": "line",
        "dimension": "2d" if len(a) == 2 else "3d",
        "label": f"Đường thẳng {a_name}{b_name}",

        # Lưu tham chiếu đến hai điểm
        "point_names": [a_name, b_name],

        # Vẫn lưu tọa độ để Canvas vẽ ban đầu
        "points": [a, b],

        **common_fields(input_data),
    }


def draw_point(input_data: dict, state: dict = None) -> dict:
    """
    Điểm 2D hoặc 3D.

    Input:
    {
        "name": "M",
        "coordinates": {"M": [3, 1.732, 0]},
        "style": {"color": "#ef4444"},
        "coordinate_control": {...}, "constraints": [...]
    }
    """
    input_data = require_dict(input_data)

    name = input_data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Thiếu tên điểm hợp lệ.")
    name = name.strip()

    coordinates = get_dict(input_data, "coordinates")
    if name not in coordinates:
        raise ValueError(f"Không tìm thấy tọa độ của điểm {name}.")

    position = validate_point(coordinates[name], name)

    return {
        "id": f"point_{name}",  # ổn định để frontend cập nhật/di chuyển điểm
        "kind": "point",
        "dimension": "2d" if len(position) == 2 else "3d",
        "label": name,
        "position": position,
        # điểm mặc định màu đen để nổi bật trên đường/hình
        **common_fields(input_data, style_default_color="#0f172a"),
    }


def draw_plane(input_data: dict, state: dict = None) -> dict:
    """
    Mặt phẳng cho Canvas 2D hoặc 3D.

    Input: dimension, name, role, style, coordinates (origin + các dữ liệu khác),
    coordinate_control, constraints.
    """
    input_data = require_dict(input_data)

    dimension = str(input_data.get("dimension", "3d")).lower()
    if dimension not in ("2d", "3d"):
        raise ValueError("dimension phải là '2d' hoặc '3d'.")

    dims = 2 if dimension == "2d" else 3
    coordinates = get_dict(input_data, "coordinates")

    origin = coordinates.get("origin", [0.0] * dims)
    origin = validate_point(origin, "origin", dims=(dims,))

    return {
        "id": make_id("plane"),
        "kind": "plane",
        "dimension": dimension,
        "label": input_data.get("name", "Mặt phẳng"),
        "coordinates": {**coordinates, "origin": origin},
        **common_fields(input_data, style_default_color="#2563eb"),
    }