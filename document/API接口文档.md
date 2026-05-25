# Blender-mcp API 接口文档

> **文档版本**：v1.4
> **最后更新**：2026-05-25

---

## 目录

- [概述](#概述)
- [连接协议](#连接协议)
- [核心工具](#核心工具)
- [变形与雕刻工具](#变形与雕刻工具)
- [3D 打印工具](#3d-打印工具)
- [文件管理工具](#文件管理工具)
- [状态管理工具](#状态管理工具)
- [材质与渲染工具](#材质与渲染工具)
- [错误码](#错误码)
- [示例](#示例)

---

## 概述

Blender-mcp 通过 Model Context Protocol (MCP) 提供一组工具，用于通过 AI 助手控制 Blender。所有通信通过 WebSocket 进行。

### 基本格式

**请求格式：**
```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "method": "tools/call",
  "params": {
    "name": "tool_name",
    "arguments": {
      "param1": "value1",
      "param2": "value2"
    }
  }
}
```

**响应格式：**
```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "result": {
    "success": true,
    "data": { ... }
  }
}
```

---

## 连接协议

### WebSocket 连接

- **地址**：`ws://127.0.0.1:8765`
- **协议**：MCP over WebSocket

### 连接流程

1. 建立 WebSocket 连接
2. 交换 MCP 握手消息
3. 发送工具调用请求
4. 接收响应
5. 心跳保持连接

### 心跳机制

- 发送频率：每 10 秒
- 超时：30 秒无响应视为断开

---

## 核心工具

### 1. create_object - 创建对象

**描述**：在 Blender 场景中创建 3D 对象

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| type | string | 是 | - | 对象类型：`mesh`、`curve` |
| name | string | 否 | 自动生成 | 对象名称 |
| location | [number, number, number] | 否 | [0, 0, 0] | 对象位置 (X, Y, Z) |
| rotation | [number, number, number] | 否 | [0, 0, 0] | 对象旋转 (X, Y, Z) 角度 |
| scale | [number, number, number] | 否 | [1, 1, 1] | 对象缩放 |
| mesh_type | string | 否（type=mesh时） | cube | 网格类型：`cube`、`sphere`、`cylinder`、`plane`、`cone`、`torus` |

**返回值：**

```json
{
  "success": true,
  "object_id": "Cube_001",
  "name": "Cube",
  "type": "MESH",
  "location": [0.0, 0.0, 0.0],
  "rotation": [0.0, 0.0, 0.0],
  "scale": [1.0, 1.0, 1.0],
  "vertex_count": 8,
  "face_count": 6
}
```

**示例：**
```json
{
  "name": "create_object",
  "arguments": {
    "type": "mesh",
    "name": "MyCube",
    "mesh_type": "cube",
    "location": [0, 0, 0],
    "scale": [2, 2, 2]
  }
}
```

---

### 2. transform_object - 变换对象

**描述**：移动、旋转或缩放已存在的对象

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID 或名称 |
| location | [number, number, number] | 否 | 保持不变 | 新位置 |
| rotation | [number, number, number] | 否 | 保持不变 | 新旋转（角度） |
| scale | [number, number, number] | 否 | 保持不变 | 新缩放 |
| mode | string | 否 | absolute | 变换模式：`absolute`、`relative` |

**返回值：**

```json
{
  "success": true,
  "object_id": "Cube_001",
  "transform": {
    "location": [2.5, 0.0, 0.0],
    "rotation": [0.0, 45.0, 0.0],
    "scale": [1.0, 1.0, 1.0]
  }
}
```

---

### 3. modify_mesh - 修改网格

**描述**：对网格对象执行修改操作

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| operation | string | 是 | - | 操作类型 |
| target_object_id | string | 条件必需 | - | 布尔运算的目标对象 |
| parameters | object | 否 | {} | 操作参数 |

**操作类型详解：**

#### 3.1 布尔运算

| operation | 参数 | 描述 |
|-----------|------|------|
| boolean_union | target_object_id | 并集 |
| boolean_difference | target_object_id | 差集 |
| boolean_intersect | target_object_id | 交集 |

#### 3.2 其他操作

| operation | 参数 | 描述 |
|-----------|------|------|
| bevel | width, segments | 倒角 |
| extrude | distance, direction | 挤出 |
| solidify | thickness | 实体化 |

**返回值：**

```json
{
  "success": true,
  "object_id": "Cube_001",
  "operation": "boolean_union",
  "result": {
    "vertex_count": 1248,
    "face_count": 832,
    "non_manifold_edges": 0
  }
}
```

---

### 4. delete_object - 删除对象

**描述**：删除场景中的对象

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| confirm | boolean | 否 | false | 确认删除（防止误操作） |

**返回值：**

```json
{
  "success": true,
  "deleted_object_id": "Cube_001",
  "remaining_objects": 5
}
```

---

## 变形与雕刻工具

### 4.1 simple_deform - 简易变形

**描述**：对网格对象执行简易变形操作（弯曲、锥化、扭曲、拉伸）

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| operation | string | 是 | - | 变形类型：`bend`、`taper`、`twist`、`stretch` |
| angle | number | 否 | 0.0 | 变形角度（度），bend/twist 时有效 |
| factor | number | 否 | 0.0 | 变形因子，taper/stretch 时有效 |
| axis | string | 否 | "Z" | 变形轴：`X`、`Y`、`Z` |
| origin | [number, number, number] | 否 | [0, 0, 0] | 变形原点 |
| limits | [number, number] | 否 | [0.0, 1.0] | 变形限制范围（0.0-1.0） |

**操作类型详解：**

| operation | 主要参数 | 描述 |
|-----------|---------|------|
| bend | angle, axis | 沿指定轴弯曲，angle 控制弯曲角度 |
| taper | factor, axis | 沿指定轴锥化，factor 控制锥化程度 |
| twist | angle, axis | 沿指定轴扭曲，angle 控制扭曲角度 |
| stretch | factor, axis | 沿指定轴拉伸，factor 控制拉伸比例 |

**返回值：**

```json
{
  "success": true,
  "object_id": "Cylinder_001",
  "operation": "bend",
  "result": {
    "vertex_count": 1024,
    "face_count": 512,
    "bounds": {
      "min": [-2.5, -1.0, 0.0],
      "max": [2.5, 1.0, 3.0]
    }
  }
}
```

**示例：**
```json
{
  "name": "simple_deform",
  "arguments": {
    "object_id": "Cylinder_001",
    "operation": "bend",
    "angle": 90.0,
    "axis": "Z"
  }
}
```

---

### 4.2 mesh_sculpt - 网格雕刻

**描述**：对网格对象执行雕刻操作（推、拉、平滑、膨胀等）

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| operation | string | 是 | - | 雕刻操作：`push`、`pull`、`smooth`、`inflate`、`flatten`、`pinch` |
| center | [number, number, number] | 是 | - | 雕刻中心点（世界坐标） |
| radius | number | 否 | 0.5 | 雕刻影响半径 |
| strength | number | 否 | 0.5 | 雕刻强度（0.0-1.0） |
| direction | [number, number, number] | 否 | 法线方向 | 雕刻方向，默认沿法线 |
| symmetry | string | 否 | "none" | 对称模式：`none`、`x`、`y`、`z` |
| iterations | number | 否 | 1 | 雕刻迭代次数 |

**操作类型详解：**

| operation | 描述 |
|-----------|------|
| push | 沿方向将顶点向外推 |
| pull | 沿方向将顶点向内拉 |
| smooth | 平滑顶点位置 |
| inflate | 沿法线方向膨胀 |
| flatten | 将顶点压平到平均平面 |
| pinch | 将顶点向中心聚拢 |

**返回值：**

```json
{
  "success": true,
  "object_id": "Sphere_001",
  "operation": "inflate",
  "affected_vertices": 256,
  "result": {
    "vertex_count": 2048,
    "face_count": 1024
  }
}
```

**示例：**
```json
{
  "name": "mesh_sculpt",
  "arguments": {
    "object_id": "Sphere_001",
    "operation": "inflate",
    "center": [0, 0, 1.0],
    "radius": 0.3,
    "strength": 0.8,
    "symmetry": "x"
  }
}
```

---

### 4.3 soft_transform - 软选择变形

**描述**：使用软选择对网格对象进行移动、旋转或缩放变形

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| selection_center | [number, number, number] | 是 | - | 选择中心点（世界坐标） |
| selection_radius | number | 否 | 1.0 | 软选择影响半径 |
| falloff_type | string | 否 | "smooth" | 衰减类型：`smooth`、`sphere`、`root`、`sharp`、`linear`、`constant` |
| transform_type | string | 是 | - | 变换类型：`translate`、`rotate`、`scale` |
| translation | [number, number, number] | 条件必需 | [0, 0, 0] | 移动偏移量（transform_type=translate时） |
| rotation | [number, number, number] | 条件必需 | [0, 0, 0] | 旋转角度（transform_type=rotate时） |
| scale | [number, number, number] | 条件必需 | [1, 1, 1] | 缩放比例（transform_type=scale时） |

**衰减类型详解：**

| falloff_type | 描述 |
|-------------|------|
| smooth | 平滑衰减（默认） |
| sphere | 球形衰减 |
| root | 根号衰减 |
| sharp | 锐利衰减 |
| linear | 线性衰减 |
| constant | 常量（无衰减） |

**返回值：**

```json
{
  "success": true,
  "object_id": "Cube_001",
  "transform_type": "translate",
  "affected_vertices": 128,
  "max_displacement": 0.95
}
```

**示例：**
```json
{
  "name": "soft_transform",
  "arguments": {
    "object_id": "Cube_001",
    "selection_center": [0, 0, 1.0],
    "selection_radius": 1.5,
    "falloff_type": "smooth",
    "transform_type": "translate",
    "translation": [0, 0, 0.5]
  }
}
```

---

### 4.4 curve_deform - 曲线变形

**描述**：沿曲线对网格对象进行变形

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 要变形的对象 ID |
| curve_id | string | 是 | - | 用作变形路径的曲线对象 ID |
| axis | string | 否 | "Z" | 变形轴：`X`、`Y`、`Z` |

**返回值：**

```json
{
  "success": true,
  "object_id": "Cylinder_001",
  "curve_id": "BezierCurve_001",
  "axis": "Z",
  "result": {
    "vertex_count": 1024,
    "face_count": 512
  }
}
```

**示例：**
```json
{
  "name": "curve_deform",
  "arguments": {
    "object_id": "Cylinder_001",
    "curve_id": "BezierCurve_001",
    "axis": "Z"
  }
}
```

---

### 4.5 subdivide_mesh - 网格细分

**描述**：对网格对象进行细分，增加顶点密度

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| levels | number | 否 | 1 | 细分层级（1-5） |
| smoothness | number | 否 | 1.0 | 平滑度（0.0-1.0） |
| boundary | string | 否 | "preserve" | 边界处理：`preserve`、`smooth`、`sharp` |

**返回值：**

```json
{
  "success": true,
  "object_id": "Cube_001",
  "levels": 2,
  "result": {
    "vertex_count": 258,
    "face_count": 256,
    "original_vertex_count": 8,
    "original_face_count": 6
  }
}
```

**示例：**
```json
{
  "name": "subdivide_mesh",
  "arguments": {
    "object_id": "Cube_001",
    "levels": 2,
    "smoothness": 0.5,
    "boundary": "preserve"
  }
}
```

---

### 4.6 shrinkwrap - 投射变形

**描述**：将网格对象投射到目标对象表面进行变形

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 要变形的对象 ID |
| target_id | string | 是 | - | 目标对象 ID（投射目标） |
| mode | string | 否 | "nearest_surface" | 投射模式：`nearest_surface`、`projection` |
| offset | number | 否 | 0.0 | 投射偏移距离 |
| substeps | number | 否 | 1 | 投射子步数（提高精度） |

**投射模式详解：**

| mode | 描述 |
|------|------|
| nearest_surface | 最近表面投射，将顶点移到目标表面最近点 |
| projection | 投影投射，沿指定方向将顶点投影到目标表面 |

**返回值：**

```json
{
  "success": true,
  "object_id": "Plane_001",
  "target_id": "Sphere_001",
  "mode": "nearest_surface",
  "result": {
    "vertex_count": 1024,
    "face_count": 512,
    "max_deviation": 0.02
  }
}
```

**示例：**
```json
{
  "name": "shrinkwrap",
  "arguments": {
    "object_id": "Plane_001",
    "target_id": "Sphere_001",
    "mode": "nearest_surface",
    "offset": 0.05
  }
}
```

---

## 3D 打印工具

### 5. import_model - 导入模型

**描述**：导入 3D 模型文件

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| filepath | string | 是 | - | 文件路径 |
| format | string | 否 | 自动检测 | 文件格式：`stl`、`obj` |
| import_options | object | 否 | {} | 导入选项 |

**导入选项：**

```json
{
  "scale": 1.0,
  "merge_vertices": false,
  "calc_normals": true
}
```

**返回值：**

```json
{
  "success": true,
  "object_id": "model_001",
  "name": "imported_model",
  "format": "stl",
  "vertex_count": 50000,
  "face_count": 100000,
  "bounds": {
    "min": [-5.0, -3.0, 0.0],
    "max": [5.0, 3.0, 10.0]
  }
}
```

---

### 6. export_model - 导出模型

**描述**：导出模型为 3D 打印格式

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 否 | 全部对象 | 对象 ID，null 表示导出全部 |
| filepath | string | 是 | - | 导出文件路径 |
| format | string | 是 | - | 格式：`stl`、`obj` |
| options | object | 否 | {} | 导出选项 |

**导出选项：**

```json
{
  "scale": 1.0,
  "use_selection": false,
  "ascii": false,
  "apply_modifiers": true
}
```

**返回值：**

```json
{
  "success": true,
  "filepath": "/path/to/export.stl",
  "format": "stl",
  "file_size": 1048576,
  "vertex_count": 50000,
  "face_count": 100000
}
```

---

### 7. check_model - 检查模型

**描述**：检查模型是否适合 3D 打印

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| checks | string[] | 否 | 全部检查 | 检查项数组 |
| min_thickness | number | 否 | 0.5 | 最小壁厚（mm） |

**检查项：**

- `non_manifold` - 非流形几何体
- `normals` - 法线方向
- `thickness` - 壁厚检查
- `intersections` - 自相交

**返回值：**

```json
{
  "success": true,
  "object_id": "model_001",
  "is_printable": false,
  "checks": [
    {
      "check": "non_manifold",
      "passed": true,
      "count": 0,
      "details": null
    },
    {
      "check": "normals",
      "passed": false,
      "count": 15,
      "details": "Found 15 faces with inverted normals"
    },
    {
      "check": "thickness",
      "passed": false,
      "count": 3,
      "details": "3 regions below minimum thickness of 0.5mm"
    }
  ],
  "summary": "Model has 2 issues that need to be fixed"
}
```

---

### 8. repair_model - 修复模型

**描述**：自动修复模型问题

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| fixes | string[] | 否 | 全部修复 | 修复项数组 |
| preserve_geometry | boolean | 否 | true | 尽量保留几何体 |

**修复项：**

- `normals` - 修复法线方向
- `vertices` - 合并重叠顶点
- `holes` - 填充孔洞
- `degenerates` - 移除退化面

**返回值：**

```json
{
  "success": true,
  "object_id": "model_001",
  "fixes_applied": ["normals", "vertices"],
  "changes": {
    "normals_fixed": 15,
    "vertices_merged": 128,
    "faces_removed": 3
  },
  "remaining_issues": 1,
  "is_printable": true
}
```

---

### 9. detect_overhangs - 检测悬垂面

**描述**：检测模型中需要支撑的悬垂面

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| angle_threshold | number | 否 | 45 | 悬垂角度阈值（度） |

**返回值：**

```json
{
  "success": true,
  "object_id": "model_001",
  "total_faces": 100000,
  "overhang_faces": 15000,
  "overhang_percentage": 15.0,
  "overhang_regions": [
    {
      "area": 2500,
      "angle": 52.3,
      "position": [0.0, 0.0, 5.0]
    }
  ],
  "requires_support": true
}
```

---

### 10. optimize_orientation - 优化打印方向

**描述**：计算最优打印方向

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| optimize_for | string | 否 | auto | 优化目标：`auto`、`strength`、`surface`、`speed` |

**返回值：**

```json
{
  "success": true,
  "object_id": "model_001",
  "recommended_orientation": {
    "rotation": [0.0, 0.0, 45.0],
    "degrees": {
      "x": 0.0,
      "y": 0.0,
      "z": 45.0
    }
  },
  "estimated_metrics": {
    "support_required": 12.5,
    "surface_quality": 85,
    "build_time": 120,
    "strength": 90
  }
}
```

---

### 11. set_shrinkage_compensation - 收缩补偿

**描述**：设置材料收缩补偿参数

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| material | string | 否 | PLA | 材料类型 |
| compensation | object | 否 | - | 自定义补偿值 |

**材料预设：**

| 材料 | 收缩率 |
|------|--------|
| PLA | 0.2% |
| ABS | 0.5% |
| PETG | 0.3% |
| TPU | 0.3% |
| Nylon | 0.4% |

**返回值：**

```json
{
  "success": true,
  "object_id": "model_001",
  "compensation": {
    "material": "PLA",
    "x": 1.002,
    "y": 1.002,
    "z": 1.002,
    "method": "uniform"
  },
  "original_dimensions": [100.0, 100.0, 50.0],
  "compensated_dimensions": [100.2, 100.2, 50.1]
}
```

---

## 文件管理工具

### 12. save_project - 保存项目

**描述**：保存 Blender 项目文件

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| filepath | string | 是 | - | 保存路径 |
| compress | boolean | 否 | true | 压缩文件 |
| backup | boolean | 否 | true | 创建备份 |

**返回值：**

```json
{
  "success": true,
  "filepath": "/path/to/project.blend",
  "file_size": 5242880,
  "backup_created": true,
  "backup_path": "/path/to/project.blend.bak"
}
```

---

### 13. open_project - 打开项目

**描述**：打开 Blender 项目文件

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| filepath | string | 是 | - | 文件路径 |
| load_ui | boolean | 否 | true | 加载 UI 设置 |

**返回值：**

```json
{
  "success": true,
  "filepath": "/path/to/project.blend",
  "loaded_objects": 15,
  "scene_name": "MainScene"
}
```

---

## 状态管理工具

### 14. list_objects - 列出对象

**描述**：获取场景中所有对象的列表

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| filter_type | string | 否 | all | 过滤类型：`all`、`mesh`、`curve`、`light`、`camera` |

**返回值：**

```json
{
  "success": true,
  "objects": [
    {
      "object_id": "Cube",
      "name": "Cube",
      "type": "MESH",
      "location": [0.0, 0.0, 0.0],
      "visible": true,
      "locked": false
    },
    {
      "object_id": "Light",
      "name": "Light",
      "type": "LIGHT",
      "location": [5.0, 5.0, 10.0],
      "visible": true,
      "locked": false
    }
  ],
  "total_count": 2
}
```

---

### 15. get_scene_info - 获取场景信息

**描述**：获取当前场景的详细信息

**返回值：**

```json
{
  "success": true,
  "scene": {
    "name": "MainScene",
    "frame_current": 1,
    "frame_start": 1,
    "frame_end": 250
  },
  "statistics": {
    "total_objects": 15,
    "meshes": 10,
    "curves": 2,
    "lights": 2,
    "cameras": 1,
    "total_vertices": 500000,
    "total_faces": 250000
  },
  "render_settings": {
    "engine": "CYCLES",
    "resolution_x": 1920,
    "resolution_y": 1080
  }
}
```

---

## 材质与渲染工具

### 16. set_material - 设置材质

**描述**：为对象设置材质

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| object_id | string | 是 | - | 对象 ID |
| material_name | string | 否 | 自动生成 | 材质名称 |
| properties | object | 否 | - | 材质属性 |

**材质属性：**

```json
{
  "base_color": [1.0, 0.8, 0.6, 1.0],
  "metallic": 0.0,
  "roughness": 0.5,
  "specular": 0.5,
  "transmission": 0.0
}
```

**返回值：**

```json
{
  "success": true,
  "object_id": "Cube_001",
  "material_id": "Material_001",
  "material_name": "MyMaterial",
  "properties_applied": {
    "base_color": [1.0, 0.8, 0.6, 1.0],
    "metallic": 0.0,
    "roughness": 0.5
  }
}
```

---

### 17. render_scene - 渲染场景

**描述**：渲染当前场景

**参数：**

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| output_path | string | 否 | 临时目录 | 输出路径 |
| resolution | [number, number] | 否 | [1920, 1080] | 分辨率 |
| engine | string | 否 | CYCLES | 渲染引擎 |

**返回值：**

```json
{
  "success": true,
  "output_path": "/path/to/render.png",
  "resolution": [1920, 1080],
  "render_time": 125.5,
  "file_size": 2097152
}
```

---

## 错误码

| 错误码 | 名称 | 描述 |
|--------|------|------|
| 1001 | OBJECT_NOT_FOUND | 指定的对象不存在 |
| 1002 | INVALID_PARAMETER | 参数无效或缺失 |
| 1003 | OPERATION_NOT_ALLOWED | 操作不被允许 |
| 1004 | FILE_NOT_FOUND | 文件不存在 |
| 1005 | PERMISSION_DENIED | 权限不足 |
| 1006 | CONNECTION_ERROR | 连接错误 |
| 1007 | TIMEOUT | 操作超时 |
| 1008 | RESOURCE_EXHAUSTED | 资源耗尽 |
| 1009 | UNSUPPORTED_FORMAT | 不支持的格式 |
| 1010 | OPERATION_FAILED | 操作失败 |
| 1011 | RATE_LIMITED | 速率限制 |
| 1012 | MESSAGE_TOO_LARGE | 消息过大 |

**错误响应格式：**

```json
{
  "success": false,
  "error": {
    "code": 1001,
    "name": "OBJECT_NOT_FOUND",
    "message": "Object 'NonExistent' not found in scene",
    "details": {
      "requested_id": "NonExistent",
      "available_objects": ["Cube", "Sphere", "Light"]
    }
  }
}
```

---

## 示例

### 示例 1：创建并导出立方体

```javascript
// 1. 创建立方体
const createResult = await mcp.call({
  name: "create_object",
  arguments: {
    type: "mesh",
    name: "ExportCube",
    mesh_type: "cube",
    location: [0, 0, 0],
    scale: [1, 1, 1]
  }
});

// 2. 导出为 STL
const exportResult = await mcp.call({
  name: "export_model",
  arguments: {
    object_id: createResult.object_id,
    filepath: "/tmp/my_cube.stl",
    format: "stl",
    options: {
      ascii: false
    }
  }
});

console.log("Exported to:", exportResult.filepath);
```

### 示例 2：导入、检查并修复模型

```javascript
// 1. 导入模型
const importResult = await mcp.call({
  name: "import_model",
  arguments: {
    filepath: "/tmp/imported_model.stl"
  }
});

// 2. 检查模型
const checkResult = await mcp.call({
  name: "check_model",
  arguments: {
    object_id: importResult.object_id,
    checks: ["non_manifold", "normals", "thickness"],
    min_thickness: 0.5
  }
});

// 3. 如果有问题，修复模型
if (!checkResult.is_printable) {
  const repairResult = await mcp.call({
    name: "repair_model",
    arguments: {
      object_id: importResult.object_id,
      fixes: ["normals", "vertices"],
      preserve_geometry: true
    }
  });
  console.log("Model repaired:", repairResult);
}
```

### 示例 3：3D 打印优化工作流

```javascript
// 1. 导入模型
const model = await mcp.call({
  name: "import_model",
  arguments: {
    filepath: "/tmp/complex_model.stl"
  }
});

// 2. 检测悬垂面
const overhangs = await mcp.call({
  name: "detect_overhangs",
  arguments: {
    object_id: model.object_id,
    angle_threshold: 45
  }
});

// 3. 优化打印方向
const orientation = await mcp.call({
  name: "optimize_orientation",
  arguments: {
    object_id: model.object_id,
    optimize_for: "surface"
  }
});

// 4. 应用优化方向
await mcp.call({
  name: "transform_object",
  arguments: {
    object_id: model.object_id,
    rotation: orientation.recommended_orientation.rotation
  }
});

// 5. 设置材料收缩补偿
await mcp.call({
  name: "set_shrinkage_compensation",
  arguments: {
    object_id: model.object_id,
    material: "PLA"
  }
});

// 6. 导出用于打印
const exportResult = await mcp.call({
  name: "export_model",
  arguments: {
    object_id: model.object_id,
    filepath: "/tmp/print_ready_model.stl",
    format: "stl",
    options: {
      scale: 1.0,
      apply_modifiers: true
    }
  }
});
```

### 示例 4：使用变形与雕刻工具创建"包子小人"

```javascript
// 1. 创建球体作为包子身体
const body = await mcp.call({
  name: "create_object",
  arguments: {
    type: "mesh",
    name: "BunBody",
    mesh_type: "sphere",
    location: [0, 0, 1.0],
    scale: [1.0, 1.0, 0.8]
  }
});

// 2. 锥化变形让底部收窄，更像包子形状
await mcp.call({
  name: "simple_deform",
  arguments: {
    object_id: body.object_id,
    operation: "taper",
    factor: 0.3,
    axis: "Z"
  }
});

// 3. 膨胀雕刻让顶部更饱满
await mcp.call({
  name: "mesh_sculpt",
  arguments: {
    object_id: body.object_id,
    operation: "inflate",
    center: [0, 0, 1.8],
    radius: 0.6,
    strength: 0.7
  }
});

// 4. 细分增加顶点密度，便于后续雕刻
await mcp.call({
  name: "subdivide_mesh",
  arguments: {
    object_id: body.object_id,
    levels: 2,
    smoothness: 0.5
  }
});

// 5. 创建小球体作为眼睛
const leftEye = await mcp.call({
  name: "create_object",
  arguments: {
    type: "mesh",
    name: "LeftEye",
    mesh_type: "sphere",
    location: [-0.25, 0.8, 1.2],
    scale: [0.12, 0.12, 0.12]
  }
});

const rightEye = await mcp.call({
  name: "create_object",
  arguments: {
    type: "mesh",
    name: "RightEye",
    mesh_type: "sphere",
    location: [0.25, 0.8, 1.2],
    scale: [0.12, 0.12, 0.12]
  }
});

// 6. 推雕刻让眼睛形成星星眼效果
await mcp.call({
  name: "mesh_sculpt",
  arguments: {
    object_id: leftEye.object_id,
    operation: "push",
    center: [-0.25, 0.92, 1.2],
    radius: 0.08,
    strength: 0.6
  }
});

await mcp.call({
  name: "mesh_sculpt",
  arguments: {
    object_id: rightEye.object_id,
    operation: "push",
    center: [0.25, 0.92, 1.2],
    radius: 0.08,
    strength: 0.6
  }
});

// 7. 创建圆柱体作为笼屉
const steamer = await mcp.call({
  name: "create_object",
  arguments: {
    type: "mesh",
    name: "Steamer",
    mesh_type: "cylinder",
    location: [0, 0, 0.15],
    scale: [1.2, 1.2, 0.3]
  }
});

// 8. 弯曲变形添加笼屉边缘弧度
await mcp.call({
  name: "simple_deform",
  arguments: {
    object_id: steamer.object_id,
    operation: "bend",
    angle: 5.0,
    axis: "Z"
  }
});

// 9. 软选择变形调整包子坐姿
await mcp.call({
  name: "soft_transform",
  arguments: {
    object_id: body.object_id,
    selection_center: [0, 0, 0.5],
    selection_radius: 0.8,
    falloff_type: "smooth",
    transform_type: "scale",
    scale: [1.1, 1.1, 0.9]
  }
});

// 10. 平滑雕刻让整体过渡自然
await mcp.call({
  name: "mesh_sculpt",
  arguments: {
    object_id: body.object_id,
    operation: "smooth",
    center: [0, 0, 1.0],
    radius: 1.5,
    strength: 0.3,
    iterations: 3
  }
});

// 11. 检查模型可打印性
const checkResult = await mcp.call({
  name: "check_model",
  arguments: {
    object_id: body.object_id,
    checks: ["non_manifold", "normals", "thickness"],
    min_thickness: 0.5
  }
});

// 12. 导出模型
const exportResult = await mcp.call({
  name: "export_model",
  arguments: {
    object_id: null,
    filepath: "/tmp/bun_character.stl",
    format: "stl",
    options: {
      scale: 1.0,
      apply_modifiers: true
    }
  }
});

console.log("包子小人已导出至:", exportResult.filepath);
```

---

> 📎 **关联文档**：
> - [系统架构文档](./系统架构文档.md)
> - [需求文档](./需求文档.md)
> - [开发计划](./开发计划.md)
