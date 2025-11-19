import http from './http'

export interface OCRRequest {
  image_base64?: string
  image_url?: string
  language?: 'auto' | 'zh' | 'en'
}

export interface OCRResponse {
  text: string
  text_blocks: Array<{
    text: string
    confidence?: number
    bbox?: {
      x: number
      y: number
      width: number
      height: number
    }
  }>
  [key: string]: any
}

/**
 * OCR API
 */
export const ocrApi = {
  /**
   * 识别图片文字
   */
  recognize: async (data: OCRRequest): Promise<OCRResponse> => {
    return http.post('/ocr/recognize', data)
  },
}

