"""知识管理器 —— 统一入口，整合向量检索 + 定位缓存"""
import json
from pathlib import Path
from typing import Optional

from knowledge.vector_store import VectorStore
from knowledge.locator_cache import LocatorCache
from knowledge.schemas.element_locator import ElementLocator
from utils.logger import logger


class KnowledgeManager:
    """
    知识库统一入口

    用法：
        km = KnowledgeManager()
        km.add_doc_file("docs/product/intro.md")
        results = km.search("如何配置认证策略")
        locator = km.get_locator("http://host/login", "登录按钮")
    """

    def __init__(self):
        self.vector_store = VectorStore()
        self.locator_cache = LocatorCache()

    # ── 文档管理 ─────────────────────────────────

    def add_doc_text(self, content: str, source: str = "manual", chunk_size: int = 500) -> bool:
        """直接添加文本内容到知识库"""
        chunks = self._split_text(content, chunk_size)
        if not chunks:
            return False
        metadatas = [{"source": source, "chunk_index": i, "total_chunks": len(chunks)}
                     for i in range(len(chunks))]
        ids = [f"{source}_chunk_{i}" for i in range(len(chunks))]
        return self.vector_store.add_documents(chunks, metadatas, ids)

    def add_doc_file(self, file_path: str) -> bool:
        """从文件添加文档（支持 .md / .txt）"""
        return self.vector_store.add_file(file_path)

    def add_doc_dir(self, dir_path: str, pattern: str = "*.md") -> int:
        """批量添加目录下的文档，返回成功入库的文件数"""
        path = Path(dir_path)
        if not path.is_dir():
            logger.error(f"目录不存在: {dir_path}")
            return 0

        count = 0
        for f in path.rglob(pattern):
            if self.vector_store.add_file(str(f)):
                count += 1
        logger.info(f"目录入库完成: {count} 个文件")
        return count

    # ── 检索 ─────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        语义检索知识库

        Returns:
            [{"content": "...", "metadata": {...}, "distance": 0.12}, ...]
        """
        return self.vector_store.search(query, top_k)

    def search_as_text(self, query: str, top_k: int = 5) -> str:
        """检索并格式化为文本（供 LLM 使用）"""
        results = self.search(query, top_k)
        if not results:
            return f"未找到与「{query}」相关的知识"

        lines = [f"检索到 {len(results)} 条相关知识："]
        for i, r in enumerate(results, 1):
            source = r.get("metadata", {}).get("source", "未知")
            lines.append(f"\n--- 结果 {i} (来源: {source}, 距离: {r['distance']:.4f}) ---")
            lines.append(r["content"][:500])
        return "\n".join(lines)

    # ── 定位缓存 ─────────────────────────────────

    def get_locator(self, page_url: str, description: str) -> Optional[ElementLocator]:
        """查询元素定位缓存"""
        return self.locator_cache.get(page_url, description)

    def cache_locator(
        self, page_url: str, description: str,
        locator_type: str, locator_value: str,
    ) -> bool:
        """缓存成功的定位策略"""
        return self.locator_cache.set(page_url, description, locator_type, locator_value)

    def record_locator_failure(self, page_url: str, description: str, locator_type: str):
        """记录定位失败"""
        self.locator_cache.record_failure(page_url, description, locator_type)

    def get_page_locators(self, page_url: str) -> list[dict]:
        """获取页面所有缓存定位"""
        return self.locator_cache.get_all_for_page(page_url)

    # ── 统计 ─────────────────────────────────────

    def stats(self) -> dict:
        """知识库统计"""
        return {
            "vector_docs": self.vector_store.count(),
            "locator_cache": self.locator_cache.stats(),
        }

    # ── 工具 ─────────────────────────────────────

    @staticmethod
    def _split_text(text: str, chunk_size: int = 500) -> list[str]:
        """按段落 + 字符数分片"""
        paragraphs = text.split("\n\n")
        chunks = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size):
                    chunks.append(para[i:i + chunk_size])
            else:
                chunks.append(para)
        return chunks


# 全局单例
knowledge_manager = KnowledgeManager()
