from dataclasses import dataclass
from typing import Callable, Any, Dict, Optional


@dataclass
class ToolDefinition:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Any]


@dataclass
class ConnectionState:
    """连接状态"""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"
    HEARTBEAT_LOST = "HEARTBEAT_LOST"


@dataclass
class ReconnectConfig:
    """重连配置"""
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0
