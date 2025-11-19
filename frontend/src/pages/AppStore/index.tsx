import { useState, useMemo } from 'react'
import { Input, Row, Col, Select, Empty } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { appsConfig, AppConfig, categories } from '@/appStore/apps.config'
import AppCard from '@/components/AppCard'
import './AppStore.css'

const { Search } = Input

export default function AppStore() {
  const [searchText, setSearchText] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('全部')

  const filteredApps = useMemo(() => {
    let result = appsConfig

    // 分类筛选
    if (selectedCategory !== '全部') {
      result = result.filter((app) => app.category === selectedCategory)
    }

    // 搜索筛选
    if (searchText.trim()) {
      const lowerSearchText = searchText.toLowerCase()
      result = result.filter(
        (app) =>
          app.name.toLowerCase().includes(lowerSearchText) ||
          app.description.toLowerCase().includes(lowerSearchText) ||
          app.tags.some((tag) => tag.toLowerCase().includes(lowerSearchText))
      )
    }

    return result
  }, [searchText, selectedCategory])

  return (
    <div className="app-store">
      <div className="app-store-header">
        <h2>AI 应用商店</h2>
        <p>探索和使用各种 AI 能力</p>
      </div>

      <div className="app-store-filters">
        <Search
          placeholder="搜索应用名称、描述或标签"
          allowClear
          enterButton={<SearchOutlined />}
          size="large"
          style={{ width: 400 }}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
        <Select
          placeholder="选择分类"
          style={{ width: 200 }}
          value={selectedCategory}
          onChange={setSelectedCategory}
        >
          <Select.Option value="全部">全部</Select.Option>
          {categories.map((cat) => (
            <Select.Option key={cat} value={cat}>
              {cat}
            </Select.Option>
          ))}
        </Select>
      </div>

      <div className="app-store-content">
        {filteredApps.length > 0 ? (
          <Row gutter={[16, 16]}>
            {filteredApps.map((app) => (
              <Col xs={24} sm={12} md={8} lg={6} key={app.id}>
                <AppCard app={app} />
              </Col>
            ))}
          </Row>
        ) : (
          <Empty description="没有找到匹配的应用" />
        )}
      </div>
    </div>
  )
}

