"""元素定位缓存 —— SQLite 存储（V1 唯一表）

缓存成功的元素定位策略，避免每次定位都走多策略尝试或调视觉接口。
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import DATA_DIR
from utils.logger import logger
from knowledge.schemas.element_locator import ElementLocator


DB_PATH = DATA_DIR / "locator_cache.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS element_locator (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    page_url      TEXT NOT NULL,
    description   TEXT NOT NULL,
    locator_type  TEXT NOT NULL,
    locator_value TEXT NOT NULL,
    success_count INTEGER DEFAULT 0,
    fail_count    INTEGER DEFAULT 0,
    last_used     TIMESTAMP,
    UNIQUE(page_url, description, locator_type)
);
"""


class LocatorCache:
    """元素定位缓存管理器"""

    def __init__(self):
        self._ensure_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self):
        """确保表存在"""
        try:
            conn = self._get_conn()
            conn.execute(CREATE_TABLE_SQL)
            conn.commit()
            conn.close()
            logger.debug("元素定位缓存表已就绪")
        except Exception as e:
            logger.error(f"创建缓存表失败: {e}")

    # ── CRUD ──────────────────────────────────────

    def get(
        self, page_url: str, description: str
    ) -> Optional[ElementLocator]:
        """
        查询缓存（按成功次数降序，取最优策略）

        Args:
            page_url: 页面 URL
            description: 元素描述

        Returns:
            ElementLocator 或 None
        """
        try:
            conn = self._get_conn()
            row = conn.execute(
                """SELECT page_url, description, locator_type, locator_value,
                          success_count, fail_count, last_used
                   FROM element_locator
                   WHERE page_url = ? AND description = ?
                   ORDER BY success_count DESC
                   LIMIT 1""",
                (page_url, description),
            ).fetchone()
            conn.close()

            if row:
                return ElementLocator(
                    page_url=row["page_url"],
                    description=row["description"],
                    locator_type=row["locator_type"],
                    locator_value=row["locator_value"],
                    success_count=row["success_count"],
                    fail_count=row["fail_count"],
                    last_used=(
                        datetime.fromisoformat(row["last_used"])
                        if row["last_used"] else None
                    ),
                )
            return None
        except Exception as e:
            logger.error(f"查询缓存失败: {e}")
            return None

    def set(
        self,
        page_url: str,
        description: str,
        locator_type: str,
        locator_value: str,
    ) -> bool:
        """
        缓存定位策略（存在则更新成功计数）

        Returns:
            是否成功
        """
        try:
            conn = self._get_conn()
            now = datetime.now().isoformat()

            conn.execute(
                """INSERT INTO element_locator
                   (page_url, description, locator_type, locator_value,
                    success_count, last_used)
                   VALUES (?, ?, ?, ?, 1, ?)
                   ON CONFLICT(page_url, description, locator_type)
                   DO UPDATE SET
                       success_count = success_count + 1,
                       locator_value = excluded.locator_value,
                       last_used = excluded.last_used""",
                (page_url, description, locator_type, locator_value, now),
            )
            conn.commit()
            conn.close()
            logger.debug(f"缓存定位: {page_url} / {description} → {locator_type}:{locator_value}")
            return True
        except Exception as e:
            logger.error(f"缓存失败: {e}")
            return False

    def record_failure(self, page_url: str, description: str, locator_type: str):
        """记录定位失败（增加 fail_count）"""
        try:
            conn = self._get_conn()
            conn.execute(
                """UPDATE element_locator
                   SET fail_count = fail_count + 1
                   WHERE page_url = ? AND description = ? AND locator_type = ?""",
                (page_url, description, locator_type),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"记录失败计数异常: {e}")

    def get_all_for_page(self, page_url: str) -> list[dict]:
        """获取某页面的所有缓存定位"""
        try:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT description, locator_type, locator_value,
                          success_count, fail_count, last_used
                   FROM element_locator
                   WHERE page_url = ?
                   ORDER BY success_count DESC""",
                (page_url,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"查询页面缓存失败: {e}")
            return []

    def stats(self) -> dict:
        """缓存统计"""
        try:
            conn = self._get_conn()
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM element_locator"
            ).fetchone()["cnt"]
            success = conn.execute(
                "SELECT COALESCE(SUM(success_count), 0) as cnt FROM element_locator"
            ).fetchone()["cnt"]
            fail = conn.execute(
                "SELECT COALESCE(SUM(fail_count), 0) as cnt FROM element_locator"
            ).fetchone()["cnt"]
            conn.close()
            return {"total_entries": total, "total_success": success, "total_fail": fail}
        except Exception as e:
            logger.error(f"统计失败: {e}")
            return {}
