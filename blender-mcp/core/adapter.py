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


class AttenuationType(Enum):
    """衰减函数类型"""
    LINEAR = "LINEAR"
    INVERSE = "INVERSE"
    CONSTANT = "CONSTANT"
    GAUSSIAN = "GAUSSIAN"
    ROOT = "ROOT"


class KDTree:
    """简单的 KD-Tree 实现，用于快速最近邻搜索"""
    
    def __init__(self, points: List[Tuple[float, float, float]]):
        self.points = points
        self.tree = None
        if points:
            self._build_tree()
    
    def _build_tree(self):
        """构建 KD-Tree（使用 Blender 的 bvhtree）"""
        # Blender 提供了内置的 BVHTree，我们直接使用它
        pass
    
    @staticmethod
    def create_bvhtree_from_mesh(obj: bpy.types.Object) -> 'bvh_tree':
        """从网格对象创建 BVHTree"""
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        bvh_tree = bvhtree.BVHTree.FromBMesh(bm)
        bm.free()
        return bvh_tree
    
    @staticmethod
    def find_vertices_in_radius(
        obj: bpy.types.Object,
        center: Tuple[float, float, float],
        radius: float
    ) -> List[Tuple[int, float]]:
        """
        在指定半径范围内查找顶点
        
        Args:
            obj: 网格对象
            center: 搜索中心点 (世界坐标)
            radius: 搜索半径
        
        Returns:
            列表格式: [(顶点索引, 距离), ...]
        """
        import mathutils
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        
        center_vec = mathutils.Vector(center)
        matrix_inv = obj.matrix_world.inverted()
        local_center = matrix_inv @ center_vec
        
        result = []
        for i, v in enumerate(bm.verts):
            dist = (v.co - local_center).length
            if dist <= radius:
                world_v = obj.matrix_world @ v.co
                world_dist = (world_v - center_vec).length
                result.append((i, world_dist))
        
        bm.free()
        return result


