import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { message } from 'antd'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
const API_KEY = import.meta.env.VITE_MEGUMI_API_KEY || ''

// 创建 Axios 实例
const http: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000, // 10分钟超时，用于长时间任务
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
http.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 自动注入 API Key
    if (API_KEY && config.headers) {
      config.headers['X-API-Key'] = API_KEY
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
http.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error: AxiosError) => {
    // 统一错误处理
    if (error.response) {
      const status = error.response.status
      const data = error.response.data as any
      const errorMessage = data?.detail || data?.message || `请求失败: ${status}`

      switch (status) {
        case 401:
          message.error('未授权，请检查 API Key')
          break
        case 403:
          message.error('禁止访问')
          break
        case 404:
          message.error('接口不存在')
          break
        case 500:
          message.error(errorMessage)
          break
        default:
          message.error(errorMessage)
      }
    } else if (error.request) {
      message.error('网络错误，请检查网络连接')
    } else {
      message.error('请求配置错误')
    }

    return Promise.reject(error)
  }
)

export default http

