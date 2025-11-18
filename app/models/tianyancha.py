"""天眼查相关数据模型."""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class CompanySearchRequest(BaseModel):
    """企业搜索请求模型."""
    company_name: str = Field(..., description="企业名称", min_length=1, max_length=255)
    page_size: Optional[int] = Field(default=20, description="每页条数", ge=1, le=20)
    page_num: Optional[int] = Field(default=1, description="当前页数", ge=1)


class CompanySearchResponse(BaseModel):
    """企业搜索响应模型."""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    total: Optional[int] = Field(default=None, description="总记录数")
    count: Optional[int] = Field(default=None, description="当前页结果数")
    companies: Optional[List[dict]] = Field(default_factory=list, description="企业信息列表")


class CompanyBatchQueryResponse(BaseModel):
    """企业批量查询响应模型."""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    total_count: int = Field(..., description="总查询数量")
    success_count: int = Field(..., description="成功查询数量")
    failed_count: int = Field(..., description="失败查询数量")
    file_path: str = Field(..., description="保存的文件路径（相对于项目根目录）")
    file_name: str = Field(..., description="文件名")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="时间戳")

