import { useState } from 'react'
import { Card, Form, Upload, Input, Button, Select, message, Typography, Space } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { ocrApi, OCRRequest } from '@/api/ocr'
import './OCR.css'

const { Title, Paragraph } = Typography

export default function OCR() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [fileList, setFileList] = useState<UploadFile[]>([])

  const handleSubmit = async (values: any) => {
    if (!values.image_url && fileList.length === 0) {
      message.warning('请上传图片或输入图片 URL')
      return
    }

    setLoading(true)
    setResult(null)

    try {
      let imageBase64: string | undefined

      if (fileList.length > 0) {
        const file = fileList[0].originFileObj
        if (file) {
          imageBase64 = await fileToBase64(file)
        }
      }

      const request: OCRRequest = {
        image_base64: imageBase64,
        image_url: values.image_url,
        language: values.language,
      }

      const response = await ocrApi.recognize(request)
      setResult(response)
      message.success('识别成功')
    } catch (error: any) {
      message.error(error?.message || '识别失败')
    } finally {
      setLoading(false)
    }
  }

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.readAsDataURL(file)
      reader.onload = () => {
        const base64 = (reader.result as string).split(',')[1]
        resolve(base64)
      }
      reader.onerror = (error) => reject(error)
    })
  }

  return (
    <div className="ocr-page">
      <Card title="OCR 文字识别">
        <Form form={form} layout="vertical" onFinish={handleSubmit} initialValues={{ language: 'auto' }}>
          <Form.Item label="上传图片">
            <Upload
              fileList={fileList}
              onChange={({ fileList }) => setFileList(fileList)}
              beforeUpload={() => false}
              maxCount={1}
              accept="image/*"
            >
              <Button icon={<UploadOutlined />}>选择图片</Button>
            </Upload>
          </Form.Item>

          <Form.Item label="或输入图片 URL" name="image_url">
            <Input placeholder="https://example.com/image.jpg" />
          </Form.Item>

          <Form.Item name="language" label="识别语言">
            <Select>
              <Select.Option value="auto">自动</Select.Option>
              <Select.Option value="zh">中文</Select.Option>
              <Select.Option value="en">英文</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              开始识别
            </Button>
          </Form.Item>
        </Form>

        {result && (
          <div className="result-section">
            <Title level={4}>识别结果</Title>
            <Paragraph>
              <strong>整体文本：</strong>
            </Paragraph>
            <div className="text-content">{result.text}</div>

            {result.text_blocks && result.text_blocks.length > 0 && (
              <div className="blocks-section">
                <Title level={5}>文本块</Title>
                <Space direction="vertical" style={{ width: '100%' }}>
                  {result.text_blocks.map((block: any, index: number) => (
                    <div key={index} className="text-block">
                      <Paragraph>
                        <strong>文本：</strong>
                        {block.text}
                      </Paragraph>
                      {block.confidence !== undefined && (
                        <Paragraph>
                          <strong>置信度：</strong>
                          {(block.confidence * 100).toFixed(2)}%
                        </Paragraph>
                      )}
                      {block.bbox && (
                        <Paragraph>
                          <strong>位置：</strong>
                          x: {block.bbox.x}, y: {block.bbox.y}, width: {block.bbox.width}, height:{' '}
                          {block.bbox.height}
                        </Paragraph>
                      )}
                    </div>
                  ))}
                </Space>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

