import http from './http'

export interface MonitorStatusResponse {
  status: 'healthy' | 'warning' | 'critical'
  [key: string]: any
}

export interface MonitorHealthResponse {
  status: string
  [key: string]: any
}

export interface ActiveUsersResponse {
  users: Array<{
    user_id?: string
    connection_count?: number
    [key: string]: any
  }>
  [key: string]: any
}

/**
 * 系统监控 API
 */
export const monitorApi = {
  /**
   * 获取 SSE 状态
   */
  getSSEStatus: async (): Promise<MonitorStatusResponse> => {
    return http.get('/monitor/sse/status')
  },

  /**
   * 获取活跃用户
   */
  getActiveUsers: async (): Promise<ActiveUsersResponse> => {
    return http.get('/monitor/sse/active-users')
  },

  /**
   * 获取系统健康状态
   */
  getSystemHealth: async (): Promise<MonitorHealthResponse> => {
    return http.get('/monitor/system/health')
  },
}

