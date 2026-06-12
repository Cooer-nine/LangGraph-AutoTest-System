"""
桌面执行器 — 基于 pywinauto + PyAutoGUI 双模封装

定位策略（优先级降级）：
  1. pywinauto 控件定位（精确，Win32/WPF/WinForms）
  2. 图像模板匹配（PyAutoGUI locateOnScreen）
  3. 坐标操作（由 Agent/Zhipu Vision 提供坐标，兜底用）
"""
import time
from pathlib import Path
from typing import Optional, Union, Tuple

import pyautogui
from PIL import Image

from utils.logger import logger
from utils.screenshot import take_screenshot, take_screenshot_bytes

# 安全设置：将鼠标移到角落会触发 pyautogui 异常，关闭此保护
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.1  # 每个操作后暂停 0.1s


class DesktopExecutor:
    """
    桌面操作执行器

    target 参数支持三种形式：
      - str: 控件名称（"确定按钮"、"用户名输入框"）
      - tuple: (x, y) 坐标
      - Path/str: 图片路径（模板匹配）
    """

    def __init__(self):
        self._app = None          # pywinauto Application
        self._window = None       # 当前窗口
        self._screen_size = pyautogui.size()

    # ── pywinauto 窗口/控件管理 ──────────────────

    def _get_pywinauto(self):
        """延迟导入 pywinauto"""
        try:
            from pywinauto import Desktop, Application
            return Desktop, Application
        except ImportError:
            return None, None

    def find_window(self, title: str) -> bool:
        """
        查找并连接窗口

        Args:
            title: 窗口标题（支持部分匹配）

        Returns:
            是否找到
        """
        Desktop, Application = self._get_pywinauto()
        if Desktop is None:
            logger.warning("pywinauto 未安装，无法查找窗口")
            return False

        try:
            desktop = Desktop(backend="uia")
            windows = desktop.windows()
            for w in windows:
                if title in (w.window_text() or ""):
                    self._window = w
                    logger.info(f"找到窗口: {w.window_text()}")
                    return True
            logger.warning(f"未找到窗口: {title}")
            return False
        except Exception as e:
            logger.error(f"查找窗口异常: {e}")
            return False

    def _try_pywinauto_click(self, control_name: str) -> bool:
        """尝试用 pywinauto 点击控件"""
        Desktop, Application = self._get_pywinauto()
        if Desktop is None:
            return False

        try:
            desktop = Desktop(backend="uia")
            # 搜索所有匹配名称的控件
            for w in desktop.windows():
                try:
                    # 遍历子控件
                    for child in w.descendants():
                        texts = [
                            child.window_text(),
                            getattr(child, "name", ""),
                            getattr(child, "automation_id", ""),
                        ]
                        if control_name in texts:
                            child.click_input()
                            logger.info(f"pywinauto 点击: {control_name}")
                            return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.debug(f"pywinauto 点击失败: {e}")
            return False

    def _try_pywinauto_input(self, control_name: str, text: str) -> bool:
        """尝试用 pywinauto 向控件输入文本"""
        Desktop, Application = self._get_pywinauto()
        if Desktop is None:
            return False

        try:
            desktop = Desktop(backend="uia")
            for w in desktop.windows():
                try:
                    for child in w.descendants():
                        texts = [
                            child.window_text(),
                            getattr(child, "name", ""),
                            getattr(child, "automation_id", ""),
                        ]
                        if control_name in texts:
                            child.click_input()
                            time.sleep(0.1)
                            child.type_keys(text, with_spaces=True)
                            logger.info(f"pywinauto 输入: {control_name} ← {text}")
                            return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.debug(f"pywinauto 输入失败: {e}")
            return False

    def _try_pywinauto_get_text(self, control_name: str) -> tuple[bool, str]:
        """尝试用 pywinauto 获取控件文本"""
        Desktop, Application = self._get_pywinauto()
        if Desktop is None:
            return False, ""

        try:
            desktop = Desktop(backend="uia")
            for w in desktop.windows():
                try:
                    for child in w.descendants():
                        texts = [
                            child.window_text(),
                            getattr(child, "name", ""),
                            getattr(child, "automation_id", ""),
                        ]
                        if control_name in texts:
                            result = child.window_text() or ""
                            return True, result
                except Exception:
                    continue
            return False, ""
        except Exception as e:
            return False, str(e)

    # ── 模板匹配 ─────────────────────────────────

    def _try_template_click(self, image_path: Union[str, Path]) -> bool:
        """在屏幕上匹配图像并点击"""
        try:
            location = pyautogui.locateOnScreen(str(image_path), confidence=0.8)
            if location:
                center = pyautogui.center(location)
                pyautogui.click(center)
                logger.info(f"模板匹配点击: {image_path} → ({center.x}, {center.y})")
                return True
            return False
        except Exception as e:
            logger.debug(f"模板匹配失败: {e}")
            return False

    # ── 公开接口 ─────────────────────────────────

    def screenshot(self, name: str = None) -> Path:
        """截取全屏"""
        return take_screenshot(name)

    def screenshot_bytes(self) -> bytes:
        """截取全屏，返回 PNG 字节"""
        return take_screenshot_bytes()

    def click(
        self,
        target: Union[str, Tuple[int, int], Path],
        description: str = ""
    ) -> bool:
        """
        点击

        Args:
            target: 控件名称 / (x, y)坐标 / 图片路径
            description: 日志用描述

        Returns:
            是否成功
        """
        desc = description or str(target)
        logger.info(f"桌面点击: {desc}")

        # 策略1: pywinauto 控件
        if isinstance(target, str) and not Path(target).exists():
            if self._try_pywinauto_click(target):
                return True

        # 策略2: 模板匹配
        if isinstance(target, (str, Path)):
            path = Path(target)
            if path.exists() and self._try_template_click(path):
                return True

        # 策略3: 坐标点击（由 Agent/Vision 提供）
        if isinstance(target, tuple) and len(target) == 2:
            pyautogui.click(target[0], target[1])
            logger.info(f"坐标点击: ({target[0]}, {target[1]})")
            return True

        logger.error(f"所有策略均失败: {desc}")
        return False

    def double_click(self, target: Union[str, Tuple[int, int]]) -> bool:
        """双击"""
        if isinstance(target, tuple):
            pyautogui.doubleClick(target[0], target[1])
            return True
        # pywinauto 双击
        if self._try_pywinauto_click(target):
            time.sleep(0.05)
            self._try_pywinauto_click(target)
            return True
        return False

    def input(self, target: Union[str, Tuple[int, int]], text: str) -> bool:
        """
        输入文本

        Args:
            target: 控件名称 或 (x, y) 坐标
            text: 文本
        """
        logger.info(f"桌面输入: {target} ← {text}")

        # 策略1: pywinauto
        if isinstance(target, str):
            if self._try_pywinauto_input(target, text):
                return True

        # 策略2: 先点击坐标再输入
        if isinstance(target, tuple):
            pyautogui.click(target[0], target[1])
            time.sleep(0.1)
            pyautogui.write(text)
            return True

        return False

    def get_text(self, target: str) -> tuple[bool, str]:
        """获取控件文本"""
        # pywinauto
        ok, text = self._try_pywinauto_get_text(target)
        if ok:
            return True, text
        return False, ""

    def hotkey(self, *keys: str) -> bool:
        """组合键，如 hotkey('ctrl', 'c')"""
        try:
            pyautogui.hotkey(*keys)
            logger.info(f"组合键: {'+'.join(keys)}")
            return True
        except Exception as e:
            logger.error(f"组合键失败: {e}")
            return False

    def scroll(self, clicks: int, x: int = None, y: int = None) -> bool:
        """滚轮滚动，正数向上"""
        try:
            pyautogui.scroll(clicks, x=x, y=y)
            return True
        except Exception as e:
            logger.error(f"滚轮失败: {e}")
            return False

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """拖拽"""
        pyautogui.moveTo(x1, y1)
        pyautogui.drag(x2 - x1, y2 - y1, duration=duration)

    def move_to(self, x: int, y: int):
        """移动鼠标"""
        pyautogui.moveTo(x, y)

    @property
    def screen_size(self) -> Tuple[int, int]:
        """屏幕分辨率"""
        return self._screen_size


# 全局单例
desktop_executor = DesktopExecutor()
