"""系统监控 API 端点."""
from fastapi import APIRouter, HTTPException
from app.services.sse_monitor import sse_monitor
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/sse/status")
async def get_sse_status():
    """
    获取SSE连接状态和统计信息.
    
    返回当前活跃的SSE连接数量、成功率、平均响应时间等指标。
    
    Returns:
        dict: SSE连接状态统计信息
    """
    try:
        stats = await sse_monitor.get_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"获取SSE状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取SSE状态失败: {str(e)}")


@router.get("/sse/active-users")
async def get_active_sse_users():
    """
    获取当前活跃的SSE用户列表.
    
    Returns:
        dict: 活跃用户列表和数量
    """
    try:
        active_users = await sse_monitor.get_active_users()
        return {
            "success": True,
            "data": {
                "active_user_count": len(active_users),
                "active_users": list(active_users)
            }
        }
    except Exception as e:
        logger.error(f"获取活跃用户失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取活跃用户失败: {str(e)}")


@router.get("/system/health")
async def system_health():
    """
    系统健康检查.
    
    Returns:
        dict: 系统健康状态
    """
    try:
        sse_stats = await sse_monitor.get_stats()
        
        # 评估系统健康状态
        health_status = "healthy"
        issues = []
        
        # 检查活跃连接数
        if sse_stats["active_connections"] > 50:
            health_status = "warning"
            issues.append("活跃连接数过高")
        
        # 检查成功率
        if sse_stats["total_connections"] > 0 and sse_stats["success_rate"] < 80:
            health_status = "critical"
            issues.append("SSE连接成功率过低")
        
        # 检查平均响应时间
        if sse_stats["average_duration"] > 300:  # 5分钟
            health_status = "warning"
            issues.append("平均响应时间过长")
        
        return {
            "success": True,
            "data": {
                "status": health_status,
                "timestamp": sse_stats["timestamp"],
                "issues": issues,
                "metrics": {
                    "active_connections": sse_stats["active_connections"],
                    "total_connections": sse_stats["total_connections"],
                    "success_rate": sse_stats["success_rate"],
                    "average_duration": sse_stats["average_duration"]
                }
            }
        }
    except Exception as e:
        logger.error(f"系统健康检查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"系统健康检查失败: {str(e)}")
