"""mclog.watcher 测试（PLAN.md §3.7 / A10 / A20 / R24-R26 / T5）。"""

from __future__ import annotations

import pytest

from conftest import App
from y33bot.mclog.watcher import MAX_BUFFER_BYTES, LogWatcher
from y33bot.state import StateStore

JOIN_LINE = "[12:00:04] [Server thread/INFO]: Steve joined the game\n"
QUIT_LINE = "[12:00:05] [Server thread/INFO]: Steve left the game\n"
CHAT_LINE = "[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #大家好\n"
NOISE_LINE = "[12:00:02] [Server thread/INFO]: Preparing spawn area: 12%\n"


def _watcher(app: App, store: StateStore | None = None, server: str = "main") -> tuple[LogWatcher, StateStore]:
    target = app.config.server(server)
    assert target is not None
    state = store if store is not None else app.state()
    return LogWatcher(target, app.config.patterns, state), state


def test_reads_existing_content_then_only_new(app: App) -> None:
    app.write_log(JOIN_LINE)
    watcher, _ = _watcher(app)

    first = watcher.poll_new_events()
    assert [event.kind for event in first] == ["join"]
    assert first[0].server == "main"
    assert watcher.poll_new_events() == []

    app.write_log(CHAT_LINE)
    second = watcher.poll_new_events()
    assert [event.kind for event in second] == ["chat"]
    assert second[0].message == "#大家好"
    assert watcher.poll_new_events() == []


def test_offset_advances_to_file_size(app: App) -> None:
    app.write_log(JOIN_LINE + QUIT_LINE)
    watcher, store = _watcher(app)
    watcher.poll_new_events()
    assert store.server_state("main").log_offset == app.log_path.stat().st_size


def test_offset_persisted_across_restart(app: App) -> None:
    app.write_log(JOIN_LINE)
    watcher, store = _watcher(app)
    assert len(watcher.poll_new_events()) == 1
    store.save()

    app.write_log(CHAT_LINE)
    restarted, _ = _watcher(app)  # 新实例、新 store：从磁盘续读
    events = restarted.poll_new_events()
    assert [event.kind for event in events] == ["chat"]


def test_partial_line_buffered_until_complete(app: App) -> None:
    app.write_log(JOIN_LINE[:20])
    watcher, store = _watcher(app)
    assert watcher.poll_new_events() == []
    assert watcher.buffered_bytes == 20
    assert store.server_state("main").log_offset == 20

    app.write_log(JOIN_LINE[20:])
    events = watcher.poll_new_events()
    assert [event.kind for event in events] == ["join"]
    assert watcher.buffered_bytes == 0


def test_multibyte_split_across_polls(app: App) -> None:
    line = "[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #你好\n"
    raw = line.encode("utf-8")
    cut = raw.index("你".encode()) + 1  # 切在多字节字符中间
    app.log_path.write_bytes(raw[:cut])

    watcher, _ = _watcher(app)
    assert watcher.poll_new_events() == []

    with app.log_path.open("ab") as handle:
        handle.write(raw[cut:])
    events = watcher.poll_new_events()
    assert len(events) == 1
    assert events[0].message == "#你好"


def test_crlf_is_tolerated(app: App) -> None:
    app.log_path.write_bytes(("x\n" + CHAT_LINE).replace("\n", "\r\n").encode("utf-8"))
    watcher, _ = _watcher(app)
    events = watcher.poll_new_events()
    assert [event.kind for event in events] == ["chat"]
    assert events[0].message == "#大家好"


def test_unmatched_lines_ignored(app: App) -> None:
    app.write_log(NOISE_LINE + JOIN_LINE)
    watcher, _ = _watcher(app)
    events = watcher.poll_new_events()
    assert [event.kind for event in events] == ["join"]


def test_rotation_resets_offset(app: App, caplog: pytest.LogCaptureFixture) -> None:
    app.write_log(JOIN_LINE + QUIT_LINE)
    watcher, store = _watcher(app)
    assert len(watcher.poll_new_events()) == 2

    app.truncate_log()
    app.write_log(JOIN_LINE)

    with caplog.at_level("WARNING"):
        events = watcher.poll_new_events()
    assert [event.kind for event in events] == ["join"]
    assert store.server_state("main").log_offset == len(JOIN_LINE)
    assert any("日志文件缩小" in record.getMessage() for record in caplog.records)


def test_missing_file_warns_once_then_recovers(app: App, caplog: pytest.LogCaptureFixture) -> None:
    app.log_path.unlink()
    watcher, _ = _watcher(app)
    with caplog.at_level("WARNING"):
        assert watcher.poll_new_events() == []
        assert watcher.poll_new_events() == []
    warnings = [record for record in caplog.records if "日志文件不可读" in record.getMessage()]
    assert len(warnings) == 1

    app.write_log(JOIN_LINE)
    events = watcher.poll_new_events()
    assert [event.kind for event in events] == ["join"]


def test_empty_file_returns_nothing(app: App) -> None:
    watcher, _ = _watcher(app)
    assert watcher.poll_new_events() == []
    assert watcher.compiled.encoding == "utf-8"
    assert watcher.server.name == "main"


def test_oversized_buffer_flushed(app: App, caplog: pytest.LogCaptureFixture) -> None:
    app.log_path.write_bytes(b"x" * (MAX_BUFFER_BYTES + 10))
    watcher, _ = _watcher(app)
    with caplog.at_level("WARNING"):
        events = watcher.poll_new_events()
    assert events == []
    assert watcher.buffered_bytes == 0
    assert any("残行缓冲超过" in record.getMessage() for record in caplog.records)


def test_broken_encoding_does_not_crash(app: App) -> None:
    # 坏字节被 errors="replace" 吃掉；行首已被污染，因此不产生事件，但轮询必须继续可用
    app.log_path.write_bytes(b"\xff\xfe[12:00:04] [Server thread/INFO]: Steve joined the game\n")
    watcher, _ = _watcher(app)
    assert watcher.poll_new_events() == []

    app.write_log(JOIN_LINE)
    events = watcher.poll_new_events()
    assert [event.kind for event in events] == ["join"]


def test_decode_error_replacement(app: App) -> None:
    app.log_path.write_bytes(
        b"[12:00:01] [Async Chat Thread - #0/INFO]: <Steve> #\xff\xfe\n" + JOIN_LINE.encode("utf-8")
    )
    watcher, _ = _watcher(app)
    events = watcher.poll_new_events()
    assert [event.kind for event in events] == ["chat", "join"]
