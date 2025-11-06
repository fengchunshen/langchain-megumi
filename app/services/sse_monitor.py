"""SSE流监控服务 - 跟踪所有活跃的Server-Sent Events连接."""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """连接状态枚举."""
    ACTIVE = "active"
    CONNECTING = "connecting"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class SSEConnectionInfo:
    """SSE连接信息."""
    connection_id: str
    user_id: Optional[str]
    start_time: float
    status: ConnectionStatus
    request_query: str
    events_sent: int
    last_activity: float
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    error_message: Optional[str] = None


class SSEMonitorService:
    """SSE流监控服务."""
    
    def __init__(self):
        """初始化监控服务."""
        self.active_connections: Dict[str, SSEConnectionInfo] = {}
        self.connection_counter = 0
        self._lock = asyncio.Lock()
        
        # 统计信息
        self.total_connections = 0
        self.successful_connections = 0
        self.failed_connections = 0
        self.average_duration = 0.0
        
        # 配置选项
        self.connection_timeout = 1800  # 30分钟超时
        self.cleanup_interval = 300     # 5分钟清理一次
        
        # 标记清理任务是否已启动
        self._cleanup_task_started = False
        self._cleanup_task = None
    
    async def _ensure_cleanup_task(self):
        """确保清理任务已启动."""
        if not self._cleanup_task_started:
            try:
                # 检查是否有运行中的事件循环
                loop = asyncio.get_running_loop()
                self._cleanup_task = asyncio.create_task(self._cleanup_expired_connections())
                self._cleanup_task_started = True
                logger.debug("SSE连接清理任务已启动")
            except RuntimeError:
                # 没有运行中的事件循环，延迟启动
                logger.debug("当前没有运行中的事件循环，清理任务将延迟启动")
    
    async def create_connection(
        self, 
        user_id: Optional[str] = None,
        request_query: str = "",
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """创建新的SSE连接记录."""
        # 确保清理任务已启动
        await self._ensure_cleanup_task()
        
        async with self._lock:
            self.connection_counter += 1
            connection_id = f"sse_{self.connection_counter}_{int(time.time())}"
            
            connection_info = SSEConnectionInfo(
                connection_id=connection_id,
                user_id=user_id,
                start_time=time.time(),
                status=ConnectionStatus.CONNECTING,
                request_query=request_query[:100],  # 只保存前100字符
                events_sent=0,
                last_activity=time.time(),
                client_ip=client_ip,
                user_agent=user_agent
            )
            
            self.active_connections[connection_id] = connection_info
            self.total_connections += 1
            
            logger.info(f"创建SSE连接: {connection_id}, 用户: {user_id}")
            return connection_id
    
    async def update_activity(self, connection_id: str, events_count: int = 1):
        """更新连接活动状态."""
        if connection_id in self.active_connections:
            async with self._lock:
                conn = self.active_connections[connection_id]
                conn.events_sent += events_count
                conn.last_activity = time.time()
                conn.status = ConnectionStatus.ACTIVE
    
    async def complete_connection(self, connection_id: str):
        """标记连接完成."""
        if connection_id in self.active_connections:
            async with self._lock:
                conn = self.active_connections[connection_id]
                conn.status = ConnectionStatus.COMPLETED
                
                # 更新统计信息
                duration = time.time() - conn.start_time
                if self.successful_connections == 0:
                    self.average_duration = duration
                else:
                    self.average_duration = (self.average_duration * self.successful_connections + duration) / (self.successful_connections + 1)
                
                self.successful_connections += 1
                
                logger.info(f"SSE连接完成: {connection_id}, 耗时: {duration:.2f}秒, 事件数: {conn.events_sent}")
    
    async def error_connection(self, connection_id: str, error_message: str):
        """标记连接错误."""
        if connection_id in self.active_connections:
            async with self._lock:
                conn = self.active_connections[connection_id]
                conn.status = ConnectionStatus.ERROR
                conn.error_message = error_message
                
                self.failed_connections += 1
                
                logger.error(f"SSE连接错误: {connection_id}, 错误: {error_message}")
    
    async def get_stats(self) -> Dict:
        """获取当前统计信息."""
        active_count = len(self.active_connections)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "active_connections": active_count,
            "total_connections": self.total_connections,
            "successful_connections": self.successful_connections,
            "failed_connections": self.failed_connections,
            "average_duration": round(self.average_duration, 2),
            "success_rate": round(
                self.successful_connections / max(self.total_connections, 1) * 100, 2
            ),
            "connection_details": [
                {
                    "connection_id": conn.connection_id,
                    "user_id": conn.user_id,
                    "status": conn.status.value,
                    "duration": round(time.time() - conn.start_time, 2),
                    "events_sent": conn.events_sent,
                    "last_activity": round(time.time() - conn.last_activity, 2)
                }
                for conn in self.active_connections.values()
            ]
        }
    
    async def get_active_users(self) -> Set[str]:
        """获取活跃用户列表."""
        return {conn.user_id for conn in self.active_connections.values() if conn.user_id}
    
    async def _cleanup_expired_connections(self):
        """定期清理过期的连接."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                current_time = time.time()
                expired_ids = []
                
                for conn_id, conn in self.active_connections.items():
                    if current_time - conn.last_activity > self.connection_timeout:
                        expired_ids.append(conn_id)
                        logger.warning(f"SSE连接超时: {conn_id}")
                
                for conn_id in expired_ids:
                    await self.error_connection(conn_id, "连接超时")
                    
            except asyncio.CancelledError:
                logger.info("SSE连接清理任务被取消")
                break
            except Exception as e:
                logger.error(f"清理过期连接时出错: {e}")
    
    async def shutdown(self):
        """优雅关闭监控服务."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("SSE监控服务已关闭")


# 创建全局监控服务实例
sse_monitor = SSEMonitorService()
