"""
截图工具
"""
from datetime import datetime
from pathlib import Path

import pyautogui
from PIL import Image

from config.settings import SCREENSHOT_DIR
from utils.logger import logger


def take_screenshot(name: str = None, region: tuple = None) -> Path:
    """
    截取屏幕截图并保存

    Args:
        name: 截图名称（不含扩展名），默认用时间戳
        region: 截图区域 (left, top, width, height)，None 为全屏

    Returns:
        截图文件路径
    """
    if name is None:
        name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    filepath = SCREENSHOT_DIR / f"{name}.png"
    filepath.parent.mkdir(parents=True, exist_ok=True)

    img: Image = pyautogui.screenshot(region=region)
    img.save(str(filepath))

    logger.debug(f"截图已保存: {filepath}")
    return filepath


def take_screenshot_bytes(region: tuple = None) -> bytes:
    """
    截取屏幕并返回 PNG 字节数据（用于直接传给 Vision API）

    Args:
        region: 截图区域

    Returns:
        PNG 字节数据
    """
    import io
    img = pyautogui.screenshot(region=region)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
