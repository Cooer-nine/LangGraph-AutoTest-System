"""执行节点 —— 调用 Tool 执行单个步骤"""
import re
from pathlib import Path
from utils.logger import logger
from utils.screenshot import take_screenshot
from config.settings import SCREENSHOT_DIR
from agent.state import AgentState
from agent.tools import TOOL_BY_NAME
from agent.tools.web_tool import _web_screenshot


_EXECUTE_COUNTER = 0


def _resolve_params(params: dict, step_results: list[dict]) -> dict:
    """解析参数中的步骤引用变量，替换为实际执行结果

    支持格式：
      - <从步骤N识别结果获取>  → 步骤N的 vision_analyze 结果中提取验证码
      - <从步骤N结果获取>      → 步骤N的完整结果文本
      - <步骤N>                → 步骤N的完整结果文本
    """
    if not params or not step_results:
        return params

    resolved = {}
    for key, value in params.items():
        if isinstance(value, str):
            # 匹配 <从步骤N...获取> 或 <步骤N>
            m = re.search(r'[<〈]从?步骤(\d+)[^>〉]*[>〉]', value)
            if m:
                step_num = int(m.group(1))
                # step_results 中 step 字段是 1-based
                ref_result = ""
                for sr in step_results:
                    if sr.get("step") == step_num:
                        ref_result = sr.get("result", "")
                        break
                if not ref_result:
                    # fallback: 用索引
                    if 0 <= step_num - 1 < len(step_results):
                        ref_result = step_results[step_num - 1].get("result", "")

                logger.info(f"[execute] 变量替换: {value} → 步骤{step_num}结果")

                if ref_result:
                    # 尝试提取纯验证码文本（vision_analyze 可能返回描述性文字）
                    # 常见格式: "识别结果: ABCD" / "验证码: 1234" / 纯文本
                    captcha = ref_result.strip()
                    # 去掉常见前缀
                    for prefix in ["识别结果:", "识别结果：", "验证码:", "验证码：",
                                   "识别到的验证码是:", "识别到的验证码是：",
                                   "验证码为:", "验证码为："]:
                        if prefix in captcha:
                            captcha = captcha.split(prefix, 1)[1].strip()
                            break
                    # 如果结果太长（超过10字符），可能不是纯验证码，取首行
                    if len(captcha) > 10:
                        captcha = captcha.split('\n')[0].strip()
                    resolved[key] = captcha
                    logger.info(f"[execute] 解析后验证码: '{captcha}'")
                else:
                    logger.warning(f"[execute] 步骤{step_num}结果为空，保留原始值")
                    resolved[key] = value
            else:
                resolved[key] = value
        else:
            resolved[key] = value

    return resolved


def execute_node(state: AgentState) -> dict:
    """执行当前步骤（由 plan 中的 current_step_index 指定）"""
    global _EXECUTE_COUNTER
    _EXECUTE_COUNTER += 1

    idx = state.get("current_step_index", 0)
    plan = state.get("plan", [])
    step_results = list(state.get("step_results", []))

    if idx >= len(plan):
        logger.warning(f"[execute] 步骤索引越界: {idx}/{len(plan)}")
        return {"error": f"步骤索引 {idx} 越界"}

    step = plan[idx]
    tool_name = step.get("tool", "")
    params = dict(step.get("params", {}))
    description = step.get("description", "")

    # 解析参数中的步骤引用变量（如 <从步骤5识别结果获取> → 实际验证码）
    params = _resolve_params(params, step_results)

    logger.info(f"[execute] 步骤 {idx + 1}/{len(plan)}: {tool_name} {params}")

    tool_def = TOOL_BY_NAME.get(tool_name)
    if not tool_def:
        result = f"未知工具: {tool_name}"
        logger.error(f"[execute] {result}")
    else:
        try:
            func = tool_def["function"]
            # vision_analyze: 自动解析 image_path（plan 生成的是通用名，需映射到前一步实际截图）
            if tool_name == "vision_analyze":
                img_path = params.get("image_path", "")
                if img_path and not Path(img_path).is_absolute() and not Path(img_path).exists():
                    for sr in reversed(step_results):
                        if sr.get("screenshot"):
                            params = dict(params)
                            params["image_path"] = sr["screenshot"]
                            logger.info(f"[execute] vision_analyze image_path -> {sr['screenshot']}")
                            break
            result = str(func(**params))
            logger.info(f"[execute] 执行结果: {result[:200]}")
        except Exception as e:
            result = f"工具执行异常: {e}"
            logger.error(f"[execute] {result}")

    # 截图：web 工具用浏览器页面截图（走 _web_screenshot），其他用桌面截图
    screenshot_path = ""
    try:
        if tool_name.startswith("web_"):
            ss_path = _web_screenshot()
            if ss_path:
                screenshot_path = ss_path
        else:
            screenshot_path = str(take_screenshot(f"step_{idx + 1:02d}_{tool_name}"))
    except Exception:
        pass

    step_result = {
        "step": idx + 1,
        "tool": tool_name,
        "params": params,
        "description": description,
        "expected": step.get("expected", ""),
        "result": result,
        "screenshot": screenshot_path,
        "passed": None,
    }
    step_results.append(step_result)

    return {"step_results": step_results}
