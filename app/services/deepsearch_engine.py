from typing import Any, Dict, List, Optional, TypedDict, Callable, TypeVar
import asyncio
import inspect
import httpx

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_openai import ChatOpenAI
from typing_extensions import Annotated
from langgraph.graph import add_messages
import operator
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
from .web_scraper import scrape_webpages, clean_and_truncate
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

# 全局取消状态管理（使用 asyncio.Event 更安全地避免竞态）
_connection_cancellations: Dict[str, asyncio.Event] = {}
_cancellations_lock = asyncio.Lock()


def reset_degradation_status():
    """重置降级状态（用于测试或新请求开始时）."""
    global _gemini_degraded
    _gemini_degraded = False
    logger.info("【降级状态】已重置，将重新尝试 Gemini")


async def set_connection_cancelled(connection_id: str):
    """标记连接为已取消."""
    global _connection_cancellations
    async with _cancellations_lock:
        event = _connection_cancellations.get(connection_id)
        if event is None:
            event = asyncio.Event()
            _connection_cancellations[connection_id] = event
        event.set()
    logger.info(f"【取消状态】连接 {connection_id} 已被标记为取消")


def is_connection_cancelled(connection_id: str) -> bool:
    """检查连接是否已被取消."""
    global _connection_cancellations
    event = _connection_cancellations.get(connection_id)
    return event.is_set() if event else False


async def cleanup_connection_cancellation(connection_id: str):
    """清理连接的取消状态."""
    global _connection_cancellations
    async with _cancellations_lock:
        if connection_id in _connection_cancellations:
            del _connection_cancellations[connection_id]
    logger.info(f"【取消状态】连接 {connection_id} 的取消状态已清理")


def check_cancellation_and_raise(connection_id: Optional[str] = None):
    """检查取消状态，如果被取消则抛出CancelledError."""
    if connection_id and is_connection_cancelled(connection_id):
        logger.info(f"【取消检查】连接 {connection_id} 已被取消，停止执行")
        raise asyncio.CancelledError(f"连接 {connection_id} 已被取消")


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


