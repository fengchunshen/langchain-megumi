"""FastGPT API 端点."""
from fastapi import APIRouter, HTTPException, Depends
from app.services.fastgpt_service import fastgpt_service
from app.apis.deps import get_api_key
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat")
async def chat_with_fastgpt(
    message: str,
    chat_id: Optional[str] = None,
    stream: bool = False,
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    与 FastGPT 进行对话接口.
    
    Args:
        message: 用户消息
        chat_id: 会话 ID（可选）
        stream: 是否流式返回
        api_key: API 密钥（通过依赖注入）
        
    Returns:
        Dict[str, Any]: FastGPT 响应
    """
    try:
        result = await fastgpt_service.chat(
            message=message,
            chat_id=chat_id,
            stream=stream
        )
        return result
    except Exception as e:
        logger.error(f"FastGPT 调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"FastGPT 调用失败: {str(e)}")


@router.get("/history/{chat_id}")
async def get_chat_history(
    chat_id: str,
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    获取聊天历史记录接口.
    
    Args:
        chat_id: 会话 ID
        api_key: API 密钥（通过依赖注入）
        
    Returns:
        Dict[str, Any]: 聊天历史
    """
    try:
        result = await fastgpt_service.get_chat_history(chat_id)
        return result
    except Exception as e:
        logger.error(f"获取聊天历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取聊天历史失败: {str(e)}")

