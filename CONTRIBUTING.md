# 贡献指南

> **文档版本**：v1.4
> **最后更新**：2026-05-25

---

感谢您对 Blender-mcp 项目的兴趣！我们欢迎各种形式的贡献，包括但不限于：

- 🐛 报告 Bug
- 💡 提出新功能建议
- 📝 完善文档
- 🔧 提交代码修复
- ✨ 添加新功能
- 🧪 编写测试

请花几分钟阅读本指南，确保您的贡献能够被顺利合并。

---

## 目录

- [行为准则](#行为准则)
- [开始之前](#开始之前)
- [开发环境设置](#开发环境设置)
- [分支管理](#分支管理)
- [开发流程](#开发流程)
- [提交规范](#提交规范)
- [代码规范](#代码规范)
- [测试要求](#测试要求)
- [文档要求](#文档要求)
- [Pull Request 流程](#pull-request-流程)
- [Issue 报告](#issue-报告)

---

## 行为准则

参与本项目的所有成员必须遵守以下行为准则：

- **友善和尊重**：与所有社区成员进行友善和尊重的互动
- **包容性**：欢迎不同背景和经验水平的贡献者
- **专业性**：保持专业的交流态度，避免人身攻击
- **建设性**：提供建设性的反馈和批评

违反行为准则的行为将被移除贡献资格。

---

## 开始之前

在开始贡献之前，请确保：

1. ⭐ Star 本项目
2. 🔱 Fork 本仓库
3. 📖 阅读 [需求文档](./document/需求文档.md) 和 [系统架构文档](./document/系统架构文档.md)
4. 💬 在 [GitHub Issues](https://github.com/your-org/blender-mcp/issues) 中搜索现有 Issue，避免重复
5. 📝 查看 [开发计划](./document/开发计划.md) 了解当前开发优先级

---

## 开发环境设置

### 环境要求

- Python 3.10+
- Blender 4.2+
- Git

### 克隆并安装

```bash
# 克隆您的 Fork
git clone https://github.com/YOUR_USERNAME/blender-mcp.git
cd blender-mcp

# 添加上游仓库
git remote add upstream https://github.com/your-org/blender-mcp.git

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 安装 Blender 插件（开发模式）
mkdir -p ~/.config/blender/4.2/scripts/addons/
ln -s $(pwd)/blender_plugin ~/.config/blender/4.2/scripts/addons/blender_mcp
```

### 验证安装

```bash
# 运行测试
pytest tests/unit/ -v

# 检查代码格式
black --check mcp_server/ core/ blender_plugin/

# 类型检查
mypy mcp_server/ core/
```

---

## 分支管理

我们使用 Git Flow 分支策略：

```
main          # 稳定发布分支
├── develop   # 开发主分支
├── feat/*    # 功能分支
├── fix/*     # 修复分支
├── docs/*    # 文档分支
└── refactor/* # 重构分支
```

### 分支命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 功能 | `feat/TICKET-ID-description` | `feat/20-add-stl-export` |
| 修复 | `fix/TICKET-ID-description` | `fix/25-fix-bool-crash` |
| 文档 | `docs/description` | `docs/update-readme` |
| 重构 | `refactor/description` | `refactor/adapter-cleanup` |

---

## 开发流程

### 1. 创建功能分支

```bash
# 确保 develop 是最新的
git checkout develop
git pull upstream develop

# 创建功能分支
git checkout -b feat/20-add-stl-export
```

### 2. 开发

```bash
# 编写代码
# ...

# 本地测试
pytest tests/unit/ -v
pytest tests/integration/ -v

# 代码格式
black mcp_server/ core/ blender_plugin/

# 类型检查
mypy mcp_server/ core/
```

### 3. 提交更改

```bash
# 添加更改
git add .

# 提交（使用语义化提交信息）
git commit -m "feat(export): add STL format support for 3D printing"
```

### 4. 同步上游

```bash
# 获取上游最新代码
git fetch upstream

# 变基到 develop
git rebase upstream/develop

# 解决冲突（如果有）
```

### 5. 推送并创建 PR

```bash
# 推送分支
git push origin feat/20-add-stl-export
```

然后在 GitHub 上创建 Pull Request。

---

## 提交规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### 提交类型

| 类型 | 描述 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(export): add STL ASCII format support` |
| `fix` | Bug 修复 | `fix(adapter): handle null mesh data gracefully` |
| `docs` | 文档更新 | `docs: update API documentation` |
| `style` | 代码格式（不影响功能） | `style: format code with black` |
| `refactor` | 代码重构 | `refactor(command): simplify error handling` |
| `perf` | 性能优化 | `perf(sync): reduce state sync overhead` |
| `test` | 测试相关 | `test: add e2e tests for export workflow` |
| `build` | 构建/依赖 | `build: add pytest-cov for coverage` |
| `ci` | CI/CD | `ci: add GitHub Actions workflow` |
| `chore` | 维护 | `chore: update requirements` |

### 提交示例

```
feat(export): add STL format support for 3D printing

- support binary STL export
- support ASCII STL export
- add scale parameter
- add unit tests

Closes #20
```

---

## 代码规范

### Python 代码规范

- 遵循 [PEP 8](https://pep8.org/)
- 所有公开函数必须有类型注解
- 使用 [Google 风格 docstring](https://google.github.io/styleguide/pyguide.html)
- 行长度限制：88 字符（Black 默认）

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | 小写下划线 | `command_handler.py` |
| 类 | PascalCase | `CommandHandler` |
| 函数/方法 | 小写下划线 | `create_object()` |
| 变量 | 小写下划线 | `object_id` |
| 常量 | 大写下划线 | `MAX_RETRY_COUNT` |
| 私有成员 | 单下划线前缀 | `_internal_state` |

### Docstring 示例

```python
def export_model(
    object_id: str | None,
    format: str,
    filepath: str,
    options: dict | None = None
) -> dict[str, str | bool]:
    """导出模型到指定格式文件。

    Args:
        object_id: 目标对象 ID，为 None 时导出全部选中对象
        format: 导出格式，支持 "stl" 或 "obj"
        filepath: 导出文件路径
        options: 导出选项，可选键值:
            - scale: 缩放比例 (float)
            - use_selection: 仅导出选中对象 (bool)
            - ascii: STL 使用 ASCII 格式 (bool)

    Returns:
        包含 success (bool) 和 filepath (str) 的字典

    Raises:
        ObjectNotFoundError: 对象不存在时抛出
        UnsupportedFormatError: 格式不支持时抛出

    Examples:
        >>> result = export_model("Cube", "stl", "/tmp/model.stl")
        >>> print(result["success"])
        True
    """
    ...
```

---

## 测试要求

### 测试覆盖率目标

| 测试类型 | 覆盖率目标 |
|----------|-----------|
| 单元测试 | ≥ 90% |
| 集成测试 | ≥ 70% |
| 端到端测试 | 核心流程 100% |

### 测试文件命名

```
tests/
├── unit/
│   ├── test_tools.py
│   ├── test_command.py
│   └── test_adapter.py
├── integration/
│   ├── test_connection.py
│   └── test_state_sync.py
└── e2e/
    ├── test_create_export_workflow.py
    └── test_import_repair_workflow.py
```

### 测试命名规范

```python
class TestExportModel:
    """export_model 工具的测试"""

    def test_export_stl_success(self):
        """导出 STL 文件成功"""
        ...

    def test_export_obj_with_scale(self):
        """导出 OBJ 文件并应用缩放"""
        ...

    def test_export_invalid_format_raises_error(self):
        """无效格式应抛出 UnsupportedFormatError"""
        ...
```

---

## 文档要求

### 新功能文档

添加新功能时，必须更新以下文档：

1. **README.md** - 如果添加了新工具，更新核心工具列表
2. **系统架构文档.md** - 更新 MCP 工具定义章节
3. **开发计划.md** - 如果是新功能，更新完成度追踪表

### API 变更文档

如果修改了现有工具的接口：

1. 更新工具的参数和返回值定义
2. 在 PR 描述中说明变更原因和影响
3. 确保向后兼容性或明确说明破坏性变更

---

## Pull Request 流程

### PR 准备

1. ✅ 所有测试通过
2. ✅ 代码格式符合规范
3. ✅ 类型检查通过
4. ✅ 文档已更新
5. ✅ 提交信息符合规范

### PR 描述模板

```markdown
## 描述
<!-- 简要说明这个 PR 做了什么 -->

## 变更类型
- [ ] 🐛 Bug 修复
- [ ] ✨ 新功能
- [ ] 📝 文档更新
- [ ] 🔧 代码重构
- [ ] 🧪 测试更新

## 影响范围
<!-- 这个 PR 影响哪些模块 -->

## 测试
<!-- 如何测试这些变更 -->

## 截图/日志
<!-- 如果有的话 -->

## Checklist
- [ ] 代码遵循项目规范
- [ ] 添加了必要的测试
- [ ] 文档已更新
- [ ] 提交信息符合规范
```

### PR 审查

1. 至少需要 1 个维护者审查
2. 所有 CI 检查必须通过
3. 解决所有审查意见
4. 保持提交历史整洁

---

## Issue 报告

### Bug 报告

使用 [Bug Report 模板](./.github/ISSUE_TEMPLATE/bug_report.md)：

```markdown
## Bug 描述
<!-- 简明扼要地描述问题 -->

## 复现步骤
1.
2.
3.

## 预期行为
<!-- 应该发生什么 -->

## 实际行为
<!-- 实际发生了什么 -->

## 环境信息
- Blender 版本:
- 操作系统:
- Python 版本:

## 日志/截图
<!-- 如果有的话 -->
```

### 功能请求

使用 [Feature Request 模板](./.github/ISSUE_TEMPLATE/feature_request.md)：

```markdown
## 功能描述
<!-- 描述你想要的功能 -->

## 使用场景
<!-- 这个功能解决什么问题 -->

## 建议的解决方案
<!-- 你有什么想法 -->

## 参考
<!-- 相关的 Issue、文档或链接 -->
```

---

## 常见问题

### Q: 如何处理大型重构？
**A:** 大型重构应该分成多个小的 PR 分步提交，每个 PR 都有可测试的功能。

### Q: PR 提交后可以修改吗？
**A:** 在审查过程中可以修改，但审查通过后应避免大幅修改。如果需要重大修改，请在评论中说明原因。

### Q: 如何处理敏感信息？
**A:** 绝对不要在代码或提交信息中包含敏感信息（如密钥、密码）。如果不小心提交了，请立即联系维护者。

---

## 联系方式

- 📧 邮箱: support@your-org.com
- 💬 GitHub Discussions: https://github.com/your-org/blender-mcp/discussions
- 🐦 Twitter: @blender_mcp

---

感谢您的贡献！🎉
