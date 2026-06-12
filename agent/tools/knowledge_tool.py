"""知识库 Tool —— 接入 ChromaDB + SQLite 定位缓存"""
from executors.ssh_executor import TopologyLoader
from knowledge.manager import knowledge_manager


def _knowledge_search(query: str, top_k: int = 5) -> str:
    """语义检索知识库"""
    return knowledge_manager.search_as_text(query, top_k)


def _knowledge_get_topology() -> str:
    """获取环境拓扑信息"""
    try:
        topo = TopologyLoader.load()
        devices = topo.get("devices", {})
        lines = ["当前环境拓扑："]
        for name, dev in devices.items():
            host = dev.get("host", "N/A")
            port = dev.get("port", "N/A")
            lines.append(f"  {name}: {host}:{port} ({dev.get('type', '')})")
        return "\n".join(lines)
    except Exception as e:
        return f"获取拓扑失败: {e}"


def _knowledge_get_locator(page_url: str, description: str) -> str:
    """查询元素定位缓存"""
    locator = knowledge_manager.get_locator(page_url, description)
    if locator:
        return (
            f"命中缓存: {locator.locator_type} → {locator.locator_value}, "
            f"成功率 {locator.success_rate():.0%}"
        )
    return f"未命中缓存: {page_url}#{description}"


def _knowledge_cache_locator(
    page_url: str, description: str, locator_type: str, locator_value: str
) -> str:
    """缓存成功的元素定位策略"""
    ok = knowledge_manager.cache_locator(
        page_url, description, locator_type, locator_value
    )
    return "已缓存" if ok else "缓存失败"


# === Tool 定义 ===

TOOL_KNOWLEDGE_SEARCH = {
    "name": "knowledge_search",
    "description": "语义检索产品知识库，返回相关文档内容",
    "parameters": {
        "query": "搜索查询语句",
        "top_k": "返回结果数量（默认5）",
    },
    "function": _knowledge_search,
}

TOOL_KNOWLEDGE_GET_TOPOLOGY = {
    "name": "knowledge_get_topology",
    "description": "获取环境拓扑信息（IP、端口、设备类型）",
    "parameters": {},
    "function": _knowledge_get_topology,
}

TOOL_KNOWLEDGE_GET_LOCATOR = {
    "name": "knowledge_get_locator",
    "description": "查询元素定位缓存，返回之前成功使用的定位策略",
    "parameters": {
        "page_url": "页面URL",
        "description": "元素描述，如'登录按钮'",
    },
    "function": _knowledge_get_locator,
}

TOOL_KNOWLEDGE_CACHE_LOCATOR = {
    "name": "knowledge_cache_locator",
    "description": "缓存成功的元素定位策略，下次优先使用",
    "parameters": {
        "page_url": "页面URL",
        "description": "元素描述",
        "locator_type": "定位类型: role/css/xpath/visual",
        "locator_value": "定位符值",
    },
    "function": _knowledge_cache_locator,
}
