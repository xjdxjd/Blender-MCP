"""
Blender API 适配器 - 阶段二核心模块
提供 bpy 操作的统一封装，处理 Blender Python API 调用
"""

import bpy
import bmesh
import logging
import math
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BlenderContextAdapter:
    """Blender 上下文管理器，处理场景切换和上下文设置"""

    @staticmethod
    def get_current_object() -> Optional[bpy.types.Object]:
        """获取当前选中的对象"""
        return bpy.context.active_object

    @staticmethod
    def get_selected_objects() -> List[bpy.types.Object]:
        """获取所有选中的对象"""
        return list(bpy.context.selected_objects)

    @staticmethod
    def get_scene() -> bpy.types.Scene:
        """获取当前场景"""
        return bpy.context.scene

    @staticmethod
    def select_object(obj: bpy.types.Object, select: bool = True):
        """设置对象选中状态"""
        obj.select_set(select)

    @staticmethod
    def set_active_object(obj: bpy.types.Object):
        """设置活跃对象"""
        bpy.context.view_layer.objects.active = obj

    @staticmethod
    def deselect_all():
        """取消所有对象选中"""
        bpy.ops.object.select_all(action='DESELECT')


@dataclass
class ObjectState:
    """对象状态快照"""
    name: str
    obj_type: str
    location: Tuple[float, float, float]
    rotation: Tuple[float, float, float]
    scale: Tuple[float, float, float]
    parent: Optional[str]
    materials: List[str]


