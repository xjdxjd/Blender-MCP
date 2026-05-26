"""
Blender MCP Plugin - 插件入口
通过 MCP 协议连接 Blender 和 AI 助手
"""

from . import addon
from . import operators
from . import panels
from . import connection

bl_info = addon.bl_info

_classes = [
    operators.BLENDER_MCP_OT_StartServer,
    operators.BLENDER_MCP_OT_StopServer,
    operators.BLENDER_MCP_OT_PingTest,
    panels.BLENDER_MCP_PT_ConnectionPanel,
]

def register():
    """注册插件"""
    addon.register()

def unregister():
    """注销插件"""
    addon.unregister()
