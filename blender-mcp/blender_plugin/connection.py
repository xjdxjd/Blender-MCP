"""
Blender MCP Plugin - WebSocket 连接管理
使用 Python 内置 socket 实现，无需安装第三方包
"""

import json
import socket
import struct
import threading
import time
import hashlib
import base64
import os
import sys
import bpy
from typing import Optional, Dict, Any
from concurrent.futures import Future


_ws_client: Optional['BlenderWSClient'] = None


def get_ws_client() -> 'BlenderWSClient':
    global _ws_client
    if _ws_client is None:
        _ws_client = BlenderWSClient()
    return _ws_client


class WebSocketFrame:
    OPCODE_TEXT = 0x1
    OPCODE_BINARY = 0x2
    OPCODE_CLOSE = 0x8
    OPCODE_PING = 0x9
    OPCODE_PONG = 0xA

    @staticmethod
    def encode(data: str, opcode: int = 0x1, mask: bool = True) -> bytes:
        payload = data.encode('utf-8') if isinstance(data, str) else data
        frame = bytearray()
        frame.append(0x80 | opcode)

        length = len(payload)
        mask_bit = 0x80 if mask else 0x00

        if length < 126:
            frame.append(mask_bit | length)
        elif length < 65536:
            frame.append(mask_bit | 126)
            frame.extend(struct.pack('!H', length))
        else:
            frame.append(mask_bit | 127)
            frame.extend(struct.pack('!Q', length))

        if mask:
            mask_key = os.urandom(4)
            frame.extend(mask_key)
            masked = bytearray(payload)
            for i in range(len(masked)):
                masked[i] ^= mask_key[i % 4]
            frame.extend(masked)
        else:
            frame.extend(payload)

        return bytes(frame)

    @staticmethod
    def recv(sock: socket.socket) -> Optional[tuple]:
        try:
            header = _recv_exact(sock, 2)
            if not header:
                return None

            opcode = header[0] & 0x0F
            masked = bool(header[1] & 0x80)
            length = header[1] & 0x7F

            if length == 126:
                data = _recv_exact(sock, 2)
                if not data:
                    return None
                length = struct.unpack('!H', data)[0]
            elif length == 127:
                data = _recv_exact(sock, 8)
                if not data:
                    return None
                length = struct.unpack('!Q', data)[0]

            mask_key = None
            if masked:
                mask_key = _recv_exact(sock, 4)
                if not mask_key:
                    return None

            payload = _recv_exact(sock, length)
            if payload is None:
                return None

            if masked and mask_key:
                payload = bytearray(payload)
                for i in range(len(payload)):
                    payload[i] ^= mask_key[i % 4]
                payload = bytes(payload)

            return (opcode, payload)
        except Exception:
            return None


