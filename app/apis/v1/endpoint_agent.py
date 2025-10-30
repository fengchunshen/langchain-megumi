"""智能体任务编排 API 端点."""
from fastapi import APIRouter, HTTPException, Depends
from app.models.agent import AgentRequest, AgentResponse
from app.services.orchestration_service import orchestration_service
from app.apis.deps import get_api_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/orchestrate", response_model=AgentResponse)
async def orchestrate_task(
    request: AgentRequest,
    api_key: str = Depends(get_api_key)
) -> AgentResponse:
    """
    编排并执行复杂任务接口.
    
    Args:
        request: 智能体请求
        api_key: API 密钥（通过依赖注入）
        
    Returns:
        AgentResponse: 智能体响应
    """
    try:
        return await orchestration_service.orchestrate(request)
    except Exception as e:
        logger.error(f"任务编排失败: {e}")
        raise HTTPException(status_code=500, detail=f"任务编排失败: {str(e)}")

