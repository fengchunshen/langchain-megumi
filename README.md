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
│   │       └── endpoint_analysis.py
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
