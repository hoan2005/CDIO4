import { useState } from 'react'
import { useAppStore } from '@/store/useAppStore'


export default function ChatInput() {

  const [text, setText] = useState('')


  const sendMessage =
    useAppStore(state => state.sendMessage)

  const isLoading =
    useAppStore(state => state.isLoading)


  const handleSubmit = async () => {

    const message = text.trim()

    // Không gửi message rỗng
    if (!message) {
      return
    }

    // Đang xử lý thì không cho hỏi tiếp
    if (isLoading) {
      return
    }


    // Xóa input ngay khi gửi
    setText('')


    try {

      await sendMessage(message)

    } catch (error) {

      console.error(
        'Không thể gửi message:',
        error
      )

    }
  }


  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLTextAreaElement>
  ) => {

    // Enter để gửi
    if (
      event.key === 'Enter' &&
      !event.shiftKey
    ) {

      event.preventDefault()

      handleSubmit()

    }
  }


  return (

    <div
      style={{
        width: '100%',
        boxSizing: 'border-box',
      }}
    >

      {/* Gợi ý nhập câu hỏi */}

      <div
        style={{
          marginBottom: '8px',
          paddingLeft: '4px',
          fontSize: '12px',
          color: '#64748B',
        }}
      >
        💡 Bạn có thể hỏi về bài học, công thức hoặc cách giải
      </div>


      {/* Ô nhập + nút gửi */}

      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '10px',
          padding: '10px',
          background: '#FFFFFF',
          border: '1px solid #CBD5E1',
          borderRadius: '16px',
          boxShadow: '0 2px 8px rgba(15, 23, 42, 0.06)',
        }}
      >

        <textarea
          value={text}
          onChange={event =>
            setText(event.target.value)
          }
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder={
            isLoading
              ? 'AI đang trả lời...'
              : 'Nhập câu hỏi của bạn...'
          }
          rows={2}
          style={{
            flex: 1,
            resize: 'none',
            minHeight: '44px',
            padding: '10px 12px',
            border: 'none',
            outline: 'none',
            background: 'transparent',
            color: '#1E293B',
            fontSize: '14px',
            lineHeight: 1.5,
            fontFamily: 'inherit',
          }}
        />


        <button
          onClick={handleSubmit}
          disabled={
            isLoading ||
            text.trim() === ''
          }
          aria-label="Gửi câu hỏi"
          style={{
            minWidth: '82px',
            height: '44px',
            padding: '0 16px',
            borderRadius: '12px',
            border: 'none',
            background:
              isLoading || text.trim() === ''
                ? '#CBD5E1'
                : '#4F46E5',
            color: '#FFFFFF',
            fontSize: '14px',
            fontWeight: 600,
            cursor:
              isLoading || text.trim() === ''
                ? 'not-allowed'
                : 'pointer',
            transition: 'background 0.2s ease',
          }}
        >
          {isLoading ? 'Đang xử lý...' : 'Gửi'}
        </button>

      </div>


      {/* Hướng dẫn phím */}

      <div
        style={{
          marginTop: '7px',
          textAlign: 'center',
          fontSize: '11px',
          color: '#94A3B8',
        }}
      >
        Enter để gửi • Shift + Enter để xuống dòng
      </div>

    </div>
  )
}
