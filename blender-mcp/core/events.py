"""
事件通知系统 - 阶段三核心模块
负责 Blender 场景事件的监听、节流和分发
"""

import time
import logging
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, asdict
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型枚举"""
    OBJECT_ADDED = "OBJECT_ADDED"
    OBJECT_REMOVED = "OBJECT_REMOVED"
    OBJECT_MODIFIED = "OBJECT_MODIFIED"
    OBJECT_SELECTED = "OBJECT_SELECTED"
    SCENE_CHANGED = "SCENE_CHANGED"
    FRAME_CHANGED = "FRAME_CHANGED"
    MODE_CHANGED = "MODE_CHANGED"
    FILE_SAVED = "FILE_SAVED"
    MESH_MODIFIED = "MESH_MODIFIED"
    CUSTOM = "CUSTOM"


@dataclass
class Event:
    """事件数据类"""
    event_type: EventType
    timestamp: float
    source: Optional[str] = None
    data: Dict[str, Any] = None
    object_name: Optional[str] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.timestamp is None:
            self.timestamp = time.time()


class EventThrottle:
    """
    事件节流器，防止事件过于频繁触发
    
    使用场景：
    - 防抖 (debounce): 在事件停止后等待一段时间再触发
    - 节流 (throttle): 限制事件触发频率
    """
    
    def __init__(
        self,
        throttle_ms: float = 100.0,
        debounce_ms: float = 0.0,
        max_wait_ms: float = 1000.0
    ):
        """
        初始化节流器
        
        Args:
            throttle_ms: 节流间隔（毫秒），在此间隔内只触发一次
            debounce_ms: 防抖延迟（毫秒），事件停止后等待此时间才触发
            max_wait_ms: 最大等待时间（毫秒），防止防抖无限延迟
        """
        self.throttle_ms = throttle_ms
        self.debounce_ms = debounce_ms
        self.max_wait_ms = max_wait_ms
        
        self._last_trigger_time: Dict[str, float] = {}
        self._pending_events: Dict[str, Dict[str, Any]] = {}
        self._pending_timers: Dict[str, Any] = {}
        self._first_trigger_time: Dict[str, float] = {}
    
    def should_trigger(self, event_key: str, current_time: float = None) -> bool:
        """
        检查是否应该触发事件
        
        Args:
            event_key: 事件标识符
            current_time: 当前时间戳（可选）
        
        Returns:
            是否应该立即触发
        """
        if current_time is None:
            current_time = time.time()
        
        last_time = self._last_trigger_time.get(event_key, 0)
        
        # 节流检查
        if self.throttle_ms > 0:
            if current_time - last_time < self.throttle_ms / 1000.0:
                return False
        
        return True
    
    def record_trigger(self, event_key: str, current_time: float = None):
        """
        记录事件触发时间
        
        Args:
            event_key: 事件标识符
            current_time: 当前时间戳（可选）
        """
        if current_time is None:
            current_time = time.time()
        
        self._last_trigger_time[event_key] = current_time
    
    def reset(self, event_key: Optional[str] = None):
        """
        重置节流器状态
        
        Args:
            event_key: 事件标识符（None 表示重置所有）
        """
        if event_key:
            self._last_trigger_time.pop(event_key, None)
            self._pending_events.pop(event_key, None)
            self._first_trigger_time.pop(event_key, None)
        else:
            self._last_trigger_time.clear()
            self._pending_events.clear()
            self._first_trigger_time.clear()


class EventBus:
    """
    事件总线，负责事件的订阅和发布
    
    特性：
    - 支持多个监听器订阅同一事件
    - 支持事件节流和防抖
    - 支持异步事件处理
    """
    
    def __init__(self):
        self._listeners: Dict[EventType, List[Callable]] = {}
        self._throttles: Dict[EventType, EventThrottle] = {}
        self._event_queue: List[Event] = []
        self._is_processing = False
        self._enabled = True
    
    def subscribe(
        self,
        event_type: EventType,
        callback: Callable,
        throttle_ms: float = 0.0,
        debounce_ms: float = 0.0
    ):
        """
        订阅事件
        
        Args:
            event_type: 事件类型
            callback: 回调函数
            throttle_ms: 节流间隔（毫秒）
            debounce_ms: 防抖延迟（毫秒）
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        
        self._listeners[event_type].append(callback)
        
        if throttle_ms > 0 or debounce_ms > 0:
            self._throttles[event_type] = EventThrottle(
                throttle_ms=throttle_ms,
                debounce_ms=debounce_ms
            )
    
    def unsubscribe(self, event_type: EventType, callback: Callable):
        """
        取消订阅
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        if event_type in self._listeners:
            try:
                self._listeners[event_type].remove(callback)
            except ValueError:
                pass
    
    def publish(self, event: Event):
        """
        发布事件
        
        Args:
            event: 事件对象
        """
        if not self._enabled:
            return
        
        # 检查节流
        throttle = self._throttles.get(event.event_type)
        if throttle:
            event_key = f"{event.event_type.value}_{event.object_name or 'global'}"
            if not throttle.should_trigger(event_key, event.timestamp):
                return
            throttle.record_trigger(event_key, event.timestamp)
        
        # 添加到队列
        self._event_queue.append(event)
        
        # 立即处理（同步方式）
        self._process_queue()
    
    def _process_queue(self):
        """处理事件队列"""
        if self._is_processing:
            return
        
        self._is_processing = True
        
        while self._event_queue:
            event = self._event_queue.pop(0)
            self._dispatch(event)
        
        self._is_processing = False
    
    def _dispatch(self, event: Event):
        """
        分发事件给所有监听器
        
        Args:
            event: 事件对象
        """
        listeners = self._listeners.get(event.event_type, [])
        
        for callback in listeners:
            try:
                callback(event)
            except Exception as e:
                logger.exception(f"事件监听器执行失败: {e}")
    
    def clear(self):
        """清除所有监听器和事件"""
        self._listeners.clear()
        self._throttles.clear()
        self._event_queue.clear()
    
    def disable(self):
        """禁用事件总线"""
        self._enabled = False
    
    def enable(self):
        """启用事件总线"""
        self._enabled = True


class BlenderEventHandlers:
    """
    Blender 应用事件处理器集成
    
    负责将 Blender 的 app.handlers 事件转换为 EventBus 事件
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._registered_handlers: Set[str] = set()
        self._last_mode: Optional[str] = None
        self._last_frame: Optional[int] = None
    
    def register_handlers(self):
        """注册所有 Blender 事件处理器"""
        import bpy
        
        # 避免重复注册
        if self._registered_handlers:
            return
        
        try:
            # 注册帧变更处理器
            bpy.app.handlers.frame_change_post.append(self._on_frame_change)
            self._registered_handlers.add("frame_change_post")
            
            # 注册文件保存处理器
            bpy.app.handlers.save_post.append(self._on_file_save)
            self._registered_handlers.add("save_post")
            
            # 注册加载完成处理器
            bpy.app.handlers.load_post.append(self._on_load_post)
            self._registered_handlers.add("load_post")
            
            # 初始化状态
            if bpy.context.scene:
                self._last_frame = bpy.context.scene.frame_current
                self._last_mode = bpy.context.mode
            
            logger.info("Blender 事件处理器已注册")
        except Exception as e:
            logger.exception(f"注册 Blender 事件处理器失败: {e}")
    
    def unregister_handlers(self):
        """取消注册所有事件处理器"""
        import bpy
        
        try:
            if "frame_change_post" in self._registered_handlers:
                try:
                    bpy.app.handlers.frame_change_post.remove(self._on_frame_change)
                except ValueError:
                    pass
            
            if "save_post" in self._registered_handlers:
                try:
                    bpy.app.handlers.save_post.remove(self._on_file_save)
                except ValueError:
                    pass
            
            if "load_post" in self._registered_handlers:
                try:
                    bpy.app.handlers.load_post.remove(self._on_load_post)
                except ValueError:
                    pass
            
            self._registered_handlers.clear()
            logger.info("Blender 事件处理器已注销")
        except Exception as e:
            logger.exception(f"注销 Blender 事件处理器失败: {e}")
    
    def _on_frame_change(self, scene, depsgraph=None):
        """帧变更回调"""
        try:
            current_frame = scene.frame_current
            if current_frame != self._last_frame:
                self.event_bus.publish(Event(
                    event_type=EventType.FRAME_CHANGED,
                    timestamp=time.time(),
                    source="BlenderEventHandlers",
                    data={
                        "old_frame": self._last_frame,
                        "new_frame": current_frame
                    }
                ))
                self._last_frame = current_frame
        except Exception as e:
            logger.exception(f"帧变更处理失败: {e}")
    
    def _on_file_save(self, dummy):
        """文件保存回调"""
        try:
            import bpy
            self.event_bus.publish(Event(
                event_type=EventType.FILE_SAVED,
                timestamp=time.time(),
                source="BlenderEventHandlers",
                data={
                    "file_path": bpy.data.filepath
                }
            ))
        except Exception as e:
            logger.exception(f"文件保存处理失败: {e}")
    
    def _on_load_post(self, dummy):
        """文件加载完成回调"""
        try:
            import bpy
            self.event_bus.publish(Event(
                event_type=EventType.SCENE_CHANGED,
                timestamp=time.time(),
                source="BlenderEventHandlers",
                data={
                    "action": "loaded",
                    "file_path": bpy.data.filepath
                }
            ))
        except Exception as e:
            logger.exception(f"文件加载处理失败: {e}")
    
    def notify_object_added(self, object_name: str):
        """通知对象已添加"""
        self.event_bus.publish(Event(
            event_type=EventType.OBJECT_ADDED,
            timestamp=time.time(),
            source="BlenderEventHandlers",
            object_name=object_name,
            data={"name": object_name}
        ))
    
    def notify_object_removed(self, object_name: str):
        """通知对象已移除"""
        self.event_bus.publish(Event(
            event_type=EventType.OBJECT_REMOVED,
            timestamp=time.time(),
            source="BlenderEventHandlers",
            object_name=object_name,
            data={"name": object_name}
        ))
    
    def notify_object_modified(self, object_name: str, changes: Dict[str, Any] = None):
        """通知对象已修改"""
        self.event_bus.publish(Event(
            event_type=EventType.OBJECT_MODIFIED,
            timestamp=time.time(),
            source="BlenderEventHandlers",
            object_name=object_name,
            data=changes or {}
        ))
    
    def notify_mesh_modified(self, object_name: str):
        """通知网格已修改"""
        self.event_bus.publish(Event(
            event_type=EventType.MESH_MODIFIED,
            timestamp=time.time(),
            source="BlenderEventHandlers",
            object_name=object_name,
            data={"name": object_name}
        ))


# 全局实例
_global_event_bus: Optional[EventBus] = None
_global_event_handlers: Optional[BlenderEventHandlers] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


def get_event_handlers() -> BlenderEventHandlers:
    """获取全局事件处理器"""
    global _global_event_handlers
    if _global_event_handlers is None:
        _global_event_handlers = BlenderEventHandlers(get_event_bus())
    return _global_event_handlers


def init_event_system():
    """初始化事件系统"""
    bus = get_event_bus()
    handlers = get_event_handlers()
    handlers.register_handlers()
    return bus, handlers


def shutdown_event_system():
    """关闭事件系统"""
    global _global_event_bus, _global_event_handlers
    if _global_event_handlers:
        _global_event_handlers.unregister_handlers()
    if _global_event_bus:
        _global_event_bus.clear()
    _global_event_handlers = None
    _global_event_bus = None
