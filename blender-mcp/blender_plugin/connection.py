"""
Blender MCP Plugin - WebSocket 连接管理
"""

import asyncio
import json
import threading
import time
import sys
from typing import Optional, Dict, Any
from concurrent.futures import Future


_ws_client: Optional['BlenderWSClient'] = None
_command_handler: Optional[Any] = None


def get_ws_client() -> 'BlenderWSClient':
    """获取单例实例
    """
    global _ws_client
    if _ws_client is None:
        _ws_client = BlenderWSClient()
    return _ws_client


def get_command_handler() -> Any:
    """获取命令处理器单例
    """
    global _command_handler
    if _command_handler is None:
        # 尝试导入核心模块
        try:
            import sys
            from pathlib import Path
            # 添加项目路径到 sys.path
            addon_dir = Path(__file__).parent
            project_root = addon_dir.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from core.command import CommandHandler
            _command_handler = CommandHandler()
        except Exception as e:
            print(f"加载 CommandHandler 失败: {e}")
    return _command_handler


class BlenderWSClient:
    """Blender 端 WebSocket 客户端，与 MCP 服务通信
    """

    def __init__(self):
        self._ws = None
        self._host = "127.0.0.1"
        self._port = 8765
        self._connected = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._request_id = 0
        self._pending: Dict[str, Future] = {}
        self._running = False
        self._handler = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _init_handler(self) -> bool:
        """延迟初始化命令处理器
        """
        if self._handler is None:
            self._handler = get_command_handler()
        return self._handler is not None

    def connect(self, host: str = "127.0.0.1", port: int = 8765) -> tuple[bool, Optional[str]]:
        """
        建立 WebSocket 连接（同步调用，内部通过线程
        """
        self._host = host
        self._port = port

        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

        future = Future()

        self._loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self._async_connect(future))
        )

        try:
            result = future.result(timeout=10)
            return result
        except Exception as e:
            return False, str(e)

    def disconnect(self) -> None:
        """断开连接"""
        self._connected = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop_loop)
        self._ws = None

    def send_request(self, message: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """同步发送请求（主线程调用
        """
        if not self._connected or self._loop is None:
            raise ConnectionError("未连接")

        future = Future()
        msg_id = f"{self._request_id}"
        self._request_id += 1
        message['id'] = msg_id

        self._pending[msg_id] = future

        self._loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self._async_send(message))
        )

        try:
            return future.result(timeout=timeout)
        except Exception as e:
            if msg_id in self._pending:
                del self._pending[msg_id]
            raise e

    def ping(self) -> Dict[str, Any]:
        """内部 ping 响应生成
        """
        import bpy
        import sys
        return {
            "id": "ping-resp",
            "type": "response",
            "action": "ping",
            "success": True,
            "payload": {
                "success": True,
                "blender_version": bpy.app.version_string,
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "scene_objects": len(bpy.context.scene.objects),
                "mode": bpy.context.mode,
                "message": ""
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
        }

    def _run_loop(self) -> None:
        """后台线程运行事件循环
        """
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        except Exception:
            pass

    async def _async_connect(self, result_future: Future) -> None:
        """内部异步连接实现
        """
        try:
            uri = f"ws://{self._host}:{self._port}"
            import websockets
            self._ws = await websockets.connect(uri)
            self._connected = True
            self._running = True

            asyncio.create_task(self._message_handler())
            result_future.set_result((True, None))
        except Exception as e:
            result_future.set_result((False, str(e)))

    async def _async_send(self, message: Dict[str, Any]) -> None:
        """发送到服务端
        """
        if not self._ws:
            return

        try:
            await self._ws.send(json.dumps(message))
        except Exception as e:
            print(f"发送失败: {e}")

    async def _message_handler(self) -> None:
        """消息接收处理循环
        """
        try:
            async for raw_msg in self._ws:
                try:
                    data = json.loads(raw_msg)
                    await self._on_message(data)
                except Exception as e:
                    print(f"解析失败: {e}")
        except Exception as e:
            if self._connected:
                print(f"连接错误: {e}")
        finally:
            self._connected = False

    async def _on_message(self, data: Dict[str, Any]) -> None:
        """处理服务端消息
        """
        import bpy

        msg_type = data.get('type')
        msg_id = data.get('id')

        if msg_type == 'request':
            action = data.get('action')
            payload = data.get('payload', {})

            if action == 'ping':
                response = {
                    "id": msg_id,
                    "type": "response",
                    "action": "ping",
                    "success": True,
                    "payload": {
                        "success": True,
                        "blender_version": bpy.app.version_string,
                        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                        "scene_objects": len(bpy.context.scene.objects),
                        "mode": bpy.context.mode,
                        "message": payload.get('message', '')
                    },
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
                }
                await self._ws.send(json.dumps(response))
            else:
                # 尝试通过 CommandHandler 处理
                try:
                    if self._init_handler():
                        handler_name = f"handle_{action}"
                        handler = getattr(self._handler, handler_name, None)
                        if handler and callable(handler):
                            result = handler(payload)
                            response = {
                                "id": msg_id,
                                "type": "response",
                                "action": action,
                                "success": result.get('success', False),
                                "payload": result,
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
                            }
                            await self._ws.send(json.dumps(response))
                        else:
                            response = {
                                "id": msg_id,
                                "type": "response",
                                "action": action,
                                "success": False,
                                "error": {"code": "UNKNOWN_ACTION", "message": f"Unknown action: {action}"},
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
                            }
                            await self._ws.send(json.dumps(response))
                    else:
                        response = {
                            "id": msg_id,
                            "type": "response",
                            "action": action,
                            "success": False,
                            "error": {"code": "NO_HANDLER", "message": "CommandHandler not available"},
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
                        }
                        await self._ws.send(json.dumps(response))
                except Exception as e:
                    print(f"处理 action {action} 失败: {e}")
                    import traceback
                    traceback.print_exc()
                    response = {
                        "id": msg_id,
                        "type": "response",
                        "action": action,
                        "success": False,
                        "error": {"code": "EXECUTE_ERROR", "message": str(e)},
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
                    }
                    await self._ws.send(json.dumps(response))
        elif msg_type == 'response' and msg_id in self._pending:
            future = self._pending.pop(msg_id)
            if not future.done():
                future.set_result(data)

    def _stop_loop(self) -> None:
        self._running = False
        tasks = [t for t in asyncio.all_tasks(self._loop)]
        for t in tasks:
            t.cancel()
        self._loop.call_soon_threadsafe(self._loop.stop())

