import os

from agent.tools_and_schemas import (
    SearchQueryList, 
    Reflection, 
    ContentQualityAssessment,
    FactVerification,
    RelevanceAssessment,
    SummaryOptimization,
    UserQueryConfirmation
)
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_core.runnables import RunnableConfig
from langchain_tavily import TavilySearch

from agent.state import (
    OverallState,
    QueryGenerationState,
    ReflectionState,
    WebSearchState,
)
from agent.configuration import Configuration
from agent.prompts import (
    get_current_date,
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
    content_quality_instructions,
    fact_verification_instructions,
    relevance_assessment_instructions,
    summary_optimization_instructions,
)
from langchain_deepseek import ChatDeepSeek
from agent.utils import (
    get_research_topic,
)

load_dotenv(override=True)

if os.getenv("DEEPSEEK_API_KEY") is None:
    raise ValueError("DEEPSEEK_API_KEY is not set")

if os.getenv("TAVILY_API_KEY") is None:
    raise ValueError("TAVILY_API_KEY is not set")

# Initialize Tavily Search
tavily_search = TavilySearch(
    max_results=5,
    search_depth="advanced",
    api_key=os.getenv("TAVILY_API_KEY")
)


# Nodes
async def generate_query(state: OverallState, config: RunnableConfig) -> OverallState:
    """LangGraph node that generates search queries based on the User's question.

    Uses DeepSeek to create optimized search queries for web research based on
    the User's question.

    Args:
        state: Current graph state containing the User's question
        config: Configuration for the runnable, including LLM provider settings

    Returns:
        Dictionary with state update, including search_query key containing the generated queries
    """
    configurable = Configuration.from_runnable_config(config)
    
    # 检查是否是用户确认消息
    last_message = state["messages"][-1] if state["messages"] else None
    if last_message and last_message.content and "[查询已确认]" in last_message.content:
        # 从确认消息中提取查询
        content = last_message.content
        queries_part = content.split("[查询已确认]")[1].strip()
        confirmed_queries = [q.strip() for q in queries_part.split("|")]
        return {
            "search_query": confirmed_queries,
            "generated_queries": confirmed_queries,
            "awaiting_user_confirmation": False,
            "user_confirmation_received": True
        }

    # check for custom initial search query count
    if state.get("initial_search_query_count") is None:
        state["initial_search_query_count"] = configurable.number_of_initial_queries

    # init DeepSeek
    llm = ChatDeepSeek(
        model=configurable.query_generator_model,
        temperature=1.0,
        max_retries=2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )
    structured_llm = llm.with_structured_output(SearchQueryList)

    # Format the prompt
    current_date = get_current_date()
    formatted_prompt = query_writer_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        number_queries=state["initial_search_query_count"],
    )
    # Generate the search queries
    result = await structured_llm.ainvoke(formatted_prompt)
    return {
        "search_query": result.query,
        "generated_queries": result.query,
        "awaiting_user_confirmation": True,
        "user_confirmation_received": False
    }


async def wait_for_user_confirmation(state: OverallState, config: RunnableConfig):
    """LangGraph node that waits for user confirmation of generated queries.
    
    This node simply outputs the generated queries and waits.
    The workflow will be paused here until user provides confirmation.
    """
    from langchain_core.messages import AIMessage
    
    # 生成一个包含查询的消息给用户确认
    queries = state.get("generated_queries", state.get("search_query", []))
    confirmation_message = f"我为您生成了以下搜索查询：\n\n" + "\n".join([f"{i+1}. {q}" for i, q in enumerate(queries)]) + "\n\n请确认是否继续使用这些查询进行搜索，或者您可以修改它们。"
    
    return {
        "messages": [AIMessage(content=confirmation_message)],
        "awaiting_user_confirmation": True
    }


def should_wait_for_confirmation(state: OverallState):
    """路由函数：决定是否需要等待用户确认"""
    # 如果已经收到用户确认，直接进行网络搜索
    if state.get("user_confirmation_received", False):
        return "web_research"
    # 如果需要等待用户确认
    elif state.get("awaiting_user_confirmation", False):
        return "wait_for_user_confirmation"
    else:
        return "web_research"


