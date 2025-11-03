"""文件信息提取 Runnable - 自动识别文件格式并提取内容."""
from typing import Union, Dict, Any, Optional, List
from langchain_core.documents import Document
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import Field, BaseModel
from app.services.ocr_service import ocr_service
from app.models.ocr import OCRRequest, OCRLanguage
import logging
import asyncio
import base64
import mimetypes
import io
from enum import Enum

logger = logging.getLogger(__name__)

# 尝试导入PDF处理库
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyPDF2 未安装，文本型PDF将无法直接提取文本")


class FileType(str, Enum):
    """文件类型枚举."""
    IMAGE = "image"  # 图片文件
    PDF_IMAGE = "pdf_image"  # 图片型PDF
    PDF_TEXT = "pdf_text"  # 文本型PDF
    TEXT = "text"  # 文本文件
    UNKNOWN = "unknown"  # 未知类型


class FileExtractorInput(BaseModel):
    """文件提取器输入模型."""
    file_url: Optional[str] = Field(default=None, description="文件 URL")
    file_base64: Optional[str] = Field(default=None, description="文件 Base64 编码")
    file_path: Optional[str] = Field(default=None, description="本地文件路径")
    language: Optional[OCRLanguage] = Field(default=OCRLanguage.AUTO, description="OCR识别语言（仅用于图片和图片型PDF）")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="附加元数据")
    force_ocr: Optional[bool] = Field(default=False, description="强制使用OCR（即使是文本型PDF）")


