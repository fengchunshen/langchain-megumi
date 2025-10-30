"""企业标签分析服务 - 基于经营范围生成企业标签."""
import logging
from typing import List
import aiohttp
from app.core.config import settings
from app.services.ai_communicator_service import ai_communicator_service

logger = logging.getLogger(__name__)


class CompanyTagService:
    """企业标签分析服务类."""
    
    def __init__(self):
        """初始化企业标签分析服务."""
        self.api_key = settings.DEEPSEEK_API_KEY or ''
        logger.info("企业标签分析服务初始化完成")
    
    async def analyze_company_business_scope(
        self, 
        company_name: str, 
        business_scope: str
    ) -> List[str]:
        """
        分析企业经营范围并生成相关标签.
        
        Args:
            company_name: 企业名称
            business_scope: 企业经营范围
            
        Returns:
            List[str]: 生成的标签列表
        """
        try:
            # 构建分析prompt
            prompt = f"""你是一位专业的企业分析师。请分析以下企业的经营范围，并生成5-10个相关的行业标签。

企业名称：{company_name}
经营范围：{business_scope}

请生成相关的标签，标签应该：
1. 简洁明了，2-6个字
2. 准确反映企业的主要业务领域和行业特征
3. 涵盖行业分类、技术领域、业务类型等
4. 使用逗号分隔返回标签列表

请直接返回标签列表，格式为：标签1, 标签2, 标签3, ..."""

            # 调用AI通信服务
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            ssl_context = ai_communicator_service._build_ssl_context()
            timeout = aiohttp.ClientTimeout(total=60, connect=30)
            connector = aiohttp.TCPConnector(ssl=ssl_context)

            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.post(
                    ai_communicator_service.api_url, 
                    headers=headers, 
                    json=data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    ai_response = result['choices'][0]['message']['content'].strip()
                    
                    # 解析标签列表
                    tags = [tag.strip() for tag in ai_response.split(',') if tag.strip()]
                    
                    return tags
                    
        except Exception as e:
            logger.error(f"企业标签分析失败: {e}")
            # 返回默认标签
            return ['企业服务', '商业分析', '行业标签']


# 创建全局服务实例
company_tag_service = CompanyTagService()

