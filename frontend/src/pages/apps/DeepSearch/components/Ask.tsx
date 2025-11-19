import { useState, useCallback, KeyboardEvent } from 'react'
import { Button, message } from 'antd'
import './Ask.css'

interface AskProps {
  onSubmit: (query: string) => void
  onStop: () => void
  isStreaming: boolean
}

export default function Ask({ onSubmit, onStop, isStreaming }: AskProps) {
  const [query, setQuery] = useState('')

  const handleSubmit = useCallback(() => {
    const text = query.trim()
    if (!text) {
      message.error('请输入研究主题')
      return
    }
    onSubmit(text)
    setQuery('')
  }, [query, onSubmit])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Shift+Enter 换行，Enter 提交
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (isStreaming) {
        onStop()
      } else {
        handleSubmit()
      }
    }
  }

  return (
    <div className="ask-wrapper">
      <div className="ask-bar">
        {/* 输入框 */}
        <div className="input-row">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="ask-input"
            placeholder="你想研究什么?&#10;例如: 量子计算的发展趋势和挑战"
            onKeyDown={handleKeyDown}
          />
        </div>

        {/* 底部功能行 */}
        <div className="tools-row">
          <div className="right-tools">
            <Button
              className="action-btn"
              type="primary"
              onClick={isStreaming ? onStop : handleSubmit}
              disabled={!isStreaming && !query.trim()}
            >
              {isStreaming ? (
                <span className="stop-icon" />
              ) : (
                <span className="send-icon" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

