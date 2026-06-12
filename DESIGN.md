# 自动化测试系统工程设计文档

## 1. 项目概述

### 1.1 项目目标
搭建一套具备 AI Agent 能力的自动化测试工程，用于测试 NAC 产品。系统部署在 Windows 虚拟机上，能够理解自然语言测试用例、自主探索被测环境、操作多种被测对象，并持续积累产品知识。

### 1.2 被测对象
| 被测对象 | 位置 | 交互方式 |
|---------|------|---------|
| Web 控制台 | Linux 控制器某端口，Windows 浏览器访问 | Playwright 浏览器自动化 |
| 客户端 | 本 Windows 虚拟机安装 | pywinauto 控件操作 + PyAutoGUI 键鼠 + 截图（双模降级） |
| Linux 控制器 | 远程 Linux 服务器 | SSH (Paramiko) |
| Huawei 交换机 | 同网段网络设备 | SSH (Paramiko) |

### 1.3 核心能力
1. **自然语言用例执行**：Agent 理解自然语言描述的测试步骤，拆解为操作序列并调度执行器完成
2. **探索式用例生成**（V2）：新功能上线时，Agent 探索环境 → 识别可测对象 → 自动生成测试用例
3. **多目标操作**：统一工具接口，适配 Web / 客户端 / 交换机 / 控制器四种操作对象
4. **知识库驱动**：先学习产品知识（页面结构、操作流程、API 契约），再基于知识执行测试

---

## 2. 系统架构

### 2.1 总体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        LLM 模型层                                 │
│  ┌────────────────────┐        ┌──────────────────────┐         │
│  │  DeepSeek-V4-Pro   │───────►│  Zhipu Vision Tool   │         │
│  │  (推理 / 规划 / 决策)│        │  (截图 → 视觉理解)    │         │
│  └────────┬───────────┘        └──────────────────────┘         │
└───────────┼──────────────────────────────────────────────────────┘
            │ Tool Calling
┌───────────▼──────────────────────────────────────────────────────┐
│                    LangGraph Agent 层                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   主执行图 (Graph)                        │    │
│  │  (V1) understand → plan → execute → verify → summarize    │    │
│  │  (V2) + retry/recover 异常恢复分支                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │Tool: Web │ │Tool:     │ │Tool: SSH │ │Tool:     │          │
│  │Playwright│ │Desktop   │ │交换机+   │ │Knowledge │          │
│  │          │ │双模键鼠  │ │控制器    │ │知识库    │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
└───────┼────────────┼────────────┼────────────┼─────────────────┘
        │            │            │            │
┌───────▼────────────▼────────────▼────────────▼─────────────────┐
│                       执行器层 (确定性强封装)                     │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │Playwright  │ │pywinauto   │ │Paramiko    │ │ChromaDB    │  │
│  │浏览器自动化 │ │+ PyAutoGUI │ │SSH 远程执行│ │向量检索    │  │
│  │+ 多策略定位 │ │双模键鼠控制│ │+ 命令封装  │ │+ 元素缓存  │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘  │
└────────────────────────────────────────────────────────────────┘
        │            │            │
        ▼            ▼            ▼
┌───────────┐ ┌───────────┐ ┌───────────┐
│Web 控制台  │ │客户端      │ │交换机+     │
│(浏览器)    │ │(桌面应用)  │ │控制器(SSH) │
└───────────┘ └───────────┘ └───────────┘
```

### 2.2 三层架构说明

| 层级 | 职责 | 核心组件 |
|------|------|---------|
| **LLM 模型层** | 推理、规划、视觉理解 | DeepSeek-V4-Pro (主推理), Zhipu Vision (视觉 Tool) |
| **Agent 层** | 任务拆解、流程编排、Tool 调度 (V1线性 / V2含异常恢复) | LangGraph, Tool 定义集 |
| **执行器层** | 确定的、低层次的设备操作 | Playwright, pywinauto+PyAutoGUI, Paramiko, ChromaDB |

---

## 3. Agent 设计

### 3.1 LangGraph 主执行图（V1：线性执行）

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ understand  │  理解自然语言用例，提取测试意图
                    │  (理解)     │  必要时查询知识库补充上下文
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   plan      │  拆解为可执行的原子操作序列
                    │  (规划)     │  决策使用哪些 Tool
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
              ┌─────│  execute    │  遍历操作序列，逐步执行
              │     │  (执行)     │  每个操作调用对应 Tool
              │     └──────┬──────┘
              │            │
              │     ┌──────▼──────┐
              │     │  verify     │  截图 + Zhipu 视觉判断 / Playwright 断言
              │     │  (验证)     │  失败直接标记，不重试
              │     └──────┬──────┘
              │            │
              │     ┌──────▼──────┐
              │     │ next step?  │──Yes──┘
              │     └──────┬──────┘
              │         No │
              │     ┌──────▼──────┐
              └────►│  summarize  │  汇总结果，输出报告到控制台
                    │  (总结)     │  记录知识库更新
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │    END      │
                    └─────────────┘
```

