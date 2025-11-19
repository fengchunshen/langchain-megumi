import { useState, useCallback } from 'react'
import { useEventSource } from './useEventSource'
import { DeepSearchEvent, DeepSearchEventType, DeepSearchRequest } from '@/api/deepsearch'
import { deepsearchApi } from '@/api/deepsearch'

export interface DeepSearchStreamState {
  events: DeepSearchEvent[]
  currentEvent: DeepSearchEvent | null
  isStreaming: boolean
  error: string | null
}

/**
 * DeepSearch 流式处理 Hook
 */
export function useDeepSearchStream() {
  const [state, setState] = useState<DeepSearchStreamState>({
    events: [],
    currentEvent: null,
    isStreaming: false,
    error: null,
  })

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data) as DeepSearchEvent
      setState((prev) => ({
        ...prev,
        events: [...prev.events, data],
        currentEvent: data,
        error: null,
      }))
    } catch (error) {
      console.error('解析 SSE 事件失败:', error)
      setState((prev) => ({
        ...prev,
        error: '解析事件数据失败',
      }))
    }
  }, [])

  const handleError = useCallback((event: Event) => {
    setState((prev) => ({
      ...prev,
      error: 'SSE 连接错误',
      isStreaming: false,
    }))
  }, [])

  const handleOpen = useCallback(() => {
    setState((prev) => ({
      ...prev,
      isStreaming: true,
      error: null,
    }))
  }, [])

  const startStream = useCallback(
    (request: DeepSearchRequest) => {
      // 重置状态
      setState({
        events: [],
        currentEvent: null,
        isStreaming: true,
        error: null,
      })

      const url = deepsearchApi.getStreamUrl(request)
      return url
    },
    []
  )

  const { status, close } = useEventSource(
    state.isStreaming ? startStream({ query: '' }) : null,
    {
      onMessage: handleMessage,
      onError: handleError,
      onOpen: handleOpen,
    }
  )

  const stopStream = useCallback(() => {
    close()
    setState((prev) => ({
      ...prev,
      isStreaming: false,
    }))
  }, [close])

  return {
    ...state,
    status,
    startStream,
    stopStream,
  }
}

