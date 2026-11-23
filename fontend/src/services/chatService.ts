import type {
  CanvasObject,
  ChatAttachments,
  ChatRequest,
  ChatResponse,
} from '@/types'


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
  ): Promise<ChatResponse> {
    const [image, audio] = await Promise.all([
      encodeMedia(attachments?.image),
      encodeMedia(attachments?.audio),
    ])

    const response = await fetch(
      `${API_BASE_URL}/chat`,
      {
        method: 'POST',

        headers: {
          'Content-Type': 'application/json',
        },

        body: JSON.stringify({ ...request, image, audio }),
      }
    )


    if (!response.ok) {

      const payload = await response.json().catch(() => null)
      if (response.status === 429) {
        throw new Error('Gemini đã chạm hạn mức. Hãy thử lại sau.')
      }
      if (attachments && typeof payload?.detail === 'string' &&
          (response.status === 422 || response.status === 502)) {
        throw new Error(payload.detail)
      }
      throw new Error(`Không thể xử lý câu hỏi (HTTP ${response.status}).`)
    }


    const data =
      await response.json()


    return data as ChatResponse
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
