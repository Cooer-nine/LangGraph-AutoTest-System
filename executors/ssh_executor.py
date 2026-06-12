"""
远程执行器 — 基于 Paramiko (SSH) + telnetlib (Telnet) 封装
"""
import re
import time
from typing import Optional, Union

import paramiko
import telnetlib
import yaml
from paramiko.ssh_exception import AuthenticationException, SSHException

from config.settings import PROJECT_ROOT
from utils.logger import logger


class TopologyLoader:
    """拓扑配置加载器"""

    _instance: Optional[dict] = None

    @classmethod
    def load(cls) -> dict:
        if cls._instance is None:
            path = PROJECT_ROOT / "config" / "topology.yaml"
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            cls._instance = cls._resolve_env(raw)
        return cls._instance

    @classmethod
    def get_device(cls, name: str) -> dict:
        return cls.load()["devices"].get(name, {})

    @staticmethod
    def _resolve_env(data: dict) -> dict:
        """简单解析 ${VAR:default} 格式的环境变量"""
        import os
        import re

        if isinstance(data, dict):
            return {k: TopologyLoader._resolve_env(v) for k, v in data.items()}
        if isinstance(data, list):
            return [TopologyLoader._resolve_env(v) for v in data]
        if isinstance(data, str):
            def replacer(m):
                var = m.group(1)
                default = m.group(2) if m.group(2) else ""
                return os.getenv(var, default)
            return re.sub(r'\$\{(\w+)(?::([^}]*))?\}', replacer, data)
        return data


