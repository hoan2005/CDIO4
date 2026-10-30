import type {
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

}