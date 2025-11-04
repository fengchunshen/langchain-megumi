from datetime import datetime


def get_current_date():
    return datetime.now().strftime("%B %d, %Y")


query_writer_instructions = """Your goal is to generate sophisticated and diverse web search queries. These queries are intended for an advanced automated web research tool capable of analyzing complex results, following links, and synthesizing information.

Instructions:
- Always prefer a single search query, only add another query if the original question requests multiple aspects or elements and one query is not enough.
- Each query should focus on one specific aspect of the original question.
- Don't produce more than {number_queries} queries.
- Queries should be diverse, if the topic is broad, generate more than 1 query.
- Don't generate multiple similar queries, 1 is enough.
- Query should ensure that the most current information is gathered. The current date is {current_date}.

Format: 
- Format your response as a JSON object with ALL two of these exact keys:
   - "rationale": Brief explanation of why these queries are relevant
   - "query": A list of search queries

Example:

Topic: What revenue grew more last year apple stock or the number of people buying an iphone
```json
{{
    "rationale": "To answer this comparative growth question accurately, we need specific data points on Apple's stock performance and iPhone sales metrics. These queries target the precise financial information needed: company revenue trends, product-specific unit sales figures, and stock price movement over the same fiscal period for direct comparison.",
    "query": ["Apple total revenue growth fiscal year 2024", "iPhone unit sales growth fiscal year 2024", "Apple stock price growth fiscal year 2024"],
}}
```

Context: {research_topic}"""


web_searcher_instructions = """Conduct targeted Google Searches to gather the most recent, credible information on "{research_topic}" and synthesize it into a verifiable text artifact.

Instructions:
- Query should ensure that the most current information is gathered. The current date is {current_date}.
- Conduct multiple, diverse searches to gather comprehensive information.
- Consolidate key findings while meticulously tracking the source(s) for each specific piece of information.
- The output should be a well-written summary or report based on your search findings. 
- Only include the information found in the search results, don't make up any information.

Research Topic:
{research_topic}
"""


reflection_instructions = """你是一名专业的研究评估专家，负责判断当前收集的信息是否足以回答用户的问题。

研究主题："{research_topic}"

核心任务：
**首要原则：如果已有信息能够充分回答用户的问题，必须将 is_sufficient 设为 true。**

判断标准：
1. 信息充足性评估（设为 true 的条件）：
   - 已收集的信息能够全面、准确地回答用户的核心问题
   - 关键数据、事实、政策、案例等都已获取
   - 信息来源可靠且相互印证
   - 能够形成完整的逻辑链条和结论

2. 需要继续研究（设为 false 的条件）：
   - 用户问题的核心要点尚未覆盖
   - 缺少关键数据或具体数字
   - 信息存在明显矛盾或不一致
   - 重要的背景信息缺失

注意事项：
- 不要过度追求完美，80-90% 的信息覆盖度已经足够
- 避免为了细枝末节继续搜索
- 优先考虑用户问题的核心需求
- 当前已经是第 {loop_count} 轮研究，应倾向于判断为充足（除非确实缺少关键信息）

输出格式：
- 将您的回复格式化为具有这些确切键的JSON对象：
   - "is_sufficient": true（信息充足）或 false（需要继续研究）
   - "knowledge_gap": 如果 is_sufficient 为 false，描述缺少什么关键信息；如果为 true，填写空字符串 ""
   - "follow_up_queries": 如果 is_sufficient 为 false，生成1-3个后续搜索查询；如果为 true，填写空数组 []

示例1（信息充足）：
```json
{{
    "is_sufficient": true,
    "knowledge_gap": "",
    "follow_up_queries": []
}}
```

示例2（信息不足）：
```json
{{
    "is_sufficient": false,
    "knowledge_gap": "缺少具体的补贴金额和申请条件等关键政策细节",
    "follow_up_queries": ["青浦区高新技术企业补贴具体金额和申请条件"]
}}
```

当前已收集的研究摘要：
{summaries}

请仔细评估上述信息是否足以回答用户的问题"{research_topic}"，并按照JSON格式输出判断结果。"""


