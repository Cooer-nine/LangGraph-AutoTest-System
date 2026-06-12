"""规划节点 —— 生成工具调用序列"""
import json
from utils.logger import logger
from agent.llm_client import call_deepseek, extract_json
from agent.prompts.plan_prompt import PLAN_PROMPT
from agent.state import AgentState
from agent.tools import ALL_TOOLS
from knowledge.manager import knowledge_manager


def _format_tools_for_prompt() -> str:
    """将工具列表格式化为 Prompt 可用的描述"""
    lines = []
    for t in ALL_TOOLS:
        params_desc = ", ".join(
            f"{k}: {v}" for k, v in t["parameters"].items()
        ) if t["parameters"] else "无参数"
        lines.append(f"- **{t['name']}({params_desc})**: {t['description']}")
    return "\n".join(lines)


def plan_node(state: AgentState) -> dict:
    """根据测试意图规划操作序列"""
    # 缓存命中：plan 已由 runner 注入 state，直接复用
    existing_plan = state.get("plan")
    if existing_plan:
        logger.info(f"[plan] 使用缓存计划 ({len(existing_plan)} 步骤)，跳过 LLM 规划")
        return {"current_step_index": 0, "step_results": []}

    logger.info("[plan] 开始规划执行步骤...")

    test_intent = state.get("test_intent", {})
    if not test_intent:
        return {"error": "test_intent 为空"}

    intent_json = json.dumps(test_intent, ensure_ascii=False, indent=2)
    tools_desc = _format_tools_for_prompt()

    # ── 知识库检索：根据测试意图检索相关文档，注入上下文 ──
    knowledge_context = ""
    goal = test_intent.get("goal", "")
    if goal:
        try:
            kb_results = knowledge_manager.search(goal, top_k=5)
            if kb_results:
                kb_lines = []
                for i, r in enumerate(kb_results, 1):
                    source = r.get("metadata", {}).get("source", "")
                    kb_lines.append(f"### 相关知识 {i} (来源: {source})")
                    kb_lines.append(r["content"][:400])
                knowledge_context = "\n\n".join(kb_lines)
                logger.info(f"[plan] 知识库检索命中 {len(kb_results)} 条 (goal: {goal[:30]}...)")
        except Exception as e:
            logger.warning(f"[plan] 知识库检索异常: {e}")

    prompt = PLAN_PROMPT.format(
        test_intent=intent_json,
        knowledge_context=knowledge_context or "（未检索到相关知识）",
    )
    prompt += f"\n\n## 当前可用工具完整列表\n{tools_desc}"

    try:
        response = call_deepseek(prompt)
        plan = extract_json(response)
        if isinstance(plan, dict):
            plan = [plan]
        logger.info(f"[plan] 规划完成: {len(plan)} 个步骤")
        for i, step in enumerate(plan):
            logger.info(f"  步骤{i + 1}: {step.get('tool', '?')} → {step.get('description', '?')}")
        return {"plan": plan, "current_step_index": 0, "step_results": []}
    except Exception as e:
        logger.error(f"[plan] 解析失败: {e}")
        return {"error": f"规划失败: {e}"}
