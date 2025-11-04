"""DeepSearch 服务 - 使用内置引擎运行研究流程。"""
from typing import Any, Dict
import logging
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.services.deepsearch_engine import graph
from app.models.deepsearch import DeepSearchRequest, DeepSearchResponse, DeepSource


logger = logging.getLogger(__name__)


class DeepSearchService:
    """封装 DeepSearch 调用逻辑。"""

    async def run(self, request: DeepSearchRequest) -> DeepSearchResponse:
        try:
            logger.info("开始构建初始状态...")
            # 构建初始状态（符合 agent.state.OverallState 的字段约定）
            state: Dict[str, Any] = {
                "messages": [HumanMessage(content=request.query)],
            }

            if request.initial_search_query_count is not None:
                state["initial_search_query_count"] = request.initial_search_query_count
                logger.info(f"设置 initial_search_query_count = {request.initial_search_query_count}")
            if request.max_research_loops is not None:
                state["max_research_loops"] = request.max_research_loops
                logger.info(f"设置 max_research_loops = {request.max_research_loops}")
            if request.reasoning_model is not None:
                state["reasoning_model"] = request.reasoning_model
                logger.info(f"设置 reasoning_model = {request.reasoning_model}")

            logger.info(f"初始状态构建完成: {list(state.keys())}")

            # 可选：支持通过 config 传递可配置项（此处先使用默认）
            config = RunnableConfig()

            logger.info("开始执行图流...")
            result_state = await graph.ainvoke(state, config=config)
            logger.info("图流执行完成")

            # 提取答案与引用
            answer_text = ""
            messages = result_state.get("messages") or []
            if messages:
                answer_text = messages[-1].content or ""

            raw_sources = result_state.get("sources_gathered") or []
            sources = [DeepSource(**s) for s in raw_sources if isinstance(s, dict)]

            metadata = {
                "research_loop_count": result_state.get("research_loop_count"),
                "number_of_queries": len(result_state.get("search_query") or []),
            }

            logger.info(f"结果提取完成 - 答案长度: {len(answer_text)}, 数据源数量: {len(sources)}")

            return DeepSearchResponse(
                success=True,
                answer=answer_text,
                sources=sources,
                metadata=metadata,
                message="ok",
            )
        except Exception as e:
            logger.error(f"DeepSearch 执行失败: {e}", exc_info=True)
            raise


deepsearch_service = DeepSearchService()


