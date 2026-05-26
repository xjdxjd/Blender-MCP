import asyncio
import json
import logging
import sys
import time
import websockets
from typing import Dict, Any, Optional, Callable, Awaitable
from pathlib import Path

# 导入项目模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import ConfigManager
from mcp_server.tools import ToolRegistry, generate_message_id, iso_now, MCPError, InternalError
from mcp_server.schemas import ConnectionState, ReconnectConfig

logger = logging.getLogger(__name__)


class StdioTransport:
    """stdio 通信层，处理消息的读取、解析、分发和响应。"""

    def __init__(self, message_handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]):
        """
        Args:
            message_handler: 异步消息处理回调，接收请求字典，返回响应字典
        """
        self._message_handler = message_handler
        self._running = False
        self.MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB

    async def read_message(self) -> Optional[Dict[str, Any]]:
        """
        从 stdin 读取一行 JSON 消息。

        Returns:
            解析后的请求字典，EOF 时返回 None

        Raises:
            json.JSONDecodeError: JSON 格式无效
            ValueError: 消息超过最大大小限制 (10MB)
        """
        loop = asyncio.get_event_loop()
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                return None

            line = line.rstrip('\n')

            if len(line) > self.MAX_MESSAGE_SIZE:
                logger.warning(f"消息大小超出限制 ({len(line)} > {self.MAX_MESSAGE_SIZE})")
                raise ValueError("消息大小超出限制")

            try:
                return json.loads(line)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}")
                raise

        except KeyboardInterrupt:
            logger.info("收到中断信号")
            return None

    async def write_message(self, message: Dict[str, Any]) -> None:
        """
        将响应字典序列化为 JSON 并写入 stdout。

        Args:
            message: 响应字典
        """
        try:
            json_line = json.dumps(message) + '\n'
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, sys.stdout.write, json_line)
            await loop.run_in_executor(None, sys.stdout.flush)
        except Exception as e:
            logger.error(f"写入消息失败: {e}")

    async def send_notification(self, method: str, params: Dict[str, Any] = None) -> None:
        """
        发送服务端通知（无 id 字段的单向消息）。

        Args:
            method: 通知方法名，如 "notifications/tools/list_changed"
            params: 通知参数
        """
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        await self.write_message(notification)

    async def run(self) -> None:
        """
        主循环：持续从 stdin 读取消息，调用 handler 处理，写回响应。
        遇到 EOF 或 KeyboardInterrupt 时退出。
        """
        self._running = True
        logger.info("StdioTransport 启动")

        try:
            while self._running:
                try:
                    request = await self.read_message()
                    if request is None:
                        break

                    response = await self._handle_request(request)
                    if response is not None:
                        await self.write_message(response)

                except json.JSONDecodeError:
                    error_response = self._build_error_response(
                        None, -32700, "Parse error", "JSON 格式无效"
                    )
                    await self.write_message(error_response)
                except ValueError as e:
                    error_response = self._build_error_response(
                        None, -32600, "Invalid Request", str(e)
                    )
                    await self.write_message(error_response)
                except Exception as e:
                    logger.exception("未捕获的异常")
                    error_response = self._build_error_response(
                        None, -32603, "Internal error", str(e)
                    )
                    await self.write_message(error_response)
        finally:
            self._running = False
            logger.info("StdioTransport 退出")

    async def _handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理单个 MCP 请求。

        Returns:
            响应字典，无响应时返回 None
        """
        request_id = request.get('id')

        try:
            # 校验 JSON-RPC 2.0
            if request.get('jsonrpc') != '2.0':
                return self._build_error_response(request_id, -32600, "Invalid Request", "缺少或无效的 jsonrpc 版本")

            method = request.get('method')
            if not method:
                return self._build_error_response(request_id, -32600, "Invalid Request", "缺少 method 字段")

            result = await self._message_handler(request)
            if request_id is not None:  # 是请求不是通知
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }
            return None

        except MCPError as e:
            return self._build_error_response(request_id, e.code, e.message, e.details)
        except Exception as e:
            logger.exception("消息处理失败")
            return self._build_error_response(request_id, -32603, "Internal error", str(e))

    def _build_error_response(self, request_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
        """
        构建 JSON-RPC 错误响应。
        """
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        if data is not None:
            response["error"]["data"] = data
        return response

    def stop(self) -> None:
        """停止传输层"""
        self._running = False


class MCPServer:
    """MCP 服务端，通过 stdio 与 AI 助手通信，通过 WebSocket 与 Blender 通信。"""

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 配置字典，包含 server/blender/logging/security/limits 等键
        """
        self._config = config
        self._registry = ToolRegistry()
        self._transport: Optional[StdioTransport] = None
        self._ws_server: Optional[websockets.WebSocketServer] = None
        self._ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self._connection_state = ConnectionState.DISCONNECTED
        self._server_info = {
            "name": "blender-mcp",
            "version": "0.1.0",
            "protocol_version": "2024-11-05",
            "capabilities": {"tools": {"listChanged": True}}
        }
        self._blender_info: Optional[Dict[str, Any]] = None
        self._ws_next_id = 0
        self._ws_pending: Dict[str, asyncio.Future] = {}
        self._server_instance = None

    def get_server_info(self) -> Dict[str, Any]:
        """
        获取服务端信息。

        Returns:
            {
                'name': 'blender-mcp',
                'version': '0.1.0',
                'protocol_version': '2024-11-05',
                'capabilities': {'tools': {'listChanged': True}},
                'connection_state': 'CONNECTED' | 'DISCONNECTED' | ...,
                'blender_info': {...} | None
            }
        """
        info = self._server_info.copy()
        info['connection_state'] = self._connection_state
        info['blender_info'] = self._blender_info
        return info

    async def start(self) -> None:
        """启动 MCP 服务，初始化 stdio 通信和 WebSocket 服务器。"""
        logger.info("MCPServer 启动中...")
        self._transport = StdioTransport(message_handler=self.handle_request)

        # 注册所有阶段的工具
        await self._register_all_tools()

        # 启动 WebSocket 服务器（等待 Blender 连接）
        ws_host = self._config.get('server', {}).get('host', '127.0.0.1')
        ws_port = self._config.get('server', {}).get('port', 8765)
        logger.info(f"启动 WebSocket 服务器: ws://{ws_host}:{ws_port}")

        start_server = websockets.serve(
            self._ws_client_handler,
            ws_host,
            ws_port,
            max_size=self._config.get('server', {}).get('ws_max_message_size', 10485760)
        )
        self._ws_server = await start_server
        self._connection_state = ConnectionState.DISCONNECTED
        logger.info(f"WebSocket 服务器已就绪，等待 Blender 连接...")

        # 启动 stdio 消息循环
        await self._transport.run()

    async def stop(self) -> None:
        """优雅停止服务，关闭所有连接和资源。"""
        logger.info("MCPServer 停止中...")
        if self._transport:
            self._transport.stop()

        # 关闭所有 WebSocket 连接
        for conn in self._ws_connections.values():
            await conn.close()
        self._ws_connections.clear()

        if self._ws_server:
            self._ws_server.close()
            await self._ws_server.wait_closed()
        logger.info("MCPServer 已停止")

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理来自 AI 助手的 MCP 请求。

        Args:
            request: JSON-RPC 2.0 格式的请求字典

        Returns:
            JSON-RPC 2.0 格式的响应 result 内容
        """
        method = request.get('method')
        params = request.get('params', {})

        if method == 'initialize':
            return await self._handle_initialize(params)
        elif method == 'tools/list':
            return {"tools": self._registry.list_tools()}
        elif method == 'tools/call':
            tool_name = params.get('name')
            arguments = params.get('arguments', {})
            result = await self._registry.call_tool(tool_name, arguments)
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
        else:
            raise InternalError(f"未知方法: {method}")

    async def send_to_blender(self, message: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """
        通过 WebSocket 向 Blender 插件发送消息并等待响应。

        Args:
            message: 操作消息字典
            timeout: 等待响应超时时间

        Returns:
            Blender 插件的响应字典

        Raises:
            ConnectionError: WebSocket 未连接或发送失败
            TimeoutError: 等待响应超时
        """
        if not self._ws_connections:
            raise ConnectionError("Blender 未连接")

        conn_id, ws = next(iter(self._ws_connections.items()))

        msg_id = message.get('id', generate_message_id())
        message['id'] = msg_id
        message['timestamp'] = iso_now()

        future = asyncio.get_event_loop().create_future()
        self._ws_pending[msg_id] = future

        try:
            await ws.send(json.dumps(message))
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            del self._ws_pending[msg_id]
            raise TimeoutError(f"等待 Blender 响应超时 ({timeout}s)")
        except Exception as e:
            if msg_id in self._ws_pending:
                del self._ws_pending[msg_id]
            raise ConnectionError(f"发送消息失败: {e}")

    async def _register_all_tools(self):
        """注册所有阶段的工具。"""

        # ==================== 通用工具注册工厂 ====================
        async def create_generic_tool_handler(action: str, **fixed_payload):
            async def handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
                request = {
                    "id": generate_message_id(),
                    "type": "request",
                    "action": action,
                    "payload": {**fixed_payload, **arguments},
                    "timestamp": iso_now()
                }
                try:
                    return await self.send_to_blender(request, timeout=30.0)
                except Exception as e:
                    logger.exception(f"{action} 工具调用失败")
                    return {"success": False, "error": str(e)}
            return handler

        # ==================== 阶段一：ping ====================
        async def handle_ping(arguments: Dict[str, Any]) -> Dict[str, Any]:
            """ping 工具处理函数"""
            start_time = time.monotonic()

            request = {
                "id": generate_message_id(),
                "type": "request",
                "action": "ping",
                "payload": {
                    "message": arguments.get('message', ''),
                    "timestamp": time.time()
                },
                "timestamp": iso_now()
            }

            try:
                response = await self.send_to_blender(request, timeout=5.0)
                end_time = time.monotonic()
                latency_ms = round((end_time - start_time) * 1000, 2)

                if response.get('success'):
                    result = response['payload']
                    result['latency_ms'] = latency_ms
                    return result
                else:
                    return {
                        "success": False,
                        "latency_ms": latency_ms,
                        "error": response.get('error', "Unknown error")
                    }
            except ConnectionError:
                return {
                    "success": False,
                    "latency_ms": 0,
                    "error": "CONNECTION_ERROR"
                }
            except TimeoutError:
                return {
                    "success": False,
                    "latency_ms": round((time.monotonic() - start_time) * 1000, 2),
                    "error": "TIMEOUT"
                }

        ping_schema = {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "可选的 ping 消息内容",
                    "default": ""
                }
            },
            "required": []
        }

        self._registry.register(
            name="ping",
            description="与 Blender 建立连接并测试延迟",
            input_schema=ping_schema,
            handler=handle_ping
        )
        logger.info("已注册: ping")

        # ==================== 阶段二：基础工具 ====================
        # create_object
        create_object_schema = {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["mesh", "curve"], "description": "对象类型", "default": "mesh"},
                "name": {"type": "string", "description": "对象名称（可选）"},
                "mesh_type": {"type": "string", "enum": ["cube", "sphere", "cylinder", "plane", "cone", "torus"], "description": "网格类型", "default": "cube"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "位置 (X,Y,Z)", "default": [0, 0, 0]},
                "rotation": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "旋转 (X,Y,Z) 角度", "default": [0, 0, 0]},
                "scale": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "缩放", "default": [1, 1, 1]}
            },
            "required": ["type"]
        }
        self._registry.register(
            name="create_object",
            description="在 Blender 中创建 3D 对象",
            input_schema=create_object_schema,
            handler=await create_generic_tool_handler("create_object")
        )
        logger.info("已注册: create_object")

        # transform_object
        transform_object_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "description": "对象名称或 ID", "required": True},
                "mode": {"type": "string", "enum": ["absolute", "relative"], "description": "变换模式", "default": "relative"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "位置变化/目标位置"},
                "rotation": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "旋转变化/目标旋转（角度）"},
                "scale": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "缩放变化/目标缩放"}
            },
            "required": ["object_id"]
        }
        self._registry.register(
            name="transform_object",
            description="移动、旋转或缩放对象",
            input_schema=transform_object_schema,
            handler=await create_generic_tool_handler("transform_object")
        )
        logger.info("已注册: transform_object")

        # delete_object
        delete_object_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "description": "对象名称或 ID", "required": True}
            },
            "required": ["object_id"]
        }
        self._registry.register(
            name="delete_object",
            description="删除场景中的对象",
            input_schema=delete_object_schema,
            handler=await create_generic_tool_handler("delete_object")
        )
        logger.info("已注册: delete_object")

        # modify_mesh
        modify_mesh_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "description": "对象名称", "required": True},
                "operation": {"type": "string", "enum": ["boolean_union", "boolean_difference", "boolean_intersect", "bevel", "extrude", "solidify"], "description": "操作类型", "required": True},
                "target_id": {"type": "string", "description": "布尔运算的目标对象"},
                "properties": {"type": "object", "description": "操作属性，取决于 operation"}
            },
            "required": ["object_id", "operation"]
        }
        self._registry.register(
            name="modify_mesh",
            description="修改网格：布尔运算、倒角、挤出等",
            input_schema=modify_mesh_schema,
            handler=await create_generic_tool_handler("modify_mesh")
        )
        logger.info("已注册: modify_mesh")

        # simple_deform
        simple_deform_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True},
                "deform_type": {"type": "string", "enum": ["bend", "twist", "taper", "stretch"], "required": True},
                "axis": {"type": "string", "enum": ["X", "Y", "Z"], "default": "Z"},
                "factor": {"type": "number", "description": "变形强度", "default": 1.0},
                "limits": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2, "default": [-1.0, 1.0]}
            },
            "required": ["object_id", "deform_type"]
        }
        self._registry.register(
            name="simple_deform",
            description="简单变形：弯曲、扭曲、锥化、拉伸",
            input_schema=simple_deform_schema,
            handler=await create_generic_tool_handler("simple_deform")
        )
        logger.info("已注册: simple_deform")

        # mesh_sculpt
        mesh_sculpt_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True},
                "operation": {"type": "string", "enum": ["push", "pull", "smooth", "inflate"], "required": True},
                "center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                "radius": {"type": "number", "default": 1.0},
                "strength": {"type": "number", "default": 0.1},
                "falloff": {"type": "string", "enum": ["linear", "inverse", "constant", "gaussian", "root"], "default": "linear"},
                "symmetry": {"type": "array", "items": {"type": "boolean"}, "minItems": 3, "maxItems": 3, "default": [False, False, False]}
            },
            "required": ["object_id", "operation"]
        }
        self._registry.register(
            name="mesh_sculpt",
            description="网格雕刻操作",
            input_schema=mesh_sculpt_schema,
            handler=await create_generic_tool_handler("mesh_sculpt")
        )
        logger.info("已注册: mesh_sculpt")

        # soft_transform
        soft_transform_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True},
                "transform_type": {"type": "string", "enum": ["translate", "rotate", "scale"], "required": True},
                "center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                "radius": {"type": "number", "default": 1.0},
                "displacement": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                "falloff_type": {"type": "string", "enum": ["linear", "inverse", "constant", "gaussian", "root"], "default": "linear"}
            },
            "required": ["object_id", "transform_type"]
        }
        self._registry.register(
            name="soft_transform",
            description="带衰减的软选择变换",
            input_schema=soft_transform_schema,
            handler=await create_generic_tool_handler("soft_transform")
        )
        logger.info("已注册: soft_transform")

        # curve_deform
        curve_deform_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True},
                "curve_id": {"type": "string", "description": "用于变形的曲线对象", "required": True},
                "axis": {"type": "string", "enum": ["X", "Y", "Z"], "default": "X"}
            },
            "required": ["object_id", "curve_id"]
        }
        self._registry.register(
            name="curve_deform",
            description="沿曲线变形对象",
            input_schema=curve_deform_schema,
            handler=await create_generic_tool_handler("curve_deform")
        )
        logger.info("已注册: curve_deform")

        # shrinkwrap
        shrinkwrap_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True},
                "target_id": {"type": "string", "required": True},
                "wrap_method": {"type": "string", "enum": ["nearest_surface", "project", "nearest_vertex"], "default": "nearest_surface"},
                "offset": {"type": "number", "default": 0.0}
            },
            "required": ["object_id", "target_id"]
        }
        self._registry.register(
            name="shrinkwrap",
            description="收缩包裹：将对象吸附到目标表面",
            input_schema=shrinkwrap_schema,
            handler=await create_generic_tool_handler("shrinkwrap")
        )
        logger.info("已注册: shrinkwrap")

        # import_model
        import_model_schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "模型文件路径", "required": True},
                "format": {"type": "string", "enum": ["stl", "obj", "fbx", "gltf"], "default": "stl"}
            },
            "required": ["file_path"]
        }
        self._registry.register(
            name="import_model",
            description="导入 STL/OBJ 等 3D 模型",
            input_schema=import_model_schema,
            handler=await create_generic_tool_handler("import_model")
        )
        logger.info("已注册: import_model")

        # export_model
        export_model_schema = {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "string"}, "description": "要导出的对象 ID 列表，不传则导出全部选中对象"},
                "file_path": {"type": "string", "description": "导出文件路径", "required": True},
                "format": {"type": "string", "enum": ["stl", "obj", "fbx", "gltf"], "default": "stl"},
                "export_selected": {"type": "boolean", "description": "仅导出选中对象", "default": True}
            },
            "required": ["file_path"]
        }
        self._registry.register(
            name="export_model",
            description="导出模型为 STL/OBJ 格式",
            input_schema=export_model_schema,
            handler=await create_generic_tool_handler("export_model")
        )
        logger.info("已注册: export_model")

        # check_model
        check_model_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True}
            },
            "required": ["object_id"]
        }
        self._registry.register(
            name="check_model",
            description="检查模型的可打印性（非流形、法线、壁厚）",
            input_schema=check_model_schema,
            handler=await create_generic_tool_handler("check_model")
        )
        logger.info("已注册: check_model")

        # repair_model
        repair_model_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True},
                "auto_repair": {"type": "boolean", "description": "自动执行所有修复", "default": True},
                "fix_flip_normals": {"type": "boolean", "description": "修复翻转法线", "default": True},
                "fix_merge_vertices": {"type": "boolean", "description": "合并重复顶点", "default": True},
                "fix_fill_holes": {"type": "boolean", "description": "填充孔洞", "default": True},
                "merge_distance": {"type": "number", "description": "顶点合并距离", "default": 0.001}
            },
            "required": ["object_id"]
        }
        self._registry.register(
            name="repair_model",
            description="修复模型问题（翻转法线、合并顶点、填充孔洞）",
            input_schema=repair_model_schema,
            handler=await create_generic_tool_handler("repair_model")
        )
        logger.info("已注册: repair_model")

        # detect_overhangs
        detect_overhangs_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True},
                "overhang_angle": {"type": "number", "description": "最大悬垂角度（度）", "default": 45.0}
            },
            "required": ["object_id"]
        }
        self._registry.register(
            name="detect_overhangs",
            description="检测模型中的悬垂区域",
            input_schema=detect_overhangs_schema,
            handler=await create_generic_tool_handler("detect_overhangs")
        )
        logger.info("已注册: detect_overhangs")

        # optimize_orientation
        optimize_orientation_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True}
            },
            "required": ["object_id"]
        }
        self._registry.register(
            name="optimize_orientation",
            description="优化模型打印方向",
            input_schema=optimize_orientation_schema,
            handler=await create_generic_tool_handler("optimize_orientation")
        )
        logger.info("已注册: optimize_orientation")

        # set_shrinkage_compensation
        shrinkage_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True},
                "compensation_factor": {"type": "number", "description": "收缩率补偿系数 (1.0 = 无补偿)", "default": 1.02},
                "material": {"type": "string", "description": "材料类型", "enum": ["pla", "abs", "petg", "tpu"], "default": "pla"}
            },
            "required": ["object_id"]
        }
        self._registry.register(
            name="set_shrinkage_compensation",
            description="设置模型收缩率补偿",
            input_schema=shrinkage_schema,
            handler=await create_generic_tool_handler("set_shrinkage_compensation")
        )
        logger.info("已注册: set_shrinkage_compensation")

        # validate_printability
        validate_printability_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True}
            },
            "required": ["object_id"]
        }
        self._registry.register(
            name="validate_printability",
            description="综合验证模型可打印性",
            input_schema=validate_printability_schema,
            handler=await create_generic_tool_handler("validate_printability")
        )
        logger.info("已注册: validate_printability")

        # list_objects
        list_objects_schema = {
            "type": "object",
            "properties": {
                "type_filter": {"type": "string", "description": "按类型过滤: mesh/curve/...", "required": False}
            },
            "required": []
        }
        self._registry.register(
            name="list_objects",
            description="列出场景中的所有对象",
            input_schema=list_objects_schema,
            handler=await create_generic_tool_handler("list_objects")
        )
        logger.info("已注册: list_objects")

        # get_scene_info
        get_scene_info_schema = {"type": "object", "properties": {}, "required": []}
        self._registry.register(
            name="get_scene_info",
            description="获取当前场景的基本信息",
            input_schema=get_scene_info_schema,
            handler=await create_generic_tool_handler("get_scene_info")
        )
        logger.info("已注册: get_scene_info")

        # ==================== 阶段三：文件管理 ====================
        # save_project
        save_project_schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "保存路径（可选，留空则保存到当前文件）"},
                "backup": {"type": "boolean", "description": "是否备份旧文件", "default": True}
            },
            "required": []
        }
        self._registry.register(
            name="save_project",
            description="保存当前 Blender 项目",
            input_schema=save_project_schema,
            handler=await create_generic_tool_handler("save_project")
        )
        logger.info("已注册: save_project")

        # open_project
        open_project_schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "required": True}
            },
            "required": ["file_path"]
        }
        self._registry.register(
            name="open_project",
            description="打开 Blender 项目文件",
            input_schema=open_project_schema,
            handler=await create_generic_tool_handler("open_project")
        )
        logger.info("已注册: open_project")

        # ==================== 阶段四：材质与渲染 ====================
        # set_material
        set_material_schema = {
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "required": True},
                "material_name": {"type": "string", "description": "材质名称（可选，默认自动生成）"},
                "preset": {"type": "string", "enum": ["plastic", "glossy_plastic", "metal", "chrome", "glass", "rubber", "ceramic", "wood"], "description": "材质预设"},
                "replace": {"type": "boolean", "description": "是否替换对象现有材质", "default": False},
                "properties": {
                    "type": "object",
                    "properties": {
                        "base_color": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4, "default": [0.8, 0.8, 0.8, 1.0]},
                        "metallic": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.0},
                        "roughness": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                        "specular": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                        "transmission": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.0},
                        "emission_color": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4, "description": "自发光颜色"},
                        "emission_strength": {"type": "number", "minimum": 0, "default": 0.0},
                        "alpha": {"type": "number", "minimum": 0, "maximum": 1, "default": 1.0}
                    }
                }
            },
            "required": ["object_id"]
        }
        self._registry.register(
            name="set_material",
            description="设置对象材质（支持自定义属性或预设）",
            input_schema=set_material_schema,
            handler=await create_generic_tool_handler("set_material")
        )
        logger.info("已注册: set_material")

        # list_materials
        list_materials_schema = {"type": "object", "properties": {}, "required": []}
        self._registry.register(
            name="list_materials",
            description="列出场景中所有材质",
            input_schema=list_materials_schema,
            handler=await create_generic_tool_handler("list_materials")
        )
        logger.info("已注册: list_materials")

        # delete_material
        delete_material_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "要删除的材质名称", "required": True}
            },
            "required": ["name"]
        }
        self._registry.register(
            name="delete_material",
            description="删除材质（仅当无对象使用时）",
            input_schema=delete_material_schema,
            handler=await create_generic_tool_handler("delete_material")
        )
        logger.info("已注册: delete_material")

        # render_scene
        render_scene_schema = {
            "type": "object",
            "properties": {
                "engine": {"type": "string", "enum": ["CYCLES", "EEVEE"], "default": "CYCLES"},
                "resolution": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2, "default": [1920, 1080]},
                "resolution_percentage": {"type": "integer", "minimum": 1, "maximum": 100, "default": 100},
                "output_path": {"type": "string", "description": "输出文件路径（可选）"},
                "file_format": {"type": "string", "enum": ["PNG", "JPEG", "TIFF", "OPEN_EXR"], "default": "PNG"},
                "color_mode": {"type": "string", "enum": ["BW", "RGB", "RGBA"], "default": "RGBA"},
                "color_depth": {"type": "integer", "enum": [8, 16, 32], "default": 8},
                "compression": {"type": "integer", "minimum": 0, "maximum": 100, "default": 15},
                "samples": {"type": "integer", "description": "采样数（可选）"},
                "use_denoising": {"type": "boolean", "default": True}
            },
            "required": []
        }
        self._registry.register(
            name="render_scene",
            description="渲染场景为图像（支持 EEVEE/Cycles）",
            input_schema=render_scene_schema,
            handler=await create_generic_tool_handler("render_scene")
        )
        logger.info("已注册: render_scene")

        logger.info(f"所有工具注册完成！总共 {len(self._registry.list_tools())} 个工具")

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 initialize 请求"""
        client_protocol_version = params.get('protocolVersion')
        if client_protocol_version != '2024-11-05':
            logger.warning(f"协议版本不匹配: {client_protocol_version}")

        return {
            "protocolVersion": "2024-11-05",
            "capabilities": self._server_info["capabilities"],
            "serverInfo": {
                "name": self._server_info["name"],
                "version": self._server_info["version"]
            }
        }

    async def _ws_client_handler(self, websocket: websockets.WebSocketClientProtocol, path: str):
        """处理一个新的 Blender WebSocket 连接"""
        conn_id = f"blender-{self._ws_next_id}"
        self._ws_next_id += 1
        self._ws_connections[conn_id] = websocket
        self._connection_state = ConnectionState.CONNECTED
        logger.info(f"Blender 已连接: {conn_id}")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_blender_message(data, conn_id)
                except Exception as e:
                    logger.error(f"处理 Blender 消息失败: {e}")
        finally:
            del self._ws_connections[conn_id]
            self._connection_state = ConnectionState.DISCONNECTED
            self._blender_info = None
            logger.info(f"Blender 已断开: {conn_id}")

    async def _handle_blender_message(self, data: Dict[str, Any], conn_id: str):
        """处理来自 Blender 的消息"""
        msg_type = data.get('type')
        msg_id = data.get('id')

        if msg_type == 'response' and msg_id in self._ws_pending:
            future = self._ws_pending.pop(msg_id)
            if not future.done():
                future.set_result(data)
        elif msg_type == 'event':
            # 阶段三会处理事件，暂存
            logger.debug(f"收到 Blender 事件: {data.get('event')}")
        elif msg_type == 'heartbeat':
            pass
        else:
            logger.warning(f"未知消息类型: {msg_type}")


def setup_logging(config: Dict[str, Any]):
    """配置日志"""
    log_level_str = config.get('logging', {}).get('level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )


async def main():
    """主函数"""
    config_path = Path(__file__).parent.parent / 'config'
    defaults_path = config_path / 'defaults.yaml'
    user_config_path = config_path / 'config.yaml'

    config_mgr = ConfigManager(str(defaults_path), str(user_config_path) if user_config_path.exists() else None)
    config = config_mgr.load()

    setup_logging(config)
    logger.info(f"配置已加载，监听端口: {config.get('server', {}).get('port', 8765)}")

    server = MCPServer(config)

    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