answer_instructions = """基于提供的研究材料，生成一份高质量、详细的调查研究报告。

指令：
- 当前日期是 {current_date}
- 你需要撰写一份完整、详细、结构化的调查研究报告
- 报告必须高度围绕用户的提问，直接回应用户的具体需求
- 报告长度应在 2000-5000 字，确保内容充实、论述详尽
- 使用专业的 Markdown 格式，包含标题（#）、子标题（##）、列表、表格等
- 必须在报告中正确引用来源，使用 markdown 格式（例如：[标题](https://vertexaisearch.cloud.google.com/id/1-0)）
- 不要只写摘要性的内容，要展开详细的分析和论述

报告结构要求：
1. 概述/执行摘要：简要说明研究目标和核心结论（200-300字）
2. 背景与目标：详细阐述研究背景和目标（300-500字）
3. 详细发现：展开详细的研究发现，分多个子章节论述（1000-2000字）
   - 使用子标题组织内容
   - 每个重要发现都要有数据和来源支持
   - 使用列表、表格等增强可读性
4. 数据分析与支撑：提供关键数据和分析（500-800字）
5. 结论与建议：给出具体、可操作的建议（500-800字）
6. 数据来源：列出主要参考来源

撰写原则：
- 专业性：使用专业术语和规范的报告语言
- 详实性：不要只给结论，要展开论述和分析
- 可读性：使用清晰的结构和格式
- 实用性：提供具体、可操作的建议

用户提问（研究主题）：
{research_topic}

研究材料：
{summaries}

请生成一份详细、完整的调查研究报告，直接回答用户的问题。"""


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
   - "verified_facts_text": 已验证事实的文本描述列表（字符串数组）
   - "verified_facts_sources": 已验证事实对应的来源列表（字符串数组，与verified_facts_text顺序一一对应）
   - "disputed_claims_text": 有争议声明的文本描述列表（字符串数组）
   - "disputed_claims_reasons": 争议原因列表（字符串数组，与disputed_claims_text顺序一一对应）
   - "verification_sources": 用于验证的所有来源列表（字符串数组）
   - "confidence_score": 0.0到1.0的置信度评分（浮点数）

注意：verified_facts_text 和 verified_facts_sources 必须长度相同且顺序对应，disputed_claims_text 和 disputed_claims_reasons 也必须长度相同且顺序对应。

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


summary_optimization_instructions = """你是一名专业的调查研究报告撰写专家，负责将研究材料整合成高质量的调查研究报告。

指令：
- 基于所有研究材料，撰写一份详细、完整、结构化的调查研究报告
- 报告必须高度围绕用户的提问，直接回应用户的需求
- 报告应包含：背景分析、详细发现、数据支持、具体建议等完整章节
- 报告长度应在 2000-5000 字，确保内容充实、论述详尽
- 使用专业的报告格式，包含标题、章节、要点等结构化内容
- 确保所有关键信息都有数据和来源支持
- 当前日期是 {current_date}

报告撰写原则：
- 准确性优先：所有信息必须有据可查
- 结构清晰：使用标题、子标题、列表等组织内容
- 内容详实：不要只写摘要，要展开详细论述
- 实用性强：提供具体、可操作的建议和方案
- 专业性：使用专业术语和规范的报告格式

报告结构建议：
1. 概述/执行摘要（200-300字）
2. 背景与目标（300-500字）
3. 详细发现（1000-2000字，分多个子章节）
4. 数据分析与支撑（500-800字）
5. 结论与建议（500-800字）
6. 附录/参考信息（如需要）

输出格式：
- 将您的回复格式化为具有这些确切键的JSON对象：
   - "optimized_summary": 完整的调查研究报告（Markdown格式，包含标题、章节结构）
   - "key_insights": 关键洞察列表（内部使用，不输出）
   - "actionable_items": 可行建议列表（内部使用，不输出）
   - "confidence_level": 置信度等级（高/中/低，内部使用）

研究主题（用户提问）：
{research_topic}

原始研究材料：
{original_summary}

质量评估参考：
{quality_assessment}

事实验证参考：
{fact_verification}

相关性评估参考：
{relevance_assessment}

请生成一份详细、完整的调查研究报告，确保报告直接回答用户的问题，并提供充分的细节和论证。"""


