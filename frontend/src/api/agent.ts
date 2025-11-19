import http from './http'

export enum TaskType {
  QA = 'Q&A',
  CODE_GENERATION = '代码生成',
  DATA_ANALYSIS = '数据分析',
  MULTI_STEP = '多步骤',
}

export interface AgentRequest {
  query: string
  task_type?: TaskType
  system_prompt?: string
  temperature?: number
  max_tokens?: number
  context?: Record<string, any>
}

export interface AgentResponse {
  answer: string
  reasoning?: string
  sources?: Array<{
    title: string
    url: string
    snippet?: string
  }>
  metadata?: Record<string, any>
}

/**
 * 智能体编排 API
 */
export const agentApi = {
  /**
   * 执行任务编排
   */
  orchestrate: async (data: AgentRequest): Promise<AgentResponse> => {
    return http.post('/agent/orchestrate', data)
  },
}

