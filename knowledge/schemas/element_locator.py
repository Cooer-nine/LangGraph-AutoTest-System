"""元素定位缓存数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ElementLocator:
    """元素定位缓存条目"""
    page_url: str
    description: str          # 元素描述，如"登录按钮"
    locator_type: str         # role / css / xpath / visual
    locator_value: str        # 定位符值
    success_count: int = 0
    fail_count: int = 0
    last_used: Optional[datetime] = None

    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "page_url": self.page_url,
            "description": self.description,
            "locator_type": self.locator_type,
            "locator_value": self.locator_value,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }
