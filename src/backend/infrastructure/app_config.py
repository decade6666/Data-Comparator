"""应用级配置（<DATA_DIR>/config.yaml）：回收站清理策略。

与 CRF-Editor 的配置结构对齐：只读 ``recycle_bin`` 段，缺失字段用默认值；
写入采用线程锁 + 临时文件 + ``os.replace`` 原子替换。
"""

import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from .file_runtime import get_app_data_dir


class RecycleBinAgeRule(BaseModel):
    """年龄规则：删除超过 value*unit 的条目。"""

    enabled: bool = False
    value: int = 30
    unit: Literal["day", "month", "year"] = "day"

    @field_validator("value")
    @classmethod
    def _value_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("value 必须 >= 1")
        return v


class RecycleBinSizeRule(BaseModel):
    """容量规则：回收站总量超过 value*unit 时按最旧优先淘汰。"""

    enabled: bool = False
    value: int = 500
    unit: Literal["MB", "GB"] = "MB"

    @field_validator("value")
    @classmethod
    def _value_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("value 必须 >= 1")
        return v


class RecycleBinConfig(BaseModel):
    interval_minutes: int = 60
    min_retain_hours: int = 24
    age: RecycleBinAgeRule = Field(default_factory=RecycleBinAgeRule)
    size: RecycleBinSizeRule = Field(default_factory=RecycleBinSizeRule)

    @field_validator("interval_minutes")
    @classmethod
    def _interval_in_range(cls, v: int) -> int:
        if not 1 <= v <= 1440:
            raise ValueError("interval_minutes 必须在 1..1440 之间")
        return v

    @field_validator("min_retain_hours")
    @classmethod
    def _retain_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("min_retain_hours 必须 >= 0")
        return v


class AppConfig(BaseModel):
    recycle_bin: RecycleBinConfig = Field(default_factory=RecycleBinConfig)


def _config_path() -> Path:
    return Path(get_app_data_dir()) / "config.yaml"


def _load_raw() -> Optional[dict]:
    """读 config.yaml 回 dict；文件缺失或解析失败返回 None（不抛）。"""
    path = _config_path()
    try:
        if not path.exists():
            return None
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - 配置损坏不应阻断服务启动
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _deep_merge(base: dict, updates: dict) -> dict:
    """深合并：字典递归合并，标量直接覆盖。"""
    result = dict(base)
    for key, value in updates.items():
        current = result.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            result[key] = _deep_merge(current, value)
        else:
            result[key] = value
    return result


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    """读取应用配置；文件缺失/解析失败/字段非法时返回默认值（不抛）。"""
    raw = _load_raw()
    if raw is None:
        return AppConfig()
    try:
        recycle_bin_raw = raw.get("recycle_bin")
        if isinstance(recycle_bin_raw, dict):
            return AppConfig.model_validate({"recycle_bin": recycle_bin_raw})
        return AppConfig()
    except (ValueError, TypeError):
        return AppConfig()


_UPDATE_LOCK = threading.Lock()


def update_app_config(updates: dict) -> AppConfig:
    """合并更新并原子写回 config.yaml，返回最新配置。"""
    with _UPDATE_LOCK:
        merged = _deep_merge(get_app_config().model_dump(), updates)
        config = AppConfig.model_validate(merged)
        path = _config_path()
        tmp_path = path.with_name(path.name + ".tmp")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as file:
            yaml.safe_dump(
                config.model_dump(), file, allow_unicode=True, sort_keys=False
            )
        os.replace(tmp_path, path)
        get_app_config.cache_clear()
        return get_app_config()
