# Phase 1 问题跟踪

> 记录 Phase 1 开发过程中遇到的问题及解决方案

---

## 已知问题

| # | 日期 | 描述 | 状态 | 解决方案 |
|---|------|------|------|---------|
| 1 | 2026-06-10 | pywinauto 依赖 pywin32，Windows 环境需预装 | 待验证 | 运行 `pip install pywin32` |
| 2 | 2026-06-10 | Playwright 首次使用需下载浏览器驱动 | 待验证 | 运行 `playwright install chromium` |
| 3 | 2026-06-10 | 交换机仅支持 Telnet 连接，不支持 SSH | ✅ 已解决 | topology.yaml 增加 `connection_type: telnet`，executor 增加 telnetlib 支持，端口改为 23 |
| 4 | 2026-06-10 | 华为交换机 Telnet 登录提示符可能因型号而异 | 观察中 | 当前匹配 `<.*>` / `[.*]` 格式，如遇其他格式需调整正则 |
| 5 | 2026-06-10 | IDE 终端不支持新版终端，无法通过 Qoder 执行命令 | 已知限制 | 请在 IDE 终端设置中勾选"经典"选项，或手动在 PowerShell 中执行以下命令 |

---

## 手动执行步骤

由于 IDE 终端限制，请在 PowerShell 中手动执行以下命令完成 Phase 1 验证：

```powershell
# 1. 进入项目目录
cd C:\Users\zgc-win10-x64\iotnac

# 2. 安装依赖
.venv\Scripts\pip.exe install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 安装 Playwright 浏览器
.venv\Scripts\playwright.exe install chromium

# 4. 复制环境变量配置（然后编辑填入实际值）
copy .env.example .env

# 5. 运行 Phase 1 验证
.venv\Scripts\python.exe main.py
```

---

## 依赖安装记录

| 日期 | 命令 | 结果 |
|------|------|------|
| 2026-06-10 | 待用户手动执行 | — |
