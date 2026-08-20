"""路径安全工具测试：白名单包含性、穿越、符号链接逃逸与编码绕过。"""

import os

from src.backend.infrastructure import path_security


def test_is_safe_path_accepts_within_root(tmp_path) -> None:
    root = str(tmp_path)
    target = str(tmp_path / "sub" / "file.xlsx")
    os.makedirs(os.path.dirname(target), exist_ok=True)

    safe, _ = path_security.is_safe_path(target, [root])

    assert safe


def test_is_safe_path_accepts_root_itself(tmp_path) -> None:
    root = str(tmp_path)

    safe, _ = path_security.is_safe_path(root, [root])

    assert safe


def test_is_safe_path_rejects_outside_root(tmp_path) -> None:
    root = str(tmp_path / "allowed")
    os.makedirs(root, exist_ok=True)
    outside = str(tmp_path / "secret.txt")
    open(outside, "w").close()

    safe, message = path_security.is_safe_path(outside, [root])

    assert not safe
    assert "允许的目录" in message


def test_is_safe_path_rejects_traversal(tmp_path) -> None:
    root = str(tmp_path)
    target = os.path.join(root, "..", "..", "etc", "passwd")

    safe, _ = path_security.is_safe_path(target, [root])

    assert not safe


def test_is_safe_path_rejects_symlink_escape(tmp_path) -> None:
    root = str(tmp_path / "root")
    outside_dir = str(tmp_path / "outside")
    os.makedirs(root, exist_ok=True)
    os.makedirs(outside_dir, exist_ok=True)
    secret = os.path.join(outside_dir, "secret.txt")
    open(secret, "w").close()
    link = os.path.join(root, "escape")
    os.symlink(outside_dir, link)

    target = os.path.join(link, "secret.txt")
    safe, _ = path_security.is_safe_path(target, [root])

    assert not safe


def test_is_safe_path_rejects_empty() -> None:
    safe, message = path_security.is_safe_path("", ["/tmp"])

    assert not safe
    assert "不能为空" in message


def test_validate_asset_raw_path_rejects_traversal() -> None:
    safe, _ = path_security.validate_asset_raw_path("../../etc/passwd")

    assert not safe


def test_validate_asset_raw_path_rejects_backslash() -> None:
    safe, _ = path_security.validate_asset_raw_path("assets\\..\\evil")

    assert not safe


def test_validate_asset_raw_path_rejects_absolute() -> None:
    safe, _ = path_security.validate_asset_raw_path("/etc/passwd")

    assert not safe


def test_validate_asset_raw_path_rejects_windows_drive() -> None:
    safe, _ = path_security.validate_asset_raw_path("C:/Windows/win.ini")

    assert not safe


def test_validate_asset_raw_path_rejects_url_encoded_traversal() -> None:
    safe, _ = path_security.validate_asset_raw_path("..%2F..%2Fetc%2Fpasswd")

    assert not safe


def test_validate_asset_raw_path_accepts_normal(monkeypatch) -> None:
    safe, _ = path_security.validate_asset_raw_path("assets/app.abc123.js")

    assert safe