def continue_to_web_research(state: OverallState):
    """LangGraph node that sends the search queries to the web research node.

    This is used to spawn n number of web research nodes, one for each search query.
    """
    # 使用确认后的查询或原始查询
    queries_to_use = state.get("user_confirmed_queries") or state.get("search_query", [])
    return [
        Send("web_research", {"search_query": search_query, "id": int(idx)})
        for idx, search_query in enumerate(queries_to_use)
    ]


async def web_research(state: WebSearchState, config: RunnableConfig) -> OverallState:
    """LangGraph node that performs web research using Tavily Search API.

    Executes a web search using Tavily Search API and then uses DeepSeek to analyze and summarize the results.

    Args:
        state: Current graph state containing the search query and research loop count
        config: Configuration for the runnable, including search API settings

    Returns:
        Dictionary with state update, including sources_gathered, research_loop_count, and web_research_results
    """
    # Configure
    configurable = Configuration.from_runnable_config(config)
    
    # Perform search using Tavily
    # Ensure search_query is a string, not a list
    search_query = state["search_query"]
    if isinstance(search_query, list):
        search_query = search_query[0] if search_query else ""
    search_results = await tavily_search.ainvoke(search_query)
    
    # Extract content and URLs from search results
    search_content = ""
    sources_gathered = []
    

    
    # Handle different return formats from Tavily
    if isinstance(search_results, list):
        results_to_process = search_results
    elif isinstance(search_results, dict):
        # Tavily typically returns a dict with 'results' key
        results_to_process = search_results.get('results', [])
    elif isinstance(search_results, str):
        # If it's a string, it might be JSON content
        try:
            import json
            parsed_results = json.loads(search_results)
            if isinstance(parsed_results, dict) and 'results' in parsed_results:
                results_to_process = parsed_results['results']
            else:
                results_to_process = [{"title": "Search Result", "url": "", "content": search_results}]
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"Warning: Failed to parse search results as JSON: {e}")
            results_to_process = [{"title": "Search Result", "url": "", "content": search_results}]
    else:
        results_to_process = []
    

    
    for i, result in enumerate(results_to_process):
        if isinstance(result, dict):
            title = result.get('title', f'Result {i+1}')
            url = result.get('url', f'https://search-result-{i+1}.com')
            content = result.get('content', str(result))
        else:
            title = f'Result {i+1}'
            url = f'https://search-result-{i+1}.com'
            content = str(result)
            
        search_content += f"Source {i+1}: {title}\nURL: {url}\nContent: {content}\n\n"
        sources_gathered.append({
            "title": title,
            "url": url,
            "content": content[:500] + "..." if len(content) > 500 else content,
            "short_url": f"[{i+1}]",
            "value": url,
            "label": title  # Add label field for frontend compatibility
        })
    

    
    # Format prompt for DeepSeek to analyze the search results
    formatted_prompt = web_searcher_instructions.format(
        current_date=get_current_date(),
        research_topic=search_query,
    )
    
    # Add search results to the prompt
    analysis_prompt = f"{formatted_prompt}\n\n搜索结果：\n{search_content}\n\n请分析这些搜索结果并提供带有引用的综合摘要。请用中文回答。"
    
    # Use DeepSeek to analyze and summarize the search results
    llm = ChatDeepSeek(
        model=configurable.query_generator_model,
        temperature=0,
        max_retries=2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )
    
    response = await llm.ainvoke(analysis_prompt)
    
    # Insert citation markers
    modified_text = response.content
    for i, source in enumerate(sources_gathered):
        # Replace URL references with short citations
        if source['url'] in modified_text:
            modified_text = modified_text.replace(source['url'], source['short_url'])
        # Also try to match domain names
        domain = source['url'].split('/')[2] if len(source['url'].split('/')) > 2 else source['url']
        if domain in modified_text:
            modified_text = modified_text.replace(domain, source['short_url'])

    return {
        "sources_gathered": sources_gathered,
        "search_query": [state["search_query"]],
        "web_research_result": [modified_text],
    }


