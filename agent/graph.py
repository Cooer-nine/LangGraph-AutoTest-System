"""LangGraph 主执行图 —— V1 线性版

understand → plan → execute ⇄ verify → summarize

条件边：verify 后判断是否还有步骤待执行
- 还有步骤 → 回到 execute
- 全部完成 → summarize
"""
from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import understand_node, plan_node, execute_node, verify_node, summarize_node


def _should_continue(state: AgentState) -> str:
    """条件路由：判断是否继续执行下一步"""
    idx = state.get("current_step_index", 0)
    plan = state.get("plan", [])
    error = state.get("error", "")

    if error:
        return "summarize"
    if idx < len(plan):
        return "execute"
    return "summarize"


def build_graph() -> StateGraph:
    """构建并编译 Agent 执行图"""
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("understand", understand_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("verify", verify_node)
    graph.add_node("summarize", summarize_node)

    # 设置入口
    graph.set_entry_point("understand")

    # 线性边
    graph.add_edge("understand", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "verify")

    # 条件边：verify → execute（继续） 或 summarize（结束）
    graph.add_conditional_edges(
        "verify",
        _should_continue,
        {
            "execute": "execute",
            "summarize": "summarize",
        },
    )

    # 终点
    graph.add_edge("summarize", END)

    return graph.compile()
