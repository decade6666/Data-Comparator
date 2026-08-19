"""浏览器上传文件的临时存储与注册表。

上传文件保存在 ``get_app_temp_dir()/uploads`` 下，以 UUID 前缀防止重名碰撞。
记录在内存中维护（进程重启后旧上传自然失效），并通过定期清理删除过期文件。
"""

import datetime
import os
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from .file_runtime import get_app_temp_dir

ALLOWED_EXTENSIONS = (".xlsx", ".xls")
DEFAULT_MAX_AGE_HOURS = 2
DEFAULT_CHUNK_BYTES = 1024 * 1024


class UploadRejectedError(ValueError):
    """上传被拒绝（扩展名不合法等），映射为 HTTP 400。"""


class UploadTooLargeError(UploadRejectedError):
    """上传超过大小限制，映射为 HTTP 413。"""


@dataclass(frozen=True)
class UploadRecord:
    upload_id: str
    file_path: str
    original_name: str
    size: int
    created_at: datetime.datetime


class UploadStore:
    def __init__(
        self,
        base_dir: Optional[str] = None,
        max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
        now: Callable[[], datetime.datetime] = datetime.datetime.now,
    ) -> None:
        self._base_dir = base_dir or os.path.join(
            get_app_temp_dir(), "uploads"
        )
        self._max_age_hours = max_age_hours
        self._now = now
        self._records: Dict[str, UploadRecord] = {}

    def save(
        self,
        original_name: str,
        stream,
        max_bytes: int,
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
    ) -> UploadRecord:
        """把上传流写入临时目录；超限抛 ``UploadTooLargeError``。"""
        ext = os.path.splitext(original_name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise UploadRejectedError(
                "仅支持 .xlsx / .xls 格式的 Excel 文件，当前文件: {!r}".format(
                    original_name
                )
            )
        upload_id = uuid.uuid4().hex[:16]
        safe_name = os.path.basename(original_name)
        target_path = os.path.join(
            self._base_dir, "{}_{}".format(upload_id, safe_name)
        )
        os.makedirs(self._base_dir, exist_ok=True)
        total = 0
        with open(target_path, "wb") as target:
            while True:
                chunk = stream.read(chunk_bytes)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    target.close()
                    try:
                        os.remove(target_path)
                    except OSError:
                        pass
                    raise UploadTooLargeError(
                        "文件大小超过限制（最大 {}MB）".format(max_bytes // (1024 * 1024))
                    )
                target.write(chunk)
        record = UploadRecord(
            upload_id=upload_id,
            file_path=target_path,
            original_name=original_name,
            size=total,
            created_at=self._now(),
        )
        self._records[upload_id] = record
        return record

    def get(self, upload_id: str) -> Optional[UploadRecord]:
        record = self._records.get(upload_id)
        if record is None:
            return None
        if not os.path.isfile(record.file_path):
            return None
        return record

    def resolve(self, upload_id: str) -> Optional[str]:
        record = self.get(upload_id)
        if record is None:
            return None
        return record.file_path

    def default_output_dir(self) -> str:
        """上传模式下的比对报告输出目录。"""
        return os.path.join(get_app_temp_dir(), "results")

    def cleanup(self, now: Optional[datetime.datetime] = None) -> int:
        """删除超过保留期的上传文件并清空对应记录。"""
        current = now or self._now()
        removed = 0
        for upload_id, record in list(self._records.items()):
            age = current - record.created_at
            if age > datetime.timedelta(hours=self._max_age_hours):
                try:
                    os.remove(record.file_path)
                except OSError:
                    pass
                del self._records[upload_id]
                removed += 1
        return removed
