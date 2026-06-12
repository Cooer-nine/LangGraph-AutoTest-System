"""理解节点 —— 解析自然语言测试用例为结构化意图"""
from utils.logger import logger
from agent.llm_client import call_deepseek, extract_json
from agent.prompts.understand_prompt import UNDERSTAND_PROMPT
from agent.state import AgentState


def understand_node(state: AgentState) -> dict:
    """理解自然语言用例，输出结构化测试意图"""
    # 缓存命中：plan 已由 runner 注入 state，直接跳过
    if state.get("plan"):
        logger.info("[understand] 使用缓存计划，跳过理解")
        return {}

    logger.info("[understand] 开始理解测试用例...")

    user_query = state.get("user_query", "")
    if not user_query:
        return {"error": "user_query 为空"}

    prompt = UNDERSTAND_PROMPT.format(user_query=user_query)

    try:
        response = call_deepseek(prompt)
        intent = extract_json(response)
        logger.info(f"[understand] 理解完成: goal={intent.get('goal', 'N/A')}")
        return {"test_intent": intent}
    except Exception as e:
        logger.error(f"[understand] 解析失败: {e}")
        return {"error": f"理解失败: {e}"}
