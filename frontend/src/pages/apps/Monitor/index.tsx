import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Table, Tag, message, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { monitorApi } from '@/api/monitor'
import './Monitor.css'

export default function Monitor() {
  const [loading, setLoading] = useState(false)
  const [healthStatus, setHealthStatus] = useState<any>(null)
  const [sseStatus, setSseStatus] = useState<any>(null)
  const [activeUsers, setActiveUsers] = useState<any[]>([])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [health, sse, users] = await Promise.all([
        monitorApi.getSystemHealth(),
        monitorApi.getSSEStatus(),
        monitorApi.getActiveUsers(),
      ])

      setHealthStatus(health)
      setSseStatus(sse)
      setActiveUsers(users.users || [])
    } catch (error: any) {
      message.error(error?.message || '获取监控数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // 每30秒刷新一次
    return () => clearInterval(interval)
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'success'
      case 'warning':
        return 'warning'
      case 'critical':
        return 'error'
      default:
        return 'default'
    }
  }

  const columns = [
    {
      title: '用户 ID',
      dataIndex: 'user_id',
      key: 'user_id',
      render: (text: string) => text || '未知',
    },
    {
      title: '连接数',
      dataIndex: 'connection_count',
      key: 'connection_count',
      render: (count: number) => count || 0,
    },
  ]

  return (
    <div className="monitor-page">
      <Card
        title="系统监控"
        extra={
          <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
            刷新
          </Button>
        }
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={8}>
            <Card>
              <Statistic
                title="系统状态"
                value={healthStatus?.status || 'unknown'}
                valueStyle={{
                  color:
                    healthStatus?.status === 'healthy'
                      ? '#3f8600'
                      : healthStatus?.status === 'warning'
                      ? '#faad14'
                      : '#cf1322',
                }}
              />
              {healthStatus?.status && (
                <Tag color={getStatusColor(healthStatus.status)} style={{ marginTop: 8 }}>
                  {healthStatus.status}
                </Tag>
              )}
            </Card>
          </Col>

          {sseStatus && (
            <>
              <Col xs={24} sm={12} md={8}>
                <Card>
                  <Statistic
                    title="活跃连接数"
                    value={sseStatus.active_connections || 0}
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={12} md={8}>
                <Card>
                  <Statistic
                    title="总连接数"
                    value={sseStatus.total_connections || 0}
                  />
                </Card>
              </Col>
              {sseStatus.success_rate !== undefined && (
                <Col xs={24} sm={12} md={8}>
                  <Card>
                    <Statistic
                      title="成功率"
                      value={sseStatus.success_rate}
                      precision={2}
                      suffix="%"
                      valueStyle={{ color: '#3f8600' }}
                    />
                  </Card>
                </Col>
              )}
              {sseStatus.average_duration !== undefined && (
                <Col xs={24} sm={12} md={8}>
                  <Card>
                    <Statistic
                      title="平均时长"
                      value={sseStatus.average_duration}
                      precision={2}
                      suffix="秒"
                    />
                  </Card>
                </Col>
              )}
            </>
          )}
        </Row>

        {activeUsers.length > 0 && (
          <Card title="活跃用户" style={{ marginTop: 16 }}>
            <Table
              dataSource={activeUsers}
              columns={columns}
              rowKey={(record, index) => record.user_id || String(index)}
              pagination={false}
            />
          </Card>
        )}
      </Card>
    </div>
  )
}

