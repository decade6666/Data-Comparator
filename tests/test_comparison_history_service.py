"""comparison_history_service 单元测试：落库、剥离、过滤、排序与删除。"""

import datetime
import json
import os

import pytest
from sqlalchemy.orm import Session

from src.backend.application import comparison_history_service as service
from src.backend.application.job_manager import JobState, JobStatus
from src.backend.infrastructure.database import db_path_for_testing
from src.backend.infrastructure.models.comparison_run import ComparisonRun
from src.backend.infrastructure.models.user import User
from src.shared.contracts import ParameterDocument


@pytest.fixture
def session(tmp_path):
    db_path_for_testing(str(tmp_path))
    from src.backend.infrastructure.database import get_engine, init_db

    init_db()
    s = Session(get_engine())
    yield s
    s.close()


def _make_job(
    *,
    job_id="abc123",
    user_id=1,
    config_name="CIMS",
    status=JobStatus.COMPLETED,
    output_path="/data/results/CIMS-比对报告-2026-08-23T12-00-00.xlsx",
    log_path="/data/results/CIMS-比对日志-2026-08-23T12-00-00.txt",
    error=None,
    started_at=None,
    finished_at=None,
) -> JobState:
    params: ParameterDocument = {
        "old_file_path": "/data/uploads/old.xlsx",
        "new_file_path": "/data/uploads/new.xlsx",
        "output_directory": "/data/results",
        "old_file_upload_id": "up_old",
        "new_file_upload_id": "up_new",
        "include_sheets": ["Sheet1"],
    }
    return JobState(
        job_id=job_id,
        status=status,
        parameters=params,
        config_name=config_name,
        user_id=user_id,
        stop_flag=__import__("threading").Event(),
        created_at=datetime.datetime(2026, 8, 23, 12, 0, 0),
        error=error,
        started_at=started_at,
        finished_at=finished_at or datetime.datetime(2026, 8, 23, 12, 5, 0),
        output_path=output_path,
        log_path=log_path,
    )


def test_record_run_stores_basename_only(session, tmp_path):
    run = service.record_run(session, _make_job())
    session.commit()
    assert run.report_filename == "CIMS-比对报告-2026-08-23T12-00-00.xlsx"
    assert run.log_filename == "CIMS-比对日志-2026-08-23T12-00-00.txt"
    assert "/" not in (run.report_filename or "")
    assert "/" not in (run.log_filename or "")


def test_record_run_strips_sensitive_fields(session, tmp_path):
    run = service.record_run(session, _make_job())
    session.commit()
    params = json.loads(run.parameters_json)
    for field in (
        "old_file_path",
        "new_file_path",
        "output_directory",
        "old_file_upload_id",
        "new_file_upload_id",
    ):
        assert field not in params
    assert params["include_sheets"] == ["Sheet1"]


def test_record_run_failed_has_no_report(session, tmp_path):
    run = service.record_run(
        session,
        _make_job(status=JobStatus.FAILED, output_path=None, error="保存失败"),
    )
    session.commit()
    assert run.status == "failed"
    assert run.report_filename is None
    assert run.log_filename == "CIMS-比对日志-2026-08-23T12-00-00.txt"
    assert run.error == "保存失败"


def test_record_run_cancelled(session, tmp_path):
    run = service.record_run(
        session,
        _make_job(status=JobStatus.CANCELLED, output_path=None, log_path=None),
    )
    session.commit()
    assert run.status == "cancelled"
    assert run.report_filename is None
    assert run.log_filename is None


def test_list_runs_filters_by_user_and_config(session, tmp_path):
    service.record_run(
        session,
        _make_job(
            job_id="a",
            user_id=1,
            config_name="CIMS",
            finished_at=datetime.datetime(2026, 8, 23, 10, 0, 0),
        ),
    )
    service.record_run(
        session,
        _make_job(
            job_id="b",
            user_id=1,
            config_name="TM",
            finished_at=datetime.datetime(2026, 8, 23, 11, 0, 0),
        ),
    )
    service.record_run(
        session,
        _make_job(
            job_id="c",
            user_id=2,
            config_name="CIMS",
            finished_at=datetime.datetime(2026, 8, 23, 12, 0, 0),
        ),
    )
    session.commit()

    runs = service.list_runs(session, user_id=1)
    assert [r.job_id for r in runs] == ["b", "a"]

    cims = service.list_runs(session, user_id=1, config_name="CIMS")
    assert [r.job_id for r in cims] == ["a"]

    none = service.list_runs(session, user_id=2, config_name="TM")
    assert none == []


def test_get_run_scopes_to_owner(session, tmp_path):
    a = service.record_run(session, _make_job(user_id=1))
    service.record_run(session, _make_job(job_id="b", user_id=2))
    session.commit()

    assert service.get_run(session, 1, a.id) is not None
    assert service.get_run(session, 2, a.id) is None
    assert service.get_run(session, 1, 99999) is None


def test_delete_runs_for_user_removes_rows_only_for_user(session, tmp_path):
    service.record_run(session, _make_job(user_id=1))
    service.record_run(session, _make_job(job_id="b", user_id=2))
    session.commit()

    assert service.delete_runs_for_user(session, 1) == 1
    session.commit()
    remaining = service.list_runs(session, user_id=2)
    assert [r.job_id for r in remaining] == ["b"]


def test_run_to_summary_reports_availability(session, tmp_path):
    run = service.record_run(session, _make_job())
    session.commit()

    results_dir = str(tmp_path)
    summary = service.run_to_summary(run, results_dir)
    assert summary["report_available"] is False
    assert summary["log_available"] is False

    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, run.report_filename or ""), "w") as f:
        f.write("x")
    with open(os.path.join(results_dir, run.log_filename or ""), "w") as f:
        f.write("y")
    summary = service.run_to_summary(run, results_dir)
    assert summary["report_available"] is True
    assert summary["log_available"] is True


def test_run_to_detail_includes_params(session, tmp_path):
    run = service.record_run(session, _make_job())
    session.commit()
    detail = service.run_to_detail(run, str(tmp_path))
    assert detail["parameters"]["include_sheets"] == ["Sheet1"]
    assert "old_file_path" not in detail["parameters"]
