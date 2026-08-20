"""管理员路由：用户配置管理 + 回收站 + 清理策略。

全部端点要求管理员权限（``require_admin``）；所有接受 config_name
的端点先做路径穿越校验（拒绝空名、含 / 或 .. 的名字）。
"""

import json
import os
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...backend.application.recycle_bin_cleanup_service import build_cleanup_plan
from ...backend.application.recycle_bin_service import RecycleBinService
from ...backend.infrastructure.app_config import get_app_config, update_app_config
from ...backend.infrastructure.database import get_session
from ...backend.infrastructure.file_runtime import get_user_data_dir
from ...backend.infrastructure.models.recycled_config import RecycledConfig
from ...backend.infrastructure.models.user import User
from ...backend.infrastructure.parameter_repository import JsonParameterRepository
from ...backend.infrastructure.parameter_templates import BUILTIN_TEMPLATES
from ...shared.contracts import ParameterDocument
from ..dependencies import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

_CONFIGS_SUBDIR = "configs"
_UPLOAD_FIELDS = (
    "old_file_upload_id",
    "new_file_upload_id",
    "old_file_path",
    "new_file_path",
    "old_file_sheets",
    "new_file_sheets",
)
_AGE_UNITS = ("day", "month", "year")
_SIZE_UNITS = ("MB", "GB")


def _configs_dir(user_id: int) -> str:
    return os.path.join(get_user_data_dir(user_id), _CONFIGS_SUBDIR)


def _repository_for(user_id: int) -> JsonParameterRepository:
    def base_dir_getter() -> str:
        return get_user_data_dir(user_id)

    return JsonParameterRepository(base_dir_getter=base_dir_getter)


def _validate_config_name(name: str) -> None:
    """项目名校验：拒绝空名、路径穿越与内置模板名。"""
    if not name or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="项目名不合法")
    if name in BUILTIN_TEMPLATES:
        raise HTTPException(status_code=400, detail="不能操作内置模板")


def _require_user(session: Session, user_id: int) -> None:
    """校验用户存在，不存在抛 404（防对已删除用户操作产生孤儿目录）。"""
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="用户不存在")


def _strip_upload_fields(document: Dict[str, Any]) -> Dict[str, Any]:
    """深拷贝并清空 upload / path 字段（目标用户需重新上传）。"""
    cleaned = dict(document)
    for field in _UPLOAD_FIELDS:
        cleaned.pop(field, None)
    return cleaned


def _read_user_config(repo: JsonParameterRepository, name: str) -> Optional[dict]:
    """直接读用户配置目录中的 JSON（绕过内置模板常量）。"""
    config_path = repo.get_config_path(name)
    if not os.path.isfile(config_path):
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            document = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    return document


def _suffix_name(configs_dir: str, base_name: str, suffix: str) -> str:
    """目标目录重名时生成 原名 (副本)/(副本2)… 或 (恢复)/(恢复2)…。"""
    existing = set()
    if os.path.isdir(configs_dir):
        existing = {
            os.path.splitext(name)[0]
            for name in os.listdir(configs_dir)
            if name.endswith(".json")
        }
    if base_name not in existing:
        return base_name
    first = f"{base_name} ({suffix})"
    if first not in existing:
        return first
    index = 2
    while f"{base_name} ({suffix}{index})" in existing:
        index += 1
    return f"{base_name} ({suffix}{index})"


class ConfigBatchCopyRequest(BaseModel):
    config_names: List[str]
    source_user_id: int
    target_user_id: int

    model_config = {"extra": "forbid"}


class ConfigBatchMoveRequest(BaseModel):
    config_names: List[str]
    source_user_id: int
    target_user_id: int

    model_config = {"extra": "forbid"}


class ConfigBatchDeleteRequest(BaseModel):
    config_names: List[str]
    user_id: int

    model_config = {"extra": "forbid"}


class RestoreRequest(BaseModel):
    target_user_id: Optional[int] = None

    model_config = {"extra": "forbid"}


class RecycleBinAgeRuleUpdate(BaseModel):
    enabled: bool
    value: int
    unit: str

    model_config = {"extra": "forbid"}


