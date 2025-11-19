import { useState } from 'react'
import { Button, Typography, Skeleton } from 'antd'
import { CloseOutlined, DownOutlined, UpOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import { DeepSearchEventType } from '@/api/deepsearch'
import './Result.css'

const { Title, Paragraph } = Typography

interface EventData {
  event_type: string
  message?: string
  data?: any
  timestamp?: number
}

interface ResultProps {
  title: string
  events: EventData[]
  onClose: () => void
  hideResearchPlan?: boolean
}

export default function Result({ title, events, onClose, hideResearchPlan = false }: ResultProps) {
  const [showThinking, setShowThinking] = useState(true)
  const [expandedReports, setExpandedReports] = useState<Set<number>>(new Set())

  const toggleReport = (index: number) => {
    setExpandedReports((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }

  const renderEventContent = (event: EventData, index: number) => {
    const { event_type, message, data } = event

    switch (event_type) {
      case DeepSearchEventType.WEB_SEARCHING:
      case 'WEB_SEARCHING':
      case 'web_searching':
        return (
          <div className="content-section">
            <div className="section-bullet">◆</div>
            <div className="section-text">
              <strong>正在搜索</strong>
              <p>{message || '正在搜索网络资源...'}</p>
            </div>
          </div>
        )

      case DeepSearchEventType.RESEARCH_PLAN:
      case 'RESEARCH_PLAN':
      case 'research_plan':
        if (hideResearchPlan) return null
        return (
          <div className="content-section">
            <div className="section-bullet">◆</div>
            <div className="section-text">
              <strong>研究计划</strong>
              {data?.sub_topics && (
                <>
                  <p>内容:</p>
                  {data.sub_topics.map((topic: string, idx: number) => (
                    <p key={idx}>
                      {idx + 1}. {topic}
                    </p>
                  ))}
                </>
              )}
              {data?.research_questions && (
                <>
                  <p>研究问题:</p>
                  {data.research_questions.map((question: string, idx: number) => (
                    <p key={idx}>
                      {idx + 1}. {question}
                    </p>
                  ))}
                </>
              )}
              {data?.rationale && <p>原理: {data.rationale}</p>}
            </div>
          </div>
        )

      case DeepSearchEventType.WEB_RESULT:
      case 'WEB_RESULT':
      case 'web_result':
        return (
          <div className="content-section">
            <div className="section-bullet">◆</div>
            <div className="section-text">
              <strong>搜索结果</strong>
              <div className="website-tags">
                {data?.sources?.map((source: any, idx: number) => (
                  <div key={idx} className="website-tag">
                    <a href={source.url} target="_blank" rel="noopener noreferrer">
                      {source.title || source.url}
                    </a>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )

      case DeepSearchEventType.REFLECTION:
      case 'REFLECTION':
      case 'reflection':
        return (
          <div className="content-section">
            <div className="section-bullet">◆</div>
            <div className="section-text">
              <strong>反思过程</strong>
              {data?.unanswered_questions?.map((question: string, idx: number) => (
                <p key={idx}>
                  {idx + 1}. {question}
                </p>
              ))}
            </div>
          </div>
        )

      case DeepSearchEventType.OPTIMIZATION:
      case 'OPTIMIZATION':
      case 'optimization':
        return (
          <div className="content-section">
            <div className="section-bullet">◆</div>
            <div className="section-text">
              <strong>优化总结</strong>
              {data?.actionable_items?.length > 0 && (
                <>
                  <p>可执行行为:</p>
                  {data.actionable_items.map((item: string, idx: number) => (
                    <p key={idx}>
                      {idx + 1}. {item}
                    </p>
                  ))}
                </>
              )}
              {data?.key_insights?.length > 0 && (
                <>
                  <p>核心要点:</p>
                  {data.key_insights.map((insight: string, idx: number) => (
                    <p key={idx}>
                      {idx + 1}. {insight}
                    </p>
                  ))}
                </>
              )}
            </div>
          </div>
        )

      case DeepSearchEventType.REPORT_GENERATED:
      case 'REPORT_GENERATED':
      case 'report_generated':
        return (
          <div className="content-section">
            <div className="section-bullet">◆</div>
            <div className="section-text">
              <strong>报告生成</strong>
              <p>{message || '研究报告已生成'}</p>
            </div>
          </div>
        )

      case DeepSearchEventType.COMPLETED:
      case 'COMPLETED':
      case 'completed':
        const isExpanded = expandedReports.has(index)
        return (
          <div className="content-section">
            <div className="section-bullet">◆</div>
            <div className="section-text">
              <strong>研究已完成</strong>
              <div className="completed-actions">
                <Button type="link" size="small" onClick={() => toggleReport(index)}>
                  {isExpanded ? '收起' : '查看'}
                </Button>
                <Button
                  type="link"
                  size="small"
                  onClick={() => {
                    const blob = new Blob([data?.markdown_report || ''], {
                      type: 'text/markdown',
                    })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `${title || '研究报告'}.md`
                    a.click()
                    URL.revokeObjectURL(url)
                  }}
                >
                  下载
                </Button>
              </div>
              {isExpanded && data?.markdown_report && (
                <div className="final-report">
                  <h3 className="report-title">📝 研究报告</h3>
                  <div className="report-content">
                    <ReactMarkdown>{data.markdown_report}</ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          </div>
        )

      default:
        if (message) {
          return (
            <div className="content-section">
              <div className="section-bullet">◆</div>
              <div className="section-text">
                <p>{message}</p>
              </div>
            </div>
          )
        }
        return null
    }
  }

  return (
    <div className="result-box">
      <div className="result-container">
        {/* 标题栏 */}
        <div className="result-header">
          <div className="header-title">{title}</div>
          <div className="header-actions">
            {events.length > 0 && (
              <div className="toggle-thinking" onClick={() => setShowThinking(!showThinking)}>
                <span>{showThinking ? '收起思考过程' : '显示思考过程'}</span>
                {showThinking ? <UpOutlined /> : <DownOutlined />}
              </div>
            )}
            <CloseOutlined className="close-btn" onClick={onClose} />
          </div>
        </div>

        {/* 内容区域 */}
        <div className={`result-content ${showThinking ? 'has-content' : ''}`}>
          {showThinking && (
            <div className="content-sections">
              {events.length === 0 ? (
                <Skeleton active paragraph={{ rows: 4 }} />
              ) : (
                events.map((event, index) => (
                  <div key={index}>{renderEventContent(event, index)}</div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
