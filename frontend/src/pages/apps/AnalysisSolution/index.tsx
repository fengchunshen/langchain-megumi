import { useState } from 'react'
import { Card, Form, Input, Button, message, Typography, Tag } from 'antd'
import { analysisApi, AnalysisSolutionRequest } from '@/api/analysis'
import './Analysis.css'

const { TextArea } = Input
const { Title } = Typography

export default function AnalysisSolution() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const handleSubmit = async (values: any) => {
    setLoading(true)
    setResult(null)

    try {
      const request: AnalysisSolutionRequest = {
        solutionName: values.solutionName,
        description: values.description,
      }

      const response = await analysisApi.analyzeSolution(request)
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
      <Card title="解决方案标签分析">
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="solutionName"
            label="解决方案名称"
            rules={[{ required: true, message: '请输入解决方案名称' }]}
          >
            <Input placeholder="输入解决方案名称" />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <TextArea rows={4} placeholder="可选，输入解决方案描述" />
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
                  <Tag key={index} color="blue" style={{ marginBottom: 8 }}>
                    {tag}
                  </Tag>
                ))}
              </div>
            ) : (
              <pre className="json-result">{JSON.stringify(result, null, 2)}</pre>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

