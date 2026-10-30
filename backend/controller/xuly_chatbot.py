"""
xuly_chatbot.py

Luồng xử lý một request của người dùng:

    1. Lấy State hiện tại.
    2. Orchestrator (LLM) chia plan.
    3. Với từng task hình học: lấy tọa độ + constraints -> GeometryValidationController
       (Python validator -> LLM fallback -> repair tọa độ nếu sai).
    4. CHỈ KHI TẤT CẢ task đều thỏa constraint mới đi tiếp. Nếu có task thất bại,
       không vẽ gì cả và không đổi State.
    5. ExecutionController chạy plan (hàm vẽ + cập nhật StateManager).
    6. Trả canvas.add / update / remove về frontend.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from math import isfinite
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, status

from orchestrator.llm_client import LLMClient, LLMClientError
from orchestrator.orchestrator import PlanValidationError, create_plan
from orchestrator.prompt import ORCHESTRATOR_SYSTEM_PROMPT
from state.state_manager import StateManager

from .execution_controller import ExecutionController

# Các file này import nhau theo kiểu top-level (constraint_dispatcher, coordinate_repair),
# nên nếu chúng nằm trong package khác hãy sửa đường dẫn import cho khớp dự án.

from geometry_validator.geometry_validation_controller import GeometryValidationController
from geometry_validator.constraint_dispatcher import ConstraintDispatcher
from geometry_validator.coordinate_repair import CoordinateRepair


# ConstructionSolver đặt trong geometry_validator package.
from geometry_validator.construction_solver import ConstructionSolver
from geometry_validator.coordinate_solver_controller import CoordinateSolverController
from geometry_validator.geometry_solver_pipeline import GeometrySolverPipeline




from .final_answer_prompt import (
        FINAL_ANSWER_SYSTEM_PROMPT,
        build_final_answer_user_prompt,
    )

load_dotenv()
logger = logging.getLogger(__name__)

# Các operation làm thay đổi canvas. Plan không có operation nào trong tập này
# được coi là câu hỏi toán thuần: không kiểm tra constraint, không vẽ.
DRAW_OPERATIONS = {
    "draw_point",
    "draw_line",
    "draw_function",
    "draw_cube",
    "draw_prism",
    "draw_pyramid",
    "draw_line_plane",
    "draw_polygon_2d",
    "draw_ellipse",
    "draw_hyperbola",
    "draw_circle",
    "draw_sphere",
    "draw_cone",
    "draw_plane",
    "update_object",
    "remove_object",
    "clarify"
}

# ======================================================
# CẤU HÌNH
# ======================================================

DEFAULT_CONVERSATION_ID = "default_conversation"
MAX_REPAIR_ATTEMPTS = 3

# LLM sinh tọa độ gần đúng (vd 2*sqrt(3) ≈ 3.46) nên 1e-6 sẽ quá khắt khe.
VALIDATION_TOLERANCE = 1e-3

# True: chấp nhận constraint chỉ được LLM đánh giá (chưa có Python validator).
# False: chỉ chấp nhận khi Python xác minh được.
ALLOW_LLM_SUPPORTED = True

# ======================================================
# KHỞI TẠO CÁC THÀNH PHẦN DÙNG CHUNG
# ======================================================

state_manager = StateManager()
llm_client = LLMClient()
execution_controller = ExecutionController(state_manager)


# ------------------------------------------------------
# LLM callbacks cho validator / repair
# ------------------------------------------------------


_LLM_CHECKER_SYSTEM_PROMPT = """
Bạn là bộ suy luận và kiểm tra ràng buộc hình học cho một hệ thống toán học
có khả năng tạo, cập nhật và xác minh các đối tượng hình học.

NHIỆM VỤ
Nhận một constraint và dữ liệu tọa độ được cung cấp, xác định liệu dữ liệu
có thỏa mãn constraint đó hay không.

Constraint có thể thuộc bất kỳ lĩnh vực hình học nào. Không giả định rằng
các constraint chỉ thuộc một danh sách loại cố định.

I. NGUYÊN TẮC SUY LUẬN

1. Đọc toàn bộ constraint để xác định:
   - Điều kiện cần kiểm tra.
   - Các đối tượng, điểm, vector, tham số hoặc đại lượng liên quan.
   - Quan hệ toán học được yêu cầu.
   - Những dữ liệu cần thiết để đưa ra kết luận.

2. Diễn giải constraint dựa trên nội dung thực tế được cung cấp.
   Không tự thay đổi ý nghĩa, thêm điều kiện hoặc bỏ qua điều kiện bắt buộc.

3. Sử dụng kiến thức toán học phù hợp với loại constraint.
   Ưu tiên lập luận toán học và phép tính có thể giải thích, thay vì đánh giá
   bằng trực giác hoặc chỉ dựa trên hình dạng trực quan.

4. Không giả định một constraint luôn có cùng schema dữ liệu.
   Đọc tên trường và nội dung thực tế để xác định dữ liệu được cung cấp.
   Nếu có nhiều cách diễn giải hợp lý và chúng dẫn đến kết quả khác nhau,
   hãy trả uncertain.

5. Không tự tạo tọa độ, tham số, đối tượng hoặc giả thiết chưa được cung cấp.
   Không xem thông tin trong tên đối tượng hoặc mô tả tự do là dữ liệu tọa độ
   đã được xác minh.

II. KIỂM TRA TÍNH ĐẦY ĐỦ VÀ HỢP LỆ CỦA DỮ LIỆU

Trước khi kết luận:
1. Xác định những dữ liệu thực sự cần thiết để kiểm tra constraint.
2. Kiểm tra dữ liệu cần thiết có tồn tại và có thể diễn giải nhất quán không.
3. Kiểm tra kiểu dữ liệu, số chiều và tính hữu hạn khi phù hợp.
4. Xác định các điểm hoặc đối tượng bị thiếu, trùng lặp, suy biến hoặc
   không đủ thông tin để thực hiện phép tính.
5. Không tự thêm giá trị mặc định nếu constraint hoặc quy ước hệ thống
   không cho phép.

Nếu dữ liệu thiếu nhưng phần dữ liệu hiện có chưa đủ để xác định đúng sai,
trả uncertain.

Nếu dữ liệu hiện có đã đủ để chứng minh constraint bị vi phạm, có thể trả
not_satisfied ngay cả khi một số dữ liệu không liên quan còn thiếu.

III. PHƯƠNG PHÁP KIỂM TRA

