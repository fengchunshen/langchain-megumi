import { ReactNode } from 'react'
import { Layout as AntLayout, Menu } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { appsConfig, categories } from '@/appStore/apps.config'
import './Layout.css'

const { Header, Content, Sider } = AntLayout

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()

  const menuItems = categories.map((category) => ({
    key: category,
    label: category,
    children: appsConfig
      .filter((app) => app.category === category)
      .map((app) => ({
        key: app.route,
        label: app.name,
      })),
  }))

  const handleMenuClick = ({ key }: { key: string }) => {
    if (key.startsWith('/')) {
      navigate(key)
    }
  }

  const selectedKeys = [location.pathname]

  return (
    <AntLayout style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header className="layout-header">
        <div className="header-title">
          <h1>中国移动AI软件平台</h1>
        </div>
      </Header>
      <AntLayout style={{ flex: 1, overflow: 'hidden' }}>
        <Sider width={200} className="layout-sider">
          <Menu
            mode="inline"
            selectedKeys={selectedKeys}
            style={{ height: '100%', borderRight: 0 }}
            items={[
              {
                key: '/apps',
                label: '应用商店',
              },
              ...menuItems,
            ]}
            onClick={handleMenuClick}
          />
        </Sider>
        <AntLayout style={{ padding: '24px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <Content className="layout-content">{children}</Content>
        </AntLayout>
      </AntLayout>
    </AntLayout>
  )
}

