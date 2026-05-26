# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-26

### Added

#### 阶段二核心功能
- **soft_transform 工具**：实现 KD-Tree 软选择变形，支持 5 种衰减函数（LINEAR/INVERSE/CONSTANT/GAUSSIAN/ROOT）和 3 种变换类型（TRANSLATE/ROTATE/SCALE）
- **curve_deform 工具**：基于 Curve 修改器的曲线变形功能
- **shrinkwrap 工具**：基于 Shrinkwrap 修改器的收缩包裹功能

#### 阶段三核心功能
- **事件通知系统**（`core/events.py`）：
  - EventBus 事件总线，支持多监听器订阅同一事件
  - EventThrottle 事件节流器，支持节流和防抖策略
  - BlenderEventHandlers，与 Blender app.handlers 集成
  - 10+ 种事件类型（OBJECT_ADDED/REMOVED/MODIFIED/SCENE_CHANGED 等）

- **性能优化**（`core/state.py`）：
  - LRU 缓存策略（CacheStrategy）
  - 采样哈希计算（默认 10% 顶点采样）
  - 0.5秒 TTL 缓存有效期
  - struct 浮点数打包优化哈希计算

- **StateManager 增强**：
  - 对象级网格哈希计算和对比
  - 增量变更检测
  - 版本号管理和变更日志

#### 项目文件
- `core/events.py`：完整的事件通知系统实现
- 更新 `core/__init__.py`：导出新增的事件系统模块

### Changed

- 更新 `core/adapter.py`：新增 soft_transform、curve_deform、shrinkwrap 方法
- 更新 `core/state.py`：新增性能优化、缓存策略、采样哈希
- 更新 `PROGRESS.md`：版本升级到 v2.0，阶段二和三标记为完成
- 更新 `开发计划.md`：版本升级到 v1.5，阶段二和三任务标记为完成

## [0.1.0] - 2026-05-26

### Added

- 需求文档（BRD-001 v1.5）：定义产品概述、核心功能、用户场景、验收标准、3D 打印参数适配、安全性威胁模型、数据验证规则、状态一致性保证和需求追踪矩阵
- 系统架构文档（SAD-001 v1.4）：定义系统架构设计、技术选型、模块划分、MCP 工具定义、通信协议、数据模型、部署方案、安全性设计、错误处理策略、日志监控策略、配置管理、API 适配器详细设计、WebSocket 连接协议、MCP 工具注册机制、性能优化方案、扩展性设计、优雅降级策略和事务性操作设计
- 开发计划（DP-001 v1.4）：定义五阶段开发计划（基础架构→3D 打印建模→文件管理与状态同步→材质与渲染→文档与优化），包含里程碑甘特图、测试策略、异常测试场景、压力测试、操作恢复机制、开发环境要求、代码规范和 CI/CD 流水线
- API 接口文档（v1.4）：定义所有 MCP 工具的接口规范，包括核心工具（create_object、transform_object、modify_mesh、delete_object）、变形与雕刻工具（simple_deform、mesh_sculpt、soft_transform、curve_deform、subdivide_mesh、shrinkwrap）、3D 打印工具（import_model、export_model、check_model、repair_model、detect_overhangs、optimize_orientation、set_shrinkage_compensation）、文件管理工具（save_project、open_project）、状态管理工具（list_objects、get_scene_info）和材质与渲染工具（set_material、render_scene）
- 阶段三详细设计文档（DD-003 v1.0）：save_project 工具设计（bpy.ops.wm.save_as_mainfile 调用、备份策略、压缩选项、路径安全校验）、open_project 工具设计（未保存变更处理、文件锁定检测、场景加载后状态重置）、StateManager 状态管理器设计（场景状态快照、增量同步算法、状态版本号管理）、事件通知系统设计（app.handlers 集成、事件类型定义、事件节流防抖）和性能优化设计（增量 vs 全量同步策略、缓存策略）
- 阶段四详细设计文档（DD-004 v1.0）：set_material 工具设计（Principled BSDF 材质创建、材质属性映射、材质分配、材质库管理）、render_scene 工具设计（渲染引擎选择、渲染参数配置、无头模式渲染、渲染进度回调）
- 阶段五详细设计文档（DD-005 v1.0）：文档编写计划（README、用户手册、安装指南、配置指南、3D 打印最佳实践）、代码优化方案（性能瓶颈识别、缓存/批处理/异步优化模式、代码重构检查清单）、最终测试计划（全量回归测试、跨平台测试矩阵、性能基准测试、UAT 方案）和发布准备（版本号策略、构建脚本设计、发布检查清单）
