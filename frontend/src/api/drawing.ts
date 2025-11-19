import http from './http'

export interface DrawingRequest {
  prompt: string
  style?: string
  width?: number
  height?: number
  n?: number
}

export interface DrawingResponse {
  image_urls: string[]
  [key: string]: any
}

/**
 * 绘图 API
 */
export const drawingApi = {
  /**
   * 生成图片
   */
  generate: async (data: DrawingRequest): Promise<DrawingResponse> => {
    return http.post('/drawing/generate', data)
  },
}

