import http from './http'

export interface ChatRequest {
  message: string
  chat_id?: string
  stream?: boolean
}

export interface ChatResponse {
  chat_id: string
  message: string
  [key: string]: any
}

export interface ChatHistoryResponse {
  messages: Array<{
    role: string
    content: string
    timestamp?: string
  }>
  [key: string]: any
}

/**
 * FastGPT 对话 API
 */
export const fastgptApi = {
  /**
   * 发送消息
   */
  chat: async (data: ChatRequest): Promise<ChatResponse> => {
    return http.post('/fastgpt/chat', data)
  },

  /**
   * 获取聊天历史
   */
  getHistory: async (chatId: string): Promise<ChatHistoryResponse> => {
    return http.get(`/fastgpt/history/${chatId}`)
  },
}