> **V2 增强**：在 execute → verify 之间增加 retry/recover 分支——验证失败时由 LLM 分析失败原因，调整定位策略或操作方式后重试，最多 N 次。

### 3.2 各节点职责（V1）

| 节点 | 输入 | 处理逻辑 | 输出 |
|------|------|---------|------|
| **understand** | 自然语言用例文本 | LLM 解析意图、提取关键对象和操作 | 结构化测试意图 (JSON) |
| **plan** | 测试意图 + **知识库上下文** | LLM 拆解为原子操作序列，匹配 Tool；**规划前自动检索知识库，注入页面结构、菜单路径、表单字段等上下文** | 操作序列列表 |
| **execute** | 单个操作指令 | 调用对应 Tool 执行；捕获执行结果和截图 | 执行结果 + 截图 |
| **verify** | 执行结果 + 截图 | Zhipu 视觉分析截图 / Playwright 元素断言 | 通过/失败 + 原因 |
| **summarize** | 全部步骤执行记录 | 汇总通过/失败，输出到控制台；提取新知更新知识库 | 测试结果摘要 |

> **V2 新增节点**：`recover` — 失败时 LLM 分析原因，调整定位策略后重试（最多 N 次）

---

## 4. Tool 设计 (供 DeepSeek 调用的工具集)

### 4.1 Web 操作 Tool (`web_tool`)

```
底层：Playwright (Python)
定位策略（优先级降级）：
  1. get_by_role + get_by_text (语义定位，抗变化最强)
  2. CSS Selector (精确)
  3. XPath (兜底)
  4. Zhipu Vision 截图分析 (以上全失败时)

对外暴露操作：
  - web_navigate(url)          导航到指定URL
  - web_click(description)     点击元素（description: "登录按钮"）
  - web_input(description, text) 输入文本
  - web_get_text(description)  获取元素文本
  - web_screenshot()           截取当前页面
  - web_wait(description)      等待元素出现
  - web_select(description, value) 下拉选择
  - web_check(description, expected) 断言元素状态
```

### 4.2 桌面操作 Tool (`desktop_tool`)

```
底层：pywinauto + PyAutoGUI + PIL/Pillow（双模降级）

定位策略（优先级降级）：
  1. pywinauto 控件定位（精确，支持 Win32/WPF/WinForms）
  2. 图像模板匹配（PyAutoGUI locateOnScreen）
  3. Zhipu Vision 截图分析 + 坐标操作（兜底，适用于 Electron/Qt 等非标准控件）

对外暴露操作：
  - desktop_screenshot()             截取全屏
  - desktop_click(target)            点击（target: 控件名/坐标/图像）
  - desktop_double_click(target)     双击
  - desktop_input(target, text)      向控件输入文本
  - desktop_hotkey(keys)             组合键
  - desktop_scroll(clicks)           滚轮滚动
  - desktop_drag(x1,y1, x2,y2)      拖拽
  - desktop_get_text(target)         获取控件文本
  - desktop_find_window(title)       查找窗口
```

### 4.3 SSH 操作 Tool (`ssh_tool`)

