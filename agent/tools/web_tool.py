"""Web 操作 Tool —— 封装 Playwright 执行器"""
from executors.web_executor import web_executor as _executor


def _web_navigate(url: str) -> str:
    """导航到指定 URL"""
    success = _executor.navigate(url)
    return f"导航成功: {url}" if success else f"导航失败: {url}"


def _web_click(description: str) -> str:
    """点击页面元素"""
    success = _executor.click(description)
    return f"点击成功: {description}" if success else f"元素未找到或点击失败: {description}"


def _web_input(description: str, text: str) -> str:
    """在输入框中输入文本"""
    success = _executor.input(description, text)
    return f"输入成功: {description} ← '{text}'" if success else f"输入失败(元素未找到): {description}"


def _web_wait(description: str) -> str:
    """等待元素出现"""
    return _executor.wait(description)


def _web_check(description: str, expected: str = "") -> str:
    """检查页面元素状态或文本"""
    ok, text = _executor.check(description, expected)
    if ok:
        return f"检查通过: {description} 包含 '{expected}'"
    return f"检查失败: {text}" if text else f"检查失败: 元素未找到 {description}"


def _web_screenshot() -> str:
    """截取当前页面截图，返回保存路径"""
    return _executor.screenshot()


# === Tool 定义（供 LLM 规划时参考） ===

TOOL_WEB_NAVIGATE = {
    "name": "web_navigate",
    "description": "导航到指定 URL",
    "parameters": {"url": "目标网页地址，如 http://192.168.1.100:8080"},
    "function": _web_navigate,
}

TOOL_WEB_CLICK = {
    "name": "web_click",
    "description": "点击页面上的元素",
    "parameters": {"description": "元素描述，如'登录按钮'、'用户管理'链接"},
    "function": _web_click,
}

TOOL_WEB_INPUT = {
    "name": "web_input",
    "description": "在输入框中输入文本",
    "parameters": {
        "description": "输入框描述，如'用户名输入框'",
        "text": "要输入的文本内容",
    },
    "function": _web_input,
}

TOOL_WEB_WAIT = {
    "name": "web_wait",
    "description": "等待指定元素出现",
    "parameters": {"description": "要等待的元素描述"},
    "function": _web_wait,
}

TOOL_WEB_CHECK = {
    "name": "web_check",
    "description": "检查页面元素状态或文本内容",
    "parameters": {
        "description": "要检查的元素描述",
        "expected": "预期的文本或状态（可选）",
    },
    "function": _web_check,
}

TOOL_WEB_SCREENSHOT = {
    "name": "web_screenshot",
    "description": "截取当前页面截图",
    "parameters": {},
    "function": _web_screenshot,
}
