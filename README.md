# Gia sư Toán AI

Ứng dụng gia sư toán học có thể giải câu hỏi bằng mô hình Gemini và minh họa
các đối tượng hình học trên canvas 2D/3D. Người dùng gửi câu hỏi trong giao diện
web; backend lập kế hoạch, kiểm tra dữ kiện hình học, thực thi phép tính hoặc
thao tác vẽ rồi trả kết quả về frontend.

## Tính năng

- Trò chuyện để hỏi bài toán và nhận lời giải.
- Lập kế hoạch và thực thi các tác vụ toán học, hình học.
- Dựng hình theo quan hệ điểm/phép dựng trong cả 2D và 3D; các điểm phụ thuộc
  được tính lại khi điểm nguồn được cập nhật.
- Hỏi lại khi tham chiếu đối tượng không duy nhất hoặc phép dựng thiếu dữ kiện.
- Vẽ đối tượng 2D bằng React-Konva và hình học 3D bằng Three.js.
- Lưu trạng thái hội thoại và đối tượng canvas theo `conversation_id`.
- Kiểm tra ràng buộc, tọa độ và các phép dựng hình trước khi cập nhật canvas.

## Cách đọc và thao tác với hình vẽ

| Tình huống | Hành vi của hệ thống |
|---|---|
| Đề cho độ dài hoặc góc | Với hình minh họa (`drawing_mode="sketch"`), mô hình có thể chọn tọa độ dễ nhìn. Backend kiểm tra thứ tự lớn, bé, bằng nhau của các số đo minh họa được khai báo và loại góc nhọn, vuông, tù. Lời giải dùng dữ kiện đề bài. Khi đề cho tọa độ hoặc yêu cầu đúng tỉ lệ, mô hình được hướng dẫn dùng quy trình chính xác. |
| Muốn ghi “9 cm” trên AB | Có thể cho số đo ngay từ đầu hoặc yêu cầu “Thêm nhãn 9 cm cho cạnh AB”. Nhãn bám theo điểm neo; sửa nhãn không đổi tọa độ. Canvas hiển thị nội dung nhãn do kế hoạch truyền xuống, gồm chữ, đơn vị và ký hiệu cho cạnh, góc, điểm, bán kính, đường kính hoặc chiều cao. |
| Bài cần đường phụ | Canvas đọc quan hệ và phép dựng để hiện nét cần thiết. Ví dụ, hình chiếu của P lên đường UV có đoạn nối P với chân chiếu. Trong 3D, mặt phẳng được tham chiếu bằng ba đỉnh được minh họa bằng một tam giác tô nhẹ. Nếu lời giải cần thêm một đoạn chưa có trong dữ kiện, kế hoạch phải yêu cầu vẽ đoạn đó. |
| Nối hai điểm bằng chuột | Trong hội thoại đang mở, nhấp đúp điểm đầu rồi nhấp một điểm khác trên canvas 2D hoặc 3D để thêm đoạn nối vào hình. |
| Bắt đầu lại | Nút **Xóa hội thoại và hình vẽ** trên thanh chat xóa tin nhắn, hình và ngữ cảnh phía máy chủ của hội thoại hiện tại. Tin nhắn kế tiếp bắt đầu hội thoại mới. |

## Từ câu hỏi đến hình vẽ

1. Frontend gửi câu hỏi và mã hội thoại đến FastAPI. [chatService.ts](fontend/src/services/chatService.ts)
2. Gemini lập kế hoạch dựa trên đề bài và trạng thái hiện tại. Kế hoạch có thể yêu cầu trả lời, hỏi lại, dựng điểm, vẽ hoặc cập nhật đối tượng. [orchestrator.py](backend/orchestrator/orchestrator.py)
3. Với tác vụ hình học, backend tập hợp tọa độ và ràng buộc, tính điểm phụ thuộc, giải các ràng buộc tọa độ bằng SciPy khi cần rồi kiểm định kết quả. Khi kiểm định thất bại, backend trả thông tin lỗi trước bước vẽ. [xuly_chatbot.py](backend/controller/xuly_chatbot.py) · [geometry_solver_pipeline.py](backend/geometry_validator/geometry_solver_pipeline.py)
4. Bộ thực thi cập nhật trạng thái của hội thoại. Frontend nhận lời đáp và danh sách đối tượng thêm, sửa, xóa. Canvas dùng dữ liệu đối tượng để đặt nhãn và dựng nét phụ theo tọa độ hiện tại. [execution_controller.py](backend/controller/execution_controller.py) · [measurementLabels.ts](fontend/src/utils/measurementLabels.ts) · [geometryGuides.ts](fontend/src/utils/geometryGuides.ts)

## Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Backend | Python, FastAPI |
| Lập kế hoạch và trả lời | Google Gemini (`google-genai`) |
| Toán học và hình học | SymPy, NumPy, SciPy |
| Frontend | React, TypeScript, Vite |
| Canvas | React-Konva (2D), Three.js / React Three Fiber (3D) |
| Quản lý trạng thái | Zustand |

## Cấu trúc dự án

```text
.
├── backend/
│   ├── controller/          # Điều phối hội thoại và thực thi
│   ├── geometry_validator/  # Kiểm tra ràng buộc và phép dựng hình
│   ├── math_engine/         # Các phép toán và hàm vẽ
│   ├── orchestrator/        # Lập kế hoạch tác vụ, tích hợp Gemini
│   ├── router/              # API FastAPI
│   ├── state/               # Trạng thái hội thoại/canvas
│   └── test/                # Kiểm thử backend
└── fontend/
    └── src/
        ├── components/      # Giao diện chat và canvas
        ├── services/        # Gọi API backend
        ├── store/           # Trạng thái ứng dụng
        └── types/           # Kiểu dữ liệu TypeScript
```

> Thư mục frontend hiện có tên `fontend` (không phải `frontend`); hãy giữ nguyên
> tên này khi chạy các lệnh bên dưới.

## Yêu cầu

- Python (môi trường phát triển dùng Python 3.12).
- Node.js và npm.
- API key Google Gemini để sử dụng các tính năng AI.

## Cài đặt và chạy

Mở hai terminal tại thư mục gốc của dự án.

### 1. Backend

Tạo môi trường ảo và cài các thư viện backend:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Trên Windows PowerShell, kích hoạt môi trường bằng:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Thiết lập các biến môi trường cần thiết. `PROJECT_NAME` và `PORT` được đọc khi
backend khởi động; `GEMINI_API_KEY` được dùng để gọi Gemini.

```bash
export PROJECT_NAME="Gia su Toan AI"
export PORT=8000
export GEMINI_API_KEY="your_gemini_api_key"
# Tùy chọn:
export GEMINI_MODEL="gemini-3.5-flash-lite"
```

Không đưa API key vào mã nguồn hoặc commit API key lên Git.

Trong PowerShell, dùng `$env:PROJECT_NAME = "Gia su Toan AI"`,
`$env:PORT = "8000"` và `$env:GEMINI_API_KEY = "your_gemini_api_key"` trong
terminal chạy backend. Có thể đặt `GEMINI_ANSWER_MODEL` để chọn riêng mô hình trả lời.

Khởi chạy backend:

```bash
cd backend
python main.py
```

Backend chạy tại `http://localhost:8000`. Có thể mở tài liệu API tự động tại
`http://localhost:8000/docs`.

### 2. Frontend

Trong terminal thứ hai, từ thư mục gốc:

```bash
cd fontend
npm ci
npm run dev
```

Mở địa chỉ được Vite hiển thị (mặc định `http://localhost:5173`). Frontend hiện
gọi API tại `http://localhost:8000`; cần khởi động backend trước khi gửi câu hỏi.

### Build frontend

```bash
cd fontend
npm run build
```

## API trò chuyện

Endpoint chính là `POST /chat`. Request gồm mã hội thoại và nội dung câu hỏi:

```json
{
  "conversation_id": "conversation-1",
  "message": "Vẽ tam giác ABC trong không gian..."
}
```

Frontend tạo một UUID cho hội thoại mới và tái sử dụng ID này ở các lượt sau.
Client gọi API trực tiếp cũng nên cấp ID riêng: nếu gửi chuỗi rỗng tới
`/chat`, backend dùng chung ID mặc định `default_conversation`. Phản hồi
chat chứa lời đáp và các thay đổi canvas (`add`, `update`, `remove`).

| API | Dữ liệu gửi | Kết quả |
|---|---|---|
| `POST /canvas/connect-points` | `conversation_id`, `start_point`, `end_point` | Lưu và trả về đoạn nối hai điểm đã có. |
| `POST /canvas/clear` | `conversation_id` | Xóa hình và dữ liệu hình học, giữ lịch sử chat. |
| `DELETE /conversations/{conversation_id}` | ID trên đường dẫn | Xóa toàn bộ trạng thái hội thoại. Trả HTTP 204. Đây là API của nút xóa trên thanh chat. |

### Phép dựng hình 2D/3D

