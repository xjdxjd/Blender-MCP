"""
Blender MCP Plugin - 操作按钮实现
"""

import bpy


class BLENDER_MCP_OT_StartServer(bpy.types.Operator):
    """启动 WebSocket 连接"""
    bl_idname = "blender_mcp.start_server"
    bl_label = "Connect"
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
    bl_label = "Disconnect"
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
    bl_label = "Ping Test"
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
                self.report({'INFO'}, f"Ping 成功，延迟: {latency:.2f} ms")
            else:
                props.last_error = result.get('error', 'Ping 失败') if result else 'Ping 失败'
                self.report({'ERROR'}, f"Ping 失败")
        except Exception as e:
            props.last_error = str(e)
            self.report({'ERROR'}, f"Ping 异常: {e}")

        return {'FINISHED'}
