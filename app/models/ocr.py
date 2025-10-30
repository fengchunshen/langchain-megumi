"""OCR 相关的 Pydantic 数据模型."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class OCRLanguage(str, Enum):
    """OCR 支持的语言."""
    CHINESE = "ch"
    ENGLISH = "en"
    AUTO = "auto"


class OCRRequest(BaseModel):
    """OCR 请求模型."""
    image_url: Optional[str] = Field(default=None, description="图片 URL")
    image_base64: Optional[str] = Field(default=None, description="图片 Base64 编码")
    language: Optional[OCRLanguage] = Field(default=OCRLanguage.AUTO, description="识别语言")


class OCRTextBlock(BaseModel):
    """OCR 文本块."""
    text: str = Field(..., description="识别的文本")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    bbox: Optional[Dict[str, float]] = Field(default=None, description="边界框坐标")


class OCRResponse(BaseModel):
    """OCR 响应模型."""
    success: bool = Field(..., description="是否成功")
    text: str = Field(..., description="识别的完整文本")
    text_blocks: Optional[List[OCRTextBlock]] = Field(default=None, description="文本块列表")
    language: Optional[str] = Field(default=None, description="识别的语言")
    message: Optional[str] = Field(default=None, description="附加消息")


class OCRError(BaseModel):
    """OCR 错误响应模型."""
    success: bool = Field(default=False, description="是否成功")
    error: str = Field(..., description="错误信息")
    code: Optional[str] = Field(default=None, description="错误代码")

