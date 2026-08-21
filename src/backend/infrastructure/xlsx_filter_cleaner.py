"""Byte-preserving cleanup helpers for filter state in OOXML zip packages."""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from typing import Any, Callable, Iterator, List, Optional, Set, Tuple

from ...shared.contracts import LogFunc
from ..domain.processing_control import check_stop_frequently

_TAG = rb"(?:[A-Za-z_][\w.\-]*:)?"
_ATTRS = rb"(?:[^>\"']|\"[^\"]*\"|'[^']*')*?"
_AUTOFILTER_RE = re.compile(
    rb"<(?P<tag>" + _TAG + rb"autoFilter)\b(?P<attrs>" + _ATTRS + rb")"
    rb"(?:/>|>.*?</(?P=tag)\s*>)",
    re.DOTALL,
)
_ROW_START_RE = rb"<(?P<tag>" + _TAG + rb"row)\b(?P<attrs>" + _ATTRS + rb")"
_ROW_TAG_RE = re.compile(_ROW_START_RE + rb"(?P<slash>/?)>")
_DEFINED_NAME_RE = re.compile(
    rb"<(?P<tag>" + _TAG + rb"definedName)\b(?P<attrs>" + _ATTRS + rb")"
    rb"(?:/>|>.*?</(?P=tag)\s*>)",
    re.DOTALL,
)
_NON_ELEMENT_RE = re.compile(
    rb"<!--.*?-->|<!\[CDATA\[.*?\]\]|<\?.*?\?>",
    re.DOTALL,
)
_XML_WHITESPACE = b" \t\r\n"
_PACKAGE_READ_ERRORS = (
    zipfile.BadZipFile,
    RuntimeError,
    EOFError,
    KeyError,
    zlib.error,
)


class NotAnOoxmlPackageError(ValueError):
    """Raised when a file is not a readable OOXML zip package."""


@dataclass(frozen=True)
class CleanupOptions:
    """Select which filter-related OOXML attributes should be removed."""

    remove_sheet_autofilter: bool = True
    remove_table_autofilter: bool = True
    unhide_rows: bool = True
    remove_filter_database: bool = False


@dataclass(frozen=True)
class FilterCleanupResult:
    """Statistics from one package cleanup attempt."""

    rewritten: bool
    parts_scanned: int
    parts_modified: int
    sheet_autofilters_removed: int
    table_autofilters_removed: int
    hidden_rows_restored: int
    defined_names_removed: int


@dataclass(frozen=True)
class _CleanupCounts:
    sheet_autofilters_removed: int = 0
    table_autofilters_removed: int = 0
    hidden_rows_restored: int = 0
    defined_names_removed: int = 0

    def add(self, other: "_CleanupCounts") -> "_CleanupCounts":
        return _CleanupCounts(
            self.sheet_autofilters_removed + other.sheet_autofilters_removed,
            self.table_autofilters_removed + other.table_autofilters_removed,
            self.hidden_rows_restored + other.hidden_rows_restored,
            self.defined_names_removed + other.defined_names_removed,
        )


@dataclass(frozen=True)
class _ScanResult:
    dirty_parts: Set[int]
    parts_scanned: int


def _mask_non_element_regions(xml: bytes) -> bytes:
    """Mask comments, CDATA, and processing instructions for tag scanning."""
    masked = bytearray(xml)
    for match in _NON_ELEMENT_RE.finditer(xml):
        start, end = match.start(), match.end()
        masked[slice(start, end)] = b" " * (end - start)
    return bytes(masked)


