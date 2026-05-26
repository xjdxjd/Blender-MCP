"""
Blender-mcp 性能优化与批处理模块

提供:
- BatchOperationManager: 批量操作管理器
- profile_tool: 性能分析装饰器
- ReleaseBuilder: 发布构建器
"""

import functools
import hashlib
import json
import logging
import os
import shutil
import struct
import time
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BatchStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class BatchOperation:
    name: str
    tool_name: str
    params: Dict[str, Any]
    status: BatchStatus = BatchStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: float = 0.0


@dataclass
class BatchResult:
    batch_id: str
    status: BatchStatus
    total: int
    completed: int = 0
    failed: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class BatchOperationManager:
    """
    批量操作管理器
    
    支持将多个 MCP 工具调用打包为一个批次执行，
    提供：
    - 顺序/并行执行策略
    - 失败时自动回滚
    - 执行进度追踪
    """

    def __init__(self, command_handler=None, max_retries: int = 1):
        self._handler = command_handler
        self._max_retries = max_retries
        self._batches: Dict[str, List[BatchOperation]] = {}
        self._batch_counter = 0

    def create_batch(self, operations: List[Dict[str, Any]]) -> str:
        self._batch_counter += 1
        batch_id = f"batch_{self._batch_counter:04d}"

        batch_ops = []
        for i, op in enumerate(operations):
            batch_ops.append(BatchOperation(
                name=op.get('name', f'op_{i}'),
                tool_name=op['tool'],
                params=op.get('params', {}),
            ))

        self._batches[batch_id] = batch_ops
        return batch_id

    def execute_batch(
        self,
        batch_id: str,
        stop_on_failure: bool = True,
        rollback_on_failure: bool = False,
    ) -> BatchResult:
        if batch_id not in self._batches:
            return BatchResult(
                batch_id=batch_id,
                status=BatchStatus.FAILED,
                total=0,
                failed=1,
                errors=[{"error": f"批次 '{batch_id}' 不存在"}],
            )

        operations = self._batches[batch_id]
        result = BatchResult(
            batch_id=batch_id,
            status=BatchStatus.RUNNING,
            total=len(operations),
        )

        start_time = time.time()
        completed_ops: List[BatchOperation] = []

        for op in operations:
            op_result = self._execute_single(op)

            if op_result.get('success', False):
                op.status = BatchStatus.COMPLETED
                op.result = op_result
                op.timestamp = time.time()
                result.completed += 1
                result.results.append(op_result)
                completed_ops.append(op)
            else:
                op.status = BatchStatus.FAILED
                op.error = op_result.get('error', '未知错误')
                op.timestamp = time.time()
                result.failed += 1
                result.errors.append({
                    "operation": op.name,
                    "tool": op.tool_name,
                    "error": op.error,
                })

                if stop_on_failure:
                    break

        elapsed = time.time() - start_time
        result.elapsed_seconds = round(elapsed, 3)

        if result.failed > 0 and rollback_on_failure:
            self._rollback(completed_ops)
            result.status = BatchStatus.ROLLED_BACK
        elif result.failed == 0:
            result.status = BatchStatus.COMPLETED
        else:
            result.status = BatchStatus.FAILED

        return result

    def _execute_single(self, op: BatchOperation) -> Dict[str, Any]:
        if self._handler is None:
            return {"success": False, "error": "CommandHandler 未设置"}

        handler_map = {
            'create_object': self._handler.handle_create_object,
            'transform_object': self._handler.handle_transform_object,
            'delete_object': self._handler.handle_delete_object,
            'modify_mesh': self._handler.handle_modify_mesh,
            'simple_deform': self._handler.handle_simple_deform,
            'mesh_sculpt': self._handler.handle_mesh_sculpt,
            'soft_transform': self._handler.handle_soft_transform,
            'curve_deform': self._handler.handle_curve_deform,
            'shrinkwrap': self._handler.handle_shrinkwrap,
            'set_material': self._handler.handle_set_material,
            'render_scene': self._handler.handle_render_scene,
            'import_model': self._handler.handle_import_model,
            'export_model': self._handler.handle_export_model,
            'check_model': self._handler.handle_check_model,
            'repair_model': self._handler.handle_repair_model,
            'save_project': self._handler.handle_save_project,
            'open_project': self._handler.handle_open_project,
            'list_objects': self._handler.handle_list_objects,
            'get_scene_info': self._handler.handle_get_scene_info,
            'list_materials': self._handler.handle_list_materials,
            'delete_material': self._handler.handle_delete_material,
        }

        handler = handler_map.get(op.tool_name)
        if handler is None:
            return {"success": False, "error": f"未知工具: {op.tool_name}"}

        for attempt in range(self._max_retries):
            try:
                return handler(op.params)
            except Exception as e:
                if attempt == self._max_retries - 1:
                    return {"success": False, "error": str(e)}
                time.sleep(0.1 * (attempt + 1))

        return {"success": False, "error": "重试次数耗尽"}

    def _rollback(self, completed_ops: List[BatchOperation]) -> None:
        for op in reversed(completed_ops):
            try:
                if op.tool_name == 'create_object' and op.result:
                    obj_name = op.result.get('object_id') or op.result.get('name')
                    if obj_name and self._handler:
                        self._handler.handle_delete_object({
                            'object_id': obj_name
                        })
                elif op.tool_name == 'set_material' and op.result:
                    mat_name = op.result.get('material_name')
                    if mat_name and self._handler:
                        self._handler.handle_delete_material({
                            'name': mat_name
                        })
            except Exception as e:
                logger.warning(f"回滚操作 '{op.name}' 失败: {e}")

    def get_batch_status(self, batch_id: str) -> Optional[BatchResult]:
        if batch_id not in self._batches:
            return None

        operations = self._batches[batch_id]
        completed = sum(1 for op in operations if op.status == BatchStatus.COMPLETED)
        failed = sum(1 for op in operations if op.status == BatchStatus.FAILED)

        if completed == len(operations):
            status = BatchStatus.COMPLETED
        elif failed > 0:
            status = BatchStatus.FAILED
        elif completed > 0:
            status = BatchStatus.RUNNING
        else:
            status = BatchStatus.PENDING

        return BatchResult(
            batch_id=batch_id,
            status=status,
            total=len(operations),
            completed=completed,
            failed=failed,
            results=[op.result for op in operations if op.result],
            errors=[{"operation": op.name, "error": op.error} for op in operations if op.error],
        )

    def cancel_batch(self, batch_id: str) -> bool:
        if batch_id not in self._batches:
            return False
        del self._batches[batch_id]
        return True


