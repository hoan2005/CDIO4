import type { Message } from '@/types'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import remarkGfm from 'remark-gfm'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'

// Gỡ backtick vô tình bọc quanh công thức LaTeX, ví dụ: `$x^2$` -> $x^2$
// Nếu không xử lý bước này, ReactMarkdown sẽ nhận diện backtick trước và
// render thành <code>, khiến rehype-katex không bao giờ thấy được công thức
// để chuyển thành ký hiệu toán học (hiện ra nguyên văn mã LaTeX trong ô xám).
function stripBackticksAroundMath(content: string): string {
  let result = content

  // `$$...$$` -> $$...$$  (khối công thức bị bọc trong 1 backtick)
  result = result.replace(/`(\$\$[\s\S]+?\$\$)`/g, '$1')

  // `$...$` -> $...$  (công thức inline bị bọc trong 1 backtick)
  result = result.replace(/`(\$[^`$\n]+?\$)`/g, '$1')

  // `\[...\]` -> \[...\]  và  `\(...\)` -> \(...\)
  result = result.replace(/`(\\\[[\s\S]+?\\\])`/g, '$1')
  result = result.replace(/`(\\\([\s\S]+?\\\))`/g, '$1')

  // ```$$...$$``` -> $$...$$  (lỡ bọc trong code block 3 dấu backtick)
  result = result.replace(/```\s*(\$\$[\s\S]+?\$\$)\s*```/g, '$1')

  return result
}

// Chuẩn hóa các chuỗi biến đổi toán học để mỗi bước nằm trên một hàng.
// Ví dụ:
// 2x = 8 ⇔ x = 4
// sẽ được hiển thị thành:
// 2x = 8
// ⇔ x = 4
function formatMathSteps(content: string): string {
  let result = content

  // Xử lý các khối LaTeX đã được đặt trong $...$, $$...$$, \(...\), \[...\].
  // Nếu bên trong có ⇔ thì tách thành nhiều khối công thức riêng.
  const mathPatterns = [
    /\$\$([\s\S]*?)\$\$/g,
    /\\\[([\s\S]*?)\\\]/g,
    /\\\(([\s\S]*?)\\\)/g,
    /(?<!\$)\$([^$\n]+?)\$(?!\$)/g,
  ]

  for (const pattern of mathPatterns) {
    result = result.replace(pattern, (fullMatch, body: string) => {
      if (!body.includes('⇔')) {
        return fullMatch
      }

      const steps = body
        .split(/\s*⇔\s*/)
        .map((step) => step.trim())
        .filter(Boolean)

      return steps
        .map((step, index) => {
          const prefix = index === 0 ? '' : '\\Leftrightarrow\\quad '
          return `$$${prefix}${step}$$`
        })
        .join('\n\n')
    })
  }

  // Trường hợp LLM trả về phương trình không có dấu LaTeX nhưng có ⇔.
  // Ví dụ: 2x = 8 ⇔ x = 4
  result = result.replace(/\s*⇔\s*/g, '\n\n⇔ ')

  return result
}

interface ChatMessageProps {
  message: Message
}

export default function ChatMessage({
  message,
}: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser
          ? 'flex-end'
          : 'flex-start',
        alignItems: 'flex-start',
        gap: '9px',
        marginBottom: '16px',
      }}
    >
      {/* ======================================================
          AVATAR CỦA AI
      ====================================================== */}

      {!isUser && (
        <div
          style={{
            flexShrink: 0,
            width: '34px',
            height: '34px',
            marginTop: '2px',
            borderRadius: '10px',
            background: '#EEF2FF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '17px',
          }}
        >
          🤖
        </div>
      )}

      {/* ======================================================
          MESSAGE CONTENT
      ====================================================== */}

      <div
        style={{
          // Cho AI rộng hơn để các bước toán dễ đọc.
          // Tin nhắn của người dùng vẫn giữ kích thước gọn hơn.
          maxWidth: isUser ? '78%' : '94%',
        }}
      >
        {/* Tên người gửi */}

        <div
          style={{
            marginBottom: '5px',
            paddingLeft: isUser ? '0' : '3px',
            paddingRight: isUser ? '3px' : '0',
            textAlign: isUser ? 'right' : 'left',
            fontSize: '11px',
            fontWeight: 600,
            color: '#64748B',
          }}
        >
          {isUser ? 'Bạn' : 'Trợ lý học tập AI'}
        </div>

        {/* ====================================================
            NỘI DUNG MESSAGE
        ==================================================== */}

        <div
          style={{
            padding: '11px 14px',
            borderRadius: isUser
              ? '16px 16px 4px 16px'
              : '16px 16px 16px 4px',

            background: isUser
              ? '#4F46E5'
              : '#FFFFFF',

            color: isUser
              ? '#FFFFFF'
              : '#334155',

            border: isUser
              ? 'none'
              : '1px solid #E2E8F0',

            boxShadow: isUser
              ? '0 2px 6px rgba(79, 70, 229, 0.18)'
              : '0 2px 6px rgba(15, 23, 42, 0.04)',

            wordBreak: 'break-word',
            fontSize: '14px',
            lineHeight: 1.7,
          }}
        >
          {message.isLoading ? (
            <LoadingDots />
          ) : (
            <div className="chat-markdown">
              <ReactMarkdown
                remarkPlugins={[remarkMath, remarkGfm]}
                rehypePlugins={[rehypeKatex]}
              >
                {formatMathSteps(stripBackticksAroundMath(message.content))}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>

      {/* ======================================================
          AVATAR CỦA NGƯỜI DÙNG
      ====================================================== */}

      {isUser && (
        <div
          style={{
            flexShrink: 0,
            width: '34px',
            height: '34px',
            marginTop: '2px',
            borderRadius: '10px',
            background: '#E0F2FE',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '17px',
          }}
        >
          👨‍🎓
        </div>
      )}

      {/* ======================================================
          MARKDOWN STYLE
      ====================================================== */}

      <style>
        {`
          .chat-markdown {
            width: 100%;
            min-width: 0;
          }

          /* Bảng Markdown (GFM): áp dụng cho mọi bảng, không phụ thuộc số cột/hàng. */
          .chat-markdown table {
            display: block;
            width: max-content;
            min-width: 100%;
            max-width: 100%;
            overflow-x: auto;
            border-collapse: collapse;
            border-spacing: 0;
            margin: 12px 0 16px;
            font-size: 14px;
            line-height: 1.5;
            -webkit-overflow-scrolling: touch;
          }

          .chat-markdown thead {
            background: rgba(148, 163, 184, 0.14);
          }

          .chat-markdown th,
          .chat-markdown td {
            border: 1px solid #CBD5E1;
            padding: 8px 12px;
            text-align: left;
            vertical-align: middle;
            min-width: 44px;
            white-space: normal;
          }

          .chat-markdown th {
            font-weight: 700;
          }

          .chat-markdown tr:nth-child(even) td {
            background: rgba(148, 163, 184, 0.07);
          }

          /* Tránh công thức trong ô bảng làm bảng bị ép nhỏ hoặc tràn khung. */
          .chat-markdown th .katex,
          .chat-markdown td .katex {
            white-space: nowrap;
          }

          /* Đoạn văn */

          .chat-markdown p {
            margin: 0 0 10px 0;

            /* Giữ các dòng mà LLM trả về.
               Ví dụ:
               2x = 8
               => x = 4
               sẽ không bị dồn thành một dòng. */
            white-space: pre-wrap;
          }

          .chat-markdown p:last-child {
            margin-bottom: 0;
          }

          /* Tiêu đề */

          .chat-markdown h1,
          .chat-markdown h2,
          .chat-markdown h3,
          .chat-markdown h4 {
            margin-top: 14px;
            margin-bottom: 8px;
            font-weight: 700;
            color: #1E293B;
          }

          .chat-markdown h1 {
            font-size: 20px;
          }

          .chat-markdown h2 {
            font-size: 18px;
          }

          .chat-markdown h3 {
            font-size: 16px;
          }

          .chat-markdown h4 {
            font-size: 15px;
          }

          /* Danh sách */

          .chat-markdown ul,
          .chat-markdown ol {
            margin-top: 6px;
            margin-bottom: 10px;
            padding-left: 22px;
          }

          .chat-markdown li {
            margin-bottom: 5px;
          }

          /* In đậm */

          .chat-markdown strong {
            font-weight: 700;
            color: inherit;
          }

          /* Code inline */

          .chat-markdown code {
            padding: 2px 5px;
            border-radius: 5px;
            background: #F1F5F9;
            color: #334155;
            font-size: 13px;
            font-family: Consolas, Monaco, monospace;
          }

          /* Code block */

          .chat-markdown pre {
            margin: 10px 0;
            padding: 12px;
            overflow-x: auto;
            border-radius: 8px;
            background: #F1F5F9;
          }

          .chat-markdown pre code {
            padding: 0;
            background: transparent;
          }

          /* Đường kẻ */

          .chat-markdown hr {
            margin: 14px 0;
            border: none;
            border-top: 1px solid #E2E8F0;
          }

          /* Link */

          .chat-markdown a {
            color: #4F46E5;
            text-decoration: underline;
          }

          /* Blockquote */

          .chat-markdown blockquote {
            margin: 10px 0;
            padding: 8px 12px;
            border-left: 4px solid #CBD5E1;
            background: #F8FAFC;
          }

          /* Công thức LaTeX */

          .chat-markdown .katex-display {
            display: block;
            width: 100%;
            box-sizing: border-box;
            margin: 14px 0;
            padding: 2px 0;

            /* Công thức dài không bị bẻ vụn giữa các ký hiệu.
               Nếu quá dài, người dùng có thể cuộn ngang. */
            overflow-x: auto;
            overflow-y: hidden;
            white-space: nowrap;
            text-align: left;
          }

          .chat-markdown .katex {
            font-size: 1.05em;
            white-space: nowrap;
          }

          /* Khoảng cách rõ ràng giữa từng bước biến đổi. */
          .chat-markdown .katex-display + .katex-display {
            margin-top: 18px;
          }
        `}
      </style>
    </div>
  )
}


// ============================================================
// LOADING DOTS
// ============================================================

function LoadingDots() {
  return (
    <>
      <style>
        {`
          @keyframes chat-loading-dot {
            0%, 60%, 100% {
              opacity: 0.25;
              transform: translateY(0);
            }

            30% {
              opacity: 1;
              transform: translateY(-3px);
            }
          }

          .chat-loading-dot {
            display: inline-block;
            animation: chat-loading-dot 1.2s infinite;
            font-size: 18px;
            line-height: 1;
            font-weight: 700;
          }

          .chat-loading-dot:nth-child(2) {
            animation-delay: 0.15s;
          }

          .chat-loading-dot:nth-child(3) {
            animation-delay: 0.3s;
          }
        `}
      </style>

      <span className="chat-loading-dot">
        .
      </span>

      <span className="chat-loading-dot">
        .
      </span>

      <span className="chat-loading-dot">
        .
      </span>
    </>
  )
}