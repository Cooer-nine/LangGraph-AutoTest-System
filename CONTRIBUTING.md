# 贡献指南

欢迎为 AI-NAC 项目做出贡献！

## 🐛 报告问题

如果你发现了 bug 或有新功能建议，请：

1. 先在 Issues 中搜索是否已有类似问题
2. 如果没有，创建一个新的 Issue，详细描述：
   - 问题现象
   - 复现步骤
   - 预期行为
   - 实际行为
   - 环境信息（Python 版本、操作系统等）

## 🔧 提交代码

### 开发流程

1. **Fork 本仓库**

2. **创建特性分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **编写代码**
   - 遵循 PEP 8 代码规范
   - 添加必要的注释和文档字符串
   - 保持代码简洁清晰

4. **测试**
   - 确保你的修改没有破坏现有功能
   - 为新功能添加测试用例

5. **提交**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```
   
   Commit 消息格式：
   - `feat`: 新功能
   - `fix`: 修复 bug
   - `docs`: 文档更新
   - `style`: 代码格式调整
   - `refactor`: 重构
   - `test`: 测试相关
   - `chore`: 构建过程或辅助工具变动

6. **推送到你的 Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **创建 Pull Request**
   - 在 GitHub 上提交 PR 到主仓库的 `main` 分支
   - 在 PR 描述中说明：
     - 解决了什么问题
     - 如何测试你的改动
     - 相关的 Issue 编号（如果有）

## 📝 代码规范

### Python 风格

- 使用 4 空格缩进
- 变量名使用 `snake_case`
- 类名使用 `PascalCase`
- 常量使用 `UPPER_CASE`
- 函数和类添加 docstring

### 示例

```python
def execute_action(action: str, target: str) -> ActionResult:
    """
    执行指定的操作
    
    Args:
        action: 操作类型 (click, fill, navigate 等)
        target: 目标元素描述
        
    Returns:
        ActionResult: 执行结果
        
    Raises:
        ExecutionError: 当执行失败时
    """
    # 实现逻辑
    pass
```

## 🎯 可以贡献的方向

1. **新执行器**: 支持更多协议和环境（API、数据库等）
2. **改进 Agent**: 优化工作流、提示词、缓存策略
3. **增强知识库**: 改进检索算法、支持更多文档格式
4. **测试用例**: 添加更多示例用例
5. **文档**: 完善使用文档、教程、最佳实践
6. **性能优化**: 提升执行速度、降低资源消耗
7. **Bug 修复**: 解决已知问题

## 💡 提问

有问题？欢迎：
- 在 Discussions 中讨论
- 加入社区（如果有的话）
- 直接联系维护者

感谢你的贡献！🎉
