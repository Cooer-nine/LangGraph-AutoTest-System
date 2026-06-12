# AI自动化测试框架 (AI-NAC)

一个基于 LLM Agent 的智能自动化测试框架，支持 Web、SSH、桌面端等多种执行环境，具备视觉理解和自然语言处理能力。

## 🎯 项目特点

- **LLM 驱动**: 使用 DeepSeek/Zhipu 等大语言模型理解测试意图并生成执行计划
- **多执行器支持**: Web (Playwright)、SSH/Telnet、桌面端自动化
- **视觉能力**: 集成视觉模型进行页面理解和元素定位兜底
- **RAG 知识库**: 基于 ChromaDB + Reranker 的产品文档检索系统
- **智能缓存**: Plan 缓存和元素定位缓存提升执行效率
- **HTML 报告**: 自动生成带截图的可视化测试报告

## 🏗️ 架构设计

```
iotnac/
├── agent/              # Agent 核心
│   ├── nodes/         # 工作流节点（理解、规划、执行、验证、总结）
│   ├── tools/         # 工具集（Web、SSH、桌面、视觉、知识库）
│   ├── prompts/       # 提示词模板
│   ├── graph.py       # LangGraph 工作流定义
│   └── llm_client.py  # LLM 客户端封装
├── executors/          # 执行器
│   ├── web_executor.py    # Playwright Web 自动化
│   ├── ssh_executor.py    # SSH/Telnet 远程执行
│   └── desktop_executor.py # 桌面端自动化（PyAutoGUI/Vision）
├── testcases/          # 测试用例系统
│   ├── schemas/       # 用例数据模型
│   ├── converters/    # Excel/YAML 转换器
│   └── runner.py      # 用例执行引擎
├── knowledge/          # 知识库（框架代码，不含产品文档）
│   ├── manager.py     # 知识库管理器
│   ├── vector_store.py # 向量存储封装
│   ├── plan_cache.py  # Plan 缓存
│   └── locator_cache.py # 元素定位缓存
├── config/             # 配置管理
│   ├── settings.py    # 应用配置
│   ├── llm_config.py  # LLM 配置
│   └── topology.yaml  # 环境拓扑模板
├── utils/              # 工具类
│   ├── logger.py      # 日志管理
│   ├── reporter.py    # HTML 报告生成
│   ├── screenshot.py  # 截图工具
│   └── result.py      # 测试结果封装
├── main.py             # 主入口
├── requirements.txt    # Python 依赖
└── .env.example        # 环境变量模板
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/your-username/ai-nac.git
cd ai-nac

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

关键配置项：
```env
# LLM API 密钥
DEEPSEEK_API_KEY=your_api_key
ZHIPU_API_KEY=your_api_key

# 被测环境拓扑
CONTROLLER_HOST=192.168.1.100
SWITCH_HOST=192.168.1.1
WEB_CONSOLE_URL=http://192.168.1.100:8080

# 知识库路径
CHROMA_PERSIST_DIR=./data/chroma_db
```

### 3. 构建知识库（可选）

将产品文档放入 `knowledge/docs/` 目录（Markdown 格式），然后：

```python
from knowledge.manager import KnowledgeManager

manager = KnowledgeManager()
manager.build_knowledge_base()
```

### 4. 运行测试

#### 方式一：自然语言指令

```python
from main import run_natural_language_test

result = run_natural_language_test(
    instruction="验证用户能够正常登录系统",
    test_name="登录功能验证"
)
print(f"测试结果: {result.status}")
```

#### 方式二：YAML 测试用例

创建 `testcases/yaml/login_test.yaml`:

```yaml
test_name: "登录功能验证"
description: "验证用户使用正确凭据能够成功登录"
steps:
  - action: "navigate"
    target: "${WEB_CONSOLE_URL}"
  - action: "fill"
    target: "用户名输入框"
    value: "admin"
  - action: "fill"
    target: "密码输入框"
    value: "Admin@123"
  - action: "click"
    target: "登录按钮"
  - action: "verify"
    target: "首页标题"
    expected: "控制台"
```

执行：

```python
from testcases.runner import TestCaseRunner

runner = TestCaseRunner()
result = runner.run_from_yaml("testcases/yaml/login_test.yaml")
```

## 📦 核心组件说明

### Agent 工作流

1. **Understand**: 理解用户意图，提取关键信息
2. **Plan**: 生成详细的执行步骤计划
3. **Execute**: 调用合适的执行器执行操作
4. **Verify**: 验证执行结果是否符合预期
5. **Summarize**: 生成测试总结报告

### 执行器

- **WebExecutor**: 基于 Playwright，支持 Chromium/Firefox/WebKit
- **SSHExecutor**: 基于 Paramiko，支持 SSH 和 Telnet 协议
- **DesktopExecutor**: 双模策略（DOM优先 + Vision兜底）

### 知识库

- **向量检索**: ChromaDB + 中文优化的 Embedding 模型
- **重排序**: BGE Reranker 提升检索精度
- **缓存机制**: Plan 缓存和元素定位缓存加速重复任务

## 🔧 适配到新产品

本框架是通用的，适配新产品只需：

1. **更新 `.env`**: 配置新产品的 URL、IP、账号等
2. **更新 `topology.yaml`**: 描述新环境的设备拓扑
3. **导入产品文档**: 将产品文档放入 `knowledge/docs/`
4. **编写测试用例**: 用 YAML 或自然语言描述测试场景

无需修改框架代码！

## 📝 开发路线图

- [x] Phase 1: 基础框架搭建
- [x] Phase 2: Agent 核心实现
- [x] Phase 3: 知识库与 RAG
- [x] Phase 4: 测试用例系统
- [x] Phase 5: 执行器完善
- [x] Phase 6: 集成与优化
- [ ] Phase 7: 更多执行器支持（API、数据库等）
- [ ] Phase 8: 分布式执行支持

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**注意**: 本仓库仅包含通用框架代码，不包含任何产品特定的文档和数据。使用时需要自行配置环境和导入产品知识。
