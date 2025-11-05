from typing import List, Dict
from pydantic import BaseModel, Field


class ResearchPlan(BaseModel):
    """为研究主题制定的结构化研究方案。"""
    research_topic: str = Field(description="重述或优化的核心研究主题")
    sub_topics: List[str] = Field(description="关键子主题列表 (3-5个)")
    research_questions: List[str] = Field(description="每个子主题对应的具体研究问题列表 (每个子主题2-3个问题，用「子主题：问题」格式)")
    rationale: str = Field(description="制定此研究方案的理由")


class SearchQueryList(BaseModel):
    query: List[str] = Field(description="A list of search queries to be used for web research.")
    rationale: str = Field(description="A brief explanation of why these queries are relevant to the research topic.")


class Reflection(BaseModel):
    is_sufficient: bool = Field(description="Whether the provided summaries are sufficient to answer the user's question.")
    knowledge_gap: str = Field(description="A description of what information is missing or needs clarification.")
    follow_up_queries: List[str] = Field(description="A list of follow-up queries to address the knowledge gap.")


class ContentQualityAssessment(BaseModel):
    """内容质量和可靠性评估。"""
    quality_score: float = Field(
        description="整体质量评分，范围 0.0 到 1.0", ge=0.0, le=1.0
    )
    reliability_assessment: str = Field(
        description="来源可靠性和可信度评估"
    )
    content_gaps: List[str] = Field(
        description="内容中识别出的空白或缺失信息"
    )
    improvement_suggestions: List[str] = Field(
        description="改进内容质量的建议"
    )


class FactVerification(BaseModel):
    """事实验证结果。"""
    verified_facts_text: List[str] = Field(
        description="已验证的事实列表（文本描述）"
    )
    verified_facts_sources: List[str] = Field(
        description="已验证事实对应的来源列表（与verified_facts_text顺序一一对应）"
    )
    disputed_claims_text: List[str] = Field(
        description="有争议的声明列表（文本描述）"
    )
    disputed_claims_reasons: List[str] = Field(
        description="争议原因列表（与disputed_claims_text顺序一一对应）"
    )
    verification_sources: List[str] = Field(
        description="用于事实验证的来源"
    )
    confidence_score: float = Field(
        description="事实验证的整体置信度", ge=0.0, le=1.0
    )


class RelevanceAssessment(BaseModel):
    """内容与研究主题的相关性评估。"""
    relevance_score: float = Field(
        description="相关性评分，范围 0.0 到 1.0", ge=0.0, le=1.0
    )
    key_topics_covered: List[str] = Field(
        description="内容中充分覆盖的关键主题"
    )
    missing_topics: List[str] = Field(
        description="缺失或覆盖不足的重要主题"
    )
    content_alignment: str = Field(
        description="内容与研究目标的对齐情况评估"
    )


class SummaryOptimization(BaseModel):
    """结构化的关键洞察和建议。"""
    key_insights: List[str] = Field(
        description="从研究中提取的关键洞察 (5-10个)"
    )
    actionable_items: List[str] = Field(
        description="基于研究发现的可行项目或建议 (3-5个)"
    )
    confidence_level: str = Field(
        description="研究的整体置信度等级（高/中/低）"
    )


