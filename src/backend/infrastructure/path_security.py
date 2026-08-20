"""路径安全校验工具。

从 CRF-Editor 的 ``backend/src/utils.py`` 与 ``backend/main.py`` 移植：
- ``is_safe_path``：解析后路径必须位于允许目录内（``os.path.commonpath`` 包含性校验）。
- ``validate_asset_raw_path``：拼接前先拒绝绝对路径、点段、反斜杠与 URL 编码绕过。

这两个函数是静态资源服务的统一安全边界，新增此类接口必须复用。
"""

import os
import re
from pathlib import Path
from typing import List, Tuple
from urllib.parse import unquote

_WINDOWS_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")


def is_safe_path(path: str, allowed_dirs: List[str]) -> Tuple[bool, str]:
    """校验解析后的路径是否位于任一允许目录内。"""
    if not path:
        return False, "路径不能为空"
    try:
        real_path = Path(path).resolve()
        for allowed_dir in allowed_dirs:
            allowed_real = Path(allowed_dir).resolve()
            try:
                common = os.path.commonpath([str(real_path), str(allowed_real)])
                if common == str(allowed_real):
                    return True, ""
            except (ValueError, OSError):
                continue
        return False, "路径必须在允许的目录内"
    except Exception as exc:  # noqa: BLE001 - 解析失败统一按不安全处理
        return False, "路径解析失败: {}".format(exc)


def _iter_path_variants(filepath: str):
    """遍历原始路径及其有限次 URL 解码结果，用于拒绝编码绕过。"""
    current = filepath
    seen = set()
    for _ in range(3):
        if current in seen:
            break
        seen.add(current)
        yield current
        decoded = unquote(current)
        if decoded == current:
            break
        current = decoded


def validate_asset_raw_path(filepath: str) -> Tuple[bool, str]:
    """在拼接资源路径前，拒绝绝对路径、点段、反斜杠和编码绕过。"""
    if not filepath:
        return False, "资源路径不能为空"
    for candidate in _iter_path_variants(filepath):
        if candidate.startswith(("/", "\\")):
            return False, "资源路径不合法"
        if "\\" in candidate:
            return False, "资源路径不合法"
        if _WINDOWS_DRIVE_PREFIX_RE.match(candidate):
            return False, "资源路径不合法"
        parts = candidate.split("/")
        if any(part in ("", ".", "..") for part in parts):
            return False, "资源路径不合法"
    return True, ""
