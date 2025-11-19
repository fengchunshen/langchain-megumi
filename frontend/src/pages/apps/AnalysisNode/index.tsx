import { useState } from 'react'
import { Card, Form, Input, Button, message, Typography } from 'antd'
import { analysisApi, AnalysisNodeRequest } from '@/api/analysis'
import './Analysis.css'

const { TextArea } = Input
const { Title, Paragraph } = Typography

export default function AnalysisNode() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const handleSubmit = async (values: any) => {
    setLoading(true)
    setResult(null)

    try {
      const request: AnalysisNodeRequest = {
        nodeName: values.nodeName,
        parentProfile: values.parentProfile,
        siblingsProfiles: values.siblingsProfiles
          ? values.siblingsProfiles.split('\n').filter((s: string) => s.trim())
          : undefined,
      }

      const response = await analysisApi.analyzeNode(request)
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
      <Card title="节点分析">
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="nodeName"
            label="节点名称"
            rules={[{ required: true, message: '请输入节点名称' }]}
          >
            <Input placeholder="输入节点名称" />
          </Form.Item>

          <Form.Item name="parentProfile" label="父节点信息">
            <TextArea rows={3} placeholder="可选，输入父节点信息" />
          </Form.Item>

          <Form.Item name="siblingsProfiles" label="兄弟节点信息（每行一个）">
            <TextArea rows={4} placeholder="可选，每行输入一个兄弟节点信息" />
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
            <pre className="json-result">{JSON.stringify(result, null, 2)}</pre>
          </div>
        )}
      </Card>
    </div>
  )
}

