"""天眼查企业搜索 Runnable - 调用天眼查API搜索企业信息."""
from typing import Union, Dict, Any, Optional, List
from langchain_core.documents import Document
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import Field, BaseModel
from app.core.config import settings
import httpx
import logging
import json
import asyncio

logger = logging.getLogger(__name__)


class TianyanchaSearchInput(BaseModel):
    """天眼查搜索输入模型."""
    word: str = Field(..., description="搜索关键词（公司名称等）", min_length=1, max_length=200)
    page_size: Optional[int] = Field(default=20, description="每页条数（默认20条，最大20条）", ge=1, le=20)
    page_num: Optional[int] = Field(default=1, description="当前页数（默认第1页）", ge=1)


class CompanyInfo(BaseModel):
    """企业信息模型."""
    id: int = Field(..., description="企业ID")
    name: str = Field(..., description="企业名称")
    reg_status: Optional[str] = Field(default=None, description="注册状态")
    estiblish_time: Optional[str] = Field(default=None, description="成立时间")
    reg_capital: Optional[str] = Field(default=None, description="注册资本")
    company_type: Optional[int] = Field(default=None, description="公司类型")
    match_type: Optional[str] = Field(default=None, description="匹配类型")
    type: Optional[int] = Field(default=None, description="类型")
    legal_person_name: Optional[str] = Field(default=None, description="法人姓名")
    reg_number: Optional[str] = Field(default=None, description="注册号")
    credit_code: Optional[str] = Field(default=None, description="统一社会信用代码")
    org_number: Optional[str] = Field(default=None, description="组织机构代码")
    base: Optional[str] = Field(default=None, description="所在地")


class TianyanchaSearchResult(BaseModel):
    """天眼查搜索结果模型."""
    total: int = Field(..., description="总记录数")
    items: List[CompanyInfo] = Field(default_factory=list, description="企业信息列表")


