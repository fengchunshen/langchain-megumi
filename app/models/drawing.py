"""绘图相关的 Pydantic 数据模型."""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class DrawingStyle(str, Enum):
    """绘图风格枚举."""
    REALISTIC = "realistic"
    CARTOON = "cartoon"
    ANIME = "anime"
    OIL_PAINTING = "oil_painting"
    WATERCOLOR = "watercolor"


class DrawingRequest(BaseModel):
    """绘图请求模型."""
    prompt: str = Field(..., description="绘图提示词", min_length=1, max_length=1000)
    style: Optional[DrawingStyle] = Field(default=DrawingStyle.REALISTIC, description="绘图风格")
    width: Optional[int] = Field(default=1024, description="图片宽度", ge=256, le=2048)
    height: Optional[int] = Field(default=1024, description="图片高度", ge=256, le=2048)
    n: Optional[int] = Field(default=1, description="生成图片数量", ge=1, le=4)


class DrawingResponse(BaseModel):
    """绘图响应模型."""
    success: bool = Field(..., description="是否成功")
    image_urls: List[str] = Field(..., description="生成的图片 URL 列表")
    message: Optional[str] = Field(default=None, description="附加消息")


class DrawingError(BaseModel):
    """绘图错误响应模型."""
    success: bool = Field(default=False, description="是否成功")
    error: str = Field(..., description="错误信息")
    code: Optional[str] = Field(default=None, description="错误代码")

