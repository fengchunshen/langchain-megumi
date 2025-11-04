# LangChain-Megumi

基于 FastAPI + LangChain 的 AI 服务，用于与 RuoYi 后端集成。

## 技术栈

- **FastAPI**: 高性能 API 框架
- **LangChain (LCEL & LangGraph)**: AI 任务编排
- **Pydantic**: 数据模型和验证
- **Httpx**: 异步 HTTP 客户端
- **Docker**: 容器化部署

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

## API 端点

- `POST /api/v1/drawing/generate` - 生成图片
- `POST /api/v1/ocr/recognize` - OCR 文字识别
- `POST /api/v1/fastgpt/chat` - FastGPT 对话
- `GET /api/v1/fastgpt/history/{chat_id}` - 获取聊天历史
- `POST /api/v1/agent/orchestrate` - 任务编排
- `POST /api/v1/analysis/analyze-node` - 分析产业节点并生成标签画像
- `POST /api/v1/analysis/analyze-solution` - 分析解决方案并生成相关标签
- `POST /api/v1/analysis/analyze-company-tags` - 分析企业经营范围并生成相关标签
- `GET /api/v1/analysis/health` - AI分析服务健康检查
- `POST /api/v1/deepsearch/run` - DeepSearch 深度研究流程

## /analyze-node 接口使用说明

### 接口地址
```
POST /api/v1/analysis/analyze-node
```

### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| nodeName | string | 是 | 节点名称，例如："光伏电池" |
| parentProfile | object | 否 | 父节点信息，例如：{"name": "光伏产业"} |
| siblingsProfiles | array | 否 | 兄弟节点信息列表，例如：[{"name": "光伏组件"}, {"name": "光伏材料"}] |

### 请求示例

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/analyze-node" \
  -H "Content-Type: application/json" \
  -d '{
    "nodeName": "TOPCon电池",
    "parentProfile": {
      "name": "光伏产业"
    },
    "siblingsProfiles": [
      {"name": "PERC电池"},
      {"name": "HJT电池"}
    ]
  }'
```

#### Python (requests)
```python
import requests

url = "http://localhost:8000/api/v1/analysis/analyze-node"
payload = {
    "nodeName": "TOPCon电池",
    "parentProfile": {
        "name": "光伏产业"
    },
    "siblingsProfiles": [
        {"name": "PERC电池"},
        {"name": "HJT电池"}
    ]
}

response = requests.post(url, json=payload)
print(response.json())
```

#### JavaScript (fetch)
```javascript
fetch('http://localhost:8000/api/v1/analysis/analyze-node', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    nodeName: 'TOPCon电池',
    parentProfile: {
      name: '光伏产业'
    },
    siblingsProfiles: [
      {name: 'PERC电池'},
      {name: 'HJT电池'}
    ]
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

### 响应示例

```json
{
  "success": true,
  "data": {
    "coreTechnologies": [
      {"name": "TOPCon技术", "weight": 0.9},
      {"name": "隧穿氧化层", "weight": 0.8},
      {"name": "N型硅片", "weight": 0.7}
    ],
    "applicationScenarios": [
      {"name": "高效光伏组件", "weight": 0.8},
      {"name": "分布式光伏", "weight": 0.7}
    ]
  },
  "error": null,
  "timestamp": "2025-01-01T12:00:00"
}
```

### 响应字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| data | object | 分析结果数据，包含分类的标签和权重 |
| data.coreTechnologies | array | 核心技术标签列表 |
| data.coreTechnologies[].name | string | 标签名称 |
| data.coreTechnologies[].weight | number | 标签权重（0-1之间） |
| data.applicationScenarios | array | 应用场景标签列表 |
| error | string | 错误信息（如果有） |
| timestamp | string | 响应时间戳 |

### 注意事项

1. 确保已配置 `DEEPSEEK_API_KEY` 环境变量
2. 节点名称应简洁明了，建议2-8个字符
3. 父节点和兄弟节点信息有助于生成更精准的标签
4. 接口使用异步处理，建议设置合适的超时时间

## /deepsearch/run 接口使用说明

### 接口地址
```
POST /api/v1/deepsearch/run
```

### 接口说明

DeepSearch 是一个基于 Gemini 的深度研究流程，能够自动执行多轮搜索、分析和总结，返回带引用的研究结果。

### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| query | string | 是 | 研究主题/问题，长度1-8000字符 |
| initial_search_query_count | int | 否 | 初始搜索 Query 数量，范围1-10，不传则使用默认配置 |
| max_research_loops | int | 否 | 最大研究循环次数，范围1-10，不传则使用默认配置 |
| reasoning_model | string | 否 | 用于反思/总结的模型覆盖，不传则使用默认配置 |

### 请求示例

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/deepsearch/run" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "query": "TOPCon电池技术的最新发展及应用前景",
    "initial_search_query_count": 3,
    "max_research_loops": 5
  }'