```
底层：Paramiko

封装两种目标：
  A) 交换机 (Huawei CLI)
  B) Linux 控制器 (Bash)

对外暴露操作：
  - ssh_execute(target, command)    执行单条命令并返回输出
  - ssh_execute_batch(target, commands) 批量执行命令
  - ssh_get_log(target, log_path, lines) 获取日志文件尾部内容
  - ssh_check_service(target, service_name) 检查服务状态
  - ssh_upload(target, local_path, remote_path) 上传文件
```

### 4.4 视觉分析 Tool (`vision_tool`)

```
底层：Zhipu GLM-4V API

职责：作为 DeepSeek 的"眼睛"，将图像转为结构化文本描述

对外暴露操作：
  - vision_analyze(image, question)   分析截图，回答特定问题
    例：vision_analyze(screenshot, "页面上是否有'创建成功'的文字？")
  - vision_locate(image, target)      定位目标元素，返回坐标
    例：vision_locate(screenshot, "用户管理按钮")
  - vision_describe_ui(image)         描述整个UI界面结构
    例：返回 "页面包含：顶栏(系统名称、用户头像)、侧栏(导航菜单)、
          主区域(用户列表表格，含新增/删除/搜索按钮)..."
  - vision_compare(before, after)     对比两张截图，描述差异
```

### 4.5 知识库 Tool (`knowledge_tool`)

```
底层：ChromaDB (向量检索) + SQLite (元素定位缓存表，V1仅此一张表)

对外暴露操作：
  - knowledge_search(query, top_k=5)   语义检索相关知识点（产品文档）
  - knowledge_get_topology()           获取环境拓扑信息
  - knowledge_get_locator(page_url, description)  查询元素定位缓存
  - knowledge_cache_locator(page_url, description, locator_type, locator_value) 缓存成功定位策略
  - knowledge_add(category, content)   人工补充知识点
```

> **V2 扩展**：`knowledge_get_page_structure`、`knowledge_get_workflow`、`knowledge_learn_page` 等操作在 V2 补全

### 4.6 知识库接入点（V1 已实现）

知识库在两个环节主动介入：

**1. Plan 节点规划前检索**

```
plan_node 收到测试意图
    │
    ├── 用 goal 检索知识库（top_k=5）
    │   → 命中相关文档片段（页面结构、菜单路径、表单字段等）
    │
    ├── 将检索结果注入 Prompt 的「产品知识库参考」章节
    │   → LLM 规划时可参考真实页面元素名称和操作路径
    │
    └── Prompt 中同时提供 knowledge_search 工具
        → LLM 可在规划过程中按需主动检索更多知识
```

**2. Excel → YAML 转换时补全**

```
excel2yaml 解析 Excel 步骤
    │
    ├── _classify_step() 推断 target/action
    │
    ├── _enrich_step_with_knowledge() 检索知识库补全
    │   ├── input 操作 → 从知识库提取输入框/按钮描述
    │   ├── click 操作 → 从知识库提取元素描述
    │   ├── navigate 操作 → 从知识库提取 URL
    │   └── 提取前置条件/注意事项作为 _knowledge_hints
    │
    └── 输出补全后的 YAML 用例
```

---

## 5. 知识库设计

### 5.1 知识来源与迁移策略

```
          ┌─────────────────────┐
          │    OpenClaw Agent   │
          │  (同网段，已有基础   │
          │   产品知识)          │
          └──────────┬──────────┘
                     │ 整理导出
                     ▼
          ┌─────────────────────┐
          │  知识迁移脚本        │
          │  openclaw2local.py  │
          │  格式化 → 入库      │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │     本地知识库       │
          │  ┌───────────────┐  │
          │  │  ChromaDB     │  │  产品文档、操作手册（RAG 检索）
          │  │  (向量存储)    │  │
          │  ├───────────────┤  │
          │  │  SQLite       │  │  页面结构、元素映射、操作流程、环境拓扑
          │  │  (结构化存储)  │  │
          │  └───────────────┘  │
          └─────────────────────┘
                     ▲
                     │ 探索 + 人工补充
          ┌──────────┴──────────┐
          │   Agent 自主探索     │
          │   + 用户人工补充    │
          └─────────────────────┘
```

### 5.2 静态知识（ChromaDB 向量库）

存储内容：
- 产品功能说明文档
- API 接口文档
- 操作手册/用户指南
- 常见问题/故障处理

