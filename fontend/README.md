# MathAI Frontend

Giao diện React cho hệ thống AI Gia Sư Toán.

## Cài đặt & chạy

```bash
# 1. Cài dependencies
npm install

# 2. Chạy development server
npm run dev
```

Mở trình duyệt tại `http://localhost:5173`

> **Lưu ý**: Backend FastAPI phải đang chạy tại `http://localhost:8000`

## Cấu trúc thư mục

```
src/
├── types/          # TypeScript types (khớp với backend schema)
├── services/       # Axios API layer
├── store/          # Zustand global state
├── hooks/          # Custom hooks (viewport, canvas)
├── utils/          # mathParser - parse equation string
└── components/
    ├── ui/         # Badge, Spinner, IconBtn, Tooltip
    ├── chat/       # ChatPanel, ChatMessage, ChatInput, ObjectList
    └── canvas/     # CanvasPanel, Canvas2D (Konva), Canvas3D (Three.js)
```

## Luồng dữ liệu

```
User nhập → ChatInput
          → useAppStore.sendMessage()
          → chatService.send({ text, trang_thai })
          → POST /chat (backend)
          → Response: { reply, local_state, knowledge, ... }
          → Cập nhật messages + canvasObjects + trangThai
          → Canvas2D render objects từ local_state
```

## Thêm loại object mới

Trong `Canvas2D.tsx`, thêm case vào component `RenderObject`:

```tsx
if (o.type === 'circle') {
  // render circle
}
```

Trong `types/index.ts`, thêm interface:

```ts
export interface CircleObject {
  type: 'circle'
  center: [number, number]
  radius: number
  color?: string
}
```

## Tech stack

| Thư viện | Mục đích |
|---|---|
| React 18 + Vite | Framework |
| TypeScript | Type safety |
| Tailwind CSS | Styling |
| Zustand | Global state |
| Axios | API calls |
| React-Konva | Canvas 2D |
| Three.js + R3F | Canvas 3D |
| mathjs | Parse equation strings |
