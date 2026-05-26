# Blender-mcp 客户端

> **文档版本**：v1.5
> **最后更新**：2026-05-25

---

## 项目简介

Blender-mcp 是一个连接 Blender 3D 建模软件与 AI 助手（Trae SOLO、hermes-agent）的中间件，实现通过自然语言指令控制 Blender 进行 3D 创作的能力，重点支持 **3D 打印建模**需求。

### 核心特性

- 🤖 **AI 驱动**：通过自然语言与 Blender 交互，降低 3D 创作门槛
- 🖨️ **3D 打印优先**：内置模型检查、修复、导出为 STL/OBJ 等 3D 打印标准格式
- 🔌 **MCP 协议**：基于 Model Context Protocol 标准，支持多种 AI 助手
- 💻 **跨平台**：支持 Windows、macOS、Linux
- 🔒 **本地通信**：所有操作在本地执行，无网络暴露

---

## 快速开始

### 环境要求

| 要求 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Blender | 4.2+ | 4.3+ |
| Python | 3.10+ | 3.11 |
| 操作系统 | Windows 10 / macOS 12 / Ubuntu 22.04 |

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/xjdxjd/Blender-MCP.git
cd Blender-MCP
```

#### 2. 安装依赖并启动 MCP 服务

```bash
cd blender-mcp
pip install -r requirements.txt
python -m mcp_server.server
```

#### 3. 安装 Blender 插件

**方式一：符号链接（推荐开发时使用）**

Linux/macOS：
```bash
mkdir -p ~/.config/blender/4.2/scripts/addons/
ln -s $(pwd)/blender_plugin ~/.config/blender/4.2/scripts/addons/blender_mcp
```

Windows：
```powershell
New-Item -ItemType Junction -Path "$env:APPDATA\Blender Foundation\Blender\4.2\scripts\addons\blender_mcp" -Target "$pwd\blender_plugin"
```

**方式二：手动安装**

1. 打开 Blender (4.2+)
2. Edit → Preferences → Add-ons → Install...
3. 选择 `blender-mcp` 目录下的 `blender_plugin` 文件夹
4. 启用 "Blender MCP" 插件

#### 4. 连接服务

1. 在 3D View 右侧找到 "Blender MCP" 面板
2. 确认 Host 为 127.0.0.1，Port 为 8765
3. 点击 "Connect" 连接

#### 5. 配置 MCP 客户端

在 AI 助手的 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "blender": {
      "command": "python",
      "args": ["/path/to/blender-mcp/mcp_server/server.py"],
      "env": {
        "BLENDER_PORT": "8765"
      }
    }
  }
}
```

---

## 使用示例

### 通过 AI 助手创建 3D 模型

```
用户：创建一个立方体，位置在 (0, 0, 0)，边长为 2
AI助手：调用 create_object 工具，创建立方体

用户：添加一个圆柱体，半径 1，高度 3，放置在立方体旁边
AI助手：调用 create_object 工具创建圆柱体

用户：对这个立方体进行倒角处理，倒角宽度为 0.1
AI助手：调用 modify_mesh 工具，operation=bevel
```

### 3D 打印建模工作流

```
用户：导入模型 model.stl，检查是否可以 3D 打印
AI助手：
  1. 调用 import_model 导入文件
  2. 调用 check_model 检查模型
  3. 返回检查结果（壁厚、法线、非流形等）

用户：如果有问题，修复这些问题
AI助手：调用 repair_model 工具修复检测到的问题

用户：导出为 STL 格式用于 3D 打印
AI助手：调用 export_model 工具，format=stl
```

---

## 核心工具