入库流程：
1. 产品 Doc (PDF/Word/Markdown) → 文档解析器分片
2. 调用 Embedding 模型生成向量
3. 存入 ChromaDB，附带元数据（文档来源、版本、时间）

### 5.3 动态知识（V1：元素定位缓存）

> **V1 范围**：仅建立元素定位缓存表，其余结构化表（页面结构、操作流程、拓扑）推迟到 V2。拓扑信息仍通过 `topology.yaml` 文件管理。

**V1 数据表设计：**

```sql
-- 元素定位缓存表（V1 唯一 SQLite 表）
CREATE TABLE element_locator (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    page_url      TEXT NOT NULL,
    description   TEXT NOT NULL,          -- 元素描述 "登录按钮"
    locator_type  TEXT NOT NULL,          -- role / css / xpath / visual
    locator_value TEXT NOT NULL,          -- 定位符值
    success_count INTEGER DEFAULT 0,      -- 成功次数（用于策略排序）
    fail_count    INTEGER DEFAULT 0,
    last_used     TIMESTAMP,
    UNIQUE(page_url, description, locator_type)
);
```

**V2 待补充表**（设计已就绪，届时创建）：
- `page_structure` — 页面结构快照
- `workflow` — 操作流程模板
- `topology` — 环境拓扑（当前用 YAML 文件替代）

### 5.4 OpenClaw 知识迁移

OpenClaw Agent 作为知识整理工具，通过脚本与其交互：

1. 向 OpenClaw 发送领域知识分类查询请求
2. OpenClaw 返回结构化的 JSON/Markdown 知识摘要
3. 迁移脚本解析 → 分片/结构化 → 入库本地 ChromaDB + SQLite

迁移脚本设计为独立工具，可重复执行以同步增量知识。

---

## 6. 测试用例管理

### 6.1 存储格式：YAML（V1 简化版）

> **V1 范围**：仅定义 `title`、`steps`、`assertions` 三个核心字段。模板变量 `{{}}`、优先级、标签、分类等高级特性推迟到 V2。

```yaml
# 示例：用户登录测试（V1 格式）
title: "登录功能验证 - 正常登录"
steps:
  - description: "打开Web控制台"
    target: web
    action: navigate
    params:
      url: "http://192.168.1.100:8080"

  - description: "输入用户名 admin"
    target: web
    action: input
    params:
      element: "用户名输入框"
      value: "admin"

  - description: "输入密码"
    target: web
    action: input
    params:
      element: "密码输入框"
      value: "123456"

  - description: "点击登录按钮"
    target: web
    action: click
    params:
      element: "登录按钮"

assertions:
  - "页面显示'欢迎'"
  - "页面包含'首页'导航"
```

### 6.2 用例目录结构

```
testcases/
├── yaml/
│   ├── web/                    # Web 控制台用例
│   │   ├── login/
│   │   │   └── TC-LOGIN-001.yaml
│   │   ├── user_management/
│   │   └── device_management/
│   ├── client/                 # 客户端用例
│   ├── controller/             # 控制器用例
│   └── integration/            # 端到端集成用例
├── schemas/
│   └── testcase_schema.json    # YAML 结构约束
└── generated/                  # Agent 探索生成的用例
```

### 6.3 Excel 用例导入

```
测试平台导出 Excel
        │
        ▼
┌───────────────────┐
│  excel2yaml.py    │  Excel 解析 → 字段映射 → 知识库补全 → YAML 生成
│  (格式转换+知识补全)│  检索知识库补全缺失的元素描述、URL、前置条件
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  人工/Agent 精修   │  补充断言、调整步骤粒度、添加变量引用
└───────┬───────────┘
        │
        ▼
 testcases/yaml/ 入库
```

转换器规则：
- Excel 列映射到 YAML 字段（用例名→title, 步骤→steps, 预期→assertions）
- **每个步骤自动检索知识库，补全 element、url 等参数（距离 < 0.3 时采纳）**
- 未能自动转换的步骤标记为 `# TODO: 需人工确认`
- 知识库补全的来源记录在 `_knowledge_source` 字段，便于追溯
- 后续接入平台 api 时，新增 `api2yaml.py` 即可

