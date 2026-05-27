# Blender MCP Plugin
# 通过 MCP 协议连接 Blender 和 AI 助手

import bpy
from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import (
    StringProperty,
    IntProperty,
    BoolProperty,
    EnumProperty,
    FloatProperty,
    PointerProperty,
)

bl_info = {
    "name": "Blender MCP",
    "author": "Blender-mcp",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Blender MCP",
    "description": "通过 MCP 协议连接 Blender 和 AI 助手",
    "category": "System",
    "support": "COMMUNITY",
}


class BlenderMCPProperties(PropertyGroup):
    host: StringProperty(
        name="主机地址",
        default="127.0.0.1",
        description="MCP 服务地址"
    )
    port: IntProperty(
        name="端口",
        default=8765,
        min=1024,
        max=65535,
        description="MCP 服务端口"
    )
    auto_connect: BoolProperty(
        name="自动连接",
        default=False,
        description="启用时自动连接"
    )
    connection_status: EnumProperty(
        name="状态",
        items=[
            ('DISCONNECTED', '未连接', ''),
            ('CONNECTING', '连接中', ''),
            ('CONNECTED', '已连接', ''),
            ('RECONNECTING', '重连中', ''),
            ('ERROR', '错误', ''),
        ],
        default='DISCONNECTED',
    )
    last_error: StringProperty(name="错误信息", default="")
    latency_ms: FloatProperty(name="延迟(毫秒)", default=0.0)


class BLENDER_MCP_OT_StartServer(Operator):
    bl_idname = "blender_mcp.start_server"
    bl_label = "连接"
    bl_description = "连接到 MCP 服务"

    def execute(self, context):
        props = context.scene.blender_mcp_props
        from . import connection
        ws = connection.get_ws_client()
        try:
            props.connection_status = 'CONNECTING'
            props.last_error = ""
            ok, err = ws.connect(props.host, props.port)
            if ok:
                props.connection_status = 'CONNECTED'
                self.report({'INFO'}, "已连接到 MCP 服务")
            else:
                props.connection_status = 'ERROR'
                props.last_error = err or "连接失败"
                self.report({'ERROR'}, f"连接失败: {err}")
        except Exception as e:
            props.connection_status = 'ERROR'
            props.last_error = str(e)
            self.report({'ERROR'}, f"连接异常: {e}")
        return {'FINISHED'}


class BLENDER_MCP_OT_StopServer(Operator):
    bl_idname = "blender_mcp.stop_server"
    bl_label = "断开连接"
    bl_description = "断开与 MCP 服务的连接"

    def execute(self, context):
        props = context.scene.blender_mcp_props
        from . import connection
        ws = connection.get_ws_client()
        try:
            ws.disconnect()
            props.connection_status = 'DISCONNECTED'
            props.last_error = ""
            self.report({'INFO'}, "已断开连接")
        except Exception as e:
            self.report({'ERROR'}, f"断开失败: {e}")
        return {'FINISHED'}


class BLENDER_MCP_OT_PingTest(Operator):
    bl_idname = "blender_mcp.ping_test"
    bl_label = "Ping 测试"
    bl_description = "测试与 MCP 服务的延迟"

    def execute(self, context):
        props = context.scene.blender_mcp_props
        from . import connection
        ws = connection.get_ws_client()
        try:
            result = ws.ping()
            if result and result.get('success'):
                props.latency_ms = result.get('latency_ms', 0)
                self.report({'INFO'}, f"Ping: {props.latency_ms:.1f}ms")
            else:
                props.last_error = "Ping 失败"
                self.report({'ERROR'}, "Ping 失败")
        except Exception as e:
            props.last_error = str(e)
            self.report({'ERROR'}, f"Ping 异常: {e}")
        return {'FINISHED'}


class BLENDER_MCP_PT_ConnectionPanel(Panel):
    bl_label = "Blender MCP"
    bl_idname = "BLENDER_MCP_PT_connection"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Blender MCP"

    def draw(self, context):
        layout = self.layout
        p = context.scene.blender_mcp_props

        layout.label(text="连接状态：")
        status_map = {
            'DISCONNECTED':  '未连接',
            'CONNECTING':    '连接中...',
            'CONNECTED':     '已连接',
            'RECONNECTING':  '重连中...',
            'ERROR':         '错误',
        }
        layout.label(text=status_map.get(p.connection_status, '未知'))

        layout.separator()
        box = layout.box()
        box.label(text="服务器设置", icon='PREFERENCES')
        box.prop(p, "host")
        box.prop(p, "port")
        box.prop(p, "auto_connect")

        layout.separator()
        row = layout.row(align=True)
        if p.connection_status == 'CONNECTED':
            row.operator("blender_mcp.stop_server", text="断开连接", icon='X')
        else:
            row.operator("blender_mcp.start_server", text="连接", icon='PLAY')

        row2 = layout.row()
        row2.enabled = (p.connection_status == 'CONNECTED')
        row2.operator("blender_mcp.ping_test", text="Ping 测试")

        if p.connection_status == 'CONNECTED':
            layout.label(text=f"延迟: {p.latency_ms:.2f} 毫秒")

        if p.last_error:
            box2 = layout.box()
            box2.alert = True
            box2.label(text=f"错误: {p.last_error}")


def register():
    bpy.utils.register_class(BlenderMCPProperties)
    bpy.utils.register_class(BLENDER_MCP_OT_StartServer)
    bpy.utils.register_class(BLENDER_MCP_OT_StopServer)
    bpy.utils.register_class(BLENDER_MCP_OT_PingTest)
    bpy.utils.register_class(BLENDER_MCP_PT_ConnectionPanel)
    bpy.types.Scene.blender_mcp_props = PointerProperty(type=BlenderMCPProperties)
    print("Blender MCP 插件已注册")


def unregister():
    from . import connection
    ws = connection.get_ws_client()
    if ws and ws.is_connected:
        ws.disconnect()

    bpy.utils.unregister_class(BLENDER_MCP_PT_ConnectionPanel)
    bpy.utils.unregister_class(BLENDER_MCP_OT_PingTest)
    bpy.utils.unregister_class(BLENDER_MCP_OT_StopServer)
    bpy.utils.unregister_class(BLENDER_MCP_OT_StartServer)
    bpy.utils.unregister_class(BlenderMCPProperties)
    del bpy.types.Scene.blender_mcp_props
    print("Blender MCP 插件已注销")