class FileExtractorRunnable(Runnable[Union[str, Dict[str, Any], FileExtractorInput], Document]):
    """
    文件信息提取 Runnable，自动识别文件格式并提取内容.
    
    支持的文件类型：
    - 图片文件（jpg, png, gif等）：使用OCR识别
    - 图片型PDF：使用OCR识别
    - 文本型PDF：直接提取文本
    - 文本文件（txt, md等）：直接读取
    
    使用示例：
    ```python
    extractor = FileExtractorRunnable()
    # 方式1：传入URL
    doc = extractor.invoke({"file_url": "https://example.com/file.pdf"})
    # 方式2：传入base64
    doc = extractor.invoke({"file_base64": "base64_string"})
    # 方式3：传入本地路径
    doc = extractor.invoke({"file_path": "/path/to/file.pdf"})
    ```
    """
    
    def __init__(
        self,
        language: Optional[OCRLanguage] = None
    ):
        """
        初始化文件提取器.
        
        Args:
            language: 默认识别语言（仅用于OCR场景）
        """
        super().__init__()
        self.language = language or OCRLanguage.AUTO
    
    def _detect_file_type(self, filename: Optional[str] = None, content: Optional[bytes] = None) -> FileType:
        """
        检测文件类型.
        
        Args:
            filename: 文件名或URL
            content: 文件内容（可选，用于更准确的检测）
        
        Returns:
            FileType: 文件类型
        """
        if not filename:
            return FileType.UNKNOWN
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(filename)
        
        # 判断文件类型
        if mime_type:
            if mime_type.startswith("image/"):
                return FileType.IMAGE
            elif mime_type == "application/pdf":
                # 判断是图片型PDF还是文本型PDF
                if content:
                    try:
                        if PDF_AVAILABLE:
                            # 尝试读取PDF，检查是否有文本层
                            pdf_file = io.BytesIO(content)
                            pdf_reader = PyPDF2.PdfReader(pdf_file)
                            has_text = False
                            for page in pdf_reader.pages[:3]:  # 检查前3页
                                if page.extract_text().strip():
                                    has_text = True
                                    break
                            return FileType.PDF_TEXT if has_text else FileType.PDF_IMAGE
                    except Exception as e:
                        logger.warning(f"无法判断PDF类型，默认使用OCR: {e}")
                        return FileType.PDF_IMAGE
                # 如果没有content，默认按图片型PDF处理（更安全）
                return FileType.PDF_IMAGE
            elif mime_type.startswith("text/"):
                return FileType.TEXT
        
        # 通过文件扩展名判断
        filename_lower = filename.lower()
        if filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
            return FileType.IMAGE
        elif filename_lower.endswith('.pdf'):
            return FileType.PDF_IMAGE  # 默认按图片型处理
        elif filename_lower.endswith(('.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm')):
            return FileType.TEXT
        
        return FileType.UNKNOWN
    
    def _parse_input(self, input_data: Union[str, Dict[str, Any], FileExtractorInput]) -> FileExtractorInput:
        """
        解析输入数据，转换为 FileExtractorInput 对象.
        
        Args:
            input_data: 输入数据，可以是：
                - str: 文件 URL、base64 或本地路径
                - Dict: 包含 file_url、file_base64、file_path 等字段的字典
                - FileExtractorInput: FileExtractorInput 对象
        
        Returns:
            FileExtractorInput: 解析后的 FileExtractorInput 对象
        """
        if isinstance(input_data, FileExtractorInput):
            return input_data
        elif isinstance(input_data, str):
            # 如果是字符串，判断是 URL、base64 还是路径
            if input_data.startswith(('http://', 'https://')):
                return FileExtractorInput(file_url=input_data, language=self.language)
            elif input_data.startswith('data:'):
                # data URL格式
                return FileExtractorInput(file_base64=input_data, language=self.language)
            elif len(input_data) > 100:  # 假设是base64字符串
                try:
                    # 尝试解码base64验证
                    base64.b64decode(input_data[:100])
                    return FileExtractorInput(file_base64=input_data, language=self.language)
                except:
                    # 如果解码失败，可能是文件路径
                    return FileExtractorInput(file_path=input_data, language=self.language)
            else:
                # 假设是文件路径
                return FileExtractorInput(file_path=input_data, language=self.language)
        elif isinstance(input_data, dict):
            # 从字典构建 FileExtractorInput
            return FileExtractorInput(
                file_url=input_data.get("file_url"),
                file_base64=input_data.get("file_base64"),
                file_path=input_data.get("file_path"),
                language=input_data.get("language", self.language),
                metadata=input_data.get("metadata"),
                force_ocr=input_data.get("force_ocr", False)
            )
        else:
            raise ValueError(f"不支持的输入类型: {type(input_data)}")
    
    async def _extract_text_from_pdf(self, content: bytes) -> str:
        """
        从文本型PDF中提取文本.
        
        Args:
            content: PDF文件内容
        
        Returns:
            str: 提取的文本
        """
        if not PDF_AVAILABLE:
            raise ValueError("PyPDF2 未安装，无法提取PDF文本")
        
        try:
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_parts = []
            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                if page_text.strip():
                    text_parts.append(f"--- 第 {page_num} 页 ---\n{page_text}")
            
            return "\n\n".join(text_parts) if text_parts else ""
        except Exception as e:
            logger.error(f"PDF文本提取失败: {e}")
            raise Exception(f"PDF文本提取失败: {str(e)}")
    
    async def _extract_text_from_file(self, file_path: str) -> str:
        """
        从文本文件中提取文本.
        
        Args:
            file_path: 文件路径
        
        Returns:
            str: 文件内容
        """
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            raise ValueError(f"无法读取文件: {file_path}，尝试了多种编码均失败")
        except Exception as e:
            logger.error(f"文本文件读取失败: {e}")
            raise Exception(f"文本文件读取失败: {str(e)}")
    
    async def _fetch_file_content(self, url: str) -> bytes:
        """
        从URL获取文件内容.
        
        Args:
            url: 文件URL
        
        Returns:
            bytes: 文件内容
        """
        import httpx
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    
    async def _process_file(
        self,
        file_input: FileExtractorInput,
        file_type: FileType,
        content: bytes
    ) -> Document:
        """
        处理文件并提取内容.
        
        Args:
            file_input: 文件输入
            file_type: 文件类型
            content: 文件内容
        
        Returns:
            Document: LangChain Document 对象
        """
        text = ""
        metadata: Dict[str, Any] = {
            "source": "file_extractor",
            "file_type": file_type.value
        }
        
        # 添加用户提供的元数据
        if file_input.metadata:
            metadata.update(file_input.metadata)
        
        # 根据文件类型提取内容
        if file_type == FileType.IMAGE or file_type == FileType.PDF_IMAGE or file_input.force_ocr:
            # 使用OCR提取
            logger.info(f"使用OCR处理文件: {file_type.value}")
            
            # 构建OCR请求
            # 优先使用已有的URL或base64，如果没有则从content构建base64
            ocr_image_url = file_input.file_url
            ocr_image_base64 = file_input.file_base64
            
            # 如果没有URL和base64，但有content，则构建base64
            if not ocr_image_url and not ocr_image_base64 and content:
                # 根据文件类型确定MIME类型
                filename = file_input.file_url or file_input.file_path or "unknown"
                if file_type == FileType.PDF_IMAGE:
                    mime_type = "application/pdf"
                else:
                    mime_type = mimetypes.guess_type(filename)[0] or "image/png"
                ocr_image_base64 = f"data:{mime_type};base64,{base64.b64encode(content).decode('utf-8')}"
            
            ocr_request = OCRRequest(
                image_url=ocr_image_url,
                image_base64=ocr_image_base64,
                language=file_input.language
            )
            
            ocr_response = await ocr_service.recognize_text(ocr_request)
            
            if not ocr_response.success:
                error_msg = ocr_response.message or "OCR识别失败"
                logger.error(f"OCR识别失败: {error_msg}")
                raise Exception(f"OCR识别失败: {error_msg}")
            
            text = ocr_response.text
            metadata["language"] = ocr_response.language or "unknown"
            metadata["extraction_method"] = "ocr"
            
            # 添加文本块信息（如果有）
            if ocr_response.text_blocks:
                metadata["text_blocks_count"] = len(ocr_response.text_blocks)
                metadata["text_blocks"] = [
                    {
                        "text": block.text,
                        "confidence": block.confidence,
                        "bbox": block.bbox
                    }
                    for block in ocr_response.text_blocks
                ]
        
        elif file_type == FileType.PDF_TEXT:
            # 直接提取PDF文本
            logger.info("从文本型PDF提取文本")
            text = await self._extract_text_from_pdf(content)
            metadata["extraction_method"] = "pdf_text_extraction"
        
        elif file_type == FileType.TEXT:
            # 读取文本文件
            if file_input.file_path:
                logger.info(f"读取文本文件: {file_input.file_path}")
                text = await self._extract_text_from_file(file_input.file_path)
            else:
                # 如果是URL或base64的文本文件，需要先下载
                if file_input.file_url:
                    content = await self._fetch_file_content(file_input.file_url)
                    text = content.decode('utf-8', errors='ignore')
                elif file_input.file_base64:
                    if file_input.file_base64.startswith('data:'):
                        # data URL格式
                        base64_part = file_input.file_base64.split(',', 1)[1]
                        text = base64.b64decode(base64_part).decode('utf-8', errors='ignore')
                    else:
                        text = base64.b64decode(file_input.file_base64).decode('utf-8', errors='ignore')
                else:
                    raise ValueError("无法确定文本文件来源")
            metadata["extraction_method"] = "text_file_reading"
        
        else:
            raise ValueError(f"不支持的文件类型: {file_type.value}")
        
        # 添加文件来源信息
        if file_input.file_url:
            metadata["file_url"] = file_input.file_url
        if file_input.file_path:
            metadata["file_path"] = file_input.file_path
        if file_input.file_base64:
            metadata["file_source"] = "base64"
        
        # 创建并返回Document对象
        document = Document(
            page_content=text,
            metadata=metadata
        )
        
        logger.info(f"文件提取完成，文本长度: {len(text)}")
        return document
    
    async def ainvoke(
        self,
        input: Union[str, Dict[str, Any], FileExtractorInput],
        config: Optional[RunnableConfig] = None
    ) -> Document:
        """
        异步调用文件提取器.
        
        Args:
            input: 输入数据（文件URL、base64、路径或FileExtractorInput对象）
            config: Runnable配置
        
        Returns:
            Document: LangChain Document对象，包含提取的文本
        
        Raises:
            ValueError: 输入参数错误
            Exception: 文件提取失败
        """
        # 解析输入
        file_input = self._parse_input(input)
        
        # 获取文件名用于类型检测
        filename = file_input.file_url or file_input.file_path or "unknown"
        
        # 获取文件内容
        content: Optional[bytes] = None
        if file_input.file_path:
            # 读取本地文件
            with open(file_input.file_path, 'rb') as f:
                content = f.read()
        elif file_input.file_url:
            # 从URL下载文件
            content = await self._fetch_file_content(file_input.file_url)
        elif file_input.file_base64:
            # 解码base64
            if file_input.file_base64.startswith('data:'):
                base64_part = file_input.file_base64.split(',', 1)[1]
                content = base64.b64decode(base64_part)
            else:
                content = base64.b64decode(file_input.file_base64)
        
        # 检测文件类型
        file_type = self._detect_file_type(filename, content)
        
        if file_type == FileType.UNKNOWN:
            logger.warning(f"无法识别文件类型: {filename}，尝试使用OCR")
            file_type = FileType.IMAGE  # 默认按图片处理
        
        # 如果没有内容但需要OCR，需要特殊处理
        if not content and (file_type == FileType.IMAGE or file_type == FileType.PDF_IMAGE or file_input.force_ocr):
            # OCR场景可以使用URL或base64，不需要content
            pass
        elif not content:
            raise ValueError("无法获取文件内容")
        
        # 处理文件
        return await self._process_file(file_input, file_type, content or b"")
    
    def invoke(
        self,
        input: Union[str, Dict[str, Any], FileExtractorInput],
        config: Optional[RunnableConfig] = None
    ) -> Document:
        """
        同步调用文件提取器.
        
        Args:
            input: 输入数据（文件URL、base64、路径或FileExtractorInput对象）
            config: Runnable配置
        
        Returns:
            Document: LangChain Document对象，包含提取的文本
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.ainvoke(input, config))
    
    def batch(
        self,
        inputs: List[Union[str, Dict[str, Any], FileExtractorInput]],
        config: Optional[RunnableConfig] = None,
        **kwargs
    ) -> List[Document]:
        """
        批量处理多个文件.
        
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
    
    async def abatch(
        self,
        inputs: List[Union[str, Dict[str, Any], FileExtractorInput]],
        config: Optional[RunnableConfig] = None,
        **kwargs
    ) -> List[Document]:
        """
        异步批量处理多个文件.
        
        Args:
            inputs: 输入数据列表
            config: Runnable配置
            **kwargs: 其他参数
        
        Returns:
            List[Document]: Document对象列表
        """
        # 并发处理所有输入
        tasks = [self.ainvoke(input_item, config) for input_item in inputs]
        return await asyncio.gather(*tasks)

