"""
核心命令处理器 - 阶段二模块
负责将 MCP 工具调用转换为 Blender API 操作
"""

import bpy
import logging
from typing import Dict, Any, Optional, List
from .adapter import BlenderAdapter
from .state import StateManager

logger = logging.getLogger(__name__)


class CommandHandler:
    """命令处理器，将 MCP 请求转换为 Blender 操作"""

    def __init__(self, adapter: Optional[BlenderAdapter] = None):
        self._adapter = adapter or BlenderAdapter()
        self._state_manager = StateManager()

    def handle_create_object(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 create_object 命令"""
        return self._adapter.create_object(
            obj_type=params.get('type', 'mesh'),
            mesh_type=params.get('mesh_type', 'cube'),
            name=params.get('name'),
            location=params.get('location', (0.0, 0.0, 0.0)),
            rotation=params.get('rotation', (0.0, 0.0, 0.0)),
            scale=params.get('scale', (1.0, 1.0, 1.0)),
            **params.get('kwargs', {})
        )

    def handle_transform_object(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 transform_object 命令"""
        return self._adapter.transform_object(
            object_name=params.get('object_name'),
            location=params.get('location'),
            rotation=params.get('rotation'),
            scale=params.get('scale'),
            mode=params.get('mode', 'absolute')
        )

    def handle_delete_object(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 delete_object 命令"""
        return self._adapter.delete_object(
            object_name=params.get('object_name'),
            use_global=params.get('use_global', False)
        )

    def handle_list_objects(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 list_objects 命令"""
        try:
            objects = self._adapter.list_objects()
            return {
                "success": True,
                "count": len(objects),
                "objects": objects
            }
        except Exception as e:
            logger.exception(f"列出对象失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_get_scene_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 get_scene_info 命令"""
        try:
            scene = bpy.context.scene
            return {
                "success": True,
                "scene_name": scene.name_full,
                "frame_current": scene.frame_current,
                "frame_start": scene.frame_start,
                "frame_end": scene.frame_end,
                "object_count": len(scene.objects),
                "selected_objects": [
                    obj.name_full for obj in bpy.context.selected_objects
                ],
                "active_object": (
                    bpy.context.active_object.name_full
                    if bpy.context.active_object else None
                )
            }
        except Exception as e:
            logger.exception(f"获取场景信息失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # === modify_mesh 工具 ===
    def handle_modify_mesh_boolean(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 modify_mesh_boolean 命令"""
        return self._adapter.modify_mesh_boolean(
            target_name=params.get("target_name"),
            operation=params.get("operation", "UNION"),
            object_name=params.get("object_name"),
            delete_other=params.get("delete_other", True)
        )

    # === 变形与雕刻工具 ===
    def handle_simple_deform(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 simple_deform 命令"""
        return self._adapter.simple_deform(
            object_name=params.get("object_name"),
            deform_type=params.get("deform_type", "BEND"),
            factor=params.get("factor", 0.5),
            angle=params.get("angle", 45),
            lock_x=params.get("lock_x", True),
            lock_y=params.get("lock_y", True),
            lock_z=params.get("lock_z", False)
        )

    def handle_mesh_sculpt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 mesh_sculpt 命令"""
        return self._adapter.mesh_sculpt(
            object_name=params.get("object_name"),
            operation=params.get("operation", "SMOOTH"),
            strength=params.get("strength", 0.5),
            radius=params.get("radius", 1.0),
            vertex_indices=params.get("vertex_indices")
        )

    # === 修改器工具 ===
    def handle_add_modifier(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 add_modifier 命令"""
        return self._adapter.add_modifier(
            object_name=params.get("object_name"),
            mod_type=params.get("mod_type", "SOLIDIFY"),
            name=params.get("name"),
            **params.get("kwargs", {})
        )

    def handle_apply_modifier(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 apply_modifier 命令"""
        return self._adapter.apply_modifier(
            object_name=params.get("object_name"),
            mod_name=params.get("mod_name", ""),
            apply_all=params.get("apply_all", False)
        )

    # === 文件导入导出 ===
    def handle_export_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 export_model 命令"""
        return self._adapter.export_model(
            file_path=params.get("file_path"),
            file_format=params.get("file_format", "STL"),
            selection_only=params.get("selection_only", False)
        )

    def handle_import_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 import_model 命令"""
        return self._adapter.import_model(
            file_path=params.get("file_path"),
            file_format=params.get("file_format", "STL")
        )

    # === 检查与修复 ===
    def handle_check_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 check_model 命令"""
        return self._adapter.check_model(
            object_name=params.get("object_name")
        )

    def handle_repair_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 repair_model 命令"""
        return self._adapter.repair_model(
            object_name=params.get("object_name"),
            recalc_normals=params.get("recalc_normals", True)
        )

    # === 项目文件管理 ===
    def handle_save_project(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 save_project 命令"""
        try:
            from pathlib import Path

            filepath = params.get('filepath')
            if not filepath:
                return {
                    "success": False,
                    "error": "缺少 filepath 参数"
                }

            # 安全检查
            filepath = str(Path(filepath).resolve())

            # 备份
            backup = params.get('backup', True)
            if backup:
                backup_path = filepath + ".bak"
                if Path(filepath).exists():
                    import shutil
                    shutil.copy2(filepath, backup_path)

            # 保存
            bpy.ops.wm.save_as_mainfile(
                filepath=filepath,
                compress=params.get('compress', True)
            )

            return {
                "success": True,
                "filepath": filepath,
                "backup_created": backup and Path(backup_path).exists()
            }
        except Exception as e:
            logger.exception(f"保存项目失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_open_project(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 open_project 命令"""
        try:
            from pathlib import Path

            filepath = params.get('filepath')
            if not filepath:
                return {
                    "success": False,
                    "error": "缺少 filepath 参数"
                }

            filepath = str(Path(filepath).resolve())
            if not Path(filepath).exists():
                return {
                    "success": False,
                    "error": f"文件不存在: {filepath}"
                }

            # 打开文件
            bpy.ops.wm.open_mainfile(filepath=filepath)

            return {
                "success": True,
                "filepath": filepath
            }
        except Exception as e:
            logger.exception(f"打开项目失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_state_snapshot(self) -> Dict[str, Any]:
        """获取状态快照"""
        return self._state_manager.take_snapshot()
