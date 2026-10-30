"""
daiso/thamso.py
----------------
Module xử lý dạng bài "tìm tham số m" cho ĐA THỨC BẬC BẤT KỲ theo x (bậc 1,
2, 3, 4, ...). Chưa hỗ trợ phương trình siêu việt (sin, log, e^x trộn x).

Triết lý: không code riêng theo từng bậc cụ thể, mà code 1 quy trình tổng
quát dựa trên LOẠI điều kiện + hệ số đa thức (lấy qua sp.Poly), tái sử dụng
được cho mọi đa thức bậc n. Đây chính là cách CAS hoạt động.

Các loại điều kiện hỗ trợ (dieu_kien_loai):
    - "nghiem_cho_truoc": PT nhận x = gia_tri làm nghiệm
        -> thế trực tiếp, TỔNG QUÁT cho mọi bậc (kể cả siêu việt).
    - "nghiem_kep":   PT có nghiệm bội (kép)
        -> discriminant(f, x) = 0, TỔNG QUÁT cho mọi bậc nhờ
           sp.discriminant (không chỉ b²-4ac của riêng bậc 2).
    - "vo_nghiem" / "co_nghiem": PT (vô nghiệm thực) / (có nghiệm thực)
        -> bậc lẻ: luôn có nghiệm thực (định lý giá trị trung gian) với
           MỌI m -> trả lời "mọi m" / "không tồn tại m" ngay, không cần tính.
        -> bậc 2: dùng dấu Δ = b²-4ac như cũ.
        -> bậc chẵn >= 4: cần kỹ thuật nâng cao hơn (dãy Sturm / CAD) để
           đếm số nghiệm thực theo tham số -> hiện CHƯA hỗ trợ, báo lỗi rõ
           ràng thay vì trả kết quả sai.
    - "vi_et_tong": tổng TẤT CẢ nghiệm = gia_tri
        -> tổng quát mọi bậc: -a_{n-1}/a_n = gia_tri (công thức Vi-ét tổng quát).
    - "vi_et_tich": tích TẤT CẢ nghiệm = gia_tri
        -> tổng quát mọi bậc: (-1)^n * a_0/a_n = gia_tri.
    - "vi_et_trai_dau" / "vi_et_cung_dau": 2 nghiệm trái/cùng dấu
        -> CHỈ có nghĩa rõ ràng khi đúng 2 nghiệm (bậc 2); bậc khác báo lỗi.
"""

from __future__ import annotations

from typing import Any, Dict, List

import sympy as sp

x, m = sp.symbols('x m', real=True)

_DIEU_KIEN_HOP_LE = {
    "nghiem_cho_truoc",
    "nghiem_kep",
    "vo_nghiem",
    "co_nghiem",
    "vi_et_tong",
    "vi_et_tich",
    "vi_et_trai_dau",
    "vi_et_cung_dau",
}


def _to_list_str(ket_qua) -> List[str]:
    """Chuẩn hóa kết quả sp.solve (có thể là list, set rỗng, ...) về list[str]."""
    if ket_qua is None:
        return []
    if isinstance(ket_qua, (list, tuple, set)):
        return [str(v) for v in ket_qua]
    return [str(ket_qua)]


def _giai_phuong_trinh_theo_m(ve_trai, ve_phai) -> Dict[str, Any]:
    """
    Giải phương trình ve_trai = ve_phai theo m, có xử lý edge-case khi
    phương trình KHÔNG chứa m (sp.solve trả [] mơ hồ trong cả 2 trường hợp
    "luôn đúng" lẫn "luôn sai" -> phải tự phân biệt bằng simplify).
    """
    hieu = sp.simplify(ve_trai - ve_phai)

    if m not in hieu.free_symbols:
        # Phương trình không phụ thuộc m -> hoặc đúng với MỌI m, hoặc sai với mọi m.
        if hieu == 0:
            return {"ket_qua": "mọi giá trị m", "loai_ket_qua": "all_m"}
        return {"ket_qua": "không tồn tại m nào thỏa mãn", "loai_ket_qua": "no_m"}

    ket_qua = sp.solve(sp.Eq(ve_trai, ve_phai), m)
    return {"ket_qua": _to_list_str(ket_qua), "loai_ket_qua": "discrete"}


