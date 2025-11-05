"""DeepSearch 研究流程的 Pydantic 数据模型。"""
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ReportFormat(str, Enum):
    """报告格式枚举。"""
    FORMAL = "formal"      # 正式公文格式
    CASUAL = "casual"      # 普通格式


class DeepSearchEventType(str, Enum):
    """DeepSearch 事件类型。"""
    STARTED = "started"                          # 流程启动
    RESEARCH_PLAN = "research_plan"              # 研究计划生成
    QUERY_GENERATED = "query_generated"          # 搜索查询生成
    WEB_SEARCHING = "web_searching"              # 网络搜索执行中
    WEB_RESULT = "web_result"                    # 网络搜索结果
    REFLECTION = "reflection"                    # 反思评估
    QUALITY_ASSESSMENT = "quality_assessment"    # 质量评估
    FACT_VERIFICATION = "fact_verification"      # 事实验证
    RELEVANCE_ASSESSMENT = "relevance_assessment" # 相关性评估
    OPTIMIZATION = "optimization"                # 总结优化
    PROGRESS = "progress"                        # 进度更新
    REPORT_GENERATED = "report_generated"        # 报告生成完成
    COMPLETED = "completed"                      # 流程完成
    ERROR = "error"                              # 错误事件


class DeepSearchEvent(BaseModel):
    """DeepSearch 流式事件统一结构。"""
    event_type: DeepSearchEventType = Field(..., description="事件类型")
    timestamp: str = Field(..., description="时间戳（ISO 8601格式）")
    sequence_number: int = Field(..., description="事件序号")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件数据载荷")
    message: Optional[str] = Field(default=None, description="描述性消息")


class ProgressEvent(BaseModel):
    """进度事件数据。"""
    current_step: str = Field(..., description="当前步骤描述")
    total_steps: int = Field(..., description="总步骤数")
    completed_steps: int = Field(..., description="已完成步骤数")
    percentage: float = Field(..., description="完成百分比", ge=0.0, le=100.0)


class ResearchPlanEventData(BaseModel):
    """研究计划事件数据。"""
    research_topic: str = Field(..., description="研究主题")
    sub_topics: List[str] = Field(default_factory=list, description="子主题列表")
    research_questions: List[str] = Field(default_factory=list, description="研究问题列表")
    rationale: str = Field(default="", description="方案理由")


class QueryGeneratedEventData(BaseModel):
    """查询生成事件数据。"""
    queries: List[str] = Field(default_factory=list, description="生成的查询列表")
    count: int = Field(..., description="查询数量")
    rationale: str = Field(default="", description="生成理由")


class ReflectionEventData(BaseModel):
    """反思事件数据。"""
    loop_count: int = Field(..., description="当前循环次数")
    is_sufficient: bool = Field(..., description="信息是否充足")
    knowledge_gap: Optional[str] = Field(default=None, description="知识差距描述")
    follow_up_queries: List[str] = Field(default_factory=list, description="后续查询列表")


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
    report_format: ReportFormat = Field(
        default=ReportFormat.FORMAL, description="报告格式"
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
    markdown_report: str = Field(..., description="Markdown格式的完整报告")
    sources: List[DeepSource] = Field(default_factory=list, description="被使用的数据源列表（被引用的）")
    all_sources: List[DeepSource] = Field(default_factory=list, description="所有搜索到的网络资源列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据，如循环次数等")
    message: Optional[str] = Field(default=None, description="附加消息")


