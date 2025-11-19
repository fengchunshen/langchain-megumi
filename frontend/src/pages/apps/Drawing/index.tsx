import { useState } from 'react'
import { Card, Form, Input, Button, InputNumber, Select, Space, message, Row, Col, Image } from 'antd'
import { drawingApi, DrawingRequest } from '@/api/drawing'
import './Drawing.css'

const { TextArea } = Input

export default function Drawing() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [images, setImages] = useState<string[]>([])

  const handleSubmit = async (values: any) => {
    setLoading(true)
    setImages([])

    try {
      const request: DrawingRequest = {
        prompt: values.prompt,
        style: values.style,
        width: values.width,
        height: values.height,
        n: values.n,
      }

      const response = await drawingApi.generate(request)
      setImages(response.image_urls || [])
      message.success('图片生成成功')
    } catch (error: any) {
      message.error(error?.message || '生成图片失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = (url: string) => {
    const link = document.createElement('a')
    link.href = url
    link.download = `image-${Date.now()}.png`
    link.click()
  }

  return (
    <div className="drawing-page">
      <Card title="绘图生成">
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            style: 'default',
            width: 1024,
            height: 1024,
            n: 1,
          }}
        >
          <Form.Item
            name="prompt"
            label="提示词"
            rules={[{ required: true, message: '请输入提示词' }]}
          >
            <TextArea rows={4} placeholder="描述您想要生成的图片..." />
          </Form.Item>

          <Form.Item name="style" label="风格">
            <Select>
              <Select.Option value="default">默认</Select.Option>
              <Select.Option value="realistic">写实</Select.Option>
              <Select.Option value="anime">动漫</Select.Option>
              <Select.Option value="oil">油画</Select.Option>
            </Select>
          </Form.Item>

          <Space>
            <Form.Item name="width" label="宽度">
              <InputNumber min={256} max={2048} step={64} />
            </Form.Item>
            <Form.Item name="height" label="高度">
              <InputNumber min={256} max={2048} step={64} />
            </Form.Item>
            <Form.Item name="n" label="生成数量">
              <InputNumber min={1} max={4} />
            </Form.Item>
          </Space>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              生成图片
            </Button>
          </Form.Item>
        </Form>

        {images.length > 0 && (
          <div className="images-section">
            <Row gutter={[16, 16]}>
              {images.map((url, index) => (
                <Col xs={24} sm={12} md={8} lg={6} key={index}>
                  <div className="image-item">
                    <Image src={url} alt={`Generated ${index + 1}`} />
                    <Button
                      type="link"
                      onClick={() => handleDownload(url)}
                      style={{ marginTop: 8 }}
                    >
                      下载
                    </Button>
                  </div>
                </Col>
              ))}
            </Row>
          </div>
        )}
      </Card>
    </div>
  )
}

