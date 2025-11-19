Megumi AI 前端应用商店方案设计文档
1. 背景与目标
1.1 背景
Megumi AI Service 当前提供了一组基于 FastAPI + LangChain 的 AI 能力，包括：
智能体任务编排（Agent）
DeepSearch 研究流程（含 SSE 流式）
FastGPT 对话
绘图（文生图）
OCR 文字识别
天眼查批量查询
AI 分析（节点分析 / 解决方案标签 / 企业标签）
系统监控与健康检查
后端接口已较为稳定，但缺少统一的可视化前端，难以被业务人员或产品化场景快速使用与展示。
1.2 目标
本方案旨在：
基于 React 构建一个独立的 “AI 应用商店”前端：
首页以“应用商店”的形式展示各 AI 能力作为“应用卡片”
点击卡片进入对应应用，完成参数输入与结果展示
暂不考虑与 RuoYi 集成，前端直接调用已有 FastAPI 接口
为后续扩展（新增 AI 能力 / 接入其他平台）预留空间
2. 整体架构设计
2.1 前后端架构
前端：React SPA（单页应用）
负责 UI 渲染、路由导航、应用商店展示、各 AI 应用交互
后端：现有 FastAPI 服务
主要端点根据 app/main.py 路由：
/api/v1/drawing – 绘图
/api/v1/ocr – OCR
/api/v1/fastgpt – FastGPT 对话
/api/v1/agent – 智能体任务编排
/api/v1/analysis – AI 分析
/api/v1/deepsearch – DeepSearch 流程
/api/v1/monitor – 监控
/api/v1/tianyancha – 天眼查批量查询
交互方式：
前端通过 HTTP / SSE 直接调用上述接口
鉴权通过请求头 X-API-Key（开发环境可使用配置注入）
2.2 部署拓扑（建议）
开发环境：
FastAPI：http://localhost:8000
前端：http://localhost:5173（Vite dev server）
Vite 代理：将 /api 代理到 FastAPI
生产环境（简化版本）：
使用 Nginx 或其他 Web 服务器托管前端静态资源
统一将 /api 反向代理到 FastAPI 服务
3. 技术栈与工程规范
3.1 技术选型
框架与语言
React 18
TypeScript：静态类型，提升可维护性
Vite：作为构建与开发工具，快速启动与 HMR
路由与布局
React Router v6：实现“应用商店 → 应用详情”的页面路由
顶层布局包括：
顶部导航栏（项目标题、简要说明）
左侧/顶部菜单（应用分类筛选）
主内容区（应用商店 / 各应用页面）
UI 组件库
Ant Design：
卡片（Card）、列表（List）、表单（Form）、上传（Upload）、标签（Tag）等
有利于快速实现“应用商店”风格和统一视觉规范
数据请求与状态管理
Axios：封装 HTTP 请求
轻量状态管理（可选其一）：
Zustand 或 Redux Toolkit
用于存储全局信息（如当前选中应用、用户偏好、API 配置等）
SSE（Server-Sent Events）：
使用原生 EventSource 封装为自定义 hook（如 useEventSource）
工程规范
TypeScript 严格模式
ESLint + Prettier 统一代码风格
使用路径别名（如 @/api, @/pages, @/components）
3.2 配置约定
环境变量（示例）：
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_MEGUMI_API_KEY=your_dev_key_here
Axios 实例：
baseURL 来自 VITE_API_BASE_URL
请求拦截器：
自动注入 X-API-Key: VITE_MEGUMI_API_KEY（仅开发/测试使用）
响应拦截器：
统一处理错误状态码，规范错误提示格式
4. 路由与页面结构设计
4.1 顶层路由结构
/apps – 应用商店首页（默认入口）
/apps/fastgpt – FastGPT 对话应用
/apps/deepsearch – DeepSearch 研究应用
/apps/agent – 智能体编排应用
/apps/drawing – 绘图应用
/apps/ocr – OCR 应用
/apps/tianyancha-batch – 天眼查批量查询应用
/apps/analysis-node – 节点分析应用
/apps/analysis-solution – 解决方案标签分析应用
/apps/analysis-company – 企业标签分析应用
/apps/monitor – 系统监控应用
> 说明：初期以固定路由配置为主，后续可将路由信息完全通过“应用配置中心”驱动。
4.2 应用商店首页（/apps）
定位：统一入口，展示所有可用 AI 能力，以“应用卡片”形式呈现。
数据来源：本地配置文件 apps.config.ts（后续可扩展为后端动态配置）。
关键元素：
搜索框：按名称/描述模糊搜索应用
分类筛选：例如 “对话”、“研究”、“图像”、“文档”、“企业服务”、“监控”
应用卡片内容：
应用名称（如“FastGPT 对话”）
简要描述（1–2 行）
标签（如“LLM”、“对话”、“多轮”）
“立即使用”按钮 → 跳转对应路由
5. 各应用详情页设计
5.1 FastGPT 对话应用（/apps/fastgpt）
后端接口：
POST /fastgpt/chat – 对话
GET /fastgpt/history/{chat_id} – 历史记录
前端交互：
左侧：会话列表（chat_id），支持新建/切换会话
右侧：对话消息列表 + 输入框
请求参数：
message: string
chat_id?: string
stream: bool（前期可默认 false，后续支持流式）
展示结果：
按时间顺序显示用户与 AI 消息
每条消息可显示时间、角色、内容
5.2 DeepSearch 研究应用（/apps/deepsearch）
后端接口：
POST /deepsearch/run – 同步执行，返回完整报告
POST /deepsearch/run/stream – SSE 流式执行
前端交互：
输入区域：
必填：query
高级选项：initial_search_query_count、max_research_loops、reasoning_model、report_format
同步模式：
提交后直接展示 markdown_report、sources、all_sources
流式模式：
使用 EventSource 订阅流式事件
根据 DeepSearchEventType 分步骤更新 UI：
RESEARCH_PLAN：显示研究计划
WEB_SEARCHING、WEB_RESULT：显示搜索进度与结果摘要
REFLECTION、OPTIMIZATION：展示推理和优化过程
REPORT_GENERATED、COMPLETED：显示最终报告
5.3 智能体编排应用（/apps/agent）
后端接口：
POST /agent/orchestrate – 执行任务编排
前端交互：
表单字段（映射 AgentRequest）：
query
task_type（枚举：Q&A、代码生成、数据分析、多步骤等）
system_prompt
temperature
max_tokens
context（JSON 编辑区域）
结果展示：
主体回答：answer
推理过程：reasoning
相关数据源：sources
附加信息：metadata
5.4 绘图应用（/apps/drawing）
后端接口：
POST /drawing/generate
前端交互：
表单字段（映射 DrawingRequest）：
prompt、style、width、height、n
调用后展示 image_urls：
网格形式展示图片
支持点击放大预览与下载
5.5 OCR 应用（/apps/ocr）
后端接口：
POST /ocr/recognize
前端交互：
输入方式：
上传图片文件 → 前端转换为 image_base64
或直接输入 image_url
选择识别语言 language（自动 / 中文 / 英文）
结果展示：
整体识别文本 text
文本块列表 text_blocks，可显示置信度、区域信息
5.6 天眼查批量查询应用（/apps/tianyancha-batch）
后端接口：
POST /tianyancha/batch-query（上传 Excel）
前端交互：
使用 AntD Upload 组件上传 xlsx/xls
提交后：
展示 total_count、success_count、failed_count
提供结果文件下载按钮（利用返回的 file_path/file_name，依赖后端静态文件映射）
5.7 AI 分析类应用
节点分析（/apps/analysis-node）
接口：POST /analysis/analyze-node
字段：nodeName、parentProfile、siblingsProfiles
展示：JSON 结果视图（树形结构）
解决方案标签分析（/apps/analysis-solution）
接口：POST /analysis/analyze-solution
字段：solutionName、description
展示：标签列表 + 简要说明
企业标签分析（/apps/analysis-company）
接口：POST /analysis/analyze-company-tags
字段：companyName、businessScope
展示：标签列表 + 时间戳等信息
5.8 系统监控应用（/apps/monitor）
后端接口：
GET /monitor/sse/status
GET /monitor/sse/active-users
GET /monitor/system/health
前端交互：
健康状态卡片：显示 status（healthy/warning/critical）、主要指标
指标卡片：活跃连接数、总连接数、成功率、平均时长等
活跃用户列表：用户标识、连接数等（若有）
6. 前端项目结构设计
6.1 目录结构（建议）
src/
api/
http.ts – Axios 实例、拦截器
fastgpt.ts、deepsearch.ts、agent.ts、drawing.ts、ocr.ts、tianyancha.ts、analysis.ts、monitor.ts
appStore/
apps.config.ts – 应用商店配置（应用列表、路由、元信息）
components/ – 应用卡片、应用头部信息等
pages/
AppStore/ – 应用商店首页
apps/FastGPT/
apps/DeepSearch/
apps/Agent/
apps/Drawing/
apps/OCR/
apps/Tianyancha/
apps/AnalysisNode/
apps/AnalysisSolution/
apps/AnalysisCompany/
apps/Monitor/
hooks/
useEventSource.ts
useDeepSearchStream.ts
router/
index.tsx – 路由定义
store/ – 全局状态（可选）
styles/ – 全局样式与主题
7. 实施计划与里程碑
初始化工程
创建 frontend 目录，使用 Vite + React + TS 初始化项目
引入 Ant Design、React Router、Axios
配置 ESLint、Prettier、别名路径
基础架构搭建
完成全局布局（导航 + 内容区）
实现路由基础结构（/apps + 各应用占位页面）
编写 apps.config.ts，完成应用列表配置与 App Store 首页展示
核心应用落地
优先实现以下应用完整功能：
FastGPT 对话
DeepSearch 研究（含流式）
绘图
验证请求封装、错误处理、UI 交互流程
扩展其它应用
补齐 OCR、天眼查批量查询、AI 分析三类应用
实现系统监控页面
优化与文档
增加统一错误提示与 loading 状态
编写使用文档（包括环境配置、启动方式、接口说明）
根据实际使用反馈优化 UI 与交互体验