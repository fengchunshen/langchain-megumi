"""网页深度抓取和正文提取工具."""
import asyncio
import logging
from typing import Dict, List, Tuple, Optional

import httpx
from bs4 import BeautifulSoup
from readability import Document

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (MegumiBot/1.0; +https://example.com/bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}


async def fetch_html(
    url: str, 
    timeout: float, 
    headers: Dict[str, str]
) -> Tuple[str, Optional[str]]:
    """
    异步抓取单个 URL 的 HTML 内容.
    
    Args:
        url: 要抓取的 URL
        timeout: 超时时间（秒）
        headers: 请求头
        
    Returns:
        Tuple[str, Optional[str]]: (url, html内容或None)
    """
    try:
        async with httpx.AsyncClient(
            timeout=timeout, 
            headers=headers, 
            follow_redirects=True
        ) as client:
            resp = await client.get(url)
            
            # 检查响应状态和内容类型
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "").lower()
                if "text/html" in content_type:
                    return url, resp.text
                else:
                    logger.warning(
                        f"抓取跳过 {url}, content-type={content_type}"
                    )
                    return url, None
            else:
                logger.warning(
                    f"抓取失败 {url}, status={resp.status_code}"
                )
                return url, None
                
    except httpx.TimeoutException:
        logger.warning(f"抓取超时 {url}")
        return url, None
    except Exception as e:
        logger.warning(f"抓取异常 {url}: {e}")
        return url, None


async def fetch_html_batch(
    urls: List[str], 
    timeout: float, 
    concurrency: int, 
    headers: Dict[str, str]
) -> Dict[str, Optional[str]]:
    """
    并发抓取一组 URL 的 HTML 内容.
    
    Args:
        urls: URL 列表
        timeout: 单个请求的超时时间（秒）
        concurrency: 最大并发数
        headers: 请求头
        
    Returns:
        Dict[str, Optional[str]]: URL 到 HTML 内容的映射
    """
    if not urls:
        return {}
    
    semaphore = asyncio.Semaphore(concurrency)

    async def _task(u: str) -> Tuple[str, Optional[str]]:
        async with semaphore:
            return await fetch_html(u, timeout, headers)

    logger.info(f"【网页抓取】开始并发抓取 {len(urls)} 个 URL，并发数={concurrency}")
    
    results = await asyncio.gather(
        *[_task(u) for u in urls], 
        return_exceptions=True
    )
    
    # 处理结果和异常
    html_map = {}
    success_count = 0
    
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"【网页抓取】任务异常: {result}")
            continue
        
        url, html = result
        html_map[url] = html
        if html:
            success_count += 1
    
    logger.info(
        f"【网页抓取】抓取完成，成功 {success_count}/{len(urls)} 个"
    )
    
    return html_map


def extract_main_text(html: str, base_url: str = "") -> str:
    """
    从 HTML 中提取正文内容.
    
    优先使用 readability-lxml 提取核心内容，
    失败则回退到 BeautifulSoup 提取 article 或 p 标签。
    
    Args:
        html: HTML 内容
        base_url: 基础 URL（用于相对链接解析，当前未使用）
        
    Returns:
        str: 提取的正文文本
    """
    if not html:
        return ""

    try:
        # 尝试使用 readability 提取主要内容
        doc = Document(html)
        article_html = doc.summary(html_partial=True)
        soup = BeautifulSoup(article_html, "lxml")
        text = soup.get_text(separator="\n")
        
        # 如果提取的内容太短，可能提取失败，回退到 BeautifulSoup
        if len(text.strip()) < 100:
            raise ValueError("Readability 提取内容过短，回退到 BeautifulSoup")
            
    except Exception as e:
        logger.debug(f"Readability 提取失败，回退到 BeautifulSoup: {e}")
        
        # 回退方案：使用 BeautifulSoup 提取
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            # 如果 lxml 失败，使用 html.parser
            soup = BeautifulSoup(html, "html.parser")
        
        # 优先提取 article 标签
        article = soup.find("article")
        if article:
            text = article.get_text(separator="\n")
        else:
            # 提取所有 p 标签
            paragraphs = [p.get_text(separator=" ") for p in soup.find_all("p")]
            text = "\n".join(paragraphs)

    # 简单清洗：去除多余空白行
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join([ln for ln in lines if ln])
    
    return text


def clean_and_truncate(text: str, max_chars: int) -> str:
    """
    清洗和截断文本.
    
    规范化空白字符并按字符上限截断，避免超长 prompt。
    
    Args:
        text: 输入文本
        max_chars: 最大字符数
        
    Returns:
        str: 清洗和截断后的文本
    """
    if not text:
        return ""
    
    # 规范化空白字符（将多个空格/换行合并为单个空格）
    text = " ".join(text.split())
    
    # 截断
    if len(text) > max_chars:
        text = text[:max_chars]
        # 尝试在最后一个句号处截断，避免截断句子
        last_period = text.rfind("。")
        if last_period > max_chars * 0.8:  # 如果句号在后 20% 范围内
            text = text[:last_period + 1]
        else:
            # 否则在最后一个空格处截断
            last_space = text.rfind(" ")
            if last_space > max_chars * 0.8:
                text = text[:last_space]
    
    return text


async def scrape_webpages(
    urls: List[str],
    timeout: float = 20.0,
    concurrency: int = 5,
    max_per_doc_chars: int = 20000,
    user_agent: str = DEFAULT_HEADERS["User-Agent"]
) -> List[Tuple[str, str]]:
    """
    抓取并提取网页正文的便捷函数.
    
    Args:
        urls: URL 列表
        timeout: 单个请求超时时间（秒）
        concurrency: 最大并发数
        max_per_doc_chars: 单个文档最大字符数
        user_agent: User-Agent 字符串
        
    Returns:
        List[Tuple[str, str]]: (URL, 正文内容) 的列表，仅包含成功的结果
    """
    if not urls:
        return []
    
    # 设置请求头
    headers = {**DEFAULT_HEADERS, "User-Agent": user_agent}
    
    # 并发抓取 HTML
    html_map = await fetch_html_batch(urls, timeout, concurrency, headers)
    
    # 提取正文
    results = []
    for url in urls:
        html = html_map.get(url)
        if not html:
            continue
        
        text = extract_main_text(html, base_url=url)
        if not text:
            continue
        
        # 清洗和截断
        text = clean_and_truncate(text, max_per_doc_chars)
        if text:
            results.append((url, text))
    
    logger.info(
        f"【正文提取】成功提取 {len(results)}/{len(urls)} 个网页的正文"
    )
    
    return results

