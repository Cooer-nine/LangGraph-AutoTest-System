"""SSH/Telnet 操作 Tool —— 封装远程执行器"""
from executors.ssh_executor import SSHExecutor

_executor = SSHExecutor()


def _ssh_execute(target: str, command: str) -> str:
    """在远程主机执行命令"""
    ok, output = _executor.execute(target, command)
    return output if ok else f"执行失败: {output}"


def _ssh_get_log(target: str, log_path: str, lines: int = 50) -> str:
    """获取日志文件尾部"""
    ok, output = _executor.get_log(target, log_path, lines)
    return output if ok else f"获取日志失败: {output}"


# === Tool 定义 ===

TOOL_SSH_EXECUTE = {
    "name": "ssh_execute",
    "description": "在远程主机执行命令。target 为 topology.yaml 中的设备名（controller/switch）",
    "parameters": {
        "target": "目标设备：controller 或 switch",
        "command": "要执行的命令",
    },
    "function": _ssh_execute,
}

TOOL_SSH_GET_LOG = {
    "name": "ssh_get_log",
    "description": "获取远程主机日志文件的尾部内容",
    "parameters": {
        "target": "目标设备：controller 或 switch",
        "log_path": "日志文件完整路径",
        "lines": "读取行数（默认50）",
    },
    "function": _ssh_get_log,
}
