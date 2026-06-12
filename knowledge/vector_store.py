"""ChromaDB 向量存储管理 —— 产品文档 RAG 检索"""
import os
from pathlib import Path
from typing import Any, Optional

# HuggingFace 国内镜像（解决 hf.co 无法访问问题）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from config.settings import CHROMA_DIR
from utils.logger import logger


class VectorStore:
    """ChromaDB 向量存储封装（sentence-transformers + PyTorch，all-MiniLM-L6-v2 模型）"""

    COLLECTION_NAME = "iotnac_knowledge"

    def __init__(self):
        self._client = None  # type: chromadb.PersistentClient
        self._collection = None
        self._ef = None

    def _ensure_client(self):
        """延迟初始化 ChromaDB 客户端"""
        if self._client is None:
            CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=self._ef,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"ChromaDB 已连接: {CHROMA_DIR}, 文档数: {self._collection.count()}, "
                        f"embedding: sentence-transformers all-MiniLM-L6-v2")

    # ── 公开接口 ─────────────────────────────────

    def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict] = None,
        ids: list[str] = None,
    ) -> bool:
        """批量添加文档"""
        self._ensure_client()
        try:
            if ids is None:
                import uuid
                ids = [str(uuid.uuid4()) for _ in texts]

            self._collection.add(
                documents=texts,
                metadatas=metadatas or [{}] * len(texts),
                ids=ids,
            )
            logger.info(f"已入库 {len(texts)} 条文档")
            return True
        except Exception as e:
            logger.error(f"文档入库失败: {e}")
            return False

    def add_file(self, file_path: str, chunk_size: int = 500) -> bool:
        """从文件入库（支持 .md / .txt），自动按段落分片"""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"文件不存在: {file_path}")
            return False

        content = path.read_text(encoding="utf-8")
        filename = path.name

        paragraphs = content.split("\n\n")
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

        if not chunks:
            logger.warning(f"文件无有效内容: {file_path}")
            return False

        ids = [f"{filename}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": filename, "chunk_index": i, "total_chunks": len(chunks)}
            for i in range(len(chunks))
        ]

        logger.info(f"文件 {filename} 分 {len(chunks)} 片，开始入库...")
        return self.add_documents(chunks, metadatas, ids)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """语义检索"""
        self._ensure_client()
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            output = []
            if results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    output.append({
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                    })
            return output
        except Exception as e:
            logger.error(f"检索失败: {e}")
            return []

    def count(self) -> int:
        self._ensure_client()
        return self._collection.count()

    def clear(self):
        self._ensure_client()
        self._client.delete_collection(self.COLLECTION_NAME)
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("知识库已清空")
