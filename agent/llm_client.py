"""DeepSeek LLM 调用辅助函数"""
import json
import re
from openai import OpenAI
from config.llm_config import LLMConfig
from agent.prompts.system_prompt import SYSTEM_PROMPT


def get_deepseek_client():
    cfg = LLMConfig.get_deepseek_config()
    return OpenAI(api_key=cfg["api_key"], base_url=cfg["api_base"]), cfg["model"]


def call_deepseek(user_prompt: str, temperature: float = 0.1) -> str:
    """调用 DeepSeek，返回文本响应"""
    client, model = get_deepseek_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=4096,
    )
    return resp.choices[0].message.content or ""


def extract_json(text: str) -> dict | list:
    """从 LLM 响应中提取 JSON（兼容 markdown 代码块包裹）"""
    # 尝试匹配 ```json ... ``` 包裹
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        text = m.group(1)
    # 尝试匹配裸 JSON
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 最后手段：找第一个 { 或 [ 到最后一个 } 或 ]
        start = min((text.find(c) for c in '[{'), default=-1)
        end = max((text.rfind(c) for c in ']}'), default=-1)
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise
