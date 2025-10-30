"""AI智能体服务 - 处理解决方案分析等任务."""
import logging
from typing import Dict, List, Any
import aiohttp
from app.core.config import settings
from app.services.ai_communicator_service import ai_communicator_service

logger = logging.getLogger(__name__)


class AIAgentService:
    """AI智能体服务类."""
    
    def __init__(self):
        """初始化AI智能体服务."""
        self.api_key = settings.DEEPSEEK_API_KEY or ''
        logger.info("AI智能体服务初始化完成")
    
    async def analyze_solution_for_company(
        self, 
        solution_name: str, 
        description: str
    ) -> Dict[str, Any]:
        """
        分析解决方案并生成相关标签.
        
        Args:
            solution_name: 解决方案名称
            description: 解决方案描述
            
        Returns:
            Dict[str, Any]: 包含标签列表的分析结果
        """
        try:
            # 构建分析prompt
            prompt = f"""你是一位专业的解决方案分析师。请分析以下解决方案，并生成5-10个相关的标签。

解决方案名称：{solution_name}
解决方案描述：{description}

请生成相关的标签，标签应该：
1. 简洁明了，2-6个字
2. 准确反映解决方案的核心特征
3. 涵盖技术、应用场景、行业等领域
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
                    
                    return {
                        'tags': tags,
                        'message': f'成功生成 {len(tags)} 个标签'
                    }
                    
        except Exception as e:
            logger.error(f"解决方案分析失败: {e}")
            # 返回默认标签
            return {
                'tags': ['智能解决方案', 'AI分析', '技术创新'],
                'message': '分析完成（使用默认标签）'
            }


# 创建全局服务实例
ai_agent_service = AIAgentService()

