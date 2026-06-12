"""视觉分析 Tool —— 封装 Zhipu GLM-4V API"""
import base64
from pathlib import Path
from openai import OpenAI
from config.llm_config import LLMConfig


def _vision_analyze(image_path: str, question: str) -> str:
    """分析截图，回答特定问题"""
    try:
        cfg = LLMConfig.get_zhipu_config()
        client = OpenAI(api_key=cfg["api_key"], base_url=cfg["api_base"])

        # 读取图片并转为 base64
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        ext = Path(image_path).suffix.lower().replace(".", "")
        mime = f"image/{'jpeg' if ext == 'jpg' else ext}"

        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                    {"type": "text", "text": question},
                ],
            }],
            max_tokens=1024,
            temperature=0.1,
        )
        return resp.choices[0].message.content or "无分析结果"
    except Exception as e:
        return f"视觉分析失败: {e}"


def _vision_compare(before: str, after: str) -> str:
    """对比两张截图，描述差异"""
    try:
        cfg = LLMConfig.get_zhipu_config()
        client = OpenAI(api_key=cfg["api_key"], base_url=cfg["api_base"])

        images = []
        for label, path in [("操作前", before), ("操作后", after)]:
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = Path(path).suffix.lower().replace(".", "")
            mime = f"image/{'jpeg' if ext == 'jpg' else ext}"
            images.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{img_b64}"},
            })

        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "第一张是操作前，第二张是操作后。请描述两张截图的差异，判断操作是否达到了预期效果。"},
                    *images,
                ],
            }],
            max_tokens=1024,
            temperature=0.1,
        )
        return resp.choices[0].message.content or "无对比结果"
    except Exception as e:
        return f"视觉对比失败: {e}"


# === Tool 定义 ===

TOOL_VISION_ANALYZE = {
    "name": "vision_analyze",
    "description": "使用视觉模型分析截图，回答关于界面内容的问题",
    "parameters": {
        "image_path": "截图文件路径",
        "question": "要分析的问题，如'页面上是否有登录成功字样'",
    },
    "function": _vision_analyze,
}

TOOL_VISION_COMPARE = {
    "name": "vision_compare",
    "description": "对比两张截图（操作前后），描述差异",
    "parameters": {
        "before": "操作前的截图路径",
        "after": "操作后的截图路径",
    },
    "function": _vision_compare,
}