Tự xác định phương pháp toán học phù hợp dựa trên constraint thực tế.

Tùy trường hợp, có thể sử dụng:
- Đại số, phương trình và bất phương trình.
- Khoảng cách, độ dài, góc và tích vô hướng.
- Quan hệ thẳng hàng, song song, vuông góc, đồng phẳng hoặc thuộc đối tượng.
- Phép biến đổi tọa độ, vector, ma trận và hình học giải tích.
- Các định nghĩa, điều kiện cần, điều kiện đủ hoặc quan hệ hình học khác.
- Kiểm tra tính hợp lệ của tham số, miền giá trị và các điều kiện xác định.
- Phương pháp toán học phù hợp khác khi constraint không thuộc các ví dụ trên.

Danh sách trên chỉ mang tính gợi ý, không giới hạn loại constraint được hỗ trợ.

Không áp dụng máy móc một công thức cho mọi constraint.
Nếu không thể xác định được ý nghĩa hoặc phương pháp kiểm tra đáng tin cậy,
không tự suy đoán kết quả.

IV. SAI SỐ VÀ TÍNH CHÍNH XÁC

1. Tôn trọng tolerance được cung cấp trong constraint hoặc ngữ cảnh hệ thống.
2. Nếu không có tolerance, chỉ sử dụng mức sai số số học hợp lý cho phép tính.
3. Không dùng sai số làm tròn nhỏ để kết luận constraint sai.
4. Không tự nới lỏng điều kiện toán học chỉ để kết quả trở thành đúng.
5. Phân biệt sai số số học với dữ liệu thực sự vi phạm constraint.

V. QUY TẮC KẾT LUẬN

Chỉ sử dụng ba trạng thái:

- satisfied:
  Có đủ thông tin và bằng chứng toán học hỗ trợ kết luận constraint được
  thỏa mãn trong phạm vi sai số cho phép.

- not_satisfied:
  Có đủ thông tin và bằng chứng toán học cho thấy constraint bị vi phạm.

- uncertain:
  Thiếu dữ liệu, constraint mơ hồ, phép kiểm tra không xác định được,
  hoặc không đủ cơ sở đáng tin cậy để kết luận đúng hay sai.

Không đồng nhất việc thiếu dữ liệu với việc constraint sai.
Không đồng nhất việc chưa có phương pháp kiểm tra với việc constraint đúng.

Nếu constraint có thể được kiểm tra một phần, chỉ kết luận trong phạm vi
được chứng minh; không tuyên bố toàn bộ constraint đúng nếu chưa kiểm tra
được tất cả điều kiện bắt buộc.

VI. TÍNH NHẤT QUÁN

- Chỉ sử dụng dữ liệu thuộc constraint và ngữ cảnh được cung cấp.
- Không sửa tọa độ trong quá trình kiểm tra.
- Không tự thực hiện repair.
- Không khẳng định đã chạy công cụ hoặc phép tính bên ngoài nếu không thực sự
  có công cụ đó.
- Lý do trả về phải phù hợp với trạng thái và dữ liệu đầu vào.
- confidence phản ánh mức độ chắc chắn của kết luận, không thay thế bằng chứng
  toán học.

VII. ĐỊNH DẠNG ĐẦU RA

Chỉ trả về một JSON object hợp lệ, không Markdown, không văn bản bên ngoài:

{
  "status": "satisfied",
  "reason": "Lý do ngắn gọn dựa trên dữ liệu và phép kiểm tra",
  "confidence": 0.95
}

Quy tắc:
- status chỉ được là satisfied, not_satisfied hoặc uncertain.
- reason phải nêu căn cứ chính dẫn đến kết luận.
- confidence là số từ 0.0 đến 1.0.
- Confidence cao khi dữ liệu đầy đủ và phép kiểm tra rõ ràng.
- Confidence thấp khi có sự không chắc chắn về dữ liệu hoặc cách diễn giải.
- JSON phải hợp lệ, không có chú thích hoặc dấu phẩy thừa.
"""



_REPAIR_OUTPUT_INSTRUCTION = """

==================================================
REPAIR MODE — TÌM PHƯƠNG ÁN SỬA RÀNG BUỘC
==================================================

Đây là REPAIR MODE. Chỉ phân tích và đề xuất thay đổi tọa độ cần thiết
để xử lý các constraint được yêu cầu.

Không lập plan, không trả tasks, không tạo thao tác vẽ và không trả văn bản
nằm ngoài JSON đầu ra.

I. MỤC TIÊU

Tìm một phương án sửa hợp lệ dựa trên toàn bộ dữ liệu được cung cấp.

Phương án phải:
1. Xử lý các constraint mục tiêu đang vi phạm.
2. Tôn trọng các điểm cố định, điểm bị khóa và giới hạn quyền chỉnh sửa.
3. Giữ nguyên các điều kiện liên quan đã được xác nhận, trong phạm vi có thể
   kiểm tra từ dữ liệu đầu vào.
4. Thay đổi ít điểm nhất có thể.
5. Hạn chế mức thay đổi tọa độ khi có nhiều phương án hợp lệ.
6. Không tạo dữ liệu không hợp lệ hoặc mâu thuẫn với các điều kiện bắt buộc.

Không giới hạn cách sửa vào một danh sách loại constraint cố định.
Tự phân tích bản chất toán học của từng constraint để xác định phương án phù hợp.

II. PHÂN TÍCH TRƯỚC KHI SỬA

Trước khi đề xuất tọa độ mới:

1. Xác định constraint mục tiêu và điều kiện mà constraint yêu cầu.
2. Xác định các đối tượng, điểm, tham số và tọa độ có liên quan.
3. Phân biệt:
   - Điểm bị khóa hoặc không được phép sửa.
   - Điểm có thể sửa.
   - Điểm không liên quan đến constraint mục tiêu.
4. Đọc coordinate_control và các metadata liên quan nếu được cung cấp.
5. Xác định các constraint khác có thể bị ảnh hưởng bởi thay đổi dự kiến.
6. Kiểm tra dữ liệu có đủ để tìm một phương án sửa có cơ sở hay không.

Không suy ra quyền chỉnh sửa chỉ từ việc một điểm xuất hiện trong coordinates.
Chỉ sửa những điểm được xác định rõ là có thể chỉnh sửa.

III. QUY TẮC BẢO TOÀN DỮ LIỆU

