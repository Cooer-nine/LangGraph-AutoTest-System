"""
测试结果数据结构
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class StepResult:
    """单步执行结果"""
    step_index: int
    description: str
    target: str                          # web / desktop / ssh
    action: str
    params: dict
    success: bool
    message: str                         # 执行信息或错误原因
    screenshot: Optional[Path] = None    # 截图路径
    duration_ms: float = 0.0


@dataclass
class TestResult:
    """完整测试结果"""
    title: str
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    steps: list[StepResult] = field(default_factory=list)
    passed: bool = True

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def passed_steps(self) -> int:
        return sum(1 for s in self.steps if s.success)

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if not s.success)

    @property
    def duration_seconds(self) -> float:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0

    def summary(self) -> str:
        lines = [
            f"测试: {self.title}",
            f"结果: {'✓ 通过' if self.passed else '✗ 失败'}",
            f"步骤: {self.total_steps} (通过 {self.passed_steps}, 失败 {self.failed_steps})",
            f"耗时: {self.duration_seconds:.2f}s",
            "",
        ]
        for step in self.steps:
            status = "✓" if step.success else "✗"
            lines.append(f"  {status} 步骤{step.step_index}: {step.description}")
            if not step.success:
                lines.append(f"     原因: {step.message}")
        return "\n".join(lines)
