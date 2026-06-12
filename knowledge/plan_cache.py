"""Plan 缓存 —— 避免重复执行相同用例时每次都让 LLM 重新规划

以测试用例标题为 key，第一次规划成功后缓存 plan，
后续执行直接复用，跳过 understand 和 plan 节点。
"""
import json
import hashlib
from pathlib import Path
from typing import Optional

from utils.logger import logger

CACHE_FILE = Path(__file__).parent.parent / "data" / "plan_cache.json"


def _load_cache() -> dict:
    """加载缓存文件"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"[plan_cache] 缓存文件损坏，重建: {e}")
    return {}


def _save_cache(cache: dict) -> None:
    """保存缓存文件"""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _make_key(case_title: str, user_query: str) -> str:
    """生成缓存 key：标题 + 查询内容的短哈希，防止标题相同但内容不同的冲突"""
    # 取 user_query 的前 200 字符做哈希（YAML 参数变化时应导致不同 key）
    content_hash = hashlib.md5(user_query[:200].encode()).hexdigest()[:8]
    return f"{case_title}__{content_hash}"


def get_plan(case_title: str, user_query: str) -> Optional[list[dict]]:
    """获取缓存的 plan

    Returns:
        缓存的 plan 列表，或 None 表示未命中
    """
    cache = _load_cache()
    key = _make_key(case_title, user_query)
    plan = cache.get(key)
    if plan:
        logger.info(f"[plan_cache] ✓ 命中缓存: {key} ({len(plan)} 步骤)")
    else:
        logger.info(f"[plan_cache] ✗ 未命中缓存: {key}")
    return plan


def set_plan(case_title: str, user_query: str, plan: list[dict]) -> None:
    """缓存 plan"""
    cache = _load_cache()
    key = _make_key(case_title, user_query)
    cache[key] = plan
    _save_cache(cache)
    logger.info(f"[plan_cache] 已缓存: {key} ({len(plan)} 步骤)")


def invalidate(case_title: str = None) -> int:
    """清除缓存

    Args:
        case_title: 指定标题清除（None 表示清除全部）
    Returns:
        清除的条目数
    """
    if case_title is None:
        count = len(_load_cache())
        CACHE_FILE.write_text("{}", encoding="utf-8")
        logger.info(f"[plan_cache] 已清除全部缓存 ({count} 条)")
        return count

    cache = _load_cache()
    # 清除所有匹配标题前缀的 key
    to_remove = [k for k in cache if k.startswith(case_title)]
    for k in to_remove:
        del cache[k]
    _save_cache(cache)
    logger.info(f"[plan_cache] 已清除: {case_title} ({len(to_remove)} 条)")
    return len(to_remove)
