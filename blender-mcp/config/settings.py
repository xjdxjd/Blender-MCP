import os
import yaml
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器，支持默认值、用户配置和环境变量三层覆盖。"""

    def __init__(self, defaults_path: str, user_config_path: str | None = None):
        self._config: dict = {}
        self._defaults_path = defaults_path
        self._user_config_path = user_config_path

    def load(self) -> dict:
        """
        加载配置：默认值 → 用户配置 → 环境变量。

        Returns:
            合并后的配置字典
        """
        config = {}

        # 1. 加载默认配置
        try:
            with open(self._defaults_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            logger.debug(f"已加载默认配置: {self._defaults_path}")
        except FileNotFoundError:
            logger.warning(f"默认配置文件不存在，使用硬编码默认值: {self._defaults_path}")
            config = self._get_hardcoded_defaults()
        except Exception as e:
            logger.error(f"加载默认配置失败: {e}")
            config = self._get_hardcoded_defaults()

        # 2. 加载用户配置
        if self._user_config_path and os.path.exists(self._user_config_path):
            try:
                with open(self._user_config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f) or {}
                    logger.debug(f"已加载用户配置: {self._user_config_path}")
                    config = self._deep_merge(config, user_config)
            except Exception as e:
                logger.error(f"加载用户配置失败，使用纯默认值: {e}")

        # 3. 应用环境变量
        config = self._apply_env_vars(config)

        # 4. 校验配置
        warnings = self.validate(config)
        for warning in warnings:
            logger.warning(warning)

        self._config = config
        return config

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        按点分路径获取配置值。

        Args:
            key_path: 点分路径，如 "server.port"
            default: 键不存在时的默认值

        Returns:
            配置值
        """
        parts = key_path.split('.')
        value = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def validate(self, config: dict) -> list[str]:
        """
        校验配置项合法性。

        Returns:
            警告消息列表（不阻断启动）
        """
        warnings = []

        # 端口范围
        server_port = config.get('server', {}).get('port', 8765)
        if not (1024 <= server_port <= 65535):
            warnings.append(f"端口超出有效范围 (1024-65535): {server_port}，使用默认值 8765")
            config['server']['port'] = 8765

        # 日志级别
        log_level = config.get('logging', {}).get('level', 'INFO')
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        if log_level.upper() not in valid_levels:
            warnings.append(f"无效日志级别: {log_level}，使用默认值 INFO")
            config['logging']['level'] = 'INFO'

        return warnings

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """深度合并两个字典，override 的值覆盖 base。"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _apply_env_vars(self, config: dict) -> dict:
        """应用环境变量覆盖。"""
        result = config.copy()
        for key, value in os.environ.items():
            if key.startswith('BLENDER_MCP_'):
                # 转换键名: BLENDER_MCP_SERVER_PORT → server.port
                config_key = key[11:].lower().replace('_', '.')
                try:
                    # 解析值类型
                    existing_value = self._get_nested_value(result, config_key)
                    if existing_value is not None:
                        parsed_value = self._parse_env_value(value, type(existing_value))
                        self._set_nested_value(result, config_key, parsed_value)
                        logger.debug(f"环境变量覆盖: {config_key} = {parsed_value}")
                except Exception as e:
                    logger.warning(f"应用环境变量 {key} 失败: {e}")
        return result

    def _get_nested_value(self, config: dict, key_path: str) -> Any:
        parts = key_path.split('.')
        value = config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def _set_nested_value(self, config: dict, key_path: str, value: Any):
        parts = key_path.split('.')
        current = config
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def _parse_env_value(self, value: str, existing_type: type) -> Any:
        """根据已有值的类型解析环境变量值。"""
        if existing_type is bool:
            return value.lower() in ['true', '1', 'yes', 'on']
        elif existing_type is int:
            return int(value)
        elif existing_type is float:
            return float(value)
        elif existing_type is list:
            # 逗号分隔列表
            return [x.strip() for x in value.split(',') if x.strip()]
        else:
            return value

    def _get_hardcoded_defaults(self) -> dict:
        """获取硬编码的默认值。"""
        return {
            'server': {
                'host': '127.0.0.1',
                'port': 8765,
                'ws_max_message_size': 10485760,
                'ws_ping_interval': 15,
                'ws_ping_timeout': 10,
                'ws_max_missed_heartbeats': 3,
                'ws_graceful_close_timeout': 5
            },
            'blender': {
                'plugin_auto_connect': False,
                'reconnect_max_retries': 5,
                'reconnect_base_delay': 1.0,
                'reconnect_max_delay': 30.0,
                'reconnect_backoff_multiplier': 2.0
            },
            'logging': {
                'level': 'INFO',
                'dir': './logs',
                'max_file_size_mb': 10,
                'backup_count': 5,
                'audit_retention_days': 30
            },
            'security': {
                'allowed_paths': [
                    '~/blender-projects/',
                    '~/Downloads/',
                    '~/Desktop/',
                    '/tmp/blender-mcp/'
                ],
                'max_file_size_mb': 500,
                'enable_audit_log': True,
                'max_message_size_mb': 10
            },
            'limits': {
                'max_objects_per_scene': 1000,
                'max_export_file_size_mb': 500,
                'operation_timeout_seconds': 60,
                'rate_limit_per_second': 10,
                'rate_limit_burst': 20
            },
            'tolerance': {
                'vertex_merge_distance': 0.0001,
                'position_snap_precision': 0.001,
                'angle_comparison_epsilon': 0.0001,
                'normal_comparison_dot': 0.9999,
                'stl_export_precision': 6,
                'dimension_comparison_tolerance': 0.01
            }
        }
