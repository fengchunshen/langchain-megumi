from typing import Any, Dict, List, Optional, TypedDict, Callable, TypeVar

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_openai import ChatOpenAI
from typing_extensions import Annotated
from langgraph.graph import add_messages
import operator
import requests
import logging

from app.core.config import settings

T = TypeVar('T')
from .deepsearch_prompts import (
    get_current_date,
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
    content_quality_instructions,
    fact_verification_instructions,
    relevance_assessment_instructions,
    summary_optimization_instructions,
    research_plan_instructions,
)
from .deepsearch_utils import (
    get_citations_from_bocha,
    get_research_topic,
    insert_citation_markers,
    resolve_urls,
    format_bocha_search_results,
)
from .deepsearch_types import (
    SearchQueryList, 
    Reflection,
    ContentQualityAssessment,
    FactVerification,
    RelevanceAssessment,
    SummaryOptimization,
    ResearchPlan,
)


logger = logging.getLogger(__name__)

# 全局变量：跟踪是否已降级到 Qwen3Max
_gemini_degraded = False


def reset_degradation_status():
    """重置降级状态（用于测试或新请求开始时）."""
    global _gemini_degraded
    _gemini_degraded = False
    logger.info("【降级状态】已重置，将重新尝试 Gemini")


def get_qwen_base_url() -> str:
    """获取 Qwen3Max API base URL."""
    base_url = settings.DASHSCOPE_BASE_URL
    if not base_url:
        raise ValueError("DASHSCOPE_BASE_URL is not set")
    # 移除末尾的斜杠（如果有）
    base_url = base_url.rstrip('/')
    # 确保以 /v1 结尾
    if not base_url.endswith('/v1'):
        base_url = f"{base_url}/v1"
    logger.debug(f"Qwen3Max API base URL: {base_url}")
    return base_url


def get_gemini_base_url() -> str:
    """获取 Gemini API base URL，确保以 /v1 结尾"""
    base_url = settings.GEMINI_API_URL
    if not base_url:
        raise ValueError("GEMINI_API_URL is not set")
    # 移除末尾的斜杠（如果有）
    base_url = base_url.rstrip('/')
    # 确保以 /v1 结尾
    if not base_url.endswith('/v1'):
        base_url = f"{base_url}/v1"
    logger.debug(f"Gemini API base URL: {base_url}")
    return base_url


if not settings.GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set")


def create_llm_with_fallback(
    model: str,
    temperature: float,
    use_gemini: bool = True,
    max_retries: int = 2
) -> ChatOpenAI:
    """
    创建 LLM 实例，支持 Gemini 和 Qwen3Max 切换.
    
    Args:
        model: 模型名称
        temperature: 温度参数
        use_gemini: 是否优先使用 Gemini（True）或 Qwen3Max（False）
        max_retries: 最大重试次数
        
    Returns:
        ChatOpenAI: LLM 实例
    """
    if use_gemini:
        base_url = get_gemini_base_url()
        api_key = settings.GEMINI_API_KEY
        logger.debug(f"创建 Gemini LLM 实例: {model}")
    else:
        base_url = get_qwen_base_url()
        api_key = settings.DASHSCOPE_API_KEY
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY is not set")
        logger.debug(f"创建 Qwen3Max LLM 实例: {model}")
    
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        max_retries=max_retries,
        api_key=api_key,
        base_url=base_url,
        timeout=settings.API_TIMEOUT,
    )


