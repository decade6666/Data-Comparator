import datetime
import io
import json

from src.backend.infrastructure.upload_store import UploadStore

CURRENT_TIME = datetime.datetime(2026, 8, 18, 12, 0, 0)


def _store(base_dir, **kwargs):
    return UploadStore(
        base_dir=str(base_dir),
        now=lambda: CURRENT_TIME,
        **kwargs,
    )


def _save_upload(store, name="data.xlsx"):
    return store.save(name, io.BytesIO(b"excel-data"), max_bytes=1024)


def test_save_persists_upload_index(tmp_path):
    record = _save_upload(_store(tmp_path))

    index = json.loads((tmp_path / "_index.json").read_text(encoding="utf-8"))

    assert index["version"] == 1
    assert index["records"][record.upload_id]["file_path"] == record.file_path
    assert index["records"][record.upload_id]["created_at"] == (
        CURRENT_TIME.isoformat()
    )


def test_store_reloads_records_after_restart(tmp_path):
    first_store = _store(tmp_path)
    record = _save_upload(first_store, "旧版本.xlsx")

    second_store = _store(tmp_path)

    assert second_store.get(record.upload_id) == record
    assert second_store.resolve(record.upload_id) == record.file_path


def test_load_ignores_records_for_missing_files(tmp_path):
    index_path = tmp_path / "_index.json"
    index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "records": {
                    "missing": {
                        "upload_id": "missing",
                        "file_path": str(tmp_path / "missing.xlsx"),
                        "original_name": "missing.xlsx",
                        "size": 0,
                        "created_at": CURRENT_TIME.isoformat(),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    store = _store(tmp_path)

    assert store.get("missing") is None


def test_cleanup_keeps_upload_referenced_by_config(tmp_path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    store = _store(
        tmp_path / "uploads",
        max_age_hours=1,
        config_dir_getter=lambda: str(config_dir),
    )
    record = _save_upload(store)
    (config_dir / "saved.json").write_text(
        json.dumps({"old_file_upload_id": record.upload_id}),
        encoding="utf-8",
    )

    removed = store.cleanup(now=CURRENT_TIME + datetime.timedelta(hours=2))

    assert removed == 0
    assert store.get(record.upload_id) == record


def test_cleanup_removes_unreferenced_expired_upload(tmp_path):
    store = _store(tmp_path, max_age_hours=1)
    record = _save_upload(store)

    removed = store.cleanup(now=CURRENT_TIME + datetime.timedelta(hours=2))

    assert removed == 1
    assert store.get(record.upload_id) is None
    index_text = (tmp_path / "_index.json").read_text(encoding="utf-8")
    assert record.upload_id not in index_text
