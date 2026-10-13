"""binding 模块测试（PLAN.md §4.2 / R20-R23 / T3）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from y33bot.binding import GAME_ID_PATTERN, BindingError, BindingStore, is_valid_game_id


def test_missing_file_is_empty(tmp_path: Path) -> None:
    store = BindingStore.load(tmp_path / "data" / "bindings.toml")
    assert len(store) == 0
    assert store.items() == {}
    assert store.lookup("nobody") is None


def test_bind_save_reload_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "data" / "bindings.toml"
    store = BindingStore.load(path)
    store.bind("OPENID-1", "Steve")
    store.bind("OPENID-2", "Alex")
    store.save()

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()  # 原子替换后不留临时文件

    reloaded = BindingStore.load(path)
    assert reloaded.lookup("OPENID-1") == "Steve"
    assert reloaded.lookup("OPENID-2") == "Alex"
    assert reloaded.items() == {"OPENID-1": "Steve", "OPENID-2": "Alex"}
    assert "OPENID-1" in reloaded


def test_bind_overwrites_same_openid(tmp_path: Path) -> None:
    store = BindingStore.load(tmp_path / "bindings.toml")
    store.bind("OPENID-1", "Steve")
    store.bind("OPENID-1", "Notch")
    assert store.items() == {"OPENID-1": "Notch"}
    assert len(store) == 1


def test_unbind(tmp_path: Path) -> None:
    store = BindingStore.load(tmp_path / "bindings.toml")
    store.bind("OPENID-1", "Steve")
    assert store.unbind("OPENID-1") is True
    assert store.unbind("OPENID-1") is False
    assert store.items() == {}


@pytest.mark.parametrize("game_id", ["ab", "a" * 17, "bad name", "名字", ""])
def test_bind_rejects_invalid_game_id(tmp_path: Path, game_id: str) -> None:
    store = BindingStore.load(tmp_path / "bindings.toml")
    with pytest.raises(BindingError, match="游戏ID 不合法"):
        store.bind("OPENID-1", game_id)


def test_bind_rejects_empty_openid(tmp_path: Path) -> None:
    store = BindingStore.load(tmp_path / "bindings.toml")
    with pytest.raises(BindingError, match="qq_openid 不能为空"):
        store.bind("   ", "Steve")


@pytest.mark.parametrize("game_id", ["Steve", "a_b1", "A" * 16, "abc"])
def test_valid_game_id(game_id: str) -> None:
    assert is_valid_game_id(game_id)
    assert GAME_ID_PATTERN.match(game_id)


def test_corrupt_file_raises_and_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "bindings.toml"
    original = "[[bindings]\nqq_openid = "
    path.write_text(original, encoding="utf-8")
    with pytest.raises(BindingError, match="不是合法 TOML"):
        BindingStore.load(path)
    assert path.read_text(encoding="utf-8") == original  # 人工数据被保护


def test_entry_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "bindings.toml"
    path.write_text('[[bindings]]\nqq_openid = "A"\n', encoding="utf-8")
    with pytest.raises(BindingError, match="缺少 game_id"):
        BindingStore.load(path)


def test_bindings_must_be_array(tmp_path: Path) -> None:
    path = tmp_path / "bindings.toml"
    path.write_text('bindings = "nope"\n', encoding="utf-8")
    with pytest.raises(BindingError, match="必须是数组"):
        BindingStore.load(path)


def test_hand_written_file_is_read(tmp_path: Path) -> None:
    path = tmp_path / "bindings.toml"
    path.write_text(
        '[[bindings]]\nqq_openid = " 1A2B3C4D "\ngame_id = " Steve "\n'
        '\n[[bindings]]\nqq_openid = "X"\ngame_id = "Alex"\n',
        encoding="utf-8",
    )
    store = BindingStore.load(path)
    assert store.items() == {"1A2B3C4D": "Steve", "X": "Alex"}
