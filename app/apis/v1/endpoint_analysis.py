"""AI分析API端点 - 提供基于DeepSeek的智能分析功能."""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.models.analysis import (
    NodeAnalysisRequest,
    AnalysisResponse,
    SolutionAnalysisRequest,
    SolutionAnalysisResponse,
    CompanyTagAnalysisRequest,
    CompanyTagAnalysisResponse
)
from app.services.ai_communicator_service import ai_communicator_service
from app.services.ai_agent_service import ai_agent_service
from app.services.company_tag_service import company_tag_service

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()


@router.post("/analyze-node", response_model=AnalysisResponse)
async def analyze_node(request: NodeAnalysisRequest) -> AnalysisResponse:
    """
    分析产业节点.
    
    为给定的产业节点生成标签画像
    
    Args:
        request: 节点分析请求，包含节点名称、父节点信息和兄弟节点信息
        
    Returns:
        AnalysisResponse: 分析结果响应
        
    Raises:
        HTTPException: 当分析失败时
    """
    try:
        logger.info(f"开始分析节点: {request.nodeName}")
        
        # 构建节点信息
        node_to_process = {"name": request.nodeName}
        
        # 生成prompt
        prompt = ai_communicator_service.format_master_prompt(
            node_to_process=node_to_process,
            parent_profile=request.parentProfile,
            siblings_profiles=request.siblingsProfiles
        )
        
        # 调用AI分析
        result = await ai_communicator_service.get_profile_from_ai(prompt)
        
        return AnalysisResponse(
            success=True,
            data=result,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"节点分析失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"节点分析失败: {str(e)}"
        )


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    AI分析服务健康检查.
    
    Returns:
        Dict[str, Any]: 健康检查结果
    """
    try:
        # 检查API密钥是否配置
        if not ai_communicator_service.api_key:
            return {
                "status": "unhealthy",
                "message": "DeepSeek API密钥未配置",
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "status": "healthy",
            "message": "AI分析服务正常运行",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "message": f"健康检查失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


@router.post("/analyze-solution", response_model=SolutionAnalysisResponse)
async def analyze_solution(request: SolutionAnalysisRequest) -> SolutionAnalysisResponse:
    """
    分析解决方案并生成相关标签.

    Args:
        request: 包含解决方案名称和描述的请求对象，包括：
            - solutionName: 解决方案名称
            - description: 解决方案描述

    Returns:
        SolutionAnalysisResponse: 包含标签列表的响应，格式为：
        {
            "success": true,
            "tags": ["智能销售", "AI预测", "SaaS平台", "B2B销售", "CRM分析"],
            "message": "解决方案分析成功"
        }
        
    Raises:
        HTTPException: 当请求参数无效或分析失败时
    """
    try:
        if not request.solutionName.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="解决方案名称不能为空"
            )

        if not request.description.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="解决方案描述不能为空"
            )

        # 调用AI agent服务进行解决方案分析
        result = await ai_agent_service.analyze_solution_for_company(
            request.solutionName,
            request.description
        )

        # 提取标签列表
        tags = result.get('tags', [])

        logger.info(f"解决方案分析成功: {request.solutionName} - 生成{len(tags)}个标签")

        return SolutionAnalysisResponse(
            success=True,
            tags=tags,
            message=f"成功生成 {len(tags)} 个相关标签"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解决方案分析时发生未预期错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}"
        )


@router.post("/analyze-company-tags", response_model=CompanyTagAnalysisResponse)
async def analyze_company_tags(request: CompanyTagAnalysisRequest) -> CompanyTagAnalysisResponse:
    """
    分析企业经营范围并生成相关标签.

    Args:
        request: 包含企业名称和经营范围的请求对象，包括：
            - companyName: 企业名称
            - businessScope: 企业经营范围

    Returns:
        CompanyTagAnalysisResponse: 包含标签列表的响应，格式为：
        {
            "success": true,
            "tags": ["智能制造", "工业互联网", "数字化转型"],
            "message": "企业标签分析成功",
            "timestamp": "2025-01-01T12:00:00"
        }
        
    Raises:
        HTTPException: 当请求参数无效或分析失败时
    """
    try:
        if not request.companyName.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="企业名称不能为空"
            )

        if not request.businessScope.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="企业经营范围不能为空"
            )

        logger.info(f"开始分析企业标签: {request.companyName}")

        # 调用企业标签分析服务
        tags = await company_tag_service.analyze_company_business_scope(
            request.companyName,
            request.businessScope
        )

        logger.info(f"企业标签分析成功: {request.companyName} - 生成{len(tags)}个标签")

        return CompanyTagAnalysisResponse(
            success=True,
            tags=tags,
            message=f"成功生成 {len(tags)} 个相关标签",
            timestamp=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"企业标签分析时发生未预期错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}"
        )

