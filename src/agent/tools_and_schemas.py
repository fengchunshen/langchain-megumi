from pydantic import BaseModel, Field
from typing import List, Dict


class SearchQueryList(BaseModel):
    """A list of search queries with rationale."""

    rationale: str = Field(
        description="The rationale for why these queries are relevant."
    )
    query: List[str] = Field(description="A list of search queries.")


class Reflection(BaseModel):
    """Reflection on the research results."""

    is_sufficient: bool = Field(
        description="Whether the research is sufficient to answer the question."
    )
    knowledge_gap: str = Field(
        description="The knowledge gap that needs to be filled."
    )
    follow_up_queries: List[str] = Field(
        description="Follow-up queries to fill the knowledge gap."
    )


class ContentQualityAssessment(BaseModel):
    """Assessment of content quality and reliability."""

    quality_score: float = Field(
        description="Overall quality score from 0.0 to 1.0", ge=0.0, le=1.0
    )
    reliability_assessment: str = Field(
        description="Assessment of source reliability and credibility"
    )
    content_gaps: List[str] = Field(
        description="Identified gaps or missing information in the content"
    )
    improvement_suggestions: List[str] = Field(
        description="Suggestions for improving content quality"
    )


class FactVerification(BaseModel):
    """Fact verification results."""

    verified_facts: List[Dict[str, str]] = Field(
        description="List of verified facts with sources"
    )
    disputed_claims: List[Dict[str, str]] = Field(
        description="List of disputed or unverified claims"
    )
    verification_sources: List[str] = Field(
        description="Sources used for fact verification"
    )
    confidence_score: float = Field(
        description="Overall confidence in fact verification", ge=0.0, le=1.0
    )


class RelevanceAssessment(BaseModel):
    """Assessment of content relevance to the research topic."""

    relevance_score: float = Field(
        description="Relevance score from 0.0 to 1.0", ge=0.0, le=1.0
    )
    key_topics_covered: List[str] = Field(
        description="Key topics that are well covered in the content"
    )
    missing_topics: List[str] = Field(
        description="Important topics that are missing or under-covered"
    )
    content_alignment: str = Field(
        description="Assessment of how well content aligns with research goals"
    )


class SummaryOptimization(BaseModel):
    """Optimized summary with enhanced insights."""

    optimized_summary: str = Field(
        description="Enhanced and optimized summary of research findings"
    )
    key_insights: List[str] = Field(
        description="Key insights extracted from the research"
    )
    actionable_items: List[str] = Field(
        description="Actionable items or recommendations based on findings"
    )
    confidence_level: str = Field(
        description="Confidence level in the summary and insights"
    )


class UserQueryConfirmation(BaseModel):
    """User confirmation for generated search queries."""

    confirmed: bool = Field(
        description="Whether the user confirmed the queries"
    )
    modified_queries: List[str] = Field(
        description="Modified queries if the user changed them"
    )
    action: str = Field(
        description="User action: 'confirm', 'modify', or 'cancel'"
    )
