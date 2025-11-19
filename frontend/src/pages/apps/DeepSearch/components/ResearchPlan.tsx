import React from 'react'
import { Typography, Card } from 'antd'
import './ResearchPlan.css'

const { Title } = Typography

interface ResearchPlanProps {
  data: any
}

export default function ResearchPlan({ data }: ResearchPlanProps) {
  if (!data) return null

  return (
    <div className="research-plan-card">
      <div className="plan-header">
        <div className="plan-icon"></div>
        <Title level={5} style={{ margin: 0 }}>研究计划</Title>
      </div>
      
      <div className="plan-content">
        {data.rationale && (
          <div className="plan-section">
            <div className="section-label">研究思路</div>
            <div className="section-body">{data.rationale}</div>
          </div>
        )}

        {data.research_questions && data.research_questions.length > 0 && (
          <div className="plan-section">
            <div className="section-label">关键问题</div>
            <div className="section-body">
              {data.research_questions.map((q: string, idx: number) => (
                <div key={idx} className="plan-item">
                  <span className="item-index">{idx + 1}.</span>
                  <span className="item-text">{q}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.sub_topics && data.sub_topics.length > 0 && (
          <div className="plan-section">
            <div className="section-label">研究方向</div>
            <div className="section-body">
              {data.sub_topics.map((topic: string, idx: number) => (
                <div key={idx} className="plan-item">
                  <span className="item-index">{idx + 1}.</span>
                  <span className="item-text">{topic}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

