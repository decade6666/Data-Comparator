import datetime
import os
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from ...shared.contracts import ParameterDocument


@dataclass(frozen=True)
class ProcessingPaths:
    old_path: str
    new_path: str
    output_dir: str


def sanitize_output_name(name: str) -> str:
    invalid = '\\/:*?"<>|\n\r\t'
    sanitized = "".join("-" if ch in invalid else ch for ch in (name or "").strip())
    collapsed = "-".join(segment for segment in sanitized.split("-") if segment)
    return collapsed or "默认配置"


def validate_processing_paths(
    parameters: ParameterDocument,
    path_exists: Callable[[str], bool] = os.path.exists,
    make_dirs: Callable[..., None] = os.makedirs,
) -> ProcessingPaths:
    old_path = parameters.get("old_file_path", "")
    new_path = parameters.get("new_file_path", "")
    output_dir = parameters.get("output_directory", "")

    if not all([old_path, new_path, output_dir]):
        raise ValueError("请填写所有必要的路径信息")

    if not path_exists(old_path) or not path_exists(new_path):
        raise FileNotFoundError("输入文件不存在")

    if not path_exists(output_dir):
        try:
            make_dirs(output_dir)
        except Exception as exc:
            raise OSError(f"创建输出目录失败: {exc}") from exc

    return ProcessingPaths(
        old_path=old_path,
        new_path=new_path,
        output_dir=output_dir,
    )


def apply_processing_paths(
    parameters: ParameterDocument, processing_paths: ProcessingPaths
) -> ParameterDocument:
    return {
        **parameters,
        "old_file_path": processing_paths.old_path,
        "new_file_path": processing_paths.new_path,
        "output_directory": processing_paths.output_dir,
    }


def resolve_log_directory(
    output_dir: str,
    app_temp_dir_getter: Callable[[], str],
) -> str:
    try:
        app_temp_dir = app_temp_dir_getter()
    except Exception:
        app_temp_dir = "."
    return output_dir or app_temp_dir


def build_output_path(
    config_name: str,
    output_dir: str,
    now: Optional[datetime.datetime] = None,
) -> str:
    current_time = (now or datetime.datetime.now()).strftime("%Y-%m-%dT%H-%M-%S")
    safe_name = sanitize_output_name(config_name)
    filename = f"{safe_name}-比对报告-{current_time}.xlsx"
    return os.path.join(output_dir, filename).replace("\\", "/")


def build_log_path(
    config_name: str,
    output_dir: str,
    now: Optional[datetime.datetime] = None,
) -> str:
    """构造与报告成对（同一时间戳）的日志文件路径。

    与 ``build_output_path`` 共用同一个 ``now``，保证「报告-日志」在
    目录里肉眼可配对、测试可断言时间戳逐字节一致。
    """
    current_time = (now or datetime.datetime.now()).strftime("%Y-%m-%dT%H-%M-%S")
    safe_name = sanitize_output_name(config_name)
    filename = f"{safe_name}-比对日志-{current_time}.txt"
    return os.path.join(output_dir, filename).replace("\\", "/")


def write_log_file(path: str, lines: Sequence[str]) -> Optional[str]:
    """把日志行写入 ``path``，返回路径；``lines`` 为空时不创建文件返回 None。

    自动创建父目录（输入文件校验失败时 results 目录可能尚未存在）。
    OSError 交由调用方处理——日志写入失败绝不能让一次成功的比对翻车。
    """
    if not lines:
        return None
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))
        if not lines[-1].endswith("\n"):
            stream.write("\n")
    return path