### 6.4 用例执行引擎（V1）

```python
# runner.py 伪代码
class TestCaseRunner:
    def run(self, case_path: str) -> TestResult:
        case = load_yaml(case_path)
        # 1. 将 case.steps 注入 Agent 的 plan 节点
        # 2. Agent 按 understand→plan→execute→verify→summarize 执行
        # 3. 收集执行截图和结果
        # 4. 汇总输出到控制台
```

> **V2 增强**：模板变量解析 `{{config.xxx}}`、按 mode 选择 Agent 图、结构化报告生成。

---

## 7. LLM 集成方案

### 7.1 模型分工

| 模型 | 角色 | 调用方式 |
|------|------|---------|
| **DeepSeek-V4-Pro** | 主推理引擎：理解用例、规划步骤、决策异常处理、编排流程 | LangGraph Agent 核心 LLM |
| **Zhipu GLM-4V** | 视觉 Tool：截图分析、UI元素定位、前后对比 | DeepSeek 通过 Tool Calling 调用 |
| **Embedding 模型** | 文档向量化，知识库检索 | ChromaDB 入库/检索时使用 |

### 7.2 Tool Calling 流程（V1：直接执行，不重试）

```
DeepSeek: "我需要点击登录按钮"
    │
    │ Tool Call: web_click(description="登录按钮")
    │
    ▼
web_tool 执行:
    1. 查 element_locator 表 → 有缓存，直接用
    2. 无缓存 → Playwright 按 role/text/css/xpath 多策略尝试
    3. 成功 → 缓存定位策略 → 返回 "点击成功"
       失败 → 返回 "未找到元素"（V1 不重试，直接标记失败）
    │
    ▼
DeepSeek: 收到结果，继续下一步（成功）或交给 verify 节点（失败）
```

> **V2 增强**：失败时 DeepSeek 可主动调用 `vision_locate` 获取坐标，再调用 `desktop_click` 用视觉方式重试。

### 7.3 模型配置

```python
# llm_config.py 伪代码
LLM_CONFIG = {
    "deepseek": {
        "model": "deepseek-v4-pro",
        "api_base": "https://api.deepseek.com/v1",
        "api_key": "${DEEPSEEK_API_KEY}",
        "temperature": 0.1,       # 测试场景用低温度保证确定性
        "max_tokens": 4096,
    },
    "zhipu_vision": {
        "model": "glm-4v",
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "${ZHIPU_API_KEY}",
    },
    "embedding": {
        "model": "text-embedding-3-small",  # 或其他可用 embedding
        "api_base": "...",
    }
}
```

---

## 8. 探索式用例生成流程（V2）

> **V1 不实现此功能，整体推迟到 V2。** 以下为设计留存，V2 开发时使用。

```
新功能上线 / 用户指定探索目标
        │
        ▼
┌───────────────────┐
│ 1. 环境探索        │  Agent 遍历目标页面/界面
│                   │  记录页面结构、可交互元素、表单字段
│                   │  调用 vision_describe_ui 描述界面
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ 2. 流程发现        │  尝试常见操作路径
│                   │  点击按钮 → 查看响应 → 记录状态变化
│                   │  对比操作前后截图差异
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ 3. 用例生成        │  LLM 基于探索结果 + 知识库
│                   │  生成：正常流程 / 异常流程 / 边界条件
│                   │  输出格式：YAML 用例
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ 4. 人工审核        │  生成的用例放入 testcases/generated/
│                   │  标记为 draft，等待人工确认
└───────────────────┘
```

---

## 9. 项目目录结构

