"""
Blender MCP Plugin - UI 面板实现
"""

import bpy


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

        layout.label(text="Connection Status:")

        status_color_map = {
            'DISCONNECTED': ('SEQUENCE_COLOR_01', 'Disconnected'),
            'CONNECTING': ('SEQUENCE_COLOR_09', 'Connecting...'),
            'CONNECTED': ('SEQUENCE_COLOR_04', 'Connected'),
            'RECONNECTING': ('SEQUENCE_COLOR_09', 'Reconnecting...'),
            'ERROR': ('SEQUENCE_COLOR_01', 'Error')
        }

        icon, status_text = status_color_map.get(props.connection_status)
        row = layout.row()
        row.label(text=status_text, icon=icon)

        # 服务器配置
        layout.separator()
        box = layout.box()
        box.label(text="Server Settings", icon='PREFERENCES')
        box.prop(props, "host")
        box.prop(props, "port")
        box.prop(props, "auto_connect")

        # 连接控制
        layout.separator()
        btn_row = layout.row(align=True)
        if props.connection_status == 'CONNECTED':
            btn_row.operator("blender_mcp.stop_server", text="Disconnect", icon='X')
        else:
            btn_row.operator("blender_mcp.start_server", text="Connect", icon='PLAY')

        # 测试功能
        test_row = layout.row()
        test_row.enabled = props.connection_status == 'CONNECTED'
        test_row.operator("blender_mcp.ping_test", text="Ping Test", icon='CONSOLE')

        # 延迟显示
        if props.connection_status == 'CONNECTED':
            latency_row = layout.row()
            latency_row.label(text=f"Latency: {props.latency_ms:.2f} ms")

        # 错误信息
        if props.last_error:
            error_box = layout.box()
            error_box.alert = True
            error_box.label(text="Error:", icon='ERROR')
            error_row = error_box.row()
            error_row.label(text=props.last_error, translate=False)