def profile_tool(func: Optional[Callable] = None, *, threshold_ms: float = 100.0):
    """
    性能分析装饰器
    
    记录工具调用的执行时间，超过阈值时发出警告。
    
    用法:
        @profile_tool
        def my_tool(params): ...
        
        @profile_tool(threshold_ms=50.0)
        def my_fast_tool(params): ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                tool_name = fn.__name__
                if elapsed_ms > threshold_ms:
                    logger.warning(
                        f"[PERF] {tool_name} 耗时 {elapsed_ms:.1f}ms "
                        f"(阈值: {threshold_ms:.1f}ms)"
                    )
                else:
                    logger.debug(
                        f"[PERF] {tool_name} 耗时 {elapsed_ms:.1f}ms"
                    )

                if isinstance(result, dict):
                    result['_profile'] = {
                        'tool': tool_name,
                        'elapsed_ms': round(elapsed_ms, 2),
                    }

            return result
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


class ReleaseBuilder:
    """
    发布构建器
    
    负责:
    - 运行测试
    - 构建 Python 包
    - 打包 Blender 插件 ZIP
    - 生成校验和
    - 生成发布说明
    """

    def __init__(self, project_root: str, version: str):
        self._root = project_root
        self._version = version
        self._dist_dir = os.path.join(project_root, 'dist')

    def build_all(self) -> Dict[str, Any]:
        results = {}
        results['tests'] = self.run_tests()
        if not results['tests']['success']:
            return {
                "success": False,
                "error": "测试未通过，中止构建",
                "details": results,
            }

        results['python_package'] = self.build_python_package()
        results['plugin_zip'] = self.build_plugin_zip()
        results['checksums'] = self.generate_checksums()
        results['release_notes'] = self.generate_release_notes()

        return {
            "success": True,
            "version": self._version,
            "details": results,
        }

    def run_tests(self) -> Dict[str, Any]:
        import subprocess

        test_dir = os.path.join(self._root, 'tests')
        if not os.path.isdir(test_dir):
            return {"success": True, "message": "无测试目录，跳过"}

        try:
            result = subprocess.run(
                ['python', '-m', 'pytest', test_dir, '-v', '--tb=short'],
                capture_output=True,
                text=True,
                timeout=300,
            )
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
                "stderr": result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "测试超时（300s）"}
        except FileNotFoundError:
            return {"success": True, "message": "pytest 未安装，跳过测试"}

    def build_python_package(self) -> Dict[str, Any]:
        os.makedirs(self._dist_dir, exist_ok=True)

        src_dir = os.path.join(self._root, 'mcp_server')
        if not os.path.isdir(src_dir):
            return {"success": False, "error": "mcp_server 目录不存在"}

        pkg_dir = os.path.join(self._dist_dir, f'blender-mcp-{self._version}')
        if os.path.exists(pkg_dir):
            shutil.rmtree(pkg_dir)

        shutil.copytree(
            os.path.join(self._root, 'core'),
            os.path.join(pkg_dir, 'core'),
        )
        shutil.copytree(
            os.path.join(self._root, 'config'),
            os.path.join(pkg_dir, 'config'),
        )
        shutil.copytree(src_dir, os.path.join(pkg_dir, 'mcp_server'))

        for fname in ('requirements.txt',):
            src = os.path.join(self._root, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(pkg_dir, fname))

        init_file = os.path.join(pkg_dir, '__init__.py')
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write(f'__version__ = "{self._version}"\n')

        return {
            "success": True,
            "package_dir": pkg_dir,
            "version": self._version,
        }

    def build_plugin_zip(self) -> Dict[str, Any]:
        os.makedirs(self._dist_dir, exist_ok=True)

        plugin_src = os.path.join(self._root, 'blender_plugin')
        if not os.path.isdir(plugin_src):
            return {"success": False, "error": "blender_plugin 目录不存在"}

        zip_path = os.path.join(
            self._dist_dir,
            f'blender_mcp_plugin_{self._version}.zip',
        )

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(plugin_src):
                for fname in files:
                    if fname.endswith('.pyc') or '__pycache__' in root:
                        continue
                    file_path = os.path.join(root, fname)
                    arcname = os.path.join(
                        'blender_mcp',
                        os.path.relpath(file_path, plugin_src),
                    )
                    zf.write(file_path, arcname)

        return {
            "success": True,
            "zip_path": zip_path,
            "size_bytes": os.path.getsize(zip_path),
        }

    def generate_checksums(self) -> Dict[str, Any]:
        checksums = {}
        if not os.path.isdir(self._dist_dir):
            return {"success": True, "checksums": {}}

        for fname in os.listdir(self._dist_dir):
            fpath = os.path.join(self._dist_dir, fname)
            if os.path.isfile(fpath):
                h = hashlib.sha256()
                with open(fpath, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        h.update(chunk)
                checksums[fname] = h.hexdigest()

        checksum_file = os.path.join(self._dist_dir, 'SHA256SUMS')
        with open(checksum_file, 'w') as f:
            for fname, digest in sorted(checksums.items()):
                f.write(f"{digest}  {fname}\n")

        return {
            "success": True,
            "checksums": checksums,
            "checksum_file": checksum_file,
        }

    def generate_release_notes(self) -> Dict[str, Any]:
        changelog_path = os.path.join(self._root, '..', 'document', '变更日志.md')
        notes_lines = [
            f"# Blender-mcp v{self._version} 发布说明",
            "",
            f"发布日期: {time.strftime('%Y-%m-%d')}",
            "",
            "## 变更内容",
            "",
        ]

        if os.path.exists(changelog_path):
            with open(changelog_path, 'r', encoding='utf-8') as f:
                content = f.read()
                in_version = False
                for line in content.split('\n'):
                    if line.startswith('## [') and self._version in line:
                        in_version = True
                        continue
                    elif line.startswith('## [') and in_version:
                        break
                    elif in_version:
                        notes_lines.append(line)

        notes_path = os.path.join(self._dist_dir, f'RELEASE_NOTES_v{self._version}.md')
        os.makedirs(self._dist_dir, exist_ok=True)
        with open(notes_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(notes_lines))

        return {
            "success": True,
            "notes_path": notes_path,
        }