```
iotnac/
│
├── DESIGN.md                       # 本设计文档
├── README.md                       # 工程说明
├── requirements.txt                # Python 依赖
├── .env.example                    # 环境变量模板
│
├── config/                         # 配置文件
│   ├── __init__.py
│   ├── settings.py                 # 全局配置（日志、路径等）
│   ├── llm_config.py               # DeepSeek + Zhipu 配置
│   └── topology.yaml               # 环境拓扑（IP、端口、主机名）
│
├── agent/                          # LangGraph Agent 层
│   ├── __init__.py
│   ├── graph.py                    # 主执行图定义
│   ├── state.py                    # Agent 状态定义
│   ├── nodes/                      # 图节点实现
│   │   ├── __init__.py
│   │   ├── understand.py           # 理解节点
│   │   ├── plan.py                 # 规划节点
│   │   ├── execute.py              # 执行节点（Tool 调度）
│   │   ├── verify.py               # 验证节点
│   │   ├── recover.py              # 恢复节点
│   │   └── summarize.py            # 总结节点
│   ├── tools/                      # Tool 定义（DeepSeek 可调用）
│   │   ├── __init__.py
│   │   ├── web_tool.py             # Playwright 操作
│   │   ├── desktop_tool.py         # 键鼠 + 截图
│   │   ├── ssh_tool.py             # SSH 远程执行
│   │   ├── vision_tool.py          # Zhipu 视觉分析
│   │   └── knowledge_tool.py       # 知识库操作
│   └── prompts/                    # Prompt 模板
│       ├── system_prompt.py        # 系统级 Prompt
│       ├── understand_prompt.py    # 理解节点 Prompt
│       ├── plan_prompt.py          # 规划节点 Prompt
│       └── recover_prompt.py       # 恢复节点 Prompt
│
├── executors/                      # 执行器层（确定性封装）
│   ├── __init__.py
│   ├── web_executor.py             # Playwright 封装（多策略定位）
│   ├── desktop_executor.py         # pywinauto + PyAutoGUI 双模封装
│   └── ssh_executor.py             # Paramiko 封装（交换机+控制器）
│
├── knowledge/                      # 知识库
│   ├── __init__.py
│   ├── manager.py                  # 知识管理器（统一入口）
│   ├── vector_store.py             # ChromaDB 向量存储管理
│   ├── plan_cache.py               # Plan 缓存（相同用例跳过 LLM 规划）
│   ├── locator_cache.py            # 元素定位缓存（V1 唯一 SQLite 表）
│   ├── docs/                       # 产品知识文档（Markdown，入库到 ChromaDB）
│   ├── migration/                  # OpenClaw 知识迁移（V2）
│   │   ├── __init__.py
│   │   └── openclaw_migrator.py    # OpenClaw → 本地知识库
│   └── schemas/                    # 知识结构定义
│       └── element_locator.py      # 元素定位 schema
│
├── testcases/                      # 测试用例
│   ├── yaml/                       # YAML 用例库
│   │   ├── web/
│   │   ├── client/
│   │   ├── controller/
│   │   └── integration/
│   ├── generated/                  # Agent 自动生成的用例（V2）
│   ├── runner.py                   # 用例执行器
│   └── converters/                 # 格式转换器
│       ├── __init__.py
│       └── excel2yaml.py           # Excel → YAML
│
├── explorer/                       # 探索式测试（V2）
│   ├── __init__.py
│   ├── web_explorer.py             # Web 页面探索
│   ├── client_explorer.py          # 客户端界面探索
│   └── case_generator.py           # 用例生成器
│
├── utils/                          # 通用工具
│   ├── __init__.py
│   ├── screenshot.py               # 截图工具
│   ├── logger.py                   # 日志
│   └── result.py                   # 测试结果数据结构
│
├── data/                           # 运行时数据
│   ├── screenshots/                # 测试过程中截图
│   ├── logs/                       # 运行日志
│   ├── chroma_db/                  # ChromaDB 向量存储（720 文档片段）
│   └── reports/                    # HTML 测试报告
│
└── docs/                           # 产品文档（已入库 knowledge/docs/）
    └── product/                    # 产品 Doc 文档存放处
```

---

## 10. 核心依赖

```
# requirements.txt
langgraph>=0.2.0
langchain>=0.3.0
langchain-deepseek
playwright
pywinauto           # Windows 控件自动化（优先）
pyautogui           # 键鼠操作（降级兜底）
Pillow
paramiko
chromadb
openai              # 兼容 DeepSeek / Zhipu API 调用
pyyaml
openpyxl            # Excel 解析
pydantic            # 数据模型
pydantic-settings   # 配置管理
loguru              # 日志
```

---

## 11. 配置说明

### 11.1 环境变量 (.env)