```

#### Python (requests)
```python
import requests

url = "http://localhost:8000/api/v1/deepsearch/run"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "your_api_key"
}
payload = {
    "query": "TOPCon电池技术的最新发展及应用前景",
    "initial_search_query_count": 3,
    "max_research_loops": 5
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

#### JavaScript (fetch)
```javascript
fetch('http://localhost:8000/api/v1/deepsearch/run', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your_api_key'
  },
  body: JSON.stringify({
    query: 'TOPCon电池技术的最新发展及应用前景',
    initial_search_query_count: 3,
    max_research_loops: 5
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

### 响应示例

```json
{
  "success": true,
  "answer": "TOPCon（隧穿氧化层钝化接触）电池技术是当前光伏行业的重要发展方向之一...\n[1][2]",
  "sources": [
    {
      "label": "TOPCon技术概述",
      "short_url": "[1]",
      "value": "https://example.com/article1"
    },
    {
      "label": "TOPCon市场分析",
      "short_url": "[2]",
      "value": "https://example.com/article2"
    }
  ],
  "metadata": {
    "research_loop_count": 3,
    "number_of_queries": 8
  },
  "message": null
}
```

### 响应字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| answer | string | 最终带引用的研究结果，正文中包含引用标记如 [1][2] |
| sources | array | 被使用的数据源列表 |
| sources[].label | string | 数据源标题/标签 |
| sources[].short_url | string | 短链引用标记（如 [1]），用于正文中引用 |
| sources[].value | string | 原始 URL |
| metadata | object | 附加元数据 |
| metadata.research_loop_count | int | 实际执行的研究循环次数 |
| metadata.number_of_queries | int | 搜索查询总数 |
| message | string | 附加消息（如果有） |

### 注意事项

1. 确保已配置 `GEMINI_API_KEY` 和 `GEMINI_API_URL` 环境变量
2. 确保已配置 `BOCHA_API_KEY` 环境变量（用于搜索功能）
3. 需要 API Key 认证，请求头中需包含 `X-API-Key`
4. 接口执行时间较长（可能几分钟），建议设置较长的超时时间（建议600秒）
5. query 字段应明确描述研究主题，有助于生成更精准的搜索结果
6. initial_search_query_count 和 max_research_loops 参数用于控制搜索深度，可根据需求调整

## OCR 配置说明

### 环境变量配置

项目使用阿里云 DashScope（通义千问）OCR 服务。在 `.env` 文件中配置以下参数：

```bash
# DashScope (阿里云通义千问) OCR 配置
DASHSCOPE_API_KEY=sk-your_dashscope_api_key_here          # DashScope API 密钥（必填）
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # DashScope API 地址（必填）
DASHSCOPE_OCR_MODEL=qwen-vl-ocr-latest                    # OCR 模型名称（可选，默认：qwen-vl-ocr-latest）
```

### 配置示例

```bash
DASHSCOPE_API_KEY=sk-0b7d3b1046744800bb1c989ee16ba576
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_OCR_MODEL=qwen-vl-ocr-latest
```

### 配置验证

配置完成后，重启服务，OCR 服务会自动从环境变量加载配置。如果配置不完整，调用 OCR API 时会返回错误。

### 获取 DashScope API Key

1. 访问 [阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/)
2. 创建 API Key
3. 将 API Key 配置到 `.env` 文件中

## 项目结构

```
jingboAI_python/
├── app/
│   ├── main.py                # FastAPI 应用主入口
│   ├── apis/                  # API 路由层
│   │   ├── deps.py            # FastAPI 依赖项
│   │   └── v1/                 # API v1 版本
│   │       ├── endpoint_drawing.py
│   │       ├── endpoint_ocr.py
│   │       ├── endpoint_fastgpt.py
│   │       ├── endpoint_agent.py
│   │       ├── endpoint_analysis.py
│   │       └── endpoint_deepsearch.py
│   ├── core/                  # 核心配置
│   │   ├── config.py          # 配置管理
│   │   └── security.py        # 安全相关
│   ├── models/                # Pydantic 数据模型
│   ├── services/              # 业务逻辑层
│   └── chains/                # LangChain 链
├── .env.example               # 环境变量示例
├── requirements.txt           # Python 依赖
├── Dockerfile                 # Docker 配置
└── README.md                  # 项目说明文档

```