async def reflection(state: OverallState, config: RunnableConfig) -> ReflectionState:
    """LangGraph node that identifies knowledge gaps and generates potential follow-up queries.

    Analyzes the current summary to identify areas for further research and generates
    potential follow-up queries. Uses structured output to extract
    the follow-up query in JSON format.

    Args:
        state: Current graph state containing the running summary and research topic
        config: Configuration for the runnable, including LLM provider settings

    Returns:
        Dictionary with state update, including search_query key containing the generated follow-up query
    """
    configurable = Configuration.from_runnable_config(config)
    # Increment the research loop count and get the reasoning model
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    reasoning_model = state.get("reasoning_model", configurable.reflection_model)

    # Format the prompt
    current_date = get_current_date()
    formatted_prompt = reflection_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n\n---\n\n".join(state["web_research_result"]),
    )
    # init Reasoning Model
    llm = ChatDeepSeek(
        model=reasoning_model,
        temperature=1.0,
        max_retries=2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )
    result = await llm.with_structured_output(Reflection).ainvoke(formatted_prompt)

    return {
        "is_sufficient": result.is_sufficient,
        "knowledge_gap": result.knowledge_gap,
        "follow_up_queries": result.follow_up_queries,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
    }


def evaluate_research(
    state: ReflectionState,
    config: RunnableConfig,
) -> OverallState:
    """LangGraph routing function that determines the next step in the research flow.

    Controls the research loop by deciding whether to continue gathering information
    or to proceed to quality enhancement based on the configured maximum number of research loops.

    Args:
        state: Current graph state containing the research loop count
        config: Configuration for the runnable, including max_research_loops setting

    Returns:
        String literal indicating the next node to visit ("web_research" or "assess_content_quality")
    """
    configurable = Configuration.from_runnable_config(config)
    max_research_loops = (
        state.get("max_research_loops")
        if state.get("max_research_loops") is not None
        else configurable.max_research_loops
    )
    if state["is_sufficient"] or state["research_loop_count"] >= max_research_loops:
        return "assess_content_quality"
    else:
        return [
            Send(
                "web_research",
                {
                    "search_query": follow_up_query,
                    "id": state["number_of_ran_queries"] + int(idx),
                },
            )
            for idx, follow_up_query in enumerate(state["follow_up_queries"])
        ]


async def assess_content_quality(state: OverallState, config: RunnableConfig):
    """LangGraph node that assesses the quality and reliability of research content.

    Evaluates the overall quality of gathered research content, assesses source
    reliability, identifies content gaps, and provides improvement suggestions.

    Args:
        state: Current graph state containing web research results
        config: Configuration for the runnable

    Returns:
        Dictionary with state update including content quality assessment
    """
    configurable = Configuration.from_runnable_config(config)
    
    # Combine all research content
    combined_content = "\n\n---\n\n".join(state["web_research_result"])
    
    # Format the prompt
    formatted_prompt = content_quality_instructions.format(
        research_topic=get_research_topic(state["messages"]),
        content=combined_content
    )
    
    # Initialize DeepSeek
    llm = ChatDeepSeek(
        model=configurable.reflection_model,
        temperature=0.3,
        max_retries=2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )
    
    result = await llm.with_structured_output(ContentQualityAssessment).ainvoke(formatted_prompt)
    
    return {
        "content_quality": {
            "quality_score": result.quality_score,
            "reliability_assessment": result.reliability_assessment,
            "content_gaps": result.content_gaps,
            "improvement_suggestions": result.improvement_suggestions
        }
    }


async def verify_facts(state: OverallState, config: RunnableConfig):
    """LangGraph node that verifies facts and claims in the research content.

    Identifies key facts and claims, verifies their accuracy, flags disputed
    information, and provides confidence scores.

    Args:
        state: Current graph state containing web research results
        config: Configuration for the runnable

    Returns:
        Dictionary with state update including fact verification results
    """
    configurable = Configuration.from_runnable_config(config)
    
    # Combine all research content
    combined_content = "\n\n---\n\n".join(state["web_research_result"])
    
    # Format the prompt
    current_date = get_current_date()
    formatted_prompt = fact_verification_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        content=combined_content
    )
    
    # Initialize DeepSeek
    llm = ChatDeepSeek(
        model=configurable.reflection_model,
        temperature=0.1,
        max_retries=2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )
    
    result = await llm.with_structured_output(FactVerification).ainvoke(formatted_prompt)
    
    return {
        "fact_verification": {
            "verified_facts": result.verified_facts,
            "disputed_claims": result.disputed_claims,
            "verification_sources": result.verification_sources,
            "confidence_score": result.confidence_score
        }
    }


