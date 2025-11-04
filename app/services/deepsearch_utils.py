from typing import Any, Dict, List
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage


def format_bocha_search_results(webpages: List[Dict[str, Any]]) -> str:
    """
    格式化博查搜索返回的网页结果。
    
    参数:
    - webpages: 博查搜索返回的网页列表
    
    返回:
    - 格式化后的文本字符串
    """
    if not webpages:
        return "未找到相关结果。"
    
    formatted_results = ""
    for idx, page in enumerate(webpages, start=1):
        formatted_results += (
            f"[引用 {idx}]\n"
            f"标题: {page.get('name', 'N/A')}\n"
            f"URL: {page.get('url', 'N/A')}\n"
            f"摘要: {page.get('summary', 'N/A')}\n"
            f"网站名称: {page.get('siteName', 'N/A')}\n"
            f"网站图标: {page.get('siteIcon', 'N/A')}\n"
            f"发布时间: {page.get('dateLastCrawled', 'N/A')}\n\n"
        )
    return formatted_results.strip()


def get_research_topic(messages: List[AnyMessage]) -> str:
    if len(messages) == 1:
        return messages[-1].content
    research_topic = ""
    for message in messages:
        if isinstance(message, HumanMessage):
            research_topic += f"User: {message.content}\n"
        elif isinstance(message, AIMessage):
            research_topic += f"Assistant: {message.content}\n"
    return research_topic


def resolve_urls(urls_to_resolve: List[Any], id: int) -> Dict[str, str]:
    """
    解析 URL 并生成短链接映射。
    
    支持两种格式：
    1. Gemini 搜索结果格式（site.web.uri）
    2. 博查搜索结果格式（Dict with 'url' key）
    """
    prefix = f"https://vertexaisearch.cloud.google.com/id/"
    resolved_map: Dict[str, str] = {}
    
    # 处理博查搜索格式（Dict列表）
    if urls_to_resolve and isinstance(urls_to_resolve[0], dict):
        urls = [site.get('url', '') for site in urls_to_resolve if site.get('url')]
    else:
        # 处理 Gemini 搜索结果格式
        urls = [site.web.uri for site in urls_to_resolve if hasattr(site, 'web')]
    
    for idx, url in enumerate(urls):
        if url and url not in resolved_map:
            resolved_map[url] = f"{prefix}{id}-{idx}"
    return resolved_map


def insert_citation_markers(text: str, citations_list: List[Dict[str, Any]]) -> str:
    sorted_citations = sorted(
        citations_list, key=lambda c: (c["end_index"], c["start_index"]), reverse=True
    )
    modified_text = text
    for citation_info in sorted_citations:
        end_idx = citation_info["end_index"]
        marker_to_insert = ""
        for segment in citation_info["segments"]:
            marker_to_insert += f" [{segment['label']}]({segment['short_url']})"
        modified_text = modified_text[:end_idx] + marker_to_insert + modified_text[end_idx:]
    return modified_text


def get_citations(response: Any, resolved_urls_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    从 Gemini 响应中提取引用信息（保留原功能以兼容）。
    """
    citations: List[Dict[str, Any]] = []
    if not response or not getattr(response, "candidates", None):
        return citations
    candidate = response.candidates[0]
    if (
        not hasattr(candidate, "grounding_metadata")
        or not candidate.grounding_metadata
        or not hasattr(candidate.grounding_metadata, "grounding_supports")
    ):
        return citations
    for support in candidate.grounding_metadata.grounding_supports:
        if not hasattr(support, "segment") or support.segment is None:
            continue
        if support.segment.end_index is None:
            continue
        start_index = support.segment.start_index if support.segment.start_index is not None else 0
        citation: Dict[str, Any] = {
            "start_index": start_index,
            "end_index": support.segment.end_index,
            "segments": [],
        }
        if hasattr(support, "grounding_chunk_indices") and support.grounding_chunk_indices:
            for ind in support.grounding_chunk_indices:
                try:
                    chunk = candidate.grounding_metadata.grounding_chunks[ind]
                    resolved_url = resolved_urls_map.get(chunk.web.uri, None)
                    citation["segments"].append(
                        {
                            "label": chunk.web.title.split(".")[:-1][0],
                            "short_url": resolved_url,
                            "value": chunk.web.uri,
                        }
                    )
                except Exception:
                    pass
        citations.append(citation)
    return citations


def get_citations_from_bocha(
    webpages: List[Dict[str, Any]], 
    resolved_urls_map: Dict[str, str],
    text: str
) -> List[Dict[str, Any]]:
    """
    从博查搜索结果中生成引用信息。
    
    参数:
    - webpages: 博查搜索返回的网页列表
    - resolved_urls_map: URL 到短链接的映射
    - text: LLM 生成的文本
    
    返回:
    - 引用列表，格式与 get_citations 兼容
    """
    import re
    
    citations: List[Dict[str, Any]] = []
    
    if not webpages or not text:
        return citations
    
    # 为每个网页创建一个引用
    # 查找文本中的引用编号模式，如 [1], [2], 引用1, 引用:1 等
    for idx, page in enumerate(webpages, start=1):
        url = page.get('url', '')
        if not url or url not in resolved_urls_map:
            continue
        
        title = page.get('name', '')
        site_name = page.get('siteName', '')
        
        # 查找文本中是否包含引用编号模式
        citation_patterns = [
            rf'\[{idx}\]',  # [1], [2] 等
            rf'\[引用\s*{idx}\]',  # [引用 1], [引用1] 等
            rf'引用\s*{idx}',  # 引用1, 引用 1 等
            rf'引用\s*:\s*{idx}',  # 引用:1 等
            rf'来源\s*{idx}',  # 来源1 等
        ]
        
        found_position = None
        for pattern in citation_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                found_position = match.start()
                break
        
        # 如果没有找到引用编号，尝试查找 URL 或标题
        if found_position is None:
            url_in_text = url in text
            title_in_text = title and title.lower() in text.lower()
            
            if url_in_text:
                found_position = text.rfind(url)
            elif title_in_text:
                found_position = text.lower().rfind(title.lower())
        
        # 如果找到了位置，创建引用
        if found_position is not None:
            # 查找引用编号的结束位置
            end_position = found_position
            for pattern in citation_patterns:
                match = re.search(pattern, text[found_position:found_position+20], re.IGNORECASE)
                if match:
                    end_position = found_position + match.end()
                    break
            
            if end_position == found_position:
                # 如果没有匹配到完整的引用模式，查找下一个空格或标点
                remaining_text = text[found_position:]
                match = re.search(r'[\s\.\,\;]', remaining_text[:50])
                if match:
                    end_position = found_position + match.start()
                else:
                    end_position = found_position + min(50, len(remaining_text))
        else:
            # 如果没有找到，将引用放在文本末尾
            found_position = len(text)
            end_position = len(text)
        
        citation: Dict[str, Any] = {
            "start_index": found_position,
            "end_index": end_position,
            "segments": [
                {
                    "label": title[:50] if title else site_name[:50] if site_name else f"来源{idx}",
                    "short_url": resolved_urls_map.get(url, url),
                    "value": url,
                }
            ],
        }
        citations.append(citation)
    
    return citations