def invoke_llm_with_fallback(
    invoke_func: Callable[[ChatOpenAI], T],
    node_name: str,
    gemini_model: str,
    temperature: float = 0.5,
    qwen_model: str = None,
    structured_output_type: Any = None,
    **llm_kwargs
) -> T:
    """
    调用 LLM，支持 Gemini 失败后自动切换到 Qwen3Max.
    
    如果已经降级到 Qwen3Max，直接使用 Qwen3Max，不再尝试 Gemini。
    否则先尝试使用 Gemini（重试2次），如果失败则切换到 Qwen3Max，并设置全局降级标志。
    
    Args:
        invoke_func: 调用函数，接受一个参数（llm 实例）并返回结果
        node_name: 节点名称（用于日志）
        gemini_model: Gemini 模型名称
        temperature: 温度参数
        qwen_model: Qwen3Max 模型名称（默认使用配置中的 DASHSCOPE_CHAT_MODEL）
        structured_output_type: 结构化输出类型（如果提供，会自动调用 with_structured_output）
        **llm_kwargs: 传递给 ChatOpenAI 的其他参数
        
    Returns:
        调用结果
        
    Raises:
        Exception: 如果两种模型都失败，抛出最后一个异常
    """
    global _gemini_degraded
    
    if qwen_model is None:
        qwen_model = settings.DASHSCOPE_CHAT_MODEL
    
    # 如果已经降级，直接使用 Qwen3Max
    if _gemini_degraded:
        logger.info(f"【节点: {node_name}】已降级，直接使用 Qwen3Max ({qwen_model})...")
        try:
            llm = create_llm_with_fallback(
                model=qwen_model,
                temperature=temperature,
                use_gemini=False,
                max_retries=2
            )
            
            # 如果指定了结构化输出类型，使用 with_structured_output
            if structured_output_type is not None:
                llm = llm.with_structured_output(structured_output_type)
            
            result = invoke_func(llm)
            logger.info(f"【节点: {node_name}】Qwen3Max 调用成功")
            return result
        except Exception as e:
            logger.error(f"【节点: {node_name}】Qwen3Max 调用失败: {str(e)}", exc_info=True)
            raise e
    
    # 尝试使用 Gemini（重试2次）
    last_error = None
    for attempt in range(3):  # 第一次 + 2次重试 = 总共3次尝试
        try:
            if attempt == 0:
                logger.info(f"【节点: {node_name}】尝试使用 Gemini ({gemini_model})...")
            else:
                logger.warning(f"【节点: {node_name}】Gemini 第 {attempt} 次重试...")
            
            llm = create_llm_with_fallback(
                model=gemini_model,
                temperature=temperature,
                use_gemini=True,
                max_retries=0  # 在包装函数中手动处理重试
            )
            
            # 如果指定了结构化输出类型，使用 with_structured_output
            if structured_output_type is not None:
                llm = llm.with_structured_output(structured_output_type)
            
            result = invoke_func(llm)
            logger.info(f"【节点: {node_name}】Gemini 调用成功")
            return result
            
        except Exception as e:
            last_error = e
            logger.warning(f"【节点: {node_name}】Gemini 调用失败 (尝试 {attempt + 1}/3): {str(e)}")
            if attempt < 2:  # 还有重试机会
                continue
            else:
                # 所有重试都失败，切换到 Qwen3Max 并设置降级标志
                logger.warning(f"【节点: {node_name}】Gemini 重试2次后仍失败，切换到 Qwen3Max ({qwen_model})...")
                logger.warning(f"【降级状态】已设置降级标志，后续所有调用将直接使用 Qwen3Max")
                _gemini_degraded = True
                break
    
    # 切换到 Qwen3Max
    try:
        llm = create_llm_with_fallback(
            model=qwen_model,
            temperature=temperature,
            use_gemini=False,
            max_retries=2
        )
        
        # 如果指定了结构化输出类型，使用 with_structured_output
        if structured_output_type is not None:
            llm = llm.with_structured_output(structured_output_type)
        
        result = invoke_func(llm)
        logger.info(f"【节点: {node_name}】Qwen3Max 调用成功")
        return result
    except Exception as e:
        logger.error(f"【节点: {node_name}】Qwen3Max 调用也失败: {str(e)}", exc_info=True)
        # 如果 Qwen3Max 也失败，抛出最后一个异常
        raise e


class OverallState(TypedDict, total=False):
    messages: Annotated[List, add_messages]
    research_plan: Optional[ResearchPlan]
    search_query: Annotated[List, operator.add]
    web_research_result: Annotated[List, operator.add]
    sources_gathered: Annotated[List, operator.add]
    all_sources_gathered: Annotated[List, operator.add]  # 所有搜索到的资源（包括未被引用的）
    initial_search_query_count: int
    max_research_loops: int
    research_loop_count: int
    reasoning_model: str
    # 质量增强相关字段
    content_quality: Dict[str, Any]
    fact_verification: Dict[str, Any]
    relevance_assessment: Dict[str, Any]
    summary_optimization: Dict[str, Any]
    verification_report: str
    final_confidence_score: float


class ReflectionState(TypedDict):
    is_sufficient: bool
    knowledge_gap: str
    follow_up_queries: Annotated[List, operator.add]
    research_loop_count: int
    number_of_ran_queries: int
    max_research_loops: int  # 添加最大研究循环次数字段


class Query(TypedDict):
    query: str
    rationale: str


class QueryGenerationState(TypedDict):
    search_query: List[str]  # 实际上是字符串列表，不是 Query 对象列表


class WebSearchState(TypedDict):
    search_query: str
    id: str


