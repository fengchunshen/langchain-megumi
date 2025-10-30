"""AI分析相关的 Pydantic 数据模型."""
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime


class NodeAnalysisRequest(BaseModel):
    """节点分析请求模型."""
    nodeName: str = Field(..., description="节点名称")
    parentProfile: Optional[Dict[str, Any]] = Field(None, description="父节点信息")
    siblingsProfiles: Optional[List[Dict[str, Any]]] = Field(None, description="兄弟节点信息列表")


class AnalysisResponse(BaseModel):
    """分析响应模型."""
    success: bool = Field(..., description="是否成功")
    data: Optional[Dict[str, Any]] = Field(None, description="分析结果数据")
    error: Optional[str] = Field(None, description="错误信息")
    timestamp: str = Field(..., description="时间戳")


class SolutionAnalysisRequest(BaseModel):
    """解决方案分析请求模型."""
    solutionName: str = Field(..., description="解决方案名称")
    description: str = Field(..., description="解决方案描述")


class SolutionAnalysisResponse(BaseModel):
    """解决方案分析响应模型."""
    success: bool = Field(..., description="是否成功")
    tags: List[str] = Field(..., description="生成的标签列表")
    message: str = Field(..., description="响应消息")


class CompanyTagAnalysisRequest(BaseModel):
    """企业标签分析请求模型."""
    companyName: str = Field(..., description="企业名称")
    businessScope: str = Field(..., description="企业经营范围")


class CompanyTagAnalysisResponse(BaseModel):
    """企业标签分析响应模型."""
    success: bool = Field(..., description="是否成功")
    tags: List[str] = Field(..., description="分析出的标签列表")
    message: str = Field(..., description="响应消息")
    timestamp: str = Field(..., description="时间戳")

