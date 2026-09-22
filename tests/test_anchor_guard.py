# -*- coding: utf-8 -*-
"""锚点不可用时的快速失败与笛卡尔积防护测试。

对应 .trellis/tasks/09-15-anchor-explosion 的 AC1 / AC2 / AC3。

背景：`create_anchor_by_sas_names` 原本在锚点匹配失败时把全表 `_ANCHOR` 置为同一个
空字符串并继续执行，下游 `pd.merge(on="_ANCHOR", how="outer")` 因此退化为笛卡尔积
（N_new × N_old），导致任务内存爆炸且长时间无法结束。
"""

import os
import threading

import pandas as pd
import pytest
from openpyxl import Workbook, load_workbook

from src.backend.domain import data_comparison
from src.backend.domain.data_comparison import (
    AnchorUnavailableError,
    create_anchor_by_sas_names,
    perform_full_comparison,
    process_edc_multithreaded,
)
from src.backend.infrastructure.config_manager import ConfigManager


def _df_with_sas(data, sas_names=None):
    """构造带 sas_file_name attrs 的 DataFrame。"""
    frame = pd.DataFrame(data)
    frame.attrs["sas_file_name"] = (
        list(frame.columns) if sas_names is None else sas_names
    )
    frame.attrs["sas_name_to_label"] = {name: name for name in frame.columns}
    return frame


class _Recorder:
    def __init__(self):
        self.messages = []

    def safe_log(self, message):
        self.messages.append(message)


# --------------------------------------------------------------------------
# AC1 · 锚点不可用必须快速失败
# --------------------------------------------------------------------------


def test_anchor_missing_sas_names_raises() -> None:
    """没有 SASFieldName 信息时无法构造锚点，必须快速失败。"""
    frame = pd.DataFrame({"SUBJID": ["001"]})
    frame.attrs["sas_file_name"] = []

    with pytest.raises(AnchorUnavailableError, match="SASFieldName"):
        create_anchor_by_sas_names(frame, ["SUBJID"], None, "AE")


def test_anchor_no_matched_keys_raises() -> None:
    """一个锚点列都匹配不上时必须快速失败，且错误信息可操作。"""
    frame = _df_with_sas({"FOO": ["x"], "BAR": ["y"]})

    with pytest.raises(AnchorUnavailableError) as excinfo:
        create_anchor_by_sas_names(frame, ["SUBJID", "VISITNUM"], None, "AE")

    message = str(excinfo.value)
    assert "AE" in message
    assert "SUBJID" in message and "VISITNUM" in message
    # 不得泄露单元格内容（错误信息里只允许出现表单名与字段名）
    assert "x1" not in message and "y1" not in message


def test_anchor_key_not_in_columns_raises() -> None:
    """attrs 声明了锚点列但 DataFrame 实际没有该列时，必须快速失败而不是置空。"""
    frame = pd.DataFrame({"OTHER": ["v"]})
    frame.attrs["sas_file_name"] = ["SUBJID", "OTHER"]

    with pytest.raises(AnchorUnavailableError, match="SUBJID"):
        create_anchor_by_sas_names(frame, ["SUBJID"], None, "AE")


def test_anchor_construction_error_raises() -> None:
    """锚点构造过程本身出错时，不得静默置空。"""

    class Exploding(pd.DataFrame):
        @property
        def _constructor(self):
            return Exploding

        def __getitem__(self, key):
            if isinstance(key, list):
                raise RuntimeError("boom")
            return super().__getitem__(key)

    frame = Exploding({"SUBJID": ["001"]})
    frame.attrs["sas_file_name"] = ["SUBJID"]

    with pytest.raises(AnchorUnavailableError):
        create_anchor_by_sas_names(frame, ["SUBJID"], None, "AE")


# --------------------------------------------------------------------------
# AC3 · 防误伤：合法场景不得被拦
# --------------------------------------------------------------------------


def test_anchor_duplicate_values_still_allowed() -> None:
    """锚点重复是合法场景（原代码只告警），不得升级为失败。"""
    frame = _df_with_sas({"SUBJID": ["001", "001", "002"], "V": [1, 2, 3]})
    recorder = _Recorder()

    result = create_anchor_by_sas_names(
        frame, ["SUBJID"], recorder.safe_log, "AE"
    )

    assert list(result["_ANCHOR"]) == ["001", "001", "002"]
    assert any("锚点重复" in message for message in recorder.messages)


def test_anchor_multi_key_join_unchanged() -> None:
    """多锚点列正常拼接行为保持不变。"""
    frame = _df_with_sas({"SUBJID": ["001"], "VISITNUM": ["1"], "V": ["x"]})

    result = create_anchor_by_sas_names(
        frame, ["SUBJID", "VISITNUM"], None, "AE"
    )

    assert list(result["_ANCHOR"]) == ["001###1"]


# --------------------------------------------------------------------------
# AC1 核心 · 绝不进入 pd.merge
# --------------------------------------------------------------------------


