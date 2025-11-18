"""天眼查API端点 - 提供企业搜索和批量查询功能."""
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, status
from datetime import datetime

from app.models.tianyancha import CompanyBatchQueryResponse
from app.services.tianyancha_batch_service import tianyancha_batch_service
from app.apis.deps import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/batch-query", response_model=CompanyBatchQueryResponse)
async def batch_query_companies(
    file: UploadFile = File(..., description="包含企业名单的Excel文件"),
    api_key: str = Depends(get_api_key)
) -> CompanyBatchQueryResponse:
    """
    批量查询企业信息接口.
    
    接收一个包含企业名单的Excel文件，调用天眼查API查询每个企业的信息，
    并将结果适配到数据库表结构后保存为Excel文件到项目目录.
    
    Args:
        file: 上传的Excel文件，应包含企业名称列（支持列名：企业名称、公司名称、名称等）
        api_key: API密钥（通过依赖注入）
    
    Returns:
        CompanyBatchQueryResponse: 包含查询结果统计和文件保存路径的响应
    
    Raises:
        HTTPException: 当文件格式错误或查询失败时
    """
    try:
        # 检查文件类型
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未提供文件名"
            )
        
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件格式错误，仅支持Excel文件（.xlsx或.xls）"
            )
        
        logger.info(f"收到批量查询请求，文件名: {file.filename}")
        
        # 读取文件内容
        file_content = await file.read()
        
        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件内容为空"
            )
        
        # 调用批量查询服务
        excel_content, total_count, success_count, failed_count = await tianyancha_batch_service.batch_query_companies(file_content)
        
        # 创建输出目录（如果不存在）
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        # 生成输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"企业信息查询结果_{timestamp}.xlsx"
        output_path = output_dir / output_filename
        
        # 保存文件到项目目录
        with open(output_path, "wb") as f:
            f.write(excel_content)
        
        # 获取相对路径（相对于项目根目录）
        relative_path = str(output_path)
        
        logger.info(f"批量查询完成，文件已保存至: {relative_path}")
        
        return CompanyBatchQueryResponse(
            success=True,
            message="批量查询完成，文件已保存",
            total_count=total_count,
            success_count=success_count,
            failed_count=failed_count,
            file_path=relative_path,
            file_name=output_filename,
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"批量查询参数错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"批量查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量查询失败: {str(e)}"
        )

