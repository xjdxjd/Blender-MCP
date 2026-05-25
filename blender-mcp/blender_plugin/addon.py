"""
Blender MCP Plugin - 主插件入口
"""

import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty, FloatProperty
from bpy.types import PropertyGroup

from . import operators
from . import panels

# 插件元数据
bl_info = {
    "name": "Blender MCP",
    "author": "Blender-mcp Project",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Blender MCP",
    "description": "Connect Blender to AI assistants via MCP protocol",
    "category": "System",
    "support": "COMMUNITY",
    "doc_url": "https://github.com/blender-mcp/blender-mcp",
}

# 需要注册的类列表
_classes = [
    operators.BLENDER_MCP_OT_StartServer,
    operators.BLENDER_MCP_OT_StopServer,
    operators.BLENDER_MCP_OT_PingTest,
    panels.BLENDER_MCP_PT_ConnectionPanel,
]


class BlenderMCPProperties(PropertyGroup):
    """插件属性组，存储在 bpy.types.Scene 上。"""

    host: StringProperty(
        name="Host",
        default="127.0.0.1",
        description="MCP 服务 WebSocket 地址"
    )

    port: IntProperty(
        name="Port",
        default=8765,
        min=1024,
        max=65535,
        description="MCP 服务 WebSocket 端口"
    )

    auto_connect: BoolProperty(
        name="Auto Connect",
        default=False,
        description="启用插件时自动连接"
    )

    connection_status: EnumProperty(
        name="Status",
        items=[
            ('DISCONNECTED', 'Disconnected', '未连接'),
            ('CONNECTING', 'Connecting', '连接中'),
            ('CONNECTED', 'Connected', '已连接'),
            ('RECONNECTING', 'Reconnecting', '重连中'),
            ('ERROR', 'Error', '连接错误'),
        ],
        default='DISCONNECTED',
    )

    last_error: StringProperty(
        name="Last Error",
        default=""
    )

    latency_ms: FloatProperty(
        name="Latency",
        default=0.0,
        description="最近一次 ping 延迟（毫秒）"
    )


def register():
    """注册插件所有类和属性。"""
    for cls in _classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.blender_mcp_props = bpy.props.PointerProperty(
        type=BlenderMCPProperties
    )

    print("Blender MCP 插件已注册")


def unregister():
    """注销插件所有类和属性，清理资源。"""
    from . import connection
    ws_client = connection.get_ws_client()
    if ws_client and ws_client.is_connected:
        ws_client.disconnect()

    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.blender_mcp_props

    print("Blender MCP 插件已注销")