def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    data = bytearray()
    while len(data) < n:
        try:
            chunk = sock.recv(n - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        except socket.timeout:
            return None
        except Exception:
            return None
    return bytes(data)


class SimpleBlenderHandler:
    """简化的 Blender 命令处理器，直接处理基本操作"""

    def __init__(self):
        pass

    def handle_action(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        handler_name = f"handle_{action}"
        handler = getattr(self, handler_name, None)
        if handler and callable(handler):
            try:
                return handler(payload)
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        return {
            "success": False,
            "error": f"未知动作: {action}"
        }

    def handle_ping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "blender_version": bpy.app.version_string,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "scene_objects": len(bpy.context.scene.objects),
            "mode": bpy.context.mode,
            "message": payload.get('message', ''),
        }

    def handle_list_objects(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            objects = []
            for obj in bpy.context.scene.objects:
                objects.append({
                    "name": obj.name_full,
                    "type": obj.type,
                    "location": list(obj.location),
                    "visible": obj.visible_get(),
                })
            return {
                "success": True,
                "count": len(objects),
                "objects": objects
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_get_scene_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            scene = bpy.context.scene
            return {
                "success": True,
                "scene_name": scene.name_full,
                "frame_current": scene.frame_current,
                "frame_start": scene.frame_start,
                "frame_end": scene.frame_end,
                "object_count": len(scene.objects),
                "selected_objects": [
                    obj.name_full for obj in bpy.context.selected_objects
                ],
                "active_object": (
                    bpy.context.active_object.name_full
                    if bpy.context.active_object else None
                )
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_create_object(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            obj_type = payload.get('type', 'mesh')
            name = payload.get('name', 'NewObject')
            location = tuple(payload.get('location', [0.0, 0.0, 0.0]))

            if obj_type == 'mesh':
                mesh_type = payload.get('mesh_type', 'cube')
                if mesh_type == 'cube':
                    bpy.ops.mesh.primitive_cube_add(size=2.0, location=location)
                elif mesh_type == 'sphere':
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=location)
                elif mesh_type == 'cylinder':
                    bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=2.0, location=location)
                elif mesh_type == 'cone':
                    bpy.ops.mesh.primitive_cone_add(radius1=1.0, depth=2.0, location=location)
                elif mesh_type == 'plane':
                    bpy.ops.mesh.primitive_plane_add(size=2.0, location=location)
                elif mesh_type == 'torus':
                    bpy.ops.mesh.primitive_torus_add(
                        major_radius=1.0,
                        minor_radius=0.25,
                        location=location
                    )
                else:
                    return {"success": False, "error": f"未知的 mesh_type: {mesh_type}"}

                obj = bpy.context.active_object
                if obj and name:
                    obj.name = name
                return {
                    "success": True,
                    "object_name": obj.name_full if obj else None,
                }
            else:
                return {"success": False, "error": f"不支持的类型: {obj_type}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_delete_object(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            object_name = payload.get('object_name')
            if not object_name:
                return {"success": False, "error": "未指定 object_name"}

            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"success": False, "error": f"找不到对象: {object_name}"}

            bpy.data.objects.remove(obj, do_unlink=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_transform_object(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            object_name = payload.get('object_name')
            if not object_name:
                return {"success": False, "error": "未指定 object_name"}

            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"success": False, "error": f"找不到对象: {object_name}"}

            if 'location' in payload:
                obj.location = tuple(payload['location'])
            if 'rotation' in payload:
                rotation = payload['rotation']
                if len(rotation) == 3:
                    obj.rotation_euler = tuple(rotation)
            if 'scale' in payload:
                obj.scale = tuple(payload['scale'])

            return {
                "success": True,
                "object_name": obj.name_full,
                "location": list(obj.location),
                "rotation": list(obj.rotation_euler),
                "scale": list(obj.scale),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class BlenderWSClient:
    def __init__(self):
        self._sock: Optional[socket.socket] = None
        self._host = "127.0.0.1"
        self._port = 8765
        self._connected = False
        self._recv_thread: Optional[threading.Thread] = None
        self._running = False
        self._request_id = 0
        self._pending: Dict[str, Future] = {}
        self._handler: Optional[SimpleBlenderHandler] = None
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self, host: str = "127.0.0.1", port: int = 8765) -> tuple:
        self._host = host
        self._port = port

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self._host, self._port))

            ws_key = base64.b64encode(os.urandom(16)).decode('ascii')
            handshake = (
                f"GET / HTTP/1.1\r\n"
                f"Host: {self._host}:{self._port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {ws_key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"\r\n"
            )
            sock.sendall(handshake.encode('utf-8'))

            response = b""
            while b"\r\n\r\n" not in response:
                chunk = sock.recv(4096)
                if not chunk:
                    sock.close()
                    return False, "WebSocket 握手失败"
                response += chunk

            if b"101" not in response.split(b"\r\n")[0]:
                sock.close()
                return False, "WebSocket 握手被拒绝"

            sock.settimeout(0.1)
            self._sock = sock
            self._connected = True
            self._running = True
            self._handler = SimpleBlenderHandler()

            self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._recv_thread.start()

            return True, None

        except socket.timeout:
            return False, "连接超时"
        except ConnectionRefusedError:
            return False, "连接被拒绝，请确认 MCP 服务已启动"
        except Exception as e:
            return False, str(e)

    def disconnect(self) -> None:
        self._running = False
        self._connected = False

        if self._sock:
            try:
                close_frame = WebSocketFrame.encode("", opcode=WebSocketFrame.OPCODE_CLOSE, mask=True)
                self._sock.sendall(close_frame)
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def send_request(self, message: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        if not self._connected or not self._sock:
            raise ConnectionError("未连接")

        with self._lock:
            msg_id = f"{self._request_id}"
            self._request_id += 1

        message['id'] = msg_id
        future = Future()
        self._pending[msg_id] = future

        try:
            data = json.dumps(message)
            frame = WebSocketFrame.encode(data)
            self._sock.sendall(frame)
        except Exception as e:
            if msg_id in self._pending:
                del self._pending[msg_id]
            raise ConnectionError(f"发送失败: {e}")

        try:
            return future.result(timeout=timeout)
        except Exception as e:
            if msg_id in self._pending:
                del self._pending[msg_id]
            raise e

    def ping(self) -> Dict[str, Any]:
        start = time.monotonic()
        try:
            request = {
                "id": f"ping-{self._request_id}",
                "type": "request",
                "action": "ping",
                "payload": {"message": ""},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            result = self.send_request(request, timeout=5.0)
            latency = (time.monotonic() - start) * 1000
            if result.get('success') or (result.get('payload', {}).get('success')):
                payload = result.get('payload', result)
                payload['latency_ms'] = round(latency, 2)
                payload['success'] = True
                return payload
            else:
                return {"success": False, "error": result.get('error', 'Ping 失败')}
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            return {"success": False, "latency_ms": round(latency, 2), "error": str(e)}

    def _recv_loop(self) -> None:
        while self._running and self._sock:
            result = WebSocketFrame.recv(self._sock)
            if result is None:
                if self._running:
                    self._connected = False
                break

            opcode, payload = result

            if opcode == WebSocketFrame.OPCODE_TEXT:
                try:
                    data = json.loads(payload.decode('utf-8'))
                    self._on_message(data)
                except Exception as e:
                    print(f"解析消息失败: {e}")

            elif opcode == WebSocketFrame.OPCODE_PING:
                try:
                    pong = WebSocketFrame.encode(payload, opcode=WebSocketFrame.OPCODE_PONG, mask=True)
                    self._sock.sendall(pong)
                except Exception:
                    pass

            elif opcode == WebSocketFrame.OPCODE_CLOSE:
                self._connected = False
                self._running = False
                break

        self._connected = False

    def _on_message(self, data: Dict[str, Any]) -> None:
        msg_type = data.get('type')
        msg_id = data.get('id')

        if msg_type == 'request':
            action = data.get('action')
            payload = data.get('payload', {})
            response = self._handle_action(msg_id, action, payload)
            self._send_response(response)

        elif msg_type == 'response' and msg_id in self._pending:
            future = self._pending.pop(msg_id)
            if not future.done():
                future.set_result(data)

    def _handle_action(self, msg_id: str, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._handler:
            try:
                result = self._handler.handle_action(action, payload)
                return {
                    "id": msg_id,
                    "type": "response",
                    "action": action,
                    "success": result.get('success', False),
                    "payload": result,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            except Exception as e:
                print(f"处理 {action} 失败: {e}")
                import traceback
                traceback.print_exc()

        return {
            "id": msg_id,
            "type": "response",
            "action": action,
            "success": False,
            "error": {"code": "NO_HANDLER", "message": f"无法处理: {action}"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def _send_response(self, response: Dict[str, Any]) -> None:
        if not self._sock or not self._connected:
            return
        try:
            data = json.dumps(response)
            frame = WebSocketFrame.encode(data)
            with self._lock:
                self._sock.sendall(frame)
        except Exception as e:
            print(f"发送响应失败: {e}")
