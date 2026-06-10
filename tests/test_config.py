"""Tests for environment parsing and access control helpers."""

from bot.config import Config, _get_int_list


def test_admin_ids_parsed():
    # conftest sets ADMIN_IDS="222,333" and OWNER_ID=111.
    assert 222 in Config.ADMIN_IDS
    assert 333 in Config.ADMIN_IDS


def test_is_admin():
    assert Config.is_admin(Config.OWNER_ID)
    assert Config.is_admin(222)
    assert not Config.is_admin(999999)


def test_get_int_list_handles_mixed_separators(monkeypatch):
    monkeypatch.setenv("SOME_IDS", "1, 2  3,4")
    assert _get_int_list("SOME_IDS") == [1, 2, 3, 4]


def test_get_int_list_ignores_invalid(monkeypatch):
    monkeypatch.setenv("SOME_IDS", "1,foo,3")
    assert _get_int_list("SOME_IDS") == [1, 3]