async def invoke_llm_with_fallback(
    invoke_func: Callable[[ChatOpenAI], T],
    node_name: str,
    gemini_model: str,
    temperature: float = 0.5,
    qwen_model: str = None,
    structured_output_type: Any = None,
    connection_id: Optional[str] = None,
    **llm_kwargs
) -> T:
    """
    异步调用 LLM，支持 Gemini 失败后自动切换到 Qwen3Max.
    
    如果已经降级到 Qwen3Max，直接使用 Qwen3Max，不再尝试 Gemini。
    否则先尝试使用 Gemini（重试2次），如果失败则切换到 Qwen3Max，并设置全局降级标志。
    
    Args:
        invoke_func: 异步调用函数，接受一个参数（llm 实例）并返回结果（支持同步和异步函数）
        node_name: 节点名称（用于日志）
        gemini_model: Gemini 模型名称
        temperature: 温度参数
        qwen_model: Qwen3Max 模型名称（默认使用配置中的 DASHSCOPE_CHAT_MODEL）
        structured_output_type: 结构化输出类型（如果提供，会自动调用 with_structured_output）
        connection_id: 连接ID，用于取消检查
        **llm_kwargs: 传递给 ChatOpenAI 的其他参数
        
    Returns:
        调用结果
        
    Raises:
        Exception: 如果两种模型都失败，抛出最后一个异常
        asyncio.CancelledError: 如果连接被取消
    """
    global _gemini_degraded
    
    # 在每次重试前检查取消状态
    check_cancellation_and_raise(connection_id)
    
    if qwen_model is None:
        qwen_model = settings.DASHSCOPE_CHAT_MODEL
    
    # 如果已经降级，直接使用 Qwen3Max
    if _gemini_degraded:
        logger.info(f"【节点: {node_name}】已降级，直接使用 Qwen3Max ({qwen_model})...")
        try:
            # 再次检查取消状态
            check_cancellation_and_raise(connection_id)
            
            llm = create_llm_with_fallback(
                model=qwen_model,
                temperature=temperature,
                use_gemini=False,
                max_retries=2
            )
            
            # 如果指定了结构化输出类型，使用 with_structured_output
            if structured_output_type is not None:
                llm = llm.with_structured_output(structured_output_type)
            
            # 调用并根据可等待性进行处理（兼容同步函数返回协程的情况）
            _maybe = invoke_func(llm)
            result = await _maybe if inspect.isawaitable(_maybe) else _maybe
            
            # 成功返回后立刻再次检查是否已取消，避免断开后继续输出
            check_cancellation_and_raise(connection_id)
            logger.info(f"【节点: {node_name}】Qwen3Max 调用成功")
            return result
        except Exception as e:
            logger.error(f"【节点: {node_name}】Qwen3Max 调用失败: {str(e)}", exc_info=True)
            raise e
    
    # 尝试使用 Gemini（重试1次）
    last_error = None
    for attempt in range(2):  # 第一次 + 1次重试 = 总共2次尝试
        try:
            # 每次重试前都检查取消状态
            check_cancellation_and_raise(connection_id)
            
            base_url = get_gemini_base_url()
            api_key = settings.GEMINI_API_KEY
            logger.info(f"【节点: {node_name}】尝试使用 Gemini ({gemini_model})...")
            
            # 每次重试都重新创建LLM实例
            llm = ChatOpenAI(
                model=gemini_model,
                temperature=temperature,
                api_key=api_key,
                base_url=base_url,
                timeout=settings.API_TIMEOUT,
                max_retries=1,  # 内部不再重试，由外层控制
                **llm_kwargs
            )
            
            # 如果指定了结构化输出类型，使用 with_structured_output
            if structured_output_type is not None:
                llm = llm.with_structured_output(structured_output_type)
            
            logger.info(f"【节点: {node_name}】Gemini 调用开始...")
            
            # 调用并根据可等待性进行处理（兼容同步函数返回协程的情况）
            _maybe = invoke_func(llm)
            result = await _maybe if inspect.isawaitable(_maybe) else _maybe
            
            # 成功返回后立刻再次检查是否已取消，避免断开后继续输出
            check_cancellation_and_raise(connection_id)
            logger.info(f"【节点: {node_name}】Gemini 调用成功")
            return result
            
        except Exception as e:
            last_error = e
            logger.warning(f"【节点: {node_name}】Gemini 调用失败 (尝试 {attempt + 1}/2): {str(e)}", exc_info=False)
            
            if attempt == 0:
                logger.info(f"【节点: {node_name}】Gemini 第 1 次重试...")
                # 重试前检查取消状态
                check_cancellation_and_raise(connection_id)
            else:
                # 所有重试都失败了，切换到 Qwen3Max
                logger.warning(f"【节点: {node_name}】Gemini 重试{attempt}次后仍失败，切换到 Qwen3Max ({qwen_model})...")
                
                # 切换前检查取消状态
                check_cancellation_and_raise(connection_id)
                
                # 设置全局降级标志
                _gemini_degraded = True
                logger.warning(f"【降级状态】已设置降级标志，后续所有调用将直接使用 Qwen3Max")
                
                # 重新递归调用，这次直接使用 Qwen3Max
                return await invoke_llm_with_fallback(
                    invoke_func=invoke_func,
                    node_name=node_name,
                    gemini_model=gemini_model,
                    temperature=temperature,
                    qwen_model=qwen_model,
                    structured_output_type=structured_output_type,
                    connection_id=connection_id,
                    **llm_kwargs
                )
    
    # 如果到这里，说明所有尝试都失败了
    logger.error(f"【节点: {node_name}】所有模型调用都失败，最后错误: {last_error}")
    raise last_error


