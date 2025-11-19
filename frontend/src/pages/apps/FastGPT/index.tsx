import { useState, useEffect } from 'react'
import { Card, Input, Button, List, Space, message, Spin } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import { fastgptApi, ChatRequest } from '@/api/fastgpt'
import './FastGPT.css'

const { TextArea } = Input

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export default function FastGPT() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [chatId, setChatId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSend = async () => {
    if (!inputValue.trim()) {
      message.warning('请输入消息内容')
      return
    }

    const userMessage: Message = {
      role: 'user',
      content: inputValue,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInputValue('')
    setLoading(true)

    try {
      const request: ChatRequest = {
        message: inputValue,
        chat_id: chatId || undefined,
        stream: false,
      }

      const response = await fastgptApi.chat(request)

      // 更新 chat_id
      if (response.chat_id && !chatId) {
        setChatId(response.chat_id)
      }

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.message || '无响应',
        timestamp: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error: any) {
      message.error(error?.message || '发送消息失败')
    } finally {
      setLoading(false)
    }
  }

  const handleNewChat = () => {
    setChatId(null)
    setMessages([])
  }

  return (
    <div className="fastgpt-page">
      <Card
        title="FastGPT 对话"
        extra={
          <Button onClick={handleNewChat} type="default">
            新建会话
          </Button>
        }
      >
        <div className="fastgpt-container">
          <div className="fastgpt-messages">
            {messages.length === 0 ? (
              <div className="empty-messages">开始对话吧！</div>
            ) : (
              <List
                dataSource={messages}
                renderItem={(item) => (
                  <List.Item className={item.role === 'user' ? 'message-user' : 'message-assistant'}>
                    <div className="message-content">
                      <div className="message-role">{item.role === 'user' ? '用户' : 'AI'}</div>
                      <div className="message-text">{item.content}</div>
                      <div className="message-time">
                        {new Date(item.timestamp).toLocaleString()}
                      </div>
                    </div>
                  </List.Item>
                )}
              />
            )}
          </div>
          <div className="fastgpt-input">
            <Space.Compact style={{ width: '100%' }}>
              <TextArea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="输入消息..."
                autoSize={{ minRows: 2, maxRows: 6 }}
                onPressEnter={(e) => {
                  if (e.shiftKey) {
                    return
                  }
                  e.preventDefault()
                  handleSend()
                }}
                disabled={loading}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={loading}
                style={{ height: 'auto' }}
              >
                发送
              </Button>
            </Space.Compact>
          </div>
        </div>
      </Card>
    </div>
  )
}

