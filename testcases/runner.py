"""测试用例执行器 — V1 版

加载 YAML 用例，转换为 Agent 可理解的格式，通过 LangGraph 执行并收集结果。
"""
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

import yaml

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import logger
from utils.result import TestResult, StepResult
from utils.reporter import generate_html_report, print_console_summary


class TestCaseRunner:
    """YAML 用例加载 + Agent 图执行"""

    def __init__(self):
        self._graph = None

    def _ensure_graph(self):
        """延迟构建 Agent 图"""
        if self._graph is None:
            from agent.graph import build_graph
            self._graph = build_graph()

    # ── 公开接口 ─────────────────────────────────

    def load(self, case_path: str) -> dict:
        """加载单个 YAML 用例文件

        Returns:
            dict: 包含 title, description, steps, assertions 的用例字典
        """
        path = Path(case_path)
        if not path.exists():
            raise FileNotFoundError(f"用例文件不存在: {case_path}")

        with open(path, "r", encoding="utf-8") as f:
            case = yaml.safe_load(f)

        if not case:
            raise ValueError(f"用例文件为空: {case_path}")

        if "title" not in case:
            raise ValueError(f"用例缺少 title 字段: {case_path}")

        return case

    def load_dir(self, dir_path: str, pattern: str = "*.yaml") -> list[dict]:
        """批量加载目录下的所有用例

        Returns:
            list[dict]: 用例字典列表，每个附带 _file_path 字段
        """
        path = Path(dir_path)
        if not path.is_dir():
            raise FileNotFoundError(f"目录不存在: {dir_path}")

        cases = []
        for f in sorted(path.rglob(pattern)):
            try:
                case = self.load(str(f))
                case["_file_path"] = str(f)
                cases.append(case)
                logger.info(f"已加载: {f.name} — {case.get('title')}")
            except Exception as e:
                logger.warning(f"跳过 {f.name}: {e}")

        return cases

    def run(self, case_path: str) -> TestResult:
        """执行单个 YAML 用例

        Args:
            case_path: YAML 用例文件路径

        Returns:
            TestResult: 包含步骤执行结果的测试结果
        """
        case = self.load(case_path)
        return self._execute(case)

    def run_case(self, case: dict) -> TestResult:
        """执行内存中的用例字典（供 load_dir 批量执行用）"""
        return self._execute(case)

    # ── 内部方法 ─────────────────────────────────

    def _build_user_query(self, case: dict) -> str:
        """将 YAML 用例转为 Agent 可理解的自然语言描述"""
        title = case.get("title", "未命名用例")
        description = case.get("description", "")
        steps = case.get("steps", [])
        assertions = case.get("assertions", [])

        lines = [f"测试用例: {title}"]
        if description:
            lines.append(f"描述: {description}")

        if steps:
            lines.append("\n操作步骤:")
            for i, step in enumerate(steps, 1):
                desc = step.get("description", f"步骤{i}")
                target = step.get("target", "")
                action = step.get("action", "")
                params = step.get("params", {})

                lines.append(f"  {i}. {desc}")
                if target and action:
                    lines.append(f"     (目标: {target}, 操作: {action})")
                if params:
                    params_str = ", ".join(f"{k}={v}" for k, v in params.items())
                    lines.append(f"     参数: {params_str}")

        if assertions:
            lines.append("\n预期结果:")
            for i, a in enumerate(assertions, 1):
                lines.append(f"  {i}. {a}")

        return "\n".join(lines)

    def _execute(self, case: dict) -> TestResult:
        """核心执行逻辑"""
        title = case.get("title", "未命名用例")
        result = TestResult(title=title)

        try:
            self._ensure_graph()

            # 构建自然语言查询
            user_query = self._build_user_query(case)
            logger.info(f"\n{'=' * 50}")
            logger.info(f"执行用例: {title}")
            logger.info(f"{'=' * 50}")

            # ── Plan 缓存检查 ──
            from knowledge.plan_cache import get_plan, set_plan
            initial_state = {"user_query": user_query}
            cached_plan = get_plan(title, user_query)
            if cached_plan:
                initial_state["plan"] = cached_plan
                logger.info(f"[runner] 使用缓存计划，跳过 understand + plan 节点")
            agent_result = self._graph.invoke(initial_state)

            # 收集结果
            step_results = agent_result.get("step_results", [])
            error = agent_result.get("error", "")
            summary = agent_result.get("summary", "")
            executed_plan = agent_result.get("plan", [])

            if error:
                logger.error(f"Agent 执行出错: {error}")
                result.passed = False

            # ── 缓存 plan（仅首次成功规划时保存） ──
            if executed_plan and not cached_plan:
                set_plan(title, user_query, executed_plan)
            # 如果使用缓存但全部步骤失败 → 清除缓存，下次重新规划
            elif cached_plan and step_results and all(sr.get("passed") is False for sr in step_results):
                from knowledge.plan_cache import invalidate
                invalidate(title)
                logger.warning(f"[runner] 缓存计划全部失败，已清除缓存，下次将重新规划")

            # 转换 step_results 为 StepResult
            for i, sr in enumerate(step_results):
                passed_raw = sr.get("passed")
                # None 表示尚未验证，当作未通过处理
                step_passed = bool(passed_raw) if passed_raw is not None else False
                result.steps.append(StepResult(
                    step_index=i + 1,
                    description=sr.get("description", sr.get("tool", "?")),
                    target=sr.get("tool", ""),
                    action=str(sr.get("params", {})),
                    params=sr.get("params", {}),
                    success=step_passed,
                    message=sr.get("result", ""),
                    screenshot=Path(sr["screenshot"]) if sr.get("screenshot") else None,
                ))

            result.finished_at = datetime.now()
            result.passed = all(s.success for s in result.steps) if result.steps else bool(error)
            duration = (result.finished_at - result.started_at).total_seconds()

            logger.info(f"\n{summary}")

            # 生成报告
            report_data = []
            for s in result.steps:
                report_data.append({
                    "description": s.description,
                    "tool": s.target,
                    "passed": s.success,
                    "result": s.message,
                    "screenshot": str(s.screenshot) if s.screenshot else None,
                })
            generate_html_report(title, report_data, result.passed, duration)
            print_console_summary(title, report_data, result.passed, duration)

        except Exception as e:
            logger.error(f"用例执行异常: {e}")
            result.passed = False
            result.steps.append(StepResult(
                step_index=0,
                description="用例执行",
                target="system",
                action="run",
                params={},
                success=False,
                message=str(e),
            ))

        return result

    def run_batch(self, dir_path: str, pattern: str = "*.yaml") -> list[TestResult]:
        """批量执行目录下的所有用例

        Returns:
            list[TestResult]: 每个用例的执行结果
        """
        cases = self.load_dir(dir_path, pattern)
        results = []

        for case in cases:
            file_path = case.pop("_file_path", None)
            result = self.run_case(case)
            case["_file_path"] = file_path
            results.append(result)

            # 打印单用例结果
            logger.info(f"\n{result.summary()}")

        # 汇总
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        logger.info(f"\n{'=' * 50}")
        logger.info(f"批量执行完成: {passed}/{total} 通过")
        logger.info(f"{'=' * 50}")

        return results


# 全局单例
runner = TestCaseRunner()


if __name__ == "__main__":
    """命令行入口: python -m testcases.runner <yaml文件或目录>"""
    if len(sys.argv) < 2:
        print("用法: python -m testcases.runner <yaml文件路径或目录>")
        print("示例: python -m testcases.runner testcases/yaml/web/login/TC-LOGIN-001.yaml")
        print("示例: python -m testcases.runner testcases/yaml/web/login/")
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.exists():
        print(f"路径不存在: {target}")
        sys.exit(1)

    if target.is_file():
        result = runner.run(str(target))
        print(f"\n{'=' * 50}")
        print(f"执行完成: {'✓ 通过' if result.passed else '✗ 失败'}")
    else:
        results = runner.run_batch(str(target))
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        print(f"\n{'=' * 50}")
        print(f"批量执行完成: {passed}/{total} 通过")
