"""Тесты устойчивого чтения схемы (ResilientSchema) — без реальной БД."""

from __future__ import annotations

import pytest

from fbschema.db import ResilientSchema, _fallback_charset


class _Primary:
    """Основная схема: 'procedures' не читается (транслитерация), остальное — да."""

    other = "delegated"

    @property
    def procedures(self):
        raise RuntimeError("Cannot transliterate character between character sets")

    @property
    def tables(self):
        return ["T1", "T2"]


class _Fallback:
    @property
    def procedures(self):
        return ["P1", "P2"]


class _Con:
    def __init__(self, schema):
        self.schema = schema
        self.closed = False

    def close(self):
        self.closed = True


def _make():
    cons: list[_Con] = []

    def factory():
        c = _Con(_Fallback())
        cons.append(c)
        return c

    return ResilientSchema(_Primary(), factory, "UTF8"), cons


def test_failing_collection_read_via_fallback():
    rs, cons = _make()
    assert list(rs.procedures) == ["P1", "P2"]   # взято с запасного соединения
    assert len(cons) == 1                          # запасное открыто один раз (лениво)


def test_ok_collection_stays_on_primary():
    rs, cons = _make()
    assert list(rs.tables) == ["T1", "T2"]         # основная схема
    assert cons == []                              # запасное НЕ открывалось


def test_non_collection_attr_delegates_to_primary():
    rs, _ = _make()
    assert rs.other == "delegated"


def test_collection_cached_fallback_opened_once():
    rs, cons = _make()
    list(rs.procedures)
    list(rs.procedures)
    assert len(cons) == 1                          # второй раз — из кэша


def test_close_fallback_closes_connection():
    rs, cons = _make()
    list(rs.procedures)
    rs.close_fallback()
    assert cons[0].closed is True


def test_close_fallback_noop_without_fallback():
    rs, cons = _make()
    list(rs.tables)          # запасное не открывали
    rs.close_fallback()      # не должно падать
    assert cons == []


@pytest.mark.parametrize("primary,expected", [
    ("UTF8", "WIN1251"), ("utf-8", "WIN1251"), ("WIN1251", "UTF8"), ("WIN1252", "UTF8"),
])
def test_fallback_charset(primary, expected):
    assert _fallback_charset(primary) == expected
