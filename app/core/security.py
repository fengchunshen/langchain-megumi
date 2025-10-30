"""安全认证模块 - 用于验证来自 RuoYi 的请求."""
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from typing import Optional
from app.core.config import settings

# API Key Header 名称
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)) -> str:
    """
    验证 API Key.
    
    Args:
        api_key: 从请求头中获取的 API Key
        
    Returns:
        str: 验证通过的 API Key
        
    Raises:
        HTTPException: 如果 API Key 无效或缺失
    """
    if not settings.RUOYI_API_KEY:
        # 如果未配置 API Key，则跳过验证（开发环境）
        return api_key or ""
    
    if not api_key or api_key != settings.RUOYI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Key",
        )
    
    return api_key