```bash
# LLM
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
ZHIPU_API_KEY=xxxxxxxxxxxxxxxxxx

# 环境拓扑
CONTROLLER_HOST=192.168.1.100
CONTROLLER_PORT=22
CONTROLLER_USER=root
CONTROLLER_PASSWORD=xxxxxxxx

SWITCH_HOST=192.168.1.1
SWITCH_PORT=22
SWITCH_USER=admin
SWITCH_PASSWORD=xxxxxxxx

WEB_CONSOLE_URL=http://192.168.1.100:8080

# 知识库
CHROMA_PERSIST_DIR=./data/chroma_db
```

### 11.2 拓扑文件 (topology.yaml)

```yaml
devices:
  controller:
    type: linux_server
    host: "${CONTROLLER_HOST}"
    port: 22
    services:
      - name: "控制器服务"
        process_name: "controllerd"
        log_path: "/var/log/controller/app.log"

  switch:
    type: huawei_switch
    host: "${SWITCH_HOST}"
    port: 22
    os: "VRP"

  web_console:
    type: web_service
    url: "${WEB_CONSOLE_URL}"
    browser: chromium
    headless: false       # 测试终端可见操作，不做无头模式
```

---

## 12. 开发阶段规划（V1）

| 阶段 | 内容 | 预计 | 完成标准 |
|------|------|------|---------|
| **Phase 1: 基础框架** | 配置管理、日志、执行器层（Playwright / pywinauto+PyAutoGUI / Paramiko） | ~2 周 | 手动调用各执行器均能返回正确结果 |
| **Phase 2: Agent 核心** | LangGraph 线性图（5节点）、5 个 Tool、DeepSeek + Zhipu 集成 | ~1.5 周 | 输入"打开控制台登录"，Agent 能自动执行并验证 |
| **Phase 3: 知识库** | ChromaDB 向量库 + 元素定位缓存表 + 文档入库 | ~1 周 | 检索产品问题能返回相关知识；元素定位二次命中 |
| **Phase 4: 用例系统** | YAML 简化规范 + Excel 转换器 + 执行器 | ~0.5 周 | excel2yaml 能转换并输出可执行用例 |
| **Phase 5: 探索式测试** | → **推迟到 V2** | — | — |
| **Phase 6: 完善与集成** | 日志归档、截图保存（报告暂打印控制台） | ~0.5 周 | 执行完成后截图和日志正确落盘 |

**V1 总计约 5.5 周**，产出：自然语言 → Agent执行 → 验证 → 截图的完整闭环。

---

## 13. V2 路线图

以下内容已在 V1 中完成设计，实际开发推迟到 V2：

### 13.1 Agent 增强
- **retry/recover 节点**：验证失败时 LLM 分析截图 → 调整定位策略 → 重试（最多 N 次）
- **条件分支**：根据验证结果（passed/failed）走不同路径

### 13.2 知识库扩展
- **SQLite 表补全**：`page_structure`（页面结构快照）、`workflow`（操作流程模板）、`topology`（环境拓扑）
- **OpenClaw 迁移脚本**：`openclaw_migrator.py`，从 OpenClaw Agent 导出结构化知识并入库
- **Agent 自主探索入库**：探索页面后自动记录页面结构到 `page_structure` 表

### 13.3 用例系统增强
- **YAML 高级特性**：模板变量 `{{config.xxx}}`、优先级、标签、分类、前置条件
- **多模式支持**：按 `mode` 字段（web/desktop/hybrid）自动选择对应 Agent 图
- **测试平台 API 接入**：新增 `api2yaml.py`，从平台直接拉取用例

### 13.4 探索式测试
- **Web 探索器**：遍历目标页面 → 记录元素树 → 尝试操作路径 → 生成用例
- **客户端探索器**：Zhipu 视觉描述界面 → 识别可交互区域 → 记录流程
- **用例自动生成**：基于探索结果 + 知识库 → LLM 生成正常/异常/边界用例 → 人工审核

### 13.5 报告与集成
- **结构化报告生成**：HTML/JSON 测试报告，含截图、步骤详情、通过率
- **CI/CD 集成**：命令行入口 + 退出码，可接入 Jenkins 等流水线
- **与其他系统对接**：测试平台 API、缺陷管理系统等
