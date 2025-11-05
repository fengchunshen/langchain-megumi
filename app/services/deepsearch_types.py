from typing import List, Dict
from pydantic import BaseModel, Field
from pydantic import field_validator, FieldValidationInfo


class ResearchPlan(BaseModel):
    """为研究主题制定的结构化研究方案。"""
    researchTopic: str = Field(description="重述或优化的核心研究主题", alias="research_topic")
    subTopics: List[str] = Field(description="关键子主题列表 (3-5个)", alias="sub_topics")
    researchQuestions: List[str] = Field(description="每个子主题对应的具体研究问题列表 (每个子主题2-3个问题，用「子主题：问题」格式)", alias="research_questions")
    rationale: str = Field(description="制定此研究方案的理由")
    
    @field_validator('rationale')
    @classmethod
    def validate_rationale(cls, v, info: FieldValidationInfo):
        # 如果没有 rationale 字段，可以从其他字段生成一个默认值
        if not v and 'researchTopic' in info.data:
            research_topic = info.data.get('researchTopic', '')
            return f"基于研究主题'{research_topic}'制定的系统化研究方案，旨在全面分析该主题的关键要素。"
        return v
    
    model_config = {
        "populate_by_name": True,  # 允许使用字段名或别名
        "json_schema_extra": {
            "examples": [{
                "researchTopic": "人工智能在医疗诊断中的应用现状",
                "subTopics": ["AI诊断技术现状", "临床应用案例", "技术挑战分析"],
                "researchQuestions": [
                    "AI诊断技术现状：当前主流的AI诊断技术有哪些？",
                    "临床应用案例：AI在哪些医疗场景中已得到应用？",
                    "技术挑战分析：AI医疗诊断面临哪些技术挑战？"
                ],
                "rationale": "基于用户查询自动生成的研究框架，旨在全面分析该主题的关键要素。"
            }]
        }
    }


class SearchQueryList(BaseModel):
    query: List[str] = Field(description="A list of search queries to be used for web research.", alias="query")
    rationale: str = Field(description="A brief explanation of why these queries are relevant to the research topic.", alias="rationale")
    
    model_config = {
        "populate_by_name": True,  # 允许使用字段名或别名
    }


class Reflection(BaseModel):
    is_sufficient: bool = Field(description="Whether the provided summaries are sufficient to answer the user's question.", alias="is_sufficient")
    knowledge_gap: str = Field(description="A description of what information is missing or needs clarification.", alias="knowledge_gap")
    follow_up_queries: List[str] = Field(description="A list of follow-up queries to address the knowledge gap.", alias="follow_up_queries")
    
    model_config = {
        "populate_by_name": True,  # 允许使用字段名或别名
    }


class ContentQualityAssessment(BaseModel):
    """内容质量和可靠性评估。"""
    quality_score: float = Field(
        description="整体质量评分，范围 0.0 到 1.0", ge=0.0, le=1.0, alias="quality_score"
    )
    reliability_assessment: str = Field(
        description="来源可靠性和可信度评估", alias="reliability_assessment"
    )
    content_gaps: List[str] = Field(
        description="内容中识别出的空白或缺失信息", alias="content_gaps"
    )
    improvement_suggestions: List[str] = Field(
        description="改进内容质量的建议", alias="improvement_suggestions"
    )
    
    model_config = {
        "populate_by_name": True,  # 允许使用字段名或别名
    }


class FactVerification(BaseModel):
    """事实验证结果。"""
    verified_facts_text: List[str] = Field(
        description="已验证的事实列表（文本描述）", alias="verified_facts_text"
    )
    verified_facts_sources: List[str] = Field(
        description="已验证事实对应的来源列表（与verified_facts_text顺序一一对应）", alias="verified_facts_sources"
    )
    disputed_claims_text: List[str] = Field(
        description="有争议的声明列表（文本描述）", alias="disputed_claims_text"
    )
    disputed_claims_reasons: List[str] = Field(
        description="争议原因列表（与disputed_claims_text顺序一一对应）", alias="disputed_claims_reasons"
    )
    verification_sources: List[str] = Field(
        description="用于事实验证的来源", alias="verification_sources"
    )
    confidence_score: float = Field(
        description="事实验证的整体置信度", ge=0.0, le=1.0, alias="confidence_score"
    )
    
    model_config = {
        "populate_by_name": True,  # 允许使用字段名或别名
    }


class RelevanceAssessment(BaseModel):
    """内容与研究主题的相关性评估。"""
    relevance_score: float = Field(
        description="相关性评分，范围 0.0 到 1.0", ge=0.0, le=1.0, alias="relevance_score"
    )
    key_topics_covered: List[str] = Field(
        description="内容中充分覆盖的关键主题", alias="key_topics_covered"
    )
    missing_topics: List[str] = Field(
        description="缺失或覆盖不足的重要主题", alias="missing_topics"
    )
    content_alignment: str = Field(
        description="内容与研究目标的对齐情况评估", alias="content_alignment"
    )
    
    model_config = {
        "populate_by_name": True,  # 允许使用字段名或别名
    }


class SummaryOptimization(BaseModel):
    """结构化的关键洞察和建议。"""
    key_insights: List[str] = Field(
        description="从研究中提取的关键洞察 (5-10个)", alias="key_insights"
    )
    actionable_items: List[str] = Field(
        description="基于研究发现的可行项目或建议 (3-5个)", alias="actionable_items"
    )
    confidence_level: str = Field(
        description="研究的整体置信度等级（高/中/低）", alias="confidence_level"
    )
    
    model_config = {
        "populate_by_name": True,  # 允许使用字段名或别名
    }


