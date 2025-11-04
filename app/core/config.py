"""应用配置管理 - 环境变量和 API Keys."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置类 - 从环境变量加载配置."""
    
    # 应用基础配置
    APP_NAME: str = "Megumi AI Servive"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # API 服务配置
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # OpenAI 配置
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None  # 可选的自定义 API 地址
    OPENAI_MODEL: str = "gpt-4"
    
    # FastGPT 配置
    FASTGPT_API_URL: Optional[str] = None
    FASTGPT_API_KEY: Optional[str] = None
    
    # 绘图服务配置（例如：DALL-E, Stable Diffusion）
    DRAWING_API_KEY: Optional[str] = None
    DRAWING_API_URL: Optional[str] = None
    
    # DashScope (阿里云通义千问) OCR 配置
    DASHSCOPE_API_KEY: Optional[str] = None
    DASHSCOPE_BASE_URL: Optional[str] = None
    DASHSCOPE_OCR_MODEL: str = "qwen-vl-ocr-latest"
    DASHSCOPE_CHAT_MODEL: str = "qwen3-max"
    
    # DeepSeek API 配置
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_URL: Optional[str] = None
    DEEPSEEK_SSL_VERIFY: bool = True
    DEEPSEEK_CA_BUNDLE: Optional[str] = None
    
    # 博查搜索 API 配置
    BOCHA_API_KEY: Optional[str] = None
    
    # Gemini API 配置
    GEMINI_API_URL: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-pro"  # Gemini 模型名称
    
    # RuoYi 后端认证配置
    RUOYI_API_KEY: Optional[str] = None  # 用于验证来自 RuoYi 的请求
    
    # 其他配置
    TIMEOUT: int = 30  # 请求超时时间（秒）
    MAX_RETRIES: int = 3  # 最大重试次数
    API_TIMEOUT: int = 600  # API 请求超时时间（秒），默认10分钟，用于 DeepSearch 等长时间任务
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }


# 创建全局配置实例
settings = Settings()

