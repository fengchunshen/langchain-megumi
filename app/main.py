"""FastAPI 应用主入口."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.apis.v1 import (
    endpoint_drawing,
    endpoint_ocr,
    endpoint_fastgpt,
    endpoint_agent,
    endpoint_analysis,
    endpoint_deepsearch
)
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 始终使用 INFO 级别，以便记录 API 请求信息
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Megumi AI Servive - FastAPI + LangChain 集成服务",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(
    endpoint_drawing.router,
    prefix=f"{settings.API_V1_PREFIX}/drawing",
    tags=["绘图"]
)

app.include_router(
    endpoint_ocr.router,
    prefix=f"{settings.API_V1_PREFIX}/ocr",
    tags=["OCR"]
)

app.include_router(
    endpoint_fastgpt.router,
    prefix=f"{settings.API_V1_PREFIX}/fastgpt",
    tags=["FastGPT"]
)

app.include_router(
    endpoint_agent.router,
    prefix=f"{settings.API_V1_PREFIX}/agent",
    tags=["智能体"]
)

app.include_router(
    endpoint_analysis.router,
    prefix=f"{settings.API_V1_PREFIX}/analysis",
    tags=["AI分析"]
)

app.include_router(
    endpoint_deepsearch.router,
    prefix=f"{settings.API_V1_PREFIX}/deepsearch",
    tags=["DeepSearch"]
)


@app.get("/")
async def root():
    """根路径."""
    return {
        "message": "Megumi AI Servive",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查接口."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        timeout_keep_alive=600,  # 保持连接超时时间（秒），用于长时间任务
        timeout_graceful_shutdown=600  # 优雅关闭超时时间（秒）
    )