class RecycleBinSizeRuleUpdate(BaseModel):
    enabled: bool
    value: int
    unit: str

    model_config = {"extra": "forbid"}


class CleanupPolicyUpdateRequest(BaseModel):
    interval_minutes: int
    min_retain_hours: int
    age: RecycleBinAgeRuleUpdate
    size: RecycleBinSizeRuleUpdate

    model_config = {"extra": "forbid"}


def _validate_policy_update(request: CleanupPolicyUpdateRequest) -> None:
    """策略值校验：value>=1、interval 1..1440、min_retain_hours>=0、unit 枚举。"""
    if not 1 <= request.interval_minutes <= 1440:
        raise HTTPException(
            status_code=400, detail="interval_minutes 必须在 1..1440 之间"
        )
    if request.min_retain_hours < 0:
        raise HTTPException(status_code=400, detail="min_retain_hours 必须 >= 0")
    if request.age.value < 1 or request.size.value < 1:
        raise HTTPException(status_code=400, detail="value 必须 >= 1")
    if request.age.unit not in _AGE_UNITS:
        raise HTTPException(status_code=400, detail="年龄规则单位不合法")
    if request.size.unit not in _SIZE_UNITS:
        raise HTTPException(status_code=400, detail="容量规则单位不合法")


def _cleanup_policy_response(session: Session) -> Dict[str, Any]:
    config = get_app_config().recycle_bin
    total, count = session.execute(
        select(
            func.coalesce(func.sum(RecycledConfig.estimated_size_bytes), 0),
            func.count(RecycledConfig.id),
        )
    ).one()
    return {
        "interval_minutes": config.interval_minutes,
        "min_retain_hours": config.min_retain_hours,
        "age": {
            "enabled": config.age.enabled,
            "value": config.age.value,
            "unit": config.age.unit,
        },
        "size": {
            "enabled": config.size.enabled,
            "value": config.size.value,
            "unit": config.size.unit,
        },
        "total_estimated_size_bytes": int(total),
        "recycled_config_count": int(count),
    }


