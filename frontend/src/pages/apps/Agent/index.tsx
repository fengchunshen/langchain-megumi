import { useState } from 'react'
import { Card, Form, Input, Button, Select, InputNumber, Space, message, Typography } from 'antd'
import { agentApi, AgentRequest, TaskType } from '@/api/agent'
import './Agent.css'

const { TextArea } = Input
const { Title, Paragraph } = Typography

export default function Agent() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const handleSubmit = async (values: any) => {
    setLoading(true)
    setResult(null)

    try {
      let context: Record<string, any> | undefined
      if (values.context) {
        try {
          context = JSON.parse(values.context)
        } catch (e) {
          message.error('Context JSON 格式错误')
          setLoading(false)
          return
        }
      }

      const request: AgentRequest = {
        query: values.query,
        task_type: values.task_type,
        system_prompt: values.system_prompt,
        temperature: values.temperature,
        max_tokens: values.max_tokens,
        context,
      }

      const response = await agentApi.orchestrate(request)
      setResult(response)
      message.success('任务执行成功')
    } catch (error: any) {
      message.error(error?.message || '任务执行失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="agent-page">
      <Card title="智能体任务编排">
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            task_type: TaskType.QA,
            temperature: 0.7,
            max_tokens: 2000,
          }}
        >
          <Form.Item
            name="query"
            label="任务查询"
            rules={[{ required: true, message: '请输入任务查询' }]}
          >
            <TextArea rows={4} placeholder="描述您要执行的任务..." />
          </Form.Item>

          <Form.Item name="task_type" label="任务类型">
            <Select>
              <Select.Option value={TaskType.QA}>Q&A</Select.Option>
              <Select.Option value={TaskType.CODE_GENERATION}>代码生成</Select.Option>
              <Select.Option value={TaskType.DATA_ANALYSIS}>数据分析</Select.Option>
              <Select.Option value={TaskType.MULTI_STEP}>多步骤</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item name="system_prompt" label="系统提示词">
            <TextArea rows={3} placeholder="可选，自定义系统提示词" />
          </Form.Item>

          <Space>
            <Form.Item name="temperature" label="Temperature">
              <InputNumber min={0} max={2} step={0.1} />
            </Form.Item>
            <Form.Item name="max_tokens" label="Max Tokens">
              <InputNumber min={100} max={8000} step={100} />
            </Form.Item>
          </Space>

          <Form.Item name="context" label="上下文 (JSON)">
            <TextArea rows={4} placeholder='{"key": "value"}' />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              执行任务
            </Button>
          </Form.Item>
        </Form>

        {result && (
          <div className="result-section">
            <Title level={4}>执行结果</Title>
            <Paragraph>
              <strong>回答：</strong>
              {result.answer}
            </Paragraph>

            {result.reasoning && (
              <Paragraph>
                <strong>推理过程：</strong>
                {result.reasoning}
              </Paragraph>
            )}

            {result.sources && result.sources.length > 0 && (
              <div className="sources-section">
                <Title level={5}>数据源</Title>
                <ul>
                  {result.sources.map((source: any, index: number) => (
                    <li key={index}>
                      <a href={source.url} target="_blank" rel="noopener noreferrer">
                        {source.title || source.url}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.metadata && (
              <div className="metadata-section">
                <Title level={5}>元数据</Title>
                <pre>{JSON.stringify(result.metadata, null, 2)}</pre>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

