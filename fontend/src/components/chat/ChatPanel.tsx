import { useEffect, useRef } from 'react'

import {
  useAppStore,
} from '@/store/useAppStore'

import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'


// ============================================================
// CHAT PANEL
// ============================================================

export default function ChatPanel() {

  // ==========================================================
  // LẤY MESSAGE TỪ ZUSTAND
  // ==========================================================

  const messages =
    useAppStore(
      state => state.messages
    )


  // ==========================================================
  // REF CUỐI DANH SÁCH MESSAGE
  // ==========================================================

  const messagesEndRef =
    useRef<HTMLDivElement | null>(null)


  // ==========================================================
  // TỰ ĐỘNG SCROLL XUỐNG MESSAGE MỚI NHẤT
  // ==========================================================

  useEffect(() => {

    messagesEndRef.current?.scrollIntoView({
      behavior: 'smooth',
    })

  }, [messages])


  // ==========================================================
  // UI
  // ==========================================================

  return (

    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: 0,
        background: '#F8FAFC',
        borderRight: '1px solid #E2E8F0',
      }}
    >

      {/* ====================================================
          HEADER
      ==================================================== */}

      <div
        style={{
          padding: '18px 20px',
          background: '#FFFFFF',
          borderBottom: '1px solid #E2E8F0',
        }}
      >

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >

          {/* ICON */}

          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '12px',
              background: '#EEF2FF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
            }}
          >
            📚
          </div>


          {/* TITLE */}

          <div>

            <div
              style={{
                fontSize: '17px',
                fontWeight: 600,
                color: '#1E293B',
              }}
            >
              Trợ lý học tập AI
            </div>

            <div
              style={{
                marginTop: '3px',
                fontSize: '12px',
                color: '#64748B',
              }}
            >
              Hỏi bài • Khám phá • Trực quan hóa
            </div>

          </div>

        </div>

      </div>


      {/* ====================================================
          MESSAGE AREA
      ==================================================== */}

      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          padding: '20px',
        }}
      >

        {/* EMPTY STATE */}

        {messages.length === 0 && (

          <div
            style={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              padding: '20px',
            }}
          >

            <div
              style={{
                maxWidth: '320px',
              }}
            >

              <div
                style={{
                  fontSize: '40px',
                  marginBottom: '14px',
                }}
              >
                🎓
              </div>

              <div
                style={{
                  fontSize: '18px',
                  fontWeight: 600,
                  color: '#334155',
                  marginBottom: '8px',
                }}
              >
                Bạn muốn học gì hôm nay?
              </div>

              <div
                style={{
                  fontSize: '14px',
                  lineHeight: 1.6,
                  color: '#64748B',
                }}
              >
                Hãy đặt câu hỏi về Toán học.
                AI có thể giải thích và trực quan hóa
                nội dung trên bảng bên cạnh.
              </div>

            </div>

          </div>

        )}


        {/* MESSAGE LIST */}

        {messages.map(message => (

          <ChatMessage
            key={message.id}
            message={message}
          />

        ))}


        {/* SCROLL TARGET */}

        <div
          ref={messagesEndRef}
        />

      </div>


      {/* ====================================================
          INPUT AREA
      ==================================================== */}

      <div
        style={{
          padding: '12px 16px 16px',
          background: '#FFFFFF',
          borderTop: '1px solid #E2E8F0',
        }}
      >

        <ChatInput />

        <div
          style={{
            marginTop: '7px',
            textAlign: 'center',
            fontSize: '11px',
            color: '#94A3B8',
          }}
        >
          Trợ lý AI có thể hỗ trợ giải thích và trực quan hóa bài học
        </div>

      </div>

    </div>
  )
}