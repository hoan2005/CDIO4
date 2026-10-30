import { useEffect, useRef, useState } from 'react'
import ChatPanel from '@/components/chat/ChatPanel'
import CanvasPanel from '@/components/canvas/CanvasPanel'

export default function App() {
  // Chiều rộng hiện tại của khu vực Chat.
  const [chatWidth, setChatWidth] = useState(380)

  // Cho phép ẩn/hiện khu vực Canvas 2D/3D.
  const [showCanvas, setShowCanvas] = useState(true)

  // Trạng thái đang kéo thanh phân cách.
  const [isResizing, setIsResizing] = useState(false)

  const resizingRef = useRef(false)

  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (event: MouseEvent) => {
      const minChatWidth = 320
      const minCanvasWidth = 400

      const maxChatWidth = window.innerWidth - minCanvasWidth

      const newWidth = Math.min(
        Math.max(event.clientX, minChatWidth),
        Math.max(minChatWidth, maxChatWidth),
      )

      setChatWidth(newWidth)
    }

    const handleMouseUp = () => {
      resizingRef.current = false
      setIsResizing(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    // Tránh kéo chọn text trong lúc resize.
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)

      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }
  }, [isResizing])

  const handleResizeStart = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault()

    resizingRef.current = true
    setIsResizing(true)
  }

  return (
    <div
      className="
        relative
        flex
        h-screen
        w-screen
        overflow-hidden
        bg-bg-primary
      "
    >
      {/* ====================================================
          CHAT
      ==================================================== */}

      <div
        className="
          relative
          h-full
          min-w-0
          flex-shrink-0
          overflow-hidden
          border-r
          border-border
        "
        style={{
          width: showCanvas ? `${chatWidth}px` : '100%',
        }}
      >
        <ChatPanel />

        {/* Nút hiện lại Canvas khi Canvas đang bị ẩn */}
        {!showCanvas && (
          <button
            type="button"
            onClick={() => setShowCanvas(true)}
            className="
              absolute
              right-4
              top-4
              z-50
              rounded-lg
              border
              border-border
              bg-white
              px-3
              py-2
              text-sm
              font-medium
              text-gray-700
              shadow-sm
              transition
              hover:bg-gray-50
              active:scale-95
            "
          >
            Hiện minh họa
          </button>
        )}
      </div>

      {/* ====================================================
          RESIZE HANDLE
          Chỉ hiển thị khi Canvas đang mở.
      ==================================================== */}

      {showCanvas && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Kéo để thay đổi kích thước Chat và Canvas"
          onMouseDown={handleResizeStart}
          className={`
            relative
            z-40
            h-full
            w-[6px]
            flex-shrink-0
            cursor-col-resize
            transition-colors
            ${
              isResizing
                ? 'bg-blue-500'
                : 'bg-border hover:bg-blue-300'
            }
          `}
        >
          {/* Vạch nhỏ ở giữa để người dùng dễ nhận biết có thể kéo */}
          <div
            className="
              absolute
              left-1/2
              top-1/2
              h-12
              w-[3px]
              -translate-x-1/2
              -translate-y-1/2
              rounded-full
              bg-gray-300
            "
          />
        </div>
      )}

      {/* ====================================================
          CANVAS
      ==================================================== */}

      {showCanvas && (
        <div
          className="
            relative
            h-full
            min-w-0
            flex-1
            overflow-hidden
          "
        >
          {/* Nút ẩn Canvas */}
          <button
            type="button"
            onClick={() => setShowCanvas(false)}
            className="
              absolute
              right-4
              top-4
              z-50
              rounded-lg
              border
              border-border
              bg-white
              px-3
              py-2
              text-sm
              font-medium
              text-gray-700
              shadow-sm
              transition
              hover:bg-gray-50
              active:scale-95
            "
          >
            Ẩn minh họa
          </button>

          <CanvasPanel />
        </div>
      )}
    </div>
  )
}