class SSHExecutor:
    """
    远程执行器（自动适配 SSH / Telnet）

    根据拓扑中 connection_type 自动选择协议：
      - 默认 / ssh → Paramiko SSH
      - telnet → telnetlib

    支持目标：
      - switch:  Huawei 交换机 CLI (Telnet)
      - controller: Linux 服务器 Bash (SSH)
    """

    def __init__(self):
        # SSH 连接: {target: paramiko.SSHClient}
        # Telnet 连接: {target: telnetlib.Telnet}
        self._connections: dict[str, Union["paramiko.SSHClient", "telnetlib.Telnet"]] = {}

    # ── 连接管理 ─────────────────────────────────

    def connect(self, target: str) -> bool:
        """
        建立连接（自动适配 SSH 或 Telnet）

        Args:
            target: 目标名称 ("controller" / "switch")

        Returns:
            连接是否成功
        """
        if target in self._connections:
            try:
                conn = self._connections[target]
                if isinstance(conn, paramiko.SSHClient):
                    conn.exec_command("echo ok", timeout=5)
                else:
                    # Telnet: 发送空命令检查连接
                    conn.write(b"\n")
                    time.sleep(0.3)
                return True
            except Exception:
                self._connections.pop(target, None)

        device = TopologyLoader.get_device(target)
        if not device:
            logger.error(f"拓扑中未找到设备: {target}")
            return False

        host = device.get("host", "")
        port = device.get("port", 22)
        user = device.get("user", "")
        password = device.get("password", "")
        conn_type = device.get("connection_type", "ssh")

        if not host:
            logger.error(f"设备 {target} 未配置 host")
            return False

        if conn_type == "telnet":
            return self._connect_telnet(target, host, port, user, password)
        else:
            return self._connect_ssh(target, host, port, user, password)

    def _connect_ssh(self, target: str, host: str, port: int, user: str, password: str) -> bool:
        """SSH 连接"""
        logger.info(f"SSH 连接 {target} ({host}:{port}) ...")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
            self._connections[target] = client
            logger.info(f"SSH 连接成功: {target}")
            return True
        except AuthenticationException:
            logger.error(f"SSH 认证失败: {target}")
            return False
        except SSHException as e:
            logger.error(f"SSH 连接失败: {target}, {e}")
            return False
        except Exception as e:
            logger.error(f"SSH 未知错误: {target}, {e}")
            return False

    def _connect_telnet(self, target: str, host: str, port: int, user: str, password: str) -> bool:
        """Telnet 连接（华为交换机典型流程）"""
        logger.info(f"Telnet 连接 {target} ({host}:{port}) ...")
        try:
            tn = telnetlib.Telnet(host, port, timeout=10)

            # 华为交换机登录流程:
            #   等待 username/password 提示 → 发送凭据 → 等待命令提示符
            # 典型提示符: <DeviceName> 或 [DeviceName]

            # 等待用户名提示
            idx, match, text = tn.expect(
                [rb"[Uu]sername[: ]*", rb"[Ll]ogin[: ]*", rb"<.*>", rb"\[.*\]"],
                timeout=10
            )
            output_so_far = text.decode("utf-8", errors="replace")

            if idx <= 1:
                # 需要用户名
                tn.write(user.encode("utf-8") + b"\n")
                time.sleep(0.5)
                idx, match, text = tn.expect(
                    [rb"[Pp]assword[: ]*", rb"<.*>", rb"\[.*\]"],
                    timeout=10
                )
                output_so_far += text.decode("utf-8", errors="replace")

            if idx == 0 or b"assword" in match.group(0) if match else False:
                # 需要密码
                tn.write(password.encode("utf-8") + b"\n")
                time.sleep(0.5)
                # 等待命令提示符
                idx, match, text = tn.expect(
                    [rb"<.*>", rb"\[.*\]", rb"[Ff]ail", rb"[Ee]rror"],
                    timeout=10
                )
                output_so_far += text.decode("utf-8", errors="replace")

                if match and (b"Fail" in match.group(0) or b"Error" in match.group(0)):
                    logger.error(f"Telnet 认证失败: {target}")
                    tn.close()
                    return False

            self._connections[target] = tn
            logger.info(f"Telnet 连接成功: {target}")
            return True

        except Exception as e:
            logger.error(f"Telnet 连接失败: {target}, {e}")
            return False

    def disconnect(self, target: str = None):
        """断开连接"""
        if target:
            conn = self._connections.pop(target, None)
            if conn:
                if isinstance(conn, paramiko.SSHClient):
                    conn.close()
                    logger.info(f"SSH 已断开: {target}")
                else:
                    conn.close()
                    logger.info(f"Telnet 已断开: {target}")
        else:
            for name, conn in list(self._connections.items()):
                if isinstance(conn, paramiko.SSHClient):
                    conn.close()
                else:
                    conn.close()
                logger.info(f"已断开: {name}")
            self._connections.clear()

    def is_connected(self, target: str) -> bool:
        return target in self._connections

    # ── 命令执行 ─────────────────────────────────

    def execute(self, target: str, command: str, timeout: int = 30) -> tuple[bool, str]:
        """
        执行单条命令（自动适配 SSH / Telnet）

        Args:
            target: 目标名称
            command: 要执行的命令
            timeout: 超时秒数

        Returns:
            (成功, 输出文本)
        """
        if not self.connect(target):
            return False, f"无法连接到 {target}"

        conn = self._connections[target]
        logger.debug(f"[{target}] >>> {command}")

        if isinstance(conn, paramiko.SSHClient):
            return self._execute_ssh(conn, target, command, timeout)
        else:
            return self._execute_telnet(conn, target, command, timeout)

    def _execute_ssh(
        self, client: "paramiko.SSHClient", target: str, command: str, timeout: int
    ) -> tuple[bool, str]:
        """SSH 方式执行命令"""
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace")
            error = stderr.read().decode("utf-8", errors="replace")

            if exit_code != 0 and error:
                output += f"\n[stderr]\n{error}"

            logger.debug(f"[{target}] <<< exit={exit_code}, len={len(output)}")
            return exit_code == 0, output.strip()
        except Exception as e:
            logger.error(f"[{target}] SSH 执行异常: {e}")
            return False, str(e)

    def _execute_telnet(
        self, tn: "telnetlib.Telnet", target: str, command: str, timeout: int
    ) -> tuple[bool, str]:
        """Telnet 方式执行命令"""
        try:
            # 发送命令
            tn.write(command.encode("utf-8") + b"\n")
            time.sleep(0.5)

            # 读取直到下一个提示符 或 超时
            # 华为交换机提示符: <DeviceName> 或 [DeviceName]
            idx, match, output_bytes = tn.expect(
                [rb"<.*>", rb"\[.*\]", rb"---- More ----"],
                timeout=timeout
            )
            output = output_bytes.decode("utf-8", errors="replace")

            # 处理分页（More）
            if match and b"More" in match.group(0):
                # 发送空格继续翻页，再读一次
                tn.write(b" ")
                time.sleep(0.3)
                try:
                    idx2, match2, more_bytes = tn.expect(
                        [rb"<.*>", rb"\[.*\]"],
                        timeout=timeout
                    )
                    output += more_bytes.decode("utf-8", errors="replace")
                except Exception:
                    pass

            # 清理回显的命令行
            lines = output.split("\n")
            if lines and command in lines[0]:
                lines = lines[1:]  # 去掉回显的命令
            output = "\n".join(lines)

            logger.debug(f"[{target}] <<< len={len(output)}")
            return True, output.strip()
        except Exception as e:
            logger.error(f"[{target}] Telnet 执行异常: {e}")
            return False, str(e)

    def execute_batch(
        self, target: str, commands: list[str], timeout: int = 60
    ) -> list[tuple[bool, str]]:
        """
        批量执行命令

        Args:
            target: 目标名称
            commands: 命令列表
            timeout: 每条命令超时

        Returns:
            [(成功, 输出), ...]
        """
        results = []
        for cmd in commands:
            ok, out = self.execute(target, cmd, timeout)
            results.append((ok, out))
            if not ok:
                logger.warning(f"批量执行中断于: {cmd}")
                break
            time.sleep(0.3)
        return results

    # ── 专用操作 ─────────────────────────────────

    def get_log(
        self, target: str, log_path: str, lines: int = 50
    ) -> tuple[bool, str]:
        """
        获取日志文件尾部内容

        Args:
            target: 目标名称
            log_path: 日志文件路径
            lines: 行数

        Returns:
            (成功, 日志内容)
        """
        return self.execute(target, f"tail -n {lines} {log_path}")

    def check_service(self, target: str, service_name: str) -> tuple[bool, str]:
        """
        检查服务状态

        Args:
            target: 目标名称
            service_name: 服务名称或进程名

        Returns:
            (运行中, 状态输出)
        """
        ok, out = self.execute(target, f"systemctl is-active {service_name}", timeout=10)
        if ok and "active" in out:
            return True, out
        return False, out


# 全局单例
ssh_executor = SSHExecutor()
