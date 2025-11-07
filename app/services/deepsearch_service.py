"""DeepSearch 服务 - 使用内置引擎运行研究流程。"""
from typing import Any, Dict, AsyncGenerator
import logging
import asyncio
from datetime import datetime
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.services.deepsearch_engine import graph, reset_degradation_status, is_connection_cancelled
from app.services.report_generator import report_generator
from app.models.deepsearch import (
    DeepSearchRequest, 
    DeepSearchResponse, 
    DeepSearchEvent,
    DeepSearchEventType,
    ProgressEvent,
    ResearchPlanEventData,
    QueryGeneratedEventData,
    ReflectionEventData,
    DeepSource
)


logger = logging.getLogger(__name__)


class DeepSearchService:
    """封装 DeepSearch 调用逻辑。"""
    
    def __init__(self):
        """初始化服务。"""
        self.sequence_number = 0
        

    async def run(self, request: DeepSearchRequest) -> DeepSearchResponse:
        try:
            # 重置降级状态，每次新请求都从 Gemini 开始尝试
            reset_degradation_status()
            
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

            # 构建响应
            response = self._build_response(request, result_state)
            
            logger.info(f"结果提取完成 - 答案长度: {len(response.answer)}, 被引用数据源数量: {len(response.sources)}, 所有搜索到的资源数量: {len(response.all_sources)}")
            
            return response
        except Exception as e:
            logger.error(f"DeepSearch 执行失败: {e}", exc_info=True)
            raise
    
    async def run_stream(
        self, 
        request: DeepSearchRequest,
        connection_id: str = None
    ) -> AsyncGenerator[DeepSearchEvent, None]:
        """
        流式执行 DeepSearch，实时推送事件.
        
        Args:
            request: DeepSearch请求
            connection_id: SSE连接ID，用于取消检查
            
        Yields:
            DeepSearchEvent: 研究过程事件
        """
        self.sequence_number = 0
        
        # 采用引擎的统一取消状态（通过 connection_id 查询）
        
        try:
            # 重置降级状态，每次新请求都从 Gemini 开始尝试
            reset_degradation_status()
            
            # 发送开始事件
            yield self._create_event(
                DeepSearchEventType.STARTED,
                {"query": request.query},
                "研究流程已启动"
            )
            
            # 检查是否已被取消（统一由 engine 管理）
            if connection_id and is_connection_cancelled(connection_id):
                yield self._create_event(
                    DeepSearchEventType.CANCELLED,
                    {"message": "用户取消了研究流程"},
                    "研究流程已取消"
                )
                return
            
            # 构建初始状态
            state = self._build_initial_state(request)
            
            # 跟踪最终状态是否获取
            final_state = None
            # 跟踪是否已发送 WEB_SEARCHING 事件
            web_searching_sent = False
            
            # 使用 astream 流式执行，传递connection_id到config
            config = RunnableConfig(configurable={"connection_id": connection_id}) if connection_id else RunnableConfig()
            
            async for chunk in graph.astream(state, config=config):
                # **优先检查取消状态**
                if connection_id and is_connection_cancelled(connection_id):
                    logger.info(f"检测到取消信号 [连接: {connection_id}]，停止流式执行")
                    yield self._create_event(
                        DeepSearchEventType.CANCELLED,
                        {"message": "用户取消了研究流程"},
                        "研究流程已取消"
                    )
                    return
                
                # 解析每个步骤的输出
                for node_name, node_output in chunk.items():
                    # **在处理每个节点输出前再次检查取消状态**
                    if connection_id and is_connection_cancelled(connection_id):
                        logger.info(f"在处理节点 {node_name} 时检测到取消信号 [连接: {connection_id}]")
                        yield self._create_event(
                            DeepSearchEventType.CANCELLED,
                            {"message": "用户取消了研究流程"},
                            "研究流程已取消"
                        )
                        return
                    
                    logger.info(f"节点 {node_name} 输出: {list(node_output.keys())}")
                    
                    # 研究计划生成
                    if node_name == "generate_research_plan":
                        if "research_plan" in node_output:
                            plan = node_output["research_plan"]
                            if plan is not None:
                                yield self._create_event(
                                    DeepSearchEventType.RESEARCH_PLAN,
                                    ResearchPlanEventData(
                                        research_topic=plan.research_topic,
                                        sub_topics=plan.sub_topics,
                                        research_questions=plan.research_questions,
                                        rationale=plan.rationale
                                    ).model_dump(),
                                    "研究计划已生成"
                                )
                            else:
                                logger.warning("研究计划生成失败或为空，跳过研究计划事件")
                        
                        yield self._create_progress_event("研究计划已制定", 1, 8, 12.5)
                    
                    # 查询生成
                    elif node_name == "generate_query":
                        if "search_query" in node_output:
                            queries = node_output["search_query"]
                            yield self._create_event(
                                DeepSearchEventType.QUERY_GENERATED,
                                QueryGeneratedEventData(
                                    queries=queries,
                                    count=len(queries),
                                    rationale="基于研究计划生成"
                                ).model_dump(),
                                f"已生成 {len(queries)} 个搜索查询"
                            )
                        
                        yield self._create_progress_event("搜索查询已生成", 2, 8, 25.0)
                    
                    # 网络搜索
                    elif node_name == "web_research":
                        # 首次进入 web_research 节点时发送 WEB_SEARCHING 事件
                        if not web_searching_sent:
                            yield self._create_event(
                                DeepSearchEventType.WEB_SEARCHING,
                                {"message": "开始执行网络搜索"},
                                "正在搜索网络资源"
                            )
                            web_searching_sent = True
                        
                        # 发送搜索中的进度事件
                        yield self._create_progress_event("正在搜索网络资源", 3, 8, 37.5)
                        
                        # 提取搜索到的资源并发送
                        if "sources_gathered" in node_output:
                            sources = node_output["sources_gathered"]
                            # 构建资源列表数据
                            sources_data = []
                            for source in sources:
                                if isinstance(source, dict):
                                    sources_data.append({
                                        "title": source.get("label", "未知标题"),
                                        "url": source.get("value", "")
                                    })
                            
                            # 发送搜索结果事件
                            yield self._create_event(
                                DeepSearchEventType.WEB_RESULT,
                                {
                                    "sources": sources_data,
                                    "count": len(sources_data)
                                },
                                f"找到 {len(sources_data)} 个网络资源"
                            )
                    
                    # 反思评估
                    elif node_name == "reflection":
                        if "is_sufficient" in node_output:
                            yield self._create_event(
                                DeepSearchEventType.REFLECTION,
                                ReflectionEventData(
                                    loop_count=node_output.get("research_loop_count", 0),
                                    is_sufficient=node_output.get("is_sufficient", False),
                                    knowledge_gap=node_output.get("knowledge_gap"),
                                    follow_up_queries=node_output.get("follow_up_queries", [])
                                ).model_dump(),
                                "反思评估完成"
                            )
                        
                        yield self._create_progress_event("反思评估完成", 4, 8, 50.0)
                    
                    # 质量评估
                    elif node_name == "assess_content_quality":
                        if "content_quality" in node_output:
                            yield self._create_event(
                                DeepSearchEventType.QUALITY_ASSESSMENT,
                                node_output["content_quality"],
                                "内容质量评估完成"
                            )
                        
                        yield self._create_progress_event("质量评估完成", 5, 8, 62.5)
                    
                    # 事实验证
                    elif node_name == "verify_facts":
                        if "fact_verification" in node_output:
                            yield self._create_event(
                                DeepSearchEventType.FACT_VERIFICATION,
                                node_output["fact_verification"],
                                "事实验证完成"
                            )
                        
                        yield self._create_progress_event("事实验证完成", 6, 8, 75.0)
                    
                    # 相关性评估
                    elif node_name == "assess_relevance":
                        if "relevance_assessment" in node_output:
                            yield self._create_event(
                                DeepSearchEventType.RELEVANCE_ASSESSMENT,
                                node_output["relevance_assessment"],
                                "相关性评估完成"
                            )
                        
                        yield self._create_progress_event("相关性评估完成", 7, 8, 87.5)
                    
                    # 总结优化
                    elif node_name == "optimize_summary":
                        if "summary_optimization" in node_output:
                            yield self._create_event(
                                DeepSearchEventType.OPTIMIZATION,
                                node_output["summary_optimization"],
                                "总结优化完成"
                            )
                    
                    # 最终答案
                    elif node_name == "finalize_answer":
                        yield self._create_progress_event("生成最终报告", 8, 8, 100.0)
                        
                        # 从流式执行的最后一个状态中获取最终结果
                        final_state = node_output
            
            # 使用流式执行中获取的最终状态构建响应，避免重复执行
            if final_state:
                response = self._build_response(request, final_state)
            else:
                # 如果流式执行没有到达最终节点，则重新获取最终状态
                logger.warning("流式执行未完成，使用重新获取的最终状态")
                config = RunnableConfig(configurable={"connection_id": connection_id}) if connection_id else RunnableConfig()
                final_state = await graph.ainvoke(state, config=config)
                response = self._build_response(request, final_state)
            
            # 发送报告生成完成事件
            yield self._create_event(
                DeepSearchEventType.REPORT_GENERATED,
                {
                    "report_length": len(response.markdown_report),
                    "answer_length": len(response.answer),
                    "sources_count": len(response.sources)
                },
                "研究报告已生成"
            )
            
            # 发送完成事件
            yield self._create_event(
                DeepSearchEventType.COMPLETED,
                response.model_dump(),
                "研究完成"
            )
            
        except Exception as e:
            logger.error(f"流式执行失败: {e}", exc_info=True)
            yield self._create_event(
                DeepSearchEventType.ERROR,
                {"error": str(e)},
                f"执行失败: {str(e)}"
            )
        finally:
            # 取消状态清理由 endpoint 统一负责（engine 层统一管理）
            pass
    
    def _build_initial_state(self, request: DeepSearchRequest) -> Dict[str, Any]:
        """构建初始状态."""
        state: Dict[str, Any] = {
            "messages": [HumanMessage(content=request.query)],
        }
        
        if request.initial_search_query_count is not None:
            state["initial_search_query_count"] = request.initial_search_query_count
        if request.max_research_loops is not None:
            state["max_research_loops"] = request.max_research_loops
        if request.reasoning_model is not None:
            state["reasoning_model"] = request.reasoning_model
        
        return state
    
    def _build_response(
        self, 
        request: DeepSearchRequest,
        result_state: Dict[str, Any]
    ) -> DeepSearchResponse:
        """构建响应对象."""
        # 提取答案
        answer_text = ""
        messages = result_state.get("messages") or []
        if messages:
            answer_text = messages[-1].content or ""
        
        # 提取被引用的来源
        sources_list = []
        sources_gathered = result_state.get("sources_gathered") or []
        for source in sources_gathered:
            if isinstance(source, dict):
                sources_list.append(
                    DeepSource(
                        label=source.get("label"),
                        short_url=source.get("shortUrl"),
                        value=source.get("value")
                    )
                )
        
        # 提取所有搜索到的来源
        all_sources_list = []
        all_sources_gathered = result_state.get("all_sources_gathered") or []
        # 使用字典去重，避免重复的URL
        seen_urls = set()
        for source in all_sources_gathered:
            if isinstance(source, dict):
                url = source.get("value")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_sources_list.append(
                        DeepSource(
                            label=source.get("label"),
                            short_url=source.get("shortUrl"),
                            value=source.get("value")
                        )
                    )
        
        # 生成 Markdown 报告
        markdown_report = ""
        if request.report_format.value == "formal":
            markdown_report = report_generator.generate_formal_report(
                query=request.query,
                research_plan=result_state.get("research_plan"),
                answer=answer_text,
                sources=sources_gathered,
                content_quality=result_state.get("content_quality", {}),
                fact_verification=result_state.get("fact_verification", {}),
                relevance_assessment=result_state.get("relevance_assessment", {}),
                summary_optimization=result_state.get("summary_optimization", {}),
                metadata={
                    "research_loop_count": result_state.get("research_loop_count", 0),
                    "number_of_queries": len(result_state.get("search_query", [])),
                    "number_of_sources": len(sources_gathered),
                    "total_sources_found": len(all_sources_gathered),
                }
            )
        else:
            # 普通格式
            markdown_report = self._generate_casual_report(answer_text, sources_gathered)
        
        # 构建元数据
        metadata = {
            "research_loop_count": result_state.get("research_loop_count", 0),
            "number_of_queries": len(result_state.get("search_query", [])),
            "number_of_sources": len(sources_gathered),
            "total_sources_found": len(all_sources_gathered),
            "reasoning_model": request.reasoning_model or "自研数据研究模型",
            "system_version": "1.0.0"
        }
        
        return DeepSearchResponse(
            success=True,
            answer=answer_text,
            markdown_report=markdown_report,
            sources=sources_list,
            all_sources=all_sources_list,
            metadata=metadata,
            message="研究完成"
        )
    
    def _generate_casual_report(self, answer: str, sources: list) -> str:
        """生成普通格式报告."""
        report = f"# 研究报告\n\n{answer}\n\n## 参考来源\n\n"
        for idx, source in enumerate(sources, 1):
            if isinstance(source, dict):
                report += f"{idx}. [{source.get('label', '来源')}]({source.get('value', '#')})\n"
        return report
    
    def _create_event(
        self,
        event_type: DeepSearchEventType,
        data: Dict[str, Any],
        message: str
    ) -> DeepSearchEvent:
        """创建事件对象."""
        self.sequence_number += 1
        return DeepSearchEvent(
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
            sequence_number=self.sequence_number,
            data=data,
            message=message
        )
    
    def _create_progress_event(
        self,
        step_name: str,
        completed: int,
        total: int,
        percentage: float
    ) -> DeepSearchEvent:
        """创建进度事件."""
        return self._create_event(
            DeepSearchEventType.PROGRESS,
            ProgressEvent(
                current_step=step_name,
                total_steps=total,
                completed_steps=completed,
                percentage=percentage
            ).model_dump(),
            f"进度: {step_name} ({completed}/{total} - {percentage:.1f}%)"
        )


deepsearch_service = DeepSearchService()