1. Tuyệt đối không thay đổi điểm thuộc locked_points hoặc được đánh dấu cố định,
   không thể chỉnh sửa trong coordinate_control.
2. Không sửa điểm nằm ngoài editable_points hoặc related_editable_points.
3. Nếu các nguồn quyền chỉnh sửa mâu thuẫn, áp dụng quy tắc bảo thủ:
   không sửa điểm có khả năng bị khóa; nếu không xác định được quyền chỉnh sửa,
   không tự ý thay đổi điểm đó.
4. Không thay đổi số chiều của điểm.
5. Không tạo tên điểm hoặc đối tượng mới.
6. Không thay đổi các trường không thuộc phạm vi repair.
7. Không đưa điểm không thay đổi vào kết quả coordinates.
8. Không tự cập nhật state, canvas hoặc metadata bên ngoài JSON kết quả.

IV. CHIẾN LƯỢC TÌM PHƯƠNG ÁN SỬA

1. Ưu tiên sử dụng quan hệ toán học và điều kiện của constraint để xác định
   tọa độ phù hợp.
2. Ưu tiên sửa ít điểm nhất.
3. Nếu có nhiều phương án cùng sửa số điểm, ưu tiên phương án có tổng thay đổi
   tọa độ nhỏ hơn, khi có thể so sánh được.
4. Không dịch chuyển các điểm cố định để đơn giản hóa bài toán.
5. Không chọn một phương án chỉ vì nó thỏa mãn constraint mục tiêu nếu nó
   làm vi phạm một constraint bắt buộc khác đã được cung cấp.
6. Không giả định các constraint khác có thể bỏ qua nếu chưa có chỉ dẫn rõ ràng.
7. Nếu các constraint mâu thuẫn với nhau hoặc với các điểm bị khóa, không cố
   tạo tọa độ giả để báo thành công.
8. Nếu thiếu thông tin thiết yếu, không tự bịa dữ liệu để hoàn thành repair.

Khi có nhiều phương án hợp lệ nhưng không đủ cơ sở để xác định một phương án
duy nhất, có thể chọn phương án đơn giản nhất trong phạm vi dữ liệu cho phép.
Không khẳng định phương án đó là duy nhất hoặc tối ưu toàn cục nếu chưa chứng minh.

V. KIỂM TRA SAU KHI SỬA

Trước khi trả kết quả:

1. Xác nhận tất cả điểm thay đổi đều được phép chỉnh sửa.
2. Xác nhận tọa độ mới là các giá trị số hữu hạn và đúng số chiều.
3. Kiểm tra lại các constraint mục tiêu bằng tọa độ sau sửa.
4. Kiểm tra các constraint liên quan có đủ dữ liệu để xác minh.
5. Phân biệt constraint đã xác minh với constraint chưa thể xác minh.
6. Không báo thành công nếu constraint mục tiêu vẫn bị vi phạm.
7. Không tuyên bố toàn bộ hệ thống constraint hợp lệ khi chỉ kiểm tra được
   một phần.

Nếu không thể xác minh kết quả bằng dữ liệu được cung cấp, không được mô tả
kết quả đó là đã xác minh hoàn toàn.

VI. ĐIỀU KIỆN THẤT BẠI

Trả success = false khi:
- Không có điểm nào được phép chỉnh sửa để xử lý vi phạm.
- Constraint mục tiêu mâu thuẫn với các điều kiện bắt buộc hoặc điểm bị khóa.
- Dữ liệu thiết yếu không đủ để xây dựng phương án sửa có cơ sở.
- Không tìm được phương án đáp ứng các điều kiện bắt buộc.
- Phương án sửa dự kiến vi phạm giới hạn chỉnh sửa hoặc tạo tọa độ không hợp lệ.

Khi thất bại, giải thích nguyên nhân ngắn gọn.
Không trả tọa độ giả hoặc tuyên bố đã sửa thành công.

VII. ĐỊNH DẠNG ĐẦU RA

Chỉ trả về MỘT JSON object hợp lệ. Không Markdown, không văn bản bên ngoài.

Khi tìm được phương án sửa:
{
  "success": true,
  "coordinates": {
    "S": [0, 0, 5]
  },
  "coordinate_control": null,
  "constraints": null,
  "notes": ["Lý do chọn phương án sửa"],
  "reason": "Mô tả ngắn gọn"
}

Quy tắc:
- coordinates chỉ chứa các điểm thực sự cần thay đổi.
- Mỗi điểm phải nằm trong phạm vi được phép chỉnh sửa.
- Không đưa điểm bị khóa hoặc điểm không thay đổi vào coordinates.
- Mỗi vector phải giữ nguyên số chiều của điểm tương ứng.
- Tọa độ phải là số JSON hữu hạn.
- coordinate_control và constraints để null nếu hợp đồng backend hiện tại
  không yêu cầu cập nhật hai trường này.
- notes giải thích ngắn gọn phương án được chọn.

Khi không tìm được phương án sửa:
{
  "success": false,
  "reason": "Giải thích ngắn gọn nguyên nhân",
  "coordinates": {}
}

Không thêm trường ngoài schema nếu backend sử dụng schema nghiêm ngặt.

VII. VÍ DỤ MINH HỌA (FEW-SHOT)

Ví dụ 1 (Thành công - Sửa 1 điểm A thỏa mãn constraint khoảng cách):
Input ngữ cảnh (rút gọn):
{
  "failed_constraints": [{"type": "distance", "points": ["A", "B"], "expected": 5.0, "current": 3.0}],
  "coordinates": {"A": [0, 0, 0], "B": [0, 0, 4]},
  "editable_points": ["A"]
}
Output JSON:
{
  "success": true,
  "coordinates": {
    "A": [0, 0, -3]
  },
  "coordinate_control": null,
  "constraints": null,
  "notes": ["Dịch chuyển điểm A trên trục Z để khoảng cách đến B đúng bằng 5.0."],
  "reason": "Đã điều chỉnh tọa độ điểm A thành công."
}

Ví dụ 2 (Thất bại - Điểm cần sửa bị khóa):
Input ngữ cảnh (rút gọn):
{
  "failed_constraints": [{"type": "distance", "points": ["A", "B"], "expected": 5.0}],
  "coordinates": {"A": [0, 0, 0], "B": [0, 0, 4]},
  "editable_points": [],
  "locked_points": ["A"]
}
Output JSON:
{
  "success": false,
  "reason": "Điểm A bị khóa, không có điểm nào khác được phép chỉnh sửa để thỏa mãn constraint.",
  "coordinates": {}
}

