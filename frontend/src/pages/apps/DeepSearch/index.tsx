import { useState, useRef } from 'react'
import { message } from 'antd'
import { deepsearchApi, DeepSearchRequest, DeepSearchEventType } from '@/api/deepsearch'
import { Ask, Answer, Result, MessageItem } from './components'
import './DeepSearch.css'

interface ResearchSession {
  id: string
  title: string
  events: any[]
}

export default function DeepSearch() {
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [streaming, setStreaming] = useState(false)
  const [currentSession, setCurrentSession] = useState<ResearchSession | null>(null)
  const streamControllerRef = useRef<AbortController | null>(null)

  const handleSubmit = async (query: string) => {
    // 添加用户问题到对话
    const newMessage: MessageItem = {
      type: 'ask',
      content: query,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, newMessage])

    // 创建新的研究会话
    const session: ResearchSession = {
      id: Date.now().toString(),
      title: query,
      events: [],
    }
    setCurrentSession(session)
    setStreaming(true)

    // 添加系统消息
    setMessages((prev) => [
      ...prev,
      {
        type: 'answer',
        content: '正在启动深度研究...',
        timestamp: Date.now(),
      },
    ])

    const request: DeepSearchRequest = {
      query,
      initial_search_query_count: 5,
      max_research_loops: 3,
    }

    try {
      streamControllerRef.current = new AbortController()

      for await (const event of deepsearchApi.runStream(request, streamControllerRef.current.signal)) {
        // 更新会话事件
        setCurrentSession((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            events: [...prev.events, event],
          }
        })

        // 根据事件类型更新对话消息
        if (event.event_type === DeepSearchEventType.RESEARCH_PLAN) {
          setMessages((prev) => [
            ...prev,
            {
              type: 'plan',
              content: '',
              data: event.data,
              timestamp: Date.now(),
            },
          ])
        } else if (event.event_type === DeepSearchEventType.WEB_SEARCHING) {
          setMessages((prev) => [
            ...prev,
            {
              type: 'answer',
              content: '正在搜索网络资源...',
              timestamp: Date.now(),
            },
          ])
        } else if (event.event_type === DeepSearchEventType.WEB_RESULT) {
          setMessages((prev) => [
            ...prev,
            {
              type: 'answer',
              content: `找到 ${event.data?.sources?.length || 0} 个搜索结果`,
              timestamp: Date.now(),
            },
          ])
        } else if (event.event_type === DeepSearchEventType.REFLECTION) {
          setMessages((prev) => [
            ...prev,
            {
              type: 'answer',
              content: '正在进行反思分析...',
              timestamp: Date.now(),
            },
          ])
        } else if (event.event_type === DeepSearchEventType.OPTIMIZATION) {
          setMessages((prev) => [
            ...prev,
            {
              type: 'answer',
              content: '正在优化研究结果...',
              timestamp: Date.now(),
            },
          ])
        } else if (event.event_type === DeepSearchEventType.REPORT_GENERATED) {
          setMessages((prev) => [
            ...prev,
            {
              type: 'answer',
              content: '报告生成完成',
              timestamp: Date.now(),
            },
          ])
        } else if (event.event_type === DeepSearchEventType.COMPLETED) {
          setMessages((prev) => [
            ...prev,
            {
              type: 'answer',
              content: '研究已完成！',
              timestamp: Date.now(),
            },
          ])
          setStreaming(false)
          message.success('研究完成')
        } else if (event.event_type === DeepSearchEventType.ERROR) {
          setMessages((prev) => [
            ...prev,
            {
              type: 'answer',
              content: `错误: ${event.message || '执行失败'}`,
              timestamp: Date.now(),
            },
          ])
          setStreaming(false)
          message.error(event.message || '执行失败')
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        // 用户主动停止，不显示错误消息
        setMessages((prev) => [
          ...prev,
          {
            type: 'answer',
            content: '研究已停止',
            timestamp: Date.now(),
          },
        ])
        message.info('已停止研究')
      } else {
        // 其他错误
        message.error(error?.message || '流式执行失败')
        setMessages((prev) => [
          ...prev,
          {
            type: 'answer',
            content: `错误: ${error?.message || '流式执行失败'}`,
            timestamp: Date.now(),
          },
        ])
      }
    } finally {
      setStreaming(false)
      streamControllerRef.current = null
    }
  }

  const handleStop = () => {
    if (streamControllerRef.current) {
      streamControllerRef.current.abort()
      // 不立即设置为 null，让 finally 块处理
    }
    // 状态更新会在 catch/finally 中处理
  }

  const handleCloseResult = () => {
    setCurrentSession(null)
  }

  return (
    <div className="deepsearch-page">
      {/* 顶部背景 */}
      <div className="deepsearch-bg"></div>

      <div className="main-content">
        {/* 左右布局容器 */}
        <div className="content-layout">
          {/* 左侧：对话区域 */}
          <div className={`left-section ${currentSession ? 'has-result' : ''}`}>
            <div className="left-scroll-container">
              <Answer messages={messages} loading={streaming} />
            </div>
            <Ask onSubmit={handleSubmit} onStop={handleStop} isStreaming={streaming} />
          </div>

          {/* 右侧：Result 区域 */}
          {currentSession && (
            <div className="right-section">
              <Result
                title={currentSession.title}
                events={currentSession.events}
                onClose={handleCloseResult}
                hideResearchPlan={true}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

