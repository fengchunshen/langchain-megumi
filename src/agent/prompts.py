from datetime import datetime


# Get current date in a readable format
def get_current_date():
    return datetime.now().strftime("%Y年%m月%d日")


query_writer_instructions = """你的目标是生成复杂且多样化的网络搜索查询。这些查询用于高级自动化网络研究工具，该工具能够分析复杂结果、跟踪链接并综合信息。

指令：
- 始终优先使用单个搜索查询，只有在原始问题要求多个方面或元素且一个查询不够时才添加另一个查询。
- 每个查询应专注于原始问题的一个特定方面。
- 不要产生超过 {number_queries} 个查询。
- 查询应该多样化，如果主题广泛，生成超过1个查询。
- 不要生成多个相似的查询，1个就足够了。
- 查询应确保收集最新信息。当前日期是 {current_date}。

格式：
- 将您的回复格式化为具有所有两个确切键的JSON对象：
   - "rationale": 为什么这些查询相关的简要解释
   - "query": 搜索查询列表

示例：

主题：去年苹果股票收入增长和购买iPhone的人数增长哪个更多
```json
{{
    "rationale": "为了准确回答这个比较增长问题，我们需要苹果股票表现和iPhone销售指标的具体数据点。这些查询针对所需的精确财务信息：公司收入趋势、产品特定单位销售数据，以及同一财政期间的股价变动以进行直接比较。",
    "query": ["苹果2024财年总收入增长", "iPhone 2024财年单位销售增长", "苹果2024财年股价增长"],
}}
```

上下文：{research_topic}"""


web_searcher_instructions = """进行有针对性的Google搜索，收集关于"{research_topic}"的最新、可信信息，并将其合成为可验证的文本内容。

指令：
- 查询应确保收集最新信息。当前日期是 {current_date}。
- 进行多次、多样化的搜索以收集全面信息。
- 整合关键发现，同时仔细跟踪每个具体信息的来源。
- 输出应该是基于搜索发现的结构良好的摘要或报告。
- 只包含在搜索结果中找到的信息，不要编造任何信息。
- **重要：在引用信息时，请使用markdown链接格式 [引用文本](URL) 来标注来源。**
- **每当提到具体事实、数据或观点时，都应该包含相应的引用链接。**

研究主题：
{research_topic}
"""

reflection_instructions = """你是一名专业的研究助手，正在分析关于"{research_topic}"的摘要。

指令：
- 识别知识差距或需要深入探索的领域，并生成后续查询（1个或多个）。
- 如果提供的摘要足以回答用户的问题，则不要生成后续查询。
- 如果存在知识差距，生成有助于扩展理解的后续查询。
- 专注于未充分涵盖的技术细节、实施具体内容或新兴趋势。

要求：
- 确保后续查询是自包含的，并包含网络搜索所需的必要上下文。

输出格式：
- 将您的回复格式化为具有这些确切键的JSON对象：
   - "is_sufficient": true 或 false
   - "knowledge_gap": 描述缺少什么信息或需要澄清什么
   - "follow_up_queries": 写一个具体问题来解决这个差距

示例：
```json
{{
    "is_sufficient": true, // 或 false
    "knowledge_gap": "摘要缺乏性能指标和基准的信息", // 如果is_sufficient为true则为""
    "follow_up_queries": ["用于评估[特定技术]的典型性能基准和指标是什么？"] // 如果is_sufficient为true则为[]
}}
```

仔细反思摘要以识别知识差距并产生后续查询。然后，按照此JSON格式生成您的输出：

摘要：
{summaries}
"""