class OverallState(TypedDict, total=False):
    messages: Annotated[List, add_messages]
    research_plan: Optional[ResearchPlan]
    search_query: Annotated[List, operator.add]
    new_search_query: List[str]  # 本轮新生成的查询（不累加）
    web_research_result: Annotated[List, operator.add]
    sources_gathered: Annotated[List, operator.add]
    all_sources_gathered: Annotated[List, operator.add]  # 所有搜索到的资源（包括未被引用的）
    initial_search_query_count: int
    max_research_loops: int
    research_loop_count: int
    reasoning_model: str
    unanswered_questions: List[str]  # 未回答的研究问题列表（每轮替换，不累加）
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
    unanswered_questions: List[str]  # 每轮替换，不累加
    research_loop_count: int
    number_of_ran_queries: int
    max_research_loops: int  # 添加最大研究循环次数字段


class Query(TypedDict):
    query: str
    rationale: str


class QueryGenerationState(TypedDict):
    search_query: List[str]  # 实际上是字符串列表，不是 Query 对象列表
    new_search_query: List[str]  # 本轮新生成的查询（不累加）


class WebSearchState(TypedDict):
    search_query: str
    id: str


async def generate_research_plan(state: OverallState, config: RunnableConfig) -> OverallState:
    """
    生成研究方案节点。
    """
    # 获取connection_id用于取消检查，安全处理config对象
    connection_id = None
    if config:
        # 处理config可能是RunnableConfig对象或字典的情况
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    logger.info("【节点: generate_research_plan】开始生成研究方案...")
    
    # 检查取消状态
    check_cancellation_and_raise(connection_id)
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    research_topic = get_research_topic(state["messages"])
    logger.info(f"【节点: generate_research_plan】研究主题: {research_topic[:200]}...")
    
    formatted_prompt = research_plan_instructions.format(
        research_topic=research_topic
    )
    
    logger.info("【节点: generate_research_plan】调用 LLM 生成方案...")
    try:
        plan = await invoke_llm_with_fallback(
            invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
            node_name="generate_research_plan",
            gemini_model=reasoning_model,
            temperature=0.3,  # 从0.5降低到0.3，让输出更严谨详细
            structured_output_type=ResearchPlan,
            connection_id=connection_id
        )
        # 返回后再次检查取消，避免后续日志继续输出
        check_cancellation_and_raise(connection_id)
        logger.info(f"【节点: generate_research_plan】研究方案生成完毕，包含 {len(plan.sub_topics)} 个子主题")
        logger.info(f"【节点: generate_research_plan】研究问题总数: {len(plan.research_questions)}")
        for idx, sub_topic in enumerate(plan.sub_topics, 1):
            logger.info(f"【节点: generate_research_plan】  子主题 {idx}: {sub_topic}")
        return {"research_plan": plan}
    except asyncio.CancelledError:
        # 主动取消时不记录错误，向上抛出以尽快停止图执行
        logger.info("【节点: generate_research_plan】检测到取消，终止节点执行")
        raise
    except Exception as e:
        logger.error(f"【节点: generate_research_plan】生成方案失败: {e}", exc_info=True)
        return {"research_plan": None}


