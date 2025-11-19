import { useState } from 'react'
import { Card, Form, Input, Button, message, Typography, Tag } from 'antd'
import { analysisApi, AnalysisCompanyRequest } from '@/api/analysis'
import './Analysis.css'

const { TextArea } = Input
const { Title, Paragraph } = Typography

export default function AnalysisCompany() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const handleSubmit = async (values: any) => {
    setLoading(true)
    setResult(null)

    try {
      const request: AnalysisCompanyRequest = {
        companyName: values.companyName,
        businessScope: values.businessScope,
      }

      const response = await analysisApi.analyzeCompany(request)
      setResult(response)
      message.success('分析完成')
    } catch (error: any) {
      message.error(error?.message || '分析失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="analysis-page">
      <Card title="企业标签分析">
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="companyName"
            label="企业名称"
            rules={[{ required: true, message: '请输入企业名称' }]}
          >
            <Input placeholder="输入企业名称" />
          </Form.Item>

          <Form.Item name="businessScope" label="经营范围">
            <TextArea rows={4} placeholder="可选，输入企业经营范围" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              开始分析
            </Button>
          </Form.Item>
        </Form>

        {result && (
          <div className="result-section">
            <Title level={4}>分析结果</Title>
            {result.tags && Array.isArray(result.tags) ? (
              <div className="tags-section">
                {result.tags.map((tag: string, index: number) => (
                  <Tag key={index} color="green" style={{ marginBottom: 8 }}>
                    {tag}
                  </Tag>
                ))}
              </div>
            ) : (
              <pre className="json-result">{JSON.stringify(result, null, 2)}</pre>
            )}
            {result.timestamp && (
              <Paragraph style={{ marginTop: 16, color: '#666' }}>
                分析时间: {new Date(result.timestamp).toLocaleString()}
              </Paragraph>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

