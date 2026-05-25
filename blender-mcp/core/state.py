"""
状态管理器 - 阶段三核心模块
负责管理 Blender 场景状态快照和增量同步
"""

import json
import time
import hashlib
import struct
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict, field
from collections import OrderedDict
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
    mesh_hash: Optional[str] = None


@dataclass
class SceneSnapshot:
    """场景快照"""
    timestamp: float
    frame_current: int
    object_count: int
    objects: List[ObjectSnapshot]
    mesh_hash: str
    version: int = 1


class CacheStrategy(OrderedDict):
    """
    LRU 缓存策略
    
    用于缓存对象的哈希值，避免重复计算
    """
    
    def __init__(self, max_size: int = 100):
        super().__init__()
        self.max_size = max_size
    
    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.max_size:
            self.popitem(last=False)


class StateManager:
    """场景状态管理器，提供快照、对比和增量同步"""

    def __init__(self):
        self._current_snapshot: Optional[SceneSnapshot] = None
        self._snapshots: List[SceneSnapshot] = []
        self._max_snapshots = 10
        self._version = 1
        
        # 性能优化：缓存和采样
        self._mesh_hash_cache = CacheStrategy(max_size=100)
        self._sample_rate = 0.1  # 采样率：10% 顶点采样
        self._last_cache_time = 0.0
        self._cache_ttl = 0.5  # 缓存有效期：0.5 秒

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
                
                # 计算单个对象的网格哈希（如果是网格对象）
                obj_mesh_hash = None
                if obj.type == 'MESH':
                    obj_mesh_hash = self._compute_single_mesh_hash(obj)

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
                    materials=materials,
                    mesh_hash=obj_mesh_hash
                )
                objects.append(snapshot)

            # 计算场景总网格数据哈希（使用采样优化）
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
        """计算场景网格数据的哈希值（使用采样优化）"""
        current_time = time.time()
        
        # 检查是否使用缓存
        cache_key = "scene_mesh_hash"
        if cache_key in self._mesh_hash_cache:
            cached_hash, cached_time = self._mesh_hash_cache[cache_key]
            if current_time - cached_time < self._cache_ttl:
                return cached_hash
        
        hasher = hashlib.sha256()

        for obj in scene.objects:
            if obj.type == 'MESH':
                mesh = obj.data
                obj_hash = self._compute_single_mesh_hash(obj)
                hasher.update(obj.name.encode())
                hasher.update(obj_hash.encode())

        result_hash = hasher.hexdigest()[:16]
        
        # 更新缓存
        self._mesh_hash_cache[cache_key] = (result_hash, current_time)
        
        return result_hash

    def _compute_single_mesh_hash(self, obj: bpy.types.Object) -> str:
        """
        计算单个对象的网格哈希值（使用顶点采样优化）"""
        current_time = time.time()
        
        # 检查对象级缓存
        cache_key = f"mesh_{obj.name_full}"
        if cache_key in self._mesh_hash_cache:
            cached_hash, cached_time = self._mesh_hash_cache[cache_key]
            if current_time - cached_time < self._cache_ttl:
                return cached_hash
        
        hasher = hashlib.sha256()
        mesh = obj.data
        
        # 基础元数据
        hasher.update(str(len(mesh.vertices)).encode())
        hasher.update(str(len(mesh.edges)).encode())
        hasher.update(str(len(mesh.polygons)).encode())
        
        # 使用顶点采样
        if len(mesh.vertices) > 0:
            sample_step = max(1, int(1.0 / self._sample_rate))
            for i in range(0, len(mesh.vertices), sample_step):
                v = mesh.vertices[i]
                # 使用 struct 打包浮点数，提高哈希速度
                hasher.update(struct.pack('<3f', v.co[0], v.co[1], v.co[2]))
        
        result_hash = hasher.hexdigest()[:12]
        
        # 更新缓存
        self._mesh_hash_cache[cache_key] = (result_hash, current_time)
        
        return result_hash

    def _has_object_changed(
        self,
        obj1: ObjectSnapshot,
        obj2: ObjectSnapshot
    ) -> bool:
        """比较两个对象快照是否有变化"""
        tolerance = 1e-6

        # 优先比较网格哈希（快速判断）
        if obj1.mesh_hash is not None and obj2.mesh_hash is not None:
            if obj1.mesh_hash != obj2.mesh_hash:
                return True

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
        self._mesh_hash_cache.clear()
    
    def clear_cache(self):
        """清空缓存"""
        self._mesh_hash_cache.clear()
    
    def set_sample_rate(self, rate: float):
        """设置采样率"""
        self._sample_rate = max(0.01, min(1.0, rate))
