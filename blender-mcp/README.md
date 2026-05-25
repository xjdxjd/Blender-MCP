# Blender MCP

一个 Model Context Protocol (MCP) 服务器，允许 AI 助手（如 Trae SOLO、hermes-agent）通过自然语言与 Blender 3D 建模软件交互。

## 项目结构

```
blender-mcp/
├── mcp_server/          # MCP 服务端
│   ├── server.py       # 服务主入口
│   ├── tools.py        # 工具定义与注册
│   └── schemas.py      # 数据模型
├── blender_plugin/      # Blender 插件
│   ├── addon.py        # 插件主入口
│   ├── operators.py    # UI 操作
│   ├── panels.py       # UI 面板
│   └── connection.py   # WebSocket 连接
├── core/               # 核心逻辑
│   ├── command.py      # 命令处理
│   ├── adapter.py      # API 适配
│   └── state.py        # 状态管理
├── config/             # 配置文件
└── tests/             # 测试代码
```

## 快速开始

### 1. 启动 MCP 服务

```bash
cd /workspace/blender-mcp
pip install -r requirements.txt
python -m mcp_server.server
```

### 2. 安装 Blender 插件

1. 打开 Blender (4.2+)
2. Edit → Preferences → Add-ons → Install...
3. 选择 `blender-mcp` 目录下的 `blender_plugin` 文件夹
4. 启用 "Blender MCP" 插件

### 3. 连接服务

1. 在 3D View 右侧找到 "Blender MCP" 面板
2. 确认 Host 为 127.0.0.1，Port 为 8765
3. 点击 "Connect" 连接

### 4. 在 AI 助手使用

在 Trae SOLO 或 hermes-agent 中配置使用这个 MCP 服务器即可。

## 功能 (阶段一已完成 ✅)

- MCP 协议服务启动
- WebSocket 连接管理
- Ping 工具（测试连接与延迟）
- 完整的 Blender 插件 UI
- 配置系统（YAML + 环境变量）
- 工具注册机制

## 开发进度

| 阶段 | 状态 | 说明 | 完成日期 |
|------|------|------|---------|
| ✅ **阶段一 (Day 1-5)** | 已完成 | 项目初始化、基础架构、连接管理、配置系统、ping工具 | 2026-05-26 |
| 🔄 **阶段二 (Day 6-17)** | 待开发 | 3D打印核心建模功能、对象创建/变换/修改、变形雕刻、文件导入导出、模型修复 | - |
| ⏳ **阶段三 (Day 18-22)** | 待开发 | 文件管理、状态同步、事件通知 | - |
| ⏳ **阶段四 (Day 23-26)** | 待开发 | 材质与渲染 | - |
| ⏳ **阶段五 (Day 27-30)** | 待开发 | 文档与优化、发布准备 | - |

---

## 文档

项目详细文档位于 `/workspace/document/` 目录：

- [需求文档](./document/需求文档.md) - 产品需求与功能说明
- [系统架构文档](./document/系统架构文档.md) - 技术架构与设计
- [开发计划](./document/开发计划.md) - 开发计划与进度追踪
- [阶段一详细设计](./document/阶段一详细设计.md) - 阶段一具体实现方案
- [API接口文档](./document/API接口文档.md) - MCP 工具接口说明
- [部署文档](./document/部署文档.md) - 部署指南

## 许可证

MIT License
