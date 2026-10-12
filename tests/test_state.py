"""state 模块测试（PLAN.md §4.3 / §4.5.4 / T3）。"""

from __future__ import annotations

import json
from pathlib import Path

from y33bot.state import STATE_VERSION, RuntimeState, ServerState, StateStore


def test_missing_file_defaults(tmp_path: Path) -> None:
    store = StateStore.load(tmp_path / "data" / "state.json")
    assert store.state.version == STATE_VERSION
    assert store.state.qq_msg_seq == 0
    assert store.state.servers == {}


def test_server_state_created_on_demand(tmp_path: Path) -> None:
    store = StateStore.load(tmp_path / "state.json")
    state = store.server_state("main")
    assert state.log_offset == 0
    assert state.health_online is None
    state.log_offset = 42
    assert store.server_state("main").log_offset == 42


def test_save_creates_parent_and_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "data" / "state.json"
    store = StateStore.load(path)
    main = store.server_state("main")
    main.log_offset = 184320
    main.log_size = 184320
    main.log_inode = "281474976711234"
    main.health_online = True
    main.health_changed_at = 1791824536.0
    assert store.next_msg_seq() == 1
    assert store.next_msg_seq() == 2
    store.save()

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == STATE_VERSION
    assert raw["qq"]["msg_seq"] == 2
    assert raw["servers"]["main"]["log_offset"] == 184320

    reloaded = StateStore.load(path)
    main2 = reloaded.server_state("main")
    assert (main2.log_offset, main2.log_size, main2.log_inode) == (184320, 184320, "281474976711234")
    assert main2.health_online is True
    assert main2.health_changed_at == 1791824536.0
    assert reloaded.state.qq_msg_seq == 2


def test_corrupt_json_backed_up_and_reset(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    store = StateStore.load(path)
    assert store.state.servers == {}
    assert (tmp_path / "state.json.bak").exists()
    assert not path.exists()


def test_version_mismatch_backed_up_and_reset(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"version": 99, "qq": {"msg_seq": 5}}), encoding="utf-8")
    store = StateStore.load(path)
    assert store.state.qq_msg_seq == 0
    backup = tmp_path / "state.json.bak"
    assert backup.exists()
    assert json.loads(backup.read_text(encoding="utf-8"))["version"] == 99


def test_bad_field_types_are_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "qq": {"msg_seq": "oops"},
                "servers": {
                    "main": {"log_offset": "x", "log_inode": None, "health_online": "yes", "health_changed_at": "n"},
                    "junk": "not-a-dict",
                },
            }
        ),
        encoding="utf-8",
    )
    store = StateStore.load(path)
    assert store.state.qq_msg_seq == 0
    assert set(store.state.servers) == {"main"}
    main = store.state.servers["main"]
    assert main.log_offset == 0
    assert main.log_inode == ""
    assert main.health_online is None
    assert main.health_changed_at == 0.0


def test_negative_offset_clamped(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"version": 1, "servers": {"main": {"log_offset": -10}}}), encoding="utf-8")
    store = StateStore.load(path)
    assert store.state.servers["main"].log_offset == 0


def test_to_dict_shape(tmp_path: Path) -> None:
    store = StateStore(path=tmp_path / "state.json", state=RuntimeState())
    store.state.servers["main"] = ServerState(log_offset=1)
    payload = store.to_dict()
    assert payload["servers"]["main"]["log_offset"] == 1
    assert payload["qq"] == {"msg_seq": 0}


def test_save_failure_is_logged_not_raised(tmp_path: Path, monkeypatch) -> None:
    store = StateStore.load(tmp_path / "state.json")

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("y33bot.state._atomic_write_bytes", boom)
    store.save()  # 不应抛异常
