"""浏览器上传文件的临时存储与注册表。

上传文件保存在 ``get_app_temp_dir()/uploads`` 下，以 UUID 前缀防止重名碰撞。
记录会持久化到同目录的 ``_index.json``，并通过定期清理删除未被配置引用的过期文件。
"""

import datetime
import json
import os
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass
from typing import Callable, Dict, Optional, Set

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
        config_dir_getter: Optional[Callable[[], str]] = None,
    ) -> None:
        self._base_dir = base_dir or os.path.join(
            get_app_temp_dir(), "uploads"
        )
        self._max_age_hours = max_age_hours
        self._now = now
        self._config_dir_getter = config_dir_getter
        self._index_lock = threading.RLock()
        self._records: Dict[str, UploadRecord] = {}
        self._load_index()

    @property
    def _index_path(self) -> str:
        return os.path.join(self._base_dir, "_index.json")

    def _load_index(self) -> None:
        """从磁盘恢复注册表，忽略损坏记录和已不存在的文件。"""
        try:
            with open(self._index_path, "r", encoding="utf-8") as index_file:
                payload = json.load(index_file)
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return

        records = payload.get("records", {}) if isinstance(payload, dict) else {}
        if not isinstance(records, dict):
            return

        restored: Dict[str, UploadRecord] = {}
        for upload_id, raw_record in records.items():
            record = self._record_from_json(upload_id, raw_record)
            if record is not None and os.path.isfile(record.file_path):
                restored[record.upload_id] = record
        with self._index_lock:
            self._records = restored

    @staticmethod
    def _record_from_json(
        upload_id: str, raw_record: object
    ) -> Optional[UploadRecord]:
        if not isinstance(raw_record, dict):
            return None
        try:
            record_id = str(raw_record.get("upload_id", upload_id))
            created_at = datetime.datetime.fromisoformat(
                str(raw_record["created_at"])
            )
            return UploadRecord(
                upload_id=record_id,
                file_path=str(raw_record["file_path"]),
                original_name=str(raw_record["original_name"]),
                size=int(raw_record["size"]),
                created_at=created_at,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _save_index(self) -> None:
        """原子更新注册表，避免进程中断留下半个 JSON 文件。"""
        os.makedirs(self._base_dir, exist_ok=True)
        with self._index_lock:
            payload = {
                "version": 1,
                "records": {
                    upload_id: {
                        **asdict(record),
                        "created_at": record.created_at.isoformat(),
                    }
                    for upload_id, record in self._records.items()
                },
            }
            temporary_path = ""
            try:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=self._base_dir,
                    prefix=".index-",
                    suffix=".tmp",
                    delete=False,
                ) as temporary_file:
                    temporary_path = temporary_file.name
                    json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
                    temporary_file.flush()
                    os.fsync(temporary_file.fileno())
                os.replace(temporary_path, self._index_path)
            finally:
                if temporary_path and os.path.exists(temporary_path):
                    os.remove(temporary_path)

    def _referenced_upload_ids(self) -> Set[str]:
        """读取配置文件，找出仍被用户配置引用的上传记录。"""
        if self._config_dir_getter is None:
            return set()
        try:
            config_dir = self._config_dir_getter()
            filenames = os.listdir(config_dir)
        except OSError:
            return set()

        referenced: Set[str] = set()
        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            try:
                with open(
                    os.path.join(config_dir, filename), "r", encoding="utf-8"
                ) as config_file:
                    document = json.load(config_file)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(document, dict):
                continue
            for key in ("old_file_upload_id", "new_file_upload_id"):
                upload_id = document.get(key)
                if isinstance(upload_id, str) and upload_id:
                    referenced.add(upload_id)
        return referenced

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
        with self._index_lock:
            self._records[upload_id] = record
            self._save_index()
        return record

    def get(self, upload_id: str) -> Optional[UploadRecord]:
        with self._index_lock:
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
        """删除未被配置引用且超过保留期的上传文件。"""
        current = now or self._now()
        referenced_ids = self._referenced_upload_ids()
        removed = 0
        with self._index_lock:
            for upload_id, record in list(self._records.items()):
                if upload_id in referenced_ids:
                    continue
                age = current - record.created_at
                if age <= datetime.timedelta(hours=self._max_age_hours):
                    continue
                try:
                    os.remove(record.file_path)
                except OSError:
                    pass
                del self._records[upload_id]
                removed += 1
            if removed:
                self._save_index()
        return removed
