"""OCR 服务 - 使用 DashScope (阿里云通义千问) OCR API."""
from app.models.ocr import OCRRequest, OCRResponse
from app.core.config import settings
import httpx
import logging
import base64
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# 尝试导入 PDF 处理库
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("PyMuPDF 未安装，PDF 文件需要先转换为图片才能使用 OCR")


class OCRService:
    """OCR 服务类."""
    
    def __init__(self):
        """初始化 OCR 服务."""
        self.dashscope_api_key = settings.DASHSCOPE_API_KEY
        self.dashscope_base_url = settings.DASHSCOPE_BASE_URL
        self.dashscope_ocr_model = settings.DASHSCOPE_OCR_MODEL
        self.timeout = settings.TIMEOUT
        
        if not self.dashscope_api_key or not self.dashscope_base_url:
            logger.warning("DashScope OCR 配置不完整，请配置 DASHSCOPE_API_KEY 和 DASHSCOPE_BASE_URL")
    
    def _build_policy_prompt(self, custom_prompt: Optional[str] = None) -> str:
        """
        构建系统策略提示词.
        
        Args:
            custom_prompt: 自定义提示词（可选）
            
        Returns:
            str: 系统提示词
        """
        if custom_prompt:
            return custom_prompt
        
        # 默认的 OCR 策略提示词
        return """你是一个专业的 OCR 文字识别助手。请准确识别图片或PDF中的所有文字内容，保持原始格式和结构。如果是表格，请保持表格结构；如果是文档，请保持段落结构。对于PDF文件，请提取所有页面的文字内容。"""
    
    def _normalize_ocr_output(self, text: str) -> str:
        """
        规范化 OCR 输出文本.
        
        Args:
            text: 原始 OCR 输出文本
            
        Returns:
            str: 规范化后的文本
        """
        if not text:
            return ""
        
        # 去除首尾空白
        text = text.strip()
        
        # 移除可能的 markdown 代码块标记
        if text.startswith("```"):
            lines = text.split("\n")
            # 移除第一行和最后一行（如果它们是代码块标记）
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        
        return text.strip()
    
    def _is_pdf(self, url: Optional[str] = None, base64_data: Optional[str] = None) -> bool:
        """
        检测是否为 PDF 文件.
        
        Args:
            url: URL 字符串
            base64_data: Base64 数据
            
        Returns:
            bool: 是否为 PDF 文件
        """
        if url:
            if url.startswith("data:application/pdf") or ".pdf" in url.lower():
                return True
        if base64_data:
            if base64_data.startswith("data:application/pdf"):
                return True
            # 检查 PDF 文件头（PDF 文件通常以 %PDF 开头）
            try:
                if base64_data.startswith("data:"):
                    # 提取 base64 部分
                    base64_part = base64_data.split(",", 1)[1]
                else:
                    base64_part = base64_data
                decoded = base64.b64decode(base64_part[:100])  # 只解码前100字节
                if decoded.startswith(b"%PDF"):
                    return True
            except:
                pass
        return False
    
    def _pdf_to_images(self, pdf_base64: str) -> List[str]:
        """
        将 PDF 文件转换为图片的 base64 列表.
        
        Args:
            pdf_base64: PDF 文件的 base64 编码（支持 data URL 格式）
            
        Returns:
            List[str]: 每页图片的 base64 data URL 列表
        """
        if not PDF_SUPPORT:
            raise ValueError("PDF 转换功能需要安装 PyMuPDF: pip install PyMuPDF")
        
        # 提取 base64 部分
        if pdf_base64.startswith("data:application/pdf;base64,"):
            base64_part = pdf_base64.split(",", 1)[1]
        elif pdf_base64.startswith("data:"):
            # 可能没有 base64 标记
            base64_part = pdf_base64.split(",", 1)[1] if "," in pdf_base64 else pdf_base64
        else:
            base64_part = pdf_base64
        
        # 解码 PDF 数据
        pdf_data = base64.b64decode(base64_part)
        
        # 使用 PyMuPDF 打开 PDF
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        
        images = []
        try:
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # 渲染页面为图片（300 DPI，高质量）
                mat = fitz.Matrix(2.0, 2.0)  # 缩放因子 2.0 = 200% = 约 300 DPI
                pix = page.get_pixmap(matrix=mat)
                
                # 转换为 PNG bytes
                img_bytes = pix.tobytes("png")
                
                # 转换为 base64
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                img_data_url = f"data:image/png;base64,{img_base64}"
                
                images.append(img_data_url)
                
                logger.info(f"PDF 第 {page_num + 1}/{len(pdf_document)} 页已转换为图片")
        finally:
            pdf_document.close()
        
        return images
    
    def _build_image_content(self, image_url: Optional[str], image_base64: Optional[str]) -> Dict[str, Any]:
        """
        构建图片/PDF 内容，用于 DashScope API.
        
        Args:
            image_url: 图片/PDF URL
            image_base64: 图片/PDF Base64 编码（支持 data URL 格式）
            
        Returns:
            Dict[str, Any]: 内容字典
        """
        if image_url:
            return {
                "type": "image_url",
                "image_url": {
                    "url": image_url
                }
            }
        elif image_base64:
            # 如果已经是 data URL 格式，直接使用
            if image_base64.startswith("data:"):
                return {
                    "type": "image_url",
                    "image_url": {
                        "url": image_base64
                    }
                }
            else:
                # 假设是图片，添加通用的 data URL 前缀
                image_base64 = f"data:image/png;base64,{image_base64}"
                return {
                    "type": "image_url",
                    "image_url": {
                        "url": image_base64
                    }
                }
        else:
            raise ValueError("必须提供 image_url 或 image_base64")
    
    async def _call_dashscope_ocr(
        self,
        image_content: Dict[str, Any],
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        调用 DashScope OCR API.
        
        Args:
            image_content: 图片内容字典
            custom_prompt: 自定义提示词（可选）
            
        Returns:
            str: 识别出的文本
        """
        # 构建 API URL
        api_url = f"{self.dashscope_base_url.rstrip('/')}/chat/completions"
        
        # 构建用户消息内容
        default_prompt = "请识别图片中的所有文字内容，保持原始格式和结构。如果是表格，请保持表格结构；如果是文档，请保持段落结构。"
        user_content = [
            image_content,
            {
                "type": "text",
                "text": custom_prompt or default_prompt
            }
        ]
        
        # 构建请求数据
        payload = {
            "model": self.dashscope_ocr_model,
            "messages": [
                {
                    "role": "system",
                    "content": self._build_policy_prompt(custom_prompt)
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4096
        }
        
        headers = {
            "Authorization": f"Bearer {self.dashscope_api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"调用 DashScope OCR API: {api_url}, 模型: {self.dashscope_ocr_model}")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                api_url,
                headers=headers,
                json=payload
            )
            
            # 如果请求失败，记录详细的错误信息
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"DashScope API 请求失败，状态码: {response.status_code}")
                logger.error(f"错误详情: {error_detail}")
                try:
                    error_json = response.json()
                    logger.error(f"错误 JSON: {error_json}")
                except:
                    pass
                # 记录简化的 payload（避免日志过大）
                payload_for_log = {
                    "model": payload.get("model"),
                    "messages_count": len(payload.get("messages", [])),
                    "content_type": type(image_content).__name__
                }
                logger.error(f"请求 payload 摘要: {payload_for_log}")
            
            response.raise_for_status()
            
            result = response.json()
            
            # 解析响应
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                return self._normalize_ocr_output(content)
            else:
                raise ValueError(f"DashScope API 返回格式异常: {result}")
    
    async def recognize_text(self, request: OCRRequest) -> OCRResponse:
        """
        识别图片中的文字.
        
        Args:
            request: OCR 请求
            
        Returns:
            OCRResponse: OCR 响应
            
        Raises:
            ValueError: 参数错误
            httpx.HTTPError: HTTP 请求错误
            Exception: 其他错误
        """
        if not request.image_url and not request.image_base64:
            raise ValueError("必须提供 image_url 或 image_base64")
        
        if not self.dashscope_api_key or not self.dashscope_base_url:
            raise ValueError("OCR API 配置不完整，请配置 DASHSCOPE_API_KEY 和 DASHSCOPE_BASE_URL")
        
        try:
            # 检测是否为 PDF 文件
            is_pdf = self._is_pdf(request.image_url, request.image_base64)
            
            if is_pdf:
                # PDF 文件需要转换为图片
                if not PDF_SUPPORT:
                    raise ValueError("PDF 文件处理需要安装 PyMuPDF: pip install PyMuPDF")
                
                logger.info("检测到 PDF 文件，开始转换为图片...")
                
                # 获取 PDF base64 数据
                pdf_base64 = request.image_base64 or request.image_url
                if not pdf_base64:
                    raise ValueError("PDF 文件必须提供 image_base64 或 image_url")
                
                # 如果是 URL，需要先下载
                if pdf_base64.startswith("http://") or pdf_base64.startswith("https://"):
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.get(pdf_base64)
                        response.raise_for_status()
                        pdf_bytes = response.content
                        pdf_base64 = f"data:application/pdf;base64,{base64.b64encode(pdf_bytes).decode('utf-8')}"
                
                # 转换为图片列表
                image_pages = self._pdf_to_images(pdf_base64)
                
                if not image_pages:
                    raise ValueError("PDF 文件转换后没有图片")
                
                logger.info(f"PDF 已转换为 {len(image_pages)} 页图片，开始逐页 OCR...")
                
                # 对每页图片进行 OCR
                all_texts = []
                for page_num, image_data_url in enumerate(image_pages, 1):
                    logger.info(f"处理第 {page_num}/{len(image_pages)} 页...")
                    
                    # 构建图片内容
                    image_content = self._build_image_content(None, image_data_url)
                    
                    # 调用 OCR
                    page_text = await self._call_dashscope_ocr(
                        image_content,
                        custom_prompt=f"请识别第 {page_num} 页中的所有文字内容，保持原始格式和结构。如果是表格，请保持表格结构；如果是文档，请保持段落结构。"
                    )
                    
                    if page_text:
                        # 添加页码标记
                        all_texts.append(f"\n\n--- 第 {page_num} 页 ---\n\n{page_text}")
                
                # 合并所有页面的文本
                text = "\n".join(all_texts)
                logger.info(f"PDF OCR 完成，共 {len(image_pages)} 页，总文本长度: {len(text)}")
            else:
                # 普通图片文件
                image_content = self._build_image_content(request.image_url, request.image_base64)
                text = await self._call_dashscope_ocr(image_content)
                logger.info(f"DashScope OCR 识别成功，文本长度: {len(text)}")
            
            return OCRResponse(
                success=True,
                text=text,
                language=request.language.value if request.language else "auto",
                message="OCR 识别成功"
            )
            
        except Exception as e:
            logger.error(f"DashScope OCR 识别失败: {e}")
            raise Exception(f"OCR 识别失败: {str(e)}")


# 创建全局服务实例
ocr_service = OCRService()

