"""
LLM 模型配置
"""
import os


class LLMConfig:
    """LLM 配置（从环境变量读取）"""

    # DeepSeek（主推理引擎）
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL = "deepseek-v4-pro"

    # Zhipu Vision（视觉 Tool）
    ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
    ZHIPU_API_BASE = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPU_VISION_MODEL = "glm-5v-turbo"

    # Embedding（知识库向量化）
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_API_BASE = os.getenv("EMBEDDING_API_BASE", "https://api.deepseek.com/v1")
    EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))

    @classmethod
    def validate(cls) -> list[str]:
        """校验必要配置，返回缺失项列表"""
        missing = []
        if not cls.DEEPSEEK_API_KEY:
            missing.append("DEEPSEEK_API_KEY")
        if not cls.ZHIPU_API_KEY:
            missing.append("ZHIPU_API_KEY")
        return missing

    @classmethod
    def get_deepseek_config(cls) -> dict:
        return {
            "api_key": cls.DEEPSEEK_API_KEY,
            "api_base": cls.DEEPSEEK_API_BASE,
            "model": cls.DEEPSEEK_MODEL,
        }

    @classmethod
    def get_zhipu_config(cls) -> dict:
        return {
            "api_key": cls.ZHIPU_API_KEY,
            "api_base": cls.ZHIPU_API_BASE,
            "model": cls.ZHIPU_VISION_MODEL,
        }

    @classmethod
    def get_embedding_config(cls) -> dict:
        return {
            "api_key": cls.EMBEDDING_API_KEY,
            "api_base": cls.EMBEDDING_API_BASE,
            "model": cls.EMBEDDING_MODEL,
        }
