def dichthuat_so(formula, kq):
    return f"""Bạn là một gia sư Toán người Việt.
    Tôi đã tính toán công thức {formula} bằng máy tính và có các kết quả chính xác là {kq}:
    Hãy dựa vào các số liệu này để viết kiến thức và một lời giải thích từng bước bằng Tiếng Việt thật sư phạm, dễ hiểu cho học sinh.
    hãy trả về kết quả dưới định dạng JSON nghiêm ngặt (không kèm theo lời thoại nào khác ngoài block JSON):
    {{
        "formula": "công thức toán học truyền vào",
        "info": "gồm kiến thức và từng bước một để giải bài toán"
    }}
    lưu ý nghiêm ngặt:
        + info không được phép chứa những câu từ liên quan đến việc hỏi lại người dùng như em hiểu chưa, có chỗ nào thắc mắc ...
    """
def dichthuat_thamso(formula,dieukien,ketqua):
    return f"""Bạn là một gia sư Toán người Việt.
    tôi đã giải bài toán tìm tham số cho công {formula} với điều kiện {dieukien} bằng sympy của python
    và được kết quả là {ketqua}
    Hãy dựa vào các số liệu này để viết kiến thức và một lời giải thích từng bước bằng Tiếng Việt thật sư phạm, dễ hiểu cho học sinh.
    hãy trả về kết quả dưới định dạng JSON nghiêm ngặt (không kèm theo lời thoại nào khác ngoài block JSON):
    {{
        "formula": "công thức toán học truyền vào",
        "dieukien":" điều kiện của bài toán truyền vào"
        "info": "gồm kiến thức và từng bước một để giải bài toán"
    }}
    lưu ý nghiêm ngặt:
        + info không được phép chứa những câu từ liên quan đến việc hỏi lại người dùng như em hiểu chưa, có chỗ nào thắc mắc ...
    """