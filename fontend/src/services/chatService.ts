import type {
  CanvasObject,
  ChatAttachments,
  ChatRequest,
  ChatResponse,
  LLMProgress,
} from '@/types'


type ChatEvent =
  | { type: 'progress'; data: LLMProgress }
  | { type: 'result'; data: ChatResponse }
  | { type: 'error'; data: { status: number; detail: string } }

const API_BASE_URL = 'http://localhost:8000'

function encodeMedia(blob?: Blob): Promise<{ mime_type: string; data: string } | undefined> {
  if (!blob) return Promise.resolve(undefined)

  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const mime = blob.type.split(';')[0]
      const dataUrl = String(reader.result)
      resolve({
        mime_type: mime === 'audio/mp4' ? 'audio/m4a' : mime,
        data: dataUrl.slice(dataUrl.indexOf(',') + 1),
      })
    }
    reader.onerror = () => reject(new Error('Không thể đọc tệp đính kèm.'))
    reader.readAsDataURL(blob)
  })
}

export const chatService = {
  async deleteConversation(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/conversations/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
  },

  async send(
    request: ChatRequest,
    attachments?: ChatAttachments,
    onProgress?: (progress: LLMProgress) => void,
  ): Promise<ChatResponse> {
    const [image, audio] = await Promise.all([
      encodeMedia(attachments?.image),
      encodeMedia(attachments?.audio),
    ])
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...request, image, audio }),
    })

    if (!response.ok || !response.body) {
      const payload = await response.json().catch(() => null)
      throw new Error(
        payload?.errors?.[0]?.message ?? payload?.detail ??
        `Không thể xử lý câu hỏi (HTTP ${response.status}).`,
      )
    }

    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
    let pending = ''
    let result: ChatResponse | undefined
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        pending += value
        const lines = pending.split('\n')
        pending = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.trim()) continue
          const event = JSON.parse(line) as ChatEvent
          if (event.type === 'progress') onProgress?.(event.data)
          if (event.type === 'result') result = event.data
          if (event.type === 'error') throw new Error(event.data.detail)
        }
      }
    } finally {
      await reader.cancel().catch(() => undefined)
      reader.releaseLock()
    }

    if (!result) throw new Error('Kết nối kết thúc trước khi nhận được câu trả lời.')
    return result
  },

  async connectPoints(
    conversationId: string,
    startPoint: string,
    endPoint: string,
  ): Promise<CanvasObject> {
    const response = await fetch(`${API_BASE_URL}/canvas/connect-points`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        start_point: startPoint,
        end_point: endPoint,
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(
        `Canvas connect API error: ${response.status} ${errorText}`,
      )
    }

    return await response.json() as CanvasObject
  },

  async clearCanvas(
    conversationId: string,
  ): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/canvas/clear`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ conversation_id: conversationId }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(
        `Canvas clear API error: ${response.status} ${errorText}`,
      )
    }

    return await response.json() as ChatResponse
  },

}
