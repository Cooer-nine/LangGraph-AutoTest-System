"""桌面操作 Tool —— 封装 pywinauto+PyAutoGUI 执行器"""
from executors.desktop_executor import DesktopExecutor

_executor = DesktopExecutor()


def _desktop_click(target: str) -> str:
    """点击桌面元素"""
    return "点击成功" if _executor.click(target) else f"未找到元素: {target}"


def _desktop_input(target: str, text: str) -> str:
    """向桌面控件输入文本"""
    return "输入成功" if _executor.input(target, text) else f"输入失败: {target}"


def _desktop_screenshot() -> str:
    """截取全屏截图"""
    path = _executor.screenshot()
    return path if path else "截图失败"


def _desktop_find_window(title: str) -> str:
    """查找窗口"""
    return _executor.find_window(title) or f"未找到窗口: {title}"


# === Tool 定义 ===

TOOL_DESKTOP_CLICK = {
    "name": "desktop_click",
    "description": "点击桌面应用程序中的元素",
    "parameters": {"target": "控件名称、图像路径或坐标(x,y)"},
    "function": _desktop_click,
}

TOOL_DESKTOP_INPUT = {
    "name": "desktop_input",
    "description": "向桌面应用程序控件输入文本",
    "parameters": {
        "target": "目标控件描述",
        "text": "要输入的文本",
    },
    "function": _desktop_input,
}

TOOL_DESKTOP_SCREENSHOT = {
    "name": "desktop_screenshot",
    "description": "截取整个桌面屏幕",
    "parameters": {},
    "function": _desktop_screenshot,
}

TOOL_DESKTOP_FIND_WINDOW = {
    "name": "desktop_find_window",
    "description": "查找指定标题的窗口",
    "parameters": {"title": "窗口标题"},
    "function": _desktop_find_window,
}