@router.get("/users/{user_id}/configs")
def list_user_configs(
    user_id: int,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    configs = [
        name
        for name in _repository_for(user_id).list_configurations()
        if name not in BUILTIN_TEMPLATES
    ]
    return {"configs": configs}


@router.post("/configs/batch-copy")
def batch_copy_configs(
    request: ConfigBatchCopyRequest,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """批量复制配置到目标用户；逐项返回成功/失败。"""
    if not request.config_names:
        raise HTTPException(status_code=400, detail="config_names 不能为空")
    _require_user(session, request.source_user_id)
    _require_user(session, request.target_user_id)
    source_repo = _repository_for(request.source_user_id)
    target_repo = _repository_for(request.target_user_id)
    target_dir = _configs_dir(request.target_user_id)
    results: List[Dict[str, Any]] = []
    for name in request.config_names:
        try:
            _validate_config_name(name)
            document = _read_user_config(source_repo, name)
            if document is None:
                results.append(
                    {"config_name": name, "status": "failed", "error": "源配置不存在"}
                )
                continue
            new_name = _suffix_name(target_dir, name, "副本")
            target_repo.save_document(
                new_name, cast(ParameterDocument, _strip_upload_fields(document))
            )
            results.append(
                {"config_name": name, "new_name": new_name, "status": "success"}
            )
        except HTTPException as exc:
            results.append(
                {"config_name": name, "status": "failed", "error": str(exc.detail)}
            )
    return results


@router.post("/configs/batch-move")
def batch_move_configs(
    request: ConfigBatchMoveRequest,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """批量转移配置：复制到目标（清空 upload 字段）后删除源文件。"""
    if not request.config_names:
        raise HTTPException(status_code=400, detail="config_names 不能为空")
    _require_user(session, request.source_user_id)
    _require_user(session, request.target_user_id)
    source_repo = _repository_for(request.source_user_id)
    target_repo = _repository_for(request.target_user_id)
    target_dir = _configs_dir(request.target_user_id)
    moved = 0
    failed = 0
    for name in request.config_names:
        try:
            _validate_config_name(name)
            document = _read_user_config(source_repo, name)
            if document is None:
                failed += 1
                continue
            new_name = _suffix_name(target_dir, name, "副本")
            target_repo.save_document(
                new_name, cast(ParameterDocument, _strip_upload_fields(document))
            )
            os.remove(source_repo.get_config_path(name))
            moved += 1
        except (HTTPException, OSError):
            failed += 1
    if moved == 0 and failed > 0:
        raise HTTPException(status_code=400, detail="全部项目转移失败")
    return {"status": "success", "moved": moved}


@router.post("/configs/batch-delete")
def batch_delete_configs(
    request: ConfigBatchDeleteRequest,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """批量把用户配置软删到回收站。"""
    if not request.config_names:
        raise HTTPException(status_code=400, detail="config_names 不能为空")
    user = session.get(User, request.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    repo = _repository_for(request.user_id)
    deleted = 0
    for name in request.config_names:
        try:
            _validate_config_name(name)
        except HTTPException:
            continue
        document = _read_user_config(repo, name)
        if document is None:
            continue
        RecycleBinService.recycle_config(
            session,
            owner_id=request.user_id,
            owner_username=user.username,
            config_name=name,
            config_path=repo.get_config_path(name),
            config_document=document,
            deleted_by_user_deletion=False,
        )
        deleted += 1
    return {"deleted": deleted}


@router.get("/recycle-bin")
def list_recycle_bin(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> List[Dict[str, Any]]:
    return [
        {
            "id": entry.id,
            "original_owner_id": entry.original_owner_id,
            "original_owner_username": entry.original_owner_username,
            "original_config_name": entry.original_config_name,
            "estimated_size_bytes": entry.estimated_size_bytes,
            "deleted_at": entry.deleted_at,
            "deleted_by_user_deletion": entry.deleted_by_user_deletion,
        }
        for entry in RecycleBinService.list_recycled(session)
    ]


@router.post("/recycle-bin/{recycled_id}/restore")
def restore_recycled_config(
    recycled_id: int,
    request: RestoreRequest,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    entry = session.get(RecycledConfig, recycled_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="回收站条目不存在")
    target_user_id = request.target_user_id
    if target_user_id is None:
        if (
            entry.original_owner_id is None
            or session.get(User, entry.original_owner_id) is None
        ):
            raise HTTPException(status_code=400, detail="原用户已删除，请指定目标用户")
        target_user_id = entry.original_owner_id
    elif session.get(User, target_user_id) is None:
        raise HTTPException(status_code=400, detail="目标用户不存在")
    try:
        return RecycleBinService.restore_config(
            session,
            recycled_id,
            target_user_id=target_user_id,
            configs_dir=_configs_dir(target_user_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/recycle-bin/{recycled_id}", status_code=204)
def hard_delete_recycled_config(
    recycled_id: int,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> None:
    try:
        RecycleBinService.hard_delete_config(session, recycled_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/recycle-bin/cleanup-policy")
def get_cleanup_policy(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    return _cleanup_policy_response(session)


@router.put("/recycle-bin/cleanup-policy")
def update_cleanup_policy(
    request: CleanupPolicyUpdateRequest,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    _validate_policy_update(request)
    update_app_config(
        {
            "recycle_bin": {
                "interval_minutes": request.interval_minutes,
                "min_retain_hours": request.min_retain_hours,
                "age": request.age.model_dump(),
                "size": request.size.model_dump(),
            }
        }
    )
    return _cleanup_policy_response(session)


@router.post("/recycle-bin/cleanup/preview")
def preview_cleanup(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """预览将清理的条目（不执行删除）。"""
    plan = build_cleanup_plan(session, policy=get_app_config().recycle_bin)
    items: List[Dict[str, Any]] = []
    for pid in plan.all_target_ids():
        entry = session.get(RecycledConfig, pid)
        if entry is None:
            continue
        items.append(
            {
                "id": entry.id,
                "original_config_name": entry.original_config_name,
                "owner_username": entry.original_owner_username,
                "deleted_at": entry.deleted_at,
                "estimated_size_bytes": entry.estimated_size_bytes,
                "matched_rules": plan.matched_rules_for(pid),
            }
        )
    return items
