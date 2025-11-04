"""DeepSearch 研究流程的 Pydantic 数据模型。"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DeepSearchRequest(BaseModel):
    """DeepSearch 请求模型。"""
    query: str = Field(..., description="研究主题/问题", min_length=1, max_length=8000)
    initial_search_query_count: Optional[int] = Field(
        default=None, description="初始搜索 Query 数量（不传则用默认配置）", ge=1, le=10
    )
    max_research_loops: Optional[int] = Field(
        default=None, description="最大研究循环次数（不传则用默认配置）", ge=1, le=5
    )
    reasoning_model: Optional[str] = Field(
        default=None, description="用于反思/总结的模型覆盖（不传则用默认配置）"
    )


class DeepSource(BaseModel):
    """引用数据源信息。"""
    label: Optional[str] = Field(default=None, description="标题/标签")
    short_url: Optional[str] = Field(default=None, description="短链（正文中用于引用）")
    value: Optional[str] = Field(default=None, description="原始 URL")


class DeepSearchResponse(BaseModel):
    """DeepSearch 响应模型。"""
    success: bool = Field(..., description="是否成功")
    answer: str = Field(..., description="最终带引用的研究结论")
    sources: List[DeepSource] = Field(default_factory=list, description="被使用的数据源列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据，如循环次数等")
    message: Optional[str] = Field(default=None, description="附加消息")