async def assess_relevance(state: OverallState, config: RunnableConfig):
    """LangGraph node that assesses content relevance to the research topic.

    Evaluates how well the content aligns with the research goals, identifies
    covered and missing topics, and provides relevance scoring.

    Args:
        state: Current graph state containing web research results
        config: Configuration for the runnable

    Returns:
        Dictionary with state update including relevance assessment
    """
    configurable = Configuration.from_runnable_config(config)
    
    # Combine all research content
    combined_content = "\n\n---\n\n".join(state["web_research_result"])
    
    # Format the prompt
    formatted_prompt = relevance_assessment_instructions.format(
        research_topic=get_research_topic(state["messages"]),
        content=combined_content
    )
    
    # Initialize DeepSeek
    llm = ChatDeepSeek(
        model=configurable.reflection_model,
        temperature=0.2,
        max_retries=2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )
    
    result = await llm.with_structured_output(RelevanceAssessment).ainvoke(formatted_prompt)
    
    return {
        "relevance_assessment": {
            "relevance_score": result.relevance_score,
            "key_topics_covered": result.key_topics_covered,
            "missing_topics": result.missing_topics,
            "content_alignment": result.content_alignment
        }
    }


async def optimize_summary(state: OverallState, config: RunnableConfig):
    """LangGraph node that optimizes and enhances the research summary.

    Uses quality assessment, fact verification, and relevance analysis to
    create an optimized summary with key insights and actionable items.

    Args:
        state: Current graph state containing all assessment results
        config: Configuration for the runnable

    Returns:
        Dictionary with state update including optimized summary
    """
    configurable = Configuration.from_runnable_config(config)
    
    # Get original summary
    original_summary = "\n\n---\n\n".join(state["web_research_result"])
    
    # Format the prompt with all assessment results
    current_date = get_current_date()
    formatted_prompt = summary_optimization_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        original_summary=original_summary,
        quality_assessment=str(state.get("content_quality", {})),
        fact_verification=str(state.get("fact_verification", {})),
        relevance_assessment=str(state.get("relevance_assessment", {}))
    )
    
    # Initialize DeepSeek
    llm = ChatDeepSeek(
        model=configurable.answer_model,
        temperature=0.3,
        max_retries=2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )
    
    result = await llm.with_structured_output(SummaryOptimization).ainvoke(formatted_prompt)
    
    # Calculate final confidence score
    quality_score = state.get("content_quality", {}).get("quality_score", 0.5)
    fact_confidence = state.get("fact_verification", {}).get("confidence_score", 0.5)
    relevance_score = state.get("relevance_assessment", {}).get("relevance_score", 0.5)
    final_confidence = (quality_score + fact_confidence + relevance_score) / 3
    
    return {
        "summary_optimization": {
            "optimized_summary": result.optimized_summary,
            "key_insights": result.key_insights,
            "actionable_items": result.actionable_items,
            "confidence_level": result.confidence_level
        },
        "quality_enhanced_summary": result.optimized_summary,
        "final_confidence_score": final_confidence
    }


async def generate_verification_report(state: OverallState, config: RunnableConfig):
    """LangGraph node that generates a comprehensive verification report.

    Creates a detailed report summarizing all quality assessments, fact
    verifications, and enhancement recommendations.

    Args:
        state: Current graph state containing all assessment results
        config: Configuration for the runnable

    Returns:
        Dictionary with state update including verification report
    """
    # Generate comprehensive verification report
    quality_data = state.get("content_quality", {})
    fact_data = state.get("fact_verification", {})
    relevance_data = state.get("relevance_assessment", {})
    optimization_data = state.get("summary_optimization", {})
    
    report = f"""# 研究质量验证报告

## 内容质量评估
- 质量评分: {quality_data.get('quality_score', 'N/A')}/1.0
- 可靠性评估: {quality_data.get('reliability_assessment', 'N/A')}
- 内容空白: {', '.join(quality_data.get('content_gaps', []))}
- 改进建议: {', '.join(quality_data.get('improvement_suggestions', []))}

## 事实验证结果
- 验证置信度: {fact_data.get('confidence_score', 'N/A')}/1.0
- 已验证事实数量: {len(fact_data.get('verified_facts', []))}
- 争议声明数量: {len(fact_data.get('disputed_claims', []))}
- 验证来源: {', '.join(fact_data.get('verification_sources', []))}

## 相关性评估
- 相关性评分: {relevance_data.get('relevance_score', 'N/A')}/1.0
- 已覆盖关键主题: {', '.join(relevance_data.get('key_topics_covered', []))}
- 缺失主题: {', '.join(relevance_data.get('missing_topics', []))}
- 内容一致性: {relevance_data.get('content_alignment', 'N/A')}

## 摘要优化结果
- 置信度等级: {optimization_data.get('confidence_level', 'N/A')}
- 关键洞察数量: {len(optimization_data.get('key_insights', []))}
- 可行建议数量: {len(optimization_data.get('actionable_items', []))}

## 综合评估
- 最终置信度评分: {state.get('final_confidence_score', 'N/A'):.3f}/1.0
"""
    
    return {
        "verification_report": report
    }


