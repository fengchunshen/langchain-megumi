import http from './http'

export interface DeepSearchRequest {
  query: string
  initial_search_query_count?: number
  max_research_loops?: number
  reasoning_model?: string
  report_format?: string
}

export interface DeepSearchResponse {
  markdown_report: string
  sources: Array<{
    title: string
    url: string
    snippet?: string
  }>
  all_sources: Array<{
    title: string
    url: string
    snippet?: string
  }>
  [key: string]: any
}

export enum DeepSearchEventType {
  STARTED = 'started',
  RESEARCH_PLAN = 'research_plan',
  QUERY_GENERATED = 'query_generated',
  WEB_SEARCHING = 'web_searching',
  WEB_RESULT = 'web_result',
  REFLECTION = 'reflection',
  QUALITY_ASSESSMENT = 'quality_assessment',
  FACT_VERIFICATION = 'fact_verification',
  RELEVANCE_ASSESSMENT = 'relevance_assessment',
  OPTIMIZATION = 'optimization',
  PROGRESS = 'progress',
  REPORT_GENERATED = 'report_generated',
  COMPLETED = 'completed',
  ERROR = 'error',
}

export interface DeepSearchEvent {
  event_type: DeepSearchEventType
  timestamp: string
  sequence_number: number
  data: any
  message?: string
}

/**
 * DeepSearch API
 */
export const deepsearchApi = {
  /**
   * 同步执行 DeepSearch
   */
  run: async (data: DeepSearchRequest): Promise<DeepSearchResponse> => {
    return http.post('/deepsearch/run', data)
  },

  /**
   * 流式执行 DeepSearch (SSE)
   * 注意：由于后端使用 POST，需要使用 fetch 而不是 EventSource
   */
  runStream: async function* (
    data: DeepSearchRequest,
    signal?: AbortSignal
  ): AsyncGenerator<DeepSearchEvent> {
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
    const API_KEY = import.meta.env.VITE_MEGUMI_API_KEY || ''
    
    const response = await fetch(`${baseURL}/deepsearch/run/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(API_KEY && { 'X-API-Key': API_KEY }),
      },
      body: JSON.stringify(data),
      signal, // 传递 AbortSignal
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('Response body is not readable')
    }

    let buffer = ''

    try {
      while (true) {
        // 检查是否已被中止
        if (signal?.aborted) {
          throw new DOMException('The operation was aborted.', 'AbortError')
        }

        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6)) as DeepSearchEvent
              yield data
            } catch (e) {
              console.error('Failed to parse SSE data:', e)
            }
          }
        }
      }
    } catch (error: any) {
      // 如果是中止错误，重新抛出
      if (error.name === 'AbortError') {
        throw error
      }
      // 其他错误也抛出
      throw error
    } finally {
      // 确保释放 reader
      try {
        await reader.cancel()
      } catch (e) {
        // 忽略取消时的错误
      }
    }
  },
}
