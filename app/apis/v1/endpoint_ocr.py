"""OCR API 端点."""
from fastapi import APIRouter, HTTPException, Depends
from app.models.ocr import OCRRequest, OCRResponse, OCRError
from app.services.ocr_service import ocr_service
from app.apis.deps import get_api_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/recognize", response_model=OCRResponse)
async def recognize_text(
    request: OCRRequest,
    api_key: str = Depends(get_api_key)
) -> OCRResponse:
    """
    识别图片中的文字接口.
    
    Args:
        request: OCR 请求
        api_key: API 密钥（通过依赖注入）
        
    Returns:
        OCRResponse: OCR 响应
    """
    try:
        return await ocr_service.recognize_text(request)
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        raise HTTPException(
            status_code=400,
            detail=OCRError(
                success=False,
                error=str(e),
                code="INVALID_PARAMS"
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"OCR 识别失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=OCRError(
                success=False,
                error=f"内部服务器错误: {str(e)}",
                code="INTERNAL_ERROR"
            ).model_dump()
        )

