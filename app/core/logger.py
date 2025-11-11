import json
import logging
from typing import Any, Dict, Optional


def _emit_json(
    logger: logging.Logger,
    level: int,
    事件: str,
    节点: Optional[str] = None,
    **字段: Any,
) -> None:
    """以 JSON 结构化方式输出日志（中文键）.

    Args:
        logger: 日志记录器
        level: 日志级别（logging 常量）
        事件: 事件名称或说明
        节点: 可选，节点名称
        字段: 其他结构化字段
    """
    payload: Dict[str, Any] = {"事件": 事件}
    if 节点:
        payload["节点"] = 节点
    if 字段:
        payload.update(字段)
    # 确保中文不转义，压缩分隔符
    message = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    logger.log(level, message)


def jdebug(logger: logging.Logger, 事件: str, 节点: Optional[str] = None, **字段: Any) -> None:
    _emit_json(logger, logging.DEBUG, 事件, 节点, **字段)


def jinfo(logger: logging.Logger, 事件: str, 节点: Optional[str] = None, **字段: Any) -> None:
    _emit_json(logger, logging.INFO, 事件, 节点, **字段)


def jwarn(logger: logging.Logger, 事件: str, 节点: Optional[str] = None, **字段: Any) -> None:
    _emit_json(logger, logging.WARNING, 事件, 节点, **字段)


def jerror(logger: logging.Logger, 事件: str, 节点: Optional[str] = None, **字段: Any) -> None:
    _emit_json(logger, logging.ERROR, 事件, 节点, **字段)


