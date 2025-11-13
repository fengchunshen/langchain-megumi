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
from app.core.logger import jinfo, jdebug, jwarn, jerror

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

_connection_degradations: Dict[str, bool] = {}
_degradations_lock = asyncio.Lock()

_connection_cancellations: Dict[str, asyncio.Event] = {}
_cancellations_lock = asyncio.Lock()


async def reset_degradation_status(connection_id: Optional[str] = None):
    """
    重置降级状态（用于测试或新请求开始时）.
    
    Args:
        connection_id: 连接ID，如果提供则只重置该连接的降级状态；如果为None则重置所有连接
    """
    global _connection_degradations
    async with _degradations_lock:
        if connection_id:
            if connection_id in _connection_degradations:
                del _connection_degradations[connection_id]
                jinfo(logger, "连接已重置，准备重试 Gemini", 分类="连接降级恢复", 连接ID=connection_id)
        else:
            _connection_degradations.clear()
            jinfo(logger, "所有连接已重置，准备重试 Gemini", 分类="连接降级恢复(全部)")


async def is_connection_degraded(connection_id: Optional[str] = None) -> bool:
    """
    检查连接是否已降级到 Qwen3Max.
    
    Args:
        connection_id: 连接ID，如果为None则返回False（未降级）
        
    Returns:
        bool: 如果连接已降级返回True，否则返回False
    """
    if not connection_id:
        return False
    async with _degradations_lock:
        return _connection_degradations.get(connection_id, False)


async def set_connection_degraded(connection_id: Optional[str] = None):
    """
    设置连接为已降级状态.
    
    Args:
        connection_id: 连接ID，如果为None则不执行任何操作
    """
    if not connection_id:
        return
    async with _degradations_lock:
        _connection_degradations[connection_id] = True
        jwarn(logger, "连接已标记为降级，切换至 Qwen3Max", 分类="连接降级", 连接ID=connection_id)


async def set_connection_cancelled(connection_id: str):
    """标记连接为已取消."""
    global _connection_cancellations
    async with _cancellations_lock:
        event = _connection_cancellations.get(connection_id)
        if event is None:
            event = asyncio.Event()
            _connection_cancellations[connection_id] = event
        event.set()
    jinfo(logger, "连接已标记为取消", 分类="取消连接", 连接ID=connection_id)


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
    jinfo(logger, "连接状态已清理", 分类="取消清理", 连接ID=connection_id)


def check_cancellation_and_raise(connection_id: Optional[str] = None):
    """检查取消状态，如果被取消则抛出CancelledError."""
    if connection_id and is_connection_cancelled(connection_id):
        jinfo(logger, "检测到连接已取消，停止执行", 分类="取消检查", 连接ID=connection_id)
        raise asyncio.CancelledError(f"连接 {connection_id} 已被取消")


def get_qwen_base_url() -> str:
    """获取 Qwen3Max API base URL."""
    base_url = settings.DASHSCOPE_BASE_URL
    if not base_url:
        raise ValueError("DASHSCOPE_BASE_URL is not set")
    base_url = base_url.rstrip('/')
    if not base_url.endswith('/v1'):
        base_url = f"{base_url}/v1"
    jdebug(logger, "Qwen3Max API 基础地址", 分类="模型配置", 基础地址=base_url)
    return base_url


