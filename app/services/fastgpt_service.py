"""FastGPT 服务 - 与 FastGPT API 通信."""
from typing import Dict, Any, Optional
from app.core.config import settings
import httpx
import logging

logger = logging.getLogger(__name__)


class FastGPTService:
    """FastGPT 服务类."""
    
    def __init__(self):
        """初始化 FastGPT 服务."""
        self.api_url = settings.FASTGPT_API_URL
        self.api_key = settings.FASTGPT_API_KEY
        self.timeout = settings.TIMEOUT
    
    async def chat(
        self,
        message: str,
        chat_id: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        与 FastGPT 进行对话.
        
        Args:
            message: 用户消息
            chat_id: 会话 ID（可选）
            stream: 是否流式返回
            **kwargs: 其他参数
            
        Returns:
            Dict[str, Any]: FastGPT 响应
        """
        try:
            if not self.api_url or not self.api_key:
                raise ValueError("FastGPT API URL 或 API Key 未配置")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "message": message,
                    "chatId": chat_id,
                    "stream": stream,
                    **kwargs
                }
                
                response = await client.post(
                    f"{self.api_url}/api/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"FastGPT HTTP 错误: {e}")
            raise Exception(f"FastGPT 请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"FastGPT 调用时发生错误: {e}")
            raise
    
    async def get_chat_history(self, chat_id: str) -> Dict[str, Any]:
        """
        获取聊天历史记录.
        
        Args:
            chat_id: 会话 ID
            
        Returns:
            Dict[str, Any]: 聊天历史
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                response = await client.get(
                    f"{self.api_url}/api/v1/chat/history/{chat_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                return response.json()
                
        except Exception as e:
            logger.error(f"获取聊天历史失败: {e}")
            raise


# 创建全局服务实例
fastgpt_service = FastGPTService()

