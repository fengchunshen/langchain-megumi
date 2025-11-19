# Megumi AI 前端应用商店

基于 React + TypeScript + Vite 构建的 AI 应用商店前端应用。

## 技术栈

- **React 18**: UI 框架
- **TypeScript**: 类型安全
- **Vite**: 构建工具
- **Ant Design**: UI 组件库
- **React Router**: 路由管理
- **Axios**: HTTP 请求

## 项目结构

```
frontend/
├── src/
│   ├── api/              # API 请求封装
│   ├── appStore/         # 应用商店配置
│   ├── components/       # 公共组件
│   ├── hooks/            # 自定义 Hooks
│   ├── pages/            # 页面组件
│   │   ├── AppStore/     # 应用商店首页
│   │   └── apps/         # 各应用页面
│   ├── styles/           # 全局样式
│   ├── App.tsx           # 根组件
│   └── main.tsx          # 入口文件
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## 快速开始

### 安装依赖

```bash
cd frontend
npm install
```

### 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_MEGUMI_API_KEY=your_dev_key_here
```

### 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173

### 构建生产版本

```bash
npm run build
```

构建产物在 `dist` 目录。

## 功能特性

### 应用商店首页

- 应用卡片展示
- 搜索和分类筛选
- 快速导航到各应用

### 已实现的应用

1. **FastGPT 对话** (`/apps/fastgpt`)
   - 多轮对话
   - 会话管理
   - 消息历史

2. **DeepSearch 研究** (`/apps/deepsearch`)
   - 同步/流式执行
   - 实时进度展示
   - Markdown 报告渲染

3. **智能体编排** (`/apps/agent`)
   - 任务类型选择
   - 参数配置
   - 结果展示

4. **绘图生成** (`/apps/drawing`)
   - 文生图
   - 参数配置
   - 图片预览和下载

5. **OCR 文字识别** (`/apps/ocr`)
   - 图片上传/URL 输入
   - 多语言识别
   - 文本块展示

6. **天眼查批量查询** (`/apps/tianyancha-batch`)
   - Excel 文件上传
   - 批量查询
   - 结果下载

7. **AI 分析类应用**
   - 节点分析 (`/apps/analysis-node`)
   - 解决方案标签分析 (`/apps/analysis-solution`)
   - 企业标签分析 (`/apps/analysis-company`)

8. **系统监控** (`/apps/monitor`)
   - 健康状态监控
   - SSE 连接统计
   - 活跃用户列表

## 开发规范

### 代码风格

- 使用 TypeScript 严格模式
- 遵循 ESLint 规则
- 使用 Prettier 格式化

### 路径别名

- `@/` 指向 `src/` 目录

### API 请求

所有 API 请求通过 `src/api/` 目录下的模块封装，统一使用 `http.ts` 中的 Axios 实例。

## 注意事项

1. 确保后端 FastAPI 服务运行在 `http://localhost:8000`
2. 开发环境通过 Vite 代理 `/api` 到后端
3. API Key 通过环境变量配置，仅用于开发/测试

## 后续计划

- [ ] 支持流式对话（FastGPT）
- [ ] 优化 DeepSearch 流式体验
- [ ] 添加更多 UI 优化
- [ ] 完善错误处理
- [ ] 添加单元测试

