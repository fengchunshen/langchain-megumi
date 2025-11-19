import { useMemo } from 'react'
import ResearchPlan from './ResearchPlan'
import './Answer.css'

export interface MessageItem {
  type: 'ask' | 'answer' | 'plan'
  content: string
  timestamp: number
  data?: any
}

interface AnswerProps {
  messages: MessageItem[]
  loading?: boolean
}

export default function Answer({ messages, loading }: AnswerProps) {
  return (
    <div className="answer-wrap">
      {messages.map((item, idx) => (
        <div key={idx} className="message-item">
          {item.type === 'ask' ? (
            <div className="ask-bubble">{item.content}</div>
          ) : item.type === 'plan' ? (
            <div className="plan-bubble">
              <ResearchPlan data={item.data} />
            </div>
          ) : (
            <div className="answer-bubble">{item.content}</div>
          )}
        </div>
      ))}

      {loading && (
        <div className="loading-dots">
          <span className="dot dot-1"></span>
          <span className="dot dot-2"></span>
          <span className="dot dot-3"></span>
        </div>
      )}
    </div>
  )
}

