"""绘图 API 端点."""
from fastapi import APIRouter, HTTPException, Depends
from app.models.drawing import DrawingRequest, DrawingResponse, DrawingError
from app.services.drawing_service import drawing_service
from app.apis.deps import get_api_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=DrawingResponse)
async def generate_image(
    request: DrawingRequest,
    api_key: str = Depends(get_api_key)
) -> DrawingResponse:
    """
    生成图片接口.
    
    Args:
        request: 绘图请求
        api_key: API 密钥（通过依赖注入）
        
    Returns:
        DrawingResponse: 绘图响应
    """
    try:
        return await drawing_service.generate_image(request)
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        raise HTTPException(
            status_code=400,
            detail=DrawingError(
                success=False,
                error=str(e),
                code="INVALID_PARAMS"
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"生成图片失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=DrawingError(
                success=False,
                error=f"内部服务器错误: {str(e)}",
                code="INTERNAL_ERROR"
            ).model_dump()
        )

