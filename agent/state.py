"""Agent 状态定义"""
from typing import TypedDict, Any


class StepPlan(TypedDict, total=False):
    """单个执行步骤"""
    tool: str          # 工具名: web_click / ssh_execute 等
    params: dict       # 工具参数
    description: str   # 步骤描述
    expected: str      # 预期结果描述


class AgentState(TypedDict, total=False):
    """LangGraph Agent 全局状态"""
    # 输入
    user_query: str            # 用户原始自然语言用例文本

    # understand 产出
    test_intent: dict          # 结构化测试意图 {goal, context, targets}

    # plan 产出
    plan: list[StepPlan]       # 操作步骤序列

    # execute 循环控制
    current_step_index: int    # 当前执行到第几步

    # 执行记录
    step_results: list[dict]   # 每个步骤的执行结果 {step, tool, params, result, screenshot, passed}

    # summarize 产出
    summary: str               # 最终测试摘要

    # 错误信息
    error: str
