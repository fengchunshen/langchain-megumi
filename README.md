# langchain-megumi

langchain-megumi 是基于 FastAPI + LangChain 的 AI 服务项目，专为与 RuoYi 后端集成而设计。项目提供深度研究、绘图、OCR、FastGPT 对话和智能体任务编排等多项 AI 功能。

## 技术栈

- **FastAPI**: 高性能 Web API 框架，使用异步编程
- **LangChain**: AI 任务编排，使用 LCEL (LangChain Expression Language) 和 LangGraph
- **Pydantic v2**: 数据模型验证和设置管理
- **httpx**: 异步 HTTP 客户端
- **Python 3.8+**: 使用类型提示和异步特性

## 核心功能

### DeepSearch 研究引擎
- 基于 LangGraph 状态图的多阶段自适应研究系统
- 迭代式信息检索与质量评估
- 自动生成带引用的研究报告
- 支持流式输出 (SSE)
- 模型降级保障服务可用性

### 研究报告生成器
- **自动报告生成**: 根据研究结果生成规范的公文格式报告
- **引用管理**: 智能引用系统，支持自动编号和超链接
- **质量评估**: 多维度质量评估指标（内容质量、信息完整性、来源可靠性、相关性）
- **事实验证**: 关键事实的交叉验证机制
- **结构化输出**: 支持结构化发现和回退渲染逻辑
- **执行摘要**: 自动生成100-200字执行摘要
- **质量保障**: 可选的质量保障章节（对外用户报告默认隐藏）

## 项目结构

```
app/
├── main.py                    # FastAPI 应用入口
├── apis/                      # API 路由层
│   └── v1/
│       ├── endpoint_agent.py      # AI 智能体端点
│       ├── endpoint_analysis.py   # 产业分析端点
│       ├── endpoint_deepsearch.py # DeepSearch 端点
│       ├── endpoint_drawing.py    # 绘图生成端点
│       ├── endpoint_fastgpt.py    # FastGPT 对话端点
│       ├── endpoint_monitor.py    # 监控端点
│       └── endpoint_ocr.py        # OCR 识别端点
├── core/                      # 核心配置
│   ├── config.py             # Pydantic Settings 配置管理
│   ├── logger.py             # 日志配置
│   └── security.py           # 安全认证
├── models/                    # Pydantic 数据模型
│   ├── agent.py              # 智能体模型
│   ├── analysis.py           # 分析模型
│   ├── deepsearch.py         # DeepSearch 模型
│   ├── drawing.py            # 绘图模型
│   └── ocr.py                # OCR 模型
├── services/                  # 业务逻辑层
│   ├── ai_agent_service.py       # AI 智能体服务
│   ├── ai_communicator_service.py # AI 通信服务
│   ├── company_tag_service.py     # 公司标签服务
│   ├── deepsearch_engine.py       # LangGraph 状态图引擎
│   ├── deepsearch_service.py      # DeepSearch 服务
│   ├── deepsearch_prompts.py      # 提示词模板
│   ├── deepsearch_types.py        # 类型定义
│   ├── deepsearch_utils.py        # 工具函数
│   ├── drawing_service.py         # 绘图服务
│   ├── fastgpt_service.py         # FastGPT 服务
│   ├── ocr_service.py             # OCR 服务
│   ├── orchestration_service.py   # 任务编排服务
│   ├── report_generator.py        # 研究报告生成器
│   ├── sse_monitor.py             # SSE 连接监控
│   └── web_scraper.py             # 网页抓取
└── chains/                    # LangChain 链定义
    ├── fastgpt_retriever.py       # FastGPT 检索器
    └── file_extractor_runnable.py # 文件提取器
```

## 快速开始

### 1. 安装依赖

```powershell
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写相关配置：

```powershell
copy .env.example .env
```

### 3. 运行服务

```powershell
python -m app.main
```

或使用 uvicorn：

```powershell
uvicorn app.main:app --reload
```

### 4. 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Docker 部署

### 构建镜像

```powershell
docker build -t langchain-megumi .
```

### 运行容器

```powershell
docker run -d `
  --name langchain-megumi `
  -p 8000:8000 `
  --env-file .env `
  langchain-megumi