def generate_research_plan(state: OverallState, config: RunnableConfig) -> OverallState:
    """
    生成研究方案节点。
    """
    logger.info("【节点: generate_research_plan】开始生成研究方案...")
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    research_topic = get_research_topic(state["messages"])
    logger.info(f"【节点: generate_research_plan】研究主题: {research_topic[:200]}...")
    
    formatted_prompt = research_plan_instructions.format(
        research_topic=research_topic
    )
    
    logger.info("【节点: generate_research_plan】调用 LLM 生成方案...")
    try:
        plan = invoke_llm_with_fallback(
            invoke_func=lambda llm: llm.invoke(formatted_prompt),
            node_name="generate_research_plan",
            gemini_model=reasoning_model,
            temperature=0.3,  # 从0.5降低到0.3，让输出更严谨详细
            structured_output_type=ResearchPlan
        )
        logger.info(f"【节点: generate_research_plan】研究方案生成完毕，包含 {len(plan.sub_topics)} 个子主题")
        logger.info(f"【节点: generate_research_plan】研究问题总数: {len(plan.research_questions)}")
        for idx, sub_topic in enumerate(plan.sub_topics, 1):
            logger.info(f"【节点: generate_research_plan】  子主题 {idx}: {sub_topic}")
        return {"research_plan": plan}
    except Exception as e:
        logger.error(f"【节点: generate_research_plan】生成方案失败: {e}", exc_info=True)
        return {"research_plan": None}


def generate_query(state: OverallState, config: RunnableConfig) -> QueryGenerationState:
    logger.info("【节点: generate_query】开始生成搜索查询...")
    initial_count = state.get("initial_search_query_count")
    if initial_count is None:
        initial_count = 3
        state["initial_search_query_count"] = initial_count
    
    logger.info(f"【节点: generate_query】初始搜索查询数量: {initial_count}")
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    logger.info(f"【节点: generate_query】使用模型: {reasoning_model}")

    research_topic = get_research_topic(state["messages"])
    research_plan = state.get("research_plan")
    
    # 将方案格式化为字符串
    plan_str = "无特定方案，请直接分析研究主题。"
    if research_plan and research_plan.sub_topics:
        logger.info(f"【节点: generate_query】基于方案 '{research_plan.research_topic}' 生成查询")
        plan_str = f"主题: {research_plan.research_topic}\n\n关键子主题和研究问题:\n"
        
        # 按子主题分组研究问题
        for i, sub_topic in enumerate(research_plan.sub_topics, 1):
            plan_str += f"\n{i}. {sub_topic}\n"
            plan_str += "   研究问题:\n"
            # 找出属于当前子主题的研究问题
            topic_questions = [q for q in research_plan.research_questions if q.startswith(f"{sub_topic}：")]
            if not topic_questions:
                # 如果没有严格匹配的，尝试模糊匹配
                topic_questions = [q for q in research_plan.research_questions if sub_topic in q]
            for j, question in enumerate(topic_questions, 1):
                # 移除「子主题：」前缀，只显示问题本身
                question_text = question.split("：", 1)[-1] if "：" in question else question
                plan_str += f"   {i}.{j}. {question_text}\n"
        
        plan_str += f"\n理由: {research_plan.rationale}"
    else:
        logger.warning("【节点: generate_query】未找到研究方案，将仅基于主题生成查询")
    
    logger.info(f"【节点: generate_query】研究主题: {research_topic[:200]}...")
    
    formatted_prompt = query_writer_instructions.format(
        current_date=get_current_date(),
        research_topic=research_topic,
        research_plan=plan_str,
        number_queries=initial_count,
    )
    
    logger.info("【节点: generate_query】调用 LLM (基于方案) 生成查询...")
    result = invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.invoke(formatted_prompt),
        node_name="generate_query",
        gemini_model=reasoning_model,
        temperature=1.0,
        structured_output_type=SearchQueryList
    )
    
    query_count = len(result.query) if result.query else 0
    logger.info(f"【节点: generate_query】成功生成 {query_count} 个搜索查询")
    for idx, query_item in enumerate(result.query[:5], 1):  # 只记录前5个
        logger.info(f"【节点: generate_query】  查询 {idx}: {query_item[:100]}...")
    
    return {"search_query": result.query}


def continue_to_web_research(state: QueryGenerationState):
    query_count = len(state["search_query"])
    logger.info(f"【节点: continue_to_web_research】准备分发 {query_count} 个搜索任务到 web_research 节点")
    return [
        Send("web_research", {"search_query": search_query, "id": int(idx)})
        for idx, search_query in enumerate(state["search_query"])
    ]


