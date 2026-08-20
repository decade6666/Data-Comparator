"""回收站清理决策引擎（复刻 CRF-Editor 算法）。

预览与执行共用 ``build_cleanup_plan``，避免两处逻辑漂移：
1. 年龄规则先选：``deleted_at`` 早于截止时间的条目（不受 min_retain_hours 保护）；
2. 容量规则在「剔除年龄命中后的剩余集合」上按 ``deleted_at ASC``（FIFO）
   淘汰到总量 <= 上限；``min_retain_hours`` 只保护容量规则命中的近期条目。

时间统一使用 naive 本地时间（与 ``recycled_config.deleted_at`` 写入值一致）。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..infrastructure.app_config import RecycleBinConfig
from ..infrastructure.models.recycled_config import RecycledConfig

_AGE_FACTORS = {"day": 1, "month": 30, "year": 365}
_SIZE_FACTORS = {"MB": 1024**2, "GB": 1024**3}


@dataclass(frozen=True)
class CleanupPlan:
    """一次清理决策的结果。"""

    age_ids: List[int]
    size_ids: List[int]
    total_bytes_before: int
    total_bytes_after: int
    would_converge: bool

    def all_target_ids(self) -> List[int]:
        """全部待删 id（保序去重）。"""
        seen = set()
        result: List[int] = []
        for pid in self.age_ids + self.size_ids:
            if pid not in seen:
                seen.add(pid)
                result.append(pid)
        return result

    def matched_rules_for(self, pid: int) -> List[str]:
        """返回命中该条目的规则名（"age"/"size"）。"""
        rules = []
        if pid in self.age_ids:
            rules.append("age")
        if pid in self.size_ids:
            rules.append("size")
        return rules


def build_cleanup_plan(
    session: Session,
    policy: Optional[RecycleBinConfig] = None,
    now: Optional[datetime] = None,
) -> CleanupPlan:
    """构建清理计划；规则 disabled 或单位未知时对应规则整体 no-op。"""
    policy = policy or RecycleBinConfig()
    now = now or datetime.now()
    rows = list(
        session.execute(
            select(RecycledConfig).order_by(
                RecycledConfig.deleted_at.asc(), RecycledConfig.id.asc()
            )
        ).scalars()
    )
    total_before = sum(row.estimated_size_bytes for row in rows)

    age_ids: List[int] = []
    age_rule = policy.age
    if age_rule.enabled and age_rule.unit in _AGE_FACTORS:
        age_cutoff = now - timedelta(days=age_rule.value * _AGE_FACTORS[age_rule.unit])
        for row in rows:
            if row.deleted_at < age_cutoff:
                age_ids.append(row.id)

    # 容量规则只在剔除年龄命中后的剩余集合上计算，避免双重扣减
    remaining = [row for row in rows if row.id not in age_ids]
    total = sum(row.estimated_size_bytes for row in remaining)
    size_ids: List[int] = []
    blocked_by_retain = False
    size_rule = policy.size
    if size_rule.enabled and size_rule.unit in _SIZE_FACTORS:
        limit = size_rule.value * _SIZE_FACTORS[size_rule.unit]
        retain_cutoff = now - timedelta(hours=max(0, policy.min_retain_hours))
        for row in remaining:
            if total <= limit:
                break
            if row.deleted_at > retain_cutoff:
                blocked_by_retain = True
                continue
            size_ids.append(row.id)
            total -= row.estimated_size_bytes

    return CleanupPlan(
        age_ids=age_ids,
        size_ids=size_ids,
        total_bytes_before=total_before,
        total_bytes_after=total,
        would_converge=not blocked_by_retain,
    )


def run_recycle_bin_cleanup(
    session: Session,
    policy: Optional[RecycleBinConfig] = None,
    now: Optional[datetime] = None,
) -> dict:
    """执行清理：逐条删除（删前重查 id 防竞态），返回统计 dict。"""
    plan = build_cleanup_plan(session, policy=policy, now=now)
    purged_count = 0
    freed_bytes = 0
    for pid in plan.all_target_ids():
        entry = session.get(RecycledConfig, pid)
        if entry is None:
            # 计划生成后被并发删除，跳过
            continue
        try:
            session.delete(entry)
            session.flush()
            purged_count += 1
            freed_bytes += entry.estimated_size_bytes
        except Exception:  # noqa: BLE001 - 单条失败不阻断整轮清理
            session.rollback()
            continue
    return {"purged_count": purged_count, "freed_bytes": freed_bytes}
