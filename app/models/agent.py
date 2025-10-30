"""智能体任务编排相关的 Pydantic 数据模型."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class TaskType(str, Enum):
    """任务类型枚举."""
    TEXT_GENERATION = "text_generation"
    QNA = "qna"
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    MULTI_STEP = "multi_step"


class AgentRequest(BaseModel):
    """智能体请求模型."""
    query: str = Field(..., description="用户查询", min_length=1, max_length=5000)
    task_type: Optional[TaskType] = Field(default=TaskType.QNA, description="任务类型")
    context: Optional[Dict[str, Any]] = Field(default=None, description="上下文信息")
    system_prompt: Optional[str] = Field(default=None, description="系统提示词")
    temperature: Optional[float] = Field(default=0.7, description="温度参数", ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=2000, description="最大生成 token 数", ge=1, le=8000)


class AgentResponse(BaseModel):
    """智能体响应模型."""
    success: bool = Field(..., description="是否成功")
    answer: str = Field(..., description="生成的回答")
    reasoning: Optional[str] = Field(default=None, description="推理过程")
    sources: Optional[List[str]] = Field(default=None, description="数据源列表")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")
    message: Optional[str] = Field(default=None, description="附加消息")


class AgentError(BaseModel):
    """智能体错误响应模型."""
    success: bool = Field(default=False, description="是否成功")
    error: str = Field(..., description="错误信息")
    code: Optional[str] = Field(default=None, description="错误代码")