def bocha_web_search(query: str, count: int = 10) -> Dict[str, Any]:
    """
    使用博查搜索 API 进行网页搜索。

    参数:
    - query: 搜索关键词
    - count: 返回的搜索结果数量

    返回:
    - 包含搜索结果和格式化文本的字典
    """
    if not settings.BOCHA_API_KEY:
        raise ValueError("BOCHA_API_KEY is not set in environment variables")

    url = 'https://api.bochaai.com/v1/web-search'
    headers = {
        'Authorization': f'Bearer {settings.BOCHA_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        "query": query,
        "freshness": "noLimit",  # 搜索的时间范围
        "summary": True,  # 是否返回长文本摘要
        "count": count
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            json_response = response.json()
            if json_response.get("code") != 200 or not json_response.get("data"):
                error_msg = json_response.get("msg", "未知错误")
                logger.error(f"博查搜索API请求失败: {error_msg}")
                return {
                    "webpages": [],
                    "formatted_text": f"搜索API请求失败，原因是: {error_msg}"
                }
            
            webpages = json_response.get("data", {}).get("webPages", {}).get("value", [])
            if not webpages:
                logger.warning(f"博查搜索API返回空结果，查询: {query[:100]}...")
                return {
                    "webpages": [],
                    "formatted_text": "未找到相关结果。"
                }
            
            logger.info(f"博查搜索API成功返回 {len(webpages)} 个结果，查询: {query[:100]}...")
            formatted_text = format_bocha_search_results(webpages)
            return {
                "webpages": webpages,
                "formatted_text": formatted_text
            }
        else:
            error_msg = f"状态码: {response.status_code}, 错误信息: {response.text}"
            logger.error(f"博查搜索API请求失败: {error_msg}")
            return {
                "webpages": [],
                "formatted_text": f"搜索API请求失败，{error_msg}"
            }
    except Exception as e:
        logger.error(f"博查搜索API调用异常: {str(e)}")
        return {
            "webpages": [],
            "formatted_text": f"搜索API请求失败，原因是：{str(e)}"
        }


def web_research(state: WebSearchState, config: RunnableConfig) -> OverallState:
    """
    使用博查搜索 API 进行网页研究。
    """
    search_query = state["search_query"]
    search_id = state["id"]
    
    logger.info(f"【节点: web_research】开始执行搜索任务 ID={search_id}")
    logger.info(f"【节点: web_research】搜索查询: {search_query[:200]}...")
    
    # 调用博查搜索 API
    logger.info(f"【节点: web_research】调用博查搜索 API...")
    search_result = bocha_web_search(query=search_query, count=10)
    
    webpages = search_result.get("webpages", [])
    formatted_text = search_result.get("formatted_text", "")
    
    webpage_count = len(webpages) if webpages else 0
    logger.info(f"【节点: web_research】搜索完成，找到 {webpage_count} 个网页结果")
    
    if webpage_count > 0:
        logger.info(f"【节点: web_research】前3个结果标题:")
        for idx, page in enumerate(webpages[:3], 1):
            logger.info(f"【节点: web_research】  {idx}. {page.get('name', 'N/A')[:100]}")
    
    # 使用 Gemini 对搜索结果进行总结和整理
    logger.info(f"【节点: web_research】开始使用 LLM 总结搜索结果...")
    formatted_prompt = web_searcher_instructions.format(
        current_date=get_current_date(),
        research_topic=search_query,
    )

    # 将搜索结果添加到提示词中，并提示 LLM 使用引用编号
    search_context = (
        f"\n\n搜索查询: {search_query}\n"
        f"搜索结果（请在你的回答中使用引用编号 [1], [2] 等来引用这些来源）:\n{formatted_text}"
    )
    full_prompt = formatted_prompt + search_context

    logger.info(f"【节点: web_research】调用 LLM API，提示词长度: {len(full_prompt)} 字符")
    llm_response = invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.invoke(full_prompt),
        node_name="web_research",
        gemini_model=settings.GEMINI_MODEL,
        temperature=0
    )
    logger.info(f"【节点: web_research】LLM 总结完成，响应长度: {len(llm_response.content)} 字符")
    
    # 处理引用和来源
    logger.info(f"【节点: web_research】开始处理引用和来源...")
    resolved_urls = resolve_urls(webpages, search_id)
    citations = get_citations_from_bocha(webpages, resolved_urls, llm_response.content)
    modified_text = insert_citation_markers(llm_response.content, citations)
    sources_gathered = [item for citation in citations for item in citation["segments"]]
    
    logger.info(f"【节点: web_research】处理完成，生成 {len(citations)} 个引用，{len(sources_gathered)} 个数据源片段")
    logger.info(f"【节点: web_research】搜索任务 ID={search_id} 完成")

    return {
        "sources_gathered": sources_gathered,
        "all_sources_gathered": sources_gathered,  # 保存所有搜索到的资源
        "search_query": [search_query],
        "web_research_result": [modified_text],
    }


