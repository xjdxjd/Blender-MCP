"""
状态管理器 - 阶段三核心模块
负责管理 Blender 场景状态快照和增量同步
"""

import json
import time
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict, field
import bpy


@dataclass
class ObjectSnapshot:
    """对象快照"""
    name: str
    type: str
    location: Tuple[float, float, float]
    rotation: Tuple[float, float, float]
    scale: Tuple[float, float, float]
    visible: bool
    locked: bool
    parent: Optional[str] = None
    modifiers: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)


@dataclass
class SceneSnapshot:
    """场景快照"""
    timestamp: float
    frame_current: int
    object_count: int
    objects: List[ObjectSnapshot]
    mesh_hash: str
    version: int = 1


class StateManager:
    """场景状态管理器，提供快照、对比和增量同步"""

    def __init__(self):
        self._current_snapshot: Optional[SceneSnapshot] = None
        self._snapshots: List[SceneSnapshot] = []
        self._max_snapshots = 10
        self._version = 1

    def take_snapshot(self) -> Dict[str, Any]:
        """获取当前场景快照"""
        try:
            scene = bpy.context.scene
            objects = []

            for obj in scene.objects:
                modifiers = [
                    mod.name for mod in obj.modifiers
                    if mod.type != 'ARMATURE'
                ]

                materials = [
                    mat.name for mat in obj.data.materials
                    if mat is not None
                ] if hasattr(obj.data, 'materials') else []

                snapshot = ObjectSnapshot(
                    name=obj.name_full,
                    type=obj.type,
                    location=tuple(obj.location),
                    rotation=tuple(r for r in obj.rotation_euler),
                    scale=tuple(obj.scale),
                    visible=obj.visible_get(),
                    locked=obj.hide_viewport,
                    parent=obj.parent.name_full if obj.parent else None,
                    modifiers=modifiers,
                    materials=materials
                )
                objects.append(snapshot)

            # 计算网格数据哈希
            mesh_hash = self._compute_mesh_hash(scene)

            snapshot = SceneSnapshot(
                timestamp=time.time(),
                frame_current=scene.frame_current,
                object_count=len(objects),
                objects=objects,
                mesh_hash=mesh_hash,
                version=self._version
            )

            self._current_snapshot = snapshot
            self._snapshots.append(snapshot)

            # 限制快照数量
            if len(self._snapshots) > self._max_snapshots:
                self._snapshots.pop(0)

            return {
                "success": True,
                "timestamp": snapshot.timestamp,
                "frame_current": snapshot.frame_current,
                "object_count": snapshot.object_count,
                "mesh_hash": snapshot.mesh_hash,
                "version": snapshot.version
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_changes(self) -> Dict[str, Any]:
        """获取相对于上一个快照的变化"""
        if not self._current_snapshot or len(self._snapshots) < 2:
            return {
                "has_changes": False,
                "changes": {}
            }

        previous_snapshot = self._snapshots[-2]
        current_snapshot = self._snapshots[-1]

        # 比较对象列表
        prev_names = {obj.name for obj in previous_snapshot.objects}
        curr_names = {obj.name for obj in current_snapshot.objects}

        added = list(curr_names - prev_names)
        removed = list(prev_names - curr_names)
        existing = list(curr_names & prev_names)

        # 检查现有对象的变化
        modified = []
        for name in existing:
            prev_obj = next(
                obj for obj in previous_snapshot.objects
                if obj.name == name
            )
            curr_obj = next(
                obj for obj in current_snapshot.objects
                if obj.name == name
            )

            if self._has_object_changed(prev_obj, curr_obj):
                modified.append(name)

        # 生成变更报告
        changes = {
            "added": added,
            "removed": removed,
            "modified": modified,
            "total_changes": len(added) + len(removed) + len(modified)
        }

        return {
            "has_changes": len(added) + len(removed) + len(modified) > 0,
            "changes": changes,
            "timestamp": current_snapshot.timestamp
        }

    def _compute_mesh_hash(self, scene: bpy.types.Scene) -> str:
        """计算场景网格数据的哈希值（用于快速变化检测）"""
        hasher = hashlib.sha256()

        for obj in scene.objects:
            if obj.type == 'MESH':
                mesh = obj.data
                hasher.update(obj.name.encode())
                hasher.update(str(mesh.total_vert_lang).encode())
                hasher.update(str(mesh.total_edge_lang).encode())
                hasher.update(str(mesh.total_loop_lang).encode())

        return hasher.hexdigest()[:16]

    def _has_object_changed(
        self,
        obj1: ObjectSnapshot,
        obj2: ObjectSnapshot
    ) -> bool:
        """比较两个对象快照是否有变化"""
        tolerance = 1e-6

        # 比较位置
        if any(
            abs(a - b) > tolerance
            for a, b in zip(obj1.location, obj2.location)
        ):
            return True

        # 比较旋转
        if any(
            abs(a - b) > tolerance
            for a, b in zip(obj1.rotation, obj2.rotation)
        ):
            return True

        # 比较缩放
        if any(
            abs(a - b) > tolerance
            for a, b in zip(obj1.scale, obj2.scale)
        ):
            return True

        # 比较可见性
        if obj1.visible != obj2.visible:
            return True

        return False

    def get_scene_diff(self) -> Dict[str, Any]:
        """获取场景差异（详细版本）"""
        changes = self.get_changes()
        if not changes.get("has_changes"):
            return changes

        result = changes.copy()

        # 添加已修改对象的详细信息
        modified_details = []
        for name in changes["changes"]["modified"]:
            obj = bpy.data.objects.get(name)
            if obj:
                modified_details.append({
                    "name": obj.name_full,
                    "type": obj.type,
                    "location": tuple(obj.location),
                    "rotation": tuple(r for r in obj.rotation_euler),
                    "scale": tuple(obj.scale)
                })

        result["modified_details"] = modified_details
        return result

    def increment_version(self):
        """递增版本号"""
        self._version += 1

    def reset(self):
        """重置状态管理器"""
        self._current_snapshot = None
        self._snapshots.clear()
        self._version = 1