async def finalize_answer(state: OverallState, config: RunnableConfig):
    """LangGraph node that finalizes the enhanced research summary.

    Creates the final output using the quality-enhanced summary, verification report,
    and properly formatted sources with citations.

    Args:
        state: Current graph state containing the enhanced summary and all assessment results

    Returns:
        Dictionary with state update, including the final enhanced message with sources
    """
    # Use the optimized summary if available, otherwise fall back to original
    final_summary = state.get("quality_enhanced_summary") or "\n---\n\n".join(state["web_research_result"])
    verification_report = state.get("verification_report", "")
    
    # Combine the enhanced summary with verification report
    enhanced_content = f"""{final_summary}

---

{verification_report}"""
    
    # Replace the short urls with the original urls and add all used urls to the sources_gathered
    unique_sources = []
    for source in state["sources_gathered"]:
        if source["short_url"] in enhanced_content:
            enhanced_content = enhanced_content.replace(
                source["short_url"], source["value"]
            )
            unique_sources.append(source)
    
    # Add quality metrics to the final message
    quality_metrics = f"\n\n## 研究质量指标\n"
    quality_metrics += f"- 最终置信度: {state.get('final_confidence_score', 0):.3f}/1.0\n"
    quality_metrics += f"- 内容质量评分: {state.get('content_quality', {}).get('quality_score', 'N/A')}/1.0\n"
    quality_metrics += f"- 事实验证置信度: {state.get('fact_verification', {}).get('confidence_score', 'N/A')}/1.0\n"
    quality_metrics += f"- 相关性评分: {state.get('relevance_assessment', {}).get('relevance_score', 'N/A')}/1.0\n"
    
    final_content = enhanced_content + quality_metrics

    return {
        "messages": [AIMessage(content=final_content)],
        "sources_gathered": unique_sources,
    }


# Create our Agent Graph
builder = StateGraph(OverallState, config_schema=Configuration)

# Define the nodes we will cycle between
builder.add_node("generate_query", generate_query)
builder.add_node("wait_for_user_confirmation", wait_for_user_confirmation)
builder.add_node("web_research", web_research)
builder.add_node("reflection", reflection)
# Add new quality enhancement nodes
builder.add_node("assess_content_quality", assess_content_quality)
builder.add_node("verify_facts", verify_facts)
builder.add_node("assess_relevance", assess_relevance)
builder.add_node("optimize_summary", optimize_summary)
builder.add_node("generate_verification_report", generate_verification_report)
builder.add_node("finalize_answer", finalize_answer)

# Set the entrypoint as `generate_query`
# This means that this node is the first one called
builder.add_edge(START, "generate_query")
# Add conditional edge to check if we need user confirmation
builder.add_conditional_edges(
    "generate_query", should_wait_for_confirmation, ["wait_for_user_confirmation", "web_research"]
)
# After user confirmation, proceed to web research
builder.add_conditional_edges(
    "wait_for_user_confirmation", continue_to_web_research, ["web_research"]
)
# Reflect on the web research
builder.add_edge("web_research", "reflection")
# Evaluate the research
builder.add_conditional_edges(
    "reflection", evaluate_research, ["web_research", "assess_content_quality"]
)
# Quality enhancement pipeline
builder.add_edge("assess_content_quality", "verify_facts")
builder.add_edge("verify_facts", "assess_relevance")
builder.add_edge("assess_relevance", "optimize_summary")
builder.add_edge("optimize_summary", "generate_verification_report")
builder.add_edge("generate_verification_report", "finalize_answer")
# Finalize the answer
builder.add_edge("finalize_answer", END)

graph = builder.compile(name="enhanced-pro-search-agent")