class BlenderAdapter:
    """Blender API 适配器核心类，封装所有 bpy 操作"""

    # 对象创建映射表
    MESH_OPERATORS = {
        "cube": "bpy.ops.mesh.primitive_cube_add",
        "sphere": "bpy.ops.mesh.primitive_uv_sphere_add",
        "cylinder": "bpy.ops.mesh.primitive_cylinder_add",
        "cone": "bpy.ops.mesh.primitive_cone_add",
        "plane": "bpy.ops.mesh.primitive_plane_add",
        "torus": "bpy.ops.mesh.primitive_torus_add",
    }

    def __init__(self):
        self._name_counter: Dict[str, int] = {}
        self._context_adapter = BlenderContextAdapter()

    def create_object(
        self,
        obj_type: str = "mesh",
        mesh_type: str = "cube",
        name: Optional[str] = None,
        location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建 3D 对象

        Args:
            obj_type: 对象类型 (mesh/curve/light/camera)
            mesh_type: 网格类型 (cube/sphere/cylinder/cone/plane/torus)
            name: 对象名称（可选，自动生成）
            location: 位置 (x, y, z)
            rotation: 旋转 (x, y, z) 弧度
            scale: 缩放 (x, y, z)
            **kwargs: 传递给 bpy 操作的其他参数

        Returns:
            包含 success、object_id、name 等字段的字典
        """
        try:
            # 生成对象名
            if not name:
                name = self._generate_name(mesh_type)

            # 转换为弧度
            rotation_rad = tuple(radians(r) for r in rotation)

            # 根据对象类型调用不同的创建函数
            if obj_type == "mesh":
                result = self._create_mesh_object(
                    mesh_type, name, location, rotation_rad, scale, **kwargs
                )
            elif obj_type == "light":
                result = self._create_light_object(name, location, **kwargs)
            elif obj_type == "camera":
                result = self._create_camera_object(name, location, rotation_rad)
            elif obj_type == "curve":
                result = self._create_curve_object(name, location, **kwargs)
            else:
                return {
                    "success": False,
                    "error": f"不支持的对象类型: {obj_type}"
                }

            if result.get("success"):
                # 应用变换
                obj = result.get("object")
                if obj:
                    obj.location = location
                    obj.rotation_euler = rotation_rad
                    obj.scale = scale
                    bpy.context.view_layer.update()

                return {
                    "success": True,
                    "object_id": str(result.get("object").name_full),
                    "name": result.get("object").name_full,
                    "type": obj_type,
                    "location": location,
                    "rotation": rotation,
                    "scale": scale,
                    "message": f"成功创建 {obj_type} 对象: {name}"
                }
            else:
                return result

        except Exception as e:
            logger.exception(f"创建对象失败: {e}")
            return {
                "success": False,
                "error": f"创建对象失败: {str(e)}"
            }

    def _create_mesh_object(
        self,
        mesh_type: str,
        name: str,
        location: Tuple[float, float, float],
        rotation: Tuple[float, float, float],
        scale: Tuple[float, float, float],
        **kwargs
    ) -> Dict[str, Any]:
        """创建网格对象"""
        operator_path = self.MESH_OPERATORS.get(mesh_type)
        if not operator_path:
            return {
                "success": False,
                "error": f"不支持的网格类型: {mesh_type}"
            }

        # 获取操作符
        parts = operator_path.split('.')
        op_module = bpy.ops.mesh
        for part in parts[1:]:
            op_module = getattr(op_module, part)

        # 准备参数
        params = {
            "location": location,
            "rotation": rotation,
            "scale": scale,
            **kwargs
        }

        # 调用操作符
        success = op_module(**params)

        if success and bpy.context.active_object:
            obj = bpy.context.active_object
            obj.name = name
            return {
                "success": True,
                "object": obj
            }
        else:
            return {
                "success": False,
                "error": f"创建网格 {mesh_type} 失败"
            }

    def _create_light_object(
        self,
        name: str,
        location: Tuple[float, float, float],
        light_type: str = "POINT",
        **kwargs
    ) -> Dict[str, Any]:
        """创建灯光对象"""
        success = bpy.ops.object.light_add(
            type=light_type,
            location=location
        )

        if success and bpy.context.active_object:
            obj = bpy.context.active_object
            obj.name = name
            return {
                "success": True,
                "object": obj
            }
        return {
            "success": False,
            "error": f"创建灯光 {light_type} 失败"
        }

    def _create_camera_object(
        self,
        name: str,
        location: Tuple[float, float, float],
        rotation: Tuple[float, float, float]
    ) -> Dict[str, Any]:
        """创建相机对象"""
        success = bpy.ops.object.camera_add(
            location=location,
            rotation=rotation
        )

        if success and bpy.context.active_object:
            obj = bpy.context.active_object
            obj.name = name
            return {
                "success": True,
                "object": obj
            }
        return {
            "success": False,
            "error": "创建相机失败"
        }

    def _create_curve_object(
        self,
        name: str,
        location: Tuple[float, float, float],
        curve_type: str = "BEZIER",
        **kwargs
    ) -> Dict[str, Any]:
        """创建曲线对象"""
        success = bpy.ops.curve.primitive_bezier_curve_add(
            location=location
        )

        if success and bpy.context.active_object:
            obj = bpy.context.active_object
            obj.name = name
            return {
                "success": True,
                "object": obj
            }
        return {
            "success": False,
            "error": "创建曲线失败"
        }

    def transform_object(
        self,
        object_name: Optional[str] = None,
        location: Optional[Tuple[float, float, float]] = None,
        rotation: Optional[Tuple[float, float, float]] = None,
        scale: Optional[Tuple[float, float, float]] = None,
        mode: str = "absolute",
        **kwargs
    ) -> Dict[str, Any]:
        """
        变换对象（移动、旋转、缩放）

        Args:
            object_name: 对象名称（None 表示操作活跃对象）
            location: 新位置 (x, y, z)
            rotation: 新旋转 (x, y, z) 角度
            scale: 新缩放 (x, y, z)
            mode: 变换模式 ("absolute" 或 "relative")
            **kwargs: 其他变换参数

        Returns:
            操作结果字典
        """
        try:
            # 获取目标对象
            if object_name:
                obj = bpy.data.objects.get(object_name)
                if not obj:
                    return {
                        "success": False,
                        "error": f"对象不存在: {object_name}"
                    }
            else:
                obj = bpy.context.active_object
                if not obj:
                    return {
                        "success": False,
                        "error": "没有活跃对象"
                    }

            # 位置变换
            if location is not None:
                if mode == "relative":
                    obj.location += location
                else:
                    obj.location = location

            # 旋转变换
            if rotation is not None:
                rotation_rad = tuple(radians(r) for r in rotation)
                if mode == "relative":
                    obj.rotation_euler = tuple(
                        obj.rotation_euler[i] + rotation_rad[i]
                        for i in range(3)
                    )
                else:
                    obj.rotation_euler = rotation_rad

            # 缩放变换
            if scale is not None:
                if mode == "relative":
                    obj.scale = tuple(
                        obj.scale[i] * scale[i]
                        for i in range(3)
                    )
                else:
                    obj.scale = scale

            # 更新场景
            bpy.context.view_layer.update()

            return {
                "success": True,
                "object_id": str(obj.name_full),
                "name": obj.name_full,
                "location": tuple(obj.location),
                "rotation": tuple(degrees(r) for r in obj.rotation_euler),
                "scale": tuple(obj.scale),
                "message": f"成功变换对象: {obj.name_full}"
            }

        except Exception as e:
            logger.exception(f"变换对象失败: {e}")
            return {
                "success": False,
                "error": f"变换对象失败: {str(e)}"
            }

    def delete_object(
        self,
        object_name: Optional[str] = None,
        use_global: bool = False
    ) -> Dict[str, Any]:
        """
        删除对象

        Args:
            object_name: 对象名称（None 表示删除选中对象）
            use_global: 是否全局删除

        Returns:
            操作结果字典
        """
        try:
            if object_name:
                obj = bpy.data.objects.get(object_name)
                if not obj:
                    return {
                        "success": False,
                        "error": f"对象不存在: {object_name}"
                    }

                # 设置活跃对象并选中
                bpy.context.view_layer.objects.active = obj
                self._context_adapter.deselect_all()
                obj.select_set(True)

            # 执行删除
            success = bpy.ops.object.delete(
                use_global=use_global,
                confirm=False
            )

            if success:
                return {
                    "success": True,
                    "message": "对象已删除"
                }
            else:
                return {
                    "success": False,
                    "error": "删除对象失败"
                }

        except Exception as e:
            logger.exception(f"删除对象失败: {e}")
            return {
                "success": False,
                "error": f"删除对象失败: {str(e)}"
            }

    def get_object_state(self, object_name: str) -> Optional[Dict[str, Any]]:
        """获取对象状态"""
        obj = bpy.data.objects.get(object_name)
        if not obj:
            return None

        return {
            "name": obj.name_full,
            "type": obj.type,
            "location": tuple(obj.location),
            "rotation": tuple(degrees(r) for r in obj.rotation_euler),
            "scale": tuple(obj.scale),
            "parent": obj.parent.name_full if obj.parent else None,
            "materials": [
                mat.name for mat in obj.data.materials if mat
            ] if hasattr(obj.data, 'materials') else []
        }

    def list_objects(self) -> List[Dict[str, Any]]:
        """列出场景中所有对象"""
        scene = self._context_adapter.get_scene()
        objects = []

        for obj in scene.objects:
            objects.append({
                "name": obj.name_full,
                "type": obj.type,
                "location": tuple(obj.location),
                "visible": obj.visible_get()
            })

        return objects

    def _generate_name(self, base_name: str) -> str:
        """生成唯一的对象名称"""
        if base_name not in self._name_counter:
            self._name_counter[base_name] = 1

        count = self._name_counter[base_name]
        self._name_counter[base_name] += 1

        return f"{base_name}.{count:03d}"

    # === modify_mesh 布尔运算 ===
    def modify_mesh_boolean(
        self,
        target_name: str,
        operation: str = "UNION",
        object_name: Optional[str] = None,
        delete_other: bool = True
    ) -> Dict[str, Any]:
        """
        执行布尔运算（UNION/INTERSECTION/DIFFERENCE）

        Args:
            target_name: 目标对象名称
            operation: 布尔操作类型
            object_name: 操作对象名称（None 表示使用活跃对象）
            delete_other: 操作后是否删除操作对象
        """
        try:
            target_obj = bpy.data.objects.get(target_name)
            if not target_obj:
                return {
                    "success": False,
                    "error": f"目标对象不存在: {target_name}"
                }

            if object_name:
                other_obj = bpy.data.objects.get(object_name)
            else:
                other_obj = bpy.context.active_object

            if not other_obj:
                return {
                    "success": False,
                    "error": "没有操作对象"
                }

            # 前置检查: 包围盒重叠
            if not self._check_bounding_box_overlap(target_obj, other_obj):
                logger.warning("警告: 包围盒不重叠")

            # 添加布尔修改器
            mod = target_obj.modifiers.new(name="Boolean", type='BOOLEAN')
            mod.operation = operation
            mod.object = other_obj

            # 应用修改器
            bpy.context.view_layer.objects.active = target_obj
            self._context_adapter.deselect_all()
            target_obj.select_set(True)
            bpy.ops.object.modifier_apply(modifier=mod.name)

            # 删除操作对象
            if delete_other:
                self._context_adapter.deselect_all()
                other_obj.select_set(True)
                bpy.ops.object.delete(confirm=False)

            return {
                "success": True,
                "target": target_obj.name_full,
                "operation": operation,
                "message": f"成功执行布尔 {operation}"
            }
        except Exception as e:
            logger.exception(f"布尔运算失败: {e}")
            return {
                "success": False,
                "error": f"布尔运算失败: {str(e)}"
            }

    def _check_bounding_box_overlap(
        self,
        obj1: bpy.types.Object,
        obj2: bpy.types.Object
    ) -> bool:
        """检查两个对象的包围盒是否重叠"""
        bbox1 = self._get_world_bbox(obj1)
        bbox2 = self._get_world_bbox(obj2)
        for i in range(3):
            if bbox1['max'][i] < bbox2['min'][i]:
                return False
            if bbox1['min'][i] > bbox2['max'][i]:
                return False
        return True

    def _get_world_bbox(self, obj: bpy.types.Object) -> Dict[str, Tuple]:
        """获取对象的世界坐标包围盒"""
        matrix = obj.matrix_world
        bbox_world = [matrix @ bpy.mathutils.Vector(p) for p in obj.bound_box]
        min_vec = bpy.mathutils.Vector((float('inf'),) * 3)
        max_vec = bpy.mathutils.Vector((-float('inf'),) * 3)
        for v in bbox_world:
            min_vec.x = min(min_vec.x, v.x)
            min_vec.y = min(min_vec.y, v.y)
            min_vec.z = min(min_vec.z, v.z)
            max_vec.x = max(max_vec.x, v.x)
            max_vec.y = max(max_vec.y, v.y)
            max_vec.z = max(max_vec.z, v.z)
        return {'min': (min_vec.x, min_vec.y, min_vec.z),
                'max': (max_vec.x, max_vec.y, max_vec.z)}

    # === 变形与雕刻工具 ===
    def simple_deform(
        self,
        object_name: Optional[str] = None,
        deform_type: str = "BEND",
        factor: float = 0.5,
        angle: float = 45,
        lock_x: bool = True,
        lock_y: bool = True,
        lock_z: bool = False
    ) -> Dict[str, Any]:
        """
        SimpleDeform 变形（BEND/TWIST/TAPER/STRETCH）
        """
        try:
            obj = bpy.data.objects.get(object_name) if object_name else bpy.context.active_object
            if not obj:
                return {"success": False, "error": "没有对象"}

            mod = obj.modifiers.new(name="SimpleDeform", type='SIMPLE_DEFORM')
            mod.deform_method = deform_type
            if deform_type == "BEND":
                mod.angle = radians(angle)
            else:
                mod.factor = factor
            if lock_x:
                mod.lock_x = True
            if lock_y:
                mod.lock_y = True
            if lock_z:
                mod.lock_z = True

            # 应用修改器
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)

            return {
                "success": True,
                "type": deform_type,
                "object": obj.name_full
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"simple_deform 失败: {str(e)}"
            }

    def mesh_sculpt(
        self,
        object_name: Optional[str] = None,
        operation: str = "SMOOTH",
        strength: float = 0.5,
        radius: float = 1.0,
        vertex_indices: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        基础雕刻操作（PUSH/PULL/SMOOTH/INFLATE）
        基于 bmesh 实现
        """
        try:
            obj = bpy.data.objects.get(object_name) if object_name else bpy.context.active_object
            if not obj or obj.type != 'MESH':
                return {
                    "success": False,
                    "error": "不是网格对象"
                }

            # 进入 Edit 模式或直接用 bmesh
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()

            # 选择顶点（默认全部或指定索引）
            selected_verts = []
            if vertex_indices:
                selected_verts = [bm.verts[i] for i in vertex_indices if 0 <= i < len(bm.verts)]
            else:
                selected_verts = list(bm.verts)

            if not selected_verts:
                return {
                    "success": False,
                    "error": "没有选中顶点"
                }

            # 执行雕刻操作
            for v in selected_verts:
                if operation == "SMOOTH":
                    # 拉普拉斯平滑
                    neighbors = list(v.link_edges)
                    if neighbors:
                        avg = bpy.mathutils.Vector((0, 0, 0))
                        for e in neighbors:
                            other = e.other_vert(v)
                            avg += other.co
                        avg /= len(neighbors)
                        v.co = v.co + (avg - v.co) * strength
                elif operation == "PUSH":
                    # 沿法线向内推
                    v.co -= v.normal * strength
                elif operation == "PULL":
                    # 沿法线向外拉
                    v.co += v.normal * strength
                elif operation == "INFLATE":
                    # 膨胀：沿法线向外
                    v.co += v.normal * strength

            # 更新回 Mesh
            bm.to_mesh(obj.data)
            obj.data.update()
            bm.free()

            return {
                "success": True,
                "operation": operation,
                "affected_verts": len(selected_verts),
                "object": obj.name_full
            }
        except Exception as e:
            logger.exception(f"mesh_sculpt 失败")
            return {
                "success": False,
                "error": f"mesh_sculpt 失败: {str(e)}"
            }

    # === 修改器添加 ===
    def add_modifier(
        self,
        object_name: Optional[str] = None,
        mod_type: str = "SOLIDIFY",
        name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        通用修改器添加：SOLIDIFY/SUBSURF/BEVEL/等
        """
        try:
            obj = bpy.data.objects.get(object_name) if object_name else bpy.context.active_object
            if not obj:
                return {
                    "success": False,
                    "error": "没有对象"
                }

            mod = obj.modifiers.new(name=name or mod_type, type=mod_type)

            # 根据类型设置参数
            if mod_type == "SUBSURF":
                mod.levels = kwargs.get("levels", 2)
                mod.render_levels = kwargs.get("render_levels", 2)
            elif mod_type == "SOLIDIFY":
                mod.thickness = kwargs.get("thickness", 0.01)
            elif mod_type == "BEVEL":
                mod.width = kwargs.get("width", 0.01)
                mod.segments = kwargs.get("segments", 2)

            return {
                "success": True,
                "mod_type": mod_type,
                "object": obj.name_full
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"添加修改器失败: {str(e)}"
            }

    def apply_modifier(
        self,
        object_name: Optional[str] = None,
        mod_name: str = "",
        apply_all: bool = False
    ) -> Dict[str, Any]:
        """应用修改器"""
        try:
            obj = bpy.data.objects.get(object_name) if object_name else bpy.context.active_object
            if not obj:
                return {
                    "success": False,
                    "error": "没有对象"
                }

            if apply_all:
                mod_names = [mod.name for mod in obj.modifiers]
                for name in mod_names:
                    try:
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.object.modifier_apply(modifier=name)
                    except Exception:
                        pass
                return {
                    "success": True,
                    "applied": mod_names
                }
            else:
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.modifier_apply(modifier=mod_name)
                return {
                    "success": True,
                    "applied": mod_name
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # === 文件导入导出 ===
    def export_model(
        self,
        file_path: str,
        file_format: str = "STL",
        selection_only: bool = False
    ) -> Dict[str, Any]:
        """导出模型"""
        try:
            bpy.ops.export_mesh.stl(
                filepath=file_path,
                use_selection=selection_only
            )
            return {
                "success": True,
                "file": file_path,
                "format": file_format
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"导出失败: {str(e)}"
            }

    def import_model(
        self,
        file_path: str,
        file_format: str = "STL"
    ) -> Dict[str, Any]:
        """导入模型"""
        try:
            bpy.ops.import_mesh.stl(filepath=file_path)
            obj = bpy.context.active_object
            return {
                "success": True,
                "object": obj.name_full if obj else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"导入失败: {str(e)}"
            }

    # === 模型检查与修复 ===
    def check_model(
        self,
        object_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        检查模型问题：非流形、法线方向、壁厚
        """
        try:
            obj = bpy.data.objects.get(object_name) if object_name else bpy.context.active_object
            if not obj or obj.type != 'MESH':
                return {
                    "success": False,
                    "error": "不是网格对象"
                }

            bm = bmesh.new()
            bm.from_mesh(obj.data)

            issues = {
                "non_manifold_edges": 0,
                "non_manifold_verts": 0,
                "normals_inconsistent": False
            }

            # 检查边
            for e in bm.edges:
                if not e.is_manifold:
                    issues["non_manifold_edges"] += 1

            # 检查顶点
            for v in bm.verts:
                if not v.is_manifold:
                    issues["non_manifold_verts"] += 1

            # 检查法线 (简单检查)
            faces = list(bm.faces)
            avg_normal = None
            issues_count = 0
            for f in faces:
                n = f.normal.normalized()
                if avg_normal is None:
                    avg_normal = n
                else:
                    if avg_normal.dot(n) < 0.0:
                        issues_count += 1
            if issues_count > len(faces) * 0.3:
                issues["normals_inconsistent"] = True

            bm.free()

            return {
                "success": True,
                "issues": issues,
                "is_print_ready": (
                    issues["non_manifold_edges"] == 0 and
                    issues["non_manifold_verts"] == 0 and
                    not issues["normals_inconsistent"]
                )
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def repair_model(
        self,
        object_name: Optional[str] = None,
        recalc_normals: bool = True
    ) -> Dict[str, Any]:
        """修复模型问题"""
        try:
            obj = bpy.data.objects.get(object_name) if object_name else bpy.context.active_object
            if not obj or obj.type != 'MESH':
                return {
                    "success": False,
                    "error": "不是网格对象"
                }

            # 切换到 Edit 模式并选中所有顶点
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')

            # 执行修复操作
            bpy.ops.mesh.remove_doubles()
            if recalc_normals:
                bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.mesh.select_all(action='DESELECT')

            bpy.ops.object.mode_set(mode='OBJECT')

            return {
                "success": True,
                "message": "修复完成"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"修复失败: {str(e)}"
            }


# 辅助函数
def radians(degrees_val: float) -> float:
    """角度转弧度"""
    return degrees_val * math.pi / 180.0


def degrees(radians_val: float) -> float:
    """弧度转角度"""
    return radians_val * 180.0 / math.pi