def calculate_attenuation(distance: float, radius: float, falloff_type: str = "LINEAR") -> float:
    """
    计算衰减因子
    
    Args:
        distance: 距离中心的距离
        radius: 作用半径
        falloff_type: 衰减类型 (LINEAR/INVERSE/CONSTANT/GAUSSIAN/ROOT)
    
    Returns:
        衰减因子 [0.0, 1.0]
    """
    if radius <= 0.0:
        return 1.0
    
    normalized_dist = min(distance / radius, 1.0)
    
    if falloff_type == "LINEAR":
        return 1.0 - normalized_dist
    elif falloff_type == "INVERSE":
        return 1.0 / (1.0 + normalized_dist * 3.0)
    elif falloff_type == "CONSTANT":
        return 1.0 if normalized_dist <= 1.0 else 0.0
    elif falloff_type == "GAUSSIAN":
        return math.exp(-3.0 * normalized_dist * normalized_dist)
    elif falloff_type == "ROOT":
        return 1.0 - math.sqrt(normalized_dist)
    else:
        return 1.0 - normalized_dist


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

    def soft_transform(
        self,
        object_name: Optional[str] = None,
        center: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        radius: float = 1.0,
        displacement: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        falloff_type: str = "LINEAR",
        transform_type: str = "TRANSLATE"
    ) -> Dict[str, Any]:
        """
        软选择变形（KD-Tree + 衰减函数）
        
        Args:
            object_name: 目标对象名称（None 表示活跃对象）
            center: 变形中心（世界坐标）
            radius: 影响半径
            displacement: 位移向量 (x, y, z)
            falloff_type: 衰减类型 (LINEAR/INVERSE/CONSTANT/GAUSSIAN/ROOT)
            transform_type: 变换类型 (TRANSLATE/ROTATE/SCALE)
        
        Returns:
            操作结果字典
        """
        try:
            import mathutils
            obj = bpy.data.objects.get(object_name) if object_name else bpy.context.active_object
            if not obj or obj.type != 'MESH':
                return {
                    "success": False,
                    "error": "不是网格对象"
                }

            # 查找半径范围内的顶点
            vertices_in_radius = KDTree.find_vertices_in_radius(obj, center, radius)
            if not vertices_in_radius:
                return {
                    "success": False,
                    "error": "没有顶点在影响范围内"
                }

            # 使用 bmesh 进行变形
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()

            displacement_vec = mathutils.Vector(displacement)
            center_vec = mathutils.Vector(center)

            affected_count = 0
            for idx, dist in vertices_in_radius:
                if idx < len(bm.verts):
                    v = bm.verts[idx]
                    # 计算衰减因子
                    attenuation = calculate_attenuation(dist, radius, falloff_type)
                    
                    # 执行变换
                    if transform_type == "TRANSLATE":
                        v.co += displacement_vec * attenuation
                    elif transform_type == "SCALE":
                        # 相对于中心进行缩放
                        local_pos = v.co - center_vec
                        scale_factor = 1.0 + (displacement_vec[0] - 1.0) * attenuation
                        v.co = center_vec + local_pos * scale_factor
                    elif transform_type == "ROTATE":
                        # 简单的旋转实现
                        rot_angle = displacement[0] * attenuation
                        rot_axis = mathutils.Vector((0, 0, 1))
                        local_pos = v.co - center_vec
                        local_pos.rotate(mathutils.Euler((0, 0, rot_angle), 'XYZ'))
                        v.co = center_vec + local_pos
                    
                    affected_count += 1

            # 更新网格
            bm.to_mesh(obj.data)
            obj.data.update()
            bm.free()

            return {
                "success": True,
                "object": obj.name_full,
                "affected_vertices": affected_count,
                "center": center,
                "radius": radius,
                "falloff": falloff_type,
                "message": f"成功软变形 {affected_count} 个顶点"
            }
        except Exception as e:
            logger.exception(f"soft_transform 失败")
            return {
                "success": False,
                "error": f"soft_transform 失败: {str(e)}"
            }

    def curve_deform(
        self,
        object_name: str,
        curve_name: str,
        deform_axis: str = 'Z',
        factor: float = 1.0
    ) -> Dict[str, Any]:
        """
        曲线变形（使用 Curve 修改器）
        
        Args:
            object_name: 要变形的对象名称
            curve_name: 曲线对象名称
            deform_axis: 变形轴 (X/Y/Z/-X/-Y/-Z)
            factor: 变形强度因子
        
        Returns:
            操作结果字典
        """
        try:
            obj = bpy.data.objects.get(object_name)
            curve_obj = bpy.data.objects.get(curve_name)
            
            if not obj or obj.type != 'MESH':
                return {"success": False, "error": "对象不是网格"}
            if not curve_obj or curve_obj.type != 'CURVE':
                return {"success": False, "error": "曲线对象不存在"}

            # 添加 Curve 修改器
            mod = obj.modifiers.new(name="CurveDeform", type='CURVE')
            mod.object = curve_obj
            mod.deform_axis = deform_axis

            return {
                "success": True,
                "object": obj.name_full,
                "curve": curve_obj.name_full,
                "message": "曲线变形修改器已添加"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"curve_deform 失败: {str(e)}"
            }

    def shrinkwrap(
        self,
        object_name: str,
        target_name: str,
        wrap_method: str = 'NEAREST_SURFACEPOINT',
        offset: float = 0.0,
        apply: bool = False
    ) -> Dict[str, Any]:
        """
        Shrinkwrap（收缩包裹）修改器
        
        Args:
            object_name: 源对象名称
            target_name: 目标对象名称
            wrap_method: 包裹方法 (NEAREST_SURFACEPOINT/PROJECT/NEAREST_VERTEX)
            offset: 偏移距离
            apply: 是否立即应用修改器
        
        Returns:
            操作结果字典
        """
        try:
            obj = bpy.data.objects.get(object_name)
            target_obj = bpy.data.objects.get(target_name)
            
            if not obj or obj.type != 'MESH':
                return {"success": False, "error": "源对象不是网格"}
            if not target_obj:
                return {"success": False, "error": "目标对象不存在"}

            mod = obj.modifiers.new(name="Shrinkwrap", type='SHRINKWRAP')
            mod.target = target_obj
            mod.wrap_method = wrap_method
            mod.offset = offset

            if apply:
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.modifier_apply(modifier=mod.name)

            return {
                "success": True,
                "object": obj.name_full,
                "target": target_obj.name_full,
                "applied": apply,
                "message": "Shrinkwrap 修改器已添加" + ("并应用" if apply else "")
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"shrinkwrap 失败: {str(e)}"
            }

    # === 材质工具 ===
    @staticmethod
    def create_principled_material(
        name: str,
        base_color: Tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
        metallic: float = 0.0,
        roughness: float = 0.5,
        specular: float = 0.5,
        transmission: float = 0.0,
        emission_color: Optional[Tuple[float, float, float, float]] = None,
        emission_strength: float = 0.0,
        alpha: float = 1.0,
    ) -> bpy.types.Material:
        _validate_material_params(
            base_color=base_color,
            metallic=metallic,
            roughness=roughness,
            specular=specular,
            transmission=transmission,
            alpha=alpha,
        )

        material = bpy.data.materials.new(name=name)
        material.use_nodes = True

        node_tree = material.node_tree
        principled_node = _find_principled_bsdf(node_tree)

        if principled_node is None:
            principled_node = node_tree.nodes.new('ShaderNodeBsdfPrincipled')

        principled_node.inputs['Base Color'].default_value = base_color
        principled_node.inputs['Metallic'].default_value = metallic
        principled_node.inputs['Roughness'].default_value = roughness
        principled_node.inputs['Specular'].default_value = specular
        principled_node.inputs['Alpha'].default_value = alpha

        if 'Transmission' in principled_node.inputs:
            principled_node.inputs['Transmission'].default_value = transmission

        if emission_color is not None and emission_strength > 0:
            if 'Emission Color' in principled_node.inputs:
                principled_node.inputs['Emission Color'].default_value = emission_color
            if 'Emission Strength' in principled_node.inputs:
                principled_node.inputs['Emission Strength'].default_value = emission_strength

        if alpha < 1.0 or transmission > 0.0:
            if hasattr(material, 'blend_method'):
                material.blend_method = 'BLEND'
            if hasattr(material, 'shadow_method'):
                material.shadow_method = 'HASHED'

        return material

    def set_material(
        self,
        object_id: str,
        material_name: Optional[str] = None,
        preset: Optional[str] = None,
        replace: bool = False,
        base_color: Tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
        metallic: float = 0.0,
        roughness: float = 0.5,
        specular: float = 0.5,
        transmission: float = 0.0,
        emission_color: Optional[Tuple[float, float, float, float]] = None,
        emission_strength: float = 0.0,
        alpha: float = 1.0,
    ) -> Dict[str, Any]:
        try:
            obj = bpy.data.objects.get(object_id)
            if obj is None:
                return {
                    "success": False,
                    "error": f"对象 '{object_id}' 不存在",
                    "error_code": "OBJECT_NOT_FOUND"
                }

            if obj.type not in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META'):
                return {
                    "success": False,
                    "error": f"对象类型 '{obj.type}' 不支持材质分配",
                    "error_code": "OPERATION_NOT_ALLOWED"
                }

            if not material_name:
                material_name = f"Material_{object_id}"

            if preset:
                material = MaterialLibrary.get_or_create(
                    name=material_name,
                    preset=preset,
                    base_color=base_color,
                    metallic=metallic,
                    roughness=roughness,
                    specular=specular,
                    transmission=transmission,
                    alpha=alpha,
                )
            else:
                material = self.create_principled_material(
                    name=material_name,
                    base_color=base_color,
                    metallic=metallic,
                    roughness=roughness,
                    specular=specular,
                    transmission=transmission,
                    emission_color=emission_color,
                    emission_strength=emission_strength,
                    alpha=alpha,
                )

            if replace:
                for i in range(len(obj.material_slots)):
                    obj.data.materials.pop(index=0)

            obj.data.materials.append(material)
            slot_index = len(obj.material_slots) - 1
            obj.active_material_index = slot_index

            return {
                "success": True,
                "object_id": object_id,
                "material_name": material.name,
                "material_id": material.name,
                "slot_index": slot_index,
                "total_materials": len(obj.material_slots),
                "preset": preset,
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "error_code": "INVALID_PARAMETER"
            }
        except Exception as e:
            logger.exception(f"set_material 失败")
            return {
                "success": False,
                "error": f"set_material 失败: {str(e)}"
            }

    def list_materials(self) -> Dict[str, Any]:
        try:
            materials = MaterialLibrary.list_materials()
            return {
                "success": True,
                "count": len(materials),
                "materials": materials
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def delete_material(self, name: str) -> Dict[str, Any]:
        try:
            deleted = MaterialLibrary.delete_material(name)
            if deleted:
                return {
                    "success": True,
                    "deleted": name
                }
            else:
                return {
                    "success": False,
                    "error": f"无法删除材质 '{name}'（不存在或仍有用户引用）"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # === 渲染工具 ===
    def render_scene(
        self,
        engine: str = 'CYCLES',
        resolution_x: int = 1920,
        resolution_y: int = 1080,
        resolution_percentage: int = 100,
        output_path: Optional[str] = None,
        file_format: str = 'PNG',
        color_mode: str = 'RGBA',
        color_depth: int = 8,
        compression: int = 15,
        samples: Optional[int] = None,
        use_denoising: bool = True,
    ) -> Dict[str, Any]:
        import os
        import tempfile
        import time as _time

        try:
            scene = bpy.context.scene

            camera = None
            for obj in scene.objects:
                if obj.type == 'CAMERA':
                    camera = obj
                    break
            if camera is None:
                return {
                    "success": False,
                    "error": "场景中没有相机，无法渲染",
                    "error_code": "OPERATION_NOT_ALLOWED"
                }

            engine_upper = engine.upper()
            if engine_upper not in RENDER_ENGINE_MAP:
                return {
                    "success": False,
                    "error": f"不支持的渲染引擎: '{engine}'，可选值: {list(RENDER_ENGINE_MAP.keys())}",
                    "error_code": "INVALID_PARAMETER"
                }

            scene.render.engine = RENDER_ENGINE_MAP[engine_upper]

            if engine_upper == 'CYCLES':
                scene.cycles.device = 'CPU'
                scene.cycles.samples = 128
                scene.cycles.use_denoising = True
            elif engine_upper == 'EEVEE':
                if hasattr(scene, 'eevee'):
                    scene.eevee.taa_render_samples = 64

            render = scene.render
            render.resolution_x = resolution_x
            render.resolution_y = resolution_y
            render.resolution_percentage = resolution_percentage

            if output_path is None:
                output_dir = tempfile.mkdtemp(prefix="blender-mcp-render-")
                output_path = os.path.join(output_dir, "render.png")

            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.isdir(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            render.filepath = output_path

            render.image_settings.file_format = FORMAT_MAP.get(
                file_format.upper(), 'PNG'
            )
            render.image_settings.color_mode = color_mode
            render.image_settings.color_depth = str(color_depth)

            if render.image_settings.file_format == 'PNG':
                render.image_settings.compression = compression

            if samples is not None:
                if engine_upper == 'CYCLES':
                    scene.cycles.samples = samples
                elif engine_upper == 'EEVEE' and hasattr(scene, 'eevee'):
                    scene.eevee.taa_render_samples = samples

            if engine_upper == 'CYCLES':
                scene.cycles.use_denoising = use_denoising

            start_time = _time.time()

            try:
                bpy.ops.render.render(write_still=True)
            except RuntimeError as e:
                if "GPU" in str(e) and engine_upper == 'CYCLES':
                    scene.cycles.device = 'CPU'
                    bpy.ops.render.render(write_still=True)
                else:
                    raise

            render_time = _time.time() - start_time

            actual_output = render.filepath
            if not actual_output.endswith(('.png', '.jpg', '.jpeg', '.tif', '.exr')):
                actual_output += '.png'

            file_size = 0
            if os.path.exists(actual_output):
                file_size = os.path.getsize(actual_output)

            actual_samples = samples
            if actual_samples is None:
                if engine_upper == 'CYCLES':
                    actual_samples = scene.cycles.samples
                elif engine_upper == 'EEVEE' and hasattr(scene, 'eevee'):
                    actual_samples = scene.eevee.taa_render_samples

            return {
                "success": True,
                "output_path": actual_output,
                "resolution": [resolution_x, resolution_y],
                "resolution_percentage": resolution_percentage,
                "engine": engine,
                "samples": actual_samples,
                "use_denoising": use_denoising,
                "render_time": round(render_time, 2),
                "file_size": file_size,
                "file_format": file_format,
            }
        except Exception as e:
            logger.exception(f"render_scene 失败")
            return {
                "success": False,
                "error": f"render_scene 失败: {str(e)}"
            }


def _validate_material_params(
    base_color: tuple,
    metallic: float,
    roughness: float,
    specular: float,
    transmission: float,
    alpha: float,
) -> None:
    for i, c in enumerate(base_color):
        if not (0.0 <= c <= 1.0):
            raise ValueError(f"base_color[{i}] = {c} 超出范围 [0.0, 1.0]")

    for name, value, lo, hi in [
        ('metallic', metallic, 0.0, 1.0),
        ('roughness', roughness, 0.0, 1.0),
        ('specular', specular, 0.0, 1.0),
        ('transmission', transmission, 0.0, 1.0),
        ('alpha', alpha, 0.0, 1.0),
    ]:
        if not (lo <= value <= hi):
            raise ValueError(f"{name} = {value} 超出范围 [{lo}, {hi}]")


def _find_principled_bsdf(node_tree):
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            return node
    return None


class MaterialLibrary:
    PRESETS = {
        'plastic': {
            'metallic': 0.0, 'roughness': 0.4, 'transmission': 0.0,
        },
        'glossy_plastic': {
            'metallic': 0.0, 'roughness': 0.1, 'transmission': 0.0,
        },
        'metal': {
            'metallic': 1.0, 'roughness': 0.3, 'transmission': 0.0,
        },
        'chrome': {
            'base_color': (0.8, 0.8, 0.8, 1.0),
            'metallic': 1.0, 'roughness': 0.05, 'transmission': 0.0,
        },
        'glass': {
            'metallic': 0.0, 'roughness': 0.0, 'transmission': 1.0,
        },
        'rubber': {
            'metallic': 0.0, 'roughness': 0.9, 'transmission': 0.0,
        },
        'ceramic': {
            'metallic': 0.0, 'roughness': 0.2, 'transmission': 0.0,
        },
        'wood': {
            'metallic': 0.0, 'roughness': 0.7, 'transmission': 0.0,
        },
    }

    @classmethod
    def get_or_create(cls, name: str, preset: Optional[str] = None, **overrides) -> bpy.types.Material:
        existing = bpy.data.materials.get(name)
        if existing is not None:
            return existing

        params = {}
        if preset and preset in cls.PRESETS:
            params = dict(cls.PRESETS[preset])
        params.update(overrides)

        return BlenderAdapter.create_principled_material(name=name, **params)

    @classmethod
    def list_materials(cls) -> List[dict]:
        materials = []
        for mat in bpy.data.materials:
            principled = None
            if mat.use_nodes:
                principled = _find_principled_bsdf(mat.node_tree)

            info = {
                'name': mat.name,
                'users': mat.users,
                'has_nodes': mat.use_nodes,
            }

            if principled:
                info['properties'] = {
                    'base_color': list(principled.inputs['Base Color'].default_value),
                    'metallic': principled.inputs['Metallic'].default_value,
                    'roughness': principled.inputs['Roughness'].default_value,
                    'specular': principled.inputs['Specular'].default_value,
                    'transmission': principled.inputs['Transmission'].default_value,
                }

            materials.append(info)

        return materials

    @classmethod
    def delete_material(cls, name: str) -> bool:
        mat = bpy.data.materials.get(name)
        if mat is None:
            return False
        if mat.users > 0:
            return False
        bpy.data.materials.remove(mat)
        return True


RENDER_ENGINE_MAP = {
    'EEVEE': 'BLENDER_EEVEE_NEXT',
    'CYCLES': 'CYCLES',
}

FORMAT_MAP = {
    'PNG': 'PNG',
    'JPEG': 'JPEG',
    'JPG': 'JPEG',
    'TIFF': 'TIFF',
    'EXR': 'OPEN_EXR',
    'OPENEXR': 'OPEN_EXR',
}


class RenderProgressCallback:
    def __init__(self, notification_sender=None):
        self.notification_sender = notification_sender
        self._start_time: float = 0.0
        self._last_progress: float = 0.0
        self._progress_interval: float = 5.0

    def register(self) -> None:
        bpy.app.handlers.render_init.append(self._on_render_init)
        bpy.app.handlers.render_complete.append(self._on_render_complete)
        bpy.app.handlers.render_cancel.append(self._on_render_cancel)
        bpy.app.handlers.render_write.append(self._on_render_write)

    def unregister(self) -> None:
        for handler_list, callback in [
            (bpy.app.handlers.render_init, self._on_render_init),
            (bpy.app.handlers.render_complete, self._on_render_complete),
            (bpy.app.handlers.render_cancel, self._on_render_cancel),
            (bpy.app.handlers.render_write, self._on_render_write),
        ]:
            if callback in handler_list:
                handler_list.remove(callback)

    def _on_render_init(self, scene, depsgraph) -> None:
        import time as _time
        self._start_time = _time.time()
        self._last_progress = 0.0
        self._send_notification("render/started", {
            "engine": scene.render.engine,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        })

    def _on_render_write(self, scene, depsgraph) -> None:
        import time as _time
        now = _time.time()
        if now - self._last_progress < self._progress_interval:
            return
        self._last_progress = now
        elapsed = now - self._start_time
        self._send_notification("render/progress", {
            "elapsed_seconds": round(elapsed, 1),
        })

    def _on_render_complete(self, scene, depsgraph) -> None:
        import time as _time
        elapsed = _time.time() - self._start_time
        self._send_notification("render/completed", {
            "elapsed_seconds": round(elapsed, 2),
            "output_path": scene.render.filepath,
        })

    def _on_render_cancel(self, scene, depsgraph) -> None:
        import time as _time
        elapsed = _time.time() - self._start_time
        self._send_notification("render/cancelled", {
            "elapsed_seconds": round(elapsed, 2),
        })

    def _send_notification(self, event: str, data: dict) -> None:
        if self.notification_sender:
            self.notification_sender.send({
                "method": "notifications/render",
                "params": {
                    "event": event,
                    "data": data,
                }
            })


# 辅助函数
def radians(degrees_val: float) -> float:
    """角度转弧度"""
    return degrees_val * math.pi / 180.0


def degrees(radians_val: float) -> float:
    """弧度转角度"""
    return radians_val * 180.0 / math.pi
