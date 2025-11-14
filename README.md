# deepResearch-FilpLine

deepResearch-FilpLine是基于 LangGraph 状态图的多阶段自适应研究系统，通过迭代式信息检索与质量评估生成带引用的研究报告。

## 技术栈

- **FastAPI**: 异步 Web 框架
- **LangGraph**: 状态图工作流编排
- **Pydantic v2**: 数据验证与配置管理
- **httpx**: 异步 HTTP 客户端

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写相关配置：

```bash
cp .env.example .env
```

### 3. 运行服务

```bash
python -m app.main
```

或使用 uvicorn：

```bash
uvicorn app.main:app --reload
```

### 4. 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Docker 部署

### 构建镜像

```bash
docker build -t ruoyi-ai-service .
```

### 运行容器

```bash
docker run -d \
  --name ruoyi-ai-service \
  -p 8000:8000 \
  --env-file .env \
  ruoyi-ai-service
```

## DeepSearch 研究引擎

DeepSearch 是基于 LangGraph 状态图的多阶段自适应研究系统，通过迭代式信息检索与质量评估生成带引用的研究报告。

### 核心算法

**状态图工作流**：采用 LangGraph 构建有向状态图，节点间通过条件边实现动态路由。

**研究流程**：
1. **研究计划生成**：基于查询主题分解子问题与研究路径
2. **查询生成**：根据研究计划生成多维度搜索查询
3. **网络搜索**：并行执行查询并聚合结果
4. **反思评估**：判断信息充分性，决定是否进入下一轮迭代
5. **质量增强**：内容质量评估 → 事实验证 → 相关性评估 → 总结优化
6. **答案生成**：自动插入引用标记并生成结构化报告

**自适应迭代**：通过反思节点评估知识缺口，动态决定是否继续搜索循环，最大循环次数可配置。

**多维度质量评估**：
- 内容质量：完整性、准确性、深度
- 事实验证：关键事实的交叉验证
- 相关性评估：信息与查询主题的匹配度
- 总结优化：结构化与可读性优化

**流式输出**：支持 Server-Sent Events (SSE) 实时推送研究进度，包含 15 种事件类型，覆盖研究全流程。

**连接管理**：基于 `asyncio.Event` 实现连接级取消机制，支持客户端主动断开时的资源清理。

**模型降级**：Gemini API 异常时自动降级至 Qwen3Max，保证服务可用性。

### API 端点

- `POST /api/v1/deepsearch/run` - 同步执行研究流程
- `POST /api/v1/deepsearch/run/stream` - 流式执行（SSE）

### 请求参数

| 参数 | 类型 | 说明 |
|------|------|------|
| query | string | 研究主题，1-8000 字符 |
| initial_search_query_count | int | 初始查询数量，1-10，默认 3 |
| max_research_loops | int | 最大迭代次数，1-5，默认 3 |
| reasoning_model | string | 推理模型覆盖（可选） |
| report_format | enum | 报告格式：formal/casual |

### 响应结构

```json
{
  "success": true,
  "answer": "研究结论文本，包含引用标记 [1][2]...",
  "markdown_report": "完整 Markdown 格式报告",
  "sources": [
    {
      "label": "数据源标题",
      "short_url": "[1]",
      "value": "https://example.com"
    }
  ],
  "all_sources": [...],
  "metadata": {
    "research_loop_count": 3,
    "number_of_queries": 8,
    "number_of_sources": 15,
    "total_sources_found": 23
  }
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

### 使用示例

```bash
curl -X POST "http://localhost:8000/api/v1/deepsearch/run" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "TOPCon电池技术的最新发展及应用前景",
    "initial_search_query_count": 3,
    "max_research_loops": 5
  }'
```

### 环境配置

```bash
GEMINI_API_KEY=your_gemini_key
GEMINI_API_URL=https://generativelanguage.googleapis.com/v1
BOCHA_API_KEY=your_bocha_key  # 用于网络搜索
DASHSCOPE_API_KEY=your_dashscope_key  # 降级备用
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

## 其他 API 端点

- `POST /api/v1/drawing/generate` - 图片生成
- `POST /api/v1/ocr/recognize` - OCR 识别
- `POST /api/v1/fastgpt/chat` - FastGPT 对话
- `POST /api/v1/agent/orchestrate` - 任务编排
- `POST /api/v1/analysis/analyze-node` - 产业节点分析
- `GET /api/v1/monitor/sse/status` - SSE 连接监控



## 项目结构

```
app/
├── main.py                    # FastAPI 应用入口
├── apis/                      # API 路由层
│   └── v1/
│       └── endpoint_deepsearch.py  # DeepSearch 端点
├── core/                      # 核心配置
│   ├── config.py             # Pydantic Settings 配置管理
│   └── security.py           # 安全认证
├── models/                    # Pydantic 数据模型
│   └── deepsearch.py         # DeepSearch 请求/响应模型
├── services/                  # 业务逻辑层
│   ├── deepsearch_service.py # DeepSearch 服务封装
│   ├── deepsearch_engine.py  # LangGraph 状态图引擎
│   ├── deepsearch_prompts.py # 提示词模板
│   ├── deepsearch_types.py   # 类型定义
│   ├── deepsearch_utils.py   # 工具函数
│   ├── report_generator.py   # 报告生成器
│   ├── web_scraper.py        # 网页抓取
│   └── sse_monitor.py        # SSE 连接监控
└── chains/                    # LangChain 链定义
```
