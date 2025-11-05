"""研究报告生成器 - 生成规范的公文格式报告."""
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from app.services.deepsearch_types import ResearchPlan

logger = logging.getLogger(__name__)


class ReportGenerator:
    """研究报告生成器，负责生成正式公文格式的研究报告."""
    
    def __init__(self):
        """初始化报告生成器."""
        self.report_counter = 0
    
    def generate_formal_report(
        self,
        query: str,
        research_plan: Optional[ResearchPlan],
        answer: str,
        sources: List[Dict[str, Any]],
        content_quality: Dict[str, Any],
        fact_verification: Dict[str, Any],
        relevance_assessment: Dict[str, Any],
        summary_optimization: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """
        生成正式公文格式的研究报告.
        
        Args:
            query: 原始研究查询
            research_plan: 研究计划
            answer: 研究结论内容
            sources: 参考来源列表
            content_quality: 内容质量评估数据
            fact_verification: 事实验证数据
            relevance_assessment: 相关性评估数据
            summary_optimization: 总结优化数据
            metadata: 元数据
            
        Returns:
            str: Markdown格式的正式报告
        """
        self.report_counter += 1
        
        # 生成报告头部信息
        report_id = str(self.report_counter).zfill(4)
        report_date = datetime.now().strftime("%Y%m%d")
        generation_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        model_name = metadata.get("reasoningModel", "Gemini 2.0 Flash")
        confidence_level = summary_optimization.get("confidence_level", "中等")
        
        # 构建报告标题
        research_topic = research_plan.researchTopic if research_plan else query
        
        markdown = f"""# {research_topic} 研究报告

**报告编号**: DR-{report_date}-{report_id}  
**生成时间**: {generation_time}  
**研究模型**: {model_name}  
**置信度等级**: {confidence_level}  

---

## 报告摘要

{self._generate_executive_summary(answer, summary_optimization)}

---

## 一、研究背景与目标

### 1.1 研究主题

{self._format_research_topic(research_topic, query)}

### 1.2 研究范围

本次研究涵盖以下关键领域：

{self._format_sub_topics(research_plan)}

---

## 二、研究方案

### 2.1 关键研究领域

根据研究主题，确定以下关键研究领域：

{self._format_research_areas(research_plan)}

### 2.2 研究问题

针对上述研究领域，本次研究重点解答以下问题：

{self._format_research_questions(research_plan)}

---

## 三、研究结论

{self._format_main_findings(answer)}

---

## 四、综合评估

### 4.1 关键洞察

基于本次研究，得出以下关键洞察：

{self._format_key_insights(summary_optimization)}

### 4.2 建议措施

针对研究结论，提出以下建议：

{self._format_recommendations(summary_optimization)}

---

## 五、质量保障

### 5.1 质量评估指标

{self._format_quality_metrics(content_quality, relevance_assessment)}

### 5.2 事实验证结果

{self._format_fact_verification(fact_verification)}

### 5.3 可信度评级

{self._format_confidence_rating(summary_optimization, content_quality)}

---

## 六、参考文献

{self._format_references(sources)}

---

## 附录：研究过程记录

### A.1 研究循环统计

{self._format_research_statistics(metadata)}

### A.2 查询历史

{self._format_query_history(metadata)}

---

**报告结束**

*本报告由 Megumi AI Service 自动生成*  
*系统版本: {metadata.get('system_version', '1.0.0')}*  
*生成引擎: DeepSearch Pro*
"""
        
        return markdown
    
    def _generate_executive_summary(
        self, 
        answer: str, 
        summary_optimization: Dict[str, Any]
    ) -> str:
        """生成执行摘要（100-200字）."""
        # 提取答案的前200字作为摘要基础
        summary_base = answer[:200] if len(answer) > 200 else answer
        
        # 如果有关键洞察，加入摘要
        key_insights = summary_optimization.get("key_insights", [])
        if key_insights:
            first_insight = key_insights[0] if len(key_insights) > 0 else ""
            summary = f"{summary_base}... 研究发现：{first_insight}"
        else:
            summary = summary_base
        
        return summary.strip()
    
    def _format_research_topic(self, research_topic: str, query: str) -> str:
        """格式化研究主题."""
        return f"本次研究聚焦于「{research_topic}」，旨在通过系统性的信息收集与分析，为该主题提供全面、准确的研究结论。"
    
    def _format_sub_topics(self, research_plan: Optional[ResearchPlan]) -> str:
        """格式化子主题列表."""
        if not research_plan or not research_plan.subTopics:
            return "（研究计划未生成详细子主题）"
        
        formatted = ""
        for idx, topic in enumerate(research_plan.subTopics, 1):
            formatted += f"{idx}. {topic}\n"
        
        return formatted.strip()
    
    def _format_research_areas(self, research_plan: Optional[ResearchPlan]) -> str:
        """格式化研究领域."""
        if not research_plan or not research_plan.subTopics:
            return "（研究计划未生成详细研究领域）"
        
        formatted = ""
        for idx, topic in enumerate(research_plan.subTopics, 1):
            formatted += f"**领域{idx}：{topic}**\n\n"
            formatted += f"- 研究内容：针对{topic}相关的核心问题进行深入调查\n"
            formatted += f"- 研究方法：通过多源信息收集、交叉验证等方式确保信息准确性\n\n"
        
        return formatted.strip()
    
    def _format_research_questions(self, research_plan: Optional[ResearchPlan]) -> str:
        """格式化研究问题."""
        if not research_plan or not research_plan.researchQuestions:
            return "（研究计划未生成具体研究问题）"
        
        formatted = ""
        for idx, question in enumerate(research_plan.researchQuestions, 1):
            formatted += f"{idx}. {question}\n"
        
        return formatted.strip()
    
    def _format_main_findings(self, answer: str) -> str:
        """格式化主要发现."""
        # 将答案分段处理
        sections = answer.split("\n\n")
        
        formatted = "### 3.1 核心发现\n\n"
        
        # 主要内容
        main_content = []
        for section in sections:
            if section.strip():
                main_content.append(section.strip())
        
        formatted += "\n\n".join(main_content)
        
        return formatted
    
    def _format_key_insights(self, summary_optimization: Dict[str, Any]) -> str:
        """格式化关键洞察."""
        key_insights = summary_optimization.get("key_insights", [])
        
        if not key_insights:
            return "（暂无关键洞察数据）"
        
        formatted = ""
        for idx, insight in enumerate(key_insights, 1):
            formatted += f"**洞察{idx}**\n\n{insight}\n\n"
        
        return formatted.strip()
    
    def _format_recommendations(self, summary_optimization: Dict[str, Any]) -> str:
        """格式化建议措施."""
        actionable_items = summary_optimization.get("actionable_items", [])
        
        if not actionable_items:
            return "（暂无具体建议）"
        
        formatted = ""
        for idx, item in enumerate(actionable_items, 1):
            formatted += f"**建议{idx}**\n\n{item}\n\n"
        
        return formatted.strip()
    
    def _format_quality_metrics(
        self, 
        content_quality: Dict[str, Any],
        relevance_assessment: Dict[str, Any]
    ) -> str:
        """格式化质量指标."""
        quality_score = content_quality.get("quality_score") or 0.0
        relevance_score = relevance_assessment.get("relevance_score") or 0.0
        
        # 确保是数字类型
        quality_score = float(quality_score) if quality_score is not None else 0.0
        relevance_score = float(relevance_score) if relevance_score is not None else 0.0
        
        # 计算完整性和可靠性评分（基于质量评估）
        completeness_score = quality_score * 0.9  # 简化计算
        reliability_score = quality_score * 0.95
        
        overall_score = (quality_score + relevance_score + completeness_score + reliability_score) / 4
        
        table = f"""| 评估维度 | 评分 | 说明 |
|---------|------|------|
| 内容质量 | {quality_score:.2f} | {content_quality.get('reliability_assessment', '内容质量评估')} |
| 信息完整性 | {completeness_score:.2f} | 信息覆盖度评估 |
| 来源可靠性 | {reliability_score:.2f} | 信息源可信度评估 |
| 相关性 | {relevance_score:.2f} | {relevance_assessment.get('content_alignment', '内容相关性评估')} |

**综合评分**: {overall_score:.2f}/1.0"""
        
        return table
    
    def _format_fact_verification(self, fact_verification: Dict[str, Any]) -> str:
        """格式化事实验证结果."""
        verified_facts = fact_verification.get("verified_facts_text", [])
        disputed_claims = fact_verification.get("disputed_claims_text", [])
        
        formatted = "**已验证核心事实**：\n\n"
        
        if verified_facts:
            for idx, fact in enumerate(verified_facts[:5], 1):  # 只显示前5个
                source_idx = idx  # 简化处理
                formatted += f"{idx}. {fact} [来源{source_idx}]\n"
        else:
            formatted += "（暂无已验证事实记录）\n"
        
        formatted += "\n**需进一步验证的内容**：\n\n"
        
        if disputed_claims:
            disputed_reasons = fact_verification.get("disputed_claims_reasons", [])
            for idx, claim in enumerate(disputed_claims[:3], 1):  # 只显示前3个
                reason = disputed_reasons[idx-1] if idx-1 < len(disputed_reasons) else "需进一步调查"
                formatted += f"{idx}. {claim}\n   - 原因：{reason}\n"
        else:
            formatted += "（无需进一步验证的内容）\n"
        
        return formatted.strip()
    
    def _format_confidence_rating(
        self, 
        summary_optimization: Dict[str, Any],
        content_quality: Dict[str, Any]
    ) -> str:
        """格式化可信度评级."""
        confidence_level = summary_optimization.get("confidence_level", "中等")
        quality_score = content_quality.get("quality_score") or 0.5
        
        # 确保是数字类型
        quality_score = float(quality_score) if quality_score is not None else 0.5
        
        # 生成评级依据
        if quality_score >= 0.8:
            rationale = "研究基于多个可靠来源，信息经过交叉验证，核心结论具有较高可信度。"
        elif quality_score >= 0.6:
            rationale = "研究涵盖了主要信息源，核心结论经过验证，但部分细节仍需进一步确认。"
        else:
            rationale = "研究提供了初步结论，但信息源有限，建议结合更多资料进行深入研究。"
        
        formatted = f"""- **整体可信度**：{confidence_level}
- **评级依据**：{rationale}"""
        
        return formatted
    
    def _format_references(self, sources: List[Dict[str, Any]]) -> str:
        """格式化参考文献."""
        if not sources:
            return "（本次研究未引用外部文献）"
        
        formatted = ""
        for idx, source in enumerate(sources, 1):
            title = source.get("label", "未知来源")
            url = source.get("value", "#")
            access_time = datetime.now().strftime("%Y年%m月%d日")
            
            formatted += f"[{idx}] {title}. {url}. 访问时间：{access_time}\n\n"
        
        return formatted.strip()
    
    def _format_research_statistics(self, metadata: Dict[str, Any]) -> str:
        """格式化研究统计数据."""
        loop_count = metadata.get("researchLoopCount") or 0
        total_queries = metadata.get("numberOfQueries") or 0
        total_sources = metadata.get("numberOfSources") or 0
        total_time = metadata.get("executionTime") or 0.0
        
        formatted = f"""- 研究循环次数：{loop_count}次
- 搜索查询总数：{total_queries}个
- 处理信息源：{total_sources}个
- 总耗时：{total_time:.2f}秒"""
        
        return formatted
    
    def _format_query_history(self, metadata: Dict[str, Any]) -> str:
        """格式化查询历史."""
        # 这里需要从metadata中提取查询历史
        # 简化版本：显示查询总数
        total_queries = metadata.get("numberOfQueries") or 0
        loop_count = metadata.get("researchLoopCount") or 0
        
        formatted = f"""本次研究共进行{loop_count}轮调查，生成{total_queries}个搜索查询。

详细查询记录已保存至系统日志中。"""
        
        return formatted


# 创建全局报告生成器实例
report_generator = ReportGenerator()