async def generate_query(state: OverallState, config: RunnableConfig) -> QueryGenerationState:
    # 获取connection_id用于取消检查
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    # 检查取消状态
    check_cancellation_and_raise(connection_id)
    
    logger.info("【节点: generate_query】开始生成搜索查询...")
    
    # 判断运行模式：首次运行 vs 针对性运行
    unanswered_questions = state.get("unanswered_questions", [])
    is_targeted_mode = len(unanswered_questions) > 0
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    logger.info(f"【节点: generate_query】使用模型: {reasoning_model}")
    
    research_topic = get_research_topic(state["messages"])
    research_plan = state.get("research_plan")
    
    # 将方案格式化为字符串
    plan_str = "无特定方案，请直接分析研究主题。"
    if research_plan and research_plan.sub_topics:
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
    
    # 根据模式设置不同的提示词
    if is_targeted_mode:
        # 针对性模式：仅针对未回答的问题生成查询
        logger.info(f"【节点: generate_query】运行模式: 针对性（Targeted）")
        logger.info(f"【节点: generate_query】未回答问题数量: {len(unanswered_questions)}")
        for idx, question in enumerate(unanswered_questions[:3], 1):
            logger.info(f"【节点: generate_query】  未回答问题 {idx}: {question[:100]}...")
        
        # 针对性模式：每个问题生成1-2个查询，总数不超过配置的上限
        max_queries = min(len(unanswered_questions) * 2, state.get("initial_search_query_count", 3))
        
        unanswered_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(unanswered_questions)])
        mode_instruction = f"""**针对性模式 (Targeted Mode):**
- 当前存在 {len(unanswered_questions)} 个未充分回答的研究问题
- 你的任务是**仅针对以下未回答问题**生成精准的搜索查询
- 每个问题生成 1-2 个查询，避免重复
- 查询应直接服务于回答这些具体问题
- 不要生成超出此清单范围的查询

未回答的问题清单：
{unanswered_text}
"""
    else:
        # 首次运行模式：基于完整研究计划生成初始查询
        logger.info(f"【节点: generate_query】运行模式: 首次（Initial）")
        initial_count = state.get("initial_search_query_count")
        if initial_count is None:
            initial_count = 3
            state["initial_search_query_count"] = initial_count
        logger.info(f"【节点: generate_query】初始搜索查询数量: {initial_count}")
        if research_plan:
            logger.info(f"【节点: generate_query】基于方案 '{research_plan.research_topic}' 生成查询")
        
        max_queries = initial_count
        mode_instruction = """**首次运行模式 (Initial Mode):**
- 这是第一次生成搜索查询
- 请基于完整的研究计划 (Research Plan) 生成多样化的初始查询
- 查询应覆盖研究计划中的各个子主题和关键问题
- Always prefer a single search query, only add another query if the original question requests multiple aspects or elements and one query is not enough.
- Each query should focus on one specific aspect of the original question.
- Queries should be diverse, if the topic is broad, generate more than 1 query.
- Don't generate multiple similar queries, 1 is enough.
"""
    
    logger.info(f"【节点: generate_query】目标查询数量: {max_queries}")
    logger.info(f"【节点: generate_query】研究主题: {research_topic[:200]}...")
    
    formatted_prompt = query_writer_instructions.format(
        current_date=get_current_date(),
        research_topic=research_topic,
        research_plan=plan_str,
        mode_instruction=mode_instruction,
        number_queries=max_queries,
    )
    
    logger.info(f"【节点: generate_query】调用 LLM 生成查询...")
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="generate_query",
        gemini_model=reasoning_model,
        temperature=1.0,
        structured_output_type=SearchQueryList,
        connection_id=connection_id
    )
    # 返回后再次检查取消，避免后续日志继续输出
    check_cancellation_and_raise(connection_id)
    
    query_count = len(result.query) if result.query else 0
    logger.info(f"【节点: generate_query】成功生成 {query_count} 个搜索查询")
    for idx, query_item in enumerate(result.query[:5], 1):  # 只记录前5个
        logger.info(f"【节点: generate_query】  查询 {idx}: {query_item[:100]}...")
    
    # 返回两个字段：search_query 用于累积（历史记录），new_search_query 用于本轮执行
    return {"search_query": result.query, "new_search_query": result.query}


def continue_to_web_research(state: QueryGenerationState):
    # 只处理本轮新生成的查询，避免重复执行历史查询
    new_queries = state.get("new_search_query", [])
    query_count = len(new_queries)
    logger.info(f"【节点: continue_to_web_research】准备分发 {query_count} 个搜索任务到 web_research 节点")
    return [
        Send("web_research", {"search_query": search_query, "id": int(idx)})
        for idx, search_query in enumerate(new_queries)
    ]


