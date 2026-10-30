import uuid
import sympy as sp


def TaoPhuongTrinh(params: dict) -> dict:
    eq_str = params.get("equation")
    color = params.get("color", "blue")
    
    if eq_str and isinstance(eq_str, str):
        # 1. Xử lý trường hợp chuỗi dạng "y = x**4" hoặc "x**4 = y"
        if "=" in eq_str and not eq_str.startswith("Eq"):
            parts = eq_str.split("=")
            # Lấy phần không chứa 'y'
            eq_str = parts[1].strip() if "y" in parts[0] else parts[0].strip()
            
        try:
            # 2. Parse chuỗi thành đối tượng SymPy
            expr = sp.sympify(eq_str)
            
            # 3. Xử lý trường hợp đối tượng SymPy dạng Eq(y, x**3)
            if isinstance(expr, sp.Equality):
                # Kiểm tra nếu vế trái (lhs) là y thì lấy vế phải (rhs) và ngược lại
                if expr.lhs == sp.Symbol('y'):
                    expr = expr.rhs
                elif expr.rhs == sp.Symbol('y'):
                    expr = expr.lhs
            
            # Chuyển về dạng chuỗi Python chuẩn (chỉ còn vế phải, ví dụ: "x**3")
            eq_str = str(expr)
        except (sp.SympifyError, TypeError):
            pass

    graph_obj = {
        "id": f"PT_{uuid.uuid4().hex[:8]}",
        "label": f"y={eq_str}",
        "type": "phuongtrinh",
        "equation": eq_str,
        "color": color,
    }
    return graph_obj


def TaoTiepTuyen(phuongtrinh: dict, at_x: float):
    # FIX: sp.Symbols (viết hoa) không tồn tại trong sympy -> dùng sp.symbols
    x = sp.symbols('x')

    f_x = sp.sympify(phuongtrinh)  # "x**2 + 2" -> biểu thức toán
    if isinstance(f_x, sp.Equality):
        f_x = f_x.rhs
    # Tính tung độ tiếp điểm
    at_y = float(f_x.subs(x, at_x))

    # Tính đạo hàm f'(x) để lấy hệ số góc tiếp tuyến
    f_prime = sp.diff(f_x, x)
    k = float(f_prime.subs(x, at_x))

    # Tự sinh phương trình tiếp tuyến: y = k*x + (at_y - k*at_x)
    tangent_eq = f"y = {k}*x + {at_y - k * at_x}"

    point = {
        "id": f"P_{uuid.uuid4().hex[:8]}",
        "label":f"P_({at_x}, {at_y})",
        "type": "point",
        "coordinates": [at_x, at_y],
        "color": "blue",
    }

    tangent = {
        "id": f"Line_{uuid.uuid4().hex[:8]}",
        "label":tangent_eq,# phương trình để tôi chú thích ví y=x+1
        "type": "line",
        "paramater": {"a":k,"b":-1,"c":at_y - k * at_x},
        "color": "red",
    }
    print("tangent",tangent)
    return point, tangent
def TaoDiem(params: dict,phuongtrinh) -> dict:
    coordinates = params.get("coordinates", [])
    color = params.get("color", "black")
    
    # Chuẩn hóa tọa độ về dạng chuỗi Python thuần túy hoặc số thực (float)
    cleaned_coords = []
    for coord in coordinates:
        try:
            # Parse qua sympy để xử lý các biểu thức như "1/2", "sqrt(3)",...
            expr = sp.sympify(coord)
            
            # Nếu là số nguyên hoặc số thực đơn giản thì giữ nguyên, 
            # nếu là biểu thức phức tạp thì chuyển thành chuỗi chuẩn Python (hoặc dùng .evalf() nếu muốn dạng số thập phân)
            if expr.is_number:
                # Nếu muốn trả về số thập phân cho frontend dễ vẽ, hãy dùng: float(expr.evalf())
                # Ở đây mình giữ nguyên dạng chuỗi/số tối giản của SymPy (ví dụ: "1/2" -> 0.5 hoặc giữ phân số)
                cleaned_coords.append(float(expr.evalf()) if not expr.is_Integer else int(expr))
            else:
                cleaned_coords.append(str(expr))
        except (sp.SympifyError, TypeError):
            # Nếu không parse được thì giữ nguyên giá trị gốc
            cleaned_coords.append(coord)

    # Xác định loại điểm (2D hay 3D) dựa trên số lượng phần tử trong mảng tọa độ
    point_type = "diem_3d" if len(cleaned_coords) == 3 else "diem_2d"
    equation_str = phuongtrinh

# Chuyển chuỗi thành đối tượng SymPy
    expr = sp.sympify(equation_str)

    # Lấy vế phải (Right-Hand Side)
    right_side = expr.rhs



    # Nếu muốn chuyển ngược lại thành chuỗi "x**2"
    right_side_str = str(right_side)
   
        # Tạo object trả về cho frontend
    graph_obj = {
        "id": f"P_{uuid.uuid4().hex[:8]}",
        "label":f"P_{cleaned_coords}",  # Dùng name làm ID, nếu không có thì tự sinh
        "type": point_type,
        "coordinates": cleaned_coords,
        "relations":right_side_str,
        "color": color,
    }
    return graph_obj