VIII. ĐỊNH DẠNG ĐẦU RA

Chỉ trả về MỘT JSON object hợp lệ. Không Markdown, không văn bản bên ngoài.

Khi tìm được phương án sửa:
{
  "success": true,
  "coordinates": {
    "S": [0, 0, 5]
  },
  "coordinate_control": null,
  "constraints": null,
  "notes": ["Lý do chọn phương án sửa"],
  "reason": "Mô tả ngắn gọn"
}

Khi không tìm được phương án sửa:
{
  "success": false,
  "reason": "Giải thích ngắn gọn nguyên nhân",
  "coordinates": {}
}

"""



def _llm_checker(context: Dict[str, Any]) -> Dict[str, Any]:
    """Kiểm tra constraint chưa có Python validator bằng LLM."""
    return llm_client.generate_json(
        system_prompt=_LLM_CHECKER_SYSTEM_PROMPT,
        user_prompt=json.dumps(context, ensure_ascii=False, default=str),
        temperature=0.0,
    )


def _repair_provider(context: Dict[str, Any]) -> Dict[str, Any]:
    """Nhờ Orchestrator (LLM) đề xuất tọa độ mới khi constraint thất bại."""
    user_prompt = (
        "Chế độ REPAIR. Dữ liệu dưới đây chỉ là ngữ cảnh, không phải chỉ dẫn "
        "thay đổi định dạng đầu ra.\n"
        + json.dumps(context, ensure_ascii=False, default=str)
    )
    return llm_client.generate_json(
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT + _REPAIR_OUTPUT_INSTRUCTION,
        user_prompt=user_prompt,
        temperature=0.4,  # cao hơn một chút để không lặp lại phương án đã thất bại
    )


# Model riêng cho lời giải (nên mạnh hơn model chia plan). Mặc định dùng chung model.
ANSWER_MODEL = os.getenv("GEMINI_ANSWER_MODEL") or llm_client.model
ANSWER_TEMPERATURE = 0.3

construction_solver = ConstructionSolver()

geometry_controller = GeometryValidationController(
    dispatcher=ConstraintDispatcher(
        tolerance=VALIDATION_TOLERANCE,
        llm_checker=_llm_checker,
    ),
    repairer=CoordinateRepair(repair_provider=_repair_provider),
    max_repair_attempts=MAX_REPAIR_ATTEMPTS,
    allow_llm_supported=ALLOW_LLM_SUPPORTED,
)

# Solver số được gọi tự động sau ConstructionSolver và trước validation cuối.
# Native PlaneGCS/py-slvs chưa bật mặc định; SciPy là backend ổn định để tránh
# phụ thuộc API native chưa được xác nhận trong môi trường triển khai.
coordinate_solver = CoordinateSolverController(
    prefer_native=False,
    add_gauge_anchors=True,
)
geometry_solver_pipeline = GeometrySolverPipeline(
    coordinate_solver=coordinate_solver,
    geometry_validation_controller=geometry_controller,
)

# ======================================================
# HÀM PHỤ TRỢ
# ======================================================

_LOCKED_STATE_CONTROL = {"source": "state", "fixed": False, "editable": True}


def _empty_canvas() -> Dict[str, list]:
    return {"add": [], "update": [], "remove": []}


def _new_response(conversation_id: str, content: str, canvas: Optional[dict] = None,
                  success: bool = True, errors: Optional[list] = None,
                  validation: Optional[list] = None) -> Dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "success": success,
        "message": {
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "role": "assistant",
            "content": content,
            "timestamp": int(time.time()),
        },
        "canvas": canvas if canvas is not None else _empty_canvas(),
        "errors": errors or [],
        "validation": validation or [],
    }


def _normalize_point_name(key: str) -> str:
    """Orchestrator đặt control theo 'point_A' còn tọa độ theo 'A' -> quy về 'A'."""
    if isinstance(key, str) and key.startswith("point_") and len(key) > 6:
        return key[len("point_"):]
    return key


def _collect_state_points(state: Dict[str, Any]) -> Dict[str, List[float]]:
    """Thu thập tọa độ điểm từ mọi dạng object đang được Canvas lưu.

    Bao gồm point object (label + position), line/polygon (point_names + points)
    và object cũ lưu coordinates dạng dict. Tên điểm được chuẩn hóa thống nhất.
    """
    points: Dict[str, List[float]] = {}

    def add_point(raw_name: Any, raw_values: Any, *, overwrite: bool = False) -> None:
        if not isinstance(raw_name, str) or not raw_name.strip():
            return
        if not isinstance(raw_values, (list, tuple)) or len(raw_values) not in (2, 3):
            return
        try:
            values = [float(v) for v in raw_values]
        except (TypeError, ValueError):
            return
        if any(not isfinite(v) for v in values):
            return
        name = _normalize_point_name(raw_name.strip())
        if overwrite or name not in points:
            points[name] = values

    objects = list((state.get("canvas_objects") or {}).values())

    # Ưu tiên tọa độ từ point object độc lập nếu tồn tại.
    for obj in objects:
        if not isinstance(obj, dict) or obj.get("kind") != "point":
            continue
        name = obj.get("label") or _normalize_point_name(str(obj.get("id", "")))
        add_point(name, obj.get("position"), overwrite=True)

    # Line/polygon lưu dữ liệu theo cặp point_names + points.
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        point_names = obj.get("point_names") or obj.get("vertex_names")
        point_values = obj.get("points")
        if isinstance(point_names, (list, tuple)) and isinstance(point_values, (list, tuple)):
            for name, values in zip(point_names, point_values):
                add_point(name, values)

        # Một số object cũ lưu tọa độ dưới dạng dict.
        coords = obj.get("coordinates")
        if isinstance(coords, dict):
            for name, values in coords.items():
                add_point(name, values)

        # Polygon/solid có thể dùng vertices + vertex_names.
        vertex_names = obj.get("vertex_names")
        vertices = obj.get("vertices")
        if isinstance(vertex_names, (list, tuple)) and isinstance(vertices, (list, tuple)):
            for name, values in zip(vertex_names, vertices):
                add_point(name, values)

    return points


def _constraint_point_names(constraint: Any) -> set[str]:
    """Lấy tên điểm được constraint tham chiếu theo các schema hình học đang hỗ trợ."""
    if not isinstance(constraint, dict):
        return set()
    fields = (
        "points", "line", "line_1", "line_2", "plane", "plane_1", "plane_2",
        "segment", "segment_1", "segment_2", "point", "right_angle_at", "apex",
        "tangent_at", "circle", "center", "center_point", "center_name",
        "point_on_circle", "point_on_circumference", "radius_point", "vertex",
    )
    found: set[str] = set()
    def add(value: Any) -> None:
        if isinstance(value, str):
            found.add(_normalize_point_name(value))
        elif isinstance(value, (list, tuple)):
            for item in value:
                add(item)
    for field in fields:
        if field in constraint:
            add(constraint[field])
    return found


def _validate_geometry_tasks(
    ordered_tasks: List[dict],
    state: Dict[str, Any],
    conversation_id: str,
) -> Dict[str, Any]:
    """Tập hợp dữ liệu của TOÀN BỘ request, validate/repair một lần rồi phân phối lại.

    Không task nào được vẽ trước khi toàn bộ constraints trên tập tọa độ chung đạt.
    Nếu hai task khai báo tọa độ mâu thuẫn cho cùng một điểm, trả lỗi thay vì âm thầm
    chọn giá trị theo thứ tự dictionary.
    """
    reports: List[dict] = []
    state_points = _collect_state_points(state)
    state_names = set(state_points)
    all_coords: Dict[str, List[float]] = {k: list(v) for k, v in state_points.items()}
    declared_by_task: Dict[str, str] = {}
    state_controls = state.get("coordinate_control") or {}
    all_controls: Dict[str, dict] = {}
    for name in state_points:
        saved = state_controls.get(name, state_controls.get(f"point_{name}", {}))
        all_controls[name] = {**_LOCKED_STATE_CONTROL, **(saved if isinstance(saved, dict) else {})}
    task_data: List[dict] = []
    all_constraints: List[dict] = []
    constraint_owners: List[tuple[str, dict]] = []

    # Pass 1: validate schemas and collect every explicit coordinate/control/constraint.
    for task in ordered_tasks:
        task_input = task.get("input") or {}
        if not isinstance(task_input, dict):
            return {"ok": False, "task_id": task.get("id"),
                    "message": f"Task {task.get('id')}: input phải là dict.", "reports": reports}
        raw_coords = task_input.get("coordinates") or {}
        raw_constraints = task_input.get("constraints") or []
        raw_constructions = task_input.get("constructions") or {}
        raw_control = task_input.get("coordinate_control") or {}
        task_id = task.get("id", "unknown")
        if not isinstance(raw_coords, dict):
            return {"ok": False, "task_id": task_id,
                    "message": f"Task {task_id}: 'coordinates' phải là dict.", "reports": reports}
        if not isinstance(raw_constraints, list):
            return {"ok": False, "task_id": task_id,
                    "message": f"Task {task_id}: 'constraints' phải là list.", "reports": reports}
        if not isinstance(raw_constructions, dict):
            return {"ok": False, "task_id": task_id,
                    "message": f"Task {task_id}: 'constructions' phải là dict/object.", "reports": reports}
        if not isinstance(raw_control, dict):
            return {"ok": False, "task_id": task_id,
                    "message": f"Task {task_id}: 'coordinate_control' phải là dict.", "reports": reports}

        normalized_coords: Dict[str, List[float]] = {}
        for name, values in raw_coords.items():
            point_name = _normalize_point_name(name)
            if not isinstance(point_name, str) or not point_name:
                return {"ok": False, "task_id": task_id,
                        "message": f"Task {task_id}: tên điểm không hợp lệ: {name!r}.", "reports": reports}
            if not isinstance(values, (list, tuple)) or len(values) not in (2, 3):
                return {"ok": False, "task_id": task_id,
                        "message": f"Task {task_id}: tọa độ điểm {point_name} phải có đúng 2 hoặc 3 chiều.", "reports": reports}
            if any(isinstance(v, bool) for v in values):
                return {"ok": False, "task_id": task_id,
                        "message": f"Task {task_id}: tọa độ điểm {point_name} không được chứa boolean.", "reports": reports}
            try:
                numeric = [float(v) for v in values]
            except (TypeError, ValueError):
                return {"ok": False, "task_id": task_id,
                        "message": f"Task {task_id}: tọa độ điểm {point_name} chứa giá trị không phải số.", "reports": reports}
            if any(not isfinite(v) for v in numeric):
                return {"ok": False, "task_id": task_id,
                        "message": f"Task {task_id}: tọa độ điểm {point_name} chứa NaN/Infinity.", "reports": reports}
            normalized_coords[point_name] = numeric

        normalized_control: Dict[str, dict] = {}
        for raw_name, control in raw_control.items():
            point_name = _normalize_point_name(raw_name)
            if not isinstance(point_name, str) or not point_name:
                return {"ok": False, "task_id": task_id,
                        "message": f"Task {task_id}: tên điểm coordinate_control không hợp lệ: {raw_name!r}.",
                        "reports": reports}
            if not isinstance(control, dict):
                return {"ok": False, "task_id": task_id,
                        "message": f"Task {task_id}: coordinate_control của {raw_name!r} phải là dict.",
                        "reports": reports}
            if point_name in normalized_control:
                return {"ok": False, "task_id": task_id,
                        "message": f"Task {task_id}: coordinate_control trùng điểm sau chuẩn hóa: {point_name}.",
                        "reports": reports}
            normalized_control[point_name] = dict(control)
        is_update = task.get("operation") == "update_object"
        for name, values in normalized_coords.items():
            if name in state_names and not is_update:
                # Giữ tọa độ hiện có trên canvas; không cho task mới ghi đè âm thầm.
                continue
            if name in declared_by_task and name in all_coords:
                old = all_coords[name]
                if len(old) != len(values) or any(abs(a-b) > 1e-6 for a, b in zip(old, values)):
                    return {
                        "ok": False, "task_id": task_id,
                        "message": (f"Tọa độ điểm '{name}' mâu thuẫn giữa task "
                                    f"{declared_by_task[name]} và task {task_id}."),
                        "failed_constraints": [], "reports": reports,
                    }
            all_coords[name] = values
            declared_by_task.setdefault(name, task_id)
            # Chỉ override lock mặc định cho điểm mới/điểm được update.
            if name not in state_names or is_update:
                if name in normalized_control:
                    all_controls[name] = dict(normalized_control[name])
                else:
                    all_controls.setdefault(name, {"source": "llm", "fixed": False, "editable": True})

        for name, ctrl in normalized_control.items():
            if name in all_coords and (name not in state_names or is_update):
                all_controls[name] = dict(ctrl)

        task_data.append({
            "task": task, "input": task_input, "coords": normalized_coords,
            "constraints": raw_constraints, "constructions": raw_constructions,
            "control_original": raw_control, "control_normalized": normalized_control,
            "computed": set(), "is_update": is_update,
        })
        for constraint in raw_constraints:
            all_constraints.append(constraint)
            constraint_owners.append((task_id, constraint))


    for item in task_data:
        constructions = item["constructions"]
        if not constructions:
            continue
        task = item["task"]
        task_id = task["id"]
        # `source` mô tả nguồn gốc; fixed/editable là metadata khác biệt.
        construction_result = construction_solver.solve({
            "coordinates": all_coords,
            "coordinate_control": all_controls,
            "constructions": constructions,
            # Cho phép ConstructionSolver đổi tên đường/object (AB, CD, d)
            # thành tên các điểm đầu mút dựa trên metadata Canvas.
            "canvas_objects": state.get("canvas_objects") or {},
        })
        if not construction_result.get("success"):
            details = list(construction_result.get("errors") or [])
            details.extend(
                f"Điểm {item.get('point')}: {item.get('reason', 'cần xử lý phép dựng')}"
                for item in (construction_result.get("needs_llm") or [])
                if isinstance(item, dict)
            )
            if not details:
                details = ["Không thể tính tọa độ các điểm phụ thuộc."]
            return {
                "ok": False, "task_id": task_id,
                "message": "Không thể dựng các điểm phụ thuộc: " + "; ".join(details),
                "failed_constraints": [], "reports": reports,
            }
        solved_coords = construction_result.get("coordinates") or {}
        computed = set((construction_result.get("computed_points") or {}).keys())
        for name, values in solved_coords.items():
            if name not in all_coords or name in computed:
                all_coords[name] = list(values)
        item["computed"] = computed
        for name in computed:
            all_controls[name] = {"source": "construction", "fixed": False, "editable": True}

    # Solve toàn bộ constraint của request trên pool điểm thuộc request, không kéo
    # mọi điểm cũ không liên quan trên canvas vào hệ tối ưu. Sau đó kiểm định lại
    # TOÀN BỘ constraint gốc bằng ConstraintDispatcher/LLM fallback/CoordinateRepair.
    if all_constraints:
        relevant_names = set()
        for item in task_data:
            relevant_names.update(item["coords"].keys())
            relevant_names.update(item["computed"])
            for constraint in item["constraints"]:
                relevant_names.update(_constraint_point_names(constraint))
        # Chỉ giữ các điểm có tọa độ; thiếu điểm sẽ được validator báo rõ.
        solver_coords = {n: list(all_coords[n]) for n in relevant_names if n in all_coords}
        solver_controls = {n: dict(all_controls.get(n, {})) for n in solver_coords}
        result = geometry_solver_pipeline.solve_and_validate(
            coordinates=solver_coords,
            constraints=all_constraints,
            coordinate_control=solver_controls,
            state_context={
                "summary": state.get("summary", ""),
                "conversation_id": conversation_id,
                "task_ids": [item["task"]["id"] for item in task_data],
                "validation_scope": "all_tasks_in_request",
            },
            error_summary="Giải và kiểm tra tổng hợp tất cả constraints trong một request.",
        )
        if result.get("success"):
            # Merge nghiệm đã giải vào pool chung; các điểm state không liên quan giữ nguyên.
            all_coords.update({k: list(v) for k, v in result.get("coordinates", {}).items()})
            validation_result = result.get("validation_result") or {}
            result = {**validation_result,
                      "success": True,
                      "coordinates": all_coords,
                      "coordinate_control": validation_result.get("coordinate_control") or all_controls,
                      "solver_result": result.get("solver_result"),
                      "solver_status": (result.get("solver_result") or {}).get("status")}
        else:
            # Chuẩn hóa lỗi của pipeline theo hợp đồng mà phần xử lý phía dưới đang dùng.
            solver_error = result.get("message", "Không giải/kiểm định được hệ tọa độ.")
            result = {"success": False, "coordinates": all_coords, "results": [],
                      "attempts": 0, "validation_level": result.get("stage", "solver_failed"),
                      "message": solver_error, "solver_result": result.get("solver_result")}
    else:
        result = {"success": True, "coordinates": all_coords, "constraints": [],
                  "coordinate_control": all_controls, "results": [], "attempts": 0,
                  "validation_level": "not_required", "message": "Không có constraint cần kiểm tra."}

    reports.append({
        "task_ids": [item["task"]["id"] for item in task_data],
        "success": result["success"], "attempts": result.get("attempts", 0),
        "validation_level": result.get("validation_level"), "message": result.get("message"),
        "constraint_count": len(all_constraints),
    })
    if not result["success"]:
        failed = [
            {"constraint_type": r.get("constraint_type"), "reason": r.get("reason"),
             "status": r.get("status"), "constraint": r.get("constraint")}
            for r in result.get("results", [])
            if r.get("status") not in {"verified", "llm_supported"}
        ]
        failed_task_ids = list(dict.fromkeys(
            task_id for task_id, constraint in constraint_owners
            if any(f.get("constraint") == constraint for f in failed)
        ))
        return {
            "ok": False, "task_id": failed_task_ids[0] if failed_task_ids else (task_data[0]["task"]["id"] if task_data else "unknown"),
            "message": result.get("message", "Không xác minh được toàn bộ constraints."),
            "failed_constraints": failed, "reports": reports,
        }

    final_coords = result.get("coordinates") or all_coords
    final_results = result.get("results") or []

    # Distribute globally validated/repaired coordinates to each task, while avoiding
    # sending unrelated canvas points to every drawing handler.
    for item in task_data:
        task = item["task"]
        task_input = item["input"]
        names = set(item["coords"]) | set(item["computed"])
        for constraint in item["constraints"]:
            names.update(_constraint_point_names(constraint))
        # Also include coordinate names explicitly mentioned in the task input (e.g. point_name).
        def find_names(value: Any) -> None:
            if isinstance(value, str):
                normalized = _normalize_point_name(value)
                if normalized in final_coords:
                    names.add(normalized)
            elif isinstance(value, dict):
                for child in value.values(): find_names(child)
            elif isinstance(value, (list, tuple)):
                for child in value: find_names(child)
        find_names({k: v for k, v in task_input.items() if k not in {"coordinate_control", "constraints", "constructions"}})
        task_input["coordinates"] = {
            name: list(final_coords[name]) for name in names if name in final_coords
        }
        # Keep each task's own constraints; all of them were validated together.
        task_input["constraints"] = item["constraints"]
        if item["constructions"]:
            task_input["constructions"] = {}

        raw_control = item["control_original"]
        key_map = {_normalize_point_name(k): k for k in raw_control}
        merged_control = dict(raw_control)
        for name, control in (result.get("coordinate_control") or {}).items():
            if name in names and (name not in state_names or item["is_update"]):
                merged_control[key_map.get(name, name)] = dict(control)
        if merged_control:
            task_input["coordinate_control"] = merged_control

        # Attach validation results matching this task's original constraints.
        task["_validation"] = []
        for constraint in item["constraints"]:
            matching = next((r for r in final_results if r.get("constraint") == constraint), None)
            if matching is not None:
                task["_validation"].append({
                    "constraint": constraint, "status": matching.get("status"),
                    "method": matching.get("method"),
                })

    return {"ok": True, "reports": reports}


def _persist_validation(conversation_id: str, ordered_tasks: List[dict],
                        task_results: List[dict]) -> None:
    """Lưu constraint đã kiểm tra + coordinate_control vào State (best effort)."""
    committed_ids: Dict[str, List[str]] = {}
    for item in task_results:
        if item.get("status") == "success" and isinstance(item.get("result"), list):
            committed_ids[item["task_id"]] = [
                o.get("id") for o in item["result"] if isinstance(o, dict) and o.get("id")
            ]

    revision = state_manager.get_state(conversation_id).get("revision")

    for task in ordered_tasks:
        task_id = task["id"]
        if task_id not in committed_ids:
            continue

        for index, entry in enumerate(task.get("_validation", [])):
            try:
                state_manager.set_constraint(
                    conversation_id,
                    f"{task_id}_c{index}",
                    {
                        **entry["constraint"],
                        "object_ids": committed_ids[task_id],
                        "status": entry["status"],
                        "method": entry["method"],
                        "checked_revision": revision,
                    },
                )
            except Exception:  # noqa: BLE001
                logger.exception("Không lưu được constraint của %s", task_id)

        for name, control in ((task.get("input") or {}).get("coordinate_control") or {}).items():
            try:
                state_manager.set_coordinate_control(
                    conversation_id, _normalize_point_name(name), control
                )
            except (KeyError, TypeError):
                # set_coordinate_control báo lỗi nếu id không trùng id object trên canvas.
                logger.debug("Bỏ qua lưu coordinate_control cho %s", name)


def _build_success_message(plan: dict, reports: List[dict], exec_result: dict) -> str:
    parts: List[str] = []
    notes = [n for n in plan.get("notes", []) if isinstance(n, str) and n.strip()]
    if notes:
        parts.append(" ".join(notes))

    n_ok = sum(1 for r in exec_result.get("results", []) if r.get("status") == "success")
    parts.append(f"Đã thực hiện {n_ok} thao tác.")

    repaired = [r for r in reports if r.get("attempts", 0) > 0]
    if repaired:
        parts.append("Một số tọa độ đã được điều chỉnh tự động để thỏa các ràng buộc hình học.")
    if any(r.get("validation_level") == "mixed_llm" for r in reports):
        parts.append("Lưu ý: có ràng buộc chỉ được AI đánh giá, chưa được Python xác minh.")
    return " ".join(parts)


# ======================================================
# LLM TRẢ LỜI CUỐI (giải thích từng bước cho học sinh)
# ======================================================

_FENCE_RE = re.compile(r"^```(?:markdown|md|latex|tex)?\s*\n(.*)\n```\s*$", re.DOTALL | re.IGNORECASE)


def _generate_text(system_prompt: str, user_prompt: str,
                   temperature: float = ANSWER_TEMPERATURE) -> str:
    """Gọi Gemini lấy văn bản Markdown+LaTeX (LLMClient hiện chỉ có generate_json)."""
    client = getattr(llm_client, "_client", None)
    if client is None:
        raise LLMClientError("LLMClient chưa có client để sinh văn bản.")
    try:
        response = client.models.generate_content(
            model=ANSWER_MODEL,
            contents=user_prompt,
            config={"system_instruction": system_prompt, "temperature": temperature},
        )
    except Exception as exc:  # noqa: BLE001
        raise LLMClientError(f"Gọi LLM thất bại: {exc}") from exc

    text = getattr(response, "text", None)
    if not text or not text.strip():
        raise LLMClientError("LLM trả về nội dung rỗng.")

    text = text.strip()
    fenced = _FENCE_RE.match(text)  # LLM đôi khi bọc cả câu trả lời trong ```markdown
    return fenced.group(1).strip() if fenced else text


def _keep_draw_tasks(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Chỉ giữ task vẽ để thực thi; phần giải thích do LLM cuối đảm nhận."""
    kept = [t for t in plan["tasks"] if t.get("operation") in DRAW_OPERATIONS]
    ids = {t["id"] for t in kept}
    tasks = []
    for t in kept:
        t = dict(t)
        t["depends_on"] = [d for d in t.get("depends_on", []) if d in ids]
        tasks.append(t)
    return {**plan, "tasks": tasks}


