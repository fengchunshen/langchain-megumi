"""FastAPI 应用主入口."""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径，确保可以直接运行此文件
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.apis.v1 import (
    endpoint_drawing,
    endpoint_ocr,
    endpoint_fastgpt,
    endpoint_agent,
    endpoint_analysis,
    endpoint_deepsearch,
    endpoint_monitor,
    endpoint_tianyancha
)
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 始终使用 INFO 级别，以便记录 API 请求信息
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# 创建 FastAPI 应用实例（生产环境禁用 API 文档，防止信息泄露）
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Megumi AI Servive - FastAPI + LangChain 集成服务",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# 配置 CORS（安全漏扫要求：生产环境必须限制具体域名）
origins = []
if settings.ALLOW_ORIGINS and settings.ALLOW_ORIGINS != "*":
    origins = [origin.strip() for origin in settings.ALLOW_ORIGINS.split(",")]
elif settings.DEBUG:
    # 开发环境允许所有来源
    origins = ["*"]
else:
    # 生产环境如果配置为 "*"，则不允许任何来源（安全考虑）
    origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加安全响应头中间件（安全漏扫要求）
@app.middleware("http")
async def add_security_headers(request, call_next):
    """添加安全响应头."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # 如果启用了 HTTPS，建议启用 HSTS
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

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

# 注册监控路由
app.include_router(
    endpoint_monitor.router,
    prefix=f"{settings.API_V1_PREFIX}/monitor",
    tags=["系统监控"]
)

# 注册天眼查路由
app.include_router(
    endpoint_tianyancha.router,
    prefix=f"{settings.API_V1_PREFIX}/tianyancha",
    tags=["天眼查"]
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
    # 根据 DEBUG 模式选择启动方式
    # reload 模式需要模块路径字符串，非 reload 模式可以直接传递 app 对象
    if settings.DEBUG:
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=True,
            timeout_keep_alive=600,  # 保持连接超时时间（秒），用于长时间任务
            timeout_graceful_shutdown=600  # 优雅关闭超时时间（秒）
        )
    else:
        uvicorn.run(
            app,
            host=settings.HOST,
            port=settings.PORT,
            reload=False,
            timeout_keep_alive=600,  # 保持连接超时时间（秒），用于长时间任务
            timeout_graceful_shutdown=600  # 优雅关闭超时时间（秒）
        )

