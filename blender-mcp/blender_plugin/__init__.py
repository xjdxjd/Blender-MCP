"""
Blender MCP Plugin - 插件入口
通过 MCP 协议连接 Blender 和 AI 助手
"""

import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty, FloatProperty
from bpy.types import PropertyGroup

bl_info = {
    "name": "Blender MCP",
    "author": "Blender-mcp 项目团队",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Blender MCP",
    "description": "通过 MCP 协议连接 Blender 和 AI 助手",
    "category": "System",
    "support": "COMMUNITY",
    "doc_url": "https://github.com/blender-mcp/blender-mcp",
}


class BlenderMCPProperties(PropertyGroup):
    """插件属性组"""

    host: StringProperty(
        name="主机地址",
        default="127.0.0.1",
        description="MCP 服务 WebSocket 地址"
    )

    port: IntProperty(
        name="端口",
        default=8765,
        min=1024,
        max=65535,
        description="MCP 服务 WebSocket 端口"
    )

    auto_connect: BoolProperty(
        name="自动连接",
        default=False,
        description="启用插件时自动连接"
    )

    connection_status: EnumProperty(
        name="状态",
        items=[
            ('DISCONNECTED', '未连接', '未连接'),
            ('CONNECTING', '连接中', '正在连接'),
            ('CONNECTED', '已连接', '已连接'),
            ('RECONNECTING', '重连中', '重新连接中'),
            ('ERROR', '错误', '连接错误'),
        ],
        default='DISCONNECTED',
    )

    last_error: StringProperty(
        name="最后错误",
        default=""
    )

    latency_ms: FloatProperty(
        name="延迟",
        default=0.0,
        description="最近一次 ping 延迟（毫秒）"
    )


class BLENDER_MCP_OT_StartServer(bpy.types.Operator):
    """启动 WebSocket 连接"""
    bl_idname = "blender_mcp.start_server"
    bl_label = "连接"
    bl_description = "连接到 MCP 服务"

    def execute(self, context):
        props = context.scene.blender_mcp_props
        from . import connection
        client = connection.get_ws_client()

        try:
            props.connection_status = 'CONNECTING'
            props.last_error = ""
            success, error_msg = client.connect(
                host=props.host,
                port=props.port
            )
            if success:
                props.connection_status = 'CONNECTED'
                self.report({'INFO'}, f"已连接到 MCP 服务")
            else:
                props.connection_status = 'ERROR'
                props.last_error = error_msg or "连接失败"
                self.report({'ERROR'}, f"连接失败: {error_msg}")
        except Exception as e:
            props.connection_status = 'ERROR'
            props.last_error = str(e)
            self.report({'ERROR'}, f"连接异常: {e}")

        return {'FINISHED'}


class BLENDER_MCP_OT_StopServer(bpy.types.Operator):
    """断开 WebSocket 连接"""
    bl_idname = "blender_mcp.stop_server"
    bl_label = "断开连接"
    bl_description = "断开与 MCP 服务的连接"

    def execute(self, context):
        props = context.scene.blender_mcp_props
        from . import connection
        client = connection.get_ws_client()
        try:
            client.disconnect()
            props.connection_status = 'DISCONNECTED'
            props.last_error = ""
            self.report({'INFO'}, "已断开连接")
        except Exception as e:
            self.report({'ERROR'}, f"断开失败: {e}")

        return {'FINISHED'}


class BLENDER_MCP_OT_PingTest(bpy.types.Operator):
    """执行 ping 测试"""
    bl_idname = "blender_mcp.ping_test"
    bl_label = "Ping 测试"
    bl_description = "测试与 MCP 服务的连接延迟"

    def execute(self, context):
        props = context.scene.blender_mcp_props
        from . import connection
        client = connection.get_ws_client()

        try:
            result = client.ping()
            if result and result.get('success'):
                latency = result.get('latency_ms', 0)
                props.latency_ms = latency
                self.report({'INFO'}, f"Ping 成功，延迟: {latency:.2f} 毫秒")
            else:
                props.last_error = result.get('error', 'Ping 失败') if result else 'Ping 失败'
                self.report({'ERROR'}, f"Ping 失败")
        except Exception as e:
            props.last_error = str(e)
            self.report({'ERROR'}, f"Ping 异常: {e}")

        return {'FINISHED'}


class BLENDER_MCP_PT_ConnectionPanel(bpy.types.Panel):
    """Blender MCP 连接管理面板"""
    bl_label = "Blender MCP"
    bl_idname = "BLENDER_MCP_PT_connection"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Blender MCP"

    def draw(self, context):
        layout = self.layout
        props = context.scene.blender_mcp_props

        layout.label(text="连接状态：")

        status_color_map = {
            'DISCONNECTED': ('SEQUENCE_COLOR_01', '未连接'),
            'CONNECTING': ('SEQUENCE_COLOR_09', '连接中...'),
            'CONNECTED': ('SEQUENCE_COLOR_04', '已连接'),
            'RECONNECTING': ('SEQUENCE_COLOR_09', '重连中...'),
            'ERROR': ('SEQUENCE_COLOR_01', '错误')
        }

        icon, status_text = status_color_map.get(props.connection_status)
        row = layout.row()
        row.label(text=status_text, icon=icon)

        layout.separator()
        box = layout.box()
        box.label(text="服务器设置", icon='PREFERENCES')
        box.prop(props, "host")
        box.prop(props, "port")
        box.prop(props, "auto_connect")

        layout.separator()
        btn_row = layout.row(align=True)
        if props.connection_status == 'CONNECTED':
            btn_row.operator("blender_mcp.stop_server", text="断开连接", icon='X')
        else:
            btn_row.operator("blender_mcp.start_server", text="连接", icon='PLAY')

        test_row = layout.row()
        test_row.enabled = props.connection_status == 'CONNECTED'
        test_row.operator("blender_mcp.ping_test", text="Ping 测试", icon='CONSOLE')

        if props.connection_status == 'CONNECTED':
            latency_row = layout.row()
            latency_row.label(text=f"延迟：{props.latency_ms:.2f} 毫秒")

        if props.last_error:
            error_box = layout.box()
            error_box.alert = True
            error_box.label(text="错误：", icon='ERROR')
            error_row = error_box.row()
            error_row.label(text=props.last_error, translate=False)


_classes = [
    BlenderMCPProperties,
    BLENDER_MCP_OT_StartServer,
    BLENDER_MCP_OT_StopServer,
    BLENDER_MCP_OT_PingTest,
    BLENDER_MCP_PT_ConnectionPanel,
]


def register():
    """注册插件"""
    for cls in _classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.blender_mcp_props = bpy.props.PointerProperty(
        type=BlenderMCPProperties
    )

    print("Blender MCP 插件已注册")


def unregister():
    """注销插件"""
    from . import connection
    ws_client = connection.get_ws_client()
    if ws_client and ws_client.is_connected:
        ws_client.disconnect()

    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.blender_mcp_props

    print("Blender MCP 插件已注销")
