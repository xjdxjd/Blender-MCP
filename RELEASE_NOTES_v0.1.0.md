# Blender-MCP v0.1.0

**首个正式发布版本** 🏆  
发布日期: 2026-05-26

---

## 项目简介

Blender-mcp 是一个连接 Blender 3D 建模软件与 AI 助手（Trae SOLO、hermes-agent）的中间件，实现通过自然语言指令控制 Blender 进行 3D 创作的能力，重点支持 **3D 打印建模**需求。

---

## ✨ 新功能

### 阶段一：基础架构
- MCP 服务端与 Blender 插件通信
- WebSocket 长连接机制
- ping 工具（连接测试）
- YAML 配置文件系统

### 阶段二：3D 打印建模核心功能
- **对象操作**: create_object, transform_object, delete_object
- **网格修改**: 布尔运算（union/difference/intersect）、倒角、挤出、实体化
- **变形工具**: simple_deform（BEND/TWIST/TAPER/STRETCH）
- **雕刻工具**: mesh_sculpt（push/pull/smooth/inflate）支持对称雕刻
- **软选择**: soft_transform（KD-Tree + 5种衰减函数）
- **高级变形**: curve_deform, shrinkwrap, subdivide_mesh
- **文件导入导出**: STL/OBJ（支持 Blender 4.0/4.1/4.2+）
- **模型检查**: check_model（非流形、法线、壁厚检测）
- **模型修复**: repair_model（法线翻转、顶点合并、孔洞填充）
- **3D打印适配**: detect_overhangs, optimize_orientation, set_shrinkage_compensation, validate_printability
- **场景查询**: list_objects, get_scene_info

### 阶段三：文件管理与状态同步
- **项目管理**: save_project, open_project（支持备份和文件锁定检测）
- **状态管理**: StateManager（增量同步、版本号管理）
- **事件通知**: BlenderEventHandler（depsgraph_update/undo/redo/load/save）
- **性能优化**: CacheStrategy、LRU缓存、采样哈希

### 阶段四：材质与渲染
- **材质工具**: set_material, list_materials, delete_material
- **材质预设**: plastic, glossy_plastic, metal, chrome, glass, rubber, ceramic, wood
- **渲染引擎**: render_scene（支持 EEVEE 和 Cycles）
- **渲染配置**: 分辨率、采样数、降噪、输出格式（PNG/JPEG/TIFF/OpenEXR）
- **进度回调**: RenderProgressCallback

### 阶段五：文档与优化
- **批处理**: BatchOperationManager（支持失败回滚）
- **性能分析**: profile_tool 装饰器
- **发布构建**: ReleaseBuilder

---

## 📦 安装

### 1. 安装 MCP 服务
```bash
cd blender-mcp
pip install -r requirements.txt
python -m mcp_server.server
```

### 2. 安装 Blender 插件
1. 打开 Blender 4.2+
2. 编辑 → 偏好设置 → 插件 → 安装
3. 选择 `blender_plugin` 文件夹
4. 启用 "Blender MCP" 插件
5. 点击 "Connect" 连接

### 3. 配置 AI 助手
在 AI 助手的 MCP 配置文件中添加：
```json
{
  "mcpServers": {
    "blender": {
      "command": "python",
      "args": ["/path/to/blender-mcp/mcp_server/server.py"]
    }
  }
}
```

---

## 🔧 可用工具列表

| 工具 | 描述 |
|------|------|
| `ping` | 测试 Blender 连接 |
| `create_object` | 创建 3D 对象 |
| `transform_object` | 移动、旋转、缩放 |
| `delete_object` | 删除对象 |
| `modify_mesh` | 布尔运算、修改器 |
| `simple_deform` | 简单变形 |
| `mesh_sculpt` | 雕刻操作 |
| `soft_transform` | 软选择变换 |
| `curve_deform` | 曲线变形 |
| `shrinkwrap` | 收缩包裹 |
| `import_model` | 导入模型 |
| `export_model` | 导出模型 |
| `check_model` | 检查模型 |
| `repair_model` | 修复模型 |
| `set_material` | 设置材质 |
| `render_scene` | 渲染场景 |
| `save_project` | 保存项目 |
| `open_project` | 打开项目 |
| `list_objects` | 列出对象 |
| `get_scene_info` | 获取场景信息 |

---

## 📄 许可证

MIT License

---

## 🙏 感谢

- Blender Foundation
- Model Context Protocol (MCP)
- Trae SOLO / hermes-agent
