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

        # 注册阶段一工具
        await self._register_phase1_tools()

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

    async def _register_phase1_tools(self):
        """注册阶段一的工具。"""

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
        logger.info("已注册阶段一工具: ping")

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
