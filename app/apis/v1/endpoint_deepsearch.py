"""DeepSearch 研究流程 API 端点。"""
from fastapi import APIRouter, HTTPException, Depends
from app.apis.deps import get_api_key
from app.models.deepsearch import DeepSearchRequest, DeepSearchResponse
from app.services.deepsearch_service import deepsearch_service
import logging


logger = logging.getLogger(__name__)


router = APIRouter()


@router.post("/run", response_model=DeepSearchResponse)
async def run_deepsearch(
    request: DeepSearchRequest,
    api_key: str = Depends(get_api_key),
) -> DeepSearchResponse:
    """
    触发基于 Gemini 的 DeepSearch 流程。

    - 读取 `.env` 中的 `GEMINI_API_KEY`
    - 使用 `agent.graph` 的图流执行 DeepSearch
    - 返回带引用的最终回答和使用到的数据源
    """
    logger.info(f"=== DeepSearch 请求开始 ===")
    logger.info(f"查询内容: {request.query[:200]}...")  # 只记录前200个字符
    logger.info(f"初始搜索查询数量: {request.initial_search_query_count}")
    logger.info(f"最大研究循环次数: {request.max_research_loops}")
    logger.info(f"推理模型: {request.reasoning_model}")
    
    try:
        result = await deepsearch_service.run(request)
        logger.info(f"=== DeepSearch 请求成功完成 ===")
        logger.info(f"答案长度: {len(result.answer)} 字符")
        logger.info(f"数据源数量: {len(result.sources)}")
        logger.info(f"研究循环次数: {result.metadata.get('research_loop_count', 'N/A')}")
        logger.info(f"搜索查询总数: {result.metadata.get('number_of_queries', 'N/A')}")
        return result
    except Exception as e:
        logger.error(f"DeepSearch 执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DeepSearch 执行失败: {str(e)}")


