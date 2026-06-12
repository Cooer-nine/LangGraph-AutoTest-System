"""
日志工具（基于 loguru）
"""
import os
from loguru import logger

from config.settings import LOG_CONFIG, LOG_DIR

# 移除默认 handler
logger.remove()

# 添加文件日志
logger.add(
    LOG_DIR / "app_{time:YYYY-MM-DD}.log",
    level=os.getenv("LOG_LEVEL", LOG_CONFIG["level"]),
    rotation=LOG_CONFIG["rotation"],
    retention=LOG_CONFIG["retention"],
    format=LOG_CONFIG["format"],
    encoding="utf-8",
)

# 添加控制台日志
logger.add(
    lambda msg: print(msg, end=""),
    level=os.getenv("LOG_LEVEL", LOG_CONFIG["level"]),
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    colorize=True,
)

# 导出（外部直接 from utils.logger import logger）
__all__ = ["logger"]