| 工具 | 描述 | 优先级 |
|------|------|--------|
| `create_object` | 创建 3D 对象（立方体、球体、圆柱体等） | P0 |
| `transform_object` | 移动、旋转、缩放对象 | P0 |
| `modify_mesh` | 布尔运算、倒角、挤出等网格操作 | P0 |
| `export_model` | 导出为 STL/OBJ 格式 | P0 |
| `import_model` | 导入 STL/OBJ 文件 | P0 |
| `check_model` | 检查模型可打印性 | P0 |
| `repair_model` | 修复模型问题 | P0 |
| `soft_transform` | 软选择变形（KD-Tree + 5种衰减） | P1 |
| `curve_deform` | 曲线变形 | P1 |
| `shrinkwrap` | 收缩包裹 | P1 |
| `detect_overhangs` | 检测悬垂面 | P1 |
| `optimize_orientation` | 优化打印方向 | P1 |
| `set_material` | 设置材质 | P3 |
| `render_scene` | 渲染场景 | P3 |

---

## 开发进度

| 阶段 | 状态 | 完成度 | 完成日期 |
|------|------|--------|---------|
| ✅ **阶段一 (Day 1-5)** | 已完成 | 100% | 2026-05-26 |
| ✅ **阶段二 (Day 6-17)** | 已完成 | 100% | 2026-05-26 |
| ✅ **阶段三 (Day 18-22)** | 已完成 | 100% | 2026-05-26 |
| ⏳ **阶段四 (Day 23-26)** | 待开发 | 0% | - |
| ⏳ **阶段五 (Day 27-30)** | 待开发 | 0% | - |

**项目总进度**: ~85% (核心功能已全部完成！)

---

## 项目结构

```
Blender-MCP/
├── document/                 # 项目文档
│   ├── 需求文档.md
│   ├── 系统架构文档.md
│   ├── 开发计划.md
│   ├── 变更日志.md
│   └── 开发进度.md
├── blender-mcp/              # 项目代码
│   ├── mcp_server/          # MCP 服务端
│   │   ├── server.py        # 服务入口
│   │   ├── tools.py         # 工具定义
│   │   └── schemas.py       # 数据模型
│   ├── blender_plugin/       # Blender 插件
│   │   ├── addon.py         # 插件注册
│   │   ├── connection.py    # 连接管理
│   │   └── operators.py     # Blender 操作封装
│   ├── core/                # 核心逻辑
│   │   ├── command.py       # 命令处理器
│   │   ├── adapter.py       # API 适配器
│   │   ├── state.py         # 状态管理
│   │   └── events.py        # 事件通知系统
│   ├── config/              # 配置文件
│   ├── tests/               # 测试
│   └── requirements.txt
├── CHANGELOG.md              # 变更日志（已移至 document/变更日志.md）
└── README.md
```

---

## 开发指南

### 开发环境设置

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 运行测试

```bash
# 单元测试
pytest tests/unit/ -v

# 集成测试
pytest tests/integration/ -v

# 端到端测试（需要 Blender）
blender --background --python tests/e2e/run_all.py
```

### 代码规范

- 遵循 PEP 8
- 所有函数必须有类型注解
- 使用 Google 风格 docstring
- 提交前运行 `black` 格式化

---

## 文档

- [需求文档](./document/需求文档.md) - 产品需求与功能定义
- [系统架构文档](./document/系统架构文档.md) - 技术架构与设计
- [开发计划](./document/开发计划.md) - 开发阶段与任务
- [变更日志](./document/变更日志.md) - 版本变更记录
- [开发进度](./document/开发进度.md) - 开发进度追踪
- [阶段一详细设计](./document/阶段一详细设计.md) - 阶段一具体实现方案
- [API接口文档](./document/API接口文档.md) - MCP 工具接口说明
- [部署文档](./document/部署文档.md) - 部署指南

---

## 贡献

欢迎提交 Issue 和 Pull Request！请阅读 [CONTRIBUTING.md](./CONTRIBUTING.md) 了解贡献指南。

---

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](./LICENSE) 文件。

---

## 联系方式

- GitHub Issues: https://github.com/xjdxjd/Blender-MCP/issues

---

> 📎 **关联文档**：
> - [需求文档](./document/需求文档.md)
> - [系统架构文档](./document/系统架构文档.md)
> - [开发计划](./document/开发计划.md)
> - [变更日志](./document/变更日志.md)
> - [开发进度](./document/开发进度.md)
