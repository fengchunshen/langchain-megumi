import { useState } from 'react'
import { Card, Upload, Button, message, Typography, Space, Statistic, Row, Col } from 'antd'
import { UploadOutlined, DownloadOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { tianyanchaApi } from '@/api/tianyancha'
import './Tianyancha.css'

const { Title } = Typography

export default function Tianyancha() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请上传 Excel 文件')
      return
    }

    const file = fileList[0].originFileObj
    if (!file) {
      message.warning('文件无效')
      return
    }

    setLoading(true)
    setResult(null)

    try {
      const response = await tianyanchaApi.batchQuery(file)
      setResult(response)
      message.success('批量查询完成')
    } catch (error: any) {
      message.error(error?.message || '批量查询失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = () => {
    if (result?.file_path) {
      const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
      const url = `${baseURL.replace('/api/v1', '')}${result.file_path}`
      window.open(url, '_blank')
    }
  }

  return (
    <div className="tianyancha-page">
      <Card title="天眼查批量查询">
        <div className="upload-section">
          <Upload
            fileList={fileList}
            onChange={({ fileList }) => setFileList(fileList)}
            beforeUpload={() => false}
            maxCount={1}
            accept=".xlsx,.xls"
          >
            <Button icon={<UploadOutlined />}>选择 Excel 文件</Button>
          </Upload>
          <Button
            type="primary"
            onClick={handleUpload}
            loading={loading}
            style={{ marginLeft: 16 }}
          >
            开始查询
          </Button>
        </div>

        {result && (
          <div className="result-section">
            <Title level={4}>查询结果</Title>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="总数" value={result.total_count} />
              </Col>
              <Col span={8}>
                <Statistic
                  title="成功"
                  value={result.success_count}
                  valueStyle={{ color: '#3f8600' }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="失败"
                  value={result.failed_count}
                  valueStyle={{ color: '#cf1322' }}
                />
              </Col>
            </Row>

            {result.file_path && (
              <div className="download-section">
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  onClick={handleDownload}
                  style={{ marginTop: 16 }}
                >
                  下载结果文件
                </Button>
                <p style={{ marginTop: 8, color: '#666' }}>
                  文件名: {result.file_name || 'result.xlsx'}
                </p>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

