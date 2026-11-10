import type {
  CanvasObject,
  ChatRequest,
  ChatResponse,
} from '@/types'


const API_BASE_URL = 'http://localhost:8000'


export const chatService = {

  async send(
    request: ChatRequest
  ): Promise<ChatResponse> {

    const response = await fetch(
      `${API_BASE_URL}/chat`,
      {
        method: 'POST',

        headers: {
          'Content-Type': 'application/json',
        },

        body: JSON.stringify(request),
      }
    )


    if (!response.ok) {

      const errorText =
        await response.text()

      throw new Error(
        `Chat API error: ${response.status} ${errorText}`
      )
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