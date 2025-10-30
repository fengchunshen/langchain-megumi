"""FastGPT Retriever - 自定义 LangChain Retriever，调用 FastGPT 数据集搜索接口."""
from typing import List, Optional, Dict, Any
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from pydantic import Field
from app.core.config import settings
import httpx
import logging

logger = logging.getLogger(__name__)


class FastGptRetriever(BaseRetriever):
    """自定义的 FastGPT Retriever 类，继承自 LangChain BaseRetriever."""
    
    # 定义 Pydantic 字段
    dataset_id: str = Field(..., description="FastGPT 数据集 ID")
    api_url: Optional[str] = Field(default=None, description="FastGPT API 地址")
    api_key: Optional[str] = Field(default=None, description="FastGPT API 密钥")
    timeout: int = Field(default=30, description="请求超时时间（秒）")
    limit: int = Field(default=5000, description="最大 tokens 数量")
    search_mode: str = Field(default="mixedRecall", description="搜索模式：embedding | fullTextRecall | mixedRecall")
    embedding_weight: float = Field(default=0.5, description="嵌入权重")
    using_re_rank: bool = Field(default=True, description="是否使用重排序")
    rerank_weight: float = Field(default=0.5, description="重排序权重")
    similarity: float = Field(default=0.0, description="最低相关度（0~1）")
    dataset_search_using_extension_query: bool = Field(default=True, description="是否使用问题优化")
    dataset_search_extension_model: str = Field(default="deepseek-chat", description="问题优化模型")
    dataset_search_extension_bg: str = Field(default="", description="问题优化背景描述")
    
    model_config = {
        "arbitrary_types_allowed": True
    }
    
    def __init__(
        self,
        dataset_id: str,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        limit: int = 5000,
        search_mode: str = "mixedRecall",
        embedding_weight: float = 0.5,
        using_re_rank: bool = True,
        rerank_weight: float = 0.5,
        similarity: float = 0.0,
        dataset_search_using_extension_query: bool = True,
        dataset_search_extension_model: str = "deepseek-chat",
        dataset_search_extension_bg: str = ""
    ):
        """
        初始化 FastGptRetriever.
        
        Args:
            dataset_id: FastGPT 数据集 ID
            api_url: FastGPT API 地址（可选，默认从配置读取）
            api_key: FastGPT API 密钥（可选，默认从配置读取）
            timeout: 请求超时时间（秒，可选，默认从配置读取）
            limit: 最大 tokens 数量，默认 5000
            search_mode: 搜索模式，可选值：embedding | fullTextRecall | mixedRecall，默认 "mixedRecall"
            embedding_weight: 嵌入权重，默认 0.5（仅在 mixedRecall 模式下有效）
            using_re_rank: 是否使用重排序，默认 True
            rerank_weight: 重排序权重，默认 0.5（仅在启用重排序时有效）
            similarity: 最低相关度（0~1），默认 0.0
            dataset_search_using_extension_query: 是否使用问题优化，默认 True
            dataset_search_extension_model: 问题优化模型，默认 "deepseek-chat"
            dataset_search_extension_bg: 问题优化背景描述，默认空字符串
        """
        # 从配置中获取默认值
        final_api_url = api_url or settings.FASTGPT_API_URL
        final_api_key = api_key or settings.FASTGPT_API_KEY
        final_timeout = timeout or settings.TIMEOUT
        
        if not final_api_url:
            raise ValueError("FastGPT API URL 未配置，请设置 api_url 或 FASTGPT_API_URL 环境变量")
        if not final_api_key:
            raise ValueError("FastGPT API Key 未配置，请设置 api_key 或 FASTGPT_API_KEY 环境变量")
        
        # 调用父类初始化，传入所有字段
        super().__init__(
            dataset_id=dataset_id,
            api_url=final_api_url,
            api_key=final_api_key,
            timeout=final_timeout,
            limit=limit,
            search_mode=search_mode,
            embedding_weight=embedding_weight,
            using_re_rank=using_re_rank,
            rerank_weight=rerank_weight,
            similarity=similarity,
            dataset_search_using_extension_query=dataset_search_using_extension_query,
            dataset_search_extension_model=dataset_search_extension_model,
            dataset_search_extension_bg=dataset_search_extension_bg
        )
    
    def _build_endpoint_url(self, endpoint: str = "/api/core/dataset/searchTest") -> str:
        """
        构建完整的 API 端点 URL.
        
        处理 api_url 可能已经包含 /api 前缀的情况，避免重复拼接.
        
        Args:
            endpoint: API 端点路径（默认: /api/core/dataset/searchTest）
            
        Returns:
            str: 完整的 API URL
        """
        api_url = self.api_url.rstrip('/')  # 移除末尾的斜杠
        endpoint = endpoint.lstrip('/')  # 移除开头的斜杠，统一处理
        
        # 如果 api_url 以 /api 结尾，说明已经包含了 /api 前缀
        # 需要去掉 endpoint 的 api/ 前缀
        if api_url.endswith('/api'):
            # endpoint 应该是 "core/dataset/searchTest"，去掉 "api/" 前缀（如果存在）
            if endpoint.startswith('api/'):
                endpoint = endpoint[4:]  # 去掉 'api/'
            return f"{api_url}/{endpoint}"
        else:
            # api_url 不包含 /api，完整拼接 endpoint（endpoint 应该包含 api/）
            return f"{api_url}/{endpoint}"
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        获取与查询相关的文档.
        
        该方法调用 FastGPT 的 /api/core/dataset/searchTest 接口，并将返回结果
        转换为 LangChain Document 对象列表.
        
        Args:
            query: 用户查询字符串
            run_manager: LangChain 回调管理器
            
        Returns:
            List[Document]: 与查询相关的 Document 对象列表
            
        Raises:
            Exception: 当 API 请求失败时
        """
        try:
            # 构造请求数据（根据 FastGPT API 规范）
            payload = {
                "datasetId": self.dataset_id,
                "text": query,
                "searchMode": self.search_mode,
                "embeddingWeight": self.embedding_weight,
                "usingReRank": self.using_re_rank,
                "rerankWeight": self.rerank_weight,
                "limit": self.limit,
                "similarity": self.similarity,
                "datasetSearchUsingExtensionQuery": self.dataset_search_using_extension_query,
                "datasetSearchExtensionModel": self.dataset_search_extension_model,
                "datasetSearchExtensionBg": self.dataset_search_extension_bg
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 使用同步 httpx 客户端（BaseRetriever 的 _get_relevant_documents 是同步方法）
            endpoint_url = self._build_endpoint_url()
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    endpoint_url,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                # 解析 JSON 响应
                result = response.json()
                
                # 将 FastGPT 返回的结果转换为 LangChain Document 对象列表
                documents = self._parse_fastgpt_response(result)
                
                logger.info(f"FastGPT 检索完成，查询: {query[:50]}...，返回 {len(documents)} 条结果")
                
                return documents
                
        except httpx.HTTPError as e:
            logger.error(f"FastGPT HTTP 错误: {e}")
            raise Exception(f"FastGPT 检索请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"FastGPT 检索时发生错误: {e}")
            raise
    
    def get_relevant_documents(self, query: str) -> List[Document]:
        """
        获取与查询相关的文档（公共方法）.
        
        这是 BaseRetriever 的标准接口方法，它调用 _get_relevant_documents.
        
        Args:
            query: 用户查询字符串
            
        Returns:
            List[Document]: 与查询相关的 Document 对象列表
        """
        # 创建空的回调管理器
        run_manager = CallbackManagerForRetrieverRun.get_noop_manager()
        
        # 调用内部方法
        return self._get_relevant_documents(query, run_manager=run_manager)
    
    async def aget_relevant_documents(self, query: str) -> List[Document]:
        """
        异步获取与查询相关的文档（公共方法）.
        
        Args:
            query: 用户查询字符串
            
        Returns:
            List[Document]: 与查询相关的 Document 对象列表
        """
        # 创建空的回调管理器
        run_manager = CallbackManagerForRetrieverRun.get_noop_manager()
        
        # 调用内部异步方法
        return await self._aget_relevant_documents(query, run_manager=run_manager)
    
    def _parse_fastgpt_response(self, result: Dict[str, Any]) -> List[Document]:
        """
        解析 FastGPT API 返回的 JSON 结果，转换为 Document 对象列表.
        
        FastGPT 返回的数据结构：
        {
            "code": 200,
            "data": {
                "list": [
                    {
                        "id": "...",
                        "q": "问题/内容",
                        "a": "答案",
                        "score": [
                            {"type": "embedding", "value": 0.65, "index": 22},
                            {"type": "rrf", "value": 0.03, "index": 0},
                            {"type": "fullText", "value": 3.03, "index": 7}
                        ],
                        "chunkIndex": 10,
                        "datasetId": "...",
                        "collectionId": "...",
                        "sourceId": "...",
                        "sourceName": "...",
                        "tokens": 694,
                        "updateTime": "..."
                    }
                ]
            }
        }
        
        Args:
            result: FastGPT API 返回的 JSON 结果
            
        Returns:
            List[Document]: Document 对象列表
        """
        documents = []
        
        # 检查响应状态码
        code = result.get("code", 200)
        if code != 200:
            message = result.get("message", "未知错误")
            logger.error(f"FastGPT API 返回错误，code: {code}, message: {message}")
            return documents
        
        # 获取数据列表（数据在 data.list 中）
        data_obj = result.get("data", {})
        if not isinstance(data_obj, dict):
            logger.warning(f"FastGPT 返回的数据格式异常，data 字段不是对象: {result}")
            return documents
        
        data_list = data_obj.get("list", [])
        if not isinstance(data_list, list):
            logger.warning(f"FastGPT 返回的数据格式异常，data.list 字段不是列表: {result}")
            return documents
        
        logger.info(f"FastGPT API 返回了 {len(data_list)} 条原始数据")
        
        for item in data_list:
            if not isinstance(item, dict):
                continue
            
            # 提取内容：优先使用 q，如果有 a 则组合
            q = item.get("q", "")
            a = item.get("a", "")
            
            # 处理 q 和 a 可能为 None 的情况
            if q is None:
                q = ""
            if a is None:
                a = ""
            
            page_content = str(q).strip() if q else ""
            if a and str(a).strip():
                page_content = f"{page_content}\n{str(a).strip()}".strip() if page_content else str(a).strip()
            
            if not page_content:
                logger.warning(f"跳过空内容项: {item.get('id', 'unknown')}, q={q[:50] if q else 'None'}, a={a[:50] if a else 'None'}")
                continue
            
            # 提取分数信息（score 是一个数组）
            score_list = item.get("score", [])
            score_dict = {}
            if isinstance(score_list, list):
                for score_item in score_list:
                    if isinstance(score_item, dict):
                        score_type = score_item.get("type", "")
                        score_value = score_item.get("value", 0.0)
                        score_dict[score_type] = score_value
            
            # 提取主分数（优先使用 embedding，其次 rrf，最后 fullText）
            main_score = 0.0
            if "embedding" in score_dict:
                main_score = score_dict["embedding"]
            elif "rrf" in score_dict:
                main_score = score_dict["rrf"]
            elif "fullText" in score_dict:
                main_score = score_dict["fullText"]
            
            # 构建元数据
            metadata: Dict[str, Any] = {
                "score": main_score,
                "scores": score_dict,  # 保存所有分数信息
                "datasetId": self.dataset_id,
            }
            
            # 添加其他字段到元数据
            if "id" in item:
                metadata["item_id"] = item["id"]
            if "chunkIndex" in item:
                metadata["chunk_index"] = item["chunkIndex"]
            if "collectionId" in item:
                metadata["collection_id"] = item["collectionId"]
            if "sourceId" in item:
                metadata["source_id"] = item["sourceId"]
            if "sourceName" in item:
                metadata["source_name"] = item["sourceName"]
            if "tokens" in item:
                metadata["tokens"] = item["tokens"]
            if "updateTime" in item:
                metadata["update_time"] = item["updateTime"]
            if q:
                metadata["question"] = q
            if a:
                metadata["answer"] = a
            
            # 创建 Document 对象
            doc = Document(
                page_content=page_content,
                metadata=metadata
            )
            documents.append(doc)
        
        logger.info(f"成功解析 {len(documents)} 条文档")
        return documents
    
    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        异步获取与查询相关的文档.
        
        Args:
            query: 用户查询字符串
            run_manager: LangChain 回调管理器
            
        Returns:
            List[Document]: 与查询相关的 Document 对象列表
        """
        try:
            # 构造请求数据（根据 FastGPT API 规范）
            payload = {
                "datasetId": self.dataset_id,
                "text": query,
                "searchMode": self.search_mode,
                "embeddingWeight": self.embedding_weight,
                "usingReRank": self.using_re_rank,
                "rerankWeight": self.rerank_weight,
                "limit": self.limit,
                "similarity": self.similarity,
                "datasetSearchUsingExtensionQuery": self.dataset_search_using_extension_query,
                "datasetSearchExtensionModel": self.dataset_search_extension_model,
                "datasetSearchExtensionBg": self.dataset_search_extension_bg
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 使用异步 httpx 客户端
            endpoint_url = self._build_endpoint_url()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint_url,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                # 解析 JSON 响应
                result = response.json()
                
                # 将 FastGPT 返回的结果转换为 LangChain Document 对象列表
                documents = self._parse_fastgpt_response(result)
                
                logger.info(f"FastGPT 异步检索完成，查询: {query[:50]}...，返回 {len(documents)} 条结果")
                
                return documents
                
        except httpx.HTTPError as e:
            logger.error(f"FastGPT HTTP 错误: {e}")
            raise Exception(f"FastGPT 检索请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"FastGPT 检索时发生错误: {e}")
            raise

