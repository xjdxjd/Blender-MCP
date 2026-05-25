import logging
import time
import uuid
from typing import Dict, Any, Callable, Optional
from jsonschema import validate, ValidationError

from .schemas import ToolDefinition

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册表，管理所有 MCP 工具的注册、查找和调用。"""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Any]
    ) -> None:
        """
        注册一个 MCP 工具。

        Args:
            name: 工具名称，如 "ping"
            description: 工具描述
            input_schema: JSON Schema 格式的参数定义
            handler: 异步处理函数，接收参数字典，返回结果字典

        Raises:
            ValueError: 工具名已存在或参数无效
        """
        if name in self._tools:
            raise ValueError(f"工具名已存在: {name}")
        if not callable(handler):
            raise ValueError(f"handler 必须是可调用对象，当前是: {type(handler)}")

        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler
        )
        logger.debug(f"已注册工具: {name}")

    def unregister(self, name: str) -> bool:
        """
        注销一个工具。

        Returns:
            是否成功注销（工具不存在返回 False）
        """
        if name in self._tools:
            del self._tools[name]
            logger.debug(f"已注销工具: {name}")
            return True
        return False

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """
        按名称查找工具。

        Returns:
            工具定义，不存在返回 None
        """
        return self._tools.get(name)

    def list_tools(self) -> list[Dict[str, Any]]:
        """
        获取所有已注册工具的列表（MCP tools/list 格式）。

        Returns:
            [{"name": "ping", "description": "...", "inputSchema": {...}}, ...]
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            }
            for tool in self._tools.values()
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用指定工具。

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果

        Raises:
            ToolNotFoundError: 工具不存在
            InvalidParameterError: 参数校验失败
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(f"工具不存在: {name}")

        try:
            validate(instance=arguments, schema=tool.input_schema)
        except ValidationError as e:
            raise InvalidParameterError(f"参数校验失败: {e.message}", details=e.schema_path) from e

        try:
            result = await tool.handler(arguments)
            return result
        except Exception as e:
            logger.exception(f"工具 {name} 执行失败")
            raise InternalError(f"工具执行失败: {str(e)}") from e


# 异常定义
class MCPError(Exception):
    """MCP 错误基类"""
    def __init__(self, message: str, code: int = -32603, details: Any = None):
        self.message = message
        self.code = code
        self.details = details
        super().__init__(message)


class ToolNotFoundError(MCPError):
    """工具不存在错误"""
    def __init__(self, message: str):
        super().__init__(message, code=-32601)


class InvalidParameterError(MCPError):
    """参数无效错误"""
    def __init__(self, message: str, details: Any = None):
        super().__init__(message, code=-32602, details=details)


class InternalError(MCPError):
    """内部错误"""
    def __init__(self, message: str):
        super().__init__(message, code=-32603)


def generate_message_id() -> str:
    """生成唯一消息 ID"""
    return str(uuid.uuid4())


def iso_now() -> str:
    """获取 ISO 8601 格式的当前时间"""
    return time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