def reflection(state: OverallState, config: RunnableConfig) -> ReflectionState:
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    loop_count = state["research_loop_count"]
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    logger.info(f"【节点: reflection】开始反思，研究循环次数: {loop_count}")
    logger.info(f"【节点: reflection】使用模型: {reasoning_model}")
    
    web_research_results = state.get("web_research_result", [])
    search_queries = state.get("search_query", [])
    logger.info(f"【节点: reflection】当前已有 {len(web_research_results)} 个搜索结果，{len(search_queries)} 个搜索查询")

    formatted_prompt = reflection_instructions.format(
        research_topic=get_research_topic(state["messages"]),
        loop_count=loop_count,
        summaries="\n\n---\n\n".join(state["web_research_result"]),
    )
    
    logger.info("【节点: reflection】调用 LLM 进行反思评估...")
    result = invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.invoke(formatted_prompt),
        node_name="reflection",
        gemini_model=reasoning_model,
        temperature=1.0,
        structured_output_type=Reflection
    )

    logger.info(f"【节点: reflection】=== 信息充足性评估结果 ===")
    logger.info(f"【节点: reflection】  当前循环: 第 {loop_count} 轮")
    logger.info(f"【节点: reflection】  信息是否充足: {result.is_sufficient}")
    
    if result.is_sufficient:
        logger.info(f"【节点: reflection】  ✅ 评估结果: 信息已充足，可以开始生成报告")
    else:
        logger.info(f"【节点: reflection】  ⚠️  评估结果: 信息不足，需要继续研究")
        logger.info(f"【节点: reflection】  知识缺口: {result.knowledge_gap[:200] if result.knowledge_gap else 'N/A'}...")
        follow_up_count = len(result.follow_up_queries) if result.follow_up_queries else 0
        logger.info(f"【节点: reflection】  后续查询数量: {follow_up_count}")
        if follow_up_count > 0:
            for idx, query in enumerate(result.follow_up_queries[:3], 1):  # 只记录前3个
                logger.info(f"【节点: reflection】    后续查询 {idx}: {query[:100]}...")

    return {
        "is_sufficient": result.is_sufficient,
        "knowledge_gap": result.knowledge_gap,
        "follow_up_queries": result.follow_up_queries,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
        "max_research_loops": state.get("max_research_loops", 5),  # 传递最大循环次数，默认5
    }


def evaluate_research(state: ReflectionState, config: RunnableConfig) -> OverallState:
    max_research_loops = state.get("max_research_loops", 5)  # 默认5次循环
    loop_count = state["research_loop_count"]
    is_sufficient = state["is_sufficient"]
    
    logger.info(f"【节点: evaluate_research】=== 研究状态决策 ===")
    logger.info(f"【节点: evaluate_research】  当前循环次数: {loop_count}/{max_research_loops}")
    logger.info(f"【节点: evaluate_research】  信息是否充足: {is_sufficient}")
    
    if state["is_sufficient"]:
        logger.info(f"【节点: evaluate_research】✅ 决策: 信息已充足，结束调查循环")
        logger.info(f"【节点: evaluate_research】➡️  下一步: 开始质量评估和报告生成流程")
        return "assess_content_quality"
    elif state["research_loop_count"] >= max_research_loops:
        logger.info(f"【节点: evaluate_research】⚠️  决策: 已达到最大循环次数 ({max_research_loops})，强制结束")
        logger.info(f"【节点: evaluate_research】➡️  下一步: 基于现有信息生成报告")
        return "assess_content_quality"
    else:
        follow_up_queries = state.get("follow_up_queries", [])
        follow_up_count = len(follow_up_queries)
        logger.info(f"【节点: evaluate_research】🔄 决策: 信息不足，继续第 {loop_count + 1} 轮调查")
        logger.info(f"【节点: evaluate_research】➡️  下一步: 分发 {follow_up_count} 个后续查询到 web_research 节点")
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