async def bocha_web_search(query: str, count: int = 10) -> Dict[str, Any]:
    """
    使用博查搜索 API 进行网页搜索（异步版本）。

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
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=data)
        
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


async def web_research(state: WebSearchState, config: RunnableConfig) -> OverallState:
    """
    使用博查搜索 API 进行网页研究，并进行深度抓取和正文提取（异步版本）。
    """
    # 获取connection_id用于取消检查
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    # 检查取消状态
    check_cancellation_and_raise(connection_id)
    
    search_query = state["search_query"]
    search_id = state["id"]
    
    logger.info(f"【节点: web_research】开始执行搜索任务 ID={search_id}")
    logger.info(f"【节点: web_research】搜索查询: {search_query[:200]}...")
    
    # 调用博查搜索 API（异步）
    logger.info(f"【节点: web_research】调用博查搜索 API...")
    search_result = await bocha_web_search(query=search_query, count=10)
    
    webpages = search_result.get("webpages", [])
    formatted_text = search_result.get("formatted_text", "")
    
    webpage_count = len(webpages) if webpages else 0
    logger.info(f"【节点: web_research】搜索完成，找到 {webpage_count} 个网页结果")
    
    if webpage_count > 0:
        logger.info(f"【节点: web_research】前3个结果标题:")
        for idx, page in enumerate(webpages[:3], 1):
            logger.info(f"【节点: web_research】  {idx}. {page.get('name', 'N/A')[:100]}")
    
    # ========== 深度抓取逻辑开始 ==========
    
    # 选取 Top-K 网页进行深度抓取
    top_k = min(settings.WEB_SCRAPE_TOP_K, len(webpages))
    top_pages = webpages[:top_k]
    top_urls = [p.get("url") for p in top_pages if p.get("url")]
    
    logger.info(f"【节点: web_research】准备深度抓取 Top-{top_k} 网页...")
    
    # 并发抓取网页并提取正文
    deep_docs = []
    if top_urls:
        try:
            scraped_results = await scrape_webpages(
                urls=top_urls,
                timeout=settings.WEB_SCRAPE_TIMEOUT,
                concurrency=settings.WEB_SCRAPE_CONCURRENCY,
                max_per_doc_chars=settings.WEB_SCRAPE_MAX_PER_DOC_CHARS,
                user_agent=settings.WEB_SCRAPE_USER_AGENT,
            )
            
            # 组装深度文档列表（保持编号与 top_pages 一致）
            url_to_text = {url: text for url, text in scraped_results}
            
            for i, page in enumerate(top_pages, start=1):
                url = page.get("url", "")
                if url in url_to_text:
                    title = page.get("name", f"来源{i}")
                    text = url_to_text[url]
                    deep_docs.append((i, title, url, text))
            
            logger.info(f"【节点: web_research】成功深度抓取 {len(deep_docs)}/{top_k} 个网页")
            
        except Exception as e:
            logger.error(f"【节点: web_research】深度抓取失败: {e}", exc_info=True)
    
    # 构建 LLM 上下文
    context_for_llm = ""
    
    if deep_docs:
        # 使用深度抓取的正文作为上下文
        deep_context_parts = []
        for idx, title, url, text in deep_docs:
            deep_context_parts.append(
                f"[{idx}] 标题: {title}\n"
                f"URL: {url}\n"
                f"正文:\n{text}\n"
                f"---"
            )
        deep_context = "\n".join(deep_context_parts)
        
        # 控制总长度
        deep_context = clean_and_truncate(
            deep_context, 
            settings.WEB_SCRAPE_MAX_TOTAL_CHARS
        )
        context_for_llm = deep_context
        
        logger.info(
            f"【节点: web_research】使用深度正文作为上下文，"
            f"总长度: {len(context_for_llm)} 字符"
        )
    else:
        # 回退到博查搜索的摘要
        context_for_llm = formatted_text
        logger.warning(
            f"【节点: web_research】深度抓取失败或无结果，"
            f"回退使用博查搜索摘要"
        )
    
    # ========== 深度抓取逻辑结束 ==========
    
    # 使用 Gemini 对搜索结果进行总结和整理
    logger.info(f"【节点: web_research】开始使用 LLM 总结搜索结果...")
    formatted_prompt = web_searcher_instructions.format(
        current_date=get_current_date(),
        research_topic=search_query,
    )

    # 将搜索结果添加到提示词中，并提示 LLM 使用引用编号
    search_context = (
        f"\n\n搜索查询: {search_query}\n"
        f"仅基于以下网页正文内容进行严谨总结，并在每条事实后使用 [编号] 标注来源：\n"
        f"{context_for_llm}"
    )
    full_prompt = formatted_prompt + search_context

    logger.info(f"【节点: web_research】调用 LLM API，提示词长度: {len(full_prompt)} 字符")
    llm_response = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(full_prompt),
        node_name="web_research",
        gemini_model=settings.GEMINI_MODEL,
        temperature=0,
        connection_id=connection_id
    )
    logger.info(f"【节点: web_research】LLM 总结完成，响应长度: {len(llm_response.content)} 字符")
    
    # 处理引用和来源
    logger.info(f"【节点: web_research】开始处理引用和来源...")
    
    # 如果有深度抓取的结果，使用 top_pages；否则使用全部 webpages
    pages_for_citation = top_pages if deep_docs else webpages
    
    resolved_urls = resolve_urls(pages_for_citation, search_id)
    citations = get_citations_from_bocha(
        pages_for_citation, 
        resolved_urls, 
        llm_response.content
    )
    modified_text = insert_citation_markers(llm_response.content, citations)
    
    # sources_gathered: 仅包含深度抓取的来源（用于引用）
    sources_gathered = [
        item for citation in citations 
        for item in citation["segments"]
    ]
    
    # all_sources_gathered: 包含所有搜索到的来源（包括非 top-k）
    all_resolved_urls = resolve_urls(webpages, search_id)
    all_sources = []
    for page in webpages:
        url = page.get("url", "")
        if url:
            title = page.get("name", "")
            site_name = page.get("siteName", "")
            all_sources.append({
                "label": title[:50] if title else site_name[:50] if site_name else "来源",
                "shortUrl": all_resolved_urls.get(url, url),
                "value": url,
            })
    
    logger.info(
        f"【节点: web_research】处理完成，"
        f"生成 {len(citations)} 个引用，"
        f"{len(sources_gathered)} 个深度来源，"
        f"{len(all_sources)} 个候选来源"
    )
    logger.info(f"【节点: web_research】搜索任务 ID={search_id} 完成")

    return {
        "sources_gathered": sources_gathered,
        "all_sources_gathered": all_sources,  # 保存所有搜索到的资源
        "search_query": [search_query],
        "web_research_result": [modified_text],
    }


async def reflection(state: OverallState, config: RunnableConfig) -> ReflectionState:
    # 获取connection_id用于取消检查
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    # 检查取消状态
    check_cancellation_and_raise(connection_id)
    
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    loop_count = state["research_loop_count"]
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    logger.info(f"【节点: reflection】开始反思，研究循环次数: {loop_count}")
    logger.info(f"【节点: reflection】使用模型: {reasoning_model}")
    
    web_research_results = state.get("web_research_result", [])
    search_queries = state.get("search_query", [])
    logger.info(f"【节点: reflection】当前已有 {len(web_research_results)} 个搜索结果，{len(search_queries)} 个搜索查询")

    # 获取研究计划并格式化
    research_plan = state.get("research_plan")
    plan_str = "无特定研究计划"
    if research_plan:
        plan_str = f"研究主题: {research_plan.research_topic}\n\n"
        plan_str += "子主题:\n"
        for i, sub_topic in enumerate(research_plan.sub_topics, 1):
            plan_str += f"{i}. {sub_topic}\n"
        plan_str += "\n研究问题 (Research Questions):\n"
        for i, question in enumerate(research_plan.research_questions, 1):
            plan_str += f"{i}. {question}\n"
        plan_str += f"\n理由: {research_plan.rationale}"
        logger.info(f"【节点: reflection】使用研究计划进行对照评估，包含 {len(research_plan.research_questions)} 个问题")

    formatted_prompt = reflection_instructions.format(
        research_topic=get_research_topic(state["messages"]),
        research_plan=plan_str,
        loop_count=loop_count,
        summaries="\n\n---\n\n".join(state["web_research_result"]),
    )
    
    logger.info("【节点: reflection】调用 LLM 进行反思评估（对照研究计划）...")
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="reflection",
        gemini_model=reasoning_model,
        temperature=1.0,
        structured_output_type=Reflection,
        connection_id=connection_id
    )

    logger.info(f"【节点: reflection】=== 信息充足性评估结果 ===")
    logger.info(f"【节点: reflection】  当前循环: 第 {loop_count} 轮")
    logger.info(f"【节点: reflection】  信息是否充足: {result.is_sufficient}")
    
    if result.is_sufficient:
        logger.info(f"【节点: reflection】  ✅ 评估结果: 信息已充足，可以开始生成报告")
    else:
        logger.info(f"【节点: reflection】  ⚠️  评估结果: 信息不足，需要继续研究")
        logger.info(f"【节点: reflection】  知识缺口: {result.knowledge_gap[:200] if result.knowledge_gap else 'N/A'}...")
        unanswered_count = len(result.unanswered_questions) if result.unanswered_questions else 0
        logger.info(f"【节点: reflection】  未回答问题数量: {unanswered_count}")
        if unanswered_count > 0:
            for idx, question in enumerate(result.unanswered_questions[:3], 1):  # 只记录前3个
                logger.info(f"【节点: reflection】    未回答问题 {idx}: {question[:100]}...")

    return {
        "is_sufficient": result.is_sufficient,
        "knowledge_gap": result.knowledge_gap,
        "unanswered_questions": result.unanswered_questions,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
        "max_research_loops": state.get("max_research_loops", 5),  # 传递最大循环次数，默认5
    }


def evaluate_research(state: ReflectionState, config: RunnableConfig) -> str:
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
        unanswered_questions = state.get("unanswered_questions", [])
        unanswered_count = len(unanswered_questions)
        logger.info(f"【节点: evaluate_research】🔄 决策: 信息不足，继续第 {loop_count + 1} 轮调查")
        logger.info(f"【节点: evaluate_research】➡️  下一步: 生成针对 {unanswered_count} 个未回答问题的新查询")
        return "generate_query"


async def assess_content_quality(state: OverallState, config: RunnableConfig):
    """内容质量评估节点。"""
    # 获取connection_id用于取消检查
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    # 检查取消状态
    check_cancellation_and_raise(connection_id)
    
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
    
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="assess_content_quality",
        gemini_model=reasoning_model,
        temperature=0.3,
        structured_output_type=ContentQualityAssessment,
        connection_id=connection_id
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


async def verify_facts(state: OverallState, config: RunnableConfig):
    """事实验证节点。"""
    # 获取connection_id用于取消检查
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    # 检查取消状态
    check_cancellation_and_raise(connection_id)
    
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
    
    async def ainvoke_with_method(llm: ChatOpenAI):
        """异步调用带 method 参数的 structured_output."""
        structured_llm = llm.with_structured_output(
            FactVerification,
            method="json_schema",
            include_raw=False
        )
        return await structured_llm.ainvoke(formatted_prompt)
    
    result = await invoke_llm_with_fallback(
        invoke_func=ainvoke_with_method,
        node_name="verify_facts",
        gemini_model=reasoning_model,
        temperature=0.1,
        connection_id=connection_id
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


async def assess_relevance(state: OverallState, config: RunnableConfig):
    """相关性评估节点。"""
    # 获取connection_id用于取消检查
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    # 检查取消状态
    check_cancellation_and_raise(connection_id)
    
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
    
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="assess_relevance",
        gemini_model=reasoning_model,
        temperature=0.2,
        structured_output_type=RelevanceAssessment,
        connection_id=connection_id
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


async def optimize_summary(state: OverallState, config: RunnableConfig):
    """摘要优化节点。"""
    # 获取connection_id用于取消检查
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    # 检查取消状态
    check_cancellation_and_raise(connection_id)
    
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
    
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="optimize_summary",
        gemini_model=reasoning_model,
        temperature=0.3,
        structured_output_type=SummaryOptimization,
        connection_id=connection_id
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


async def generate_verification_report(state: OverallState, config: RunnableConfig):
    """生成综合验证报告节点。"""
    # 获取connection_id用于取消检查
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    # 检查取消状态
    check_cancellation_and_raise(connection_id)
    
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


async def finalize_answer(state: OverallState, config: RunnableConfig):
    """生成最终答案，返回高度围绕用户提问的调查研究报告。"""
    # 获取connection_id用于取消检查
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    # 检查取消状态
    check_cancellation_and_raise(connection_id)
    
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
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="finalize_answer",
        gemini_model=reasoning_model,
        temperature=0.2,
        connection_id=connection_id
    )
    final_report = result.content  # 这就是纯 Markdown 报告
    
    logger.info(f"【节点: finalize_answer】LLM 生成完成，报告长度: {len(final_report)} 字符")
    
    # 处理数据源引用（改进版：扫描引用编号并生成参考来源列表）
    logger.info("【节点: finalize_answer】处理数据源引用...")
    import re
    
    # 1. 扫描报告中的所有引用编号 [1], [2], [3] 等
    citation_pattern = re.compile(r'\[(\d+)\]')
    found_citations = set(citation_pattern.findall(final_report))
    logger.info(f"【节点: finalize_answer】扫描到 {len(found_citations)} 个引用编号: {sorted(found_citations, key=int)}")
    
    # 2. 将 shortUrl 替换为实际 URL
    enhanced_content = final_report
    for source in sources_gathered:
        if source["shortUrl"] in enhanced_content:
            enhanced_content = enhanced_content.replace(source["shortUrl"], source["value"])
    
    # 3. 构建引用编号到来源的映射（基于顺序）
    citation_to_source = {}
    unique_sources: List[Dict[str, Any]] = []
    
    # 按引用编号排序来源（基于 shortUrl 中的编号）
    def extract_citation_num(source: Dict[str, Any]) -> int:
        """从 shortUrl 中提取引用编号"""
        short_url = source.get("shortUrl", "")
        # shortUrl 格式: https://vertexaisearch.cloud.google.com/id/{search_id}-{idx}
        match = re.search(r'/id/\d+-(\d+)$', short_url)
        if match:
            return int(match.group(1))
        return 999999  # 如果无法提取，放到最后
    
    # 按照引用编号排序来源
    sorted_sources = sorted(sources_gathered, key=extract_citation_num)
    
    # 为每个来源分配引用编号（从1开始）
    for idx, source in enumerate(sorted_sources, start=1):
        citation_num = str(idx)
        citation_to_source[citation_num] = source
        unique_sources.append(source)
    
    logger.info(f"【节点: finalize_answer】共有 {len(unique_sources)} 个数据源")
    
    # 4. 在报告末尾添加"参考来源"列表（如果报告中有引用编号）
    if found_citations:
        logger.info("【节点: finalize_answer】在报告末尾添加参考来源列表...")
        
        # 检查报告是否已有"参考来源"、"引用"、"来源" 等标题
        has_references = bool(re.search(r'#+\s*(参考来源|引用|来源|参考资料|References)', enhanced_content, re.IGNORECASE))
        
        if not has_references:
            # 如果没有，添加参考来源列表
            enhanced_content += "\n\n---\n\n## 参考来源\n\n"
            
            # 按引用编号排序
            sorted_citations = sorted([int(c) for c in found_citations])
            
            for citation_num in sorted_citations:
                citation_str = str(citation_num)
                if citation_str in citation_to_source:
                    source = citation_to_source[citation_str]
                    label = source.get("label", f"来源 {citation_num}")
                    url = source.get("value", "")
                    enhanced_content += f"{citation_num}. [{label}]({url})\n"
                else:
                    # 引用编号在报告中存在，但没有对应的来源
                    logger.warning(f"【节点: finalize_answer】引用编号 [{citation_num}] 没有对应的来源")
                    enhanced_content += f"{citation_num}. 来源未找到\n"
            
            logger.info(f"【节点: finalize_answer】已添加 {len(sorted_citations)} 个参考来源")
        else:
            logger.info("【节点: finalize_answer】报告已包含参考来源部分，跳过添加")
    else:
        logger.info("【节点: finalize_answer】报告中未找到引用编号，跳过添加参考来源列表")
    
    logger.info(f"【节点: finalize_answer】最终答案包含 {len(unique_sources)} 个数据源")
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
_builder.add_conditional_edges("reflection", evaluate_research, ["generate_query", "assess_content_quality"])

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