Task vẽ có thể khai báo `constructions` theo tên điểm để backend tính tọa độ,
thay vì yêu cầu mô hình ngôn ngữ tự đoán tọa độ cho điểm phụ thuộc. Bộ dựng hiện
hỗ trợ trung điểm, hình chiếu lên đường (2D/3D), hình chiếu lên mặt phẳng (3D),
giao điểm hai đường (2D/3D), điểm xác định đường song song/vuông góc, phân giác
góc (2D/3D) và tiếp điểm đường tròn. Trong 3D, dựng đường vuông góc cần điểm
tham chiếu để xác định mặt phẳng; tiếp tuyến cần vector pháp tuyến mặt phẳng
đường tròn. Nếu dữ kiện đó thiếu, backend hỏi bổ sung thay vì tự chọn mặt phẳng.

State duy trì `geometry_model` gồm chỉ mục đối tượng, điểm, constraints và đồ
thị dependency. Khi tọa độ một điểm được cập nhật, backend tính lại các điểm
dựng phụ thuộc và đồng bộ tọa độ lên những đối tượng cùng sử dụng điểm đó. Xóa
đối tượng nguồn cũng xóa đối tượng được dựng phụ thuộc khi không còn nguồn điểm
nào khác. State hiện vẫn được lưu trong bộ nhớ của tiến trình backend.

Tham chiếu như “đường AB” được đối chiếu với tên/nhãn đối tượng trên canvas.
“Đường vừa vẽ” chỉ dùng đối tượng focus gần nhất khi loại đối tượng khớp; nếu
không tìm thấy hoặc không xác định duy nhất được đối tượng, hệ thống hỏi lại.

### Từ khóa gợi ý và khi nào sử dụng

Không cần nhớ cú pháp nội bộ hay tên phép dựng tiếng Anh. Hãy mô tả yêu cầu
bằng tiếng Việt tự nhiên, gọi rõ tên điểm/đối tượng và nêu các dữ kiện quyết
định hình vẽ. Các từ/cụm từ dưới đây giúp AI nhận ra đúng ý định; chúng là gợi
ý diễn đạt, không phải lệnh bắt buộc.

| Từ khóa/cụm từ nên dùng | Dùng khi nào | Ví dụ |
|---|---|---|
| **vẽ**, **dựng**, **tạo** | Tạo hình hoặc đối tượng mới. Nêu rõ 2D hay 3D nếu không thể suy ra từ yêu cầu. | “Vẽ tam giác ABC trong mặt phẳng 2D.” |
| **trung điểm**, **nằm chính giữa** | Dựng điểm mới chính giữa hai điểm đã có. | “Dựng M là trung điểm của AB.” |
| **hình chiếu**, **chân đường vuông góc** | Chiếu một điểm lên đường thẳng; nêu điểm cần chiếu và đường. | “Dựng H là hình chiếu vuông góc của P lên đường thẳng AB.” |
| **hình chiếu lên mặt phẳng** | Chiếu một điểm lên mặt phẳng trong 3D; xác định mặt phẳng bằng ba điểm không thẳng hàng. | “Trong 3D, dựng H là hình chiếu của P lên mặt phẳng ABC.” |
| **giao điểm** | Tìm điểm chung của hai đường; gọi tên hai đường bằng điểm xác định chúng. Trong 3D, hai đường phải thực sự cắt nhau, không phải hai đường chéo nhau. | “Gọi I là giao điểm của AB và CD.” |
| **song song**, **cùng hướng** | Dựng đường/điểm theo hướng song song với một đường đã biết. Nêu điểm mà đường mới đi qua; nếu cần vị trí điểm cụ thể, hãy cho thêm độ dài và phía/hướng. | “Qua P, dựng đường thẳng song song AB.” |
| **vuông góc**, **đường vuông góc** | Dựng hướng vuông góc với đường đã biết. Trong 3D, hãy nêu thêm một điểm hoặc mặt phẳng để xác định duy nhất hướng vuông góc. | “Trong mặt phẳng ABC, qua P dựng đường vuông góc với AB.” |
| **phân giác**, **chia đôi góc** | Dựng phân giác của góc; ghi đủ ba điểm và để điểm giữa là đỉnh góc. Có thể nêu phân giác trong hay ngoài. | “Dựng tia phân giác trong của góc ABC.” |
| **tiếp tuyến**, **tiếp điểm** | Dựng tiếp điểm từ điểm ngoài đến đường tròn; nêu tâm, bán kính, điểm ngoài. Có hai tiếp điểm thì chỉ rõ chọn bên nào nếu cần. Trong 3D, nêu thêm mặt phẳng hoặc vector pháp tuyến của mặt phẳng đường tròn. | “Đường tròn tâm O bán kính 3; từ D ở ngoài đường tròn, dựng tiếp điểm T phía trên.” |
| **cập nhật**, **di chuyển**, **đổi tọa độ** | Sửa điểm/đối tượng đã có. Dùng tên rõ ràng và ghi tọa độ mới nếu muốn vị trí chính xác; các điểm phụ thuộc sẽ được tính lại. | “Di chuyển A đến (2, 1), giữ nguyên các quan hệ dựng hình.” |
| **xóa**, **bỏ**, **loại bỏ** | Xóa điểm hoặc đối tượng; gọi rõ tên để tránh xóa nhầm. Đối tượng phụ thuộc có thể bị xóa theo nếu không còn nguồn điểm nào khác. | “Xóa đường thẳng CD.” |
| **đường vừa vẽ**, **điểm đó**, **hình này** | Tiếp tục nói về đối tượng gần nhất trong hội thoại/canvas khi chỉ có một đối tượng phù hợp. Nếu có nhiều đối tượng cùng loại, dùng tên cụ thể như “đường AB”. | “Xóa đường vừa vẽ.” |
| **giải thích**, **chứng minh**, **tính** | Yêu cầu giải bài toán thay vì chỉ tạo/cập nhật hình. Nêu kết luận hoặc đại lượng cần tìm và giả thiết liên quan. | “Tính độ dài AB và giải thích cách làm.” |

