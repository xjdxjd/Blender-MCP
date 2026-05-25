"""
Blender API 适配器 - 阶段二核心模块
提供 bpy 操作的统一封装，处理 Blender Python API 调用
"""

import bpy
import logging
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


# 辅助函数
def radians(degrees: float) -> float:
    """角度转弧度"""
    import math
    return degrees * math.pi / 180.0


def degrees(radians: float) -> float:
    """弧度转角度"""
    import math
    return radians * 180.0 / math.pi
