from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from langgraph.graph import add_messages
from typing_extensions import Annotated


import operator


class OverallState(TypedDict):
    messages: Annotated[list, add_messages]
    search_query: Annotated[list, operator.add]
    web_research_result: Annotated[list, operator.add]
    sources_gathered: Annotated[list, operator.add]
    initial_search_query_count: int
    max_research_loops: int
    research_loop_count: int
    reasoning_model: str
    # 人在闭环相关状态
    generated_queries: list  # 生成的原始查询
    user_confirmed_queries: list  # 用户确认/修改后的查询
    awaiting_user_confirmation: bool  # 是否等待用户确认
    user_confirmation_received: bool  # 是否已收到用户确认
    # 新增的状态字段
    content_quality: ContentQualityState
    fact_verification: FactVerificationState
    translation: TranslationState
    relevance_assessment: RelevanceState
    summary_optimization: SummaryOptimizationState
    quality_enhanced_summary: str
    verification_report: str
    final_confidence_score: float


class ReflectionState(TypedDict):
    is_sufficient: bool
    knowledge_gap: str
    follow_up_queries: Annotated[list, operator.add]
    research_loop_count: int
    number_of_ran_queries: int


class Query(TypedDict):
    query: str
    rationale: str


class QueryGenerationState(TypedDict):
    search_query: list[Query]


class WebSearchState(TypedDict):
    search_query: str
    id: str


class ContentQualityState(TypedDict):
    quality_score: float
    reliability_assessment: str
    content_gaps: list[str]
    improvement_suggestions: list[str]


class FactVerificationState(TypedDict):
    verified_facts: list[dict]
    disputed_claims: list[dict]
    verification_sources: list[str]
    confidence_score: float


class TranslationState(TypedDict):
    original_language: str
    target_language: str
    translated_content: str
    translation_quality: str


class RelevanceState(TypedDict):
    relevance_score: float
    key_topics_covered: list[str]
    missing_topics: list[str]
    content_alignment: str


class SummaryOptimizationState(TypedDict):
    optimized_summary: str
    key_insights: list[str]
    actionable_items: list[str]
    confidence_level: str


@dataclass(kw_only=True)
class SearchStateOutput:
    running_summary: str = field(default="")  # Final report