#### Cách viết yêu cầu để AI hiểu chính xác hơn

Nên viết theo thứ tự: **việc cần làm → không gian 2D/3D → tên đối tượng →
quan hệ hoặc dữ kiện → kết quả mong muốn**. Hãy dùng tên điểm nhất quán trong
cùng một hội thoại; nếu một dữ kiện chưa được xác định thì nói rõ để AI hỏi
lại, thay vì yêu cầu tự chọn một giá trị bất kỳ.

```text
2D: Vẽ tam giác ABC với A(0,0), B(4,0), C(1,3).
Dựng M là trung điểm AB, rồi dựng H là hình chiếu vuông góc của M lên BC.

3D: Vẽ tứ diện ABCD trong không gian 3D.
Dựng H là hình chiếu vuông góc của D lên mặt phẳng ABC.
Nếu chưa có tọa độ hoặc mặt phẳng chưa xác định, hãy hỏi tôi trước.
```

Khi cần cập nhật hoặc xóa, hãy nêu tên điểm/đối tượng và hành động rõ ràng.
Ví dụ: “Di chuyển C đến (1, 4)” hoặc “Xóa đường thẳng AB”. Nếu có nhiều điểm
cùng tên hoặc nhiều đối tượng phù hợp, bổ sung mô tả như “đường AB trong hình
3D bên phải” để AI có thể hỏi lại khi vẫn chưa xác định duy nhất được.

## Kiểm thử

Trên Windows PowerShell, từ thư mục gốc:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m unittest discover -s backend/test
cd fontend
node --test tests/point-connection.test.mjs
npm.cmd run build
```

Bài kiểm tra frontend mô phỏng luồng chọn hai điểm; lệnh build kiểm tra
TypeScript và đóng gói giao diện. Để kiểm tra toàn bộ luồng chat qua Gemini,
cần backend có API key và frontend đang chạy.

Từ thư mục gốc, kích hoạt môi trường Python rồi chạy:

```bash
cd backend
PYTHONPATH=. python -m unittest discover -s test -p 'test_*.py'
```

Mặc định các kiểm thử không gọi API LLM. Để chạy thêm bộ đánh giá paraphrase
tiếng Việt qua Gemini (cần `GEMINI_API_KEY`), chạy từ thư mục `backend`:

```bash
RUN_GEOMETRY_LLM_EVAL=1 PYTHONPATH=. python -m unittest discover -s test -p 'test_geometry_language_eval.py'
```

## Khắc phục sự cố

- **Thiếu cấu hình backend:** kiểm tra đã đặt `PROJECT_NAME`, `PORT` và biến
  `GEMINI_API_KEY` trong terminal chạy backend.
- **Không gửi được câu hỏi:** xác nhận backend đang chạy tại cổng `8000`.
- **Lỗi CORS khi chạy frontend:** backend hiện cho phép origin
  `http://localhost:5173`; truy cập frontend bằng đúng địa chỉ này.
- **Không thấy hình trong canvas:** chọn đúng chế độ 2D/3D; hình không gian
  được hiển thị trong canvas 3D.