def GiaiThamSo(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Giải bài toán tìm tham số m dựa trên điều kiện cho trước.
    Hỗ trợ ĐA THỨC theo x bậc bất kỳ (1, 2, 3, 4, ...).

    params = {
        "equation": "x**3 + m*x + 1",   # vế trái PT (đã chuyển vế = 0)
        "dieu_kien_loai": "nghiem_kep",
        "gia_tri": "2"                   # chỉ cần khi dieu_kien_loai cần 1 giá trị cụ thể
    }
    """
    equation_str = params.get("equation")
    dieu_kien = params.get("dieu_kien_loai")
    gia_tri = params.get("gia_tri")

    if not equation_str:
        raise ValueError("Thiếu 'equation' để giải tham số m.")
    if dieu_kien not in _DIEU_KIEN_HOP_LE:
        raise ValueError(f"Loại điều kiện không hỗ trợ: {dieu_kien}")

    expr = sp.sympify(equation_str, locals={'x': x, 'm': m})

    # ---- Trường hợp 1: biết trước 1 nghiệm cụ thể -> thế trực tiếp ----
    # Tổng quát cho MỌI dạng phương trình (kể cả siêu việt), vì chỉ là phép thế.
    if dieu_kien == "nghiem_cho_truoc":
        if gia_tri is None:
            raise ValueError("Thiếu 'gia_tri' (nghiệm đã cho) cho điều kiện 'nghiem_cho_truoc'.")
        x0 = sp.sympify(gia_tri, locals={'x': x, 'm': m})
        ket_qua = _giai_phuong_trinh_theo_m(expr.subs(x, x0), 0)
        return {"dieu_kien": dieu_kien, **ket_qua}

    # ---- Các điều kiện còn lại hiện chỉ hỗ trợ ĐA THỨC theo x ----
    if not expr.is_polynomial(x):
        raise ValueError(
            "Điều kiện này hiện chỉ hỗ trợ phương trình ĐA THỨC theo x "
            "(chưa hỗ trợ phương trình lượng giác/log/mũ)."
        )

    poly = sp.Poly(sp.expand(expr), x)
    n = poly.degree()
    coeffs = poly.all_coeffs()  # [a_n, a_{n-1}, ..., a_1, a_0]
    a_n, a_0 = coeffs[0], coeffs[-1]

    # ---- Nghiệm kép/nghiệm bội: TỔNG QUÁT mọi bậc nhờ sp.discriminant ----
    if dieu_kien == "nghiem_kep":
        delta = sp.discriminant(poly.as_expr(), x)
        ket_qua = _giai_phuong_trinh_theo_m(delta, 0)
        return {"dieu_kien": dieu_kien, **ket_qua}

    # ---- Vô nghiệm / có nghiệm thực ----
    if dieu_kien in ("vo_nghiem", "co_nghiem"):
        if n % 2 == 1:
            # Đa thức bậc lẻ với hệ số thực LUÔN có ít nhất 1 nghiệm thực
            # (định lý giá trị trung gian) -> đúng với MỌI giá trị m.
            if dieu_kien == "co_nghiem":
                return {"dieu_kien": dieu_kien, "ket_qua": "mọi giá trị m (đa thức bậc lẻ luôn có nghiệm thực)", "loai_ket_qua": "all_m"}
            return {"dieu_kien": dieu_kien, "ket_qua": "không tồn tại m nào (đa thức bậc lẻ luôn có nghiệm thực)", "loai_ket_qua": "no_m"}

        if n == 2:
            a, b, c = coeffs
            delta = sp.expand(b**2 - 4 * a * c)
            if dieu_kien == "vo_nghiem":
                ket_qua = sp.solve_univariate_inequality(delta < 0, m, relational=False)
            else:
                ket_qua = sp.solve_univariate_inequality(delta >= 0, m, relational=False)
            return {"dieu_kien": dieu_kien, "ket_qua": str(ket_qua), "loai_ket_qua": "interval"}

        # Bậc chẵn >= 4: đếm số nghiệm thực theo tham số m đòi hỏi kỹ thuật
        # nâng cao hơn discriminant đơn thuần (dãy Sturm / phân tích CAD).
        raise ValueError(
            f"Đa thức bậc {n} (chẵn, từ bậc 4 trở lên): xác định điều kiện "
            "vô nghiệm/có nghiệm thực tổng quát theo m hiện CHƯA được hỗ trợ "
            "(cần dãy Sturm hoặc phân tích CAD)."
        )

    # ---- Vi-ét: tổng / tích TẤT CẢ nghiệm -> tổng quát mọi bậc ----
    if dieu_kien == "vi_et_tong":
        if gia_tri is None:
            raise ValueError("Thiếu 'gia_tri' cho điều kiện 'vi_et_tong'.")
        target = sp.sympify(gia_tri, locals={'x': x, 'm': m})
        tong = -coeffs[1] / a_n
        ket_qua = _giai_phuong_trinh_theo_m(tong, target)
        return {"dieu_kien": dieu_kien, **ket_qua}

    if dieu_kien == "vi_et_tich":
        if gia_tri is None:
            raise ValueError("Thiếu 'gia_tri' cho điều kiện 'vi_et_tich'.")
        target = sp.sympify(gia_tri, locals={'x': x, 'm': m})
        tich = ((-1) ** n) * a_0 / a_n
        ket_qua = _giai_phuong_trinh_theo_m(tich, target)
        return {"dieu_kien": dieu_kien, **ket_qua}

    # ---- "Trái dấu / cùng dấu" chỉ có nghĩa rõ ràng khi đúng 2 nghiệm ----
    if dieu_kien in ("vi_et_trai_dau", "vi_et_cung_dau"):
        if n != 2:
            raise ValueError(
                f"Điều kiện '{dieu_kien}' chỉ áp dụng được cho phương trình bậc 2 "
                f"(đúng 2 nghiệm); phương trình bạn đưa vào có bậc {n}."
            )
        a, b, c = coeffs
        ti_le = c / a
        if dieu_kien == "vi_et_trai_dau":
            ket_qua = sp.solve_univariate_inequality(ti_le < 0, m, relational=False)
        else:
            ket_qua = sp.solve_univariate_inequality(ti_le > 0, m, relational=False)
        return {"dieu_kien": dieu_kien, "ket_qua": str(ket_qua), "loai_ket_qua": "interval"}

    raise ValueError(f"Loại điều kiện không hỗ trợ: {dieu_kien}")