def _iter_attributes(
    attrs: bytes,
) -> Iterator[Tuple[int, int, bytes, bytes]]:
    """Yield byte spans and values for syntactically valid quoted
    attributes."""
    index = 0
    length = len(attrs)
    while index < length:
        leading_start = index
        while index < length and attrs[index] in _XML_WHITESPACE:
            index += 1
        if index >= length:
            break

        name_start = index
        while index < length and attrs[index] not in _XML_WHITESPACE + b"=":
            index += 1
        if index == name_start:
            index += 1
            continue
        name = attrs[name_start:index]

        while index < length and attrs[index] in _XML_WHITESPACE:
            index += 1
        if index >= length or attrs[index] != ord("="):
            continue
        index += 1
        while index < length and attrs[index] in _XML_WHITESPACE:
            index += 1
        if index >= length or attrs[index] not in (ord('"'), ord("'")):
            continue

        quote = attrs[index]
        value_start = index + 1
        value_end = attrs.find(bytes((quote,)), value_start)
        if value_end < 0:
            break
        yield leading_start, value_end + 1, name, attrs[value_start:value_end]
        index = value_end + 1


def _remove_matching_attributes(
    attrs: bytes,
    predicate: Callable[[bytes, bytes], bool],
) -> Tuple[bytes, int]:
    removals = [
        (start, end)
        for start, end, name, value in _iter_attributes(attrs)
        if predicate(name, value)
    ]
    if not removals:
        return attrs, 0

    chunks: List[bytes] = []
    cursor = 0
    for start, end in removals:
        chunks.append(attrs[cursor:start])
        cursor = end
    chunks.append(attrs[cursor:])
    return b"".join(chunks), len(removals)


def _remove_element_spans(
    xml: bytes,
    spans: Iterator[Tuple[int, int]],
) -> bytes:
    chunks: List[bytes] = []
    cursor = 0
    for start, end in spans:
        chunks.append(xml[cursor:start])
        cursor = end
    chunks.append(xml[cursor:])
    return b"".join(chunks)


def _iter_element_spans(
    pattern: re.Pattern,
    xml: bytes,
) -> Iterator[Tuple[int, int]]:
    masked = _mask_non_element_regions(xml)
    for match in pattern.finditer(masked):
        yield match.start(), match.end()


def strip_autofilter(xml: bytes) -> Tuple[bytes, int]:
    """Remove actual autoFilter elements without reserializing
    surrounding XML."""
    spans = list(_iter_element_spans(_AUTOFILTER_RE, xml))
    if not spans:
        return xml, 0
    return _remove_element_spans(xml, iter(spans)), len(spans)


def _has_autofilter(xml: bytes) -> bool:
    return any(_AUTOFILTER_RE.finditer(_mask_non_element_regions(xml)))


def _is_hidden_attribute(name: bytes, value: bytes) -> bool:
    return name == b"hidden" and value.lower() in (b"1", b"true")


def _rewrite_row_tag(tag: bytes) -> Tuple[bytes, int]:
    match = _ROW_TAG_RE.fullmatch(tag)
    if match is None:
        return tag, 0
    attrs = match.group("attrs")
    cleaned_attrs, count = _remove_matching_attributes(
        attrs,
        _is_hidden_attribute,
    )
    if not count:
        return tag, 0
    row_parts = (
        b"<",
        match.group("tag"),
        cleaned_attrs,
        match.group("slash"),
        b">",
    )
    return b"".join(row_parts), count


def unhide_rows(xml: bytes) -> Tuple[bytes, int]:
    """Remove true hidden attributes from worksheet row start tags only."""
    masked = _mask_non_element_regions(xml)
    replacements = []
    for match in _ROW_TAG_RE.finditer(masked):
        start, end = match.start(), match.end()
        cleaned_tag, count = _rewrite_row_tag(xml[start:end])
        if count:
            replacements.append((start, end, cleaned_tag, count))

    if not replacements:
        return xml, 0

    chunks: List[bytes] = []
    cursor = 0
    removed = 0
    for start, end, replacement, count in replacements:
        chunks.extend((xml[cursor:start], replacement))
        cursor = end
        removed += count
    chunks.append(xml[cursor:])
    return b"".join(chunks), removed


def _has_removable_hidden_row(xml: bytes) -> bool:
    masked = _mask_non_element_regions(xml)
    return any(
        _rewrite_row_tag(xml[slice(match.start(), match.end())])[1]
        for match in _ROW_TAG_RE.finditer(masked)
    )


def _is_filter_database_attribute(name: bytes, value: bytes) -> bool:
    return name == b"name" and value == b"_xlnm._FilterDatabase"


