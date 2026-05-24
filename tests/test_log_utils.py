import builtins

from src.shared.log_utils import log


def test_log_prints_and_delegates_to_callback(capsys) -> None:
    messages = []

    log("message", messages.append)

    assert capsys.readouterr().out == "message\n"
    assert messages == ["message"]


def test_log_allows_missing_callback(capsys) -> None:
    log("message", None)

    assert capsys.readouterr().out == "message\n"


def test_log_falls_back_when_console_encoding_fails(monkeypatch) -> None:
    printed = []
    messages = []

    def fake_print(message):
        if not printed:
            printed.append("failed")
            raise UnicodeEncodeError("ascii", "消息", 0, 1, "unsupported")
        printed.append(message)

    monkeypatch.setattr(builtins, "print", fake_print)

    log("消息", messages.append)

    assert printed == ["failed", "消息"]
    assert messages == ["消息"]
