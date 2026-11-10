# Gia sư Toán AI

Ứng dụng gia sư toán học có thể giải câu hỏi bằng mô hình Gemini và minh họa
các đối tượng hình học trên canvas 2D/3D. Người dùng gửi câu hỏi trong giao diện
web; backend lập kế hoạch, kiểm tra dữ kiện hình học, thực thi phép tính hoặc
thao tác vẽ rồi trả kết quả về frontend.

## Tính năng

- Trò chuyện để hỏi bài toán và nhận lời giải.
- Lập kế hoạch và thực thi các tác vụ toán học, hình học.
- Vẽ đối tượng 2D bằng React-Konva và hình học 3D bằng Three.js.
- Lưu trạng thái hội thoại và đối tượng canvas theo `conversation_id`.
- Kiểm tra ràng buộc, tọa độ và các phép dựng hình trước khi cập nhật canvas.

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

- Python 3.10 trở lên.
- Node.js và npm.
- API key Google Gemini để sử dụng các tính năng AI.

## Cài đặt và chạy

Mở hai terminal tại thư mục gốc của dự án.

### 1. Backend

Tạo môi trường ảo và cài các thư viện backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic-settings sqlalchemy python-dotenv \
  google-genai sympy numpy scipy
```

Trên Windows PowerShell, kích hoạt môi trường bằng:

```powershell
.\.venv\Scripts\Activate.ps1
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
npm install
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

Để bắt đầu hội thoại mới, có thể truyền `conversation_id` rỗng. Backend phản
hồi nội dung trợ lý cùng các thay đổi canvas (`add`, `update`, `remove`) để
frontend cập nhật giao diện.

## Kiểm thử

Từ thư mục gốc, kích hoạt môi trường Python rồi chạy:

```bash
cd backend
PYTHONPATH=. python -m unittest discover -s test -p 'test_*.py'
```

## Khắc phục sự cố

- **Thiếu cấu hình backend:** kiểm tra đã đặt `PROJECT_NAME`, `PORT` và biến
  `GEMINI_API_KEY` trong terminal chạy backend.
- **Không gửi được câu hỏi:** xác nhận backend đang chạy tại cổng `8000`.
- **Lỗi CORS khi chạy frontend:** backend hiện cho phép origin
  `http://localhost:5173`; truy cập frontend bằng đúng địa chỉ này.
- **Không thấy hình trong canvas:** chọn đúng chế độ 2D/3D; hình không gian
  được hiển thị trong canvas 3D.