def _element_has_filter_database(element: bytes) -> bool:
    match = _DEFINED_NAME_RE.fullmatch(element)
    return bool(
        match
        and any(
            _is_filter_database_attribute(name, value)
            for _, _, name, value in _iter_attributes(match.group("attrs"))
        )
    )


def strip_filter_database(xml: bytes) -> Tuple[bytes, int]:
    """Remove defined names used as Excel filter database ranges."""
    masked = _mask_non_element_regions(xml)
    spans = []
    for match in _DEFINED_NAME_RE.finditer(masked):
        start, end = match.start(), match.end()
        if _element_has_filter_database(xml[start:end]):
            spans.append((start, end))
    if not spans:
        return xml, 0
    return _remove_element_spans(xml, iter(spans)), len(spans)


def _has_filter_database(xml: bytes) -> bool:
    masked = _mask_non_element_regions(xml)
    return any(
        _element_has_filter_database(xml[slice(match.start(), match.end())])
        for match in _DEFINED_NAME_RE.finditer(masked)
    )


def _is_worksheet_part(name: str) -> bool:
    return (
        name.startswith("xl/worksheets/")
        and name.endswith(".xml")
        and "/_rels/" not in name
    )


def _is_table_part(name: str) -> bool:
    return name.startswith("xl/tables/") and name.endswith(".xml")


def _is_workbook_part(name: str) -> bool:
    return name == "xl/workbook.xml"


def _part_may_be_dirty(
    name: str,
    data: bytes,
    options: CleanupOptions,
) -> bool:
    if _is_worksheet_part(name):
        sheet_filter_enabled = options.remove_sheet_autofilter
        sheet_filter_dirty = sheet_filter_enabled and _has_autofilter(data)
        can_unhide_rows = _has_removable_hidden_row(data)
        row_filter_dirty = options.unhide_rows and can_unhide_rows
        return sheet_filter_dirty or row_filter_dirty
    if _is_table_part(name):
        table_filter_present = _has_autofilter(data)
        return options.remove_table_autofilter and table_filter_present
    return (
        options.remove_filter_database
        and _is_workbook_part(name)
        and _has_filter_database(data)
    )


def _transform_part(
    name: str, data: bytes, options: CleanupOptions
) -> Tuple[bytes, _CleanupCounts]:
    transformed = data
    counts = _CleanupCounts()
    if _is_worksheet_part(name):
        if options.remove_sheet_autofilter:
            transformed, removed = strip_autofilter(transformed)
            counts = _CleanupCounts(sheet_autofilters_removed=removed)
        if options.unhide_rows:
            transformed, removed = unhide_rows(transformed)
            counts = counts.add(_CleanupCounts(hidden_rows_restored=removed))
    elif _is_table_part(name) and options.remove_table_autofilter:
        transformed, removed = strip_autofilter(transformed)
        counts = _CleanupCounts(table_autofilters_removed=removed)
    elif _is_workbook_part(name) and options.remove_filter_database:
        transformed, removed = strip_filter_database(transformed)
        counts = _CleanupCounts(defined_names_removed=removed)
    return transformed, counts


def _read_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    try:
        with archive.open(info) as entry:
            return entry.read()
    except _PACKAGE_READ_ERRORS as exc:
        raise NotAnOoxmlPackageError(
            f"无法读取 OOXML 部件 {info.filename}: {exc}"
        ) from exc


def _scan_dirty_parts(
    archive: zipfile.ZipFile,
    options: CleanupOptions,
    log_func: Optional[LogFunc],
    stop_flag: Optional[Any],
) -> _ScanResult:
    dirty_parts: Set[int] = set()
    parts_scanned = 0
    for entry_index, info in enumerate(archive.infolist()):
        check_stop_frequently(log_func, stop_flag)
        if not (
            _is_worksheet_part(info.filename)
            or _is_table_part(info.filename)
            or _is_workbook_part(info.filename)
        ):
            continue
        data = _read_entry(archive, info)
        if _part_may_be_dirty(info.filename, data, options):
            dirty_parts.add(entry_index)
        parts_scanned += 1
    return _ScanResult(dirty_parts, parts_scanned)