def get_gemini_base_url() -> str:
    """获取 Gemini API base URL，确保以 /v1 结尾"""
    base_url = settings.GEMINI_API_URL
    if not base_url:
        raise ValueError("GEMINI_API_URL is not set")
    base_url = base_url.rstrip('/')
    if not base_url.endswith('/v1'):
        base_url = f"{base_url}/v1"
    jdebug(logger, "Gemini API 基础地址", 分类="模型配置", 基础地址=base_url)
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
        jdebug(logger, "创建 Gemini LLM 实例", 分类="模型实例化", 模型=model)
    else:
        base_url = get_qwen_base_url()
        api_key = settings.DASHSCOPE_API_KEY
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY is not set")
        jdebug(logger, "创建 Qwen3Max LLM 实例", 分类="模型实例化", 模型=model)
    
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
    
    如果该连接已经降级到 Qwen3Max，直接使用 Qwen3Max，不再尝试 Gemini。
    否则先尝试使用 Gemini（重试2次），如果失败则切换到 Qwen3Max，并设置该连接的降级标志。
    
    Args:
        invoke_func: 异步调用函数，接受一个参数（llm 实例）并返回结果（支持同步和异步函数）
        node_name: 节点名称（用于日志）
        gemini_model: Gemini 模型名称
        temperature: 温度参数
        qwen_model: Qwen3Max 模型名称（默认使用配置中的 DASHSCOPE_CHAT_MODEL）
        structured_output_type: 结构化输出类型（如果提供，会自动调用 with_structured_output）
        connection_id: 连接ID，用于取消检查和降级状态管理
        **llm_kwargs: 传递给 ChatOpenAI 的其他参数
        
    Returns:
        调用结果
        
    Raises:
        Exception: 如果两种模型都失败，抛出最后一个异常
        asyncio.CancelledError: 如果连接被取消
    """
    check_cancellation_and_raise(connection_id)
    
    if qwen_model is None:
        qwen_model = settings.DASHSCOPE_CHAT_MODEL
    
    is_degraded = await is_connection_degraded(connection_id)
    
    if is_degraded:
        jinfo(logger, "节点降级，改用 Qwen3Max", 分类="模型降级", 节点=node_name, 备用模型=qwen_model)
        try:
            check_cancellation_and_raise(connection_id)
            
            llm = create_llm_with_fallback(
                model=qwen_model,
                temperature=temperature,
                use_gemini=False,
                max_retries=2
            )
            
            if structured_output_type is not None:
                llm = llm.with_structured_output(structured_output_type)
            
            _maybe = invoke_func(llm)
            result = await _maybe if inspect.isawaitable(_maybe) else _maybe
            
            check_cancellation_and_raise(connection_id)
            jinfo(logger, "Qwen3Max 调用成功", 分类="模型调用成功", 节点=node_name)
            return result
        except Exception as e:
            jerror(logger, "Qwen3Max 调用失败", 分类="模型调用失败", 节点=node_name, 错误=str(e))
            raise e
    
    last_error = None
    for attempt in range(2):
        try:
            check_cancellation_and_raise(connection_id)
            
            base_url = get_gemini_base_url()
            api_key = settings.GEMINI_API_KEY
            jinfo(logger, "尝试调用 Gemini", 分类="模型切换", 节点=node_name, 模型=gemini_model)
            
            llm = ChatOpenAI(
                model=gemini_model,
                temperature=temperature,
                api_key=api_key,
                base_url=base_url,
                timeout=settings.API_TIMEOUT,
                max_retries=1,
                **llm_kwargs
            )
            
            if structured_output_type is not None:
                llm = llm.with_structured_output(structured_output_type)
            
            jinfo(logger, "Gemini 调用开始", 分类="模型调用开始", 节点=node_name)
            
            _maybe = invoke_func(llm)
            result = await _maybe if inspect.isawaitable(_maybe) else _maybe
            
            check_cancellation_and_raise(connection_id)
            jinfo(logger, "Gemini 调用成功", 分类="模型调用成功", 节点=node_name)
            return result
            
        except Exception as e:
            last_error = e
            jwarn(logger, "Gemini 调用失败", 分类="模型调用失败", 节点=node_name, 尝试次数=attempt + 1, 最大次数=2, 错误=str(e))
            
            if attempt == 0:
                jinfo(logger, "Gemini 第一次重试", 分类="模型重试", 节点=node_name, 重试次数=1)
                check_cancellation_and_raise(connection_id)
            else:
                jwarn(logger, "Gemini 持续失败，切换至 Qwen3Max", 分类="模型切换", 节点=node_name, 备用模型=qwen_model)
                
                check_cancellation_and_raise(connection_id)
                
                await set_connection_degraded(connection_id)
                
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
    jerror(logger, "所有模型调用均失败", 分类="模型全部失败", 节点=node_name, 错误=str(last_error))
    raise last_error


class OverallState(TypedDict, total=False):
    messages: Annotated[List, add_messages]
    research_plan: Optional[ResearchPlan]
    search_query: Annotated[List, operator.add]  # 累积的查询（用于历史记录，存储中文查询用于前端展示）
    new_search_query: List[str]  # 本轮新生成的英文查询（用于实际搜索，不累加）
    new_search_query_zh: List[str]  # 本轮新生成的中文查询（用于前端展示，不累加）
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
    search_query: List[str]  # 累积的查询（用于历史记录，存储中文查询用于前端展示）
    new_search_query: List[str]  # 本轮新生成的英文查询（用于实际搜索，不累加）
    new_search_query_zh: List[str]  # 本轮新生成的中文查询（用于前端展示，不累加）


class WebSearchState(TypedDict):
    search_query: str
    id: str


async def generate_research_plan(state: OverallState, config: RunnableConfig) -> OverallState:
    """
    生成研究方案节点。
    """
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    jinfo(logger, "开始生成研究计划", 节点="生成研究计划")
    
    check_cancellation_and_raise(connection_id)
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    research_topic = get_research_topic(state["messages"])
    jinfo(logger, "研究主题", 节点="生成研究计划", 主题=research_topic[:200])
    
    formatted_prompt = research_plan_instructions.format(
        research_topic=research_topic
    )
    
    jinfo(logger, "调用 LLM 生成计划", 节点="生成研究计划")
    try:
        plan = await invoke_llm_with_fallback(
            invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
            node_name="generate_research_plan",
            gemini_model=reasoning_model,
            temperature=0.3,  # 从0.5降低到0.3，让输出更严谨详细
            structured_output_type=ResearchPlan,
            connection_id=connection_id
        )
        check_cancellation_and_raise(connection_id)
        jinfo(logger, "子主题数量", 节点="生成研究计划", 数量=len(plan.sub_topics))
        jinfo(logger, "研究问题数量", 节点="生成研究计划", 数量=len(plan.research_questions))
        for idx, sub_topic in enumerate(plan.sub_topics, 1):
            jinfo(logger, "子主题", 节点="生成研究计划", 序号=idx, 子主题=sub_topic)
        return {"research_plan": plan}
    except asyncio.CancelledError:
        jinfo(logger, "任务已取消，停止生成计划", 节点="生成研究计划")
        raise
    except Exception as e:
        jerror(logger, "生成研究计划失败", 节点="生成研究计划", 错误=str(e))
        return {"research_plan": None}


async def generate_query(state: OverallState, config: RunnableConfig) -> QueryGenerationState:
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    check_cancellation_and_raise(connection_id)
    
    jinfo(logger, "开始生成查询", 节点="生成查询")
    
    unanswered_questions = state.get("unanswered_questions", [])
    is_targeted_mode = len(unanswered_questions) > 0
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    jinfo(logger, "推理模型", 节点="生成查询", 模型=reasoning_model)
    
    research_topic = get_research_topic(state["messages"])
    research_plan = state.get("research_plan")
    
    plan_str = "无特定方案，请直接分析研究主题。"
    if research_plan and research_plan.sub_topics:
        plan_str = f"主题: {research_plan.research_topic}\n\n关键子主题和研究问题:\n"
        
        for i, sub_topic in enumerate(research_plan.sub_topics, 1):
            plan_str += f"\n{i}. {sub_topic}\n"
            plan_str += "   研究问题:\n"
            topic_questions = [q for q in research_plan.research_questions if q.startswith(f"{sub_topic}：")]
            if not topic_questions:
                topic_questions = [q for q in research_plan.research_questions if sub_topic in q]
            for j, question in enumerate(topic_questions, 1):
                question_text = question.split("：", 1)[-1] if "：" in question else question
                plan_str += f"   {i}.{j}. {question_text}\n"
        
        plan_str += f"\n理由: {research_plan.rationale}"
    
    if is_targeted_mode:
        jinfo(logger, "模式：针对未解问题", 节点="生成查询")
        jinfo(logger, "未解问题数量", 节点="生成查询", 数量=len(unanswered_questions))
        for idx, question in enumerate(unanswered_questions[:3], 1):
            jinfo(logger, "未解问题", 节点="生成查询", 序号=idx, 问题=question[:100])
        
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
        jinfo(logger, "模式：初始探索", 节点="生成查询")
        initial_count = state.get("initial_search_query_count")
        if initial_count is None:
            initial_count = 3
            state["initial_search_query_count"] = initial_count
        jinfo(logger, "初始查询数量", 节点="生成查询", 数量=initial_count)
        if research_plan:
            jinfo(logger, "基于研究计划生成查询", 节点="生成查询", 主题=research_plan.research_topic)
        
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
    
    jinfo(logger, "目标查询数量", 节点="生成查询", 数量=max_queries)
    jinfo(logger, "研究主题", 节点="生成查询", 主题=research_topic[:200])
    
    formatted_prompt = query_writer_instructions.format(
        current_date=get_current_date(),
        research_topic=research_topic,
        research_plan=plan_str,
        mode_instruction=mode_instruction,
        number_queries=max_queries,
    )
    
    jinfo(logger, "调用 LLM 生成查询", 节点="生成查询")
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="generate_query",
        gemini_model=reasoning_model,
        temperature=1.0,
        structured_output_type=SearchQueryList,
        connection_id=connection_id
    )
    check_cancellation_and_raise(connection_id)
    
    # 获取英文和中文查询
    english_queries = result.query if result.query else []
    chinese_queries = result.query_zh if result.query_zh else []
    
    # 如果中文查询为空或数量不匹配，使用英文查询作为后备
    if not chinese_queries or len(chinese_queries) != len(english_queries):
        jwarn(logger, "中文查询缺失或不匹配，使用英文查询作为后备", 节点="生成查询", 英文数量=len(english_queries), 中文数量=len(chinese_queries))
        chinese_queries = english_queries
    
    query_count = len(english_queries)
    jinfo(logger, "生成查询条数", 节点="生成查询", 数量=query_count)
    for idx, (en_query, zh_query) in enumerate(zip(english_queries[:5], chinese_queries[:5]), 1):  # 只记录前5个
        jinfo(logger, "查询样本", 节点="生成查询", 序号=idx, 英文查询=en_query[:100], 中文查询=zh_query[:100])
    
    # 返回三个字段：
    # - search_query: 累积的中文查询（用于前端展示和历史记录）
    # - new_search_query: 英文查询（用于实际搜索）
    # - new_search_query_zh: 中文查询（用于前端展示）
    return {
        "search_query": chinese_queries,  # 累积中文查询用于前端展示
        "new_search_query": english_queries,  # 英文查询用于实际搜索
        "new_search_query_zh": chinese_queries  # 中文查询用于前端展示
    }


def continue_to_web_research(state: QueryGenerationState):
    new_queries = state.get("new_search_query", [])
    query_count = len(new_queries)
    jinfo(logger, "分发到网络研究任务", 节点="继续到网络研究", 任务数量=query_count)
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
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    check_cancellation_and_raise(connection_id)
    
    search_query = state["search_query"]
    search_id = state["id"]
    
    jinfo(logger, "开始网络研究", 节点="网络研究", 任务ID=search_id)
    jinfo(logger, "研究查询", 节点="网络研究", 查询=search_query[:200])
    
    jinfo(logger, "调用博查搜索 API", 节点="网络研究")
    search_result = await bocha_web_search(query=search_query, count=10)
    
    webpages = search_result.get("webpages", [])
    formatted_text = search_result.get("formatted_text", "")
    
    webpage_count = len(webpages) if webpages else 0
    jinfo(logger, "搜索完成", 节点="网络研究", 网页数量=webpage_count)
    
    if webpage_count > 0:
        jinfo(logger, "Top3 标题", 节点="网络研究")
        for idx, page in enumerate(webpages[:3], 1):
            jinfo(logger, "标题", 节点="网络研究", 序号=idx, 标题=page.get("name", "N/A")[:100])
    
    top_k = min(settings.WEB_SCRAPE_TOP_K, len(webpages))
    top_pages = webpages[:top_k]
    top_urls = [p.get("url") for p in top_pages if p.get("url")]
    
    jinfo(logger, "深度抓取开始", 节点="网络研究", TopK=top_k)
    
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
            
            url_to_text = {url: text for url, text in scraped_results}
            
            for i, page in enumerate(top_pages, start=1):
                url = page.get("url", "")
                if url in url_to_text:
                    title = page.get("name", f"来源{i}")
                    text = url_to_text[url]
                    deep_docs.append((i, title, url, text))
            
            jinfo(logger, "深度抓取进度", 节点="网络研究", 已抓取=len(deep_docs), 目标=top_k)
            
        except Exception as e:
            jerror(logger, "深度抓取失败", 节点="网络研究", 错误=str(e))
    
    context_for_llm = ""
    
    if deep_docs:
        deep_context_parts = []
        for idx, title, url, text in deep_docs:
            deep_context_parts.append(
                f"[{idx}] 标题: {title}\n"
                f"URL: {url}\n"
                f"正文:\n{text}\n"
                f"---"
            )
        deep_context = "\n".join(deep_context_parts)
        
        deep_context = clean_and_truncate(
            deep_context, 
            settings.WEB_SCRAPE_MAX_TOTAL_CHARS
        )
        context_for_llm = deep_context
        
        jinfo(logger, "使用深度内容", 节点="网络研究", 内容长度=len(context_for_llm))
    else:
        context_for_llm = formatted_text
        jwarn(logger, "深度内容不可用，回退至博查摘要", 节点="网络研究")
    
    jinfo(logger, "使用 LLM 总结", 节点="网络研究")
    formatted_prompt = web_searcher_instructions.format(
        current_date=get_current_date(),
        research_topic=search_query,
    )

    search_context = (
        f"\n\n搜索查询: {search_query}\n"
        f"仅基于以下网页正文内容进行严谨总结，并在每条事实后使用 [编号] 标注来源：\n"
        f"{context_for_llm}"
    )
    full_prompt = formatted_prompt + search_context

    jinfo(logger, "LLM 提示长度", 节点="网络研究", 长度=len(full_prompt))
    llm_response = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(full_prompt),
        node_name="web_research",
        gemini_model=settings.GEMINI_MODEL,
        temperature=0,
        connection_id=connection_id
    )
    jinfo(logger, "LLM 摘要长度", 节点="网络研究", 长度=len(llm_response.content))
    
    jinfo(logger, "处理引文与来源", 节点="网络研究")
    
    pages_for_citation = top_pages if deep_docs else webpages
    
    resolved_urls = resolve_urls(pages_for_citation, search_id)
    citations = get_citations_from_bocha(
        pages_for_citation, 
        resolved_urls, 
        llm_response.content
    )
    modified_text = insert_citation_markers(llm_response.content, citations)
    
    sources_gathered = [
        item for citation in citations 
        for item in citation["segments"]
    ]
    
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
    
    jinfo(logger, "处理完成", 节点="网络研究", 引文数量=len(citations), 深度来源数量=len(sources_gathered), 全部来源数量=len(all_sources))
    jinfo(logger, "任务完成", 节点="网络研究", 任务ID=search_id)

    return {
        "sources_gathered": sources_gathered,
        "all_sources_gathered": all_sources,
        "search_query": [search_query],
        "web_research_result": [modified_text],
    }


async def reflection(state: OverallState, config: RunnableConfig) -> ReflectionState:
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    check_cancellation_and_raise(connection_id)
    
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    loop_count = state["research_loop_count"]
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    jinfo(logger, "开始反思评估", 节点="反思", 循环次数=loop_count)
    jinfo(logger, "推理模型", 节点="反思", 模型=reasoning_model)
    
    web_research_results = state.get("web_research_result", [])
    search_queries = state.get("search_query", [])
    jinfo(logger, "输入规模", 节点="反思", 研究结果=len(web_research_results), 查询数量=len(search_queries))

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
        jinfo(logger, "使用研究计划", 节点="反思", 问题数量=len(research_plan.research_questions))

    formatted_prompt = reflection_instructions.format(
        research_topic=get_research_topic(state["messages"]),
        research_plan=plan_str,
        loop_count=loop_count,
        summaries="\n\n---\n\n".join(state["web_research_result"]),
    )
    
    jinfo(logger, "调用 LLM 进行充分性评估", 节点="反思")
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="reflection",
        gemini_model=reasoning_model,
        temperature=1.0,
        structured_output_type=Reflection,
        connection_id=connection_id
    )

    jinfo(logger, "充分性评估完成", 节点="反思")
    jinfo(logger, "循环计数", 节点="反思", 当前循环=loop_count)
    jinfo(logger, "是否充分", 节点="反思", 充分=result.is_sufficient)
    jinfo(logger, "知识缺口", 节点="反思", 缺口=(result.knowledge_gap[:200] if result.knowledge_gap else "N/A"))
    unanswered_count = len(result.unanswered_questions) if result.unanswered_questions else 0
    jinfo(logger, "未解问题数量", 节点="反思", 数量=unanswered_count)
    if unanswered_count > 0:
        for idx, question in enumerate(result.unanswered_questions[:3], 1):  # 只记录前3个
            jinfo(logger, "未解问题", 节点="反思", 序号=idx, 问题=question[:100])

    return {
        "is_sufficient": result.is_sufficient,
        "knowledge_gap": result.knowledge_gap,
        "unanswered_questions": result.unanswered_questions,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
        "max_research_loops": state.get("max_research_loops", 5),
    }


def evaluate_research(state: ReflectionState, config: RunnableConfig) -> str:
    max_research_loops = state.get("max_research_loops", 5)
    loop_count = state["research_loop_count"]
    is_sufficient = state["is_sufficient"]
    
    jinfo(logger, "做出研究循环决策", 节点="评估研究")
    jinfo(logger, "循环进度", 节点="评估研究", 当前循环=loop_count, 最大循环=max_research_loops)
    jinfo(logger, "是否充分", 节点="评估研究", 充分=is_sufficient)
    
    if state["is_sufficient"]:
        jinfo(logger, "进入质量评估与报告阶段", 节点="评估研究")
        return "assess_content_quality"
    elif state["research_loop_count"] >= max_research_loops:
        jinfo(logger, "达到最大循环次数，进入报告阶段", 节点="评估研究", 最大循环=max_research_loops)
        return "assess_content_quality"
    else:
        unanswered_questions = state.get("unanswered_questions", [])
        unanswered_count = len(unanswered_questions)
        jinfo(logger, "尚未充分，继续下一循环", 节点="评估研究", 下次循环=loop_count + 1)
        jinfo(logger, "为未解问题生成查询", 节点="评估研究", 未解问题数量=unanswered_count)
        return "generate_query"


async def assess_content_quality(state: OverallState, config: RunnableConfig):
    """内容质量评估节点。"""
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    check_cancellation_and_raise(connection_id)
    
    jinfo(logger, "开始内容质量评估", 节点="评估内容质量")
    
    combined_content = "\n\n---\n\n".join(state.get("web_research_result", []))
    
    formatted_prompt = content_quality_instructions.format(
        research_topic=get_research_topic(state["messages"]),
        content=combined_content
    )
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    jinfo(logger, "推理模型", 节点="评估内容质量", 模型=reasoning_model)
    
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="assess_content_quality",
        gemini_model=reasoning_model,
        temperature=0.3,
        structured_output_type=ContentQualityAssessment,
        connection_id=connection_id
    )
    
    jinfo(logger, "质量评分", 节点="评估内容质量", 分数=result.quality_score)
    jinfo(logger, "内容缺口数量", 节点="评估内容质量", 数量=len(result.content_gaps))
    
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
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    check_cancellation_and_raise(connection_id)
    
    jinfo(logger, "开始事实核验", 节点="事实核验")
    
    combined_content = "\n\n---\n\n".join(state.get("web_research_result", []))
    
    current_date = get_current_date()
    formatted_prompt = fact_verification_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        content=combined_content
    )
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    jinfo(logger, "推理模型", 节点="事实核验", 模型=reasoning_model)
    
    async def ainvoke_with_method(llm: ChatOpenAI):
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
    
    jinfo(logger, "可信度评分", 节点="事实核验", 分数=result.confidence_score)
    jinfo(logger, "已核事实数量", 节点="事实核验", 数量=len(result.verified_facts_text))
    jinfo(logger, "存疑陈述数量", 节点="事实核验", 数量=len(result.disputed_claims_text))
    
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
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    check_cancellation_and_raise(connection_id)
    
    jinfo(logger, "开始相关性评估", 节点="评估相关性")
    
    combined_content = "\n\n---\n\n".join(state.get("web_research_result", []))
    
    formatted_prompt = relevance_assessment_instructions.format(
        research_topic=get_research_topic(state["messages"]),
        content=combined_content
    )
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    jinfo(logger, "推理模型", 节点="评估相关性", 模型=reasoning_model)
    
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="assess_relevance",
        gemini_model=reasoning_model,
        temperature=0.2,
        structured_output_type=RelevanceAssessment,
        connection_id=connection_id
    )
    
    jinfo(logger, "相关性得分", 节点="评估相关性", 分数=result.relevance_score)
    jinfo(logger, "覆盖主题数量", 节点="评估相关性", 数量=len(result.key_topics_covered))
    jinfo(logger, "缺失主题数量", 节点="评估相关性", 数量=len(result.missing_topics))
    
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
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    check_cancellation_and_raise(connection_id)
    
    jinfo(logger, "开始优化总结", 节点="优化总结")
    
    original_summary = "\n\n---\n\n".join(state.get("web_research_result", []))
    
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
    
    jinfo(logger, "推理模型", 节点="优化总结", 模型=reasoning_model)
    
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="optimize_summary",
        gemini_model=reasoning_model,
        temperature=0.3,
        structured_output_type=SummaryOptimization,
        connection_id=connection_id
    )
    
    quality_score = state.get("content_quality", {}).get("quality_score", 0.5)
    fact_confidence = state.get("fact_verification", {}).get("confidence_score", 0.5)
    relevance_score = state.get("relevance_assessment", {}).get("relevance_score", 0.5)
    final_confidence = (quality_score + fact_confidence + relevance_score) / 3
    
    jinfo(logger, "关键洞见数量", 节点="优化总结", 数量=len(result.key_insights))
    jinfo(logger, "可执行项数量", 节点="优化总结", 数量=len(result.actionable_items))
    jinfo(logger, "模型自信度", 节点="优化总结", 自信度=result.confidence_level)
    jinfo(logger, "综合自信度", 节点="优化总结", 自信度=round(final_confidence, 3))
    
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
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    check_cancellation_and_raise(connection_id)
    
    jinfo(logger, "开始生成核验报告", 节点="生成核验报告")
    
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
    
    jinfo(logger, "核验报告生成完成", 节点="生成核验报告")
    
    return {
        "verification_report": report
    }


async def finalize_answer(state: OverallState, config: RunnableConfig):
    """生成最终答案，返回高度围绕用户提问的调查研究报告。"""
    connection_id = None
    if config:
        if hasattr(config, 'configurable') and config.configurable:
            connection_id = config.configurable.get("connection_id")
        elif isinstance(config, dict):
            connection_id = config.get("configurable", {}).get("connection_id")
    
    check_cancellation_and_raise(connection_id)
    
    reasoning_model = state.get("reasoning_model") or settings.GEMINI_MODEL
    
    jinfo(logger, "开始生成最终答复", 节点="生成最终答复")
    jinfo(logger, "推理模型", 节点="生成最终答复", 模型=reasoning_model)
    
    web_research_results = state.get("web_research_result", [])
    sources_gathered = state.get("sources_gathered", [])
    jinfo(logger, "输入规模", 节点="生成最终答复", 研究结果=len(web_research_results), 来源数量=len(sources_gathered))

    summaries = "\n---\n\n".join(web_research_results)
    
    optimization_data = state.get("summary_optimization", {})
    key_insights = optimization_data.get("key_insights", [])
    actionable_items = optimization_data.get("actionable_items", [])
    
    jinfo(logger, "关键洞见数量", 节点="生成最终答复", 数量=len(key_insights))
    jinfo(logger, "可执行项数量", 节点="生成最终答复", 数量=len(actionable_items))
    
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
    
    formatted_prompt = answer_instructions.format(
        current_date=get_current_date(),
        research_topic=get_research_topic(state["messages"]),
        summaries=summaries + prompt_enhancement
    )
    
    jinfo(logger, "调用 LLM 生成报告", 节点="生成最终答复")
    
    result = await invoke_llm_with_fallback(
        invoke_func=lambda llm: llm.ainvoke(formatted_prompt),
        node_name="finalize_answer",
        gemini_model=reasoning_model,
        temperature=0.2,
        connection_id=connection_id
    )
    final_report = result.content
    
    jinfo(logger, "报告长度", 节点="生成最终答复", 长度=len(final_report))
    
    jinfo(logger, "处理引文", 节点="生成最终答复")
    import re
    
    citation_pattern = re.compile(r'\[(\d+)\]')
    found_citations = set(citation_pattern.findall(final_report))
    jinfo(logger, "发现引文编号", 节点="生成最终答复", 引文编号=sorted(found_citations, key=int))
    
    enhanced_content = final_report
    for source in sources_gathered:
        if source["shortUrl"] in enhanced_content:
            enhanced_content = enhanced_content.replace(source["shortUrl"], source["value"])
    
    citation_to_source = {}
    unique_sources: List[Dict[str, Any]] = []
    
    def extract_citation_num(source: Dict[str, Any]) -> int:
        """从 shortUrl 中提取引用编号"""
        short_url = source.get("shortUrl", "")
        match = re.search(r'/id/\d+-(\d+)$', short_url)
        if match:
            return int(match.group(1))
        return 999999  # 如果无法提取，放到最后
    
    sorted_sources = sorted(sources_gathered, key=extract_citation_num)
    
    for idx, source in enumerate(sorted_sources, start=1):
        citation_num = str(idx)
        citation_to_source[citation_num] = source
        unique_sources.append(source)
    
    jinfo(logger, "来源去重后数量", 节点="生成最终答复", 数量=len(unique_sources))
    
    if found_citations:
        jinfo(logger, "追加参考文献章节", 节点="生成最终答复")
        
        has_references = bool(re.search(r'#+\s*(参考来源|引用|来源|参考资料|References)', enhanced_content, re.IGNORECASE))
        
        if not has_references:
            enhanced_content += "\n\n---\n\n## 参考来源\n\n"
            
            sorted_citations = sorted([int(c) for c in found_citations])
            
            for citation_num in sorted_citations:
                citation_str = str(citation_num)
                if citation_str in citation_to_source:
                    source = citation_to_source[citation_str]
                    label = source.get("label", f"来源 {citation_num}")
                    url = source.get("value", "")
                    enhanced_content += f"{citation_num}. [{label}]({url})\n"
                else:
                    jwarn(logger, "缺失对应来源的引文编号", 节点="生成最终答复", 引文编号=citation_num)
                    enhanced_content += f"{citation_num}. 来源未找到\n"
            
            jinfo(logger, "已添加参考文献数量", 节点="生成最终答复", 数量=len(sorted_citations))
        else:
            jinfo(logger, "参考文献章节已存在，跳过", 节点="生成最终答复")
    else:
        jinfo(logger, "无引文，跳过参考文献章节", 节点="生成最终答复")
    
    jinfo(logger, "最终内容长度", 节点="生成最终答复", 长度=len(enhanced_content))
    jinfo(logger, "最终答复生成完成", 节点="生成最终答复")

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

jinfo(logger, "搜索引擎图编译完成（已启用研究计划步骤）", 节点="图编译")


