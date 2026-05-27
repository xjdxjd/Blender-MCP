# 项目分支管理规则

## ⚠️ 重要规则

**所有开发工作必须在 `trae/solo-agent-C6RI1Z` 分支上进行！**

### 规则说明

1. **开发分支**: `trae/solo-agent-C6RI1Z`
   - 所有新功能开发、Bug 修复、文档更新等代码改动
   - 提交到这个分支

2. **发布分支**: `main`
   - **不要** 直接在 main 分支上开发或提交代码
   - **只有** 当用户明确要求 "合并到 main" 时，才执行合并操作

### 操作流程

```
✅ 正确流程:
1. 确保在 trae/solo-agent-C6RI1Z 分支
2. 开发代码
3. 提交到 trae/solo-agent-C6RI1Z
4. (重复步骤 2-3 直到功能完成)

❌ 错误流程:
1. 在 main 分支上开发
2. 直接提交到 main
3. 忘记切换回开发分支
```

### 合并时机

只有在以下情况下才合并到 main：
- 用户明确要求 "合并到 main" / "发布" / "release"
- 阶段性开发完成，需要发布时

### 合并命令

```bash
# 1. 切换到 main
git checkout main

# 2. 合并开发分支
git merge trae/solo-agent-C6RI1Z

# 3. 推送到远程
git push origin main
```

### 验证当前分支

每次提交前检查：
```bash
git branch --show-current
# 应该是: trae/solo-agent-C6RI1Z
```

---

最后更新: 2026-05-27
