"""AI通信服务 - 负责与DeepSeek API的交互."""
import json
import logging
import aiohttp
import ssl
import certifi
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class AICommunicatorService:
    """AI通信服务类."""
    
    def __init__(self):
        """初始化AI通信服务."""
        self.api_key = settings.DEEPSEEK_API_KEY or ''
        self.api_url = settings.DEEPSEEK_API_URL or "https://api.deepseek.com/v1/chat/completions"
        self.max_retries = 3
        self.retry_delay = 2
        self.ssl_verify = settings.DEEPSEEK_SSL_VERIFY
        self.ca_bundle = settings.DEEPSEEK_CA_BUNDLE or ''
        
        logger.info("AI通信服务初始化完成")
    
    def format_master_prompt(
        self, 
        node_to_process: Dict[str, Any], 
        parent_profile: Optional[Dict[str, Any]] = None, 
        siblings_profiles: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        生成一个能处理所有节点的、携带上下文的"大师级"Prompt.
        
        Args:
            node_to_process: 待处理的节点信息
            parent_profile: 父节点信息
            siblings_profiles: 兄弟节点信息列表
            
        Returns:
            str: 格式化后的prompt字符串
        """
        node_name = node_to_process['name']
        
        # 构建父节点名称
        parent_name = parent_profile['name'] if parent_profile else "无"
        
        # 构建兄弟节点名称列表
        sibling_names = []
        if siblings_profiles:
            sibling_names = [s['name'] for s in siblings_profiles if s['name'] != node_name]
        sibling_names_str = ", ".join(sibling_names) if sibling_names else "无"
        
        prompt = f"""你是一位顶级的产业分析师和知识图谱构建专家。你的唯一使命是为给定的产业节点，生成一套高度结构化、精准且专业的关键词标签，并为每个标签分配反映其核心度的权重。

**第一部分：专家的思考链 (Internal Thought Process)**
在生成最终的JSON输出前，你必须在内部遵循以下思考步骤来分析节点：
1.  **深度理解节点**：首先，深入分析节点 `{node_name}` 的核心定义、其在产业链中的精确位置（上游、中游、下游）以及它的核心价值主张。
2.  **利用上下文进行界定**：
    * 分析**父节点** `{parent_name}`，确保所有标签都是在父节点的范畴之下，并且能体现 `{node_name}` 的具体细分领域。
    * 分析**兄弟节点** `{sibling_names_str}`，识别出 `{node_name}` 与它们的关键区别。生成的标签应聚焦于 `{node_name}` 的独特性，避免生成那些在兄弟节点间普遍适用的、缺乏区分度的标签。
3.  **头脑风暴与筛选**：基于以上分析，广泛生成候选标签。然后，运用以下三大原则进行严格筛选：
    * **精确性 (Specificity)**：标签是否足够具体？例如，对于"光伏电池"，"N型电池"比"太阳能技术"更精确。
    * **必要性 (Necessity)**：这个标签对于定义 `{node_name}` 是否不可或缺？
    * **非重叠性 (Non-redundancy)**：避免同义词或高度重叠的标签。例如，保留"HJT电池"，就删除"异质结电池"。

**第二部分：权重分配核心原则**
权重的核心依据是**"标签对于定义该节点的中心度（Centrality）"**，而不是其所属的类别。
* **1.0 (定义性)**：这是节点的同义词或最核心的定义。缺少这个标签，节点的身份就会模糊。
* **0.8 - 0.9 (关键构成)**：节点最关键的技术、最主要的产品、或不可或缺的核心组成部分。
* **0.6 - 0.7 (重要属性)**：重要的工艺、关键的设备、或直接相关的上下游产品。
* **0.4 - 0.5 (相关场景/领域)**：主要的下游应用场景或相关的技术领域。

**第三部分：严格的输出规则**
1.  **必须只返回一个JSON对象**。绝对禁止在JSON对象之外包含任何文字、解释、注释或代码块标记（如`json`）。
2.  返回的JSON必须严格遵循下面定义的`"output_schema"`结构。
3.  所有标签(tag)必须是**简洁的名词或公认的技术术语**，长度通常在2到8个字之间。
4.  **禁止使用**任何句子、描述性语言、形容词或非通用缩写作为标签。

---

**任务开始**

* **分析上下文:**
    * **父节点**: `{parent_name}`
    * **兄弟节点**: `{sibling_names_str}`

* **生成画像:**
    请为以下节点生成标签画像: **`{node_name}`**

* **输出格式 (output_schema):**
    ```json
    {{
      "node_name": "{node_name}",
      "tags": {{
        "coreTechnologies": [
          {{"name": "在此处填充核心技术标签", "weight": 0.9}},
          {{"name": "例如: TOPCon", "weight": 0.8}}
        ],
        "key_products": [
          {{"name": "在此处填充关键产品标签", "weight": 0.8}},
          {{"name": "例如: 光伏组件", "weight": 0.9}}
        ],
        "related_equipment": [
          {{"name": "在此处填充相关设备标签", "weight": 0.7}},
          {{"name": "例如: PECVD设备", "weight": 0.6}}
        ],
        "applicationScenarios": [
          {{"name": "在此处填充应用场景标签", "weight": 0.6}},
          {{"name": "例如: 分布式光伏", "weight": 0.7}}
        ]
      }}
    }}
    ```"""
        return prompt

    async def get_profile_from_ai(self, prompt: str) -> Dict[str, Any]:
        """
        发送prompt给DeepSeek API并获取结构化的画像结果.
        
        Args:
            prompt: 要发送的prompt字符串
            
        Returns:
            Dict[str, Any]: 结构化的标签画像结果
        """
        logger.info("----------- 向DeepSeek发送的Prompt -----------")
        logger.info(prompt)
        logger.info("--------------------------------------")
        
        try:
            # DeepSeek API调用
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt + "\n\n请以JSON格式返回结果，确保格式正确。"
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }
            
            # 构建SSL上下文
            ssl_context = self._build_ssl_context()

            timeout = aiohttp.ClientTimeout(total=120, connect=30)
            connector = aiohttp.TCPConnector(ssl=ssl_context)

            # 使用异步请求
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.post(self.api_url, headers=headers, json=data) as response:
                    response.raise_for_status()
                    result = await response.json()
                    ai_response = result['choices'][0]['message']['content']
                    
                    logger.info("----------- DeepSeek API返回结果 -----------")
                    logger.info(ai_response)
                    logger.info("--------------------------------------")
                    
                    # 尝试解析JSON响应
                    try:
                        # 如果响应是纯JSON，直接解析
                        ai_result = json.loads(ai_response)
                        return self._convert_ai_result_to_tags(ai_result)
                    except json.JSONDecodeError:
                        # 如果响应包含其他文本，尝试提取JSON部分
                        import re
                        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                        if json_match:
                            ai_result = json.loads(json_match.group())
                            return self._convert_ai_result_to_tags(ai_result)
                        else:
                            logger.warning("警告：无法从AI响应中提取有效的JSON格式")
                            # 返回模拟数据作为备选
                            return {
                                "coreTechnologies": [{"name": "空间数据存储引擎", "weight": 0.9}, {"name": "PostGIS", "weight": 0.8}],
                                "applicationScenarios": [{"name": "地理信息系统", "weight": 0.7}, {"name": "空间数据分析", "weight": 0.6}]
                            }
                            
        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {e}")
            # 返回模拟数据作为备选
            return {
                "coreTechnologies": [{"name": "AI生成标签", "weight": 0.8}],
                "applicationScenarios": [{"name": "智能应用", "weight": 0.6}]
            }
    
    def _build_ssl_context(self) -> ssl.SSLContext:
        """
        构建SSL上下文.
        
        Returns:
            ssl.SSLContext: SSL上下文对象
        """
        if self.ssl_verify:
            ssl_context = ssl.create_default_context()
            # 优先使用自定义CA，其次使用certifi内置
            try:
                if isinstance(self.ca_bundle, str) and self.ca_bundle.strip():
                    ssl_context.load_verify_locations(cafile=self.ca_bundle.strip())
                else:
                    ssl_context.load_verify_locations(cafile=certifi.where())
            except Exception as e:
                logger.warning(f"加载CA证书失败，将回退到系统默认CA链: {e}")
            return ssl_context
        else:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            return ssl_context
    
    def _convert_ai_result_to_tags(self, ai_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        将AI返回的JSON结果转换为带权重的标签格式.
        
        Args:
            ai_result: AI返回的原始结果
            
        Returns:
            Dict[str, Any]: 转换后的标签画像
        """
        tags_profile = {
            "coreTechnologies": [],
            "applicationScenarios": []
        }
        
        try:
            # 检查是否是新的带权重格式
            if "tags" in ai_result and isinstance(ai_result["tags"], dict):
                tags = ai_result["tags"]
                
                # 处理核心技术标签
                if "coreTechnologies" in tags and isinstance(tags["coreTechnologies"], list):
                    for item in tags["coreTechnologies"]:
                        if isinstance(item, dict) and "name" in item and "weight" in item:
                            tag_name = item["name"].strip()
                            weight = float(item["weight"])
                            if tag_name and 0.0 <= weight <= 1.0:
                                tags_profile["coreTechnologies"].append({"name": tag_name, "weight": weight})
                        elif isinstance(item, str) and item.strip():
                            # 兼容旧格式（纯字符串）
                            tags_profile["coreTechnologies"].append({"name": item.strip(), "weight": 0.8})
                
                # 处理关键产品标签
                if "key_products" in tags and isinstance(tags["key_products"], list):
                    for item in tags["key_products"]:
                        if isinstance(item, dict) and "name" in item and "weight" in item:
                            tag_name = item["name"].strip()
                            weight = float(item["weight"])
                            if tag_name and 0.0 <= weight <= 1.0:
                                tags_profile["coreTechnologies"].append({"name": tag_name, "weight": weight})
                        elif isinstance(item, str) and item.strip():
                            # 兼容旧格式（纯字符串）
                            tags_profile["coreTechnologies"].append({"name": item.strip(), "weight": 0.7})
                
                # 处理相关设备标签
                if "related_equipment" in tags and isinstance(tags["related_equipment"], list):
                    for item in tags["related_equipment"]:
                        if isinstance(item, dict) and "name" in item and "weight" in item:
                            tag_name = item["name"].strip()
                            weight = float(item["weight"])
                            if tag_name and 0.0 <= weight <= 1.0:
                                tags_profile["coreTechnologies"].append({"name": tag_name, "weight": weight})
                        elif isinstance(item, str) and item.strip():
                            # 兼容旧格式（纯字符串）
                            tags_profile["coreTechnologies"].append({"name": item.strip(), "weight": 0.6})
                
                # 处理应用场景标签
                if "applicationScenarios" in tags and isinstance(tags["applicationScenarios"], list):
                    for item in tags["applicationScenarios"]:
                        if isinstance(item, dict) and "name" in item and "weight" in item:
                            tag_name = item["name"].strip()
                            weight = float(item["weight"])
                            if tag_name and 0.0 <= weight <= 1.0:
                                tags_profile["applicationScenarios"].append({"name": tag_name, "weight": weight})
                        elif isinstance(item, str) and item.strip():
                            # 兼容旧格式（纯字符串）
                            tags_profile["applicationScenarios"].append({"name": item.strip(), "weight": 0.5})
            
            # 兼容旧格式（如果AI返回了旧格式）
            else:
                # 从核心理念中提取技术相关标签
                if "核心理念" in ai_result and isinstance(ai_result["核心理念"], list):
                    for concept in ai_result["核心理念"]:
                        if isinstance(concept, str) and len(concept.strip()) > 0:
                            tags_profile["coreTechnologies"].append({"name": concept.strip(), "weight": 0.8})
                
                # 从核心技术组件中提取标签
                if "核心技术组件" in ai_result and isinstance(ai_result["核心技术组件"], list):
                    for component in ai_result["核心技术组件"]:
                        if isinstance(component, dict) and "组件名称" in component:
                            component_name = component["组件名称"]
                            if isinstance(component_name, str) and len(component_name.strip()) > 0:
                                tags_profile["coreTechnologies"].append({"name": component_name.strip(), "weight": 0.7})
                
                # 从关键特征中提取应用场景相关标签
                if "关键特征" in ai_result and isinstance(ai_result["关键特征"], list):
                    for feature in ai_result["关键特征"]:
                        if isinstance(feature, str) and len(feature.strip()) > 0:
                            keywords = self._extract_keywords_from_feature(feature)
                            for keyword in keywords:
                                tags_profile["applicationScenarios"].append({"name": keyword, "weight": 0.5})
            
            # 清理和去重标签，按权重排序
            for tag_type in tags_profile:
                # 过滤空标签
                tags_profile[tag_type] = [tag for tag in tags_profile[tag_type] 
                                        if tag and isinstance(tag, dict) and tag.get("name") and tag["name"].strip()]
                
                # 去重（基于标签名称）
                seen_names = set()
                unique_tags = []
                for tag in tags_profile[tag_type]:
                    tag_name = tag["name"]
                    if tag_name not in seen_names:
                        seen_names.add(tag_name)
                        unique_tags.append(tag)
                
                # 按权重降序排序，限制标签数量
                unique_tags.sort(key=lambda x: x["weight"], reverse=True)
                tags_profile[tag_type] = unique_tags[:10]
            
            logger.info(f"转换后的标签画像: {tags_profile}")
            return tags_profile
            
        except Exception as e:
            logger.error(f"转换AI结果时发生错误: {e}")
            # 返回默认标签
            return {
                "coreTechnologies": [{"name": "AI生成标签", "weight": 0.8}],
                "applicationScenarios": [{"name": "智能应用", "weight": 0.6}]
            }
    
    def _extract_keywords_from_feature(self, feature_text: str) -> List[str]:
        """
        从特征描述中提取关键词.
        
        Args:
            feature_text: 特征描述文本
            
        Returns:
            List[str]: 提取的关键词列表
        """
        keywords = []

        # 简单的关键词提取逻辑
        # 可以在这里添加更复杂的NLP处理
        important_words = []

        # 提取一些常见的技术关键词
        tech_keywords = ["技术", "系统", "平台", "算法", "数据", "智能", "自动化", "数字化", "网络", "软件", "硬件"]
        for keyword in tech_keywords:
            if keyword in feature_text:
                important_words.append(keyword)

        # 提取一些应用场景关键词
        app_keywords = ["应用", "服务", "解决方案", "管理", "监控", "分析", "处理", "存储", "传输"]
        for keyword in app_keywords:
            if keyword in feature_text:
                important_words.append(keyword)

        return important_words[:3]  # 最多返回3个关键词

    async def polish_text_with_deepseek(self, user_text: str) -> str:
        """
        使用DeepSeek API润色用户输入的文本.

        Args:
            user_text: 用户输入的原始文本

        Returns:
            str: 润色后的文本
        """
        logger.info("----------- 开始使用DeepSeek润色文本 -----------")
        logger.info(f"原始文本: {user_text}")
        logger.info("--------------------------------------")

        try:
            # 构建润色提示词
            system_prompt = """你是一个需求精细化助手。你的任务是将用户的创意描述精细化,补充关键细节,让图像生成AI能更准确地理解需求。

优化策略:
1. 保留用户的核心创意和主要表达,不改变原意
2. 适度补充视觉相关的关键信息(如场景细节、氛围描述、画面构成等)
3. 将模糊的表达具体化(如"好看"→明确是什么风格的好看)
4. 明确主体、场景、风格、情感等关键要素
5. 不要添加与用户意图无关的新主题或复杂元素
6. 优化后的描述长度约为原文的1.5-2倍

请直接返回优化后的文本,不要包含任何多余的解释。"""

            user_prompt = f"请优化以下描述:\n\n{user_text}"

            # DeepSeek API调用
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
                "stream": False
            }

            # 构建SSL上下文
            ssl_context = self._build_ssl_context()

            timeout = aiohttp.ClientTimeout(total=60, connect=30)
            connector = aiohttp.TCPConnector(ssl=ssl_context)

            # 使用异步请求
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.post(self.api_url, headers=headers, json=data) as response:
                    response.raise_for_status()
                    result = await response.json()
                    polished_text = result['choices'][0]['message']['content'].strip()

                    logger.info("----------- DeepSeek润色结果 -----------")
                    logger.info(f"润色后文本: {polished_text}")
                    logger.info("--------------------------------------")

                    return polished_text

        except Exception as e:
            logger.error(f"DeepSeek文本润色失败: {e}")
            # 失败时返回原始文本
            return user_text


# 创建全局服务实例
ai_communicator_service = AICommunicatorService()