def _clone_entry_info(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    clone.compress_type = info.compress_type
    clone.external_attr = info.external_attr
    clone.internal_attr = info.internal_attr
    clone.create_system = info.create_system
    clone.comment = info.comment
    clone.extra = info.extra
    clone.create_version = info.create_version
    clone.extract_version = info.extract_version
    clone.volume = info.volume
    clone.reserved = info.reserved
    return clone


def _rewrite_package(
    source: zipfile.ZipFile,
    destination: zipfile.ZipFile,
    dirty_parts: Set[int],
    options: CleanupOptions,
    log_func: Optional[LogFunc],
    stop_flag: Optional[Any],
) -> Tuple[_CleanupCounts, int]:
    counts = _CleanupCounts()
    parts_modified = 0
    destination.comment = source.comment
    for entry_index, info in enumerate(source.infolist()):
        check_stop_frequently(log_func, stop_flag)
        data = _read_entry(source, info)
        if entry_index in dirty_parts:
            transformed, delta = _transform_part(info.filename, data, options)
            if transformed != data:
                data = transformed
                counts = counts.add(delta)
                parts_modified += 1
        destination.writestr(_clone_entry_info(info), data)
    return counts, parts_modified


def _new_temp_path(path: str) -> Tuple[int, str]:
    directory = os.path.dirname(path) or "."
    filename = os.path.basename(path)
    return tempfile.mkstemp(
        prefix=f".{filename}.rewrite-",
        suffix=".tmp",
        dir=directory,
    )


def _cleanup_temp_path(path: str, log_func: Optional[LogFunc]) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        if log_func:
            try:
                log_func(f"⚠️ 清理 OOXML 重写临时文件失败: {str(exc)}")
            except Exception:
                pass


def _open_scan_result(
    path: str,
    options: CleanupOptions,
    log_func: Optional[LogFunc],
    stop_flag: Optional[Any],
) -> _ScanResult:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            return _scan_dirty_parts(archive, options, log_func, stop_flag)
    except _PACKAGE_READ_ERRORS as exc:
        raise NotAnOoxmlPackageError(f"不是可处理的 OOXML 文件: {exc}") from exc


def remove_filters(
    path: str,
    *,
    options: Optional[CleanupOptions] = None,
    log_func: Optional[LogFunc] = None,
    stop_flag: Optional[Any] = None,
) -> FilterCleanupResult:
    """Remove filter state from an OOXML package using an atomic rewrite."""
    package_path = os.fspath(path)
    active_options = options or CleanupOptions()
    scan = _open_scan_result(package_path, active_options, log_func, stop_flag)
    if not scan.dirty_parts:
        return FilterCleanupResult(False, scan.parts_scanned, 0, 0, 0, 0, 0)

    descriptor, temporary_path = _new_temp_path(package_path)
    descriptor_to_close: Optional[int] = descriptor
    try:
        with os.fdopen(descriptor, "w+b") as temporary_file:
            descriptor_to_close = None
            try:
                with zipfile.ZipFile(package_path, "r") as source:
                    with zipfile.ZipFile(
                        temporary_file, "w", allowZip64=True
                    ) as destination:
                        counts, parts_modified = _rewrite_package(
                            source,
                            destination,
                            scan.dirty_parts,
                            active_options,
                            log_func,
                            stop_flag,
                        )
            except _PACKAGE_READ_ERRORS as exc:
                raise NotAnOoxmlPackageError(f"无法重写 OOXML 文件: {exc}") from exc
        os.replace(temporary_path, package_path)
    finally:
        if descriptor_to_close is not None:
            try:
                os.close(descriptor_to_close)
            except OSError:
                pass
        _cleanup_temp_path(temporary_path, log_func)

    return FilterCleanupResult(
        True,
        scan.parts_scanned,
        parts_modified,
        counts.sheet_autofilters_removed,
        counts.table_autofilters_removed,
        counts.hidden_rows_restored,
        counts.defined_names_removed,
    )