def assess_content_quality(state: OverallState, config: RunnableConfig):
    """内容质量评估节点。"""
    logger.info(f"【节点: assess_content_quality】开始内容质量评估")
    
    # 合并所有研究内容
    combined_content = "\n\n---\n\n".join(state.get("web_research_result", []))
    
    # 格式化提示词
    formatted_prompt = content_quality_instructions.format(
        research_topic=get_research_topic(state["messages"]),
        content=combined_content
    )
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    logger.info(f"【节点: assess_content_quality】使用模型: {reasoning_model}")
    
    result = invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.invoke(formatted_prompt),
        node_name="assess_content_quality",
        gemini_model=reasoning_model,
        temperature=0.3,
        structured_output_type=ContentQualityAssessment
    )
    
    logger.info(f"【节点: assess_content_quality】质量评分: {result.quality_score}")
    logger.info(f"【节点: assess_content_quality】内容空白数量: {len(result.content_gaps)}")
    
    return {
        "content_quality": {
            "quality_score": result.quality_score,
            "reliability_assessment": result.reliability_assessment,
            "content_gaps": result.content_gaps,
            "improvement_suggestions": result.improvement_suggestions
        }
    }


def verify_facts(state: OverallState, config: RunnableConfig):
    """事实验证节点。"""
    logger.info(f"【节点: verify_facts】开始事实验证")
    
    # 合并所有研究内容
    combined_content = "\n\n---\n\n".join(state.get("web_research_result", []))
    
    # 格式化提示词
    current_date = get_current_date()
    formatted_prompt = fact_verification_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        content=combined_content
    )
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    logger.info(f"【节点: verify_facts】使用模型: {reasoning_model}")
    
    def invoke_with_method(llm: ChatOpenAI):
        """调用带 method 参数的 structured_output."""
        structured_llm = llm.with_structured_output(
            FactVerification,
            method="json_schema",
            include_raw=False
        )
        return structured_llm.invoke(formatted_prompt)
    
    result = invoke_llm_with_fallback(
        invoke_func=invoke_with_method,
        node_name="verify_facts",
        gemini_model=reasoning_model,
        temperature=0.1
    )
    
    logger.info(f"【节点: verify_facts】验证置信度: {result.confidence_score}")
    logger.info(f"【节点: verify_facts】已验证事实数量: {len(result.verified_facts_text)}")
    logger.info(f"【节点: verify_facts】争议声明数量: {len(result.disputed_claims_text)}")
    
    # 将扁平化的列表转换为字典列表
    verified_facts_dicts = [
        {"fact": fact, "source": source} 
        for fact, source in zip(result.verified_facts_text, result.verified_facts_sources)
    ]
    disputed_claims_dicts = [
        {"claim": claim, "reason": reason} 
        for claim, reason in zip(result.disputed_claims_text, result.disputed_claims_reasons)
    ]
    
    return {
        "fact_verification": {
            "verified_facts": verified_facts_dicts,
            "disputed_claims": disputed_claims_dicts,
            "verification_sources": result.verification_sources,
            "confidence_score": result.confidence_score
        }
    }


def assess_relevance(state: OverallState, config: RunnableConfig):
    """相关性评估节点。"""
    logger.info(f"【节点: assess_relevance】开始相关性评估")
    
    # 合并所有研究内容
    combined_content = "\n\n---\n\n".join(state.get("web_research_result", []))
    
    # 格式化提示词
    formatted_prompt = relevance_assessment_instructions.format(
        research_topic=get_research_topic(state["messages"]),
        content=combined_content
    )
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    logger.info(f"【节点: assess_relevance】使用模型: {reasoning_model}")
    
    result = invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.invoke(formatted_prompt),
        node_name="assess_relevance",
        gemini_model=reasoning_model,
        temperature=0.2,
        structured_output_type=RelevanceAssessment
    )
    
    logger.info(f"【节点: assess_relevance】相关性评分: {result.relevance_score}")
    logger.info(f"【节点: assess_relevance】覆盖关键主题数量: {len(result.key_topics_covered)}")
    logger.info(f"【节点: assess_relevance】缺失主题数量: {len(result.missing_topics)}")
    
    return {
        "relevance_assessment": {
            "relevance_score": result.relevance_score,
            "key_topics_covered": result.key_topics_covered,
            "missing_topics": result.missing_topics,
            "content_alignment": result.content_alignment
        }
    }


