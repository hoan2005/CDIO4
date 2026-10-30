"""
Tiện ích dùng chung cho mọi hàm draw_*.

Schema thống nhất của một Canvas Object:
{
    "id": "<kind>_xxxxxxxx",
    "kind": "...",
    "dimension": "2d" | "3d",
    "label": "...",
    "role": "original",
    "style": {"color": "#...", "line_style": "solid"},
    "color": "#...",          # bản sao phẳng của style.color (tương thích frontend cũ)
    "line_style": "solid",    # bản sao phẳng của style.line_style
    "coordinate_control": {},
    "constraints": [],
    ... các trường riêng của từng loại hình
}
Cạnh luôn có dạng {"start": "A", "end": "B"} (có thể thêm "type").
"""

import math
import re
import uuid

DEFAULT_COLOR = "#64748b"
DEFAULT_LINE_STYLE = "solid"
VALID_LINE_STYLES = {"solid", "dashed", "dotted"}
HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


# ---------------------------------------------------------------- ID
def make_id(prefix: str) -> str:
    """Tạo ID duy nhất dạng '<prefix>_xxxxxxxx'."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------- style
def resolve_style(
    style: dict = None,
    default_color: str = DEFAULT_COLOR,
    default_line_style: str = DEFAULT_LINE_STYLE,
) -> dict:
    """Chuẩn hóa style thành {"color", "line_style"}; giá trị sai rơi về mặc định."""
    color = default_color
    line_style = default_line_style

    if isinstance(style, dict):
        raw_color = style.get("color")
        if isinstance(raw_color, str) and HEX_COLOR_PATTERN.match(raw_color.strip()):
            color = raw_color.strip()

        raw_ls = style.get("line_style")
        if isinstance(raw_ls, str) and raw_ls.strip().lower() in VALID_LINE_STYLES:
            line_style = raw_ls.strip().lower()

    return {"color": color, "line_style": line_style}


def style_fields(style: dict = None, default_color: str = DEFAULT_COLOR) -> dict:
    """
    Trả về các trường style để gộp vào object:
    style lồng nhau + color/line_style phẳng.
    """
    s = resolve_style(style, default_color=default_color)
    return {"style": s, "color": s["color"], "line_style": s["line_style"]}


# ---------------------------------------------------------------- số / điểm
def is_real(value) -> bool:
    """Số thực hữu hạn, không phải bool."""
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def validate_point(point, name: str, dims=(2, 3)) -> list:
    """Kiểm tra tọa độ và trả về list float."""
    if not isinstance(point, (list, tuple)):
        raise ValueError(f"Tọa độ {name} phải là list hoặc tuple.")
    if len(point) not in dims:
        want = " hoặc ".join(str(d) for d in dims)
        raise ValueError(f"{name} phải có {want} tọa độ, nhận được {len(point)}.")
    if not all(is_real(v) for v in point):
        raise ValueError(f"Tọa độ {name} phải là số hữu hạn.")
    return [float(v) for v in point]


def positive_number(value, name: str, default=None) -> float:
    """Số hữu hạn > 0 (dùng cho bán kính, bán trục, chiều cao...)."""
    if value is None:
        value = default
    if not is_real(value) or value <= 0:
        raise ValueError(f"{name} phải là số hữu hạn lớn hơn 0.")
    return float(value)


# ---------------------------------------------------------------- trường chung
def require_dict(input_data) -> dict:
    if not isinstance(input_data, dict):
        raise ValueError("input_data phải là dict.")
    return input_data


def get_list(input_data: dict, key: str) -> list:
    value = input_data.get(key) or []
    if not isinstance(value, list):
        raise ValueError(f"{key} phải là list.")
    return value


def get_dict(input_data: dict, key: str) -> dict:
    value = input_data.get(key) or {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} phải là dict.")
    return value


def common_fields(input_data: dict, style_default_color: str = DEFAULT_COLOR) -> dict:
    """role, style, coordinate_control, constraints."""
    return {
        "role": input_data.get("role", "original"),
        **style_fields(input_data.get("style"), default_color=style_default_color),
        "coordinate_control": get_dict(input_data, "coordinate_control"),
        "constraints": get_list(input_data, "constraints"),
    }


def make_edge(start: str, end: str, edge_type: str = None) -> dict:
    edge = {"start": start, "end": end}
    if edge_type:
        edge["type"] = edge_type
    return edge


def clean_vertex_names(vertices) -> list:
    if not isinstance(vertices, list) or not vertices:
        raise ValueError("vertices phải là list không rỗng.")
    if not all(isinstance(v, str) and v.strip() for v in vertices):
        raise ValueError("Tên đỉnh phải là chuỗi không rỗng.")
    if len(set(vertices)) != len(vertices):
        raise ValueError("Danh sách đỉnh không được trùng nhau.")
    return list(vertices)