```

## API 端点

### 深度研究服务

- `POST /api/v1/deepsearch/run` - 同步执行研究流程
- `POST /api/v1/deepsearch/run/stream` - 流式执行（SSE）

### 绘图服务

- `POST /api/v1/drawing/generate` - AI 图片生成

### OCR 服务

- `POST /api/v1/ocr/recognize` - 光学字符识别

### FastGPT 服务

- `POST /api/v1/fastgpt/chat` - FastGPT 对话

### AI 智能体

- `POST /api/v1/agent/orchestrate` - 任务编排

### 产业分析

- `POST /api/v1/analysis/analyze-node` - 产业节点分析

### 系统监控

- `GET /api/v1/monitor/sse/status` - SSE 连接监控

## DeepSearch 研究引擎详情

DeepSearch 是基于 LangGraph 状态图的多阶段自适应研究系统，通过迭代式信息检索与质量评估生成带引用的研究报告。

### 核心算法

**状态图工作流**：采用 LangGraph 构建有向状态图，节点间通过条件边实现动态路由。

**研究流程**：
1. **研究计划生成**：基于查询主题分解子问题与研究路径
2. **查询生成**：根据研究计划生成多维度搜索查询
3. **网络搜索**：并行执行查询并聚合结果
4. **反思评估**：判断信息充分性，决定是否进入下一轮迭代
5. **质量增强**：内容质量评估 → 事实验证 → 相关性评估 → 总结优化
6. **报告生成**：自动插入引用标记并生成结构化报告

**自适应迭代**：通过反思节点评估知识缺口，动态决定是否继续搜索循环，最大循环次数可配置。

**多维度质量评估**：
- 内容质量：完整性、准确性、深度
- 事实验证：关键事实的交叉验证
- 相关性评估：信息与查询主题的匹配度
- 总结优化：结构化与可读性优化

**流式输出**：支持 Server-Sent Events (SSE) 实时推送研究进度，包含 15 种事件类型，覆盖研究全流程。

**连接管理**：基于 `asyncio.Event` 实现连接级取消机制，支持客户端主动断开时的资源清理。

**模型降级**：Gemini API 异常时自动降级至 Qwen3Max，保证服务可用性。

### 请求参数示例

```json
{
  "query": "TOPCon电池技术的最新发展及应用前景",
  "initial_search_query_count": 3,
  "max_research_loops": 5
}
```

### 流式事件类型

- `started` - 流程启动
- `research_plan` - 研究计划生成
- `query_generated` - 查询生成
- `web_searching` - 网络搜索中
- `web_result` - 搜索结果
- `reflection` - 反思评估
- `quality_assessment` - 质量评估
- `fact_verification` - 事实验证
- `relevance_assessment` - 相关性评估
- `optimization` - 总结优化
- `progress` - 进度更新
- `report_generated` - 报告生成完成
- `completed` - 流程完成
- `cancelled` - 流程取消
- `error` - 错误事件

## 环境配置

```bash
GEMINI_API_KEY=your_gemini_key
GEMINI_API_URL=https://generativelanguage.googleapis.com/v1
BOCHA_API_KEY=your_bocha_key  # 用于网络搜索
DASHSCOPE_API_KEY=your_dashscope_key  # 降级备用
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

## 开发规范

### 代码风格

- 遵循 PEP 8 Python 代码规范
- 使用类型提示和异步编程
- 遵循 Google 风格的中文 docstring
- 使用标准库 → 第三方库 → 本地模块的导入顺序

### 项目规范

- 路由定义使用 `APIRouter`，在 `main.py` 中统一注册
- 数据模型继承自 `pydantic.BaseModel`
- 服务类使用单例模式，方法使用 `async def`
- 使用 `logging` 模块记录错误和重要信息
- 异常处理使用 `HTTPException`，配合 try-except

## 许可证

本项目采用 MIT 许可证。
