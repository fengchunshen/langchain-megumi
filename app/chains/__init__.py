"""LangChain chains package."""
from app.chains.fastgpt_retriever import FastGptRetriever
from app.chains.file_extractor_runnable import FileExtractorRunnable, FileExtractorInput
from app.chains.tianyancha_search_runnable import (
    TianyanchaSearchRunnable,
    TianyanchaSearchInput,
    CompanyInfo,
    TianyanchaSearchResult
)

# 保持向后兼容（已废弃，建议使用 FileExtractorRunnable）
from app.chains.file_extractor_runnable import FileExtractorRunnable as OCRRunnable, FileExtractorInput as OCRInput

__all__ = [
    "FastGptRetriever",
    "FileExtractorRunnable",
    "FileExtractorInput",
    "OCRRunnable",
    "OCRInput",
    "TianyanchaSearchRunnable",
    "TianyanchaSearchInput",
    "CompanyInfo",
    "TianyanchaSearchResult"
]

