import { Card, Button, Tag, Space } from 'antd'
import { useNavigate } from 'react-router-dom'
import { AppConfig } from '@/appStore/apps.config'
import './AppCard.css'

interface AppCardProps {
  app: AppConfig
}

export default function AppCard({ app }: AppCardProps) {
  const navigate = useNavigate()

  return (
    <Card
      className="app-card"
      hoverable
      actions={[
        <Button type="primary" onClick={() => navigate(app.route)}>
          立即使用
        </Button>,
      ]}
    >
      <div className="app-card-content">
        <h3>{app.name}</h3>
        <p className="app-description">{app.description}</p>
        <Space wrap className="app-tags">
          {app.tags.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </Space>
      </div>
    </Card>
  )
}

