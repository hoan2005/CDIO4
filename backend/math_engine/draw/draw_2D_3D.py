import math

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


def draw_angle(input_data: dict, state: dict = None) -> dict:
    """Góc ABC; tọa độ dùng để đặt cung góc hoặc ký hiệu góc vuông."""
    input_data = require_dict(input_data)
    names = input_data.get("points")
    if not isinstance(names, list) or len(names) != 3 or len(set(names)) != 3:
        raise ValueError("Góc phải được xác định bởi ba điểm phân biệt [A, B, C].")

    raw_coordinates = get_dict(input_data, "coordinates")
    if any(name not in raw_coordinates for name in names):
        raise ValueError("Thiếu tọa độ một hoặc nhiều điểm xác định góc.")
    coordinates = {name: validate_point(raw_coordinates[name], name) for name in names}
    dimensions = {len(point) for point in coordinates.values()}
    if len(dimensions) != 1:
        raise ValueError("Ba điểm của góc phải cùng số chiều.")

    a, vertex, c = (coordinates[name] for name in names)
    first = [a[i] - vertex[i] for i in range(len(vertex))]
    second = [c[i] - vertex[i] for i in range(len(vertex))]
    first_length = math.sqrt(sum(value * value for value in first))
    second_length = math.sqrt(sum(value * value for value in second))
    if first_length == 0 or second_length == 0:
        raise ValueError("Hai tia xác định góc không được có độ dài bằng 0.")
    cosine = sum(first[i] * second[i] for i in range(len(vertex))) / (
        first_length * second_length
    )
    angle_degrees = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

    right_angle = input_data.get("right_angle", False)
    if not isinstance(right_angle, bool):
        raise ValueError("right_angle phải là boolean.")
    requested_angle = input_data.get("angle_degrees")
    if requested_angle is not None:
        if isinstance(requested_angle, bool) or not isinstance(requested_angle, (int, float)):
            raise ValueError("angle_degrees phải là số.")
        if not math.isfinite(requested_angle) or not 0 < requested_angle < 180:
            raise ValueError("angle_degrees phải nằm giữa 0 và 180.")
        if abs(angle_degrees - requested_angle) > 0.5:
            raise ValueError("Tọa độ các điểm không khớp với số đo góc được yêu cầu.")
    if right_angle and abs(angle_degrees - 90) > 0.5:
        raise ValueError("Không thể đánh dấu góc vuông vì tọa độ hiện tại không tạo góc 90 độ.")

    return {
        "id": make_id("angle"),
        "kind": "angle",
        "dimension": "2d" if len(vertex) == 2 else "3d",
        "label": input_data.get("label", f"∠{names[0]}{names[1]}{names[2]}"),
        "points": list(names),
        "coordinates": coordinates,
        "angle_degrees": float(requested_angle if requested_angle is not None else angle_degrees),
        "right_angle": right_angle,
        "marker_size": positive_number(input_data.get("marker_size", 0.35), "marker_size"),
        **common_fields(input_data),
    }


def draw_equal_segments(input_data: dict, state: dict = None) -> dict:
    """Đánh dấu các đoạn có cùng độ dài bằng cùng số vạch."""
    input_data = require_dict(input_data)
    segments = input_data.get("segments")
    if not isinstance(segments, list) or len(segments) < 2:
        raise ValueError("Cần ít nhất hai đoạn thẳng để đánh dấu bằng nhau.")
    if any(
        not isinstance(segment, list)
        or len(segment) != 2
        or segment[0] == segment[1]
        for segment in segments
    ):
        raise ValueError("Mỗi đoạn phải có đúng hai đầu mút khác tên nhau.")

    names = list(dict.fromkeys(name for segment in segments for name in segment))
    raw_coordinates = get_dict(input_data, "coordinates")
    if any(name not in raw_coordinates for name in names):
        raise ValueError("Thiếu tọa độ một hoặc nhiều đầu mút đoạn thẳng.")
    coordinates = {name: validate_point(raw_coordinates[name], name) for name in names}
    dimensions = {len(point) for point in coordinates.values()}
    if len(dimensions) != 1:
        raise ValueError("Các đoạn được đánh dấu phải cùng số chiều.")
    lengths = [
        math.sqrt(sum(
            (coordinates[end][i] - coordinates[start][i]) ** 2
            for i in range(len(coordinates[start]))
        ))
        for start, end in segments
    ]
    if any(length == 0 for length in lengths):
        raise ValueError("Đoạn thẳng được đánh dấu không được suy biến.")
    tolerance = max(lengths) * 1e-3
    if any(abs(length - lengths[0]) > tolerance for length in lengths[1:]):
        raise ValueError("Các đoạn được đánh dấu không có cùng độ dài.")

    mark_count = input_data.get("mark_count", 1)
    if isinstance(mark_count, bool) or not isinstance(mark_count, int) or not 1 <= mark_count <= 3:
        raise ValueError("mark_count phải là số nguyên từ 1 đến 3.")
    return {
        "id": make_id("equal_segments"),
        "kind": "equal_segments",
        "dimension": "2d" if next(iter(dimensions)) == 2 else "3d",
        "label": input_data.get("label", ""),
        "segments": [{"start": start, "end": end} for start, end in segments],
        "coordinates": coordinates,
        "mark_count": mark_count,
        **common_fields(input_data),
    }