"""总结节点 —— 汇总所有步骤结果"""
from utils.logger import logger
from agent.state import AgentState


def summarize_node(state: AgentState) -> dict:
    """汇总测试结果"""
    step_results = state.get("step_results", [])
    plan = state.get("plan", [])

    total = len(step_results)
    passed = sum(1 for r in step_results if r.get("passed"))
    failed = total - passed

    lines = []
    lines.append(f"测试完成: {passed}/{total} 步骤通过")
    lines.append("")

    for r in step_results:
        status = "✓" if r.get("passed") else "✗"
        desc = r.get("description", r.get("tool", "?"))
        lines.append(f"  {status} 步骤{r['step']}: {desc}")
        if not r.get("passed"):
            detail = r.get("verify_detail", r.get("result", ""))
            lines.append(f"      原因: {detail[:200]}")

    summary = "\n".join(lines)
    logger.info(f"[summarize] {summary}")
    return {"summary": summary}
