import http from './http'

export interface TianyanchaBatchRequest {
  file: File
}

export interface TianyanchaBatchResponse {
  total_count: number
  success_count: number
  failed_count: number
  file_path?: string
  file_name?: string
  [key: string]: any
}

/**
 * 天眼查 API
 */
export const tianyanchaApi = {
  /**
   * 批量查询
   */
  batchQuery: async (file: File): Promise<TianyanchaBatchResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    return http.post('/tianyancha/batch-query', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
}