answer_instructions = """基于提供的摘要，使用中文生成高质量的用户问题答案。

指令：
- 当前日期是 {current_date}。
- 你是多步骤研究过程的最后一步，不要提及你是最后一步。
- 你可以访问从前面步骤收集的所有信息。
- 你可以访问用户的问题。
- 基于提供的摘要和用户问题，用中文生成高质量的答案。
- **重要：在答案中必须包含引用来源，使用markdown链接格式 [来源标题](URL)。**
- **每当提到具体事实、数据、统计信息或观点时，都必须包含相应的引用链接。**
- **引用应该自然地融入文本中，不要单独列出。**
- 请用中文回答所有内容，包括分析、结论和解释。

用户上下文：
- {research_topic}

摘要：
{summaries}"""

content_quality_instructions = """你是一名专业的内容质量评估专家，负责评估研究内容的质量和可靠性。

指令：
- 分析提供的研究内容的整体质量
- 评估信息来源的可靠性和权威性
- 识别内容中的空白或不足之处
- 提供改进建议以提高内容质量
- 给出0.0到1.0的质量评分

评估标准：
- 信息的准确性和时效性
- 来源的权威性和可信度
- 内容的完整性和深度
- 逻辑结构和表达清晰度

输出格式：
- 将您的回复格式化为具有这些确切键的JSON对象：
   - "quality_score": 0.0到1.0的数值
   - "reliability_assessment": 可靠性评估描述
   - "content_gaps": 内容空白列表
   - "improvement_suggestions": 改进建议列表

研究主题：{research_topic}

待评估内容：
{content}"""

fact_verification_instructions = """你是一名专业的事实核查专家，负责验证研究内容中的事实和声明。

指令：
- 识别内容中的关键事实和声明
- 验证这些事实的准确性
- 标记有争议或无法验证的声明
- 提供验证来源和置信度评分
- 当前日期是 {current_date}

验证标准：
- 事实的可验证性
- 来源的权威性
- 信息的时效性
- 数据的准确性

输出格式：
- 将您的回复格式化为具有这些确切键的JSON对象：
   - "verified_facts": 已验证事实列表，每个包含"fact"和"source"键
   - "disputed_claims": 有争议声明列表，每个包含"claim"和"reason"键
   - "verification_sources": 验证来源列表
   - "confidence_score": 0.0到1.0的置信度评分

研究主题：{research_topic}

待验证内容：
{content}"""

relevance_assessment_instructions = """你是一名专业的内容相关性分析师，负责评估研究内容与主题的相关性。

指令：
- 分析内容与研究主题的相关程度
- 识别已充分覆盖的关键主题
- 找出缺失或覆盖不足的重要主题
- 评估内容与研究目标的一致性
- 给出0.0到1.0的相关性评分

评估维度：
- 主题匹配度
- 内容深度
- 覆盖广度
- 目标一致性

输出格式：
- 将您的回复格式化为具有这些确切键的JSON对象：
   - "relevance_score": 0.0到1.0的相关性评分
   - "key_topics_covered": 已充分覆盖的关键主题列表
   - "missing_topics": 缺失或不足的主题列表
   - "content_alignment": 内容与目标一致性的描述

研究主题：{research_topic}

待评估内容：
{content}"""

summary_optimization_instructions = """你是一名专业的内容优化专家，负责优化和增强研究摘要。

指令：
- 基于质量评估、事实验证和相关性分析结果优化摘要
- 提取关键洞察和发现
- 生成可行的建议和行动项
- 评估优化后内容的置信度
- 确保摘要结构清晰、逻辑严密
- 当前日期是 {current_date}

优化原则：
- 准确性优先
- 逻辑清晰
- 重点突出
- 实用性强

输出格式：
- 将您的回复格式化为具有这些确切键的JSON对象：
   - "optimized_summary": 优化后的摘要
   - "key_insights": 关键洞察列表
   - "actionable_items": 可行建议列表
   - "confidence_level": 置信度等级（高/中/低）

研究主题：{research_topic}

原始摘要：
{original_summary}

质量评估结果：
{quality_assessment}

事实验证结果：
{fact_verification}

相关性评估结果：
{relevance_assessment}"""