def optimize_summary(state: OverallState, config: RunnableConfig):
    """摘要优化节点。"""
    logger.info(f"【节点: optimize_summary】开始摘要优化")
    
    # 获取原始摘要
    original_summary = "\n\n---\n\n".join(state.get("web_research_result", []))
    
    # 格式化提示词
    current_date = get_current_date()
    formatted_prompt = summary_optimization_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        original_summary=original_summary,
        quality_assessment=str(state.get("content_quality", {})),
        fact_verification=str(state.get("fact_verification", {})),
        relevance_assessment=str(state.get("relevance_assessment", {}))
    )
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    logger.info(f"【节点: optimize_summary】使用模型: {reasoning_model}")
    
    result = invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.invoke(formatted_prompt),
        node_name="optimize_summary",
        gemini_model=reasoning_model,
        temperature=0.3,
        structured_output_type=SummaryOptimization
    )
    
    # 计算最终置信度评分
    quality_score = state.get("content_quality", {}).get("quality_score", 0.5)
    fact_confidence = state.get("fact_verification", {}).get("confidence_score", 0.5)
    relevance_score = state.get("relevance_assessment", {}).get("relevance_score", 0.5)
    final_confidence = (quality_score + fact_confidence + relevance_score) / 3
    
    logger.info(f"【节点: optimize_summary】关键洞察数量: {len(result.key_insights)}")
    logger.info(f"【节点: optimize_summary】可行建议数量: {len(result.actionable_items)}")
    logger.info(f"【节点: optimize_summary】置信度等级: {result.confidence_level}")
    logger.info(f"【节点: optimize_summary】最终置信度评分: {final_confidence:.3f}")
    
    return {
        "summary_optimization": {
            "key_insights": result.key_insights,
            "actionable_items": result.actionable_items,
            "confidence_level": result.confidence_level
        },
        "final_confidence_score": final_confidence
    }


def generate_verification_report(state: OverallState, config: RunnableConfig):
    """生成综合验证报告节点。"""
    logger.info(f"【节点: generate_verification_report】开始生成验证报告")
    
    # 生成综合验证报告
    quality_data = state.get("content_quality", {})
    fact_data = state.get("fact_verification", {})
    relevance_data = state.get("relevance_assessment", {})
    optimization_data = state.get("summary_optimization", {})
    
    report = f"""
# 研究质量验证报告

## 内容质量评估
- **质量评分**: {quality_data.get('quality_score', 'N/A'):.2f}/1.0
- **可靠性评估**: {quality_data.get('reliability_assessment', 'N/A')}
- **内容空白**: {', '.join(quality_data.get('content_gaps', [])) if quality_data.get('content_gaps') else '无明显空白'}
- **改进建议**: {', '.join(quality_data.get('improvement_suggestions', [])) if quality_data.get('improvement_suggestions') else '无特别建议'}

## 事实验证结果
- **验证置信度**: {fact_data.get('confidence_score', 'N/A'):.2f}/1.0
- **已验证事实数量**: {len(fact_data.get('verified_facts', []))}
- **争议声明数量**: {len(fact_data.get('disputed_claims', []))}
- **验证来源**: {', '.join(fact_data.get('verification_sources', [])) if fact_data.get('verification_sources') else '多个来源'}

## 相关性评估
- **相关性评分**: {relevance_data.get('relevance_score', 'N/A'):.2f}/1.0
- **已覆盖关键主题**: {', '.join(relevance_data.get('key_topics_covered', [])) if relevance_data.get('key_topics_covered') else 'N/A'}
- **缺失主题**: {', '.join(relevance_data.get('missing_topics', [])) if relevance_data.get('missing_topics') else '无明显缺失'}
- **内容一致性**: {relevance_data.get('content_alignment', 'N/A')}

## 摘要优化结果
- **置信度等级**: {optimization_data.get('confidence_level', 'N/A')}
- **关键洞察数量**: {len(optimization_data.get('key_insights', []))}
- **可行建议数量**: {len(optimization_data.get('actionable_items', []))}

## 综合评估
- **最终置信度评分**: {state.get('final_confidence_score', 0):.3f}/1.0
"""
    
    logger.info(f"【节点: generate_verification_report】验证报告生成完成")
    
    return {
        "verification_report": report
    }


