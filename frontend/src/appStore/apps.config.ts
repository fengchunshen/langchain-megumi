export interface AppConfig {
  id: string
  name: string
  description: string
  route: string
  category: '对话' | '研究' | '图像' | '文档' | '企业服务' | '监控'
  tags: string[]
  icon?: string
}

export const appsConfig: AppConfig[] = [
  {
    id: 'fastgpt',
    name: 'FastGPT 对话',
    description: '基于 FastGPT 的多轮对话能力，支持上下文记忆和流式响应',
    route: '/apps/fastgpt',
    category: '对话',
    tags: ['LLM', '对话', '多轮'],
  },
  {
    id: 'deepsearch',
    name: 'DeepSearch 研究',
    description: '深度研究流程，自动搜索、分析和生成研究报告',
    route: '/apps/deepsearch',
    category: '研究',
    tags: ['研究', '搜索', '报告'],
  },
  {
    id: 'agent',
    name: '智能体编排',
    description: '智能体任务编排，支持复杂多步骤任务执行',
    route: '/apps/agent',
    category: '对话',
    tags: ['智能体', '编排', '任务'],
  },
  {
    id: 'drawing',
    name: '绘图生成',
    description: '文生图能力，根据文本描述生成高质量图片',
    route: '/apps/drawing',
    category: '图像',
    tags: ['图像', '生成', 'AI'],
  },
  {
    id: 'ocr',
    name: 'OCR 文字识别',
    description: '图片文字识别，支持中英文自动识别',
    route: '/apps/ocr',
    category: '文档',
    tags: ['OCR', '识别', '文字'],
  },
  {
    id: 'tianyancha',
    name: '天眼查批量查询',
    description: '批量查询企业信息，支持 Excel 文件上传',
    route: '/apps/tianyancha-batch',
    category: '企业服务',
    tags: ['企业', '查询', '批量'],
  },
  {
    id: 'analysis-node',
    name: '节点分析',
    description: 'AI 节点分析，分析节点特征和关系',
    route: '/apps/analysis-node',
    category: '企业服务',
    tags: ['分析', '节点', 'AI'],
  },
  {
    id: 'analysis-solution',
    name: '解决方案标签分析',
    description: '分析解决方案标签，提供智能分类建议',
    route: '/apps/analysis-solution',
    category: '企业服务',
    tags: ['分析', '标签', '解决方案'],
  },
  {
    id: 'analysis-company',
    name: '企业标签分析',
    description: '企业标签分析，自动生成企业特征标签',
    route: '/apps/analysis-company',
    category: '企业服务',
    tags: ['分析', '标签', '企业'],
  },
  {
    id: 'monitor',
    name: '系统监控',
    description: '系统健康监控，查看服务状态和活跃连接',
    route: '/apps/monitor',
    category: '监控',
    tags: ['监控', '健康', '系统'],
  },
]

export const categories = ['对话', '研究', '图像', '文档', '企业服务', '监控'] as const