class TianyanchaSearchRunnable(Runnable[Union[str, Dict[str, Any], TianyanchaSearchInput], Document]):
    """
    天眼查企业搜索 Runnable，调用天眼查API搜索企业信息.
    
    使用示例：
    ```python
    search = TianyanchaSearchRunnable()
    # 方式1：传入关键词字符串
    doc = await search.ainvoke("北京百度网讯科技有限公司")
    # 方式2：传入字典
    doc = await search.ainvoke({"word": "百度", "page_size": 10, "page_num": 1})
    # 方式3：传入TianyanchaSearchInput对象
    doc = await search.ainvoke(TianyanchaSearchInput(word="百度"))
    ```
    """
    
    def __init__(self):
        """初始化天眼查搜索Runnable."""
        super().__init__()
        self.api_url = "http://open.api.tianyancha.com/services/open/search/2.0"
        self.api_token = settings.TIANYANCHA_API_TOKEN
        self.timeout = settings.TIMEOUT
        
        if not self.api_token:
            logger.warning("天眼查API Token未配置，请设置TIANYANCHA_API_TOKEN环境变量")
    
    def _parse_input(
        self, 
        input_data: Union[str, Dict[str, Any], TianyanchaSearchInput]
    ) -> TianyanchaSearchInput:
        """
        解析输入数据，转换为 TianyanchaSearchInput 对象.
        
        Args:
            input_data: 输入数据，可以是：
                - str: 搜索关键词
                - Dict: 包含 word、page_size、page_num 等字段的字典
                - TianyanchaSearchInput: TianyanchaSearchInput 对象
        
        Returns:
            TianyanchaSearchInput: 解析后的输入对象
        """
        if isinstance(input_data, TianyanchaSearchInput):
            return input_data
        elif isinstance(input_data, str):
            return TianyanchaSearchInput(word=input_data)
        elif isinstance(input_data, dict):
            return TianyanchaSearchInput(
                word=input_data.get("word", ""),
                page_size=input_data.get("page_size", 20),
                page_num=input_data.get("page_num", 1)
            )
        else:
            raise ValueError(f"不支持的输入类型: {type(input_data)}")
    
    def _format_company_info(self, company: CompanyInfo) -> str:
        """
        格式化企业信息为文本.
        
        Args:
            company: 企业信息对象
        
        Returns:
            str: 格式化后的文本
        """
        lines = [
            f"企业名称：{company.name}",
            f"企业ID：{company.id}",
        ]
        
        if company.reg_status:
            lines.append(f"注册状态：{company.reg_status}")
        if company.estiblish_time:
            lines.append(f"成立时间：{company.estiblish_time}")
        if company.reg_capital:
            lines.append(f"注册资本：{company.reg_capital}")
        if company.legal_person_name:
            lines.append(f"法人代表：{company.legal_person_name}")
        if company.reg_number:
            lines.append(f"注册号：{company.reg_number}")
        if company.credit_code:
            lines.append(f"统一社会信用代码：{company.credit_code}")
        if company.org_number:
            lines.append(f"组织机构代码：{company.org_number}")
        if company.base:
            lines.append(f"所在地：{company.base}")
        if company.match_type:
            lines.append(f"匹配类型：{company.match_type}")
        
        return "\n".join(lines)
    
    async def ainvoke(
        self,
        input: Union[str, Dict[str, Any], TianyanchaSearchInput],
        config: Optional[RunnableConfig] = None
    ) -> Document:
        """
        异步调用天眼查搜索.
        
        Args:
            input: 输入数据（关键词、字典或TianyanchaSearchInput对象）
            config: Runnable配置
        
        Returns:
            Document: LangChain Document对象，包含搜索结果
        
        Raises:
            ValueError: 输入参数错误或API Token未配置
            httpx.HTTPError: HTTP请求错误
            Exception: 其他错误
        """
        if not self.api_token:
            raise ValueError("天眼查API Token未配置，请设置TIANYANCHA_API_TOKEN环境变量")
        
        # 解析输入
        search_input = self._parse_input(input)
        
        # 构建请求参数
        params = {
            "word": search_input.word,
            "pageSize": search_input.page_size,
            "pageNum": search_input.page_num
        }
        
        # 构建请求头
        headers = {
            "Authorization": self.api_token
        }
        
        logger.info(f"调用天眼查API搜索: {search_input.word}, 页码: {search_input.page_num}, 每页: {search_input.page_size}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.api_url,
                    params=params,
                    headers=headers
                )
                
                # 检查HTTP状态码
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"天眼查API请求失败，状态码: {response.status_code}")
                    logger.error(f"错误详情: {error_detail}")
                    raise httpx.HTTPStatusError(
                        f"天眼查API请求失败，状态码: {response.status_code}",
                        request=response.request,
                        response=response
                    )
                
                result = response.json()
                
                # 检查API返回的错误码
                error_code = result.get("error_code", 0)
                if error_code != 0:
                    reason = result.get("reason", "未知错误")
                    logger.error(f"天眼查API返回错误: {reason} (error_code: {error_code})")
                    raise ValueError(f"天眼查API返回错误: {reason} (error_code: {error_code})")
                
                # 解析结果
                result_data = result.get("result", {})
                total = result_data.get("total", 0)
                items_data = result_data.get("items", [])
                
                # 转换为CompanyInfo对象列表
                companies = []
                for item in items_data:
                    try:
                        company = CompanyInfo(
                            id=item.get("id"),
                            name=item.get("name", ""),
                            reg_status=item.get("regStatus"),
                            estiblish_time=item.get("estiblishTime"),
                            reg_capital=item.get("regCapital"),
                            company_type=item.get("companyType"),
                            match_type=item.get("matchType"),
                            type=item.get("type"),
                            legal_person_name=item.get("legalPersonName"),
                            reg_number=item.get("regNumber"),
                            credit_code=item.get("creditCode"),
                            org_number=item.get("orgNumber"),
                            base=item.get("base")
                        )
                        companies.append(company)
                    except Exception as e:
                        logger.warning(f"解析企业信息失败，跳过该项: {e}, 数据: {item}")
                        continue
                
                # 构建搜索结果文本
                if companies:
                    text_parts = [
                        f"搜索关键词：{search_input.word}",
                        f"总记录数：{total}",
                        f"当前页：{search_input.page_num}",
                        f"每页条数：{search_input.page_size}",
                        f"本页结果数：{len(companies)}",
                        "",
                        "=" * 50,
                        ""
                    ]
                    
                    for idx, company in enumerate(companies, 1):
                        text_parts.append(f"【企业 {idx}】")
                        text_parts.append(self._format_company_info(company))
                        if idx < len(companies):
                            text_parts.append("")
                            text_parts.append("-" * 50)
                            text_parts.append("")
                    
                    text = "\n".join(text_parts)
                else:
                    text = f"搜索关键词：{search_input.word}\n未找到相关企业信息。"
                
                # 构建元数据
                metadata: Dict[str, Any] = {
                    "source": "tianyancha_search",
                    "search_word": search_input.word,
                    "page_num": search_input.page_num,
                    "page_size": search_input.page_size,
                    "total": total,
                    "count": len(companies),
                    "companies": [
                        {
                            "id": company.id,
                            "name": company.name,
                            "reg_status": company.reg_status,
                            "base": company.base,
                            "legal_person_name": company.legal_person_name,
                            "reg_capital": company.reg_capital
                        }
                        for company in companies
                    ]
                }
                
                # 创建并返回Document对象
                document = Document(
                    page_content=text,
                    metadata=metadata
                )
                
                logger.info(f"天眼查搜索完成，找到 {len(companies)} 家企业（共 {total} 家）")
                return document
                
        except httpx.HTTPError as e:
            logger.error(f"天眼查API HTTP错误: {e}")
            raise Exception(f"天眼查API请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"天眼查搜索失败: {e}", exc_info=True)
            raise
    
    def invoke(
        self,
        input: Union[str, Dict[str, Any], TianyanchaSearchInput],
        config: Optional[RunnableConfig] = None
    ) -> Document:
        """
        同步调用天眼查搜索.
        
        Args:
            input: 输入数据（关键词、字典或TianyanchaSearchInput对象）
            config: Runnable配置
        
        Returns:
            Document: LangChain Document对象，包含搜索结果
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.ainvoke(input, config))
    
    async def abatch(
        self,
        inputs: List[Union[str, Dict[str, Any], TianyanchaSearchInput]],
        config: Optional[RunnableConfig] = None,
        **kwargs
    ) -> List[Document]:
        """
        异步批量搜索.
        
        Args:
            inputs: 输入数据列表
            config: Runnable配置
            **kwargs: 其他参数
        
        Returns:
            List[Document]: Document对象列表
        """
        tasks = [self.ainvoke(input_item, config) for input_item in inputs]
        return await asyncio.gather(*tasks)
    
    def batch(
        self,
        inputs: List[Union[str, Dict[str, Any], TianyanchaSearchInput]],
        config: Optional[RunnableConfig] = None,
        **kwargs
    ) -> List[Document]:
        """
        同步批量搜索.
        
        Args:
            inputs: 输入数据列表
            config: Runnable配置
            **kwargs: 其他参数
        
        Returns:
            List[Document]: Document对象列表
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.abatch(inputs, config, **kwargs))