def _answer_math_only(question: str, conversation_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Câu hỏi toán không cần vẽ: xin LLM lời giải rồi trả luôn."""
    prompt = build_final_answer_user_prompt(
        mode="math_only",
        question=question,
        summary=state.get("summary", ""),
        recent_turns=state.get("recent_turns", []),
    )
    try:
        answer = _generate_text(FINAL_ANSWER_SYSTEM_PROMPT, prompt)
    except LLMClientError as exc:
        logger.exception("Lỗi LLM khi tạo lời giải")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    state_manager.add_turn(conversation_id, question, answer)
    return _new_response(conversation_id, answer)


def _explain_after_drawing(
    question: str,
    conversation_id: str,
    ordered_tasks: List[dict],
    exec_result: Dict[str, Any],
    plan: Dict[str, Any],
    reports: List[dict],
) -> str:
    """Sau khi vẽ: gửi câu hỏi + tọa độ mới (không gửi constraint) để LLM giải thích."""
    state = state_manager.get_state(conversation_id)

    # Tọa độ đang có trên canvas; điểm của task vừa chạy (đã kiểm tra/sửa) ghi đè.
    points = _collect_state_points(state)
    operations = []
    for task in ordered_tasks:
        task_input = task.get("input") or {}
        coords = task_input.get("coordinates")
        if isinstance(coords, dict):
            points.update(coords)
        operations.append({
            "operation": task.get("operation"),
            "vertices": task_input.get("vertices"),
            "base_order": task_input.get("base_order"),
        })
    points = {
        name: [round(float(v), 4) for v in values]
        for name, values in points.items()
        if isinstance(values, (list, tuple))
    }

    objects = []
    for item in exec_result.get("results", []):
        if item.get("status") == "success" and isinstance(item.get("result"), list):
            for obj in item["result"]:
                if isinstance(obj, dict):
                    objects.append({k: obj[k] for k in ("id", "kind", "label", "dimension") if k in obj})

    prompt = build_final_answer_user_prompt(
        mode="after_drawing",
        question=question,
        summary=state.get("summary", ""),
        recent_turns=state.get("recent_turns", []),
        points=points,
        operations=operations,
        objects=objects,
        notes=[n for n in plan.get("notes", []) if isinstance(n, str)],
    )
    try:
        return _generate_text(FINAL_ANSWER_SYSTEM_PROMPT, prompt)
    except LLMClientError:
        logger.exception("Lỗi LLM khi giải thích sau khi vẽ")
        return (
            _build_success_message(plan, reports, exec_result)
            + " Mình đã vẽ xong hình nhưng chưa tạo được lời giải chi tiết, "
              "bạn hãy gửi lại câu hỏi để mình giải thích nhé."
        )


# ======================================================
# HÀM CHÍNH
# ======================================================

def xuly_thongtin(current_question: str, conversation_id: str = DEFAULT_CONVERSATION_ID):
    conversation_id = conversation_id or DEFAULT_CONVERSATION_ID

    # 1. State hiện tại
    state = state_manager.get_state(conversation_id)
    print("..............",state["canvas_objects"])

    # 2. Orchestrator chia plan
    try:
        plan = create_plan(current_question, state, llm_client)
        print("plan-----------",plan)
    except LLMClientError as exc:
        logger.exception("Lỗi gọi LLM khi tạo plan")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except PlanValidationError as exc:
        logger.warning("Plan không hợp lệ: %s", exc)
        return _new_response(
            conversation_id,
            "Mình chưa lập được kế hoạch hợp lệ cho yêu cầu này, bạn thử diễn đạt lại nhé.",
            success=False, errors=[str(exc)],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    tasks = plan.get("tasks", [])
    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tasks generated in the plan.",
        )

    # 2b. Yêu cầu mơ hồ -> hỏi lại, không vẽ.
    if plan.get("ambiguous") or all(t.get("operation") == "clarify" for t in tasks):
        question = " ".join(n for n in plan.get("notes", []) if isinstance(n, str)) \
            or "Bạn có thể nói rõ hơn yêu cầu được không?"
        state_manager.add_turn(conversation_id, current_question, question)
        return _new_response(conversation_id, question)

    state_manager.set_tasks(conversation_id, tasks)

    # 2c. Không có task vẽ -> câu hỏi toán thuần: xin LLM lời giải và trả luôn.
    if not any(t.get("operation") in DRAW_OPERATIONS for t in tasks):
        return _answer_math_only(current_question, conversation_id, state)

    # Có task vẽ: chỉ thực thi task vẽ, phần giải thích do LLM cuối đảm nhận.
    plan = _keep_draw_tasks(plan)

    # 3. Kiểm tra plan + sắp xếp task (dùng lại logic của ExecutionController)
    try:
        execution_controller.validate_plan(plan)
        ordered_tasks = execution_controller.sort_tasks(plan["tasks"])
    except (ValueError, TypeError, KeyError) as exc:
        return _new_response(
            conversation_id, "Kế hoạch được tạo ra không hợp lệ, chưa vẽ gì cả.",
            success=False, errors=[str(exc)],
        )

    # 4. Kiểm tra ràng buộc cho TẤT CẢ task trước khi vẽ bất cứ thứ gì
    validation = _validate_geometry_tasks(ordered_tasks, state, conversation_id)
    if not validation["ok"]:
        lines = [
            f"Mình chưa vẽ vì tọa độ chưa thỏa mãn ràng buộc hình học (task {validation['task_id']})."
        ]
        if validation.get("message"):
            lines.append(validation["message"])
        for item in validation.get("failed_constraints", []):
            lines.append(f"- {item['constraint_type']}: {item['reason']}")
        logger.warning("Validation thất bại: %s", validation)
        return _new_response(
            conversation_id, "\n".join(lines), success=False,
            errors=[validation.get("message", "")],
            validation=validation.get("reports", []),
        )

    # 5. Cập nhật coordinate_control vào snapshot state để add_object lưu cùng object
    state = state_manager.get_state(conversation_id)
    merged_control = dict(state.get("coordinate_control") or {})
    for task in ordered_tasks:
        for name, control in ((task.get("input") or {}).get("coordinate_control") or {}).items():
            if isinstance(control, dict):
                merged_control[_normalize_point_name(name)] = control
    state["coordinate_control"] = merged_control

    # 6. Thực thi plan: vẽ + cập nhật State
    exec_result = execution_controller.run(plan, state)
    logger.info("Execution result: %s", exec_result)

    # 7. Lưu constraint đã kiểm tra, ghi lịch sử hội thoại
    try:
        _persist_validation(conversation_id, ordered_tasks, exec_result.get("results", []))
    except Exception:  # noqa: BLE001
        logger.exception("Không lưu được thông tin validation vào State")

    if exec_result.get("success"):
        content = _explain_after_drawing(
            current_question, conversation_id, ordered_tasks,
            exec_result, plan, validation["reports"],
        )
    else:
        errs = [e.get("error", str(e)) if isinstance(e, dict) else str(e)
                for e in exec_result.get("errors", [])]
        content = "Có lỗi khi thực thi: " + "; ".join(errs)

    state_manager.add_turn(conversation_id, current_question, content)
    print(exec_result.get("canvas") or _empty_canvas())
    return _new_response(
        conversation_id,
        content,
        canvas=exec_result.get("canvas") or _empty_canvas(),
        success=bool(exec_result.get("success")),
        errors=[e.get("error", str(e)) if isinstance(e, dict) else str(e)
                for e in exec_result.get("errors", [])],
        validation=validation["reports"],
    )