def test_perform_full_comparison_never_merges_on_anchor_failure(monkeypatch) -> None:
    """锚点失败时必须在 pd.merge 之前抛出——这是笛卡尔积爆炸的回归保护。"""

    def exploding_merge(*_args, **_kwargs):
        raise AssertionError("锚点失败时不应调用 pd.merge")

    monkeypatch.setattr(data_comparison.pd, "merge", exploding_merge)

    old_df = _df_with_sas({"FOO": ["a"] * 5})
    new_df = _df_with_sas({"FOO": ["b"] * 5})
    recorder = _Recorder()

    with pytest.raises(AnchorUnavailableError):
        perform_full_comparison(
            "AE",
            old_df,
            new_df,
            ["SUBJID"],
            ConfigManager(),
            recorder,
        )


def test_anchor_error_is_not_interrupted_error() -> None:
    """AnchorUnavailableError 必须能被 process_single_sheet_complete 的
    `except Exception` 接住，且不得与用户停止语义混淆。"""
    assert issubclass(AnchorUnavailableError, Exception)
    assert not issubclass(AnchorUnavailableError, InterruptedError)


# --------------------------------------------------------------------------
# AC3 · 防爆闸：拦住双侧塌缩，放行正常场景
# --------------------------------------------------------------------------


def _anchored(anchors):
    frame = pd.DataFrame({"V": list(range(len(anchors)))})
    frame["_ANCHOR"] = anchors
    return frame


def test_guard_blocks_double_collapse() -> None:
    """新旧两侧锚点都塌缩为单一取值且规模超阈值时必须拦截。"""
    new_df = _anchored([""] * 2000)
    old_df = _anchored([""] * 2000)

    with pytest.raises(AnchorUnavailableError, match="笛卡尔积"):
        data_comparison._guard_anchor_cardinality(new_df, old_df, "AE", None)


def test_guard_allows_single_side_collapse() -> None:
    """只有一侧塌缩时外连接是 N+M 量级，不构成爆炸，必须放行。"""
    new_df = _anchored([""] * 2000)
    old_df = _anchored([str(i) for i in range(2000)])

    data_comparison._guard_anchor_cardinality(new_df, old_df, "AE", None)


def test_guard_allows_normal_duplicates() -> None:
    """存在多个重复锚点值是合法场景，不得误伤。"""
    new_df = _anchored([str(i % 50) for i in range(2000)])
    old_df = _anchored([str(i % 50) for i in range(2000)])

    data_comparison._guard_anchor_cardinality(new_df, old_df, "AE", None)


def test_guard_allows_small_tables_even_when_collapsed() -> None:
    """小表即使锚点塌缩也不会爆炸，阈值以下一律放行。"""
    new_df = _anchored([""] * 3)
    old_df = _anchored([""] * 3)

    data_comparison._guard_anchor_cardinality(new_df, old_df, "AE", None)


def test_guard_ignores_frames_without_anchor_column() -> None:
    """没有 _ANCHOR 列时闸门不应报错。"""
    data_comparison._guard_anchor_cardinality(
        pd.DataFrame({"V": [1]}), pd.DataFrame({"V": [1]}), "AE", None
    )


# --------------------------------------------------------------------------
# AC2 · 单表单失败不拖垮整个任务（端到端）
# --------------------------------------------------------------------------


def _make_wb(path, sheets):
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, frame in sheets.items():
        worksheet = workbook.create_sheet(title=name)
        worksheet.append(list(frame.columns))
        for row in frame.itertuples(index=False):
            worksheet.append(list(row))
    workbook.save(path)


def test_anchorless_sheet_is_skipped_and_job_completes(tmp_path) -> None:
    """一个表单锚点失效时，它被跳过，其余表单照常输出，任务整体成功。"""
    old_path = os.path.join(str(tmp_path), "old.xlsx")
    new_path = os.path.join(str(tmp_path), "new.xlsx")
    out_path = os.path.join(str(tmp_path), "out.xlsx")

    # GOOD 有 SUBJID 锚点；BAD 完全没有锚点列，旧实现会在此产生笛卡尔积
    good_old = pd.DataFrame({"SUBJID": ["001"], "V": ["a"]})
    good_new = pd.DataFrame({"SUBJID": ["001"], "V": ["b"]})
    bad_old = pd.DataFrame({"FOO": ["x1", "x2"], "BAR": ["y1", "y2"]})
    bad_new = pd.DataFrame({"FOO": ["x3", "x4"], "BAR": ["y3", "y4"]})

    _make_wb(old_path, {"GOOD": good_old, "BAD": bad_old})
    _make_wb(new_path, {"GOOD": good_new, "BAD": bad_new})

    messages = []
    config = ConfigManager()
    config.update_from_parameters({"default_keys": ["SUBJID"]}, {})

    result_path = process_edc_multithreaded(
        old_path,
        new_path,
        out_path,
        messages.append,
        config=config,
        stop_flag=threading.Event(),
    )

    # 任务成功产出报告，而不是整体失败
    assert result_path
    workbook = load_workbook(result_path)

    # 锚点有效的表单正常输出；锚点失效的表单被跳过
    assert "GOOD" in workbook.sheetnames
    assert "BAD" not in workbook.sheetnames

    # 日志里有可操作的失败原因
    joined = "\n".join(messages)
    assert "BAD" in joined
    assert "锚点" in joined