def finalize_answer(state: OverallState, config: RunnableConfig):
    """生成最终答案，返回高度围绕用户提问的调查研究报告。"""
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    logger.info(f"【节点: finalize_answer】开始生成最终答案")
    logger.info(f"【节点: finalize_answer】使用模型: {reasoning_model}")
    
    web_research_results = state.get("web_research_result", [])
    sources_gathered = state.get("sources_gathered", [])
    logger.info(f"【节点: finalize_answer】汇总 {len(web_research_results)} 个搜索结果，{len(sources_gathered)} 个数据源")

    # 获取所有原始材料
    summaries = "\n---\n\n".join(web_research_results)
    
    # 获取上一步的结构化洞察
    optimization_data = state.get("summary_optimization", {})
    key_insights = optimization_data.get("key_insights", [])
    actionable_items = optimization_data.get("actionable_items", [])
    
    logger.info(f"【节点: finalize_answer】核心洞察数量: {len(key_insights)}")
    logger.info(f"【节点: finalize_answer】可行建议数量: {len(actionable_items)}")
    
    # 构建增强的提示词，将结构化洞察注入
    prompt_enhancement = ""
    if key_insights or actionable_items:
        prompt_enhancement = "\n\n---\n\n**以下是基于研究材料提炼出的核心洞察和建议，请将它们作为报告的重点，在报告中详细展开论述：**\n\n"
        
        if key_insights:
            prompt_enhancement += "**核心洞察 (Key Insights):**\n"
            for i, insight in enumerate(key_insights, 1):
                prompt_enhancement += f"{i}. {insight}\n"
            prompt_enhancement += "\n"
        
        if actionable_items:
            prompt_enhancement += "**可行建议 (Actionable Items):**\n"
            for i, item in enumerate(actionable_items, 1):
                prompt_enhancement += f"{i}. {item}\n"
    
    # 使用 answer_instructions 来撰写报告
    formatted_prompt = answer_instructions.format(
        current_date=get_current_date(),
        research_topic=get_research_topic(state["messages"]),
        summaries=summaries + prompt_enhancement  # 将洞察注入提示词
    )
    
    logger.info("【节点: finalize_answer】调用 LLM 生成专业报告...")
    
    # *** 关键：这里不使用 .with_structured_output()，直接生成纯文本报告 ***
    result = invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.invoke(formatted_prompt),
        node_name="finalize_answer",
        gemini_model=reasoning_model,
        temperature=0.2
    )
    final_report = result.content  # 这就是纯 Markdown 报告
    
    logger.info(f"【节点: finalize_answer】LLM 生成完成，报告长度: {len(final_report)} 字符")
    
    # 处理数据源引用
    logger.info("【节点: finalize_answer】处理数据源引用...")
    unique_sources: List[Dict[str, Any]] = []
    enhanced_content = final_report
    
    for source in sources_gathered:
        if source["shortUrl"] in enhanced_content:
            enhanced_content = enhanced_content.replace(source["shortUrl"], source["value"])
            unique_sources.append(source)
    
    logger.info(f"【节点: finalize_answer】最终答案包含 {len(unique_sources)} 个被引用的数据源")
    logger.info(f"【节点: finalize_answer】最终内容长度: {len(enhanced_content)} 字符")
    logger.info(f"【节点: finalize_answer】节点执行完成")

    return {
        "messages": [AIMessage(content=enhanced_content)],
        "sources_gathered": unique_sources,
    }


_builder = StateGraph(OverallState)
_builder.add_node("generate_research_plan", generate_research_plan)
_builder.add_node("generate_query", generate_query)
_builder.add_node("web_research", web_research)
_builder.add_node("reflection", reflection)
# 添加质量增强节点
_builder.add_node("assess_content_quality", assess_content_quality)
_builder.add_node("verify_facts", verify_facts)
_builder.add_node("assess_relevance", assess_relevance)
_builder.add_node("optimize_summary", optimize_summary)
_builder.add_node("generate_verification_report", generate_verification_report)
_builder.add_node("finalize_answer", finalize_answer)

# 设置入口点
_builder.add_edge(START, "generate_research_plan")
_builder.add_edge("generate_research_plan", "generate_query")
_builder.add_conditional_edges("generate_query", continue_to_web_research, ["web_research"])
_builder.add_edge("web_research", "reflection")
_builder.add_conditional_edges("reflection", evaluate_research, ["web_research", "assess_content_quality"])

# 质量增强流程
_builder.add_edge("assess_content_quality", "verify_facts")
_builder.add_edge("verify_facts", "assess_relevance")
_builder.add_edge("assess_relevance", "optimize_summary")
_builder.add_edge("optimize_summary", "generate_verification_report")
_builder.add_edge("generate_verification_report", "finalize_answer")

# 结束节点
_builder.add_edge("finalize_answer", END)

graph = _builder.compile(name="enhanced-pro-search-engine")

logger.info("【图构建完成】增强型 Pro Search Engine 已编译完成 (已加入研究方案步骤)")


