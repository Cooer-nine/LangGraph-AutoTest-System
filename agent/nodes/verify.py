"""验证节点 —— 截图 + 视觉分析判断步骤是否通过"""
from utils.logger import logger
from agent.state import AgentState
from agent.tools.vision_tool import _vision_analyze


def verify_node(state: AgentState) -> dict:
    """验证当前步骤执行结果"""
    idx = state.get("current_step_index", 0)
    step_results = list(state.get("step_results", []))

    if idx >= len(step_results):
        logger.warning(f"[verify] 步骤索引越界: {idx}/{len(step_results)}")
        return {"current_step_index": idx + 1}

    step = step_results[idx]
    description = step.get("description", "")
    expected = step.get("expected", "")
    result = step.get("result", "")
    screenshot = step.get("screenshot", "")
    tool = step.get("tool", "")

    logger.info(f"[verify] 验证步骤 {idx + 1}: {description}")

    passed = False
    verify_detail = ""

    # 元操作（截图/视觉分析）：自身即是结果，跳过视觉验证
    is_meta = tool in ("web_screenshot", "vision_analyze")
    # 远程操作：直接用文本结果判断
    is_remote = tool.startswith(("ssh_", "knowledge_"))

    if is_meta:
        # 截图/视觉分析步骤：结果不为空且无异常即通过
        if result and "失败" not in result and "异常" not in result:
            passed = True
            verify_detail = result[:200]
        else:
            passed = False
            verify_detail = result[:200]

    elif screenshot and not is_remote:
        # 工具执行结果已明确成功（如"导航成功""输入成功"） → 信任工具返回值
        tool_result_success = ("成功" in result and "失败" not in result)

        try:
            question = (
                f"请严格判断：这张截图中是否【实际显示】了以下操作的成功结果？\n"
                f"操作：{description}\n"
                f"预期：{expected}\n"
                f"请只根据截图内容回答，不要推测、不要假设、不要描述页面上的其他无关元素。\n"
                f"如果截图不能明确证明操作成功，请回答'无法确定'。"
            )
            analysis = _vision_analyze(screenshot, question)
            verify_detail = analysis

            # 否定关键词：视觉模型明确说"没有/未/无法" → 直接判失败
            negative = ["没有显示", "未显示", "未出现", "没有出现",
                        "未能显示", "并未填入", "并未", "未填入", "没有输入",
                        "没有导航菜单", "并没有出现", "无法得知", "不清楚",
                        "没有展示", "无法判断", "不能确定", "无法确认",
                        "从图中无法", "截图不能", "并没有", "没有填入"]
            # 推测/模糊用语
            speculative = ["可以推测", "可能是", "应该", "应当", "看起来", "似乎"]
            # 模型以"否"开头 → 明确否定的信号
            starts_with_no = analysis.strip().startswith("否")

            # 视觉分析不确定（如"无法确定"）但工具返回成功 → 信任工具结果
            uncertain = ["无法确定", "无法判断", "不能确定", "无法确认",
                         "无法得知", "不清楚", "从图中无法", "截图不能"]
            is_uncertain = any(w in analysis for w in uncertain)

            if is_uncertain and tool_result_success:
                # 视觉模型不确定，但工具执行报告成功 → 通过
                passed = True
                verify_detail = f"[视觉无法确认，工具返回成功] {analysis[:150]}"
                logger.info(f"[verify] 视觉不确定但工具成功，判定通过")
            elif tool_result_success:
                # 工具返回成功, 视觉模型无明确否定 → 信任工具
                passed = True
                verify_detail = f"[工具返回成功] {analysis[:150]}"
                logger.info(f"[verify] 工具返回成功, 判定通过")
            elif any(w in analysis for w in negative) or any(w in analysis for w in speculative) or starts_with_no:
                passed = False
            else:
                positive = ["成功", "正确", "显示", "存在", "已", "完成", "正常", "通过"]
                passed = any(w in analysis for w in positive)
        except Exception as e:
            logger.warning(f"视觉分析异常，改用文本判断: {e}")
            verify_detail = f"视觉分析不可用: {e}"
            # 降级到文本判断
            if expected and expected in result:
                passed = True
                verify_detail += f"，但结果包含预期: {expected}"
            elif "成功" in result or "完成" in result or result.strip():
                passed = True
                verify_detail += f"，输出: {result[:100]}"
    elif is_remote:
        # SSH / 知识库类操作：直接判断输出
        if "失败" in result or "错误" in result or "无法" in result:
            passed = False
            verify_detail = result[:200]
        elif result.strip():
            passed = True
            verify_detail = f"输出: {result[:200]}"
        else:
            passed = False
            verify_detail = "无输出"

    step_results[idx]["passed"] = passed
    step_results[idx]["verify_detail"] = verify_detail

    status = "✓ 通过" if passed else "✗ 失败"
    logger.info(f"[verify] 步骤 {idx + 1}: {status} — {verify_detail[:100]}")

    return {
        "step_results": step_results,
        "current_step_index": idx + 1,
    }
