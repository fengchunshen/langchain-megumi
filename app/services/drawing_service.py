"""绘图服务 - 使用 LangChain 调用绘图 API."""
from typing import List
from app.models.drawing import DrawingRequest, DrawingResponse
from app.core.config import settings
import httpx
import logging

logger = logging.getLogger(__name__)


class DrawingService:
    """绘图服务类."""
    
    def __init__(self):
        """初始化绘图服务."""
        self.api_key = settings.DRAWING_API_KEY
        self.api_url = settings.DRAWING_API_URL or "https://api.openai.com/v1/images/generations"
        self.timeout = settings.TIMEOUT
    
    async def generate_image(self, request: DrawingRequest) -> DrawingResponse:
        """
        生成图片.
        
        Args:
            request: 绘图请求
            
        Returns:
            DrawingResponse: 绘图响应
            
        Raises:
            ValueError: 参数错误
            httpx.HTTPError: HTTP 请求错误
            Exception: 其他错误
        """
        if not self.api_key:
            raise ValueError("绘图 API Key 未配置")
        
        # TODO: 集成 LangChain 的图片生成链
        # 这里可以使用 LangChain 的 LCEL 来构建图片生成流程
        
        # 示例：调用 OpenAI DALL-E API
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "dall-e-3",
                "prompt": request.prompt,
                "size": f"{request.width}x{request.height}",
                "n": request.n,
                "quality": "standard"
            }
            
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            image_urls = [item["url"] for item in data.get("data", [])]
            
            return DrawingResponse(
                success=True,
                image_urls=image_urls,
                message="图片生成成功"
            )


# 创建全局服务实例
drawing_service = DrawingService()

