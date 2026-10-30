def xacdinh_action(text_yeucau, object):
    return f"""
Đây là yêu cầu của người dùng:

{text_yeucau}

Đây là đối tượng hiện tại cần xác định hành động:

{object}

NHIỆM VỤ:

Dựa trên yêu cầu và và đối tượng để xác định hành động(action) theo nghiêm nghặt các quy tắc bên dưới

QUY TẮC BẮT BUỘC:

1. Chỉ xét DUY NHẤT đối tượng hiện tại được cung cấp ở trên.
2. Nếu yêu cầu của người dùng KHÔNG áp dụng cho đối tượng hiện tại thì trả về:
   null
3. Nếu yêu cầu có áp dụng thì chỉ trả về DUY NHẤT MỘT action dưới dạng JSON.
4. KHÔNG được tạo nhiều action.
5. KHÔNG được tạo action cho đối tượng khác.
6. KHÔNG ĐƯỢC tự giải toán, không tính đạo hàm, không tính tung độ, chỉ trích xuất tham số thô.
7. Các biểu thức toán học phải được chuyển về định dạng chuẩn SymPy không phải python
8. Không giải thích, không viết thêm chữ, không bọc trong ```json.

CÁC ACTION HỢP LỆ:

- {{
    "action": "tao_phuongtrinh",
    "params": {{
        "equation": "chuỗi phương trình đại số",
        "color": "màu"
    }}
}}

- {{
    "action": "tao_tieptuyen",
    "params": {{
        "at_x": số,
        "color": "màu"
    }}
}}

- {{
    "action": "tao_duongthang",
    "params": {{
        "equation": "phương trình đường thẳng",
        "color": "màu"
    }}
}}

- {{
    "action": "tao_diem",
    "params": {{
        "coordinates": [x, y] hoặc [x, y, z],
        
        "color": "màu"
    }}
}}

- {{
    "action": "tim_tham_so",
    "params": {{
        "equation": "đa thức đã chuyển về dạng =0",
        "dieu_kien_loai": "nghiem_cho_truoc | nghiem_kep | vo_nghiem | co_nghiem | vi_et_tong | vi_et_tich | vi_et_trai_dau | vi_et_cung_dau",
        "gia_tri": "giá trị hoặc null"
    }}
}}



Ví dụ:

Object:

{{
    "formula":"y=x**3",
    "type":"dai_so",
    "has_graph":true,
    "relations":null
}}

Yêu cầu:

"Vẽ tiếp tuyến tại x=3 cho đồ thị y=x**3"

AI_thought : áp dụng quy tắc 1  ta nhìn vào object thấy có formula là y=x**3 và nhìn vào yêu cầu có cho đồ thị y=x**3
suy ra chúng ta chỉ tạo action cho đối tượng có formular là 'y=x**3' và thấy yêu câu cho đồ thị hoặc vẽ đồ thị  suy action=tao_phuongtrinh
tiếp đến áp dụng quy tắc 3->5 ta dừng việc xác định action ở đây( bỏ qua yêu cầu vẽ tiếp tuyến ) và trả về kết quat như sau: 
Kết quả:

{{
    "action":"tao_phuongtrinh",
    "params":{{
        "equation":"y=x**3",
        "color":"blue"
    }}
}}



Nếu object hiện tại không liên quan đến yêu cầu thì:

null
"""