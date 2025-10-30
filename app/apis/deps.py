"""API 依赖项模块."""
from typing import Optional
from fastapi import Depends
from app.core.security import verify_api_key


# 可选：如果不需要所有接口都验证，可以创建一个可选的依赖
async def get_api_key(api_key: Optional[str] = Depends(verify_api_key)) -> Optional[str]:
    """获取验证后的 API Key（可选验证）."""
    return api_key

