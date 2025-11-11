"""DeepSearch 研究流程 API 端点."""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from datetime import datetime
from app.models.deepsearch import (
    DeepSearchRequest, 
    DeepSearchResponse,
    DeepSearchEvent,
    DeepSearchEventType
)
from app.services.deepsearch_service import deepsearch_service
from app.services.sse_monitor import sse_monitor
import logging
import asyncio


logger = logging.getLogger(__name__)


router = APIRouter()


@router.post("/run", response_model=DeepSearchResponse)
async def run_deepsearch(
    request: DeepSearchRequest,
) -> DeepSearchResponse:
    """
    触发基于 Gemini 的 DeepSearch 流程。

    - 读取 `.env` 中的 `GEMINI_API_KEY`
    - 使用 `agent.graph` 的图流执行 DeepSearch
    - 返回带引用的最终回答和使用到的数据源
    
    Args:
        request: DeepSearch请求
        
    Returns:
        DeepSearchResponse: DeepSearch响应结果
    """
    try:
        result = await deepsearch_service.run(request)
        return result
    except Exception as e:
        logger.error(f"DeepSearch 执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DeepSearch 执行失败: {str(e)}")


@router.post("/run/stream")
async def run_deepsearch_stream(
    request: Request,
    request_data: DeepSearchRequest,
):
    """
    DeepSearch 流式接口（SSE）.
    
    实时推送研究过程中的各个阶段和结果。
    
    响应类型：Server-Sent Events (text/event-stream)
    
    事件格式：
    ```
    event: <事件类型>
    data: <JSON数据>
    ```
    
    Args:
        request: FastAPI请求对象
        request_data: DeepSearch请求
        
    Returns:
        StreamingResponse: SSE流式响应
    """
    # 从请求头获取客户端信息
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # 创建监控连接，传递 Request 对象用于主动检测连接状态
    connection_id = await sse_monitor.create_connection(
        user_id=None,  # 如果有认证系统，从token中获取
        request_query=request_data.query,
        client_ip=client_ip,
        user_agent=user_agent,
        request_object=request  # 传递 Request 对象用于健康检查
    )
    
    logger.info(f"DeepSearch流式请求开始: {connection_id}")
    
    async def event_generator():
        """事件生成器."""
        # 导入取消函数
        from app.services.deepsearch_engine import set_connection_cancelled, cleanup_connection_cancellation
        
        # 创建后台任务定期检查连接状态
        check_task = None
        
        async def periodic_connection_check():
            """定期检查连接状态的后台任务."""
            check_interval = 5  # 每5秒检查一次
            while True:
                try:
                    await asyncio.sleep(check_interval)
                    if await request.is_disconnected():
                        logger.info(f"后台任务检测到客户端断开连接: {connection_id}")
                        await set_connection_cancelled(connection_id)
                        await sse_monitor.error_connection(connection_id, "客户端主动断开连接（后台检测）")
                        await cleanup_connection_cancellation(connection_id)
                        break
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"连接检查任务出错: {e}")
                    break
        
        try:
            # 启动后台连接检查任务
            check_task = asyncio.create_task(periodic_connection_check())
            
            # 使用监控的迭代器包装原始服务，传递connection_id
            async for event in deepsearch_service.run_stream(request_data, connection_id):
                # **关键改进：主动检查客户端连接状态（双重检测）**
                if await request.is_disconnected():
                    logger.info(f"事件循环中检测到客户端断开连接: {connection_id}")
                    # 立即标记取消状态
                    await set_connection_cancelled(connection_id)
                    await sse_monitor.error_connection(connection_id, "客户端主动断开连接")
                    # 清理取消状态
                    await cleanup_connection_cancellation(connection_id)
                    # 取消后台检查任务
                    if check_task and not check_task.done():
                        check_task.cancel()
                    return
                
                # 更新监控信息
                await sse_monitor.update_activity(connection_id)
                
                # SSE 格式
                yield f"event: {event.event_type.value}\n"
                yield f"data: {event.model_dump_json()}\n\n"
            
            # 标记连接完成
            await sse_monitor.complete_connection(connection_id)
            
            # 取消后台检查任务
            if check_task and not check_task.done():
                check_task.cancel()
                try:
                    await check_task
                except asyncio.CancelledError:
                    pass
            
        except asyncio.CancelledError:
            # 客户端主动断开连接（备用方案）
            logger.info(f"捕获到CancelledError: {connection_id}")
            
            # 取消后台检查任务
            if check_task and not check_task.done():
                check_task.cancel()
                try:
                    await check_task
                except asyncio.CancelledError:
                    pass
            
            # 通知服务和引擎取消处理流程
            await set_connection_cancelled(connection_id)
            await sse_monitor.error_connection(connection_id, "客户端主动断开连接")
            
            # 清理取消状态
            await cleanup_connection_cancellation(connection_id)
            
            # 不需要重新抛出CancelledError，让FastAPI处理
            return
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"流式执行失败 [{connection_id}]: {e}", exc_info=True)
            
            # 标记连接错误
            await sse_monitor.error_connection(connection_id, error_msg)
            
            # 发送错误事件
            error_event = DeepSearchEvent(
                event_type=DeepSearchEventType.ERROR,
                timestamp=datetime.now().isoformat(),
                sequence_number=9999,
                data={"error": error_msg},
                message=f"执行失败: {error_msg}"
            )
            yield f"event: {error_event.event_type.value}\n"
            yield f"data: {error_event.model_dump_json()}\n\n"
        finally:
            # 确保清理工作总是执行
            # 取消后台检查任务
            if check_task and not check_task.done():
                check_task.cancel()
                try:
                    await check_task
                except asyncio.CancelledError:
                    pass
            
            await cleanup_connection_cancellation(connection_id)
            logger.info(f"事件生成器清理完成: {connection_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Connection-ID": connection_id,  # 返回连接ID给客户端
        }
    )


